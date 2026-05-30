"""智能聊天 IM 模块 - 仿微信即时通信子系统"""
import os
import hashlib
import uuid
import urllib.parse
import aiofiles
from pathlib import Path
from fastapi import APIRouter, Depends, Query, UploadFile, File as FastAPIFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, desc, or_, and_, func, union
from typing import Optional, List
from database.engine import db_manager
from database.models import (
    User, Friend, FriendRequest, ChatGroup, GroupMember, 
    ChatMessage, ChatServer, File as FileModel, MessageRead, Worker,
    Job, ApiKey, Tool
)
from middleware.auth_middleware import get_current_user, get_admin_user
from utils.helpers import success_response, AppException, logger
from config import settings
from utils.db_utils import fetch_paginated

import json

router = APIRouter(prefix="/api/im", tags=["智能聊天"])

# ===== 请求模型 =====

class FriendRequestCreate(BaseModel):
    receiver_id: int
    message: str = ""

class FriendRequestHandle(BaseModel):
    request_id: int
    action: str  # accept / reject

class FriendRemarkUpdate(BaseModel):
    friend_id: int
    remark: str

class GroupCreate(BaseModel):
    name: str
    member_ids: List[int] = []

class GroupUpdate(BaseModel):
    name: Optional[str] = None
    announcement: Optional[str] = None

class GroupMemberAdd(BaseModel):
    user_ids: List[int]

class MessageSend(BaseModel):
    receiver_id: int
    receiver_type: str  # user / group
    type: str = "text"
    content: str = ""
    mentions: List[int] = []  # 被@的用户ID列表
    file_id: Optional[int] = None
    reply_to: Optional[int] = None

class SearchUserRequest(BaseModel):
    keyword: str

class MessagesRead(BaseModel):
    receiver_type: str
    receiver_id: int
    last_read_msg_id: int

# ===== 好友管理 =====

@router.get("/friends")
async def list_friends(q: str = "", user: User = Depends(get_current_user)):
    """获取好友列表, q 用于搜索用户名"""
    async with db_manager.get_session() as session:
        query = select(Friend).where(Friend.user_id == user.id)
        result = await session.execute(query)
        friends = result.scalars().all()
        
        friend_ids = [f.friend_id for f in friends]
        if not friend_ids:
            return success_response(data=[])
        
        user_query = select(User).where(User.id.in_(friend_ids))
        if q:
            user_query = user_query.where(User.username.ilike(f"%{q}%"))
        user_result = await session.execute(user_query)
        users_map = {u.id: u for u in user_result.scalars().all()}
        
        friend_map = {f.friend_id: f for f in friends}
        
        data = []
        for fid in friend_ids:
            if fid in users_map:
                u = users_map[fid]
                f = friend_map[fid]
                data.append({
                    "id": fid,
                    "username": u.username,
                    "nickname": u.nickname,
                    "avatar": u.avatar,
                    "remark": f.remark or "",
                    "is_blocked": f.is_blocked,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                })
        
        return success_response(data=data)

@router.post("/friends/search")
async def search_users(req: SearchUserRequest, user: User = Depends(get_current_user)):
    """搜索用户（用于添加好友）"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(User).where(
                User.username.ilike(f"%{req.keyword}%"),
                User.id != user.id,
                User.status == "active"
            ).limit(20)
        )
        users = result.scalars().all()
        return success_response(data=[{
            "id": u.id, "username": u.username,
            "nickname": u.nickname, "avatar": u.avatar,
        } for u in users])

@router.post("/friend-requests")
async def send_friend_request(req: FriendRequestCreate, user: User = Depends(get_current_user)):
    """发送好友申请"""
    if req.receiver_id == user.id:
        raise AppException("不能添加自己为好友", status_code=400)
    
    async with db_manager.get_session() as session:
        # 检查是否已是好友
        exist = await session.execute(
            select(Friend).where(
                or_(
                    and_(Friend.user_id == user.id, Friend.friend_id == req.receiver_id),
                    and_(Friend.user_id == req.receiver_id, Friend.friend_id == user.id),
                )
            )
        )
        if exist.scalars().first():
            raise AppException("已经是好友了", status_code=409)
        
        # 检查是否已有待处理的申请
        pending = await session.execute(
            select(FriendRequest).where(
                FriendRequest.sender_id == user.id,
                FriendRequest.receiver_id == req.receiver_id,
                FriendRequest.status == "pending"
            )
        )
        if pending.scalar_one_or_none():
            raise AppException("已发送过好友申请，请等待回复", status_code=409)
        
        fr = FriendRequest(
            sender_id=user.id,
            receiver_id=req.receiver_id,
            message=req.message,
        )
        session.add(fr)
        await session.commit()
        await session.refresh(fr)

        return success_response(data={"id": fr.id}, message="好友申请已发送")

@router.get("/friend-requests")
async def list_friend_requests(user: User = Depends(get_current_user)):
    """获取好友申请列表（收到的和发出的）"""
    async with db_manager.get_session() as session:
        received = await session.execute(
            select(FriendRequest).where(
                FriendRequest.receiver_id == user.id
            ).order_by(desc(FriendRequest.created_at))
        )
        sent = await session.execute(
            select(FriendRequest).where(
                FriendRequest.sender_id == user.id
            ).order_by(desc(FriendRequest.created_at))
        )
        
        # 收集所有涉及的 user_id
        all_requests = list(received.scalars().all()) + list(sent.scalars().all())
        involved_ids = set()
        for req in all_requests:
            involved_ids.add(req.sender_id)
            involved_ids.add(req.receiver_id)
        
        # 批量查询用户信息
        users_map = {}
        if involved_ids:
            users_result = await session.execute(
                select(User).where(User.id.in_(involved_ids))
            )
            users_map = {u.id: u for u in users_result.scalars().all()}
        
        def map_request(req, is_received):
            other_id = req.sender_id if is_received else req.receiver_id
            other_user = users_map.get(other_id)
            sender_user = users_map.get(req.sender_id)
            receiver_user = users_map.get(req.receiver_id)
            return {
                "id": req.id,
                "sender_id": req.sender_id,
                "receiver_id": req.receiver_id,
                "other_id": other_id,
                "message": req.message or "",
                "status": req.status,
                "is_received": is_received,
                # 申请人信息（双方都需要）
                "sender_username": sender_user.username if sender_user else "未知",
                "sender_nickname": sender_user.nickname or "" if sender_user else "",
                "sender_avatar": sender_user.avatar or "" if sender_user else "",
                "receiver_username": receiver_user.username if receiver_user else "未知",
                "receiver_nickname": receiver_user.nickname or "" if receiver_user else "",
                "receiver_avatar": receiver_user.avatar or "" if receiver_user else "",
                "other_username": other_user.username if other_user else "未知",
                "other_nickname": other_user.nickname or "" if other_user else "",
                "other_avatar": other_user.avatar or "" if other_user else "",
                "created_at": req.created_at.isoformat() if req.created_at else None,
            }
        
        received_list = [map_request(r, True) for r in all_requests if r.receiver_id == user.id]
        sent_list = [map_request(r, False) for r in all_requests if r.sender_id == user.id]
        
        return success_response(data={
            "received": received_list,
            "sent": sent_list,
        })

@router.post("/friend-requests/handle")
async def handle_friend_request(req: FriendRequestHandle, user: User = Depends(get_current_user)):
    """处理好友申请（接受/拒绝）"""
    if req.action not in ("accept", "reject"):
        raise AppException("无效的操作", status_code=400)
    
    async with db_manager.get_session() as session:
        fr = await session.get(FriendRequest, req.request_id)
        if not fr:
            raise AppException("申请不存在", status_code=404)
        if fr.receiver_id != user.id:
            raise AppException("无权处理此申请", status_code=403)
        if fr.status != "pending":
            raise AppException("申请已处理", status_code=400)
        
        fr.status = "accepted" if req.action == "accept" else "rejected"
        
        if req.action == "accept":
            # 建立双向好友关系
            f1 = Friend(user_id=fr.sender_id, friend_id=fr.receiver_id)
            f2 = Friend(user_id=fr.receiver_id, friend_id=fr.sender_id)
            session.add_all([f1, f2])
        
        await session.commit()

        return success_response(message="好友申请已{}".format("接受" if req.action == "accept" else "拒绝"))

@router.put("/friends/remark")
async def update_friend_remark(req: FriendRemarkUpdate, user: User = Depends(get_current_user)):
    """修改好友备注"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Friend).where(
                Friend.user_id == user.id,
                Friend.friend_id == req.friend_id
            )
        )
        friend = result.scalar_one_or_none()
        if not friend:
            raise AppException("好友关系不存在", status_code=404)
        friend.remark = req.remark
        await session.commit()
        return success_response(message="备注已更新")

