import json
import re
import tornado.web
from app.controllers.base import BaseHandler
from app.models.db import get_connection
from app.models.model import ModelRepository


class SentimentHandler(BaseHandler):
    """用户侧智慧舆情页面"""
    @tornado.web.authenticated
    def get(self):
        self.render("user/sentiment.html", title="数智大屏 & 智慧舆情", username=self.current_user, current_page="sentiment")


class DashboardChartsHandler(BaseHandler):
    """数智大屏图表数据 API"""
    @tornado.web.authenticated
    def get(self):
        try:
            with get_connection() as conn:
                total = conn.execute(
                    "SELECT COUNT(*) as cnt FROM outlook_data"
                ).fetchone()["cnt"]

                today = conn.execute(
                    "SELECT COUNT(*) as cnt FROM outlook_data WHERE date(create_at,'+8 hours')=date('now','+8 hours')"
                ).fetchone()["cnt"]

                sources = conn.execute(
                    "SELECT source_name as name, COUNT(*) as value "
                    "FROM outlook_data GROUP BY source_name "
                    "ORDER BY value DESC LIMIT 10"
                ).fetchall()

                tasks = conn.execute(
                    "SELECT COUNT(*) as cnt FROM outlook_tasks"
                ).fetchone()["cnt"]

                trend_data = conn.execute(
                    "SELECT date(create_at,'+8 hours') as date, COUNT(*) as cnt "
                    "FROM outlook_data GROUP BY date ORDER BY date DESC LIMIT 7"
                ).fetchall()
                trend_data = list(reversed(trend_data))

                task_status = conn.execute(
                    "SELECT status as name, COUNT(*) as value "
                    "FROM outlook_tasks GROUP BY status"
                ).fetchall()

                recent = conn.execute(
                    "SELECT title, publish_date FROM outlook_data "
                    "ORDER BY id DESC LIMIT 20"
                ).fetchall()

            self.write({
                "code": 0,
                "msg": "success",
                "data": {
                    "total": total,
                    "today": today,
                    "sources": [dict(r) for r in sources],
                    "tasks": tasks,
                    "trend": {
                        "dates": [r["date"] for r in trend_data],
                        "values": [r["cnt"] for r in trend_data]
                    },
                    "taskStatus": [dict(r) for r in task_status],
                    "recent": [dict(r) for r in recent]
                }
            })
        except Exception as e:
            self.write({
                "code": 1,
                "msg": f"获取图表数据失败: {str(e)}",
                "data": None
            })


class SentimentStatsHandler(BaseHandler):
    """智慧舆情统计 API"""
    @tornado.web.authenticated
    def get(self):
        try:
            outlook_data = SentimentRepository.get_outlook_data_stats()

            im_messages = SentimentRepository.get_im_messages_summary(limit=1)
            im_conversations = SentimentRepository.get_im_conversations_summary(limit=1)

            self.write({
                "code": 0,
                "msg": "success",
                "data": {
                    "outlook": outlook_data,
                    "im": {
                        "conversations": len(im_conversations),
                        "messages": len(im_messages)
                    }
                }
            })
        except Exception as e:
            self.write({
                "code": 1,
                "msg": f"获取统计数据失败: {str(e)}",
                "data": None
            })


class SentimentAnalyzeHandler(BaseHandler):
    """智慧舆情分析 API"""
    @tornado.web.authenticated
    def post(self):
        try:
            outlook_data = SentimentRepository.get_outlook_data_summary(limit=50)
            outlook_stats = SentimentRepository.get_outlook_data_stats()
            im_conversations = SentimentRepository.get_im_conversations_summary(limit=30)
            im_messages = SentimentRepository.get_im_messages_summary(limit=100)

            data_context = {
                "outlook_data": outlook_data,
                "outlook_stats": outlook_stats,
                "im_conversations": im_conversations,
                "im_messages": im_messages,
                "im_stats": {
                    "conversations": len(im_conversations),
                    "messages": len(im_messages)
                }
            }

            analysis = SentimentRepository.analyze_with_ai(data_context)

            if "error" in analysis:
                self.write({
                    "code": 1,
                    "msg": analysis["error"],
                    "data": None
                })
            else:
                SentimentRepository.save_analysis_cache(analysis)
                self.write({
                    "code": 0,
                    "msg": "分析成功",
                    "data": analysis
                })
        except Exception as e:
            self.write({
                "code": 1,
                "msg": f"分析失败: {str(e)}",
                "data": None
            })


