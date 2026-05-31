"""
cnAgentOS Unified Dev Server
============================
同时启动两个服务：
  - 主服务（Tornado）：端口 10086，需要鉴权
  - 外部天气服务（FastAPI）：端口 9877，无鉴权

URL: 
  - 主服务: http://localhost:10086
  - 外部天气服务: http://localhost:9877
"""

import sys
import os
import multiprocessing

# 确保项目根目录在 sys.path 中
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)


def run_main_server():
    """运行主服务器（Tornado）"""
    import tornado.ioloop
    import tornado.web
    from tornado.httpserver import HTTPServer
    from app import make_app
    from app.models.db import init_db, upgrade_db

    try:
        init_db()
        upgrade_db()
    except Exception as e:
        print(f"DB init error: {e}", flush=True)

    # 启动定时调度器（APScheduler）
    try:
        from app.models import crawl_scheduler
        crawl_scheduler.start_scheduler()
    except Exception as e:
        print(f"Scheduler start error: {e}", flush=True)
        import traceback
        traceback.print_exc()

    try:
        app = make_app()
        server = HTTPServer(app)
        server.bind(10086)
        server.start()
        print("===== 主服务启动成功 ===== 端口：10086 ======", flush=True)
        tornado.ioloop.IOLoop.current().start()
    except Exception as e:
        print(f"Server error: {e}", flush=True)
        import traceback
        traceback.print_exc()


def run_external_server():
    """运行外部天气服务（FastAPI）- 使用 CToS/CToS2Back 的 AI 版本"""
    ctos_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CToS", "CToS2Back")
    ctos_dir = os.path.normpath(ctos_dir)

    # 切换到 CToS 自己的工作目录，确保 .env 和数据库路径正确解析
    original_cwd = os.getcwd()
    os.chdir(ctos_dir)
    if ctos_dir not in sys.path:
        sys.path.insert(0, ctos_dir)

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ctos_external",
        os.path.join(ctos_dir, "external.py")
    )
    ctos_external = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ctos_external)

    port = int(os.getenv("EXTERNAL_PORT", "9877"))

    print(f"===== 外部天气服务（AI 数字员工）启动成功 ===== 端口：{port} ======", flush=True)
    import uvicorn
    uvicorn.run(
        ctos_external.external_app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    port_main = 10086
    port_ext = int(os.getenv("EXTERNAL_PORT", "9877"))

    print("=" * 60)
    print("  cnAgentOS development server starting...")
    print(f"  - 主服务 (需鉴权): http://localhost:{port_main}")
    print(f"  - 外部天气服务 (无鉴权): http://localhost:{port_ext}")
    print(f"  - 天气查询: POST http://localhost:{port_ext}/weather")
    print(f"  - 健康检查: GET http://localhost:{port_ext}/health")
    print("  - Press Ctrl+C to stop")
    print("=" * 60)

    # 使用多进程同时启动两个服务
    p1 = multiprocessing.Process(target=run_main_server, name="main-server")
    p2 = multiprocessing.Process(target=run_external_server, name="external-server")

    try:
        p1.start()
        p2.start()
        p1.join()
        p2.join()
    except KeyboardInterrupt:
        print("\n收到中断信号，正在关闭服务...", flush=True)
        p1.terminate()
        p2.terminate()
        p1.join()
        p2.join()
        print("所有服务已关闭。", flush=True)
