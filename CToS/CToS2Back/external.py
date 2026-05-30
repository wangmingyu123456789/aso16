"""
外部服务独立入口
=================
在独立的端口上运行无鉴权的外部服务，调用内部数字员工（天气助手）AI 流程。
天气助手的业务流程：
  外部请求 → 通过 LLM (function calling) 理解用户意图 → 调用 get_weather 工具 → 生成天气卡片图片 →
  保存到内部数据库（正常流程）→ 截胡结果 → 转发图片URL + 文本消息到远程回调服务器
"""
import sys
import json
import uuid
import urllib.parse
from pathlib import Path

# 将项目根目录加入 sys.path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from config import settings
from utils.helpers import logger
from tools.weather_tools import get_weather, send_weather_card
from services.file_service import get_file_record_raw
from services.llm_service import call_llm, select_api_key

try:
    import httpx
except ImportError:
    httpx = None

# ── 创建外部 FastAPI 应用 ──
external_app = FastAPI(
    title="CToS2 External API",
    description="外部无鉴权服务 - 天气助手（AI 数字员工代理）",
    version="1.0.0",
)

# CORS - 允许所有来源
external_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 天气卡片图片缓存目录
CARD_CACHE_DIR = Path(__file__).parent / "data" / "weather_cards"
CARD_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── 系统提示词（天气助手人格 + 函数调用模板） ──
WEATHER_SYSTEM_PROMPT = """你是一个专业的天气助手。你通过调用 get_weather 工具来获取实时天气数据，然后以友好的自然语言播报天气。

=== 可用工具 ===

1. get_weather(city_name: str)
   - 功能：获取指定城市的实时天气数据
   - 参数：city_name - 城市名称（必须从用户输入中提取纯城市名，如"北京"、"东京"、"长沙"）
   - 返回：温度、体感温度、天气描述、湿度、风速、风向、未来3天预报等
   - 注意：city_name 必须去掉"天气"、"今天"、"怎么样"等修饰词，只保留城市名本身

=== 工作流程 ===

Step 1: 分析用户输入，提取城市名称
  - 用户可能说"北京天气"、"查一下东京的天气"、"上海今天冷吗"、"纽约"等
  - 必须去掉：天气、今天、明天、后天、查一下、怎么样、怎样、冷吗、热吗 等修饰词
  - 只保留纯城市名

Step 2: 调用 get_weather(city_name) 获取天气数据
  - 使用提取到的纯城市名调用工具
  - 如果第一次返回失败，尝试不同的城市名变体（如英文名）

Step 3: 根据 get_weather 返回的数据生成天气播报
  - 用友好的语气、适当使用 emoji 来播报天气
  - 包含：当前温度、体感温度、天气描述、湿度、风速风向
  - 如果有未来预报信息，一并告知
  - 回复简洁友好，控制在200字以内

=== 回复格式 ===

回复必须是纯文本的自然语言播报，不要包含 JSON 结构或工具调用信息。

示例播报：
"🌤 北京今天天气不错！当前温度 25°C，体感 26°C，湿度 60%，南风 15km/h，整体比较舒适。未来三天以晴为主，最高温 28°C 左右，适合外出活动～"

=== 注意 ===
- 禁止自行编造天气数据，必须通过 get_weather 工具获取
- 如果 get_weather 返回失败，请告知用户暂时无法获取该城市的天气信息
- 不要回复工具调用内部的 JSON 结构给用户看"""


# ── 请求模型 ──

class WeatherReq(BaseModel):
    """外部天气请求"""
    city: str
    conversation_id: str
    callback_url: str


# ── 工具函数 ──

def _save_card_to_file(image_bytes: bytes, city: str) -> str:
    """将天气卡片图片保存到本地文件"""
    safe_city = "".join(c if c.isalnum() or c in ('-_') else '_' for c in city)
    filename = f"weather_{safe_city}_{uuid.uuid4().hex[:8]}.png"
    filepath = CARD_CACHE_DIR / filename
    with open(filepath, "wb") as f:
        f.write(image_bytes)
    logger.info(f"天气卡片已保存: {filepath} ({len(image_bytes)} bytes)")
    return str(filepath)


