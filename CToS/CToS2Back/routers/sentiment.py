"""舆情分析 Sentiment 模块

遵循数据库详细设计 3.12 智慧舆情 定义。
集成 services/sentiment_service.py 的 AI 舆情分析业务逻辑。
支持 LLM 分析 + 规则引擎降级。
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from typing import Optional
from database.engine import db_manager
from database.models import (
    User,
    SentimentAnalysis,
    SentimentEvent,
    SentimentWord,
    SentimentLocation,
    SentimentDashboard,
    WarehouseArticle,
)
from middleware.auth_middleware import get_current_user
from utils.helpers import success_response, AppException
from utils.db_utils import fetch_paginated
from services.sentiment_service import trigger_sentiment_analysis

router = APIRouter(prefix="/api/sentiment", tags=["舆情分析"])


class TriggerAnalysisRequest(BaseModel):
    """触发舆情分析请求"""
    trigger_type: str = "manual"


# ============================================================
# 1. 舆情分析任务
# ============================================================

@router.get("/analyses")
async def list_analyses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
):
    """获取舆情分析列表"""
    async with db_manager.get_session() as session:
        return await fetch_paginated(
            session,
            select(SentimentAnalysis).order_by(desc(SentimentAnalysis.created_at)),
            page, page_size,
            mapper=lambda a: {
                "id": a.id,
                "trigger_type": a.trigger_type,
                "status": a.status,
                "summary": a.summary,
                "overall_sentiment": a.overall_sentiment,
                "articles_analyzed": a.articles_analyzed,
                "articles_scope": a.articles_scope,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            }
        )


@router.get("/analyses/{analysis_id}")
async def get_analysis_detail(
    analysis_id: int,
    user: User = Depends(get_current_user),
):
    """获取舆情分析详情（含关联事件 + 关键词 + 地点）"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(SentimentAnalysis).where(SentimentAnalysis.id == analysis_id)
        )
        analysis = result.scalar_one_or_none()
        if not analysis:
            raise AppException(status_code=404, message="分析任务不存在")

        # 查询关联事件
        events_result = await session.execute(
            select(SentimentEvent)
            .where(SentimentEvent.analysis_id == analysis_id)
            .order_by(desc(SentimentEvent.heat))
        )
        events = events_result.scalars().all()

        # 查询关联关键词
        words_result = await session.execute(
            select(SentimentWord)
            .where(SentimentWord.analysis_id == analysis_id)
            .order_by(desc(SentimentWord.weight))
        )
        words = words_result.scalars().all()

        # 查询关联地点
        if events:
            event_ids = [e.id for e in events]
            locs_result = await session.execute(
                select(SentimentLocation)
                .where(SentimentLocation.event_id.in_(event_ids))
                .order_by(desc(SentimentLocation.heat))
            )
            locations = locs_result.scalars().all()
        else:
            locations = []

        return success_response(data={
            "id": analysis.id,
            "trigger_type": analysis.trigger_type,
            "status": analysis.status,
            "summary": analysis.summary,
            "overall_sentiment": analysis.overall_sentiment,
            "articles_analyzed": analysis.articles_analyzed,
            "articles_scope": analysis.articles_scope,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
            "updated_at": analysis.updated_at.isoformat() if analysis.updated_at else None,
            "events": [{
                "id": e.id,
                "event_name": e.event_name,
                "sentiment_type": e.sentiment_type,
                "description": e.description,
                "keywords_json": e.keywords_json,
                "heat": e.heat,
                "related_article_ids": e.related_article_ids,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            } for e in events],
            "words": [{
                "id": w.id,
                "word": w.word,
                "weight": w.weight,
                "sentiment_type": w.sentiment_type,
                "category": w.category,
            } for w in words],
            "locations": [{
                "id": loc.id,
                "event_id": loc.event_id,
                "location_name": loc.location_name,
                "longitude": loc.longitude,
                "latitude": loc.latitude,
                "heat": loc.heat,
                "description": loc.description,
            } for loc in locations],
        })


@router.post("/analyses/trigger")
async def trigger_analysis(
    req: TriggerAnalysisRequest,
    user: User = Depends(get_current_user),
):
    """手动触发舆情分析

    从数据仓库中选取文章进行分析，支持指定文章ID列表或自动选择。
    分析过程会同步执行 LLM 调用（或降级到规则引擎），
    自动创建 SentimentEvent / SentimentWord / SentimentLocation
    并更新 SentimentDashboard 快照。
    """
    try:
        analysis_id = await trigger_sentiment_analysis(
            trigger_type=req.trigger_type,
            user_id=user.id,
        )

        return success_response(
            data={"id": analysis_id},
            message="舆情分析完成"
        )
    except AppException as e:
        raise e
    except Exception as e:
        raise AppException(f"舆情分析执行失败: {str(e)}", status_code=500)


