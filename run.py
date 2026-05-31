"""
cnAgentOS Unified Dev Server
============================
一键启动所有服务：
  - 主服务（Tornado）：端口 10086（HTTP + WebSocket）
  - 外部天气服务（FastAPI）：端口 9877
  - IM集群节点：端口 10081~10082（WebSocket，自动分配用户）
"""

import sys
import os
import time
import signal
import multiprocessing
import atexit

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# ==================== 配置 ====================
IM_NODE_COUNT = int(os.getenv("IM_NODE_COUNT", "2"))     # 额外IM节点数量
IM_NODE_START_PORT = int(os.getenv("IM_NODE_START_PORT", "10081"))
MAIN_PORT = 10086
EXTERNAL_PORT = int(os.getenv("EXTERNAL_PORT", "9877"))

# 存储所有子进程，用于统一关闭
_processes = []


def cleanup():
    for p in _processes:
        if p and p.is_alive():
            try:
                p.terminate()
            except Exception:
                pass


atexit.register(cleanup)


def run_main_server():
    """主服务器进程：HTTP + WS（node-0）"""
    import tornado.ioloop
    import tornado.web
    from tornado.httpserver import HTTPServer
    from app import make_app
    from app.models.db import init_db, upgrade_db
    import socket
    import threading
    import time

    try:
        init_db()
        upgrade_db()
    except Exception as e:
        print(f"[Main] DB init error: {e}", flush=True)

    # 注册主服务器为集群 node-0
    try:
        from app.models.im_server import ServerRegistry
        local_ip = "127.0.0.1"
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            pass
        pid = os.getpid()
        ServerRegistry.register("node-0", local_ip, MAIN_PORT, MAIN_PORT + 10000, pid, 500)
        print(f"[Cluster] node-0 已注册 ({local_ip}:{MAIN_PORT} PID={pid})", flush=True)

        def main_heartbeat():
            from app.controllers.im_ws import connection_pool
            while True:
                try:
                    conn_count = sum(len(conns) for conns in connection_pool.values())
                    ServerRegistry.heartbeat("node-0", conn_count)
                except Exception:
                    pass
                time.sleep(5)

        t = threading.Thread(target=main_heartbeat, daemon=True)
        t.start()
    except Exception as e:
        print(f"[Cluster] 节点注册跳过: {e}", flush=True)

    # 启动定时调度器
    try:
        from app.models import crawl_scheduler
        crawl_scheduler.start_scheduler()
    except Exception as e:
        print(f"[Main] Scheduler error: {e}", flush=True)

    try:
        app = make_app()
        server = HTTPServer(app)
        server.bind(MAIN_PORT)
        server.start()
        print(f"[Main] 🟢 主服务 HTTP + WS 运行在 http://0.0.0.0:{MAIN_PORT}", flush=True)
        tornado.ioloop.IOLoop.current().start()
    except Exception as e:
        print(f"[Main] Server error: {e}", flush=True)


def run_external_server():
    """外部天气服务进程（FastAPI）"""
    ctos_dir = os.path.join(PROJECT_DIR, "CToS", "CToS2Back")
    ctos_dir = os.path.normpath(ctos_dir)

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

    print(f"[Weather] 🟢 外部天气服务运行在 http://0.0.0.0:{EXTERNAL_PORT}", flush=True)
    import uvicorn
    uvicorn.run(
        ctos_external.external_app,
        host="0.0.0.0",
        port=EXTERNAL_PORT,
        log_level="info",
    )


def run_im_node(port, node_id):
    """IM节点进程：仅 WebSocket + 内部通信"""
    from run_im_node import start_node
    start_node(port=port, node_id=node_id)


def start_all():
    """启动所有服务"""
    print("=" * 60)
    print("  cnAgentOS 一键启动")
    print("=" * 60)
    print(f"  🌐 主服务 (HTTP+WS):   http://localhost:{MAIN_PORT}")
    print(f"  ☁️  天气服务:           http://localhost:{EXTERNAL_PORT}")
    print(f"  📡 IM节点数:           {IM_NODE_COUNT + 1} 个")
    print(f"     - node-0:           ws://localhost:{MAIN_PORT}/im/ws")
    for i in range(IM_NODE_COUNT):
        port = IM_NODE_START_PORT + i
        print(f"     - node-{i+1}:        ws://localhost:{port}/im/ws")
    print("  - 按 Ctrl+C 停止所有服务")
    print("=" * 60)

    # ========== 1. 启动主服务 ==========
    p_main = multiprocessing.Process(target=run_main_server, name="main-server")
    p_main.daemon = True
    p_main.start()
    _processes.append(p_main)
    print(f"[启动] 主服务进程已启动 (PID={p_main.pid})", flush=True)

    # ========== 2. 启动天气服务 ==========
    p_weather = multiprocessing.Process(target=run_external_server, name="external-weather")
    p_weather.daemon = True
    p_weather.start()
    _processes.append(p_weather)
    print(f"[启动] 天气服务进程已启动 (PID={p_weather.pid})", flush=True)

    # ========== 3. 启动IM集群节点 ==========
    im_node_processes = []
    for i in range(IM_NODE_COUNT):
        port = IM_NODE_START_PORT + i
        node_id = "node-{}".format(i + 1)
        p = multiprocessing.Process(target=run_im_node, args=(port, node_id), name="im-node-{}".format(node_id))
        p.daemon = True
        p.start()
        _processes.append(p)
        im_node_processes.append(p)
        print(f"[启动] IM节点 {node_id} 进程已启动 (PID={p.pid}, 端口={port})", flush=True)

    # ========== 4. 等待所有进程 ==========
    try:
        while True:
            time.sleep(1)
            # 检查是否有进程意外退出
            for p in _processes:
                if not p.is_alive():
                    print(f"[警告] 进程 {p.name} (PID={p.pid}) 已退出", flush=True)
    except KeyboardInterrupt:
        print("\n\n🛑 收到停止信号，正在关闭所有服务...", flush=True)
        for p in _processes:
            if p and p.is_alive():
                p.terminate()
                p.join(timeout=3)
        print("✅ 所有服务已关闭。", flush=True)


if __name__ == "__main__":
    # Windows 多进程支持
    if sys.platform == "win32":
        multiprocessing.freeze_support()

    start_all()
