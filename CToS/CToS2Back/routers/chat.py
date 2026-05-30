"""智能问数 Chat 模块"""
import json
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, desc
from database.engine import db_manager
from database.models import User, Conversation, Message
from middleware.auth_middleware import get_current_user
from utils.helpers import success_response, error_response, AppException, logger
from services.llm_service import call_llm_stream, select_api_key, record_token_usage
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/chat", tags=["智能问数"])

# 存储正在进行的流式任务，用于中断
_active_streams: dict[int, asyncio.Event] = {}

class CreateConversationRequest(BaseModel):
    title: str = "新对话"

class RenameConversationRequest(BaseModel):
    title: str

class SendMessageRequest(BaseModel):
    content: str

class MessageRequest(BaseModel):
    content: str
    conversation_id: int

class StopRequest(BaseModel):
    conversation_id: int


@router.get("/conversations")
async def list_conversations(user: User = Depends(get_current_user)):
    """获取对话列表"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Conversation).where(Conversation.user_id == user.id)
            .order_by(desc(Conversation.updated_at))
            .limit(50)
        )
        conversations = result.scalars().all()
        return success_response(data=[{
            "id": c.id,
            "title": c.title,
            "model_name": c.model_name,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        } for c in conversations])


@router.post("/conversations")
async def create_conversation(req: CreateConversationRequest, user: User = Depends(get_current_user)):
    """创建新对话"""
    async with db_manager.get_session() as session:
        conv = Conversation(user_id=user.id, title=req.title)
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        return success_response(data={"id": conv.id, "title": conv.title}, message="对话创建成功")


@router.delete("/conversation/{conv_id}")
async def delete_conversation(conv_id: int, user: User = Depends(get_current_user)):
    """删除对话"""
    async with db_manager.get_session() as session:
        conv = await session.get(Conversation, conv_id)
        if not conv:
            raise AppException("对话不存在", status_code=404)
        if conv.user_id != user.id:
            raise AppException("无权删除此对话", status_code=403)
        await session.delete(conv)
        await session.commit()
        return success_response(message="对话已删除")


@router.put("/conversation/{conv_id}")
async def rename_conversation(conv_id: int, req: RenameConversationRequest, user: User = Depends(get_current_user)):
    """重命名对话"""
    async with db_manager.get_session() as session:
        conv = await session.get(Conversation, conv_id)
        if not conv:
            raise AppException("对话不存在", status_code=404)
        if conv.user_id != user.id:
            raise AppException("无权修改此对话", status_code=403)
        conv.title = req.title
        await session.commit()
        return success_response(message="对话已重命名")


@router.get("/conversations/{conv_id}/messages")
async def get_messages(conv_id: int, user: User = Depends(get_current_user)):
    """获取对话消息历史"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Message).where(Message.conversation_id == conv_id)
            .order_by(Message.created_at)
            .limit(100)
        )
        messages = result.scalars().all()
        return success_response(data=[{
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        } for m in messages])


@router.post("/conversations/{conv_id}/messages")
async def send_message(conv_id: int, req: SendMessageRequest, user: User = Depends(get_current_user)):
    """发送消息（用户消息）"""
    async with db_manager.get_session() as session:
        # 校验对话存在性
        conv = await session.get(Conversation, conv_id)
        if not conv:
            raise AppException("对话不存在", status_code=404)
        if conv.user_id != user.id:
            raise AppException("无权向此对话发送消息", status_code=403)
        
        msg = Message(conversation_id=conv_id, role="user", content=req.content)
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return success_response(data={
            "id": msg.id,
            "role": "user",
            "content": msg.content,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }, message="消息已发送")


@router.post("/message")
async def send_chat_message(req: MessageRequest, user: User = Depends(get_current_user)):
    """发送消息（SSE流式AI回复）"""
    conversation_id = req.conversation_id

    # 创建中断事件
    stop_event = asyncio.Event()
    _active_streams[conversation_id] = stop_event

    async def generate():
        full_response = ""
        try:
            # 获取对话历史
            async with db_manager.get_session() as session:
                # 校验对话存在性
                conv = await session.get(Conversation, conversation_id)
                if not conv:
                    yield f"data: {json.dumps({'type': 'error', 'content': '对话不存在'}, ensure_ascii=False)}\n\n"
                    return
                if conv.user_id != user.id:
                    yield f"data: {json.dumps({'type': 'error', 'content': '无权使用此对话'}, ensure_ascii=False)}\n\n"
                    return

                # 保存用户消息
                user_msg = Message(
                    conversation_id=conversation_id,
                    role="user",
                    content=req.content
                )
                session.add(user_msg)

                # 获取历史消息构建 messages 列表
                result = await session.execute(
                    select(Message).where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at)
                )
                history = result.scalars().all()

                # 构建 LLM 消息列表
                messages = []
                for m in history:
                    messages.append({"role": m.role, "content": m.content or ""})

                await session.commit()

            # 流式调用 LLM
            ai_message_id = None
            async with db_manager.get_session() as session:
                ai_msg = Message(conversation_id=conversation_id, role="assistant", content="")
                session.add(ai_msg)
                await session.commit()
                await session.refresh(ai_msg)
                ai_message_id = ai_msg.id

            # 使用流式调用
            async for chunk in call_llm_stream(messages, purpose="chat"):
                if stop_event.is_set():
                    break
                full_response += chunk
                yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

            # 保存完整回复
            async with db_manager.get_session() as session:
                ai_msg_db = await session.get(Message, ai_message_id)
                if ai_msg_db:
                    ai_msg_db.content = full_response
                    await session.commit()

            # 发送完成信号
            meta = {
                "type": "meta",
                "conversation_id": conversation_id,
                "message_id": ai_message_id,
                "content": full_response,
            }
            yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"SSE流式错误: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            _active_streams.pop(conversation_id, None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/message/stop")
async def stop_chat_message(req: StopRequest):
    """中断流式AI回复"""
    conversation_id = req.conversation_id
    stop_event = _active_streams.get(conversation_id)
    if stop_event:
        stop_event.set()
        return success_response(message="已中断流式回复")
    return success_response(message="当前无活跃流式回复")