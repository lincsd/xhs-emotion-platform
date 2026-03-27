#!/usr/bin/env python3
"""Patch v3 prompt: upgrade iron rules 9→12"""
import re

fp = r'd:\Users\Administrator\Desktop\ls\xhsqg\generate_card_images_v3.py'
with open(fp, 'r', encoding='utf-8') as f:
    src = f.read()

old_rules = '''⚠️⚠️⚠️ 极重要提醒：英语卡片质量铁律！
🔒1. 单卡只讲一个知识点！标题必须精确(如\u201cpay attention to搭配\u201d)，禁止泛化标题如\u201c高频词\u201d\u201c重点语法\u201d
🔒2. 知识点准确性第一！不能把正确用法标为❌！每个❌/✅必须反复检查
🔒3. 必须有完整例句对比(不能只放孤立短语)：❌错句 vs ✅正句，例句必须是完整英语句子
🔒4. 所有英文单词必须是真实存在的词！严禁编造不存在的词(如guestioneful)
🔒5. 错因必须具体(如\u201cto后接动词原形\u201d)，禁止\u201c词性错\u201d\u201c搭配错\u201d等笼统说法
🔒6. 口诀必须有记忆粘性，禁止\u201c搭配固定\u201d\u201c多练就会\u201d\u201c记住就好\u201d类废话！
🔒7. 所有Steps必须围绕同一个知识点展开，步骤间逻辑连贯递进
🔒8. 视觉隐喻必须匹配内容逻辑(不用阶梯图表示非递进关系)
🔒9. 学生看完必须能答\u201c为什么这样用\u201d，不能只停留在\u201c知道这样用\u201d'''

# Also try with straight quotes in case the file was edited
old_rules_alt = old_rules.replace('\u201c', '"').replace('\u201d', '"')

new_rules = '''⚠️⚠️⚠️ 极重要提醒：英语卡片质量铁律！
🔒1. 单卡只讲一个知识点！标题必须精确(如"pay attention to搭配")，禁止泛化标题如"高频词""重点语法""搭配活用"
🔒2. 知识点准确性第一！不能把正确用法标为❌！每个❌/✅必须反复检查
🔒3. 必须有完整例句对比(不能只放孤立短语)：❌错句 vs ✅正句，例句必须是完整英语句子
🔒4. 所有英文单词必须是真实存在的词！严禁编造不存在的词(如guestioneful)
🔒5. 错因必须具体(如"to后接动词原形")，禁止"词性错""搭配错"等笼统说法
🔒6. 口诀必须是完整有意义的短句(如"to后加原形")，禁止截断废话如"搭配固定要""搭配固定""多练就会""记住就好"！
🔒7. 所有Steps必须围绕同一个知识点展开，步骤间逻辑连贯递进
🔒8. 视觉隐喻必须匹配内容逻辑(不用阶梯图表示非递进关系)
🔒9. 学生看完必须能答"为什么这样用"，不能只停留在"知道这样用"
🔒10. 🚫严禁在图中添加任何与"{topic_phrase}"无关的语法公式、规则、知识点！（如本卡讲搭配，就不能出现Modal verb公式）
🔒11. 图片底部/总结区域只能总结本卡主题的结论，禁止突然出现卡片数据中没有的新知识点！
🔒12. 所有中文文字必须是完整的词/短句，禁止截断（如"搭配固"就是截断废字）'''

if old_rules in src:
    src = src.replace(old_rules, new_rules)
    print("Replaced with smart quotes version")
elif old_rules_alt in src:
    src = src.replace(old_rules_alt, new_rules)
    print("Replaced with straight quotes version")
else:
    # Try to find the marker and do line-based replacement
    lines = src.split('\n')
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if '极重要提醒：英语卡片质量铁律' in line:
            start_idx = i
        if start_idx and '知道这样用' in line:
            end_idx = i
            break
    if start_idx is not None and end_idx is not None:
        before = '\n'.join(lines[:start_idx])
        after = '\n'.join(lines[end_idx+1:])
        src = before + '\n' + new_rules + '\n' + after
        print(f"Line-based replacement: lines {start_idx+1}~{end_idx+1}")
    else:
        print("ERROR: Could not find iron rules block!")
        print(f"start_idx={start_idx}, end_idx={end_idx}")
        # Show context
        for i, line in enumerate(lines):
            if '铁律' in line or '知道这样' in line:
                print(f"  L{i+1}: {line[:80]}")
        exit(1)

with open(fp, 'w', encoding='utf-8') as f:
    f.write(src)

# Verify
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()
assert '🔒10.' in content, "Rule 10 not found after patch!"
assert '🔒11.' in content, "Rule 11 not found after patch!"
assert '🔒12.' in content, "Rule 12 not found after patch!"
assert '搭配固定要' in content, "Rule 6 example not found!"
print("✅ Patch verified: 12 iron rules in place")
