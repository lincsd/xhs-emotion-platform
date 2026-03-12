import urllib.request, urllib.error, json
key = open(r'D:\Users\Administrator\Desktop\ls\xhsqg\api_key.txt').read().strip().split('=',1)[-1].strip()
print(f'Using key: {key[:8]}...{key[-4:]}')
body = json.dumps({'apiKey': key, 'model': 'gemini-2.5-flash', 'payload': {'contents': [{'parts': [{'text': 'Hi'}]}]}}).encode()
req = urllib.request.Request('http://localhost:3000/api/gemini-proxy', data=body, headers={'Content-Type': 'application/json'})
try:
    resp = urllib.request.urlopen(req, timeout=60)
    data = json.loads(resp.read())
    text = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
    print(f'PROXY_OK: {text.strip()[:80]}')
except urllib.error.HTTPError as e:
    print(f'HTTP {e.code}:')
    print(e.read().decode()[:500])
except Exception as e:
    print(f'Error: {e}')
