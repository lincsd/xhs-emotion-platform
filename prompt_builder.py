"""
Prompt 分段生成引擎 — 将单次 prompt 生成拆为「骨架 + 填充」两阶段。

设计理念:
  之前: 一段巨大的 system_prompt + card_info 丢给 AI → 一次性生成全部 prompt
  现在:
    阶段 A — 骨架构建: 基于 SkillSchema 的布局定义，先锁定「哪些区块 + 面积比例 + 排列顺序」
    阶段 B — 内容填充: 把卡片 JSON 数据填入骨架中每个区块的具体教学内容

  好处:
    1. 骨架保证布局一致性 → 不会漏掉必需区块
    2. 填充基于真实数据 → 不会张冠李戴
    3. 审计器可逐区块检查 → 发现哪里遗漏

版本: 1.0 (2025-06-27)
"""

from __future__ import annotations
import re
from typing import Optional

from skill_schema import (
    get_skill_schema, match_sub_type,
    SkillSchema, LayoutBlock, SubType,
)


# ═══════════════════════════════════════════
# 阶段 A: 布局骨架构建
# ═══════════════════════════════════════════

def build_layout_skeleton(card_type: str, card_data: dict) -> str:
    """基于 SkillSchema 构建布局骨架指令。
    
    输出格式: 一段结构化英文 prompt 片段，描述每个区块的位置、面积、约束。
    这段骨架会在最终 prompt 中先于内容出现，锁定视觉结构。
    
    Args:
        card_type: 卡片类型名
        card_data: 卡片 JSON 数据
    
    Returns:
        布局骨架 prompt 文本 (English)
    """
    schema = get_skill_schema(card_type)
    if not schema:
        return ''

    lines = []
    lines.append('=== LAYOUT SKELETON (MUST follow this exact structure) ===')
    lines.append(f'Card Type: {card_type} | Strategy: {schema.core_strategy}')
    lines.append('')

    # 计算已分配面积，剩余给中间内容区
    allocated = sum(b.min_area_pct for b in schema.layout_blocks if b.min_area_pct > 0)
    remaining = max(0, 100 - allocated - 25)  # 25% 留白

    for i, block in enumerate(schema.layout_blocks):
        req = 'REQUIRED' if block.required else 'OPTIONAL'
        area = f'{block.min_area_pct}%+' if block.min_area_pct > 0 else 'auto'
        char_limit = f'max {block.max_chars} CN chars' if block.max_chars > 0 else 'visual/numbers'

        lines.append(f'BLOCK {i+1}: [{block.name}]')
        lines.append(f'  Position: {block.placement} | Area: {area} | {req}')
        lines.append(f'  Content: {char_limit}')
        if block.description:
            lines.append(f'  Spec: {block.description}')
        lines.append('')

    # 匹配子类型的视觉策略
    matched_sub = match_sub_type(card_type, card_data)
    if matched_sub:
        lines.append(f'MATCHED SUB-TYPE: {matched_sub.name}')
        lines.append(f'  Visual Method: {matched_sub.visual_method}')
        if matched_sub.analogy:
            lines.append(f'  Life Analogy (bubble): "{matched_sub.analogy}"')
        if matched_sub.typical_error:
            lines.append(f'  Error Hint (optional): "⚠️{matched_sub.typical_error}"')
        lines.append('')

    lines.append(f'WHITESPACE: ≥25% of total area')
    lines.append(f'=== END SKELETON ===')

    return '\n'.join(lines)


# ═══════════════════════════════════════════
# 阶段 B: 内容填充
# ═══════════════════════════════════════════

