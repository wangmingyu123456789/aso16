import json
import os
import uuid
import hashlib
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


class IMRestoreConversationHandler(BaseHandler):
    """恢复已删除的会话"""
    @tornado.web.authenticated
    def post(self):
        conv_id = int(self.get_argument("conversation_id", "0"))
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        if not conv_id:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 400, "msg": "参数错误"})
            return
        IMRepository.restore_conversation(conv_id, user_id)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "msg": ""})


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

        # 检查是否为好友
        if not IMRepository.is_friend(user_id, target_id):
            self.set_header("Content-Type", "application/json")
            self.write({"code": 403, "msg": "只能和好友聊天"})
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
        from app.controllers.im_ws import broadcast_to_user
        import json as json_mod

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

        for mid in member_ids:
            if mid != user_id:
                invite = IMRepository.get_pending_invite(conv_id, mid)
                if invite:
                    broadcast_to_user(mid, json_mod.dumps({
                        "type": "group_invite",
                        "invite_id": invite["id"],
                        "group_id": conv_id,
                        "group_name": name,
                        "inviter_id": user_id,
                        "inviter_name": self.current_user,
                        "message": ""
                    }))

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
    """全局搜索（仅搜索好友和群聊）"""
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


class IMGlobalSearchHandler(BaseHandler):
    """全局搜索所有用户（用于添加好友）"""
    @tornado.web.authenticated
    def get(self):
        keyword = self.get_argument("keyword", "").strip()
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        if not keyword:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 0, "data": {"users": [], "groups": []}})
            return

        users = IMRepository.search_all_users(keyword, user_id)
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

        elif action == "mark_read":
            req_type = data.get("type", "received")
            IMRepository.mark_friend_req_read(user_id, req_type)
            self.set_header("Content-Type", "application/json")
            self.write({"code": 0})

    @tornado.web.authenticated
    def get(self):
        """获取好友申请列表"""
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        req_type = self.get_argument("type", "received")
        received = req_type == "received"
        requests = IMRepository.get_friend_requests(user_id, received)
        unread = IMRepository.get_unread_friend_req_count(user_id)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": requests, "unread": unread})


