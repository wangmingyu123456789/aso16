"""
自动工作流模块 - 自动化数据采集→清洗入库→舆情分析全流程
"""
import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from typing import Optional
from database.engine import db_manager
from database.models import (
    User, WorkflowTask, WorkflowTaskLog,
    WatchSource, WatchData, SentimentAnalysis,
    CleaningLog, WarehouseArticle,
)
from middleware.auth_middleware import get_current_user
from utils.helpers import success_response, AppException, logger
from utils.db_utils import fetch_paginated
from services.sentiment_service import trigger_sentiment_analysis
from services.cleaning_service import start_ai_cleaning, execute_cleaning_pipeline

router = APIRouter(prefix="/api/workflow", tags=["自动工作流"])


class CreateWorkflowRequest(BaseModel):
    """创建任务请求"""
    name: str
    source_ids: list[int]  # 要采集的瞭望源ID列表


# ============================================================
# 1. 创建任务
# ============================================================

@router.post("/tasks")
async def create_task(
    req: CreateWorkflowRequest,
    user: User = Depends(get_current_user),
):
    """创建自动工作流任务"""
    if not req.name.strip():
        raise AppException("任务名称不能为空")
    if not req.source_ids:
        raise AppException("请至少选择一个数据源")

    async with db_manager.get_session() as session:
        result = await session.execute(
            select(WatchSource).where(
                WatchSource.id.in_(req.source_ids),
                WatchSource.user_id == user.id
            )
        )
        sources = result.scalars().all()
        if len(sources) != len(req.source_ids):
            raise AppException("部分瞭望源不存在或无权访问")

        steps_config = [
            {
                "step_type": "collect",
                "label": f"📡 采集数据源 ({len(sources)}个)",
                "source_ids": [s.id for s in sources],
                "sources": [{"id": s.id, "name": s.name} for s in sources],
            },
            {
                "step_type": "cleaning",
                "label": "🧹 清洗采集数据并入库",
                "source_ids": [s.id for s in sources],
            },
            {
                "step_type": "sentiment",
                "label": "📊 舆情分析",
                "source_ids": [s.id for s in sources],
            },
        ]

        task = WorkflowTask(
            name=req.name.strip(),
            user_id=user.id,
            status="pending",
            steps_config=json.dumps(steps_config, ensure_ascii=False),
            total_steps=len(steps_config),
            current_step=0,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)

        return success_response(data={
            "id": task.id,
            "name": task.name,
            "status": task.status,
            "total_steps": task.total_steps,
            "steps_config": steps_config,
            "created_at": task.created_at.isoformat() if task.created_at else None,
        })


# ============================================================
# 2. 任务列表
# ============================================================

@router.get("/tasks")
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    """获取任务列表"""
    async with db_manager.get_session() as session:
        query = select(WorkflowTask).where(
            WorkflowTask.user_id == user.id
        ).order_by(desc(WorkflowTask.created_at))

        if status:
            query = query.where(WorkflowTask.status == status)

        return await fetch_paginated(
            session, query, page, page_size,
            mapper=lambda t: {
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "total_steps": t.total_steps,
                "current_step": t.current_step,
                "error_message": t.error_message,
                "started_at": t.started_at.isoformat() if t.started_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
        )


# ============================================================
# 3. 任务详情
# ============================================================

@router.get("/tasks/{task_id}")
async def get_task(
    task_id: int,
    user: User = Depends(get_current_user),
):
    """获取任务详情（含步骤日志）"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(WorkflowTask).where(
                WorkflowTask.id == task_id,
                WorkflowTask.user_id == user.id
            )
        )
        task = result.scalar_one_or_none()
        if not task:
            raise AppException("任务不存在", status_code=404)

        logs_result = await session.execute(
            select(WorkflowTaskLog)
            .where(WorkflowTaskLog.task_id == task_id)
            .order_by(WorkflowTaskLog.step_index)
        )
        logs = logs_result.scalars().all()

        steps_config = json.loads(task.steps_config) if task.steps_config else []

        return success_response(data={
            "id": task.id,
            "name": task.name,
            "status": task.status,
            "total_steps": task.total_steps,
            "current_step": task.current_step,
            "steps_config": steps_config,
            "error_message": task.error_message,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            "logs": [{
                "id": log.id,
                "step_index": log.step_index,
                "step_name": log.step_name,
                "step_label": log.step_label,
                "status": log.status,
                "target_id": log.target_id,
                "target_name": log.target_name,
                "result": json.loads(log.result) if log.result else None,
                "error_message": log.error_message,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            } for log in logs],
        })


# ============================================================
# 4. 启动任务
# ============================================================

@router.post("/tasks/{task_id}/start")
async def start_task(
    task_id: int,
    user: User = Depends(get_current_user),
):
    """启动自动工作流任务"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(WorkflowTask).where(
                WorkflowTask.id == task_id,
                WorkflowTask.user_id == user.id
            )
        )
        task = result.scalar_one_or_none()
        if not task:
            raise AppException("任务不存在", status_code=404)
        if task.status != "pending":
            raise AppException(f"任务已处于 {task.status} 状态，无法启动")

        task.status = "running"
        task.started_at = datetime.now()
        await session.commit()

    asyncio.create_task(_execute_workflow(task_id, user.id))

    return success_response(data={
        "id": task.id,
        "status": "running",
        "message": "任务已启动",
    })


