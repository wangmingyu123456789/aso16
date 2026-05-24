# 权限管理控制器
import tornado.web
from app.controllers.admin.base import AdminBaseHandler
from app.models.permission import RoleRepository, PermissionRepository, FunctionRepository

class AdminPermissionListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		roles = RoleRepository.get_all_roles()
		self.render("admin/permission_list.html", title="权限管理", username=self.current_user, current_page='permissions', roles=roles)

class AdminPermissionTreeHandler(AdminBaseHandler):
	"""获取指定角色的权限树（用于二级联动展示）"""
	@tornado.web.authenticated
	def get(self):
		role_id = int(self.get_argument("role_id", "0"))
		if role_id <= 0:
			self.write({'code': 1, 'msg': '请选择角色'})
			return
		tree = PermissionRepository.get_role_function_tree(role_id)
		self.write({'code': 0, 'msg': '', 'data': tree})

class AdminPermissionSaveHandler(AdminBaseHandler):
	"""保存角色权限"""
	@tornado.web.authenticated
	def post(self):
		role_id = int(self.get_body_argument("role_id", "0"))
		function_ids_str = self.get_body_argument("function_ids", "")
		
		if role_id <= 0:
			self.write({'code': 1, 'msg': '请选择角色'})
			return

		# 解析功能ID列表
		function_ids = []
		if function_ids_str:
			try:
				function_ids = [int(x) for x in function_ids_str.split(",") if x.strip()]
			except ValueError:
				self.write({'code': 1, 'msg': '功能ID格式错误'})
				return

		if PermissionRepository.assign_functions_to_role(role_id, function_ids):
			self.write({'code': 0, 'msg': '权限保存成功'})
		else:
			self.write({'code': 1, 'msg': '权限保存失败'})
