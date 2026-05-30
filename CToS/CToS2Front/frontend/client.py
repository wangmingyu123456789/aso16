#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CToS 统一客户端启动器
集成了 HTTP 服务器（前端托管/API代理/WS代理）+ 手势识别服务
"""
import os, sys, io, json, socket, argparse, datetime, threading, webbrowser, subprocess, signal
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# SSL
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)

try:
    import requests
except ImportError:
    print("[!] 安装 requests...")
    os.system(f"{sys.executable} -m pip install requests")
    import requests

FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PORT = 5500
DEFAULT_BACKEND = "http://127.0.0.1:8000"
GESTURE_SCRIPT = os.path.join(os.path.dirname(FRONTEND_DIR), "gesture", "camera_gesture.py")
GESTURE_WS_PORT = 8765


class DebugHTTPRequestHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器，支持 API 代理、WS 代理、静态文件"""

    def __init__(self, *args, **kwargs):
        self.backend_url = kwargs.pop("backend_url", DEFAULT_BACKEND)
        self._ws_mode = False
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        pass

    @staticmethod
    def _now():
        return datetime.datetime.now().strftime("[%H:%M:%S]")

    # ==================== WS 代理 ====================

    def _ws_forward(self, src, dst, direction):
        try:
            while True:
                data = src.recv(4096)
                if not data:
                    break
                dst.sendall(data)
                self._log_ws_frame(data, direction)
        except:
            pass

    def _log_ws_frame(self, data, direction):
        if len(data) <= 10:
            return
        try:
            text = data.decode("utf-8", errors="replace")
            if text.startswith("{"):
                import json as _json
                obj = _json.loads(text)
                msg_type = obj.get("type", "")
                msg_data = obj.get("data", {})
                if isinstance(msg_data, dict):
                    content_preview = (msg_data.get("content", "") or "")[:40]
                    print(f"  {self._now()} \033[35m[WS {direction}]\033[0m type={msg_type} content=\"{content_preview}\" data_keys={list(msg_data.keys())}")
                else:
                    print(f"  {self._now()} \033[35m[WS {direction}]\033[0m type={msg_type}")
            else:
                print(f"  {self._now()} \033[35m[WS {direction}]\033[0m {text[:60]}")
        except:
            print(f"  {self._now()} \033[35m[WS {direction}]\033[0m [{len(data)} bytes]")

    def _proxy_ws(self):
        backend = self.backend_url.rstrip("/")
        parsed = urlparse(backend)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8000
        use_ssl = parsed.scheme == "https"

        try:
            if use_ssl:
                import ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                bs = ctx.wrap_socket(socket.socket(socket.AF_INET, socket.SOCK_STREAM), server_hostname=host)
            else:
                bs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            bs.settimeout(10)
            bs.connect((host, port))

            req = f"GET {self.path} HTTP/1.1\r\n"
            for k, v in self.headers.items():
                if k.lower() == "host":
                    req += f"Host: {host}:{port}\r\n"
                else:
                    req += f"{k}: {v}\r\n"
            req += "\r\n"
            bs.sendall(req.encode())

            resp = b""
            while b"\r\n\r\n" not in resp:
                chunk = bs.recv(4096)
                if not chunk:
                    break
                resp += chunk
            if not resp:
                bs.close()
                return

            resp_str = resp.decode("utf-8", errors="replace")
            status_line = resp_str.split("\r\n")[0]
            parts = status_line.split(" ", 2)
            self.send_response_only(int(parts[1]))
            for line in resp_str.split("\r\n")[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    self.send_header(k.strip(), v.strip())
            self.end_headers()
            self.wfile.flush()

            self._ws_mode = True
            print(f"{self._now()} \033[35m[WS 已连接] {self.path}\033[0m")

            t1 = threading.Thread(target=self._ws_forward, args=(self.connection, bs, "→"), daemon=True)
            t2 = threading.Thread(target=self._ws_forward, args=(bs, self.connection, "←"), daemon=True)
            t1.start()
            t2.start()
            t1.join()
            t2.join()
        except:
            pass
        finally:
            try:
                bs.close()
            except:
                pass
            print(f"{self._now()} \033[35m[WS 断开]\033[0m")

    # ==================== API 代理 ====================

    def _proxy_api(self, method):
        url = f"{self.backend_url.rstrip('/')}{self.path}"
        hdrs = {}
        for k, v in self.headers.items():
            if k.lower() in ("authorization", "content-type"):
                hdrs[k] = v
        if "content-type" not in {k.lower() for k in hdrs}:
            hdrs["Content-Type"] = "application/json; charset=utf-8"

        cl = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(cl) if cl > 0 else None

        try:
            verify = not self.backend_url.startswith("https")
            start = datetime.datetime.now()
            resp = requests.request(method, url, headers=hdrs, data=body, timeout=60, allow_redirects=False, verify=verify)
            dur = (datetime.datetime.now() - start).total_seconds() * 1000

            print(f"{self._now()} 🌐 API: {method} {self.path}")
            if body:
                try:
                    print(f"{self._now()}   \033[36m[请求体]\033[0m {json.dumps(json.loads(body), indent=2, ensure_ascii=False)}")
                except:
                    print(f"{self._now()}   \033[36m[请求体]\033[0m {body[:500]}")
            color = "\033[92m" if resp.status_code < 400 else "\033[91m"
            print(f"{self._now()}   {color}[{method}] {resp.status_code} ({dur:.0f}ms)\033[0m")
            print(f"{self._now()}   \033[35m[响应头]\033[0m {dict(resp.headers)}")
            ct = resp.headers.get("content-type", "")
            if "text/event-stream" in ct:
                print(f"{self._now()}   \033[33m[SSE]\033[0m 流式响应 ↓↓↓")
                self._send_sse(resp)
                return
            if not any(ct.startswith(t) for t in ("image/","audio/","video/","application/octet-stream")) and len(resp.content) < 102400:
                try:
                    print(f"{self._now()}   \033[33m[响应体]\033[0m {json.dumps(resp.json(), indent=2, ensure_ascii=False)}")
                except:
                    print(f"{self._now()}   \033[33m[响应体]\033[0m {resp.text[:1000]}")
            if resp.status_code >= 400:
                print(f"{self._now()}   ⚠️ \033[91mHTTP {resp.status_code}\033[0m")

            self.send_response(resp.status_code)
            for k, v in resp.headers.items():
                if k.lower() not in ("transfer-encoding", "connection", "content-encoding"):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(resp.content)
        except requests.exceptions.ConnectionError:
            print(f"{self._now()} ❌ \033[91m无法连接后端: {self.backend_url}\033[0m")
            self.send_error(502, "Backend Unavailable")
        except Exception as e:
            print(f"{self._now()} ❌ \033[91m代理错误: {e}\033[0m")
            self.send_error(502, "Backend Error")

    def _send_sse(self, resp):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            for chunk in resp.iter_content(chunk_size=1):
                if chunk:
                    s = chunk.decode("utf-8", errors="replace")
                    if s.strip():
                        print(f"    \033[33m>>\033[0m {s.rstrip()}")
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except:
            pass

    # ==================== 请求分发 ====================

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/ws":
            self._proxy_ws()
        elif p.startswith("/api/"):
            self._proxy_api("GET")
        else:
            self._serve_static()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._proxy_api("POST")
        else:
            self.send_error(404)

    def do_PUT(self):
        if self.path.startswith("/api/"):
            self._proxy_api("PUT")
        else:
            self.send_error(404)

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            self._proxy_api("DELETE")
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def _serve_static(self):
        path = urlparse(self.path).path
        if path == "/":
            path = "/index.html"
        filepath = os.path.join(FRONTEND_DIR, path.lstrip("/"))
        if os.path.isfile(filepath):
            self.send_response(200)
            ext = os.path.splitext(filepath)[1].lower()
            ct = {
                ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8", ".json": "application/json",
                ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".svg": "image/svg+xml", ".ico": "image/x-icon",
            }
            self.send_header("Content-Type", ct.get(ext, "application/octet-stream"))
            self.end_headers()
            with open(filepath, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404)

    def handle_one_request(self):
        self._ws_mode = False
        try:
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.send_error(414)
                return
            if not self.raw_requestline:
                self.close_connection = True
                return
            if not self.parse_request():
                return
            mname = 'do_' + self.command
            if not hasattr(self, mname):
                self.send_error(501)
                return
            getattr(self, mname)()
            if not self._ws_mode:
                self.wfile.flush()
        except socket.timeout:
            self.handle_timeout()
            self.close_connection = True


# ==================== 手势识别服务 ====================

class GestureService:
    """手势识别服务管理器"""

    def __init__(self, ws_port=8765, camera_id=0):
        self.ws_port = ws_port
        self.camera_id = camera_id
        self.process = None
        self.running = False

    def start(self):
        """启动手势识别服务（子进程）"""
        if not os.path.exists(GESTURE_SCRIPT):
            print(f"  ⚠️  手势识别脚本不存在: {GESTURE_SCRIPT}")
            print(f"     跳过手势服务启动")
            return

        script_dir = os.path.dirname(GESTURE_SCRIPT)
        cmd = [
            sys.executable,
            GESTURE_SCRIPT,
            f"--ws-port={self.ws_port}",
            f"--camera={self.camera_id}",
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=script_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            self.running = True
            print(f"  ✅ 手势识别服务已启动 (pid={self.process.pid})")
            print(f"  📷 摄像头: #{self.camera_id}")
            print(f"  🔌 WebSocket: ws://127.0.0.1:{self.ws_port}")

            # 启动日志线程
            t = threading.Thread(target=self._log_reader, daemon=True)
            t.start()
        except Exception as e:
            print(f"  ❌ 手势识别启动失败: {e}")

    def _log_reader(self):
        """读取手势服务的日志输出"""
        try:
            for line in iter(self.process.stdout.readline, b''):
                if line:
                    text = line.decode('utf-8', errors='replace').rstrip()
                    if text:
                        print(f"  \033[36m[Gesture]\033[0m {text}")
        except:
            pass

    def stop(self):
        """停止手势识别服务"""
        if self.process and self.process.poll() is None:
            if sys.platform == "win32":
                self.process.terminate()
            else:
                os.kill(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=3)
            except:
                self.process.kill()
            print(f"  👋 手势识别服务已停止")
        self.running = False


# ==================== 启动 ====================

def find_free_port(start):
    for p in range(start, start + 100):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", p))
            s.close()
            return p
        except:
            pass
    raise RuntimeError(f"无可用端口 (从 {start})")


def print_banner(port, backend, gesture_port):
    banner = f"""
  ╔{'═'*50}╗
  ║{' ' * 20}CToS 客户端{' ' * 20}║
  ╠{'═'*50}╣
  ║  🔗 前台: http://localhost:{port}{' ' * (32 - len(str(port)))}║
  ║  🖥️  后端: {backend}{' ' * (38 - len(backend))}║
  ║  📁 目录: {os.path.basename(FRONTEND_DIR)}{' ' * (38 - len(os.path.basename(FRONTEND_DIR)))}║
  ╠{'═'*50}╣
  ║  代理: WS /ws → {backend}/ws{' ' * (27 - len(backend))}║
  ║       API /api/* → {backend}/api/*{' ' * (24 - len(backend))}║
  ║  🖐️  手势: ws://127.0.0.1:{gesture_port}{' ' * (25 - len(str(gesture_port)))}║
  ╚{'═'*50}╝
"""
    print(banner)


def main():
    parser = argparse.ArgumentParser(description="CToS 统一客户端启动器")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="前端HTTP端口")
    parser.add_argument("--backend", type=str, default=DEFAULT_BACKEND, help="后端API地址")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--no-gesture", action="store_true", help="不启动手势识别服务")
    parser.add_argument("--camera", type=int, default=0, help="手势识别的摄像头ID")
    parser.add_argument("--gesture-port", type=int, default=GESTURE_WS_PORT, help="手势WebSocket端口")
    args = parser.parse_args()

    port = find_free_port(args.port)
    backend = args.backend.rstrip("/")
    gesture_port = args.gesture_port

    # 启动手势识别服务
    gesture_service = None
    if not args.no_gesture:
        gesture_service = GestureService(ws_port=gesture_port, camera_id=args.camera)
        gesture_service.start()

    print_banner(port, backend, gesture_port)

    # 启动 HTTP 服务器
    server = ThreadingHTTPServer(
        ("127.0.0.1", port),
        lambda *a, **kw: DebugHTTPRequestHandler(*a, backend_url=backend, **kw)
    )

    if not args.no_browser:
        t = threading.Thread(
            target=lambda: (__import__("time").sleep(1.5), webbrowser.open(f"http://localhost:{port}")),
            daemon=True
        )
        t.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  👋 正在关闭...")
        server.server_close()
        if gesture_service:
            gesture_service.stop()
        print("  ✅ 已停止\n")


if __name__ == "__main__":
    main()