@router.delete("/friends/{friend_id}")
async def remove_friend(friend_id: int, user: User = Depends(get_current_user)):
    """删除好友"""
    async with db_manager.get_session() as session:
        # 查询双向好友关系
        result = await session.execute(
            select(Friend).where(
                or_(
                    and_(Friend.user_id == user.id, Friend.friend_id == friend_id),
                    and_(Friend.user_id == friend_id, Friend.friend_id == user.id),
                )
            )
        )
        friends_to_delete = result.scalars().all()
        if not friends_to_delete:
            raise AppException("好友关系不存在", status_code=404)
        
        for f in friends_to_delete:
            await session.delete(f)
        
        await session.commit()
        return success_response(message="好友已删除")

# ===== 群组管理 =====

@router.get("/groups")
async def list_groups(user: User = Depends(get_current_user)):
    """获取我的群组列表"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(GroupMember).where(GroupMember.user_id == user.id)
        )
        memberships = result.scalars().all()
        group_ids = [m.group_id for m in memberships]
        
        if not group_ids:
            return success_response(data=[])
        
        groups_result = await session.execute(
            select(ChatGroup).where(ChatGroup.id.in_(group_ids))
        )
        groups = groups_result.scalars().all()
        
        return success_response(data=[{
            "id": g.id, "name": g.name,
            "avatar": g.avatar or "", "announcement": g.announcement or "",
            "member_count": g.member_count,
            "owner_id": g.owner_id,
            "status": g.status,
            "created_at": g.created_at.isoformat() if g.created_at else None,
        } for g in groups])

@router.post("/groups")
async def create_group(req: GroupCreate, user: User = Depends(get_current_user)):
    """创建群组"""
    if not req.name.strip():
        raise AppException("群名称不能为空", status_code=400)
    
    async with db_manager.get_session() as session:
        group = ChatGroup(
            name=req.name, owner_id=user.id,
            member_count=1 + len(req.member_ids)
        )
        session.add(group)
        await session.flush()
        
        # 添加群主
        owner_member = GroupMember(group_id=group.id, user_id=user.id, role="owner")
        session.add(owner_member)
        
        # 添加成员
        for uid in req.member_ids:
            if uid != user.id:
                member = GroupMember(group_id=group.id, user_id=uid, role="member")
                session.add(member)
        
        await session.commit()
        await session.refresh(group)
        return success_response(data={"id": group.id}, message="群组创建成功")

@router.get("/groups/{group_id}/members")
async def list_group_members(group_id: int, user: User = Depends(get_current_user)):
    """获取群成员的简要列表（供@弹出选择）"""
    async with db_manager.get_session() as session:
        # 检查是否是成员
        membership = await session.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user.id
            )
        )
        if not membership.scalar_one_or_none():
            raise AppException("你不是群成员", status_code=403)
        
        members_result = await session.execute(
            select(GroupMember).where(GroupMember.group_id == group_id)
        )
        members = members_result.scalars().all()
        member_user_ids = [m.user_id for m in members]
        
        users_result = await session.execute(
            select(User).where(User.id.in_(member_user_ids))
        )
        users_map = {u.id: u for u in users_result.scalars().all()}
        
        # 获取数字员工信息（用于展示员工名称而非用户名）
        worker_result = await session.execute(
            select(Worker).where(
                Worker.enabled == 1,
                Worker.user_id.in_(member_user_ids),
            )
        )
        worker_map = {}
        for w in worker_result.scalars().all():
            if w.user_id:
                worker_map[w.user_id] = w
        
        members_data = []
        for m in members:
            u = users_map.get(m.user_id)
            if not u:
                continue
            w = worker_map.get(m.user_id)
            display_name = w.name if w else (u.nickname or u.username)
            members_data.append({
                "user_id": m.user_id,
                "username": u.username,
                "nickname": u.nickname,
                "display_name": display_name,
                "avatar": u.avatar or "",
                "role": m.role,
                "is_worker": w is not None,
                "worker_icon": w.icon if w else "",
            })
        
        return success_response(data=members_data)

@router.get("/groups/{group_id}")
async def get_group_detail(group_id: int, user: User = Depends(get_current_user)):
    """获取群组详情"""
    async with db_manager.get_session() as session:
        group = await session.get(ChatGroup, group_id)
        if not group:
            raise AppException("群组不存在", status_code=404)
        
        # 检查是否成员
        membership = await session.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user.id
            )
        )
        if not membership.scalar_one_or_none():
            raise AppException("你不是群成员", status_code=403)
        
        # 获取成员列表
        members_result = await session.execute(
            select(GroupMember).where(GroupMember.group_id == group_id)
        )
        members = members_result.scalars().all()
        member_user_ids = [m.user_id for m in members]
        
        users_result = await session.execute(
            select(User).where(User.id.in_(member_user_ids))
        )
        users_map = {u.id: u for u in users_result.scalars().all()}
        
        return success_response(data={
            "id": group.id, "name": group.name,
            "avatar": group.avatar or "",
            "announcement": group.announcement or "",
            "member_count": group.member_count,
            "owner_id": group.owner_id,
            "status": group.status,
            "created_at": group.created_at.isoformat() if group.created_at else None,
            "members": [{
                "user_id": m.user_id,
                "username": users_map[m.user_id].username if m.user_id in users_map else "未知",
                "nickname": users_map[m.user_id].nickname if m.user_id in users_map else "",
                "avatar": users_map[m.user_id].avatar if m.user_id in users_map else "",
                "role": m.role,
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            } for m in members],
        })

@router.put("/groups/{group_id}")
async def update_group(group_id: int, req: GroupUpdate, user: User = Depends(get_current_user)):
    """更新群信息（群主/管理员）"""
    async with db_manager.get_session() as session:
        group = await session.get(ChatGroup, group_id)
        if not group:
            raise AppException("群组不存在", status_code=404)
        
        # 检查权限
        membership = await session.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user.id,
                GroupMember.role.in_(["owner", "admin"])
            )
        )
        if not membership.scalar_one_or_none():
            raise AppException("只有群主或管理员才能修改群信息", status_code=403)
        
        if req.name is not None:
            group.name = req.name
        if req.announcement is not None:
            group.announcement = req.announcement
        
        await session.commit()
        return success_response(message="群信息已更新")

@router.post("/groups/{group_id}/members")
async def add_group_members(group_id: int, req: GroupMemberAdd, user: User = Depends(get_current_user)):
    """添加群成员"""
    async with db_manager.get_session() as session:
        group = await session.get(ChatGroup, group_id)
        if not group:
            raise AppException("群组不存在", status_code=404)
        
        # 检查权限
        membership = await session.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user.id,
                GroupMember.role.in_(["owner", "admin"])
            )
        )
        if not membership.scalar_one_or_none():
            raise AppException("只有群主或管理员才能添加成员", status_code=403)
        
        added = 0
        for uid in req.user_ids:
            existing = await session.execute(
                select(GroupMember).where(
                    GroupMember.group_id == group_id,
                    GroupMember.user_id == uid
                )
            )
            if not existing.scalar_one_or_none():
                member = GroupMember(group_id=group_id, user_id=uid, role="member")
                session.add(member)
                added += 1
        
        group.member_count += added
        await session.commit()
        return success_response(message=f"已添加{added}名成员")

@router.delete("/groups/{group_id}/members/{member_id}")
async def remove_group_member(group_id: int, member_id: int, user: User = Depends(get_current_user)):
    """移除群成员"""
    async with db_manager.get_session() as session:
        group = await session.get(ChatGroup, group_id)
        if not group:
            raise AppException("群组不存在", status_code=404)
        
        # 检查权限
        membership = await session.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user.id,
                GroupMember.role.in_(["owner", "admin"])
            )
        )
        is_admin = membership.scalar_one_or_none()
        
        # 自己退群不需要权限
        if member_id != user.id and not is_admin:
            raise AppException("只有群主或管理员才能移除成员", status_code=403)
        
        if member_id == group.owner_id:
            raise AppException("不能移除群主", status_code=400)
        
        member = await session.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == member_id
            )
        )
        member_obj = member.scalar_one_or_none()
        if member_obj:
            await session.delete(member_obj)
            group.member_count = max(0, group.member_count - 1)
            await session.commit()
        
        return success_response(message="成员已移除")

@router.delete("/groups/{group_id}")
async def disband_group(group_id: int, user: User = Depends(get_current_user)):
    """解散群组（仅群主/管理员）"""
    async with db_manager.get_session() as session:
        group = await session.get(ChatGroup, group_id)
        if not group:
            raise AppException("群组不存在", status_code=404)
        
        # 群主或管理员可解散
        is_admin_user = user.role == "admin"
        if group.owner_id != user.id and not is_admin_user:
            raise AppException("只有群主或管理员才能解散群组", status_code=403)
        
        # 删除所有群聊消息
        from sqlalchemy import delete as sa_delete
        await session.execute(
            sa_delete(ChatMessage).where(
                ChatMessage.receiver_type == "group",
                ChatMessage.receiver_id == group_id
            )
        )
        # 删除所有群成员记录
        await session.execute(sa_delete(GroupMember).where(GroupMember.group_id == group_id))
        # 删除群组已读记录
        await session.execute(
            sa_delete(MessageRead).where(
                MessageRead.receiver_type == "group",
                MessageRead.receiver_id == group_id
            )
        )
        # 删除群组本身
        await session.delete(group)
        
        # 记录操作日志
        try:
            from database.models import SystemLog
            log = SystemLog(
                user_id=user.id,
                action="group_disband",
                target=f"group:{group_id}",
                detail=f'{{"group_name":"{group.name}","by_admin":{is_admin_user}}}',
            )
            session.add(log)
        except Exception:
            pass
        
        await session.commit()
        return success_response(message="群组已解散")

@router.get("/workers/chat")
async def list_chat_workers(user: User = Depends(get_current_user)):
    """获取可用于聊天的数字员工列表"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(Worker).where(
                Worker.enabled == 1,
                Worker.user_id != None  # 有对应user_id的才能参与聊天
            ).order_by(Worker.sort_order)
        )
        workers = result.scalars().all()
        worker_user_ids = [w.user_id for w in workers]
        
        if not worker_user_ids:
            return success_response(data=[])
        
        users_result = await session.execute(
            select(User).where(User.id.in_(worker_user_ids))
        )
        users_map = {u.id: u for u in users_result.scalars().all()}
        
        return success_response(data=[{
            "id": w.id,
            "user_id": w.user_id,
            "name": w.name,
            "icon": w.icon,
            "description": w.description,
            "username": users_map[w.user_id].username if w.user_id in users_map else w.name,
            "nickname": users_map[w.user_id].nickname if w.user_id in users_map else w.name,
            "avatar": users_map[w.user_id].avatar if w.user_id in users_map else "",
        } for w in workers])

