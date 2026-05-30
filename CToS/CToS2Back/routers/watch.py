"""智能瞭望 Watch 模块"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, desc, delete
from database.engine import db_manager
from database.models import User, WatchSource, WatchData
from middleware.auth_middleware import get_current_user
from utils.helpers import success_response, AppException
import json
import httpx
from datetime import datetime

router = APIRouter(prefix="/api/watch", tags=["智能瞭望"])

class WatchSourceCreate(BaseModel):
    name: str
    url: str
    method: str = "GET"
    headers: str = "{}"
    body_template: str = ""
    interval_seconds: int = 3600

class WatchSourceUpdate(BaseModel):
    name: str = None
    url: str = None
    method: str = None
    headers: str = None
    body_template: str = None
    interval_seconds: int = None
    enabled: int = None


# ===== 瞭望源管理 =====

@router.get("/sources")
async def list_sources(user: User = Depends(get_current_user)):
    """获取瞭望源列表"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(WatchSource).where(WatchSource.user_id == user.id)
            .order_by(desc(WatchSource.created_at))
        )
        sources = result.scalars().all()
        return success_response(data=[{
            "id": s.id, "name": s.name, "url": s.url,
            "method": s.method, "headers": s.headers,
            "body_template": s.body_template,
            "interval_seconds": s.interval_seconds,
            "enabled": s.enabled,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        } for s in sources])

@router.post("/sources")
async def create_source(req: WatchSourceCreate, user: User = Depends(get_current_user)):
    """创建瞭望源"""
    async with db_manager.get_session() as session:
        source = WatchSource(
            user_id=user.id, name=req.name, url=req.url,
            method=req.method, headers=req.headers,
            body_template=req.body_template, interval_seconds=req.interval_seconds
        )
        session.add(source)
        await session.commit()
        await session.refresh(source)
        return success_response(data={"id": source.id}, message="瞭望源创建成功")

@router.get("/sources/{source_id}")
async def get_source(source_id: int, user: User = Depends(get_current_user)):
    """获取瞭望源详情"""
    async with db_manager.get_session() as session:
        source = await session.get(WatchSource, source_id)
        if not source:
            raise AppException("瞭望源不存在", status_code=404)
        # 获取最新采集时间
        data_result = await session.execute(
            select(WatchData).where(WatchData.source_id == source_id)
            .order_by(desc(WatchData.collected_at)).limit(1)
        )
        latest_data = data_result.scalar_one_or_none()
        return success_response(data={
            "id": source.id, "name": source.name, "url": source.url,
            "method": source.method, "headers": source.headers,
            "body_template": source.body_template,
            "interval_seconds": source.interval_seconds,
            "enabled": source.enabled,
            "latest_collected_at": latest_data.collected_at.isoformat() if latest_data and latest_data.collected_at else None,
            "latest_status": latest_data.status if latest_data else None,
            "created_at": source.created_at.isoformat() if source.created_at else None,
            "updated_at": source.updated_at.isoformat() if source.updated_at else None,
        })

@router.put("/sources/{source_id}")
async def update_source(source_id: int, req: WatchSourceUpdate, user: User = Depends(get_current_user)):
    """编辑瞭望源"""
    async with db_manager.get_session() as session:
        source = await session.get(WatchSource, source_id)
        if not source:
            raise AppException("瞭望源不存在", status_code=404)
        if req.name is not None:
            source.name = req.name
        if req.url is not None:
            source.url = req.url
        if req.method is not None:
            source.method = req.method
        if req.headers is not None:
            source.headers = req.headers
        if req.body_template is not None:
            source.body_template = req.body_template
        if req.interval_seconds is not None:
            source.interval_seconds = req.interval_seconds
        if req.enabled is not None:
            source.enabled = req.enabled
        source.updated_at = datetime.utcnow()
        await session.commit()
        return success_response(message="瞭望源已更新")

@router.delete("/sources/{source_id}")
async def delete_source(source_id: int, user: User = Depends(get_current_user)):
    """删除瞭望源"""
    async with db_manager.get_session() as session:
        source = await session.get(WatchSource, source_id)
        if not source:
            raise AppException("瞭望源不存在", status_code=404)
        await session.delete(source)
        await session.commit()
        return success_response(message="瞭望源已删除")

