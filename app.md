# 智能瞭望与问数系统 - 项目架构说明

> 本文档描述项目的完整系统架构、目录结构、模块说明，用于指导AI完成开发任务。

---

## 一、项目概述

基于 **Python 3.10+ / Tornado / SQLite** 的 B/S 架构 Web 应用，采用 MVC 分层设计。

- **主框架**: Tornado 6.x (异步 Web 框架)
- **数据库**: SQLite3 (嵌入式，零配置)
- **前端 UI**: Layui 2.13.6 (管理侧) + 原生 HTML/CSS/JS (用户侧)
- **图表**: ECharts 5.x + Three.js (3D地球)
- **手势识别**: MediaPipe (21点手部关键点)
- **定时调度**: APScheduler 3.x
- **主端口**: 10086
- **天气服务端口**: 9877 (FastAPI 外部服务)
- **IM 集群节点**: 10081~10082 (可配置)

---

## 二、目录结构

```
cnAgentOS/
├── app.py                  # 主入口：Tornado 应用配置 + 路由注册 + 服务启动
├── run.py                  # 一键启动脚本（主服务 + 天气服务 + IM集群节点）
├── run_im_node.py          # IM节点独立启动脚本（支持被 run.py 调用）
├── text.py                 # 临时测试脚本
│
├── app/                    # 应用核心目录
│   ├── __init__.py
│   │
│   ├── controllers/        # 【控制层】HTTP 请求处理器
│   │   ├── __init__.py
│   │   ├── base.py                  # BaseHandler：用户侧基础类（cookie 登录态）
│   │   ├── auth.py                  # 用户认证：登录/注册/退出
│   │   ├── home.py                  # 首页跳转逻辑 + 用户侧首页
│   │   ├── chat.py                  # 智能问数：SSE 流式对话 / 历史 / 模型 / 数字员工
│   │   ├── dashboard.py             # 数智大屏页面 + 统计数据 API
│   │   ├── im.py                    # 智能聊天：会话/好友/群聊/文件/搜索等 API
│   │   ├── im_ws.py                 # WebSocket 实时通信（连接池/心跳/消息推送）
│   │   ├── im_group.py              # 群聊管理：详情/成员/公告/解散/转让
│   │   ├── im_server_api.py         # IM集群：用户节点分配 / 节点状态 API
│   │   ├── im_internal.py           # IM集群：节点间内部通信（消息转发/健康检查）
│   │   │
│   │   ├── admin/                   # 【管理侧控制器】
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # AdminBaseHandler：管理侧基础类（权限/菜单过滤）
│   │   │   ├── auth.py              # 管理员登录/退出
│   │   │   ├── index.py             # 管理后台首页
│   │   │   ├── user.py              # 用户管理（CRUD/批量删除）
│   │   │   ├── function.py          # 功能模块管理
│   │   │   ├── role.py              # 角色管理
│   │   │   ├── permission.py        # 权限分配（角色-功能绑定）
│   │   │   ├── model.py             # 模型引擎管理 + 流式对话测试
│   │   │   ├── outlook.py           # 瞭望采集/数据仓库/深度采集/数据源
│   │   │   ├── watch.py             # 采集日志 / 定时采集调度
│   │   │   ├── api_mgmt.py          # API 接口管理
│   │   │   ├── assistant.py         # 数字员工管理 / 管理侧对话
│   │   │   ├── im_files.py          # IM 文件管理
│   │   │   ├── settings.py          # 系统设置
│   │   │   └── workflow.py          # 自动化工作流管理
│   │   │
│   │   └── user/                    # 【用户侧控制器】
│   │       ├── __init__.py
│   │       ├── outlook.py           # 用户侧瞭望采集/数据仓库/深度采集/调度
│   │       └── sentiment.py         # 智慧舆情：图表/分析/词云
│   │
│   ├── models/             # 【模型层】数据库操作与业务逻辑
│   │   ├── __init__.py
│   │   ├── db.py                    # SQLite 连接管理 + 全部建表逻辑
│   │   ├── user.py                  # 用户数据操作（PBKDF2 密码加密）
│   │   ├── im.py                    # 即时通讯数据操作
│   │   ├── im_server.py             # IM集群：节点注册/发现/用户分配/消息投递
│   │   ├── outlook.py               # 瞭望采集：数据源/任务/数据/日志/调度 Repository
│   │   ├── model.py                 # 模型引擎操作
│   │   ├── assistant.py             # 数字员工操作
│   │   ├── api.py                   # API 接口管理操作
│   │   ├── permission.py            # 权限/功能/角色数据操作
│   │   ├── workflow.py              # 工作流数据操作
│   │   ├── crawl_scheduler.py       # APScheduler 定时采集调度器
│   │   └── watch_collector.py       # 采集器引擎（HTML 抓取/解析）
│   │
│   ├── templates/          # 【视图层-模板】HTML 模板文件
│   │   ├── base.html                # 基础布局模板
│   │   ├── login.html               # 管理侧登录（旧版，extends base.html）
│   │   ├── user_login.html          # 用户登录页（独立样式）
│   │   ├── register.html            # 注册页
│   │   ├── index.html               # 后台首页（旧版）
│   │   ├── home.html                # 用户侧首页（带左侧导航栏）
│   │   ├── chat.html                # 智能问数对话页
│   │   ├── im.html                  # 智能聊天主界面
│   │   │
│   │   ├── admin/                   # 【管理侧模板】
│   │   │   ├── layout.html          # 管理后台布局（侧边栏/顶栏/权限菜单）
│   │   │   ├── login.html           # 管理登录页（独立沉浸式风格）
│   │   │   ├── index.html           # 管理首页
│   │   │   ├── user_list.html       # 用户管理
│   │   │   ├── function_list.html   # 功能管理
│   │   │   ├── role_list.html       # 角色管理
│   │   │   ├── permission_list.html # 权限管理
│   │   │   ├── model_list.html      # 模型引擎
│   │   │   ├── assistant.html       # 数字员工
│   │   │   ├── assistant_usage.html # 助手使用统计
│   │   │   ├── agent_chat.html      # 管理侧数字员工对话
│   │   │   ├── outlook_collect.html # 瞭望采集
│   │   │   ├── outlook_source_list.html # 数据源管理
│   │   │   ├── outlook_data_list.html   # 数据仓库
│   │   │   ├── outlook_task_data.html   # 任务数据
│   │   │   ├── crawl_log.html       # 采集日志
│   │   │   ├── crawl_schedule.html  # 定时采集
│   │   │   ├── api_list.html        # 接口管理
│   │   │   ├── dashboard.html       # 数智大屏
│   │   │   ├── im_files.html        # IM文件管理
│   │   │   ├── settings.html        # 系统设置
│   │   │   ├── workflow_list.html   # 工作流列表
│   │   │   └── workflow_edit.html   # 工作流编辑
│   │   │
│   │   ├── user/                    # 【用户侧模板】
│   │   │   ├── layout.html          # 用户侧布局（侧边导航）
│   │   │   ├── dashboard.html       # 数智大屏
│   │   │   ├── sentiment.html       # 智慧舆情
│   │   │   ├── outlook_collect.html # 瞭望采集
│   │   │   ├── outlook_source_list.html # 数据源
│   │   │   ├── outlook_data_list.html   # 数据仓库
│   │   │   ├── outlook_task_data.html   # 任务数据
│   │   │   ├── crawl_log.html       # 采集日志
│   │   │   └── crawl_schedule.html  # 定时采集
│   │   │
│   │   └── components/              # 【公共组件】
│   │       └── gesture_panel.html   # 手势识别面板
│   │
│   └── static/              # 【静态资源】
│       ├── css/
│       │   ├── base.css             # 全局基础样式
│       │   └── theme.css            # 暗色主题变量
│       ├── js/
│       │   ├── base.js              # 全局基础脚本
│       │   ├── gesture.js           # 手势识别主入口
│       │   ├── gesture-rule-engine.js   # 手势规则引擎
│       │   ├── gesture-event-bus.js     # 手势事件总线
│       │   ├── gesture-feedback.js      # 手势视觉反馈
│       │   ├── gesture-settings.js      # 手势配置管理
│       │   └── voice-broadcast.js       # 语音播报
│       └── dist/                    # 第三方库
│           ├── layui-v2.13.6/
│           ├── bootstrap-5.3.8-dist/
│           └── fontawesome-free-5.15.4-web/
│
├── database/                # 【数据库目录】
│   └── app.db               # SQLite 数据库（运行时自动创建）
│
├── uploads/                 # 【上传文件目录】
│   └── im/                  # IM 聊天文件（按 UUID 子目录存储）
│
├── CToS/                    # 【CToS 子项目】FastAPI 后端 + 前端设计
│   ├── CToS2Back/           # FastAPI 后端（独立服务，端口 9877）
│   │   ├── app.py           # FastAPI 应用入口
│   │   ├── external.py      # 外部天气服务
│   │   ├── config.py        # 配置
│   │   ├── routers/         # 路由模块
│   │   ├── services/        # 业务服务
│   │   ├── tools/           # 工具函数
│   │   └── database/        # SQLAlchemy 模型
│   ├── CToS2Front/          # 前端设计
│   │   ├── frontend/        # 前端页面
│   │   └── gesture/         # 手势识别 Python 版
│   └── patch_files/         # Git patches
│
└── requirements.txt         # Python 依赖清单
```

