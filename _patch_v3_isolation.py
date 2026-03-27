#!/usr/bin/env python3
"""Patch v3 prompt: strengthen topic isolation rules"""
fp = r'd:\Users\Administrator\Desktop\ls\xhsqg\generate_card_images_v3.py'
with open(fp, 'r', encoding='utf-8') as f:
    src = f.read()

# Find and replace the instruction block after the iron rules
old_block = """图片上只能出现"""
# Add a strong isolation instruction BEFORE the char limit line
isolation_instruction = """🚨🚨🚨 最终检查清单（生成图片前必须逐条确认）：
□ 图中是否只有「{topic_phrase}」这一个语法/搭配知识点？
□ 是否有任何与「{topic_phrase}」无关的公式/规则/例子？如果有，立即删除！
□ 答案区域是否只包含「{topic_phrase}」相关的答案？
□ Common Error 是否与「{topic_phrase}」直接相关？
□ 口诀是否是完整且有意义的中文短句？

图片上只能出现"""

if old_block in src:
    src = src.replace(old_block, isolation_instruction, 1)  # only first occurrence in grammar func
    print("✅ Isolation checklist injected")
else:
    print("ERROR: Could not find insertion point")
    exit(1)

with open(fp, 'w', encoding='utf-8') as f:
    f.write(src)

# Verify
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()
assert '最终检查清单' in content
assert '立即删除' in content
print("✅ Patch verified")
