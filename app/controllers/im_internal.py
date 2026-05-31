import json
import tornado.web
import tornado.websocket
from app.models.im import IMRepository
from app.models.im_server import MessageDelivery

# 内部端点不需要 xsrf 验证，也不需要鉴权（因为只在内网调用）


class InternalSendHandler(tornado.web.RequestHandler):
    """接收其他节点转发的消息，推送到本地WebSocket连接"""

    def check_xsrf_cookie(self):
        pass

    def prepare(self):
        self.set_header("Content-Type", "application/json")

    async def post(self):
        from app.controllers.im_ws import connection_pool

        try:
            data = json.loads(self.request.body)
        except Exception:
            self.write({"code": 400, "msg": "无效的JSON"})
            return

        messages = data.get("messages", [])
        if not messages:
            self.write({"code": 400, "msg": "缺少 messages"})
            return

        delivered = 0
        failed = 0

        for msg in messages:
            # 消息格式与 IMWebSocketHandler 推送的一致
            target_user_id = msg.get("target_user_id")
            if not target_user_id:
                failed += 1
                continue

            # 如果目标用户连接在本节点，推送
            if target_user_id in connection_pool:
                msg_obj = {
                    "type": "message",
                    "id": msg.get("id", 0),
                    "conversation_id": msg.get("conversation_id", 0),
                    "sender_id": msg.get("sender_id", 0),
                    "sender_name": msg.get("sender_name", ""),
                    "sender_role": msg.get("sender_role", ""),
                    "msg_type": msg.get("msg_type", "text"),
                    "content": msg.get("content", ""),
                    "create_at": msg.get("create_at", "")
                }
                for conn in connection_pool[target_user_id]:
                    try:
                        await conn.write_message(json.dumps(msg_obj))
                        delivered += 1
                    except Exception:
                        failed += 1
            else:
                failed += 1

        self.write({
            "code": 0,
            "msg": "ok",
            "delivered": delivered,
            "failed": failed
        })


class InternalHealthHandler(tornado.web.RequestHandler):
    """健康检查端点"""

    def check_xsrf_cookie(self):
        pass

    def prepare(self):
        self.set_header("Content-Type", "application/json")

    def get(self):
        self.write({
            "code": 0,
            "status": "online",
            "timestamp": __import__('time').time()
        })


class InternalBatchUserCheckHandler(tornado.web.RequestHandler):
    """批量检查哪些用户连接在本节点"""

    def check_xsrf_cookie(self):
        pass

    def prepare(self):
        self.set_header("Content-Type", "application/json")

    def post(self):
        from app.controllers.im_ws import connection_pool

        try:
            data = json.loads(self.request.body)
        except Exception:
            self.write({"code": 400, "msg": "无效的JSON"})
            return

        user_ids = data.get("user_ids", [])
        local_users = []
        remote_users = []

        for uid in user_ids:
            if uid in connection_pool and connection_pool[uid]:
                local_users.append(uid)
            else:
                remote_users.append(uid)

        self.write({
            "code": 0,
            "data": {
                "local_users": local_users,
                "remote_users": remote_users
            }
        })