def build_content_fill(card_type: str, card_data: dict, subject: str,
                       grade: str, semester: str) -> str:
    """基于卡片 JSON 数据填充每个区块的具体教学内容。
    
    根据 SkillSchema 中的 layout_blocks 名称动态映射内容，
    而非使用硬编码的泛型区块名。同时支持英语卡特有字段。
    
    Args:
        card_type: 卡片类型名  
        card_data: 卡片 JSON 数据
        subject: 学科名
        grade: 年级
        semester: 学期
    
    Returns:
        内容填充 prompt 文本 (混合中英文)
    """
    schema = get_skill_schema(card_type)
    
    lines = []
    lines.append('=== CONTENT FILL (map to skeleton blocks above) ===')
    lines.append(f'Subject: {subject} | Grade: {grade} {semester} | Type: {card_type}')
    lines.append('')

    title = card_data.get('title', '')
    definition = card_data.get('definition', '')[:120]

    # 获取 Schema 中的区块名列表（用于动态映射）
    block_names = set()
    if schema:
        block_names = {b.name for b in schema.layout_blocks}

    # ── 标题 ──
    title_display = title[:8]
    lines.append(f'[标题] → "{title_display}"')

    # ── 例题/题目 ──
    example = card_data.get('example', {})
    if isinstance(example, str):
        example_q = example[:120]
        example_steps = ''
        example_answer = ''
    else:
        example_q = (example.get('question') or '')[:120]
        steps = example.get('steps', [])
        example_steps = ' > '.join(str(s)[:60] for s in steps[:3]) if steps else ''
        example_answer = str(example.get('answer', ''))[:80]

    # 动态选择区块名: 优先匹配 Schema 中的实际名称
    example_block = '例题'
    for name in ['例题', '题目', '大题目', '陷阱题', '问题']:
        if name in block_names:
            example_block = name
            break

    if example_q:
        lines.append(f'[{example_block}] → "{example_q}"')
        if example_steps:
            lines.append(f'  Steps: {example_steps}')
        if example_answer:
            lines.append(f'  Answer: {example_answer}')
    elif definition:
        lines.append(f'[{example_block}] → (derive from definition: {definition[:60]})')

    # ── 核心教学区 (根据 Schema 区块名动态选择) ──
    points = card_data.get('core_points', [])[:4]

    # 映射: Schema 区块名 → 填充内容
    core_block_name = None
    for name in ['解法', '推导图', '对比区', '双栏对比区', '规则可视化区',
                 '句型公式区', '用法拓展区', '知识树/导图', '情景区',
                 '揭秘对比区', '生活场景大图', '概念提炼', '思维区']:
        if name in block_names:
            core_block_name = name
            break

    if core_block_name and points:
        clean = [str(p)[:80] for p in points]
        lines.append(f'[{core_block_name}] reference points:')
        for p in clean:
            lines.append(f'  • {p}')
    elif points:
        clean = [str(p)[:80] for p in points]
        lines.append(f'[核心教学区] reference points:')
        for p in clean:
            lines.append(f'  • {p}')

    # ── 公式 (公式卡专属) ──
    if '公式' in block_names:
        formula = card_data.get('definition', '')
        if formula:
            lines.append(f'[公式] → display prominently: "{formula[:80]}"')

    # ── 概念提炼 (概念卡专属) ──
    if '概念提炼' in block_names and definition:
        lines.append(f'[概念提炼] → key phrase: "{definition[:60]}"')

    # ── 生活场景大图 (概念卡专属) ──
    if '生活场景大图' in block_names:
        lines.append(f'[生活场景大图] → illustrate "{title}" with a real-life object/scene')

    # ── 金句 (辨析卡专属) ──
    if '金句' in block_names:
        tip = card_data.get('memory_tip', '')
        if tip:
            lines.append(f'[金句] → "{tip[:30]}"')
        else:
            lines.append(f'[金句] → (generate a ≤6字 summary of the key difference)')

    # ── 句型公式区 (句型卡专属) ──
    if '句型公式区' in block_names and definition:
        lines.append(f'[句型公式区] → structure: "{definition[:80]}"')

    # ── 例句展示区 (句型卡/语法卡) ──
    if '例句展示区' in block_names or '例句区' in block_names:
        ex_block = '例句展示区' if '例句展示区' in block_names else '例句区'
        if points:
            lines.append(f'[{ex_block}] → example sentences:')
            for p in points[:3]:
                lines.append(f'  • {str(p)[:80]}')

    # ── 规则可视化区 (语法卡) ──
    if '规则可视化区' in block_names and definition:
        lines.append(f'[规则可视化区] → visualize rule: "{definition[:80]}"')

    # ── 速记区分/速记公式/速记区 ──
    for name in ['速记区分', '速记公式', '速记区']:
        if name in block_names:
            tip = card_data.get('memory_tip', '')
            if tip:
                lines.append(f'[{name}] → "{tip[:30]}"')
            break

    # ── 替换练习 (情景对话卡) ──
    if '替换练习' in block_names and points:
        lines.append(f'[替换练习] → key phrase variations from core_points')

    # ── 真题速记 (知识总结卡) ──
    exam_focus = card_data.get('exam_focus', {})
    if '真题速记' in block_names and exam_focus:
        real_exam = exam_focus.get('real_exam_example', {})
        if real_exam:
            lines.append(f'[真题速记] → "{real_exam.get("question", "")[:60]}"')
            scoring = real_exam.get('scoring_notes', '')
            if scoring:
                lines.append(f'  Scoring: {scoring[:60]}')

    # ── 易错提醒 (知识总结卡) ──
    if '易错提醒' in block_names:
        trap = exam_focus.get('common_trap', '') if exam_focus else ''
        if trap:
            lines.append(f'[易错提醒] → "⚠️{trap[:40]}"')

    # ── 对错对比 / 揭秘对比区 ──
    mistakes = card_data.get('mistakes', [])
    contrast_block = None
    for name in ['对错对比', '揭秘对比区', '对比区']:
        if name in block_names:
            contrast_block = name
            break
    if contrast_block is None and mistakes:
        contrast_block = '对错对比'

    if contrast_block and mistakes:
        m = mistakes[0]
        lines.append(f'[{contrast_block}]')
        lines.append(f'  ❌ Wrong: {m.get("wrong", "")[:100]}')
        lines.append(f'  ✅ Correct: {m.get("correct", "")[:100]}')
        reason = m.get('reason', '')
        if reason:
            lines.append(f'  💡 Why: {reason[:80]}')

    # ── 本质原因 ──
    why = card_data.get('why_explanation', '')
    if why:
        lines.append(f'[本质原因] → {why[:150]}')

    # ── 口诀/记忆口诀 (非金句/非速记类的口诀区块) ──
    memory_tip = card_data.get('memory_tip', '')
    mnemonic_block = None
    for name in ['口诀', '记忆口诀', '口诀+小老师', '口诀+气泡(含类比)']:
        if name in block_names:
            mnemonic_block = name
            break
    if mnemonic_block:
        if memory_tip:
            lines.append(f'[{mnemonic_block}] → "{memory_tip[:30]}"')
        else:
            lines.append(f'[{mnemonic_block}] → (generate a ≤8字 mnemonic)')

    # ── 类比 (从匹配的子类型取) ──
    matched_sub = match_sub_type(card_type, card_data) if schema else None
    if matched_sub and matched_sub.analogy:
        lines.append(f'[气泡类比] → "{matched_sub.analogy}"')

    # ── 易错提示 (从子类型或 card_data 取) ──
    if '易错' in block_names:
        if matched_sub and matched_sub.typical_error:
            lines.append(f'[易错] → "⚠️{matched_sub.typical_error}"')
        elif card_data.get('easy_mistake'):
            lines.append(f'[易错] → "⚠️{str(card_data["easy_mistake"])[:20]}"')

    # ── 钩子文案 (陷阱卡/爆款) ──
    emotion_hook = card_data.get('emotion_hook', '')
    if '钩子' in block_names and emotion_hook:
        lines.append(f'[钩子] → "{emotion_hook[:40]}"')

    # ── 难度 ──
    diff = card_data.get('difficulty', 3)
    lines.append(f'[难度] → {diff}/5')

    lines.append('=== END CONTENT ===')
    return '\n'.join(lines)


