import urllib.request, json, ssl, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ctx = ssl.create_default_context()
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

urls = [
    ('GH Pages manifest', 'https://lincsd.github.io/xhs-emotion-platform/knowledge_cards/manifest.json'),
    ('GH Pages index', 'https://lincsd.github.io/xhs-emotion-platform/'),
    ('Render version', 'https://xhs-gemini-proxy.onrender.com/api/version'),
    ('Tunnel version', 'https://xhs.xiaohsai.com/api/version'),
    ('Localhost version', 'http://localhost:3000/api/version'),
]

for name, u in urls:
    try:
        req = urllib.request.Request(u, headers={'User-Agent': UA})
        r = urllib.request.urlopen(req, timeout=30, context=ctx)
        data = r.read()
        print(f"[OK] {name}: {len(data)} bytes")
        if 'manifest' in u:
            d = json.loads(data)
            stages = [s['stage'] for s in d.get('stages', [])]
            print(f"     total_cards={d.get('total_cards')}, stages={stages}")
        elif 'version' in u:
            print(f"     {data.decode().strip()}")
    except Exception as e:
        print(f"[FAIL] {name}: {e}")

print("\nDone.")