# ============================================================
# 5. 取消任务
# ============================================================

@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: int,
    user: User = Depends(get_current_user),
):
    """取消任务"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(WorkflowTask).where(
                WorkflowTask.id == task_id,
                WorkflowTask.user_id == user.id
            )
        )
        task = result.scalar_one_or_none()
        if not task:
            raise AppException("任务不存在", status_code=404)
        if task.status not in ("pending", "running"):
            raise AppException(f"任务已处于 {task.status} 状态，无法取消")

        task.status = "cancelled"
        await session.commit()

    return success_response(data={"id": task_id, "status": "cancelled"})


# ============================================================
# 6. 删除任务
# ============================================================

@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    user: User = Depends(get_current_user),
):
    """删除任务"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(WorkflowTask).where(
                WorkflowTask.id == task_id,
                WorkflowTask.user_id == user.id
            )
        )
        task = result.scalar_one_or_none()
        if not task:
            raise AppException("任务不存在", status_code=404)

        await session.delete(task)
        await session.commit()

    return success_response(data={"id": task_id}, message="任务已删除")


# ============================================================
# 7. 执行工作流（后台异步）
# ============================================================

async def _execute_workflow(task_id: int, user_id: int):
    """后台执行工作流：采集 → 清洗入库 → 舆情分析"""
    try:
        async with db_manager.get_session() as session:
            result = await session.execute(
                select(WorkflowTask).where(WorkflowTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if not task:
                logger.error(f"[工作流] 任务 {task_id} 不存在")
                return

            steps_config = json.loads(task.steps_config) if task.steps_config else []

            for step_idx, step in enumerate(steps_config):
                await session.refresh(task)
                if task.status == "cancelled":
                    logger.info(f"[工作流] 任务 {task_id} 已被取消")
                    return

                step_type = step.get("step_type", "")
                step_label = step.get("label", "")

                step_log = WorkflowTaskLog(
                    task_id=task_id,
                    step_index=step_idx,
                    step_name=step_type,
                    step_label=step_label,
                    status="running",
                )
                session.add(step_log)
                task.current_step = step_idx
                await session.commit()
                await session.refresh(step_log)

                try:
                    if step_type == "collect":
                        await _execute_collect_step(session, task, step_log, step, user_id)
                    elif step_type == "cleaning":
                        await _execute_cleaning_step(session, task, step_log, step, user_id)
                    elif step_type == "sentiment":
                        await _execute_sentiment_step(session, task, step_log, step, user_id)
                    else:
                        step_log.status = "skipped"
                        step_log.error_message = f"未知步骤类型: {step_type}"
                        await session.commit()

                except Exception as step_err:
                    step_log.status = "failed"
                    step_log.error_message = str(step_err)
                    step_log.completed_at = datetime.now()
                    task.status = "failed"
                    task.error_message = f"步骤 {step_label} 失败: {str(step_err)}"
                    await session.commit()
                    logger.error(f"[工作流] 任务 {task_id} 步骤 {step_label} 失败: {step_err}")
                    return

            task.status = "completed"
            task.completed_at = datetime.now()
            await session.commit()
            logger.info(f"[工作流] 任务 {task_id} 全部完成（采集→清洗→舆情分析）")

    except Exception as e:
        logger.error(f"[工作流] 任务 {task_id} 执行异常: {e}")
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(WorkflowTask).where(WorkflowTask.id == task_id)
                )
                task = result.scalar_one_or_none()
                if task:
                    task.status = "failed"
                    task.error_message = f"执行异常: {str(e)}"
                    await session.commit()
        except:
            pass


async def _execute_collect_step(session, task, step_log, step, user_id):
    """步骤1: 采集所有数据源"""
    source_ids = step.get("source_ids", [])
    sources_info = []
    all_watch_data_ids = []

    for source_id in source_ids:
        result = await session.execute(
            select(WatchSource).where(WatchSource.id == source_id)
        )
        source = result.scalar_one_or_none()
        if not source:
            sources_info.append({"source_id": source_id, "status": "skipped", "error": "瞭望源不存在"})
            continue

        step_log.target_id = source_id
        step_log.target_name = source.name
        step_log.started_at = datetime.now()
        await session.commit()

        try:
            import httpx
            headers = {}
            if source.headers and source.headers != "{}":
                try:
                    headers = json.loads(source.headers)
                except:
                    pass

            async with httpx.AsyncClient(timeout=30) as client:
                if source.method.upper() == "GET":
                    resp = await client.get(source.url, headers=headers)
                elif source.method.upper() == "POST":
                    body = source.body_template or ""
                    resp = await client.post(source.url, content=body, headers=headers)
                else:
                    resp = await client.request(source.method.upper(), source.url, headers=headers)

                raw = resp.text[:10000]
                parsed = None
                try:
                    parsed = resp.json()
                    if isinstance(parsed, (dict, list)):
                        parsed = json.dumps(parsed, ensure_ascii=False)
                except:
                    pass

                watch_data = WatchData(
                    source_id=source_id,
                    raw_response=raw,
                    parsed_data=parsed,
                    status="success" if resp.status_code < 400 else "error",
                    http_status=resp.status_code,
                )
                session.add(watch_data)
                await session.flush()
                all_watch_data_ids.append(watch_data.id)

                sources_info.append({
                    "source_id": source_id,
                    "source_name": source.name,
                    "watch_data_id": watch_data.id,
                    "status": "success",
                    "http_status": resp.status_code,
                })

        except Exception as e:
            sources_info.append({
                "source_id": source_id,
                "source_name": source.name,
                "status": "failed",
                "error": str(e),
            })

    step_log.status = "completed"
    step_log.completed_at = datetime.now()
    step_log.result = json.dumps({
        "sources": sources_info,
        "all_watch_data_ids": all_watch_data_ids,
    }, ensure_ascii=False)
    await session.commit()


async def _execute_cleaning_step(session, task, step_log, step, user_id):
    """步骤2: 清洗采集数据并入库（调用cleaning_service）"""
    step_log.started_at = datetime.now()
    step_log.target_name = "清洗采集数据 → 知识仓库"
    await session.commit()

    # 获取此任务采集的所有watch_data_ids
    # 从上一个步骤(collect)的日志中获取
    collect_log_result = await session.execute(
        select(WorkflowTaskLog).where(
            WorkflowTaskLog.task_id == task.id,
            WorkflowTaskLog.step_name == "collect",
            WorkflowTaskLog.status == "completed"
        ).order_by(desc(WorkflowTaskLog.step_index)).limit(1)
    )
    collect_log = collect_log_result.scalar_one_or_none()

    watch_data_ids = []
    if collect_log and collect_log.result:
        try:
            collect_result = json.loads(collect_log.result)
            watch_data_ids = collect_result.get("all_watch_data_ids", [])
        except:
            pass

    if not watch_data_ids:
        # 尝试直接从数据库中查找当前采集的数据
        result = await session.execute(
            select(WatchData).order_by(desc(WatchData.collected_at)).limit(50)
        )
        watch_data_ids = [wd.id for wd in result.scalars().all()]

    cleaned_count = 0
    failed_count = 0
    cleaning_results = []

    for wd_id in watch_data_ids:
        try:
            cleaning_log_id, exec_log_id = await start_ai_cleaning(
                watch_data_id=wd_id,
                user_id=user_id,
            )
            # 执行清洗管道（在后台执行，但这里我们同步等待完成）
            await execute_cleaning_pipeline(cleaning_log_id, exec_log_id)

            # 检查清洗结果
            async with db_manager.get_session() as check_session:
                cl = await check_session.get(CleaningLog, cleaning_log_id)
                if cl and cl.status == "success":
                    cleaned_count += 1
                    cleaning_results.append({
                        "watch_data_id": wd_id,
                        "cleaning_log_id": cleaning_log_id,
                        "status": "success",
                    })
                else:
                    failed_count += 1
                    cleaning_results.append({
                        "watch_data_id": wd_id,
                        "cleaning_log_id": cleaning_log_id,
                        "status": cl.status if cl else "unknown",
                        "error": cl.error_message if cl else "清洗日志不存在",
                    })
        except Exception as e:
            failed_count += 1
            cleaning_results.append({
                "watch_data_id": wd_id,
                "status": "failed",
                "error": str(e),
            })

    step_log.status = "completed"
    step_log.completed_at = datetime.now()
    step_log.result = json.dumps({
        "total": len(watch_data_ids),
        "cleaned": cleaned_count,
        "failed": failed_count,
        "details": cleaning_results,
    }, ensure_ascii=False)
    await session.commit()


async def _execute_sentiment_step(session, task, step_log, step, user_id):
    """步骤3: 舆情分析"""
    step_log.started_at = datetime.now()
    await session.commit()

    try:
        analysis_id = await trigger_sentiment_analysis(
            trigger_type="workflow",
            user_id=user_id,
        )

        if analysis_id:
            step_log.target_id = analysis_id
            step_log.target_name = f"舆情分析 #{analysis_id}"
            step_log.status = "completed"
            step_log.result = json.dumps({
                "analysis_id": analysis_id,
            }, ensure_ascii=False)
        else:
            step_log.status = "skipped"
            step_log.error_message = "舆情分析无返回结果"
    except Exception as e:
        step_log.status = "failed"
        step_log.error_message = str(e)
        step_log.result = json.dumps({"error": str(e)}, ensure_ascii=False)

    step_log.completed_at = datetime.now()
    await session.commit()


# ============================================================
# 8. 获取瞭望源列表
# ============================================================

@router.get("/sources")
async def list_workflow_sources(
    user: User = Depends(get_current_user),
):
    """获取用户的可选瞭望源列表"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(WatchSource)
            .where(WatchSource.user_id == user.id)
            .order_by(desc(WatchSource.created_at))
        )
        sources = result.scalars().all()
        return success_response(data=[{
            "id": s.id,
            "name": s.name,
            "url": s.url,
            "enabled": s.enabled,
        } for s in sources])


# ============================================================
# 9. 任务统计
# ============================================================

@router.get("/stats")
async def get_workflow_stats(
    user: User = Depends(get_current_user),
):
    """获取工作流统计"""
    async with db_manager.get_session() as session:
        total = await session.scalar(
            select(WorkflowTask).where(WorkflowTask.user_id == user.id).with_only_columns(
                __import__('sqlalchemy').func.count()
            )
        ) or 0

        running = await session.scalar(
            select(WorkflowTask).where(
                WorkflowTask.user_id == user.id,
                WorkflowTask.status == "running"
            ).with_only_columns(__import__('sqlalchemy').func.count())
        ) or 0

        return success_response(data={
            "total": total,
            "running": running,
        })