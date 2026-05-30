"""
舆情分析工具集

本模块注册了「舆情观察」工作所需的工具：
1. classify_sentiment      - 对文本进行情感分类（positive/negative/neutral）
2. extract_keywords        - 从文本中提取关键词及权重
3. detect_events           - 从一批文章中检测舆情事件
4. extract_locations       - 从文本中提取地理位置信息
5. generate_summary        - 生成舆情分析摘要
"""
import json
import re
from typing import Optional


# ============================================================
# 全局城市坐标字典
# 用于 LLM 未提供经纬度时的自动补全
# 覆盖中国主要城市 + 世界主要城市
# ============================================================
CITY_COORDS = {
    # ---- 中国 ----
    "北京": {"longitude": 116.4074, "latitude": 39.9042},
    "上海": {"longitude": 121.4737, "latitude": 31.2304},
    "广州": {"longitude": 113.2644, "latitude": 23.1291},
    "深圳": {"longitude": 114.0579, "latitude": 22.5431},
    "成都": {"longitude": 104.0648, "latitude": 30.5723},
    "杭州": {"longitude": 120.1551, "latitude": 30.2741},
    "武汉": {"longitude": 114.3054, "latitude": 30.5931},
    "重庆": {"longitude": 106.5516, "latitude": 29.5630},
    "南京": {"longitude": 118.7969, "latitude": 32.0603},
    "天津": {"longitude": 117.2010, "latitude": 39.0842},
    "苏州": {"longitude": 120.5841, "latitude": 31.2974},
    "西安": {"longitude": 108.9402, "latitude": 34.2611},
    "长沙": {"longitude": 112.9388, "latitude": 28.2282},
    "郑州": {"longitude": 113.6254, "latitude": 34.7466},
    "东莞": {"longitude": 113.7518, "latitude": 23.0207},
    "青岛": {"longitude": 120.3826, "latitude": 36.0671},
    "沈阳": {"longitude": 123.4315, "latitude": 41.8057},
    "宁波": {"longitude": 121.5440, "latitude": 29.8683},
    "昆明": {"longitude": 102.8332, "latitude": 24.8797},
    "大连": {"longitude": 121.6148, "latitude": 38.9138},
    "厦门": {"longitude": 118.0894, "latitude": 24.4798},
    "合肥": {"longitude": 117.2272, "latitude": 31.8206},
    "佛山": {"longitude": 113.1219, "latitude": 23.0219},
    "福州": {"longitude": 119.2965, "latitude": 26.0745},
    "哈尔滨": {"longitude": 126.5350, "latitude": 45.8038},
    "济南": {"longitude": 117.0000, "latitude": 36.6500},
    "温州": {"longitude": 120.6994, "latitude": 27.9943},
    "南宁": {"longitude": 108.3665, "latitude": 22.8170},
    "贵阳": {"longitude": 106.6300, "latitude": 26.6470},
    "乌鲁木齐": {"longitude": 87.6168, "latitude": 43.8266},
    # ---- 世界主要城市 ----
    "东京": {"longitude": 139.6917, "latitude": 35.6895},
    "首尔": {"longitude": 126.9780, "latitude": 37.5665},
    "曼谷": {"longitude": 100.5018, "latitude": 13.7563},
    "新加坡": {"longitude": 103.8198, "latitude": 1.3521},
    "香港": {"longitude": 114.1694, "latitude": 22.3193},
    "台北": {"longitude": 121.5654, "latitude": 25.0330},
    "伦敦": {"longitude": -0.1278, "latitude": 51.5074},
    "巴黎": {"longitude": 2.3522, "latitude": 48.8566},
    "柏林": {"longitude": 13.4050, "latitude": 52.5200},
    "莫斯科": {"longitude": 37.6173, "latitude": 55.7558},
    "纽约": {"longitude": -74.0060, "latitude": 40.7128},
    "华盛顿": {"longitude": -77.0369, "latitude": 38.9072},
    "洛杉矶": {"longitude": -118.2437, "latitude": 34.0522},
    "旧金山": {"longitude": -122.4194, "latitude": 37.7749},
    "多伦多": {"longitude": -79.3832, "latitude": 43.6532},
    "悉尼": {"longitude": 151.2093, "latitude": -33.8688},
    "墨尔本": {"longitude": 144.9631, "latitude": -37.8136},
    "迪拜": {"longitude": 55.2708, "latitude": 25.2048},
    "沙特阿拉伯": {"longitude": 46.6753, "latitude": 24.7136},
    "约翰内斯堡": {"longitude": 28.0473, "latitude": -26.2041},
    "开罗": {"longitude": 31.2357, "latitude": 30.0444},
    "内罗毕": {"longitude": 36.8219, "latitude": -1.2921},
    "新德里": {"longitude": 77.2090, "latitude": 28.6139},
    "孟买": {"longitude": 72.8777, "latitude": 19.0760},
    "雅加达": {"longitude": 106.8456, "latitude": -6.2088},
    "马尼拉": {"longitude": 120.9842, "latitude": 14.5995},
    "河内": {"longitude": 105.8542, "latitude": 21.0278},
    "胡志明": {"longitude": 106.6297, "latitude": 10.8231},
    "伊斯坦布尔": {"longitude": 28.9784, "latitude": 41.0082},
    "罗马": {"longitude": 12.4964, "latitude": 41.9028},
    "马德里": {"longitude": -3.7038, "latitude": 40.4168},
    "里斯本": {"longitude": -9.1393, "latitude": 38.7223},
    "阿姆斯特丹": {"longitude": 4.9041, "latitude": 52.3676},
    "斯德哥尔摩": {"longitude": 18.0686, "latitude": 59.3293},
}