async def _call_weather_tool(city: str) -> dict:
    """
    调用天气工具获取天气数据。
    先尝试直接查询，如果城市名包含"天气"等冗余词则自动清理后重试。
    """
    # 清理城市名（去掉"天气"、"怎么样"等自然语言修饰词）
    clean_city = city.strip()
    for suffix in ["天气", "怎么样", "怎样", "如何", "的天气", "今天", "明天", "后天"]:
        if clean_city.endswith(suffix):
            clean_city = clean_city[:-len(suffix)].strip()
            break
    for prefix in ["查一下", "查询", "看看", "告诉我", "播报", "今天", "明天"]:
        if clean_city.startswith(prefix):
            clean_city = clean_city[len(prefix):].strip()
            break

    logger.info(f"[天气工具] 原始城市名: '{city}' → 清理后: '{clean_city}'")

    # 如果清理后还有多余词汇，用 LLM 提取城市名
    if clean_city != city and len(clean_city) > 0:
        logger.info(f"[天气工具] 使用清理后的城市名: {clean_city}")
        weather_data = await get_weather(clean_city)
        if weather_data.get("success"):
            return weather_data
        logger.warning(f"[天气工具] 清理后查询失败 ({clean_city})，尝试用 LLM 提取城市名")

    # 用 LLM 提取城市名
    try:
        extract_prompt = [
            {"role": "system", "content": "你是一个城市名提取器。从用户的输入中提取城市名称，只返回城市名本身，不要任何其他内容。如果找不到城市名，返回'未知'。"},
            {"role": "user", "content": f"请从以下输入中提取城市名：{city}"},
        ]
        extracted_city, _, _ = await call_llm(extract_prompt, purpose="chat")
        extracted_city = extracted_city.strip().strip('"').strip("'").strip('"')
        logger.info(f"[天气工具] LLM 提取城市名: '{city}' → '{extracted_city}'")
        if extracted_city and extracted_city != "未知" and len(extracted_city) <= 10:
            weather_data = await get_weather(extracted_city)
            if weather_data.get("success"):
                return weather_data
    except Exception as e:
        logger.warning(f"[天气工具] LLM 提取城市名失败: {e}")

    # 最终保底：用原始输入查询
    logger.info(f"[天气工具] 最终使用原始城市名查询: {city}")
    return await get_weather(city)


# ── 端点1：健康检查 ──

@external_app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "service": "external", "version": "1.0.0"}


# ── 端点2：天气代理（走数字员工 AI 流程） ──

