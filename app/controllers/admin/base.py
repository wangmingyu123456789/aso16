import tornado.web

class AdminBaseHandler(tornado.web.RequestHandler):
	def get_current_user(self):
		username = self.get_secure_cookie("admin_username")
		if not username:
			return None
		return username.decode('utf-8')