---

## 三、路由总表

### 3.1 用户认证
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET/POST | `/auth/login` | LoginHandler | 用户登录 |
| GET/POST | `/auth/register` | RegisterHandler | 用户注册 |
| POST | `/auth/logout` | LogoutHandler | 退出登录 |

### 3.2 首页
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/` | IndexHandler | 根路径跳转（按角色跳转） |
| GET | `/home` | HomePageHandler | 用户侧首页 |

### 3.3 智能问数
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/qa` | ChatPageHandler | 问数页面 |
| POST | `/api/chat/stream` | ChatStreamHandler | SSE 流式对话 |
| GET/POST/DELETE | `/api/chat/history` | ChatHistoryHandler | 对话历史 |
| GET | `/api/chat/models` | ChatModelsHandler | 模型列表 |
| GET | `/api/chat/assistants` | ChatAssistantsHandler | 数字员工列表 |

### 3.4 智能聊天
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/im` | IMPageHandler | 聊天页面 |
| WS | `/im/ws` | IMWebSocketHandler | WebSocket 实时通信 |
| GET | `/im/api/conversations` | IMConversationsHandler | 会话列表 |
| POST | `/im/api/conversations/restore` | IMRestoreConversationHandler | 恢复会话 |
| POST | `/im/api/history` | IMHistoryHandler | 历史消息 |
| POST | `/im/api/send` | IMSendHandler | 发送消息 |
| POST | `/im/api/private` | IMCreatePrivateHandler | 创建私聊 |
| POST | `/im/api/assistant-chat` | IMAssistantChatHandler | 数字员工聊天 |
| POST | `/im/api/group` | IMCreateGroupHandler | 创建群聊 |
| GET | `/im/api/members` | IMMembersHandler | 群成员 |
| GET | `/im/api/users` | IMUsersHandler | 用户列表 |
| GET | `/im/api/assistants` | IMAssistantsHandler | 可用的数字员工 |
| GET | `/im/api/search` | IMSearchHandler | 搜索 |
| GET | `/im/api/global-search` | IMGlobalSearchHandler | 全局搜索 |
| POST | `/im/api/read` | IMMarkReadHandler | 标记已读 |
| GET | `/im/api/friends` | IMFriendsHandler | 好友列表 |
| POST | `/im/api/friend/request` | IMFriendRequestHandler | 好友申请 |
| POST | `/im/api/group/invite` | IMGroupInviteHandler | 邀请入群 |
| POST | `/im/api/friend/remove` | IMRemoveFriendHandler | 删除好友 |
| GET | `/im/api/groups` | IMGroupsHandler | 群聊列表 |
| POST | `/im/api/group/manage` | IMGroupManageOldHandler | 群管理 |

### 3.5 群聊管理
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/im/api/group/detail` | IMGroupDetailHandler | 群详情 |
| POST | `/im/api/group/manage2` | IMGroupManageHandler | 群管理（成员/信息） |
| GET | `/im/api/group/member/search` | IMGroupMemberSearchHandler | 搜索可邀请成员 |
| POST | `/im/api/group/announcement` | IMGroupAnnounceHandler | 群公告 |
| POST | `/im/api/group/dismiss` | IMGroupDismissHandler | 解散群 |
| POST | `/im/api/group/leave` | IMGroupLeaveHandler | 退群 |
| POST | `/im/api/group/transfer` | IMGroupTransferHandler | 转让群 |
| GET | `/im/api/announcement/unconfirmed` | IMAnnounceUnconfirmedHandler | 未确认公告 |
| POST | `/im/api/announcement/confirm` | IMAnnounceConfirmHandler | 确认公告 |

