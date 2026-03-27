"""迭代测试 - 测试多种英语卡片以验证质量一致性"""
import os, sys, json, time, base64
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

with open('api_key.txt') as f:
    for line in f:
        if line.startswith('GEMINI_API_KEY='):
            keys_str = line.split('=', 1)[1].strip()
            API_KEYS = [k.strip() for k in keys_str.split(',') if k.strip()]
            break

from generate_card_images_v3 import (
    generate_image_prompt, generate_card_image, gemini_call,
    _count_chinese_chars, _DANGLING_ENDINGS
)
from card_review import validate_hard_rules
import card_review
card_review._BASIC_ENGLISH_WORDS = None  # force reload

# ── 测试卡片2: look forward to (另一个 to 做介词的搭配) ──
card2 = {
    "full_id": "英语_高三_高频活用卡_look_forward_to_test",
    "title": "高频词汇活用与固定搭配",
    "type": "高频活用卡",
    "definition": "look forward to 是高考高频固定搭配，意为'期待、盼望'。to是介词，后接名词/动名词。",
    "example": {
        "question": "I look forward to ___ (hear) from you soon.",
        "steps": [
            "look forward to 意为'期待'，是固定搭配",
            "to 是介词，不是不定式标志",
            "后接名词: I look forward to the weekend. (我期待周末)",
            "后接动名词: I look forward to hearing from you. (我期待收到你的来信)"
        ],
        "answer": "hearing"
    },
    "core_points": [
        "look forward to 中的 to 是介词，后接doing",
        "易与 want to / hope to 混淆",
        "常考形式: look forward to doing sth"
    ],
    "mistakes": [
        {
            "wrong": "I look forward to hear from you.",
            "correct": "I look forward to hearing from you.",
            "reason": "to 是介词，后面必须接动名词 doing，不能接动词原形"
        }
    ],
    "memory_tip": "期待就doing",
    "emotion_hook": "高考完形填空常考陷阱，一不小心就丢分！",
    "trap_point": "与 want to do / hope to do 混淆，误用动词原形",
    "why_explanation": "look forward to 中的 to 是介词 prep.，与 want to (不定式) 本质不同。",
    "difficulty": 3
}

# ── 测试卡片3: be used to vs used to (易混词卡) ──
card3 = {
    "full_id": "英语_高三_易混词卡_used_to_test",
    "title": "高频词汇活用与固定搭配",
    "type": "易混词卡",
    "definition": "be used to doing (习惯于做某事) vs used to do (过去常常做某事)，是高考高频易混搭配。",
    "example": {
        "question": "He ___ (use) to getting up early, but he used to ___ (sleep) late.",
        "steps": [
            "be used to doing = 习惯于做某事，to是介词",
            "used to do = 过去常常做某事，to是不定式", 
            "He is used to getting up early. (他习惯早起)",
            "He used to sleep late. (他过去常常晚睡)"
        ],
        "answer": "is used; sleep"
    },
    "core_points": [
        "be used to + doing (习惯于)",
        "used to + do (过去常常)",
        "两个结构中to的词性不同"
    ],
    "mistakes": [
        {
            "wrong": "I am used to get up early.",
            "correct": "I am used to getting up early.",
            "reason": "be used to 中的 to 是介词，后接动名词doing"
        }
    ],
    "memory_tip": "习惯doing",
    "emotion_hook": "高考必考易混点，你能分清吗？",
    "trap_point": "两个 used to 结构看起来一样但to的词性完全不同",
    "why_explanation": "be used to 中 to=介词(prep.)，used to 中 to=不定式(infinitive)。",
    "difficulty": 4
}

test_cards = [
    ('look forward to', card2),
    ('be used to vs used to', card3),
]

results = []

