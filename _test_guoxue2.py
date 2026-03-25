import urllib.request, json

# Test card file loading by trying to find the card
body = json.dumps({
    'subject': '国学',
    'grade_short': '预言', 
    'template': '故事型',
    'card_ids': ['国学-预言-01-01']
}).encode()

req = urllib.request.Request(
    'http://localhost:3000/api/generate-note',
    data=body,
    headers={'Content-Type': 'application/json', 'Origin': 'https://lincsd.github.io'},
    method='POST'
)

try:
    r = urllib.request.urlopen(req, timeout=180)
    d = json.loads(r.read())
    if d.get('ok'):
        print(f"SUCCESS! title: {d['note']['title'][:60]}")
        print(f"slides: {len(d['note'].get('slides', []))}")
    else:
        print(f"API Error: {d.get('error', 'unknown')}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body[:300]}")
except Exception as e:
    print(f"Exception: {e}")