### 3.6 IM 文件
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| POST | `/im/api/file/upload` | IMFileUploadHandler | 上传文件 |
| GET | `/im/api/file/(.+)` | IMFileDownloadHandler | 下载文件 |
| GET | `/im/api/files` | IMFilesHandler | 文件列表 |
| POST | `/im/api/weather/callback` | WeatherCallbackHandler | 天气回调 |

### 3.7 IM 集群
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/im/api/assign_node` | AssignNodeHandler | 分配最优节点 |
| GET | `/im/api/nodes/status` | NodeStatusHandler | 节点状态 |

### 3.8 IM 内部通信
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| POST | `/internal/send` | InternalSendHandler | 跨节点消息转发 |
| GET | `/internal/health` | InternalHealthHandler | 健康检查 |
| POST | `/internal/batch-check` | InternalBatchUserCheckHandler | 批量用户检查 |

### 3.9 管理后台
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET/POST | `/admin/login` | AdminLoginHandler | 管理员登录 |
| POST | `/admin/logout` | AdminLogoutHandler | 管理员退出 |
| GET | `/admin` | AdminIndexHandler | 管理后台首页 |
| GET/POST | `/admin/users` | AdminUserListHandler | 用户列表 |
| GET/POST | `/admin/users/api` | AdminUserApiHandler | 用户API |
| GET | `/admin/users/roles_api` | AdminUserRolesApiHandler | 用户角色API |
| POST | `/admin/users/add` | AdminUserAddHandler | 新增用户 |
| POST | `/admin/users/edit` | AdminUserEditHandler | 编辑用户 |
| POST | `/admin/users/delete` | AdminUserDeleteHandler | 删除用户 |
| POST | `/admin/users/batch_delete` | AdminUserBatchDeleteHandler | 批量删除 |

### 3.10 功能管理
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/admin/functions` | AdminFunctionListHandler | 功能管理页 |
| GET | `/admin/functions/api` | AdminFunctionApiHandler | 功能API |
| POST | `/admin/functions/add` | AdminFunctionAddHandler | 新增功能 |
| POST | `/admin/functions/edit` | AdminFunctionEditHandler | 编辑功能 |
| POST | `/admin/functions/delete` | AdminFunctionDeleteHandler | 删除功能 |
| GET | `/admin/functions/tree` | AdminFunctionTreeHandler | 功能树 |

