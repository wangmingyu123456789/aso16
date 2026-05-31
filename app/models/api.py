import json
import httpx
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
from app.models.db import get_connection


class ApiRepository:
    @staticmethod
    def get_api_list(page=1, page_size=20, keyword=None):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if keyword:
                like = f"%{keyword}%"
                count_row = conn.execute(
                    "SELECT COUNT(*) as total FROM api_interfaces WHERE name LIKE ? OR code LIKE ? OR api_url LIKE ?",
                    (like, like, like)
                ).fetchone()
                rows = conn.execute(
                    """SELECT * FROM api_interfaces
                    WHERE name LIKE ? OR code LIKE ? OR api_url LIKE ?
                    ORDER BY id DESC LIMIT ? OFFSET ?""",
                    (like, like, like, page_size, offset)
                ).fetchall()
            else:
                count_row = conn.execute("SELECT COUNT(*) as total FROM api_interfaces").fetchone()
                rows = conn.execute(
                    "SELECT * FROM api_interfaces ORDER BY id DESC LIMIT ? OFFSET ?",
                    (page_size, offset)
                ).fetchall()
            return {
                "total": count_row["total"],
                "page": page,
                "page_size": page_size,
                "data": [dict(r) for r in rows]
            }

    @staticmethod
    def get_api_by_id(api_id):
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM api_interfaces WHERE id=?", (api_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_api_by_code(code):
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM api_interfaces WHERE code=? AND status=1", (code,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_api(name, code, api_url, method='GET', response_format='JSON',
                request_example='', params_schema='', headers='', description='',
                qps_limit='', status=1):
        try:
            with get_connection() as conn:
                conn.execute(
                    """INSERT INTO api_interfaces(
                    name,code,api_url,method,response_format,request_example,
                    params_schema,headers,description,qps_limit,status
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (name, code, api_url, method, response_format, request_example,
                    params_schema, headers, description, qps_limit, status)
                )
                return True
        except Exception:
            return False

    @staticmethod
    def update_api(api_id, name=None, code=None, api_url=None, method=None,
                response_format=None, request_example=None, params_schema=None,
                headers=None, description=None, qps_limit=None, status=None):
        updates = []
        params = []
        fields = {
            'name': name, 'code': code, 'api_url': api_url, 'method': method,
            'response_format': response_format, 'request_example': request_example,
            'params_schema': params_schema, 'headers': headers,
            'description': description, 'qps_limit': qps_limit, 'status': status
        }
        for key, val in fields.items():
            if val is not None:
                updates.append(f"{key}=?")
                params.append(val)
        if not updates:
            return False
        params.append(api_id)
        try:
            with get_connection() as conn:
                conn.execute(
                    f"UPDATE api_interfaces SET {','.join(updates)} WHERE id=?",
                    params
                )
                return True
        except Exception:
            return False

    @staticmethod
    def delete_api(api_id):
        try:
            with get_connection() as conn:
                conn.execute("DELETE FROM api_interfaces WHERE id=?", (api_id,))
                return True
        except Exception:
            return False

    @staticmethod
    def _build_url(base_url, params):
        if not params:
            return base_url
        parsed = urlparse(base_url)
        existing = parse_qs(parsed.query)
        merged = {k: v for k, vals in existing.items() for v in vals}
        merged.update({k: str(v) for k, v in params.items() if v is not None and str(v) != ''})
        query = urlencode(merged)
        return urlunparse(parsed._replace(query=query))

    @staticmethod
    def _parse_headers(headers_str):
        if not headers_str:
            return {}
        try:
            data = json.loads(headers_str)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @staticmethod
    def _record_call(api_id):
        with get_connection() as conn:
            conn.execute(
                """UPDATE api_interfaces SET total_calls=total_calls+1,
                last_called_at=datetime('now','localtime') WHERE id=?""",
                (api_id,)
            )

    @staticmethod
    def invoke(code, params=None, timeout=30):
        """供系统其他模块调用的统一 API 服务入口"""
        params = params or {}
        api = ApiRepository.get_api_by_code(code)
        if not api:
            return {"success": False, "error": f"接口不存在或已禁用: {code}"}

        url = ApiRepository._build_url(api["api_url"], params)
        method = (api.get("method") or "GET").upper()
        headers = ApiRepository._parse_headers(api.get("headers") or "")

        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                if method == "POST":
                    resp = client.post(url, headers=headers, data=params)
                else:
                    resp = client.get(url, headers=headers)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if "json" in content_type or api.get("response_format", "").upper() == "JSON":
                    try:
                        body = resp.json()
                    except Exception:
                        body = resp.text
                else:
                    body = resp.text

                ApiRepository._record_call(api["id"])
                return {
                    "success": True,
                    "code": api["code"],
                    "name": api["name"],
                    "url": url,
                    "status_code": resp.status_code,
                    "data": body
                }
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}",
                "url": url,
                "data": e.response.text[:2000]
            }
        except Exception as e:
            return {"success": False, "error": str(e), "url": url}

    @staticmethod
    def test_api(api_id, params=None, timeout=30):
        api = ApiRepository.get_api_by_id(api_id)
        if not api:
            return {"success": False, "error": "接口不存在"}
        if api["status"] != 1:
            return {"success": False, "error": "接口已禁用"}
        return ApiRepository.invoke(api["code"], params, timeout=timeout)
