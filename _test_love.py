import json, sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# First validate JSON
fp = r'd:\Users\Administrator\Desktop\ls\xhsqg\public\knowledge_cards\情感生活\恋爱_谈恋爱.json'
print(f'File exists: {os.path.exists(fp)}')
try:
    with open(fp, encoding='utf-8') as f:
        d = json.load(f)
    total = sum(len(u['cards']) for u in d['units'])
    print(f'JSON OK: {len(d["units"])} units, {total} cards')
except json.JSONDecodeError as e:
    print(f'JSON ERROR: {e}')
    sys.exit(1)

# Then test API
import urllib.request, urllib.error
body = json.dumps({
    'subject': '恋爱',
    'grade_short': '谈恋爱',
    'template': '干货型',
    'card_ids': ['恋爱-谈恋爱-01-01']
}).encode()

req = urllib.request.Request(
    'http://localhost:3000/api/generate-note',
    data=body,
    headers={'Content-Type': 'application/json', 'Origin': 'http://localhost:3000'},
    method='POST'
)

try:
    r = urllib.request.urlopen(req, timeout=120)
    d = json.loads(r.read())
    if d.get('ok'):
        title = d['note']['title']
        slides = len(d['note'].get('slides', []))
        print(f'SUCCESS! title: {title}, slides: {slides}')
    else:
        print(f'Error: {d.get("error", "")}')
except urllib.error.HTTPError as e:
    body_text = e.read().decode('utf-8', errors='replace')
    print(f'HTTP {e.code}: {body_text[:500]}')
except Exception as e:
    print(f'FAILED: {e}')
