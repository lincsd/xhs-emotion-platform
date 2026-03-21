import urllib.request, ssl, re
ctx = ssl.create_default_context()
BASE = 'https://xhs-gemini-proxy.onrender.com'

print('=== Render Health Check ===')
try:
    r = urllib.request.urlopen(BASE + '/healthz', timeout=120, context=ctx)
    print('healthz:', r.read().decode())
except Exception as e:
    print('healthz ERROR:', e)

print('\n=== Render Version API ===')
try:
    r = urllib.request.urlopen(BASE + '/api/version', timeout=30, context=ctx)
    print('version:', r.read().decode())
except Exception as e:
    print('version ERROR:', e)

print('\n=== Render Frontend ===')
try:
    r = urllib.request.urlopen(BASE + '/', timeout=30, context=ctx)
    d = r.read().decode()
    m = re.search("BUILD='([^']+)'", d)
    print('BUILD:', m.group(1) if m else 'NOT FOUND')
except Exception as e:
    print('frontend ERROR:', e)
