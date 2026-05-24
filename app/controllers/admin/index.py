import tornado.web
from app.controllers.admin.base import AdminBaseHandler

class AdminIndexHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin/index.html",title="系统首页",username=self.current_user,current_page='index')
