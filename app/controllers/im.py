import json
import os
import uuid
import tornado.web
from app.controllers.base import BaseHandler
from app.models.im import IMRepository
from app.models.assistant import AssistantRepository

# 文件上传目录
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "im")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class IMPageHandler(BaseHandler):
    """即时通信主页面"""
    @tornado.web.authenticated
    def get(self):
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        self.render("im.html", title="智能聊天", username=self.current_user, user_id=user_id, xsrf_token=self.xsrf_token)


class IMConversationsHandler(BaseHandler):
    """获取用户的会话列表"""
    @tornado.web.authenticated
    def get(self):
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        conversations = IMRepository.get_user_conversations(user_id)
        for conv in conversations:
            if conv["type"] == "private":
                members = IMRepository.get_conversation_members(conv["id"])
                for m in members:
                    if m["id"] != user_id:
                        conv["name"] = m["username"]
                        conv["avatar"] = m["username"][0]
                        break
            else:
                conv["avatar"] = conv["name"][0] if conv["name"] else "#"
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": conversations})

    @tornado.web.authenticated
    def delete(self):
        """删除会话"""
        conv_id = int(self.get_argument("conversation_id", "0"))
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        if not conv_id:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 400, "msg": "参数错误"})
            return
        ok = IMRepository.delete_conversation(conv_id, user_id)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0 if ok else 500, "msg": "" if ok else "删除失败"})


class IMHistoryHandler(BaseHandler):
    """获取历史消息"""
    @tornado.web.authenticated
    def get(self):
        conv_id = int(self.get_argument("conversation_id", "0"))
        limit = int(self.get_argument("limit", "50"))
        before_id = int(self.get_argument("before_id", "0"))
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        # 验证用户是否在会话中
        members = IMRepository.get_conversation_members(conv_id)
        member_ids = [m["id"] for m in members]
        if user_id not in member_ids:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 403, "msg": "无权访问该会话"})
            return

        messages = IMRepository.get_messages(conv_id, limit, before_id)
        # 反转顺序（从旧到新）
        messages.reverse()
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": messages})


class IMSendHandler(BaseHandler):
    """HTTP 发送消息（备用）"""
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        conv_id = data.get("conversation_id", 0)
        msg_type = data.get("msg_type", "text")
        content = data.get("content", "")
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        if not conv_id or not content:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 400, "msg": "参数不完整"})
            return

        msg_id = IMRepository.save_message(conv_id, user_id, msg_type, content)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": {"id": msg_id}})


class IMCreatePrivateHandler(BaseHandler):
    """创建/获取私聊会话"""
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        target_id = data.get("target_id", 0)
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        if not target_id or target_id == user_id:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 400, "msg": "参数错误"})
            return

        conv_id = IMRepository.create_private_conversation(user_id, target_id)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": {"conversation_id": conv_id}})


class IMAssistantChatHandler(BaseHandler):
    """创建/获取与数字员工的私聊会话"""
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        assistant_id = data.get("assistant_id", 0)
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        if not assistant_id:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 400, "msg": "参数错误"})
            return

        target_uid = IMRepository.get_or_create_assistant_user(assistant_id)
        if not target_uid:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 404, "msg": "数字员工不存在"})
            return

        if target_uid == user_id:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 400, "msg": "不能和自己聊天"})
            return

        conv_id = IMRepository.create_private_conversation(user_id, target_uid)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": {"conversation_id": conv_id}})


class IMCreateGroupHandler(BaseHandler):
    """创建群聊会话"""
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        name = data.get("name", "")
        member_ids = data.get("member_ids", [])
        assistant_ids = data.get("assistant_ids", [])
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        if not name or (not member_ids and not assistant_ids):
            self.set_header("Content-Type", "application/json")
            self.write({"code": 400, "msg": "参数不完整"})
            return

        conv_id = IMRepository.create_group_conversation(name, user_id, member_ids, assistant_ids)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": {"conversation_id": conv_id}})


