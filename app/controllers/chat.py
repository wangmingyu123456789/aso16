import json
import time
import httpx
import tornado.web
from app.controllers.base import BaseHandler
from app.models.model import ModelRepository
from app.models.db import get_connection


class ChatPageHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("chat.html", title="智能问数", username=self.current_user)


class ChatStreamHandler(BaseHandler):
    @tornado.web.authenticated
    async def post(self):
        message = (self.get_body_argument("message", "") or "").strip()
        conv_id = int(self.get_body_argument("conversation_id", "0") or "0")
        model_id = int(self.get_body_argument("model_id", "0") or "0")

        if not message:
            self.set_status(400)
            return self.finish({"error": "消息不能为空"})

        user_id = self._get_user_id()
        model = ModelRepository.get_default_model()
        if model_id:
            m = ModelRepository.get_model_by_id(model_id)
            if m and m.get("status") == 1:
                model = m

        if not model:
            self.set_status(500)
            return self.finish({"error": "没有可用模型"})

        if not conv_id:
            conv_id = self._create_conversation(user_id, model["id"], message[:30])

        self._save_message(conv_id, "user", message)

        self.set_header("Content-Type", "text/event-stream")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("X-Accel-Buffering", "no")

        intent = ChatStreamHandler._detect_intent(message)
        full_response = ""

        if intent == "sql_query":
            try:
                sql_result = ChatStreamHandler._execute_sql_query(message, model)
                if sql_result:
                    full_response = sql_result
                    self.write(f"data: {json.dumps({'content': sql_result, 'done': True})}\n\n")
                    self.flush()
                else:
                    full_response = await ChatStreamHandler._stream_ai_response(self, message, model)
            except Exception as e:
                full_response = await ChatStreamHandler._stream_ai_response(self, message, model)
        elif intent == "digital_employee":
            full_response = await ChatStreamHandler._handle_digital_employee(self, message)
        else:
            full_response = await ChatStreamHandler._stream_ai_response(self, message, model)

        if full_response:
            self._save_message(conv_id, "assistant", full_response)
            self._update_conversation(conv_id)

    @staticmethod
    def _detect_intent(message):
        msg_lower = message.strip().lower()
        if msg_lower.startswith("@"):
            return "digital_employee"
        sql_keywords = ["最新一条", "最近", "查询", "统计", "多少条", "有哪些", "数据", "总数",
                        "最后一条", "最早", "最大值", "最小值", "平均值", "计数", "按"]
        if any(kw in message for kw in sql_keywords) and len(message) < 100:
            return "sql_query"
        return "normal"

    @staticmethod
    def _execute_sql_query(message, model):
        with get_connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('outlook_data','outlook_data_detail','outlook_tasks')"
            ).fetchall()
            if not tables:
                return None

            schema_info = []
            for t in tables:
                cols = conn.execute(f"PRAGMA table_info({t['name']})").fetchall()
                col_desc = ", ".join(f"{c['name']}" for c in cols[:10])
                count = conn.execute(f"SELECT COUNT(*) as cnt FROM {t['name']}").fetchone()["cnt"]
                schema_info.append(f"表 {t['name']}({col_desc}) 共{count}条")

            # 尝试让AI生成结构化的查询策略，但失败时用简单查询
            schema_text = "; ".join(schema_info)

            sample = conn.execute(
                "SELECT id,title,source_name,content,publish_date,create_at FROM outlook_data ORDER BY id DESC LIMIT 3"
            ).fetchall()
            sample_text = "\n".join(
                f"id={r['id']}, title={r['title']}, source={r['source_name']}, date={r['publish_date']}, created={r['create_at']}"
                for r in sample
            )

            prompt = f"""你是一个SQLite数据分析助手。根据用户问题生成SQL查询并返回结果。

数据库Schema:
{schema_text}

最新3条数据样本:
{sample_text}

用户问题: {message}

请直接生成并解释SQL查询，然后以JSON格式返回:
{{"sql": "SELECT ...", "explanation": "解释", "result_mode": "raw"}}

注意：只能使用SELECT，create_at存储的是UTC时间。"""

            sql_result = ModelRepository.call_model_api(
                model["api_url"], model["api_key"], model["code"],
                [{"role": "user", "content": prompt}],
                temperature=0.3, max_tokens=800
            )

            if not sql_result:
                # 简单fallback: 返回最新几条
                rows = conn.execute(
                    "SELECT id,title,source_name,content,publish_date FROM outlook_data ORDER BY id DESC LIMIT 5"
                ).fetchall()
                lines = ["**最新数据（前5条）：**\n"]
                for i, r in enumerate(rows):
                    lines.append(f"{i+1}. **{r['title']}** ({r['source_name']}) - {r['publish_date'] or '未知日期'}")
                    if r['content']:
                        lines.append(f"   > {r['content'][:100]}...")
                return "\n".join(lines)

            # 尝试从AI响应中提取SQL
            import re
            sql_match = re.search(r'```sql\s*(.*?)\s*```', sql_result, re.DOTALL)
            if not sql_match:
                sql_match = re.search(r'"sql"\s*:\s*"([^"]+)"', sql_result)
            if not sql_match:
                sql_match = re.search(r'SELECT\s+.*?(?:;|$)', sql_result, re.IGNORECASE | re.DOTALL)

            if sql_match:
                sql = sql_match.group(1) if sql_match.lastindex else sql_match.group(0)
                sql = sql.strip().rstrip(';')
                # 安全检查
                if not sql.upper().startswith("SELECT"):
                    raise ValueError("只允许SELECT查询")

                try:
                    result_rows = conn.execute(sql).fetchall()
                    if not result_rows:
                        return "查询结果为空。\n\n" + sql_result[:500]

                    lines = [f"**查询结果（{len(result_rows)}条）：**\n"]
                    for i, row in enumerate(result_rows[:10]):
                        d = dict(row)
                        title = d.get('title', '')
                        if title:
                            lines.append(f"{i+1}. **{title}**")
                        else:
                            lines.append(f"{i+1}. {json.dumps(d, ensure_ascii=False)[:200]}")
                        if 'content' in d and d['content']:
                            lines.append(f"   > {str(d['content'])[:150]}...")
                    if len(result_rows) > 10:
                        lines.append(f"\n... 还有 {len(result_rows)-10} 条结果")
                    return "\n".join(lines)
                except Exception as e:
                    return f"SQL执行错误: {str(e)}\n\nAI建议: {sql_result[:500]}"

            return f"**AI分析结果：**\n\n{sql_result[:2000]}"

    @staticmethod
    async def _stream_ai_response(handler, message, model):
        full = ""
        headers = {
            "Authorization": f"Bearer {model['api_key']}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model["code"],
            "messages": [{"role": "user", "content": message}],
            "stream": True
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", model["api_url"], headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        text = await resp.aread()
                        err = f"API错误 {resp.status_code}: {text[:200]}"
                        handler.write(f"data: {json.dumps({'content': err, 'done': True})}\n\n")
                        await handler.flush()
                        return err
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            handler.write(f"data: {json.dumps({'done': True})}\n\n")
                            await handler.flush()
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full += content
                                handler.write(f"data: {json.dumps({'content': content})}\n\n")
                                await handler.flush()
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            err = f"连接错误: {str(e)}"
            handler.write(f"data: {json.dumps({'content': err, 'done': True})}\n\n")
            await handler.flush()
            return err
        return full

    @staticmethod
    async def _handle_digital_employee(handler, message):
        parts = message.strip().split(maxsplit=1)
        at_name = parts[0][1:] if len(parts) > 0 else ""
        user_msg = parts[1] if len(parts) > 1 else ""

        from app.models.assistant import AssistantRepository

        asst = AssistantRepository.get_assistant_by_code(at_name)
        if asst:
            prefix = f"**@{asst['assistant_name']}** "
            if asst.get("category") == "API":
                return await ChatStreamHandler._handle_api_employee(handler, asst, prefix, user_msg)
            else:
                return await ChatStreamHandler._handle_ai_employee(handler, asst, prefix, user_msg)

        from app.models.db import get_connection
        with get_connection() as conn:
            api_row = conn.execute(
                "SELECT * FROM api_interfaces WHERE status=1 AND (name LIKE ? OR code LIKE ?)",
                (f"%{at_name}%", f"%{at_name}%")
            ).fetchone()
            if api_row:
                full = f"已找到API服务 **{api_row['name']}**，正在调用...\n\n"
                handler.write(f"data: {json.dumps({'content': full})}\n\n")
                await handler.flush()
                result = ChatStreamHandler._call_api_service(api_row, user_msg)
                full += result
                handler.write(f"data: {json.dumps({'content': result, 'done': True})}\n\n")
                await handler.flush()
                return full

        not_found = f"未找到数字员工「{at_name}」，请检查名称是否正确。\n\n可用的数字员工请查看侧边栏提示。"
        handler.write(f"data: {json.dumps({'content': not_found, 'done': True})}\n\n")
        await handler.flush()
        return not_found

    @staticmethod
    async def _handle_ai_employee(handler, asst, prefix, user_msg):
        prompt_template = asst.get("prompt_template", "")
        if prompt_template:
            system_msg = prompt_template.replace("{query}", user_msg).replace("{{query}}", user_msg)
        else:
            system_msg = f"你是数字员工「{asst['assistant_name']}」，请用专业友好的语气回答用户问题。"

        model = ModelRepository.get_default_model()
        if asst.get("model_id"):
            m = ModelRepository.get_model_by_id(asst["model_id"])
            if m and m.get("status") == 1:
                model = m

        if not model:
            err = "没有可用模型，请先配置模型引擎。"
            handler.write(f"data: {json.dumps({'content': prefix + err, 'done': True})}\n\n")
            await handler.flush()
            return prefix + err

        handler.write(f"data: {json.dumps({'content': prefix + '正在思考...'})}\n\n")
        await handler.flush()

        messages = [{"role": "system", "content": system_msg}]
        if user_msg:
            messages.append({"role": "user", "content": user_msg})

        full = ""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                headers = {"Authorization": f"Bearer {model['api_key']}", "Content-Type": "application/json"}
                payload = {"model": model["code"], "messages": messages, "stream": True}
                async with client.stream("POST", model["api_url"], headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        text = await resp.aread()
                        err = f"API错误 {resp.status_code}: {text[:200]}"
                        handler.write(f"data: {json.dumps({'content': err, 'done': True})}\n\n")
                        await handler.flush()
                        return err
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            handler.write(f"data: {json.dumps({'done': True})}\n\n")
                            await handler.flush()
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full += content
                                handler.write(f"data: {json.dumps({'content': content})}\n\n")
                                await handler.flush()
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            err = f"连接错误: {str(e)}"
            handler.write(f"data: {json.dumps({'content': err, 'done': True})}\n\n")
            await handler.flush()
            return err
        return full

    @staticmethod
    async def _handle_api_employee(handler, asst, prefix, user_msg):
        api_interface_id = asst.get("api_interface_id")
        if not api_interface_id:
            err = "该数字员工未关联API接口，请联系管理员配置。"
            handler.write(f"data: {json.dumps({'content': prefix + err, 'done': True})}\n\n")
            await handler.flush()
            return prefix + err

        # =============================================
        # TODO: 截胡天气助手，转发到外部 FastAPI 服务器
        # 与 im_ws.py 中的截胡逻辑保持一致。
        # 当外部 FastAPI 服务器部署好后，取消下方注释，
        # 并删除后面原有的 _call_api_service 调用。
        # FastAPI 期望: POST /weather  {"city": "...", "user_id": ...}
        # 返回: {"reply": "天气信息..."}
        # =============================================
        if asst.get("assistant_code") == "weather_query":
            try:
                EXTERNAL_FASTAPI_URL = "http://127.0.0.1:9877/weather"
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(EXTERNAL_FASTAPI_URL, json={
                        "city": user_msg,
                        "user_id": handler._get_user_id() if hasattr(handler, "_get_user_id") else 0
                    })
                    if resp.status_code == 200:
                        data = resp.json()
                        reply = data.get("reply", "")
                        if reply:
                            handler.write(f"data: {json.dumps({'content': prefix + reply, 'done': True})}\n\n")
                            await handler.flush()
                            return prefix + reply
                    return f"天气查询失败"
            except Exception as e:
                return f"天气服务异常: {str(e)}"

        from app.models.db import get_connection
        with get_connection() as conn:
            api_row = conn.execute("SELECT * FROM api_interfaces WHERE id=? AND status=1", (api_interface_id,)).fetchone()

        if not api_row:
            err = "关联的API接口不存在或已禁用。"
            handler.write(f"data: {json.dumps({'content': prefix + err, 'done': True})}\n\n")
            await handler.flush()
            return prefix + err

        api_name = api_row["name"]
        handler.write(f"data: {json.dumps({'content': prefix + '正在调用API接口 **' + api_name + '**...'})}\n\n")
        await handler.flush()

        result = ChatStreamHandler._call_api_service(dict(api_row), user_msg)
        full = result
        handler.write(f"data: {json.dumps({'content': result, 'done': True})}\n\n")
        await handler.flush()
        return full

    @staticmethod
    def _call_api_service(api_row, user_msg):
        try:
            params = {}
            if api_row['params_schema']:
                schema = json.loads(api_row['params_schema'])
                if isinstance(schema, list) and len(schema) > 0:
                    params[schema[0]['name']] = user_msg if user_msg else schema[0].get('example', '')
            url = api_row['api_url']
            if api_row['method'] == 'GET':
                resp = httpx.get(url, params=params, timeout=15)
            else:
                resp = httpx.post(url, json=params, timeout=15)
            if resp.status_code == 200:
                text = resp.text
                if api_row['response_format'] == 'JSON':
                    try:
                        data = resp.json()
                        return "```json\n" + json.dumps(data, ensure_ascii=False, indent=2)[:3000] + "\n```"
                    except:
                        return text[:3000]
                return text[:3000]
            return f"API调用失败: HTTP {resp.status_code}"
        except Exception as e:
            return f"API调用异常: {str(e)}"

    def _get_user_id(self):
        from app.models.db import get_connection
        with get_connection() as conn:
            row = conn.execute("SELECT id FROM users WHERE username=?", (self.current_user,)).fetchone()
            return row["id"] if row else 0

    def _create_conversation(self, user_id, model_id, title):
        with get_connection() as conn:
            c = conn.execute(
                "INSERT INTO chat_conversations(user_id,title,model_id) VALUES(?,?,?)",
                (user_id, title, model_id)
            )
            return c.lastrowid

    def _save_message(self, conv_id, role, content):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO chat_messages(conversation_id,role,content) VALUES(?,?,?)",
                (conv_id, role, content)
            )

    def _update_conversation(self, conv_id):
        import datetime
        with get_connection() as conn:
            conn.execute(
                "UPDATE chat_conversations SET update_at=? WHERE id=?",
                (datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), conv_id)
            )


class ChatAssistantsHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        from app.models.assistant import AssistantRepository
        assistants = AssistantRepository.get_enabled_assistants()
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": assistants})


class ChatHistoryHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        user_id = self._get_user_id()
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, title, model_id, create_at, update_at FROM chat_conversations WHERE user_id=? ORDER BY update_at DESC",
                (user_id,)
            ).fetchall()
            data = [dict(r) for r in rows]
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": data})

    @tornado.web.authenticated
    def post(self):
        conv_id = int(self.get_body_argument("conversation_id", "0"))
        if not conv_id:
            self.write({"code": 1, "msg": "conversation_id不能为空"})
            return
        user_id = self._get_user_id()
        with get_connection() as conn:
            conv = conn.execute(
                "SELECT id FROM chat_conversations WHERE id=? AND user_id=?",
                (conv_id, user_id)
            ).fetchone()
            if not conv:
                self.write({"code": 1, "msg": "对话不存在"})
                return
            messages = conn.execute(
                "SELECT id, role, content, create_at FROM chat_messages WHERE conversation_id=? ORDER BY id ASC",
                (conv_id,)
            ).fetchall()
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": [dict(m) for m in messages]})

    @tornado.web.authenticated
    def delete(self):
        conv_id = int(self.get_argument("conversation_id", "0"))
        user_id = self._get_user_id()
        with get_connection() as conn:
            conn.execute("DELETE FROM chat_messages WHERE conversation_id=? AND conversation_id IN (SELECT id FROM chat_conversations WHERE id=? AND user_id=?)",
                        (conv_id, conv_id, user_id))
            conn.execute("DELETE FROM chat_conversations WHERE id=? AND user_id=?", (conv_id, user_id))
        self.write({"code": 0, "msg": "已删除"})

    def _get_user_id(self):
        from app.models.db import get_connection
        with get_connection() as conn:
            row = conn.execute("SELECT id FROM users WHERE username=?", (self.current_user,)).fetchone()
            return row["id"] if row else 0


class ChatModelsHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        with get_connection() as conn:
            rows = conn.execute("SELECT id, name, code, is_system_default FROM models WHERE status=1").fetchall()
        self.set_header("Content-Type", "application/json")
        self.write({"code": 0, "data": [dict(r) for r in rows]})
