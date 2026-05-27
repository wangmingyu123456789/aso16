# -*- coding: utf-8 -*-
"""注入 IM 测试 mock 数据到现有数据库"""
import sqlite3
import os
import secrets

db_path = os.path.join("database", "app.db")
if not os.path.exists(db_path):
    print("数据库文件不存在，请先启动服务创建数据库")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

def ensure_user(username, password="test1234"):
    row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        # 简单 hash: salt + sha256
        salt = secrets.token_bytes(16)
        import hashlib
        pw_hash = hashlib.sha256(salt + password.encode()).hexdigest()
        conn.execute(
            "INSERT INTO users(username,password_hash,salt,role,status,can_login_admin) VALUES(?,?,?,?,?,?)",
            (username, pw_hash, salt.hex(), "user", 1, 0)
        )
        conn.commit()
        row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    return row["id"]

# 创建测试用户
users = {
    "admin": "admin123",
    "test1": "test1234",
    "test2": "test1234",
    "张三": "test1234",
    "张三1": "test1234",
    "张三2": "test1234",
    "李四": "test1234",
    "王五": "test1234",
}

print("=== 创建/获取用户 ===")
user_ids = {}
for username, password in users.items():
    uid = ensure_user(username, password)
    user_ids[username] = uid
    print(f"  {username}: id={uid}")

aid = user_ids["admin"]
t1id = user_ids["test1"]
t2id = user_ids["test2"]
zhangsan_id = user_ids["张三"]
zhangsan1_id = user_ids["张三1"]
zhangsan2_id = user_ids["张三2"]
lisi_id = user_ids["李四"]
wangwu_id = user_ids["王五"]

# 插入好友关系
print("\n=== 插入好友关系 ===")
friend_pairs = [
    (aid, t1id, "admin ↔ test1"),
    (t1id, aid, "test1 ↔ admin"),
    (aid, t2id, "admin ↔ test2"),
    (t2id, aid, "test2 ↔ admin"),
    (aid, zhangsan_id, "admin ↔ 张三"),
    (zhangsan_id, aid, "张三 ↔ admin"),
    (t1id, zhangsan1_id, "test1 ↔ 张三1"),
    (zhangsan1_id, t1id, "张三1 ↔ test1"),
    (t1id, zhangsan2_id, "test1 ↔ 张三2"),
    (zhangsan2_id, t1id, "张三2 ↔ test1"),
    (t2id, lisi_id, "test2 ↔ 李四"),
    (lisi_id, t2id, "李四 ↔ test2"),
]

for uid1, uid2, desc in friend_pairs:
    conn.execute("INSERT OR IGNORE INTO im_friends(user_id,friend_id) VALUES(?,?)", (uid1, uid2))
    print(f"  {desc}")
conn.commit()

# 插入好友申请
print("\n=== 插入好友申请 ===")
requests = [
    (t1id, aid, "你好，我是test1，想加你为好友", "pending", "test1 → admin (待处理)"),
    (lisi_id, aid, "你好，我是李四", "pending", "李四 → admin (待处理)"),
    (wangwu_id, aid, "你好，我是王五", "accepted", "王五 → admin (已同意)"),
    (aid, zhangsan1_id, "你好，我想加你为好友", "pending", "admin → 张三1 (待处理)"),
    (aid, zhangsan2_id, "你好，认识一下", "rejected", "admin → 张三2 (已拒绝)"),
    (zhangsan_id, t1id, "你好，我是张三", "accepted", "张三 → test1 (已同意)"),
]

for from_id, to_id, msg, status, desc in requests:
    conn.execute(
        "INSERT OR IGNORE INTO im_friend_requests(from_user_id,to_user_id,message,status) VALUES(?,?,?,?)",
        (from_id, to_id, msg, status)
    )
    print(f"  {desc}")
conn.commit()

# 统计
fc = conn.execute("SELECT COUNT(*) as cnt FROM im_friends").fetchone()["cnt"]
frc = conn.execute("SELECT COUNT(*) as cnt FROM im_friend_requests").fetchone()["cnt"]
uc = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]

print(f"\n=== 完成 ===")
print(f"  用户数: {uc}")
print(f"  好友关系数: {fc}")
print(f"  好友申请数: {frc}")

conn.close()
