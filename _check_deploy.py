"""Check all deployment targets for BUILD version"""
import urllib.request, ssl, re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

targets = [
    ('Localhost',     'http://localhost:3000'),
    ('GitHub Pages',  'https://lincsd.github.io/xhs-emotion-platform'),
    ('Render',        'https://xhs-gemini-proxy.onrender.com'),
    ('Tunnel',        'https://xhs.xiaohsai.com'),
]

for name, url in targets:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        if url.startswith('https'):
            r = urllib.request.urlopen(req, timeout=30, context=ctx)
        else:
            r = urllib.request.urlopen(req, timeout=10)
        html = r.read().decode('utf-8', errors='replace')
        m = re.search(r"BUILD='([^']+)'", html)
        build = m.group(1) if m else '?'
        print(f"  {name}: OK {r.status} BUILD={build}")
    except Exception as e:
        err = str(e)[:100]
        print(f"  {name}: FAIL - {err}")
