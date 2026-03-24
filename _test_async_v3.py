#!/usr/bin/env python3
"""Test async v3 image generation flow (submit + poll) via tunnel"""
import urllib.request, json, time

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

def test_async(base_url, label):
    print(f'\n=== {label}: {base_url} ===')
    body = json.dumps({
        'card': {'full_id': '养生减脂-爆款-B1-01', 'type': '反差卡', 'title': 'test', '_subject': '养生减脂'},
        'subject': '养生减脂', 'grade': '爆款', 'skipAudit': True
    }).encode()

    # Step 1: Submit async task
    print('1. Submitting async task...')
    t0 = time.time()
    req = urllib.request.Request(
        f'{base_url}/api/generate-card-image-v3-async',
        data=body,
        headers={'Content-Type': 'application/json', 'Origin': 'https://lincsd.github.io', 'User-Agent': UA},
    )
    try:
        r = urllib.request.urlopen(req, timeout=30)
        d = json.loads(r.read())
        print(f'   Status: {r.status}, ACAO: {r.getheader("Access-Control-Allow-Origin","NONE")}')
        print(f'   Response: {d}')
        task_id = d.get('task_id')
        if not task_id:
            print('   FAIL: No task_id!')
            return
        print(f'   Submit took: {time.time()-t0:.1f}s')
    except Exception as e:
        print(f'   SUBMIT FAILED: {e}')
        return

    # Step 2: Poll for result
    print(f'2. Polling task {task_id}...')
    for i in range(60):  # max 3 minutes
        time.sleep(3)
        elapsed = time.time() - t0
        try:
            poll_req = urllib.request.Request(
                f'{base_url}/api/task-status/{task_id}',
                headers={'Origin': 'https://lincsd.github.io', 'User-Agent': UA},
            )
            pr = urllib.request.urlopen(poll_req, timeout=15)
            pd = json.loads(pr.read())
            status = pd.get('status')
            progress = pd.get('progress', '')
            print(f'   [{elapsed:.0f}s] status={status} progress={progress}')
            
            if status == 'done':
                result = pd.get('result', {})
                print(f'   ✅ DONE! ok={result.get("ok")} model={result.get("model")} rounds={result.get("rounds")}')
                print(f'   auditScore={result.get("auditScore")} qualityScore={result.get("qualityScore")}')
                print(f'   image size: {len(result.get("image",""))} chars base64')
                print(f'   Total time: {elapsed:.1f}s')
                return True
            elif status == 'error':
                result = pd.get('result', {})
                print(f'   ❌ ERROR: {result.get("error","")}')
                return False
        except Exception as e:
            print(f'   [{elapsed:.0f}s] poll error: {e}')
    
    print('   TIMEOUT: task did not complete in 180s')
    return False

# Test localhost first
test_async('http://localhost:3000', 'LOCALHOST')

# Test via tunnel
test_async('https://xhs.xiaohsai.com', 'TUNNEL')
