"""
天气工具集 - 包含：
1. get_weather : 通过 wttr.in 获取真实天气数据（免费，无需API Key）
2. send_weather_card : 根据天气数据生成天气卡片图片（纯本地合成，无需网络）
"""
from __future__ import annotations
import os
import io
import json
import math
import random
import hashlib
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional

from utils.helpers import logger

try:
    import aiohttp
except ImportError:
    aiohttp = None

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageColor
except ImportError:
    Image = ImageDraw = ImageFont = ImageFilter = ImageColor = None

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 缓存目录 (保留)
CACHE_DIR = Path(__file__).parent.parent / "data" / "weather_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 天气码 → 中文天气描述
WEATHER_CODE_MAP = {
    113: "☀️ 晴", 116: "⛅ 多云", 119: "☁️ 阴",
    122: "☁️ 阴", 143: "🌫️ 雾/霾",
    176: "🌦️ 小雨", 179: "🌧️ 雨", 182: "🌧️ 雨夹雪", 185: "🌧️ 毛毛雨",
    200: "⛈️ 雷阵雨", 227: "🌨️ 小雪", 230: "🌨️ 大雪", 248: "🌫️ 雾",
    260: "🌫️ 大雾", 263: "🌦️ 小雨", 266: "🌦️ 小雨", 281: "🌧️ 毛毛雨",
    284: "🌧️ 冻雨", 293: "🌦️ 小雨", 296: "🌦️ 小雨", 299: "🌧️ 中雨",
    302: "🌧️ 中雨", 305: "🌧️ 大雨", 308: "🌧️ 暴雨", 311: "🌧️ 冻雨",
    314: "🌧️ 冻雨", 317: "🌧️ 雨夹雪", 320: "🌨️ 雨夹雪", 323: "🌨️ 小雪",
    326: "🌨️ 小雪", 329: "❄️ 大雪", 332: "❄️ 大雪", 335: "❄️ 大雪",
    338: "❄️ 暴雪", 350: "🧊 冰雹", 353: "🌦️ 小雨", 356: "🌧️ 中雨",
    359: "🌧️ 暴雨", 362: "🌧️ 雨夹雪", 365: "🌧️ 雨夹雪", 368: "🌨️ 小雪",
    371: "❄️ 大雪", 374: "🧊 冰雹", 377: "🧊 冰雹", 386: "⛈️ 雷阵雨",
    389: "⛈️ 雷阵雨", 392: "⛈️ 雷阵雪", 395: "❄️ 暴雪",
}

# 天气码 → 背景特效类型
WEATHER_EFFECT_MAP = {
    113: "sunny", 116: "cloudy", 119: "cloudy", 122: "cloudy",
    143: "foggy", 176: "rainy", 179: "rainy", 182: "rainy",
    185: "rainy", 200: "stormy", 227: "snowy", 230: "snowy",
    248: "foggy", 260: "foggy", 263: "rainy", 266: "rainy",
    293: "rainy", 296: "rainy", 299: "rainy", 302: "rainy",
    305: "rainy", 308: "rainy", 311: "rainy", 314: "rainy",
    317: "rainy", 320: "rainy", 323: "snowy", 326: "snowy",
    329: "snowy", 332: "snowy", 335: "snowy", 338: "snowy",
    350: "snowy", 353: "rainy", 356: "rainy", 359: "rainy",
    362: "rainy", 365: "rainy", 368: "snowy", 371: "snowy",
    374: "rainy", 377: "rainy", 386: "stormy", 389: "stormy",
    392: "snowy", 395: "snowy",
}

