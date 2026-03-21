import urllib.request, ssl, re
ctx = ssl.create_default_context()

endpoints = [
    ('GitHub Pages', 'https://lincsd.github.io/xhs-emotion-platform/'),
    ('Render',       'https://xhs-gemini-proxy.onrender.com/'),
    ('Local/Tunnel', 'http://localhost:3000/'),
]

for name, url in endpoints:
    try:
        r = urllib.request.urlopen(url, timeout=120, context=ctx if url.startswith('https') else None)
        d = r.read().decode()
        m = re.search("BUILD='([^']+)'", d)
        print(f'{name:16s} BUILD = {m.group(1) if m else "NOT FOUND"}')
    except Exception as e:
        print(f'{name:16s} ERROR: {e}')