class IMGroupInviteHandler(BaseHandler):
    """发送/处理群邀请"""
    @tornado.web.authenticated
    def get(self):
        """获取群邀请列表"""
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        req_type = self.get_argument("type", "received")
        received = req_type == "received"
        invites = IMRepository.get_group_invites(user_id, received)
        unread = IMRepository.get_unread_group_invite_count(user_id)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": invites, "unread": unread})

    @tornado.web.authenticated
    def post(self):
        from app.controllers.im_ws import broadcast_to_user
        import json as json_mod

        data = json.loads(self.request.body)
        action = data.get("action", "")
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        if action == "send":
            group_id = data.get("group_id", 0)
            invitee_id = data.get("invitee_id", 0)
            message = data.get("message", "")
            if not group_id or not invitee_id or invitee_id == user_id:
                self.set_header("Content-Type", "application/json")
                self.write({"code": 400, "msg": "参数错误"})
                return
            if IMRepository.is_user_in_group(group_id, invitee_id):
                self.set_header("Content-Type", "application/json")
                self.write({"code": 400, "msg": "该用户已在群中"})
                return
            if IMRepository.has_pending_invite(group_id, invitee_id):
                self.set_header("Content-Type", "application/json")
                self.write({"code": 400, "msg": "已有待处理邀请"})
                return
            invite_id = IMRepository.create_group_invite(group_id, user_id, invitee_id, message)
            group_name = IMRepository.get_conversation_info(group_id).get("name", "")
            broadcast_to_user(invitee_id, json_mod.dumps({
                "type": "group_invite",
                "invite_id": invite_id,
                "group_id": group_id,
                "group_name": group_name,
                "inviter_id": user_id,
                "inviter_name": self.current_user,
                "message": message
            }))
            self.set_header("Content-Type", "application/json")
            self.write({"code": 0, "data": {"invite_id": invite_id}})

        elif action == "handle":
            invite_id = data.get("invite_id", 0)
            status = data.get("status", "")
            if not invite_id or status not in ("accepted", "rejected"):
                self.set_header("Content-Type", "application/json")
                self.write({"code": 400, "msg": "参数错误"})
                return
            success = IMRepository.handle_group_invite(invite_id, user_id, status)
            self.set_header("Content-Type", "application/json")
            if success:
                invite_info = IMRepository.get_invite_by_id(invite_id)
                if invite_info:
                    group_name = IMRepository.get_conversation_info(invite_info["group_id"]).get("name", "")
                    ws_type = "group_invite_accepted" if status == "accepted" else "group_invite_rejected"
                    broadcast_to_user(invite_info["inviter_id"], json_mod.dumps({
                        "type": ws_type,
                        "invite_id": invite_id,
                        "group_id": invite_info["group_id"],
                        "group_name": group_name,
                        "invitee_id": user_id,
                        "invitee_name": self.current_user
                    }))
                    if status == "accepted":
                        broadcast_to_user(user_id, json_mod.dumps({
                            "type": "group_joined",
                            "group_id": invite_info["group_id"],
                            "group_name": group_name
                        }))
                        from app.controllers.im_ws import broadcast_to_all_members
                        broadcast_to_all_members(invite_info["group_id"], json_mod.dumps({
                            "type": "member_added",
                            "group_id": invite_info["group_id"],
                            "user_id": user_id,
                            "username": self.current_user
                        }))
                        IMRepository.add_system_message(invite_info["group_id"], f"{self.current_user} 加入了群聊")
                self.write({"code": 0})
            else:
                self.write({"code": 403, "msg": "无权操作"})

        elif action == "delete":
            invite_id = data.get("invite_id", 0)
            if not invite_id:
                self.set_header("Content-Type", "application/json")
                self.write({"code": 400, "msg": "参数错误"})
                return
            success = IMRepository.delete_group_invite(invite_id, user_id)
            self.set_header("Content-Type", "application/json")
            if success:
                self.write({"code": 0})
            else:
                self.write({"code": 403, "msg": "无权操作"})

        elif action == "mark_read":
            invite_type = data.get("type", "received")
            IMRepository.mark_group_invite_read(user_id, invite_type)
            self.set_header("Content-Type", "application/json")
            self.write({"code": 0})

    @tornado.web.authenticated
    def get(self):
        """获取群邀请列表"""
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        invite_type = self.get_argument("type", "received")
        invites = IMRepository.get_group_invites(user_id, invite_type)
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": invites})


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
            IMRepository.update_group_info(group_id, name=name, operator_id=user_id)
            self.set_header("Content-Type", "application/json")
            self.write({"code": 0})


class IMFileUploadHandler(BaseHandler):
    """文件上传（支持去重存储，支持所有文件类型）"""
    @tornado.web.authenticated
    def post(self):
        files = self.request.files.get("file", [])
        if not files:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 400, "msg": "未上传文件"})
            return

        file_info = files[0]
        body = file_info["body"]
        file_size = len(body)
        original_name = file_info["filename"]
        if isinstance(original_name, bytes):
            original_name = original_name.decode('utf-8', errors='replace')

        # 限制 10MB
        if file_size > 10 * 1024 * 1024:
            self.set_header("Content-Type", "application/json")
            self.write({"code": 400, "msg": "文件大小不能超过10MB"})
            return

        # 获取扩展名，支持 .tar.gz 等多级扩展
        name_lower = original_name.lower()
        ext = ""
        if name_lower.endswith('.tar.gz'):
            ext = '.tar.gz'
        elif name_lower.endswith('.tar.bz2'):
            ext = '.tar.bz2'
        else:
            ext = os.path.splitext(original_name)[1].lower() if "." in original_name else ""

        file_hash = hashlib.sha256(body).hexdigest()
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        # 检测是否已有相同哈希的文件
        existing = IMRepository.find_file_by_hash(file_hash)
        if existing:
            IMRepository.increment_file_ref(existing["id"])
            file_id = existing["id"]
        else:
            sub_dir = file_hash[:2]
            target_dir = os.path.join(UPLOAD_DIR, sub_dir)
            os.makedirs(target_dir, exist_ok=True)
            filename = file_hash + ext
            filepath = os.path.join(target_dir, filename)
            with open(filepath, "wb") as f:
                f.write(body)

            storage_rel = os.path.join("uploads", "im", sub_dir, filename)
            mime_type = file_info.get("content_type", "")
            file_id = IMRepository.save_file_record(
                original_name, file_size, file_hash, ext, mime_type, storage_rel, user_id
            )

        is_image = ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg")
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": {
            "file_id": file_id,
            "filename": original_name,
            "url": "/im/api/file/" + file_hash + ext,
            "size": file_size,
            "type": "image" if is_image else "file"
        }})


