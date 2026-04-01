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

  v2.0 增强 (2025-07):
    - attention_priority: 按注意力层级排序区块
    - visual_language: 注入独特视觉语言指令
    - hook_strategy: 3秒钩子策略 (小红书传播)
    - l1_interference: 中文母语干扰提示
    - max_info_chunks: 认知负荷上限
    - visual_variants: 每次随机选一个视觉变体
    - color_config: 结构化配色 (优先于文本 color_scheme)

版本: 2.0 (2025-07)
"""

from __future__ import annotations
import random
import re
from typing import Optional

from skill_schema import (
    get_skill_schema, match_sub_type,
    SkillSchema, LayoutBlock, SubType, ColorConfig,
)


# ═══════════════════════════════════════════
# 阶段 A: 布局骨架构建
# ═══════════════════════════════════════════

def build_layout_skeleton(card_type: str, card_data: dict, grade: str = '') -> str:
    """基于 SkillSchema 构建布局骨架指令。
    
    输出格式: 一段结构化英文 prompt 片段，描述每个区块的位置、面积、约束。
    这段骨架会在最终 prompt 中先于内容出现，锁定视觉结构。
    
    Args:
        card_type: 卡片类型名
        card_data: 卡片 JSON 数据
        grade: 年级名（可选），用于分年级段 Skill 查找
    
    Returns:
        布局骨架 prompt 文本 (English)
    """
    schema = get_skill_schema(card_type, grade)
    if not schema:
        return ''

    lines = []
    lines.append('=== LAYOUT SKELETON (MUST follow this exact structure) ===')
    lines.append(f'Card Type: {card_type} | Strategy: {schema.core_strategy}')

    # ── v2.0: 视觉语言指令 ──
    if schema.visual_language:
        lines.append(f'Visual Language: {schema.visual_language}')

    # ── v2.0: 认知负荷上限 ──
    lines.append(f'Max info chunks: {schema.max_info_chunks} (DO NOT exceed)')

    # ── v2.0: 视觉变体随机选择 ──
    if schema.visual_variants:
        chosen_variant = random.choice(schema.visual_variants)
        lines.append(f'Visual Variant (use this style): {chosen_variant}')

    # ── v2.0: 情绪弧线 ──
    if schema.emotion_design:
        lines.append(f'Emotion Arc: {schema.emotion_design}')

    # ── v2.0: 3秒钩子策略 ──
    if schema.hook_strategy:
        lines.append(f'Hook (first 3 seconds): {schema.hook_strategy}')

    lines.append('')

    # ── v2.0: 结构化配色 (优先) 或文本配色 ──
    if schema.color_config and schema.color_config.primary:
        lines.append('=== COLOR CONFIG ===')
        lines.append(schema.color_config.to_prompt())
        lines.append('')
    elif schema.color_scheme:
        lines.append(f'Color scheme: {schema.color_scheme}')
        lines.append('')

    # 按 attention_priority 排序区块 (1=先看, 3=最后看)
    sorted_blocks = sorted(schema.layout_blocks, key=lambda b: b.attention_priority)

    # 计算已分配面积，剩余给中间内容区
    allocated = sum(b.min_area_pct for b in schema.layout_blocks if b.min_area_pct > 0)
    remaining = max(0, 100 - allocated - 25)  # 25% 留白

    for i, block in enumerate(sorted_blocks):
        req = 'REQUIRED' if block.required else 'OPTIONAL'
        area = f'{block.min_area_pct}%+' if block.min_area_pct > 0 else 'auto'
        char_limit = f'max {block.max_chars} CN chars' if block.max_chars > 0 else 'visual/numbers'
        priority_label = {1: '🔴HOOK(eye-catch first)', 2: '🟡CORE', 3: '🟢SUPPLEMENT'}
        prio = priority_label.get(block.attention_priority, '🟡CORE')

        lines.append(f'BLOCK {i+1}: [{block.name}] — {prio}')
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
        # v2.0: 子类型级别的母语干扰
        if matched_sub.l1_interference:
            lines.append(f'  ⚠️ L1 Chinese Interference: {matched_sub.l1_interference}')
        lines.append('')

    # ── v2.0: 母语干扰提示 (schema级别) ──
    if schema.l1_interference:
        lines.append('=== L1 INTERFERENCE (Chinese mother tongue) ===')
        lines.append('Students will make these errors due to Chinese thinking patterns:')
        for li in schema.l1_interference[:3]:
            lines.append(f'  ⚠️ {li}')
        lines.append('→ Design the card to PREVENT these errors, not just teach the rule.')
        lines.append('')

    lines.append(f'WHITESPACE: ≥25% of total area')

    # ── v10.22: P0 统一吉祥物形象 ──
    lines.append('')
    lines.append('=== MASCOT RULES (MANDATORY) ===')
    lines.append('  🦉 ALWAYS use the SAME mascot: a cute owl wearing a graduation cap (学士帽猫头鹰)')
    lines.append('  • Place the owl in the bottom-right corner, small size (under 8% of card area)')
    lines.append('  • The owl may hold props matching the card type:')
    lines.append('    - 词汇卡/速记卡: owl holds a dictionary or magnifying glass')
    lines.append('    - 语法卡/时态卡/句型卡: owl holds a ruler or pointer')
    lines.append('    - 易混词卡/陷阱卡/辨析卡: owl holds a warning sign or balance scale')
    lines.append('    - 情景对话卡: owl wears a stethoscope or relevant costume')
    lines.append('    - PK挑战卡: owl holds a trophy or boxing gloves')
    lines.append('    - 知识总结卡: owl holds a checklist or clipboard')
    lines.append('    - 发音挑战卡: owl holds a megaphone or microphone')
    lines.append('  • ❌ NEVER use a bear, pencil, or any other character as mascot')
    lines.append('  • ❌ NEVER omit the mascot entirely')
    lines.append('')

    # ── v10.22: P1 视觉层次与排版优化 ──
    lines.append('=== VISUAL HIERARCHY RULES ===')
    lines.append('  📐 LINE SPACING: Use generous line spacing (1.5x) between content lines')
    lines.append('  📐 PARAGRAPH GAP: Leave clear vertical gaps between different sections')
    lines.append('  🎨 BACKGROUND BLOCKS: Use subtle light-colored background blocks (pale blue, light gray, cream)')
    lines.append('     to visually separate different knowledge sections within the content card')
    lines.append('  🎨 For listed items (multiple phrases/rules), alternate background tint per item')
    lines.append('  📊 COLOR-CODE key terms: use distinct colors for verbs, nouns, and structures')
    lines.append('  📊 Use thin divider lines or spacing to separate Usage/Example/Error sections')
    lines.append('')

    # ── v10.22: P2 主题相关插图（强化版）──
    lines.append('=== ILLUSTRATION REQUIREMENTS ===')
    lines.append('Every card MUST include at least ONE concept illustration (NOT just the mascot):')
    lines.append('  • The illustration should directly explain or visualize the knowledge point')
    lines.append('  • SPECIFIC illustration types by card category:')
    lines.append('    - 词汇卡: small scene/object illustrating the word meaning')
    lines.append('    - 语法卡: color-coded sentence diagram, formula box with arrows')
    lines.append('    - 时态卡: timeline with past/present/future markers and action icons')
    lines.append('    - 易混词卡/辨析卡: side-by-side contrast illustration (two mini-scenes)')
    lines.append('    - 情景对话卡: comic-strip style with 2-3 panels and speech bubbles')
    lines.append('    - PK挑战卡: VS battle layout with two competing answer boxes')
    lines.append('    - 知识总结卡: mini mind-map or radial diagram')
    lines.append('    - 发音挑战卡: mouth/tongue position diagram or waveform icon')
    lines.append('  • Illustrations should occupy 15-25% of card area')
    lines.append('  • Style: flat design, clean lines, 2-3 colors max per illustration')
    lines.append('')

    # ── v10.22: P2 互动元素指令 ──
    lines.append('=== INTERACTIVE ELEMENT (recommended) ===')
    lines.append('  Include a mini-exercise or thought prompt in the card where appropriate:')
    lines.append('  • Fill-in-the-blank: "She ___ (go) to school yesterday."')
    lines.append('  • Quick quiz: "Which is correct? A or B?"')
    lines.append('  • Think prompt: "💡 Can you make a sentence using this pattern?"')
    lines.append('  • Place interactive elements in a distinct colored box (e.g., pale yellow background)')
    lines.append('')

    # ── v10.22: P3 底部区域统一规范 ──
    lines.append('=== BOTTOM AREA STANDARD ===')
    lines.append('  The bottom area of every card must follow this exact layout (top to bottom):')
    lines.append('  1. ACCENT STRIP: warm gradient bar with SLOGAN text (white, bold, centered)')
    lines.append('  2. TIP LINE: small gray text, always "年级 + 学期 + 卡片类型" format')
    lines.append('  3. MASCOT: owl in bottom-right corner')
    lines.append('  • TIP text font size must be consistent across all cards (10-11pt equivalent)')
    lines.append('  • English encouragement tips (e.g., "Practice daily!") go INSIDE the content card, NOT in the bottom area')
    lines.append('')

    # ── v10.22: 可视化教学工具 ──
    lines.append('=== VISUAL TEACHING TOOLS (use at least 2) ===')
    lines.append('  📊 Color-coded text: highlight key words/structures with distinct colors')
    lines.append('  🔀 Arrows/flow lines: show transformations, cause-effect, or word order')
    lines.append('  📐 Structure diagrams: sentence formulas like "S + V + O" in rounded boxes')
    lines.append('  🕐 Timelines: for tense/sequence topics, show past→present→future')
    lines.append('  💬 Speech bubbles: for dialogues, show characters speaking')
    lines.append('  🔲 Comparison tables: 2-column layout for vs/contrast topics')
    lines.append('  ⭕ Mind maps: for summary/overview cards, radial branch layout')
    lines.append('  🎨 Background color blocks: group related items with subtle tinted backgrounds')
    lines.append('')

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
    schema = get_skill_schema(card_type, grade)
    
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
    skeleton = build_layout_skeleton(card_type, card_data, grade)
    content = build_content_fill(card_type, card_data, subject, grade, semester)

    if not skeleton:
        # 未注册的卡片类型，返回空（会降级到原有逻辑）
        return ''

    schema = get_skill_schema(card_type, grade)

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

def get_visual_strategy(card_type: str, card_data: dict = None, grade: str = '') -> str:
    """获取视觉策略摘要。
    
    优先从 SkillSchema 取，同时融合子类型的视觉方法。
    可作为 CARD_TYPE_VISUAL_RULES 的结构化替代。
    """
    schema = get_skill_schema(card_type, grade)
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
