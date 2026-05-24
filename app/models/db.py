# 数据库链接与建表
import os
import sqlite3
def _projiect_root():
	return os.path.abspath(os.path.join(os.path.dirname(__file__),os.pardir,os.pardir))
DB_PATH = os.path.join(_projiect_root(),"database","app.db")

def get_connection():
	os.makedirs(os.path.dirname(DB_PATH),exist_ok=True)
	conn = sqlite3.connect(DB_PATH)
	conn.row_factory = sqlite3.Row 
	return conn

#创建表的方法
def init_db():
	with get_connection() as conn:
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS users(
				id integer PRIMARY KEY AUTOINCREMENT,
				username TEXT NOT NULL UNIQUE,
				password_hash TEXT NOT NULL,
				salt TEXT NOT NULL,
				role TEXT NOT NULL DEFAULT 'user',
				status INTEGER NOT NULL DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now'))
			)
			"""
		)

def upgrade_db():
	with get_connection() as conn:
		cursor = conn.execute("PRAGMA table_info(users)")
		columns = [row[1] for row in cursor.fetchall()]
		if 'role' not in columns:
			conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
		if 'status' not in columns:
			conn.execute("ALTER TABLE users ADD COLUMN status INTEGER NOT NULL DEFAULT 1")
		if 'create_at' not in columns:
			conn.execute("ALTER TABLE users ADD COLUMN create_at TEXT NOT NULL DEFAULT(datetime('now'))")
		conn.commit()