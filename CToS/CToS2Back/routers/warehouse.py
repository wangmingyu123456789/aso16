"""知识仓库 Warehouse 模块 - 存储管理 AI 清洗后的结构化文章数据"""
import re
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, desc, asc, or_, func, and_
from database.engine import db_manager
from database.models import User, WarehouseArticle, WarehouseCategory, CleaningLog
from middleware.auth_middleware import get_current_user
from utils.helpers import success_response, AppException
from utils.db_utils import fetch_paginated

router = APIRouter(prefix="/api/warehouse", tags=["知识仓库"])


def extract_domain(url: str) -> str:
    """从 URL 提取主体域名（去 www. 前缀）"""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        return re.sub(r'^www\.', '', hostname).lower() if hostname else ""
    except:
        return ""


class CategoryCreate(BaseModel):
    name: str
    description: str = ""
    icon: str = "📁"


class CategoryUpdate(BaseModel):
    name: str = None
    description: str = None
    icon: str = None


class ArticleCreate(BaseModel):
    title: str
    content: str = ""
    category_id: int = None
    tags: str = ""
    url: str = ""


class ArticleUpdate(BaseModel):
    title: str = None
    content: str = None
    category_id: int = None
    tags: str = None
    url: str = None
    status: str = None
    domain_name: str = None


# ===== 分类管理 =====

