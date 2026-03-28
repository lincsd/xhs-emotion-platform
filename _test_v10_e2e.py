#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v10 E2E 真实测试 — 调用 Gemini API 生成 2 张卡片，验证完整流水线。

测试卡片:
  1. 数学方法卡: 口算整十整百÷一位数 (三下) — 测 v2 两阶段 + PIL 叠加
  2. 英语词汇卡: look at / look for 辨析 — 测英语审计 + 英文关键词

用法:
  先设置环境变量 GEMINI_API_KEY 或在 api_key.txt 中配置
  python _test_v10_e2e.py
"""

import json, os, sys, time

_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_DIR)

# ── 读 API Key ──
api_key = os.environ.get('GEMINI_API_KEY', '')
if not api_key:
    try:
        content = open(os.path.join(_DIR, 'api_key.txt'), encoding='utf-8').read()
        import re
        m = re.search(r'GEMINI_API_KEY=(.+)', content)
        if m:
            api_key = m.group(1).strip()
    except:
        pass

if not api_key:
    print('❌ 未找到 GEMINI_API_KEY，请设置环境变量或在 api_key.txt 中配置')
    sys.exit(1)

# 支持逗号分隔的多 key
api_keys = [k.strip() for k in api_key.split(',') if k.strip()]
print(f'API Keys: {len(api_keys)} 个, 首个={api_keys[0][:15]}...')

# ── 导入主模块 ──
print('\n=== 导入模块 ===')
import generate_card_images_v3 as v3

print(f'\n模块 Flag:')
print(f'  _HAS_PROMPT_V2     = {v3._HAS_PROMPT_V2}')
print(f'  _HAS_PIL_RENDERER  = {v3._HAS_PIL_RENDERER}')
print(f'  _HAS_SKILL_FEEDBACK= {v3._HAS_SKILL_FEEDBACK}')
print(f'  _HAS_SKILL_SCHEMA  = {v3._HAS_SKILL_SCHEMA}')
print(f'  _HAS_ENG_AUDIT     = {v3._HAS_ENG_AUDIT}')

# ── 测试卡片数据 ──
test_cards = [
    {
        'label': '数学方法卡 (三下)',
        'card': {
            'card_id': 'test-v10-01',
            'full_id': '数学-三下-test-v10-01',
            'title': '口算整十整百÷一位数',
            'type': '方法卡',
            'difficulty': 2,
            'importance': 5,
            'definition': '用拆数法把整十整百数拆成几个部分分别除，再把各部分的商加起来。',
            'core_points': [
                '先拆后除再合：840 = 800 + 40',
                '从高位拆起，每部分都能整除',
                '最后把各部分的商相加',
            ],
            'example': {
                'question': '840 ÷ 4 = ?',
                'steps': ['800 ÷ 4 = 200', '40 ÷ 4 = 10', '200 + 10 = 210'],
                'answer': '210',
            },
            'mistakes': [
                {'wrong': '840÷4=200', 'correct': '840÷4=210', 'reason': '忘记算40÷4=10'}
            ],
            'memory_tip': '拆开除,再合体',
            'why_explanation': '拆数法的本质是利用乘法分配律：(a+b)÷c = a÷c + b÷c',
        },
        'subject': '数学',
        'grade': '三年级',
        'semester': '下册',
    },
    {
        'label': '英语易混词卡 (五上)',
        'card': {
            'card_id': 'test-v10-02',
            'full_id': '英语-五上-test-v10-02',
            'title': 'look at VS look for',
            'type': '易混词卡',
            'difficulty': 2,
            'importance': 4,
            'definition': 'look at 是"看"（目光落在某物上），look for 是"找"（努力寻找某物）',
            'core_points': [
                'look at = 看 (eyes on it)',
                'look for = 找 (searching for it)',
                'at 表示目标明确，for 表示目的',
            ],
            'example': {
                'question': 'Look ___ the blackboard. / I am looking ___ my pen.',
                'steps': ['看黑板 → 目标明确 → look at', '找钢笔 → 正在寻找 → look for'],
                'answer': 'at / for',
            },
            'mistakes': [
                {'wrong': 'Look for the blackboard', 'correct': 'Look at the blackboard', 'reason': '看黑板是"注视"不是"寻找"'}
            ],
            'memory_tip': 'at看for找',
            'why_explanation': 'at 指向已知目标(注视)，for 指向未知目标(寻找)',
        },
        'subject': '英语',
        'grade': '五年级',
        'semester': '上册',
    },
]

# ── 执行测试 ──
output_dir = os.path.join(_DIR, '_test_v10_output')
os.makedirs(output_dir, exist_ok=True)
keys = api_keys
results = []

for i, tc in enumerate(test_cards):
    print(f'\n{"="*60}')
    print(f'  测试 {i+1}/{len(test_cards)}: {tc["label"]}')
    print(f'{"="*60}')
    
    t0 = time.time()
    try:
        success, filepath, stats = v3.process_single_card(
            card=tc['card'],
            subject=tc['subject'],
            grade=tc['grade'],
            semester=tc['semester'],
            keys=keys,
            output_dir=output_dir,
            skip_audit=False,  # 完整流水线
        )
        elapsed = time.time() - t0
        
        results.append({
            'label': tc['label'],
            'success': success,
            'filepath': filepath,
            'elapsed': elapsed,
            'stats': stats,
        })
        
        print(f'\n  结果: {"✅ 成功" if success else "❌ 失败"}')
        print(f'  耗时: {elapsed:.1f}s')
        print(f'  图片: {filepath}')
        print(f'  统计: {json.dumps({k: v for k, v in stats.items() if k != "card_id"}, ensure_ascii=False, indent=2)[:500]}')
        
    except Exception as e:
        elapsed = time.time() - t0
        results.append({
            'label': tc['label'],
            'success': False,
            'filepath': '',
            'elapsed': elapsed,
            'error': str(e),
        })
        print(f'\n  ❌ 异常: {e}')
        import traceback
        traceback.print_exc()

# ── 汇总 ──
print(f'\n{"="*60}')
print(f'  v10 E2E 测试汇总')
print(f'{"="*60}')

for r in results:
    status = '✅' if r['success'] else '❌'
    elapsed = r.get('elapsed', 0)
    stats = r.get('stats', {})
    score = stats.get('audit_score', 0)
    model = stats.get('image_model', '?')
    action = stats.get('final_action', '?')
    pil = '🎨PIL' if stats.get('pil_rendered') else ''
    
    print(f'  {status} {r["label"]:20s} | {elapsed:5.1f}s | score={score} | model={model} | {action} {pil}')
    if r.get('error'):
        print(f'     ERROR: {r["error"][:80]}')

total_ok = sum(1 for r in results if r['success'])
print(f'\n  总计: {total_ok}/{len(results)} 成功')
print(f'  输出目录: {output_dir}')

sys.exit(0 if total_ok == len(results) else 1)