class IMFileDownloadHandler(BaseHandler):
    """文件下载（支持 hash 路径和旧路径）"""
    @tornado.web.authenticated
    def get(self, filename):
        import urllib.parse

        # 尝试从 im_files 查找
        file_info = None
        name_no_ext = os.path.splitext(filename)[0]
        if len(name_no_ext) == 64:
            try:
                int(name_no_ext, 16)
                file_info = IMRepository.find_file_by_hash(name_no_ext)
            except ValueError:
                pass

        if file_info:
            filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), file_info["storage_path"])
        else:
            # 兼容旧路径
            filepath = os.path.join(UPLOAD_DIR, filename)

        if not os.path.exists(filepath):
            self.set_status(404)
            self.write("文件不存在")
            return

        ext = os.path.splitext(filename)[1].lower()
        content_types = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
            ".pdf": "application/pdf",
            ".txt": "text/plain", ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".zip": "application/zip", ".rar": "application/x-rar-compressed",
            ".mp3": "audio/mpeg", ".wav": "audio/wav", ".flac": "audio/flac", ".aac": "audio/aac",
            ".mp4": "video/mp4", ".avi": "video/x-msvideo", ".mov": "video/quicktime", ".mkv": "video/x-matroska",
            ".csv": "text/csv", ".json": "application/json", ".xml": "application/xml",
            ".py": "text/plain", ".js": "text/plain", ".ts": "text/plain", ".html": "text/plain", ".css": "text/plain",
            ".md": "text/markdown", ".yml": "text/plain", ".yaml": "text/plain",
            ".7z": "application/x-7z-compressed", ".tar": "application/x-tar", ".gz": "application/gzip"
        }
        self.set_header("Content-Type", content_types.get(ext, "application/octet-stream"))

        # 获取原始文件名（用于下载显示）
        raw_name = file_info["file_name"] if file_info else filename
        safe_name = os.path.basename(raw_name)
        # 使用 RFC 5987 编码非ASCII文件名
        encoded_name = urllib.parse.quote(safe_name, safe='')
        self.set_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_name}")

        with open(filepath, "rb") as f:
            self.write(f.read())


class IMFilesHandler(BaseHandler):
    """文件列表查询"""
    @tornado.web.authenticated
    def get(self):
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        scope = self.get_argument("scope", "")
        conv_id = self.get_argument("conversation_id", "0")
        group_id = self.get_argument("group_id", "0")
        page = int(self.get_argument("page", "1"))
        page_size = int(self.get_argument("page_size", "50"))

        self.set_header("Content-Type", "application/json")

        if scope == "group" and group_id:
            # 群聊文件
            members = IMRepository.get_conversation_members(int(group_id))
            if user_id not in [m["id"] for m in members]:
                self.write({"code": 403, "msg": "无权访问"})
                return
            result = IMRepository.get_group_files(int(group_id), page, page_size)
        elif conv_id and int(conv_id) > 0:
            # 会话文件
            members = IMRepository.get_conversation_members(int(conv_id))
            if user_id not in [m["id"] for m in members]:
                self.write({"code": 403, "msg": "无权访问"})
                return
            result = IMRepository.get_conversation_files(int(conv_id), user_id, page, page_size)
        else:
            # 用户所有文件
            result = IMRepository.get_all_user_files(user_id, page, page_size)

        self.write({"code": 0, "data": result["data"], "total": result["total"]})
