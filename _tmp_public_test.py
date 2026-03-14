import json, urllib.request, urllib.error
from pathlib import Path

BASE = 'https://xhs-gemini-proxy.onrender.com/api/gemini-proxy'
raw = Path('api_key.txt').read_text(encoding='utf-8').strip()
key = raw.split('=',1)[-1].strip()


def call(model, payload):
    body = json.dumps({
        'apiKey': key,
        'model': model,
        'payload': payload,
        'action': 'generateContent'
    }).encode('utf-8')
    req = urllib.request.Request(BASE, data=body, headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=220) as r:
            return r.getcode(), json.loads(r.read().decode('utf-8', errors='replace'))
    except urllib.error.HTTPError as e:
        txt = e.read().decode('utf-8', errors='replace')
        try:
            data = json.loads(txt)
        except Exception:
            data = {'raw': txt[:1200]}
        return e.code, data
    except Exception as e:
        return -1, {'error': str(e)}

# 1) 文本生成测试
text_payload = {
    'contents': [{'parts':[{'text':'请生成1条小红书图文笔记，返回标题、正文、3个标签。'}]}]
}
code1, data1 = call('gemini-2.5-flash', text_payload)
text = ''
try:
    text = data1.get('candidates',[{}])[0].get('content',{}).get('parts',[{}])[0].get('text','')
except Exception:
    text = ''

# 2) 图片生成测试（Nano Banana默认模型）
img_payload = {
    'contents': [{'parts':[{'text':'Create a vertical 3:4 Xiaohongshu style cover image about healing mood, no text'}]}],
    'generationConfig': {'responseModalities':['IMAGE']}
}
code2, data2 = call('gemini-2.5-flash-image', img_payload)
img_b64_len = 0
mime = ''
try:
    parts = data2.get('candidates',[{}])[0].get('content',{}).get('parts',[])
    for p in parts:
        inline = p.get('inlineData') or {}
        if inline.get('data'):
            img_b64_len = len(inline.get('data'))
            mime = inline.get('mimeType','')
            break
except Exception:
    pass

print('TEXT_STATUS', code1)
print('TEXT_OK', bool(text.strip()))
print('TEXT_PREVIEW', (text or '')[:120].replace('\n',' '))
print('IMG_STATUS', code2)
print('IMG_OK', img_b64_len > 0)
print('IMG_MIME', mime)
print('IMG_B64_LEN', img_b64_len)

if code1 != 200:
    print('TEXT_ERR', json.dumps(data1, ensure_ascii=False)[:500])
if code2 != 200 or img_b64_len == 0:
    print('IMG_ERR', json.dumps(data2, ensure_ascii=False)[:700])
