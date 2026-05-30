# CToS 后端 API 接口文档

> **文档版本**: 2.0.0  
> **最后更新**: 2026-05-29  
> **基础路径**: `http://localhost:8000`  
> **认证方式**: Bearer Token（登录后获取，放在 `Authorization` 请求头）  
> **响应格式**: 所有接口返回统一结构 `{ "code": 200, "message": "...", "data": {...} }`
> **OpenAPI 文档**: 服务启动后访问 `http://localhost:8000/docs`（Swagger UI）或 `http://localhost:8000/redoc`

---

## 目录

1. [通用说明](#通用说明)
   - [响应格式](#响应格式)
   - [分页响应格式](#分页响应格式)
   - [认证方式](#认证方式)
   - [错误码说明](#错误码说明)
   - [调用限制](#调用限制)
   - [接口版本化策略](#接口版本化策略)
   - [跨域说明](#跨域说明)
2. [认证模块 Auth](#1-认证模块-auth)
3. [智能问数 Chat](#2-智能问数-chat)
4. [智能瞭望 Watch](#3-智能瞭望-watch)
5. [数字员工 Workers](#4-数字员工-workers)
6. [派遣执行 Dispatch](#5-派遣执行-dispatch)
7. [数据清洗 Cleaning](#6-数据清洗-cleaning)
8. [知识仓库 Warehouse](#7-知识仓库-warehouse)
9. [智慧舆情 Sentiment](#8-智慧舆情-sentiment)
10. [数字大屏 Dashboard](#9-数字大屏-dashboard)
11. [系统管理 Admin](#10-系统管理-admin)
12. [智能聊天 IM](#11-智能聊天-im)
13. [WebSocket 推送](#12-websocket-推送)
14. [内部 API Internal](#13-内部-api-internal)
15. [附录：接口统计](#附录接口统计)

---

## 通用说明

### 响应格式

```json
// 成功
{ "code": 200, "message": "操作成功", "data": { ... } }

// 失败
{ "code": 4xx/5xx, "message": "错误描述", "data": null }
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| code | int | 状态码（200 成功，4xx 客户端错误，5xx 服务端错误） |
| message | string | 提示信息 |
| data | object/array/null | 业务数据 |

### 分页响应格式

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [ ... ],       // 数据列表
    "total": 100,           // 总记录数
    "page": 1,              // 当前页码
    "page_size": 20,        // 每页条数
    "total_pages": 5        // 总页数
  }
}
```

### 认证方式

除登录/注册外，所有接口需要在请求头添加：
```
Authorization: Bearer <token>
```

部分文件下载接口也支持通过 URL 查询参数传递 Token（用于 `<img>`、`<a>` 等原生标签）：
```
/xxx?token=<JWT>
```

**Token 获取**: 调用 `POST /api/auth/login` 获取 JWT Token。

### 错误码说明

| code | 说明 | 处理方式 |
|------|------|---------|
| 200 | 操作成功 | — |
| 400 | 请求参数错误 | 检查请求体/查询参数 |
| 401 | 未认证或 Token 过期 | 重新登录获取 Token |
| 403 | 权限不足（需 admin 角色） | 确认用户权限 |
| 404 | 资源不存在 | 检查资源 ID 是否正确 |
| 409 | 资源冲突（如用户名已存在） | 修改请求后重试 |
| 422 | 请求参数校验失败 | 检查参数类型和格式 |
| 429 | 请求频率过高 | 等待后重试 |
| 500 | 服务器内部错误 | 联系管理员 |

### 调用限制

- **请求体大小限制**: 默认 10MB（受 `MAX_FILE_SIZE` 环境变量控制）
- **文件上传**: 单文件最大 10MB，支持所有 MIME 类型
- **流式接口超时**: SSE 流式聊天接口（`POST /api/chat/message`）无硬超时限制，建议客户端设置 60s 超时
- **并发建议**: HTTP/1.1 下单域名最多 6 个并发连接；服务端建议使用 HTTP/2 获取更好的多路复用性能

### 接口版本化策略

当前使用隐式版本化策略：

| 方式 | 说明 | 示例 |
|------|------|------|
| 路径前缀 | 所有接口以 `/api/` 为前缀 | `/api/auth/login` |
| 后续版本 | 如需版本化，将在路径中追加版本号 | `/api/v2/auth/login` |
| 兼容性 | 同一主版本号下保持向后兼容 | — |

> 所有外部调用方应使用 `/api/` 前缀路径，并订阅文档更新通知以跟踪接口变更。

### 跨域说明

- 默认允许所有来源（`CORS_ORIGINS=*`），生产环境应配置为具体的域名白名单
- 允许所有 HTTP 方法和请求头

---

## 1. 认证模块 Auth

**前缀**: `/api/auth`  
**认证**: 登录/注册无需认证，其余需要 Bearer Token

### POST `/api/auth/login` — 登录

**请求体**:
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | ✅ | 用户名 |
| password | string | ✅ | 密码 |

**响应 data**:
```json
{
  "token": "jwt_token_string",
  "user": {
    "id": 1,
    "username": "admin",
    "nickname": "管理员",
    "avatar": "",
    "role": "admin"
  }
}
```

### POST `/api/auth/register` — 注册

**请求体**:
| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| username | string | ✅ | — | 用户名（唯一） |
| password | string | ✅ | — | 密码（至少6位） |
| nickname | string | ❌ | "" | 昵称 |

**注意**: 当系统配置 `disable_register=true` 时，注册接口返回 400 错误。

**响应 data**: `{ "username": "xxx" }`

### GET `/api/auth/me` — 获取当前用户信息

**请求头**: Authorization  
**响应 data**:
```json
{
  "id": 1,
  "username": "admin",
  "nickname": "管理员",
  "avatar": "",
  "role": "admin"
}
```

### POST `/api/auth/logout` — 退出登录

**请求头**: Authorization  
**说明**: JWT 为无状态 Token，后端仅做确认响应，客户端清除本地 Token 即可。

---

## 2. 智能问数 Chat

**前缀**: `/api/chat`

### GET `/api/chat/conversations` — 对话列表

**响应 data** (数组):
```json
[{
  "id": 1,
  "title": "新对话",
  "model_name": "gpt-4o-mini",
  "created_at": "2026-05-26T12:00:00",
  "updated_at": "2026-05-26T12:30:00"
}]
```

### POST `/api/chat/conversations` — 创建对话

**请求体**: `{ "title": "新对话" }`  
**响应 data**: `{ "id": 1, "title": "新对话" }`

### DELETE `/api/chat/conversation/{conv_id}` — 删除对话

**路径参数**: `conv_id` (int) — 对话 ID

### PUT `/api/chat/conversation/{conv_id}` — 重命名对话

**请求体**: `{ "title": "新标题" }`

### GET `/api/chat/conversations/{conv_id}/messages` — 历史消息

**响应 data** (数组):
```json
[{
  "id": 1,
  "role": "user",
  "content": "你好",
  "created_at": "2026-05-26T12:00:00"
}]
```

### POST `/api/chat/conversations/{conv_id}/messages` — 发送消息（非流式）

**请求体**: `{ "content": "你好" }`  
**说明**: 直接发送用户消息到指定对话，适用于不需要 AI 回复的场景。

### POST `/api/chat/message` — 发送消息（SSE 流式）

**请求体**: `{ "content": "你好", "conversation_id": 1 }`  
**响应**: SSE (Server-Sent Events) 流式输出，逐 token 推送。最后一个 chunk 包含 `_meta` 信息。  
**前置条件**: 系统需已配置有效的 LLM API Key（如 OpenAI）。

### POST `/api/chat/message/stop` — 中断流式

**请求体**: `{ "conversation_id": 1 }`  
**说明**: 中断正在进行中的 SSE 流式 AI 回复。

**流式消息格式**:
```
data: {"token": "你好"}
data: {"token": "，"}
data: {"token": "今天"}
data: {"token": "天气"}
data: {"token": "不错"}
data: {"_meta": {"conversation_id": 1, "model": "gpt-4o-mini", "usage": {"prompt_tokens": 10, "completion_tokens": 5}}}
```

---

## 3. 智能瞭望 Watch

**前缀**: `/api/watch`

### GET `/api/watch/sources` — 瞭望源列表

**响应 data** (数组):
```json
[{
  "id": 1, "name": "新浪财经", "url": "https://...",
  "method": "GET", "headers": "{}", "body_template": null,
  "interval_seconds": 3600, "enabled": 1,
  "created_at": "...", "updated_at": "..."
}]
```

### POST `/api/watch/sources` — 创建瞭望源

**请求体**:
| 字段 | 类型 | 必填 | 默认 |
|------|------|------|------|
| name | string | ✅ | — |
| url | string | ✅ | — |
| method | string | ❌ | "GET" |
| headers | string(JSON) | ❌ | "{}" |
| body_template | string | ❌ | "" |
| interval_seconds | int | ❌ | 3600 |

**响应 data**: `{ "id": 1 }`

### GET `/api/watch/sources/{source_id}` — 瞭望源详情

### PUT `/api/watch/sources/{source_id}` — 编辑瞭望源

**请求体**: 同创建（字段均可选）

### DELETE `/api/watch/sources/{source_id}` — 删除瞭望源

### POST `/api/watch/sources/{source_id}/trigger` — 手动采集

**响应 data**:
```json
{
  "id": 1,
  "status": "success",
  "raw_response": "(截断前500字符)"
}
```

### GET `/api/watch/sources/{source_id}/data` — 采集历史

**查询参数**: `limit=20`  
**响应 data** (数组):
```json
[{
  "id": 1, "source_id": 1, "status": "success",
  "raw_response": "(截断10000字符)",
  "parsed_data": "{...}",
  "http_status": 200,
  "collected_at": "..."
}]
```

### GET `/api/watch/data/{data_id}` — 采集数据详情

### POST `/api/watch/export/{source_id}` — 导出 JSON

**查询参数**: `limit=100`

---

## 4. 数字员工 Workers

**前缀**: `/api/workers`

### 4.1 工作管理 (Jobs)

#### GET `/api/workers/jobs` — 工作列表

**响应 data** (数组):
```json
[{
  "id": 1, "name": "数据清洗", "code": "data_cleaner",
  "description": "...", "icon": "🧹",
  "tool_names": "[\"extract_structural_info\",...]",
  "is_preset": 1
}]
```

#### POST `/api/workers/jobs` — 创建工作

**请求体**:
| 字段 | 类型 | 必填 | 默认 |
|------|------|------|------|
| name | string | ✅ | — |
| code | string | ✅ | — |
| description | string | ❌ | "" |
| icon | string | ❌ | "🤖" |
| prompt_template | string | ❌ | "" |
| tool_names | string(JSON) | ❌ | "[]" |
| sort_order | int | ❌ | 0 |

#### GET `/api/workers/jobs/{job_id}` — 工作详情

#### PUT `/api/workers/jobs/{job_id}` — 编辑工作

#### DELETE `/api/workers/jobs/{job_id}` — 删除工作

**注意**: 预设工作（`is_preset=1`）不可删除。

### 4.2 员工管理 (Workers)

#### GET `/api/workers` — 员工列表

**响应 data** (数组):
```json
[{
  "id": 1, "name": "助手", "icon": "🤖",
  "description": "", "job_id": 1, "enabled": 1
}]
```

#### POST `/api/workers` — 创建员工

**请求体**:
| 字段 | 类型 | 必填 | 默认 |
|------|------|------|------|
| job_id | int | ✅ | — |
| name | string | ✅ | — |
| icon | string | ❌ | "🤖" |
| description | string | ❌ | "" |
| system_prompt | string | ❌ | "" |
| api_key_id | int | ❌ | null |

#### GET `/api/workers/{worker_id}` — 员工详情

**响应 data**:
```json
{
  "id": 1, "name": "...", "icon": "...", "job_id": 1,
  "job_name": "数据清洗", "system_prompt": "...",
  "api_key_id": 1, "enabled": 1, "is_preset": 0,
  "created_at": "..."
}
```

#### PUT `/api/workers/{worker_id}` — 编辑员工

#### DELETE `/api/workers/{worker_id}` — 删除员工

**注意**: 预设员工（`is_preset=1`）不可删除。

#### PUT `/api/workers/{worker_id}/toggle` — 启用/禁用

### 4.3 任务执行

#### POST `/api/workers/{worker_id}/execute` — 执行任务

**请求体**: `{ "user_query": "..." }`  
**响应 data**: `{ "execution_id": 1 }`

#### GET `/api/workers/executions/{execution_id}` — 执行详情

**响应 data**:
```json
{
  "id": 1, "status": "success",
  "user_query": "...", "final_response": "...",
  "tokens_used": 100,
  "messages": [{ "role": "system", "content": "...", "tool_calls_json": null }],
  "created_at": "..."
}
```

### 4.4 工具管理

#### POST `/api/workers/tools` — 注册工具

**请求体**:
| 字段 | 类型 | 必填 |
|------|------|------|
| name | string | ✅ |
| description | string | ❌ |
| function_schema | string(JSON) | ❌ |
| module_path | string | ❌ |

---

## 5. 派遣执行 Dispatch

**前缀**: `/api/dispatch`

### POST `/api/dispatch/execute` — 派遣员工执行

**请求体**:
| 字段 | 类型 | 必填 |
|------|------|------|
| worker_id | int | ✅ |
| query | string | ✅ |

**响应 data**:
```json
{
  "execution_log_id": 1,
  "worker_id": 1,
  "worker_name": "助手",
  "query": "...",
  "status": "processing",
  "created_at": "..."
}
```

### GET `/api/dispatch/logs` — 执行记录列表

**查询参数**: `page=1&page_size=20&worker_id=&status=`  
**响应**: 分页格式

### GET `/api/dispatch/logs/{log_id}` — 执行记录详情

**响应 data**:
```json
{
  "id": 1, "worker_id": 1, "worker_name": "...",
  "job_name": "...", "user_query": "...",
  "final_response": "...", "status": "success",
  "tokens_used": 100,
  "cleaning_log_id": null, "sentiment_analysis_id": null,
  "messages": [{ "role": "system", "content": "...", "tool_calls_json": null, "tool_call_id": null }],
  "created_at": "...", "updated_at": "..."
}
```

### PUT `/api/dispatch/logs/{log_id}` — 更新执行记录

**请求体**: `{ "status": "success", "final_response": "...", "tokens_used": 100 }`

### DELETE `/api/dispatch/logs/{log_id}` — 删除执行记录

**说明**: 级联删除关联的执行消息（通过外键 `ondelete="CASCADE"`）。

### POST `/api/dispatch/messages` — 创建执行消息

**请求体**:
| 字段 | 类型 | 必填 |
|------|------|------|
| execution_log_id | int | ✅ |
| role | string | ✅ |
| content | string | ❌ |
| tool_calls_json | string(JSON) | ❌ |
| tool_call_id | string | ❌ |

### GET `/api/dispatch/workers/{worker_id}/stats` — 员工执行统计

**响应 data**:
```json
{
  "worker_id": 1,
  "total_executions": 10,
  "success_count": 8,
  "error_count": 2,
  "total_tokens_used": 5000
}
```

### GET `/api/dispatch/tools` — 可用工具列表

**响应 data** (数组):
```json
[{
  "id": 1, "name": "execute_python",
  "description": "...",
  "function_schema": "{...}",
  "is_builtin": 1
}]
```

---

## 6. 数据清洗 Cleaning

**前缀**: `/api/cleaning`

### GET `/api/cleaning/logs` — 清洗日志列表

**查询参数**: `page=1&page_size=20&status=&watch_data_id=`  
**响应** (分页格式):
```json
{
  "items": [{
    "id": 1, "watch_data_id": 1,
    "method": "ai", "status": "success",
    "result": "{\"title\":\"...\",\"content\":\"...\",\"domain_name\":\"...\"}",
    "error_message": null,
    "created_at": "..."
  }],
  "total": 50, "page": 1, "page_size": 20, "total_pages": 3
}
```

### POST `/api/cleaning/start` — 启动清洗

**请求体**:
| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| watch_data_ids | [int] | ✅ | — | 瞭望数据 ID 列表 |
| method | string | ❌ | "ai" | "ai" 或 "regex" |
| worker_id | int | ❌ | null | AI 清洗时必填 |

**响应 data** (数组):
```json
[{
  "id": 1,
  "watch_data_id": 1,
  "method": "ai",
  "status": "processing",
  "execution_log_id": 1
}]
```

> **注意**: AI 清洗在后台执行，前端需轮询日志状态。

### GET `/api/cleaning/logs/{log_id}` — 清洗日志详情

**响应 data**:
```json
{
  "id": 1, "watch_data_id": 1,
  "watch_data_raw": "(原始数据前500字符)",
  "watch_data_parsed": null,
  "method": "ai", "status": "success",
  "result": "{...}",
  "error_message": null,
  "execution_log_id": 1,
  "execution_status": "success",
  "article_id": 1,
  "article_title": "清洗后的文章标题",
  "created_at": "..."
}
```

### POST `/api/cleaning/logs/{log_id}/retry` — 重新清洗

### POST `/api/cleaning/logs/{log_id}/result` — 更新清洗结果

**请求参数**: `result` (string, query parameter)

### GET `/api/cleaning/stats` — 清洗统计

**响应 data**: `{ "total": 50, "success": 40, "failed": 5, "processing": 5 }`

### GET `/api/cleaning/tools` — 可用清洗工具列表

**响应 data** (数组):
```json
[{
  "name": "extract_structural_info",
  "description": "函数文档字符串",
  "module": "tools.cleaning_tools"
}]
```

---

## 7. 知识仓库 Warehouse

**前缀**: `/api/warehouse`

### 7.1 分类管理

#### GET `/api/warehouse/categories` — 分类列表

**响应 data** (数组):
```json
[{
  "id": 1, "name": "科技", "description": "...",
  "icon": "📁", "sort_order": 0
}]
```

#### POST `/api/warehouse/categories` — 创建分类

**请求体**: `{ "name": "科技", "description": "", "icon": "📁" }`

#### PUT `/api/warehouse/categories/{category_id}` — 编辑分类

#### DELETE `/api/warehouse/categories/{category_id}` — 删除分类

### 7.2 文章管理

#### GET `/api/warehouse/articles` — 文章列表

**查询参数**: `page=1&page_size=20&category_id=&status=&q=`  
**响应** (分页格式):
```json
{
  "items": [{
    "id": 1, "category_id": 1, "category_name": "科技",
    "title": "文章标题",
    "domain_name": "example.com",
    "content": "(前200字符)",
    "tags": "tag1,tag2",
    "url": "https://...",
    "status": "published",
    "created_at": "...", "updated_at": "..."
  }]
}
```

#### POST `/api/warehouse/articles` — 创建文章

**请求体**: 
| 字段 | 类型 | 必填 | 默认 |
|------|------|------|------|
| title | string | ✅ | — |
| content | string | ✅ | — |
| category_id | int | ❌ | null |
| domain_name | string | ❌ | "" |
| tags | string | ❌ | "" |
| url | string | ❌ | "" |
| status | string | ❌ | "draft" |

#### GET `/api/warehouse/articles/{article_id}` — 文章详情

#### PUT `/api/warehouse/articles/{article_id}` — 编辑文章

**请求体**: 同创建（全部可选），额外支持 `status` 切换 "draft"/"published"

#### DELETE `/api/warehouse/articles/{article_id}` — 删除文章

### 7.3 统计与域名

#### GET `/api/warehouse/stats` — 统计信息

**响应 data**:
```json
{
  "total_articles": 100,
  "draft_count": 30,
  "published_count": 70,
  "today_count": 5,
  "domain_distribution": { "example.com": 50, "test.com": 30 }
}
```

#### GET `/api/warehouse/domains` — 域名列表

**响应 data** (数组): `["example.com", "test.com"]`

---

## 8. 智慧舆情 Sentiment

**前缀**: `/api/sentiment`

### GET `/api/sentiment/analyses` — 分析列表

**查询参数**: `page=1&page_size=20`  
**响应** (分页格式):
```json
{
  "items": [{
    "id": 1,
    "trigger_type": "manual",
    "status": "completed",
    "summary": "本次舆情分析覆盖 50 条数据...",
    "overall_sentiment": "positive",
    "articles_analyzed": 50,
    "articles_scope": "{\"warehouse_article_count\":30,\"chat_message_count\":20,\"since_time\":\"...\",\"analysis_time\":\"...\"}",
    "created_at": "...", "updated_at": "..."
  }]
}
```

### GET `/api/sentiment/analyses/{analysis_id}` — 分析详情

**响应 data**:
```json
{
  "id": 1, "trigger_type": "manual", "status": "completed",
  "summary": "...", "overall_sentiment": "positive",
  "articles_analyzed": 50,
  "events": [{
    "id": 1, "event_name": "关键词 - domain",
    "sentiment_type": "positive",
    "description": "...",
    "keywords_json": "[\"关键词1\",\"关键词2\"]",
    "heat": 85,
    "related_article_ids": "[1,2,3]"
  }],
  "words": [{
    "id": 1, "word": "增长", "weight": 15.2,
    "sentiment_type": "positive", "category": "topic"
  }],
  "locations": [{
    "id": 1, "event_id": 1,
    "location_name": "北京",
    "longitude": 116.4074, "latitude": 39.9042,
    "heat": 50, "description": ""
  }]
}
```

### POST `/api/sentiment/analyses/trigger` — 触发分析

点击即自动采集「数据仓库（清洗后已发布文章）」和「智能问数（AI对话记录）」两个子系统的增量文本数据进行舆情分析。

- **增量机制**: 只分析上次成功分析时间点之后的新增数据（首次分析则采集全部数据）
- **数据来源**: 
  - 数据仓库 `WarehouseArticle`（status=published，清洗后入库的已发布文章） 
  - 智能问数 `Message`（用户与 AI 的对话记录）

**请求体**:
| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| trigger_type | string | ❌ | "manual" | "manual" 或 "auto" |

**响应 data**: `{ "id": 1 }`  
> **注意**: 分析同步执行，直接返回完成结果。如自上次分析以来无新增数据，则返回 400 错误。

### GET `/api/sentiment/events` — 事件列表

**查询参数**: `page=1&page_size=20&analysis_id=`  
**响应**: 分页格式

### GET `/api/sentiment/wordcloud` — 词云数据

**查询参数**: `analysis_id=&sentiment_type=`  
**响应 data** (数组):
```json
[{"id": 1, "word": "增长", "weight": 15.2, "sentiment_type": "positive", "category": "topic"}]
```

### GET `/api/sentiment/locations` — 地点标记（3D地球）

**查询参数**: `event_id=`  
**响应 data** (数组):
```json
[{"id": 1, "event_id": 1, "location_name": "北京",
  "longitude": 116.4074, "latitude": 39.9042,
  "heat": 50, "description": ""}]
```

### GET `/api/sentiment/dashboard` — 最新大屏快照

**响应 data**:
```json
{
  "id": 1, "total_articles": 100,
  "positive_count": 60, "negative_count": 20, "neutral_count": 20,
  "total_events": 5, "avg_heat": 72.5,
  "top_words_json": "[{\"word\":\"增长\",\"weight\":15.2}]",
  "top_events_json": "[{\"name\":\"事件名\",\"heat\":85}]",
  "snapshot_at": "..."
}
```

### GET `/api/sentiment/stats` — 统计概览

**响应 data**: `{ "total_analyses": 10, "positive_count": 5, "negative_count": 2, "neutral_count": 2, "mixed_count": 1, "total_events": 20 }`

---

## 9. 数字大屏 Dashboard

**前缀**: `/api/dashboard`

### GET `/api/dashboard/stats` — 实时指标

**响应 data**:
```json
{
  "watch_sources": 10,
  "today_collected": 50,
  "total_collected": 1000,
  "total_tokens": 50000,
  "total_users": 20,
  "uptime": "N/A（需配置应用启动时间记录）",
  "total_articles": 100
}
```

### GET `/api/dashboard/collect-trend` — 采集趋势

**查询参数**: `days=7`  
**响应 data** (数组):
```json
[{"date": "2026-05-20", "count": 15}, {"date": "2026-05-21", "count": 22}]
```

### GET `/api/dashboard/token-trend` — Token 趋势

**查询参数**: `days=7`  
**响应 data** (数组):
```json
[{"date": "2026-05-20", "tokens": 1500}, {"date": "2026-05-21", "tokens": 2200}]
```

### GET `/api/dashboard/earth` — 3D 地球数据

**响应 data** (数组 → 地图组件用):
```json
[{
  "name": "北京", "longitude": 116.4074, "latitude": 39.9042,
  "value": 85, "event_name": "某热点事件"
}]
```

### GET `/api/dashboard/wordcloud` — 词云数据

**响应 data** (数组):
```json
[{"name": "增长", "value": 15.2, "sentiment_type": "positive"}]
```

### GET `/api/dashboard/sentiment-stats` — 舆情统计

**响应 data**:
```json
{
  "total_articles": 100, "positive_count": 60,
  "negative_count": 20, "neutral_count": 20,
  "total_events": 5, "avg_heat": 72.5,
  "top_words": [{"word": "增长", "weight": 15.2}],
  "top_events": [{"name": "事件名", "heat": 85}],
  "snapshot_at": "..."
}
```

---

## 10. 系统管理 Admin

**前缀**: `/api/admin`  
**权限**: 所有接口需要 admin 角色

### 10.1 用户管理

#### GET `/api/admin/users` — 用户列表

**查询参数**: `page=1&page_size=20`  
**响应** (分页):
```json
{
  "items": [{
    "id": 1, "username": "admin", "nickname": "管理员",
    "role": "admin", "status": "active", "created_at": "..."
  }]
}
```

#### PUT `/api/admin/users/status` — 更新用户状态

**请求体**: `{ "user_id": 1, "status": "active" }`  
status 可选: `active`, `disabled`, `banned`

#### POST `/api/admin/users` — 创建用户

**请求体**:
| 字段 | 类型 | 必填 | 默认 |
|------|------|------|------|
| username | string | ✅ | — |
| password | string | ✅ | —（至少6位） |
| nickname | string | ❌ | "" |
| role | string | ❌ | "user"（可选 user/admin） |

#### PUT `/api/admin/users/{user_id}/role` — 修改角色

**请求体**: `{ "role": "admin" }`  
role 可选: `user`, `admin`（不可改为 worker）

#### DELETE `/api/admin/users/{user_id}` — 删除用户

**限制**: 不可删除 root 角色和自己。

### 10.2 系统配置

#### GET `/api/admin/configs` — 获取配置列表

**响应 data** (数组): `[{ "key": "disable_register", "value": "false" }]`

#### PUT `/api/admin/configs` — 更新配置

**请求体**: `{ "key": "disable_register", "value": "true" }`

### 10.3 API Key 管理

#### GET `/api/admin/api-keys` — 列表

**响应 data** (数组):
```json
[{
  "id": 1, "name": "默认OpenAI", "provider": "openai",
  "base_url": "https://api.openai.com/v1",
  "model_name": "gpt-4o-mini", "purpose": "all",
  "max_tokens": 4096, "temperature": 0.7, "top_p": 1.0,
  "enabled": 1, "sort_order": 0,
  "created_at": "..."
}]
```

#### GET `/api/admin/api-keys/{key_id}` — 详情

**注意**: 响应中**屏蔽** `api_key` 敏感字段。

#### POST `/api/admin/api-keys` — 创建

**请求体**:
| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| name | string | ✅ | — | 配置名称 |
| api_key | string | ✅ | — | API 密钥 |
| provider | string | ❌ | "openai" | 提供方 |
| base_url | string | ❌ | "" | API 地址 |
| model_name | string | ❌ | "" | 模型名 |
| purpose | string | ❌ | "chat" | chat/dataworker/all |
| max_tokens | int | ❌ | 4096 | 最大 Token |
| temperature | float | ❌ | 0.7 | 温度参数 |
| top_p | float | ❌ | 1.0 | Top-P |
| sort_order | int | ❌ | 0 | 排序值 |

#### PUT `/api/admin/api-keys/{key_id}` — 编辑

**请求体**: 同创建（全部字段可选），额外支持 `enabled` 字段

#### DELETE `/api/admin/api-keys/{key_id}` — 删除

**限制**: 如有 Worker 引用此 Key 则禁止删除。

#### PUT `/api/admin/api-keys/{key_id}/toggle` — 启用/禁用

### 10.4 Token 统计

#### GET `/api/admin/token-stats/daily` — 日统计

**查询参数**: `days=30`  
**响应 data** (数组):
```json
[{"date": "2026-05-20", "total_tokens": 5000, "active_users": 3}]
```

#### GET `/api/admin/token-stats/users` — 用户排行

**查询参数**: `limit=20`  
**响应 data** (数组):
```json
[{"user_id": 1, "username": "admin", "total_tokens": 50000}]
```

### 10.5 数据库管理（多数据库支持）

> Admin 后台提供的数据库管理能力，支持 SQLite ↔ MySQL 的切换与数据迁移。

#### GET `/api/admin/database/status` — 获取数据库连接状态

**响应 data**:
```json
{
  "active_database": "sqlite",
  "db_type": "sqlite+aiosqlite",
  "mysql_config": {
    "host": "localhost",
    "port": 3306,
    "database": "ctos",
    "user": "root"
  },
  "sqlite_config": {
    "path": "./data/ctos.db"
  },
  "engine_status": "connected",
  "available_databases": ["sqlite", "mysql"]
}
```

#### PUT `/api/admin/database/mysql-config` — 更新 MySQL 配置

**请求体**: 全部字段可选
| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| host | string | — | MySQL 主机地址 |
| port | int | — | 端口 |
| user | string | — | 用户名 |
| password | string | — | 密码 |
| database | string | — | 数据库名 |

**注意**: 此接口仅更新内存中的配置，持久化需修改 `.env` 文件。

#### POST `/api/admin/database/switch` — 切换数据库

全自动切换流程：检查 → 建库（MySQL）→ 建表 → 数据迁移 → 切库

**请求体**:
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| db_type | string | ✅ | "sqlite" 或 "mysql" |

**响应 data**: `{ "active_database": "mysql" }`

#### POST `/api/admin/database/migrate` — 执行数据迁移

在 SQLite ↔ MySQL 之间进行单向数据迁移（目标库不可与当前库相同）。

**请求体**:
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| target_db | string | ✅ | "sqlite" 或 "mysql" |

**响应 data**:
```json
{
  "tables": { "users": 5, "chat_conversations": 10, ... },
  "duration_seconds": 2.35
}
```

#### GET `/api/admin/database/migration/progress` — 迁移进度查询

**响应 data**:
```json
{
  "in_progress": false,
  "progress_pct": 100,
  "current_table": "",
  "rows_processed": 0,
  "total_rows": 0,
  "error": null
}
```

### 10.6 操作日志

#### GET `/api/admin/logs` — 日志列表

**查询参数**: `page=1&page_size=20&action=`  
**响应** (分页):
```json
{
  "items": [{
    "id": 1, "user_id": 1,
    "action": "login", "target": "",
    "detail": "{}", "ip_address": "127.0.0.1",
    "created_at": "..."
  }]
}
```

---

## 11. 智能聊天 IM

**前缀**: `/api/im`

### 11.1 好友管理

#### GET `/api/im/friends` — 好友列表

**查询参数**: `q=`（用户名搜索）  
**响应 data** (数组):
```json
[{
  "id": 2,
  "username": "friend1",
  "nickname": "",
  "avatar": "",
  "remark": "备注名",
  "is_blocked": 0,
  "created_at": "..."
}]
```

#### POST `/api/im/friends/search` — 搜索用户

**请求体**: `{ "keyword": "用户名" }`  
**响应 data** (数组): `[{ "id": 2, "username": "...", "nickname": "...", "avatar": "" }]`

#### POST `/api/im/friend-requests` — 发送好友申请

**请求体**: `{ "receiver_id": 2, "message": "你好" }`

#### GET `/api/im/friend-requests` — 申请列表

**响应 data**:
```json
{
  "received": [{
    "id": 1, "sender_id": 1, "receiver_id": 2,
    "other_id": 1, "message": "你好", "status": "pending",
    "is_received": true,
    "sender_username": "me", "sender_nickname": "", "sender_avatar": "",
    "receiver_username": "friend", "receiver_nickname": "", "receiver_avatar": "",
    "other_username": "me", "other_nickname": "", "other_avatar": "",
    "created_at": "..."
  }],
  "sent": [{
    "id": 1, "sender_id": 1, "receiver_id": 2,
    "other_id": 2, "message": "你好", "status": "pending",
    "is_received": false,
    "sender_username": "me", "sender_nickname": "", "sender_avatar": "",
    "receiver_username": "friend", "receiver_nickname": "", "receiver_avatar": "",
    "other_username": "friend", "other_nickname": "", "other_avatar": "",
    "created_at": "..."
  }]
}
```

#### POST `/api/im/friend-requests/handle` — 处理申请

**请求体**: `{ "request_id": 1, "action": "accept" }`  
action: `accept` / `reject`

#### PUT `/api/im/friends/remark` — 修改备注

**请求体**: `{ "friend_id": 2, "remark": "新备注" }`

#### DELETE `/api/im/friends/{friend_id}` — 删除好友

### 11.2 群组管理

#### GET `/api/im/groups` — 我的群组列表

**响应 data** (数组):
```json
[{
  "id": 1, "name": "群聊名称", "avatar": "",
  "announcement": "", "member_count": 5,
  "owner_id": 1, "status": "active",
  "created_at": "..."
}]
```

#### POST `/api/im/groups` — 创建群组

**请求体**: `{ "name": "群名", "member_ids": [2, 3] }`

#### GET `/api/im/groups/{group_id}/members` — 群成员列表（供@弹出选择）

**响应 data** (数组):
```json
[{
  "user_id": 1, "username": "user1",
  "nickname": "", "display_name": "用户一",
  "avatar": "", "role": "owner",
  "is_worker": false, "worker_icon": ""
}]
```

#### GET `/api/im/groups/{group_id}` — 群组详情（含成员列表）

**响应 data**:
```json
{
  "id": 1, "name": "群聊名称", "avatar": "",
  "announcement": "", "member_count": 5,
  "owner_id": 1, "status": "active",
  "created_at": "...",
  "members": [{
    "user_id": 1, "username": "user1",
    "nickname": "", "avatar": "",
    "role": "owner", "joined_at": "..."
  }]
}
```

#### PUT `/api/im/groups/{group_id}` — 更新群信息

**请求体**: `{ "name": "新群名", "announcement": "公告" }`  
**权限**: 群主或管理员

#### POST `/api/im/groups/{group_id}/members` — 添加群成员

**请求体**: `{ "user_ids": [4, 5] }`  
**权限**: 群主或管理员

#### DELETE `/api/im/groups/{group_id}/members/{member_id}` — 移除成员/退群

**权限**: 群主/管理员可移除其他人，普通成员可退群（传自己的 user_id）

#### DELETE `/api/im/groups/{group_id}` — 解散群组

**权限**: 仅群主可解散

### 11.3 聊天消息

#### GET `/api/im/messages` — 消息历史

**查询参数**: `receiver_type=user&receiver_id=2&before_id=&limit=50`  
- `receiver_type`: "user"（私聊）或 "group"（群聊）
- `receiver_id`: 对方用户ID（私聊）或群组ID（群聊）
- `before_id`: 可选，分页游标，上次加载的最后一条消息ID
- `limit`: 可选，每页条数（默认 50）
- **私聊消息双向返回**：返回当前用户与对方之间发送和接收的所有消息

**响应** (数组):
```json
{
  "items": [{
    "id": 1, "sender_id": 1, "receiver_id": 2,
    "receiver_type": "user", "type": "text",
    "content": "你好", "mentions": [],
    "file_id": null,
    "file_info": null,  // 文件消息时包含文件元信息
    "reply_to": null,
    "sender_username": "me",
    "sender_nickname": "",
    "sender_avatar": "",
    "created_at": "..."
  }]
}
```

- `file_info`: 当 `file_id` 不为 null 时，附带文件详细信息：
  ```json
  {
    "id": 456,
    "file_name": "photo.jpg",
    "file_size": 102400,
    "mime_type": "image/jpeg",
    "md5_hash": "d41d8cd98f00b204e9800998ecf8427e"
  }
  ```

#### POST `/api/im/messages` — 发送消息

**请求体**:
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| receiver_id | int | ✅ | 用户ID 或群组ID |
| receiver_type | string | ✅ | "user" / "group" |
| type | string | ❌ | "text" / "emoji" / "sticker" / "file" / "image" / "system" |
| content | string | ❌ | 消息内容 |
| mentions | [int] | ❌ | 被@的用户ID列表（群聊时） |
| file_id | int | ❌ | 文件ID |
| reply_to | int | ❌ | 回复的消息ID |

> **数字员工@回复**: 在群聊中@某个已绑定的数字员工用户时，系统会自动触发 LLM 回复，将 AI 生成的回复作为群聊消息发送。

#### GET `/api/im/conversations` — 会话列表

**响应 data** (数组):
```json
[{
  "id": 2,
  "type": "user",
  "title": "friend1",
  "avatar": "",
  "last_message": {
    "id": 10,
    "sender_id": 1,
    "content": "最后一条消息内容",
    "type": "text",
    "created_at": "2026-05-28T12:00:00"
  },
  "unread_count": 3
}]
```
- `id`: 私聊时为对方用户ID，群聊时为群组ID
- `type`: "user"（私聊）或 "group"（群聊）
- `title`: 聊天对象显示名称
- `last_message`: 最后一条消息的详情
- `unread_count`: 未读消息数
- **私聊会话中对方身份修正**：`id` 始终是"对方"的ID，而非当前用户自身
- **私聊会话去重合并**：后端强制对私聊的两个方向（A→B 和 B→A）进行 key 归一化（`user_{小ID}_{大ID}`），同一对用户只返回一条会话记录，取最后一条消息作为 `last_message`。未读数合并两个方向的未读计数

#### POST `/api/im/messages/read` — 标记已读

**请求体**: `{ "receiver_type": "user", "receiver_id": 2, "last_read_msg_id": 100 }`

### 11.4 聊天服务器 & 数字员工

#### GET `/api/im/servers` — 可用服务器列表

**响应 data** (数组):
```json
[{
  "id": 1, "name": "主服务器",
  "url": "ws://...",
  "status": "online",
  "priority": 0
}]
```

#### GET `/api/im/workers/chat` — 可聊天的数字员工列表

**响应 data** (数组):
```json
[{
  "id": 1, "user_id": 3,
  "name": "助手", "icon": "🤖",
  "description": "",
  "username": "assistant",
  "nickname": "助手",
  "avatar": ""
}]
```

### 11.5 文件管理

#### POST `/api/im/files/upload` — 上传文件

**请求方式**: `multipart/form-data`  
**请求参数**:
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | ✅ | 上传的文件（支持所有类型） |

**响应 data**:
```json
{
  "id": 1,
  "file_name": "photo.jpg",
  "file_size": 102400,
  "mime_type": "image/jpeg",
  "md5_hash": "d41d8cd98f00b204e9800998ecf8427e",
  "duplicate": false
}
```
> **MD5 去重**: 相同内容的文件不会重复存储，`duplicate=true` 表示复用已有记录。

#### GET `/api/im/files/{file_id}` — 文件信息

**响应 data**:
```json
{
  "id": 1, "file_name": "photo.jpg",
  "file_size": 102400, "mime_type": "image/jpeg",
  "md5_hash": "d41d8cd98f00b204e9800998ecf8427e",
  "created_at": "2026-05-27T12:00:00"
}
```

#### GET `/api/im/files/{file_id}/download` — 下载/预览文件

**说明**:
- 图片类文件（`image/*`）→ `Content-Disposition: inline`，浏览器直接预览
- 其他文件 → `Content-Disposition: attachment`，浏览器触发下载
- **认证方式**：支持以下两种方式之一：
  1. `Authorization: Bearer <token>` — HTTP 请求头（适用于 `fetch`/`XMLHttpRequest`）
  2. `?token=<JWT>` — URL 查询参数（适用于 `<img src>`、`<a href>` 等浏览器原生标签）

**响应**: 文件二进制流，直接返回原始文件内容。

### 11.6 管理后台（IM 相关）

#### GET `/api/im/admin/groups` — 群组管理列表

**查询参数**: `page=1&page_size=20`

#### GET `/api/im/admin/messages` — 消息管理列表

**查询参数**: `page=1&page_size=20`

---

## 12. WebSocket 推送

> WebSocket 已整合到 FastAPI 主后端（端口 8000），不再需要独立 WS 服务器。

### 12.1 概述

CToS 使用 WebSocket 实现消息的实时下行推送。WebSocket 端点与 REST API **共用同一个端口**（8000）。

**核心原则：**
- ✅ 发消息 → 走 REST API（不变）
- ✅ 收消息 → 通过 WebSocket（与主后端同端口）
- ⛔ WS 只走下行不上行

### 12.2 连接地址

```javascript
// 自动检测当前主机端口
const baseUrl = window.location.origin;               // e.g. http://localhost:8000
const wsBase = baseUrl.replace(/^http/, 'ws');         // e.g. ws://localhost:8000
const url = `${wsBase}/ws?token=${encodeURIComponent(token)}`;
```

**连接参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| token | string | ✅ | JWT Token（登录后获取） |

### 12.3 消息格式

所有 WebSocket 消息为 JSON 文本帧：

```json
{
  "type": "event_type",
  "data": { ... }
}
```

### 12.4 服务端推送事件

| 事件类型 | 说明 | 触发条件 |
|---------|------|---------|
| `offline_messages` | 用户上线后批量推送离线数据 | WebSocket 连接建立后自动触发 |
| `new_message` | 有新私聊消息 | 好友发送私聊消息 |
| `group_message` | 群组有新消息 | 群成员发送群消息 |
| `friend_request` | 收到新的好友申请 | 有人发送好友申请 |
| `friend_request_handled` | 好友申请被处理 | 对方接受/拒绝申请 |
| `ping` | 心跳检测 | 每 30 秒 |

### 12.5 心跳机制

- **服务端 → 客户端**：每 30 秒发送 `{"type":"ping","data":{"timestamp":"..."}}`
- **客户端 → 服务端**：收到后回复 `{"type":"pong"}`
- 客户端也可主动发送 `{"type":"ping"}`，服务端回复 `{"type":"pong"}`

### 12.6 `offline_messages` 离线消息结构

```json
{
  "type": "offline_messages",
  "data": {
    "messages": [
      {
        "id": 1,
        "sender_id": 2,
        "sender_username": "user2",
        "sender_nickname": "用户二",
        "receiver_type": "user",
        "receiver_id": 1,
        "content": "你好",
        "type": "text",
        "created_at": "2026-05-28T12:00:00"
      }
    ],
    "conversations": [
      {
        "id": 1,
        "name": "群聊名称",
        "type": "group",
        "member_count": 5,
        "last_message": { "content": "最后一条消息", "sender_id": 1, "created_at": "..." }
      }
    ],
    "friend_requests": {
      "received": [ { "id": 1, "sender_id": 2, "status": "pending", ... } ],
      "sent": []
    }
  }
}
```

### 12.7 IM 模块 Push 事件映射

| 操作 | Push 事件 | 目标 |
|------|----------|------|
| 发送私聊消息 | `new_message` | 消息接收方 |
| 发送群聊消息 | `group_message` | 群组所有成员（排除发送者） |
| 发送好友申请 | `friend_request` | 申请接收方 |
| 处理好友申请 | `friend_request_handled` | 申请发起方 |

### 12.8 WS 状态查询 API

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/api/ws/stats` | 获取 WebSocket 连接统计（在线人数/连接数） | 无需认证 |

**响应**:
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "online_users": 5,
    "connections": 8
  }
}
```

---

## 13. 内部 API Internal

**前缀**: `/api/internal`  
**认证**: 内部 API Key（通过 `X-Internal-Api-Key` 请求头传递）  
**用途**: 供 CToSWsChat 或其他内部服务调用

### POST `/api/internal/ws-auth` — WS Token 验证

**请求体**:
```json
{ "token": "jwt_token_string" }
```

**响应 data**:
```json
{
  "valid": true,
  "user_id": 1,
  "username": "admin",
  "nickname": "",
  "avatar": ""
}
```

### POST `/api/internal/user-status` — 更新用户在线状态

**请求体**:
```json
{ "user_id": 1, "status": "online" }
```
status: `online` / `offline`

---

## 14. WebSocket 内部推送（兼容接口）

> 以下接口定义在 WebSocket 路由模块中，使用内部 API Key 认证，保留以兼容旧版调用方。

### POST `/api/internal/ws/push` — 推送消息给指定用户

**请求参数**: `user_id`, `event`, `data` (query params)  
**认证**: `X-Internal-Api-Key`

### POST `/api/internal/ws/push-group` — 推送消息给群组

**请求参数**: `group_id`, `exclude_user_id`, `event`, `data` (query params)  
**认证**: `X-Internal-Api-Key`

### GET `/api/internal/ws/user-status` — 查询用户在线状态

**请求参数**: `user_id` (query param)  
**认证**: `X-Internal-Api-Key`

### POST `/api/internal/ws/batch-status` — 批量查询用户在线状态

**请求体**:
```json
{ "user_ids": [1, 2, 3] }
```
**认证**: `X-Internal-Api-Key`

---

## 附录：接口统计

| 模块 | 端点数 | 需要认证 | 需要 admin |
|------|--------|---------|-----------|
| Auth 认证 | 4 | 部分（/me, /logout） | 否 |
| Chat 智能问数 | 8 | ✅ | 否 |
| Watch 智能瞭望 | 9 | ✅ | 否 |
| Workers 数字员工 | 14 | ✅ | 否 |
| Dispatch 派遣 | 8 | ✅ | 否 |
| Cleaning 数据清洗 | 7 | ✅ | 否 |
| Warehouse 知识仓库 | 11 | ✅ | 否 |
| Sentiment 舆情 | 8 | ✅ | 否 |
| Dashboard 大屏 | 6 | ✅ | 否 |
| Admin 系统管理 | 21 | ✅ | ✅ |
| IM 智能聊天 | 22 | ✅ | 部分 |
| WebSocket | 1 (WS) + 1 (HTTP) + 4 (内部兼容) | ✅ / 内部 Key | 否 |
| Internal 内部 API | 2 | 内部 Key | 否 |
| 健康检查 | 1 | 否 | 否 |
| **总计** | **122** | — | — |

> **注**: Admin 模块含 5 个数据库管理端点（database/status, mysql-config, switch, migrate, migration/progress）。

---

## 附录：集成指南

### 快速接入

外部项目或应用接入 CToS API 的建议步骤：

1. **获取基础路径**: 确认目标环境的 Base URL（开发: `http://localhost:8000`）
2. **创建用户**: 调用 `POST /api/auth/register` 注册，或由管理员在后台创建
3. **获取 Token**: 调用 `POST /api/auth/login` 获取 JWT Token
4. **携带 Token**: 在所有请求的 `Authorization` 请求头添加 `Bearer <token>`
5. **调用业务接口**: 按需调用各模块接口

### 环境配置

| 环境 | Base URL | 说明 |
|------|----------|------|
| 开发环境 | `http://localhost:8000` | 本地开发调试 |
| 测试环境 | 由运维提供 | 集成测试 |
| 生产环境 | 由运维提供 | 正式服务 |

### 安全建议

- **Token 管理**: JWT Token 有效期为 24 小时（可通过 `JWT_EXPIRATION_HOURS` 环境变量配置），过期后需重新登录
- **HTTPS**: 生产环境请务必配置 HTTPS，避免 Token 和敏感数据明文传输
- **CORS**: 生产环境应将 `CORS_ORIGINS` 配置为具体的域名白名单，而非通配符 `*`
- **API Key 保护**: 内部 API Key 应妥善保管，定期轮换
- **频率控制**: 建议调用方实现本地重试机制（指数退避），应对服务端限流

### OpenAPI / Swagger

服务启动后可直接访问以下地址查看交互式 API 文档：

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

> **文档结束**