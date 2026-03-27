"""修改 generate_card_images_v3.py 的铁律规则"""
with open('generate_card_images_v3.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = """⚠️⚠️⚠️ 极重要提醒：英语卡片质量铁律！
🔒1. 知识点准确性第一！不能把正确用法标为❌！每个❌/✅必须反复检查。
🔒2. 必须有完整例句对比(不能只放孤立短语)：❌错句 vs ✅正句
🔒3. 口诀必须有记忆粘性，禁止\u201c搭配固定\u201d\u201c多练就会\u201d\u201c记住就好\u201d类废话！
🔒4. 视觉隐喻必须匹配内容逻辑(不用阶梯图表示非递进关系)
🔒5. 学生看完必须能答\u201c为什么这样用\u201d，不能只停留在\u201c知道这样用\u201d

图片上只能出现≤{_mc}个中文字！
以下信息仅供理解知识点，图片上只需展示：
  - 标题(≤{_mpb}中文字)
  - 1个✓正确例句 vs 1个✗错误例句（用英文写例句）
  - 口诀(≤{min(_mpb+2, 8)}中文字，必须有巧妙联想)
  - 其余全部用图形/箭头/色块/图标表达！"""

new = """⚠️⚠️⚠️ 极重要提醒：英语卡片质量铁律！
🔒1. 单卡只讲一个知识点！标题必须精确(如\u201cpay attention to搭配\u201d)，禁止泛化标题如\u201c高频词\u201d\u201c重点语法\u201d
🔒2. 知识点准确性第一！不能把正确用法标为❌！每个❌/✅必须反复检查
🔒3. 必须有完整例句对比(不能只放孤立短语)：❌错句 vs ✅正句，例句必须是完整英语句子
🔒4. 所有英文单词必须是真实存在的词！严禁编造不存在的词(如guestioneful)
🔒5. 错因必须具体(如\u201cto后接动词原形\u201d)，禁止\u201c词性错\u201d\u201c搭配错\u201d等笼统说法
🔒6. 口诀必须有记忆粘性，禁止\u201c搭配固定\u201d\u201c多练就会\u201d\u201c记住就好\u201d类废话！
🔒7. 所有Steps必须围绕同一个知识点展开，步骤间逻辑连贯递进
🔒8. 视觉隐喻必须匹配内容逻辑(不用阶梯图表示非递进关系)
🔒9. 学生看完必须能答\u201c为什么这样用\u201d，不能只停留在\u201c知道这样用\u201d

图片上只能出现≤{_mc}个中文字！
以下信息仅供理解知识点，图片上只需展示：
  - 标题(≤{_mpb}中文字，必须精确到具体知识点)
  - 1个✓正确例句 vs 1个✗错误例句（用英文写完整句子）
  - 口诀(≤{min(_mpb+2, 8)}中文字，必须有巧妙联想)
  - 其余全部用图形/箭头/色块/图标表达！"""

if old in content:
    content = content.replace(old, new, 1)
    with open('generate_card_images_v3.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK: replaced')
else:
    print('ERROR: old text not found')
    # Try to diagnose
    for line in old.split('\n'):
        if line in content:
            print(f'  FOUND: {line[:60]}')
        else:
            print(f'  MISS:  {line[:60]}')
