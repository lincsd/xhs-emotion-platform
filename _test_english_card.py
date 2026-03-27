#!/usr/bin/env python3
"""测试英语知识总结卡（高频词汇活用与固定搭配）的生成流水线。

对应截图中的卡片 #12：
- 标题：高频词汇活用与固定搭配
- 描述：熟练掌握高考高频词汇的多种用法，固定搭配和短语动词，是提升语言运用能力和高考成绩的关键。
- 类型：知识总结卡
- 学科：英语

测试目标：
1. Step 1 生成的 Prompt 质量（铁律是否注入、英文标题是否含英语关键词）
2. TEXT_MANIFEST 质量（有无截断废字、口诀完整性、标题含英文）
3. card_review 硬规则通过情况
4. [可选] Step 2 实际出图
"""
import os, sys, json, time

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

# ── API Key ──
API_KEYS = []
with open('api_key.txt') as f:
    for line in f:
        if line.startswith('GEMINI_API_KEY='):
            keys_str = line.split('=', 1)[1].strip()
            API_KEYS = [k.strip() for k in keys_str.split(',') if k.strip()]
            break

assert API_KEYS, '未找到 API Key'
print(f'[INFO] 找到 {len(API_KEYS)} 个 API Key')

# ── 构造测试卡片（模拟截图中"高频词汇活用与固定搭配"的 pay attention to 卡片） ──
test_card = {
    "full_id": "英语_高三_高频活用卡_pay_attention_to_test",
    "title": "高频词汇活用与固定搭配",
    "type": "高频活用卡",
    "definition": "pay attention to 是高考高频固定搭配，意为'注意、关注'。to是介词，后接名词/动名词。",
    "example": {
        "question": "You should pay attention ___ your pronunciation when speaking English.",
        "steps": [
            "pay attention to 意为'注意'，是固定搭配",
            "to 是介词，不是不定式标志",
            "后接名词: Pay attention to the details. (注意细节)",
            "后接动名词: Pay attention to spelling your name correctly. (注意正确拼写你的名字)"
        ],
        "answer": "to"
    },
    "core_points": [
        "pay attention to 是固定搭配，to 是介词",
        "to 后接名词或动名词(doing)",
        "常考陷阱：学生误把 to 当不定式，后接动词原形"
    ],
    "mistakes": [
        {
            "wrong": "Pay attention to listen carefully.",
            "correct": "Pay attention to listening carefully.",
            "reason": "to 是介词，后面必须接名词或动名词 doing，不能接动词原形"
        }
    ],
    "memory_tip": "to后接doing",
    "emotion_hook": "高考必考的固定搭配陷阱，90%的学生都会犯这个错！",
    "trap_point": "学生容易把 to 当作不定式标志，后面误接动词原形",
    "why_explanation": "pay attention to 中的 to 是介词（prep.），后面只能接名词性成分。而不定式中的 to 后接动词原形。",
    "difficulty": 3
}

# ══════════════════════════════════════════
# TEST 1: card_review 硬规则
# ══════════════════════════════════════════
print('\n' + '='*60)
print('TEST 1: card_review 硬规则')
print('='*60)
try:
    from card_review import validate_hard_rules
    hr = validate_hard_rules(test_card, '英语')
    if hr['pass']:
        print(f'  ✅ 硬规则通过 ({len(hr.get("issues", []))} issues)')
    else:
        print(f'  ⚠️ 硬规则不通过:')
        for iss in hr['issues']:
            print(f'    - {iss}')
except Exception as e:
    print(f'  ❌ card_review 异常: {e}')

# ══════════════════════════════════════════
# TEST 2: Step 1 — 生成 Prompt + TEXT_MANIFEST
# ══════════════════════════════════════════
print('\n' + '='*60)
print('TEST 2: Step 1 — generate_image_prompt()')
print('='*60)

from generate_card_images_v3 import (
    generate_image_prompt, _parse_text_manifest, _enforce_manifest_limits,
    _count_chinese_chars, _ensure_complete_chinese, _fix_english_card_title_manifest,
    _DANGLING_ENDINGS
)

prompt, manifest = generate_image_prompt(
    test_card, '英语', '高三', '下册',
    API_KEYS[0], all_keys=API_KEYS
)

if not prompt:
    print('  ❌ Step 1 失败：未能生成 Prompt')
    sys.exit(1)

print(f'  Prompt 长度: {len(prompt)} 字符')
print(f'  Manifest 块数: {len(manifest) if manifest else 0}')

