"""
全面优化补丁 v4: 7项修复
=========================
P0:
  1. 口诀截断 → 智能截断 + 口诀独立预算
  2. 标题泛化 → 英语卡自动注入英文关键词到 TITLE manifest
  3. Manifest 守门员截断制造乱码 → 中文完整性校验

P1:
  4. OCR审计不检查语义完整性 → 审计 prompt 增加截断废字检测
  5. 质量评分过宽 → 增加截断/不完整扣分维度
  6. card_review Rule13 → 口诀完整性检测
  7. 铁律精简 → 15条合并为10条核心规则
"""
import re

FILE_V3 = 'generate_card_images_v3.py'
FILE_CR = 'card_review.py'

with open(FILE_V3, 'r', encoding='utf-8') as f:
    v3 = f.read()

with open(FILE_CR, 'r', encoding='utf-8') as f:
    cr = f.read()

ok_count = 0
fail_count = 0

def patch(code, old, new, label):
    global ok_count, fail_count
    if old in code:
        code = code.replace(old, new, 1)
        print(f'  [OK] {label}')
        ok_count += 1
    else:
        print(f'  [FAIL] {label}')
        fail_count += 1
    return code


# ============================================================
# FIX 1+3: 智能截断 + 口诀独立预算
# 替换 _trim_to_n_chinese + _enforce_manifest_limits
# ============================================================
print('=== FIX 1+3: 智能截断 + 口诀独立预算 ===')

old_trim = '''def _trim_to_n_chinese(text, n):
    """截断文本保留前n个中文字符（保留非中文字符）"""
    result = []
    cn_count = 0
    for c in text:
        if '\\u4e00' <= c <= '\\u9fff':
            cn_count += 1
            if cn_count > n:
                break
        result.append(c)
    return ''.join(result).rstrip()'''

new_trim = '''def _trim_to_n_chinese(text, n):
    """智能截断：保留前n个中文字（保留非中文字符），确保不以虚词/助词半截结尾"""
    result = []
    cn_count = 0
    for c in text:
        if '\\u4e00' <= c <= '\\u9fff':
            cn_count += 1
            if cn_count > n:
                break
        result.append(c)
    trimmed = ''.join(result).rstrip()
    # 如果截断了，检查末尾是否完整
    if len(trimmed) < len(text):
        trimmed = _ensure_complete_chinese(trimmed)
    return trimmed


# 常见的中文"废尾"——如果口诀以这些字结尾，说明被截断了
_DANGLING_ENDINGS = set('要的了地得在是和与用把被让给往到从向对着过将')

def _ensure_complete_chinese(text):
    """确保中文文字块不以虚词/助词结尾（说明被截断）"""
    if not text:
        return text
    last_char = text[-1]
    if last_char in _DANGLING_ENDINGS:
        # 去掉最后的虚词
        return text[:-1].rstrip()
    return text'''

v3 = patch(v3, old_trim, new_trim, '智能截断 _trim_to_n_chinese + _ensure_complete_chinese')


# 在 _enforce_manifest_limits 中给口诀独立预算
# 找到 "优先保留 TITLE" 注释块，在其前面增加 SLOGAN 特殊处理
old_enforce_title = """    result = {}
    budget = max_total
    
    # 优先保留 TITLE
    for k, v in manifest.items():
        if 'TITLE' in k.upper():
            trimmed_v = _trim_to_n_chinese(v, min(max_per_block, budget))
            result[k] = trimmed_v
            budget -= _count_chinese_chars(trimmed_v)
            break
    
    # 其余按顺序，每块限max_per_block且总量不超budget
    for k, v in manifest.items():
        if k in result:
            continue
        if budget <= 0:
            print(f'      [manifest guard] 丢弃 {k}: "{v}" (预算用完)')
            continue
        alloc = min(max_per_block, budget)
        cn_count = _count_chinese_chars(v)
        if cn_count == 0:
            result[k] = v  # 纯数字/符号，保留
        elif cn_count <= alloc:
            result[k] = v
            budget -= cn_count
        else:
            trimmed_v = _trim_to_n_chinese(v, alloc)
            print(f'      [manifest guard] {k}: "{v}" → "{trimmed_v}"')
            result[k] = trimmed_v
            budget -= _count_chinese_chars(trimmed_v)"""

