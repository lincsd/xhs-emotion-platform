import urllib.request, json

# Test v3 image generation via tunnel for wellness card
print('=== TEST v3 image gen via TUNNEL ===')
card = {
    "full_id": "养生减脂-爆款-B1-01",
    "card_id": "养生减脂-爆款-B1-01",
    "type": "反差卡",
    "title": "健康减脂餐vs伪健康减脂餐",
    "_subject": "养生减脂"
}
body = json.dumps({
    'card': card,
    'subject': '养生减脂',
    'grade': '爆款',
    'semester': 'B1单元'
}).encode()

browser_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

# First test via localhost
print('\n--- Localhost ---')
req = urllib.request.Request(
    'http://localhost:3000/api/generate-card-image-v3',
    data=body,
    headers={'Content-Type': 'application/json', 'Origin': 'https://lincsd.github.io'},
    method='POST'
)
try:
    r = urllib.request.urlopen(req, timeout=300)
    print(f'Status: {r.status}')
    acao = r.getheader('Access-Control-Allow-Origin', 'MISSING')
    print(f'ACAO: {acao}')
    d = json.loads(r.read())
    if d.get('ok'):
        print(f'OK! image size: {len(d.get("image",""))[:100] if d.get("image") else "none"}')
        print(f'auditScore: {d.get("auditScore")}')
    else:
        print(f'Error: {d.get("error","")}')
except urllib.error.HTTPError as e:
    print(f'HTTP {e.code}')
    print(e.read().decode()[:500])
except Exception as e:
    print(f'FAILED: {e}')

# Then test via tunnel
print('\n--- Tunnel ---')
req2 = urllib.request.Request(
    'https://xhs.xiaohsai.com/api/generate-card-image-v3',
    data=body,
    headers={
        'Content-Type': 'application/json',
        'Origin': 'https://lincsd.github.io',
        'User-Agent': browser_ua
    },
    method='POST'
)
try:
    r2 = urllib.request.urlopen(req2, timeout=300)
    print(f'Status: {r2.status}')
    acao = r2.getheader('Access-Control-Allow-Origin', 'MISSING')
    print(f'ACAO: {acao}')
    d2 = json.loads(r2.read())
    if d2.get('ok'):
        print(f'OK! rounds: {d2.get("rounds")}, model: {d2.get("model")}')
    else:
        print(f'Error: {d2.get("error","")}')
except urllib.error.HTTPError as e:
    print(f'HTTP {e.code}')
    print(e.read().decode()[:500])
except Exception as e:
    print(f'FAILED: {e}')
