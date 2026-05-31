import datetime
import time
import json
import httpx
from app.models.db import get_connection


class ServerRegistry:
    """IM服务器节点注册与发现"""

    @staticmethod
    def register(node_id, host, public_port, internal_port, pid=0, max_connections=200):
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM im_server_nodes WHERE node_id=?", (node_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE im_server_nodes SET host=?, public_port=?, internal_port=?,
                       pid=?, status='online', load_score=0, connection_count=0,
                       max_connections=?, started_at=?, last_heartbeat=?
                       WHERE node_id=?""",
                    (host, public_port, internal_port, pid, max_connections, now, now, node_id)
                )
                return existing["id"]
            else:
                cursor = conn.execute(
                    """INSERT INTO im_server_nodes
                       (node_id, host, public_port, internal_port, pid, status,
                        max_connections, started_at, last_heartbeat)
                       VALUES(?,?,?,?,?,'online',?,?,?)""",
                    (node_id, host, public_port, internal_port, pid, max_connections, now, now)
                )
                return cursor.lastrowid

    @staticmethod
    def heartbeat(node_id, connection_count):
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with get_connection() as conn:
            conn.execute(
                """UPDATE im_server_nodes SET
                   connection_count=?, load_score=?,
                   last_heartbeat=?, status='online'
                   WHERE node_id=?""",
                (connection_count, min(1.0, connection_count / 200.0) if connection_count > 0 else 0,
                 now, node_id)
            )

    @staticmethod
    def get_online_nodes():
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM im_server_nodes
                   WHERE status='online'
                   ORDER BY load_score ASC, priority ASC"""
            ).fetchall()
            # 检查心跳是否过期（超过15秒视为离线）
            now = datetime.datetime.now()
            result = []
            for row in rows:
                d = dict(row)
                try:
                    hb = datetime.datetime.strptime(d["last_heartbeat"], '%Y-%m-%d %H:%M:%S')
                    if (now - hb).total_seconds() > 15:
                        d["status"] = "offline"
                        ServerRegistry.mark_offline(d["node_id"])
                        continue
                except (ValueError, TypeError):
                    pass
                result.append(d)
            return result

    @staticmethod
    def get_node_by_id(node_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM im_server_nodes WHERE node_id=?", (node_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def mark_offline(node_id):
        with get_connection() as conn:
            conn.execute(
                "UPDATE im_server_nodes SET status='offline' WHERE node_id=?", (node_id,)
            )

    @staticmethod
    def get_node_count():
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM im_server_nodes WHERE status='online'"
            ).fetchone()
            return row["cnt"] if row else 0

    @staticmethod
    def get_all_nodes():
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM im_server_nodes ORDER BY node_id"
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def clean_dead_nodes():
        with get_connection() as conn:
            conn.execute(
                "UPDATE im_server_nodes SET status='dead' WHERE last_heartbeat < datetime('now', '-30 seconds') AND status='online'"
            )


