import urllib.request, ssl
ctx = ssl._create_unverified_context()
ua = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0'}

for name, url in [('Tunnel', 'https://xhs.xiaohsai.com/healthz'), ('Render', 'https://xhs-gemini-proxy.onrender.com/healthz')]:
    req = urllib.request.Request(url, headers=ua)
    try:
        r = urllib.request.urlopen(req, timeout=30, context=ctx)
        print(f'{name}: OK {r.status} {r.read().decode().strip()}')
    except Exception as e:
        print(f'{name}: FAIL - {e}')