# 热门城市拼音映射（帮助 wttr.in 正确识别）
CITY_PINYIN_MAP = {
    "北京": "Beijing", "上海": "Shanghai", "广州": "Guangzhou",
    "深圳": "Shenzhen", "杭州": "Hangzhou", "成都": "Chengdu",
    "重庆": "Chongqing", "武汉": "Wuhan", "南京": "Nanjing",
    "西安": "Xi'an", "天津": "Tianjin", "苏州": "Suzhou",
    "长沙": "Changsha", "郑州": "Zhengzhou", "东莞": "Dongguan",
    "青岛": "Qingdao", "沈阳": "Shenyang", "宁波": "Ningbo",
    "昆明": "Kunming", "大连": "Dalian", "厦门": "Xiamen",
    "福州": "Fuzhou", "合肥": "Hefei", "佛山": "Foshan",
    "哈尔滨": "Harbin", "济南": "Jinan", "温州": "Wenzhou",
    "长春": "Changchun", "石家庄": "Shijiazhuang", "常州": "Changzhou",
    "贵阳": "Guiyang", "南宁": "Nanning", "南昌": "Nanchang",
    "太原": "Taiyuan", "烟台": "Yantai", "兰州": "Lanzhou",
    "珠海": "Zhuhai", "海口": "Haikou", "拉萨": "Lhasa",
    "银川": "Yinchuan", "西宁": "Xining", "乌鲁木齐": "Urumqi",
    "呼和浩特": "Hohhot", "唐山": "Tangshan", "徐州": "Xuzhou",
    "洛阳": "Luoyang", "邯郸": "Handan", "襄阳": "Xiangyang",
    "桂林": "Guilin", "遵义": "Zunyi", "三亚": "Sanya", "雅安": "Yaan",
    "香港": "Hong Kong", "澳门": "Macau", "台北": "Taipei",
    "高雄": "Kaohsiung", "东京": "Tokyo", "纽约": "New York",
    "伦敦": "London", "巴黎": "Paris", "悉尼": "Sydney",
    "首尔": "Seoul", "曼谷": "Bangkok", "新加坡": "Singapore",
    "吉隆坡": "Kuala Lumpur", "莫斯科": "Moscow", "柏林": "Berlin",
    "罗马": "Rome", "迪拜": "Dubai", "大阪": "Osaka",
}

# 天气卡片配色方案（作为随机渐变的基础）
WEATHER_CARD_COLORS = {
    "sunny":  {"bg1": "#FF9500", "bg2": "#FF6B35", "text": "#FFFFFF", "accent": "#FFF3E0"},
    "cloudy": {"bg1": "#78909C", "bg2": "#546E7A", "text": "#FFFFFF", "accent": "#ECEFF1"},
    "rainy":  {"bg1": "#37474F", "bg2": "#1565C0", "text": "#FFFFFF", "accent": "#BBDEFB"},
    "snowy":  {"bg1": "#90CAF9", "bg2": "#E3F2FD", "text": "#1A237E", "accent": "#FFFFFF"},
    "stormy": {"bg1": "#1A237E", "bg2": "#311B92", "text": "#FFFFFF", "accent": "#FFE082"},
    "foggy":  {"bg1": "#607D8B", "bg2": "#455A64", "text": "#FFFFFF", "accent": "#CFD8DC"},
}

WEATHER_CARD_EMOJIS = {
    "sunny": "☀️", "cloudy": "☁️", "rainy": "🌧️",
    "snowy": "❄️", "stormy": "⛈️", "foggy": "🌫️",
}

# ======================================================================
# 工具 1: get_weather — 获取实时天气数据
# ======================================================================


def _city_to_english(city_name: str) -> str:
    """将城市名转为英文，wttr.in 需要英文城市名"""
    if city_name in CITY_PINYIN_MAP:
        return CITY_PINYIN_MAP[city_name]
    return city_name


