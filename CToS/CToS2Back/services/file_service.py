"""
文件管理服务 - 提供文件上传、下载、删除、列表管理，支持MD5去重
"""
import os
import hashlib
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import File
from database.engine import db_manager
from utils.helpers import logger, AppException


# 上传根目录（与 data/uploads 保持一致）
UPLOAD_BASE_DIR = Path("data/uploads")
UPLOAD_BASE_DIR.mkdir(parents=True, exist_ok=True)


def _get_storage_dir() -> Path:
    """获取存储根目录，按月分目录存储"""
    month_dir = UPLOAD_BASE_DIR / datetime.now().strftime("%Y%m")
    month_dir.mkdir(parents=True, exist_ok=True)
    return month_dir


def _compute_md5(file_path: str) -> str:
    """计算文件的MD5哈希"""
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


async def _check_md5_exists(session: AsyncSession, md5_hash: str) -> Optional[File]:
    """检查MD5是否已存在，返回已存在的文件记录"""
    result = await session.execute(
        select(File).where(File.md5_hash == md5_hash).limit(1)
    )
    return result.scalar_one_or_none()


async def upload_file(
    file: UploadFile,
    uploader_id: int,
    chat_message_id: Optional[int] = None,
) -> dict:
    """
    上传文件，支持MD5去重
    返回文件信息字典
    """
    # 读取文件内容
    content = await file.read()
    file_size = len(content)

    if file_size <= 0:
        raise AppException("空文件不允许上传")

    # 限制单个文件大小（默认10MB）
    max_size = getattr(settings, "MAX_FILE_SIZE", 10 * 1024 * 1024)
    if file_size > max_size:
        max_mb = max_size / 1024 / 1024
        raise AppException(f"文件大小超过限制（最大 {max_mb:.0f}MB）")

    # 计算MD5
    md5_hash = hashlib.md5(content).hexdigest()

    async with db_manager.get_session() as session:
        # 检查MD5去重
        existing = await _check_md5_exists(session, md5_hash)
        if existing:
            logger.info(f"📎 MD5重复文件，复用已有记录: {existing.file_name} (MD5: {md5_hash[:16]}...)")
            # 返回已有文件信息，但是更新chat_message_id关联
            if chat_message_id and not existing.chat_message_id:
                existing.chat_message_id = chat_message_id
                await session.commit()
                await session.refresh(existing)
            return _file_to_dict(existing)

        # 生成存储路径：按月分目录，UUID文件名防止冲突
        storage_dir = _get_storage_dir()
        ext = Path(file.filename).suffix if file.filename else ""
        stored_name = f"{uuid.uuid4().hex}{ext}"
        stored_path = storage_dir / stored_name

        # 写入文件
        with open(stored_path, "wb") as f:
            f.write(content)

        # 保存文件记录
        file_record = File(
            file_name=file.filename or stored_name,
            file_path=str(stored_path),
            file_size=file_size,
            md5_hash=md5_hash,
            mime_type=file.content_type or "application/octet-stream",
            uploader_id=uploader_id,
            chat_message_id=chat_message_id,
        )
        session.add(file_record)
        await session.commit()
        await session.refresh(file_record)

        logger.info(f"📄 文件上传成功: {file.filename} ({file_size} bytes, MD5: {md5_hash[:16]}...)")
        return _file_to_dict(file_record)


async def get_file_record(file_id: int) -> dict:
    """获取文件记录详情"""
    async with db_manager.get_session() as session:
        file_record = await session.get(File, file_id)
        if not file_record:
            raise AppException("文件不存在", status_code=404)
        return _file_to_dict(file_record)


async def get_file_record_raw(file_id: int) -> Optional[File]:
    """获取文件记录ORM对象（供内部使用）"""
    async with db_manager.get_session() as session:
        return await session.get(File, file_id)


