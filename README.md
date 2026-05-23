# AI智能瞭望与智能问数系统

> 基于 Python 3.10 + Tornado + SQLite3 + MVC 架构的 B/S 模式 Web 应用

---

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 技术栈](#2-技术栈)
- [3. 项目架构](#3-项目架构)
- [4. 目录结构](#4-目录结构)
- [5. 核心模块详解](#5-核心模块详解)
- [6. 路由与URL映射](#6-路由与url映射)
- [7. 数据库设计](#7-数据库设计)
- [8. 安全机制](#8-安全机制)
- [9. 前端模板系统](#9-前端模板系统)
- [10. 开发规范](#10-开发规范)
- [11. 环境搭建与运行](#11-环境搭建与运行)
- [12. 已实现功能](#12-已实现功能)
- [13. 待开发功能规划](#13-待开发功能规划)
- [14. 扩展建议](#14-扩展建议)

---

## 1. 项目概述

本项目是一个 **AI智能瞭望与智能问数系统**，采用 B/S（Browser/Server）架构模式，基于 Python 的 Tornado Web 框架开发，遵循经典的 MVC（Model-View-Controller）分层架构设计。

系统当前已完成基础框架搭建和用户认证模块（登录/退出功能），后续将在此基础上逐步完善 AI 智能瞭望与智能问数相关的核心业务功能。

### 1.1 项目定位

- **智能瞭望**：AI 驱动的数据监控、预警与分析能力
- **智能问数**：自然语言交互式数据查询与可视化展示

### 1.2 架构特点

- **轻量级**：采用 SQLite3 嵌入式数据库，零配置即可运行
- **高性能**：Tornado 框架支持异步非阻塞 I/O，适合高并发场景
- **分层清晰**：严格的 MVC 分层，便于维护和扩展
- **安全机制**：内置 CSRF 防护、Secure Cookie 会话管理、密码 PBKDF2 加密

---

## 2. 技术栈

| 层级 | 技术 | 版本 | 说明 |
|------|------|------|------|
| **运行环境** | Python | 3.10 | 编程语言运行环境 |
| **Web框架** | Tornado | 6.5.5 | 异步 Web 框架 + HTTP 服务器 |
| **数据库** | SQLite3 | 内置 | 嵌入式关系型数据库 |
| **前端模板** | Tornado Templates | 内置 | Tornado 自带模板引擎 |
| **前端UI框架** | Layui | 2.13.6 | 模块化前端UI组件库（本地化） |
| **前端UI框架** | Bootstrap | 5.3.8 | 响应式前端组件库（本地化） |
| **图标库** | Font Awesome | 5.15.4 | 矢量图标库（本地化） |
| **标记语言** | HTML5 | - | 页面结构 |
| **样式表** | CSS3 | - | 页面样式 |
| **脚本语言** | JavaScript | ES6+ | 前端交互逻辑 |
| **虚拟环境** | venv | 内置 | Python 虚拟环境隔离 |

### 2.1 前端组件说明

| 组件 | 本地路径 | 用途 |
|------|---------|------|
| **Layui** | `app/static/dist/layui-v2.13.6/layui-v2.13.6/layui/` | 后台管理系统UI、表格、表单、弹窗等组件 |
| **Bootstrap** | `app/static/dist/bootstrap-5.3.8-dist/bootstrap-5.3.8-dist/` | 响应式布局、组件样式 |
| **Font Awesome** | `app/static/dist/fontawesome-free-5.15.4-web/fontawesome-free-5.15.4-web/` | 图标展示 |

### 2.2 组件使用方式

```html
<!-- Layui -->
<link rel="stylesheet" href="{{static_url('dist/layui-v2.13.6/layui-v2.13.6/layui/css/layui.css')}}">
<script src="{{static_url('dist/layui-v2.13.6/layui-v2.13.6/layui/layui.js')}}"></script>

<!-- Bootstrap -->
<link rel="stylesheet" href="{{static_url('dist/bootstrap-5.3.8-dist/bootstrap-5.3.8-dist/css/bootstrap.min.css')}}">
<script src="{{static_url('dist/bootstrap-5.3.8-dist/bootstrap-5.3.8-dist/js/bootstrap.bundle.min.js')}}"></script>

<!-- Font Awesome -->
<link rel="stylesheet" href="{{static_url('dist/fontawesome-free-5.15.4-web/fontawesome-free-5.15.4-web/css/all.min.css')}}">
```

> **注意**：所有前端组件均已本地化，不依赖互联网资源。

---

---

## 3. 项目架构

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                      B/S 架构                            │
├─────────────────────────────────────────────────────────┤
│  客户端 (Browser)                                        │
│  HTML5 + CSS3 + JavaScript                               │
├─────────────────────────────────────────────────────────┤
│                         HTTP/HTTPS                        │
├─────────────────────────────────────────────────────────┤
│  服务器端 (Server) - Tornado HTTPServer                  │
│  ┌───────────────────────────────────────────────────┐   │
│  │              Tornado IOLoop (事件循环)              │   │
│  └───────────────────────────────────────────────────┘   │
│                         │                                 │
│  ┌───────────────────────────────────────────────────┐   │
│  │              URL Router (路由分发)                  │   │
│  └───────────────────────────────────────────────────┘   │
│                         │                                 │
│  ┌───────────────────────────────────────────────────┐   │
│  │           MVC 分层架构                             │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐            │   │
│  │  │Control  │─>│ Model   │─>│  View   │            │   │
│  │  │  控制层  │  │  模型层  │  │  视图层  │            │   │
│  │  └─────────┘  └─────────┘  └─────────┘            │   │
│  └───────────────────────────────────────────────────┘   │
│                         │                                 │
│  ┌───────────────────────────────────────────────────┐   │
│  │           SQLite3 Database (数据库)                │   │
│  └───────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 3.2 MVC 分层说明

#### Controller 层（控制层）
- **位置**：`app/controllers/`
- **职责**：
  - 接收 HTTP 请求（GET/POST）
  - 参数校验与数据预处理
  - 调用 Model 层处理业务逻辑
  - 渲染 View 模板或返回响应/跳转
- **实现方式**：继承 `tornado.web.RequestHandler`，每个 URL 对应一个 Handler 类

#### Model 层（模型层）
- **位置**：`app/models/`
- **职责**：
  - 数据库连接管理
  - 数据表初始化（DDL）
  - 数据访问对象（DAO/Repository 模式）
  - 业务逻辑处理
- **实现方式**：使用 sqlite3 原生连接，封装 Repository 类提供数据操作接口

#### View 层（视图层）
- **位置**：`app/templates/` + `app/static/`
- **职责**：
  - 页面模板渲染（Tornado 模板引擎）
  - 静态资源管理（CSS/JS）
  - 前端交互逻辑
- **实现方式**：继承模板 `base.html`，使用 `{% block %}` 实现页面复用

---

## 4. 目录结构

```
cnAgentOS/
│
├── app.py                          # 【主入口】程序启动文件，Tornado 服务器配置与路由定义
├── text.py                         # 【测试脚本】临时测试用脚本，用于单元测试/功能验证
├── app.md                          # 【项目说明】项目目录结构说明文档
├── README.md                       # 【本文档】项目详细开发指南
│
├── app/                            # 【应用包】MVC 业务代码主目录
│   ├── __init__.py                 # 包标识文件，便于 IDE 识别和模块导入
│   │
│   ├── controllers/                # 【控制层】处理 HTTP 请求的 Handler
│   │   ├── __init__.py             # 包标识，说明控制器模块约定
│   │   ├── base.py                 # 基础 Handler 类，提供公共登录态校验逻辑
│   │   ├── auth.py                 # 认证控制器：登录/退出功能
│   │   └── home.py                 # 后台首页控制器
│   │
│   ├── models/                     # 【模型层】数据库操作与业务逻辑
│   │   ├── __init__.py             # 包标识，说明模型层职责
│   │   ├── db.py                   # 数据库连接层：SQLite 连接管理 + 建表逻辑
│   │   └── user.py                 # 用户模型：UserRepository 数据访问对象
│   │
│   ├── templates/                  # 【视图层-模板】HTML 模板文件
│   │   ├── base.html               # 基础布局模板（所有页面继承此模板）
│   │   ├── index.html              # 后台首页模板
│   │   ├── login.html              # 登录页模板
│   │   └── register.html           # 注册页模板（空文件，待开发）
│   │
│   └── static/                     # 【静态资源】CSS/JS/图片等
│       ├── css/
│       │   └── base.css            # 全局基础样式
│       ├── js/
│       │   └── base.js             # 全局基础脚本
│       └── dist/                   # 【第三方UI组件库】已本地化
│           ├── layui-v2.13.6/      # Layui 2.13.6
│           ├── bootstrap-5.3.8-dist/  # Bootstrap 5.3.8
│           └── fontawesome-free-5.15.4-web/  # Font Awesome 5.15.4
│
├── database/                       # 【数据库目录】存放 SQLite 数据库文件
│   └── app.db                      # SQLite 数据库文件（运行时自动创建）
│
└── venv/                           # 【虚拟环境】Python 3.10 虚拟环境
    └── ...
```

---

## 5. 核心模块详解

### 5.1 主入口文件 [app.py](file:///c:/Users/wangmingyu/Desktop/work/day5/cnAgentOS/app.py)

**作用**：程序启动入口，承担服务器容器 + 应用程序本体的双重职责。

**核心功能**：
1. **Tornado 应用配置**：通过 `make_app()` 函数创建 `tornado.web.Application` 实例
2. **路由注册**：定义 URL 到 Handler 的映射关系
3. **静态资源配置**：指定模板路径和静态资源路径
4. **安全配置**：Cookie 密钥、登录 URL、CSRF 防护、调试模式
5. **服务启动**：绑定端口 10086，启动 HTTPServer

**配置项说明**：

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `template_path` | `app/templates` | Tornado 模板文件目录 |
| `static_path` | `app/static` | 静态资源目录 |
| `cookie_secret` | `demo-cookie-secret-change-me` | Secure Cookie 加密密钥（生产环境需更换） |
| `login_url` | `/auth/login` | 未登录时自动跳转的登录页 URL |
| `xsrf_cookies` | `True` | 启用 CSRF 防护 |
| `debug` | `True` | 调试模式，开启自动重载和错误详情 |
| `autoreload` | `True` | 代码变动时自动重启服务 |

**启动流程**：
```python
init_db()          # 1. 初始化数据库表
app = make_app()   # 2. 创建 Tornado 应用
server = HTTPServer(app)  # 3. 创建 HTTP 服务器
server.bind(10086)        # 4. 绑定端口
server.start()            # 5. 启动服务（使用 CPU 核心数）
IOLoop.current().start()  # 6. 启动事件循环
```

### 5.2 控制层 (Controllers)

#### 5.2.1 基础 Handler [base.py](file:///c:/Users/wangmingyu/Desktop/work/day5/cnAgentOS/app/controllers/base.py)

**类**：`BaseHandler(tornado.web.RequestHandler)`

**作用**：所有业务 Handler 的公共基类，提供统一的登录态认证机制。

**核心方法**：

| 方法 | 说明 |
|------|------|
| `get_current_user()` | 从 Secure Cookie 中读取 `username`，返回当前登录用户或 None |

**认证流程**：
1. Tornado 框架调用 `get_current_user()` 获取当前用户
2. 如果返回 `None`，则 `@tornado.web.authenticated` 装饰器自动跳转到 `login_url`
3. 如果返回用户名，则允许访问受保护的页面

#### 5.2.2 认证控制器 [auth.py](file:///c:/Users/wangmingyu/Desktop/work/day5/cnAgentOS/app/controllers/auth.py)

**Handler 类**：

| 类名 | URL | 功能 |
|------|-----|------|
| `LoginHandler` | `/auth/login` | 登录处理（GET 渲染页面 / POST 处理登录） |
| `LogoutHandler` | `/auth/logout` | 退出登录（POST 清除 Cookie 并跳转） |

**LoginHandler 逻辑**：

```
GET /auth/login
  └─> 渲染 login.html 模板，传递 title 和 error 参数

POST /auth/login
  ├─> 获取表单参数：username, password
  ├─> 参数校验：用户名或密码为空 → 返回 400 + 错误提示
  ├─> 调用 UserRepository.verify_user() 验证
  │   └─> 验证失败 → 返回 401 + 错误提示
  └─> 验证成功 → 写入 Secure Cookie → 跳转到首页 (/)
```

**LogoutHandler 逻辑**：

```
POST /auth/logout
  └─> 清除 username Cookie → 跳转到登录页
```

#### 5.2.3 首页控制器 [home.py](file:///c:/Users/wangmingyu/Desktop/work/day5/cnAgentOS/app/controllers/home.py)

**Handler 类**：`IndexHandler`

| URL | 方法 | 说明 |
|-----|------|------|
| `/` | GET | 后台首页，需要登录才能访问 |

**特性**：使用 `@tornado.web.authenticated` 装饰器，未登录用户自动跳转到登录页。

### 5.3 模型层 (Models)

#### 5.3.1 数据库连接层 [db.py](file:///c:/Users/wangmingyu/Desktop/work/day5/cnAgentOS/app/models/db.py)

**核心函数**：

| 函数 | 说明 |
|------|------|
| `_projiect_root()` | 获取项目根目录绝对路径 |
| `get_connection()` | 获取 SQLite 数据库连接，设置 `row_factory = sqlite3.Row` |
| `init_db()` | 初始化数据库表（CREATE TABLE IF NOT EXISTS） |

**数据库路径**：`项目根目录/database/app.db`

**连接特性**：
- 自动创建数据库目录（如不存在）
- 使用 `sqlite3.Row` 工厂，支持字典式字段访问（`row["username"]`）
- 使用上下文管理器（`with` 语句）自动管理事务

#### 5.3.2 用户模型 [user.py](file:///c:/Users/wangmingyu/Desktop/work/day5/cnAgentOS/app/models/user.py)

**类**：`UserRepository`

**核心方法**：

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `create_user()` | username, password | bool | 创建新用户，返回是否成功 |
| `get_user_by_username()` | username | Row/None | 根据用户名查询用户信息 |
| `verify_user()` | username, password | bool | 验证用户名和密码是否正确 |

**密码加密方案**：

```
password + salt → PBKDF2-HMAC-SHA256 (100,000 次迭代) → hex 字符串
```

| 组件 | 说明 |
|------|------|
| 算法 | PBKDF2 with HMAC-SHA256 |
| 迭代次数 | 100,000 次 |
| Salt | 16 字节随机值（`secrets.token_bytes(16)`） |
| 存储 | salt 和 password_hash 分别存储在数据库 |

### 5.4 测试脚本 [text.py](file:///c:/Users/wangmingyu/Desktop/work/day5/cnAgentOS/text.py)

**作用**：临时测试脚本，用于快速验证 Model 层功能。

**测试内容**：
1. 初始化数据库
2. 创建测试用户（admin / 123456）
3. 查询用户信息
4. 验证登录凭据

---

## 6. 路由与URL映射

### 6.1 当前路由表

| URL | Handler | 方法 | 是否需要登录 | 功能说明 |
|-----|---------|------|-------------|----------|
| `/` | `IndexHandler` | GET | ✅ | 后台首页 |
| `/auth/login` | `LoginHandler` | GET | ❌ | 渲染登录页 |
| `/auth/login` | `LoginHandler` | POST | ❌ | 处理登录请求 |
| `/auth/logout` | `LogoutHandler` | POST | ✅ | 退出登录 |

### 6.2 路由注册位置

路由在 [app.py](file:///c:/Users/wangmingyu/Desktop/work/day5/cnAgentOS/app.py#L26-L31) 的 `make_app()` 函数中通过列表形式注册：

```python
return tornado.web.Application([
    (r"/", IndexHandler),
    (r"/auth/login", LoginHandler),
    (r"/auth/logout", LogoutHandler),
], **settings)
```

### 6.3 添加新路由的方法

1. 在对应的 Controller 文件中创建新的 Handler 类
2. 在 `app.py` 的 `make_app()` 路由列表中添加新的路由映射
3. 如需访问控制，继承 `BaseHandler` 并使用 `@tornado.web.authenticated` 装饰器

---

## 7. 数据库设计

### 7.1 数据库概况

| 属性 | 值 |
|------|-----|
| 数据库类型 | SQLite3 |
| 数据库文件 | `database/app.db` |
| 初始化方式 | 调用 `init_db()` 函数自动创建 |
| 扩展性 | 支持后续迁移到 MySQL/PostgreSQL |

### 7.2 数据表结构

#### users 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 用户唯一标识 |
| `username` | TEXT | NOT NULL UNIQUE | 用户名（唯一） |
| `password_hash` | TEXT | NOT NULL | PBKDF2 加密后的密码哈希 |
| `salt` | TEXT | NOT NULL | 密码加密盐值（hex 格式） |
| `create_at` | TEXT | NOT NULL DEFAULT datetime('now') | 创建时间 |

### 7.3 建表 SQL

```sql
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    create_at TEXT NOT NULL DEFAULT(datetime('now'))
);
```

### 7.4 数据访问模式

- **连接管理**：每次操作通过 `get_connection()` 获取新连接
- **事务管理**：使用 `with` 上下文管理器自动提交/回滚
- **查询方式**：使用参数化查询（`?` 占位符）防止 SQL 注入
- **结果集**：`sqlite3.Row` 支持字典式访问（`row["字段名"]`）

---

## 8. 安全机制

### 8.1 CSRF 防护

| 配置 | 说明 |
|------|------|
| `xsrf_cookies = True` | 全局启用 CSRF Token 验证 |
| 使用方式 | 表单中添加 `{% module xsrf_form_html() %}` |
| 保护范围 | 所有 POST/PUT/DELETE 请求 |

### 8.2 会话管理

| 机制 | 说明 |
|------|------|
| Secure Cookie | 使用 `set_secure_cookie()` 加密存储用户名 |
| Cookie 密钥 | `cookie_secret` 配置项（生产环境必须更换） |
| 登录态校验 | `get_current_user()` 方法读取 Cookie 判断登录状态 |
| 自动跳转 | `@authenticated` 装饰器自动跳转未登录页面 |

### 8.3 密码安全

| 机制 | 说明 |
|------|------|
| 加密算法 | PBKDF2-HMAC-SHA256 |
| 迭代次数 | 100,000 次 |
| Salt | 16 字节密码学安全随机数 |
| 存储方式 | 密码哈希和 Salt 分开存储 |

### 8.4 其他安全考虑

| 方面 | 当前状态 | 建议 |
|------|---------|------|
| SQL 注入 | ✅ 已防护（参数化查询） | 保持使用参数化查询 |
| XSS 攻击 | ⚠️ 模板自动转义 | 确保不直接使用 `raw()` |
| 密码强度 | ❌ 未校验 | 建议添加密码复杂度校验 |
| 登录失败限制 | ❌ 未实现 | 建议添加失败次数限制 |
| HTTPS | ❌ 未启用 | 生产环境必须启用 HTTPS |

---

## 9. 前端模板系统

### 9.1 模板引擎

使用 Tornado 内置模板引擎，支持以下特性：
- 模板继承（`{% extends %}`）
- 块定义（`{% block %}`）
- 变量插值（`{{ variable }}`）
- 条件判断（`{% if %}`）
- 循环（`{% for %}`）
- 模板模块调用（`{% module %}`）

### 9.2 模板文件说明

#### base.html（基础布局模板）

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <link rel="stylesheet" href="{{static_url('css/base.css')}}">
    <script src="{{static_url('js/base.js')}}"></script>
</head>
<body>
    <div class="container">
        {% block body %}{% end %}
    </div>
</body>
</html>
```

**说明**：
- 定义页面基本结构（DOCTYPE、meta、head、body）
- 引入全局 CSS 和 JS
- 提供 `{% block body %}` 供子模板填充内容
- 使用 `{{static_url()}}` 生成静态资源 URL（带版本戳）

#### login.html（登录页模板）

```html
{% extends "base.html" %}
{% block body %}
<h3>登录</h3>
{% if error %}
<div class="error">{{ error }}</div>
{% end %}
<form method="post" action="/auth/login">
<input name="username">
<input name="password">
<button type="submit">登录admin</button>
{% module xsrf_form_html() %}
</form>
{% end %}
```

**说明**：
- 继承 base.html
- 显示错误信息（如果有）
- 包含 CSRF Token
- POST 到 `/auth/login`

#### index.html（后台首页模板）

```html
{% extends "base.html" %}
{% block body %}
<h3>后台页面</h3>
<form action="/auth/logout" method="post">
    {% module xsrf_form_html() %}
    <button type="submit">退出</button>
</form>
<div>{{ username }}</div>
{% end %}
```

**说明**：
- 显示当前登录用户名
- 提供退出登录按钮
- 需要登录才能访问

#### register.html（注册页模板）

- **当前状态**：空文件，待开发

### 9.3 静态资源

#### base.css

```css
*{
    margin: 0;
    padding: 0;
}
html,body{
    height:100%;
    width:100%;
}
.error{
    color:red;
}
```

#### base.js

```javascript
console.log("加载了Js")
```

---

## 10. 开发规范

### 10.1 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | 小写字母 + 下划线 | `auth.py`, `user.py`, `base.css` |
| 类名 | 大驼峰（PascalCase） | `LoginHandler`, `UserRepository` |
| 函数/方法 | 小写字母 + 下划线 | `get_current_user()`, `create_user()` |
| 变量 | 小写字母 + 下划线 | `username`, `password_hash` |
| 常量 | 大写字母 + 下划线 | `DB_PATH` |

### 10.2 文件组织规范

- **一个业务模块一个文件**：如 `auth.py`、`home.py`
- **Handler 职责单一**：每个 Handler 只负责一个 URL 的请求处理
- **Model 封装数据访问**：使用 Repository 模式封装数据库操作
- **模板继承复用**：所有页面模板继承 `base.html`

### 10.3 代码约定

- **Controller 层**：
  - 负责接收表单参数、校验输入
  - 调用 Model 层处理业务
  - 渲染 View 模板或跳转
- **Model 层**：
  - 负责数据库连接和 SQL 操作
  - 提供业务方法（如验证、创建、查询）
- **View 层**：
  - 只负责展示，不包含业务逻辑
  - 使用模板语法渲染数据

### 10.4 错误处理

| HTTP 状态码 | 使用场景 |
|------------|---------|
| 400 | 参数校验失败（如用户名为空） |
| 401 | 认证失败（用户名或密码错误） |
| 302 | 重定向（登录成功跳转） |

---

## 11. 环境搭建与运行

### 11.1 环境要求

- Python 3.10+
- Windows / macOS / Linux

### 11.2 环境初始化

```bash
# 1. 创建虚拟环境
python -m venv venv

# 2. 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. 安装依赖
pip install tornado==6.5.5
```

### 11.3 启动服务

```bash
# 启动主程序
python app.py
```

服务启动后将显示：
```
=====Sever 启动成功 =====端口：10086 ======
```

### 11.4 访问地址

- 首页：`http://localhost:10086/`
- 登录页：`http://localhost:10086/auth/login`

### 11.5 测试账号

- 用户名：`admin`
- 密码：`123456`

（通过 `text.py` 脚本初始化的测试账号）

### 11.6 测试脚本使用

```bash
# 运行测试脚本（创建测试用户、验证登录等）
python text.py
```

---

## 12. 已实现功能

### 12.1 用户认证模块 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| 登录页面 | ✅ | 支持用户名密码登录 |
| 登录验证 | ✅ | 校验用户名密码，错误提示 |
| 会话管理 | ✅ | Secure Cookie 保存登录态 |
| 退出登录 | ✅ | 清除 Cookie 并跳转 |
| 登录保护 | ✅ | `@authenticated` 装饰器保护页面 |
| CSRF 防护 | ✅ | 所有表单包含 CSRF Token |
| 密码加密 | ✅ | PBKDF2-HMAC-SHA256 加密存储 |

### 12.2 基础框架 ✅

| 功能 | 状态 | 说明 |
|------|------|------|
| MVC 架构 | ✅ | 清晰的分层结构 |
| 路由系统 | ✅ | Tornado URL 映射 |
| 模板引擎 | ✅ | Tornado 模板继承 |
| 静态资源 | ✅ | CSS/JS 资源管理 |
| 数据库连接 | ✅ | SQLite3 连接池 |
| 自动重载 | ✅ | 开发模式代码变动自动重启 |

---

## 13. 待开发功能规划

### 13.1 用户模块完善

| 功能 | 优先级 | 说明 |
|------|--------|------|
| 用户注册 | P0 | 完善 `register.html` 和注册逻辑 |
| 密码修改 | P1 | 用户修改密码功能 |
| 个人信息 | P1 | 查看和编辑个人信息 |
| 密码强度校验 | P1 | 注册/修改密码时校验复杂度 |

### 13.2 AI 智能瞭望模块（规划中）

> 待确认具体需求后详细设计

可能的功能方向：
- 数据监控面板
- 实时数据预警
- AI 数据分析报告
- 图表可视化展示

### 13.3 智能问数模块（规划中）

> 待确认具体需求后详细设计

可能的功能方向：
- 自然语言数据查询
- AI 对话式数据分析
- 数据结果可视化
- 查询历史记录

### 13.4 系统功能完善

| 功能 | 优先级 | 说明 |
|------|--------|------|
| 权限管理 | P1 | 角色权限控制 |
| 操作日志 | P1 | 记录用户操作日志 |
| 数据导出 | P2 | 支持导出 Excel/PDF 等格式 |
| 系统设置 | P2 | 全局配置管理 |

---

## 14. 扩展建议

### 14.1 数据库扩展

- **迁移到 MySQL/PostgreSQL**：`db.py` 已预留扩展能力，可封装统一的数据库接口层
- **ORM 框架**：考虑引入 SQLAlchemy 简化数据访问层
- **数据库迁移工具**：使用 Alembic 管理数据库版本

### 14.2 安全加固

- **更换 Cookie 密钥**：将 `cookie_secret` 替换为强随机字符串
- **HTTPS 支持**：生产环境启用 HTTPS
- **登录失败限制**：添加失败次数限制和锁定机制
- **会话超时**：设置 Cookie 过期时间

### 14.3 前端优化

- **UI 框架**：引入 Bootstrap/Ant Design 等 UI 组件库
- **响应式布局**：优化移动端显示效果
- **AJAX 交互**：使用 Fetch API 实现异步请求
- **前端验证**：添加表单前端校验

### 14.4 后端优化

- **日志系统**：接入 Python logging 模块
- **配置管理**：使用配置文件管理环境变量
- **错误处理**：统一异常处理和错误页面
- **API 版本控制**：为后续 API 扩展预留版本管理

### 14.5 部署建议

- **进程管理**：使用 Supervisor/Systemd 管理进程
- **反向代理**：使用 Nginx 作为反向代理
- **容器化**：使用 Docker 容器化部署
- **CI/CD**：搭建自动化构建和部署流程

---

## 附录

### A. 依赖清单

```
tornado==6.5.5
```

### B. 端口说明

| 端口 | 用途 |
|------|------|
| 10086 | Tornado HTTP 服务端口 |

### C. 关键文件速查

| 文件 | 路径 | 作用 |
|------|------|------|
| 主入口 | `app.py` | 服务启动与配置 |
| 基础 Handler | `app/controllers/base.py` | 公共认证逻辑 |
| 认证控制器 | `app/controllers/auth.py` | 登录/退出 |
| 首页控制器 | `app/controllers/home.py` | 后台首页 |
| 数据库连接 | `app/models/db.py` | SQLite 连接与建表 |
| 用户模型 | `app/models/user.py` | 用户数据操作 |
| 基础模板 | `app/templates/base.html` | 页面布局 |
| 登录模板 | `app/templates/login.html` | 登录页 |
| 首页模板 | `app/templates/index.html` | 后台首页 |

---

> **文档版本**：v1.0  
> **最后更新**：2026-05-23  
> **维护说明**：本文档随项目开发同步更新，确保反映最新的项目状态
