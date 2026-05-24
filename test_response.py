import urllib.request
import http.client

url = 'http://localhost:10086/admin/login'
req = urllib.request.Request(url)
req.add_header('User-Agent', 'Mozilla/5.0')
req.add_header('Accept', 'text/html,application/xhtml+xml')
req.add_header('Accept-Language', 'zh-CN,zh;q=0.9')
req.add_header('Accept-Encoding', 'identity')

response = urllib.request.urlopen(req)
print('Status:', response.status)
print('Headers:')
for k,v in response.headers.items():
    print(f'  {k}: {v}')
html = response.read().decode('utf-8')
print('Content length:', len(html))
print('\n=== Full HTML ===')
print(html)
