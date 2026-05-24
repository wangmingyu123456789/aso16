import urllib.request
import urllib.parse
import http.cookiejar

# 创建 cookie jar
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# 1. 先 GET 登录页面获取 xsrf token
url = 'http://localhost:10086/admin/login'
resp = opener.open(url)
html = resp.read().decode('utf-8')
print('GET status:', resp.status)

# 提取 xsrf token
import re
xsrf_match = re.search(r'name="_xsrf"\s+value="([^"]+)"', html)
if xsrf_match:
    xsrf = xsrf_match.group(1)
    print('XSRF token:', xsrf[:20], '...')
else:
    print('No XSRF token found')
    xsrf = ''

# 2. POST 登录
data = urllib.parse.urlencode({
    '_xsrf': xsrf,
    'username': 'admin',
    'password': 'admin888',
    'login_type': 'admin'
}).encode()

req = urllib.request.Request(url, data=data, method='POST')
try:
    resp = opener.open(req)
    print('POST status:', resp.status)
    print('Final URL:', resp.url)
    print('Redirect:', resp.url != url)
    final_html = resp.read().decode('utf-8')
    if 'admin' in final_html.lower() or 'index' in final_html.lower():
        print('Login SUCCESS - redirected to admin page')
    else:
        print('Login FAILED - still on login page')
        if 'error' in final_html.lower():
            err_match = re.search(r'class="error-tip show">([^<]+)', final_html)
            if err_match:
                print('Error:', err_match.group(1))
except urllib.error.HTTPError as e:
    print('HTTP Error:', e.code)
    print('Response:', e.read().decode('utf-8')[:500])
