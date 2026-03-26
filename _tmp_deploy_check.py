import urllib.request, json

# 1. GitHub Pages - manifest
try:
    r = urllib.request.urlopen('https://lincsd.github.io/xhs-emotion-platform/knowledge_cards/manifest.json', timeout=10)
    d = json.loads(r.read())
    total = 0
    for stage, entries in d.get('stages', {}).items():
        n = len(entries)
        total += n
        has_summary = sum(1 for e in entries if e.get('is_summary'))
        print(f'  GH Pages {stage}: {n} files ({has_summary} summary)')
    tc = d.get('total_cards', 'N/A')
    print(f'  GH Pages Total: {total} files, {tc} cards')
except Exception as e:
    print(f'GitHub Pages: {e}')

# 2. Render
try:
    req = urllib.request.Request('https://xhs-emotion-platform.onrender.com/api/version', headers={'User-Agent': 'Mozilla/5.0'})
    r2 = urllib.request.urlopen(req, timeout=20)
    print(f'Render: {r2.read().decode()[:200]}')
except Exception as e:
    print(f'Render: {e}')

# 3. Tunnel
try:
    req = urllib.request.Request('https://xhs.xiaohsai.com/api/version', headers={'User-Agent': 'Mozilla/5.0'})
    r3 = urllib.request.urlopen(req, timeout=10)
    print(f'Tunnel: {r3.read().decode()[:200]}')
except Exception as e:
    print(f'Tunnel: {e}')

# 4. Local
try:
    r4 = urllib.request.urlopen('http://localhost:3000/api/version', timeout=5)
    print(f'Local:  {r4.read().decode()[:200]}')
except Exception as e:
    print(f'Local:  {e}')