# ===== 聊天消息 =====

@router.get("/messages")
async def get_messages(
    receiver_type: str,
    receiver_id: int,
    before_id: Optional[int] = None,
    limit: int = 50,
    user: User = Depends(get_current_user),
):
    """获取聊天消息（私聊/群聊）"""
    async with db_manager.get_session() as session:
        # 权限校验：私聊需要是好友
        if receiver_type == "user":
            is_friend = await session.execute(
                select(Friend).where(
                    or_(
                        and_(Friend.user_id == user.id, Friend.friend_id == receiver_id),
                        and_(Friend.user_id == receiver_id, Friend.friend_id == user.id),
                    )
                )
            )
            if not is_friend.scalars().first() and receiver_id != user.id:
                pass  # 允许查看自己的消息
        elif receiver_type == "group":
            is_member = await session.execute(
                select(GroupMember).where(
                    GroupMember.group_id == receiver_id,
                    GroupMember.user_id == user.id
                )
            )
            if not is_member.scalar_one_or_none():
                raise AppException("你不是群成员", status_code=403)
        
        # 【修复】私聊消息查询改为双向：用户发出的消息 AND 用户收到的消息
        # 【新增】增加 receiver_type 过滤，防止群聊消息混入私聊（之前 missing 此条件导致群聊receiver_id=1的消息被错误返回）
        if receiver_type == "user":
            query = select(ChatMessage).where(
                ChatMessage.receiver_type == "user",
                or_(
                    and_(ChatMessage.sender_id == user.id, ChatMessage.receiver_id == receiver_id),
                    and_(ChatMessage.sender_id == receiver_id, ChatMessage.receiver_id == user.id),
                )
            )
        else:
            # 群聊：按 receiver_id 和 receiver_type 查询
            query = select(ChatMessage).where(
                ChatMessage.receiver_type == receiver_type,
                ChatMessage.receiver_id == receiver_id
            )
        
        if before_id:
            query = query.where(ChatMessage.id < before_id)
        
        query = query.order_by(desc(ChatMessage.created_at)).limit(limit)
        
        result = await session.execute(query)
        messages = result.scalars().all()
        messages.reverse()  # 按时间正序返回
        
        # 获取发送者信息
        sender_ids = list(set(m.sender_id for m in messages))
        senders_result = await session.execute(
            select(User).where(User.id.in_(sender_ids))
        )
        senders_map = {u.id: u for u in senders_result.scalars().all()}
        
        # 获取文件信息（包含 file_id 的消息需要额外信息用于前端展示）
        file_ids = list(set(m.file_id for m in messages if m.file_id))
        files_map = {}
        if file_ids:
            files_result = await session.execute(
                select(FileModel).where(FileModel.id.in_(file_ids))
            )
            for f in files_result.scalars().all():
                files_map[f.id] = {
                    "id": f.id,
                    "file_name": f.file_name,
                    "file_size": f.file_size,
                    "mime_type": f.mime_type,
                    "md5_hash": f.md5_hash,
                }
        
        return success_response(data=[{
            "id": m.id,
            "sender_id": m.sender_id,
            "sender_username": senders_map[m.sender_id].username if m.sender_id in senders_map else "未知",
            "sender_nickname": senders_map[m.sender_id].nickname if m.sender_id in senders_map else "",
            "sender_avatar": senders_map[m.sender_id].avatar if m.sender_id in senders_map else "",
            "receiver_type": m.receiver_type,
            "receiver_id": m.receiver_id,
            "type": m.type,
            "content": m.content or "",
            "mentions": json.loads(m.mentions) if m.mentions else [],
            "file_id": m.file_id,
            "file_info": files_map.get(m.file_id) if m.file_id else None,  # 附带文件信息
            "reply_to": m.reply_to,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            # 天气效果：图片消息且文件名包含"天气卡片"时，从文件名提取天气效果
            "weather_effect": _detect_weather_effect_from_content(m.content or ""),
        } for m in messages])