async def get_weather(city_name: str) -> dict:
    """
    通过 wttr.in 获取指定城市的实时天气

    Args:
        city_name: 城市名称（支持中文城市名）

    Returns:
        dict 包含天气信息的结构化数据:
        {
            "success": True/False,
            "city": "北京", "city_en": "Beijing",
            "temp_c": 25, "feelslike_c": 26,
            "weather_code": 113, "weather_desc": "☀️ 晴", "weather_effect": "sunny",
            "humidity": 60, "wind_kph": 15, "wind_dir": "南风",
            "visibility_km": 10, "uv_index": 5,
            "last_updated": "2024-01-01 12:00",
            "forecast": [...],  # 未来3天预报
            "error": "" (失败时)
        }
    """
    if not aiohttp:
        logger.warning("aiohttp 未安装，无法获取真实天气数据")
        return {"success": False, "error": "缺少网络请求库 aiohttp"}

    city_en = _city_to_english(city_name.strip())
    url = f"https://wttr.in/{city_en}?format=j1"

    logger.info(f"正在请求 wttr.in 获取天气: city={city_name}, city_en={city_en}, url={url}")

    try:
        async with aiohttp.ClientSession(headers={"Accept": "application/json"}) as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.warning(f"wttr.in 返回 {resp.status}: {text[:200]}")
                    return {"success": False, "error": f"天气服务返回错误 (HTTP {resp.status})"}

                text_body = await resp.text()
                data = json.loads(text_body)

        current = data.get("current_condition", [{}])[0]
        if not current:
            return {"success": False, "error": "未找到该城市的天气数据"}

        weather_code = current.get("weatherCode", 113)
        weather_desc = WEATHER_CODE_MAP.get(int(weather_code), "🌤️ 未知")
        weather_effect = WEATHER_EFFECT_MAP.get(int(weather_code), "cloudy")

        nearest = data.get("nearest_area", [{}])[0]
        area_name = nearest.get("areaName", [{}])[0].get("value", city_en) if nearest.get("areaName") else city_en
        region = nearest.get("region", [{}])[0].get("value", "") if nearest.get("region") else ""
        country = nearest.get("country", [{}])[0].get("value", "") if nearest.get("country") else ""

        result = {
            "success": True,
            "city": city_name.strip(),
            "city_en": area_name,
            "region": region,
            "country": country,
            "temp_c": current.get("temp_C", "?"),
            "feelslike_c": current.get("FeelsLikeC", "?"),
            "weather_code": int(weather_code),
            "weather_desc": weather_desc,
            "weather_effect": weather_effect,
            "humidity": current.get("humidity", "?"),
            "wind_kph": current.get("windspeedKmph", "?"),
            "wind_dir": current.get("winddir16Point", "?"),
            "visibility_km": current.get("visibility", "?"),
            "uv_index": current.get("uvIndex", 0),
            "last_updated": current.get("localObsDateTime", ""),
        }

        forecast = data.get("weather", [])
        if forecast:
            result["forecast"] = []
            for day in forecast[:3]:
                date_str = day.get("date", "")
                max_temp = day.get("maxtempC", "?")
                min_temp = day.get("mintempC", "?")
                hourly = day.get("hourly", [{}])
                day_code = hourly[0].get("weatherCode", 113) if hourly else 113
                day_desc = WEATHER_CODE_MAP.get(int(day_code), "🌤️ 未知")
                result["forecast"].append({
                    "date": date_str,
                    "max_temp": max_temp,
                    "min_temp": min_temp,
                    "weather_desc": day_desc,
                })

        logger.info(f"天气查询成功: {city_name} → {weather_desc} {result['temp_c']}°C")
        return result

    except Exception as e:
        logger.error(f"天气查询失败 ({city_name}): {e}")
        return {"success": False, "error": f"天气查询失败: {str(e)}"}


# ======================================================================
# 工具 2: send_weather_card — 生成天气卡片图片
#         纯本地随机渐变背景，无需网络请求
# ======================================================================


def _get_font(size: int, bold: bool = False):
    """获取中文字体，优先使用系统字体"""
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
    ]

    if bold:
        bold_paths = ["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf"]
        for fp in bold_paths:
            if os.path.exists(fp):
                try:
                    return ImageFont.truetype(fp, size)
                except Exception:
                    pass

    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass

    return ImageFont.load_default()


