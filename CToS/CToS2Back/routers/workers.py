"""数字员工 Workers 模块"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, desc
from database.engine import db_manager
from database.models import User, Worker, Job, ExecutionLog, ExecutionMessage, Tool, ApiKey
from middleware.auth_middleware import get_current_user
from utils.helpers import success_response, AppException
from utils.db_utils import fetch_paginated

router = APIRouter(prefix="/api/workers", tags=["数字员工"])

class WorkerCreate(BaseModel):
    job_id: int
    name: str
    icon: str = "🤖"
    description: str = ""
    system_prompt: str = ""
    api_key_id: int = None

class WorkerUpdate(BaseModel):
    name: str = None
    icon: str = None
    description: str = None
    job_id: int = None
    system_prompt: str = None
    api_key_id: int = None
    enabled: int = None

class ExecutionRequest(BaseModel):
    user_query: str

class JobCreate(BaseModel):
    name: str
    code: str
    description: str = ""
    icon: str = "🤖"
    prompt_template: str = ""
    tool_names: str = "[]"
    sort_order: int = 0

class JobUpdate(BaseModel):
    name: str = None
    description: str = None
    icon: str = None
    prompt_template: str = None
    tool_names: str = None
    sort_order: int = None

class ToolCreate(BaseModel):
    name: str
    description: str = ""
    function_schema: str = "{}"
    module_path: str = ""


# ===== 工作管理 =====

@router.get("/jobs")
async def list_jobs(user: User = Depends(get_current_user)):
    """获取工作列表"""
    async with db_manager.get_session() as session:
        result = await session.execute(select(Job).order_by(Job.sort_order))
        jobs = result.scalars().all()
        return success_response(data=[{
            "id": j.id, "name": j.name, "code": j.code,
            "description": j.description, "icon": j.icon,
            "tool_names": j.tool_names, "is_preset": j.is_preset,
        } for j in jobs])

@router.post("/jobs")
async def create_job(req: JobCreate, user: User = Depends(get_current_user)):
    """创建工作"""
    async with db_manager.get_session() as session:
        job = Job(
            name=req.name, code=req.code,
            description=req.description, icon=req.icon,
            prompt_template=req.prompt_template,
            tool_names=req.tool_names, sort_order=req.sort_order,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return success_response(data={"id": job.id}, message="工作创建成功")

@router.get("/jobs/{job_id}")
async def get_job(job_id: int, user: User = Depends(get_current_user)):
    """获取单个工作详情"""
    async with db_manager.get_session() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise AppException("工作不存在", status_code=404)
        return success_response(data={
            "id": job.id, "name": job.name, "code": job.code,
            "description": job.description, "icon": job.icon,
            "prompt_template": job.prompt_template,
            "tool_names": job.tool_names,
            "is_preset": job.is_preset, "sort_order": job.sort_order,
        })

@router.put("/jobs/{job_id}")
async def update_job(job_id: int, req: JobUpdate, user: User = Depends(get_current_user)):
    """编辑工作"""
    async with db_manager.get_session() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise AppException("工作不存在", status_code=404)
        if req.name is not None:
            job.name = req.name
        if req.description is not None:
            job.description = req.description
        if req.icon is not None:
            job.icon = req.icon
        if req.prompt_template is not None:
            job.prompt_template = req.prompt_template
        if req.tool_names is not None:
            job.tool_names = req.tool_names
        if req.sort_order is not None:
            job.sort_order = req.sort_order
        await session.commit()
        return success_response(message="工作已更新")

@router.delete("/jobs/{job_id}")
async def delete_job(job_id: int, user: User = Depends(get_current_user)):
    """删除工作"""
    async with db_manager.get_session() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise AppException("工作不存在", status_code=404)
        if job.is_preset:
            raise AppException("预设工作不可删除", status_code=400)
        await session.delete(job)
        await session.commit()
        return success_response(message="工作已删除")


# ===== 数字员工管理 =====

@router.get("")
async def list_workers(user: User = Depends(get_current_user)):
    """获取数字员工列表"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Worker).order_by(Worker.sort_order)
        )
        workers = result.scalars().all()
        return success_response(data=[{
            "id": w.id, "name": w.name, "icon": w.icon,
            "description": w.description, "job_id": w.job_id,
            "enabled": w.enabled,
        } for w in workers])

@router.post("")
async def create_worker(req: WorkerCreate, user: User = Depends(get_current_user)):
    """创建数字员工（事务：先创建 role=worker 的 User 记录，再创建 Worker）"""
    async with db_manager.get_session() as session:
        # Step 1: 生成唯一的用户名（users.username 有 UNIQUE 约束）
        base_username = req.name.replace(" ", "_")[:50]
        import time
        unique_suffix = str(int(time.time() * 1000))[-6:]
        worker_username = f"{base_username}_{unique_suffix}"

        # 创建 role='worker' 的 User 记录（password_hash=NULL 不可登录）
        worker_user = User(
            username=worker_username,
            password_hash=None,
            nickname=req.name,
            role="worker",
            status="active",
        )
        session.add(worker_user)
        await session.flush()

        # Step 2: 创建 Worker 记录，user_id 指向刚创建的 worker 用户
        worker = Worker(
            user_id=worker_user.id,
            job_id=req.job_id,
            name=req.name,
            icon=req.icon,
            description=req.description,
            system_prompt=req.system_prompt,
            api_key_id=req.api_key_id,
        )
        session.add(worker)
        await session.commit()
        await session.refresh(worker)
        return success_response(data={"id": worker.id}, message="员工创建成功")