def _detect_weather_effect_from_content(content: str) -> Optional[str]:
    """从消息内容中检测天气效果类型
    格式: "🌤 北京 天气|effect:sunny"
    """
    if not content:
        return None
    content = str(content)
    # 优先从 |effect: 标记中提取
    if "|effect:" in content:
        effect = content.split("|effect:")[-1].strip().split()[0].strip()
        if effect in ["sunny", "cloudy", "rainy", "snowy", "stormy", "foggy"]:
            return effect
    # fallback: 关键词匹配
    for effect in ["sunny", "cloudy", "rainy", "snowy", "stormy", "foggy"]:
        if effect in content:
            return effect
    return None


async def _execute_tool_call(
    tool_name: str,
    arguments: dict,
    session=None,
    msg_id: int = 0,
    receiver_id: int = 0,
    worker_user_id: int = 0,
    worker_name: str = "",
    worker_username: str = "",
) -> str:
    """执行工具调用，返回工具执行结果文本"""
    try:
        if tool_name == "get_weather":
            from tools.weather_tools import get_weather
            city_name = arguments.get("city_name", "")
            if not city_name:
                return json.dumps({"success": False, "error": "缺少城市名称参数"})
            result = await get_weather(city_name)
            # 工具调用失败时，明确提示 LLM 不要编造数据
            if not result.get("success"):
                return json.dumps({
                    "success": False,
                    "error": result.get("error", "天气查询失败"),
                    "hint": "天气服务查询失败，请直接告知用户无法获取天气数据，不要编造或推测具体的天气信息。"
                }, ensure_ascii=False)
            return json.dumps(result, ensure_ascii=False)
        elif tool_name == "send_weather_card":
            """AI主动调用的工具：根据天气数据生成天气卡片图片并发送到群聊"""
            if not session or not receiver_id:
                return json.dumps({"success": False, "error": "缺少必要的会话上下文"})
            
            # 收集参数
            city = arguments.get("city", "")
            temp_c = arguments.get("temp_c", "?")
            feelslike_c = arguments.get("feelslike_c", "?")
            weather_desc = arguments.get("weather_desc", "🌤️ 未知")
            weather_effect = arguments.get("weather_effect", "cloudy")
            humidity = arguments.get("humidity", "?")
            wind_kph = arguments.get("wind_kph", "?")
            wind_dir = arguments.get("wind_dir", "?")
            
            weather_data = {
                "city": city,
                "temp_c": temp_c,
                "feelslike_c": feelslike_c,
                "weather_desc": weather_desc,
                "weather_effect": weather_effect,
                "humidity": humidity,
                "wind_kph": wind_kph,
                "wind_dir": wind_dir,
            }
            
            try:
                from tools.weather_tools import send_weather_card
                card_bytes = await send_weather_card(weather_data)
                
                if not card_bytes or len(card_bytes) < 100:
                    return json.dumps({"success": False, "error": "天气卡片生成失败"})
                
                md5_hash = hashlib.md5(card_bytes).hexdigest()
                
                # 检查是否已有相同图片
                existing = await session.execute(
                    select(FileModel).where(FileModel.md5_hash == md5_hash).limit(1)
                )
                existing_file = existing.scalar_one_or_none()
                
                if existing_file:
                    file_id = existing_file.id
                else:
                    file_ext = ".png"
                    stored_name = f"{uuid.uuid4().hex}{file_ext}"
                    file_path = Path(settings.SQLITE_PATH).parent / "uploads" / stored_name
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    async with aiofiles.open(file_path, "wb") as f:
                        await f.write(card_bytes)
                    
                    file_record = FileModel(
                        file_name=f"天气卡片_{city}.png",
                        file_path=str(file_path),
                        file_size=len(card_bytes),
                        md5_hash=md5_hash,
                        mime_type="image/png",
                        uploader_id=worker_user_id,
                    )
                    session.add(file_record)
                    await session.flush()
                    await session.refresh(file_record)
                    file_id = file_record.id
                
                # 创建图片消息（content中携带effect标记，供前端轮询检测天气效果）
                weather_content = f"🌤 {city} 天气|effect:{weather_effect}"
                img_msg = ChatMessage(
                    sender_id=worker_user_id,
                    receiver_id=receiver_id,
                    receiver_type="group",
                    type="image",
                    content=weather_content,
                    file_id=file_id,
                )
                session.add(img_msg)
                await session.flush()
                await session.refresh(img_msg)
                
                logger.info(f"AI调用send_weather_card成功: {city} → {weather_effect}, file_id={file_id}")
                return json.dumps({
                    "success": True,
                    "file_id": file_id,
                    "message": f"天气卡片已发送到群聊，包含{city}的天气信息"
                }, ensure_ascii=False)
            except Exception as e:
                logger.error(f"send_weather_card执行失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return json.dumps({"success": False, "error": f"天气卡片生成失败: {str(e)}"})
        elif tool_name == "execute_python":
            from tools.python_tools import execute_python
            code = arguments.get("code", "")
            result = execute_python(code)
            return json.dumps(result, ensure_ascii=False)
        elif tool_name == "clean_html_content":
            from tools.cleaning_tools import clean_html_content
            result = clean_html_content(**arguments)
            return json.dumps(result, ensure_ascii=False)
        elif tool_name == "extract_structural_info":
            from tools.cleaning_tools import extract_structural_info
            result = await extract_structural_info(**arguments)
            return json.dumps(result, ensure_ascii=False)
        elif tool_name == "parse_json_data":
            from tools.cleaning_tools import parse_json_data
            result = parse_json_data(**arguments)
            return json.dumps(result, ensure_ascii=False)
        elif tool_name == "validate_result":
            from tools.cleaning_tools import validate_result
            result = validate_result(**arguments)
            return json.dumps(result, ensure_ascii=False)
        elif tool_name == "extract_domain":
            from tools.cleaning_tools import extract_domain
            result = extract_domain(**arguments)
            return json.dumps(result, ensure_ascii=False)
        elif tool_name == "classify_sentiment":
            from tools.sentiment_tools import classify_sentiment
            result = await classify_sentiment(**arguments)
            return json.dumps(result, ensure_ascii=False)
        elif tool_name == "extract_keywords":
            from tools.sentiment_tools import extract_keywords
            result = await extract_keywords(**arguments)
            return json.dumps(result, ensure_ascii=False)
        elif tool_name == "detect_events":
            from tools.sentiment_tools import detect_events
            result = await detect_events(**arguments)
            return json.dumps(result, ensure_ascii=False)
        elif tool_name == "extract_locations":
            from tools.sentiment_tools import extract_locations
            result = await extract_locations(**arguments)
            return json.dumps(result, ensure_ascii=False)
        elif tool_name == "generate_summary":
            from tools.sentiment_tools import generate_summary
            result = await generate_summary(**arguments)
            return json.dumps(result, ensure_ascii=False)
        else:
            logger.warning(f"未知工具调用: {tool_name}")
            return json.dumps({"success": False, "error": f"未知工具: {tool_name}"})
    except Exception as e:
        logger.error(f"工具 {tool_name} 执行失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return json.dumps({"success": False, "error": f"工具执行失败: {str(e)}"})


async def _call_llm_with_tools(
    llm_messages: list[dict],
    tools_schemas: list[dict],
    api_key_override=None,
    purpose: str = "chat",
    max_tool_rounds: int = 5,
    # send_weather_card 工具所需的上下文
    _session=None,
    _receiver_id: int = 0,
    _worker_user_id: int = 0,
    _worker_name: str = "",
    _worker_username: str = "",
) -> tuple[str, int, str]:
    """
    调用 LLM 并支持多轮工具调用（Function Calling）
    返回 (final_content, tokens_used, model_name)
    """
    from services.llm_service import call_llm
    from openai import AsyncOpenAI
    from services.llm_service import build_openai_client, select_api_key
    
    api_key = api_key_override or await select_api_key(purpose)
    client = build_openai_client(api_key)
    
    # 构建请求参数
    from services.llm_service import build_headers_from_key
    kwargs = build_headers_from_key(api_key)
    kwargs["messages"] = llm_messages
    
    if tools_schemas:
        kwargs["tools"] = tools_schemas
        kwargs["tool_choice"] = "auto"
    
    total_tokens = 0
    model_name = kwargs["model"]
    current_messages = list(llm_messages)
    
    for round_idx in range(max_tool_rounds + 1):
        try:
            resp = await client.chat.completions.create(**kwargs)
            choice = resp.choices[0]
            
            if resp.usage:
                total_tokens += resp.usage.total_tokens or 0
            model_name = resp.model or model_name
            
            # 检查是否有工具调用请求
            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                assistant_msg = {
                    "role": "assistant",
                    "content": choice.message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        }
                        for tc in choice.message.tool_calls
                    ]
                }
                current_messages.append(assistant_msg)
                
                # 逐个执行工具
                for tc in choice.message.tool_calls:
                    tool_name = tc.function.name
                    try:
                        arguments = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    logger.info(f"工具调用 round {round_idx + 1}: {tool_name}({arguments})")
                    # 为send_weather_card工具传递session等上下文
                    tool_result = await _execute_tool_call(
                        tool_name, arguments,
                        session=_session,
                        receiver_id=_receiver_id,
                        worker_user_id=_worker_user_id,
                        worker_name=_worker_name,
                        worker_username=_worker_username,
                    )
                    
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result,
                    })
                
                # 更新 kwargs 中的 messages 继续下一轮
                kwargs["messages"] = current_messages
                continue
            
            # 没有工具调用，返回最终回复
            content = choice.message.content or ""
            return content, total_tokens, model_name
            
        except Exception as e:
            logger.exception(f"LLM 调用失败 (round {round_idx}): {e}")
            return f"抱歉，AI 服务调用失败: {str(e)}", total_tokens, model_name
    
    # 超过最大轮数，返回最后一条消息
    return "抱歉，工具调用次数过多，请简化您的请求。", total_tokens, model_name


