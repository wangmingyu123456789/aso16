import json
import datetime
import tornado.web
from app.controllers.base import BaseHandler
from app.models.im import IMRepository
from app.controllers.im_ws import broadcast_to_user


def _json_response(handler, code=0, msg="", data=None):
    handler.set_header("Content-Type", "application/json")
    result = {"code": code, "msg": msg}
    if data is not None:
        result["data"] = data
    handler.write(result)


def _check_group_permission(group_id, user_id, allowed_roles):
    """检查群权限，返回 (is_ok, my_role, group_info)"""
    detail = IMRepository.get_group_detail(group_id, user_id)
    if not detail:
        return False, "none", None
    if detail.get('is_deleted'):
        return False, detail['my_role'], detail
    my_role = detail['my_role']
    if my_role not in allowed_roles:
        return False, my_role, detail
    return True, my_role, detail


class IMGroupDetailHandler(BaseHandler):
    """获取群详情"""
    @tornado.web.authenticated
    def get(self):
        group_id = int(self.get_argument("group_id", "0"))
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        if not group_id:
            return _json_response(self, 400, "参数错误")

        detail = IMRepository.get_group_detail(group_id, user_id)
        if not detail:
            return _json_response(self, 404, "群不存在")
        if detail.get('is_deleted'):
            return _json_response(self, 410, "群已被解散")

        members = IMRepository.get_group_members_detail(group_id)
        announcements = IMRepository.get_announcements(group_id, limit=10)
        settings = IMRepository.get_group_settings(group_id)

        _json_response(self, 0, "", {
            "group": detail,
            "members": members,
            "announcements": announcements,
            "settings": settings,
            "operation_logs": IMRepository.get_group_operation_logs(group_id, limit=50)
        })


class IMGroupMemberSearchHandler(BaseHandler):
    """搜索可邀请进群的用户"""
    @tornado.web.authenticated
    def get(self):
        group_id = int(self.get_argument("group_id", "0"))
        keyword = self.get_argument("keyword", "").strip()
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        if not group_id:
            return _json_response(self, 400, "参数错误")

        if not IMRepository.is_user_in_group(group_id, user_id):
            return _json_response(self, 403, "你不是群成员")

        if keyword:
            users = IMRepository.search_non_group_members(group_id, keyword, user_id)
        else:
            users = IMRepository.get_non_group_friends(user_id, group_id)

        for u in users:
            u['has_pending'] = IMRepository.has_pending_invite(group_id, u['id'])

        return _json_response(self, 0, "", {"users": users})