def _create_random_gradient_background(
    width: int, height: int, base_color1: str, base_color2: str
) -> Image.Image:
    """
    在天气配色基础上生成随机变化的渐变背景。
    对基础颜色的 RGB 各分量加入随机偏移（±30），
    随机决定渐变方向（垂直/水平/对角线）。
    """
    c1 = ImageColor.getrgb(base_color1)
    c2 = ImageColor.getrgb(base_color2)

    def _randomize_color(r, g, b, max_delta=30):
        return (
            max(0, min(255, r + random.randint(-max_delta, max_delta))),
            max(0, min(255, g + random.randint(-max_delta, max_delta))),
            max(0, min(255, b + random.randint(-max_delta, max_delta))),
        )

    c1_rnd = _randomize_color(c1[0], c1[1], c1[2])
    c2_rnd = _randomize_color(c2[0], c2[1], c2[2])
    direction = random.choice(["vertical", "horizontal", "diagonal"])

    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    if direction == "vertical":
        for y in range(height):
            ratio = y / height
            draw.line([(0, y), (width, y)], fill=(
                int(c1_rnd[0] * (1 - ratio) + c2_rnd[0] * ratio),
                int(c1_rnd[1] * (1 - ratio) + c2_rnd[1] * ratio),
                int(c1_rnd[2] * (1 - ratio) + c2_rnd[2] * ratio),
            ))
    elif direction == "horizontal":
        for x in range(width):
            ratio = x / width
            draw.line([(x, 0), (x, height)], fill=(
                int(c1_rnd[0] * (1 - ratio) + c2_rnd[0] * ratio),
                int(c1_rnd[1] * (1 - ratio) + c2_rnd[1] * ratio),
                int(c1_rnd[2] * (1 - ratio) + c2_rnd[2] * ratio),
            ))
    else:
        max_dist = math.sqrt(width ** 2 + height ** 2)
        for y in range(height):
            for x in range(width):
                dist = math.sqrt(x ** 2 + y ** 2)
                ratio = dist / max_dist
                draw.point((x, y), fill=(
                    int(c1_rnd[0] * (1 - ratio) + c2_rnd[0] * ratio),
                    int(c1_rnd[1] * (1 - ratio) + c2_rnd[1] * ratio),
                    int(c1_rnd[2] * (1 - ratio) + c2_rnd[2] * ratio),
                ))

    return img


def _draw_sun(draw: ImageDraw, cx: int, cy: int, size: int, color: str):
    for r in range(size * 2, size, -1):
        alpha = int(30 * (1 - r / (size * 2)))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     fill=(255, 200, 50, alpha), outline=None)
    draw.ellipse([cx - size, cy - size, cx + size, cy + size], fill=color)
    for angle in range(0, 360, 30):
        rad = math.radians(angle)
        x1 = cx + math.cos(rad) * (size + 5)
        y1 = cy + math.sin(rad) * (size + 5)
        x2 = cx + math.cos(rad) * (size + 18)
        y2 = cy + math.sin(rad) * (size + 18)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=3)


