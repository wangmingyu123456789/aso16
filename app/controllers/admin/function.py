# 功能管理控制器
import tornado.web
from app.controllers.admin.base import AdminBaseHandler
from app.models.permission import FunctionRepository

class AdminFunctionListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		tree = FunctionRepository.get_function_tree()
		self.render("admin/function_list.html", title="功能管理", username=self.current_user, current_page='functions', tree=tree)

class AdminFunctionApiHandler(AdminBaseHandler):
	"""功能数据API"""
	@tornado.web.authenticated
	def get(self):
		tree = FunctionRepository.get_function_tree()
		data = []
		for p in tree:
			data.append({
				'id': p['id'],
				'parent_id': p['parent_id'],
				'name': p['name'],
				'code': p['code'],
				'icon': p['icon'],
				'url': p['url'],
				'sort_order': p['sort_order'],
				'status': p['status'],
				'create_at': p['create_at'],
				'level': 'parent'
			})
			for c in p.get('children', []):
				data.append({
					'id': c['id'],
					'parent_id': c['parent_id'],
					'name': c['name'],
					'code': c['code'],
					'icon': c['icon'],
					'url': c['url'],
					'sort_order': c['sort_order'],
					'status': c['status'],
					'create_at': c['create_at'],
					'level': 'child'
				})
		self.write({'code': 0, 'msg': '', 'count': len(data), 'data': data})

class AdminFunctionAddHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def post(self):
		parent_id = int(self.get_body_argument("parent_id", "0"))
		name = (self.get_body_argument("name", "") or "").strip()
		code = (self.get_body_argument("code", "") or "").strip()
		icon = (self.get_body_argument("icon", "") or "").strip()
		url = (self.get_body_argument("url", "") or "").strip()
		sort_order = int(self.get_body_argument("sort_order", "0"))
		status = int(self.get_body_argument("status", "1"))

		if not name or not code:
			self.write({'code': 1, 'msg': '功能名称和编码不能为空'})
			return

		if FunctionRepository.create_function(parent_id, name, code, icon, url, sort_order, status):
			self.write({'code': 0, 'msg': '添加成功'})
		else:
			self.write({'code': 1, 'msg': '添加失败，功能编码可能已存在'})

class AdminFunctionEditHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def post(self):
		func_id = int(self.get_body_argument("id", "0"))
		name = (self.get_body_argument("name", "") or "").strip()
		code = (self.get_body_argument("code", "") or "").strip()
		icon = (self.get_body_argument("icon", "") or "").strip()
		url = (self.get_body_argument("url", "") or "").strip()
		sort_order = int(self.get_body_argument("sort_order", "0"))
		status = int(self.get_body_argument("status", "1"))

		if not name or not code:
			self.write({'code': 1, 'msg': '功能名称和编码不能为空'})
			return

		if FunctionRepository.update_function(func_id, name=name, code=code, icon=icon, url=url, sort_order=sort_order, status=status):
			self.write({'code': 0, 'msg': '修改成功'})
		else:
			self.write({'code': 1, 'msg': '修改失败'})

class AdminFunctionDeleteHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def post(self):
		func_id = int(self.get_body_argument("id", "0"))
		if FunctionRepository.delete_function(func_id):
			self.write({'code': 0, 'msg': '删除成功'})
		else:
			self.write({'code': 1, 'msg': '删除失败'})

class AdminFunctionTreeHandler(AdminBaseHandler):
	"""获取功能树（用于二级联动）"""
	@tornado.web.authenticated
	def get(self):
		tree = FunctionRepository.get_function_tree()
		self.write({'code': 0, 'msg': '', 'data': tree})
