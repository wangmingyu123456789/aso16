"""
舆情分析服务 - AI 驱动的舆情分析业务逻辑

工作流程：
1. 用户点击舆情分析按钮触发
2. 自动从两个子系统采集增量文本数据：
   - 数据仓库（清洗后已发布文章）：WarehouseArticle（status="published"）
   - 智能问数（AI对话记录）：Message
3. 按时间增量采集：只采集上次分析时间点之后的新数据
   - 若无历史分析记录，采集全部可用数据
4. 将采集数据格式化为结构化文本，调用 LLM 进行 AI 舆情分析
5. 提取情感倾向、事件、关键词、地点信息
6. 写入 SentimentEvent / SentimentWord / SentimentLocation
7. 更新 SentimentDashboard 快照
8. 记录 Token 消耗

注：不再与 WarehouseArticle 的文章 ID 关联，
articles_scope 字段仅记录本次分析的数据源类型和数量
"""
import json
from typing import Optional
from datetime import datetime
from sqlalchemy import select, desc, func
from database.engine import db_manager
from database.models import (
    SentimentAnalysis,
    SentimentEvent,
    SentimentWord,
    SentimentLocation,
    SentimentDashboard,
    WarehouseArticle,
    Message,
    ExecutionLog,
    ExecutionMessage,
    Worker,
    Job,
)
from services.llm_service import (
    call_llm,
    record_token_usage,
    extract_json_from_response,
    build_system_message,
    build_user_message,
    PURPOSE_SENTIMENT,
)
from tools.sentiment_tools import (
    classify_sentiment,
    extract_keywords,
    detect_events,
    extract_locations,
    generate_summary,
    resolve_location_coords,
)
from utils.helpers import AppException, logger

# 舆情分析系统提示词（V2 - 多源数据）
SENTIMENT_SYSTEM_PROMPT = """你是一个专业的舆情分析专家。你的任务是根据用户提供的多源数据，进行全面的舆情分析。

本次分析的数据来源包括两个子系统：
1. **智能问数（AI对话）**：用户在AI问数系统中的对话记录（包含用户问题和AI回复），反映了用户关注的热点话题和情绪倾向。
2. **数据仓库（清洗后文章）**：从数字瞭望采集、经清洗入库的已发布文章，反映了外部环境动态。

请分析以下内容，并以 **纯 JSON 格式** 返回（不要包含 markdown 代码块标记）：

```json
{
  "overall_sentiment": "positive/negative/neutral/mixed",
  "summary": "分析摘要文本，需区分说明数据来源",
  "events": [
    {
      "event_name": "事件名称",
      "sentiment_type": "positive/negative/neutral",
      "description": "事件描述（标注数据来源：智能问数/数据仓库）",
      "keywords": ["关键词1", "关键词2"],
      "heat": 0-100的热度值
    }
  ],
  "words": [
    {
      "word": "关键词",
      "weight": 0-100的权重值,
      "sentiment_type": "positive/negative/neutral",
      "category": "event/topic/entity/emotion"
    }
  ],
  "locations": [
    {
      "location_name": "地点名",
      "description": "相关描述"
    }
  ],
  "sentiment_counts": {
    "positive": 0,
    "negative": 0,
    "neutral": 0
  }
}
```

要求：
1. overall_sentiment 判断整体舆情倾向
2. events 中每个事件需有明确的事件名称和热度值，标注数据来源
3. words 包含所有重要的关键词及权重
4. locations 从文本中识别涉及的地理位置（包括对话中提及的地点）
5. 分析需客观、全面，结合两个数据源的交叉信息"""


# ---------------------------------------------------------------------------
# 查找可用的舆情分析 Worker
# ---------------------------------------------------------------------------

async def _get_sentiment_worker() -> tuple[Optional[Worker], Optional[Job]]:
    """查找第一个可用的舆情分析 Worker"""
    async with db_manager.get_session() as session:
        job_result = await session.execute(
            select(Job).where(Job.code == "sentiment_analysis").limit(1)
        )
        job = job_result.scalar_one_or_none()
        if not job:
            return None, None

        worker_result = await session.execute(
            select(Worker)
            .where(Worker.job_id == job.id)
            .where(Worker.enabled == 1)
            .order_by(Worker.sort_order)
            .limit(1)
        )
        worker = worker_result.scalar_one_or_none()
        return worker, job


# ---------------------------------------------------------------------------
# 获取上次分析时间（用于增量分析）
# ---------------------------------------------------------------------------