class SentimentResultHandler(BaseHandler):
    """获取已保存的舆情分析结果"""
    @tornado.web.authenticated
    def get(self):
        try:
            cache = SentimentRepository.get_analysis_cache()
            if cache:
                self.write({
                    "code": 0,
                    "msg": "success",
                    "data": cache
                })
            else:
                self.write({
                    "code": 1,
                    "msg": "暂无缓存的分析结果",
                    "data": None
                })
        except Exception as e:
            self.write({
                "code": 1,
                "msg": f"获取缓存失败: {str(e)}",
                "data": None
            })


class WordCloudHandler(BaseHandler):
    """词云数据 API"""
    @tornado.web.authenticated
    def get(self):
        try:
            import jieba
            from collections import Counter

            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT title, content FROM outlook_data ORDER BY id DESC LIMIT 10000"
                ).fetchall()

            all_text = []
            for r in rows:
                if r["title"]:
                    all_text.append(r["title"])
                if r["content"]:
                    all_text.append(r["content"])

            text = " ".join(all_text)
            words = jieba.lcut(text)

            stopwords = set()
            common_stop = "的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己 这 他 她 它 们 那 里 为 与 及 但 或 而 被 把 对 从 以 又 还 将 能 所 得 地 着 过 个 之 中 大 小 多 少 做 做 用 让 让 给 向 拿 下 出 来 更 最 已 已经 可以 这个 那个 什么 怎么 如何 如果 因为 所以 但是 然而 虽然 而且 并 并且 或者 还是 只是 不过 不仅 而且 然后 之后 可能 应该 能够 需要 没有 还是 而是 都 已经 通过 进行 以及 及其 等".split()
            stopwords.update(common_stop)

            filtered = []
            for w in words:
                w = w.strip()
                if len(w) < 2:
                    continue
                if w in stopwords:
                    continue
                filtered.append(w)

            word_freq = Counter(filtered)
            top_words = word_freq.most_common(100)

            data = [{"name": w, "value": v} for w, v in top_words]
            self.write({"code": 0, "msg": "success", "data": data})
        except Exception as e:
            self.write({"code": 1, "msg": f"词云数据生成失败: {str(e)}", "data": []})