def resolve_location_coords(location_name: str) -> Optional[dict]:
    """根据地名查找对应经纬度。支持模糊匹配（包含关系）"""
    if not location_name:
        return None
    # 精确匹配
    if location_name in CITY_COORDS:
        return CITY_COORDS[location_name]
    # 模糊匹配：如果地名包含城市名
    for city_name, coords in CITY_COORDS.items():
        if city_name in location_name or location_name in city_name:
            return coords
    return None


def classify_sentiment(text: str) -> dict:
    """
    对文本进行情感倾向分类。

    参数:
    - text: 待分析的文本

    返回:
    - dict: {"sentiment": str, "confidence": float, "positive_score": float, "negative_score": float, "neutral_score": float}
    """
    # 简单的关键词匹配规则分析
    positive_words = [
        "好", "优", "赞", "成功", "增长", "突破", "创新", "领先",
        "满意", "支持", "利好", "繁荣", "发展", "提升", "改善",
    ]
    negative_words = [
        "差", "坏", "劣", "失败", "下降", "危机", "风险", "问题",
        "投诉", "负面", "暴跌", "崩盘", "争议", "违规", "违法",
    ]

    positive_count = sum(1 for w in positive_words if w in text)
    negative_count = sum(1 for w in negative_words if w in text)
    total = positive_count + negative_count

    if total == 0:
        sentiment = "neutral"
        confidence = 0.5
    elif positive_count > negative_count:
        sentiment = "positive"
        confidence = positive_count / total
    elif negative_count > positive_count:
        sentiment = "negative"
        confidence = negative_count / total
    else:
        sentiment = "neutral"
        confidence = 0.5

    return {
        "sentiment": sentiment,
        "confidence": round(min(confidence, 1.0), 2),
        "positive_score": round(positive_count / max(total, 1), 2),
        "negative_score": round(negative_count / max(total, 1), 2),
        "neutral_score": round(1.0 - abs(positive_count - negative_count) / max(total, 1), 2),
    }