# ═══════════════════════════════════════════
# 合并: 骨架 + 填充 → 完整 Skill 增强 prompt 段
# ═══════════════════════════════════════════

def build_skill_enhanced_prompt(card_type: str, card_data: dict,
                                 subject: str, grade: str, semester: str) -> str:
    """构建完整的 Skill 增强 prompt 段 (骨架 + 填充)。
    
    这段文本将注入到 v3 流水线的 Step 1 中，
    放在 system_prompt 和 card_info 之间，
    为 AI 提供精确的布局约束和内容映射。
    
    Args:
        card_type: 卡片类型名
        card_data: 卡片 JSON
        subject: 学科
        grade: 年级
        semester: 学期
    
    Returns:
        完整的 Skill 增强 prompt 文本
    """
    skeleton = build_layout_skeleton(card_type, card_data)
    content = build_content_fill(card_type, card_data, subject, grade, semester)

    if not skeleton:
        # 未注册的卡片类型，返回空（会降级到原有逻辑）
        return ''

    schema = get_skill_schema(card_type)

    lines = []
    lines.append('')
    lines.append('╔══════════════════════════════════════╗')
    lines.append('║  SKILL-ENHANCED GENERATION GUIDE     ║')
    lines.append('╚══════════════════════════════════════╝')
    lines.append('')
    lines.append(skeleton)
    lines.append('')
    lines.append(content)

    # 追加禁止事项
    if schema and schema.forbidden:
        lines.append('')
        lines.append('=== FORBIDDEN (violation = card rejected) ===')
        for i, f in enumerate(schema.forbidden, 1):
            lines.append(f'  ❌{i}. {f}')

    # 追加检查清单
    if schema and schema.required_elements:
        lines.append('')
        lines.append('=== SELF-CHECK before output ===')
        for elem in schema.required_elements:
            lines.append(f'  □ Does the card include [{elem}]?')

    lines.append('')
    return '\n'.join(lines)


# ═══════════════════════════════════════════
# 工具: 从 card_data 提取视觉策略 (兼容 CARD_TYPE_VISUAL_RULES)
# ═══════════════════════════════════════════

def get_visual_strategy(card_type: str, card_data: dict = None) -> str:
    """获取视觉策略摘要。
    
    优先从 SkillSchema 取，同时融合子类型的视觉方法。
    可作为 CARD_TYPE_VISUAL_RULES 的结构化替代。
    """
    schema = get_skill_schema(card_type)
    if not schema:
        return ''

    parts = [schema.visual_rule_summary]

    if card_data:
        matched = match_sub_type(card_type, card_data)
        if matched:
            parts.append(f'本卡子类型「{matched.name}」: {matched.visual_method}')

    return '\n   '.join(parts)


# ── 快速测试 ──
if __name__ == '__main__':
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
        'difficulty': 2,
    }

    print('=== Skill Enhanced Prompt ===')
    result = build_skill_enhanced_prompt('方法卡', test_card, '数学', '三年级', '下册')
    print(result)

    print('\n=== Visual Strategy ===')
    print(get_visual_strategy('方法卡', test_card))
