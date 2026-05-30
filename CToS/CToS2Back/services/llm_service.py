"""
LLM 调用核心服务

提供统一的 OpenAI 兼容 API 调用封装，支持：
- 自动从 api_keys 表选择可用 Key（按用途、排序）
- 流式（SSE）与非流式调用
- Token 消耗统计与记录
- 多轮消息构建
"""
import json
import re
from typing import AsyncGenerator, Optional
from openai import AsyncOpenAI
from sqlalchemy import select
from database.engine import db_manager
from database.models import ApiKey, TokenStat

from utils.helpers import AppException, logger


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

PURPOSE_CHAT = "chat"
PURPOSE_DATA_WORKER = "dataworker"
PURPOSE_SENTIMENT = "sentiment"

# 默认模型参数回退
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 1.0


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

async def select_api_key(purpose: str = "all") -> ApiKey:
    """按用途选取第一个可用的 API Key（按 sort_order 升序）"""
    async with db_manager.get_session() as session:
        stmt = (
            select(ApiKey)
            .where(ApiKey.enabled == 1)
            .where((ApiKey.purpose == purpose) | (ApiKey.purpose == "all"))
            .order_by(ApiKey.sort_order)
            .limit(1)
        )
        result = await session.execute(stmt)
        key = result.scalar_one_or_none()
        if not key:
            raise AppException(
                f"未找到用途为「{purpose}」的可用 API Key，请先在系统配置中添加",
                status_code=400,
            )
        return key


def build_openai_client(api_key: ApiKey) -> AsyncOpenAI:
    """根据 ApiKey 记录构建 AsyncOpenAI 客户端"""
    return AsyncOpenAI(
        base_url=api_key.base_url.rstrip("/") + "/",
        api_key=api_key.api_key,
    )


def build_headers_from_key(api_key: ApiKey) -> dict:
    """构造 LLM 请求参数（不含 messages）"""
    return {
        "model": api_key.model_name or "gpt-4o-mini",
        "max_tokens": api_key.max_tokens or DEFAULT_MAX_TOKENS,
        "temperature": api_key.temperature or DEFAULT_TEMPERATURE,
        "top_p": api_key.top_p or DEFAULT_TOP_P,
    }


# ---------------------------------------------------------------------------
# Token 统计
# ---------------------------------------------------------------------------

async def record_token_usage(
    user_id: int,
    tokens_used: int,
    model_name: str,
    purpose: str,
) -> None:
    """记录 Token 消耗到 token_stats 表（UPSERT 模式）"""
    from datetime import date

    today = date.today().isoformat()
    async with db_manager.get_session() as session:
        stmt = (
            select(TokenStat)
            .where(TokenStat.user_id == user_id)
            .where(TokenStat.date == today)
            .where(TokenStat.purpose == purpose)
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.tokens_used = (existing.tokens_used or 0) + tokens_used
            existing.model_name = model_name
        else:
            session.add(
                TokenStat(
                    user_id=user_id,
                    date=today,
                    tokens_used=tokens_used,
                    model_name=model_name,
                    purpose=purpose,
                )
            )
        await session.commit()


# ---------------------------------------------------------------------------
# 非流式 LLM 调用
# ---------------------------------------------------------------------------

async def call_llm(
    messages: list[dict],
    purpose: str = "all",
    api_key_override: Optional[ApiKey] = None,
    response_format: Optional[dict] = None,
) -> tuple[str, int, str]:
    """
    非流式调用 LLM，返回 (content, token_used, model_name)

    Parameters
    ----------
    messages : list[dict]
        OpenAI 格式的消息列表 [{"role":"user","content":"..."}, ...]
    purpose : str
        用途标识，用于选取 API Key
    api_key_override : ApiKey | None
        若传入则使用该 Key 而非自动选择
    response_format : dict | None
        若传入 {"type":"json_object"} 则强制 LLM 返回 JSON
    """
    api_key = api_key_override or await select_api_key(purpose)
    client = build_openai_client(api_key)
    kwargs = build_headers_from_key(api_key)
    kwargs["messages"] = messages

    if response_format:
        kwargs["response_format"] = response_format

    logger.info(
        f"call_llm | model={kwargs['model']} | purpose={purpose} | "
        f"messages={len(messages)}"
    )

    try:
        resp = await client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        content = choice.message.content or ""
        tokens_used = resp.usage.total_tokens if resp.usage else 0
        model_name = resp.model or kwargs["model"]
        return content, tokens_used, model_name
    except Exception as e:
        logger.exception(f"LLM 调用失败: {e}")
        raise AppException(f"AI 服务调用失败: {str(e)}", status_code=502)


# ---------------------------------------------------------------------------
# 流式 LLM 调用（SSE）
# ---------------------------------------------------------------------------

async def call_llm_stream(
    messages: list[dict],
    purpose: str = "all",
    api_key_override: Optional[ApiKey] = None,
) -> AsyncGenerator[str, None]:
    """
    流式调用 LLM，逐个 yield token。
    最后一个 yield 会附带 meta JSON：{"_meta":{"tokens_used":N,"model":"..."}}
    """
    api_key = api_key_override or await select_api_key(purpose)
    client = build_openai_client(api_key)
    kwargs = build_headers_from_key(api_key)
    kwargs["messages"] = messages
    kwargs["stream"] = True
    kwargs["stream_options"] = {"include_usage": True}

    logger.info(
        f"call_llm_stream | model={kwargs['model']} | purpose={purpose} | "
        f"messages={len(messages)}"
    )

    try:
        full_content = ""
        tokens_used = 0
        model_name = kwargs["model"]

        # 尝试加 stream_options（openai >= 1.31.0 支持），不支持则回退
        stream = await client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    full_content += delta.content
                    yield delta.content

            # 从 usage 获取 token 数（部分版本在最后 chunk 返回 usage）
            if hasattr(chunk, "usage") and chunk.usage:
                tokens_used = chunk.usage.total_tokens or tokens_used
                model_name = chunk.model or model_name

        # 最后 yield meta 信息
        yield json.dumps({
            "_meta": {
                "tokens_used": tokens_used,
                "model": model_name,
            }
        })
    except Exception as e:
        logger.exception(f"LLM 流式调用失败: {e}")
        yield json.dumps({"_error": str(e)})


# ---------------------------------------------------------------------------
# 消息构建工具
# ---------------------------------------------------------------------------

def build_system_message(content: str) -> dict:
    return {"role": "system", "content": content}


def build_user_message(content: str) -> dict:
    return {"role": "user", "content": content}


def build_assistant_message(content: str = "") -> dict:
    return {"role": "assistant", "content": content}


def extract_json_from_response(text: str) -> Optional[dict]:
    """从 LLM 回复中提取 JSON（可能被 markdown 包围）"""
    # 尝试 ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试直接解析为 JSON
    text_clean = text.strip()
    try:
        return json.loads(text_clean)
    except json.JSONDecodeError:
        pass
    return None