new_enforce_title = """    result = {}
    budget = max_total
    max_slogan = min(max_per_block + 2, 8)  # 口诀独立预算，比普通块多2字
    
    # 优先保留 TITLE
    for k, v in manifest.items():
        if 'TITLE' in k.upper():
            trimmed_v = _trim_to_n_chinese(v, min(max_per_block, budget))
            result[k] = trimmed_v
            budget -= _count_chinese_chars(trimmed_v)
            break
    
    # 其余按顺序，口诀给独立预算
    for k, v in manifest.items():
        if k in result:
            continue
        if budget <= 0:
            print(f'      [manifest guard] 丢弃 {k}: "{v}" (预算用完)')
            continue
        # 口诀/SLOGAN 类字段给更大预算
        is_slogan = any(s in k.upper() for s in ('SLOGAN', '口诀', 'TIP', 'MOTTO'))
        alloc = min(max_slogan if is_slogan else max_per_block, budget)
        cn_count = _count_chinese_chars(v)
        if cn_count == 0:
            result[k] = v  # 纯数字/符号，保留
        elif cn_count <= alloc:
            result[k] = v
            budget -= cn_count
        else:
            trimmed_v = _trim_to_n_chinese(v, alloc)
            print(f'      [manifest guard] {k}: "{v}" → "{trimmed_v}"')
            result[k] = trimmed_v
            budget -= _count_chinese_chars(trimmed_v)"""

v3 = patch(v3, old_enforce_title, new_enforce_title, '口诀独立预算 + manifest guard')


# ============================================================
# FIX 2: 英语卡标题自动注入英文关键词
# 在 _parse_text_manifest 后面加一个 _fix_english_card_manifest
# ============================================================
print('\n=== FIX 2: 英语卡标题自动注入英文关键词 ===')

old_parse_end = '''def _parse_text_manifest(text):
    """从 prompt 输出中解析 TEXT_MANIFEST"""
    manifest = {}
    m = re.search(r'\\[TEXT_MANIFEST\\](.*?)\\[/TEXT_MANIFEST\\]', text, re.DOTALL)
    if m:
        for line in m.group(1).strip().split('\\n'):
            line = line.strip()
            if ':' in line:
                key, val = line.split(':', 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if val:
                    manifest[key] = val
    return manifest'''

new_parse_end = '''def _parse_text_manifest(text):
    """从 prompt 输出中解析 TEXT_MANIFEST"""
    manifest = {}
    m = re.search(r'\\[TEXT_MANIFEST\\](.*?)\\[/TEXT_MANIFEST\\]', text, re.DOTALL)
    if m:
        for line in m.group(1).strip().split('\\n'):
            line = line.strip()
            if ':' in line:
                key, val = line.split(':', 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if val:
                    manifest[key] = val
    return manifest


def _fix_english_card_title_manifest(manifest, card, subject):
    """英语卡标题优化: 如果 TITLE 是纯中文泛化标题，自动拼入英文关键短语"""
    if subject != '英语' and subject != 'english':
        return manifest
    
    title_key = None
    title_val = None
    for k, v in manifest.items():
        if 'TITLE' in k.upper():
            title_key = k
            title_val = v
            break
    
    if not title_key or not title_val:
        return manifest
    
    # 检查: TITLE 是否有英文
    has_eng = bool(re.search(r'[a-zA-Z]', title_val))
    if has_eng:
        return manifest  # 已经有英文了，不动
    
    # 从 definition 中提取英文关键短语
    definition = card.get('definition', '')
    eng_phrase = ''
    # 尝试提取完整短语 (如 "pay attention to")
    eng_words = re.findall(r'[a-zA-Z][a-zA-Z\\s]{2,}', definition)
    if eng_words:
        # 取最长的英文片段
        eng_phrase = max(eng_words, key=len).strip()[:25]
    
    if not eng_phrase:
        # 从 title 尝试
        title_full = card.get('title', '')
        eng_words = re.findall(r'[a-zA-Z][a-zA-Z\\s]{2,}', title_full)
        if eng_words:
            eng_phrase = max(eng_words, key=len).strip()[:25]
    
    if eng_phrase:
        # 中文标题保留前2字 + 英文关键词
        cn_chars = re.findall(r'[\\u4e00-\\u9fff]', title_val)
        cn_prefix = ''.join(cn_chars[:2]) if cn_chars else title_val[:2]
        manifest[title_key] = f'{cn_prefix}{eng_phrase}'
        print(f'      [title fix] "{title_val}" → "{manifest[title_key]}"')
    
    return manifest'''