async def _get_last_analysis_time() -> Optional[datetime]:
    """获取最近一次成功完成的舆情分析时间"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(SentimentAnalysis.created_at)
            .where(SentimentAnalysis.status == "completed")
            .order_by(desc(SentimentAnalysis.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# 从数据仓库采集清洗后的文章数据
# ---------------------------------------------------------------------------

async def _collect_warehouse_data(since_time: Optional[datetime] = None) -> list[dict]:
    """
    从 WarehouseArticle 表采集清洗后已发布的文章数据

    返回格式：
    [{ "id", "title", "content", "domain_name", "source_type", "source_label" }]
    """
    async with db_manager.get_session() as session:
        query = (
            select(WarehouseArticle)
            .where(WarehouseArticle.status == "published")
            .order_by(WarehouseArticle.created_at)
        )

        if since_time:
            query = query.where(WarehouseArticle.created_at > since_time)

        # 限制最多采集 200 条
        query = query.limit(200)
        result = await session.execute(query)
        articles = result.scalars().all()

    collected = []
    for art in articles:
        collected.append({
            "id": f"wh_{art.id}",
            "title": art.title or "",
            "content": (art.content or "")[:1000],
            "domain_name": art.domain_name or "",
            "source_type": "warehouse",
            "source_label": f"数据仓库-{art.domain_name or '未知'}",
        })

    logger.info(f"从数据仓库采集到 {len(collected)} 篇已发布文章（since={since_time}）")
    return collected


# ---------------------------------------------------------------------------
# 从智能问子系统中采集数据
# ---------------------------------------------------------------------------

async def _collect_chat_data(since_time: Optional[datetime] = None) -> list[dict]:
    """
    从 Message 表采集智能问数对话记录

    返回格式：
    [{ "id", "title", "content", "domain_name", "source_type", "source_label" }]
    """
    async with db_manager.get_session() as session:
        query = select(Message).order_by(Message.created_at)

        if since_time:
            query = query.where(Message.created_at > since_time)

        # 限制最多采集 200 条
        query = query.limit(200)
        result = await session.execute(query)
        messages = result.scalars().all()

    collected = []
    for msg in messages:
        role_label = "用户提问" if msg.role == "user" else "AI回复"
        collected.append({
            "id": f"chat_{msg.id}",
            "title": f"[智能问数] {role_label} - 会话#{msg.conversation_id}",
            "content": msg.content or "",
            "domain_name": "智能问数",
            "source_type": "chat",
            "source_label": f"智能问数-{role_label}",
        })

    logger.info(f"从智能问数采集到 {len(collected)} 条消息记录（since={since_time}）")
    return collected


# ---------------------------------------------------------------------------
# 格式化输入数据供 LLM 分析
# ---------------------------------------------------------------------------

def _format_data_for_llm(data_items: list[dict]) -> str:
    """
    将多源数据格式化为 LLM 可读的文本
    """
    lines = []
    for i, item in enumerate(data_items, 1):
        source_tag = item.get("source_label", item.get("domain_name", "未知来源"))
        title = item.get("title", "")
        content = item.get("content", "")

        # 截取过长内容
        if len(content) > 800:
            content = content[:800] + "…（截断）"

        lines.append(f"--- 数据 #{i} [{source_tag}] ---")
        lines.append(f"标题: {title}" if title else f"来源: {source_tag}")
        if content:
            lines.append(f"内容: {content}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 核心舆情分析逻辑
# ---------------------------------------------------------------------------

async def trigger_sentiment_analysis(
    trigger_type: str = "manual",
    user_id: int = 0,
) -> int:
    """
    触发并执行完整的舆情分析流程。

    自动从「数据仓库（清洗后已发布文章）」和「智能问数（AI对话）」采集增量数据，
    使用 AI 模型进行分析并写入分析结果。

    参数:
    - trigger_type: 触发类型 manual/auto
    - user_id: 触发用户ID

    返回 analysis_id
    """
    # -------------------------------------------------------------------
    # 1. 确定分析范围 - 增量采集两个数据源
    # -------------------------------------------------------------------
    last_time = await _get_last_analysis_time()

    if last_time:
        logger.info(f"增量舆情分析：上次分析时间 {last_time.isoformat()}")
    else:
        logger.info("首次舆情分析：分析全部可用数据")

    # 采集两个数据源
    warehouse_data = await _collect_warehouse_data(last_time)
    chat_data = await _collect_chat_data(last_time)

    # 合并数据（仓库文章在前，对话记录在后）
    all_data = warehouse_data + chat_data

    if not all_data:
        if last_time:
            raise AppException(
                "自上次分析（{}）以来，数据仓库和智能问数均无新增数据".format(
                    last_time.strftime("%Y-%m-%d %H:%M:%S")
                ),
                status_code=400,
            )
        else:
            raise AppException(
                "数据仓库和智能问数均无可用数据，请先在智能问数中发起对话或采集清洗数据",
                status_code=400,
            )

    source_summary = (
        f"数据仓库（清洗后）{len(warehouse_data)} 篇文章 + "
        f"智能问数 {len(chat_data)} 条对话记录"
    )

    # 记录数据范围摘要（不再关联具体文章ID）
    scope_summary = json.dumps({
        "warehouse_article_count": len(warehouse_data),
        "chat_message_count": len(chat_data),
        "since_time": last_time.isoformat() if last_time else None,
        "analysis_time": datetime.now().isoformat(),
    }, ensure_ascii=False)

    # -------------------------------------------------------------------
    # 2. 创建分析任务
    # -------------------------------------------------------------------
    async with db_manager.get_session() as session:
        analysis = SentimentAnalysis(
            trigger_type=trigger_type,
            articles_scope=scope_summary,
            status="processing",
            articles_analyzed=len(all_data),
            overall_sentiment=None,
        )
        session.add(analysis)
        await session.flush()
        analysis_id = analysis.id

        # 3. 查找 Worker 并创建 ExecutionLog
        worker, job = await _get_sentiment_worker()

        exec_log = None
        if worker:
            exec_log = ExecutionLog(
                worker_id=worker.id,
                user_query=f"舆情分析 #{analysis_id}：{source_summary}",
                status="processing",
                sentiment_analysis_id=analysis_id,
            )
            session.add(exec_log)
            await session.flush()

            # 写入系统消息
            session.add(ExecutionMessage(
                execution_log_id=exec_log.id,
                role="system",
                content=SENTIMENT_SYSTEM_PROMPT,
            ))

            # 构造并写入用户消息
            formatted_input = _format_data_for_llm(all_data)
            session.add(ExecutionMessage(
                execution_log_id=exec_log.id,
                role="user",
                content=f"请对以下多源数据进行舆情分析：\n\n{formatted_input}"[:15000],
            ))

        await session.commit()

    # --- 在 session 外执行 AI 分析 ---
    formatted_input = _format_data_for_llm(all_data)
    user_prompt = f"请对以下多源数据进行舆情分析（数据来源：{source_summary}）：\n\n{formatted_input}"

    # 限制输入长度
    if len(user_prompt) > 15000:
        user_prompt = user_prompt[:15000]

    # 先用 LLM 尝试分析
    content = ""
    tokens_used = 0
    model_name = ""
    try:
        messages = [
            build_system_message(SENTIMENT_SYSTEM_PROMPT),
            build_user_message(user_prompt),
        ]

        content, tokens_used, model_name = await call_llm(
            messages=messages,
            purpose=PURPOSE_SENTIMENT,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        logger.warning(f"LLM 舆情分析失败，降级到规则引擎: {e}")
        content = ""

    # 解析 LLM 结果或降级到规则引擎
    result_data = None
    if content:
        result_data = extract_json_from_response(content)
        if not result_data:
            try:
                result_data = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                result_data = None

    if not result_data:
        # 降级到规则引擎分析
        logger.info("使用规则引擎进行舆情分析（降级）")
        result_data = await _rule_based_analysis(all_data)

    # --- 写入分析结果 ---
    async with db_manager.get_session() as session:
        analysis = await session.get(SentimentAnalysis, analysis_id)
        if not analysis:
            return analysis_id

        # 更新状态
        analysis.status = "completed"
        analysis.overall_sentiment = result_data.get("overall_sentiment", "neutral")
        analysis.summary = result_data.get("summary", "") or generate_summary(result_data)

        # 写入事件
        for event_data in result_data.get("events", []):
            event = SentimentEvent(
                analysis_id=analysis_id,
                event_name=event_data.get("event_name", "未知事件")[:256],
                sentiment_type=event_data.get("sentiment_type", "neutral"),
                description=event_data.get("description", ""),
                keywords_json=json.dumps(event_data.get("keywords", []), ensure_ascii=False),
                heat=min(event_data.get("heat", 0), 100),
                related_article_ids=json.dumps(event_data.get("related_article_ids", []), ensure_ascii=False),
            )
            session.add(event)
        await session.flush()

        # 写入关键词
        word_count_map = {}
        for word_data in result_data.get("words", []):
            word_text = word_data.get("word", "")
            if word_text and word_text not in word_count_map:
                word_count_map[word_text] = True
                word = SentimentWord(
                    analysis_id=analysis_id,
                    word=word_text,
                    weight=min(word_data.get("weight", 0), 100),
                    sentiment_type=word_data.get("sentiment_type", "neutral"),
                    category=word_data.get("category", "topic"),
                )
                session.add(word)

        # 写入地点（自动补全 LLM 缺失的经纬度）
        for loc_data in result_data.get("locations", []):
            # 关联到热度最高的事件
            events_result = await session.execute(
                select(SentimentEvent)
                .where(SentimentEvent.analysis_id == analysis_id)
                .order_by(desc(SentimentEvent.heat))
                .limit(1)
            )
            top_event = events_result.scalar_one_or_none()

            location_name = loc_data.get("location_name", "未知")
            longitude = loc_data.get("longitude")
            latitude = loc_data.get("latitude")

            # LLM 没返回经纬度时，从城市坐标字典补全
            if (longitude is None or latitude is None) and location_name:
                coords = resolve_location_coords(location_name)
                if coords:
                    longitude = coords["longitude"]
                    latitude = coords["latitude"]

            location = SentimentLocation(
                event_id=top_event.id if top_event else 0,
                location_name=location_name,
                longitude=longitude,
                latitude=latitude,
                heat=50,
                description=loc_data.get("description", ""),
            )
            session.add(location)

        # 更新 ExecutionLog
        if exec_log:
            exec_log_result = await session.execute(
                select(ExecutionLog).where(ExecutionLog.sentiment_analysis_id == analysis_id)
            )
            exec_log = exec_log_result.scalar_one_or_none()
            if exec_log:
                exec_log.status = "success"
                exec_log.final_response = json.dumps(result_data, ensure_ascii=False)[:5000]
                exec_log.tokens_used = tokens_used

        await session.commit()

    # 更新 Dashboard 快照
    await _update_sentiment_dashboard(analysis_id)

    # 记录 Token 消耗
    if tokens_used > 0:
        await record_token_usage(
            user_id=user_id,
            tokens_used=tokens_used,
            model_name=model_name,
            purpose=PURPOSE_SENTIMENT,
        )

    logger.info(
        f"舆情分析完成 | analysis_id={analysis_id} | "
        f"数据来源={source_summary} | tokens={tokens_used} | model={model_name}"
    )

    return analysis_id


async def _rule_based_analysis(data_items: list[dict]) -> dict:
    """基于规则引擎的舆情分析（LLM 不可用时的降级方案）"""
    all_text = " ".join([
        (item.get("title", "") or "") + " " + ((item.get("content", "") or "") or "")[:500]
        for item in data_items
    ])

    # 情感分类
    sentiment = classify_sentiment(all_text)

    # 事件检测
    article_dicts = [
        {
            "id": item.get("id", ""),
            "title": item.get("title", "") or "",
            "content": (item.get("content", "") or "")[:500],
            "domain_name": item.get("domain_name", "") or "",
        }
        for item in data_items
    ]
    events = detect_events(article_dicts)

    # 关键词
    keywords = extract_keywords(all_text, 30)

    # 地点
    locations = extract_locations(all_text)

    # 情感计数
    sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
    for item in data_items:
        s = classify_sentiment(
            (item.get("title", "") or "") + " " + ((item.get("content", "") or "") or "")[:200]
        )
        sent_type = s["sentiment"]
        if sent_type in sentiment_counts:
            sentiment_counts[sent_type] += 1

    # 摘要
    summary = generate_summary({
        "events": events,
        "words": keywords,
        "sentiment_counts": sentiment_counts,
    })

    return {
        "overall_sentiment": sentiment["sentiment"],
        "summary": summary,
        "events": events,
        "words": keywords,
        "locations": locations,
        "sentiment_counts": sentiment_counts,
    }


async def _update_sentiment_dashboard(analysis_id: int) -> None:
    """根据最新分析结果更新舆情大屏快照"""
    async with db_manager.get_session() as session:
        analysis = await session.get(SentimentAnalysis, analysis_id)
        if not analysis:
            return

        # 统计数据
        total_articles = analysis.articles_analyzed or 0
        overall = analysis.overall_sentiment or "neutral"

        # 查询事件
        events_result = await session.execute(
            select(SentimentEvent).where(SentimentEvent.analysis_id == analysis_id)
        )
        events = events_result.scalars().all()

        total_events = len(events)
        avg_heat = sum(e.heat for e in events) / max(total_events, 1)

        # 查询关键词 top 20
        words_result = await session.execute(
            select(SentimentWord)
            .where(SentimentWord.analysis_id == analysis_id)
            .order_by(desc(SentimentWord.weight))
            .limit(20)
        )
        words = words_result.scalars().all()

        top_words = [{"word": w.word, "weight": w.weight} for w in words]
        top_events = [{"name": e.event_name, "heat": e.heat} for e in events[:10]]

        # 计数情感类型
        positive_count = sum(1 for e in events if e.sentiment_type == "positive")
        negative_count = sum(1 for e in events if e.sentiment_type == "negative")
        neutral_count = sum(1 for e in events if e.sentiment_type == "neutral")

        # 创建快照
        dashboard = SentimentDashboard(
            total_articles=total_articles,
            positive_count=positive_count,
            negative_count=negative_count,
            neutral_count=neutral_count,
            total_events=total_events,
            avg_heat=round(avg_heat, 2),
            top_words_json=json.dumps(top_words, ensure_ascii=False),
            top_events_json=json.dumps(top_events, ensure_ascii=False),
        )
        session.add(dashboard)
        await session.commit()