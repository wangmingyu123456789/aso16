from app.models.db import get_connection, DB_PATH
import sqlite3
import os


class IMRepository:
    """即时通信数据操作层"""

    @staticmethod
    def get_user_id_by_username(username: str) -> int:
        """根据用户名获取用户ID"""
        with get_connection() as conn:
            row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            return row["id"] if row else 0

    @staticmethod
    def get_username_by_id(user_id: int) -> str:
        """根据用户ID获取用户名"""
        with get_connection() as conn:
            row = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
            return row["username"] if row else ""

    # ==================== 会话管理 ====================

    @staticmethod
    def get_user_conversations(user_id: int) -> list:
        """获取用户的会话列表（含最后消息、未读数）"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    c.id, c.type, c.name, c.avatar,
                    c.last_message, c.last_message_at,
                    COALESCE(u.count, 0) as unread_count
                FROM im_conversation_members m
                JOIN im_conversations c ON m.conversation_id = c.id
                LEFT JOIN im_unread_counts u ON u.conversation_id = c.id AND u.user_id = m.user_id
                WHERE m.user_id = ? AND m.is_deleted = 0
                ORDER BY c.last_message_at DESC
                """,
                (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_conversation_info(conv_id: int):
        """获取会话基本信息"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, type, name, creator_id FROM im_conversations WHERE id=?", (conv_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_private_conversation(user_id: int, target_id: int) -> int:
        """创建或获取私聊会话"""
        with get_connection() as conn:
            # 检查是否已存在
            row = conn.execute(
                """
                SELECT c.id FROM im_conversations c
                JOIN im_conversation_members m1 ON m1.conversation_id = c.id AND m1.user_id = ?
                JOIN im_conversation_members m2 ON m2.conversation_id = c.id AND m2.user_id = ?
                WHERE c.type = 'private'
                """,
                (user_id, target_id)
            ).fetchone()
            if row:
                return row["id"]

            # 创建新会话
            cursor = conn.execute(
                "INSERT INTO im_conversations(type) VALUES('private')"
            )
            conv_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO im_conversation_members(conversation_id, user_id) VALUES(?,?)",
                (conv_id, user_id)
            )
            conn.execute(
                "INSERT INTO im_conversation_members(conversation_id, user_id) VALUES(?,?)",
                (conv_id, target_id)
            )
            return conv_id

    @staticmethod
    def get_or_create_assistant_user(assistant_id: int) -> int:
        """为数字员工获取或创建用户记录，返回 user_id"""
        with get_connection() as conn:
            asst = conn.execute(
                "SELECT assistant_name FROM assistants WHERE id=? AND is_enabled=1", (assistant_id,)
            ).fetchone()
            if not asst:
                return 0
            aname = asst["assistant_name"]
            import hashlib
            salt = "im_bot_salt"
            pwd = hashlib.sha256(("assistant_bot" + salt).encode()).hexdigest()
            user = conn.execute("SELECT id FROM users WHERE username=?", (aname,)).fetchone()
            if user:
                return user["id"]
            cur = conn.execute(
                "INSERT OR IGNORE INTO users(username,password_hash,salt,role,status) VALUES(?,?,?,?,?)",
                (aname, pwd, salt, "user", 1)
            )
            uid = cur.lastrowid
            if uid == 0:
                user2 = conn.execute("SELECT id FROM users WHERE username=?", (aname,)).fetchone()
                uid = user2["id"] if user2 else 0
            return uid

    @staticmethod
    def get_assistant_id_by_user_id(user_id: int) -> int:
        """如果 user_id 对应一个数字员工，返回 assistant_id，否则返回 0"""
        with get_connection() as conn:
            user = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
            if not user:
                return 0
            asst = conn.execute(
                "SELECT id FROM assistants WHERE assistant_name=? AND is_enabled=1", (user["username"],)
            ).fetchone()
            return asst["id"] if asst else 0

    @staticmethod
    def create_group_conversation(name: str, creator_id: int, member_ids: list, assistant_ids: list = None) -> int:
        """创建群聊会话（创建者直接加入，其他成员发送邀请）"""
        import datetime
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO im_conversations(type, name, creator_id) VALUES(?,?,?)",
                ("group", name, creator_id)
            )
            conv_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO im_conversation_members(conversation_id, user_id, role) VALUES(?,?,?)",
                (conv_id, creator_id, "admin")
            )
            now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for mid in member_ids:
                if mid != creator_id:
                    conn.execute(
                        "INSERT INTO im_group_invites (group_id, inviter_id, invitee_id, message, status, create_at) VALUES (?, ?, ?, ?, 'pending', ?)",
                        (conv_id, creator_id, mid, '', now)
                    )
            if assistant_ids:
                for aid in assistant_ids:
                    asst = conn.execute(
                        "SELECT assistant_name FROM assistants WHERE id=? AND is_enabled=1", (aid,)
                    ).fetchone()
                    if asst:
                        aname = asst["assistant_name"]
                        import hashlib
                        salt = "im_bot_salt"
                        pwd = hashlib.sha256(("assistant_bot" + salt).encode()).hexdigest()
                        user = conn.execute(
                            "SELECT id FROM users WHERE username=?", (aname,)
                        ).fetchone()
                        if user:
                            uid = user["id"]
                        else:
                            cur = conn.execute(
                                "INSERT OR IGNORE INTO users(username,password_hash,salt,role,status) VALUES(?,?,?,?,?)",
                                (aname, pwd, salt, "user", 1)
                            )
                            uid = cur.lastrowid
                            if uid == 0:
                                user2 = conn.execute("SELECT id FROM users WHERE username=?", (aname,)).fetchone()
                                uid = user2["id"] if user2 else None
                        if uid:
                            conn.execute(
                                "INSERT OR IGNORE INTO im_conversation_members(conversation_id, user_id) VALUES(?,?)",
                                (conv_id, uid)
                            )
            creator = conn.execute(
                "SELECT username FROM users WHERE id=?", (creator_id,)
            ).fetchone()
            if creator:
                sys_content = f'{creator["username"]} 创建了群聊'
                conn.execute(
                    "INSERT INTO im_messages(conversation_id, sender_id, type, content, create_at) VALUES(?,?,?,?,?)",
                    (conv_id, 0, 'system', sys_content, now)
                )
                conn.execute(
                    "UPDATE im_conversations SET last_message=?, last_message_at=? WHERE id=?",
                    (sys_content[:100], now, conv_id)
                )
            return conv_id

    @staticmethod
    def get_conversation_members(conv_id: int) -> list:
        """获取会话成员列表"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT u.id, u.username, m.role
                FROM im_conversation_members m
                JOIN users u ON m.user_id = u.id
                WHERE m.conversation_id = ?
                """,
                (conv_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ==================== 消息管理 ====================

    @staticmethod
    def save_message(conv_id: int, sender_id: int, msg_type: str, content: str, client_msg_id: str = "") -> int:
        """保存消息到数据库"""
        import datetime
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_connection()
        try:
            # 如果提供了 client_msg_id，先检查是否已存在
            if client_msg_id:
                existing = conn.execute(
                    "SELECT id FROM im_messages WHERE client_msg_id=?", (client_msg_id,)
                ).fetchone()
                if existing:
                    return existing["id"]

            cursor = conn.execute(
                "INSERT INTO im_messages(conversation_id, sender_id, type, content, client_msg_id, create_at) VALUES(?,?,?,?,?,?)",
                (conv_id, sender_id, msg_type, content, client_msg_id, now)
            )
            msg_id = cursor.lastrowid
            # 更新会话最后一条消息（文件/图片消息只显示文件名）
            if msg_type in ('file', 'image'):
                try:
                    import json as _json
                    content_obj = _json.loads(content)
                    fname = content_obj.get('filename', '')
                    summary = fname[:100] if fname else ('[图片]' if msg_type == 'image' else content[:100])
                except Exception:
                    summary = content[:100]
            else:
                summary = content[:100]
            conn.execute(
                "UPDATE im_conversations SET last_message=?, last_message_at=? WHERE id=?",
                (summary, now, conv_id)
            )
            # 更新未读计数（排除发送者）
            conn.execute(
                """
                INSERT INTO im_unread_counts(conversation_id, user_id, count)
                SELECT ?, user_id, 1 FROM im_conversation_members
                WHERE conversation_id = ? AND user_id != ?
                ON CONFLICT(conversation_id, user_id) DO UPDATE SET count = count + 1
                """,
                (conv_id, conv_id, sender_id)
            )
            conn.commit()
            return msg_id
        finally:
            conn.close()

    # ==================== 文件管理（去重存储） ====================

    @staticmethod
    def find_file_by_hash(file_hash: str):
        """按哈希查找文件记录"""
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM im_files WHERE file_hash=?", (file_hash,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def save_file_record(file_name: str, file_size: int, file_hash: str, file_ext: str, mime_type: str, storage_path: str, uploader_id: int) -> int:
        """新增文件记录"""
        with get_connection() as conn:
            c = conn.execute(
                "INSERT INTO im_files(file_name, file_size, file_hash, file_ext, mime_type, storage_path, uploader_id) VALUES(?,?,?,?,?,?,?)",
                (file_name, file_size, file_hash, file_ext, mime_type, storage_path, uploader_id)
            )
            return c.lastrowid

    @staticmethod
    def increment_file_ref(file_id: int):
        """增加文件引用计数"""
        with get_connection() as conn:
            conn.execute("UPDATE im_files SET ref_count = ref_count + 1 WHERE id=?", (file_id,))

    @staticmethod
    def decrement_file_ref(file_id: int):
        """减少文件引用计数，为0时清理"""
        with get_connection() as conn:
            conn.execute("UPDATE im_files SET ref_count = ref_count - 1 WHERE id=?", (file_id,))
            row = conn.execute("SELECT ref_count, storage_path FROM im_files WHERE id=?", (file_id,)).fetchone()
            if row and row['ref_count'] <= 0:
                path = row['storage_path']
                full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), path)
                if os.path.exists(full_path):
                    try:
                        os.remove(full_path)
                    except Exception:
                        pass
                conn.execute("DELETE FROM im_files WHERE id=?", (file_id,))

    @staticmethod
    def get_file_by_id(file_id: int) -> dict:
        """获取文件记录"""
        with get_connection() as conn:
            row = conn.execute(
                """SELECT f.*, u.username as uploader_name FROM im_files f
                LEFT JOIN users u ON f.uploader_id = u.id WHERE f.id=?""",
                (file_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_all_user_files(user_id: int, page: int = 1, page_size: int = 20) -> dict:
        """获取当前用户参与的所有会话中的文件（去重后按时间倒序）"""
        offset = (page - 1) * page_size
        with get_connection() as conn:
            file_match = "m.content LIKE '%\"file_id\":' || imf.id || ',%' OR m.content LIKE '%\"file_id\": ' || imf.id || ',%'"
            total = conn.execute(
                f"""
                SELECT COUNT(DISTINCT imf.id) as cnt FROM im_files imf
                JOIN im_messages m ON ({file_match})
                JOIN im_conversation_members cm ON m.conversation_id = cm.conversation_id
                WHERE cm.user_id=? AND m.type IN ('file','image')
                """,
                (user_id,)
            ).fetchone()['cnt']

            rows = conn.execute(
                f"""
                SELECT DISTINCT imf.*, u.username as uploader_name
                FROM im_files imf
                JOIN im_messages m ON ({file_match})
                JOIN im_conversation_members cm ON m.conversation_id = cm.conversation_id
                LEFT JOIN users u ON imf.uploader_id = u.id
                WHERE cm.user_id=? AND m.type IN ('file','image')
                ORDER BY imf.create_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, page_size, offset)
            ).fetchall()
            return {'total': total, 'data': [dict(r) for r in rows]}

    @staticmethod
    def get_conversation_files(conv_id: int, user_id: int = None, page: int = 1, page_size: int = 20) -> dict:
        """获取指定会话中的文件"""
        offset = (page - 1) * page_size
        with get_connection() as conn:
            file_match = "m.content LIKE '%\"file_id\":' || imf.id || ',%' OR m.content LIKE '%\"file_id\": ' || imf.id || ',%'"
            total = conn.execute(
                f"""
                SELECT COUNT(DISTINCT imf.id) as cnt FROM im_files imf
                JOIN im_messages m ON ({file_match})
                WHERE m.conversation_id=? AND m.type IN ('file','image')
            """,
                (conv_id,)
            ).fetchone()['cnt']

            rows = conn.execute(
                f"""
                SELECT DISTINCT imf.*, u.username as uploader_name
                FROM im_files imf
                JOIN im_messages m ON ({file_match})
                LEFT JOIN users u ON imf.uploader_id = u.id
                WHERE m.conversation_id=? AND m.type IN ('file','image')
                ORDER BY imf.create_at DESC
                LIMIT ? OFFSET ?
                """,
                (conv_id, page_size, offset)
            ).fetchall()
            return {'total': total, 'data': [dict(r) for r in rows]}

    @staticmethod
    def get_group_files(group_id: int, page: int = 1, page_size: int = 20) -> dict:
        """获取群聊中的文件"""
        return IMRepository.get_conversation_files(group_id, page=page, page_size=page_size)

    @staticmethod
    def get_all_files_admin(page: int = 1, page_size: int = 20, keyword: str = '', file_type: str = '', uploader_id: int = 0) -> dict:
        """管理员获取文件列表"""
        offset = (page - 1) * page_size
        with get_connection() as conn:
            conditions = []
            params = []
            if keyword:
                conditions.append("imf.file_name LIKE ?")
                params.append(f'%{keyword}%')
            if file_type:
                if file_type == 'image':
                    conditions.append("imf.file_ext IN ('.jpg','.jpeg','.png','.gif','.webp','.bmp')")
                elif file_type == 'doc':
                    conditions.append("imf.file_ext IN ('.doc','.docx','.pdf','.txt','.xls','.xlsx','.ppt','.pptx')")
                elif file_type == 'zip':
                    conditions.append("imf.file_ext IN ('.zip','.rar','.7z','.tar','.gz')")
            if uploader_id:
                conditions.append("imf.uploader_id=?")
                params.append(uploader_id)

            where_sql = (' WHERE ' + ' AND '.join(conditions)) if conditions else ''
            count_sql = f"SELECT COUNT(*) as cnt FROM im_files imf{where_sql}"
            total = conn.execute(count_sql, params).fetchone()['cnt']

            data_sql = f"""
                SELECT imf.*, u.username as uploader_name
                FROM im_files imf
                LEFT JOIN users u ON imf.uploader_id = u.id
                {where_sql}
                ORDER BY imf.create_at DESC
                LIMIT ? OFFSET ?
            """
            rows = conn.execute(data_sql, params + [page_size, offset]).fetchall()
            return {'total': total, 'data': [dict(r) for r in rows]}

    @staticmethod
    def get_file_stats() -> dict:
        """获取文件统计"""
        with get_connection() as conn:
            total_files = conn.execute("SELECT COUNT(*) as cnt FROM im_files").fetchone()['cnt']
            total_size = conn.execute("SELECT COALESCE(SUM(file_size),0) as total FROM im_files").fetchone()['total']
            ref_sum = conn.execute("SELECT COALESCE(SUM(ref_count),0) as total FROM im_files").fetchone()['total']
            saved = total_size * (ref_sum - total_files) / max(ref_sum, 1) if ref_sum > total_files else 0

            image_count = conn.execute("SELECT COUNT(*) as cnt FROM im_files WHERE file_ext IN ('.jpg','.jpeg','.png','.gif','.webp')").fetchone()['cnt']
            doc_count = conn.execute("SELECT COUNT(*) as cnt FROM im_files WHERE file_ext IN ('.doc','.docx','.pdf','.txt','.xls','.xlsx','.ppt','.pptx')").fetchone()['cnt']
            zip_count = conn.execute("SELECT COUNT(*) as cnt FROM im_files WHERE file_ext IN ('.zip','.rar','.7z','.tar','.gz')").fetchone()['cnt']
            other_count = total_files - image_count - doc_count - zip_count

            return {
                'total_files': total_files,
                'total_size': total_size,
                'saved_space': int(saved),
                'ref_sum': ref_sum,
                'type_distribution': {
                    'image': image_count,
                    'doc': doc_count,
                    'zip': zip_count,
                    'other': max(0, other_count)
                }
            }

    @staticmethod
    def admin_delete_file(file_id: int) -> bool:
        """管理员删除文件"""
        with get_connection() as conn:
            row = conn.execute("SELECT ref_count, storage_path FROM im_files WHERE id=?", (file_id,)).fetchone()
            if not row:
                return False
            if row['ref_count'] > 0:
                return False
            path = row['storage_path']
            full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), path)
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                except Exception:
                    pass
            conn.execute("DELETE FROM im_files WHERE id=?", (file_id,))
            return True

    @staticmethod
    def get_users_dropdown() -> list:
        """获取用户下拉列表（用于管理后台筛选）"""
        with get_connection() as conn:
            rows = conn.execute("SELECT id, username FROM users ORDER BY username").fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def add_system_message(conv_id: int, content: str) -> int:
        """添加系统消息到群聊"""
        import datetime
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO im_messages(conversation_id, sender_id, type, content, create_at) VALUES(?,?,?,?,?)",
                (conv_id, 0, 'system', content, now)
            )
            msg_id = cursor.lastrowid
            conn.execute(
                "UPDATE im_conversations SET last_message=?, last_message_at=? WHERE id=?",
                (content[:100], now, conv_id)
            )
            return msg_id

    @staticmethod
    def is_msg_exists(client_msg_id: str) -> bool:
        """检查客户端消息ID是否已存在（幂等检查）"""
        if not client_msg_id:
            return False
        with get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM im_messages WHERE client_msg_id=?", (client_msg_id,)
            ).fetchone()
            return row is not None

    @staticmethod
    def get_msg_id_by_client_id(client_msg_id: str) -> int:
        """根据客户端消息ID获取服务端消息ID"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM im_messages WHERE client_msg_id=?", (client_msg_id,)
            ).fetchone()
            return row["id"] if row else 0

    @staticmethod
    def get_offline_messages(user_id: int, limit: int = 100) -> list:
        """获取用户的离线消息（所有未读消息）"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT m.id, m.conversation_id, m.sender_id, u.username as sender_name, m.type, m.content, m.create_at
                FROM im_messages m
                LEFT JOIN users u ON m.sender_id = u.id
                JOIN im_conversation_members cm ON cm.conversation_id = m.conversation_id AND cm.user_id = ?
                WHERE m.is_read = 0 AND m.sender_id != ?
                ORDER BY m.id ASC
                LIMIT ?
                """,
                (user_id, user_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def mark_messages_read_by_conv(conv_id: int, user_id: int):
        """标记某个会话中发送给当前用户的消息为已读"""
        with get_connection() as conn:
            conn.execute(
                "UPDATE im_messages SET is_read = 1 WHERE conversation_id = ? AND sender_id != ?",
                (conv_id, user_id)
            )

    @staticmethod
    def get_messages(conv_id: int, limit: int = 50, before_id: int = 0) -> list:
        """获取历史消息"""
        with get_connection() as conn:
            if before_id > 0:
                rows = conn.execute(
                    """
                    SELECT m.id, m.sender_id, u.username as sender_name, m.type, m.content, m.status, m.create_at,
                        cm.role as sender_role
                    FROM im_messages m
                    LEFT JOIN users u ON m.sender_id = u.id
                    LEFT JOIN im_conversation_members cm ON m.sender_id = cm.user_id AND cm.conversation_id = ?
                    WHERE m.conversation_id = ? AND m.id < ?
                    ORDER BY m.id DESC
                    LIMIT ?
                    """,
                    (conv_id, conv_id, before_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT m.id, m.sender_id, u.username as sender_name, m.type, m.content, m.status, m.create_at,
                        cm.role as sender_role
                    FROM im_messages m
                    LEFT JOIN users u ON m.sender_id = u.id
                    LEFT JOIN im_conversation_members cm ON m.sender_id = cm.user_id AND cm.conversation_id = ?
                    WHERE m.conversation_id = ?
                    ORDER BY m.id DESC
                    LIMIT ?
                    """,
                    (conv_id, conv_id, limit)
                ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def mark_read(conv_id: int, user_id: int):
        """标记会话消息为已读"""
        with get_connection() as conn:
            conn.execute(
                "UPDATE im_unread_counts SET count = 0 WHERE conversation_id = ? AND user_id = ?",
                (conv_id, user_id)
            )

    # ==================== 好友管理 ====================

    @staticmethod
    def get_all_users(except_id: int) -> list:
        """获取所有用户（排除自己）"""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, username FROM users WHERE id != ? ORDER BY username",
                (except_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def search_friends(keyword: str, user_id: int) -> list:
        """搜索好友（双向）"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT u.id, u.username
                FROM users u
                WHERE u.username LIKE ?
                AND (
                    EXISTS (SELECT 1 FROM im_friends f WHERE f.user_id = ? AND f.friend_id = u.id)
                    OR EXISTS (SELECT 1 FROM im_friends f WHERE f.friend_id = ? AND f.user_id = u.id)
                )
                ORDER BY u.username
                """,
                (f"%{keyword}%", user_id, user_id)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def search_all_users(keyword: str, except_id: int) -> list:
        """搜索所有用户（用于添加好友）"""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, username FROM users WHERE id != ? AND username LIKE ? ORDER BY username",
                (except_id, f"%{keyword}%")
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def search_users(keyword: str, except_id: int) -> list:
        """搜索用户（仅返回好友）"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT u.id, u.username
                FROM users u
                WHERE u.id != ?
                AND u.username LIKE ?
                AND (
                    EXISTS (SELECT 1 FROM im_friends f WHERE f.user_id = ? AND f.friend_id = u.id)
                    OR EXISTS (SELECT 1 FROM im_friends f WHERE f.friend_id = ? AND f.user_id = u.id)
                )
                ORDER BY u.username
                """,
                (except_id, f"%{keyword}%", except_id, except_id)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def search_non_group_members(group_id: int, keyword: str, except_id: int) -> list:
        """搜索不在群中的用户"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT u.id, u.username
                FROM users u
                WHERE u.id != ?
                AND u.username LIKE ?
                AND u.id NOT IN (
                    SELECT user_id FROM im_conversation_members WHERE conversation_id = ? AND is_deleted = 0
                )
                ORDER BY u.username
                """,
                (except_id, f"%{keyword}%", group_id)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_non_group_friends(user_id: int, group_id: int) -> list:
        """获取不在群中的好友列表（双向）"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT u.id, u.username
                FROM im_friends f
                JOIN users u ON (
                    CASE WHEN f.user_id = ? THEN f.friend_id = u.id
                        WHEN f.friend_id = ? THEN f.user_id = u.id
                    END
                )
                WHERE (f.user_id = ? OR f.friend_id = ?)
                AND f.status = 'accepted'
                AND u.id NOT IN (
                    SELECT user_id FROM im_conversation_members WHERE conversation_id = ? AND is_deleted = 0
                )
                ORDER BY u.username
                """,
                (user_id, user_id, user_id, user_id, group_id)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def search_groups(keyword: str, user_id: int) -> list:
        """搜索群聊"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.name, c.avatar
                FROM im_conversations c
                JOIN im_conversation_members m ON m.conversation_id = c.id
                WHERE c.type = 'group' AND m.user_id = ? AND c.name LIKE ?
                ORDER BY c.name
                """,
                (user_id, f"%{keyword}%")
            ).fetchall()
            return [dict(r) for r in rows]

    # ==================== 好友管理 ====================

    @staticmethod
    def add_friend(user_id: int, friend_id: int, remark: str = ""):
        """添加好友"""
        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO im_friends(user_id, friend_id, remark) VALUES(?,?,?)",
                (user_id, friend_id, remark)
            )
            # 双向添加
            conn.execute(
                "INSERT OR IGNORE INTO im_friends(user_id, friend_id, remark) VALUES(?,?,?)",
                (friend_id, user_id, "")
            )

    @staticmethod
    def remove_friend(user_id: int, friend_id: int):
        """删除好友（同时删除私聊会话和相关数据）"""
        with get_connection() as conn:
            # 查找私聊会话
            rows = conn.execute(
                """
                SELECT cm.conversation_id FROM im_conversation_members cm
                JOIN im_conversations c ON cm.conversation_id = c.id
                WHERE c.type = 'private' AND cm.user_id IN (?,?)
                GROUP BY cm.conversation_id
                HAVING COUNT(DISTINCT cm.user_id) = 2
                """,
                (user_id, friend_id)
            ).fetchall()
            conv_ids = [r["conversation_id"] for r in rows]

            if conv_ids:
                placeholders = ",".join(["?"] * len(conv_ids))
                # 删除未读计数
                conn.execute(
                    f"DELETE FROM im_unread_counts WHERE conversation_id IN ({placeholders})",
                    conv_ids
                )
                # 删除会话成员
                conn.execute(
                    f"DELETE FROM im_conversation_members WHERE conversation_id IN ({placeholders})",
                    conv_ids
                )
                # 删除消息
                conn.execute(
                    f"DELETE FROM im_messages WHERE conversation_id IN ({placeholders})",
                    conv_ids
                )
                # 删除会话
                conn.execute(
                    f"DELETE FROM im_conversations WHERE id IN ({placeholders})",
                    conv_ids
                )

            # 删除好友关系（双向）
            conn.execute("DELETE FROM im_friends WHERE user_id=? AND friend_id=?", (user_id, friend_id))
            conn.execute("DELETE FROM im_friends WHERE user_id=? AND friend_id=?", (friend_id, user_id))

    @staticmethod
    def get_friends(user_id: int) -> list:
        """获取好友列表"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT u.id, u.username, f.remark
                FROM im_friends f
                JOIN users u ON f.friend_id = u.id
                WHERE f.user_id = ?
                ORDER BY u.username
                """,
                (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def is_friend(user_id: int, friend_id: int) -> bool:
        """检查是否为好友（双向）"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM im_friends WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)",
                (user_id, friend_id, friend_id, user_id)
            ).fetchone()
            return row is not None

    # ==================== 好友申请 ====================

    @staticmethod
    def send_friend_request(from_user_id: int, to_user_id: int, message: str = "") -> int:
        """发送好友申请"""
        with get_connection() as conn:
            # 检查是否已有待处理的申请
            row = conn.execute(
                "SELECT id FROM im_friend_requests WHERE from_user_id=? AND to_user_id=? AND status='pending'",
                (from_user_id, to_user_id)
            ).fetchone()
            if row:
                return row["id"]

            cursor = conn.execute(
                "INSERT INTO im_friend_requests(from_user_id, to_user_id, message) VALUES(?,?,?)",
                (from_user_id, to_user_id, message)
            )
            return cursor.lastrowid

    @staticmethod
    def get_friend_requests(user_id: int, received: bool = True) -> list:
        """获取好友申请列表"""
        with get_connection() as conn:
            if received:
                rows = conn.execute(
                    """
                    SELECT r.id, r.from_user_id, u.username as from_name, r.to_user_id, r.message, r.status, r.create_at
                    FROM im_friend_requests r
                    JOIN users u ON r.from_user_id = u.id
                    WHERE r.to_user_id = ?
                    ORDER BY r.create_at DESC
                    """,
                    (user_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT r.id, r.from_user_id, r.to_user_id, u.username as to_name, r.message, r.status, r.create_at
                    FROM im_friend_requests r
                    JOIN users u ON r.to_user_id = u.id
                    WHERE r.from_user_id = ?
                    ORDER BY r.create_at DESC
                    """,
                    (user_id,)
                ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_friend_request_by_id(request_id: int) -> dict:
        """根据ID获取好友申请详情"""
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT r.id, r.from_user_id, r.to_user_id, r.message, r.status,
                    u1.username as from_name, u2.username as to_name
                FROM im_friend_requests r
                JOIN users u1 ON r.from_user_id = u1.id
                JOIN users u2 ON r.to_user_id = u2.id
                WHERE r.id = ?
                """,
                (request_id,)
            ).fetchone()
            return dict(row) if row else {}

    @staticmethod
    def handle_friend_request(request_id: int, status: str, user_id: int):
        """处理好友申请（接受/拒绝）"""
        from_user_id = None
        with get_connection() as conn:
            row = conn.execute(
                "SELECT from_user_id, to_user_id FROM im_friend_requests WHERE id=?",
                (request_id,)
            ).fetchone()
            if not row:
                return False

            if row["to_user_id"] != user_id:
                return False

            from_user_id = row["from_user_id"]

            conn.execute(
                "UPDATE im_friend_requests SET status=?, update_at=datetime('now') WHERE id=?",
                (status, request_id)
            )

        # 在事务提交后再添加好友，避免SQLite写锁冲突
        if status == "accepted" and from_user_id is not None:
            IMRepository.add_friend(from_user_id, row["to_user_id"])

        return True

    @staticmethod
    def delete_friend_request(request_id: int, user_id: int):
        """删除好友申请记录（只有发送方或接收方可以删除）"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT from_user_id, to_user_id FROM im_friend_requests WHERE id=?",
                (request_id,)
            ).fetchone()
            if not row:
                return False
            if row["from_user_id"] != user_id and row["to_user_id"] != user_id:
                return False
            conn.execute("DELETE FROM im_friend_requests WHERE id=?", (request_id,))
            return True

    @staticmethod
    def has_sent_pending_request(from_user_id: int, to_user_id: int) -> bool:
        """检查是否已发送待处理的好友申请"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM im_friend_requests WHERE from_user_id=? AND to_user_id=? AND status='pending'",
                (from_user_id, to_user_id)
            ).fetchone()
            return row is not None

    @staticmethod
    def mark_friend_req_read(user_id: int, req_type: str):
        """标记好友申请已读
        req_type: 'received' - 无操作（收到的待处理申请不需要标记已读，处理后会从计数中移除）
                'sent' - 标记发出的已处理反馈已读
        """
        with get_connection() as conn:
            if req_type == 'sent':
                # 标记发出的所有已处理反馈为已读
                rows = conn.execute(
                    "SELECT id FROM im_friend_requests WHERE from_user_id=? AND status IN ('accepted', 'rejected')",
                    (user_id,)
                ).fetchall()
                for row in rows:
                    conn.execute(
                        "INSERT OR IGNORE INTO im_friend_req_reads (user_id, req_id, req_type) VALUES (?, ?, ?)",
                        (user_id, row['id'], 'sent')
                    )

    @staticmethod
    def get_unread_friend_req_count(user_id: int) -> dict:
        """获取好友申请未读数量
        返回: {'received': 收到的待处理数量（不需要已读标记，处理后才移除）, 'sent': 发出的已处理未读数量}
        """
        with get_connection() as conn:
            # 收到的待处理申请数量（始终计数，直到被处理）
            pending_received = conn.execute(
                "SELECT COUNT(*) as cnt FROM im_friend_requests WHERE to_user_id = ? AND status = 'pending'",
                (user_id,)
            ).fetchone()['cnt']

            # 发出的已处理反馈中未读的数量
            processed_sent = conn.execute(
                """
                SELECT COUNT(*) as cnt FROM im_friend_requests r
                WHERE r.from_user_id = ? AND r.status IN ('accepted', 'rejected')
                  AND r.id NOT IN (SELECT req_id FROM im_friend_req_reads WHERE user_id = ? AND req_type = 'sent')
                """,
                (user_id, user_id)
            ).fetchone()['cnt']

            return {'received': pending_received, 'sent': processed_sent}

    @staticmethod
    def mark_group_invite_read(user_id: int, invite_type: str):
        """标记群邀请已读
        invite_type: 'received' - 无操作（收到的待处理邀请不需要标记已读，处理后会从计数中移除）
                     'sent' - 标记发出的已处理反馈已读
        """
        with get_connection() as conn:
            if invite_type == 'sent':
                rows = conn.execute(
                    "SELECT id FROM im_group_invites WHERE inviter_id=? AND status IN ('accepted', 'rejected')",
                    (user_id,)
                ).fetchall()
                for row in rows:
                    conn.execute(
                        "INSERT OR IGNORE INTO im_group_invite_reads (user_id, invite_id, invite_type) VALUES (?, ?, ?)",
                        (user_id, row['id'], 'sent')
                    )

    @staticmethod
    def get_unread_group_invite_count(user_id: int) -> dict:
        """获取群邀请未读数量
        返回: {'received': 收到的待处理数量（不需要已读标记，处理后才移除）, 'sent': 发出的已处理未读数量}
        """
        with get_connection() as conn:
            # 收到的待处理邀请数量（始终计数，直到被处理）
            pending_received = conn.execute(
                "SELECT COUNT(*) as cnt FROM im_group_invites WHERE invitee_id = ? AND status = 'pending'",
                (user_id,)
            ).fetchone()['cnt']

            # 发出的已处理反馈中未读的数量
            processed_sent = conn.execute(
                """
                SELECT COUNT(*) as cnt FROM im_group_invites gi
                WHERE gi.inviter_id = ? AND gi.status IN ('accepted', 'rejected')
                  AND gi.id NOT IN (SELECT invite_id FROM im_group_invite_reads WHERE user_id = ? AND invite_type = 'sent')
                """,
                (user_id, user_id)
            ).fetchone()['cnt']

            return {'received': pending_received, 'sent': processed_sent}

    # ==================== 群聊管理 ====================

    @staticmethod
    def add_group_member(group_id: int, user_id: int, role: str = "member"):
        """添加群成员"""
        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO im_conversation_members(conversation_id, user_id, role) VALUES(?,?,?)",
                (group_id, user_id, role)
            )

    @staticmethod
    def remove_group_member(group_id: int, user_id: int):
        """移除群成员"""
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM im_conversation_members WHERE conversation_id=? AND user_id=?",
                (group_id, user_id)
            )

    @staticmethod
    def is_group_member(group_id: int, user_id: int) -> bool:
        """检查是否为群成员"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM im_conversation_members WHERE conversation_id=? AND user_id=?",
                (group_id, user_id)
            ).fetchone()
            return row is not None

    @staticmethod
    def get_user_groups(user_id: int) -> list:
        """获取用户加入的群聊列表"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.name, c.avatar, m.role
                FROM im_conversation_members m
                JOIN im_conversations c ON m.conversation_id = c.id
                WHERE m.user_id = ? AND c.type = 'group'
                ORDER BY c.name
                """,
                (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def update_group_info(group_id: int, name: str = None, avatar: str = None, operator_id: int = None):
        """更新群信息"""
        with get_connection() as conn:
            if name:
                conn.execute("UPDATE im_conversations SET name=? WHERE id=?", (name, group_id))
            if avatar:
                conn.execute("UPDATE im_conversations SET avatar=? WHERE id=?", (avatar, group_id))
            if operator_id:
                conn.execute(
                    "INSERT INTO group_operation_logs(group_id, operator_id, operation_type, detail) VALUES(?,?,?,?)",
                    (group_id, operator_id, 'update_group_info', name or '')
                )

    @staticmethod
    def delete_conversation(conv_id: int, user_id: int):
        """删除会话（从用户会话列表中隐藏，不退出群聊）"""
        with get_connection() as conn:
            conv = conn.execute(
                "SELECT type, creator_id FROM im_conversations WHERE id=?", (conv_id,)
            ).fetchone()
            if not conv:
                return False
            if conv["type"] == "private":
                # 私聊：物理删除整个会话
                conn.execute("DELETE FROM im_messages WHERE conversation_id=?", (conv_id,))
                conn.execute("DELETE FROM im_unread_counts WHERE conversation_id=?", (conv_id,))
                conn.execute("DELETE FROM im_conversation_members WHERE conversation_id=?", (conv_id,))
                conn.execute("DELETE FROM im_conversations WHERE id=?", (conv_id,))
            else:
                # 群聊：只标记 is_deleted=1，不删除成员关系，不删除群
                conn.execute(
                    "UPDATE im_conversation_members SET is_deleted=1 WHERE conversation_id=? AND user_id=?",
                    (conv_id, user_id)
                )
                conn.execute(
                    "UPDATE im_unread_counts SET count=0 WHERE conversation_id=? AND user_id=?",
                    (conv_id, user_id)
                )
            return True

    @staticmethod
    def restore_conversation(conv_id: int, user_id: int):
        """恢复已删除的会话（将 is_deleted 重置为 0）"""
        with get_connection() as conn:
            conn.execute(
                "UPDATE im_conversation_members SET is_deleted=0 WHERE conversation_id=? AND user_id=?",
                (conv_id, user_id)
            )

    # ==================== 群管理扩展 ====================

    @staticmethod
    def get_group_detail(group_id: int, user_id: int) -> dict:
        """获取群详情（含我的角色、公告、管控状态）"""
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, type, name, avatar, creator_id,
                       is_muted_all, allow_join, announcement, announcement_time, announcement_publisher_id,
                       is_deleted
                FROM im_conversations WHERE id=? AND type='group'
                """,
                (group_id,)
            ).fetchone()
            if not row:
                return {}
            result = dict(row)
            # 获取我的角色
            member = conn.execute(
                "SELECT role FROM im_conversation_members WHERE conversation_id=? AND user_id=?",
                (group_id, user_id)
            ).fetchone()
            result['my_role'] = member['role'] if member else 'none'
            # 获取公告发布者名称
            if result.get('announcement_publisher_id'):
                pub = conn.execute(
                    "SELECT username FROM users WHERE id=?", (result['announcement_publisher_id'],)
                ).fetchone()
                result['announcement_publisher_name'] = pub['username'] if pub else ''
            return result

    @staticmethod
    def get_member_role(conv_id: int, user_id: int) -> str:
        """获取用户在指定会话中的角色"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT role FROM im_conversation_members WHERE conversation_id=? AND user_id=?",
                (conv_id, user_id)
            ).fetchone()
            return row['role'] if row else ''

    # ==================== 群邀请管理 ====================

    @staticmethod
    def create_group_invite(group_id: int, inviter_id: int, invitee_id: int, message: str = '') -> int:
        """创建群邀请"""
        with get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO im_group_invites (group_id, inviter_id, invitee_id, message, status) VALUES (?, ?, ?, ?, 'pending')",
                (group_id, inviter_id, invitee_id, message)
            )
            return cursor.lastrowid

    @staticmethod
    def get_group_invites(user_id: int, invite_type: str = 'received') -> list:
        """获取用户的群邀请列表
        invite_type: 'received' - 收到的邀请, 'sent' - 发出的邀请
        """
        with get_connection() as conn:
            if invite_type == 'received':
                rows = conn.execute(
                    """
                    SELECT gi.id, gi.group_id, gi.inviter_id, gi.invitee_id, gi.message, gi.status, gi.create_at,
                        u.username as inviter_name, c.name as group_name
                    FROM im_group_invites gi
                    JOIN users u ON gi.inviter_id = u.id
                    JOIN im_conversations c ON gi.group_id = c.id
                    WHERE gi.invitee_id = ?
                    ORDER BY gi.create_at DESC
                    """,
                    (user_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT gi.id, gi.group_id, gi.inviter_id, gi.invitee_id, gi.message, gi.status, gi.create_at,
                        u.username as invitee_name, c.name as group_name
                    FROM im_group_invites gi
                    JOIN users u ON gi.invitee_id = u.id
                    JOIN im_conversations c ON gi.group_id = c.id
                    WHERE gi.inviter_id = ?
                    ORDER BY gi.create_at DESC
                    """,
                    (user_id,)
                ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def handle_group_invite(invite_id: int, user_id: int, status: str) -> bool:
        """处理群邀请（同意/拒绝）
        status: 'accepted' 或 'rejected'
        """
        import datetime
        with get_connection() as conn:
            invite = conn.execute(
                "SELECT * FROM im_group_invites WHERE id=? AND invitee_id=? AND status='pending'",
                (invite_id, user_id)
            ).fetchone()
            if not invite:
                return False

            conn.execute(
                "UPDATE im_group_invites SET status=?, update_at=datetime('now') WHERE id=?",
                (status, invite_id)
            )

            if status == 'accepted':
                conn.execute(
                    """
                    INSERT OR IGNORE INTO im_conversation_members (conversation_id, user_id, role)
                    VALUES (?, ?, 'member')
                    """,
                    (invite['group_id'], user_id)
                )

                conn.execute(
                    """
                    INSERT OR IGNORE INTO im_unread_counts (conversation_id, user_id, count)
                    VALUES (?, ?, 0)
                    """,
                    (invite['group_id'], user_id)
                )

                conn.execute(
                    "INSERT INTO group_operation_logs(group_id, operator_id, operation_type, target_id) VALUES(?,?,?,?)",
                    (invite['group_id'], invite['inviter_id'], 'add_member', user_id)
                )

                now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                username = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
                if username:
                    content = f"{username['username']} 加入了群聊"
                    conn.execute(
                        "INSERT INTO im_messages(conversation_id, sender_id, type, content, create_at) VALUES(?,?,?,?,?)",
                        (invite['group_id'], 0, 'system', content, now)
                    )
                    conn.execute(
                        "UPDATE im_conversations SET last_message=?, last_message_at=? WHERE id=?",
                        (content[:100], now, invite['group_id'])
                    )

            return True

    @staticmethod
    def delete_group_invite(invite_id: int, user_id: int) -> bool:
        """删除群邀请记录"""
        with get_connection() as conn:
            result = conn.execute(
                "DELETE FROM im_group_invites WHERE id=? AND (inviter_id=? OR invitee_id=?)",
                (invite_id, user_id, user_id)
            )
            return result.rowcount > 0

    @staticmethod
    def get_pending_invite_count(user_id: int) -> int:
        """获取用户待处理的群邀请数量"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM im_group_invites WHERE invitee_id=? AND status='pending'",
                (user_id,)
            ).fetchone()
            return row['cnt'] if row else 0

    @staticmethod
    def is_user_in_group(group_id: int, user_id: int) -> bool:
        """检查用户是否已在群中"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM im_conversation_members WHERE conversation_id=? AND user_id=? AND is_deleted=0",
                (group_id, user_id)
            ).fetchone()
            return row is not None

    @staticmethod
    def has_pending_invite(group_id: int, invitee_id: int) -> bool:
        """检查用户是否已有待处理的群邀请"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM im_group_invites WHERE group_id=? AND invitee_id=? AND status='pending'",
                (group_id, invitee_id)
            ).fetchone()
            return row is not None

    @staticmethod
    def get_pending_invite(group_id: int, invitee_id: int) -> dict:
        """获取待处理的群邀请详情"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM im_group_invites WHERE group_id=? AND invitee_id=? AND status='pending'",
                (group_id, invitee_id)
            ).fetchone()
            return dict(row) if row else {}

    @staticmethod
    def get_invite_by_id(invite_id: int) -> dict:
        """根据邀请ID获取邀请详情"""
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT gi.id, gi.group_id, gi.inviter_id, gi.invitee_id, gi.message, gi.status,
                       c.name as group_name
                FROM im_group_invites gi
                JOIN im_conversations c ON gi.group_id = c.id
                WHERE gi.id = ?
                """,
                (invite_id,)
            ).fetchone()
            return dict(row) if row else {}

    @staticmethod
    def get_group_members_detail(group_id: int) -> list:
        """获取群成员详细信息（含禁言状态、入群时间、最后发言）"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT u.id, u.username, m.role, m.join_at, m.mute_until,
                       (SELECT MAX(create_at) FROM im_messages WHERE conversation_id=? AND sender_id=u.id) as last_speak_at
                FROM im_conversation_members m
                JOIN users u ON m.user_id = u.id
                WHERE m.conversation_id = ?
                ORDER BY
                    CASE m.role WHEN 'owner' THEN 1 WHEN 'admin' THEN 2 ELSE 3 END,
                    m.join_at ASC
                """,
                (group_id, group_id)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def update_group_name(group_id: int, name: str, operator_id: int):
        """修改群名称"""
        with get_connection() as conn:
            conn.execute("UPDATE im_conversations SET name=? WHERE id=?", (name, group_id))
            conn.execute(
                "INSERT INTO group_operation_logs(group_id, operator_id, operation_type, detail) VALUES(?,?,?,?)",
                (group_id, operator_id, 'update_name', f'"{name}"')
            )

    @staticmethod
    def update_group_avatar(group_id: int, avatar: str, operator_id: int):
        """修改群头像"""
        with get_connection() as conn:
            conn.execute("UPDATE im_conversations SET avatar=? WHERE id=?", (avatar, group_id))
            conn.execute(
                "INSERT INTO group_operation_logs(group_id, operator_id, operation_type, detail) VALUES(?,?,?,?)",
                (group_id, operator_id, 'update_avatar', f'"{avatar}"')
            )

    @staticmethod
    def set_admin(group_id: int, member_id: int, action: str, operator_id: int):
        """设置/取消管理员"""
        with get_connection() as conn:
            if action == 'set':
                conn.execute(
                    "UPDATE im_conversation_members SET role='admin' WHERE conversation_id=? AND user_id=? AND role='member'",
                    (group_id, member_id)
                )
            else:
                conn.execute(
                    "UPDATE im_conversation_members SET role='member' WHERE conversation_id=? AND user_id=? AND role='admin'",
                    (group_id, member_id)
                )
            conn.execute(
                "INSERT INTO group_operation_logs(group_id, operator_id, operation_type, target_id) VALUES(?,?,?,?)",
                (group_id, operator_id, 'set_admin', member_id)
            )

    @staticmethod
    def remove_group_member_with_log(group_id: int, member_id: int, operator_id: int):
        """移除群成员（带日志）"""
        import datetime
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with get_connection() as conn:
            member = conn.execute(
                "SELECT username FROM users WHERE id=?", (member_id,)
            ).fetchone()
            operator = conn.execute(
                "SELECT username FROM users WHERE id=?", (operator_id,)
            ).fetchone()
            conn.execute(
                "DELETE FROM im_conversation_members WHERE conversation_id=? AND user_id=?",
                (group_id, member_id)
            )
            conn.execute(
                "INSERT INTO group_operation_logs(group_id, operator_id, operation_type, target_id) VALUES(?,?,?,?)",
                (group_id, operator_id, 'remove_member', member_id)
            )
            if member and operator:
                sys_content = f'{member["username"]} 被 {operator["username"]} 移出了群聊'
                conn.execute(
                    "INSERT INTO im_messages(conversation_id, sender_id, type, content, create_at) VALUES(?,?,?,?,?)",
                    (group_id, 0, 'system', sys_content, now)
                )
                conn.execute(
                    "UPDATE im_conversations SET last_message=?, last_message_at=? WHERE id=?",
                    (sys_content[:100], now, group_id)
                )

    @staticmethod
    def batch_remove_members(group_id: int, member_ids: list, operator_id: int):
        """批量移除群成员"""
        import datetime
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with get_connection() as conn:
            placeholders = ",".join(["?"] * len(member_ids))
            conn.execute(
                f"DELETE FROM im_conversation_members WHERE conversation_id=? AND user_id IN ({placeholders})",
                [group_id] + member_ids
            )
            operator = conn.execute(
                "SELECT username FROM users WHERE id=?", (operator_id,)
            ).fetchone()
            for mid in member_ids:
                conn.execute(
                    "INSERT INTO group_operation_logs(group_id, operator_id, operation_type, target_id) VALUES(?,?,?,?)",
                    (group_id, operator_id, 'remove_member', mid)
                )
                member = conn.execute(
                    "SELECT username FROM users WHERE id=?", (mid,)
                ).fetchone()
                if member and operator:
                    sys_content = f'{member["username"]} 被 {operator["username"]} 移出了群聊'
                    conn.execute(
                        "INSERT INTO im_messages(conversation_id, sender_id, type, content, create_at) VALUES(?,?,?,?,?)",
                        (group_id, 0, 'system', sys_content, now)
                    )
            if operator:
                conn.execute(
                    "UPDATE im_conversations SET last_message=?, last_message_at=? WHERE id=?",
                    (f'{operator["username"]} 移除了 {len(member_ids)} 名成员'[:100], now, group_id)
                )

    @staticmethod
    def mute_member(group_id: int, member_id: int, mute_until: str, operator_id: int):
        """禁言成员"""
        with get_connection() as conn:
            conn.execute(
                "UPDATE im_conversation_members SET mute_until=? WHERE conversation_id=? AND user_id=?",
                (mute_until, group_id, member_id)
            )
            conn.execute(
                "INSERT INTO group_operation_logs(group_id, operator_id, operation_type, target_id, detail) VALUES(?,?,?,?,?)",
                (group_id, operator_id, 'ban_member', member_id, f'mute_until={mute_until}')
            )

    @staticmethod
    def unmute_member(group_id: int, member_id: int, operator_id: int):
        """解除禁言"""
        with get_connection() as conn:
            conn.execute(
                "UPDATE im_conversation_members SET mute_until=NULL WHERE conversation_id=? AND user_id=?",
                (group_id, member_id)
            )
            conn.execute(
                "INSERT INTO group_operation_logs(group_id, operator_id, operation_type, target_id) VALUES(?,?,?,?)",
                (group_id, operator_id, 'ban_member', member_id)
            )

    @staticmethod
    def is_muted(group_id: int, user_id: int) -> dict:
        """检查用户是否被禁言，返回 {is_muted: bool, reason: str}"""
        import datetime
        with get_connection() as conn:
            # 检查群全体禁言
            group = conn.execute(
                "SELECT is_muted_all FROM im_conversations WHERE id=?", (group_id,)
            ).fetchone()
            if group and group['is_muted_all']:
                # 检查是否是管理员或群主
                member = conn.execute(
                    "SELECT role FROM im_conversation_members WHERE conversation_id=? AND user_id=?",
                    (group_id, user_id)
                ).fetchone()
                if member and member['role'] in ('owner', 'admin'):
                    return {'is_muted': False, 'reason': ''}
                return {'is_muted': True, 'reason': '群主已开启全体禁言'}

            # 检查个人禁言
            member = conn.execute(
                "SELECT mute_until FROM im_conversation_members WHERE conversation_id=? AND user_id=?",
                (group_id, user_id)
            ).fetchone()
            if member and member['mute_until']:
                now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if member['mute_until'] > now:
                    return {'is_muted': True, 'reason': f'你已被禁言，解除时间：{member["mute_until"]}'}
                # 禁言已过期，清除
                conn.execute(
                    "UPDATE im_conversation_members SET mute_until=NULL WHERE conversation_id=? AND user_id=?",
                    (group_id, user_id)
                )
            return {'is_muted': False, 'reason': ''}

    @staticmethod
    def set_mute_all(group_id: int, enabled: int, operator_id: int):
        """设置全体禁言"""
        with get_connection() as conn:
            conn.execute("UPDATE im_conversations SET is_muted_all=? WHERE id=?", (enabled, group_id))
            conn.execute(
                "INSERT INTO group_operation_logs(group_id, operator_id, operation_type, detail) VALUES(?,?,?,?)",
                (group_id, operator_id, 'mute_all', f'enabled={enabled}')
            )

    @staticmethod
    def set_allow_join(group_id: int, enabled: int, operator_id: int):
        """设置是否允许新成员加入"""
        with get_connection() as conn:
            conn.execute("UPDATE im_conversations SET allow_join=? WHERE id=?", (enabled, group_id))
            conn.execute(
                "INSERT INTO group_operation_logs(group_id, operator_id, operation_type, detail) VALUES(?,?,?,?)",
                (group_id, operator_id, 'allow_join', f'enabled={enabled}')
            )

    @staticmethod
    def dismiss_group(group_id: int, operator_id: int):
        """解散群聊"""
        import datetime
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with get_connection() as conn:
            conn.execute("UPDATE im_conversations SET is_deleted=1, deleted_at=? WHERE id=?", (now, group_id))
            conn.execute("DELETE FROM im_conversation_members WHERE conversation_id=?", (group_id,))
            conn.execute(
                "INSERT INTO group_operation_logs(group_id, operator_id, operation_type) VALUES(?,?,?)",
                (group_id, operator_id, 'dismiss_group')
            )

    @staticmethod
    def leave_group(group_id: int, user_id: int):
        """退出群聊"""
        import datetime
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with get_connection() as conn:
            user = conn.execute(
                "SELECT username FROM users WHERE id=?", (user_id,)
            ).fetchone()
            conn.execute(
                "DELETE FROM im_conversation_members WHERE conversation_id=? AND user_id=?",
                (group_id, user_id)
            )
            conn.execute(
                "INSERT INTO group_operation_logs(group_id, operator_id, operation_type) VALUES(?,?,?)",
                (group_id, user_id, 'leave_group')
            )
            if user:
                sys_content = f'{user["username"]} 退出了群聊'
                conn.execute(
                    "INSERT INTO im_messages(conversation_id, sender_id, type, content, create_at) VALUES(?,?,?,?,?)",
                    (group_id, 0, 'system', sys_content, now)
                )
                conn.execute(
                    "UPDATE im_conversations SET last_message=?, last_message_at=? WHERE id=?",
                    (sys_content[:100], now, group_id)
                )

    @staticmethod
    def publish_announcement(group_id: int, content: str, publisher_id: int) -> int:
        """发布公告"""
        import datetime
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with get_connection() as conn:
            conn.execute(
                "UPDATE group_announcements SET is_active=0 WHERE group_id=? AND is_active=1",
                (group_id,)
            )
            cursor = conn.execute(
                "INSERT INTO group_announcements(group_id, content, publisher_id, create_at) VALUES(?,?,?,?)",
                (group_id, content, publisher_id, now)
            )
            ann_id = cursor.lastrowid
            conn.execute(
                "UPDATE im_conversations SET announcement=?, announcement_time=?, announcement_publisher_id=? WHERE id=?",
                (content, now, publisher_id, group_id)
            )
            conn.execute(
                "INSERT INTO group_operation_logs(group_id, operator_id, operation_type, target_id) VALUES(?,?,?,?)",
                (group_id, publisher_id, 'publish_announcement', ann_id)
            )
            pub = conn.execute(
                "SELECT username FROM users WHERE id=?", (publisher_id,)
            ).fetchone()
            if pub:
                sys_content = f'{pub["username"]} 发布了新公告'
                conn.execute(
                    "INSERT INTO im_messages(conversation_id, sender_id, type, content, create_at) VALUES(?,?,?,?,?)",
                    (group_id, 0, 'system', sys_content, now)
                )
                conn.execute(
                    "UPDATE im_conversations SET last_message=?, last_message_at=? WHERE id=?",
                    (sys_content[:100], now, group_id)
                )
            return ann_id

    @staticmethod
    def get_unconfirmed_announcement(group_id: int, user_id: int) -> dict:
        """获取用户未确认的最新公告"""
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT a.id, a.content, a.create_at, a.publisher_id, u.username as publisher_name
                FROM group_announcements a
                JOIN users u ON a.publisher_id = u.id
                WHERE a.group_id = ? AND a.id NOT IN (
                    SELECT announcement_id FROM announcement_confirmations WHERE user_id = ?
                )
                ORDER BY a.create_at DESC LIMIT 1
                """,
                (group_id, user_id)
            ).fetchone()
            return dict(row) if row else {}

    @staticmethod
    def is_digital_employee(user_id: int) -> bool:
        """检查用户是否为数字员工"""
        with get_connection() as conn:
            user = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
            if not user:
                return False
            asst = conn.execute(
                "SELECT 1 FROM assistants WHERE assistant_name=? AND is_enabled=1", (user["username"],)
            ).fetchone()
            return asst is not None

    @staticmethod
    def confirm_announcement(announcement_id: int, group_id: int, user_id: int) -> bool:
        """确认公告"""
        import datetime
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO announcement_confirmations(announcement_id, group_id, user_id, create_at) VALUES(?,?,?,?)",
                (announcement_id, group_id, user_id, now)
            )
            user = conn.execute(
                "SELECT username FROM users WHERE id=?", (user_id,)
            ).fetchone()
            if user:
                sys_content = f'{user["username"]} 已确认公告'
                conn.execute(
                    "INSERT INTO im_messages(conversation_id, sender_id, type, content, create_at) VALUES(?,?,?,?,?)",
                    (group_id, 0, 'system', sys_content, now)
                )
                conn.execute(
                    "UPDATE im_conversations SET last_message=?, last_message_at=? WHERE id=?",
                    (sys_content[:100], now, group_id)
                )
            return True

    @staticmethod
    def get_announcements(group_id: int, limit: int = 20) -> list:
        """获取公告历史"""
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.execute(
                """
                SELECT a.id, a.content, a.create_at, a.is_active,
                    u.username as publisher_name
                FROM group_announcements a
                JOIN users u ON a.publisher_id = u.id
                WHERE a.group_id = ?
                ORDER BY a.create_at DESC
                LIMIT ?
                """,
                (group_id, limit)
            )
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        finally:
            conn.close()

    @staticmethod
    def delete_announcement(ann_id: int, group_id: int, operator_id: int) -> bool:
        """删除公告 - 删除记录并更新当前公告显示"""
        try:
            with get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM group_announcements WHERE id=? AND group_id=?",
                    (ann_id, group_id)
                )
                if cursor.rowcount == 0:
                    return False

                conn.execute(
                    "INSERT INTO group_operation_logs(group_id, operator_id, operation_type, target_id) VALUES(?,?,?,?)",
                    (group_id, operator_id, 'delete_announcement', ann_id)
                )

                row = conn.execute(
                    "SELECT content, publisher_id, create_at FROM group_announcements WHERE group_id=? ORDER BY create_at DESC LIMIT 1",
                    (group_id,)
                ).fetchone()

                if row:
                    conn.execute(
                        "UPDATE im_conversations SET announcement=?, announcement_time=?, announcement_publisher_id=? WHERE id=?",
                        (row['content'], row['create_at'], row['publisher_id'], group_id)
                    )
                else:
                    conn.execute(
                        "UPDATE im_conversations SET announcement=NULL, announcement_time=NULL, announcement_publisher_id=NULL WHERE id=?",
                        (group_id,)
                    )

                op = conn.execute(
                    "SELECT username FROM users WHERE id=?", (operator_id,)
                ).fetchone()
                if op:
                    import datetime
                    sys_now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    sys_content = f'{op["username"]} 删除了一条公告'
                    conn.execute(
                        "INSERT INTO im_messages(conversation_id, sender_id, type, content, create_at) VALUES(?,?,?,?,?)",
                        (group_id, 0, 'system', sys_content, sys_now)
                    )
                    conn.execute(
                        "UPDATE im_conversations SET last_message=?, last_message_at=? WHERE id=?",
                        (sys_content[:100], sys_now, group_id)
                    )

                return True
        except Exception:
            return False

    @staticmethod
    def transfer_group(group_id: int, new_owner_id: int, operator_id: int):
        """转让群主"""
        import datetime
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with get_connection() as conn:
            conn.execute(
                "UPDATE im_conversation_members SET role='admin' WHERE conversation_id=? AND user_id=?",
                (group_id, operator_id)
            )
            conn.execute(
                "UPDATE im_conversation_members SET role='owner' WHERE conversation_id=? AND user_id=?",
                (group_id, new_owner_id)
            )
            conn.execute(
                "UPDATE im_conversations SET creator_id=? WHERE id=?",
                (new_owner_id, group_id)
            )
            conn.execute(
                "INSERT INTO group_operation_logs(group_id, operator_id, operation_type, target_id) VALUES(?,?,?,?)",
                (group_id, operator_id, 'transfer_group', new_owner_id)
            )
            operator = conn.execute(
                "SELECT username FROM users WHERE id=?", (operator_id,)
            ).fetchone()
            new_owner = conn.execute(
                "SELECT username FROM users WHERE id=?", (new_owner_id,)
            ).fetchone()
            if operator and new_owner:
                sys_content = f'{operator["username"]} 将群主转让给了 {new_owner["username"]}'
                conn.execute(
                    "INSERT INTO im_messages(conversation_id, sender_id, type, content, create_at) VALUES(?,?,?,?,?)",
                    (group_id, 0, 'system', sys_content, now)
                )
                conn.execute(
                    "UPDATE im_conversations SET last_message=?, last_message_at=? WHERE id=?",
                    (sys_content[:100], now, group_id)
                )

    @staticmethod
    def get_group_settings(group_id: int) -> dict:
        """获取群管控设置"""
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute(
                "SELECT is_muted_all, allow_join FROM im_conversations WHERE id=?",
                (group_id,)
            ).fetchone()
            return dict(zip(['is_muted_all', 'allow_join'], row)) if row else {}
        finally:
            conn.close()

    @staticmethod
    def get_group_operation_logs(group_id: int, limit: int = 50) -> list:
        """获取群操作日志"""
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.execute(
                """
                SELECT l.id, l.operation_type, l.target_id, l.detail, l.create_at,
                       u.username as operator_name
                FROM group_operation_logs l
                JOIN users u ON l.operator_id = u.id
                WHERE l.group_id = ?
                ORDER BY l.create_at DESC
                LIMIT ?
                """,
                (group_id, limit)
            )
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        finally:
            conn.close()