@external_app.post("/weather")
async def external_weather(req: WeatherReq):
    """
    外部天气服务代理。
    
    调用内部天气助手数字员工 AI 流程：
    1. LLM 理解用户请求（提取城市名）
    2. 调用 get_weather 工具获取实时天气
    3. 生成天气卡片图片
    4. 保存到本地
    5. 将图片URL + 文本消息分两次转发到远程回调服务器
    """
    city = req.city
    conversation_id = req.conversation_id
    callback_url = req.callback_url

    logger.info(f"[外部天气] 收到请求: city={city}, callback={callback_url}")

    if not httpx:
        logger.error("httpx 未安装，无法转发到远程服务器")
        return JSONResponse(
            status_code=500,
            content={"code": -1, "message": "缺少 httpx 库", "data": None}
        )

    # ── Step 1: 调用天气工具（智能提取城市名后查询） ──
    weather_data = await _call_weather_tool(city)
    if not weather_data.get("success"):
        err_msg = weather_data.get("error", "未知错误")
        logger.error(f"[外部天气] 天气查询失败: {err_msg}")
        return JSONResponse(
            status_code=502,
            content={
                "code": -1,
                "message": f"天气查询失败: {err_msg}",
                "data": None,
            }
        )

    actual_city = weather_data.get("city", city)
    logger.info(f"[外部天气] 天气查询成功: city={actual_city}")

    # ── Step 2: 用 LLM 生成友好的天气文本回复 ──
    try:
        temp = weather_data.get("temp_c", "?")
        feels = weather_data.get("feelslike_c", "?")
        desc = weather_data.get("weather_desc", "未知")
        humidity = weather_data.get("humidity", "?")
        wind = weather_data.get("wind_kph", "?")
        wind_dir = weather_data.get("wind_dir", "?")
        forecast = weather_data.get("forecast", [])

        # 构建天气数据的结构描述供 LLM 生成自然语言
        weather_info = {
            "city": actual_city,
            "temperature": f"{temp}°C",
            "feels_like": f"{feels}°C",
            "description": desc,
            "humidity": f"{humidity}%",
            "wind": f"{wind_dir} {wind} km/h",
        }
        if forecast:
            weather_info["forecast"] = []
            for day in forecast[:3]:
                weather_info["forecast"].append({
                    "date": day.get("date", ""),
                    "weather_desc": day.get("weather_desc", "?"),
                    "temp_range": f"{day.get('min_temp', '?')}°~{day.get('max_temp', '?')}°",
                })

        # 播报生成提示词（与天气助手数字员工一致）
        broadcast_prompt = """你是一个天气播报员。根据提供的结构化天气数据，生成一段自然流畅的天气播报文本。

=== 要求 ===
1. 语气友好自然，像是在和用户聊天
2. 适当使用 emoji 增强可读性（☀️🌤⛅🌧❄️🌡️💧💨等）
3. 必须包含：城市名、当前温度、体感温度、天气描述
4. 尽量包含：湿度、风速风向
5. 如果有未来预报（forecast），告知用户未来天气趋势
6. 回复简洁，控制在200字以内
7. 纯文本，不要包含 JSON、Markdown 标记或代码块

=== 输入数据格式 ===
{
  "city": "城市名",
  "temperature": "当前温度",
  "feels_like": "体感温度",
  "description": "天气描述（如☀️ 晴）",
  "humidity": "湿度",
  "wind": "风向风速",
  "forecast": [  // 可选
    {"date": "日期", "weather_desc": "天气", "temp_range": "温度范围"}
  ]
}

=== 输出示例 ===
"🌤 北京今天天气不错！当前温度 25°C，体感 26°C，湿度 60%，南风 15km/h，整体比较舒适。未来三天以晴为主，最高温 28°C 左右，适合外出活动～"

请根据以下天气数据生成播报："""

        llm_messages = [
            {"role": "system", "content": broadcast_prompt},
            {"role": "user", "content": json.dumps(weather_info, ensure_ascii=False, indent=2)},
        ]
        text, _, _ = await call_llm(llm_messages, purpose="chat")
        logger.info(f"[外部天气] LLM 生成天气播报成功")
    except Exception as e:
        logger.warning(f"[外部天气] LLM 生成播报失败，使用模板文本: {e}")
        # 回退到模板文本
        temp = weather_data.get("temp_c", "?")
        desc = weather_data.get("weather_desc", "未知")
        humidity = weather_data.get("humidity", "?")
        wind = weather_data.get("wind_kph", "?")
        wind_dir = weather_data.get("wind_dir", "?")
        feels = weather_data.get("feelslike_c", "?")

        text = (
            f"☀️ {actual_city} 今日天气：{desc}\n"
            f"🌡️ 当前温度：{temp}°C（体感 {feels}°C）\n"
            f"💧 湿度：{humidity}%\n"
            f"💨 风速：{wind} km/h {wind_dir}\n"
        )
        forecast = weather_data.get("forecast", [])
        if forecast:
            text += "\n📅 未来天气：\n"
            for day in forecast:
                date = day.get("date", "")[-5:]
                day_desc = day.get("weather_desc", "?")
                max_t = day.get("max_temp", "?")
                min_t = day.get("min_temp", "?")
                text += f"  {date} {day_desc} {min_t}°~{max_t}°\n"

    # ── Step 3: 生成天气卡片图片 ──
    card_bytes = await send_weather_card(weather_data)
    image_download_url = None
    if card_bytes and len(card_bytes) > 100:
        image_path = _save_card_to_file(card_bytes, actual_city)
        file_name = Path(image_path).name
        image_download_url = f"/files/weather_card/{file_name}"
        logger.info(f"[外部天气] 天气卡片已保存: {image_download_url}")

    # ── Step 4: 转发到远程回调（先发图片URL，再发文本） ──
    forward_success = True
    async with httpx.AsyncClient(timeout=10) as client:
        # 第一条消息：图片
        if image_download_url:
            full_image_url = f"{settings.EXTERNAL_BASE_URL}{image_download_url}"
            try:
                img_resp = await client.post(callback_url, json={
                    "conversation_id": conversation_id,
                    "type": "image",
                    "image_url": full_image_url,
                    "text": f"🌤 {actual_city} 天气卡片",
                })
                logger.info(f"[外部天气] 图片消息回调: {callback_url} → {img_resp.status_code}")
                if img_resp.status_code >= 400:
                    logger.warning(f"图片回调返回非成功状态码: {img_resp.status_code}")
            except Exception as e:
                logger.error(f"[外部天气] 图片消息回调失败: {e}")
                forward_success = False

        # 第二条消息：AI 生成的文本
        try:
            txt_resp = await client.post(callback_url, json={
                "conversation_id": conversation_id,
                "type": "text",
                "text": text,
            })
            logger.info(f"[外部天气] 文本消息回调: {callback_url} → {txt_resp.status_code}")
            if txt_resp.status_code >= 400:
                logger.warning(f"文本回调返回非成功状态码: {txt_resp.status_code}")
        except Exception as e:
            logger.error(f"[外部天气] 文本消息回调失败: {e}")
            forward_success = False

    # ── Step 5: 返回结果 ──
    result = {
        "city": actual_city,
        "weather": {
            "temp_c": weather_data.get("temp_c", "?"),
            "description": weather_data.get("weather_desc", "?"),
            "humidity": weather_data.get("humidity", "?"),
            "wind": f"{weather_data.get('wind_dir', '?')} {weather_data.get('wind_kph', '?')} km/h",
        },
        "image_url": image_download_url,
        "text": text,
        "forward_to": callback_url,
        "forward_status": "success" if forward_success else "partial_failure",
    }

    logger.info(f"[外部天气] 处理完成: city={actual_city}, forward={forward_success}")
    return JSONResponse(
        status_code=200,
        content={"code": 0, "message": "ok", "data": result}
    )


