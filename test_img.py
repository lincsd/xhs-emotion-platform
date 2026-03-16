import urllib.request, json, ssl, time, sys
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
url = 'https://xhs-gemini-proxy.onrender.com/api/gemini-proxy'
model = sys.argv[1] if len(sys.argv) > 1 else 'gemini-2.5-flash-image'
prompt = sys.argv[2] if len(sys.argv) > 2 else 'Generate a beautiful cover image for a Chinese social media post. Category: love. Cover text: heart. Style: aesthetic, soft colors. Vertical 3:4 ratio.'
body = json.dumps({
    'model': model,
    'payload': {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'responseModalities': ['TEXT', 'IMAGE']}
    },
    'action': 'generateContent', 'feature': 'img'
}).encode()
req = urllib.request.Request(url, data=body, headers={'Content-Type':'application/json'})
sys.stdout.write(f"Calling {model}...")
sys.stdout.flush()
t0 = time.time()
try:
    resp = urllib.request.urlopen(req, timeout=180, context=ctx)
    raw = resp.read()
    elapsed = time.time() - t0
    data = json.loads(raw)
    parts = data.get('candidates',[{}])[0].get('content',{}).get('parts',[])
    has_image = any(p.get('inlineData') for p in parts)
    # Don't print base64 data, just metadata
    print(f" {elapsed:.1f}s image={has_image} size={len(raw)//1024}KB")
    if not has_image:
        text_parts = [p.get('text','')[:200] for p in parts if p.get('text')]
        print(f"  Text response: {text_parts}")
        # Check finish reason
        fr = data.get('candidates',[{}])[0].get('finishReason','?')
        print(f"  Finish reason: {fr}")
    if has_image:
        img_part = [p for p in parts if p.get('inlineData')][0]['inlineData']
        print(f"  Image: {img_part.get('mimeType','?')}")
except urllib.error.HTTPError as e:
    elapsed = time.time() - t0
    body_text = e.read().decode()[:200]
    is_render = '<html' in body_text.lower()
    print(f" HTTP {e.code} in {elapsed:.1f}s {'(Render timeout)' if is_render else body_text[:100]}")
except Exception as e:
    elapsed = time.time() - t0
    print(f" ERROR in {elapsed:.1f}s: {e}")
