#!/usr/bin/env python3
"""v10 架构升级补丁 — 一次性应用所有改动到 generate_card_images_v3.py"""

import re

TARGET = 'generate_card_images_v3.py'

with open(TARGET, 'r', encoding='utf-8') as f:
    content = f.read()
    original = content

changes = 0

# ═══════════════════════════════════════════
# Change 1: 简化 manifest 注入 — 删除 Unicode codepoint 冗余
# ═══════════════════════════════════════════
old_lines_1 = [
    '    # 逐字注入 manifest —— 让模型精确知道每个字',
    '    if manifest:',
    '        # 再次强制确保manifest字数在限制内',
    '        manifest = _enforce_manifest_limits(manifest)',
    '        total_cn = sum(_count_chinese_chars(v) for v in manifest.values())',
]
new_lines_1_header = [
    '    # 注入 manifest — 精简格式，减少噪声（删除 Unicode codepoint 冗余）',
    '    if manifest:',
    '        # 再次强制确保manifest字数在限制内',
    '        manifest = _enforce_manifest_limits(manifest)',
    '        total_cn = sum(_count_chinese_chars(v) for v in manifest.values())',
]

# Find the block from "逐字注入 manifest" to "if audit_hint:"
marker_start = '    # 逐字注入 manifest'
marker_end = '\n    if audit_hint:'
idx_s = content.find(marker_start)
idx_e = content.find(marker_end, idx_s)

if idx_s >= 0 and idx_e >= 0:
    new_block = """    # 注入 manifest — 精简格式，减少噪声（删除 Unicode codepoint 冗余）
    if manifest:
        # 再次强制确保manifest字数在限制内
        manifest = _enforce_manifest_limits(manifest)
        total_cn = sum(_count_chinese_chars(v) for v in manifest.values())
        chinese_prefix += f"\\n=== EXACT TEXT ({total_cn} Chinese chars — MAXIMUM) ===\\n"
        for key, val in manifest.items():
            chinese_prefix += f"{key}: \\"{val}\\"\\n"
        chinese_prefix += "=== END TEXT ===\\n"
        chinese_prefix += f"IMPORTANT: Render ONLY these {total_cn} Chinese characters. Do NOT add ANY extra Chinese text. Do NOT change or approximate any character. ALL background/decorative areas must be text-free (no random Chinese).\\n"
"""
    content = content[:idx_s] + new_block + content[idx_e:]
    changes += 1
    print(f'[OK] Change 1: Manifest injection simplified (removed Unicode codepoints)')
else:
    print(f'[SKIP] Change 1: marker not found (start={idx_s}, end={idx_e})')


# ═══════════════════════════════════════════
# Change 2: 简化 audit hint — 删除 Unicode codepoint 冗余
# ═══════════════════════════════════════════
marker2_start = '        # 逐字拆分期望文字'
marker2_end_text = "            hints.append(f'Fix:"
idx2_s = content.find(marker2_start)
if idx2_s >= 0:
    # Find the end of this block (the 'else:' + hints.append line + closing)
    idx2_e = content.find("\n\n    return '\\n'.join(hints)", idx2_s)
    if idx2_e < 0:
        idx2_e = content.find('\n\n    return', idx2_s)
    
    if idx2_e >= 0:
        new_audit_block = """        if etype == 'garbled':
            hints.append(f'CRITICAL: "{exp}" appeared as garbled "{act}". Render EXACTLY "{exp}" in thick bold strokes.')
        elif etype == 'wrong_char':
            hints.append(f'WRONG CHARACTER: "{act}" must be "{exp}". Replace exactly.')
        elif etype == 'missing':
            hints.append(f'MISSING TEXT: "{exp}" must appear. Add it clearly.')
        elif etype == 'distorted':
            hints.append(f'DISTORTED: "{exp}" is unreadable. Re-render with thick bold strokes.')
        else:
            hints.append(f'Fix: "{act}" → "{exp}"')"""
        content = content[:idx2_s] + new_audit_block + content[idx2_e:]
        changes += 1
        print(f'[OK] Change 2: Audit hint simplified (removed Unicode codepoints)')
    else:
        print(f'[SKIP] Change 2: end marker not found')
else:
    print(f'[SKIP] Change 2: start marker not found')


# ═══════════════════════════════════════════
# Change 3: manifest 字数硬限收紧 15→12
# ═══════════════════════════════════════════
old_default = "'max_chinese_chars': 20,"
old_default2 = "'max_chinese_chars': 15"
# In _get_effective_params defaults
content = content.replace(
    "            'max_chinese_chars': 20,\n            'max_chars_per_block': 5,",
    "            'max_chinese_chars': 15,\n            'max_chars_per_block': 4,",
)
changes += 1
print(f'[OK] Change 3: Manifest char limits tightened (20→15 total, 5→4 per block)')


# ═══════════════════════════════════════════
# Change 4: PROMPT_SYSTEM_TEMPLATE 加负约束
# ═══════════════════════════════════════════
# 在"提示词长度: 350-500 英文单词。"前面加一条负约束
old_end_prompt = '提示词长度: 350-500 英文单词。"""'
new_end_prompt = """══════ ⚠️ 额外禁令 ══════

- ❌ 背景装饰区域不得出现任何中文
- ❌ 不在空白区域随机添加中文文字
- ❌ 不要在图片边缘/角落放无意义的中文字符
- 只有 TEXT_MANIFEST 中列出的文字才允许出现

提示词长度: 350-500 英文单词。\"\"\""""
content = content.replace(old_end_prompt, new_end_prompt, 1)
changes += 1
print(f'[OK] Change 4: Added negative constraints to PROMPT_SYSTEM_TEMPLATE')

# Also add to wellness template
old_end_wellness = '提示词长度: 350-500 英文单词。"""'
if old_end_wellness in content:
    content = content.replace(old_end_wellness, new_end_prompt, 1)
    print(f'[OK] Change 4b: Added negative constraints to WELLNESS template too')


# ═══════════════════════════════════════════
# Save
# ═══════════════════════════════════════════
with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'\n✅ Applied {changes} changes. File: {len(original)} → {len(content)} chars')
