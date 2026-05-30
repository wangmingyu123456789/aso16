"""
CToS2 Unified Dev Server
=======================
Serves both:
  - Frontend static files (CToS2Front/frontend/)
  - Backend FastAPI app (CToS2Back/app.py) on port 8000
  - External API service (CToS2Back/external_app.py) on port 8080

URL: http://localhost:8000 (主服务, 需要鉴权)
     http://localhost:8080 (外部服务, 无鉴权)
"""

import sys
import os
import multiprocessing

# ── Ensure backend module is importable ────────────
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "CToS2Back")
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "CToS2Front", "frontend")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ── FastAPI + StaticFiles ──────────────────────────
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

# Backend FastAPI app (imported from CToS2Back/app.py)
from app import app

# ── Serve frontend static files ────────────────────
# Non-API requests try the frontend directory first.
# If no matching file, fall back to index.html (SPA support).
@app.middleware("http")
async def serve_frontend(request, call_next):
    path = request.url.path

    # API/WebSocket requests go to normal routes
    if path.startswith("/api/") or path.startswith("/ws"):
        return await call_next(request)

    # Static file request: serve directly
    static_path = os.path.join(FRONTEND_DIR, path.lstrip("/"))
    if path != "/" and os.path.isfile(static_path):
        return FileResponse(static_path)

    # Everything else -> index.html (SPA fallback)
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)

    return await call_next(request)


# ── Mount static directories (CSS/JS/etc.) ────────
app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")


def run_main_server():
    """运行主服务器（内部API + 前端）"""
    from config import settings
    port = settings.APP_PORT
    print(f"  ▶ 主服务启动在 http://0.0.0.0:{port}")
    uvicorn.run(
        "run:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False,  # 多进程时不能用 reload
    )


def run_external_server():
    """运行外部服务（无鉴权API）"""
    from config import settings
    port = settings.EXTERNAL_PORT
    print(f"  ▶ 外部服务启动在 http://0.0.0.0:{port}")
    uvicorn.run(
        "external_app:external_app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    # 需要在启动前确保 BACKEND_DIR 在 sys.path 中（外部服务也要能用）
    os.environ["PYTHONPATH"] = BACKEND_DIR + os.pathsep + os.environ.get("PYTHONPATH", "")

    port_main = int(os.getenv("APP_PORT", "8000"))
    port_ext = int(os.getenv("EXTERNAL_PORT", "8080"))

    print("=" * 50)
    print("  CToS2 development server starting...")
    print(f"  - 主服务 (需鉴权): http://localhost:{port_main}")
    print(f"  - 外部服务 (无鉴权): http://localhost:{port_ext}")
    print(f"  - 前端: http://localhost:{port_main}")
    print(f"  - 天气代理: POST http://localhost:{port_ext}/weather")
    print(f"  - 文件下载: GET http://localhost:{port_ext}/files/{{id}}/download")
    print("  - Press Ctrl+C to stop")
    print("=" * 50)

    # 使用多进程同时启动两个服务
    p1 = multiprocessing.Process(target=run_main_server, name="main-server")
    p2 = multiprocessing.Process(target=run_external_server, name="external-server")

    try:
        p1.start()
        p2.start()
        p1.join()
        p2.join()
    except KeyboardInterrupt:
        print("\n收到中断信号，正在关闭服务...")
        p1.terminate()
        p2.terminate()
        p1.join()
        p2.join()
        print("所有服务已关闭。")