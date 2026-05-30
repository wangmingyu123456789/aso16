import os
import sys
import traceback
import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado.httpserver import HTTPServer
from app.controllers.auth import LoginHandler,LogoutHandler,RegisterHandler
from app.controllers.home import IndexHandler,HomePageHandler
from app.controllers.admin.auth import AdminLoginHandler,AdminLogoutHandler
from app.controllers.admin.index import AdminIndexHandler
from app.controllers.admin.user import AdminUserListHandler,AdminUserApiHandler,AdminUserRolesApiHandler,AdminUserAddHandler,AdminUserEditHandler,AdminUserDeleteHandler,AdminUserBatchDeleteHandler
from app.controllers.admin.function import AdminFunctionListHandler,AdminFunctionApiHandler,AdminFunctionAddHandler,AdminFunctionEditHandler,AdminFunctionDeleteHandler,AdminFunctionTreeHandler
from app.controllers.admin.role import AdminRoleListHandler,AdminRoleApiHandler,AdminRoleAddHandler,AdminRoleEditHandler,AdminRoleDeleteHandler
from app.controllers.admin.permission import AdminPermissionListHandler,AdminPermissionTreeHandler,AdminPermissionSaveHandler
from app.controllers.admin.model import AdminModelListHandler,AdminModelApiHandler,AdminModelAddHandler,AdminModelEditHandler,AdminModelDeleteHandler,AdminModelSetDefaultHandler,AdminModelChatTestHandler,AdminModelChatStreamHandler
from app.controllers.admin.outlook import AdminOutlookRedirectHandler,AdminOutlookSourceListHandler,AdminOutlookSourceApiHandler,AdminOutlookSourceAddHandler,AdminOutlookSourceEditHandler,AdminOutlookSourceDeleteHandler,AdminOutlookCollectHandler,AdminOutlookDataListHandler,AdminOutlookDataApiHandler,AdminOutlookDataDeleteHandler,AdminOutlookCollectPageHandler,AdminOutlookTaskApiHandler,AdminOutlookTaskDeleteHandler,AdminOutlookTaskDataHandler,AdminOutlookTaskDataApiHandler,AdminOutlookLatestDataApiHandler,AdminOutlookStatusApiHandler,AdminOutlookDeepCollectHandler,AdminOutlookDeepCollectStatusHandler,AdminOutlookDeepDetailHandler
from app.controllers.admin.api_mgmt import AdminApiListHandler,AdminApiListApiHandler,AdminApiAddHandler,AdminApiEditHandler,AdminApiDeleteHandler,AdminApiTestHandler,AdminApiServiceHandler
from app.controllers.admin.watch import AdminCrawlLogHandler,AdminCrawlLogApiHandler,AdminCrawlScheduleHandler,AdminCrawlScheduleApiHandler,AdminCrawlLogClearHandler,AdminCrawlLogStatsHandler
from app.controllers.user.outlook import UserOutlookCollectPageHandler,UserOutlookCollectHandler,UserOutlookStatusApiHandler,UserOutlookLatestDataApiHandler,UserOutlookDataListHandler,UserOutlookDataApiHandler,UserOutlookTaskApiHandler,UserOutlookTaskDeleteHandler,UserOutlookTaskDataHandler,UserOutlookTaskDataApiHandler,UserOutlookDeepCollectHandler,UserOutlookDeepCollectStatusHandler,UserOutlookDeepDetailHandler,UserOutlookSourceApiHandler,UserOutlookSourceAddHandler,UserOutlookSourceEditHandler,UserOutlookSourceDeleteHandler,UserOutlookDataDeleteHandler,UserCrawlLogHandler,UserCrawlLogApiHandler,UserCrawlLogClearHandler,UserCrawlLogStatsHandler,UserCrawlScheduleHandler,UserCrawlScheduleApiHandler
from app.controllers.admin.assistant import AdminAssistantConfigHandler,AdminAssistantApiHandler,AdminAssistantChatHandler,AdminAssistantUsageHandler,AdminChatSendHandler,AdminChatHistoryHandler,AdminChatClearHandler
from app.controllers.admin.settings import AdminSettingsHandler
from app.controllers.admin.workflow import AdminWorkflowListHandler,AdminWorkflowEditHandler,AdminWorkflowApiHandler
from app.controllers.dashboard import DashboardPageHandler,UserDashboardPageHandler,DashboardStatsHandler
from app.controllers.user.sentiment import SentimentHandler,DashboardChartsHandler,SentimentStatsHandler,SentimentAnalyzeHandler,SentimentResultHandler,WordCloudHandler
from app.controllers.chat import ChatPageHandler,ChatStreamHandler,ChatAssistantsHandler,ChatHistoryHandler,ChatModelsHandler
from app.controllers.im import IMPageHandler,IMConversationsHandler,IMRestoreConversationHandler,IMHistoryHandler,IMSendHandler,IMCreatePrivateHandler,IMAssistantChatHandler,IMCreateGroupHandler,IMMembersHandler,IMUsersHandler,IMAssistantsHandler,IMSearchHandler,IMGlobalSearchHandler,IMMarkReadHandler,IMFriendsHandler,IMFriendRequestHandler,IMGroupInviteHandler,IMRemoveFriendHandler,IMGroupsHandler,IMGroupManageHandler as IMGroupManageOldHandler,IMFileUploadHandler,IMFileDownloadHandler,IMFilesHandler
from app.controllers.im_ws import IMWebSocketHandler
from app.controllers.im_group import IMGroupDetailHandler,IMGroupManageHandler,IMGroupAnnounceHandler,IMGroupDismissHandler,IMGroupLeaveHandler,IMGroupTransferHandler,IMGroupMemberSearchHandler,IMAnnounceUnconfirmedHandler,IMAnnounceConfirmHandler
from app.controllers.admin.im_files import AdminIMFilesHandler,AdminIMFilesApiHandler,AdminIMFilesDeleteHandler,AdminIMFilesStatsHandler
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
			(r"/auth/register",RegisterHandler),
			(r"/auth/logout",LogoutHandler),

			(r"/home",HomePageHandler),
			(r"/qa",ChatPageHandler),
			(r"/api/chat/stream",ChatStreamHandler),
			(r"/api/chat/history",ChatHistoryHandler),
			(r"/api/chat/models",ChatModelsHandler),
			(r"/api/chat/assistants",ChatAssistantsHandler),

			# 智能聊天
			(r"/im",IMPageHandler),
			(r"/im/ws",IMWebSocketHandler),
			(r"/im/api/conversations",IMConversationsHandler),
			(r"/im/api/conversations/restore",IMRestoreConversationHandler),
			(r"/im/api/history",IMHistoryHandler),
			(r"/im/api/send",IMSendHandler),
			(r"/im/api/private",IMCreatePrivateHandler),
			(r"/im/api/assistant-chat",IMAssistantChatHandler),
			(r"/im/api/group",IMCreateGroupHandler),
			(r"/im/api/members",IMMembersHandler),
			(r"/im/api/users",IMUsersHandler),
			(r"/im/api/assistants",IMAssistantsHandler),
			(r"/im/api/search",IMSearchHandler),
			(r"/im/api/global-search",IMGlobalSearchHandler),
			(r"/im/api/read",IMMarkReadHandler),
			(r"/im/api/friends",IMFriendsHandler),
			(r"/im/api/friend/request",IMFriendRequestHandler),
			(r"/im/api/group/invite",IMGroupInviteHandler),
			(r"/im/api/friend/remove",IMRemoveFriendHandler),
			(r"/im/api/groups",IMGroupsHandler),
			(r"/im/api/group/manage",IMGroupManageOldHandler),
		(r"/im/api/group/detail",IMGroupDetailHandler),
		(r"/im/api/group/manage2",IMGroupManageHandler),
		(r"/im/api/group/member/search",IMGroupMemberSearchHandler),
		(r"/im/api/group/announcement",IMGroupAnnounceHandler),
		(r"/im/api/group/dismiss",IMGroupDismissHandler),
		(r"/im/api/group/leave",IMGroupLeaveHandler),
		(r"/im/api/group/transfer",IMGroupTransferHandler),
		(r"/im/api/announcement/unconfirmed",IMAnnounceUnconfirmedHandler),
		(r"/im/api/announcement/confirm",IMAnnounceConfirmHandler),
		(r"/im/api/file/upload",IMFileUploadHandler),
		(r"/im/api/file/(.+)",IMFileDownloadHandler),
		(r"/im/api/files",IMFilesHandler),

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
			(r"/admin/outlook/deep/collect",AdminOutlookDeepCollectHandler),
			(r"/admin/outlook/deep/collect/status",AdminOutlookDeepCollectStatusHandler),
			(r"/admin/outlook/deep/detail",AdminOutlookDeepDetailHandler),

			# 接口管理
			(r"/admin/api",AdminApiListHandler),
			(r"/admin/api/list",AdminApiListApiHandler),
			(r"/admin/api/add",AdminApiAddHandler),
			(r"/admin/api/edit",AdminApiEditHandler),
			(r"/admin/api/delete",AdminApiDeleteHandler),
			(r"/admin/api/test",AdminApiTestHandler),
			(r"/admin/api/service",AdminApiServiceHandler),

			# 定时采集
			(r"/admin/outlook/log",AdminCrawlLogHandler),
			(r"/admin/outlook/log/api",AdminCrawlLogApiHandler),
			(r"/admin/outlook/log/clear",AdminCrawlLogClearHandler),
			(r"/admin/outlook/log/stats",AdminCrawlLogStatsHandler),
			(r"/admin/outlook/schedule",AdminCrawlScheduleHandler),
			(r"/admin/outlook/schedule/api",AdminCrawlScheduleApiHandler),

			# 数字员工
			(r"/admin/agent",AdminAssistantConfigHandler),
			(r"/admin/agent/chat",AdminAssistantChatHandler),
			(r"/admin/agent/usage",AdminAssistantUsageHandler),
			(r"/admin/assistant/api",AdminAssistantApiHandler),
			(r"/api/admin/chat/send",AdminChatSendHandler),

			# 聊天文件管理
			(r"/admin/im/files",AdminIMFilesHandler),
			(r"/admin/im/files/api",AdminIMFilesApiHandler),
			(r"/admin/im/files/delete",AdminIMFilesDeleteHandler),
			(r"/admin/im/files/stats",AdminIMFilesStatsHandler),

			# 设置
			(r"/api/admin/chat/history",AdminChatHistoryHandler),
			(r"/api/admin/chat/clear",AdminChatClearHandler),

			# 系统设置
			(r"/admin/settings",AdminSettingsHandler),

			# 自动化工作流
			(r"/admin/workflow",AdminWorkflowListHandler),
			(r"/admin/workflow/edit/?(\d*)",AdminWorkflowEditHandler),
			(r"/admin/workflow/api",AdminWorkflowApiHandler),

			# 数智大屏
			(r"/dashboard",DashboardPageHandler),
			(r"/user/dashboard",UserDashboardPageHandler),
			(r"/api/dashboard/stats",DashboardStatsHandler),

			# 用户侧-智慧舆情分析
			(r"/user/sentiment",SentimentHandler),
			(r"/api/dashboard/charts",DashboardChartsHandler),
			(r"/api/sentiment/stats",SentimentStatsHandler),
			(r"/api/sentiment/analyze",SentimentAnalyzeHandler),
			(r"/api/sentiment/result",SentimentResultHandler),
			(r"/api/wordcloud",WordCloudHandler),

			# 用户侧-瞭望系统
			(r"/user/outlook/collect",UserOutlookCollectPageHandler),
			(r"/user/outlook/collect/do",UserOutlookCollectHandler),
			(r"/user/outlook/status/api",UserOutlookStatusApiHandler),
			(r"/user/outlook/latest/data/api",UserOutlookLatestDataApiHandler),
			(r"/user/outlook/data",UserOutlookDataListHandler),
			(r"/user/outlook/data/api",UserOutlookDataApiHandler),
			(r"/user/outlook/data/delete",UserOutlookDataDeleteHandler),
			(r"/user/outlook/tasks/api",UserOutlookTaskApiHandler),
			(r"/user/outlook/task/data",UserOutlookTaskDataHandler),
			(r"/user/outlook/task/data/api",UserOutlookTaskDataApiHandler),
			(r"/user/outlook/task/delete",UserOutlookTaskDeleteHandler),
			(r"/user/outlook/deep/collect",UserOutlookDeepCollectHandler),
			(r"/user/outlook/deep/collect/status",UserOutlookDeepCollectStatusHandler),
			(r"/user/outlook/deep/detail",UserOutlookDeepDetailHandler),
			(r"/user/outlook/sources/api",UserOutlookSourceApiHandler),
			(r"/user/outlook/sources/add",UserOutlookSourceAddHandler),
			(r"/user/outlook/sources/edit",UserOutlookSourceEditHandler),
			(r"/user/outlook/sources/delete",UserOutlookSourceDeleteHandler),
			(r"/user/outlook/log",UserCrawlLogHandler),
			(r"/user/outlook/log/api",UserCrawlLogApiHandler),
			(r"/user/outlook/log/clear",UserCrawlLogClearHandler),
			(r"/user/outlook/log/stats",UserCrawlLogStatsHandler),
			(r"/user/outlook/schedule",UserCrawlScheduleHandler),
			(r"/user/outlook/schedule/api",UserCrawlScheduleApiHandler),

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
		from app.models import crawl_scheduler
		crawl_scheduler.start_scheduler()
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