# ============================================================
# 2. 舆情事件
# ============================================================

@router.get("/events")
async def list_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    analysis_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
):
    """获取舆情事件列表"""
    async with db_manager.get_session() as session:
        query = select(SentimentEvent).order_by(desc(SentimentEvent.heat))
        if analysis_id:
            query = query.where(SentimentEvent.analysis_id == analysis_id)
        return await fetch_paginated(
            session, query, page, page_size,
            mapper=lambda e: {
                "id": e.id,
                "analysis_id": e.analysis_id,
                "event_name": e.event_name,
                "sentiment_type": e.sentiment_type,
                "description": e.description,
                "keywords_json": e.keywords_json,
                "heat": e.heat,
                "related_article_ids": e.related_article_ids,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
        )


# ============================================================
# 3. 舆情词云
# ============================================================

@router.get("/wordcloud")
async def get_wordcloud(
    analysis_id: Optional[int] = Query(None),
    sentiment_type: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
):
    """获取舆情词云数据"""
    async with db_manager.get_session() as session:
        query = select(SentimentWord).order_by(desc(SentimentWord.weight))
        if analysis_id:
            query = query.where(SentimentWord.analysis_id == analysis_id)
        if sentiment_type:
            query = query.where(SentimentWord.sentiment_type == sentiment_type)
        result = await session.execute(query)
        words = result.scalars().all()
        return success_response(data=[{
            "id": w.id,
            "word": w.word,
            "weight": w.weight,
            "sentiment_type": w.sentiment_type,
            "category": w.category,
        } for w in words])


# ============================================================
# 4. 舆情地点（3D地球）
# ============================================================

@router.get("/locations")
async def list_locations(
    event_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
):
    """获取舆情地点标记数据（用于3D地球）"""
    async with db_manager.get_session() as session:
        query = select(SentimentLocation).order_by(desc(SentimentLocation.heat))
        if event_id:
            query = query.where(SentimentLocation.event_id == event_id)
        result = await session.execute(query)
        locations = result.scalars().all()
        return success_response(data=[{
            "id": loc.id,
            "event_id": loc.event_id,
            "location_name": loc.location_name,
            "longitude": loc.longitude,
            "latitude": loc.latitude,
            "heat": loc.heat,
            "description": loc.description,
            "created_at": loc.created_at.isoformat() if loc.created_at else None,
        } for loc in locations])


# ============================================================
# 5. 舆情大屏
# ============================================================

@router.get("/dashboard")
async def get_dashboard(
    user: User = Depends(get_current_user),
):
    """获取最新舆情大屏数据"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(SentimentDashboard)
            .order_by(desc(SentimentDashboard.snapshot_at))
            .limit(1)
        )
        dashboard = result.scalar_one_or_none()
        if not dashboard:
            return success_response(data={
                "total_articles": 0, "positive_count": 0,
                "negative_count": 0, "neutral_count": 0,
                "total_events": 0, "avg_heat": 0.0,
                "top_words_json": "[]", "top_events_json": "[]",
                "snapshot_at": None,
            })
        return success_response(data={
            "id": dashboard.id,
            "total_articles": dashboard.total_articles,
            "positive_count": dashboard.positive_count,
            "negative_count": dashboard.negative_count,
            "neutral_count": dashboard.neutral_count,
            "total_events": dashboard.total_events,
            "avg_heat": dashboard.avg_heat,
            "top_words_json": dashboard.top_words_json,
            "top_events_json": dashboard.top_events_json,
            "snapshot_at": dashboard.snapshot_at.isoformat() if dashboard.snapshot_at else None,
        })


# ============================================================
# 6. 统计概览
# ============================================================

@router.get("/stats")
async def get_sentiment_stats(
    user: User = Depends(get_current_user),
):
    """获取舆情分析统计概览"""
    async with db_manager.get_session() as session:
        # 分析总数
        total_result = await session.execute(
            select(func.count(SentimentAnalysis.id))
        )
        total_analyses = total_result.scalar() or 0

        # 各情感倾向统计
        sentiment_counts = await session.execute(
            select(
                SentimentAnalysis.overall_sentiment,
                func.count(SentimentAnalysis.id)
            )
            .where(SentimentAnalysis.overall_sentiment.isnot(None))
            .group_by(SentimentAnalysis.overall_sentiment)
        )
        sentiment_map = dict(sentiment_counts.all())

        # 事件总数
        events_result = await session.execute(
            select(func.count(SentimentEvent.id))
        )
        total_events = events_result.scalar() or 0

        return success_response(data={
            "total_analyses": total_analyses,
            "positive_count": sentiment_map.get("positive", 0),
            "negative_count": sentiment_map.get("negative", 0),
            "neutral_count": sentiment_map.get("neutral", 0),
            "mixed_count": sentiment_map.get("mixed", 0),
            "total_events": total_events,
        })