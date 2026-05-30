"""系统管理 Admin 模块"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, desc, func, text
from sqlalchemy.ext.asyncio import create_async_engine
from database.engine import db_manager
from database.models import User, SystemConfig, ApiKey, SystemLog, TokenStat
from database.migration import migration
from config import settings
from middleware.auth_middleware import get_current_user, get_admin_user
from utils.helpers import success_response, AppException, logger
from utils.db_utils import fetch_paginated

router = APIRouter(prefix="/api/admin", tags=["系统管理"])

# ===== 用户管理 =====

class CreateUserRequest(BaseModel):
    username: str
    password: str
    nickname: str = ""
    role: str = "user"

@router.get("/users")
async def list_users(page: int = 1, page_size: int = 20, admin: User = Depends(get_admin_user)):
    """用户列表"""
    async with db_manager.get_session() as session:
        return await fetch_paginated(
            session, select(User).order_by(desc(User.created_at)), page, page_size,
            mapper=lambda u: {
                "id": u.id, "username": u.username, "nickname": u.nickname,
                "role": u.role, "status": u.status,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
        )

class UpdateUserStatusRequest(BaseModel):
    user_id: int
    status: str

@router.put("/users/status")
async def update_user_status(req: UpdateUserStatusRequest, admin: User = Depends(get_admin_user)):
    """更新用户状态"""
    if req.status not in ("active", "disabled", "banned"):
        raise AppException("无效的状态值")
    async with db_manager.get_session() as session:
        user = await session.get(User, req.user_id)
        if not user:
            raise AppException("用户不存在", status_code=404)
        user.status = req.status
        await session.commit()
        return success_response(message="用户状态已更新")

@router.post("/users")
async def create_user(req: CreateUserRequest, admin: User = Depends(get_admin_user)):
    """创建用户"""
    from utils.helpers import hash_password
    if req.role not in ("user", "admin"):
        raise AppException("无效的角色值，可选: user/admin")
    if len(req.password) < 6:
        raise AppException("密码长度至少6位")
    async with db_manager.get_session() as session:
        existing = await session.execute(select(User).where(User.username == req.username))
        if existing.scalar_one_or_none():
            raise AppException("用户名已存在", status_code=409)
        user = User(
            username=req.username,
            password_hash=hash_password(req.password),
            nickname=req.nickname or req.username,
            role=req.role,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return success_response(data={"id": user.id}, message="用户创建成功")

class UpdateUserRoleRequest(BaseModel):
    role: str

@router.put("/users/{user_id}/role")
async def update_user_role(user_id: int, req: UpdateUserRoleRequest, admin: User = Depends(get_admin_user)):
    """修改用户角色"""
    if req.role not in ("user", "admin"):
        raise AppException("无效的角色值，可选: user/admin")
    async with db_manager.get_session() as session:
        user = await session.get(User, user_id)
        if not user:
            raise AppException("用户不存在", status_code=404)
        if user.role == "worker":
            raise AppException("不可修改数字员工角色")
        user.role = req.role
        await session.commit()
        return success_response(message="用户角色已更新")

@router.delete("/users/{user_id}")
async def delete_user(user_id: int, admin: User = Depends(get_admin_user)):
    """删除用户"""
    async with db_manager.get_session() as session:
        user = await session.get(User, user_id)
        if not user:
            raise AppException("用户不存在", status_code=404)
        if user.role == "root":
            raise AppException("不可删除超级管理员")
        if user.id == admin.id:
            raise AppException("不可删除自己")
        await session.delete(user)
        await session.commit()
        return success_response(message="用户已删除")


# ===== 系统配置 =====

@router.get("/configs")
async def list_configs(admin: User = Depends(get_admin_user)):
    """获取系统配置"""
    async with db_manager.get_session() as session:
        result = await session.execute(select(SystemConfig))
        configs = result.scalars().all()
        return success_response(data=[{
            "key": c.key, "value": c.value,
        } for c in configs])

class UpdateConfigRequest(BaseModel):
    key: str
    value: str

@router.put("/configs")
async def update_config(req: UpdateConfigRequest, admin: User = Depends(get_admin_user)):
    """更新系统配置"""
    async with db_manager.get_session() as session:
        result = await session.execute(select(SystemConfig).where(SystemConfig.key == req.key))
        config = result.scalar_one_or_none()
        if config:
            config.value = req.value
        else:
            config = SystemConfig(key=req.key, value=req.value)
            session.add(config)
        await session.commit()
        return success_response(message="配置已更新")


# ===== API密钥管理 =====

@router.get("/api-keys")
async def list_api_keys(admin: User = Depends(get_admin_user)):
    """获取API密钥列表"""
    async with db_manager.get_session() as session:
        result = await session.execute(select(ApiKey).order_by(desc(ApiKey.created_at)))
        keys = result.scalars().all()
        return success_response(data=[{
            "id": k.id, "name": k.name, "provider": k.provider,
            "base_url": k.base_url,
            "model_name": k.model_name, "purpose": k.purpose,
            "max_tokens": k.max_tokens, "temperature": k.temperature, "top_p": k.top_p,
            "enabled": k.enabled, "sort_order": k.sort_order,
            "created_at": k.created_at.isoformat() if k.created_at else None,
        } for k in keys])

@router.get("/api-keys/{key_id}")
async def get_api_key(key_id: int, admin: User = Depends(get_admin_user)):
    """获取API密钥详情（屏蔽敏感 api_key 字段）"""
    async with db_manager.get_session() as session:
        key = await session.get(ApiKey, key_id)
        if not key:
            raise AppException("API密钥不存在", status_code=404)
        return success_response(data={
            "id": key.id, "name": key.name, "provider": key.provider,
            "base_url": key.base_url,
            "model_name": key.model_name, "purpose": key.purpose,
            "max_tokens": key.max_tokens, "temperature": key.temperature, "top_p": key.top_p,
            "enabled": key.enabled, "sort_order": key.sort_order,
            "created_at": key.created_at.isoformat() if key.created_at else None,
            "updated_at": key.updated_at.isoformat() if key.updated_at else None,
        })

class CreateApiKeyRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    name: str
    provider: str = "openai"
    base_url: str = ""
    api_key: str
    model_name: str = ""
    purpose: str = "chat"
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 1.0
    sort_order: int = 0

class UpdateApiKeyRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    name: str = None
    provider: str = None
    base_url: str = None
    api_key: str = None
    model_name: str = None
    purpose: str = None
    max_tokens: int = None
    temperature: float = None
    top_p: float = None
    enabled: int = None
    sort_order: int = None

@router.post("/api-keys")
async def create_api_key(req: CreateApiKeyRequest, admin: User = Depends(get_admin_user)):
    """创建API密钥（含高级参数）"""
    if not req.api_key:
        raise AppException("API Key 不能为空")
    async with db_manager.get_session() as session:
        key = ApiKey(
            name=req.name, provider=req.provider,
            base_url=req.base_url, api_key=req.api_key,
            model_name=req.model_name, purpose=req.purpose,
            max_tokens=req.max_tokens, temperature=req.temperature,
            top_p=req.top_p, sort_order=req.sort_order,
        )
        session.add(key)
        await session.commit()
        await session.refresh(key)
        return success_response(data={"id": key.id}, message="API密钥创建成功")

@router.put("/api-keys/{key_id}")
async def update_api_key(key_id: int, req: UpdateApiKeyRequest, admin: User = Depends(get_admin_user)):
    """编辑API密钥"""
    async with db_manager.get_session() as session:
        key = await session.get(ApiKey, key_id)
        if not key:
            raise AppException("API密钥不存在", status_code=404)
        if req.name is not None:
            key.name = req.name
        if req.provider is not None:
            key.provider = req.provider
        if req.base_url is not None:
            key.base_url = req.base_url
        if req.api_key is not None:
            key.api_key = req.api_key
        if req.model_name is not None:
            key.model_name = req.model_name
        if req.purpose is not None:
            key.purpose = req.purpose
        if req.max_tokens is not None:
            key.max_tokens = req.max_tokens
        if req.temperature is not None:
            key.temperature = req.temperature
        if req.top_p is not None:
            key.top_p = req.top_p
        if req.enabled is not None:
            key.enabled = req.enabled
        if req.sort_order is not None:
            key.sort_order = req.sort_order
        await session.commit()
        return success_response(message="API密钥已更新")

@router.delete("/api-keys/{key_id}")
async def delete_api_key(key_id: int, admin: User = Depends(get_admin_user)):
    """删除API密钥"""
    async with db_manager.get_session() as session:
        key = await session.get(ApiKey, key_id)
        if not key:
            raise AppException("API密钥不存在", status_code=404)
        # 检查是否有 Worker 引用此 Key
        from database.models import Worker
        ref_result = await session.execute(
            select(Worker).where(Worker.api_key_id == key_id).limit(1)
        )
        if ref_result.scalar_one_or_none():
            raise AppException("有数字员工正在使用此API密钥，请先切换或删除员工", status_code=400)
        await session.delete(key)
        await session.commit()
        return success_response(message="API密钥已删除")

@router.put("/api-keys/{key_id}/toggle")
async def toggle_api_key(key_id: int, admin: User = Depends(get_admin_user)):
    """启用/禁用API密钥"""
    async with db_manager.get_session() as session:
        key = await session.get(ApiKey, key_id)
        if not key:
            raise AppException("API密钥不存在", status_code=404)
        key.enabled = 1 - key.enabled
        await session.commit()
        status_text = "已启用" if key.enabled else "已禁用"
        return success_response(data={"enabled": key.enabled}, message=f"API密钥{status_text}")


# ===== Token 统计 =====

@router.get("/token-stats/daily")
async def get_token_stats_daily(days: int = 30, admin: User = Depends(get_admin_user)):
    """Token 日统计"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(
                TokenStat.date,
                func.sum(TokenStat.tokens_used).label("total"),
                func.count(func.distinct(TokenStat.user_id)).label("active_users"),
            )
            .group_by(TokenStat.date)
            .order_by(desc(TokenStat.date))
            .limit(days)
        )
        data = [{"date": row[0], "total_tokens": row[1] or 0, "active_users": row[2] or 0} for row in result]
        data.reverse()
        return success_response(data=data)

