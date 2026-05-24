import tornado.web
from app.models.permission import FunctionRepository, PermissionRepository
from app.models.db import get_connection

class AdminBaseHandler(tornado.web.RequestHandler):
	def get_current_user(self):
		username = self.get_secure_cookie("admin_username")
		if not username:
			return None
		return username.decode('utf-8')

	def get_current_user_role(self):
		"""获取当前登录用户的角色"""
		with get_connection() as conn:
			user = conn.execute(
				"SELECT role FROM users WHERE username=?", (self.current_user,)
			).fetchone()
		return user["role"] if user else None

	def get_user_role_functions(self, username):
		"""获取用户角色对应的功能权限"""
		with get_connection() as conn:
			user = conn.execute(
				"SELECT role FROM users WHERE username=?", (username,)
			).fetchone()
		if not user:
			return []
		role_code = user["role"]
		# 超级管理员拥有所有权限
		if role_code == 'admin':
			return None  # 返回None表示拥有所有权限
		# 获取角色ID
		from app.models.permission import RoleRepository
		role = RoleRepository.get_role_by_code(role_code)
		if not role:
			return []
		# 获取角色的功能权限
		return PermissionRepository.get_role_functions(role["id"])

	def filter_menu_by_permissions(self, menu_tree, allowed_func_ids):
		"""根据权限过滤菜单树"""
		# allowed_func_ids为None表示拥有所有权限（超级管理员）
		if allowed_func_ids is None:
			return menu_tree
		allowed_set = set(allowed_func_ids)
		filtered = []
		for item in menu_tree:
			children = item.get("children", [])
			# 过滤子菜单
			filtered_children = [c for c in children if c["id"] in allowed_set]
			# 如果父节点有权限或者有子节点有权限，则保留
			if item["id"] in allowed_set or filtered_children:
				item_copy = dict(item)
				item_copy["children"] = filtered_children
				filtered.append(item_copy)
		return filtered

	def render(self, template_name, **kwargs):
		# 自动注入菜单树（根据用户权限过滤）
		if 'menu_tree' not in kwargs:
			full_tree = FunctionRepository.get_function_tree()
			allowed_ids = self.get_user_role_functions(self.current_user)
			kwargs['menu_tree'] = self.filter_menu_by_permissions(full_tree, allowed_ids)
		super().render(template_name, **kwargs)
