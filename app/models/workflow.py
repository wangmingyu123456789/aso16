import json
from app.models.db import get_connection


class WorkflowRepository:
	TABLE = "auto_workflows"

	@classmethod
	def create_table(cls):
		with get_connection() as conn:
			conn.execute("""
				CREATE TABLE IF NOT EXISTS auto_workflows(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					name TEXT NOT NULL,
					description TEXT DEFAULT '',
					steps TEXT NOT NULL DEFAULT '[]',
					cron_expression TEXT DEFAULT '',
					is_enabled INTEGER DEFAULT 1,
					last_run_at TEXT,
					last_result TEXT DEFAULT '',
					create_at TEXT DEFAULT (datetime('now'))
				)
			""")
			conn.execute("""
				CREATE TABLE IF NOT EXISTS workflow_logs(
					id INTEGER PRIMARY KEY AUTOINCREMENT,
					workflow_id INTEGER NOT NULL,
					status TEXT DEFAULT 'running',
					result TEXT DEFAULT '',
					started_at TEXT DEFAULT (datetime('now')),
					finished_at TEXT
				)
			""")

	@classmethod
	def get_all(cls):
		with get_connection() as conn:
			return conn.execute("SELECT * FROM auto_workflows ORDER BY id DESC").fetchall()

	@classmethod
	def get_by_id(cls, wid):
		with get_connection() as conn:
			return conn.execute("SELECT * FROM auto_workflows WHERE id=?", (wid,)).fetchone()

	@classmethod
	def create(cls, name, description, steps, cron_expression=""):
		with get_connection() as conn:
			conn.execute(
				"INSERT INTO auto_workflows(name,description,steps,cron_expression) VALUES(?,?,?,?)",
				(name, description, json.dumps(steps, ensure_ascii=False), cron_expression)
			)
			return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

	@classmethod
	def update(cls, wid, name, description, steps, cron_expression, is_enabled):
		with get_connection() as conn:
			conn.execute(
				"UPDATE auto_workflows SET name=?,description=?,steps=?,cron_expression=?,is_enabled=? WHERE id=?",
				(name, description, json.dumps(steps, ensure_ascii=False), cron_expression, is_enabled, wid)
			)

	@classmethod
	def delete(cls, wid):
		with get_connection() as conn:
			conn.execute("DELETE FROM workflow_logs WHERE workflow_id=?", (wid,))
			conn.execute("DELETE FROM auto_workflows WHERE id=?", (wid,))

	@classmethod
	def toggle(cls, wid):
		with get_connection() as conn:
			row = conn.execute("SELECT is_enabled FROM auto_workflows WHERE id=?", (wid,)).fetchone()
			if row:
				conn.execute("UPDATE auto_workflows SET is_enabled=? WHERE id=?", (1-row["is_enabled"], wid))

	@classmethod
	def add_log(cls, workflow_id, status="running", result=""):
		with get_connection() as conn:
			conn.execute(
				"INSERT INTO workflow_logs(workflow_id,status,result) VALUES(?,?,?)",
				(workflow_id, status, result)
			)
			return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

	@classmethod
	def update_log(cls, log_id, status, result=""):
		with get_connection() as conn:
			conn.execute(
				"UPDATE workflow_logs SET status=?,result=?,finished_at=datetime('now') WHERE id=?",
				(status, result, log_id)
			)

	@classmethod
	def get_logs(cls, workflow_id, limit=20):
		with get_connection() as conn:
			return conn.execute(
				"SELECT * FROM workflow_logs WHERE workflow_id=? ORDER BY id DESC LIMIT ?",
				(workflow_id, limit)
			).fetchall()

	@classmethod
	def get_enabled(cls):
		with get_connection() as conn:
			return conn.execute("SELECT * FROM auto_workflows WHERE is_enabled=1").fetchall()
