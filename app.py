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
from app.controllers.admin.user import AdminUserListHandler,AdminUserApiHandler,AdminUserRolesApiHandler,AdminUserAddHandler,AdminUserEditHandler,AdminUserDeleteHandler,AdminUserBatchDeleteHandler
from app.controllers.admin.function import AdminFunctionListHandler,AdminFunctionApiHandler,AdminFunctionAddHandler,AdminFunctionEditHandler,AdminFunctionDeleteHandler,AdminFunctionTreeHandler
from app.controllers.admin.role import AdminRoleListHandler,AdminRoleApiHandler,AdminRoleAddHandler,AdminRoleEditHandler,AdminRoleDeleteHandler
from app.controllers.admin.permission import AdminPermissionListHandler,AdminPermissionTreeHandler,AdminPermissionSaveHandler
from app.controllers.admin.model import AdminModelListHandler,AdminModelApiHandler,AdminModelAddHandler,AdminModelEditHandler,AdminModelDeleteHandler,AdminModelSetDefaultHandler,AdminModelChatTestHandler,AdminModelChatStreamHandler
from app.controllers.admin.outlook import AdminOutlookRedirectHandler,AdminOutlookSourceListHandler,AdminOutlookSourceApiHandler,AdminOutlookSourceAddHandler,AdminOutlookSourceEditHandler,AdminOutlookSourceDeleteHandler,AdminOutlookCollectHandler,AdminOutlookDataListHandler,AdminOutlookDataApiHandler,AdminOutlookDataDeleteHandler,AdminOutlookCollectPageHandler,AdminOutlookTaskApiHandler,AdminOutlookTaskDeleteHandler,AdminOutlookTaskDataHandler,AdminOutlookTaskDataApiHandler,AdminOutlookLatestDataApiHandler,AdminOutlookStatusApiHandler
from app.controllers.admin.api_mgmt import AdminApiListHandler,AdminApiListApiHandler,AdminApiAddHandler,AdminApiEditHandler,AdminApiDeleteHandler,AdminApiTestHandler,AdminApiServiceHandler
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
	def get(self, path=""):
		self.set_status(200)
		self.write("")
	def post(self, path=""):
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
			(r"/admin/users/roles_api",AdminUserRolesApiHandler),
			(r"/admin/users/add",AdminUserAddHandler),
			(r"/admin/users/edit",AdminUserEditHandler),
			(r"/admin/users/delete",AdminUserDeleteHandler),
			(r"/admin/users/batch_delete",AdminUserBatchDeleteHandler),

			# 功能管理
			(r"/admin/functions",AdminFunctionListHandler),
			(r"/admin/functions/api",AdminFunctionApiHandler),
			(r"/admin/functions/add",AdminFunctionAddHandler),
			(r"/admin/functions/edit",AdminFunctionEditHandler),
			(r"/admin/functions/delete",AdminFunctionDeleteHandler),
			(r"/admin/functions/tree",AdminFunctionTreeHandler),

			# 角色管理
			(r"/admin/roles",AdminRoleListHandler),
			(r"/admin/roles/api",AdminRoleApiHandler),
			(r"/admin/roles/add",AdminRoleAddHandler),
			(r"/admin/roles/edit",AdminRoleEditHandler),
			(r"/admin/roles/delete",AdminRoleDeleteHandler),

			# 权限管理
			(r"/admin/permissions",AdminPermissionListHandler),
			(r"/admin/permissions/tree",AdminPermissionTreeHandler),
			(r"/admin/permissions/save",AdminPermissionSaveHandler),

			# 模型引擎
			(r"/admin/models",AdminModelListHandler),
			(r"/admin/models/api",AdminModelApiHandler),
			(r"/admin/models/add",AdminModelAddHandler),
			(r"/admin/models/edit",AdminModelEditHandler),
			(r"/admin/models/delete",AdminModelDeleteHandler),
			(r"/admin/models/set_default",AdminModelSetDefaultHandler),
			(r"/admin/models/chat_test",AdminModelChatTestHandler),
			(r"/admin/models/chat_stream",AdminModelChatStreamHandler),

			# 瞭望管理
			(r"/admin/outlook",AdminOutlookCollectPageHandler),
			(r"/admin/outlook/sources",AdminOutlookSourceListHandler),
			(r"/admin/outlook/sources/api",AdminOutlookSourceApiHandler),
			(r"/admin/outlook/sources/add",AdminOutlookSourceAddHandler),
			(r"/admin/outlook/sources/edit",AdminOutlookSourceEditHandler),
			(r"/admin/outlook/sources/delete",AdminOutlookSourceDeleteHandler),
			(r"/admin/outlook/collect/do",AdminOutlookCollectHandler),
			(r"/admin/outlook/data",AdminOutlookDataListHandler),
			(r"/admin/warehouse",AdminOutlookDataListHandler),
			(r"/admin/outlook/data/api",AdminOutlookDataApiHandler),
			(r"/admin/outlook/data/delete",AdminOutlookDataDeleteHandler),
			(r"/admin/outlook/tasks/api",AdminOutlookTaskApiHandler),
			(r"/admin/outlook/task/data",AdminOutlookTaskDataHandler),
			(r"/admin/outlook/task/data/api",AdminOutlookTaskDataApiHandler),
			(r"/admin/outlook/task/delete",AdminOutlookTaskDeleteHandler),
			(r"/admin/outlook/latest/data/api",AdminOutlookLatestDataApiHandler),
			(r"/admin/outlook/status/api",AdminOutlookStatusApiHandler),

			# 接口管理
			(r"/admin/api",AdminApiListHandler),
			(r"/admin/api/list",AdminApiListApiHandler),
			(r"/admin/api/add",AdminApiAddHandler),
			(r"/admin/api/edit",AdminApiEditHandler),
			(r"/admin/api/delete",AdminApiDeleteHandler),
			(r"/admin/api/test",AdminApiTestHandler),
			(r"/admin/api/service",AdminApiServiceHandler),

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
