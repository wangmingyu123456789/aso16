#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI扩词和清洗功能测试脚本
验证 outlook.py 中 ModelEngine -> ModelRepository 修复是否生效
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

from app.models.outlook import OutlookCollector
from app.models.model import ModelRepository

def test_get_default_model():
    print("=" * 60)
    print("测试1：获取系统默认模型")
    print("=" * 60)
    model = ModelRepository.get_default_model()
    if model:
        print(f"  模型名称: {model['name']}")
        print(f"  模型编码: {model['code']}")
        print(f"  API URL:  {model['api_url']}")
        print(f"  状态: {'启用' if model['status'] == 1 else '禁用'}")
        print(f"  默认: {'是' if model.get('is_system_default', 0) == 1 else '否'}")
    else:
        print("  ⚠️ 未找到可用的默认模型")
    print()
    return model

def test_model_api():
    print("=" * 60)
    print("测试2：直接调用模型API（非流式）")
    print("=" * 60)
    model = ModelRepository.get_default_model()
    if not model:
        print("  跳过：没有可用模型")
        print()
        return False
    
    messages = [{"role": "user", "content": "请用一句话介绍Python编程语言"}]
    print(f"  请求: {messages[0]['content']}")
    
    response = ModelRepository.call_model_api(
        model['api_url'],
        model['api_key'],
        model['code'],
        messages,
        temperature=0.7,
        max_tokens=200
    )
    
    if response:
        print(f"  响应: {response[:100]}...")
        print("  ✅ 模型API调用成功")
    else:
        print("  ❌ 模型API调用失败（返回空）")
    print()
    return bool(response)

def test_ai_expand_keywords():
    print("=" * 60)
    print("测试3：AI关键词扩展功能")
    print("=" * 60)
    
    keyword = "人工智能"
    prompt = f'请为关键词"{keyword}"生成5个相关的搜索关键词，用于扩展数据采集范围。每个关键词用逗号分隔，不要输出其他内容。'
    
    print(f"  原始关键词: {keyword}")
    print(f"  扩词Prompt: {prompt[:80]}...")
    
    try:
        keywords = OutlookCollector.expand_keywords_with_ai(keyword, prompt)
        print(f"  扩展结果: {keywords}")
        print(f"  扩展数量: {len(keywords)}")
        if len(keywords) > 1:
            print("  ✅ AI扩词功能正常")
        else:
            print("  ⚠️ 扩词返回单个关键词（可能AI未生效或失败）")
    except Exception as e:
        print(f"  ❌ AI扩词失败: {e}")
    print()

def test_ai_clean_data():
    print("=" * 60)
    print("测试4：AI数据清洗功能")
    print("=" * 60)
    
    raw_items = [
        {
            "title": "2024年AI技术发展报告：大模型引领新变革",
            "content": "摘要：近年来，人工智能技术特别是大语言模型取得了突破性进展...",
            "author": "张三",
            "publish_date": "2024-01-15",
            "url": "https://example.com/news1"
        },
        {
            "title": "机器学习在医疗领域的应用实践",
            "content": "本文介绍了机器学习技术在医疗诊断中的最新应用案例...",
            "author": "李四",
            "publish_date": "2024-02-20",
            "url": "https://example.com/news2"
        }
    ]
    
    prompt = '请对以下数据进行清洗：去除URL字段，将title和content合并为summary字段，保留author和date。返回JSON数组格式：[{"summary":"...","author":"...","date":"..."}]'
    
    print(f"  原始数据条数: {len(raw_items)}")
    print(f"  清洗Prompt: {prompt[:80]}...")
    
    try:
        cleaned = OutlookCollector.clean_data_with_ai(raw_items, prompt)
        print(f"  清洗结果条数: {len(cleaned)}")
        if cleaned and isinstance(cleaned, list):
            for i, item in enumerate(cleaned):
                print(f"  第{i+1}条: {item}")
            print("  ✅ AI清洗功能正常")
        else:
            print("  ⚠️ 清洗结果格式异常（可能AI未生效或失败）")
    except Exception as e:
        print(f"  ❌ AI清洗失败: {e}")
    print()

def test_full_collect_flow():
    print("=" * 60)
    print("测试5：完整采集流程（含AI扩词+AI清洗）")
    print("=" * 60)
    
    # 构造一个测试数据源
    test_source = {
        'id': 999,
        'name': '测试数据源',
        'code': 'test_source',
        'entry_url': 'http://www.baidu.com/s?tn=news&word={keyword}&pn={page}',
        'method': 'GET',
        'request_headers': '',
        'body_template': '',
        'parser_type': 'html',
        'html_selector': 'div.result',
        'title_selector': 'h3',
        'url_selector': 'h3 a',
        'content_selector': 'div.content-right > span',
        'date_selector': 'span.c-color-gray2',
        'author_selector': 'p.author-text',
        'page_size_step': 10,
        'page_start': 0,
        'ai_expand_keyword': 1,
        'ai_expand_prompt': '',
        'ai_clean_data': 1,
        'ai_clean_prompt': '请对采集到的新闻标题和内容进行AI清洗，去除无关信息，提取核心要点。',
        'status': 1,
        'description': '测试用数据源'
    }
    
    print(f"  数据源: {test_source['name']}")
    print(f"  关键词: 科技")
    print(f"  AI扩词: 开启")
    print(f"  AI清洗: 开启")
    print()
    
    # 注意：百度有反爬，这里可能采集不到数据，但可以看到AI扩词是否工作
    print("  开始采集（注：百度有反爬，可能采集不到数据，重点看AI扩词是否工作）...")
    try:
        count = OutlookCollector.collect(
            test_source, 
            keyword="科技", 
            pages=1, 
            page_size_step=10,
            use_ai_expand=True,
            use_ai_clean=True
        )
        print(f"  采集结果: 保存了 {count} 条数据")
    except Exception as e:
        print(f"  采集异常: {e}")
    print()

def test_model_list():
    print("=" * 60)
    print("补充检查：查看数据库中所有模型")
    print("=" * 60)
    result = ModelRepository.get_model_list(page=1, page_size=20)
    print(f"  模型总数: {result['total']}")
    for m in result['data']:
        default_mark = " [默认]" if m.get('is_system_default', 0) == 1 else ""
        status_mark = "[OK]" if m['status'] == 1 else "[OFF]"
        print(f"  {status_mark} {m['name']} ({m['code']}){default_mark}")
    print()

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         AI 扩词与清洗功能 - 自动化测试                    ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    
    # 1. 检查模型
    test_model_list()
    
    # 2. 获取默认模型
    default_model = test_get_default_model()
    
    # 3. 如果默认模型不存在，提示
    if not default_model:
        print("⚠️ 没有可用的默认模型，AI功能无法测试。")
        print("   请先在「模型引擎」中添加模型并设置为系统默认。")
        sys.exit(1)
    
    # 4. 测试模型API
    api_ok = test_model_api()
    
    # 5. 测试AI扩词
    if api_ok:
        test_ai_expand_keywords()
        test_ai_clean_data()
        # 完整采集流程（可选，因为百度有反爬）
        # test_full_collect_flow()
    else:
        print("⚠️ 模型API调用失败，跳过AI扩词和清洗测试。")
        print("   请检查API Key和网络连接。")
    
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                    测试完成                               ║")
    print("╚══════════════════════════════════════════════════════════╝")
