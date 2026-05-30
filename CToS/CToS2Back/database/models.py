"""
数据库模型 - 严格遵循《数据库详细设计.md》定义
包含所有表的SQLAlchemy ORM模型
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, ForeignKey, 
    UniqueConstraint, Index, text
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ============================================================
# 3.1 用户与鉴权
# ============================================================

class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="用户ID")
    username = Column(String(64), nullable=False, unique=True, comment="用户名（唯一，用于登录）")
    password_hash = Column(String(256), nullable=True, comment="密码哈希（worker用户可为NULL）")
    nickname = Column(String(64), default="", comment="用户昵称")
    avatar = Column(String(512), default="", comment="头像URL")
    role = Column(String(16), nullable=False, default="user", comment="角色: user/admin/worker")
    status = Column(String(16), nullable=False, default="active", comment="状态: active/disabled")
    permissions = Column(Text, default="[]", comment="权限列表（JSON数组）")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment="创建时间")
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment="更新时间")

    __table_args__ = (
        Index("idx_users_username", "username"),
        Index("idx_users_role", "role"),
        Index("idx_users_status", "status"),
    )


class UserSession(Base):
    """用户登录会话"""
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="会话ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="→ users.id")
    token = Column(String(256), nullable=False, unique=True, comment="JWT令牌")
    ip_address = Column(String(45), comment="登录IP")
    user_agent = Column(String(512), comment="User-Agent")
    expires_at = Column(DateTime, nullable=False, comment="过期时间")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment="创建时间")

    __table_args__ = (
        Index("idx_sessions_token", "token"),
        Index("idx_sessions_user", "user_id"),
    )


# ============================================================
# 3.2 智能问数
# ============================================================

class Conversation(Base):
    """AI对话会话"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="→ users.id")
    title = Column(String(128), default="新对话", comment="会话标题")
    model_name = Column(String(64), comment="使用的模型名称")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_conversations_user", "user_id"),
        Index("idx_conversations_updated", "updated_at"),
    )


