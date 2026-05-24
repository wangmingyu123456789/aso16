# 角色管理控制器
import tornado.web
from app.controllers.admin.base import AdminBaseHandler
from app.models.permission import RoleRepository, PermissionRepository

class AdminRoleListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		roles = RoleRepository.get_all_roles()
		self.render("admin/role_list.html", title="角色管理", username=self.current_user, current_page='roles', roles=roles)

class AdminRoleApiHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		roles = RoleRepository.get_all_roles()
		self.write({'code': 0, 'msg': '', 'count': len(roles), 'data': roles})

class AdminRoleAddHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def post(self):
		name = (self.get_body_argument("name", "") or "").strip()
		code = (self.get_body_argument("code", "") or "").strip()
		description = (self.get_body_argument("description", "") or "").strip()
		status = int(self.get_body_argument("status", "1"))

		if not name or not code:
			self.write({'code': 1, 'msg': '角色名称和编码不能为空'})
			return

		if RoleRepository.create_role(name, code, description, status):
			self.write({'code': 0, 'msg': '添加成功'})
		else:
			self.write({'code': 1, 'msg': '添加失败，角色名称或编码可能已存在'})

class AdminRoleEditHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def post(self):
		role_id = int(self.get_body_argument("id", "0"))
		name = (self.get_body_argument("name", "") or "").strip()
		code = (self.get_body_argument("code", "") or "").strip()
		description = (self.get_body_argument("description", "") or "").strip()
		status = int(self.get_body_argument("status", "1"))

		if not name or not code:
			self.write({'code': 1, 'msg': '角色名称和编码不能为空'})
			return

		if RoleRepository.is_system_role(role_id):
			self.write({'code': 1, 'msg': '系统角色不允许修改'})
			return

		if RoleRepository.update_role(role_id, name=name, code=code, description=description, status=status):
			self.write({'code': 0, 'msg': '修改成功'})
		else:
			self.write({'code': 1, 'msg': '修改失败'})

class AdminRoleDeleteHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def post(self):
		role_id = int(self.get_body_argument("id", "0"))
		if RoleRepository.is_system_role(role_id):
			self.write({'code': 1, 'msg': '系统角色不允许删除'})
			return
		if RoleRepository.delete_role(role_id):
			self.write({'code': 0, 'msg': '删除成功'})
		else:
			self.write({'code': 1, 'msg': '删除失败'})