if manifest:
    print(f'\n  --- TEXT_MANIFEST ---')
    total_cn = 0
    for k, v in manifest.items():
        cn = _count_chinese_chars(v)
        total_cn += cn
        print(f'  {k}: "{v}" ({cn}中文字)')
    print(f'  总中文字数: {total_cn}')

    # ── 检查项 ──
    issues = []

    # 检查1: TITLE 是否包含英文关键词
    title_val = manifest.get('TITLE', '')
    import re
    has_eng = bool(re.search(r'[a-zA-Z]', title_val))
    if not has_eng:
        issues.append(f'TITLE 缺少英文关键词: "{title_val}"')
    else:
        print(f'  ✅ TITLE 含英文: "{title_val}"')

    # 检查2: SLOGAN/TIP/MOTTO 是否完整（不以废尾结尾）
    for key in ['SLOGAN', 'TIP', 'MOTTO']:
        val = manifest.get(key, '')
        if not val:
            continue
        last_char = val[-1] if val else ''
        if last_char in _DANGLING_ENDINGS:
            issues.append(f'{key} 以废尾结尾: "{val}" (末字="{last_char}")')
        else:
            print(f'  ✅ {key} 完整: "{val}"')

    # 检查3: 总汉字数 ≤ 20
    if total_cn > 20:
        issues.append(f'总中文字数={total_cn}>20 超标')
    else:
        print(f'  ✅ 总汉字 {total_cn}≤20')

    # 检查4: 单块 ≤ 5字（SLOGAN允许到6）
    for k, v in manifest.items():
        cn = _count_chinese_chars(v)
        limit = 6 if k.upper() in ('SLOGAN', 'TIP', 'MOTTO') else 5
        if cn > limit:
            issues.append(f'{k} 中文字数={cn}>limit({limit}): "{v}"')

    if issues:
        print(f'\n  ⚠️ Manifest 问题:')
        for iss in issues:
            print(f'    - {iss}')
    else:
        print(f'\n  ✅ Manifest 全部检查通过！')

# ══════════════════════════════════════════
# TEST 3: Prompt 内容审查
# ══════════════════════════════════════════
print('\n' + '='*60)
print('TEST 3: Prompt 内容审查')
print('='*60)

prompt_lower = prompt.lower()

# 检查是否包含关键教学元素
checks = {
    'pay attention to': 'pay attention to' in prompt_lower,
    '完整例句(English sentence)': bool(re.search(r'[A-Z][a-z]+\s+\w+\s+\w+\s+\w+\s+\w+', prompt)),
    '错误对比(❌/✗)': '❌' in prompt or '✗' in prompt or 'wrong' in prompt_lower or 'incorrect' in prompt_lower,
    '正确对比(✅/✓)': '✅' in prompt or '✓' in prompt or 'correct' in prompt_lower,
}

for name, ok in checks.items():
    status = '✅' if ok else '❌'
    print(f'  {status} {name}')

# 输出 prompt 前500字（供人工审查）
print(f'\n  --- Prompt 预览 (前800字) ---')
print(prompt[:800])
print(f'  ... (共{len(prompt)}字)')

# ══════════════════════════════════════════
# TEST 4: Step 2 — 实际生成图片
# ══════════════════════════════════════════
print('\n' + '='*60)
print('TEST 4: Step 2 — generate_card_image()')
print('='*60)

from generate_card_images_v3 import generate_card_image

print('  正在生成图片（可能需要30-60秒）...')
t0 = time.time()
img_data, ext, model = generate_card_image(
    prompt, API_KEYS,
    card_title=test_card['title'],
    subject='英语',
    audit_hint='',
    manifest=manifest
)
elapsed = time.time() - t0

if img_data:
    size_kb = len(img_data) / 1024
    print(f'  ✅ 图片生成成功: {size_kb:.0f}KB, 格式={ext}, 模型={model}, 耗时={elapsed:.1f}s')

    # 保存图片到文件
    import base64
    out_path = f'_test_english_card_output.{ext}'
    with open(out_path, 'wb') as f:
        f.write(img_data)
    print(f'  💾 图片已保存: {out_path}')
else:
    print(f'  ❌ 图片生成失败 (耗时={elapsed:.1f}s)')

# ══════════════════════════════════════════
# TEST 5: OCR 审计（如果图片生成成功）
# ══════════════════════════════════════════
if img_data:
    print('\n' + '='*60)
    print('TEST 5: OCR 审计')
    print('='*60)
    try:
        from generate_card_images_v3 import ocr_audit
        audit_result = ocr_audit(img_data, manifest or {}, API_KEYS[0], all_keys=API_KEYS)
        if audit_result:
            score = audit_result.get('score', 0)
            verdict = audit_result.get('verdict', '')
            ocr_text = audit_result.get('ocr_text', '')
            print(f'  分数: {score}/100')
            print(f'  结论: {verdict}')
            if ocr_text:
                print(f'  OCR识别文字: {ocr_text[:200]}')
            issues_list = audit_result.get('issues', [])
            if issues_list:
                print(f'  问题:')
                for iss in issues_list[:5]:
                    print(f'    - {iss}')
        else:
            print('  ⚠️ OCR 审计无结果')
    except Exception as e:
        print(f'  ❌ OCR审计异常: {e}')

# ══════════════════════════════════════════
# TEST 6: 质量评分（如果图片生成成功）
# ══════════════════════════════════════════
if img_data:
    print('\n' + '='*60)
    print('TEST 6: 质量评分')
    print('='*60)
    try:
        from generate_card_images_v3 import quality_score
        qr = quality_score(img_data, API_KEYS[0], card_title=test_card['title'], all_keys=API_KEYS)
        if qr:
            qs = qr.get('score', 0)
            print(f'  质量分: {qs}/100')
            dims = qr.get('dimensions', {})
            if dims:
                for dim_name, dim_val in dims.items():
                    print(f'    {dim_name}: {dim_val}')
        else:
            print('  ⚠️ 质量评分无结果')
    except Exception as e:
        print(f'  ❌ 质量评分异常: {e}')

print('\n' + '='*60)
print('测试完成！')
print('='*60)
