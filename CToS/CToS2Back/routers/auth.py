"""用户认证模块"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from database.engine import db_manager
from database.models import User, SystemConfig
from middleware.auth_middleware import AuthMiddleware, get_current_user
from utils.helpers import success_response, error_response, AppException, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["认证"])

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    nickname: str = ""

@router.post("/login")
async def login(req: LoginRequest):
    """用户登录"""
    async with db_manager.get_session() as session:
        result = await session.execute(select(User).where(User.username == req.username))
        user = result.scalar_one_or_none()

        if not user:
            raise AppException("用户名或密码错误", status_code=401)

        if user.status != "active":
            raise AppException("账户已被禁用", status_code=403)

        if not user.password_hash:
            raise AppException("该账户不能通过密码登录", status_code=401)

        if not verify_password(req.password, user.password_hash):
            raise AppException("用户名或密码错误", status_code=401)

        token = AuthMiddleware.create_token(user.id, user.username, user.role)

        return success_response(data={
            "token": token,
            "user": {
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "avatar": user.avatar,
                "role": user.role,
            }
        }, message="登录成功")

@router.post("/register")
async def register(req: RegisterRequest):
    """用户注册"""
    # 检查是否允许注册
    async with db_manager.get_session() as session:
        config_result = await session.execute(select(SystemConfig).where(SystemConfig.key == "disable_register"))
        config = config_result.scalar_one_or_none()
        if config and config.value == "true":
            raise AppException("当前系统已关闭注册功能", status_code=403)

        # 检查用户名是否已存在
        result = await session.execute(select(User).where(User.username == req.username))
        if result.scalar_one_or_none():
            raise AppException("用户名已存在", status_code=409)

        # 创建用户
        user = User(
            username=req.username,
            password_hash=hash_password(req.password),
            nickname=req.nickname or req.username,
            role="user",
            status="active",
        )
        session.add(user)
        await session.commit()

        return success_response(message="注册成功", data={"username": user.username})

@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return success_response(data={
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "role": user.role,
    })

@router.post("/logout")
async def logout(user: User = Depends(get_current_user)):
    """用户登出（JWT无状态，客户端清除token即可）"""
    return success_response(message="登出成功")