import urllib.request
import sys

url = 'http://localhost:10086/admin/login'

class DebugHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        print(f'REDIRECT: {code} -> {newurl}')
        return None

opener = urllib.request.build_opener(DebugHandler)
req = urllib.request.Request(url)
req.add_header('User-Agent', 'Mozilla/5.0')
req.add_header('Accept', 'text/html')

response = opener.open(req)
print(f'Final URL: {response.url}')
print(f'Status: {response.status}')
print(f'Headers: {dict(response.headers)}')
html = response.read().decode('utf-8')
print(f'Content length: {len(html)}')
print(f'Contains login-card: {"login-card" in html}')
print(f'First 500 chars:\n{html[:500]}')
