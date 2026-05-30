"""数字大屏 Dashboard 模块"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc, case
from database.engine import db_manager
from database.models import (
    User, Conversation, WatchSource, WatchData, Worker, ExecutionLog,
    SentimentAnalysis, SentimentEvent, SentimentWord, SentimentLocation,
    SentimentDashboard, WarehouseArticle, TokenStat
)
from middleware.auth_middleware import get_current_user
from utils.helpers import success_response
from utils.db_utils import fetch_paginated

router = APIRouter(prefix="/api/dashboard", tags=["数字大屏"])


@router.get("/stats")
async def get_dashboard_stats(user: User = Depends(get_current_user)):
    """获取仪表盘实时指标"""
    async with db_manager.get_session() as session:
        watch_count = await session.scalar(select(func.count(WatchSource.id)))
        today_collected = await session.scalar(
            select(func.count(WatchData.id)).where(
                func.date(WatchData.collected_at) == func.current_date()
            )
        )
        total_collected = await session.scalar(select(func.count(WatchData.id)))
        total_tokens = await session.scalar(select(func.coalesce(func.sum(TokenStat.tokens_used), 0)))
        total_users = await session.scalar(select(func.count(User.id)))
        total_articles = await session.scalar(select(func.count(WarehouseArticle.id)))

        # uptime 由前端从应用启动时间计算或后端简单计算
        uptime = "N/A"

        return success_response(data={
            "watch_sources": watch_count or 0,
            "today_collected": today_collected or 0,
            "total_collected": total_collected or 0,
            "total_tokens": total_tokens or 0,
            "total_users": total_users or 0,
            "uptime": uptime,
            "total_articles": total_articles or 0,
        })


@router.get("/collect-trend")
async def get_collect_trend(days: int = 7, user: User = Depends(get_current_user)):
    """获取采集趋势（按天统计采集数据量）"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(
                func.date(WatchData.collected_at).label("date"),
                func.count(WatchData.id).label("count"),
            )
            .group_by(func.date(WatchData.collected_at))
            .order_by(desc("date"))
            .limit(days)
        )
        trend = [{"date": str(row[0]), "count": row[1]} for row in result]
        trend.reverse()
        return success_response(data=trend)


