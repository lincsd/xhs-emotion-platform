"""快速查看生成的英语卡片图片内容（用 Gemini Vision 描述）"""
import os, sys, json, base64
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

# Load key
with open('api_key.txt') as f:
    for line in f:
        if line.startswith('GEMINI_API_KEY='):
            KEY = line.split('=', 1)[1].strip().split(',')[0]
            break

from generate_card_images_v3 import gemini_call

img_path = '_test_english_card_output.jpg'
with open(img_path, 'rb') as f:
    img_data = f.read()

b64 = base64.b64encode(img_data).decode()

contents = [
    {'role': 'user', 'parts': [
        {'text': """Please analyze this educational card image. Tell me:
1. What Chinese text do you see? List each text block.
2. What English text do you see?
3. Is the card about "pay attention to"? 
4. Is the title specific (contains English keyword) or vague (pure Chinese like "高频词汇")?
5. Are there any truncated/incomplete Chinese text blocks?
6. Overall quality assessment (1-10).
7. Any issues you notice?

Answer in Chinese."""},
        {'inlineData': {'mimeType': 'image/jpeg', 'data': b64}}
    ]}
]

resp = gemini_call('gemini-2.5-flash', contents, KEY)
if resp:
    parts = resp.get('candidates', [{}])[0].get('content', {}).get('parts', [])
    for p in parts:
        if 'text' in p and not p.get('thought', False):
            print(p['text'])
else:
    print('ERROR: No response')