for name, card in test_cards:
    print(f'\n{"="*60}')
    print(f'测试: {name}')
    print(f'{"="*60}')
    
    result = {'name': name, 'issues': []}

    # 1. card_review
    hr = validate_hard_rules(card, '英语')
    if hr['pass']:
        print(f'  ✅ card_review 通过')
    else:
        for iss in hr['issues']:
            print(f'  ⚠️ {iss}')
            result['issues'].append(f'card_review: {iss}')

    # 2. Generate prompt
    print(f'  Step 1: 生成Prompt...')
    prompt, manifest = generate_image_prompt(card, '英语', '高三', '下册', API_KEYS[0], all_keys=API_KEYS)
    
    if not prompt:
        print(f'  ❌ Prompt生成失败')
        result['issues'].append('Prompt生成失败')
        results.append(result)
        continue

    print(f'  Prompt: {len(prompt)}字')
    
    if manifest:
        print(f'  Manifest:')
        total_cn = 0
        for k, v in manifest.items():
            cn = _count_chinese_chars(v)
            total_cn += cn
            # check dangling
            flag = ''
            if v and v[-1] in _DANGLING_ENDINGS:
                flag = ' ⚠️废尾!'
                result['issues'].append(f'Manifest {k} 废尾: "{v}"')
            print(f'    {k}: "{v}" ({cn}中文字){flag}')
        
        title_val = manifest.get('TITLE', '')
        import re
        if not re.search(r'[a-zA-Z]', title_val):
            result['issues'].append(f'TITLE无英文: "{title_val}"')
            print(f'  ⚠️ TITLE无英文: "{title_val}"')
        else:
            print(f'  ✅ TITLE含英文')
        
        if total_cn > 20:
            result['issues'].append(f'中文超标: {total_cn}')
        print(f'  总中文: {total_cn}/20')

    # 3. Generate image
    print(f'  Step 2: 生成图片...')
    t0 = time.time()
    img_data, ext, model = generate_card_image(prompt, API_KEYS, card_title=card['title'], subject='英语', manifest=manifest)
    elapsed = time.time() - t0
    
    if not img_data:
        print(f'  ❌ 图片生成失败 ({elapsed:.1f}s)')
        result['issues'].append('图片生成失败')
        results.append(result)
        continue
    
    print(f'  ✅ 图片: {len(img_data)/1024:.0f}KB, {model}, {elapsed:.1f}s')
    
    # Save image
    fname = f'_test_card_{name.replace(" ", "_").replace("/", "_")}.{ext}'
    with open(fname, 'wb') as f:
        f.write(img_data)
    print(f'  💾 {fname}')
    
    # 4. Quick Vision check
    print(f'  Vision审查...')
    b64 = base64.b64encode(img_data).decode()
    contents = [
        {'role': 'user', 'parts': [
            {'text': f"""分析这张英语教学卡片图片，简洁回答：
1. 卡片标题是什么？包含英文关键词吗？
2. 是否只讲了一个知识点（{card['definition'][:30]}）？有没有混入其他知识点？
3. 有没有截断/不完整的中文文字？
4. 错误对比例句是否完整（≥5个英文词）？
5. 打分(1-10)及一句话评价。
用中文简洁回答，每项2句话以内。"""},
            {'inlineData': {'mimeType': f'image/{ext}', 'data': b64}}
        ]}
    ]
    resp = gemini_call('gemini-2.5-flash', contents, API_KEYS[0], all_keys=API_KEYS)
    if resp:
        parts = resp.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        for p in parts:
            if 'text' in p and not p.get('thought', False):
                print(f'\n  --- Vision分析 ---')
                print(f'  {p["text"][:600]}')
                result['vision'] = p['text'][:600]
    
    results.append(result)
    time.sleep(2)

# ══════════════════════════════════════════
# 汇总
# ══════════════════════════════════════════
print(f'\n\n{"="*60}')
print('汇总')
print(f'{"="*60}')
all_issues = []
for r in results:
    status = '✅' if not r['issues'] else '⚠️'
    print(f'  {status} {r["name"]}: {len(r["issues"])} issues')
    for iss in r['issues']:
        print(f'      - {iss}')
    all_issues.extend(r['issues'])

if not all_issues:
    print(f'\n🎉 全部测试通过！卡片质量满意！')
else:
    print(f'\n⚠️ 共 {len(all_issues)} 个问题需要关注')
