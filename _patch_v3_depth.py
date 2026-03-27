"""
Patch: 加入浅层内容检测 + 深度教学指令
修改 generate_card_images_v3.py:
1. 新增 _detect_shallow_steps() 检测拆词式步骤
2. _build_card_info_grammar() 注入深度教学覆盖指令
3. 铁律升级: 禁止拆词步骤，要求完整例句
"""
import re

FILE = 'generate_card_images_v3.py'

with open(FILE, 'r', encoding='utf-8') as f:
    code = f.read()

# ============================================================
# 1. 在 _filter_off_topic_steps 之前插入 _detect_shallow_steps
# ============================================================

NEW_FUNC = '''
def _detect_shallow_steps(card):
    """检测步骤是否为'拆词式'浅层内容 (如把 pay attention to 拆成三步: attention / pay->attention / pay attention to)
    
    返回: (is_shallow: bool, reason: str)
    """
    import re as _re
    steps = (card.get('example') or {}).get('steps', [])
    if not steps:
        return False, ''
    
    definition = card.get('definition', '').lower().strip()
    title = card.get('title', '').lower().strip()
    
    # 检测1: 步骤是否只是逐词拆解短语
    # 如果大部分步骤只有1-2个英文单词(无解释句子)，就是拆词
    short_step_count = 0
    for s in steps:
        s_str = str(s).strip()
        # 去掉箭头等符号后，看纯英文单词数
        eng_words = _re.findall(r'[a-zA-Z]+', s_str)
        # 如果中文字符极少(<=8)且英文单词<=3，视为浅层步骤
        cn_chars = len(_re.findall(r'[\\u4e00-\\u9fff]', s_str))
        if len(eng_words) <= 3 and cn_chars <= 8:
            short_step_count += 1
    
    if len(steps) >= 2 and short_step_count >= len(steps) * 0.6:
        return True, f'{short_step_count}/{len(steps)}步是孤立短语/单词，缺少完整例句和解释'
    
    # 检测2: 步骤是否包含完整英文句子(至少有主谓结构，>=5个词)
    has_sentence = False
    for s in steps:
        eng_words = _re.findall(r'[a-zA-Z]+', str(s))
        if len(eng_words) >= 5:
            has_sentence = True
            break
    
    if not has_sentence and len(steps) >= 2:
        return True, '所有步骤都没有完整英文例句，缺乏教学深度'
    
    return False, ''


'''

# 在 def _filter_off_topic_steps 之前插入
anchor = 'def _filter_off_topic_steps(card):'
if anchor in code:
    code = code.replace(anchor, NEW_FUNC + anchor, 1)
    print('[OK] _detect_shallow_steps 已插入')
else:
    print('[WARN] 未找到 _filter_off_topic_steps 锚点')


# ============================================================
# 2. 在 _build_card_info_grammar 中加入浅层检测 + 深度教学覆盖
# ============================================================

# 找到 _build_card_info_grammar 函数中构建 return 的部分
# 在 topic_phrase 赋值之后、return f""" 之前，插入浅层检测逻辑

# 先找 topic_phrase 行
old_topic_line = "topic_phrase = card.get('definition', '')[:60] or card.get('title', '')"
new_topic_block = """topic_phrase = card.get('definition', '')[:60] or card.get('title', '')

    # ── 浅层内容检测: 识别拆词式步骤并生成深度教学覆盖指令 ──
    is_shallow, shallow_reason = _detect_shallow_steps(card)
    depth_override = ''
    if is_shallow:
        depth_override = f\"\"\"

\\u2757\\u2757\\u2757 \\u6781\\u91cd\\u8981\\uff01\\u5361\\u7247\\u6570\\u636e\\u7684\\u6b65\\u9aa4\\u8fc7\\u4e8e\\u6d45\\u8584: {shallow_reason}
\\u4f60\\u5fc5\\u987b\\u5b8c\\u5168\\u91cd\\u65b0\\u8bbe\\u8ba1\\u6559\\u5b66\\u5185\\u5bb9\\uff0c\\u800c\\u4e0d\\u662f\\u7167\\u642c\\u4e0a\\u9762\\u7684\\u6b65\\u9aa4\\uff01

\\u6b63\\u786e\\u7684\\u82f1\\u8bed\\u5361\\u7247\\u5e94\\u8be5\\u8fd9\\u6837\\u8bbe\\u8ba1:
\\u2460 \\u5b8c\\u6574\\u4f8b\\u53e5\\u5c55\\u793a\\u7528\\u6cd5: \\u5199\\u4e00\\u4e2a\\u5b8c\\u6574\\u82f1\\u6587\\u53e5\\u5b50\\uff0c\\u591a\\u5173\\u952e\\u8bcd\\u7c97\\u4f53\\u9ad8\\u4eae
\\u2461 \\u6613\\u9519\\u5bf9\\u6bd4(\\u5b8c\\u6574\\u53e5): \\u2716 \\u9519\\u8bef\\u53e5\\u5b50 vs \\u2714 \\u6b63\\u786e\\u53e5\\u5b50\\uff0c\\u5fc5\\u987b\\u662f\\u5b8c\\u6574\\u82f1\\u6587\\u53e5
\\u2462 \\u89e3\\u91ca\\u201c\\u4e3a\\u4ec0\\u4e48\\u201d: \\u7528\\u7b80\\u77ed\\u4e2d\\u6587(\\u22644\\u5b57)\\u89e3\\u91ca\\u8bed\\u6cd5\\u89c4\\u5219\\u7684\\u672c\\u8d28\\u539f\\u56e0

\\u7edd\\u5bf9\\u7981\\u6b62:
- \\u628a\\u77ed\\u8bed\\u62c6\\u6210\\u5355\\u8bcd\\u5f53\\u6b65\\u9aa4(\\u5982: attention \\u2192 pay attention \\u2192 pay attention to)
- \\u6b65\\u9aa4\\u53ea\\u6709\\u5b64\\u7acb\\u5355\\u8bcd/\\u77ed\\u8bed\\uff0c\\u6ca1\\u6709\\u5b8c\\u6574\\u53e5\\u5b50
- \\u201c\\u62fc\\u4e50\\u9ad8\\u5f0f\\u201d\\u9010\\u8bcd\\u7ec4\\u88c5\\u2014\\u2014\\u8fd9\\u4e0d\\u662f\\u6559\\u5b66\\uff0c\\u8fd9\\u662f\\u5e9f\\u8bdd
\"\"\"
"""

