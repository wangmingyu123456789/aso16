"""内部 API 鉴权中间件 — 识别 CToSWsChat 的调用请求"""
from fastapi import Request, HTTPException, Depends
from sqlalchemy import select
from config import settings
from database.engine import db_manager
from database.models import User


async def verify_internal_api_key(request: Request) -> bool:
    """验证请求头中的 X-Internal-Api-Key 是否匹配"""
    api_key = request.headers.get("X-Internal-Api-Key", "")
    return api_key == settings.WS_INTERNAL_API_KEY


async def require_internal_api_key(request: Request):
    """依赖注入：要求请求携带有效的内部 API Key"""
    if not await verify_internal_api_key(request):
        raise HTTPException(status_code=403, detail="无效的内部 API Key")


async def get_internal_user(request: Request) -> User:
    """
    内部调用获取代理用户。
    CToSWsChat 代理客户端调用时使用此依赖：
      - X-Internal-Api-Key 验证身份
      - X-Internal-User-Id 指定代理的用户
    此依赖会跳过 JWT 验证，直接以 X-Internal-User-Id 作为当前用户。
    """
    # 1. 验证 API Key
    if not await verify_internal_api_key(request):
        raise HTTPException(status_code=403, detail="无效的内部 API Key")

    # 2. 获取代理用户 ID
    proxy_user_id_str = request.headers.get("X-Internal-User-Id")
    if not proxy_user_id_str:
        raise HTTPException(status_code=400, detail="缺少 X-Internal-User-Id 请求头")

    try:
        proxy_user_id = int(proxy_user_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="X-Internal-User-Id 必须是整数")

    # 3. 从数据库加载用户
    async with db_manager.get_session() as session:
        user = await session.get(User, proxy_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="代理用户不存在")
        if user.status != "active":
            raise HTTPException(status_code=403, detail="代理用户已被禁用")
        return user