async def _trigger_digital_employee_reply(msg_id: int, receiver_id: int, mentions: list[int], content: str, sender_id: int, sender_name: str):
    """
    触发数字员工回复逻辑（后台异步任务，自行创建session）
    检查消息中的 mentions，若有数字员工被@，则构建上下文并调用 LLM 回复
    支持 Function Calling 工具调用（如 get_weather）
    """
    try:
        # 只处理群聊的@消息
        if not mentions or not receiver_id:
            return

        async with db_manager.get_session() as session:
            # 查询被@的用户中哪些是数字员工（Worker.user_id）
            worker_result = await session.execute(
                select(Worker).where(
                    Worker.enabled == 1,
                    Worker.user_id.in_(mentions),
                    Worker.user_id != None,
                )
            )
            workers = worker_result.scalars().all()
            if not workers:
                return

            for worker in workers:
                try:
                    # 获取该worker关联的user和job信息
                    worker_user = await session.get(User, worker.user_id)
                    if not worker_user:
                        continue
                    
                    job = await session.get(Job, worker.job_id)
                    
                    # 构建上下文：获取该群中最近100条与该数字员工相关的消息
                    # 包括：用户@该数字员工的消息 + 该数字员工自己回复的消息
                    context_msgs_result = await session.execute(
                        select(ChatMessage).where(
                            ChatMessage.receiver_type == "group",
                            ChatMessage.receiver_id == receiver_id,
                            or_(
                                # 条件1：该数字员工自己发送的消息（回复）
                                ChatMessage.sender_id == worker.user_id,
                                # 条件2：其他用户@该数字员工的消息
                                and_(
                                    ChatMessage.sender_id != worker.user_id,
                                    ChatMessage.mentions.like(f'%{worker.user_id}%'),
                                )
                            )
                        ).order_by(desc(ChatMessage.created_at)).limit(100)
                    )
                    context_msgs = context_msgs_result.scalars().all()
                    context_msgs.reverse()  # 按时间正序

                    # 构建LLM消息
                    system_prompt = worker.system_prompt or (job.prompt_template if job else "")
                    if not system_prompt:
                        system_prompt = f"你是{worker.name}，请专业地回答用户问题。"

                    # 替换模板中的 {user_query} (如果存在)
                    system_prompt = system_prompt.replace("{user_query}", content)
                    
                    llm_messages = [{"role": "system", "content": system_prompt}]

                    # 判断是否是天气小助手（通过job.code识别）
                    # 天气小助手：为防止历史消息中|effect:格式标记污染LLM输出，跳过历史上下文，只传当前提问
                    # 其他数字员工：保留原有逻辑，传入历史上下文
                    is_weather_worker = (job is not None and job.code == "weather_assistant")

                    if is_weather_worker:
                        # 天气助手专用：跳过所有历史上下文，只传入本次用户提问
                        llm_messages.append({"role": "user", "content": f"{sender_name}: {content}"})
                    else:
                        # 其他数字员工：保留历史上下文，按时间顺序添加上下文消息
                        for ctx_msg in context_msgs:
                            if ctx_msg.id >= msg_id:
                                continue  # 不包括当前消息本身和之后的消息
                            ctx_sender = await session.get(User, ctx_msg.sender_id)
                            ctx_sender_name = ctx_sender.nickname or ctx_sender.username if ctx_sender else "未知"
                            if ctx_msg.sender_id == worker.user_id:
                                role = "assistant"
                                msg_content = ctx_msg.content or ""
                            else:
                                role = "user"
                                msg_content = f"{ctx_sender_name}: {ctx_msg.content}" if ctx_msg.content else ""

                            if msg_content:
                                llm_messages.append({"role": role, "content": msg_content})

                        # 添加当前用户消息
                        llm_messages.append({"role": "user", "content": f"{sender_name}: {content}"})

                    # 获取API Key (使用worker绑定的key或其他可用key)
                    api_key = None
                    if worker.api_key_id:
                        api_key = await session.get(ApiKey, worker.api_key_id)

                    # 获取该worker关联的job的工具列表（用于Function Calling）
                    tools_schemas = []
                    if job and job.tool_names:
                        try:
                            tool_names_list = json.loads(job.tool_names)
                            if tool_names_list:
                                tools_result = await session.execute(
                                    select(Tool).where(Tool.name.in_(tool_names_list))
                                )
                                for tool in tools_result.scalars().all():
                                    schema = json.loads(tool.function_schema)
                                    tools_schemas.append({
                                        "type": "function",
                                        "function": schema,
                                    })
                        except (json.JSONDecodeError, Exception) as e:
                            logger.warning(f"解析工具列表失败 (worker {worker.id}): {e}")

                    # 调用LLM（支持工具调用），传递session上下文供send_weather_card使用
                    reply_content, tokens_used, model_name = await _call_llm_with_tools(
                        llm_messages=llm_messages,
                        tools_schemas=tools_schemas,
                        api_key_override=api_key,
                        purpose="chat",
                        _session=session,
                        _receiver_id=receiver_id,
                        _worker_user_id=worker.user_id,
                        _worker_name=worker.name,
                        _worker_username=worker_user.username,
                    )

                    if not reply_content:
                        reply_content = "抱歉，我现在无法回答这个问题。"

                    # 天气特效信号：从LLM回复内容中检测天气效果关键字
                    weather_effect = None
                    for effect_word in ["sunny", "cloudy", "rainy", "snowy", "stormy", "foggy"]:
                        if effect_word in reply_content.lower():
                            weather_effect = effect_word
                            break

                    # 将AI文字回复作为群聊消息发送
                    reply_msg = ChatMessage(
                        sender_id=worker.user_id,
                        receiver_id=receiver_id,
                        receiver_type="group",
                        type="text",
                        content=reply_content,
                    )
                    session.add(reply_msg)
                    await session.commit()
                    await session.refresh(reply_msg)

                    # 获取群成员列表
                    members_result = await session.execute(
                        select(GroupMember).where(GroupMember.group_id == receiver_id)
                    )
                    members = members_result.scalars().all()
                    member_ids = [m.user_id for m in members]

                    # 记录token消耗
                    try:
                        from services.llm_service import record_token_usage
                        await record_token_usage(
                            user_id=sender_id,
                            tokens_used=tokens_used,
                            model_name=model_name,
                            purpose="chat",
                        )
                    except Exception as e:
                        logger.warning(f"Token记录异常: {e}")

                except Exception as e:
                    logger.error(f"数字员工 {worker.name}({worker.id}) 回复失败: {e}")
                    import traceback
                    logger.error(traceback.format_exc())

    except Exception as e:
        logger.error(f"数字员工触发回复逻辑异常: {e}")