@router.get("/categories")
async def list_categories(user: User = Depends(get_current_user)):
    """获取分类列表（带文章计数）"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(
                WarehouseCategory, 
                func.count(WarehouseArticle.id).label("article_count")
            )
            .outerjoin(WarehouseArticle, WarehouseArticle.category_id == WarehouseCategory.id)
            .group_by(WarehouseCategory.id)
            .order_by(WarehouseCategory.sort_order)
        )
        rows = result.all()
        return success_response(data=[{
            "id": c.id, "name": c.name, "description": c.description,
            "icon": c.icon, "sort_order": c.sort_order,
            "article_count": cnt or 0,
        } for c, cnt in rows])


@router.post("/categories")
async def create_category(req: CategoryCreate, user: User = Depends(get_current_user)):
    """创建分类"""
    async with db_manager.get_session() as session:
        cat = WarehouseCategory(name=req.name, description=req.description, icon=req.icon)
        session.add(cat)
        await session.commit()
        await session.refresh(cat)
        return success_response(data={"id": cat.id}, message="分类创建成功")


@router.put("/categories/{category_id}")
async def update_category(category_id: int, req: CategoryUpdate, user: User = Depends(get_current_user)):
    """编辑分类"""
    async with db_manager.get_session() as session:
        cat = await session.get(WarehouseCategory, category_id)
        if not cat:
            raise AppException("分类不存在", status_code=404)
        if req.name is not None:
            cat.name = req.name
        if req.description is not None:
            cat.description = req.description
        if req.icon is not None:
            cat.icon = req.icon
        await session.commit()
        return success_response(message="分类已更新")


@router.delete("/categories/{category_id}")
async def delete_category(category_id: int, user: User = Depends(get_current_user)):
    """删除分类"""
    async with db_manager.get_session() as session:
        cat = await session.get(WarehouseCategory, category_id)
        if not cat:
            raise AppException("分类不存在", status_code=404)
        # 检查是否有文章关联
        article_count = await session.scalar(
            select(func.count(WarehouseArticle.id))
            .where(WarehouseArticle.category_id == category_id)
        )
        if article_count and article_count > 0:
            raise AppException(f"该分类下有 {article_count} 篇文章，无法删除", status_code=400)
        await session.delete(cat)
        await session.commit()
        return success_response(message="分类已删除")


# ===== 文章管理 =====

@router.get("/articles")
async def list_articles(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=200, description="每页条数"),
    category_id: int = Query(None, description="分类ID筛选"),
    status: str = Query(None, description="状态筛选: draft/published"),
    domain: str = Query(None, description="域名筛选"),
    q: str = Query("", description="关键词搜索（标题/内容/域名）"),
    sort: str = Query("created_at", description="排序字段: created_at/updated_at/title"),
    order: str = Query("desc", description="排序方向: asc/desc"),
    user: User = Depends(get_current_user),
):
    """获取文章列表（增强版：支持分页、状态筛选、域名筛选、关键词搜索）"""
    async with db_manager.get_session() as session:
        sort_column = {
            "created_at": WarehouseArticle.created_at,
            "updated_at": WarehouseArticle.updated_at,
            "title": WarehouseArticle.title,
        }.get(sort, WarehouseArticle.created_at)
        
        order_func = desc if order == "desc" else asc
        query = select(WarehouseArticle).order_by(order_func(sort_column))

        # 分类筛选
        if category_id is not None and category_id > 0:
            query = query.where(WarehouseArticle.category_id == category_id)
        
        # 状态筛选
        if status and status in ("draft", "published"):
            query = query.where(WarehouseArticle.status == status)
        
        # 域名筛选
        if domain:
            query = query.where(WarehouseArticle.domain_name.ilike(f"%{domain}%"))
        
        # 关键词搜索
        if q:
            keyword = f"%{q}%"
            query = query.where(
                or_(
                    WarehouseArticle.title.ilike(keyword),
                    WarehouseArticle.content.ilike(keyword),
                    WarehouseArticle.domain_name.ilike(keyword),
                    WarehouseArticle.tags.ilike(keyword),
                )
            )

        return await fetch_paginated(
            session, query, page, page_size,
            mapper=lambda a: {
                "id": a.id, "title": a.title,
                "category_id": a.category_id,
                "content": (a.content or "")[:200],  # 预览内容
                "tags": a.tags, "url": a.url,
                "status": a.status,
                "domain_name": a.domain_name,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            }
        )


@router.post("/articles")
async def create_article(req: ArticleCreate, user: User = Depends(get_current_user)):
    """创建文章（自动提取域名）"""
    async with db_manager.get_session() as session:
        domain_name = extract_domain(req.url)
        article = WarehouseArticle(
            title=req.title, content=req.content,
            category_id=req.category_id, tags=req.tags, url=req.url,
            domain_name=domain_name,
        )
        session.add(article)
        await session.commit()
        await session.refresh(article)
        return success_response(data={"id": article.id, "domain_name": domain_name}, message="文章创建成功")


@router.get("/articles/{article_id}")
async def get_article(article_id: int, user: User = Depends(get_current_user)):
    """获取文章详情（含分类名称）"""
    async with db_manager.get_session() as session:
        article = await session.get(WarehouseArticle, article_id)
        if not article:
            raise AppException("文章不存在", status_code=404)
        
        # 获取分类名称
        category_name = ""
        if article.category_id:
            cat = await session.get(WarehouseCategory, article.category_id)
            if cat:
                category_name = cat.name
        
        return success_response(data={
            "id": article.id, "title": article.title,
            "content": article.content, "category_id": article.category_id,
            "category_name": category_name,
            "tags": article.tags, "url": article.url,
            "status": article.status, "domain_name": article.domain_name,
            "created_at": article.created_at.isoformat() if article.created_at else None,
            "updated_at": article.updated_at.isoformat() if article.updated_at else None,
        })


@router.put("/articles/{article_id}")
async def update_article(article_id: int, req: ArticleUpdate, user: User = Depends(get_current_user)):
    """编辑文章（URL变更时自动重提取域名）"""
    async with db_manager.get_session() as session:
        article = await session.get(WarehouseArticle, article_id)
        if not article:
            raise AppException("文章不存在", status_code=404)
        if req.title is not None:
            article.title = req.title
        if req.content is not None:
            article.content = req.content
        if req.category_id is not None:
            article.category_id = req.category_id
        if req.tags is not None:
            article.tags = req.tags
        if req.url is not None:
            article.url = req.url
            article.domain_name = extract_domain(req.url)
        if req.domain_name is not None:
            article.domain_name = req.domain_name
        if req.status is not None:
            if req.status not in ("draft", "published"):
                raise AppException("无效的状态值，可选: draft/published")
            article.status = req.status
        await session.commit()
        return success_response(message="文章已更新")


@router.delete("/articles/{article_id}")
async def delete_article(article_id: int, user: User = Depends(get_current_user)):
    """删除文章"""
    async with db_manager.get_session() as session:
        article = await session.get(WarehouseArticle, article_id)
        if not article:
            raise AppException("文章不存在", status_code=404)
        await session.delete(article)
        await session.commit()
        return success_response(message="文章已删除")


# ===== 域名管理 =====

@router.get("/domains")
async def list_domains(user: User = Depends(get_current_user)):
    """获取域名列表（按文章数排序）"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(WarehouseArticle.domain_name, func.count(WarehouseArticle.id).label("cnt"))
            .where(WarehouseArticle.domain_name.isnot(None))
            .where(WarehouseArticle.domain_name != "")
            .group_by(WarehouseArticle.domain_name)
            .order_by(desc("cnt"))
        )
        domains = [{"domain": row[0], "count": row[1]} for row in result]
        return success_response(data=domains)