class IMMembersHandler(BaseHandler):
    """获取会话成员"""
    @tornado.web.authenticated
    def get(self):
        conv_id = int(self.get_argument("conversation_id", "0"))
        members = IMRepository.get_conversation_members(conv_id)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": members})


class IMUsersHandler(BaseHandler):
    """获取所有用户（用于通讯录）"""
    @tornado.web.authenticated
    def get(self):
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        users = IMRepository.get_all_users(user_id)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": users})


class IMAssistantsHandler(BaseHandler):
    """获取启用的数字员工列表"""
    @tornado.web.authenticated
    def get(self):
        assistants = AssistantRepository.get_enabled_assistants()
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": assistants})


class IMSearchHandler(BaseHandler):
    """全局搜索"""
    @tornado.web.authenticated
    def get(self):
        keyword = self.get_argument("keyword", "").strip()
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        if not keyword:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 0, "data": {"users": [], "groups": []}})
            return

        users = IMRepository.search_users(keyword, user_id)
        groups = IMRepository.search_groups(keyword, user_id)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": {"users": users, "groups": groups}})


class IMMarkReadHandler(BaseHandler):
    """标记已读"""
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        conv_id = data.get("conversation_id", 0)
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        IMRepository.mark_read(conv_id, user_id)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0})


class IMFriendsHandler(BaseHandler):
    """获取好友列表"""
    @tornado.web.authenticated
    def get(self):
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        friends = IMRepository.get_friends(user_id)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": friends})


class IMFriendRequestHandler(BaseHandler):
    """发送/处理好友申请"""
    @tornado.web.authenticated
    def post(self):
        from app.controllers.im_ws import broadcast_to_user
        import json as json_mod

        data = json.loads(self.request.body)
        action = data.get("action", "")
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        if action == "send":
            target_id = data.get("target_id", 0)
            message = data.get("message", "")
            if not target_id or target_id == user_id:
                self.set_header("Content-Type", "application/json")
                self.write({"code": 400, "msg": "参数错误"})
                return
            # 检查是否已经是好友
            if IMRepository.is_friend(user_id, target_id):
                self.set_header("Content-Type", "application/json")
                self.write({"code": 400, "msg": "已是好友"})
                return
            # 检查是否已有待处理申请
            if IMRepository.has_sent_pending_request(user_id, target_id):
                self.set_header("Content-Type", "application/json")
                self.write({"code": 400, "msg": "已发送申请"})
                return
            req_id = IMRepository.send_friend_request(user_id, target_id, message)
            # 通过 WebSocket 通知目标用户
            broadcast_to_user(target_id, json_mod.dumps({
                "type": "friend_request",
                "request_id": req_id,
                "from_user_id": user_id,
                "from_name": self.current_user,
                "message": message
            }))
            self.set_header("Content-Type", "application/json")
            self.write({"code": 0, "data": {"request_id": req_id}})

        elif action == "handle":
            request_id = data.get("request_id", 0)
            status = data.get("status", "")  # accepted / rejected
            if not request_id or status not in ("accepted", "rejected"):
                self.set_header("Content-Type", "application/json")
                self.write({"code": 400, "msg": "参数错误"})
                return
            # 获取申请信息用于通知
            success = IMRepository.handle_friend_request(request_id, status, user_id)
            self.set_header("Content-Type", "application/json")
            if success:
                # 通知发送方
                req_info = IMRepository.get_friend_request_by_id(request_id)
                if req_info:
                    ws_type = "friend_request_accepted" if status == "accepted" else "friend_request_rejected"
                    broadcast_to_user(req_info["from_user_id"], json_mod.dumps({
                        "type": ws_type,
                        "request_id": request_id,
                        "to_user_id": user_id,
                        "to_name": self.current_user
                    }))
                    # 如果同意，也通知发送方刷新好友列表
                    if status == "accepted":
                        broadcast_to_user(user_id, json_mod.dumps({
                            "type": "friend_added",
                            "friend_id": req_info["from_user_id"],
                            "friend_name": req_info.get("from_name", "")
                        }))
                self.write({"code": 0})
            else:
                self.write({"code": 403, "msg": "无权操作"})

        elif action == "delete":
            request_id = data.get("request_id", 0)
            if not request_id:
                self.set_header("Content-Type", "application/json")
                self.write({"code": 400, "msg": "参数错误"})
                return
            success = IMRepository.delete_friend_request(request_id, user_id)
            self.set_header("Content-Type", "application/json")
            if success:
                self.write({"code": 0})
            else:
                self.write({"code": 403, "msg": "无权操作"})

    @tornado.web.authenticated
    def get(self):
        """获取好友申请列表"""
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        req_type = self.get_argument("type", "received")
        received = req_type == "received"
        requests = IMRepository.get_friend_requests(user_id, received)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": requests})