@router.post("/messages")
async def send_message(req: MessageSend, user: User = Depends(get_current_user)):
    """发送聊天消息"""
    if not req.content.strip() and req.type == "text" and not req.file_id:
        raise AppException("消息内容不能为空", status_code=400)
    
    if req.receiver_type not in ("user", "group"):
        raise AppException("无效的接收类型", status_code=400)
    
    async with db_manager.get_session() as session:
        msg = ChatMessage(
            sender_id=user.id,
            receiver_id=req.receiver_id,
            receiver_type=req.receiver_type,
            type=req.type,
            content=req.content,
            mentions=json.dumps(req.mentions, ensure_ascii=False) if req.mentions else "[]",
            file_id=req.file_id,
            reply_to=req.reply_to,
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)

        # === 异步触发数字员工回复（有@数字员工时） ===
        if req.mentions and req.receiver_type == "group":
            import asyncio
            # 传入必要的id信息，让后台任务自行创建session，避免session已关闭导致查询失败
            asyncio.create_task(_trigger_digital_employee_reply(
                msg_id=msg.id,
                receiver_id=req.receiver_id,
                mentions=req.mentions,
                content=req.content,
                sender_id=user.id,
                sender_name=user.nickname or user.username,
            ))

        return success_response(data={
            "id": msg.id,
            "sender_id": msg.sender_id,
            "receiver_type": msg.receiver_type,
            "receiver_id": msg.receiver_id,
            "type": msg.type,
            "content": msg.content or "",
            "mentions": req.mentions,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }, message="消息已发送")

@router.get("/conversations")
async def get_conversations(user: User = Depends(get_current_user)):
    """获取会话列表（最近联系人/群组及其最后一条消息）"""
    async with db_manager.get_session() as session:
        # 查询所有涉及的消息
        # 1. 私聊：user 发送或接收的消息
        # 2. 群聊：user 所在群的消息
        sent = select(ChatMessage.receiver_id, ChatMessage.receiver_type,
                      func.max(ChatMessage.id).label("max_id")).where(
            ChatMessage.sender_id == user.id
        ).group_by(ChatMessage.receiver_id, ChatMessage.receiver_type).subquery()
        
        received = select(ChatMessage.sender_id.label("receiver_id"),
                          ChatMessage.receiver_type,
                          func.max(ChatMessage.id).label("max_id")).where(
            ChatMessage.receiver_type == "user",
            ChatMessage.receiver_id == user.id
        ).group_by(ChatMessage.sender_id).subquery()
        
        # 获取用户所在群组
        group_ids_sub = select(GroupMember.group_id).where(
            GroupMember.user_id == user.id
        ).subquery()
        
        group_msgs = select(ChatMessage.receiver_id.label("receiver_id"),
                            ChatMessage.receiver_type,
                            func.max(ChatMessage.id).label("max_id")).where(
            ChatMessage.receiver_type == "group",
            ChatMessage.receiver_id.in_(select(group_ids_sub.c.group_id))
        ).group_by(ChatMessage.receiver_id).subquery()
        
        # 合并
        union_query = union(
            select(sent.c.receiver_id, sent.c.receiver_type, sent.c.max_id),
            select(received.c.receiver_id, received.c.receiver_type, received.c.max_id),
            select(group_msgs.c.receiver_id, group_msgs.c.receiver_type, group_msgs.c.max_id)
        ).subquery()
        
        # 获取最后消息详情
        last_msgs = await session.execute(
            select(ChatMessage).where(
                ChatMessage.id.in_(select(union_query.c.max_id))
            )
        )
        last_msg_map = {}
        for msg in last_msgs.scalars().all():
            # 【修复】私聊会话 key 归一化：无论哪个方向，都用 user_{小ID}_{大ID}
            if msg.receiver_type == "user":
                # 找出当前用户和对方的 ID，排序后组成统一 key
                other_id = msg.sender_id if msg.sender_id != user.id else msg.receiver_id
                a, b = (user.id, other_id) if user.id < other_id else (other_id, user.id)
                key = f"user_{a}_{b}"
            else:
                key = f"{msg.receiver_type}_{msg.receiver_id}"
            if key not in last_msg_map or msg.id > last_msg_map[key].id:
                last_msg_map[key] = msg
        
        # 获取未读消息数
        unread_counts = {}
        read_results = await session.execute(
            select(MessageRead).where(MessageRead.user_id == user.id)
        )
        for read_rec in read_results.scalars().all():
            # 【修复】私聊 key 使用归一化格式，与 last_msg_map 保持一致
            if read_rec.receiver_type == "user":
                a, b = (user.id, read_rec.receiver_id) if user.id < read_rec.receiver_id else (read_rec.receiver_id, user.id)
                key = f"user_{a}_{b}"
                # 【修复】私聊未读数：需要查两个方向的消息
                # - 当前用户收到的（对方发给我的）：receiver_id=user.id, sender_id=对方
                # - 当前用户发出的（我发给对方的）：receiver_id=对方, sender_id=user.id(排除自己)
                count_result = await session.execute(
                    select(func.count(ChatMessage.id)).where(
                        ChatMessage.sender_id != user.id,
                        ChatMessage.id > read_rec.last_read_msg_id,
                        or_(
                            and_(ChatMessage.sender_id == read_rec.receiver_id, ChatMessage.receiver_id == user.id),
                            and_(ChatMessage.sender_id == user.id, ChatMessage.receiver_id == read_rec.receiver_id),
                        )
                    )
                )
            else:
                key = f"{read_rec.receiver_type}_{read_rec.receiver_id}"
                count_result = await session.execute(
                    select(func.count(ChatMessage.id)).where(
                        ChatMessage.receiver_type == read_rec.receiver_type,
                        ChatMessage.receiver_id == read_rec.receiver_id,
                        ChatMessage.id > read_rec.last_read_msg_id,
                        ChatMessage.sender_id != user.id
                    )
                )
            count = count_result.scalar() or 0
            # 【修复】私聊可能有左右两个方向的 unread 记录，合并到同一个 key
            if key in unread_counts:
                unread_counts[key] += count
            else:
                unread_counts[key] = count
        
        # 组装数据
        conversations = []
        for key, last_msg in last_msg_map.items():
            # 【修复】私聊：对方ID = 消息中"不是我"的那个ID；群聊：对方ID = receiver_id（群组ID）
            if last_msg.receiver_type == "group":
                other_id = last_msg.receiver_id
            else:
                other_id = last_msg.sender_id if last_msg.sender_id != user.id else last_msg.receiver_id
            other_type = last_msg.receiver_type
            
            if other_type == "user":
                # 获取对方信息
                other_user = await session.get(User, other_id)
                if not other_user:
                    continue
                title = other_user.nickname or other_user.username
                avatar = other_user.avatar or ""
            else:
                group = await session.get(ChatGroup, other_id)
                if not group:
                    continue
                title = group.name
                avatar = group.avatar or ""
            
            conversations.append({
                "id": other_id,
                "type": other_type,
                "title": title,
                "avatar": avatar or "",
                "last_message": {
                    "id": last_msg.id,
                    "sender_id": last_msg.sender_id,
                    "content": last_msg.content or f"[{last_msg.type}]",
                    "type": last_msg.type,
                    "created_at": last_msg.created_at.isoformat() if last_msg.created_at else None,
                },
                "unread_count": unread_counts.get(key, 0),
            })
        
        # 按最后消息时间排序
        conversations.sort(key=lambda c: c["last_message"]["created_at"], reverse=True)
        
        return success_response(data=conversations)

