import os
import sys
import traceback
import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado.httpserver import HTTPServer
from app.controllers.auth import LoginHandler,LogoutHandler
from app.controllers.home import IndexHandler
from app.controllers.admin.auth import AdminLoginHandler,AdminLogoutHandler
from app.controllers.admin.index import AdminIndexHandler
from app.controllers.admin.user import AdminUserListHandler,AdminUserApiHandler,AdminUserAddHandler,AdminUserEditHandler,AdminUserDeleteHandler,AdminUserBatchDeleteHandler
from app.models.db import init_db,upgrade_db

class ViteClientHandler(tornado.web.RequestHandler):
	def get(self):
		self.set_header("Content-Type","application/javascript")
		self.set_header("Cache-Control","no-store")
		self.write("/* Vite HMR client stub - no-op */\n")

class ViteEnvHandler(tornado.web.RequestHandler):
	def get(self):
		self.set_header("Content-Type","application/javascript")
		self.set_header("Cache-Control","no-store")
		self.write("/* Vite env stub */\n")

class ViteIdHandler(tornado.web.RequestHandler):
	def get(self):
		self.set_header("Content-Type","application/javascript")
		self.set_header("Cache-Control","no-store")
		self.write("/* Vite id stub */\n")

class ViteWSHandler(tornado.websocket.WebSocketHandler):
	def open(self):
		pass
	def on_message(self, message):
		pass
	def on_close(self):
		pass
	def check_origin(self, origin):
		return True

class DefaultHandler(tornado.web.RequestHandler):
	def get(self):
		self.set_status(200)
		self.write("")
	def post(self):
		self.set_status(200)
		self.write("")

def make_app():
	base_url = os.path.dirname(os.path.abspath(__file__))
	settings = dict(
		template_path=os.path.join(base_url,"app","templates"),
		static_path=os.path.join(base_url,"app","static"),
		cookie_secret="demo-cookie-secret-change-me",
		login_url="/auth/login",
		xsrf_cookies=True,
		debug=True,
		autoreload=False
	)
	return tornado.web.Application([
			(r"/",IndexHandler),
			(r"/auth/login",LoginHandler),
			(r"/auth/logout",LogoutHandler),

			(r"/admin/login",AdminLoginHandler),
			(r"/admin/logout",AdminLogoutHandler),
			(r"/admin",AdminIndexHandler),
			(r"/admin/users",AdminUserListHandler),
			(r"/admin/users/api",AdminUserApiHandler),
			(r"/admin/users/add",AdminUserAddHandler),
			(r"/admin/users/edit",AdminUserEditHandler),
			(r"/admin/users/delete",AdminUserDeleteHandler),
			(r"/admin/users/batch_delete",AdminUserBatchDeleteHandler),

			(r"/@vite/client",ViteClientHandler),
			(r"/@vite/env",ViteEnvHandler),
			(r"/@id/__x00__vite/client",ViteIdHandler),
			(r"/@id/__x00__vite/env",ViteIdHandler),
			(r"/@react-refresh",ViteClientHandler),
			(r"/vite-ws",ViteWSHandler),
			(r"/vite-hmr",ViteWSHandler),
			(r"/(.*)",DefaultHandler),

		],
		**settings
	)

if __name__ == "__main__":
	try:
		init_db()
		upgrade_db()
	except Exception as e:
		print(f"DB init error: {e}",flush=True)
		traceback.print_exc()

	try:
		app = make_app()
		server = HTTPServer(app)
		server.bind(10086)
		server.start()
		print("=====Sever 启动成功 =====端口：10086 ======",flush=True)
		tornado.ioloop.IOLoop.current().start()
	except Exception as e:
		print(f"Server error: {e}",flush=True)
		traceback.print_exc()
