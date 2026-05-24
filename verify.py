import urllib.request
url = 'http://localhost:10086/admin/login'
r = urllib.request.urlopen(url)
print('Status:', r.status)
html = r.read().decode('utf-8')
print('Length:', len(html))
print('Has blue-bg:', '#1a6fb5' in html or '#4a9bd9' in html)
print('Has white-card:', '#ffffff' in html)
print('Has cyan-btn:', '#2fb8c8' in html or '#1ea8b8' in html)
print('Has admin-option:', '管理员' in html)
print('Has register-link:', '注册' in html)
print('--- HTML Preview ---')
print(html[:800])