@router.post("/messages/read")
async def mark_messages_read(req: MessagesRead, user: User = Depends(get_current_user)):
    """标记消息已读"""
    async with db_manager.get_session() as session:
        existing = await session.execute(
            select(MessageRead).where(
                MessageRead.user_id == user.id,
                MessageRead.receiver_type == req.receiver_type,
                MessageRead.receiver_id == req.receiver_id
            )
        )
        read_rec = existing.scalar_one_or_none()
        if read_rec:
            if req.last_read_msg_id > read_rec.last_read_msg_id:
                read_rec.last_read_msg_id = req.last_read_msg_id
        else:
            read_rec = MessageRead(
                user_id=user.id,
                receiver_type=req.receiver_type,
                receiver_id=req.receiver_id,
                last_read_msg_id=req.last_read_msg_id,
            )
            session.add(read_rec)
        await session.commit()
        return success_response(message="已读")

# ===== 聊天服务器管理 =====

@router.get("/servers")
async def list_servers(user: User = Depends(get_current_user)):
    """获取聊天服务器列表"""
    async with db_manager.get_session() as session:
        result = await session.execute(
            select(ChatServer).where(
                ChatServer.enabled == 1
            ).order_by(ChatServer.priority)
        )
        servers = result.scalars().all()
        return success_response(data=[{
            "id": s.id, "name": s.name, "url": s.url,
            "status": s.status, "priority": s.priority,
        } for s in servers])

# ===== 文件上传与下载 =====

UPLOAD_DIR = Path(settings.SQLITE_PATH).parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/files/upload")
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    user: User = Depends(get_current_user),
):
    """
    上传文件
    - 支持所有类型文件
    - MD5 去重（相同内容不重复存储）
    - 返回 file_id 供发送消息时使用
    """
    # 读取文件内容
    content = await file.read()
    
    # 计算 MD5
    md5_hash = hashlib.md5(content).hexdigest()
    
    max_size = settings.MAX_FILE_SIZE
    if len(content) > max_size:
        raise AppException(f"文件大小超过限制 ({max_size // 1048576}MB)", status_code=413)
    
    async with db_manager.get_session() as session:
        # MD5 去重：检查是否已有相同内容的文件
        existing = await session.execute(
            select(FileModel).where(FileModel.md5_hash == md5_hash).limit(1)
        )
        existing_file = existing.scalar_one_or_none()
        if existing_file:
            # 文件已存在，复用记录
            return success_response(data={
                "id": existing_file.id,
                "file_name": existing_file.file_name,
                "file_size": existing_file.file_size,
                "mime_type": existing_file.mime_type,
                "md5_hash": md5_hash,
                "duplicate": True,
            }, message="文件已存在，复用已有记录")

        # 生成唯一文件名存储
        ext = Path(file.filename or "file").suffix if file.filename else ""
        stored_name = f"{uuid.uuid4().hex}{ext}"
        file_path = UPLOAD_DIR / stored_name
        
        # 保存到磁盘
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        
        # 创建数据库记录
        file_record = FileModel(
            file_name=file.filename or stored_name,
            file_path=str(file_path),
            file_size=len(content),
            md5_hash=md5_hash,
            mime_type=file.content_type or "application/octet-stream",
            uploader_id=user.id,
        )
        session.add(file_record)
        await session.commit()
        await session.refresh(file_record)
        
        logger.info(f"文件上传成功: id={file_record.id}, name={file.filename}, size={len(content)}, md5={md5_hash}")
        
        return success_response(data={
            "id": file_record.id,
            "file_name": file_record.file_name,
            "file_size": file_record.file_size,
            "mime_type": file_record.mime_type,
            "md5_hash": md5_hash,
            "duplicate": False,
        }, message="文件上传成功")


@router.get("/files/{file_id}")
async def get_file_info(file_id: int, user: User = Depends(get_current_user)):
    """获取文件信息"""
    async with db_manager.get_session() as session:
        file = await session.get(FileModel, file_id)
        if not file:
            raise AppException("文件不存在", status_code=404)
        
        return success_response(data={
            "id": file.id,
            "file_name": file.file_name,
            "file_size": file.file_size,
            "mime_type": file.mime_type,
            "md5_hash": file.md5_hash,
            "created_at": file.created_at.isoformat() if file.created_at else None,
        })


@router.get("/files/{file_id}/download")
async def download_file_legacy(file_id: int, user: User = Depends(get_current_user)):
    """
    下载/查看文件（兼容旧接口：前端不传 md5_hash 时自动重定向到带 md5_hash 的 URL）
    """
    async with db_manager.get_session() as session:
        file = await session.get(FileModel, file_id)
        if not file:
            raise AppException("文件不存在", status_code=404)
        return download_response(file, user)

@router.get("/files/{file_id}/download/{md5_hash}")
async def download_file(file_id: int, md5_hash: str, user: User = Depends(get_current_user)):
    """
    下载/查看文件（URL中包含MD5哈希，文件内容变了URL自然失效，浏览器缓存自动不命中）
    - 图片类型直接 inline 展示（浏览器可预览）
    - 其他文件作为附件下载
    """
    async with db_manager.get_session() as session:
        file = await session.get(FileModel, file_id)
        if not file:
            raise AppException("文件不存在", status_code=404)
        
        # 验证MD5哈希是否匹配（防篡改 + 确保URL和内容一致）
        if file.md5_hash != md5_hash:
            raise AppException("文件内容已变更，请刷新后重试", status_code=409)
        
        return download_response(file, user)