@router.post("/sources/{source_id}/trigger")
async def trigger_collection(source_id: int, user: User = Depends(get_current_user)):
    """手动触发采集"""
    async with db_manager.get_session() as session:
        source = await session.get(WatchSource, source_id)
        if not source:
            raise AppException("瞭望源不存在", status_code=404)

        # 执行 HTTP 请求采集
        headers = json.loads(source.headers or "{}")
        error_message = None
        http_status = None
        raw_response = None
        parsed_data = None
        status = "success"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if source.method.upper() == "GET":
                    resp = await client.get(source.url, headers=headers)
                elif source.method.upper() == "POST":
                    body = json.loads(source.body_template) if source.body_template else {}
                    resp = await client.post(source.url, headers=headers, json=body)
                elif source.method.upper() == "PUT":
                    body = json.loads(source.body_template) if source.body_template else {}
                    resp = await client.put(source.url, headers=headers, json=body)
                else:
                    resp = await client.get(source.url, headers=headers)

                http_status = resp.status_code
                raw_response = resp.text[:10000]  # 截断至10000字符

                # 尝试解析 JSON
                try:
                    parsed_data = resp.json()
                    parsed_data = json.dumps(parsed_data, ensure_ascii=False)[:10000]
                except Exception:
                    parsed_data = None

                if resp.status_code >= 400:
                    status = "error"
                    error_message = f"HTTP {resp.status_code}: {resp.text[:500]}"

        except Exception as e:
            status = "error"
            error_message = str(e)[:1000]

        watch_data = WatchData(
            source_id=source_id,
            raw_response=raw_response,
            parsed_data=parsed_data,
            status=status,
            error_message=error_message,
            http_status=http_status,
        )
        session.add(watch_data)
        await session.commit()
        await session.refresh(watch_data)

        return success_response(data={
            "id": watch_data.id,
            "status": watch_data.status,
            "http_status": watch_data.http_status,
            "raw_response": raw_response[:500] if raw_response else None,
        }, message="采集完成" if status == "success" else "采集失败")


# ===== 采集数据 =====

@router.get("/sources/{source_id}/data")
async def get_source_data(source_id: int, limit: int = 20, user: User = Depends(get_current_user)):
    """获取采集历史"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(WatchData).where(WatchData.source_id == source_id)
            .order_by(desc(WatchData.collected_at)).limit(limit)
        )
        data_list = result.scalars().all()
        return success_response(data=[{
            "id": d.id, "status": d.status,
            "http_status": d.http_status,
            "parsed_data": d.parsed_data,
            "collected_at": d.collected_at.isoformat() if d.collected_at else None,
        } for d in data_list])

@router.get("/data/{data_id}")
async def get_watch_data_detail(data_id: int, user: User = Depends(get_current_user)):
    """获取采集数据详情"""
    async with db_manager.get_session() as session:
        data = await session.get(WatchData, data_id)
        if not data:
            raise AppException("采集数据不存在", status_code=404)
        return success_response(data={
            "id": data.id,
            "source_id": data.source_id,
            "raw_response": data.raw_response,
            "parsed_data": data.parsed_data,
            "status": data.status,
            "http_status": data.http_status,
            "error_message": data.error_message,
            "collected_at": data.collected_at.isoformat() if data.collected_at else None,
        })

@router.post("/export/{source_id}")
async def export_source_data(source_id: int, user: User = Depends(get_current_user)):
    """导出采集数据为 JSON"""
    async with db_manager.get_session() as session:
        source = await session.get(WatchSource, source_id)
        if not source:
            raise AppException("瞭望源不存在", status_code=404)

        result = await session.execute(
            select(WatchData).where(WatchData.source_id == source_id)
            .order_by(desc(WatchData.collected_at)).limit(100)
        )
        data_list = result.scalars().all()

        export_data = {
            "source_name": source.name,
            "source_url": source.url,
            "export_time": datetime.utcnow().isoformat(),
            "total_records": len(data_list),
            "records": [{
                "id": d.id,
                "status": d.status,
                "http_status": d.http_status,
                "raw_response": d.raw_response,
                "parsed_data": d.parsed_data,
                "error_message": d.error_message,
                "collected_at": d.collected_at.isoformat() if d.collected_at else None,
            } for d in data_list],
        }
        return success_response(data=export_data)