class UserAssigner:
    """用户-服务器分配管理"""

    @staticmethod
    def assign(user_id, preferred_node_id=None):
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with get_connection() as conn:
            # 检查是否有旧的绑定
            binding = conn.execute(
                "SELECT * FROM im_user_node_map WHERE user_id=?", (user_id,)
            ).fetchone()

            if binding:
                b = dict(binding)
                # 如果该节点还在线，保持粘性
                if b["is_active"]:
                    node = ServerRegistry.get_node_by_id(b["node_id"])
                    if node and node["status"] == "online":
                        # 检查心跳是否过期
                        try:
                            hb = datetime.datetime.strptime(node["last_heartbeat"], '%Y-%m-%d %H:%M:%S')
                            now_dt = datetime.datetime.now()
                            if (now_dt - hb).total_seconds() <= 15:
                                conn.execute(
                                    "UPDATE im_user_node_map SET last_active_at=?, is_active=1 WHERE user_id=?",
                                    (now, user_id)
                                )
                                return b["node_id"]
                        except (ValueError, TypeError):
                            pass

            # 需要重新分配：选择负载最低的在线节点
            nodes = ServerRegistry.get_online_nodes()
            if not nodes:
                return None

            # 优先选择 preferred_node_id
            if preferred_node_id:
                for n in nodes:
                    if n["node_id"] == preferred_node_id:
                        selected = n
                        break
                else:
                    selected = nodes[0]
            else:
                selected = nodes[0]

            # 更新绑定
            conn.execute(
                """INSERT OR REPLACE INTO im_user_node_map
                   (user_id, node_id, assigned_at, last_active_at, is_active)
                   VALUES(?,?,?,?,1)""",
                (user_id, selected["node_id"], now, now)
            )

            return selected["node_id"]

    @staticmethod
    def get_user_node(user_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM im_user_node_map WHERE user_id=? AND is_active=1",
                (user_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            node = ServerRegistry.get_node_by_id(d["node_id"])
            if node and node["status"] == "online":
                return d["node_id"]
            return None

    @staticmethod
    def release_user(user_id):
        with get_connection() as conn:
            conn.execute(
                "UPDATE im_user_node_map SET is_active=0 WHERE user_id=?", (user_id,)
            )

    @staticmethod
    def get_all_assignments():
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT u.id as user_id, u.username, m.node_id FROM im_user_node_map m JOIN users u ON m.user_id=u.id WHERE m.is_active=1"
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def build_node_url(node_id, ws_path="/im/ws"):
        node = ServerRegistry.get_node_by_id(node_id)
        if not node:
            return None
        return "ws://{}:{}{}".format(node["host"], node["public_port"], ws_path)


class MessageDelivery:
    """跨服务器消息投递确认"""

    @staticmethod
    def create(msg_id, conv_id, sender_id, target_user_id, target_node_id):
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO im_message_delivery
                   (msg_id, conv_id, sender_id, target_user_id, target_node_id, status)
                   VALUES(?,?,?,?,?,'pending')""",
                (msg_id, conv_id, sender_id, target_user_id, target_node_id)
            )
            return cursor.lastrowid

    @staticmethod
    def mark_delivered(delivery_id):
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with get_connection() as conn:
            conn.execute(
                "UPDATE im_message_delivery SET status='delivered', delivered_at=? WHERE id=?",
                (now, delivery_id)
            )

    @staticmethod
    def mark_failed(delivery_id, reason):
        with get_connection() as conn:
            conn.execute(
                "UPDATE im_message_delivery SET status='failed', fail_reason=?, retry_count=retry_count+1 WHERE id=?",
                (reason[:200], delivery_id)
            )

    @staticmethod
    def get_undelivered():
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM im_message_delivery WHERE status='pending' AND retry_count < 3"
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_failed_for_user(user_id, limit=50):
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM im_message_delivery WHERE target_user_id=? AND status='failed' ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    async def forward_to_node(target_node_id, message_obj, delivery_id=None):
        """转发消息到目标节点的内部 API"""
        node = ServerRegistry.get_node_by_id(target_node_id)
        if not node:
            if delivery_id:
                MessageDelivery.mark_failed(delivery_id, "target node not found")
            return False

        url = "http://{}:{}/internal/send".format(node["host"], node["internal_port"])
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json={
                    "messages": [message_obj]
                })
                if resp.status_code == 200:
                    if delivery_id:
                        MessageDelivery.mark_delivered(delivery_id)
                    return True
                else:
                    if delivery_id:
                        MessageDelivery.mark_failed(delivery_id, "HTTP {}".format(resp.status_code))
                    return False
        except httpx.ConnectError:
            if delivery_id:
                MessageDelivery.mark_failed(delivery_id, "connect refused")
            return False
        except httpx.TimeoutException:
            if delivery_id:
                MessageDelivery.mark_failed(delivery_id, "timeout")
            return False
        except Exception as e:
            if delivery_id:
                MessageDelivery.mark_failed(delivery_id, str(e)[:200])
            return False