### 3.11 角色管理
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/admin/roles` | AdminRoleListHandler | 角色管理页 |
| GET | `/admin/roles/api` | AdminRoleApiHandler | 角色API |
| POST | `/admin/roles/add` | AdminRoleAddHandler | 新增角色 |
| POST | `/admin/roles/edit` | AdminRoleEditHandler | 编辑角色 |
| POST | `/admin/roles/delete` | AdminRoleDeleteHandler | 删除角色 |

### 3.12 权限管理
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/admin/permissions` | AdminPermissionListHandler | 权限管理页 |
| GET | `/admin/permissions/tree` | AdminPermissionTreeHandler | 权限树 |
| POST | `/admin/permissions/save` | AdminPermissionSaveHandler | 保存权限 |

### 3.13 模型引擎
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/admin/models` | AdminModelListHandler | 模型管理页 |
| GET | `/admin/models/api` | AdminModelApiHandler | 模型API |
| POST | `/admin/models/add` | AdminModelAddHandler | 新增模型 |
| POST | `/admin/models/edit` | AdminModelEditHandler | 编辑模型 |
| POST | `/admin/models/delete` | AdminModelDeleteHandler | 删除模型 |
| POST | `/admin/models/set_default` | AdminModelSetDefaultHandler | 设默认模型 |
| POST | `/admin/models/chat_test` | AdminModelChatTestHandler | 对话测试 |
| GET | `/admin/models/chat_stream` | AdminModelChatStreamHandler | 流式对话测试 |

### 3.14 瞭望采集
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/admin/outlook` | AdminOutlookCollectPageHandler | 采集页 |
| GET | `/admin/outlook/sources` | AdminOutlookSourceListHandler | 数据源列表 |
| GET | `/admin/outlook/sources/api` | AdminOutlookSourceApiHandler | 数据源API |
| POST | `/admin/outlook/sources/add` | AdminOutlookSourceAddHandler | 新增数据源 |
| POST | `/admin/outlook/sources/edit` | AdminOutlookSourceEditHandler | 编辑数据源 |
| POST | `/admin/outlook/sources/delete` | AdminOutlookSourceDeleteHandler | 删除数据源 |
| POST | `/admin/outlook/collect/do` | AdminOutlookCollectHandler | 执行采集 |
| GET | `/admin/outlook/data` | AdminOutlookDataListHandler | 数据仓库 |
| GET | `/admin/outlook/data/api` | AdminOutlookDataApiHandler | 数据API |
| POST | `/admin/outlook/data/delete` | AdminOutlookDataDeleteHandler | 删除数据 |
| GET | `/admin/outlook/tasks/api` | AdminOutlookTaskApiHandler | 任务API |
| GET | `/admin/outlook/task/data` | AdminOutlookTaskDataHandler | 任务数据页 |
| GET | `/admin/outlook/task/data/api` | AdminOutlookTaskDataApiHandler | 任务数据API |
| POST | `/admin/outlook/task/delete` | AdminOutlookTaskDeleteHandler | 删除任务 |
| GET | `/admin/outlook/latest/data/api` | AdminOutlookLatestDataApiHandler | 最新数据API |
| GET | `/admin/outlook/status/api` | AdminOutlookStatusApiHandler | 状态API |
| POST | `/admin/outlook/deep/collect` | AdminOutlookDeepCollectHandler | 深度采集 |
| GET | `/admin/outlook/deep/collect/status` | AdminOutlookDeepCollectStatusHandler | 深度采集状态 |
| GET | `/admin/outlook/deep/detail` | AdminOutlookDeepDetailHandler | 深度详情 |
| GET | `/admin/outlook/log` | AdminCrawlLogHandler | 采集日志页 |
| GET | `/admin/outlook/log/api` | AdminCrawlLogApiHandler | 日志API |
| POST | `/admin/outlook/log/clear` | AdminCrawlLogClearHandler | 清空日志 |
| GET | `/admin/outlook/log/stats` | AdminCrawlLogStatsHandler | 日志统计 |
| GET | `/admin/outlook/schedule` | AdminCrawlScheduleHandler | 定时采集页 |
| GET/POST | `/admin/outlook/schedule/api` | AdminCrawlScheduleApiHandler | 定时采集API |

