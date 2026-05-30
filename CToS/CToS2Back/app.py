"""
CToS2 - 智能问数系统后端主入口
"""
import sys
import time
import uvicorn
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# 将项目根目录加入 sys.path
sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from database.engine import db_manager
from database.seeds import seed_default_data
from utils.helpers import logger, error_response, AppException
from routers import (
    auth, chat, watch, workers, dashboard, sentiment, warehouse, admin,
    im, cleaning, dispatch, files as files_router,
    internal as internal_router,
    workflow as workflow_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("=" * 50)
    logger.info(f"CToS2 服务启动 | 环境: {settings.ENV}")
    logger.info(f"数据库: {settings.DB_TYPE}://{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    logger.info("=" * 50)

    # 初始化数据库引擎和创建表
    await db_manager.init()
    from database.models import Base
    async with db_manager._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ 数据库连接成功, 表已创建")

    # 执行种子数据
    try:
        await seed_default_data()
        logger.info("✅ 种子数据初始化完成")
    except Exception as e:
        logger.warning(f"⚠️ 种子数据初始化异常(可忽略): {e}")

    yield

    # 关闭数据库
    if hasattr(db_manager, '_engine') and db_manager._engine:
        await db_manager._engine.dispose()
    logger.info("数据库连接已关闭")


app = FastAPI(
    title=settings.APP_NAME,
    description="CToS2 智能问数系统",
    version="1.0.0",
    lifespan=lifespan,
)

# 请求耗时日志中间件
@app.middleware("http")
async def log_request_time(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    # 只记录 API 请求（跳过静态资源等）
    if request.url.path.startswith("/api/"):
        logger.info(
            f"[{request.method}] {request.url.path} "
            f"→ {response.status_code} "
            f"({elapsed*1000:.0f}ms)"
        )
    return response

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return error_response(message=exc.detail, status_code=exc.status_code)

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception("未捕获的异常")
    return error_response(message="服务器内部错误", status_code=500)


# 注册路由
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(watch.router)
app.include_router(workers.router)
app.include_router(dashboard.router)
app.include_router(sentiment.router)
app.include_router(warehouse.router)
app.include_router(admin.router)
app.include_router(im.router)
app.include_router(cleaning.router)
app.include_router(dispatch.router)
app.include_router(files_router.router)
app.include_router(internal_router.router)
app.include_router(workflow_router.router)


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok", "app": settings.APP_NAME, "version": "1.0.0"}


if __name__ == "__main__":
    port = settings.APP_PORT
    
    # ============================================================
    # 🚀 启用 HTTP/2 + 多 Workers 并发优化
    # ============================================================
    # HTTP/1.1 下 Chrome 限制单域名最多 6 个并发连接。
    # 启用 HTTP/2 后多路复用，单一 TCP 连接可承载数百个并发请求。
    # 
    # 注意：`reload=True` 时无法同时使用 `workers` 参数。
    # 生产环境建议 `reload=False` + `workers=N`。
    # ============================================================
    
    # 基础运行参数
    run_kwargs = {
        "host": "0.0.0.0",
        "port": port,
        "limit_concurrency": None,   # 不限并发连接数
        "backlog": 2048,             # 连接等待队列
    }
    
    # HTTP 模式（已移除 SSL 证书）
    logger.info(f"🚀 HTTP 模式 | 地址: http://0.0.0.0:{port}")
    
    # reload=True 时不能使用 workers 参数
    # 生产环境部署：
    #   1. 设置环境变量 ENV=production
    #   2. 使用 --workers 4 启动（此时 auto-reload 自动关闭）
    if settings.ENV == "production":
        run_kwargs["workers"] = 4
        logger.info(f"   Workers: {run_kwargs.get('workers', 1)} 进程并行")
    else:
        run_kwargs["reload"] = True
        logger.info(f"   开发模式: 热重载已启用")
    
    uvicorn.run("app:app", **run_kwargs)
