"""
v10.9 理科卡片类型集成测试
验证 9 个新理科卡片类型在各模块中的注册正确性。
"""
import sys, os, json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ─── 待测卡片类型 ─────────────────────────────────
SCIENCE_CARD_TYPES = [
    '实验卡', '公式推导卡', '过程流卡', '微观图解卡', '图像解读卡',
    '模型卡', '解题策略卡', '知识网络卡', '术语精准卡',
]

EXISTING_TYPES_REUSED = ['对比辨析卡', '易错陷阱卡', '生活应用卡']

passed = 0
failed = 0

def ok(name):
    global passed
    passed += 1
    print(f'  ✅ {name}')

def fail(name, detail=''):
    global failed
    failed += 1
    print(f'  ❌ {name}  {detail}')

# ═══════════════════════════════════════════════════
# 1. skill_schema 注册检查
# ═══════════════════════════════════════════════════
print('\n[1] skill_schema.py — SkillSchema 注册')
from skill_schema import get_skill_schema, _SKILL_REGISTRY
for ct in SCIENCE_CARD_TYPES:
    if get_skill_schema(ct) is not None:
        ok(f'SkillSchema 已注册: {ct}')
    else:
        fail(f'SkillSchema 缺失: {ct}')

# ═══════════════════════════════════════════════════
# 2. CARD_TYPE_VISUAL_RULES 检查
# ═══════════════════════════════════════════════════
print('\n[2] generate_card_images_v3.py — CARD_TYPE_VISUAL_RULES')
from generate_card_images_v3 import CARD_TYPE_VISUAL_RULES
for ct in SCIENCE_CARD_TYPES:
    if ct in CARD_TYPE_VISUAL_RULES:
        ok(f'VISUAL_RULES 已注册: {ct}')
    else:
        fail(f'VISUAL_RULES 缺失: {ct}')

# ═══════════════════════════════════════════════════
# 3. _CARD_TYPE_LAYOUT_MAP 检查
# ═══════════════════════════════════════════════════
print('\n[3] generate_card_images_v3.py — _CARD_TYPE_LAYOUT_MAP')
from generate_card_images_v3 import _CARD_TYPE_LAYOUT_MAP
for ct in SCIENCE_CARD_TYPES:
    if ct in _CARD_TYPE_LAYOUT_MAP:
        ok(f'LAYOUT_MAP 已注册: {ct} → {_CARD_TYPE_LAYOUT_MAP[ct]}')
    else:
        fail(f'LAYOUT_MAP 缺失: {ct}')

# ═══════════════════════════════════════════════════
# 4. _CONTENT_RATIO_MAP 检查
# ═══════════════════════════════════════════════════
print('\n[4] generate_card_images_v3.py — _CONTENT_RATIO_MAP')
from generate_card_images_v3 import _CONTENT_RATIO_MAP
for ct in SCIENCE_CARD_TYPES:
    if ct in _CONTENT_RATIO_MAP:
        ok(f'RATIO_MAP 已注册: {ct} → {_CONTENT_RATIO_MAP[ct]}')
    else:
        fail(f'RATIO_MAP 缺失: {ct}')

# ═══════════════════════════════════════════════════
# 5. _LAYOUT_VARIANTS 存在性检查
# ═══════════════════════════════════════════════════
print('\n[5] generate_card_images_v3.py — _LAYOUT_VARIANTS (新增布局)')
from generate_card_images_v3 import _LAYOUT_VARIANTS
NEW_LAYOUTS = ['experiment', 'derivation', 'microscopic', 'graph_analysis', 'model', 'precise_wording']
for lk in NEW_LAYOUTS:
    if lk in _LAYOUT_VARIANTS:
        ok(f'LAYOUT_VARIANT 存在: {lk}')
    else:
        fail(f'LAYOUT_VARIANT 缺失: {lk}')

# ═══════════════════════════════════════════════════
# 6. CARD_TYPE_STRATEGY_MAP 检查
# ═══════════════════════════════════════════════════
print('\n[6] content_design_engine.py — CARD_TYPE_STRATEGY_MAP')
from content_design_engine import CARD_TYPE_STRATEGY_MAP
for ct in SCIENCE_CARD_TYPES:
    if ct in CARD_TYPE_STRATEGY_MAP:
        strat = CARD_TYPE_STRATEGY_MAP[ct]
        ok(f'STRATEGY_MAP 已注册: {ct} → primary={strat["primary"]}')
    else:
        fail(f'STRATEGY_MAP 缺失: {ct}')

