"""测试浅层步骤检测 + card_review 新规则"""
import sys, json

# 测试1: 浅层步骤检测函数
print("=" * 50)
print("测试1: _detect_shallow_steps")
print("=" * 50)

from generate_card_images_v3 import _detect_shallow_steps

# 浅层卡 (拆词式)
shallow_card = {
    'title': '注意搭配',
    'definition': 'pay attention to',
    'example': {
        'steps': [
            'attention',
            'pay → attention, Pay attention is a fixed phrase.',
            'pay attention to'
        ],
        'answer': 'pay; to'
    }
}

is_shallow, reason = _detect_shallow_steps(shallow_card)
print(f"拆词卡: is_shallow={is_shallow}, reason={reason}")
assert is_shallow, "应该检测为浅层!"

# 好卡 (有完整句子)
good_card = {
    'title': 'pay attention to搭配',
    'definition': 'pay attention to + noun/gerund',
    'example': {
        'steps': [
            'You should pay attention to the details in the exam.',
            'He paid attention on the wrong thing. → He paid attention to the right thing.',
            'Why: "to" means direction toward an object, "on" is wrong collocation'
        ],
        'answer': 'to'
    }
}

is_shallow2, reason2 = _detect_shallow_steps(good_card)
print(f"好卡: is_shallow={is_shallow2}, reason={reason2}")
assert not is_shallow2, "好卡不应检测为浅层!"

print("\n✅ _detect_shallow_steps 测试通过")

# 测试2: card_review 新规则12
print("\n" + "=" * 50)
print("测试2: card_review Rule 12 (步骤教学深度)")
print("=" * 50)

from card_review import validate_hard_rules

# 浅层卡
result = validate_hard_rules(shallow_card, '英语')
print(f"浅层卡: pass={result['pass']}")
for iss in result['issues']:
    print(f"  - {iss}")

has_depth_issue = any('步骤内容过浅' in i for i in result['issues'])
print(f"  检测到步骤深度问题: {has_depth_issue}")
assert has_depth_issue, "应该报步骤过浅!"

# 好卡
result2 = validate_hard_rules(good_card, '英语')
print(f"好卡: pass={result2['pass']}")
for iss in result2['issues']:
    print(f"  - {iss}")

has_depth_issue2 = any('步骤内容过浅' in i for i in result2['issues'])
print(f"  检测到步骤深度问题: {has_depth_issue2}")
assert not has_depth_issue2, "好卡不应报步骤过浅!"

print("\n✅ Rule 12 测试通过")

# 测试3: _build_card_info_grammar 输出包含 depth_override
print("\n" + "=" * 50)
print("测试3: _build_card_info_grammar 深度覆盖指令")
print("=" * 50)

from generate_card_images_v3 import _build_card_info_grammar

info = _build_card_info_grammar(shallow_card, '英语', '初一', '下册')
has_override = '拆词' in info or '浅薄' in info or '重新设计' in info
print(f"浅层卡 prompt 中包含深度覆盖指令: {has_override}")
if has_override:
    # 找到关键行
    for line in info.split('\n'):
        if '拆词' in line or '浅薄' in line or '重新设计' in line or '禁止' in line:
            print(f"  >> {line.strip()[:80]}")

info2 = _build_card_info_grammar(good_card, '英语', '初一', '下册')
has_override2 = '拆词' in info2 or '浅薄' in info2 or '重新设计' in info2
print(f"好卡 prompt 中包含深度覆盖指令: {has_override2}")

print("\n✅ 全部测试完成!")
