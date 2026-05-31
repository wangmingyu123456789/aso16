"""
IM服务器节点启动脚本

用法：
    # 单独启动节点
    python run_im_node.py --port=10081 --node=node-1

    # 由 run.py 自动调用（无需手动运行）
"""

import os
import sys
import time
import json
import socket
import argparse
import threading
import datetime

_root_dir = os.path.dirname(os.path.abspath(__file__))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

import tornado.ioloop
import tornado.web
import tornado.websocket
import httpx

os.environ['RUN_IM_NODE'] = 'true'


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def make_node_app(public_port, internal_port, node_id, cookie_secret):
    from app.controllers.im_ws import IMWebSocketHandler
    from app.controllers.im_internal import InternalSendHandler, InternalHealthHandler, InternalBatchUserCheckHandler

    IMWebSocketHandler._server_node_id = node_id

    node_settings = {
        "cookie_secret": cookie_secret,
        "login_url": "/auth/login",
        "xsrf_cookies": True,
        "debug": False,
    }

    return tornado.web.Application([
        (r"/im/ws", IMWebSocketHandler),
        (r"/internal/send", InternalSendHandler),
        (r"/internal/health", InternalHealthHandler),
        (r"/internal/batch-check", InternalBatchUserCheckHandler),
    ], **node_settings)


def heartbeat_loop(node_id, interval=5):
    from app.models.im_server import ServerRegistry
    while True:
        try:
            from app.controllers.im_ws import connection_pool
            conn_count = sum(len(conns) for conns in connection_pool.values())
            ServerRegistry.heartbeat(node_id, conn_count)
        except Exception:
            pass
        time.sleep(interval)


def health_check_loop(interval=15):
    from app.models.im_server import ServerRegistry
    while True:
        time.sleep(interval)
        try:
            nodes = ServerRegistry.get_all_nodes()
            now = datetime.datetime.now()
            for node in nodes:
                if node["status"] != "online":
                    continue
                try:
                    hb = datetime.datetime.strptime(node["last_heartbeat"], '%Y-%m-%d %H:%M:%S')
                    if (now - hb).total_seconds() > 15:
                        url = "http://{}:{}/internal/health".format(node["host"], node["internal_port"])
                        try:
                            resp = httpx.get(url, timeout=3.0)
                            if resp.status_code == 200:
                                continue
                        except Exception:
                            pass
                        ServerRegistry.mark_offline(node["node_id"])
                        print("[IM-Node] 节点 {} 已标记为离线".format(node["node_id"]))
                except (ValueError, TypeError):
                    pass
        except Exception:
            pass


def start_node(port, node_id=None, host=None, max_connections=200):
    """
    启动一个IM节点（可在独立进程或线程中调用）
    
    参数：
        port: WebSocket 端口
        node_id: 节点ID（默认 node-PORT）
        host: 本机IP（默认自动检测）
        max_connections: 最大连接数
    """
    internal_port = port + 10000
    host = host if host else get_local_ip()
    node_id = node_id if node_id else "node-{}".format(port)

    # 每个节点独立初始化数据库连接
    from app.models.db import init_db, upgrade_db, DB_PATH
    init_db()
    upgrade_db()

    from app.models.im_server import ServerRegistry
    pid = os.getpid()
    ServerRegistry.register(node_id, host, port, internal_port, pid, max_connections)
    print("[IM-Node] {} 注册成功 ({}:{} PID={})".format(node_id, host, port, pid), flush=True)

    cookie_secret = "demo-cookie-secret-change-me"
    node_app = make_node_app(port, internal_port, node_id, cookie_secret)

    t1 = threading.Thread(target=heartbeat_loop, args=(node_id,), daemon=True)
    t1.start()

    t2 = threading.Thread(target=health_check_loop, daemon=True)
    t2.start()

    node_app.listen(port)
    print("[IM-Node] 🟢 {} 运行在 ws://{}:{}/im/ws (内部 :{})".format(
        node_id, host, port, internal_port), flush=True)

    try:
        tornado.ioloop.IOLoop.current().start()
    except KeyboardInterrupt:
        print("\n[IM-Node] 正在停止 {}...".format(node_id), flush=True)
        ServerRegistry.mark_offline(node_id)


def main():
    parser = argparse.ArgumentParser(description="启动IM服务器节点")
    parser.add_argument("--port", type=int, default=10081, help="WebSocket端口 (默认: 10081)")
    parser.add_argument("--node", type=str, default="", help="节点ID (默认: node-PORT)")
    parser.add_argument("--host", type=str, default="", help="本机IP (默认: 自动检测)")
    parser.add_argument("--max-connections", type=int, default=200, help="最大连接数 (默认: 200)")
    args = parser.parse_args()

    start_node(
        port=args.port,
        node_id=args.node if args.node else None,
        host=args.host if args.host else None,
        max_connections=args.max_connections
    )


if __name__ == "__main__":
    main()