class Message(Base):
    """AI对话消息"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, comment="→ conversations.id")
    role = Column(String(16), nullable=False, comment="角色: user/assistant/system")
    content = Column(Text, comment="消息内容")
    tokens_used = Column(Integer, default=0, comment="Token消耗")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_messages_conversation", "conversation_id"),
        Index("idx_messages_created", "created_at"),
    )


# ============================================================
# 3.3 智能瞭望
# ============================================================

class WatchSource(Base):
    """瞭望采集源"""
    __tablename__ = "watch_sources"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="源ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="创建者")
    name = Column(String(128), nullable=False, comment="采集源名称")
    url = Column(String(1024), nullable=False, comment="目标URL")
    method = Column(String(16), nullable=False, default="GET", comment="请求方法")
    headers = Column(Text, default="{}", comment="JSON自定义请求头")
    body_template = Column(Text, comment="请求体模板")
    interval_seconds = Column(Integer, nullable=False, default=3600, comment="采集间隔（秒）")
    enabled = Column(Integer, nullable=False, default=1, comment="启用: 1/0")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_watchsources_user", "user_id"),
        Index("idx_watchsources_enabled", "enabled"),
    )


class WatchData(Base):
    """采集的原始数据"""
    __tablename__ = "watch_data"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="数据ID")
    source_id = Column(Integer, ForeignKey("watch_sources.id", ondelete="CASCADE"), nullable=False, comment="瞭望源ID")
    raw_response = Column(Text, comment="原始响应（截断10000字符）")
    parsed_data = Column(Text, comment="解析后的JSON结构化数据")
    status = Column(String(16), nullable=False, default="success", comment="采集状态: success/error")
    error_message = Column(Text, comment="错误信息")
    http_status = Column(Integer, comment="HTTP状态码")
    collected_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment="采集时间")

    __table_args__ = (
        Index("idx_watchdata_source", "source_id"),
        Index("idx_watchdata_status", "status"),
        Index("idx_watchdata_collected", "collected_at"),
    )


# ============================================================
# 3.4 Token 统计
# ============================================================

class TokenStat(Base):
    """Token消耗统计"""
    __tablename__ = "token_stats"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="统计ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    tokens_used = Column(Integer, nullable=False, default=0, comment="消耗Token数")
    purpose = Column(String(32), nullable=False, default="chat", comment="用途: chat/worker/dataworker/sentiment")
    model_name = Column(String(64), comment="模型名称")
    date = Column(String(10), nullable=False, comment="统计日期 YYYY-MM-DD")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("user_id", "purpose", "date", name="uk_tokenstat_day"),
        Index("idx_tokenstats_user", "user_id"),
        Index("idx_tokenstats_date", "date"),
    )


# ============================================================
# 3.5 数字员工
# ============================================================

class Job(Base):
    """工作定义"""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="工作ID")
    name = Column(String(128), nullable=False, comment="工作名称")
    code = Column(String(64), nullable=False, unique=True, comment="工作唯一编码")
    description = Column(Text, comment="工作描述")
    icon = Column(String(64), default="🤖", comment="图标")
    tool_names = Column(Text, default="[]", comment="关联工具名称列表（JSON数组）")
    prompt_template = Column(Text, comment="工具调用提示词模板")
    is_preset = Column(Integer, default=0, comment="是否预设: 1/0")
    sort_order = Column(Integer, default=0, comment="排序值")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_jobs_code", "code"),
        Index("idx_jobs_sort", "sort_order"),
    )


class Tool(Base):
    """注册工具"""
    __tablename__ = "tools"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="工具ID")
    name = Column(String(64), nullable=False, unique=True, comment="工具名称")
    description = Column(Text, comment="工具描述")
    function_schema = Column(Text, nullable=False, comment="JSON Schema格式的函数签名")
    module_path = Column(String(256), comment="工具函数模块路径")
    is_builtin = Column(Integer, default=0, comment="是否内置: 1/0")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_tools_name", "name"),
    )


class Worker(Base):
    """数字员工"""
    __tablename__ = "workers"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="员工ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, comment="→ users.id（role=worker）")
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, comment="→ jobs.id")
    name = Column(String(128), nullable=False, comment="员工名称")
    icon = Column(String(64), default="🤖", comment="图标")
    description = Column(Text, comment="员工描述")
    system_prompt = Column(Text, comment="人格提示词")
    api_key_id = Column(Integer, ForeignKey("api_keys.id", ondelete="RESTRICT"), comment="大模型配置引用")
    enabled = Column(Integer, nullable=False, default=1, comment="启用: 1/0")
    is_preset = Column(Integer, default=0, comment="是否预设: 1/0")
    sort_order = Column(Integer, default=0, comment="排序值")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_workers_user", "user_id"),
        Index("idx_workers_job", "job_id"),
        Index("idx_workers_enabled", "enabled"),
        Index("idx_workers_sort", "sort_order"),
    )


class ExecutionLog(Base):
    """执行记录"""
    __tablename__ = "execution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="执行ID")
    worker_id = Column(Integer, ForeignKey("workers.id", ondelete="CASCADE"), nullable=False, comment="→ workers.id")
    cleaning_log_id = Column(Integer, ForeignKey("cleaning_logs.id", ondelete="CASCADE"), unique=True, comment="关联清洗记录")
    sentiment_analysis_id = Column(Integer, ForeignKey("sentiment_analyses.id", ondelete="CASCADE"), comment="关联舆情分析")
    user_query = Column(Text, comment="用户查询内容")
    final_response = Column(Text, comment="最终回复")
    status = Column(String(16), nullable=False, default="processing", comment="状态: processing/success/error")
    tokens_used = Column(Integer, default=0, comment="Token消耗")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_executionlogs_worker", "worker_id"),
        Index("idx_executionlogs_status", "status"),
        Index("idx_executionlogs_created", "created_at"),
    )


class ExecutionMessage(Base):
    """执行消息（多轮工具调用日志）"""
    __tablename__ = "execution_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_log_id = Column(Integer, ForeignKey("execution_logs.id", ondelete="CASCADE"), nullable=False, comment="执行记录ID")
    role = Column(String(16), nullable=False, comment="角色: system/user/assistant/tool")
    content = Column(Text, comment="消息内容")
    tool_call_id = Column(String(64), comment="工具调用ID")
    tool_calls_json = Column(Text, comment="JSON工具调用列表")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_executionmsgs_log", "execution_log_id"),
    )


# ============================================================
# 3.6 数据清洗
# ============================================================

class CleaningLog(Base):
    """清洗工作执行记录"""
    __tablename__ = "cleaning_logs"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="清洗记录ID")
    watch_data_id = Column(Integer, ForeignKey("watch_data.id", ondelete="CASCADE"), nullable=False, comment="关联的原始采集数据")
    method = Column(String(16), nullable=False, default="ai", comment="清洗方法: ai/regex")
    status = Column(String(16), nullable=False, default="processing", comment="状态: processing/success/failed")
    result = Column(Text, comment="清洗结果（JSON）")
    error_message = Column(Text, comment="错误信息")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_cleaninglogs_watchdata", "watch_data_id"),
        Index("idx_cleaninglogs_status", "status"),
    )


# ============================================================
# 3.7 数据仓库
# ============================================================

class WarehouseCategory(Base):
    """数据仓库分类"""
    __tablename__ = "warehouse_categories"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="分类ID")
    name = Column(String(128), nullable=False, comment="分类名称")
    description = Column(Text, comment="分类描述")
    icon = Column(String(64), default="📁", comment="分类图标")
    sort_order = Column(Integer, default=0, comment="排序值")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_warehouse_categories_sort", "sort_order"),
    )


class WarehouseArticle(Base):
    """清洗后结构化文章"""
    __tablename__ = "warehouse_articles"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="文章ID")
    category_id = Column(Integer, ForeignKey("warehouse_categories.id", ondelete="SET NULL"), comment="分类ID")
    watch_data_id = Column(Integer, ForeignKey("watch_data.id", ondelete="CASCADE"), comment="关联原始采集数据")
    cleaning_log_id = Column(Integer, ForeignKey("cleaning_logs.id", ondelete="CASCADE"), comment="关联清洗日志")
    title = Column(String(512), comment="文章标题")
    domain_name = Column(String(256), comment="主体名称/域名")
    content = Column(Text, comment="纯文本正文")
    tags = Column(String(512), default="", comment="标签（逗号分隔）")
    url = Column(String(1024), comment="原文URL")
    status = Column(String(16), nullable=False, default="draft", comment="状态: draft/published")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_warehouse_domain", "domain_name"),
        Index("idx_warehouse_status", "status"),
        Index("idx_warehouse_created", "created_at"),
        Index("idx_warehouse_category", "category_id"),
    )


# ============================================================
# 3.8 智能聊天
# ============================================================

class Friend(Base):
    """好友关系"""
    __tablename__ = "friends"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="关系ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="本人")
    friend_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="好友")
    remark = Column(String(64), comment="备注名")
    is_blocked = Column(Integer, default=0, comment="是否拉黑: 1/0")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("user_id", "friend_id", name="uk_friendship"),
        Index("idx_friends_user", "user_id"),
        Index("idx_friends_friend", "friend_id"),
    )


class FriendRequest(Base):
    """好友申请表"""
    __tablename__ = "friend_requests"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="请求ID")
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="发送方")
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="接收方")
    message = Column(String(256), comment="申请消息")
    status = Column(String(16), nullable=False, default="pending", comment="状态: pending/accepted/rejected")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_friendreq_sender", "sender_id"),
        Index("idx_friendreq_receiver", "receiver_id"),
        Index("idx_friendreq_status", "status"),
    )


class ChatGroup(Base):
    """群组"""
    __tablename__ = "chat_groups"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="群组ID")
    name = Column(String(128), nullable=False, comment="群名称")
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="群主")
    avatar = Column(String(512), comment="群头像")
    announcement = Column(Text, comment="群公告")
    member_count = Column(Integer, default=0, comment="成员数")
    status = Column(String(16), nullable=False, default="active", comment="状态: active/banned")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_groups_owner", "owner_id"),
        Index("idx_groups_status", "status"),
    )


class GroupMember(Base):
    """群成员"""
    __tablename__ = "group_members"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="成员ID")
    group_id = Column(Integer, ForeignKey("chat_groups.id", ondelete="CASCADE"), nullable=False, comment="群组ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    role = Column(String(16), nullable=False, default="member", comment="角色: owner/admin/member")
    joined_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uk_group_member"),
        Index("idx_groupmembers_group", "group_id"),
        Index("idx_groupmembers_user", "user_id"),
    )


class ChatMessage(Base):
    """聊天消息"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="消息ID")
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="发送者")
    receiver_id = Column(Integer, nullable=False, comment="接收方ID（用户或群组）")
    receiver_type = Column(String(16), nullable=False, comment="接收类型: user/group")
    type = Column(String(32), nullable=False, default="text", comment="消息类型: text/emoji/sticker/file/image/system")
    content = Column(Text, comment="消息内容")
    mentions = Column(Text, default="[]", comment="被@的用户ID列表（JSON数组）")
    file_id = Column(Integer, ForeignKey("files.id", ondelete="SET NULL"), comment="关联文件")
    reply_to = Column(Integer, comment="回复的消息ID")
    weather_effect = Column(String(64), comment="天气效果类型")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_chatmessages_receiver", "receiver_id", "receiver_type"),
        Index("idx_chatmessages_sender", "sender_id"),
        Index("idx_chatmessages_created", "created_at"),
    )