class IMGroupManageHandler(BaseHandler):
    """群管理统一入口（action 分发）"""
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        action = data.get("action", "")
        group_id = int(data.get("group_id", "0"))
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        if not group_id:
            return _json_response(self, 400, "参数错误")

        handlers_map = {
            'update_name': self._update_name,
            'update_avatar': self._update_avatar,
            'set_admin': self._set_admin,
            'remove_member': self._remove_member,
            'batch_remove': self._batch_remove,
            'mute_member': self._mute_member,
            'unmute_member': self._unmute_member,
            'mute_all': self._mute_all,
            'allow_join': self._allow_join,
            'add_member': self._add_member,
        }

        handler = handlers_map.get(action)
        if not handler:
            return _json_response(self, 400, "未知操作")

        return handler(group_id, user_id, data)

    def _update_name(self, group_id, user_id, data):
        ok, role, detail = _check_group_permission(group_id, user_id, ['owner'])
        if not ok:
            return _json_response(self, 403, "无权操作" if role != 'none' else "你不是群成员")
        name = (data.get("name") or "").strip()
        if not name:
            return _json_response(self, 400, "群名称不能为空")
        IMRepository.update_group_name(group_id, name, user_id)
        broadcast_to_all_members(group_id, {
            "type": "group_info_changed",
            "group_id": group_id,
            "name": name
        })
        return _json_response(self, 0, "群名称已更新")

    def _update_avatar(self, group_id, user_id, data):
        ok, role, detail = _check_group_permission(group_id, user_id, ['owner'])
        if not ok:
            return _json_response(self, 403, "无权操作")
        avatar = (data.get("avatar") or "").strip()
        IMRepository.update_group_avatar(group_id, avatar, user_id)
        broadcast_to_all_members(group_id, {
            "type": "group_info_changed",
            "group_id": group_id,
            "avatar": avatar
        })
        return _json_response(self, 0, "群头像已更新")

    def _set_admin(self, group_id, user_id, data):
        ok, role, detail = _check_group_permission(group_id, user_id, ['owner'])
        if not ok:
            return _json_response(self, 403, "仅群主可设置管理员")
        member_id = int(data.get("member_id", "0"))
        action = data.get("set_action", "")
        if not member_id or action not in ('set', 'cancel'):
            return _json_response(self, 400, "参数错误")
        if member_id == user_id:
            return _json_response(self, 400, "不能操作自己")
        IMRepository.set_admin(group_id, member_id, action, user_id)
        members = IMRepository.get_group_members_detail(group_id)
        target = next((m for m in members if m['id'] == member_id), None)
        new_role = target['role'] if target else 'member'
        broadcast_to_all_members(group_id, {
            "type": "member_role_changed",
            "group_id": group_id,
            "member_id": member_id,
            "member_name": IMRepository.get_username_by_id(member_id),
            "new_role": new_role,
            "operator_name": self.current_user
        })
        label = "设为管理员" if action == 'set' else "撤销管理员"
        return _json_response(self, 0, f"已{label}")

    def _remove_member(self, group_id, user_id, data):
        ok, role, detail = _check_group_permission(group_id, user_id, ['owner', 'admin'])
        if not ok:
            return _json_response(self, 403, "无权操作")
        member_id = int(data.get("member_id", "0"))
        if not member_id:
            return _json_response(self, 400, "参数错误")
        if member_id == user_id:
            return _json_response(self, 400, "不能移除自己")
        members = IMRepository.get_group_members_detail(group_id)
        target = next((m for m in members if m['id'] == member_id), None)
        if not target:
            return _json_response(self, 404, "成员不存在")
        if role == 'admin':
            if target['role'] in ('owner', 'admin'):
                return _json_response(self, 403, "管理员不能移除群主或其他管理员")
        member_name = IMRepository.get_username_by_id(member_id)
        IMRepository.remove_group_member_with_log(group_id, member_id, user_id)
        broadcast_to_all_members(group_id, {
            "type": "member_removed",
            "group_id": group_id,
            "member_id": member_id,
            "member_name": member_name,
            "operator_name": self.current_user
        })
        broadcast_to_user(member_id, json.dumps({
            "type": "you_removed",
            "group_id": group_id,
            "operator_name": self.current_user
        }))
        return _json_response(self, 0, f"已将 {member_name} 移出群聊")

    def _batch_remove(self, group_id, user_id, data):
        ok, role, detail = _check_group_permission(group_id, user_id, ['owner'])
        if not ok:
            return _json_response(self, 403, "仅群主可批量移除")
        member_ids = data.get("member_ids", [])
        if not member_ids:
            return _json_response(self, 400, "请选择成员")
        members = IMRepository.get_group_members_detail(group_id)
        valid_ids = []
        for mid in member_ids:
            if mid == user_id:
                continue
            target = next((m for m in members if m['id'] == mid), None)
            if target and target['role'] == 'member':
                valid_ids.append(mid)
        if not valid_ids:
            return _json_response(self, 400, "没有可移除的成员")
        IMRepository.batch_remove_members(group_id, valid_ids, user_id)
        for mid in valid_ids:
            member_name = IMRepository.get_username_by_id(mid)
            broadcast_to_all_members(group_id, {
                "type": "member_removed",
                "group_id": group_id,
                "member_id": mid,
                "member_name": member_name,
                "operator_name": self.current_user
            })
            broadcast_to_user(mid, json.dumps({
                "type": "you_removed",
                "group_id": group_id,
                "operator_name": self.current_user
            }))
        return _json_response(self, 0, f"已移除 {len(valid_ids)} 名成员")

    def _mute_member(self, group_id, user_id, data):
        ok, role, detail = _check_group_permission(group_id, user_id, ['owner', 'admin'])
        if not ok:
            return _json_response(self, 403, "无权操作")
        member_id = int(data.get("member_id", "0"))
        duration = int(data.get("duration", 60))
        if not member_id:
            return _json_response(self, 400, "参数错误")
        if member_id == user_id:
            return _json_response(self, 400, "不能禁言自己")
        members = IMRepository.get_group_members_detail(group_id)
        target = next((m for m in members if m['id'] == member_id), None)
        if not target:
            return _json_response(self, 404, "成员不存在")
        if role == 'admin':
            if target['role'] in ('owner', 'admin'):
                return _json_response(self, 403, "管理员不能禁言群主或其他管理员")
        mute_until = (datetime.datetime.now() + datetime.timedelta(minutes=duration)).strftime('%Y-%m-%d %H:%M:%S')
        IMRepository.mute_member(group_id, member_id, mute_until, user_id)
        member_name = IMRepository.get_username_by_id(member_id)
        broadcast_to_all_members(group_id, {
            "type": "member_muted",
            "group_id": group_id,
            "member_id": member_id,
            "member_name": member_name,
            "mute_until": mute_until,
            "operator_name": self.current_user
        })
        duration_text = f"{duration}分钟"
        if duration >= 1440:
            duration_text = f"{duration // 1440}天"
        elif duration >= 60:
            duration_text = f"{duration // 60}小时"
        return _json_response(self, 0, f"已禁言 {member_name} {duration_text}")

    def _unmute_member(self, group_id, user_id, data):
        ok, role, detail = _check_group_permission(group_id, user_id, ['owner', 'admin'])
        if not ok:
            return _json_response(self, 403, "无权操作")
        member_id = int(data.get("member_id", "0"))
        if not member_id:
            return _json_response(self, 400, "参数错误")
        IMRepository.unmute_member(group_id, member_id, user_id)
        member_name = IMRepository.get_username_by_id(member_id)
        broadcast_to_all_members(group_id, {
            "type": "member_muted",
            "group_id": group_id,
            "member_id": member_id,
            "member_name": member_name,
            "mute_until": None,
            "operator_name": self.current_user
        })
        return _json_response(self, 0, f"已解除 {member_name} 的禁言")

    def _mute_all(self, group_id, user_id, data):
        ok, role, detail = _check_group_permission(group_id, user_id, ['owner'])
        if not ok:
            return _json_response(self, 403, "仅群主可设置全体禁言")
        enabled = int(data.get("enabled", 0))
        IMRepository.set_mute_all(group_id, enabled, user_id)
        broadcast_to_all_members(group_id, {
            "type": "group_mute_all",
            "group_id": group_id,
            "enabled": enabled,
            "operator_name": self.current_user
        })
        msg = "已开启全体禁言" if enabled else "已关闭全体禁言"
        return _json_response(self, 0, msg)

    def _allow_join(self, group_id, user_id, data):
        ok, role, detail = _check_group_permission(group_id, user_id, ['owner'])
        if not ok:
            return _json_response(self, 403, "仅群主可设置")
        enabled = int(data.get("enabled", 1))
        IMRepository.set_allow_join(group_id, enabled, user_id)
        broadcast_to_all_members(group_id, {
            "type": "group_allow_join_changed",
            "group_id": group_id,
            "enabled": enabled
        })
        msg = "已允许新成员加入" if enabled else "已禁止新成员加入"
        return _json_response(self, 0, msg)

    def _add_member(self, group_id, user_id, data):
        print(f"[DEBUG] _add_member called: group_id={group_id}, user_id={user_id}, data={data}")
        ok, role, detail = _check_group_permission(group_id, user_id, ['owner', 'admin'])
        if not ok:
            return _json_response(self, 403, "无权操作")
        if detail.get('allow_join') == 0:
            return _json_response(self, 403, "群已禁止新成员加入")
        member_ids = data.get("member_ids", [])
        if not member_ids:
            return _json_response(self, 400, "请选择成员")
        added = []
        invited = []
        for mid in member_ids:
            print(f"[DEBUG] Processing member {mid}")
            is_member = IMRepository.is_group_member(group_id, mid)
            print(f"[DEBUG] is_group_member: {is_member}")
            if is_member:
                continue
            has_invite = IMRepository.has_pending_invite(group_id, mid)
            print(f"[DEBUG] has_pending_invite: {has_invite}")
            if has_invite:
                continue
            invite_id = IMRepository.create_group_invite(group_id, user_id, mid, "")
            print(f"[DEBUG] Created invite: {invite_id}")
            invited.append(mid)
            group_name = detail.get("name", "")
            broadcast_to_user(mid, json.dumps({
                "type": "group_invite",
                "invite_id": invite_id,
                "group_id": group_id,
                "group_name": group_name,
                "inviter_id": user_id,
                "inviter_name": self.current_user,
                "message": ""
            }))
        print(f"[DEBUG] Final result: invited={invited}")
        if invited:
            return _json_response(self, 0, f"已向 {len(invited)} 名成员发送入群邀请")
        return _json_response(self, 0, "所有成员已在群中或已有待处理邀请")


