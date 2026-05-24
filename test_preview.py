import urllib.request

url = 'http://localhost:10086/admin/login'
req = urllib.request.Request(url)
req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
req.add_header('Accept-Language', 'zh-CN,zh;q=0.9,en;q=0.8')

response = urllib.request.urlopen(req)
print('=== Status ===')
print(response.status)
print('\n=== Headers ===')
for k,v in response.headers.items():
    print(f'{k}: {v}')
print('\n=== Content Length ===')
html = response.read().decode('utf-8')
print(len(html))
print('\n=== Full HTML ===')
print(html)
