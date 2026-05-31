import json
import time
import datetime
import httpx
import tornado.websocket
import tornado.web
from app.models.im import IMRepository
from app.models.assistant import AssistantRepository
from app.models.model import ModelRepository
from app.models.db import get_connection


# 全局连接池：user_id -> set of WebSocket connections
connection_pool = {}


class IMWebSocketHandler(tornado.websocket.WebSocketHandler):
    """即时通信 WebSocket 处理器"""

    def check_origin(self, origin):
        return True

    def get_current_user(self):
        """从 cookie 获取当前用户"""
        return self.get_secure_cookie("username")

    @tornado.web.authenticated
    async def open(self):
        """建立连接"""
        username = self.current_user
        if isinstance(username, bytes):
            username = username.decode("utf-8")
        self.username = username
        self.user_id = IMRepository.get_user_id_by_username(username)
        self._last_pong = time.time()

        if not self.user_id:
            self.close()
            return

        # 注册到连接池
        if self.user_id not in connection_pool:
            connection_pool[self.user_id] = set()
        connection_pool[self.user_id].add(self)

        # 发送连接成功消息
        await self.write_message(json.dumps({
            "type": "connected",
            "user_id": self.user_id,
            "username": self.username
        }))

        # 推送离线消息
        offline_msgs = IMRepository.get_offline_messages(self.user_id)
        if offline_msgs:
            pushed_convs = set()
            for msg in offline_msgs:
                await self.write_message(json.dumps({
                    "type": "message",
                    "id": msg["id"],
                    "conversation_id": msg["conversation_id"],
                    "sender_id": msg["sender_id"],
                    "sender_name": msg["sender_name"],
                    "msg_type": msg["type"],
                    "content": msg["content"],
                    "create_at": msg["create_at"]
                }))
                pushed_convs.add(msg["conversation_id"])
            # 标记这些会话的消息为已读
            for conv_id in pushed_convs:
                IMRepository.mark_messages_read_by_conv(conv_id, self.user_id)

    async def on_message(self, message):
        """接收消息"""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")

            if msg_type == "ping":
                self._last_pong = time.time()
                await self.write_message(json.dumps({"type": "pong", "timestamp": int(time.time())}))
                return

            if msg_type == "message":
                await self._handle_message(data)
                return

            if msg_type == "read":
                await self._handle_read(data)
                return

        except Exception as e:
            await self.write_message(json.dumps({
                "type": "error",
                "message": str(e)
            }))

    async def _handle_message(self, data):
        """处理消息发送"""
        conv_id = data.get("conversation_id", 0)
        msg_type = data.get("msg_type", "text")
        content = data.get("content", "")
        client_msg_id = data.get("client_msg_id", "")  # 客户端消息ID（用于幂等）

        if not conv_id or not content:
            await self.write_message(json.dumps({
                "type": "error",
                "message": "参数不完整"
            }))
            return

        # 幂等检查：如果客户端提供了 client_msg_id，检查是否已存在
        if client_msg_id and IMRepository.is_msg_exists(client_msg_id):
            # 消息已存在，返回之前的 msg_id
            msg_id = IMRepository.get_msg_id_by_client_id(client_msg_id)
            await self.write_message(json.dumps({
                "type": "ack",
                "msg_id": msg_id,
                "conversation_id": conv_id,
                "client_msg_id": client_msg_id
            }))
            return

        # 群聊禁言检查
        conv_info = IMRepository.get_conversation_info(conv_id)
        if conv_info and conv_info.get("type") == "group":
            mute_check = IMRepository.is_muted(conv_id, self.user_id)
            if mute_check["is_muted"]:
                await self.write_message(json.dumps({
                    "type": "error",
                    "message": mute_check["reason"]
                }))
                return
            # 更新最后发言时间
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with get_connection() as conn:
                conn.execute(
                    "UPDATE im_conversation_members SET last_speak_at=? WHERE conversation_id=? AND user_id=?",
                    (now, conv_id, self.user_id)
                )

        # 保存消息到数据库
        msg_id = IMRepository.save_message(conv_id, self.user_id, msg_type, content, client_msg_id)

        # 获取发送者名称
        sender_name = self.username

        # 获取发送者在当前群中的角色（如果是群聊）
        sender_role = ""
        if conv_info and conv_info.get("type") == "group":
            role_info = IMRepository.get_member_role(conv_id, self.user_id)
            sender_role = role_info if role_info else ""

        # 构造消息对象
        msg_obj = {
            "type": "message",
            "id": msg_id,
            "conversation_id": conv_id,
            "sender_id": self.user_id,
            "sender_name": sender_name,
            "sender_role": sender_role,
            "msg_type": msg_type,
            "content": content,
            "create_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        }

        # 推送给会话中的其他在线成员
        members = IMRepository.get_conversation_members(conv_id)
        for member in members:
            mid = member["id"]
            if mid != self.user_id and mid in connection_pool:
                for conn in connection_pool[mid]:
                    try:
                        await conn.write_message(json.dumps(msg_obj))
                    except Exception:
                        pass

        # 发送 ack 确认给发送者
        await self.write_message(json.dumps({
            "type": "ack",
            "msg_id": msg_id,
            "conversation_id": conv_id,
            "client_msg_id": client_msg_id
        }))

        # 检测是否需要数字员工回复（私聊中对方是数字员工，或群聊中@了数字员工）
        await self._maybe_assistant_reply(conv_id, content, members)

    async def _maybe_assistant_reply(self, conv_id, content, members):
        """检测消息是否需要数字员工回复"""
        # 保存当前会话ID，供 _call_assistant_api 中截胡天气助手使用
        self._current_conv_id = conv_id

        # 情况1：私聊中对方是数字员工
        if len(members) == 2:
            for m in members:
                if m["id"] != self.user_id:
                    ast_id = IMRepository.get_assistant_id_by_user_id(m["id"])
                    if ast_id:
                        reply = await self._call_assistant_api(ast_id, content)
                        if reply:
                            reply_msg_id = IMRepository.save_message(
                                conv_id, m["id"], "text",
                                reply, ""
                            )
                            reply_obj = {
                                "type": "message",
                                "id": reply_msg_id,
                                "conversation_id": conv_id,
                                "sender_id": m["id"],
                                "sender_name": m["username"],
                                "msg_type": "text",
                                "content": reply,
                                "create_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                            }
                            for mb in members:
                                if mb["id"] in connection_pool:
                                    for conn in connection_pool[mb["id"]]:
                                        try:
                                            await conn.write_message(json.dumps(reply_obj))
                                        except Exception:
                                            pass
                        return

        # 情况2：群聊中 @数字员工名称
        conv_info = IMRepository.get_conversation_info(conv_id)
        if conv_info and conv_info.get("type") == "group" and "@" in content:
            import re
            at_pattern = re.findall(r'@(\S+)', content)
            for at_name in at_pattern:
                at_name = at_name.rstrip('，,。.!！?？:：')
                asst = AssistantRepository.get_assistant_by_name(at_name) or AssistantRepository.get_assistant_by_code(at_name)
                if asst:
                    asst_uid = IMRepository.get_or_create_assistant_user(asst["id"])
                    if asst_uid:
                        user_msg = content.split("@" + at_name, 1)[-1].strip()
                        if not user_msg:
                            user_msg = "你好"
                        reply = await self._call_assistant_api(asst["id"], user_msg)
                        if reply:
                            reply_msg_id = IMRepository.save_message(
                                conv_id, asst_uid, "text",
                                "@" + self.username + " " + reply, ""
                            )
                            reply_obj = {
                                "type": "message",
                                "id": reply_msg_id,
                                "conversation_id": conv_id,
                                "sender_id": asst_uid,
                                "sender_name": "系统",
                                "msg_type": "text",
                                "content": "@" + self.username + " " + reply,
                                "create_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                            }
                            for mb in members:
                                if mb["id"] in connection_pool:
                                    for conn in connection_pool[mb["id"]]:
                                        try:
                                            await conn.write_message(json.dumps(reply_obj))
                                        except Exception:
                                            pass
                    break

    async def _call_assistant_api(self, assistant_id, user_message):
        """调用数字员工AI API获取回复"""
        try:
            asst = AssistantRepository.get_assistant_by_id(assistant_id)
            if not asst:
                return None

            # =============================================
            # TODO: 截胡天气助手 - 转发到外部 CToS2 服务器
            # =============================================
            #
            # 外部服务器地址: http://{host}:9877
            # 接口: POST /weather
            # 请求体:
            #   {
            #     "city": "北京",
            #     "conversation_id": "conv_2",      # 字符串类型！
            #     "callback_url": "http://本服务器IP:10086/im/api/weather/callback"
            #   }
            #
            # 外部服务器会分 2 次回调 callback_url：
            #   第1次: {"conversation_id": "conv_2", "type": "image", "image_url": "http://...png", "text": "天气卡片"}
            #   第2次: {"conversation_id": "conv_2", "type": "text",  "text": "☀️ 北京 今日天气：晴..."}
            #
            # 本服务器的 WeatherCallbackHandler 按 type 字段分别处理。
            # =============================================
            if asst.get("assistant_code") == "weather_query":
                try:
                    # CToS2 外部服务地址（同机本地运行，端口 9877）
                    EXTERNAL_FASTAPI_URL = "http://127.0.0.1:9877/weather"

                    conv_id = getattr(self, "_current_conv_id", 0)

                    # 获取数字员工的 user_id，回调时需要用正确的 sender_id 保存消息
                    asst_uid = IMRepository.get_or_create_assistant_user(assistant_id)

                    # 本服务器的回调地址（同机 Tornado 端口 10086）
                    CALLBACK_URL = "http://127.0.0.1:10086/im/api/weather/callback"

                    # 注意：conversation_id 需要转为字符串，因为外部服务器接收字符串类型
                    payload = {
                        "city": user_message,
                        "conversation_id": str(conv_id),
                        "callback_url": CALLBACK_URL,
                        "sender_id": asst_uid
                    }
                    import asyncio
                    asyncio.ensure_future(self._send_weather_request(EXTERNAL_FASTAPI_URL, payload))
                    return "⏳ 正在查询天气，请稍候..."
                except Exception as e:
                    return f"天气服务异常: {str(e)}"

            # =============================================
            # TODO: 如果外部 FastAPI 支持同步响应，也可以使用下面的同步模式
            # （取消下方注释，注释掉上面的异步回调代码即可）
            # =============================================
            # if asst.get("assistant_code") == "weather_query":
            #     try:
            #         EXTERNAL_FASTAPI_URL = "http://your-fastapi-server:9877/weather"
            #         payload = {
            #             "city": user_message,
            #             "user_id": self.user_id if hasattr(self, "user_id") else 0
            #         }
            #         async with httpx.AsyncClient(timeout=15.0) as client:
            #             resp = await client.post(EXTERNAL_FASTAPI_URL, json=payload)
            #             if resp.status_code == 200:
            #                 data = resp.json()
            #                 reply = data.get("reply", "")
            #                 if reply:
            #                     return reply
            #             return f"天气查询失败，服务器返回: HTTP {resp.status_code}"
            #     except httpx.ConnectError:
            #         return "天气服务暂时不可用（无法连接到外部服务器），请确认 FastAPI 服务器已启动。"
            #     except Exception as e:
            #         return f"天气服务异常: {str(e)}"

            prompt_template = asst.get("prompt_template", "")
            if prompt_template:
                system_msg = prompt_template.replace("{query}", user_message).replace("{{query}}", user_message)
            else:
                system_msg = f"你是数字员工「{asst['assistant_name']}」，请用专业友好的语气回答用户问题。"

            model = ModelRepository.get_default_model()
            if asst.get("model_id"):
                m = ModelRepository.get_model_by_id(asst["model_id"])
                if m and m.get("status") == 1:
                    model = m
            if not model:
                return "抱歉，没有可用模型。"

            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_message}
            ]

            async with httpx.AsyncClient(timeout=120.0) as client:
                headers = {"Authorization": f"Bearer {model['api_key']}", "Content-Type": "application/json"}
                payload = {"model": model["code"], "messages": messages, "stream": False}
                resp = await client.post(model["api_url"], headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "")
                return "抱歉，AI 服务暂时不可用。"
        except Exception:
            return "抱歉，AI 服务暂时不可用。"

    async def _handle_read(self, data):
        """处理已读标记"""
        conv_id = data.get("conversation_id", 0)
        if conv_id:
            IMRepository.mark_read(conv_id, self.user_id)

    def on_close(self):
        """连接关闭"""
        if hasattr(self, "user_id") and self.user_id in connection_pool:
            connection_pool[self.user_id].discard(self)
            if not connection_pool[self.user_id]:
                del connection_pool[self.user_id]

    async def _send_weather_request(self, url, payload):
        """异步发送天气查询请求到外部 FastAPI（fire-and-forget）"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(url, json=payload)
        except Exception:
            pass


class WeatherCallbackHandler(tornado.web.RequestHandler):
    """
    外部 FastAPI 服务器的回调接口

    外部服务器分两次回调此接口：
    POST /im/api/weather/callback

    第1次（图片消息）:
    {
        "conversation_id": 2,
        "type": "image",
        "image_url": "http://host:9877/files/weather_card/weather_Beijing_xxx.png",
        "text": "🌤 北京 天气卡片"
    }

    第2次（文本消息）:
    {
        "conversation_id": 2,
        "type": "text",
        "text": "☀️ 北京 今日天气：晴..."
    }
    """

    def check_xsrf_cookie(self):
        pass

    def prepare(self):
        self.set_header("Content-Type", "application/json")

    async def post(self):
        try:
            data = json.loads(self.request.body)
        except Exception:
            self.write({"code": 400, "msg": "无效的JSON"})
            return

        conv_id_raw = data.get("conversation_id", "")
        msg_type = data.get("type", "")
        text = data.get("text", "")
        image_url = data.get("image_url", "")
        sender_id = data.get("sender_id", 0)  # 由外部服务传回的数字员工 user_id

        if isinstance(conv_id_raw, str) and conv_id_raw.startswith("conv_"):
            conv_id = int(conv_id_raw[5:])
        else:
            try:
                conv_id = int(conv_id_raw)
            except (ValueError, TypeError):
                conv_id = 0

        if not conv_id or not msg_type:
            self.write({"code": 400, "msg": "缺少 conversation_id 或 type"})
            return

        if msg_type not in ("image", "text"):
            self.write({"code": 400, "msg": "type 必须是 image 或 text"})
            return

        if msg_type == "image" and not image_url:
            self.write({"code": 400, "msg": "图片消息缺少 image_url"})
            return

        if msg_type == "text" and not text:
            self.write({"code": 400, "msg": "文本消息缺少 text"})
            return

        members = IMRepository.get_conversation_members(conv_id)
        if not members:
            self.write({"code": 404, "msg": "会话不存在"})
            return

        # 优先使用回调中传回的 sender_id（数字员工 user_id）
        # 如果没有传回，则在会话成员中查找关联了数字员工的用户
        if sender_id:
            assistant_uid = sender_id
        else:
            assistant_uid = None
            for m in members:
                ast_id = IMRepository.get_assistant_id_by_user_id(m["id"])
                if ast_id:
                    assistant_uid = m["id"]
                    break

        if not assistant_uid:
            self.set_status(400)
            self.write({"code": 400, "msg": "未找到数字员工"})
            return

        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        if msg_type == "image":
            content = image_url
            db_msg_type = "image"
        else:
            content = text
            db_msg_type = "text"

        msg_id = IMRepository.save_message(conv_id, assistant_uid, db_msg_type, content, "")
        msg_obj = {
            "type": "message",
            "id": msg_id,
            "conversation_id": conv_id,
            "sender_id": assistant_uid,
            "sender_name": "天气查询",
            "msg_type": db_msg_type,
            "content": content,
            "create_at": now
        }

        for m in members:
            if m["id"] in connection_pool:
                for conn in connection_pool[m["id"]]:
                    try:
                        conn.write_message(json.dumps(msg_obj))
                    except Exception:
                        pass

        self.write({"code": 0, "msg": "ok"})


def is_user_online(user_id: int) -> bool:
    """检查用户是否在线"""
    return user_id in connection_pool and len(connection_pool[user_id]) > 0


def broadcast_to_user(user_id: int, message: str):
    """向指定用户广播消息"""
    if user_id in connection_pool:
        for conn in connection_pool[user_id]:
            try:
                conn.write_message(message)
            except Exception:
                pass
