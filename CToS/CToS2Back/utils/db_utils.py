"""数据库工具函数"""
import math
from typing import Any, Callable, List, Optional, TypeVar
from sqlalchemy import Select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse

T = TypeVar("T")

async def fetch_paginated(
    session: AsyncSession,
    query: Select,
    page: int = 1,
    page_size: int = 20,
    mapper: Optional[Callable[[Any], dict]] = None,
) -> JSONResponse:
    """分页查询工具"""
    from utils.helpers import success_response
    
    # 计算总数（需先清除 ORDER BY，否则 count 查询会因引用 SELECT 外的列而报错）
    count_query = query.with_only_columns(func.count(), maintain_column_froms=False).order_by(None)
    total = await session.scalar(count_query) or 0
    
    # 分页
    offset = (page - 1) * page_size
    result = await session.execute(query.offset(offset).limit(page_size))
    rows = result.scalars().all()
    
    items = [mapper(r) for r in rows] if mapper else [dict(r) for r in rows]
    
    return success_response(data={
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0,
    })