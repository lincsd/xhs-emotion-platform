import urllib.request, json

# 1. Test localhost generate-note with CORS
print('=== TEST LOCALHOST generate-note ===')
body = json.dumps({
    'subject': '养生',
    'grade_short': '经期调理',
    'template': '反差型',
    'card_ids': ['养生减脂-爆款-B1-01']
}).encode()
req = urllib.request.Request(
    'http://localhost:3000/api/generate-note',
    data=body,
    headers={
        'Content-Type': 'application/json',
        'Origin': 'https://lincsd.github.io'
    },
    method='POST'
)
try:
    r = urllib.request.urlopen(req, timeout=120)
    print(f'Status: {r.status}')
    acao = r.getheader('Access-Control-Allow-Origin', 'MISSING')
    acam = r.getheader('Access-Control-Allow-Methods', 'MISSING')
    print(f'Access-Control-Allow-Origin: {acao}')
    print(f'Access-Control-Allow-Methods: {acam}')
    d = json.loads(r.read())
    if d.get('ok'):
        print(f'OK! title: {d["note"]["title"][:30]}')
    else:
        print(f'Error: {d.get("error", "")}')
except urllib.error.HTTPError as e:
    print(f'HTTP {e.code}')
    acao = e.headers.get('Access-Control-Allow-Origin', 'MISSING')
    print(f'ACAO: {acao}')
    print(e.read().decode()[:200])
except Exception as e:
    print(f'FAILED: {e}')

# 2. Test CORS preflight (OPTIONS)
print()
print('=== TEST CORS PREFLIGHT (OPTIONS) ===')
req2 = urllib.request.Request(
    'http://localhost:3000/api/generate-note',
    method='OPTIONS',
    headers={
        'Origin': 'https://lincsd.github.io',
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type'
    }
)
try:
    r2 = urllib.request.urlopen(req2, timeout=5)
    print(f'Status: {r2.status}')
    print(f'ACAO: {r2.getheader("Access-Control-Allow-Origin", "MISSING")}')
    print(f'ACAM: {r2.getheader("Access-Control-Allow-Methods", "MISSING")}')
    print(f'ACAH: {r2.getheader("Access-Control-Allow-Headers", "MISSING")}')
except urllib.error.HTTPError as e:
    print(f'HTTP {e.code}')
    print(f'ACAO: {e.headers.get("Access-Control-Allow-Origin", "MISSING")}')
except Exception as e:
    print(f'FAILED: {e}')

# 3. Test tunnel
print()
print('=== TEST TUNNEL ===')
browser_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
req3 = urllib.request.Request(
    'https://xhs.xiaohsai.com/api/generate-note',
    data=body,
    headers={
        'Content-Type': 'application/json',
        'Origin': 'https://lincsd.github.io',
        'User-Agent': browser_ua
    },
    method='POST'
)
try:
    r3 = urllib.request.urlopen(req3, timeout=120)
    print(f'Status: {r3.status}')
    acao = r3.getheader('Access-Control-Allow-Origin', 'MISSING')
    print(f'ACAO: {acao}')
    d3 = json.loads(r3.read())
    if d3.get('ok'):
        print(f'OK! title: {d3["note"]["title"][:30]}')
    else:
        print(f'Error: {d3.get("error", "")}')
except urllib.error.HTTPError as e:
    print(f'HTTP {e.code}')
    print(e.read().decode()[:300])
except Exception as e:
    print(f'FAILED: {e}')
