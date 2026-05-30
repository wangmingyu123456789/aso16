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
