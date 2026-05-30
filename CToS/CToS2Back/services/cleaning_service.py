"""
数据清洗服务 - AI 驱动的数据清洗业务逻辑

工作流程：
1. 用户选定 watch_data（采集数据）发起清洗
2. 系统创建 CleaningLog + ExecutionLog
3. 调用 LLM 进行 AI 清洗（使用 dataworker 用途的 API Key）
4. 提取结构化信息并验证
5. 清洗成功 → 自动写入 WarehouseArticle
6. 记录 Token 消耗
"""
import json
from typing import Optional
from sqlalchemy import select
from database.engine import db_manager
from database.models import (
    CleaningLog,
    WatchData,
    ExecutionLog,
    ExecutionMessage,
    WarehouseArticle,
    Worker,
    Job,
    Tool,
    User,
)
from services.llm_service import (
    call_llm,
    record_token_usage,
    extract_json_from_response,
    build_system_message,
    build_user_message,
    PURPOSE_DATA_WORKER,
)
from tools.cleaning_tools import (
    extract_structural_info,
    clean_html_content,
    parse_json_data,
    validate_result,
    extract_domain,
)
from utils.helpers import AppException, logger

# 清洗提示词（用于 AI 清洗）
CLEANING_SYSTEM_PROMPT = """你是一个专业的数据清洗助手。你的任务是分析用户提供的原始采集数据，提取结构化信息。

请从原始数据中提取以下字段，并以 **纯 JSON 格式** 返回（不要包含 markdown 代码块标记）：

```json
{
  "title": "提取的文章标题",
  "content": "纯文本正文（去掉HTML标签、脚本等无关内容）",
  "domain_name": "来源网站域名（去www.前缀）",
  "summary": "200字以内的内容摘要"
}
```

要求：
1. title 尽量从 HTML 的 title 标签或首段中提取
2. content 需要去除 script、style 标签和所有 HTML 标签
3. domain_name 从 URL 中提取，需要去掉 "www." 前缀
4. 如果数据无法解析，返回 {"error": "原因说明"}
5. 只返回 JSON，不要附加任何解释文字

注意：temperature 参数已设为 0.3，请尽可能精确提取。"""


# ---------------------------------------------------------------------------
# 查找可用的清洗 Worker
# ---------------------------------------------------------------------------

async def _get_cleaning_worker() -> tuple[Optional[Worker], Optional[Job]]:
    """查找第一个可用的清洗 Worker（关联 data_cleaner 工作）"""
    async with db_manager.get_session() as session:
        # 查找 data_cleaner 工作
        job_result = await session.execute(
            select(Job).where(Job.code == "data_cleaner").limit(1)
        )
        job = job_result.scalar_one_or_none()
        if not job:
            return None, None

        # 查找启用的 Worker
        worker_result = await session.execute(
            select(Worker)
            .where(Worker.job_id == job.id)
            .where(Worker.enabled == 1)
            .order_by(Worker.sort_order)
            .limit(1)
        )
        worker = worker_result.scalar_one_or_none()
        return worker, job


async def _get_regex_worker() -> tuple[Optional[Worker], Optional[Job]]:
    """查找使用 data_cleaner 工作的任意启用 Worker（正则回退时也可用）"""
    return await _get_cleaning_worker()


# ---------------------------------------------------------------------------
# 核心清洗逻辑
# ---------------------------------------------------------------------------

async def start_ai_cleaning(
    watch_data_id: int,
    worker_id: Optional[int] = None,
    user_id: int = 0,
) -> tuple[int, int]:
    """
    启动 AI 数据清洗。

    返回 (cleaning_log_id, execution_log_id)
    """
    async with db_manager.get_session() as session:
        # 1. 检查原始数据
        watch_data = await session.get(WatchData, watch_data_id)
        if not watch_data:
            raise AppException(f"采集数据 #{watch_data_id} 不存在", status_code=404)

        raw_text = watch_data.raw_response or ""
        if not raw_text:
            raise AppException(f"采集数据 #{watch_data_id} 内容为空，无法清洗", status_code=400)

        # 2. 确定 Worker
        worker = None
        job = None
        if worker_id:
            worker = await session.get(Worker, worker_id)
            if worker:
                job = await session.get(Job, worker.job_id)
        else:
            worker, job = await _get_cleaning_worker()

        if not worker:
            raise AppException(
                "未找到可用的清洗数字员工，请先创建一个绑定 data_cleaner 工作的员工",
                status_code=400,
            )

        # 3. 创建 CleaningLog
        cleaning_log = CleaningLog(
            watch_data_id=watch_data_id,
            method="ai",
            status="processing",
        )
        session.add(cleaning_log)
        await session.flush()

        # 4. 创建 ExecutionLog（关联到 cleaning_log，实现多轮工具调用的记录）
        exec_log = ExecutionLog(
            worker_id=worker.id,
            user_query=f"清洗瞭望数据 #{watch_data_id}：{raw_text[:500]}",
            status="processing",
            cleaning_log_id=cleaning_log.id,
        )
        session.add(exec_log)
        await session.flush()

        # 5. 写入系统提示词和用户输入到 execution_messages
        system_msg = ExecutionMessage(
            execution_log_id=exec_log.id,
            role="system",
            content=CLEANING_SYSTEM_PROMPT,
        )
        session.add(system_msg)

        user_msg = ExecutionMessage(
            execution_log_id=exec_log.id,
            role="user",
            content=f"请清洗以下数据：\n\n源URL: {watch_data.parsed_data or '无'}\n原始内容:\n{raw_text[:8000]}",
        )
        session.add(user_msg)

        await session.commit()

    # --- 在 session 外执行 LLM 调用（异步非阻塞） ---
    # 通过后台任务执行完整的清洗流程
    # 但这里我们先返回，让调用方决定是否异步执行

    return cleaning_log.id, exec_log.id