@router.get("/{worker_id}")
async def get_worker(worker_id: int, user: User = Depends(get_current_user)):
    """获取员工详情"""
    async with db_manager.get_session() as session:
        worker = await session.get(Worker, worker_id)
        if not worker:
            raise AppException("员工不存在", status_code=404)

        # 获取关联的工作信息
        job = None
        if worker.job_id:
            job = await session.get(Job, worker.job_id)

        return success_response(data={
            "id": worker.id, "name": worker.name, "icon": worker.icon,
            "description": worker.description, "job_id": worker.job_id,
            "job_name": job.name if job else None,
            "system_prompt": worker.system_prompt,
            "api_key_id": worker.api_key_id,
            "enabled": worker.enabled,
            "is_preset": worker.is_preset,
            "created_at": worker.created_at.isoformat() if worker.created_at else None,
        })

@router.put("/{worker_id}")
async def update_worker(worker_id: int, req: WorkerUpdate, user: User = Depends(get_current_user)):
    """编辑员工"""
    async with db_manager.get_session() as session:
        worker = await session.get(Worker, worker_id)
        if not worker:
            raise AppException("员工不存在", status_code=404)
        if req.name is not None:
            worker.name = req.name
        if req.icon is not None:
            worker.icon = req.icon
        if req.description is not None:
            worker.description = req.description
        if req.job_id is not None:
            worker.job_id = req.job_id
        if req.system_prompt is not None:
            worker.system_prompt = req.system_prompt
        if req.api_key_id is not None:
            worker.api_key_id = req.api_key_id
        if req.enabled is not None:
            worker.enabled = req.enabled
        await session.commit()
        return success_response(message="员工已更新")

@router.delete("/{worker_id}")
async def delete_worker(worker_id: int, user: User = Depends(get_current_user)):
    """删除员工"""
    async with db_manager.get_session() as session:
        worker = await session.get(Worker, worker_id)
        if not worker:
            raise AppException("员工不存在", status_code=404)
        if worker.is_preset:
            raise AppException("预设员工不可删除", status_code=400)
        await session.delete(worker)
        await session.commit()
        return success_response(message="员工已删除")

@router.put("/{worker_id}/toggle")
async def toggle_worker(worker_id: int, user: User = Depends(get_current_user)):
    """启用/禁用员工"""
    async with db_manager.get_session() as session:
        worker = await session.get(Worker, worker_id)
        if not worker:
            raise AppException("员工不存在", status_code=404)
        worker.enabled = 1 - worker.enabled
        await session.commit()
        status_text = "已启用" if worker.enabled else "已禁用"
        return success_response(data={"enabled": worker.enabled}, message=f"员工{status_text}")


# ===== 执行任务 =====

@router.post("/{worker_id}/execute")
async def execute_worker(worker_id: int, req: ExecutionRequest, user: User = Depends(get_current_user)):
    """执行数字员工任务"""
    async with db_manager.get_session() as session:
        worker = await session.get(Worker, worker_id)
        if not worker:
            raise AppException("员工不存在", status_code=404)

        log = ExecutionLog(worker_id=worker.id, user_query=req.user_query, status="processing")
        session.add(log)
        await session.commit()
        await session.refresh(log)

        return success_response(data={"execution_id": log.id}, message="任务已提交")


# ===== 执行记录 =====

@router.get("/executions/{execution_id}")
async def get_execution(execution_id: int, user: User = Depends(get_current_user)):
    """获取执行详情"""
    async with db_manager.get_session() as session:
        log = await session.get(ExecutionLog, execution_id)
        if not log:
            raise AppException("执行记录不存在", status_code=404)

        result = await session.execute(
            select(ExecutionMessage).where(ExecutionMessage.execution_log_id == execution_id)
            .order_by(ExecutionMessage.created_at)
        )
        messages = result.scalars().all()

        return success_response(data={
            "id": log.id, "status": log.status,
            "user_query": log.user_query,
            "final_response": log.final_response,
            "tokens_used": log.tokens_used,
            "messages": [{
                "role": m.role, "content": m.content,
                "tool_calls_json": m.tool_calls_json,
            } for m in messages],
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })


# ===== 工具管理 =====

@router.post("/tools")
async def register_tool(req: ToolCreate, user: User = Depends(get_current_user)):
    """注册工具"""
    async with db_manager.get_session() as session:
        tool = Tool(
            name=req.name, description=req.description,
            function_schema=req.function_schema, module_path=req.module_path,
        )
        session.add(tool)
        await session.commit()
        await session.refresh(tool)
        return success_response(data={"id": tool.id}, message="工具注册成功")