@router.get("/token-stats/users")
async def get_token_stats_users(limit: int = 20, admin: User = Depends(get_admin_user)):
    """Token 用户排行"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(
                TokenStat.user_id,
                User.username,
                func.sum(TokenStat.tokens_used).label("total"),
            )
            .join(User, TokenStat.user_id == User.id)
            .group_by(TokenStat.user_id)
            .order_by(desc("total"))
            .limit(limit)
        )
        data = [{"user_id": row[0], "username": row[1], "total_tokens": row[2] or 0} for row in result]
        return success_response(data=data)


# ===== 操作日志 =====

# ===== 数据库管理（多数据库支持与切换） =====

@router.get("/database/status")
async def get_database_status(admin: User = Depends(get_admin_user)):
    """获取数据库连接状态和配置信息"""
    return success_response(data={
        "active_database": settings.ACTIVE_DATABASE,
        "db_type": settings.DB_TYPE,
        "mysql_config": {
            "host": settings.MYSQL_HOST,
            "port": settings.MYSQL_PORT,
            "database": settings.MYSQL_DATABASE,
            "user": settings.MYSQL_USER,
        },
        "sqlite_config": {
            "path": settings.SQLITE_PATH,
        },
        "engine_status": "connected" if db_manager._engine else "disconnected",
        "available_databases": ["sqlite", "mysql"],
    })


class UpdateMySQLConfigRequest(BaseModel):
    """更新MySQL配置请求"""
    host: str = None
    port: int = None
    user: str = None
    password: str = None
    database: str = None


@router.put("/database/mysql-config")
async def update_mysql_config(req: UpdateMySQLConfigRequest, admin: User = Depends(get_admin_user)):
    """更新MySQL数据库连接配置（保存到内存，重启后失效，如需持久化请修改.env文件）"""
    from utils.helpers import logger as _log
    if req.host is not None:
        settings.MYSQL_HOST = req.host
    if req.port is not None:
        settings.MYSQL_PORT = req.port
    if req.user is not None:
        settings.MYSQL_USER = req.user
    if req.password is not None:
        settings.MYSQL_PASSWORD = req.password
    if req.database is not None:
        settings.MYSQL_DATABASE = req.database
    
    _log.info(f"🔧 管理员 {admin.username} 更新了MySQL配置")
    return success_response(message="MySQL配置已更新，可尝试切换数据库验证连接")


class SwitchDatabaseRequest(BaseModel):
    """切换数据库请求"""
    db_type: str  # "sqlite" 或 "mysql"

@router.post("/database/switch")
async def switch_database(req: SwitchDatabaseRequest, admin: User = Depends(get_admin_user)):
    """切换数据库（全自动：检查→建库→建表→数据迁移→切库）"""
    if req.db_type not in ("sqlite", "mysql"):
        raise AppException("不支持的数据库类型，可选: sqlite, mysql")
    
    if req.db_type == settings.ACTIVE_DATABASE:
        return success_response(message=f"已经是 {req.db_type} 数据库，无需切换")
    
    source_type = settings.ACTIVE_DATABASE
    
    try:
        if req.db_type == "mysql":
            # 1. 自动检查并创建数据库（若不存在）
            await db_manager.ensure_mysql_database()
            
            # 2. 在目标库创建表结构
            target_url = db_manager.get_url("mysql")
            target_engine = create_async_engine(target_url, echo=False)
            from database.models import Base
            async with target_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await target_engine.dispose()
            
            # 3. 数据迁移：从源库（SQLite）读取 → 写入目标库（MySQL）
            logger.info(f"📦 自动迁移数据: {source_type} → {req.db_type}")
            
            # 读取源库数据
            source_data = await migration._read_source_data(source_type)
            if source_data and any(rows for rows in source_data.values()):
                # 写入目标库
                target_data_url = db_manager.get_url(req.db_type)
                data_target_engine = create_async_engine(target_data_url, echo=False)
                try:
                    async with data_target_engine.connect() as conn:
                        from sqlalchemy import text as sa_t
                        for table_name in migration.TABLE_ORDER:
                            rows = source_data.get(table_name, [])
                            if not rows:
                                continue
                            # 清空目标表（覆写）
                            try:
                                await conn.execute(sa_t(f"DELETE FROM {table_name}"))
                            except Exception:
                                pass  # 表可能不存在
                            # 插入数据（列名加反引号，避免 MySQL 保留字冲突如 key）
                            for row in rows:
                                cols = list(row.keys())
                                placeholders = ", ".join([f":{c}" for c in cols])
                                col_names = ", ".join([f"`{c}`" for c in cols])
                                clean = {}
                                for k, v in row.items():
                                    from datetime import datetime
                                    clean[k] = v if not isinstance(v, datetime) else v
                                stmt = sa_t(f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})")
                                await conn.execute(stmt, clean)
                            await conn.commit()
                            logger.info(f"  ✅ {table_name}: {len(rows)} 条")
                finally:
                    await data_target_engine.dispose()
                logger.info(f"✅ 数据迁移完成")
            else:
                logger.info(f"ℹ️ 源数据库无数据，跳过迁移")
        else:
            # SQLite 不需要建库，直接测试
            test_url = db_manager.get_url("sqlite")
            test_engine = create_async_engine(test_url, echo=False)
            async with test_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await test_engine.dispose()
        
        # 4. 切换数据库连接
        await db_manager.switch_database(req.db_type)
        
        # 5. 更新配置对象
        settings.ACTIVE_DATABASE = req.db_type
        
        logger.info(f"🔄 管理员 {admin.username} 将数据库切换为: {req.db_type}")
        return success_response(
            data={"active_database": req.db_type},
            message=f"数据库已切换到 {req.db_type}，数据已自动迁移"
        )
    except Exception as e:
        err_msg = str(e)
        if "Unknown database" in err_msg:
            raise AppException(
                f"❌ MySQL 自动创建数据库失败。\n"
                f"请检查 MySQL 连接权限，或手动创建数据库：\n"
                f"  CREATE DATABASE `{settings.MYSQL_DATABASE}` CHARACTER SET utf8mb4;"
            )
        if "Access denied" in err_msg or "1045" in err_msg:
            raise AppException(
                f"❌ MySQL 连接被拒绝。\n"
                f"请检查用户名和密码是否正确。"
            )
        raise AppException(f"切换失败: {err_msg}")


class MigrateDatabaseRequest(BaseModel):
    """迁移数据库请求"""
    target_db: str  # "sqlite" 或 "mysql"

@router.post("/database/migrate")
async def migrate_database(req: MigrateDatabaseRequest, admin: User = Depends(get_admin_user)):
    """执行数据库迁移（SQLite ↔ MySQL 数据互迁）"""
    if req.target_db not in ("sqlite", "mysql"):
        raise AppException("不支持的数据库类型，可选: sqlite, mysql")
    
    if req.target_db == settings.ACTIVE_DATABASE:
        raise AppException(
            f"目标数据库与当前数据库相同（{req.target_db}），"
            "请先切换到另一个数据库再进行迁移"
        )
    
    logger.info(f"🔄 管理员 {admin.username} 启动数据库迁移: {settings.ACTIVE_DATABASE} → {req.target_db}")
    
    # 在后台任务中执行迁移，防止超时
    result = await migration.migrate(req.target_db)
    
    return success_response(data=result, message="数据库迁移任务已完成")


@router.get("/database/migration/progress")
async def get_migration_progress(admin: User = Depends(get_admin_user)):
    """获取数据库迁移进度"""
    return success_response(data=migration.progress)


@router.get("/logs")
async def list_logs(page: int = 1, page_size: int = 20, action: str = "",
                    admin: User = Depends(get_admin_user)):
    """操作日志列表"""
    async with db_manager.get_session() as session:
        query = select(SystemLog).order_by(desc(SystemLog.created_at))
        if action:
            query = query.where(SystemLog.action == action)
        return await fetch_paginated(
            session, query, page, page_size,
            mapper=lambda l: {
                "id": l.id, "user_id": l.user_id,
                "action": l.action, "target": l.target,
                "detail": l.detail, "ip_address": l.ip_address,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
        )