async def execute_cleaning_pipeline(
    cleaning_log_id: int,
    execution_log_id: int,
    user_id: int = 0,
) -> None:
    """
    执行完整的清洗流水线（LLM 调用 + 工具验证 + 入库）。

    此函数应在后台任务中执行。
    """
    async with db_manager.get_session() as session:
        cleaning_log = await session.get(CleaningLog, cleaning_log_id)
        exec_log = await session.get(ExecutionLog, execution_log_id)
        if not cleaning_log or not exec_log:
            logger.error(f"清洗记录不存在: cleaning_log={cleaning_log_id}, execution_log={execution_log_id}")
            return

        watch_data = await session.get(WatchData, cleaning_log.watch_data_id)
        raw_text = watch_data.raw_response if watch_data else ""

    # --- 1. 调用 LLM 进行 AI 清洗 ---
    messages = [
        build_system_message(CLEANING_SYSTEM_PROMPT),
        build_user_message(f"请清洗以下数据：\n\n原始内容:\n{raw_text[:8000]}"),
    ]

    try:
        content, tokens_used, model_name = await call_llm(
            messages=messages,
            purpose=PURPOSE_DATA_WORKER,
            response_format={"type": "json_object"},
        )
    except AppException as e:
        await _fail_cleaning(cleaning_log_id, execution_log_id, str(e))
        return
    except Exception as e:
        await _fail_cleaning(cleaning_log_id, execution_log_id, f"LLM 调用异常: {str(e)}")
        return

    # --- 2. 解析 LLM 返回的 JSON ---
    result_data = extract_json_from_response(content)
    if not result_data:
        # 尝试直接解析
        try:
            result_data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            await _fail_cleaning(cleaning_log_id, execution_log_id, "LLM 返回了非 JSON 格式内容")
            return

    # --- 3. 如果 LLM 返回了 error，直接失败 ---
    if "error" in result_data:
        await _fail_cleaning(cleaning_log_id, execution_log_id, result_data["error"])
        return

    # --- 4. 验证清洗结果 ---
    validation = validate_result(result_data)
    if not validation["valid"]:
        # 尝试用规则工具补充
        fallback = extract_structural_info(raw_text)
        result_data["title"] = result_data.get("title") or fallback["title"]
        result_data["content"] = result_data.get("content") or fallback["content"]
        result_data["domain_name"] = result_data.get("domain_name") or fallback["domain_name"]
        result_data["summary"] = result_data.get("summary") or fallback["summary"]

        # 再次验证
        validation = validate_result(result_data)
        if not validation["valid"]:
            await _fail_cleaning(
                cleaning_log_id,
                execution_log_id,
                f"清洗结果不完整: {json.dumps(validation['missing_fields'], ensure_ascii=False)}",
            )
            return

    # --- 5. 写入 LLM 的 assistant 回复到 execution_messages ---
    async with db_manager.get_session() as session:
        # 重新查询 cleaning_log 和 exec_log（它们属于上一个 session，已 detached）
        cleaning_log = await session.get(CleaningLog, cleaning_log_id)
        exec_log = await session.get(ExecutionLog, execution_log_id)
        if not cleaning_log or not exec_log:
            logger.error(f"清洗记录不存在: cleaning_log={cleaning_log_id}, execution_log={execution_log_id}")
            return

        assistant_msg = ExecutionMessage(
            execution_log_id=execution_log_id,
            role="assistant",
            content=json.dumps(result_data, ensure_ascii=False),
        )
        session.add(assistant_msg)

        # 6. 创建 WarehouseArticle
        article = WarehouseArticle(
            watch_data_id=cleaning_log.watch_data_id,
            cleaning_log_id=cleaning_log_id,
            title=result_data.get("title", "")[:512],
            domain_name=result_data.get("domain_name", ""),
            content=result_data.get("content", ""),
            status="published",
        )
        session.add(article)
        await session.flush()

        # 7. 更新 CleaningLog 状态
        cleaning_log.status = "success"
        cleaning_log.result = json.dumps(result_data, ensure_ascii=False)

        # 8. 更新 ExecutionLog 状态
        exec_log.status = "success"
        exec_log.final_response = json.dumps(result_data, ensure_ascii=False)
        exec_log.tokens_used = tokens_used

        await session.commit()

    # 9. 记录 Token 消耗
    await record_token_usage(
        user_id=user_id or 0,
        tokens_used=tokens_used,
        model_name=model_name,
        purpose=PURPOSE_DATA_WORKER,
    )

    logger.info(
        f"清洗完成 | cleaning_log={cleaning_log_id} | "
        f"tokens={tokens_used} | model={model_name}"
    )