class ChatServer(Base):
    """聊天服务器配置"""
    __tablename__ = "chat_servers"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="服务器ID")
    name = Column(String(128), nullable=False, comment="服务器名称")
    url = Column(String(512), nullable=False, comment="服务器地址")
    status = Column(String(16), nullable=False, default="offline", comment="状态: online/offline/error")
    priority = Column(Integer, nullable=False, default=0, comment="优先级")
    enabled = Column(Integer, nullable=False, default=1, comment="启用: 1/0")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_chatservers_priority", "priority"),
        Index("idx_chatservers_enabled", "enabled"),
    )


class MessageRead(Base):
    """消息已读记录"""
    __tablename__ = "message_reads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    last_read_msg_id = Column(Integer, nullable=False, comment="最后已读消息ID")
    receiver_type = Column(String(16), nullable=False, comment="类型: user/group")
    receiver_id = Column(Integer, nullable=False, comment="对方ID（用户或群组）")
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("user_id", "receiver_type", "receiver_id", name="uk_msgread"),
        Index("idx_msgread_user", "user_id"),
    )


# ============================================================
# 3.9 文件管理
# ============================================================

class File(Base):
    """上传文件记录"""
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="文件ID")
    file_name = Column(String(256), nullable=False, comment="原始文件名")
    file_path = Column(String(512), nullable=False, comment="服务器存储路径")
    file_size = Column(Integer, nullable=False, comment="文件大小（字节）")
    md5_hash = Column(String(64), nullable=False, comment="MD5哈希（去重）")
    mime_type = Column(String(128), comment="MIME类型")
    uploader_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="上传者")
    chat_message_id = Column(Integer, comment="关联的消息ID")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_files_md5", "md5_hash"),
        Index("idx_files_uploader", "uploader_id"),
        Index("idx_files_chatmsg", "chat_message_id"),
    )