v3 = patch(v3, old_parse_end, new_parse_end, '英语卡标题 _fix_english_card_title_manifest')

# 在 generate_image_prompt 中调用 _fix_english_card_title_manifest
# 在 manifest = _parse_text_manifest(best_text) 之后
old_manifest_parse = """        # 解析 TEXT_MANIFEST
        manifest = _parse_text_manifest(best_text)
        # 清理 prompt（移除 manifest 标签）
        prompt_clean = re.sub(r'\\[TEXT_MANIFEST\\].*?\\[/TEXT_MANIFEST\\]', '', best_text, flags=re.DOTALL).strip()"""

new_manifest_parse = """        # 解析 TEXT_MANIFEST
        manifest = _parse_text_manifest(best_text)
        # 英语卡标题优化: 自动注入英文关键词
        manifest = _fix_english_card_title_manifest(manifest, card, subject)
        # 清理 prompt（移除 manifest 标签）
        prompt_clean = re.sub(r'\\[TEXT_MANIFEST\\].*?\\[/TEXT_MANIFEST\\]', '', best_text, flags=re.DOTALL).strip()"""

v3 = patch(v3, old_manifest_parse, new_manifest_parse, '调用 _fix_english_card_title_manifest')


# ============================================================
# FIX 4: OCR 审计增加中文语义完整性检查
# ============================================================
print('\n=== FIX 4: OCR 审计增加截断废字检测 ===')

old_ocr_scoring = """评分标准(0-100)：
- 100: 所有中文完美无误
- 80+: 有轻微瑕疵但可读
- 60-79: 有明显错字但整体可理解
- <60: 严重乱码，需要重新生成

只输出JSON，不要其他文字。\""""

new_ocr_scoring = """评分标准(0-100)：
- 100: 所有中文完美无误
- 80+: 有轻微瑕疵但可读
- 60-79: 有明显错字但整体可理解
- <60: 严重乱码，需要重新生成

⚠️ 特别检查：截断废字
- 检查每个中文文字块是否是**完整**的词或短句
- 如果某个文字块以虚词/助词结尾(如"搭配固定要""注意到""记住就")明显是被截断了 → 标记为 type:"truncated", severity:"high"
- 截断废字每发现一处扣10分

只输出JSON，不要其他文字。\""""

v3 = patch(v3, old_ocr_scoring, new_ocr_scoring, 'OCR 审计增加截断废字检测')


# ============================================================
# FIX 5: 质量评分增加截断扣分维度
# ============================================================
print('\n=== FIX 5: 质量评分增加截断/完整性维度 ===')

old_quality = '''QUALITY_PROMPT = """你是知识卡片质量评审员。请从5个维度评分(每项0-20分，满分100)：

1. **教学清晰度**(20分): 例题清晰? 解题步骤直观? 一眼就懂?
2. **文字准确性**(20分): 中文无乱码无错字? 数字公式正确?
3. **视觉美感**(20分): 配色好看? 像小红书爆款? 有吸引力?
4. **布局合理性**(20分): 信息层次清晰? 留白充足? 不拥挤?
5. **可收藏感**(20分): 看到就想截图保存? 有"干货感"?

只输出JSON格式（不要代码块标记）：
{{"teaching": 16, "text_accuracy": 18, "visual": 17, "layout": 15, "saveable": 16, "total": 82, "comment": "一句话点评"}}'''

