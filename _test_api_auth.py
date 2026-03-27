#!/usr/bin/env python3
"""Test API auth + generate-card-image-v3-async locally"""
import urllib.request, json, sys

BASE = 'http://localhost:3000'

# 1. Check version
try:
    r = urllib.request.urlopen(f'{BASE}/api/version', timeout=5)
    ver = json.loads(r.read())
    print(f"✅ Server version: keyCount={ver.get('keyCount')}, hasServerKey={ver.get('hasServerKey')}")
except Exception as e:
    print(f"❌ Server not reachable: {e}")
    sys.exit(1)

# 2. Login
try:
    login_data = json.dumps({'username': 'Lin', 'password': 'lin123456'}).encode()
    req = urllib.request.Request(f'{BASE}/api/auth/login', data=login_data, headers={'Content-Type': 'application/json'})
    r = urllib.request.urlopen(req, timeout=10)
    resp = json.loads(r.read())
    token = resp.get('token', '')
    print(f"✅ Login OK, token length: {len(token)}")
except Exception as e:
    print(f"❌ Login failed: {e}")
    sys.exit(1)

# 3. Test generate-card-image-v3-async with auth
card_data = {
    'card': {
        'full_id': '英语-三下-03-02',
        'type': '句型卡',
        'title': 'Do you like...?',
        'definition': 'test def',
        'core_points': ['point1'],
        'example': {'question': 'Do you like cats?', 'answer': 'Yes, I do.'},
        'difficulty': 3
    },
    'subject': '英语',
    'grade': '三年级',
    'semester': '下册'
}
try:
    req = urllib.request.Request(
        f'{BASE}/api/generate-card-image-v3-async',
        data=json.dumps(card_data).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    )
    r = urllib.request.urlopen(req, timeout=15)
    result = json.loads(r.read())
    print(f"✅ v3-async: task_id={result.get('task_id', 'NONE')}")
    
    if result.get('task_id'):
        # 4. Poll task status once
        import time
        time.sleep(3)
        r2 = urllib.request.urlopen(f"{BASE}/api/task-status/{result['task_id']}", timeout=10)
        status = json.loads(r2.read())
        print(f"✅ Task status: {status.get('status')}")
except urllib.error.HTTPError as e:
    body = e.read().decode()[:300]
    print(f"❌ v3-async HTTP {e.code}: {body}")
except Exception as e:
    print(f"❌ v3-async error: {e}")

# 5. Test WITHOUT auth (should get 401)
try:
    req_noauth = urllib.request.Request(
        f'{BASE}/api/generate-card-image-v3-async',
        data=json.dumps(card_data).encode(),
        headers={'Content-Type': 'application/json'}
    )
    r = urllib.request.urlopen(req_noauth, timeout=10)
    print(f"⚠️ No-auth request succeeded (unexpected): {r.read().decode()[:100]}")
except urllib.error.HTTPError as e:
    if e.code == 401:
        print(f"✅ No-auth correctly rejected with 401")
    else:
        print(f"⚠️ No-auth got unexpected HTTP {e.code}")
except Exception as e:
    print(f"❌ No-auth test error: {e}")

print("\n--- Done ---")
