"""JWT认证中间件"""
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from database.engine import db_manager
from database.models import User, UserSession

security = HTTPBearer(auto_error=False)

class AuthMiddleware:
    """JWT认证处理"""
    
    @staticmethod
    def create_token(user_id: int, username: str, role: str) -> str:
        """创建JWT令牌"""
        expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
        payload = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "exp": expire,
            "iat": datetime.now(timezone.utc)
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    @staticmethod
    def decode_token(token: str) -> dict:
        """解码JWT令牌"""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload
        except JWTError:
            raise HTTPException(status_code=401, detail="无效的令牌")
    
    @staticmethod
    def get_token_from_request(request: Request) -> Optional[str]:
        """从请求中提取令牌"""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        # 也支持从URL参数获取
        token = request.query_params.get("token")
        return token


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    request: Request = None
) -> User:
    """获取当前登录用户（依赖注入）"""
    token = None
    if credentials:
        token = credentials.credentials
    elif request:
        token = AuthMiddleware.get_token_from_request(request)
    
    if not token:
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    
    payload = AuthMiddleware.decode_token(token)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="无效的令牌载荷")
    
    async with db_manager.get_session() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")
        if user.status != "active":
            raise HTTPException(status_code=403, detail="账户已被禁用")
        return user


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """获取当前管理员用户"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user