new_quality = '''QUALITY_PROMPT = """你是知识卡片质量评审员。请从5个维度评分(每项0-20分，满分100)：

1. **教学清晰度**(20分): 例题清晰? 解题步骤直观? 一眼就懂? (英语卡: 有完整例句+易错对比+本质原因?)
2. **文字准确性**(20分): 中文无乱码无错字? 数字公式正确? ⚠️截断废字(如"搭配固定要""注意到")直接扣15分!
3. **视觉美感**(20分): 配色好看? 像小红书爆款? 有吸引力?
4. **布局合理性**(20分): 信息层次清晰? 留白充足? 不拥挤?
5. **可收藏感**(20分): 看到就想截图保存? 有"干货感"? 口诀是否完整有意义(截断废话扣10分)?

只输出JSON格式（不要代码块标记）：
{{"teaching": 16, "text_accuracy": 18, "visual": 17, "layout": 15, "saveable": 16, "total": 82, "comment": "一句话点评"}}'''

v3 = patch(v3, old_quality, new_quality, '质量评分增加截断扣分')


# ============================================================
# FIX 7: 铁律精简 15条→10条核心规则
# ============================================================
print('\n=== FIX 7: 铁律精简合并 ===')

old_rules = """⚠️⚠️⚠️ 极重要提醒：英语卡片质量铁律！
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
🔒12. 所有中文文字必须是完整的词/短句，禁止截断（如"搭配固"就是截断废字）
🔒13. 🚫严禁"拆词式"步骤！不能把短语拆成单词当步骤(如 attention→pay attention→pay attention to 是废话)
🔒14. 每个步骤必须包含至少一个完整英文例句(≥5词)，展示知识点在真实语境中的用法
🔒15. 学生看完必须能回答"这个词/短语怎么在句子里用"+"常见错误是什么"+"为什么错"三个问题"""

new_rules = """⚠️⚠️⚠️ 英语卡片10条铁律（违反任何一条=废卡重做）！
🔒1. 单卡只讲「{topic_phrase}」一个知识点！标题必须含英文关键词，禁止"高频词""搭配活用"等泛化标题
🔒2. 知识点准确性第一！❌/✅必须反复核对，不能把正确用法标错！所有单词必须真实存在！
🔒3. 必须有完整英文例句对比：❌错句(≥5词) vs ✅正句(≥5词)，禁止孤立短语/单词当步骤！
🔒4. 🚫严禁"拆词式"步骤（如 attention→pay attention→pay attention to 是废话），每步必须展示真实语境用法
🔒5. 错因必须具体(如"to后接动词原形")，学生看完能答"为什么这样用"，禁止"词性错""搭配错"等笼统说法
🔒6. 口诀必须是完整有意义的短句(如"to后加原形"，≤6字)，🚫严禁截断废字（"搭配固定要""搭配固""记住就"都是废话）！
🔒7. 🚫严禁添加任何与「{topic_phrase}」无关的公式/规则/知识点！图片底部只总结本卡结论！
🔒8. 所有中文文字必须是完整的词/短句，禁止截断！每个中文字笔画清晰粗体加大！
🔒9. 视觉隐喻必须匹配内容逻辑，布局清晰不拥挤，≥25%留白
🔒10. 学生看完必须能回答三个问题: ①怎么在句子里用 ②常见错误是什么 ③为什么错"""

v3 = patch(v3, old_rules, new_rules, '铁律 15→10 精简合并')


# ============================================================
# FIX 6: card_review.py Rule 13 口诀完整性检测
# ============================================================
print('\n=== FIX 6: card_review Rule 13 口诀完整性 ===')

old_cr_return = """    # ── 规则 12: 步骤教学深度检测 (英语卡，防止拆词式浅层内容) ──
    if is_eng:
        steps = card.get('example', {}).get('steps', [])
        if len(steps) >= 2:
            short_step_count = 0
            for s in steps:
                s_str = str(s).strip()
                eng_words = re.findall(r'[a-zA-Z]+', s_str)
                cn_chars = len(re.findall(r'[\\u4e00-\\u9fff]', s_str))
                # 步骤只有1-3个英文单词且中文极少 → 浅层
                if len(eng_words) <= 3 and cn_chars <= 8:
                    short_step_count += 1
            if short_step_count >= len(steps) * 0.6:
                issues.append(
                    f'步骤内容过浅: {short_step_count}/{len(steps)}步只有孤立单词/短语，'
                    f'缺少完整例句和解释 (禁止把短语拆成单词当步骤)'
                )

    return {
        'pass': len(issues) == 0,
        'issues': issues,
        'stage': 'hard_rule',
    }"""

