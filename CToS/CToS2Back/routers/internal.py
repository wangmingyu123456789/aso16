"""内部 API 路由 — 供 CToSWsChat 调用"""
from fastapi import APIRouter, Request, Depends
from middleware.auth_middleware import AuthMiddleware
from utils.helpers import success_response, error_response, logger
from middleware.internal_auth import require_internal_api_key
from database.models import User, UserSession
from sqlalchemy import select, update
from database.engine import db_manager
from datetime import datetime

router = APIRouter(prefix="/api/internal", tags=["内部API"])


@router.post("/ws-auth")
async def ws_auth(request: Request, _=Depends(require_internal_api_key)):
    """
    CToSWsChat 调用：验证 JWT Token 有效性
    返回用户基本信息（user_id, username, nickname, avatar）
    """
    try:
        body = await request.json()
    except Exception:
        return error_response("无效的请求体", 400)

    token = body.get("token", "")
    if not token:
        return error_response("缺少 token 参数", 400)

    try:
        payload = AuthMiddleware.decode_token(token)
    except Exception as e:
        logger.warning(f"WS 鉴权失败: {e}")
        return success_response(data={"valid": False, "user_id": 0})

    user_id = payload.get("user_id")
    if not user_id:
        return success_response(data={"valid": False, "user_id": 0})

    async with db_manager.get_session() as session:
        user = await session.get(User, user_id)
        if not user or user.status != "active":
            return success_response(data={"valid": False, "user_id": 0})

        return success_response(data={
            "valid": True,
            "user_id": user.id,
            "username": user.username,
            "nickname": user.nickname or "",
            "avatar": user.avatar or "",
        })


@router.post("/user-status")
async def user_status(request: Request, _=Depends(require_internal_api_key)):
    """
    CToSWsChat 调用：更新用户在线状态
    请求体: {"user_id": 1, "status": "online" | "offline"}
    """
    try:
        body = await request.json()
    except Exception:
        return error_response("无效的请求体", 400)

    user_id = body.get("user_id")
    status = body.get("status")
    if not user_id or status not in ("online", "offline"):
        return error_response("参数无效: 需要 user_id 和 status (online/offline)", 400)

    # 更新 UserSession 记录（记录最近一次在线状态变化）
    async with db_manager.get_session() as session:
        # 查找已有会话记录
        result = await session.execute(
            select(UserSession).where(UserSession.user_id == user_id).order_by(UserSession.created_at.desc()).limit(1)
        )
        existing = result.scalar_one_or_none()

        if status == "online":
            if existing:
                existing.updated_at = datetime.now()
            else:
                session.add(UserSession(
                    user_id=user_id,
                    ip_address="",
                    user_agent="CToSWsChat",
                ))
        elif status == "offline":
            if existing:
                existing.logged_out_at = datetime.now()
                existing.updated_at = datetime.now()

        await session.commit()

    logger.info(f"用户 {user_id} 状态更新为: {status}")
    return success_response(message=f"状态已更新为 {status}")