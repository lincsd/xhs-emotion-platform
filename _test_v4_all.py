"""测试全部7项优化"""
import re

print("=" * 60)
print("测试 FIX 1+3: 智能截断 + 口诀独立预算")
print("=" * 60)

from generate_card_images_v3 import (
    _trim_to_n_chinese, _ensure_complete_chinese,
    _enforce_manifest_limits, _count_chinese_chars,
    _fix_english_card_title_manifest,
)

# 测试智能截断
assert _trim_to_n_chinese("搭配固定要记住", 4) == "搭配固定"  # "要"被智能去掉
assert _trim_to_n_chinese("注意用to", 4) == "注意用to"  # 未超限
assert _trim_to_n_chinese("搭配用to好", 3) == "搭配用to"  # 正常截断
print(f'  ✅ _trim_to_n_chinese("搭配固定要记住", 4) = "{_trim_to_n_chinese("搭配固定要记住", 4)}"')
print(f'  ✅ _trim_to_n_chinese("注意用to", 4) = "{_trim_to_n_chinese("注意用to", 4)}"')

# 测试 _ensure_complete_chinese
assert _ensure_complete_chinese("搭配固定要") == "搭配固定"
assert _ensure_complete_chinese("注意用") == "注意"  # "用"是虚助词
assert _ensure_complete_chinese("搭配用") == "搭配"
assert _ensure_complete_chinese("注意搭配") == "注意搭配"  # "配"不是虚词
print(f'  ✅ _ensure_complete_chinese("搭配固定要") = "{_ensure_complete_chinese("搭配固定要")}"')
print(f'  ✅ _ensure_complete_chinese("注意搭配") = "{_ensure_complete_chinese("注意搭配")}"')

# 测试口诀独立预算
manifest = {
    'TITLE': '注意搭配',
    'LINE1': '看这里',
    'SLOGAN': '搭配固定要记住',
    'LINE2': '固定搭配',
}
result = _enforce_manifest_limits(manifest, max_total=20, max_per_block=4)
print(f'  口诀预算测试:')
for k, v in result.items():
    cn = _count_chinese_chars(v)
    tag = 'SLOGAN' if 'SLOGAN' in k else ''
    print(f'    {k}: "{v}" ({cn}字) {tag}')
# SLOGAN 应该允许最多6字而非4字
slogan_cn = _count_chinese_chars(result.get('SLOGAN', ''))
assert slogan_cn <= 6, f'SLOGAN应≤6字, 实际{slogan_cn}字'
print(f'  ✅ SLOGAN 预算: {slogan_cn}字 (限额6字)')

print()
print("=" * 60)
print("测试 FIX 2: 英语卡标题注入英文关键词")
print("=" * 60)

card1 = {'title': '注意搭配', 'definition': 'pay attention to'}
m1 = {'TITLE': '注意搭配', 'LINE1': '看这里'}
m1_fixed = _fix_english_card_title_manifest(m1.copy(), card1, '英语')
print(f'  标题: "{m1["TITLE"]}" → "{m1_fixed["TITLE"]}"')
assert 'attention' in m1_fixed['TITLE'].lower() or 'pay' in m1_fixed['TITLE'].lower(), \
    "标题应包含英文关键词"
print(f'  ✅ 注入成功')

# 已有英文的不动
card2 = {'title': 'pay attention to搭配', 'definition': 'pay attention to'}
m2 = {'TITLE': 'pay attention to', 'LINE1': '看这里'}
m2_fixed = _fix_english_card_title_manifest(m2.copy(), card2, '英语')
assert m2_fixed['TITLE'] == 'pay attention to', "已有英文的不应修改"
print(f'  ✅ 已有英文的不动: "{m2_fixed["TITLE"]}"')

# 非英语科不动
m3 = {'TITLE': '注意搭配'}
m3_fixed = _fix_english_card_title_manifest(m3.copy(), card1, '数学')
assert m3_fixed['TITLE'] == '注意搭配', "非英语科不应修改"
print(f'  ✅ 非英语科不动')

print()
print("=" * 60)
print("测试 FIX 6: card_review Rule 13 口诀完整性")
print("=" * 60)

from card_review import validate_hard_rules

# 截断口诀
card_bad_tip = {
    'title': 'pay attention to搭配',
    'definition': 'pay attention to + noun/gerund',
    'memory_tip': '搭配固定要',
    'example': {
        'steps': ['You should pay attention to the details in the exam.', 
                  'He paid attention on the wrong thing → He paid attention to the right thing.'],
        'answer': 'to'
    },
    'mistakes': [{'wrong': 'pay attention on', 'correct': 'pay attention to', 'reason': '固定搭配用to不用on'}]
}
r1 = validate_hard_rules(card_bad_tip, '英语')
tip_issue = [i for i in r1['issues'] if '口诀' in i and '截断' in i]
print(f'  截断口诀"搭配固定要": {tip_issue}')
assert len(tip_issue) > 0, "应检测到口诀截断"
print(f'  ✅ 截断检测成功')

# 好口诀
card_good_tip = card_bad_tip.copy()
card_good_tip['memory_tip'] = '搭配用to'
r2 = validate_hard_rules(card_good_tip, '英语')
tip_issue2 = [i for i in r2['issues'] if '口诀' in i and '截断' in i]
print(f'  好口诀"搭配用to": pass={r2["pass"]}, 截断问题={tip_issue2}')
assert len(tip_issue2) == 0, "好口诀不应报截断"
print(f'  ✅ 好口诀通过')

# 无意义口诀
card_useless = card_bad_tip.copy()
card_useless['memory_tip'] = '多练就会'
r3 = validate_hard_rules(card_useless, '英语')
useless_issue = [i for i in r3['issues'] if '笼统' in i]
print(f'  无意义口诀"多练就会": {useless_issue}')
assert len(useless_issue) > 0, "应检测到无意义口诀"
print(f'  ✅ 无意义检测成功')

print()
print("=" * 60)
print("测试 FIX 7: 铁律精简")
print("=" * 60)

from generate_card_images_v3 import _build_card_info_grammar
info = _build_card_info_grammar(card_good_tip, '英语', '初一', '下册')
rule_count = len(re.findall(r'🔒\d+\.', info))
print(f'  铁律数量: {rule_count}条')
assert rule_count == 10, f"应为10条铁律, 实际{rule_count}"
assert '拆词' in info, "应包含禁拆词规则"
assert '截断废字' in info, "应包含禁截断规则"
print(f'  ✅ 10条精简铁律')

print()
print("=" * 60)
print("测试 FIX 4+5: OCR/质量评分 prompt 内容")
print("=" * 60)

from generate_card_images_v3 import OCR_AUDIT_PROMPT, QUALITY_PROMPT
assert '截断废字' in OCR_AUDIT_PROMPT, "OCR prompt 应包含截断检测"
assert 'truncated' in OCR_AUDIT_PROMPT, "OCR prompt 应有 truncated type"
print(f'  ✅ OCR 审计 prompt 包含截断废字检测')

assert '截断废字' in QUALITY_PROMPT, "质量 prompt 应包含截断扣分"
assert '扣15分' in QUALITY_PROMPT, "质量 prompt 应有扣分规则"
print(f'  ✅ 质量评分 prompt 包含截断扣分')

print()
print("🎉 全部 7 项优化测试通过！")
