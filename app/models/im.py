from app.models.db import get_connection


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
                WHERE m.user_id = ?
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
        """创建群聊会话"""
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
            for mid in member_ids:
                if mid != creator_id:
                    conn.execute(
                        "INSERT INTO im_conversation_members(conversation_id, user_id) VALUES(?,?)",
                        (conv_id, mid)
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
        now = "datetime('now')"
        with get_connection() as conn:
            # 如果提供了 client_msg_id，先检查是否已存在
            if client_msg_id:
                existing = conn.execute(
                    "SELECT id FROM im_messages WHERE client_msg_id=?", (client_msg_id,)
                ).fetchone()
                if existing:
                    return existing["id"]

            cursor = conn.execute(
                "INSERT INTO im_messages(conversation_id, sender_id, type, content, client_msg_id) VALUES(?,?,?,?,?)",
                (conv_id, sender_id, msg_type, content, client_msg_id)
            )
            msg_id = cursor.lastrowid
            # 更新会话最后一条消息
            conn.execute(
                "UPDATE im_conversations SET last_message=?, last_message_at=datetime('now') WHERE id=?",
                (content[:100], conv_id)
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
                JOIN users u ON m.sender_id = u.id
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
                    SELECT m.id, m.sender_id, u.username as sender_name, m.type, m.content, m.status, m.create_at
                    FROM im_messages m
                    JOIN users u ON m.sender_id = u.id
                    WHERE m.conversation_id = ? AND m.id < ?
                    ORDER BY m.id DESC
                    LIMIT ?
                    """,
                    (conv_id, before_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT m.id, m.sender_id, u.username as sender_name, m.type, m.content, m.status, m.create_at
                    FROM im_messages m
                    JOIN users u ON m.sender_id = u.id
                    WHERE m.conversation_id = ?
                    ORDER BY m.id DESC
                    LIMIT ?
                    """,
                    (conv_id, limit)
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
    def search_users(keyword: str, except_id: int) -> list:
        """搜索用户"""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, username FROM users WHERE id != ? AND username LIKE ? ORDER BY username",
                (except_id, f"%{keyword}%")
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
        """检查是否为好友"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM im_friends WHERE user_id=? AND friend_id=?",
                (user_id, friend_id)
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
    def update_group_info(group_id: int, name: str = None, avatar: str = None):
        """更新群信息"""
        with get_connection() as conn:
            if name:
                conn.execute("UPDATE im_conversations SET name=? WHERE id=?", (name, group_id))
            if avatar:
                conn.execute("UPDATE im_conversations SET avatar=? WHERE id=?", (avatar, group_id))

    @staticmethod
    def delete_conversation(conv_id: int, user_id: int):
        """删除会话（只删除当前用户与会话的关系，群聊检查是否为创建者）"""
        with get_connection() as conn:
            conv = conn.execute(
                "SELECT type, creator_id FROM im_conversations WHERE id=?", (conv_id,)
            ).fetchone()
            if not conv:
                return False
            if conv["type"] == "private":
                conn.execute("DELETE FROM im_messages WHERE conversation_id=?", (conv_id,))
                conn.execute("DELETE FROM im_unread_counts WHERE conversation_id=?", (conv_id,))
                conn.execute("DELETE FROM im_conversation_members WHERE conversation_id=?", (conv_id,))
                conn.execute("DELETE FROM im_conversations WHERE id=?", (conv_id,))
            else:
                conn.execute("DELETE FROM im_conversation_members WHERE conversation_id=? AND user_id=?", (conv_id, user_id))
                conn.execute("DELETE FROM im_unread_counts WHERE conversation_id=? AND user_id=?", (conv_id, user_id))
                remaining = conn.execute(
                    "SELECT COUNT(*) as cnt FROM im_conversation_members WHERE conversation_id=?", (conv_id,)
                ).fetchone()
                if remaining["cnt"] == 0:
                    conn.execute("DELETE FROM im_messages WHERE conversation_id=?", (conv_id,))
                    conn.execute("DELETE FROM im_conversation_members WHERE conversation_id=?", (conv_id,))
                    conn.execute("DELETE FROM im_conversations WHERE id=?", (conv_id,))
            return True