# ============================================================
# 3.10 系统配置
# ============================================================

class SystemConfig(Base):
    """系统配置键值表"""
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="配置ID")
    key = Column(String(128), nullable=False, unique=True, comment="配置键")
    value = Column(Text, comment="配置值（JSON格式）")
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_config_key", "key"),
    )


class SystemLog(Base):
    """系统操作日志"""
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="日志ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), comment="操作用户")
    action = Column(String(64), nullable=False, comment="操作类型")
    target = Column(String(128), comment="操作目标")
    detail = Column(Text, comment="操作详情（JSON格式）")
    ip_address = Column(String(45), comment="客户端IP")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_systemlogs_user", "user_id"),
        Index("idx_systemlogs_action", "action"),
        Index("idx_systemlogs_created", "created_at"),
    )


# ============================================================
# 3.11 API Key 管理
# ============================================================

class ApiKey(Base):
    """LLM API密钥配置"""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="密钥ID")
    name = Column(String(128), nullable=False, comment="配置名称")
    provider = Column(String(64), default="openai", comment="提供商")
    base_url = Column(String(512), nullable=False, comment="API地址")
    api_key = Column(String(512), nullable=False, comment="API密钥")
    model_name = Column(String(64), comment="模型名称")
    max_tokens = Column(Integer, default=4096, comment="最大Token数")
    temperature = Column(Float, default=0.7, comment="温度参数")
    top_p = Column(Float, default=1.0, comment="Top-P参数")
    enabled = Column(Integer, nullable=False, default=1, comment="启用: 1/0")
    purpose = Column(String(32), nullable=False, default="chat", comment="用途: chat/dataworker/all")
    sort_order = Column(Integer, default=0, comment="排序值")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_apikeys_purpose", "purpose"),
        Index("idx_apikeys_enabled", "enabled"),
        Index("idx_apikeys_sort", "sort_order"),
    )


