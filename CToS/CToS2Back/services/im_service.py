"""
IM 服务层 — 提供 IM 模块的内部服务函数
======================================
作用：将 routers/im.py 中的数据库查询逻辑提取为可复用的服务层，
      供 WebSocket 路由在拉取离线数据时直接调用（避免通过 HTTP）。
"""
from sqlalchemy import select, desc, or_, and_
from database.engine import db_manager
from database.models import (
    User, Friend, FriendRequest, ChatGroup, GroupMember,
    ChatMessage, ChatServer, File as FileModel,
)
from utils.helpers import logger


async def pull_messages_for_user(user_id: int, after_id: int = 0) -> list[dict]:
    """
    拉取用户在某时间点之后的所有消息（用于 WebSocket 离线消息拉取）
    """
    async with db_manager.get_session() as session:
        # 获取用户的会话列表（私聊 + 群聊）
        # 私聊：用户作为发送者或接收者的消息
        # 群聊：用户作为群成员收到的群消息
        query = select(ChatMessage).where(
            ChatMessage.id > after_id,
            or_(
                # 用户是发送者
                ChatMessage.sender_id == user_id,
                # 用户是私聊接收者
                and_(
                    ChatMessage.receiver_type == "user",
                    ChatMessage.receiver_id == user_id,
                ),
                # 用户是群成员（群聊消息）
                ChatMessage.receiver_type == "group",
            )
        ).order_by(ChatMessage.id).limit(200)

        result = await session.execute(query)
        messages = result.scalars().all()

        if not messages:
            return []

        # 过滤群聊消息：只保留用户所在的群
        group_ids = set()
        for m in messages:
            if m.receiver_type == "group":
                group_ids.add(m.receiver_id)

        user_group_ids = set()
        if group_ids:
            gm_result = await session.execute(
                select(GroupMember).where(
                    GroupMember.user_id == user_id,
                    GroupMember.group_id.in_(group_ids),
                )
            )
            user_group_ids = {gm.group_id for gm in gm_result.scalars().all()}

        # 获取发送者信息
        sender_ids = list(set(m.sender_id for m in messages))
        senders_result = await session.execute(
            select(User).where(User.id.in_(sender_ids))
        )
        senders_map = {u.id: u for u in senders_result.scalars().all()}

        result_list = []
        for m in messages:
            # 过滤：群聊消息但不是用户所在群
            if m.receiver_type == "group" and m.receiver_id not in user_group_ids:
                continue
            # 过滤：发送者不是用户自己的消息（已通过 above query 覆盖）
            result_list.append({
                "id": m.id,
                "sender_id": m.sender_id,
                "sender_username": senders_map[m.sender_id].username
                    if m.sender_id in senders_map else "未知",
                "sender_nickname": senders_map[m.sender_id].nickname
                    if m.sender_id in senders_map else "",
                "sender_avatar": senders_map[m.sender_id].avatar
                    if m.sender_id in senders_map else "",
                "receiver_type": m.receiver_type,
                "receiver_id": m.receiver_id,
                "type": m.type,
                "content": m.content or "",
                "file_id": m.file_id,
                "reply_to": m.reply_to,
                "created_at": m.created_at.isoformat()
                    if m.created_at else None,
            })

        return result_list


async def pull_conversations_for_user(user_id: int) -> list[dict]:
    """
    拉取用户的会话列表（用于 WebSocket 离线拉取）
    """
    async with db_manager.get_session() as session:
        # 1. 私聊会话：最近有消息交互的好友
        # 获取用户发送或接收的最新消息
        sent_messages = await session.execute(
            select(ChatMessage).where(
                ChatMessage.sender_id == user_id,
                ChatMessage.receiver_type == "user",
            ).order_by(desc(ChatMessage.created_at))
        )
        received_messages = await session.execute(
            select(ChatMessage).where(
                ChatMessage.receiver_id == user_id,
                ChatMessage.receiver_type == "user",
                ChatMessage.sender_id != user_id,
            ).order_by(desc(ChatMessage.created_at))
        )

        # 2. 群聊会话：用户所在群
        groups_result = await session.execute(
            select(GroupMember).where(GroupMember.user_id == user_id)
        )
        group_ids = [gm.group_id for gm in groups_result.scalars().all()]
        groups = []
        if group_ids:
            groups_result = await session.execute(
                select(ChatGroup).where(ChatGroup.id.in_(group_ids))
            )
            groups = groups_result.scalars().all()

        # 合并为会话列表（简化版）
        conversations = []

        # 添加群聊
        for g in groups:
            # 获取群最后一条消息
            last_msg_result = await session.execute(
                select(ChatMessage).where(
                    ChatMessage.receiver_type == "group",
                    ChatMessage.receiver_id == g.id,
                ).order_by(desc(ChatMessage.created_at)).limit(1)
            )
            last_msg = last_msg_result.scalar_one_or_none()

            conversations.append({
                "id": g.id,
                "name": g.name,
                "avatar": g.avatar or "",
                "type": "group",
                "member_count": g.member_count,
                "last_message": {
                    "content": last_msg.content if last_msg else "",
                    "sender_id": last_msg.sender_id if last_msg else 0,
                    "created_at": last_msg.created_at.isoformat()
                        if last_msg and last_msg.created_at else None,
                } if last_msg else None,
            })

        return conversations


async def pull_friend_requests_for_user(user_id: int) -> dict:
    """
    拉取用户的好友申请列表（用于 WebSocket 离线拉取）
    """
    async with db_manager.get_session() as session:
        received = await session.execute(
            select(FriendRequest).where(
                FriendRequest.receiver_id == user_id
            ).order_by(desc(FriendRequest.created_at))
        )
        sent = await session.execute(
            select(FriendRequest).where(
                FriendRequest.sender_id == user_id
            ).order_by(desc(FriendRequest.created_at))
        )

        all_requests = list(received.scalars().all()) + list(sent.scalars().all())
        involved_ids = set()
        for req in all_requests:
            involved_ids.add(req.sender_id)
            involved_ids.add(req.receiver_id)

        users_map = {}
        if involved_ids:
            users_result = await session.execute(
                select(User).where(User.id.in_(involved_ids))
            )
            users_map = {u.id: u for u in users_result.scalars().all()}

        def map_request(req, is_received):
            sender_user = users_map.get(req.sender_id)
            return {
                "id": req.id,
                "sender_id": req.sender_id,
                "receiver_id": req.receiver_id,
                "message": req.message or "",
                "status": req.status,
                "is_received": is_received,
                "sender_username": sender_user.username if sender_user else "未知",
                "sender_nickname": sender_user.nickname or "" if sender_user else "",
                "sender_avatar": sender_user.avatar or "" if sender_user else "",
                "created_at": req.created_at.isoformat() if req.created_at else None,
            }

        received_list = [
            map_request(r, True) for r in all_requests if r.receiver_id == user_id
        ]
        sent_list = [
            map_request(r, False) for r in all_requests if r.sender_id == user_id
        ]

        return {
            "received": received_list,
            "sent": sent_list,
        }