def extract_keywords(text: str, max_keywords: int = 20) -> list[dict]:
    """
    从文本中提取关键词及权重。

    参数:
    - text: 待分析的文本
    - max_keywords: 最大关键词数量

    返回:
    - list[dict]: [{"word": str, "weight": float, "category": str}, ...]
    """
    # 使用简单的词频统计提取关键词
    # 过滤掉常见的停用词
    stop_words = {
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
        "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
        "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
        "它", "们", "那", "里", "为", "所", "得", "与", "其", "之",
        "及", "但", "而", "或", "被", "把", "对", "从", "以", "将",
        "还", "又", "可", "如果", "虽然", "因为", "所以", "但是",
    }

    # 简单分词（按常见分隔符切分 + 中文字符双字组合）
    words = re.findall(r'[\u4e00-\u9fff]{2,4}|[a-zA-Z]\w+', text)
    
    # 过滤停用词和短词
    filtered = [w for w in words if w.lower() not in stop_words and len(w) >= 2]
    
    # 统计词频
    freq = {}
    for w in filtered:
        freq[w] = freq.get(w, 0) + 1
    
    # 排序取 top N
    sorted_words = sorted(freq.items(), key=lambda x: -x[1])
    total = max(sum(freq.values()), 1)
    
    result = []
    for word, count in sorted_words[:max_keywords]:
        weight = round(count / total * 100, 1)
        # 分类
        if word in ["问题", "风险", "危机", "暴跌", "投诉", "违规", "违法", "争议", "失败"]:
            category = "negative_topic"
        elif word in ["增长", "突破", "创新", "发展", "成功", "领先", "利好", "繁荣"]:
            category = "positive_topic"
        else:
            category = "topic"
        
        result.append({
            "word": word,
            "weight": weight,
            "category": category,
        })
    
    return result