# ── 端点3：天气卡片图片下载 ──

@external_app.get("/files/weather_card/{filename}")
async def download_weather_card(filename: str):
    """下载天气卡片图片（无鉴权）"""
    if not filename.endswith(".png"):
        raise HTTPException(status_code=400, detail="无效的文件类型")
    safe_name = Path(filename).name
    filepath = CARD_CACHE_DIR / safe_name
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    # Content-Disposition 必须用 ASCII 安全字符，中文文件名需要编码
    ascii_name = safe_name.encode("ascii", errors="replace").decode("ascii")
    return FileResponse(
        path=str(filepath),
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{ascii_name}"'},
    )


# ── 端点4：通用文件下载 ──

@external_app.get("/files/{file_id}/download")
async def external_file_download(file_id: int):
    """通过文件ID下载系统中已上传的文件（无鉴权）"""
    file_record = await get_file_record_raw(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="文件不存在")
    stored_path = Path(file_record.file_path)
    if not stored_path.exists():
        raise HTTPException(status_code=404, detail="文件存储已丢失")
    mime_type = file_record.mime_type or "application/octet-stream"
    is_preview = mime_type.startswith(("image/", "text/", "application/pdf"))
    encoded_filename = urllib.parse.quote(file_record.file_name, safe='')
    ascii_fallback = ''.join(c if ord(c) < 128 else '_' for c in file_record.file_name)
    disposition_type = 'inline' if is_preview else 'attachment'
    disposition = (
        f"{disposition_type}; "
        f"filename=\"{ascii_fallback}\"; "
        f"filename*=UTF-8''{encoded_filename}"
    )
    return FileResponse(
        path=str(stored_path),
        filename=ascii_fallback,
        media_type=mime_type,
        headers={"Content-Disposition": disposition},
    )


# ── 独立启动 ──

if __name__ == "__main__":
    import uvicorn
    port = settings.EXTERNAL_PORT
    logger.info("=" * 50)
    logger.info(f"🚀 外部服务启动 | 端口: {port}")
    logger.info(f"   Weather(AI): POST http://0.0.0.0:{port}/weather")
    logger.info(f"   File DL:     GET  http://0.0.0.0:{port}/files/{{id}}/download")
    logger.info(f"   健康检查:     GET  http://0.0.0.0:{port}/health")
    logger.info("=" * 50)
    uvicorn.run(
        external_app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )