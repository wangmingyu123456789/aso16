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
				create_at TXTE NOT NULL DEFAULT(datetime('now'))
			)
			"""
		)