class IMGroupAnnounceHandler(BaseHandler):
    """公告管理"""
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        action = data.get("action", "publish")
        group_id = int(data.get("group_id", "0"))
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        if not group_id:
            return _json_response(self, 400, "参数错误")

        if action == "publish":
            ok, role, detail = _check_group_permission(group_id, user_id, ['owner', 'admin'])
            if not ok:
                return _json_response(self, 403, "无权发布公告")
            content = (data.get("content") or "").strip()
            if not content:
                return _json_response(self, 400, "公告内容不能为空")
            ann_id = IMRepository.publish_announcement(group_id, content, user_id)
            broadcast_to_all_members(group_id, {
                "type": "new_announcement",
                "group_id": group_id,
                "announcement_id": ann_id,
                "content": content,
                "publisher_name": self.current_user,
                "publisher_id": user_id,
                "time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            return _json_response(self, 0, "公告已发布", {"announcement_id": ann_id})

        elif action == "delete":
            ok, role, detail = _check_group_permission(group_id, user_id, ['owner', 'admin'])
            if not ok:
                return _json_response(self, 403, "无权操作")
            ann_id = int(data.get("announcement_id", "0"))
            if not ann_id:
                return _json_response(self, 400, "参数错误")
            result = IMRepository.delete_announcement(ann_id, group_id, user_id)
            if result:
                broadcast_to_all_members(group_id, {
                    "type": "announcement_deleted",
                    "group_id": group_id,
                    "announcement_id": ann_id,
                    "operator_name": self.current_user
                })
                return _json_response(self, 0, "公告已删除")
            else:
                return _json_response(self, 404, "公告不存在")

    @tornado.web.authenticated
    def get(self):
        group_id = int(self.get_argument("group_id", "0"))
        limit = int(self.get_argument("limit", "20"))
        if not group_id:
            return _json_response(self, 400, "参数错误")
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        if not IMRepository.is_group_member(group_id, user_id):
            return _json_response(self, 403, "你不是群成员")
        announcements = IMRepository.get_announcements(group_id, limit)
        return _json_response(self, 0, "", announcements)


class IMGroupDismissHandler(BaseHandler):
    """解散群聊"""
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        group_id = int(data.get("group_id", "0"))
        confirm_name = (data.get("confirm_name") or "").strip()
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        if not group_id:
            return _json_response(self, 400, "参数错误")

        ok, role, detail = _check_group_permission(group_id, user_id, ['owner'])
        if not ok:
            return _json_response(self, 403, "仅群主可解散群聊")

        if confirm_name != detail.get('name', ''):
            return _json_response(self, 400, "群名称输入不正确")

        group_name = detail['name']
        IMRepository.dismiss_group(group_id, user_id)
        broadcast_to_all_members(group_id, {
            "type": "group_dismissed",
            "group_id": group_id,
            "group_name": group_name,
            "operator_name": self.current_user
        })
        return _json_response(self, 0, "群聊已解散")


class IMGroupLeaveHandler(BaseHandler):
    """退出群聊"""
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        group_id = int(data.get("group_id", "0"))
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        if not group_id:
            return _json_response(self, 400, "参数错误")

        detail = IMRepository.get_group_detail(group_id, user_id)
        if not detail:
            return _json_response(self, 404, "群不存在")
        if detail['my_role'] == 'owner':
            return _json_response(self, 400, "群主不能退出群，请转让或解散")

        IMRepository.leave_group(group_id, user_id)
        return _json_response(self, 0, "已退出群聊")


class IMGroupTransferHandler(BaseHandler):
    """转让群主"""
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        group_id = int(data.get("group_id", "0"))
        new_owner_id = int(data.get("new_owner_id", "0"))
        user_id = IMRepository.get_user_id_by_username(self.current_user)

        if not group_id or not new_owner_id:
            return _json_response(self, 400, "参数错误")
        if new_owner_id == user_id:
            return _json_response(self, 400, "不能转让给自己")

        ok, role, detail = _check_group_permission(group_id, user_id, ['owner'])
        if not ok:
            return _json_response(self, 403, "仅群主可转让群")

        members = IMRepository.get_group_members_detail(group_id)
        target = next((m for m in members if m['id'] == new_owner_id), None)
        if not target:
            return _json_response(self, 404, "目标成员不在群内")

        new_owner_name = IMRepository.get_username_by_id(new_owner_id)
        IMRepository.transfer_group(group_id, new_owner_id, user_id)
        broadcast_to_all_members(group_id, {
            "type": "group_transferred",
            "group_id": group_id,
            "new_owner_id": new_owner_id,
            "new_owner_name": new_owner_name,
            "old_owner_name": self.current_user
        })
        return _json_response(self, 0, f"群已转让给 {new_owner_name}")


class IMAnnounceUnconfirmedHandler(BaseHandler):
    """获取用户未确认的最新公告"""
    @tornado.web.authenticated
    def get(self):
        group_id = int(self.get_argument("group_id", "0"))
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        if not group_id:
            return _json_response(self, 400, "参数错误")
        announcement = IMRepository.get_unconfirmed_announcement(group_id, user_id)
        if not announcement:
            return _json_response(self, 0, "", {"announcement": {}})
        detail = IMRepository.get_group_detail(group_id, user_id)
        publisher_id = announcement.get("publisher_id", 0)
        is_digital = IMRepository.is_digital_employee(user_id)
        return _json_response(self, 0, "", {
            "announcement": announcement,
            "need_confirm": user_id != publisher_id and not is_digital and bool(announcement)
        })


class IMAnnounceConfirmHandler(BaseHandler):
    """确认公告"""
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        announcement_id = int(data.get("announcement_id", "0"))
        group_id = int(data.get("group_id", "0"))
        user_id = IMRepository.get_user_id_by_username(self.current_user)
        if not announcement_id or not group_id:
            return _json_response(self, 400, "参数错误")
        detail = IMRepository.get_group_detail(group_id, user_id)
        if not detail or detail.get('is_deleted'):
            return _json_response(self, 404, "群不存在")
        IMRepository.confirm_announcement(announcement_id, group_id, user_id)
        broadcast_to_all_members(group_id, {
            "type": "announcement_confirmed",
            "group_id": group_id,
            "announcement_id": announcement_id,
            "user_id": user_id,
            "username": self.current_user
        })
        return _json_response(self, 0, "已确认公告")


def broadcast_to_all_members(group_id, message):
    """向群所有在线成员广播消息"""
    members = IMRepository.get_conversation_members(group_id)
    for member in members:
        broadcast_to_user(member["id"], json.dumps(message))