def download_response(file, user):
    """公共的文件响应逻辑"""
    import urllib.parse
    file_path = Path(file.file_path)
    if not file_path.exists():
        fallback_path = UPLOAD_DIR / file_path.name
        if fallback_path.exists():
            file_path = fallback_path
        else:
            raise AppException("文件数据已丢失", status_code=404)
    
    mime = file.mime_type or "application/octet-stream"
    is_inline = mime.startswith("image/")
    
    encoded_filename = urllib.parse.quote(file.file_name, encoding="utf-8")
    content_disposition = (
        f"{'inline' if is_inline else 'attachment'}; "
        f"filename*=UTF-8''{encoded_filename}"
    )

    return FileResponse(
        path=str(file_path),
        media_type=mime,
        headers={
            "Content-Disposition": content_disposition,
            "Cache-Control": "private, max-age=3600",
        },
    )


# ===== 管理后台接口 =====
@router.get("/admin/groups")
async def admin_list_groups(page: int = 1, page_size: int = 20, admin: User = Depends(get_admin_user)):
    """管理后台-群组列表"""
    async with db_manager.get_session() as session:
        return await fetch_paginated(
            session, select(ChatGroup).order_by(desc(ChatGroup.created_at)), page, page_size,
            mapper=lambda g: {
                "id": g.id, "name": g.name,
                "owner_id": g.owner_id,
                "member_count": g.member_count,
                "status": g.status,
                "created_at": g.created_at.isoformat() if g.created_at else None,
            }
        )

@router.get("/admin/messages")
async def admin_list_messages(page: int = 1, page_size: int = 20, admin: User = Depends(get_admin_user)):
    """管理后台-消息列表"""
    async with db_manager.get_session() as session:
        return await fetch_paginated(
            session, select(ChatMessage).order_by(desc(ChatMessage.created_at)), page, page_size,
            mapper=lambda m: {
                "id": m.id, "sender_id": m.sender_id,
                "receiver_type": m.receiver_type, "receiver_id": m.receiver_id,
                "type": m.type, "content": m.content[:100] if m.content else "",
                "file_id": m.file_id,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
        )

class GroupBanRequest(BaseModel):
    action: str  # ban / unban

class GroupAnnouncementRequest(BaseModel):
    announcement: str

@router.put("/admin/groups/{group_id}/status")
async def admin_set_group_status(group_id: int, req: GroupBanRequest, admin: User = Depends(get_admin_user)):
    """管理后台-封禁/解封群组"""
    if req.action not in ("ban", "unban"):
        raise AppException("无效的操作，可选: ban/unban", status_code=400)
    
    async with db_manager.get_session() as session:
        group = await session.get(ChatGroup, group_id)
        if not group:
            raise AppException("群组不存在", status_code=404)
        
        new_status = "banned" if req.action == "ban" else "active"
        group.status = new_status
        
        # 记录操作日志
        try:
            from database.models import SystemLog
            log = SystemLog(
                user_id=admin.id,
                action=f"group_{req.action}",
                target=f"group:{group_id}",
                detail=f'{{"group_name":"{group.name}","action":"{req.action}"}}',
            )
            session.add(log)
        except Exception:
            pass
        
        await session.commit()
        status_text = "已封禁" if req.action == "ban" else "已解封"
        return success_response(data={"status": new_status}, message=f"群组{status_text}")

@router.post("/admin/groups/{group_id}/announcement")
async def admin_set_group_announcement(group_id: int, req: GroupAnnouncementRequest, admin: User = Depends(get_admin_user)):
    """管理后台-发送系统群公告"""
    async with db_manager.get_session() as session:
        group = await session.get(ChatGroup, group_id)
        if not group:
            raise AppException("群组不存在", status_code=404)
        
        # 保存公告
        group.announcement = req.announcement
        
        # 以系统消息格式发送群公告（发送方为管理员user_id）
        import json
        msg = ChatMessage(
            sender_id=admin.id,
            receiver_id=group_id,
            receiver_type="group",
            type="system",
            content=f"【系统公告】{req.announcement}",
        )
        session.add(msg)
        await session.flush()
        
        # 记录操作日志
        try:
            from database.models import SystemLog
            log = SystemLog(
                user_id=admin.id,
                action="group_announcement",
                target=f"group:{group_id}",
                detail=f'{{"group_name":"{group.name}","announcement":"{req.announcement[:50]}"}}',
            )
            session.add(log)
        except Exception:
            pass
        
        await session.commit()
        return success_response(message="系统公告已发送")

@router.post("/admin/groups/{group_id}/dissolve")
async def admin_dissolve_group(group_id: int, admin: User = Depends(get_admin_user)):
    """管理后台-解散群组"""
    async with db_manager.get_session() as session:
        group = await session.get(ChatGroup, group_id)
        if not group:
            raise AppException("群组不存在", status_code=404)
        
        # 删除所有群聊消息
        from sqlalchemy import delete as sa_delete
        await session.execute(
            sa_delete(ChatMessage).where(
                ChatMessage.receiver_type == "group",
                ChatMessage.receiver_id == group_id
            )
        )
        # 删除所有群成员记录
        await session.execute(sa_delete(GroupMember).where(GroupMember.group_id == group_id))
        # 删除群组已读记录
        await session.execute(
            sa_delete(MessageRead).where(
                MessageRead.receiver_type == "group",
                MessageRead.receiver_id == group_id
            )
        )
        # 删除群组本身
        await session.delete(group)
        
        # 记录操作日志
        try:
            from database.models import SystemLog
            log = SystemLog(
                user_id=admin.id,
                action="admin_group_dissolve",
                target=f"group:{group_id}",
                detail=f'{{"group_name":"{group.name}"}}',
            )
            session.add(log)
        except Exception:
            pass
        
        await session.commit()
        return success_response(message="群组已解散")

@router.get("/admin/groups/{group_id}/detail")
async def admin_get_group_detail(group_id: int, admin: User = Depends(get_admin_user)):
    """管理后台-查看群组详情（跳过成员检查）"""
    async with db_manager.get_session() as session:
        group = await session.get(ChatGroup, group_id)
        if not group:
            raise AppException("群组不存在", status_code=404)
        
        # 获取群主信息
        owner = await session.get(User, group.owner_id)
        
        return success_response(data={
            "id": group.id,
            "name": group.name,
            "avatar": group.avatar or "",
            "announcement": group.announcement or "",
            "member_count": group.member_count,
            "owner_id": group.owner_id,
            "owner_name": owner.nickname or owner.username if owner else "未知",
            "status": group.status,
            "created_at": group.created_at.isoformat() if group.created_at else None,
            "updated_at": group.updated_at.isoformat() if group.updated_at else None,
        })

@router.get("/admin/groups/{group_id}/members")
async def admin_list_group_members(group_id: int, admin: User = Depends(get_admin_user)):
    """管理后台-查看群成员列表"""
    async with db_manager.get_session() as session:
        group = await session.get(ChatGroup, group_id)
        if not group:
            raise AppException("群组不存在", status_code=404)
        
        members_result = await session.execute(
            select(GroupMember).where(GroupMember.group_id == group_id)
        )
        members = members_result.scalars().all()
        member_user_ids = [m.user_id for m in members]
        
        if not member_user_ids:
            return success_response(data={"members": [], "group_name": group.name})
        
        users_result = await session.execute(
            select(User).where(User.id.in_(member_user_ids))
        )
        users_map = {u.id: u for u in users_result.scalars().all()}
        
        return success_response(data={
            "group_name": group.name,
            "member_count": group.member_count,
            "status": group.status,
            "owner_id": group.owner_id,
            "announcement": group.announcement or "",
            "members": [{
                "user_id": m.user_id,
                "username": users_map[m.user_id].username if m.user_id in users_map else "未知",
                "nickname": users_map[m.user_id].nickname if m.user_id in users_map else "",
                "avatar": users_map[m.user_id].avatar if m.user_id in users_map else "",
                "role": m.role,
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            } for m in members],
        })
