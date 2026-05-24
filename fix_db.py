import sqlite3
import os
import hashlib
import secrets

DB_PATH = os.path.join(os.path.dirname(__file__), "database", "app.db")

def fix_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    
    # 检查并添加 can_login_admin 字段
    columns = [row[1] for row in conn.execute("PRAGMA table_info(users)")]
    if 'can_login_admin' not in columns:
        print("Adding can_login_admin column to users table...")
        conn.execute("ALTER TABLE users ADD COLUMN can_login_admin INTEGER NOT NULL DEFAULT 0")
        conn.execute("UPDATE users SET can_login_admin=1 WHERE role='admin'")
        print("Column added successfully.")
    else:
        print("can_login_admin column already exists.")
    
    # 检查 admin 用户是否存在
    admin_row = conn.execute("SELECT id,username,role,status FROM users WHERE username='admin'").fetchone()
    if not admin_row:
        print("Creating default admin user (admin/admin888)...")
        salt = secrets.token_bytes(16)
        dk = hashlib.pbkdf2_hmac("sha256", "admin888".encode('utf-8'), salt, 100_000)
        password_hash = dk.hex()
        conn.execute(
            "INSERT INTO users(username,password_hash,salt,role,status,can_login_admin) VALUES(?,?,?,?,?,?)",
            ("admin", password_hash, salt.hex(), "admin", 1, 1)
        )
        print("Admin user created successfully.")
    else:
        print(f"Admin user already exists (id={admin_row[0]}, role={admin_row[2]}, status={admin_row[3]})")
    
    conn.commit()
    conn.close()
    print("Database fix completed!")

if __name__ == "__main__":
    fix_db()