### 3.15 接口管理
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/admin/api` | AdminApiListHandler | 接口管理页 |
| GET | `/admin/api/list` | AdminApiListApiHandler | 接口列表API |
| POST | `/admin/api/add` | AdminApiAddHandler | 新增接口 |
| POST | `/admin/api/edit` | AdminApiEditHandler | 编辑接口 |
| POST | `/admin/api/delete` | AdminApiDeleteHandler | 删除接口 |
| POST | `/admin/api/test` | AdminApiTestHandler | 接口测试 |
| GET | `/admin/api/service` | AdminApiServiceHandler | 接口服务 |

### 3.16 数字员工
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/admin/agent` | AdminAssistantConfigHandler | 数字员工管理页 |
| GET | `/admin/agent/chat` | AdminAssistantChatHandler | 管理侧对话页 |
| GET | `/admin/agent/usage` | AdminAssistantUsageHandler | 使用统计页 |
| GET/POST | `/admin/assistant/api` | AdminAssistantApiHandler | 数字员工API |
| POST | `/api/admin/chat/send` | AdminChatSendHandler | 发送消息 |
| GET | `/api/admin/chat/history` | AdminChatHistoryHandler | 对话历史 |
| POST | `/api/admin/chat/clear` | AdminChatClearHandler | 清空对话 |