@router.get("/token-trend")
async def get_token_trend(days: int = 7, user: User = Depends(get_current_user)):
    """获取 Token 消耗趋势"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(
                TokenStat.date,
                func.sum(TokenStat.tokens_used).label("tokens"),
            )
            .group_by(TokenStat.date)
            .order_by(desc(TokenStat.date))
            .limit(days)
        )
        trend = [{"date": str(row[0]), "tokens": row[1] or 0} for row in result]
        trend.reverse()
        return success_response(data=trend)


@router.get("/earth")
async def get_earth_data(user: User = Depends(get_current_user)):
    """获取 3D 地球标记数据（舆情地点）"""
    async with db_manager.get_session() as session:
        # 获取最近的舆情分析ID
        latest = await session.execute(
            select(SentimentAnalysis.id).order_by(desc(SentimentAnalysis.created_at)).limit(1)
        )
        latest_id = latest.scalar_one_or_none()
        if not latest_id:
            return success_response(data=[])

        result = await session.execute(
            select(
                SentimentLocation.location_name,
                SentimentLocation.longitude,
                SentimentLocation.latitude,
                SentimentLocation.heat,
                SentimentEvent.event_name,
            )
            .join(SentimentEvent, SentimentLocation.event_id == SentimentEvent.id)
            .where(SentimentEvent.analysis_id == latest_id)
            .where(SentimentLocation.longitude.isnot(None))
            .where(SentimentLocation.latitude.isnot(None))
            .order_by(desc(SentimentLocation.heat))
        )
        locations = [{
            "name": row[0],
            "longitude": row[1], "latitude": row[2],
            "value": row[3],
            "event_name": row[4],
        } for row in result]
        return success_response(data=locations)


@router.get("/wordcloud")
async def get_wordcloud_data(limit: int = 50, user: User = Depends(get_current_user)):
    """获取词云数据"""
    async with db_manager.get_session() as session:
        # 取最近一次舆情分析
        latest = await session.execute(
            select(SentimentAnalysis.id).order_by(desc(SentimentAnalysis.created_at)).limit(1)
        )
        latest_id = latest.scalar_one_or_none()
        if not latest_id:
            return success_response(data=[])

        result = await session.execute(
            select(
                SentimentWord.word,
                SentimentWord.weight,
                SentimentWord.sentiment_type,
            )
            .where(SentimentWord.analysis_id == latest_id)
            .order_by(desc(SentimentWord.weight))
            .limit(limit)
        )
        words = [{
            "name": row[0], "value": row[1],
            "sentiment_type": row[2],
        } for row in result]
        return success_response(data=words)


@router.get("/sentiment-stats")
async def get_sentiment_stats(user: User = Depends(get_current_user)):
    """获取舆情统计概览"""
    async with db_manager.get_session() as session:
        # 取最新大屏快照
        dashboard = await session.execute(
            select(SentimentDashboard).order_by(desc(SentimentDashboard.snapshot_at)).limit(1)
        )
        dash = dashboard.scalar_one_or_none()

        if dash:
            return success_response(data={
                "total_articles": dash.total_articles,
                "positive_count": dash.positive_count,
                "negative_count": dash.negative_count,
                "neutral_count": dash.neutral_count,
                "total_events": dash.total_events,
                "avg_heat": dash.avg_heat,
                "top_words": dash.top_words_json,
                "top_events": dash.top_events_json,
                "snapshot_at": dash.snapshot_at.isoformat() if dash.snapshot_at else None,
            })

        # 无快照时从原始数据统计
        latest = await session.execute(
            select(SentimentAnalysis.id).order_by(desc(SentimentAnalysis.created_at)).limit(1)
        )
        latest_id = latest.scalar_one_or_none()
        if not latest_id:
            return success_response(data={
                "total_articles": 0, "positive_count": 0, "negative_count": 0,
                "neutral_count": 0, "total_events": 0, "avg_heat": 0,
                "top_words": "[]", "top_events": "[]", "snapshot_at": None,
            })

        # 事件统计
        event_stats = await session.execute(
            select(
                func.count(SentimentEvent.id),
                func.sum(case((SentimentEvent.sentiment_type == "positive", 1), else_=0)),
                func.sum(case((SentimentEvent.sentiment_type == "negative", 1), else_=0)),
                func.sum(case((SentimentEvent.sentiment_type == "neutral", 1), else_=0)),
                func.avg(SentimentEvent.heat),
            )
            .where(SentimentEvent.analysis_id == latest_id)
        )
        row = event_stats.one()
        total_events = row[0] or 0
        positive = row[1] or 0
        negative = row[2] or 0
        neutral = row[3] or 0
        avg_heat = round(row[4] or 0, 1)

        # Top 词云
        top_words = await session.execute(
            select(SentimentWord.word, SentimentWord.weight)
            .where(SentimentWord.analysis_id == latest_id)
            .order_by(desc(SentimentWord.weight))
            .limit(10)
        )
        words = [{"word": w, "weight": wt} for w, wt in top_words]

        # Top 事件
        top_events = await session.execute(
            select(SentimentEvent.event_name, SentimentEvent.heat, SentimentEvent.sentiment_type)
            .where(SentimentEvent.analysis_id == latest_id)
            .order_by(desc(SentimentEvent.heat))
            .limit(10)
        )
        events = [{"event_name": e, "heat": h, "sentiment_type": s} for e, h, s in top_events]

        return success_response(data={
            "total_articles": 0,
            "positive_count": positive,
            "negative_count": negative,
            "neutral_count": neutral,
            "total_events": total_events,
            "avg_heat": avg_heat,
            "top_words": str(words),
            "top_events": str(events),
            "snapshot_at": None,
        })