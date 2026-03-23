"""Quick test to verify the server routing works for /api/ai-match-cards."""
import sys, os, json, threading, time
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

# Monkey-patch to capture routing decisions
original_read = None

import server

# Start server in thread
srv = server.ThreadedHTTPServer(('0.0.0.0', 3001), server.APIHandler)
t = threading.Thread(target=srv.serve_forever, daemon=True)
t.start()
time.sleep(1)

# Test
import urllib.request
tests = [
    ('GET', 'http://localhost:3001/api/generated-notes', None),
    ('POST', 'http://localhost:3001/api/ai-match-cards', {'query': 'test'}),
    ('POST', 'http://localhost:3001/api/generate-note', {'subject': '数学', 'grade_short': '三上', 'template': '反差型'}),
]

for method, url, data in tests:
    try:
        if data:
            req = urllib.request.Request(url, json.dumps(data).encode(), {'Content-Type': 'application/json'})
        else:
            req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req)
        body = resp.read().decode()[:200]
        print(f"  {method} {url.split('3001')[1]} => {resp.status} {body[:100]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        print(f"  {method} {url.split('3001')[1]} => {e.code} {body[:100]}")
    except Exception as ex:
        print(f"  {method} {url.split('3001')[1]} => ERROR: {ex}")

srv.shutdown()
print("Done")