def _draw_cloud(draw: ImageDraw, cx: int, cy: int, size: int, color: str):
    draw.ellipse([cx - size // 2, cy - size // 3, cx + size // 2, cy + size // 3], fill=color)
    draw.ellipse([cx - size // 3, cy - size // 2, cx + size // 3, cy], fill=color)
    draw.ellipse([cx - size, cy - size // 4, cx, cy + size // 4], fill=color)
    draw.ellipse([cx, cy - size // 4, cx + size, cy + size // 4], fill=color)


def _draw_raindrops(draw: ImageDraw, width: int, height: int, color: str, count: int = 60):
    for _ in range(count):
        x = random.randint(0, width)
        y = random.randint(0, height)
        length = random.randint(6, 14)
        draw.line([(x, y), (x - 2, y + length)], fill=color, width=1)


def _draw_snowflakes(draw: ImageDraw, width: int, height: int, color: str, count: int = 40):
    for _ in range(count):
        x = random.randint(0, width)
        y = random.randint(0, height)
        r = random.randint(2, 4)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)


def _draw_lightning(draw: ImageDraw, cx: int, cy: int, color: str):
    points = [
        (cx, cy - 40), (cx + 8, cy - 10), (cx - 2, cy - 10),
        (cx + 12, cy + 40), (cx + 2, cy + 10), (cx + 14, cy + 10),
    ]
    draw.polygon(points, fill=color)


def _generate_card_image(
    city_name: str,
    city_en: str = "",
    temp_c: str = "?",
    feelslike_c: str = "?",
    weather_desc: str = "☀️ 晴",
    weather_effect: str = "sunny",
    humidity: str = "?",
    wind_kph: str = "?",
    wind_dir: str = "?",
    visibility_km: str = "?",
    uv_index: int = 0,
    last_updated: str = "",
    forecast: list = None,
) -> bytes:
    """生成天气卡片图片（PNG 格式），纯本地合成无需网络"""
    if Image is None:
        logger.error("Pillow 未安装，无法生成天气卡片")
        return b""

    width, height = 420, 560
    colors = WEATHER_CARD_COLORS.get(weather_effect, WEATHER_CARD_COLORS["cloudy"])

    # 1. 本地随机渐变背景
    img = _create_random_gradient_background(width, height, colors["bg1"], colors["bg2"])
    img = img.convert("RGBA")
    draw = ImageDraw.Draw(img)

    # 2. 天气特效装饰
    if weather_effect == "sunny":
        _draw_sun(draw, width - 80, 120, 35, "#FFD54F")
    elif weather_effect == "cloudy":
        _draw_cloud(draw, width - 60, 100, 60, (255, 255, 255, 76))
        _draw_cloud(draw, width - 130, 130, 45, (255, 255, 255, 51))
    elif weather_effect == "rainy":
        _draw_cloud(draw, width // 2, 80, 80, (255, 255, 255, 63))
        _draw_raindrops(draw, width, height, (200, 220, 255, 76))
    elif weather_effect == "snowy":
        _draw_snowflakes(draw, width, height, (255, 255, 255, 153))
    elif weather_effect == "stormy":
        _draw_lightning(draw, width - 100, 120, "#FFE082")
        _draw_cloud(draw, width // 2, 80, 100, (40, 40, 60, 102))
        _draw_raindrops(draw, width, height, (150, 180, 255, 102), count=80)
    elif weather_effect == "foggy":
        for i in range(5):
            y = 80 + i * 60
            draw.rectangle([0, y, width, y + 20], fill=(200, 200, 200, 38))

    # 3. 半透明卡片背景
    overlay = Image.new("RGBA", (width - 40, height - 40), (0, 0, 0, 100))
    img.paste(overlay, (20, 20), overlay)
    draw = ImageDraw.Draw(img)

    # 4. 字体
    font_large = _get_font(48, bold=True)
    font_medium = _get_font(28)
    font_small = _get_font(18)
    font_tiny = _get_font(14)
    text_color = colors["text"]
    temp_font = font_large
    temp_font_path = "C:/Windows/Fonts/msyhbd.ttc"
    if os.path.exists(temp_font_path):
        try:
            temp_font = ImageFont.truetype(temp_font_path, 72)
        except Exception:
            pass

    y_offset = 40

    # 城市名
    display_city = city_name or city_en or "未知城市"
    draw.text((width // 2, y_offset), display_city, fill=text_color, font=font_large, anchor="mt")
    y_offset += 50

    # 更新时间
    if last_updated:
        try:
            dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            time_str = last_updated
        draw.text((width // 2, y_offset), f"🕐 {time_str}", fill=colors["accent"], font=font_tiny, anchor="mt")
    y_offset += 30

    # 温度
    draw.text((width // 2, y_offset + 20), f"{temp_c}°C", fill=text_color, font=temp_font, anchor="mt")
    y_offset += 100

    # 天气描述
    emoji = WEATHER_CARD_EMOJIS.get(weather_effect, "🌤️")
    draw.text((width // 2, y_offset), f"{emoji} {weather_desc}", fill=text_color, font=font_medium, anchor="mt")
    y_offset += 50

    # 体感
    draw.text((width // 2, y_offset), f"体感 {feelslike_c}°C", fill=colors["accent"], font=font_small, anchor="mt")
    y_offset += 40

    # 分隔线
    draw.line([(60, y_offset), (width - 60, y_offset)], fill=colors["accent"], width=1)
    y_offset += 20

    # 详细信息
    info_items = [
        ("💧 湿度", f"{humidity}%" if humidity != "?" else "?"),
        ("💨 风速", f"{wind_kph} km/h" if wind_kph != "?" else "?"),
        ("🧭 风向", wind_dir if wind_dir != "?" else "?"),
        ("👁️ 能见度", f"{visibility_km} km" if visibility_km != "?" else "?"),
    ]
    col1_x, col2_x = 80, width // 2 + 20
    for i, (label, value) in enumerate(info_items):
        row_y = y_offset + i * 32
        col = col1_x if i < 2 else col2_x
        draw.text((col, row_y), label, fill=colors["accent"], font=font_tiny)
        draw.text((col + 90, row_y), value, fill=text_color, font=font_small)
    y_offset += 32 * 2 + 10

    # 未来预报
    if forecast:
        y_offset += 5
        draw.text((width // 2, y_offset), "📅 未来天气", fill=colors["accent"], font=font_tiny, anchor="mt")
        y_offset += 25
        fc_width = (width - 60) // len(forecast)
        for i, day in enumerate(forecast[:3]):
            x = 30 + i * fc_width + fc_width // 2
            date_str = day.get("date", "")[-5:]
            day_desc = day.get("weather_desc", "?")[:2]
            max_t = day.get("max_temp", "?")
            min_t = day.get("min_temp", "?")
            draw.text((x, y_offset), date_str, fill=colors["accent"], font=font_tiny, anchor="mt")
            y_offset += 22
            draw.text((x, y_offset), day_desc[:1], fill=text_color, font=font_small, anchor="mt")
            y_offset += 22
            draw.text((x, y_offset), f"{min_t}°/{max_t}°", fill=colors["accent"], font=font_tiny, anchor="mt")
            y_offset -= 44
        y_offset += 30

    # 署名
    draw.text((width // 2, height - 30), "🌤 CToS 天气助手 · 数据来源 wttr.in",
              fill=colors["accent"], font=font_tiny, anchor="mb")

    output = io.BytesIO()
    img.save(output, format="PNG", optimize=True)
    return output.getvalue()


async def send_weather_card(weather_data: dict) -> bytes:
    """
    根据天气数据生成天气卡片图片（纯本地合成，无需网络请求）。

    最小只需 city + weather_desc 即可生成，其余字段缺失会自动用默认值填充。
    所有字段均可选，不会因参数不全而失败。

    Args:
        weather_data: dict — 天气数据字典，支持以下字段（全部可选）:
            - city: 城市名称
            - temp_c / feelslike_c: 温度/体感温度
            - weather_desc: 天气文字描述（如"晴"、"小雨"）
            - weather_effect: 特效类型 sunny/cloudy/rainy/snowy/stormy/foggy
            - humidity / wind_kph / wind_dir: 湿度/风速/风向
            - visibility_km / uv_index: 能见度/紫外线
            - last_updated: 更新时间
            - forecast: 未来天气预报列表

    Returns:
        bytes: PNG 图片字节数据，任何异常返回空 bytes 并记录错误日志
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        card_bytes = await loop.run_in_executor(
            None,
            lambda: _generate_card_image(
                city_name=weather_data.get("city", ""),
                city_en=weather_data.get("city_en", ""),
                temp_c=str(weather_data.get("temp_c", "?")),
                feelslike_c=str(weather_data.get("feelslike_c", "?")),
                weather_desc=weather_data.get("weather_desc", "🌤️ 未知"),
                weather_effect=weather_data.get("weather_effect", "cloudy"),
                humidity=str(weather_data.get("humidity", "?")),
                wind_kph=str(weather_data.get("wind_kph", "?")),
                wind_dir=weather_data.get("wind_dir", "?"),
                visibility_km=str(weather_data.get("visibility_km", "?")),
                uv_index=weather_data.get("uv_index", 0),
                last_updated=weather_data.get("last_updated", ""),
                forecast=weather_data.get("forecast", []),
            )
        )

        if card_bytes and len(card_bytes) > 100:
            logger.info(f"send_weather_card 成功 | city={weather_data.get('city', '?')} | effect={weather_data.get('weather_effect', '?')} | size={len(card_bytes)}B")
        else:
            logger.warning(f"send_weather_card 生成结果异常 | city={weather_data.get('city', '?')} | size={len(card_bytes) if card_bytes else 0}B")

        return card_bytes

    except Exception as e:
        logger.error(f"send_weather_card 执行失败 | city={weather_data.get('city', '?')} | error={e}")
        import traceback
        logger.error(traceback.format_exc())
        return b""