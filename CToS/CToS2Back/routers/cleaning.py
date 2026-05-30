"""数据清洗 Cleaning 模块

集成 services/cleaning_service.py 的 AI 清洗业务逻辑。
支持 AI 清洗（LLM+工具验证）和正则清洗（规则回退）。
清洗成功后自动创建 WarehouseArticle 记录。
"""
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, desc
from typing import Optional
from database.engine import db_manager
from database.models import User, CleaningLog, WatchData, ExecutionLog, Worker, WarehouseArticle
from middleware.auth_middleware import get_current_user
from utils.helpers import success_response, AppException
from utils.db_utils import fetch_paginated
from services.cleaning_service import (
    start_ai_cleaning,
    start_regex_cleaning,
    execute_cleaning_pipeline,
    get_tool_function,
    get_tool_schemas_for_worker,
    TOOL_REGISTRY,
)
from utils.helpers import logger

router = APIRouter(prefix="/api/cleaning", tags=["数据清洗"])


class CleaningStartRequest(BaseModel):
    watch_data_ids: list[int]
    method: str = "ai"
    worker_id: Optional[int] = None  # 使用哪个数字员工进行清洗（不传则自动选择）


@router.get("/logs")
async def list_cleaning_logs(
    page: int = 1,
    page_size: int = 20,
    status: str = "",
    watch_data_id: Optional[int] = None,
    user: User = Depends(get_current_user),
):
    """获取数据清洗日志列表"""
    async with db_manager.get_session() as session:
        query = select(CleaningLog).order_by(desc(CleaningLog.created_at))
        if status:
            query = query.where(CleaningLog.status == status)
        if watch_data_id:
            query = query.where(CleaningLog.watch_data_id == watch_data_id)
        
        return await fetch_paginated(
            session, query, page, page_size,
            mapper=lambda log: {
                "id": log.id,
                "watch_data_id": log.watch_data_id,
                "method": log.method,
                "status": log.status,
                "result": log.result,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
        )


@router.post("/start")
async def start_cleaning(
    req: CleaningStartRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """启动数据清洗

    支持两种清洗方法：
    - ai: 调用 LLM 进行 AI 清洗，清洗完成后自动创建 WarehouseArticle
    - regex: 使用正则规则清洗，同步执行并创建 WarehouseArticle
    """
    if not req.watch_data_ids:
        raise AppException("请选择要清洗的数据", status_code=400)
    
    if req.method not in ("ai", "regex"):
        raise AppException("清洗方法必须是 ai 或 regex", status_code=400)
    
    if req.method == "ai" and not req.worker_id:
        raise AppException("AI清洗需要指定一个数字员工", status_code=400)
    
    created_logs = []
    
    for wd_id in req.watch_data_ids:
        if req.method == "regex":
            # 正则清洗 - 同步执行
            try:
                cleaning_log_id = await start_regex_cleaning(
                    watch_data_id=wd_id,
                    user_id=user.id,
                )
                created_logs.append({
                    "id": cleaning_log_id,
                    "watch_data_id": wd_id,
                    "method": "regex",
                    "status": "success" if cleaning_log_id else "failed",
                })
            except AppException as e:
                created_logs.append({
                    "watch_data_id": wd_id,
                    "method": "regex",
                    "status": "failed",
                    "error": str(e),
                })
        else:
            # AI 清洗 - 创建记录并在后台执行完整流水线
            try:
                cleaning_log_id, exec_log_id = await start_ai_cleaning(
                    watch_data_id=wd_id,
                    worker_id=req.worker_id,
                    user_id=user.id,
                )

                # 在后台执行完整的清洗流水线（LLM 调用 + 工具验证 + 入库）
                background_tasks.add_task(
                    execute_cleaning_pipeline,
                    cleaning_log_id,
                    exec_log_id,
                    user.id,
                )

                created_logs.append({
                    "id": cleaning_log_id,
                    "watch_data_id": wd_id,
                    "method": "ai",
                    "status": "processing",
                    "execution_log_id": exec_log_id,
                })
            except AppException as e:
                created_logs.append({
                    "watch_data_id": wd_id,
                    "method": "ai",
                    "status": "failed",
                    "error": str(e),
                })
    
    return success_response(
        data=created_logs,
        message=f"已创建{len(created_logs)}个清洗任务（AI任务将在后台执行）"
    )


@router.get("/logs/{log_id}")
async def get_cleaning_log(log_id: int, user: User = Depends(get_current_user)):
    """获取清洗日志详情（含关联的原始数据 + 执行记录 + 入库文章）"""
    async with db_manager.get_session() as session:
        log = await session.get(CleaningLog, log_id)
        if not log:
            raise AppException("清洗日志不存在", status_code=404)
        
        # 获取关联的原始数据
        watch_data = await session.get(WatchData, log.watch_data_id)
        
        # 获取关联的执行记录
        exec_result = await session.execute(
            select(ExecutionLog).where(ExecutionLog.cleaning_log_id == log_id)
        )
        exec_log = exec_result.scalar_one_or_none()
        
        # 获取关联的仓库文章
        article_result = await session.execute(
            select(WarehouseArticle).where(WarehouseArticle.cleaning_log_id == log_id)
        )
        article = article_result.scalar_one_or_none()
        
        return success_response(data={
            "id": log.id,
            "watch_data_id": log.watch_data_id,
            "watch_data_raw": watch_data.raw_response[:500] if watch_data else None,
            "watch_data_parsed": watch_data.parsed_data if watch_data else None,
            "method": log.method,
            "status": log.status,
            "result": log.result,
            "error_message": log.error_message,
            "execution_log_id": exec_log.id if exec_log else None,
            "execution_status": exec_log.status if exec_log else None,
            "article_id": article.id if article else None,
            "article_title": article.title if article else None,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })


@router.post("/logs/{log_id}/retry")
async def retry_cleaning(
    log_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """重新执行清洗"""
    async with db_manager.get_session() as session:
        log = await session.get(CleaningLog, log_id)
        if not log:
            raise AppException("清洗日志不存在", status_code=404)
        
        watch_data = await session.get(WatchData, log.watch_data_id)
        if not watch_data:
            raise AppException("关联的采集数据不存在", status_code=404)
        
        # 重置状态
        log.status = "processing"
        log.result = None
        log.error_message = None
        
        # 删除旧的关联执行记录（如果有）
        exec_result = await session.execute(
            select(ExecutionLog).where(ExecutionLog.cleaning_log_id == log_id)
        )
        old_exec = exec_result.scalar_one_or_none()
        if old_exec:
            await session.delete(old_exec)
        
        # 创建新的执行记录
        from services.cleaning_service import _get_cleaning_worker
        worker, job = await _get_cleaning_worker()
        if not worker:
            raise AppException("未找到可用的清洗数字员工", status_code=400)
        
        from database.models import ExecutionLog as ExecLogModel, ExecutionMessage
        exec_log = ExecLogModel(
            worker_id=worker.id,
            user_query=f"重新清洗瞭望数据 #{log.watch_data_id}：{(watch_data.raw_response or '')[:500]}",
            status="processing",
            cleaning_log_id=log.id,
        )
        session.add(exec_log)
        await session.flush()
        
        # 写入消息
        from services.cleaning_service import CLEANING_SYSTEM_PROMPT
        session.add(ExecutionMessage(
            execution_log_id=exec_log.id,
            role="system",
            content=CLEANING_SYSTEM_PROMPT,
        ))
        session.add(ExecutionMessage(
            execution_log_id=exec_log.id,
            role="user",
            content=f"请重新清洗以下数据：\n\n原始内容:\n{(watch_data.raw_response or '')[:8000]}",
        ))
        
        await session.commit()
        
        # 后台执行
        background_tasks.add_task(
            execute_cleaning_pipeline,
            log_id,
            exec_log.id,
            user.id,
        )
        
        return success_response(message="清洗任务已重新提交，正在后台执行")


@router.post("/logs/{log_id}/result")
async def update_cleaning_result(log_id: int, result: str, user: User = Depends(get_current_user)):
    """更新清洗结果（由数字员工回写）"""
    async with db_manager.get_session() as session:
        log = await session.get(CleaningLog, log_id)
        if not log:
            raise AppException("清洗日志不存在", status_code=404)
        
        log.status = "success"
        log.result = result
        await session.commit()
        
        return success_response(message="清洗结果已更新")


@router.get("/stats")
async def get_cleaning_stats(user: User = Depends(get_current_user)):
    """获取清洗统计"""
    async with db_manager.get_session() as session:
        from sqlalchemy import func
        total = await session.scalar(select(func.count(CleaningLog.id)))
        success = await session.scalar(
            select(func.count(CleaningLog.id)).where(CleaningLog.status == "success")
        )
        failed = await session.scalar(
            select(func.count(CleaningLog.id)).where(CleaningLog.status == "failed")
        )
        processing = await session.scalar(
            select(func.count(CleaningLog.id)).where(CleaningLog.status == "processing")
        )
        
        return success_response(data={
            "total": total or 0,
            "success": success or 0,
            "failed": failed or 0,
            "processing": processing or 0,
        })


@router.get("/uncleaned")
async def list_uncleaned_watch_data(
    page: int = 1,
    page_size: int = 50,
    source_id: Optional[int] = None,
    user: User = Depends(get_current_user),
):
    """获取尚未清洗的瞭望数据（即没有对应 CleaningLog 的 WatchData）

    用于数据清洗工作台左侧"待清洗数据"面板，确保只显示未清洗的原始数据。
    """
    async with db_manager.get_session() as session:
        # 子查询：已有关联 CleaningLog 的 watch_data_id
        from sqlalchemy import func
        subq = (
            select(CleaningLog.watch_data_id)
            .distinct()
            .subquery()
        )

        # 查询 watch_data 中 watch_data_id 不在 cleaning_logs 中的记录
        query = (
            select(WatchData)
            .outerjoin(subq, WatchData.id == subq.c.watch_data_id)
            .where(subq.c.watch_data_id.is_(None))
            .order_by(desc(WatchData.collected_at))
        )

        if source_id:
            query = query.where(WatchData.source_id == source_id)

        return await fetch_paginated(
            session, query, page, page_size,
            mapper=lambda wd: {
                "id": wd.id,
                "source_id": wd.source_id,
                "raw_response": wd.raw_response,
                "parsed_data": wd.parsed_data,
                "status": wd.status,
                "http_status": wd.http_status,
                "error_message": wd.error_message,
                "collected_at": wd.collected_at.isoformat() if wd.collected_at else None,
            }
        )


@router.get("/tools")
async def list_cleaning_tools(user: User = Depends(get_current_user)):
    """获取可用的清洗工具列表"""
    tools = []
    for name, func in TOOL_REGISTRY.items():
        tools.append({
            "name": name,
            "description": func.__doc__,
            "module": func.__module__,
        })
    return success_response(data=tools)