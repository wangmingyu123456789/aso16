"""派遣执行 Dispatch 模块 - 数字员工任务调度"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, desc
from typing import Optional
from database.engine import db_manager
from database.models import User, Worker, Job, ExecutionLog, ExecutionMessage, Tool, CleaningLog, WarehouseArticle
from middleware.auth_middleware import get_current_user
from utils.helpers import success_response, AppException
from utils.db_utils import fetch_paginated

router = APIRouter(prefix="/api/dispatch", tags=["派遣执行"])

class DispatchRequest(BaseModel):
    worker_id: int
    query: str

class ExecutionLogUpdate(BaseModel):
    status: str  # processing/success/error
    final_response: Optional[str] = None
    tokens_used: Optional[int] = None

class ExecutionMessageCreate(BaseModel):
    execution_log_id: int
    role: str  # system/user/assistant/tool
    content: Optional[str] = None
    tool_calls_json: Optional[str] = None
    tool_call_id: Optional[str] = None

@router.post("/execute")
async def dispatch_worker(req: DispatchRequest, user: User = Depends(get_current_user)):
    """派遣数字员工执行任务"""
    if not req.query.strip():
        raise AppException("查询内容不能为空", status_code=400)
    
    async with db_manager.get_session() as session:
        worker = await session.get(Worker, req.worker_id)
        if not worker:
            raise AppException("数字员工不存在", status_code=404)
        if not worker.enabled:
            raise AppException("该数字员工已停用", status_code=400)
        
        # 创建执行记录
        exec_log = ExecutionLog(
            worker_id=worker.id,
            user_query=req.query,
            status="processing",
        )
        session.add(exec_log)
        await session.commit()
        await session.refresh(exec_log)
        
        return success_response(data={
            "execution_log_id": exec_log.id,
            "worker_id": worker.id,
            "worker_name": worker.name,
            "query": req.query,
            "status": "processing",
            "created_at": exec_log.created_at.isoformat() if exec_log.created_at else None,
        }, message="任务已派遣")

@router.get("/logs")
async def list_execution_logs(
    page: int = 1,
    page_size: int = 20,
    worker_id: Optional[int] = None,
    status: str = "",
    user: User = Depends(get_current_user),
):
    """获取执行记录列表"""
    async with db_manager.get_session() as session:
        query = select(ExecutionLog).order_by(desc(ExecutionLog.created_at))
        if worker_id:
            query = query.where(ExecutionLog.worker_id == worker_id)
        if status:
            query = query.where(ExecutionLog.status == status)
        
        return await fetch_paginated(
            session, query, page, page_size,
            mapper=lambda log: {
                "id": log.id,
                "worker_id": log.worker_id,
                "user_query": log.user_query,
                "final_response": log.final_response,
                "status": log.status,
                "tokens_used": log.tokens_used,
                "cleaning_log_id": log.cleaning_log_id,
                "sentiment_analysis_id": log.sentiment_analysis_id,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "updated_at": log.updated_at.isoformat() if log.updated_at else None,
            }
        )

@router.get("/logs/{log_id}")
async def get_execution_log(log_id: int, user: User = Depends(get_current_user)):
    """获取执行记录详情"""
    async with db_manager.get_session() as session:
        log = await session.get(ExecutionLog, log_id)
        if not log:
            raise AppException("执行记录不存在", status_code=404)
        
        # 获取关联的工人信息
        worker = await session.get(Worker, log.worker_id)
        job = await session.get(Job, worker.job_id) if worker else None
        
        # 获取执行消息
        msgs_result = await session.execute(
            select(ExecutionMessage).where(
                ExecutionMessage.execution_log_id == log_id
            ).order_by(ExecutionMessage.created_at)
        )
        messages = msgs_result.scalars().all()
        
        return success_response(data={
            "id": log.id,
            "worker_id": log.worker_id,
            "worker_name": worker.name if worker else "未知",
            "job_name": job.name if job else "未知",
            "user_query": log.user_query,
            "final_response": log.final_response,
            "status": log.status,
            "tokens_used": log.tokens_used,
            "cleaning_log_id": log.cleaning_log_id,
            "sentiment_analysis_id": log.sentiment_analysis_id,
            "messages": [{
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "tool_calls_json": m.tool_calls_json,
                "tool_call_id": m.tool_call_id,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            } for m in messages],
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "updated_at": log.updated_at.isoformat() if log.updated_at else None,
        })

@router.put("/logs/{log_id}")
async def update_execution_log(log_id: int, req: ExecutionLogUpdate, user: User = Depends(get_current_user)):
    """更新执行记录（由数字员工回写）"""
    if req.status not in ("processing", "success", "error"):
        raise AppException("无效的状态值", status_code=400)
    
    async with db_manager.get_session() as session:
        log = await session.get(ExecutionLog, log_id)
        if not log:
            raise AppException("执行记录不存在", status_code=404)
        
        log.status = req.status
        if req.final_response is not None:
            log.final_response = req.final_response
        if req.tokens_used is not None:
            log.tokens_used = req.tokens_used
        
        await session.commit()
        return success_response(message="执行记录已更新")

@router.delete("/logs/{log_id}")
async def delete_execution_log(log_id: int, user: User = Depends(get_current_user)):
    """删除执行记录，同时级联清理关联的清洗日志和仓库文章"""
    async with db_manager.get_session() as session:
        log = await session.get(ExecutionLog, log_id)
        if not log:
            raise AppException("执行记录不存在", status_code=404)
        
        # 如果该执行记录关联了数据清洗日志，同步删除清洗日志和仓库文章
        if log.cleaning_log_id:
            # 1. 先删除关联的仓库文章（清洗后入库的）
            article_result = await session.execute(
                select(WarehouseArticle).where(
                    WarehouseArticle.cleaning_log_id == log.cleaning_log_id
                )
            )
            article = article_result.scalar_one_or_none()
            if article:
                await session.delete(article)
            
            # 2. 删除清洗日志（数据库级 ondelete=CASCADE 会自动级联删除关联的 ExecutionLog）
            cleaning_log = await session.get(CleaningLog, log.cleaning_log_id)
            if cleaning_log:
                await session.delete(cleaning_log)
                # 注意：当前 log 对象会被级联删除，不需要再手动 session.delete(log)
        else:
            # 无关联清洗日志，直接删除执行记录
            await session.delete(log)
        
        await session.commit()
        return success_response(message="执行记录及相关数据（清洗日志、仓库文章）已全部删除")

@router.post("/messages")
async def create_execution_message(req: ExecutionMessageCreate, user: User = Depends(get_current_user)):
    """创建执行消息（由数字员工回写）"""
    if req.role not in ("system", "user", "assistant", "tool"):
        raise AppException("无效的role值", status_code=400)
    
    async with db_manager.get_session() as session:
        exec_log = await session.get(ExecutionLog, req.execution_log_id)
        if not exec_log:
            raise AppException("执行记录不存在", status_code=404)
        
        msg = ExecutionMessage(
            execution_log_id=req.execution_log_id,
            role=req.role,
            content=req.content,
            tool_calls_json=req.tool_calls_json,
            tool_call_id=req.tool_call_id,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        
        return success_response(data={"id": msg.id}, message="消息已创建")

@router.get("/workers/{worker_id}/stats")
async def get_worker_stats(worker_id: int, user: User = Depends(get_current_user)):
    """获取数字员工执行统计"""
    async with db_manager.get_session() as session:
        from sqlalchemy import func
        
        total = await session.scalar(
            select(func.count(ExecutionLog.id)).where(ExecutionLog.worker_id == worker_id)
        )
        success = await session.scalar(
            select(func.count(ExecutionLog.id)).where(
                ExecutionLog.worker_id == worker_id,
                ExecutionLog.status == "success"
            )
        )
        error = await session.scalar(
            select(func.count(ExecutionLog.id)).where(
                ExecutionLog.worker_id == worker_id,
                ExecutionLog.status == "error"
            )
        )
        total_tokens = await session.scalar(
            select(func.sum(ExecutionLog.tokens_used)).where(ExecutionLog.worker_id == worker_id)
        )
        
        return success_response(data={
            "worker_id": worker_id,
            "total_executions": total or 0,
            "success_count": success or 0,
            "error_count": error or 0,
            "total_tokens_used": total_tokens or 0,
        })

@router.get("/tools")
async def list_available_tools(user: User = Depends(get_current_user)):
    """获取可用的工具列表"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Tool).order_by(Tool.name)
        )
        tools = result.scalars().all()
        return success_response(data=[{
            "id": t.id, "name": t.name,
            "description": t.description,
            "function_schema": t.function_schema,
            "is_builtin": t.is_builtin,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        } for t in tools])