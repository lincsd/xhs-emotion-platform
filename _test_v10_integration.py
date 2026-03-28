#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v10 架构集成测试 — 验证所有新模块导入成功 + 核心逻辑正确。

测试范围:
  1. 模块导入: pil_text_renderer, prompt_builder_v2, skill_feedback, prompt_auditor (L2)
  2. prompt_builder_v2: 两阶段 prompt 构建
  3. prompt_auditor L2: 充分性检查
  4. skill_feedback: 反馈分析 (空DB降级)
  5. pil_text_renderer: PIL overlay (需要 Pillow)
  6. generate_card_images_v3 导入: 验证所有 flag 正确

用法: python _test_v10_integration.py
"""

import sys
import os
import json

_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_DIR)

passed = 0
failed = 0
errors = []


def test(name, condition, detail=''):
    global passed, failed
    if condition:
        passed += 1
        print(f'  ✅ {name}')
    else:
        failed += 1
        errors.append(f'{name}: {detail}')
        print(f'  ❌ {name} — {detail}')


# ═══════════════════════════════════════════
# 1. 模块导入测试
# ═══════════════════════════════════════════
print('\n=== 1. 模块导入 ===')

try:
    from pil_text_renderer import pil_primary_render, PIL_MODE_OVERLAY, PIL_MODE_DISABLED
    test('pil_text_renderer 导入', True)
except ImportError as e:
    test('pil_text_renderer 导入', False, str(e))

try:
    from prompt_builder_v2 import (
        build_content_decision_prompt,
        parse_content_decision,
        build_visual_translation_prompt,
        build_two_phase_prompt,
    )
    test('prompt_builder_v2 导入', True)
except ImportError as e:
    test('prompt_builder_v2 导入', False, str(e))

try:
    from skill_feedback import (
        analyze_card_type, analyze_all_types,
        build_feedback_prompt_hint, get_feedback_summary,
    )
    test('skill_feedback 导入', True)
except ImportError as e:
    test('skill_feedback 导入', False, str(e))

try:
    from prompt_auditor import audit_prompt, audit_and_patch, format_audit_summary, AuditResult
    test('prompt_auditor 导入', True)
except ImportError as e:
    test('prompt_auditor 导入', False, str(e))


# ═══════════════════════════════════════════
# 2. prompt_builder_v2: 两阶段构建
# ═══════════════════════════════════════════
print('\n=== 2. Prompt Builder v2 (两阶段) ===')

test_card = {
    'title': '口算整十整百÷一位数',
    'type': '方法卡',
    'definition': '用拆数法把整十整百数拆成几个部分分别除',
    'example': {
        'question': '840 ÷ 4 = ?',
        'steps': ['800÷4=200', '40÷4=10', '200+10=210'],
        'answer': '210'
    },
    'core_points': ['先拆后除再合', '从高位拆起'],
    'mistakes': [{'wrong': '840÷4=200', 'correct': '840÷4=210', 'reason': '忘算40÷4'}],
    'memory_tip': '拆开除,再合体',
    'why_explanation': '拆数法的本质是利用乘法分配律',
    'difficulty': 2,
}

try:
    p1a = build_content_decision_prompt(test_card, '方法卡', '数学', '三年级', '下册')
    test('Step 1a prompt 生成', len(p1a) > 200, f'len={len(p1a)}')
    test('1a 包含卡片标题', '口算' in p1a or '整十' in p1a)
    test('1a 包含例题', '840' in p1a)
    test('1a 包含字数限制', 'max_chars' in p1a or '≤' in p1a)
except Exception as e:
    test('Step 1a prompt 生成', False, str(e))

# 模拟 1a 输出
mock_decision = {
    'blocks': [
        {'id': 'TITLE', 'text': '口除', 'font_size': '72pt'},
        {'id': 'EXAMPLE', 'text': '840 ÷ 4 = ?'},
        {'id': 'CORE', 'visual_type': 'color_blocks', 'steps': ['800÷4=200', '40÷4=10']},
        {'id': 'ANSWER', 'text': '=210'},
        {'id': 'SLOGAN', 'text': '拆除合'},
    ],
    'text_manifest': {'TITLE': '口除', 'SLOGAN': '拆除合'},
    'total_chinese_chars': 5,
}

try:
    p1b = build_visual_translation_prompt(mock_decision, '方法卡', '数学')
    test('Step 1b prompt 生成', len(p1b) > 100, f'len={len(p1b)}')
    test('1b 包含 manifest', 'TITLE' in p1b)
    test('1b 包含视觉规则', 'Chinese' in p1b or 'chinese' in p1b.lower())
except Exception as e:
    test('Step 1b prompt 生成', False, str(e))

# parse_content_decision
try:
    json_str = json.dumps(mock_decision, ensure_ascii=False)
    parsed = parse_content_decision(json_str)
    test('parse_content_decision', parsed is not None and 'blocks' in parsed)
    
    # 无效输入
    parsed_bad = parse_content_decision('this is not json at all')
    test('parse_content_decision 无效输入', parsed_bad is None)
except Exception as e:
    test('parse_content_decision', False, str(e))


# ═══════════════════════════════════════════
# 3. prompt_auditor L2 充分性
# ═══════════════════════════════════════════
print('\n=== 3. Prompt Auditor L2 ===')

test_prompt_good = """
Create a 3:4 vertical knowledge card about oral division.
Title: "口除" in large bold text at top.
Main area: Show the example problem "840 ÷ 4 = ?" prominently.
Split 840 into two color-coded blocks: 800 ÷ 4 = 200 (green), 40 ÷ 4 = 10 (orange).
Answer section: Large bold "= 210" with fireworks effect.
Bottom: Mnemonic slogan "拆开除再合体" on a sticky note.
Small teacher character in corner with bubble saying "拆!" 
Background: warm pastel gradient, no text in decorative areas.
"""

test_prompt_vague = """
Create a nice educational card.
Include some math stuff.
Make it colorful.
"""

test_manifest_good = {'TITLE': '口除', 'LINE1': '拆除', 'SLOGAN': '合体'}
test_manifest_bad = {'TITLE': '这是一个非常长的标题超过限制了啊', 'LINE1': '详细解释', 'EXTRA': '额外文字'}

try:
    result_good = audit_prompt(test_prompt_good, '方法卡', test_card, test_manifest_good)
    test('L1+L2 审计 (好prompt) pass', result_good.verdict in ('pass', 'warn'),
         f'verdict={result_good.verdict}, coverage={result_good.coverage_pct:.0f}%')
    
    # L2 检查: 好 prompt 应有 840 这样的具体数字
    l2_issues = [i for i in result_good.issues if i.category == 'insufficiency']
    test('L2 好prompt insufficiency少', len(l2_issues) <= 2,
         f'insufficiency issues: {len(l2_issues)}')
    
    result_vague = audit_prompt(test_prompt_vague, '方法卡', test_card, test_manifest_bad)
    test('L1+L2 审计 (差prompt) 分低', result_vague.coverage_pct < 80,
         f'coverage={result_vague.coverage_pct:.0f}%')
    
    l2_vague = [i for i in result_vague.issues if i.category == 'insufficiency']
    test('L2 差prompt insufficiency多', len(l2_vague) >= 1,
         f'insufficiency issues: {len(l2_vague)}')
    
    # 格式化摘要
    summary = format_audit_summary(result_good)
    test('审计摘要格式', '[审计]' in summary, summary[:50])
    
except Exception as e:
    test('L2 审计执行', False, str(e))


# ═══════════════════════════════════════════
# 4. skill_feedback: 降级测试
# ═══════════════════════════════════════════
print('\n=== 4. Skill Feedback (降级) ===')

try:
    fb = analyze_card_type('方法卡', min_samples=1000)
    test('analyze_card_type 无数据返回None', fb is None)
    
    hint = build_feedback_prompt_hint('方法卡')
    test('build_feedback_prompt_hint 无数据返回空', hint == '')
    
    summary = get_feedback_summary('方法卡')
    test('get_feedback_summary 无数据有提示', '样本不足' in summary or '方法卡' in summary)
except Exception as e:
    test('skill_feedback 降级', False, str(e))


# ═══════════════════════════════════════════
# 5. PIL 文字渲染 (有Pillow才测)
# ═══════════════════════════════════════════
print('\n=== 5. PIL 文字渲染 ===')

try:
    from PIL import Image
    has_pil = True
except ImportError:
    has_pil = False
    print('  ⏭️  Pillow 未安装，跳过 PIL 渲染测试')

if has_pil:
    try:
        # 创建测试图片 (800x1066, 3:4)
        img = Image.new('RGB', (800, 1066), color=(255, 200, 150))
        import io
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        test_img_data = buf.getvalue()
        
        test_manifest_pil = {'TITLE': '口除', 'LINE1': '拆除', 'SLOGAN': '合体'}
        
        result_data, ok = pil_primary_render(
            test_img_data, test_manifest_pil, card_title='口算÷一位数'
        )
        test('PIL primary render 执行', ok, f'ok={ok}')
        if ok:
            test('PIL 输出有数据', len(result_data) > 100)
            # 验证输出是有效 PNG
            out_img = Image.open(io.BytesIO(result_data))
            test('PIL 输出尺寸正确', out_img.size == (800, 1066),
                 f'size={out_img.size}')
    except Exception as e:
        test('PIL 渲染测试', False, str(e))


# ═══════════════════════════════════════════
# 6. generate_card_images_v3 模块 flag 检查
# ═══════════════════════════════════════════
print('\n=== 6. 主管道模块 Flag ===')

try:
    # 导入时会打印各模块加载状态
    import generate_card_images_v3 as v3
    
    test('_HAS_SKILL_SCHEMA', hasattr(v3, '_HAS_SKILL_SCHEMA'))
    test('_HAS_PROMPT_V2', hasattr(v3, '_HAS_PROMPT_V2'))
    test('_HAS_PIL_RENDERER', hasattr(v3, '_HAS_PIL_RENDERER'))
    test('_HAS_SKILL_FEEDBACK', hasattr(v3, '_HAS_SKILL_FEEDBACK'))
    
    test('generate_image_prompt_v2 存在', hasattr(v3, 'generate_image_prompt_v2'))
    test('generate_image_prompt 存在', hasattr(v3, 'generate_image_prompt'))
except Exception as e:
    test('主管道导入', False, str(e))


# ═══════════════════════════════════════════
# 7. v10.5 视觉反馈闭环组件测试
# ═══════════════════════════════════════════
print('\n=== 7. v10.5 视觉反馈闭环 ===')

try:
    import generate_card_images_v3 as v3
    
    # 检查新常量
    test('VISUAL_REFINE_THRESHOLD 存在', hasattr(v3, 'VISUAL_REFINE_THRESHOLD'))
    test('MAX_REFINE_ROUNDS 存在', hasattr(v3, 'MAX_REFINE_ROUNDS'))
    test('VISUAL_REFINE_THRESHOLD 合理', 60 <= v3.VISUAL_REFINE_THRESHOLD <= 95,
         f'值={v3.VISUAL_REFINE_THRESHOLD}')
    test('MAX_REFINE_ROUNDS 合理', 1 <= v3.MAX_REFINE_ROUNDS <= 5,
         f'值={v3.MAX_REFINE_ROUNDS}')
    
    # 检查新函数存在
    test('visual_feedback_audit 存在', callable(getattr(v3, 'visual_feedback_audit', None)))
    test('_build_refinement_prompt 存在', callable(getattr(v3, '_build_refinement_prompt', None)))
    test('refine_card_image 存在', callable(getattr(v3, 'refine_card_image', None)))
    
    # 检查 VISUAL_FEEDBACK_AUDIT_PROMPT 内容
    prompt = v3.VISUAL_FEEDBACK_AUDIT_PROMPT
    test('审核prompt包含5层结构', 'Layer A' in prompt and 'Layer B' in prompt and 
         'Layer C' in prompt and 'Layer D' in prompt and 'Layer E' in prompt)
    test('审核prompt包含致命缺陷', 'fatal_flaws' in prompt)
    test('审核prompt包含笔画保真', '笔画保真' in prompt or 'stroke_fidelity' in prompt)
    test('审核prompt包含记忆锚点', '记忆锚点' in prompt or 'memory_anchor' in prompt)
    test('审核prompt包含截图冲动', '截图冲动' in prompt or 'screenshot_urge' in prompt)
    test('审核prompt包含学科专属', 'subject_specific' in prompt)
    test('审核prompt包含视线引导', 'eye_flow' in prompt or '视线引导' in prompt)
    
    # 测试 _build_refinement_prompt 输出格式
    mock_audit = {
        'total': 65,
        'fatal_flaws': [{'code': 'A1', 'description': '标题乱码'}],
        'scores': {
            'B_stroke_fidelity': 5, 'B_text_completeness': 7, 'B_typo_system': 6,
            'C_color_narrative': 8, 'C_spatial_rhythm': 7, 'C_eye_flow': 6,
            'D_cognitive_load': 8, 'D_memory_anchor': 6, 'D_key_emphasis': 7,
            'E_thumb_stop': 7, 'E_screenshot_urge': 6, 'E_craft_polish': 5,
        },
        'text_errors': [
            {'expected': '乘法口诀', 'actual': '乘法口决', 'type': 'wrong_char', 'severity': 'high', 'location': 'Banner'},
            {'expected': '速算技巧', 'actual': '', 'type': 'missing', 'severity': 'fatal', 'location': 'Content'},
        ],
        'improvements': [
            '【B1·笔画】标题"诀"误写为"决"',
            '【C2·空间】左边距不足',
        ],
        'keep': ['配色不错', '卡通角色可爱'],
        'eye_flow_path': '标题→步骤→口诀',
        'subject_specific': {'check': '数学', 'issues': ['公式上标渲染错误']},
        'one_line_verdict': '文字有误，整体还行',
    }
    mock_manifest = {'TITLE': '乘法口诀', 'LINE1': '速算技巧', 'SLOGAN': '一起来学'}
    
    ref_prompt = v3._build_refinement_prompt(mock_audit, mock_manifest, subject='数学')
    test('精修prompt包含分数', '65/100' in ref_prompt)
    test('精修prompt包含KEEP', 'DO NOT CHANGE' in ref_prompt or '配色不错' in ref_prompt)
    test('精修prompt包含致命缺陷', 'FATAL' in ref_prompt or '标题乱码' in ref_prompt)
    test('精修prompt包含文字修正', '乘法口决' in ref_prompt and '乘法口诀' in ref_prompt)
    test('精修prompt包含manifest', '速算技巧' in ref_prompt)
    test('精修prompt包含学科专属', '公式上标' in ref_prompt or 'SUBJECT' in ref_prompt)
    
    # 测试 visual_feedback_audit 无manifest降级
    empty_result = v3.visual_feedback_audit(b'fake_img', {}, 'fake_key')
    test('无manifest审核降级', empty_result.get('total', 0) == 75)
    
except Exception as e:
    test('v10.5 组件测试', False, str(e))
    import traceback
    traceback.print_exc()


# ═══════════════════════════════════════════
# 结果汇总
# ═══════════════════════════════════════════
print(f'\n{"="*50}')
print(f'  v10 集成测试: {passed} passed, {failed} failed')
print(f'{"="*50}')

if errors:
    print('\n失败项:')
    for e in errors:
        print(f'  ❌ {e}')

sys.exit(0 if failed == 0 else 1)