# ============================================================
# 3.12 智慧舆情
# ============================================================

class SentimentAnalysis(Base):
    """舆情分析任务"""
    __tablename__ = "sentiment_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="分析任务ID")
    trigger_type = Column(String(16), nullable=False, default="auto", comment="触发类型: auto/manual")
    articles_scope = Column(Text, comment="本次分析覆盖的文章ID范围（JSON数组）")
    status = Column(String(16), nullable=False, default="processing", comment="状态: processing/completed/failed")
    summary = Column(Text, comment="舆情分析摘要")
    overall_sentiment = Column(String(32), comment="总体舆情倾向: positive/negative/neutral/mixed")
    articles_analyzed = Column(Integer, default=0, comment="本次分析的文章数")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_sentiment_analyses_created", "created_at"),
        Index("idx_sentiment_analyses_status", "status"),
    )


class SentimentEvent(Base):
    """舆情事件"""
    __tablename__ = "sentiment_events"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="事件ID")
    analysis_id = Column(Integer, ForeignKey("sentiment_analyses.id", ondelete="CASCADE"), nullable=False, comment="分析任务ID")
    event_name = Column(String(256), nullable=False, comment="事件名称")
    sentiment_type = Column(String(32), nullable=False, default="neutral", comment="舆情倾向: positive/negative/neutral")
    description = Column(Text, comment="事件描述")
    keywords_json = Column(Text, comment="关键词（JSON数组）")
    heat = Column(Integer, default=0, comment="热度")
    related_article_ids = Column(Text, comment="关联文章ID列表（JSON数组）")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_sentiment_events_analysis", "analysis_id"),
    )