if old_topic_line in code:
    code = code.replace(old_topic_line, new_topic_block, 1)
    print('[OK] 浅层检测逻辑已插入 _build_card_info_grammar')
else:
    print('[WARN] 未找到 topic_phrase 锚点')


# ============================================================
# 3. 在 return f""" 块中注入 depth_override
# ============================================================

# 找到铁律12之后的检查清单之前，插入 depth_override 变量引用
# 实际上最好在检查清单之后、return 块末尾的信息区之前注入

# 安全方式: 在 return 块中找到 "图片上只能出现" 这行，在其前面注入
old_line = '图片上只能出现'
# 需要更精确的锚点
old_anchor = '□ 口诀是否是完整且有意义的中文短句？\n'
new_anchor = '□ 口诀是否是完整且有意义的中文短句？\n{depth_override}\n'

if old_anchor in code:
    code = code.replace(old_anchor, new_anchor, 1)
    print('[OK] depth_override 注入点已设置')
else:
    print('[WARN] 未找到检查清单锚点，尝试备用')
    # 备用: 在 "图片上只能出现" 行前面插入
    alt_anchor = '\n图片上只能出现'
    alt_new = '\n{depth_override}\n图片上只能出现'
    if alt_anchor in code:
        code = code.replace(alt_anchor, alt_new, 1)
        print('[OK] 备用注入点已设置')


# ============================================================
# 4. 升级铁律: 在 12条之后追加 13-15
# ============================================================

old_rule12 = '🔒12. 所有中文文字必须是完整的词/短句，禁止截断（如"搭配固"就是截断废字）'
new_rules = '''🔒12. 所有中文文字必须是完整的词/短句，禁止截断（如"搭配固"就是截断废字）
🔒13. 🚫严禁"拆词式"步骤！不能把短语拆成单词当步骤(如 attention→pay attention→pay attention to 是废话)
🔒14. 每个步骤必须包含至少一个完整英文例句(≥5词)，展示知识点在真实语境中的用法
🔒15. 学生看完必须能回答"这个词/短语怎么在句子里用"+"常见错误是什么"+"为什么错"三个问题'''

if old_rule12 in code:
    code = code.replace(old_rule12, new_rules, 1)
    print('[OK] 铁律升级到15条')
else:
    print('[WARN] 未找到铁律12')


# ============================================================
# 5. 升级系统 prompt: 增加深度教学要求
# ============================================================

old_depth_req = """⚠️ 深度教学要求：
- 如果有"本质原因"或"错因"信息，必须在视觉中体现（用💡图标+简短文字）
- ❌错误示范不能只标红叉，必须配一句"为什么错"的解释
- 口诀区如有例外情况，用小字标注"""

new_depth_req = """⚠️ 深度教学要求：
- 如果有"本质原因"或"错因"信息，必须在视觉中体现（用💡图标+简短文字）
- ❌错误示范不能只标红叉，必须配一句"为什么错"的解释
- 口诀区如有例外情况，用小字标注
- 🚫 严禁把短语拆成单词当步骤（如"attention → pay attention → pay attention to"是无意义拆词）
- ✅ 每个步骤必须展示知识点在完整句子中的用法 + 为什么这样用
- ✅ 英语卡核心三要素: ①完整例句(粗体关键词) ②易错对比(完整句) ③本质原因(≤4中文字)"""

if old_depth_req in code:
    code = code.replace(old_depth_req, new_depth_req, 1)
    print('[OK] 系统 prompt 深度教学要求已升级')
else:
    print('[WARN] 未找到深度教学要求锚点')


# ============================================================
# 写回文件
# ============================================================
with open(FILE, 'w', encoding='utf-8') as f:
    f.write(code)

print('\n✅ 所有补丁已写入 generate_card_images_v3.py')
print('验证: 搜索关键函数...')

# 验证
with open(FILE, 'r', encoding='utf-8') as f:
    content = f.read()

checks = [
    ('_detect_shallow_steps', 'def _detect_shallow_steps('),
    ('depth_override', 'is_shallow, shallow_reason = _detect_shallow_steps('),
    ('铁律13', '🔒13.'),
    ('铁律14', '🔒14.'),
    ('铁律15', '🔒15.'),
    ('系统prompt深度', '严禁把短语拆成单词当步骤'),
]

all_ok = True
for name, pattern in checks:
    if pattern in content:
        print(f'  ✅ {name}')
    else:
        print(f'  ❌ {name} 未找到!')
        all_ok = False

if all_ok:
    print('\n✅ 全部检查通过！')
else:
    print('\n⚠️ 部分检查失败，请手动检查')