class IMRemoveFriendHandler(BaseHandler):
    """删除好友"""
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        friend_id = data.get("friend_id", 0)
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        if not friend_id:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 400, "msg": "参数错误"})
            return
        IMRepository.remove_friend(user_id, friend_id)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0})


class IMGroupsHandler(BaseHandler):
    """获取用户的群聊列表"""
    @tornado.web.authenticated
    def get(self):
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        groups = IMRepository.get_user_groups(user_id)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": groups})


class IMGroupManageHandler(BaseHandler):
    """群聊管理（添加/移除成员）"""
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        action = data.get("action", "")
        group_id = data.get("group_id", 0)
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        if not group_id:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 400, "msg": "参数错误"})
            return

        # 验证是否为群主或管理员
        members = IMRepository.get_conversation_members(group_id)
        is_admin = any(m["id"] == user_id and m["role"] == "admin" for m in members)
        if not is_admin:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 403, "msg": "无权操作"})
            return

        if action == "add":
            member_ids = data.get("member_ids", [])
            for mid in member_ids:
                IMRepository.add_group_member(group_id, mid)
            self.set_header("Content-Type", "application/json")
            self.write({"code": 0})

        elif action == "remove":
            member_id = data.get("member_id", 0)
            if not member_id:
                self.set_header("Content-Type", "application/json")
                self.write({"code": 400, "msg": "参数错误"})
                return
            IMRepository.remove_group_member(group_id, member_id)
            self.set_header("Content-Type", "application/json")
            self.write({"code": 0})

        elif action == "update":
            name = data.get("name")
            IMRepository.update_group_info(group_id, name=name)
            self.set_header("Content-Type", "application/json")
            self.write({"code": 0})


class IMFileUploadHandler(BaseHandler):
    """文件上传"""
    @tornado.web.authenticated
    def post(self):
        files = self.request.files.get("file", [])
        if not files:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 400, "msg": "未上传文件"})
            return

        file_info = files[0]
        # 生成唯一文件名
        ext = os.path.splitext(file_info["filename"])[1] if "." in file_info["filename"] else ""
        filename = str(uuid.uuid4()) + ext
        filepath = os.path.join(UPLOAD_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(file_info["body"])

        # 限制 10MB
        file_size = len(file_info["body"])
        if file_size > 10 * 1024 * 1024:
            os.remove(filepath)
            self.set_header("Content-Type", "application/json")
            self.write({"code": 400, "msg": "文件大小不能超过10MB"})
            return

        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": {
            "filename": file_info["filename"],
            "url": "/im/api/file/" + filename,
            "size": file_size,
            "type": "file" if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp") else "image"
        }})


class IMFileDownloadHandler(BaseHandler):
    """文件下载"""
    @tornado.web.authenticated
    def get(self, filename):
        filepath = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(filepath):
            self.set_status(404)
            self.write("文件不存在")
            return

        # 设置正确的 Content-Type
        ext = os.path.splitext(filename)[1].lower()
        content_types = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".gif": "image/gif", ".webp": "image/webp", ".pdf": "application/pdf",
            ".txt": "text/plain", ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".zip": "application/zip", ".rar": "application/x-rar-compressed"
        }
        self.set_header("Content-Type", content_types.get(ext, "application/octet-stream"))
        self.set_header("Content-Disposition", f'attachment; filename="{filename}"')
        with open(filepath, "rb") as f:
            self.write(f.read())