### 3.17 IM 文件管理
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/admin/im/files` | AdminIMFilesHandler | 文件管理页 |
| GET | `/admin/im/files/api` | AdminIMFilesApiHandler | 文件API |
| POST | `/admin/im/files/delete` | AdminIMFilesDeleteHandler | 删除文件 |
| GET | `/admin/im/files/stats` | AdminIMFilesStatsHandler | 文件统计 |

### 3.18 系统设置
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET/POST | `/admin/settings` | AdminSettingsHandler | 系统设置 |

### 3.19 自动化工作流
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/admin/workflow` | AdminWorkflowListHandler | 工作流列表 |
| GET | `/admin/workflow/edit` | AdminWorkflowEditHandler | 工作流编辑 |
| GET/POST | `/admin/workflow/api` | AdminWorkflowApiHandler | 工作流API |

### 3.20 数智大屏
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/dashboard` | DashboardPageHandler | 管理侧大屏 |
| GET | `/user/dashboard` | UserDashboardPageHandler | 用户侧大屏 |
| GET | `/api/dashboard/stats` | DashboardStatsHandler | 统计数据API |

### 3.21 智慧舆情
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/user/sentiment` | SentimentHandler | 舆情页面 |
| GET | `/api/dashboard/charts` | DashboardChartsHandler | 图表数据 |
| GET | `/api/sentiment/stats` | SentimentStatsHandler | 统计数据 |
| POST | `/api/sentiment/analyze` | SentimentAnalyzeHandler | 发起分析 |
| GET | `/api/sentiment/result` | SentimentResultHandler | 分析结果 |
| GET | `/api/wordcloud` | WordCloudHandler | 词云数据 |

### 3.22 用户侧瞭望
| 方法 | URL | Handler | 说明 |
|------|-----|---------|------|
| GET | `/user/outlook/collect` | UserOutlookCollectPageHandler | 采集页 |
| POST | `/user/outlook/collect/do` | UserOutlookCollectHandler | 执行采集 |
| GET | `/user/outlook/status/api` | UserOutlookStatusApiHandler | 状态API |
| GET | `/user/outlook/latest/data/api` | UserOutlookLatestDataApiHandler | 最新数据 |
| GET | `/user/outlook/data` | UserOutlookDataListHandler | 数据仓库 |
| + 20+ 个用户侧瞭望相关 API | ... | ... | ... |

---

## 四、数据库核心表