# ═══════════════════════════════════════════════════
# 7. Knowledge card JSON 文件存在性
# ═══════════════════════════════════════════════════
print('\n[7] 知识卡片 JSON 文件')
JSON_FILES = [
    ('public/knowledge_cards/初中', '物理_八上_总结.json'),
    ('public/knowledge_cards/初中', '化学_九上_总结.json'),
    ('public/knowledge_cards/初中', '生物_七上_总结.json'),
    ('public/knowledge_cards/高中', '物理_高一上_总结.json'),
    ('public/knowledge_cards/高中', '化学_高一上_总结.json'),
    ('public/knowledge_cards/高中', '生物_高一上_总结.json'),
]
for folder, fname in JSON_FILES:
    fp = os.path.join(BASE_DIR, folder, fname)
    if os.path.exists(fp):
        try:
            data = json.loads(open(fp, encoding='utf-8').read())
            cards_count = sum(len(u.get('cards', [])) for u in data.get('units', []))
            ok(f'{folder}/{fname}  ({cards_count} 张卡片)')
        except Exception as e:
            fail(f'{folder}/{fname} JSON解析失败', str(e))
    else:
        fail(f'{folder}/{fname} 文件不存在')

# ═══════════════════════════════════════════════════
# 8. JSON 中的卡片类型覆盖度
# ═══════════════════════════════════════════════════
print('\n[8] JSON 卡片类型覆盖度')
all_types_in_json = set()
for folder, fname in JSON_FILES:
    fp = os.path.join(BASE_DIR, folder, fname)
    if os.path.exists(fp):
        data = json.loads(open(fp, encoding='utf-8').read())
        for u in data.get('units', []):
            for c in u.get('cards', []):
                all_types_in_json.add(c.get('type', ''))

ALL_12 = set(SCIENCE_CARD_TYPES + EXISTING_TYPES_REUSED)
covered = ALL_12 & all_types_in_json
missing = ALL_12 - all_types_in_json
for t in sorted(covered):
    ok(f'JSON中使用: {t}')
if missing:
    for t in sorted(missing):
        # 已存在类型缺少示例不算严重错误，用 warning
        print(f'  ⚠️  JSON 中未使用（已有类型可复用）: {t}')

# ═══════════════════════════════════════════════════
# 9. server.py _EDUCATION_SUBJECTS 包含理科
# ═══════════════════════════════════════════════════
print('\n[9] server.py — _EDUCATION_SUBJECTS 包含理科')
server_src = open(os.path.join(BASE_DIR, 'server.py'), encoding='utf-8').read()
for subj in ['物理', '化学', '生物']:
    if f"'{subj}'" in server_src and '_EDUCATION_SUBJECTS' in server_src:
        ok(f'server.py _EDUCATION_SUBJECTS 包含 {subj}')
    else:
        fail(f'server.py _EDUCATION_SUBJECTS 缺少 {subj}')

# 检查 folder routing 使用 stage
if 'folder = stage if stage in _EDUCATION_STAGES' in server_src:
    ok('server.py 文件夹路由使用 stage 参数')
else:
    fail('server.py 文件夹路由未使用 stage 参数')

# ═══════════════════════════════════════════════════
# 10. _SCIENCE_CARD_TYPES / _SCIENCE_SUBJECTS 集合
# ═══════════════════════════════════════════════════
print('\n[10] generate_card_images_v3.py — 科学类型/学科集合')
try:
    from generate_card_images_v3 import _SCIENCE_CARD_TYPES, _SCIENCE_SUBJECTS
    for ct in SCIENCE_CARD_TYPES:
        if ct in _SCIENCE_CARD_TYPES:
            ok(f'_SCIENCE_CARD_TYPES 包含: {ct}')
        else:
            fail(f'_SCIENCE_CARD_TYPES 缺少: {ct}')
    for s in ['物理', '化学', '生物']:
        if s in _SCIENCE_SUBJECTS:
            ok(f'_SCIENCE_SUBJECTS 包含: {s}')
        else:
            fail(f'_SCIENCE_SUBJECTS 缺少: {s}')
except ImportError as e:
    fail('导入 _SCIENCE_CARD_TYPES/_SCIENCE_SUBJECTS 失败', str(e))

# ═══════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════
print(f'\n{"="*50}')
print(f'总计: {passed} 通过 / {failed} 失败')
if failed == 0:
    print('🎉 所有测试通过！v10.9 理科卡片系统就绪。')
else:
    print(f'⚠️  有 {failed} 项失败，请检查。')
    sys.exit(1)