class SentimentRepository:
    """智慧舆情数据仓库"""

    @staticmethod
    def get_outlook_data_summary(limit=50):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT id, title, content, source_name, publish_date, create_at
                   FROM outlook_data
                   ORDER BY id DESC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_outlook_data_stats():
        with get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM outlook_data"
            ).fetchone()["cnt"]

            sources = conn.execute(
                "SELECT source_name, COUNT(*) as cnt "
                "FROM outlook_data GROUP BY source_name "
                "ORDER BY cnt DESC LIMIT 10"
            ).fetchall()

            recent = conn.execute(
                "SELECT COUNT(*) as cnt FROM outlook_data "
                "WHERE create_at >= datetime('now', '+8 hours', '-24 hours')"
            ).fetchone()["cnt"]

            return {
                "total": total,
                "sources": [dict(r) for r in sources],
                "recent_24h": recent
            }

    @staticmethod
    def get_im_conversations_summary(limit=30):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT c.id, c.type, c.name, c.last_message, c.last_message_at,
                          (SELECT COUNT(*) FROM im_messages
                           WHERE conversation_id = c.id) as msg_count
                   FROM im_conversations c
                   ORDER BY c.last_message_at DESC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_im_messages_summary(limit=100):
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT cm.id, cm.conversation_id, cm.type, cm.content, cm.create_at,
                          c.type as conv_type, c.name as conv_name
                   FROM im_messages cm
                   LEFT JOIN im_conversations c ON c.id = cm.conversation_id
                   WHERE cm.type = 'text'
                   ORDER BY cm.id DESC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def save_analysis_cache(result_dict):
        with get_connection() as conn:
            conn.execute("DELETE FROM outlook_sentiment_cache")
            conn.execute(
                "INSERT INTO outlook_sentiment_cache(result_json) VALUES(?)",
                (json.dumps(result_dict, ensure_ascii=False),)
            )

    @staticmethod
    def get_analysis_cache():
        with get_connection() as conn:
            row = conn.execute(
                "SELECT result_json, create_at FROM outlook_sentiment_cache ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row:
                return {
                    "result": json.loads(row["result_json"]),
                    "create_at": row["create_at"]
                }
            return None

    @staticmethod
    def analyze_with_ai(data_context):
        model = ModelRepository.get_model_by_code('deepseek-r1-distill-qwen-7b')
        if not model:
            model = ModelRepository.get_default_model()
        if not model:
            return {"error": "未配置 AI 模型，请先在管理后台配置模型"}

        prompt = f"""你是一个专业的舆情分析专家。请分析以下数据并提供风险评估报告。

## 数据概况

### 瞭望采集数据概览
- 数据总量: {data_context.get('outlook_stats', {}).get('total', 0)} 条
- 24 小时内新增: {data_context.get('outlook_stats', {}).get('recent_24h', 0)} 条
- 数据来源分布: {json.dumps(data_context.get('outlook_stats', {}).get('sources', []), ensure_ascii=False)}

### 瞭望数据样本（最近 {len(data_context.get('outlook_data', []))} 条）
{chr(10).join([f"- [{d.get('title', '无标题')}] 来源:{d.get('source_name', '未知')} 时间:{d.get('publish_date', '未知')}" for d in data_context.get('outlook_data', [])[:10]])}

### 智能聊天数据概览
- 会话数量: {data_context.get('im_stats', {}).get('conversations', 0)} 个
- 用户消息数量: {data_context.get('im_stats', {}).get('messages', 0)} 条

### 聊天消息样本（最近 {len(data_context.get('im_messages', []))} 条用户消息）
{chr(10).join([f"- [{m.get('conv_name', m.get('conv_type', '未知'))}] {m.get('content', '')[:100]}" for m in data_context.get('im_messages', [])[:10]])}

## 分析任务

请提供以下分析报告：

### 1. 舆情热点分析
- 当前热点话题有哪些
- 各话题的关注度排序

### 2. 情感倾向分析
- 整体情感倾向（正面/中性/负面）
- 负面舆情预警

### 3. 风险等级评估
- 高风险事项（需要立即关注）
- 中风险事项（需要持续跟踪）
- 低风险事项（常规关注）

### 4. 趋势预测
- 未来可能的发展趋势
- 建议的应对措施

请用 JSON 格式返回分析结果，格式如下：
```json
{{
  "hot_topics": [
    {{"topic": "话题名称", "heat": 85, "trend": "上升/下降/平稳", "sources": ["来源 1", "来源 2"]}}
  ],
  "sentiment": {{
    "overall": "正面/中性/负面",
    "positive_rate": 60,
    "neutral_rate": 25,
    "negative_rate": 15,
    "warnings": ["负面舆情预警 1", "负面舆情预警 2"]
  }},
  "risks": [
    {{"level": "高/中/低", "title": "风险标题", "description": "风险描述", "suggestion": "应对建议"}}
  ],
  "trends": {{
    "prediction": "趋势预测描述",
    "actions": ["建议措施 1", "建议措施 2"]
  }},
  "summary": "整体舆情总结"
}}
```"""

        try:
            api_url = model.get("api_url", "")
            api_key = model.get("api_key", "")

            if not api_url:
                return {"error": "模型 API 地址未配置"}

            import httpx
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

            payload = {
                "model": model.get("code", ""),
                "messages": [
                    {"role": "system", "content": "你是一个专业的舆情分析专家，擅长数据分析和风险评估。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 4000
            }

            with httpx.Client(timeout=60.0) as client:
                resp = client.post(api_url, json=payload, headers=headers)
                resp.raise_for_status()
                result = resp.json()

                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)

                try:
                    analysis = json.loads(content)
                    return analysis
                except json.JSONDecodeError:
                    return {"raw_analysis": content, "error": "AI 返回数据解析失败，请重试"}

        except Exception as e:
            return {"error": f"AI 分析失败：{str(e)}"}