class SentimentWord(Base):
    """舆情关键词（词云）"""
    __tablename__ = "sentiment_words"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="关键词ID")
    analysis_id = Column(Integer, ForeignKey("sentiment_analyses.id", ondelete="CASCADE"), nullable=False, comment="分析任务ID")
    word = Column(String(128), nullable=False, comment="关键词")
    weight = Column(Float, default=0.0, comment="权重")
    sentiment_type = Column(String(32), default="neutral", comment="情感倾向")
    category = Column(String(32), default="topic", comment="分类")

    __table_args__ = (
        Index("idx_sentiment_words_analysis", "analysis_id"),
    )


class SentimentLocation(Base):
    """舆情地点"""
    __tablename__ = "sentiment_locations"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="地点ID")
    event_id = Column(Integer, ForeignKey("sentiment_events.id", ondelete="CASCADE"), nullable=False, comment="事件ID")
    location_name = Column(String(128), nullable=False, comment="地点名称")
    longitude = Column(Float, default=0.0, comment="经度")
    latitude = Column(Float, default=0.0, comment="纬度")
    heat = Column(Integer, default=0, comment="热度")
    description = Column(Text, comment="描述")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_sentiment_locations_event", "event_id"),
    )


class SentimentDashboard(Base):
    """舆情大屏数据快照"""
    __tablename__ = "sentiment_dashboards"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="快照ID")
    total_articles = Column(Integer, default=0, comment="总文章数")
    positive_count = Column(Integer, default=0, comment="正面舆情数")
    negative_count = Column(Integer, default=0, comment="负面舆情数")
    neutral_count = Column(Integer, default=0, comment="中性舆情数")
    total_events = Column(Integer, default=0, comment="事件总数")
    avg_heat = Column(Float, default=0.0, comment="平均热度")
    top_words_json = Column(Text, comment="Top词云（JSON数组）")
    top_events_json = Column(Text, comment="Top事件（JSON数组）")
    snapshot_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment="快照时间")

    __table_args__ = (
        Index("idx_sentiment_dashboards_snapshot", "snapshot_at"),
    )


# ============================================================
# 3.14 自动工作流
# ============================================================

class WorkflowTask(Base):
    """自动工作流任务"""
    __tablename__ = "workflow_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="任务ID")
    name = Column(String(128), nullable=False, comment="任务名称")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="创建者")
    status = Column(String(16), nullable=False, default="pending", comment="状态: pending/running/completed/failed/cancelled")
    steps_config = Column(Text, comment="步骤配置（JSON）: [{step_type, source_ids, ...}]")
    total_steps = Column(Integer, default=0, comment="总步骤数")
    current_step = Column(Integer, default=0, comment="当前步骤索引")
    error_message = Column(Text, comment="错误信息")
    started_at = Column(DateTime, comment="开始时间")
    completed_at = Column(DateTime, comment="完成时间")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_workflow_user", "user_id"),
        Index("idx_workflow_status", "status"),
        Index("idx_workflow_created", "created_at"),
    )


class WorkflowTaskLog(Base):
    """工作流任务步骤日志"""
    __tablename__ = "workflow_task_logs"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="日志ID")
    task_id = Column(Integer, ForeignKey("workflow_tasks.id", ondelete="CASCADE"), nullable=False, comment="任务ID")
    step_index = Column(Integer, nullable=False, comment="步骤索引（从0开始）")
    step_name = Column(String(64), nullable=False, comment="步骤名称: collect/sentiment")
    step_label = Column(String(128), comment="步骤显示名称")
    status = Column(String(16), nullable=False, default="pending", comment="状态: pending/running/completed/failed/skipped")
    target_id = Column(Integer, comment="关联目标ID（瞭望源ID/舆情分析ID）")
    target_name = Column(String(128), comment="目标名称")
    result = Column(Text, comment="步骤结果（JSON）")
    error_message = Column(Text, comment="错误信息")
    started_at = Column(DateTime, comment="步骤开始时间")
    completed_at = Column(DateTime, comment="步骤完成时间")
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        Index("idx_wftasklog_task", "task_id"),
        Index("idx_wftasklog_status", "status"),
    )