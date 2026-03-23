"""Test Gemini API to reproduce 400 error"""
import urllib.request, json, ssl, sys

with open('api_key.txt', 'r') as f:
    keys = f.read().strip().split(',')
key = keys[0].strip()

print(f"Using key: {key[:10]}...{key[-4:]}")
print(f"Key length: {len(key)}")

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"

body = json.dumps({
    "contents": [{"parts": [{"text": "Hello, reply with just OK"}]}],
    "generationConfig": {"temperature": 0.8, "maxOutputTokens": 4096}
}).encode('utf-8')

req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")

ctx = ssl.create_default_context()

try:
    resp = urllib.request.urlopen(req, timeout=60, context=ctx)
    data = json.loads(resp.read().decode('utf-8'))
    text = ''
    for part in data.get('candidates', [{}])[0].get('content', {}).get('parts', []):
        if 'text' in part and 'thought' not in part:
            text = part['text'].strip()
    print(f"SUCCESS: {text}")
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8')
    print(f"HTTP Error {e.code}: {e.reason}")
    print(f"Response body:\n{body}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
