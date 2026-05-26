from app.models.db import get_connection


class AssistantRepository:
	@staticmethod
	def get_assistant_list(page=1, page_size=20, keyword=None):
		offset = (page - 1) * page_size
		with get_connection() as conn:
			if keyword:
				count_row = conn.execute(
					"SELECT COUNT(*) as total FROM assistants WHERE (assistant_name LIKE ? OR assistant_code LIKE ?)",
					(f"%{keyword}%", f"%{keyword}%")
				).fetchone()
				rows = conn.execute(
					"""SELECT a.*, m.name as model_name FROM assistants a
					LEFT JOIN models m ON a.model_id=m.id
					WHERE (a.assistant_name LIKE ? OR a.assistant_code LIKE ?)
					ORDER BY a.sort_order ASC, a.id ASC LIMIT ? OFFSET ?""",
					(f"%{keyword}%", f"%{keyword}%", page_size, offset)
				).fetchall()
				total = count_row["total"]
			else:
				count_row = conn.execute("SELECT COUNT(*) as total FROM assistants").fetchone()
				rows = conn.execute(
					"""SELECT a.*, m.name as model_name FROM assistants a
					LEFT JOIN models m ON a.model_id=m.id
					ORDER BY a.sort_order ASC, a.id ASC LIMIT ? OFFSET ?""",
					(page_size, offset)
				).fetchall()
				total = count_row["total"]
		return {
			"data": [dict(r) for r in rows],
			"total": total,
			"page": page,
			"page_size": page_size,
		}

	@staticmethod
	def get_enabled_assistants():
		with get_connection() as conn:
			rows = conn.execute(
				"SELECT id,assistant_name,assistant_code,icon,description,category,prompt_template,model_id,api_interface_id FROM assistants WHERE is_enabled=1 ORDER BY sort_order ASC"
			).fetchall()
		return [dict(r) for r in rows]

	@staticmethod
	def get_assistant_by_id(assistant_id):
		with get_connection() as conn:
			row = conn.execute(
				"""SELECT a.*, m.name as model_name FROM assistants a
				LEFT JOIN models m ON a.model_id=m.id WHERE a.id=?""",
				(assistant_id,)
			).fetchone()
		return dict(row) if row else None

	@staticmethod
	def get_assistant_by_code(code):
		with get_connection() as conn:
			row = conn.execute(
				"""SELECT a.*, m.name as model_name, m.api_url as model_api_url,
				m.api_key as model_api_key, m.code as model_code FROM assistants a
				LEFT JOIN models m ON a.model_id=m.id
				WHERE a.assistant_code=? AND a.is_enabled=1""",
				(code,)
			).fetchone()
		return dict(row) if row else None

	@staticmethod
	def add_assistant(data):
		try:
			with get_connection() as conn:
				conn.execute(
					"""INSERT INTO assistants(assistant_name,assistant_code,icon,prompt_template,model_id,sort_order,is_enabled,api_key,api_url,description,category,api_interface_id)
					VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
					(data["assistant_name"], data["assistant_code"], data.get("icon", "layui-icon-user"),
					 data.get("prompt_template", ""), data.get("model_id"), data.get("sort_order", 0),
					 data.get("is_enabled", 1), data.get("api_key", ""), data.get("api_url", ""),
					 data.get("description", ""), data.get("category", "AI"), data.get("api_interface_id"))
				)
			return True
		except Exception:
			return False

	@staticmethod
	def update_assistant(assistant_id, data):
		updates = []
		params = []
		for k in ["assistant_name", "assistant_code", "icon", "prompt_template", "model_id",
				  "sort_order", "is_enabled", "api_key", "api_url", "description", "category", "api_interface_id"]:
			if k in data:
				updates.append(f"{k}=?")
				params.append(data[k])
		if not updates:
			return False
		params.append(assistant_id)
		try:
			with get_connection() as conn:
				conn.execute(f"UPDATE assistants SET {','.join(updates)} WHERE id=?", params)
			return True
		except Exception:
			return False

	@staticmethod
	def delete_assistant(assistant_id):
		try:
			with get_connection() as conn:
				conn.execute("DELETE FROM assistants WHERE id=?", (assistant_id,))
			return True
		except Exception:
			return False

	@staticmethod
	def batch_delete(ids):
		try:
			with get_connection() as conn:
				conn.execute(f"DELETE FROM assistants WHERE id IN ({','.join(['?']*len(ids))})", ids)
			return True
		except Exception:
			return False

	@staticmethod
	def update_sort_order(ids):
		try:
			with get_connection() as conn:
				for idx, aid in enumerate(ids):
					conn.execute("UPDATE assistants SET sort_order=? WHERE id=?", (idx + 1, aid))
			return True
		except Exception:
			return False

	@staticmethod
	def get_usage_stats(days=7):
		with get_connection() as conn:
			rows = conn.execute(
				"""SELECT a.assistant_name, a.assistant_code, a.icon,
				   COUNT(ch.id) as call_count,
				   COALESCE(SUM(ch.total_tokens),0) as total_tokens,
				   COALESCE(SUM(ch.prompt_tokens),0) as prompt_tokens,
				   COALESCE(SUM(ch.completion_tokens),0) as completion_tokens
				FROM assistants a
				LEFT JOIN chat_history ch ON a.id=ch.assistant_id
				  AND ch.create_at >= datetime('now', '-' || ? || ' days')
				GROUP BY a.id
				ORDER BY call_count DESC""",
				(days,)
			).fetchall()
		return [dict(r) for r in rows]


class ChatHistoryRepository:
	@staticmethod
	def save_message(user_id, assistant_id, model_id, role, content, prompt_tokens=0, completion_tokens=0, total_tokens=0):
		try:
			with get_connection() as conn:
				conn.execute(
					"""INSERT INTO chat_history(user_id,assistant_id,model_id,role,content,prompt_tokens,completion_tokens,total_tokens)
					VALUES(?,?,?,?,?,?,?,?)""",
					(user_id, assistant_id, model_id, role, content, prompt_tokens, completion_tokens, total_tokens)
				)
			return True
		except Exception:
			return False

	@staticmethod
	def get_history(user_id, assistant_id=None, limit=50):
		with get_connection() as conn:
			if assistant_id:
				rows = conn.execute(
					"SELECT * FROM chat_history WHERE user_id=? AND assistant_id=? ORDER BY id ASC LIMIT ?",
					(user_id, assistant_id, limit)
				).fetchall()
			else:
				rows = conn.execute(
					"SELECT * FROM chat_history WHERE user_id=? ORDER BY id ASC LIMIT ?",
					(user_id, limit)
				).fetchall()
		return [dict(r) for r in rows]

	@staticmethod
	def clear_history(user_id, assistant_id=None):
		try:
			with get_connection() as conn:
				if assistant_id:
					conn.execute("DELETE FROM chat_history WHERE user_id=? AND assistant_id=?", (user_id, assistant_id))
				else:
					conn.execute("DELETE FROM chat_history WHERE user_id=?", (user_id,))
			return True
		except Exception:
			return False
