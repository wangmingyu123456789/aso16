import json
import httpx
from app.models.db import get_connection

class ModelRepository:
    @staticmethod
    def get_model_list(page=1, page_size=6, keyword=None):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if keyword:
                count_row = conn.execute(
                    "SELECT COUNT(*) AS total FROM models WHERE name LIKE ? OR code LIKE ?",
                    (f'%{keyword}%', f'%{keyword}%')
                ).fetchone()
                total = count_row["total"]
                rows = conn.execute(
                    """SELECT id, name, code, api_url, status, is_system_default, 
                              total_requests, total_tokens, prompt_tokens, completion_tokens,
                              last_used_at, create_at 
                       FROM models WHERE name LIKE ? OR code LIKE ? 
                       ORDER BY is_system_default DESC, id DESC LIMIT ? OFFSET ?""",
                    (f'%{keyword}%', f'%{keyword}%', page_size, offset)
                ).fetchall()
            else:
                count_row = conn.execute("SELECT COUNT(*) AS total FROM models").fetchone()
                total = count_row["total"]
                rows = conn.execute(
                    """SELECT id, name, code, api_url, status, is_system_default, 
                              total_requests, total_tokens, prompt_tokens, completion_tokens,
                              last_used_at, create_at 
                       FROM models 
                       ORDER BY is_system_default DESC, id DESC LIMIT ? OFFSET ?""",
                    (page_size, offset)
                ).fetchall()
        return {
            'total': total,
            'data': [dict(row) for row in rows],
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size if total > 0 else 1
        }

    @staticmethod
    def get_model_by_id(model_id):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM models WHERE id=?", (model_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_model_by_code(code):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM models WHERE code=?", (code,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_default_model():
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM models WHERE is_system_default=1 AND status=1"
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_model(name, code, api_url='', api_key='', status=1):
        try:
            with get_connection() as conn:
                conn.execute(
                    """INSERT INTO models(name, code, api_url, api_key, status) 
                       VALUES(?,?,?,?,?)""",
                    (name, code, api_url, api_key, status)
                )
                return True
        except Exception:
            return False

    @staticmethod
    def update_model(model_id, name=None, code=None, api_url=None, api_key=None, status=None):
        updates = []
        params = []
        if name is not None:
            updates.append("name=?")
            params.append(name)
        if code is not None:
            updates.append("code=?")
            params.append(code)
        if api_url is not None:
            updates.append("api_url=?")
            params.append(api_url)
        if api_key is not None:
            updates.append("api_key=?")
            params.append(api_key)
        if status is not None:
            updates.append("status=?")
            params.append(status)
        if not updates:
            return False
        params.append(model_id)
        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE models SET {} WHERE id=?".format(','.join(updates)),
                    params
                )
                return True
        except Exception:
            return False

    @staticmethod
    def delete_model(model_id):
        try:
            with get_connection() as conn:
                conn.execute("DELETE FROM models WHERE id=?", (model_id,))
                return True
        except Exception:
            return False

    @staticmethod
    def set_default_model(model_id):
        try:
            with get_connection() as conn:
                conn.execute("UPDATE models SET is_system_default=0")
                conn.execute("UPDATE models SET is_system_default=1 WHERE id=?", (model_id,))
                return True
        except Exception:
            return False

    @staticmethod
    def update_token_stats(model_id, prompt_tokens=0, completion_tokens=0):
        try:
            with get_connection() as conn:
                conn.execute(
                    """UPDATE models SET 
                          total_requests = total_requests + 1,
                          total_tokens = total_tokens + ?,
                          prompt_tokens = prompt_tokens + ?,
                          completion_tokens = completion_tokens + ?,
                          last_used_at = datetime('now')
                       WHERE id=?""",
                    (prompt_tokens + completion_tokens, prompt_tokens, completion_tokens, model_id)
                )
                return True
        except Exception:
            return False

    @staticmethod
    def test_model_chat(api_url, api_key, model_code, messages):
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model_code,
            "messages": messages,
            "stream": False
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(api_url, headers=headers, json=payload)
                if response.status_code == 200:
                    result = response.json()
                    usage = result.get("usage", {})
                    return {
                        "success": True,
                        "content": result["choices"][0]["message"]["content"],
                        "usage": {
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                            "total_tokens": usage.get("total_tokens", 0)
                        }
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API Error: {response.status_code} - {response.text}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": f"Connection Error: {str(e)}"
            }

    @staticmethod
    def call_model_api(api_url, api_key, model_code, messages, temperature=0.7, max_tokens=2000):
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model_code,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(api_url, headers=headers, json=payload)
                if response.status_code == 200:
                    result = response.json()
                    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return content.strip()
        except Exception:
            pass
        return ""

    @staticmethod
    def stream_model_chat(api_url, api_key, model_code, messages):
        """流式对话测试，生成器，逐块返回 SSE 数据"""
        import json
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model_code,
            "messages": messages,
            "stream": True
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(api_url, headers=headers, json=payload, stream=True)
                if response.status_code != 200:
                    yield f'{{"error":"API Error: {response.status_code}"}}'
                    return
                
                full_content = ""
                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            yield '{"done":true}'
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full_content += content
                                yield json.dumps({"content": content}, ensure_ascii=False)
                            # 捕获 usage
                            u = data.get("usage")
                            if u:
                                yield json.dumps({"usage": u}, ensure_ascii=False)
                        except Exception:
                            continue
        except Exception as e:
            yield json.dumps({"error": str(e)}, ensure_ascii=False)