async def _fail_cleaning(
    cleaning_log_id: int,
    execution_log_id: int,
    error_message: str,
) -> None:
    """将清洗标记为失败"""
    async with db_manager.get_session() as session:
        cleaning_log = await session.get(CleaningLog, cleaning_log_id)
        exec_log = await session.get(ExecutionLog, execution_log_id)
        if cleaning_log:
            cleaning_log.status = "failed"
            cleaning_log.error_message = error_message[:500]
            cleaning_log.result = json.dumps({"error": error_message}, ensure_ascii=False)
        if exec_log:
            exec_log.status = "error"
            exec_log.final_response = error_message
        await session.commit()
    logger.error(f"清洗失败 | cleaning_log={cleaning_log_id} | error={error_message}")


# ---------------------------------------------------------------------------
# 正则规则清洗（回退方案）
# ---------------------------------------------------------------------------

async def start_regex_cleaning(
    watch_data_id: int,
    user_id: int = 0,
) -> int:
    """启动基于正则规则的数据清洗（非 AI，不消耗 Token）"""
    async with db_manager.get_session() as session:
        watch_data = await session.get(WatchData, watch_data_id)
        if not watch_data:
            raise AppException(f"采集数据 #{watch_data_id} 不存在", status_code=404)

        raw_text = watch_data.raw_response or ""

        cleaning_log = CleaningLog(
            watch_data_id=watch_data_id,
            method="regex",
            status="processing",
        )
        session.add(cleaning_log)
        await session.flush()

    # 执行规则清洗
    result = extract_structural_info(raw_text)
    validation = validate_result(result)

    async with db_manager.get_session() as session:
        cleaning_log = await session.get(CleaningLog, cleaning_log.id)
        if not cleaning_log:
            return 0

        if validation["valid"]:
            # 创建 WarehouseArticle
            article = WarehouseArticle(
                watch_data_id=watch_data_id,
                cleaning_log_id=cleaning_log.id,
                title=result.get("title", "")[:512],
                domain_name=result.get("domain_name", ""),
                content=result.get("content", ""),
                status="published",
            )
            session.add(article)

            cleaning_log.status = "success"
            cleaning_log.result = json.dumps(result, ensure_ascii=False)
        else:
            cleaning_log.status = "failed"
            cleaning_log.error_message = f"规则清洗结果不完整: {json.dumps(validation['missing_fields'], ensure_ascii=False)}"
            cleaning_log.result = json.dumps(result, ensure_ascii=False)

        await session.commit()
        return cleaning_log.id


# ---------------------------------------------------------------------------
# 工具函数仓库
# ---------------------------------------------------------------------------

TOOL_REGISTRY = {
    "extract_structural_info": extract_structural_info,
    "clean_html_content": clean_html_content,
    "parse_json_data": parse_json_data,
    "validate_result": validate_result,
    "extract_domain": extract_domain,
}


def get_tool_function(tool_name: str):
    """根据工具名称获取可调用的工具函数"""
    return TOOL_REGISTRY.get(tool_name)


async def get_tool_schemas_for_worker(worker_id: int) -> list[dict]:
    """获取 Worker 关联的所有工具的 function_schema"""
    async with db_manager.get_session() as session:
        worker = await session.get(Worker, worker_id)
        if not worker:
            return []

        job = await session.get(Job, worker.job_id)
        if not job:
            return []

        # 从 job.tool_names 解析工具名称列表
        try:
            tool_names = json.loads(job.tool_names) if job.tool_names else []
        except (json.JSONDecodeError, TypeError):
            tool_names = []

        if not tool_names:
            return []

        # 从 Tool 表查询
        result = await session.execute(
            select(Tool).where(Tool.name.in_(tool_names))
        )
        tools = result.scalars().all()
        schemas = []
        for t in tools:
            try:
                schemas.append(json.loads(t.function_schema))
            except (json.JSONDecodeError, TypeError):
                schemas.append({"name": t.name, "description": t.description})
        return schemas