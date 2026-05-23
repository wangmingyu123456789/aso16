import tornado.web
from app.controllers.base import BaseHandler

class IndexHandler(BaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("index.html",title="后台",username=self.current_user)