# 功能、角色、权限相关的数据访问层
from app.models.db import get_connection

class FunctionRepository:
	@staticmethod
	def get_all_functions():
		"""获取所有功能（按sort_order排序）"""
		with get_connection() as conn:
			rows = conn.execute(
				"SELECT * FROM functions ORDER BY sort_order ASC, id ASC"
			).fetchall()
			return [dict(r) for r in rows]

	@staticmethod
	def get_parent_functions():
		"""获取所有一级功能（parent_id=0）"""
		with get_connection() as conn:
			rows = conn.execute(
				"SELECT * FROM functions WHERE parent_id=0 AND status=1 ORDER BY sort_order ASC, id ASC"
			).fetchall()
			return [dict(r) for r in rows]

	@staticmethod
	def get_children_by_parent(parent_id):
		"""获取指定父级下的子功能"""
		with get_connection() as conn:
			rows = conn.execute(
				"SELECT * FROM functions WHERE parent_id=? ORDER BY sort_order ASC, id ASC",
				(parent_id,)
			).fetchall()
			return [dict(r) for r in rows]

	@staticmethod
	def get_function_tree():
		"""获取功能树（二级结构）"""
		parents = FunctionRepository.get_parent_functions()
		tree = []
		for p in parents:
			children = FunctionRepository.get_children_by_parent(p["id"])
			p["children"] = children
			tree.append(p)
		return tree

	@staticmethod
	def get_function_by_id(func_id):
		with get_connection() as conn:
			row = conn.execute(
				"SELECT * FROM functions WHERE id=?", (func_id,)
			).fetchone()
			return dict(row) if row else None

	@staticmethod
	def create_function(parent_id, name, code, icon='', url='', sort_order=0, status=1):
		try:
			with get_connection() as conn:
				conn.execute(
					"INSERT INTO functions(parent_id,name,code,icon,url,sort_order,status) VALUES(?,?,?,?,?,?,?)",
					(parent_id, name, code, icon, url, sort_order, status)
				)
				return True
		except Exception:
			return False

	@staticmethod
	def update_function(func_id, name=None, code=None, icon=None, url=None, sort_order=None, status=None):
		updates = []
		params = []
		if name is not None:
			updates.append("name=?")
			params.append(name)
		if code is not None:
			updates.append("code=?")
			params.append(code)
		if icon is not None:
			updates.append("icon=?")
			params.append(icon)
		if url is not None:
			updates.append("url=?")
			params.append(url)
		if sort_order is not None:
			updates.append("sort_order=?")
			params.append(sort_order)
		if status is not None:
			updates.append("status=?")
			params.append(status)
		if not updates:
			return False
		params.append(func_id)
		try:
			with get_connection() as conn:
				conn.execute(
					"UPDATE functions SET {} WHERE id=?".format(','.join(updates)),
					params
				)
				return True
		except Exception:
			return False

	@staticmethod
	def delete_function(func_id):
		"""删除功能及其子功能"""
		try:
			with get_connection() as conn:
				# 先删除子功能
				conn.execute("DELETE FROM functions WHERE parent_id=?", (func_id,))
				# 删除权限映射
				conn.execute("DELETE FROM role_functions WHERE function_id=?", (func_id,))
				# 删除功能本身
				conn.execute("DELETE FROM functions WHERE id=?", (func_id,))
				return True
		except Exception:
			return False


class RoleRepository:
	SUPER_ADMIN_CODE = 'super_admin'

	@staticmethod
	def get_all_roles():
		with get_connection() as conn:
			rows = conn.execute(
				"SELECT * FROM roles ORDER BY id ASC"
			).fetchall()
			return [dict(r) for r in rows]

	@staticmethod
	def get_role_by_id(role_id):
		with get_connection() as conn:
			row = conn.execute(
				"SELECT * FROM roles WHERE id=?", (role_id,)
			).fetchone()
			return dict(row) if row else None

	@staticmethod
	def get_role_by_code(code):
		with get_connection() as conn:
			row = conn.execute(
				"SELECT * FROM roles WHERE code=?", (code,)
			).fetchone()
			return dict(row) if row else None

	@staticmethod
	def create_role(name, code, description='', status=1):
		try:
			with get_connection() as conn:
				conn.execute(
					"INSERT INTO roles(name,code,description,status) VALUES(?,?,?,?)",
					(name, code, description, status)
				)
				return True
		except Exception:
			return False

	@staticmethod
	def update_role(role_id, name=None, code=None, description=None, status=None):
		updates = []
		params = []
		if name is not None:
			updates.append("name=?")
			params.append(name)
		if code is not None:
			updates.append("code=?")
			params.append(code)
		if description is not None:
			updates.append("description=?")
			params.append(description)
		if status is not None:
			updates.append("status=?")
			params.append(status)
		if not updates:
			return False
		params.append(role_id)
		try:
			with get_connection() as conn:
				conn.execute(
					"UPDATE roles SET {} WHERE id=?".format(','.join(updates)),
					params
				)
				return True
		except Exception:
			return False

	@staticmethod
	def delete_role(role_id):
		role = RoleRepository.get_role_by_id(role_id)
		if not role or role["is_system"] == 1:
			return False
		try:
			with get_connection() as conn:
				conn.execute("DELETE FROM role_functions WHERE role_id=?", (role_id,))
				conn.execute("DELETE FROM roles WHERE id=?", (role_id,))
				return True
		except Exception:
			return False

	@staticmethod
	def is_system_role(role_id):
		role = RoleRepository.get_role_by_id(role_id)
		return role and role["is_system"] == 1


class PermissionRepository:
	@staticmethod
	def get_role_functions(role_id):
		"""获取角色拥有的功能权限"""
		with get_connection() as conn:
			rows = conn.execute(
				"SELECT function_id FROM role_functions WHERE role_id=?",
				(role_id,)
			).fetchall()
			return [r["function_id"] for r in rows]

	@staticmethod
	def get_role_function_tree(role_id):
		"""获取角色的功能树（带选中状态）"""
		tree = FunctionRepository.get_function_tree()
		role_funcs = set(PermissionRepository.get_role_functions(role_id))
		for p in tree:
			p["checked"] = p["id"] in role_funcs
			for c in p["children"]:
				c["checked"] = c["id"] in role_funcs
		return tree

	@staticmethod
	def assign_functions_to_role(role_id, function_ids):
		"""为角色分配功能权限"""
		try:
			with get_connection() as conn:
				# 先清除旧权限
				conn.execute("DELETE FROM role_functions WHERE role_id=?", (role_id,))
				# 插入新权限
				for fid in function_ids:
					conn.execute(
						"INSERT OR IGNORE INTO role_functions(role_id,function_id) VALUES(?,?)",
						(role_id, fid)
					)
				return True
		except Exception:
			return False

	@staticmethod
	def get_user_functions(username):
		"""获取用户（通过角色）拥有的功能权限"""
		with get_connection() as conn:
			# 获取用户角色
			user = conn.execute(
				"SELECT role FROM users WHERE username=?", (username,)
			).fetchone()
			if not user:
				return []
			role = RoleRepository.get_role_by_code(user["role"])
			if not role:
				return []
			return PermissionRepository.get_role_functions(role["id"])