# ===== 统计信息 =====

@router.get("/stats")
async def get_warehouse_stats(user: User = Depends(get_current_user)):
    """获取仓库全量统计信息"""
    async with db_manager.get_session() as session:
        # 总数
        total = await session.scalar(select(func.count(WarehouseArticle.id))) or 0
        published = await session.scalar(
            select(func.count(WarehouseArticle.id)).where(WarehouseArticle.status == "published")
        ) or 0
        draft = await session.scalar(
            select(func.count(WarehouseArticle.id)).where(WarehouseArticle.status == "draft")
        ) or 0
        
        # 今日新增
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_new = await session.scalar(
            select(func.count(WarehouseArticle.id))
            .where(WarehouseArticle.created_at >= today_start)
        ) or 0
        
        # 分类数
        categories = await session.scalar(select(func.count(WarehouseCategory.id))) or 0
        
        # 域名数
        domain_count = await session.scalar(
            select(func.count(func.distinct(WarehouseArticle.domain_name)))
            .where(WarehouseArticle.domain_name.isnot(None))
            .where(WarehouseArticle.domain_name != "")
        ) or 0
        
        # 清洗统计数据（关联 cleaning_logs）
        cleaning_total = await session.scalar(
            select(func.count(CleaningLog.id))
        ) or 0
        cleaning_success = await session.scalar(
            select(func.count(CleaningLog.id)).where(CleaningLog.status == "success")
        ) or 0
        cleaning_failed = await session.scalar(
            select(func.count(CleaningLog.id)).where(CleaningLog.status == "failed")
        ) or 0
        cleaning_pending = cleaning_total - cleaning_success - cleaning_failed
        
        # 域名TOP榜
        domain_result = await session.execute(
            select(WarehouseArticle.domain_name, func.count(WarehouseArticle.id).label("cnt"))
            .where(WarehouseArticle.domain_name.isnot(None))
            .where(WarehouseArticle.domain_name != "")
            .group_by(WarehouseArticle.domain_name)
            .order_by(desc("cnt")).limit(10)
        )
        top_domains = [{"domain": row[0], "count": row[1]} for row in domain_result]
        
        # 标签统计（前20）
        # 获取所有非空tags
        tags_result = await session.execute(
            select(WarehouseArticle.tags)
            .where(WarehouseArticle.tags.isnot(None))
            .where(WarehouseArticle.tags != "")
            .limit(500)
        )
        tag_counter = {}
        for (tags_str,) in tags_result:
            if tags_str:
                for t in tags_str.split(","):
                    t = t.strip()
                    if t:
                        tag_counter[t] = tag_counter.get(t, 0) + 1
        top_tags = sorted(tag_counter.items(), key=lambda x: -x[1])[:20]
        
        return success_response(data={
            "total_articles": total,
            "published": published,
            "draft": draft,
            "today_new": today_new,
            "total_categories": categories,
            "total_domains": domain_count,
            "cleaning": {
                "total": cleaning_total,
                "success": cleaning_success,
                "failed": cleaning_failed,
                "pending": cleaning_pending,
            },
            "top_domains": top_domains,
            "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
        })


# ===== 批量操作 =====

class BatchDeleteRequest(BaseModel):
    ids: list[int]


@router.post("/articles/batch-delete")
async def batch_delete_articles(req: BatchDeleteRequest, user: User = Depends(get_current_user)):
    """批量删除文章"""
    if not req.ids:
        raise AppException("请提供要删除的文章ID列表", status_code=400)
    async with db_manager.get_session() as session:
        for article_id in req.ids:
            article = await session.get(WarehouseArticle, article_id)
            if article:
                await session.delete(article)
        await session.commit()
        return success_response(message=f"已删除 {len(req.ids)} 篇文章")


class BatchStatusRequest(BaseModel):
    ids: list[int]
    status: str


@router.post("/articles/batch-status")
async def batch_update_status(req: BatchStatusRequest, user: User = Depends(get_current_user)):
    """批量更新文章状态"""
    if req.status not in ("draft", "published"):
        raise AppException("无效的状态值，可选: draft/published", status_code=400)
    if not req.ids:
        raise AppException("请提供文章ID列表", status_code=400)
    async with db_manager.get_session() as session:
        for article_id in req.ids:
            article = await session.get(WarehouseArticle, article_id)
            if article:
                article.status = req.status
        await session.commit()
        return success_response(message=f"已将 {len(req.ids)} 篇文章状态更新为 {req.status}")