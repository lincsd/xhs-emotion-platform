import urllib.request, json

# Test that the server can find 国学 cards
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
    r = urllib.request.urlopen(req, timeout=120)
    d = json.loads(r.read())
    if d.get('ok'):
        print(f"OK! title: {d['note']['title'][:50]}")
    else:
        print(f"Error: {d.get('error', 'unknown')}")
except Exception as e:
    print(f"FAILED: {e}")
