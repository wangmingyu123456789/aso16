import tornado.web
from app.models.permission import FunctionRepository

class AdminBaseHandler(tornado.web.RequestHandler):
	def get_current_user(self):
		username = self.get_secure_cookie("admin_username")
		if not username:
			return None
		return username.decode('utf-8')

	def render(self, template_name, **kwargs):
		# 自动注入菜单树
		if 'menu_tree' not in kwargs:
			kwargs['menu_tree'] = FunctionRepository.get_function_tree()
		super().render(template_name, **kwargs)
