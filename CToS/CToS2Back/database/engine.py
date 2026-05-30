"""数据库引擎 - 支持SQLite/MySQL双数据库"""
import time
from typing import Optional
from sqlalchemy import event, text as sa_text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from config import settings
from utils.helpers import logger

class DatabaseManager:
    """数据库管理器，支持SQLite/MySQL切换"""
    
    def __init__(self):
        self._engine = None
        self._session_factory = None
    
    def get_url(self, db_type: Optional[str] = None) -> str:
        """获取数据库URL"""
        target = db_type or settings.ACTIVE_DATABASE
        if target == "mysql":
            return f"mysql+aiomysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}?charset=utf8mb4"
        import os
        db_path = settings.SQLITE_PATH
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        return f"sqlite+aiosqlite:///{db_path}"
    
    async def init(self, db_type: Optional[str] = None):
        """初始化数据库引擎"""
        url = self.get_url(db_type)
        self._engine = create_async_engine(url, echo=False, future=True)
        self._session_factory = async_sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)
        
        # 如果是SQLite，启用WAL模式和外键
        if "sqlite" in url:
            @event.listens_for(self._engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA busy_timeout=5000")
                cursor.close()
    
    async def ensure_mysql_database(self):
        """确保MySQL数据库存在，不存在则自动创建"""
        try:
            # 先连接mysql（不指定数据库），检查并创建数据库
            no_db_url = f"mysql+aiomysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}"
            temp_engine = create_async_engine(no_db_url, echo=False)
            async with temp_engine.connect() as conn:
                db_name = settings.MYSQL_DATABASE
                result = await conn.execute(
                    sa_text(f"SELECT SCHEMA_NAME FROM information_schema.schemata WHERE SCHEMA_NAME = '{db_name}'")
                )
                exists = result.scalar()
                if not exists:
                    await conn.execute(sa_text(
                        f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    ))
                    logger.info(f"✅ MySQL 数据库 '{db_name}' 已自动创建")
                else:
                    logger.info(f"ℹ️ MySQL 数据库 '{db_name}' 已存在")
                await conn.commit()
            await temp_engine.dispose()
            return True
        except Exception as e:
            logger.error(f"❌ 确保MySQL数据库存在时出错: {e}")
            raise

    async def create_all_tables(self):
        """创建所有表（基于ORM模型）"""
        from database.models import Base
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ 数据库表已创建/同步")

    async def switch_database(self, db_type: str):
        """切换数据库"""
        if self._engine:
            await self._engine.dispose()
        
        if db_type == "mysql":
            # 先确保MySQL数据库存在
            await self.ensure_mysql_database()
        
        await self.init(db_type)
        
        # 切换后自动创建表结构
        await self.create_all_tables()
    
    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        if not self._session_factory:
            raise RuntimeError("数据库未初始化，请先调用 init()")
        return self._session_factory
    
    def get_session(self) -> AsyncSession:
        return self.session_factory()

db_manager = DatabaseManager()

async def init_db():
    """初始化数据库（供应用启动时调用）"""
    from database.models import Base
    await db_manager.init()
    async with db_manager._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 连表创建后，插入预设种子数据
    from database.seeds import seed_default_data
    await seed_default_data()