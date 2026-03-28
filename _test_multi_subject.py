#!/usr/bin/env python3
"""v10.6 多学科支持单元测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_card_images_v3 import (
    _SUBJECT_TERMS_PROTECTED,
    _get_subject_terms,
    _find_subject_terms_in_card,
    _inject_grammar_terms_to_manifest,
    _validate_and_repair_card,
    _build_card_info,
    _build_card_info_yuwen,
    _build_card_info_edu,
    _SUBJECT_EDU_HINTS,
)

passed = 0
failed = 0

def check(name, condition, detail=''):
    global passed, failed
    if condition:
        print(f'  ✓ {name}')
        passed += 1
    else:
        print(f'  ✗ {name} — {detail}')
        failed += 1


print('=== 1. 学科术语保护表 ===')
# 确认所有学科都有术语
for subj in ['英语', '语文', '数学', '物理', '化学', '生物', '历史', '地理', '政治']:
    terms = _get_subject_terms(subj)
    check(f'{subj} 有术语 ({len(terms)}个)', len(terms) >= 10, f'只有{len(terms)}个')

# 确认英语是原来的 _GRAMMAR_TERMS_PROTECTED
check('英语术语包含宾语从句', '宾语从句' in _get_subject_terms('英语'))
check('物理术语包含牛顿第二定律', '牛顿第二定律' in _get_subject_terms('物理'))
check('化学术语包含氧化还原', '氧化还原' in _get_subject_terms('化学'))
check('生物术语包含光合作用', '光合作用' in _get_subject_terms('生物'))
check('历史术语包含辛亥革命', '辛亥革命' in _get_subject_terms('历史'))

print('\n=== 2. 术语查找 ===')
# 物理卡片
physics_card = {
    'title': '欧姆定律',
    'definition': '电流与电压成正比，与电阻成反比',
    'core_points': ['I=U/R, 电流=电压÷电阻', '串联电路电流处处相等', '并联电路电压处处相等'],
}
phys_terms = _find_subject_terms_in_card(physics_card, '物理')
check('物理卡找到术语', len(phys_terms) >= 2, f'只找到{phys_terms}')
check('包含欧姆定律', '欧姆定律' in phys_terms)
check('包含电流', '电流' in phys_terms)

# 语文卡片
yuwen_card = {
    'title': '修辞手法——比喻与拟人',
    'definition': '比喻是用相似的事物来打比方，拟人是把事物当人来写',
    'core_points': ['明喻、暗喻、借喻是比喻的三种类型', '拟人赋予事物人的行为感情'],
}
yw_terms = _find_subject_terms_in_card(yuwen_card, '语文')
check('语文卡找到术语', len(yw_terms) >= 2, f'只找到{yw_terms}')
check('包含比喻', '比喻' in yw_terms)
check('包含拟人', '拟人' in yw_terms)

print('\n=== 3. 术语注入到manifest ===')
# 物理卡: 术语应注入manifest
manifest = {'TITLE': '欧姆定律', 'LINE1': 'I=U/R'}
result = _inject_grammar_terms_to_manifest(manifest.copy(), physics_card, '物理')
check('物理卡注入了术语到manifest', len(result) > len(manifest), f'{len(result)} vs {len(manifest)}')

# 化学卡
chem_card = {
    'title': '氧化还原反应',
    'definition': '化合价升高的物质是还原剂，被氧化',
    'core_points': ['氧化剂+还原剂→氧化产物+还原产物', '化合价升高=失去电子=被氧化'],
}
chem_manifest = {'TITLE': '氧化还原'}
chem_result = _inject_grammar_terms_to_manifest(chem_manifest.copy(), chem_card, '化学')
check('化学卡注入了术语', len(chem_result) > len(chem_manifest))

# 英语卡: 原有逻辑保留（只对概念卡注入）
eng_simple_card = {
    'title': 'pay attention to',
    'definition': '注意某事',
    'core_points': ['Pay attention to your spelling.'],
}
eng_manifest = {'TITLE': 'pay attention to'}
eng_result = _inject_grammar_terms_to_manifest(eng_manifest.copy(), eng_simple_card, '英语')
check('英语非概念卡不注入', len(eng_result) == len(eng_manifest))

print('\n=== 4. 学科校验 ===')
# 语文诗词卡缺少core_points
yw_poetry_card = {
    'title': '古诗默写——春晓',
    'definition': '春眠不觉晓，处处闻啼鸟',
    'core_points': [],
}
ok, _, issues = _validate_and_repair_card(yw_poetry_card, '语文', '小学三年级')
check('语文诗词无core_points有警告', any('core_points' in i for i in issues))

# 废话口诀检测（非英语）
boring_card = {
    'title': '测试',
    'definition': '测试定义',
    'memory_tip': '认真学习',
}
ok, card, issues = _validate_and_repair_card(boring_card, '物理', '初二')
check('废话口诀被清空', card['memory_tip'] == '', f'口诀={card["memory_tip"]}')

print('\n=== 5. 卡片信息构建 ===')
# 语文卡走yuwen路径
yw_info = _build_card_info(yuwen_card, '语文', '初一', '上')
check('语文卡信息包含学科标记', '语文' in yw_info)
check('语文卡信息包含修辞标记', '修辞' in yw_info or '比喻' in yw_info)

# 物理卡走edu路径，有专属提示
phys_info = _build_card_info(physics_card, '物理', '初二', '上')
check('物理卡信息包含学科标记', '物理' in phys_info)
check('物理卡包含专属提示', '物理卡片要求' in phys_info)

# 化学卡有专属提示
chem_info = _build_card_info(chem_card, '化学', '高一', '上')
check('化学卡包含专属提示', '化学卡片要求' in chem_info)

# 数学卡（原有路径不变）
math_card = {
    'title': '一元一次方程',
    'definition': 'ax+b=0 形式的方程',
    'core_points': ['移项变号', '合并同类项'],
}
math_info = _build_card_info(math_card, '数学', '初一', '上')
check('数学卡走通用edu路径', '数学' in math_info)

print('\n=== 6. 专属提示覆盖 ===')
for subj in ['物理', '化学', '生物', '历史', '地理', '政治']:
    check(f'{subj} 有专属提示', subj in _SUBJECT_EDU_HINTS)

print(f'\n{"="*50}')
print(f'  v10.6 多学科测试: {passed} passed, {failed} failed')
print(f'{"="*50}')
sys.exit(0 if failed == 0 else 1)
