import json
import re
import httpx
import time
from html.parser import HTMLParser


class _LinkExtractor(HTMLParser):
	def __init__(self):
		super().__init__()
		self.items = []
		self._current = {}
		self._in_a = False
		self._text = ""

	def handle_starttag(self, tag, attrs):
		attrs_dict = dict(attrs)
		if tag == "a":
			self._in_a = True
			self._current = {"url": attrs_dict.get("href", ""), "title": ""}
			self._text = ""

	def handle_endtag(self, tag):
		if tag == "a" and self._in_a:
			self._in_a = False
			title = self._text.strip()
			if title and self._current.get("url"):
				self._current["title"] = title
				self.items.append(dict(self._current))
		self._text = ""

	def handle_data(self, data):
		self._text += data


class WatchCollector:
	def build_url(self, source, keyword, page):
		entry_url = source.get("entry_url", "")
		if keyword and ("{}" in entry_url or "{keyword}" in entry_url):
			entry_url = entry_url.replace("{keyword}", keyword).replace("{}", keyword)
		if page > 1:
			if "?" in entry_url:
				entry_url += f"&page={page}"
			else:
				entry_url += f"?page={page}"
		return entry_url

	def fetch_html(self, url, headers_str=None):
		req_headers = {
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
			"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
			"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
		}
		if headers_str:
			try:
				custom = json.loads(headers_str)
				req_headers.update(custom)
			except Exception:
				pass
		try:
			with httpx.Client(timeout=30.0, follow_redirects=True) as client:
				resp = client.get(url, headers=req_headers)
				resp.raise_for_status()
				try:
					return resp.text
				except UnicodeDecodeError:
					return resp.content.decode("gbk", errors="replace")
		except Exception:
			return ""

	def parse_items(self, html, source):
		parser = _LinkExtractor()
		try:
			parser.feed(html)
		except Exception:
			pass
		results = []
		for item in parser.items:
			url = item.get("url", "")
			if url and not url.startswith("http"):
				base = source.get("entry_url", "")
				if "/" in base.split("//", 1)[-1]:
					pos = base.rfind("/")
					if pos > 8:
						base = base[:pos + 1]
				url = base.rstrip("/") + "/" + url.lstrip("/")
			results.append({
				"title": item.get("title", ""),
				"url": url,
				"content": "",
				"author": "",
				"publish_date": "",
			})
		return results

	def collect(self, source, keyword, pages=1, per_page=10):
		all_items = []
		headers_str = source.get("request_headers", "")
		for page in range(1, pages + 1):
			url = self.build_url(source, keyword, page)
			if not url:
				continue
			html = self.fetch_html(url, headers_str)
			if not html:
				continue
			items = self.parse_items(html, source)
			page_items = items[:per_page] if per_page else items
			all_items.extend(page_items)
			if pages > 1 and page < pages:
				time.sleep(1.5)
		return all_items
