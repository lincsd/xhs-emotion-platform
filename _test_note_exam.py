import urllib.request, json

# Test 1: without card_ids
print("=== Test 1: without card_ids ===")
body = json.dumps({'subject':'数学','grade_short':'三下','template':'干货型'}).encode()
req = urllib.request.Request('http://localhost:3000/api/generate-note', data=body, headers={'Content-Type':'application/json'})
try:
    resp = urllib.request.urlopen(req, timeout=10)
    d = json.loads(resp.read())
    print(f"ok={d.get('ok')} error={d.get('error')}")
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8')
    print(f"HTTP {e.code}: {body[:300]}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: with exam card_id
print("\n=== Test 2: with exam card_id ===")
body = json.dumps({'subject':'数学','grade_short':'三下','template':'干货型','card_ids':['数学-三下-E1-01']}).encode()
req = urllib.request.Request('http://localhost:3000/api/generate-note', data=body, headers={'Content-Type':'application/json'})
try:
    resp = urllib.request.urlopen(req, timeout=10)
    d = json.loads(resp.read())
    print(f"ok={d.get('ok')} error={d.get('error')}")
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8')
    print(f"HTTP {e.code}: {body[:300]}")
except Exception as e:
    print(f"Error: {e}")

# Test 3: with standard card_id  
print("\n=== Test 3: with standard card_id ===")
body = json.dumps({'subject':'数学','grade_short':'三下','template':'干货型','card_ids':['数学-三下-U1-01']}).encode()
req = urllib.request.Request('http://localhost:3000/api/generate-note', data=body, headers={'Content-Type':'application/json'})
try:
    resp = urllib.request.urlopen(req, timeout=10)
    d = json.loads(resp.read())
    print(f"ok={d.get('ok')} error={d.get('error')}")
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8')
    print(f"HTTP {e.code}: {body[:300]}")
except Exception as e:
    print(f"Error: {e}")