| 表名 | 说明 |
|------|------|
| `users` | 用户表（PBKDF2 加密密码） |
| `functions` | 功能模块表（二级层级） |
| `roles` | 角色表 |
| `role_functions` | 角色-功能映射表 |
| `outlook_sources` | 瞭望数据源配置 |
| `outlook_data` | 瞭望采集数据 |
| `outlook_tasks` | 采集任务记录 |
| `crawl_logs` | 采集日志 |
| `crawl_schedules` | 定时采集任务 |
| `models` | 模型配置 |
| `assistants` | 数字员工配置 |
| `assistant_calls` | 数字员工调用统计 |
| `im_conversations` | IM 会话 |
| `im_messages` | IM 消息 |
| `im_conversation_members` | 会话成员 |
| `im_friends` | 好友关系 |
| `im_friend_requests` | 好友申请 |
| `im_group_members` | 群成员 |
| `im_group_announcements` | 群公告 |
| `im_group_announce_confirm` | 公告确认 |
| `im_conv_aggregates` | 会话聚合（未读数等） |
| `im_files` | IM 文件记录 |
| `im_server_nodes` | IM 集群节点注册表 |
| `im_user_node_map` | 用户-节点映射表 |
| `im_message_delivery` | 跨节点消息投递记录 |
| `api_interfaces` | API 接口配置 |
| `api_call_logs` | API 调用日志 |
| `settings` | 系统设置 |
| `workflows` | 工作流配置 |
| `workflow_steps` | 工作流步骤 |
| `workflow_executions` | 工作流执行记录 |
| `workflow_step_logs` | 工作流步骤日志 |
| `wordcloud_cache` | 词云缓存 |

---

## 五、技术栈详情

| 类别 | 技术 | 版本 | 用途 |
|------|------|------|------|
| Web框架 | Tornado | 6.x | 主 HTTP + WebSocket 服务 |
| 数据库 | SQLite3 | 内置 | 嵌入式关系数据库 |
| 前端UI | Layui | 2.13.6 | 管理后台界面 |
| 前端UI | Bootstrap | 5.3.8 | 响应式布局 |
| 图标库 | Font Awesome | 5.15.4 | 图标 |
| 图表 | ECharts | 5.x | 数据可视化 |
| 3D渲染 | Three.js | 0.150+ | 3D地球展示 |
| 词云 | WordCloud | 1.9+ | 词云生成 |
| 图像处理 | OpenCV + Pillow | 4.8+ / 10+ | 词云生成 |
| 手势识别 | MediaPipe | 0.10+ | 21点手部关键点检测 |
| 定时调度 | APScheduler | 3.10+ | 定时采集 + 工作流调度 |
| HTTP客户端 | httpx | 0.28+ | 模型API调用 + 数据采集 |
| HTML解析 | lxml | 6.1+ | 数据采集解析 |
| 外部服务 | FastAPI | - | 天气服务 (端口9877) |
| 流式响应 | SSE | - | AI对话流式输出 |
| 实时通信 | WebSocket | - | IM 聊天 |

---

## 六、IM 集群架构

系统支持多 IM 服务器节点，实现高可用和负载均衡：

```
用户 → 分配节点 (/im/api/assign_node) → 获取最优节点地址
      → 连接 WebSocket 到指定节点
      → 跨节点消息通过 /internal/send 转发

节点注册:  每节点启动时写入 im_server_nodes 表
节点心跳:  每5秒更新 last_heartbeat
节点故障:  15秒无心跳自动标记离线
用户分配:  粘性策略（绑定后持续使用）+ 负载感知（新用户选最低负载）
并发安全:  SQLite WAL模式 + client_msg_id 幂等 + 短事务
```

---

## 七、安全机制

- **密码加密**: PBKDF2-HMAC-SHA256 (100,000 次迭代 + 16字节随机 Salt)
- **登录态**: Secure Cookie（`username` / `admin_username`）
- **CSRF 防护**: Tornado XSRF Cookie
- **认证装饰器**: `@tornado.web.authenticated` 强制登录
- **权限过滤**: 管理侧菜单树按角色-功能权限动态过滤
- **管理侧认证**: `AdminBaseHandler.get_current_user()` 验证 `admin_username`
- **用户侧认证**: `BaseHandler.get_current_user()` 验证 `username`
- **路由保护**: 所有业务 Handler 均需继承认证基类
