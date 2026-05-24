import urllib.request
url = 'http://localhost:10086/admin/login'
try:
    r = urllib.request.urlopen(url)
    print('Status:', r.status)
    print('Length:', len(r.read().decode('utf-8')))
except Exception as e:
    print('Error:', e)
