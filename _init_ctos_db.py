"""初始化 CToS 数据库，从 cnAgentOS 的默认模型同步 API Key"""
import os
import sys
import asyncio
import sqlite3

# 切换到 CToS 工作目录
ctos_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CToS", "CToS2Back")
ctos_dir = os.path.normpath(ctos_dir)
os.chdir(ctos_dir)
sys.path.insert(0, ctos_dir)

# 读取 cnAgentOS 默认模型配置
root_dir = os.path.dirname(os.path.abspath(__file__))
app_db = os.path.join(root_dir, "database", "app.db")
conn = sqlite3.connect(app_db)
conn.row_factory = sqlite3.Row
row = conn.execute(
    "SELECT api_url, api_key, code FROM models WHERE is_system_default=1 AND status=1"
).fetchone()
conn.close()

if not row:
    print("❌ cnAgentOS 中没有配置默认模型")
    exit(1)

model_api_url = row["api_url"]
model_api_key = row["api_key"]
model_code = row["code"]
print(f"✅ 读取到默认模型: {model_code}")
# OpenAI 客户端会自动追加 /chat/completions，所以 base_url 要去掉尾部
base_url = model_api_url.replace("/chat/completions", "")
print(f"   api_url: {base_url}")
print(f"   api_key: {model_api_key[:20]}...")

# 初始化 CToS 数据库
async def init_ctos():
    from database.engine import db_manager, init_db
    from database.models import ApiKey
    from sqlalchemy import select

    # 初始化数据库（创建表）
    await init_db()
    print("✅ CToS 数据库初始化完成")

    # 检查是否已有 api key
    async with db_manager.get_session() as session:
        stmt = select(ApiKey).where(ApiKey.sort_order == -1)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            print(f"ℹ️ 已存在 sort_order=-1 的 API Key（id={existing.id}），更新配置")
            existing.base_url = base_url
            existing.api_key = model_api_key
            existing.model_name = model_code
        else:
            print("🆕 插入新的 API Key（sort_order=-1，最高优先级）")
            new_key = ApiKey(
                name="cnAgentOS 默认模型",
                provider="openai",
                base_url=base_url,
                api_key=model_api_key,
                model_name=model_code,
                max_tokens=4096,
                temperature=0.7,
                top_p=1.0,
                enabled=1,
                purpose="all",
                sort_order=-1,
            )
            session.add(new_key)

        await session.commit()
        print("✅ API Key 写入成功（sort_order=-1，最高优先级）")

        # 验证
        stmt = select(ApiKey).order_by(ApiKey.sort_order).limit(5)
        result = await session.execute(stmt)
        keys = result.scalars().all()
        print(f"\n📋 当前 API Keys 列表:")
        for k in keys:
            print(f"   id={k.id}  name={k.name}  base_url={k.base_url}  sort_order={k.sort_order}  enabled={k.enabled}")

asyncio.run(init_ctos())
print("\n🎉 CToS 数据库初始化完成！")