new_cr_return = """    # ── 规则 12: 步骤教学深度检测 (英语卡，防止拆词式浅层内容) ──
    if is_eng:
        steps = card.get('example', {}).get('steps', [])
        if len(steps) >= 2:
            short_step_count = 0
            for s in steps:
                s_str = str(s).strip()
                eng_words = re.findall(r'[a-zA-Z]+', s_str)
                cn_chars = len(re.findall(r'[\\u4e00-\\u9fff]', s_str))
                # 步骤只有1-3个英文单词且中文极少 → 浅层
                if len(eng_words) <= 3 and cn_chars <= 8:
                    short_step_count += 1
            if short_step_count >= len(steps) * 0.6:
                issues.append(
                    f'步骤内容过浅: {short_step_count}/{len(steps)}步只有孤立单词/短语，'
                    f'缺少完整例句和解释 (禁止把短语拆成单词当步骤)'
                )

    # ── 规则 13: 口诀完整性检测 ──
    memory_tip = card.get('memory_tip', '').strip()
    if memory_tip:
        # 检查是否以虚词/助词结尾(表被截断)
        _DANGLING_TAILS = set('要的了地得在是和与用把被让给往到从向对着过将')
        if memory_tip[-1] in _DANGLING_TAILS and len(memory_tip) <= 8:
            issues.append(
                f'口诀疑似截断: "{memory_tip}" 以虚词"{memory_tip[-1]}"结尾，'
                f'不是完整短句 (如"搭配固定要" → 应改为"搭配用to")'
            )
        # 检查是否太笼统无意义
        _USELESS_SLOGANS = ['多练就会', '记住就好', '背了就行', '牢记即可', '熟能生巧']
        if memory_tip in _USELESS_SLOGANS:
            issues.append(f'口诀"{memory_tip}"过于笼统无意义，需要包含具体知识点')

    return {
        'pass': len(issues) == 0,
        'issues': issues,
        'stage': 'hard_rule',
    }"""

cr = patch(cr, old_cr_return, new_cr_return, 'Rule 13 口诀完整性检测')


# ============================================================
# 写回文件
# ============================================================
print(f'\n=== 写入文件 ===')

with open(FILE_V3, 'w', encoding='utf-8') as f:
    f.write(v3)
print(f'  [OK] {FILE_V3} 已写入')

with open(FILE_CR, 'w', encoding='utf-8') as f:
    f.write(cr)
print(f'  [OK] {FILE_CR} 已写入')


# ============================================================
# 验证
# ============================================================
print(f'\n=== 验证补丁 ===')

with open(FILE_V3, 'r', encoding='utf-8') as f:
    v3_check = f.read()

with open(FILE_CR, 'r', encoding='utf-8') as f:
    cr_check = f.read()

checks = [
    (v3_check, '_ensure_complete_chinese', 'FIX1: 智能截断函数'),
    (v3_check, '_DANGLING_ENDINGS', 'FIX1: 废尾字集'),
    (v3_check, 'is_slogan = any', 'FIX1: 口诀独立预算'),
    (v3_check, '_fix_english_card_title_manifest', 'FIX2: 标题注入函数'),
    (v3_check, '截断废字', 'FIX4: OCR截断检测'),
    (v3_check, '截断废字(如', 'FIX5: 质量评分截断扣分'),
    (v3_check, '10条铁律', 'FIX7: 铁律精简'),
    (cr_check, '规则 13: 口诀完整性检测', 'FIX6: Rule13 口诀检测'),
    (cr_check, '_DANGLING_TAILS', 'FIX6: 废尾字集'),
    (cr_check, '_USELESS_SLOGANS', 'FIX6: 无意义口诀'),
]

all_ok = True
for code, pattern, label in checks:
    if pattern in code:
        print(f'  ✅ {label}')
    else:
        print(f'  ❌ {label}')
        all_ok = False

print(f'\n{"✅" if all_ok else "⚠️"} 结果: {ok_count}成功, {fail_count}失败')