def detect_events(articles: list[dict]) -> list[dict]:
    """
    从一批文章中检测舆情事件。

    参数:
    - articles: 文章列表，每项含 title, content, domain_name, id

    返回:
    - list[dict]: [{"event_name": str, "sentiment_type": str, "description": str,
                     "keywords": list, "heat": int, "related_article_ids": list}, ...]
    """
    if not articles:
        return []

    # 简单的事件检测：按domain_name分组，结合关键词匹配
    domain_groups = {}
    for art in articles:
        domain = art.get("domain_name", "unknown")
        if domain not in domain_groups:
            domain_groups[domain] = []
        domain_groups[domain].append(art)

    events = []
    for domain, arts in domain_groups.items():
        # 收集该域名的所有文本
        all_text = " ".join([a.get("title", "") + " " + (a.get("content", "") or "")[:500] for a in arts])
        
        # 情感分析
        sentiment = classify_sentiment(all_text)
        
        # 关键词提取
        keywords = extract_keywords(all_text, 10)
        
        # 热度估算（基于文章数量和关键词权重）
        heat = min(len(arts) * 15 + sum(k["weight"] for k in keywords) // 5, 100)
        
        # 生成事件名称
        top_words = [k["word"] for k in keywords[:3]]
        event_name = f"{domain}相关"
        if top_words:
            event_name = f"{'、'.join(top_words)} - {domain}"
        
        events.append({
            "event_name": event_name[:256],
            "sentiment_type": sentiment["sentiment"],
            "description": f"共{len(arts)}篇文章，平均情感倾向为{sentiment['sentiment']}（置信度{sentiment['confidence']}）",
            "keywords": [k["word"] for k in keywords],
            "heat": heat,
            "related_article_ids": [a.get("id") for a in arts if a.get("id")],
        })
    
    # 按热度排序
    events.sort(key=lambda e: -e["heat"])
    return events


def extract_locations(text: str) -> list[dict]:
    """
    从文本中提取地理位置信息。

    参数:
    - text: 待分析的文本

    返回:
    - list[dict]: [{"location_name": str, "longitude": float, "latitude": float, "description": str}, ...]
    """
    # 预定义的中国常见城市坐标
    cities = {
        "北京": {"longitude": 116.4074, "latitude": 39.9042},
        "上海": {"longitude": 121.4737, "latitude": 31.2304},
        "广州": {"longitude": 113.2644, "latitude": 23.1291},
        "深圳": {"longitude": 114.0579, "latitude": 22.5431},
        "成都": {"longitude": 104.0648, "latitude": 30.5723},
        "杭州": {"longitude": 120.1551, "latitude": 30.2741},
        "武汉": {"longitude": 114.3054, "latitude": 30.5931},
        "重庆": {"longitude": 106.5516, "latitude": 29.5630},
        "南京": {"longitude": 118.7969, "latitude": 32.0603},
        "天津": {"longitude": 117.2010, "latitude": 39.0842},
        "苏州": {"longitude": 120.5841, "latitude": 31.2974},
        "西安": {"longitude": 108.9402, "latitude": 34.2611},
        "长沙": {"longitude": 112.9388, "latitude": 28.2282},
        "郑州": {"longitude": 113.6254, "latitude": 34.7466},
        "东莞": {"longitude": 113.7518, "latitude": 23.0207},
        "青岛": {"longitude": 120.3826, "latitude": 36.0671},
        "沈阳": {"longitude": 123.4315, "latitude": 41.8057},
        "宁波": {"longitude": 121.5440, "latitude": 29.8683},
        "昆明": {"longitude": 102.8332, "latitude": 24.8797},
        "大连": {"longitude": 121.6148, "latitude": 38.9138},
        "厦门": {"longitude": 118.0894, "latitude": 24.4798},
        "合肥": {"longitude": 117.2272, "latitude": 31.8206},
        "佛山": {"longitude": 113.1219, "latitude": 23.0219},
        "福州": {"longitude": 119.2965, "latitude": 26.0745},
        "哈尔滨": {"longitude": 126.5350, "latitude": 45.8038},
        "济南": {"longitude": 117.0000, "latitude": 36.6500},
        "温州": {"longitude": 120.6994, "latitude": 27.9943},
        "南宁": {"longitude": 108.3665, "latitude": 22.8170},
        "贵阳": {"longitude": 106.6300, "latitude": 26.6470},
        "乌鲁木齐": {"longitude": 87.6168, "latitude": 43.8266},
    }

    found = []
    for city_name, coords in cities.items():
        if city_name in text:
            found.append({
                "location_name": city_name,
                "longitude": coords["longitude"],
                "latitude": coords["latitude"],
                "description": "",
            })

    return found


def generate_summary(analysis_result: dict) -> str:
    """
    根据舆情分析结果生成中英文混合摘要。

    参数:
    - analysis_result: 包含 events, words, sentiment_counts 的 dict

    返回:
    - str: 摘要文本
    """
    events = analysis_result.get("events", [])
    words = analysis_result.get("words", [])
    sentiment_counts = analysis_result.get("sentiment_counts", {})

    total = sum(sentiment_counts.values())
    if total == 0:
        return "本次舆情分析未发现有效数据。"

    positive = sentiment_counts.get("positive", 0)
    negative = sentiment_counts.get("negative", 0)
    neutral = sentiment_counts.get("neutral", 0)

    # 情感倾向判定
    if positive > negative:
        overall = "正面"
    elif negative > positive:
        overall = "负面"
    else:
        overall = "中性"

    lines = [
        f"本次舆情分析覆盖 {total} 篇文章。",
        f"总体倾向为「{overall}」。其中正面 {positive} 篇、负面 {negative} 篇、中性 {neutral} 篇。",
    ]

    if events:
        top_event = events[0]
        lines.append(f"最热事件：「{top_event['event_name']}」，热度 {top_event['heat']}。")

    if words:
        top_words = [w["word"] for w in words[:5]]
        lines.append(f"高频关键词：{'、'.join(top_words)}。")

    return "\n".join(lines)