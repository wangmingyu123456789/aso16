"""
数据清洗工具集

本模块注册了「数据清洗」工作所需的 5 个工具：
1. extract_structural_info  - 从原始文本提取结构化信息
2. clean_html_content      - 清洗 HTML 标签，提取纯文本
3. parse_json_data         - 尝试解析 JSON 格式的采集数据
4. validate_result         - 验证清洗结果完整性
5. extract_domain          - 从 URL 中提取域名

这些工具在 seeds.py 中注册到 Tool 表，并关联到 data_cleaning 工作。
"""
import json
import re
from urllib.parse import urlparse


def extract_structural_info(raw_text: str, instructions: str = "") -> dict:
    """
    从原始采集文本中提取结构化信息。

    参数:
    - raw_text: 原始采集数据文本
    - instructions: 额外的清洗指令

    返回:
    - dict: {"title": str, "content": str, "domain_name": str, "summary": str}
    """
    # 尝试提取标题
    title = ""
    title_match = re.search(r'<title[^>]*>(.*?)</title>', raw_text, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = title_match.group(1).strip()
    else:
        # 从文本首行取前 80 字符作为标题
        lines = raw_text.strip().split("\n")
        if lines:
            title = lines[0].strip()[:80]

    # 提取纯文本内容
    content = raw_text
    content = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'<[^>]+>', ' ', content)
    content = re.sub(r'\s+', ' ', content).strip()
    content = content[:10000]  # 限制 10000 字符

    # 提取域名
    domain = ""
    domain_patterns = re.findall(r'https?://([^/\s]+)', raw_text)
    if domain_patterns:
        parsed = urlparse(f"https://{domain_patterns[0]}")
        domain = parsed.netloc.replace("www.", "")

    # 生成摘要
    summary = content[:200] if content else ""

    return {
        "title": title,
        "content": content,
        "domain_name": domain,
        "summary": summary,
    }


def clean_html_content(html_text: str, remove_scripts: bool = True) -> str:
    """
    清洗 HTML 标签，返回纯文本。

    参数:
    - html_text: 含 HTML 标签的文本
    - remove_scripts: 是否移除 script/style 标签

    返回:
    - str: 纯文本
    """
    text = html_text

    if remove_scripts:
        text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', text, flags=re.IGNORECASE)
        text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', text, flags=re.IGNORECASE)

    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', ' ', text)
    # 合并空白字符
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'<', '<', text)
    text = re.sub(r'>', '>', text)
    text = re.sub(r'&', '&', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_json_data(raw_json_str: str) -> dict:
    """
    尝试解析 JSON 格式的采集数据，结构化返回。

    参数:
    - raw_json_str: JSON 字符串

    返回:
    - dict: {"parsed": bool, "data": dict|list|None, "error": str}
    """
    result = {"parsed": False, "data": None, "error": ""}
    try:
        data = json.loads(raw_json_str)
        result["parsed"] = True
        result["data"] = data
    except json.JSONDecodeError as e:
        result["error"] = str(e)
    return result


def validate_result(cleaned_data: dict) -> dict:
    """
    验证清洗结果是否完整有效。

    参数:
    - cleaned_data: 清洗后的结构化数据 dict

    返回:
    - dict: {"valid": bool, "missing_fields": list, "score": float}
    """
    required_fields = ["title", "content"]
    missing = [f for f in required_fields if not cleaned_data.get(f)]
    score = 1.0

    if missing:
        score = max(0, 1.0 - len(missing) * 0.3)
    if not cleaned_data.get("content") or len(cleaned_data.get("content", "")) < 10:
        if "content_too_short" not in missing:
            missing.append("content_too_short")
        score = max(0, score - 0.3)

    return {
        "valid": len(missing) == 0,
        "missing_fields": missing,
        "score": round(score, 2),
    }


def extract_domain(url: str) -> str:
    """
    从 URL 中提取域名（去 www. 前缀）。

    参数:
    - url: 完整 URL 或域名

    返回:
    - str: 域名，如 "example.com"
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        domain = domain.split(":")[0]  # 移除端口
        domain = domain.removeprefix("www.")
        return domain
    except Exception:
        return ""