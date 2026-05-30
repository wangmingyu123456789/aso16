"""
文件管理路由 - 提供文件上传、下载、列表、删除、统计等功能
"""
import os
import urllib.parse
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional

from database.models import User, File as FileModel
from middleware.auth_middleware import get_current_user, get_admin_user
from utils.helpers import success_response, AppException, logger
from services.file_service import (
    upload_file, get_file_record, get_file_record_raw,
    delete_file, list_files, get_file_stats,
)

router = APIRouter(prefix="/api/files", tags=["文件管理"])


# ===== 文件统计 =====

@router.get("/stats")
async def file_stats(current_user: User = Depends(get_current_user)):
    """获取文件统计信息"""
    stats = await get_file_stats()
    return success_response(data=stats)


# ===== 文件列表 =====

@router.get("")
async def file_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    file_name: str = Query("", description="文件名搜索"),
    mime_type: str = Query("", description="MIME类型筛选"),
    uploader_id: Optional[int] = Query(None, description="上传者ID筛选"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向 asc/desc"),
    current_user: User = Depends(get_current_user),
):
    """分页获取文件列表"""
    # 非管理员只能看到自己上传的文件
    if current_user.role != "admin" and uploader_id is None:
        uploader_id = current_user.id

    result = await list_files(
        page=page,
        page_size=page_size,
        file_name=file_name,
        mime_type=mime_type,
        uploader_id=uploader_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return result


# ===== 文件详情 =====

@router.get("/{file_id}")
async def file_detail(file_id: int, current_user: User = Depends(get_current_user)):
    """获取文件详情"""
    record = await get_file_record(file_id)
    # 非管理员只能查看自己上传的文件
    if current_user.role != "admin" and record["uploader_id"] != current_user.id:
        raise AppException("无权访问此文件", status_code=403)
    return success_response(data=record)


# ===== 文件上传 =====

@router.post("/upload")
async def file_upload(
    file: UploadFile = File(..., description="要上传的文件"),
    chat_message_id: Optional[int] = Form(None, description="关联的消息ID"),
    current_user: User = Depends(get_current_user),
):
    """上传文件（支持MD5去重）"""
    if not file.filename:
        raise AppException("文件名不能为空")
    
    result = await upload_file(
        file=file,
        uploader_id=current_user.id,
        chat_message_id=chat_message_id,
    )
    return success_response(data=result, message="文件上传成功")


# ===== 文件下载/预览 =====

@router.get("/{file_id}/download")
async def file_download(file_id: int, current_user: User = Depends(get_current_user)):
    """下载或预览文件"""
    file_record = await get_file_record_raw(file_id)
    if not file_record:
        raise AppException("文件不存在", status_code=404)

    # 权限检查：非管理员只能下载自己上传的文件
    if current_user.role != "admin" and file_record.uploader_id != current_user.id:
        raise AppException("无权访问此文件", status_code=403)

    stored_path = Path(file_record.file_path)
    if not stored_path.exists():
        raise AppException("文件存储已丢失", status_code=404)

    # 根据MIME类型决定是预览还是下载
    mime_type = file_record.mime_type or "application/octet-stream"
    is_preview = mime_type.startswith(("image/", "text/", "application/pdf"))

    # 手动编码文件名为 RFC 5987 格式，支持中文文件名
    # filename 必须用 ASCII 安全的 fallback（latin-1 限制），filename* 用 UTF-8 编码
    encoded_filename = urllib.parse.quote(file_record.file_name, safe='')
    ascii_fallback = ''.join(c if ord(c) < 128 else '_' for c in file_record.file_name)
    disposition_type = 'inline' if is_preview else 'attachment'
    disposition = (
        f"{disposition_type}; "
        f"filename=\"{ascii_fallback}\"; "
        f"filename*=UTF-8''{encoded_filename}"
    )

    return FileResponse(
        path=str(stored_path),
        filename=ascii_fallback,
        media_type=mime_type,
        headers={
            "Content-Disposition": disposition,
        },
    )


# ===== 文件删除 =====

@router.delete("/{file_id}")
async def file_delete(file_id: int, current_user: User = Depends(get_current_user)):
    """删除文件（管理员可删除任意文件，普通用户只能删除自己上传的文件）"""
    # 先获取文件记录检查权限
    record = await get_file_record(file_id)
    if current_user.role != "admin" and record["uploader_id"] != current_user.id:
        raise AppException("无权删除此文件", status_code=403)

    await delete_file(file_id, current_user.id)
    return success_response(message="文件已删除")


# ===== 批量操作 =====

class BatchDeleteRequest(BaseModel):
    ids: list[int]

@router.post("/batch-delete")
async def file_batch_delete(
    req: BatchDeleteRequest,
    current_user: User = Depends(get_admin_user),
):
    """批量删除文件（仅管理员）"""
    if not req.ids:
        raise AppException("请提供要删除的文件ID列表")

    deleted_count = 0
    errors = []
    for file_id in req.ids:
        try:
            await delete_file(file_id, current_user.id)
            deleted_count += 1
        except Exception as e:
            errors.append({"id": file_id, "error": str(e)})

    return success_response(
        data={
            "deleted_count": deleted_count,
            "error_count": len(errors),
            "errors": errors if errors else None,
        },
        message=f"成功删除 {deleted_count} 个文件" + (f"，{len(errors)} 个失败" if errors else ""),
    )


# ===== 上传者列表（供下拉筛选） =====

@router.get("/uploaders/list")
async def file_uploaders(current_user: User = Depends(get_admin_user)):
    """获取所有上传过文件的用户列表（仅管理员）"""
    from sqlalchemy import select, func
    from database.engine import db_manager
    from database.models import User

    async with db_manager.get_session() as session:
        result = await session.execute(
            select(User.id, User.username, User.nickname)
            .join(FileModel, FileModel.uploader_id == User.id)
            .distinct()
            .order_by(User.id)
        )
        uploaders = [
            {"id": row[0], "username": row[1], "nickname": row[2] or row[1]}
            for row in result
        ]
        return success_response(data=uploaders)