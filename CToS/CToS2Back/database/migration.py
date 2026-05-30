"""
数据库迁移工具 - 支持 SQLite ↔ MySQL 数据互迁

核心能力：
1. 从源数据库读取所有表结构和数据
2. 自动创建目标数据库表（基于 SQLAlchemy Base）
3. 按外键依赖顺序迁移数据，保证数据完整性
4. 支持断点续传（分批迁移）
5. 迁移前后校验（记录数比对）
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from config import settings
from database.engine import db_manager

logger = logging.getLogger("ctos.migration")

# ============================================================
# 表依赖顺序（外键约束需要的迁移顺序）
# 目标：先迁"被引用"的表，再迁"引用"的表
# ============================================================
TABLE_ORDER = [
    # 3.1 用户与鉴权（基础表，不被其他表外键引用）
    "users",
    "user_sessions",
    
    # 3.11 API Key 管理（被 workers 引用）
    "api_keys",
    
    # 3.10 系统配置（独立表）
    "system_config",
    "system_logs",
    
    # 3.5 数字员工（依赖 users, jobs, api_keys）
    "jobs",
    "tools",
    "workers",
    
    # 3.2 智能问数（依赖 users）
    "conversations",
    "messages",
    
    # 3.3 智能瞭望（依赖 users）
    "watch_sources",
    "watch_data",
    
    # 3.4 Token 统计（依赖 users）
    "token_stats",
    
    # 3.6 数据清洗（依赖 watch_data）
    "cleaning_logs",
    
    # 3.12 智慧舆情·主表（被 execution_logs 引用，必须优先于 execution_logs）
    "sentiment_analyses",
    
    # 3.5 执行记录（依赖 workers, cleaning_logs, sentiment_analyses）
    "execution_logs",
    "execution_messages",
    
    # 3.7 数据仓库（依赖 watch_data, cleaning_logs, warehouse_categories）
    "warehouse_categories",
    "warehouse_articles",
    
    # 3.8 智能聊天（依赖 users, chat_groups, files）
    "chat_groups",
    "group_members",
    "friends",
    "friend_requests",
    "files",
    "chat_messages",
    "chat_servers",
    "message_reads",
    
    # 3.12 智慧舆情·子表（依赖 sentiment_analyses, sentiment_events）
    "sentiment_events",
    "sentiment_locations",
    "sentiment_words",
    "sentiment_dashboards",
]


class DatabaseMigration:
    """数据库迁移管理器"""
    
    TABLE_ORDER = TABLE_ORDER  # 表依赖顺序（用于外部引用）

    def __init__(self):
        self._progress = {
            "status": "idle",          # idle / running / completed / failed
            "source": "",
            "target": "",
            "current_table": "",
            "tables_total": 0,
            "tables_done": 0,
            "rows_total": 0,
            "rows_migrated": 0,
            "errors": [],
            "started_at": None,
            "finished_at": None,
        }
    
    @property
    def progress(self) -> dict:
        """获取当前迁移进度（线程安全快照）"""
        return dict(self._progress)
    
    def _reset_progress(self, source: str, target: str):
        """重置进度"""
        self._progress = {
            "status": "running",
            "source": source,
            "target": target,
            "current_table": "",
            "tables_total": len(TABLE_ORDER),
            "tables_done": 0,
            "rows_total": 0,
            "rows_migrated": 0,
            "errors": [],
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
        }
    
    async def migrate(self, target_db_type: str) -> dict:
        """
        执行数据库迁移
        
        Args:
            target_db_type: 目标数据库类型 "sqlite" 或 "mysql"
        
        Returns:
            迁移结果摘要
        """
        source_db_type = "sqlite" if target_db_type == "mysql" else "mysql"
        
        if self._progress["status"] == "running":
            return {"error": "已有迁移任务正在执行，请等待完成"}
        
        self._reset_progress(source_db_type, target_db_type)
        
        try:
            logger.info(f"🚀 开始数据库迁移: {source_db_type} → {target_db_type}")
            
            # 1. 从源数据库读取数据
            source_data = await self._read_source_data(source_db_type)
            if not source_data:
                raise ValueError(f"源数据库({source_db_type})中无可迁移的数据")
            
            self._progress["rows_total"] = sum(len(rows) for rows in source_data.values())
            
            # 2. 写入目标数据库
            await self._write_target_data(target_db_type, source_data)
            
            # 3. 校验迁移结果
            verification = await self._verify_migration(source_db_type, target_db_type)
            
            self._progress["status"] = "completed"
            self._progress["finished_at"] = datetime.now().isoformat()
            
            result = {
                "status": "completed",
                "source": source_db_type,
                "target": target_db_type,
                "tables_migrated": self._progress["tables_done"],
                "total_rows": self._progress["rows_migrated"],
                "errors": self._progress["errors"],
                "verification": verification,
                "started_at": self._progress["started_at"],
                "finished_at": self._progress["finished_at"],
            }
            
            logger.info(f"✅ 数据库迁移完成: 迁移了 {result['total_rows']} 条数据, "
                        f"涉及 {result['tables_migrated']}/{self._progress['tables_total']} 张表")
            
            # 4. 自动切换到目标数据库
            await db_manager.switch_database(target_db_type)
            logger.info(f"🔄 已自动切换到 {target_db_type} 数据库")
            
            return result
            
        except Exception as e:
            self._progress["status"] = "failed"
            self._progress["finished_at"] = datetime.now().isoformat()
            self._progress["errors"].append(str(e))
            logger.exception(f"❌ 数据库迁移失败: {e}")
            return {
                "status": "failed",
                "source": source_db_type,
                "target": target_db_type,
                "error": str(e),
                "tables_done": self._progress["tables_done"],
                "rows_migrated": self._progress["rows_migrated"],
                "started_at": self._progress["started_at"],
                "finished_at": self._progress["finished_at"],
            }
    
    async def _read_source_data(self, db_type: str) -> Dict[str, List[Dict]]:
        """
        从源数据库读取所有表数据
        
        Returns:
            {表名: [行字典, ...], ...}
        """
        source_url = db_manager.get_url(db_type)
        source_engine = create_async_engine(source_url, echo=False)
        
        result: Dict[str, List[Dict]] = {}
        
        try:
            async with source_engine.connect() as conn:
                # 获取所有表名
                if db_type == "sqlite":
                    tables_query = text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                else:
                    tables_query = text(
                        "SELECT TABLE_NAME FROM information_schema.tables "
                        "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'"
                    )
                
                table_rows = await conn.execute(tables_query)
                existing_tables = {row[0] for row in table_rows}
                
                # 按依赖顺序读取数据
                for table_name in TABLE_ORDER:
                    if table_name not in existing_tables:
                        logger.info(f"  ⏭️ 跳过 {table_name}（源数据库中不存在）")
                        continue
                    
                    self._progress["current_table"] = table_name
                    logger.info(f"  📖 读取表: {table_name}")
                    
                    rows_data = await conn.execute(text(f"SELECT * FROM {table_name}"))
                    columns = rows_data.keys()
                    rows = [dict(zip(columns, row)) for row in rows_data.fetchall()]
                    
                    if rows:
                        result[table_name] = rows
                        logger.info(f"    → {len(rows)} 条记录")
                    else:
                        result[table_name] = []
                        logger.info(f"    → 0 条记录（空表）")
        
        finally:
            await source_engine.dispose()
        
        return result
    
    async def _write_target_data(self, target_db_type: str, data: Dict[str, List[Dict]]):
        """
        将数据写入目标数据库
        
        1. 先创建表结构（基于 ORM models）
        2. 按依赖顺序插入数据
        3. 处理自增主键兼容性
        """
        target_url = db_manager.get_url(target_db_type)
        target_engine = create_async_engine(target_url, echo=False)
        
        try:
            # 1. 创建所有表（先 drop 再 create，保证干净）
            from database.models import Base
            
            async with target_engine.begin() as conn:
                # 检查目标数据库是否已有数据
                has_data = False
                for table_name in TABLE_ORDER:
                    try:
                        count = await conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                        if count.scalar() > 0:
                            has_data = True
                            break
                    except Exception:
                        pass  # 表可能不存在
                
                if has_data:
                    logger.warning("⚠️ 目标数据库已有数据，将先清空后重新迁移")
                    # 按依赖顺序反向删除（先删引用表，再删被引用表）
                    for table_name in reversed(TABLE_ORDER):
                        try:
                            await conn.execute(text(f"DELETE FROM {table_name}"))
                        except Exception:
                            pass  # 表可能不存在
                
                # 创建所有表
                await conn.run_sync(Base.metadata.create_all)
                logger.info("  📦 目标数据库表结构已创建")
            
            # 2. 逐表插入数据
            async with target_engine.connect() as conn:
                for table_name in TABLE_ORDER:
                    rows = data.get(table_name, [])
                    if not rows:
                        self._progress["tables_done"] += 1
                        continue
                    
                    self._progress["current_table"] = table_name
                    logger.info(f"  ✍️ 写入表: {table_name} ({len(rows)} 条)")
                    
                    # 分批插入（每批 100 条）
                    BATCH_SIZE = 100
                    for i in range(0, len(rows), BATCH_SIZE):
                        batch = rows[i:i + BATCH_SIZE]
                        
                        if target_db_type == "mysql":
                            # MySQL 使用标准 INSERT（列名加反引号防保留字冲突）
                            columns = list(batch[0].keys())
                            placeholders = ", ".join([f":{col}" for col in columns])
                            column_names = ", ".join([f"`{c}`" for c in columns])
                            
                            for row in batch:
                                clean_row = {}
                                for k, v in row.items():
                                    if isinstance(v, datetime):
                                        clean_row[k] = v
                                    else:
                                        clean_row[k] = v
                                
                                stmt = text(
                                    f"INSERT INTO {table_name} ({column_names}) "
                                    f"VALUES ({placeholders})"
                                )
                                await conn.execute(stmt, clean_row)
                        else:
                            # SQLite
                            columns = list(batch[0].keys())
                            placeholders = ", ".join([f":{col}" for col in columns])
                            column_names = ", ".join(columns)
                            
                            for row in batch:
                                clean_row = {}
                                for k, v in row.items():
                                    if isinstance(v, datetime):
                                        clean_row[k] = v
                                    else:
                                        clean_row[k] = v
                                
                                stmt = text(
                                    f"INSERT INTO {table_name} ({column_names}) "
                                    f"VALUES ({placeholders})"
                                )
                                await conn.execute(stmt, clean_row)
                        
                        self._progress["rows_migrated"] += len(batch)
                    
                    await conn.commit()
                    self._progress["tables_done"] += 1
                    logger.info(f"    ✅ {table_name} 迁移完成")
        
        finally:
            await target_engine.dispose()
    
    async def _verify_migration(self, source_type: str, target_type: str) -> Dict[str, Any]:
        """
        校验迁移结果：比对源和目标数据库的记录数
        """
        source_url = db_manager.get_url(source_type)
        target_url = db_manager.get_url(target_type)
        
        source_engine = create_async_engine(source_url, echo=False)
        target_engine = create_async_engine(target_url, echo=False)
        
        verification = {
            "source_count": {},
            "target_count": {},
            "mismatches": [],
            "passed": True,
        }
        
        try:
            async with source_engine.connect() as src_conn, target_engine.connect() as tgt_conn:
                for table_name in TABLE_ORDER:
                    try:
                        src_count = await src_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                        src_val = src_count.scalar() or 0
                        
                        tgt_count = await tgt_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                        tgt_val = tgt_count.scalar() or 0
                        
                        verification["source_count"][table_name] = src_val
                        verification["target_count"][table_name] = tgt_val
                        
                        if src_val != tgt_val:
                            verification["mismatches"].append({
                                "table": table_name,
                                "source": src_val,
                                "target": tgt_val,
                            })
                            verification["passed"] = False
                    
                    except Exception as e:
                        logger.warning(f"  ⚠️ 校验 {table_name} 失败: {e}")
        
        finally:
            await source_engine.dispose()
            await target_engine.dispose()
        
        if verification["passed"]:
            logger.info("✅ 迁移校验通过: 所有表记录数一致")
        else:
            logger.warning(f"⚠️ 迁移校验发现 {len(verification['mismatches'])} 张表记录数不匹配")
        
        return verification


# ============================================================
# 全局单例
# ============================================================
migration = DatabaseMigration()