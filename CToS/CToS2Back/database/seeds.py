"""数据库种子数据"""
import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.engine import db_manager
from database.models import User, Worker, Job, Tool, SystemConfig, ApiKey, WatchSource
from utils.helpers import hash_password

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"
DEFAULT_API_KEY_NAME = "默认DeepSeek"
DEFAULT_API_KEY = ""
DEFAULT_API_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"

async def seed_default_data():
    """插入预设数据（仅当表为空时）"""
    async with db_manager.get_session() as session:
        # 1. 创建默认管理员
        result = await session.execute(select(User).where(User.username == DEFAULT_ADMIN_USERNAME))
        if not result.scalar_one_or_none():
            admin = User(
                username=DEFAULT_ADMIN_USERNAME,
                password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
                nickname="系统管理员",
                role="admin",
                status="active",
                permissions=json.dumps(["*"])
            )
            session.add(admin)
            await session.flush()

        # 1.1 创建预设测试用户
        test_users = [
            {
                "username": "1",
                "password": "123456",
                "nickname": "用户1",
                "role": "user",
                "status": "active",
            },
            {
                "username": "2",
                "password": "123456",
                "nickname": "用户2",
                "role": "user",
                "status": "active",
            },
        ]
        for user_data in test_users:
            result = await session.execute(select(User).where(User.username == user_data["username"]))
            if not result.scalar_one_or_none():
                user = User(
                    username=user_data["username"],
                    password_hash=hash_password(user_data["password"]),
                    nickname=user_data["nickname"],
                    role=user_data["role"],
                    status=user_data["status"],
                    permissions=json.dumps([]),
                )
                session.add(user)
        await session.flush()

        # 2. 创建默认API Key配置（仅一个DeepSeek Key，purpose=all 覆盖所有用途）
        result = await session.execute(select(ApiKey).where(ApiKey.name == DEFAULT_API_KEY_NAME))
        if not result.scalar_one_or_none():
            api_key = ApiKey(
                name=DEFAULT_API_KEY_NAME,
                provider="openai",
                base_url=DEFAULT_API_BASE_URL,
                api_key=DEFAULT_API_KEY,
                model_name=DEFAULT_MODEL,
                max_tokens=102400,
                temperature=0.7,
                top_p=1.0,
                enabled=1,
                purpose="all",
                sort_order=0
            )
            session.add(api_key)
            await session.flush()

        # ---- 注册天气工具 ----
        weather_tools_data = [
            {
                "name": "get_weather",
                "description": "通过wttr.in免费天气API获取指定城市的实时天气数据，支持国内及国外主要城市",
                "function_schema": json.dumps({
                    "name": "get_weather",
                    "description": "获取指定城市的实时天气信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city_name": {"type": "string", "description": "城市名称，支持中文（如：北京、上海、东京、伦敦）"}
                        },
                        "required": ["city_name"]
                    }
                }, ensure_ascii=False),
                "is_builtin": 1,
                "module_path": "tools.weather_tools.get_weather"
            },
            {
                "name": "send_weather_card",
                "description": "根据天气数据生成一张精美的天气卡片图片并发送到群聊。获取天气后必须调用此工具将天气信息以图片形式展示给群成员。所有字段均可选，建议尽可能多传参数以展示更丰富的信息。",
                "function_schema": json.dumps({
                    "name": "send_weather_card",
                    "description": "根据天气数据生成天气卡片图片并发送到群聊",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "城市名称，如北京"},
                            "temp_c": {"type": "string", "description": "当前温度，如25"},
                            "feelslike_c": {"type": "string", "description": "体感温度，如26"},
                            "weather_desc": {"type": "string", "description": "天气描述，如☀️ 晴"},
                            "weather_effect": {"type": "string", "description": "天气特效类型，可选值: sunny/cloudy/rainy/snowy/stormy/foggy"},
                            "humidity": {"type": "string", "description": "湿度百分比，如60"},
                            "wind_kph": {"type": "string", "description": "风速km/h"},
                            "wind_dir": {"type": "string", "description": "风向，如南风"}
                        },
                        "required": ["city", "temp_c"]
                    }
                }, ensure_ascii=False),
                "is_builtin": 1,
                "module_path": "tools.weather_tools.send_weather_card"
            },
        ]
        for wt in weather_tools_data:
            result = await session.execute(select(Tool).where(Tool.name == wt["name"]))
            if not result.scalar_one_or_none():
                session.add(Tool(**wt))
        await session.flush()

        # 3. 创建预设工作(Jobs) - 包含数据清洗和舆情分析
        preset_jobs = [
            {
                "name": "通用对话", "code": "general_chat",
                "description": "通用对话助手",
                "icon": "💬",
                "prompt_template": "你是一个有用的AI助手。请回答用户的问题。",
                "tool_names": "[]",
                "sort_order": 0, "is_preset": 1
            },
            {
                "name": "代码助手", "code": "code_assistant",
                "description": "帮助编写和审查代码",
                "icon": "💻",
                "prompt_template": "你是一个专业的编程助手。请帮助用户解决编程问题。\n\n可用工具：\n{tools}",
                "tool_names": '["execute_python"]',
                "sort_order": 1, "is_preset": 1
            },
            {
                "name": "数据清洗", "code": "data_cleaner",
                "description": "使用AI清洗和结构化采集数据",
                "icon": "🧹",
                "prompt_template": "你是一个数据清洗专家。请分析并结构化以下原始数据。\n\n原始数据：\n{input_data}\n\n请提取关键信息并以JSON格式返回。",
                "tool_names": '["extract_structural_info", "clean_html_content", "parse_json_data", "validate_result", "extract_domain"]',
                "sort_order": 2, "is_preset": 1
            },
            {
                "name": "舆情分析", "code": "sentiment_analysis",
                "description": "分析舆情数据和情感倾向",
                "icon": "📊",
                "prompt_template": "你是一个舆情分析专家。请分析以下文章数据，提取舆情信息。\n\n文章数据：\n{input_data}",
                "tool_names": '["classify_sentiment", "extract_keywords", "detect_events", "extract_locations", "generate_summary"]',
                "sort_order": 3, "is_preset": 1
            },
            {
                "name": "数据汇总", "code": "data_summary",
                "description": "汇总和总结瞭望采集的数据",
                "icon": "📝",
                "prompt_template": "请对以下数据进行汇总总结：\n{input_data}",
                "tool_names": "[]",
                "sort_order": 4, "is_preset": 1
            },
        ]
        for job_data in preset_jobs:
            result = await session.execute(select(Job).where(Job.code == job_data["code"]))
            if not result.scalar_one_or_none():
                session.add(Job(**job_data))
        await session.flush()

        # 4. 创建内置工具 - 包含数据清洗、舆情分析工具
        builtin_tools = [
            # ---- 通用工具 ----
            {
                "name": "execute_python",
                "description": "执行Python代码并返回结果",
                "function_schema": json.dumps({
                    "name": "execute_python",
                    "description": "在沙箱环境中执行Python代码",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "要执行的Python代码"}
                        },
                        "required": ["code"]
                    }
                }, ensure_ascii=False),
                "is_builtin": 1
            },
            # ---- 数据清洗工具（5个） ----
            {
                "name": "extract_structural_info",
                "description": "从原始采集文本中提取结构化信息（标题、正文、域名、摘要）",
                "function_schema": json.dumps({
                    "name": "extract_structural_info",
                    "description": "从原始采集文本中提取结构化信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "raw_text": {"type": "string", "description": "原始采集数据文本"},
                            "instructions": {"type": "string", "description": "额外的清洗指令"}
                        },
                        "required": ["raw_text"]
                    }
                }, ensure_ascii=False),
                "is_builtin": 1,
                "module_path": "tools.cleaning_tools.extract_structural_info"
            },
            {
                "name": "clean_html_content",
                "description": "清洗HTML标签，提取纯文本内容",
                "function_schema": json.dumps({
                    "name": "clean_html_content",
                    "description": "清洗HTML标签，提取纯文本",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "html_text": {"type": "string", "description": "含HTML标签的文本"},
                            "remove_scripts": {"type": "boolean", "description": "是否移除script/style标签"}
                        },
                        "required": ["html_text"]
                    }
                }, ensure_ascii=False),
                "is_builtin": 1,
                "module_path": "tools.cleaning_tools.clean_html_content"
            },
            {
                "name": "parse_json_data",
                "description": "尝试解析JSON格式的采集数据",
                "function_schema": json.dumps({
                    "name": "parse_json_data",
                    "description": "解析JSON格式的采集数据",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "raw_json_str": {"type": "string", "description": "JSON字符串"}
                        },
                        "required": ["raw_json_str"]
                    }
                }, ensure_ascii=False),
                "is_builtin": 1,
                "module_path": "tools.cleaning_tools.parse_json_data"
            },
            {
                "name": "validate_result",
                "description": "验证清洗结果是否完整有效",
                "function_schema": json.dumps({
                    "name": "validate_result",
                    "description": "验证清洗结果完整性",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "cleaned_data": {"type": "object", "description": "清洗后的结构化数据"}
                        },
                        "required": ["cleaned_data"]
                    }
                }, ensure_ascii=False),
                "is_builtin": 1,
                "module_path": "tools.cleaning_tools.validate_result"
            },
            {
                "name": "extract_domain",
                "description": "从URL中提取域名（去www.前缀）",
                "function_schema": json.dumps({
                    "name": "extract_domain",
                    "description": "从URL中提取域名",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "完整URL或域名"}
                        },
                        "required": ["url"]
                    }
                }, ensure_ascii=False),
                "is_builtin": 1,
                "module_path": "tools.cleaning_tools.extract_domain"
            },
            # ---- 舆情分析工具（5个） ----
            {
                "name": "classify_sentiment",
                "description": "对文本进行情感倾向分类（positive/negative/neutral）",
                "function_schema": json.dumps({
                    "name": "classify_sentiment",
                    "description": "对文本进行情感倾向分类",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "待分析的文本"}
                        },
                        "required": ["text"]
                    }
                }, ensure_ascii=False),
                "is_builtin": 1,
                "module_path": "tools.sentiment_tools.classify_sentiment"
            },
            {
                "name": "extract_keywords",
                "description": "从文本中提取关键词及权重",
                "function_schema": json.dumps({
                    "name": "extract_keywords",
                    "description": "提取文本关键词",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "待分析的文本"},
                            "max_keywords": {"type": "integer", "description": "最大关键词数量"}
                        },
                        "required": ["text"]
                    }
                }, ensure_ascii=False),
                "is_builtin": 1,
                "module_path": "tools.sentiment_tools.extract_keywords"
            },
            {
                "name": "detect_events",
                "description": "从一批文章中检测舆情事件",
                "function_schema": json.dumps({
                    "name": "detect_events",
                    "description": "检测舆情事件",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "articles": {
                                "type": "array",
                                "description": "文章列表（每项含title, content, domain_name, id）"
                            }
                        },
                        "required": ["articles"]
                    }
                }, ensure_ascii=False),
                "is_builtin": 1,
                "module_path": "tools.sentiment_tools.detect_events"
            },
            {
                "name": "extract_locations",
                "description": "从文本中提取地理位置信息",
                "function_schema": json.dumps({
                    "name": "extract_locations",
                    "description": "提取地理位置信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "待分析的文本"}
                        },
                        "required": ["text"]
                    }
                }, ensure_ascii=False),
                "is_builtin": 1,
                "module_path": "tools.sentiment_tools.extract_locations"
            },
            {
                "name": "generate_summary",
                "description": "根据舆情分析结果生成分析摘要",
                "function_schema": json.dumps({
                    "name": "generate_summary",
                    "description": "生成舆情分析摘要",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "analysis_result": {
                                "type": "object",
                                "description": "包含events, words, sentiment_counts的dict"
                            }
                        },
                        "required": ["analysis_result"]
                    }
                }, ensure_ascii=False),
                "is_builtin": 1,
                "module_path": "tools.sentiment_tools.generate_summary"
            },
        ]
        for tool_data in builtin_tools:
            result = await session.execute(select(Tool).where(Tool.name == tool_data["name"]))
            if not result.scalar_one_or_none():
                session.add(Tool(**tool_data))
        await session.flush()

        # 5. 创建预设配置
        config_items = {
            "disable_register": "false",
            "max_file_size": "10485760",
            "system_name": "CToS智能系统",
        }
        for key, value in config_items.items():
            result = await session.execute(select(SystemConfig).where(SystemConfig.key == key))
            if not result.scalar_one_or_none():
                session.add(SystemConfig(key=key, value=value))

        # 6. 为每个预设 Job 创建默认 Worker（确保数字员工至少有一个可用的默认员工）
        #    先获取第一个可用的 API Key（即使是假的也可以）
        api_key_result = await session.execute(select(ApiKey).order_by(ApiKey.sort_order).limit(1))
        default_api_key = api_key_result.scalar_one_or_none()

        if default_api_key:
            # 获取所有预设 job
            job_result = await session.execute(select(Job).where(Job.is_preset == 1))
            all_jobs = job_result.scalars().all()

            for job in all_jobs:
                # 检查该 job 是否已有 worker
                existing = await session.execute(
                    select(Worker).where(Worker.job_id == job.id).limit(1)
                )
                if not existing.scalar_one_or_none():
                    # 创建 role='worker' 的 User 记录
                    worker_username = f"default_{job.code}"
                    user = User(
                        username=worker_username,
                        password_hash=None,
                        nickname=f"默认{job.name}",
                        role="worker",
                        status="active",
                    )
                    session.add(user)
                    await session.flush()

                    # 创建 Worker 记录，user_id 指向新创建的 worker 用户
                    worker = Worker(
                        user_id=user.id,
                        job_id=job.id,
                        name=f"默认{job.name}",
                        icon=job.icon or "🤖",
                        description=f"系统预设的{job.name}数字员工",
                        system_prompt=f"你是{job.name}助手，请专业地回答用户问题。",
                        api_key_id=default_api_key.id,
                        enabled=1,
                        is_preset=1,
                        sort_order=job.sort_order,
                    )
                    session.add(worker)

        # 7. 创建聊天专用的三个数字员工（川农小助手、天气小助手、毒鸡汤助手）
        chat_worker_jobs = [
            {
                "name": "川农助手", "code": "sicau_assistant",
                "description": "关于川农（四川农业大学）的限定范围问题聊天",
                "icon": "🌾",
                "prompt_template": (
                    "你是一个专注于四川农业大学（川农）相关话题的助手。\n"
                    "你可以回答关于川农的以下方面问题：\n"
                    "1. 川农的历史、校训、校风\n"
                    "2. 川农的校区（雅安、成都、都江堰）及各校区情况\n"
                    "3. 川农的专业设置、学院分布\n"
                    "4. 川农的校园生活、社团活动\n"
                    "5. 川农的招生政策、录取分数线\n"
                    "6. 川农的科研成果、知名校友\n"
                    "7. 川农的就业情况、校园招聘\n\n"
                    "请注意：如果用户问到与川农无关的问题，请礼貌地表示你只了解川农相关话题。\n\n"
                    "用户问题：{user_query}"
                ),
                "tool_names": "[]",
                "sort_order": 10, "is_preset": 1
            },
            {
                "name": "天气助手", "code": "weather_assistant",
                "description": "输入城市名，返回指定城市天气信息",
                "icon": "🌤️",
                "prompt_template": (
                    '你是天气小助手，负责提供城市天气预报。\n\n'
                    '===== 强制工具调用规则（必须遵守）=====\n'
                    '当你查询天气时，必须严格按照以下流程执行：\n'
                    '1. 先调用 get_weather 工具获取城市的实时天气数据\n'
                    '2. 获取数据后，**必须**调用 send_weather_card 工具生成天气卡片图片并发送到群聊\n'
                    '3. 最后用文字简要回复用户，例如"已为您生成{城市}天气卡片~"\n\n'
                    '⚠️ 特别注意：\n'
                    '- 拿到 get_weather 结果后，**不允许**跳过 send_weather_card 直接输出文字\n'
                    '- 即使你认为数据可以直接回复，也必须先调用 send_weather_card 发送图片\n'
                    '- send_weather_card 需要传入的参数来自 get_weather 的返回结果\n'
                    '- 如果你跳过了 send_weather_card，会是一次业务错误\n'
                    '===============================\n\n'
                    '用户问题：{user_query}'
                ),
                "tool_names": '["get_weather", "send_weather_card"]',
                "sort_order": 11, "is_preset": 1
            },
            {
                "name": "毒鸡汤", "code": "poison_chicken_soup",
                "description": "随机回复毒鸡汤语句，让人清醒的扎心语录",
                "icon": "🧪",
                "prompt_template": (
                    "你是毒鸡汤助手，专长是用尖锐而幽默的方式讲出扎心的大实话。\n"
                    "请根据用户的输入，随机回复一条毒鸡汤语录。\n"
                    "毒鸡汤应当：\n"
                    "1. 简短有力，一两句话即可\n"
                    "2. 带有黑色幽默或反讽色彩\n"
                    "3. 既要扎心又要让人会心一笑\n"
                    "4. 可以根据用户输入内容进行针对性回复\n"
                    "5. 不要过于恶毒或人身攻击，保持幽默底线\n\n"
                    "示例风格：\n"
                    "- \u201c努力不一定成功，但不努力一定很舒服。\u201d\n"
                    "- \u201c你以为你是主角，其实你连NPC都不如。\u201d\n"
                    "- \u201c加油，你是最胖的！\u201d\n\n"
                    "用户问题：{user_query}"
                ),
                "tool_names": "[]",
                "sort_order": 12, "is_preset": 1
            },
        ]
        for job_data in chat_worker_jobs:
            result = await session.execute(select(Job).where(Job.code == job_data["code"]))
            if not result.scalar_one_or_none():
                session.add(Job(**job_data))
        await session.flush()

        # 8. 为三个聊天数字员工创建 Worker
        chat_jobs_codes = ["sicau_assistant", "weather_assistant", "poison_chicken_soup"]
        for job_code in chat_jobs_codes:
            job_result = await session.execute(select(Job).where(Job.code == job_code))
            job = job_result.scalar_one_or_none()
            if not job:
                continue
            # 检查该 job 是否已有 worker
            existing = await session.execute(
                select(Worker).where(Worker.job_id == job.id).limit(1)
            )
            if not existing.scalar_one_or_none():
                worker_username = f"default_{job.code}"
                user = User(
                    username=worker_username,
                    password_hash=None,
                    nickname=job.name,
                    role="worker",
                    status="active",
                )
                session.add(user)
                await session.flush()

                system_prompts = {
                    "sicau_assistant": "你是川农小助手，身份是四川农业大学的学长/学姐。你对川农的一切了如指掌，回答亲切耐心，带有校园气息。",
                    "weather_assistant": "你是天气小助手，开朗活泼，喜欢用天气相关的emoji和生动语言描述天气。请用生动形象的方式播报天气。",
                    "poison_chicken_soup": "你是毒鸡汤助手，性格腹黑又幽默，专门用毒鸡汤语录让人清醒。语气要像看透红尘的老友。",
                }
                worker = Worker(
                    user_id=user.id,
                    job_id=job.id,
                    name=job.name,
                    icon=job.icon or "🤖",
                    description=job.description,
                    system_prompt=system_prompts.get(job_code, f"你是{job.name}，请根据工作内容回答用户问题。"),
                    api_key_id=default_api_key.id if default_api_key else None,
                    enabled=1,
                    is_preset=1,
                    sort_order=job.sort_order,
                )
                session.add(worker)

        # 9. 创建默认瞭望数据源（供简化测试）
        async def _create_watch_source(url: str, name: str):
            existing_source = await session.execute(
                select(WatchSource).where(WatchSource.url == url)
            )
            if not existing_source.scalar_one_or_none():
                # 获取 admin 用户的 ID
                admin_result = await session.execute(
                    select(User).where(User.username == DEFAULT_ADMIN_USERNAME)
                )
                admin_user = admin_result.scalar_one_or_none()
                admin_id = admin_user.id if admin_user else 1

                watch_source = WatchSource(
                    user_id=admin_id,
                    name=name,
                    url=url,
                    method="GET",
                    headers="{}",
                    interval_seconds=3600,
                    enabled=1,
                )
                session.add(watch_source)

        await _create_watch_source("https://www.ithome.com/rss/", "IT之家")
        await _create_watch_source("https://www.chinanews.com.cn/rss/scroll-news.xml", "中国新闻网")

        await session.commit()