async def delete_file(file_id: int, user_id: int) -> None:
    """
    删除文件记录和物理文件
    如果有其他记录引用了相同MD5的物理文件，不删除物理文件
    """
    async with db_manager.get_session() as session:
        file_record = await session.get(File, file_id)
        if not file_record:
            raise AppException("文件不存在", status_code=404)

        # 检查MD5是否被其他记录引用
        md5_hash = file_record.md5_hash
        ref_result = await session.execute(
            select(File).where(File.md5_hash == md5_hash, File.id != file_id).limit(1)
        )
        has_other_ref = ref_result.scalar_one_or_none() is not None

        # 删除数据库记录
        await session.delete(file_record)
        await session.commit()

        # 如果没有其他引用且文件存在，删除物理文件
        if not has_other_ref:
            stored_path = Path(file_record.file_path)
            if stored_path.exists():
                stored_path.unlink()
                logger.info(f"🗑️ 已删除物理文件: {stored_path}")

        logger.info(f"🗑️ 文件记录已删除: id={file_id}, name={file_record.file_name}")


async def list_files(
    page: int = 1,
    page_size: int = 20,
    file_name: str = "",
    mime_type: str = "",
    uploader_id: Optional[int] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> dict:
    """
    分页查询文件列表，支持按文件名、MIME类型、上传者筛选
    """
    from utils.db_utils import fetch_paginated

    async with db_manager.get_session() as session:
        query = select(File)

        # 筛选条件
        if file_name:
            query = query.where(File.file_name.ilike(f"%{file_name}%"))
        if mime_type:
            query = query.where(File.mime_type.ilike(f"%{mime_type}%"))
        if uploader_id is not None:
            query = query.where(File.uploader_id == uploader_id)

        # 排序
        sort_column = getattr(File, sort_by, File.created_at)
        if sort_order == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(desc(sort_column))

        result = await fetch_paginated(
            session, query, page, page_size,
            mapper=_file_to_dict,
        )
        return result


async def get_file_stats() -> dict:
    """获取文件统计信息"""
    from sqlalchemy import func

    async with db_manager.get_session() as session:
        # 总文件数、总大小
        result = await session.execute(
            select(
                func.count(File.id).label("total_files"),
                func.coalesce(func.sum(File.file_size), 0).label("total_size"),
            )
        )
        row = result.one()
        total_files = row[0] or 0
        total_size = row[1] or 0

        # 各MIME类型分布
        type_result = await session.execute(
            select(File.mime_type, func.count(File.id).label("count"))
            .group_by(File.mime_type)
            .order_by(desc("count"))
            .limit(20)
        )
        type_distribution = [
            {"mime_type": row[0] or "unknown", "count": row[1] or 0}
            for row in type_result
        ]

        # 今日上传
        today = datetime.now().strftime("%Y-%m-%d")
        today_result = await session.execute(
            select(func.count(File.id))
            .where(func.date(File.created_at) == today)
        )
        today_count = today_result.scalar() or 0

        # 总上传者数
        uploader_result = await session.execute(
            select(func.count(func.distinct(File.uploader_id)))
        )
        uploader_count = uploader_result.scalar() or 0

        return {
            "total_files": total_files,
            "total_size": total_size,
            "type_distribution": type_distribution,
            "today_uploads": today_count,
            "total_uploaders": uploader_count,
        }


def _file_to_dict(file_record: File) -> dict:
    """将File ORM对象转为字典"""
    return {
        "id": file_record.id,
        "file_name": file_record.file_name,
        "file_path": file_record.file_path,
        "file_size": file_record.file_size,
        "md5_hash": file_record.md5_hash,
        "mime_type": file_record.mime_type,
        "uploader_id": file_record.uploader_id,
        "chat_message_id": file_record.chat_message_id,
        "created_at": file_record.created_at.isoformat() if file_record.created_at else None,
        # 额外计算字段
        "file_size_display": _format_size(file_record.file_size),
    }


def _format_size(size_bytes: int) -> str:
    """格式化文件大小显示"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"