#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompt 分段生成引擎 v2 — 将 Step 1 拆为「内容决策 + 视觉翻译」两阶段。

v1 架构问题:
  一个超长 prompt (system_template + card_info + skill_hint + fewshot + quality + design + ...)
  → Gemini 一次性生成全部 → 后段内容注意力衰减严重

v2 架构:
  Step 1a — 内容决策: 基于 SkillSchema + 卡片数据，生成结构化教学内容 JSON
  Step 1b — 视觉翻译: 拿到确定的内容 JSON → 翻译成精简的图片 prompt

  好处:
    1. 每步 prompt 短、信号密度高 → 模型遵循率高
    2. 内容和视觉解耦 → 可分别优化
    3. 中间 JSON 可审计 → 在生图前就发现内容问题

版本: 2.0 (2026-03-28)
"""

from __future__ import annotations
import json
import re
from typing import Optional

from skill_schema import (
    get_skill_schema, match_sub_type,
    SkillSchema, LayoutBlock, SubType,
)

# v1 的函数保留兼容
from prompt_builder import (
    build_layout_skeleton,
    build_content_fill,
    build_skill_enhanced_prompt,
    get_visual_strategy,
)


# ═══════════════════════════════════════════
# Step 1a: 内容决策 — 输出结构化 JSON
# ═══════════════════════════════════════════

CONTENT_DECISION_TEMPLATE = """你是教育卡片内容策划师。基于以下知识点信息，输出一个 JSON 对象，
精确描述卡片上每个区块应该展示什么内容。 

== 知识点 ==
学科: {subject} | 年级: {grade} {semester} | 类型: {card_type}
标题: {title}
定义: {definition}
例题: {example_text}
核心要点: {core_points_text}
易错: {mistakes_text}
记忆口诀: {memory_tip}
本质原因: {why_explanation}

== 卡片结构要求 (来自 SkillSchema) ==
{schema_blocks}

== 子类型匹配 ==
{sub_type_info}

== 输出格式 ==
输出纯 JSON（不加 ``` 标记），格式:

{{
  "blocks": [
    {{"id": "TITLE", "text": "标题中文 (≤{title_limit}字)", "font_size": "72pt"}},
    {{"id": "EXAMPLE", "text": "具体题目/例子", "visual_style": "white_card"}},
    {{"id": "CORE", "visual_type": "color_blocks|timeline|tree|comparison", 
      "steps": ["步骤1", "步骤2"], "why_explanation": "为什么这样做"}},
    {{"id": "ANSWER", "text": "答案", "font_size": "48pt"}},
    {{"id": "SLOGAN", "text": "口诀(≤8字)", "style": "sticky_note"}},
    {{"id": "ERROR_TIP", "text": "⚠️ 易错提示(≤6字)", "optional": true}}
  ],
  "color_scheme": "主色调描述",
  "text_manifest": {{
    "TITLE": "标题中文",
    "LINE1": "第一行核心内容（例题/规则/短语）",
    "LINE2": "第二行（解题步骤/对比/补充说明）",
    "LINE3": "第三行（答案/结论/更多例子）",
    "SLOGAN": "口诀/助记",
    "TIP": "⚠️ 易错提示(可选)"
  }},
  "total_chinese_chars": 12,
  "teaching_chain": "场景 → 规则 → 例句 → 对比 → 口诀"
}}

规则:
1. text_manifest 中所有中文总计 ≤ {max_chars} 字（越少越好，AI渲染少量文字更准确）
2. 每个文字块 ≤ {max_per_block} 字
3. 能用数字/符号/图表表达的绝不用中文（→ ① ② ③ ≈ ≥ ≤ ✓ ✗ + = 代替文字）
4. text_manifest 至少5项（TITLE + LINE1 + LINE2 + LINE3 + SLOGAN），有易错提示加TIP
5. LINE1/2/3 来自 blocks 的 EXAMPLE/CORE/ANSWER 内容，浓缩成短行
6. 英语卡: 标题用英文短语本身, 例句≥6个英文单词, LINE1/2/3 用英文例句+对比
7. ⚠️ 用符号压缩: "固定打点计时器在铁架台顶端"→"① 固定计时器→悬挂" 用→/①代替连词
"""

def build_content_decision_prompt(card: dict, card_type: str, subject: str,
                                   grade: str, semester: str,
                                   max_chars: int = 80,
                                   max_per_block: int = 20) -> str:
    """构建 Step 1a 的内容决策 prompt。
    
    输出一段 prompt，让 Gemini 生成结构化的教学内容 JSON。
    """
    schema = get_skill_schema(card_type, grade)
    title = card.get('title', '')
    definition = card.get('definition', '')[:150]
    memory_tip = card.get('memory_tip', '')
    why_explanation = card.get('why_explanation', '')[:200]
    
    # 例题
    example = card.get('example', {})
    if isinstance(example, str):
        example_text = example[:150]
    else:
        q = example.get('question', '')[:100]
        steps = example.get('steps', [])
        ans = example.get('answer', '')
        example_text = f'{q} → {" → ".join(str(s) for s in steps[:3])} = {ans}'
    
    # 核心要点
    points = card.get('core_points', [])[:4]
    core_points_text = '\n'.join(f'  - {str(p)[:80]}' for p in points) if points else '(无)'
    
    # 易错
    mistakes = card.get('mistakes', [])
    if mistakes:
        m = mistakes[0]
        mistakes_text = f'❌ {m.get("wrong", "")} → ✅ {m.get("correct", "")} (原因: {m.get("reason", "")})'
    else:
        mistakes_text = '(无)'
    
    # Schema 区块
    if schema:
        blocks_desc = []
        for b in schema.layout_blocks:
            req = '★必需' if b.required else '☆可选'
            area = f' ≥{b.min_area_pct}%' if b.min_area_pct else ''
            chars = f' ≤{b.max_chars}字' if b.max_chars else ''
            blocks_desc.append(f'  [{b.name}] ({b.placement}) {req}{area}{chars}: {b.description}')
        schema_blocks = '\n'.join(blocks_desc)
        title_limit = 8
        for b in schema.layout_blocks:
            if b.name == '标题' and b.max_chars > 0:
                title_limit = b.max_chars
    else:
        schema_blocks = '(未注册的卡片类型，使用通用布局)'
        title_limit = 8
    
    # 子类型
    matched_sub = match_sub_type(card_type, card) if schema else None
    if matched_sub:
        sub_type_info = (f'匹配: {matched_sub.name}\n'
                         f'  核心技巧: {matched_sub.core_technique}\n'
                         f'  视觉方法: {matched_sub.visual_method}')
        if matched_sub.analogy:
            sub_type_info += f'\n  类比: {matched_sub.analogy}'
    else:
        sub_type_info = '(无匹配子类型)'
    
    return CONTENT_DECISION_TEMPLATE.format(
        subject=subject, grade=grade, semester=semester,
        card_type=card_type, title=title, definition=definition,
        example_text=example_text, core_points_text=core_points_text,
        mistakes_text=mistakes_text, memory_tip=memory_tip,
        why_explanation=why_explanation,
        schema_blocks=schema_blocks, sub_type_info=sub_type_info,
        title_limit=title_limit, max_chars=max_chars, max_per_block=max_per_block,
    )


def parse_content_decision(response_text: str) -> Optional[dict]:
    """解析 Step 1a 的 JSON 输出"""
    # 尝试提取 JSON
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if not json_match:
        return None
    try:
        data = json.loads(json_match.group())
        if 'blocks' in data or 'text_manifest' in data:
            return data
    except json.JSONDecodeError:
        pass
    return None


# ═══════════════════════════════════════════
# Step 1b: 视觉翻译 — 内容 JSON → 图片 prompt
# ═══════════════════════════════════════════

VISUAL_TRANSLATION_TEMPLATE = """You are an AI image prompt engineer for Xiaohongshu-style educational knowledge cards.

Convert the following structured content into a concise English image generation prompt.

== Card Content (from content planner) ==
{content_json}

== Visual Rules — COMPLETE CARD WITH TEXT ==
- {canvas_line}
- Small cute mascot in bottom-right corner (<10% of image)
- Xiaohongshu style: professional card template design (like Canva/PPT)
{extra_visual_rules}

Design these 4 STRUCTURAL ZONES with text rendered directly:
🔹 Zone A — TOP BANNER (~2%-12%): Dark gradient strip, WHITE TITLE TEXT centered
🔹 Zone B — CONTENT CARD (~14%-78%): White rounded rectangle, TEACHING CONTENT text inside
🔹 Zone C — ACCENT STRIP (~80%-92%): Warm gradient bar, WHITE SLOGAN TEXT centered
🔹 Zone D — BOTTOM (~93%-98%): Small tip text if any
Fill remaining background with soft gradient of the main color's lightest tint.

== ⚠️ TEXT RENDERING RULE (MOST IMPORTANT) ==
- RENDER ALL TEXT directly in the image — text is the core content
- Every Chinese character must be perfectly formed (correct strokes, no garbled text)
- Every English word must be spelled correctly
- Text must look professionally typeset: clear size hierarchy, aligned, readable
- Title = large white bold text in banner
- Content = dark text on white card, well-spaced
- Slogan = white bold text on accent strip
- Text and visuals must feel unified — like a professional designer's work

== Output ==
Write ONLY the English image prompt (250-400 words).
Start with: "IMPORTANT: Generate a COMPLETE knowledge card with ALL text rendered directly in the image. The card must have: (1) a dark gradient BANNER at top ~2-12% with white title text, (2) a white rounded CONTENT CARD ~14-78% with teaching content text, (3) a warm colored ACCENT STRIP ~80-92% with white slogan text, (4) a small cute mascot in corner. All Chinese characters must be perfectly formed."

Then at the end, include the TEXT_MANIFEST (text that MUST appear in the image):
[TEXT_MANIFEST]
{manifest_lines}
[/TEXT_MANIFEST]
"""


def build_visual_translation_prompt(content_decision: dict, card_type: str,
                                     subject: str,
                                     extra_color_hint: str = '',
                                     extra_layout_hint: str = '',
                                     canvas_line: str = '',
                                     grade: str = '') -> str:
    """构建 Step 1b 的视觉翻译 prompt。
    
    把 Step 1a 输出的内容 JSON 翻译成图片生成 prompt。
    
    Args:
        extra_color_hint: v10.7 学科配色提示（英文）
        extra_layout_hint: v10.7 布局变体提示（英文）
        canvas_line: v10.8 画布描述行（英文），默认 "Canvas: 3:4 vertical ratio / ≥ 25% whitespace"
    """
    schema = get_skill_schema(card_type, grade)
    
    if not canvas_line:
        canvas_line = 'Canvas: 3:4 vertical ratio\\n- ≥ 25% whitespace'
    
    # 序列化内容 JSON
    content_json = json.dumps(content_decision, ensure_ascii=False, indent=2)
    
    # 额外视觉规则
    extra_rules = ''
    if extra_color_hint:
        extra_rules += extra_color_hint
    if extra_layout_hint:
        extra_rules += extra_layout_hint
    if schema:
        extra_rules += f'- Visual strategy: {schema.visual_rule_summary}\n'
        # v2.0: 结构化配色优先于文本配色
        if schema.color_config and schema.color_config.primary:
            extra_rules += '- Color config:\n'
            for cl in schema.color_config.to_prompt().split('\n'):
                extra_rules += f'  {cl}\n'
        elif schema.color_scheme:
            extra_rules += f'- Color scheme: {schema.color_scheme}\n'
        # v2.0: 视觉语言指令
        if schema.visual_language:
            extra_rules += f'- Visual language: {schema.visual_language}\n'
        # v2.0: 情绪弧线
        if schema.emotion_design:
            extra_rules += f'- Emotion arc: {schema.emotion_design}\n'
        if schema.forbidden:
            extra_rules += '- FORBIDDEN:\n'
            for f in schema.forbidden[:3]:
                extra_rules += f'  ❌ {f}\n'
    
    # manifest 行
    manifest = content_decision.get('text_manifest', {})
    manifest_lines = '\n'.join(f'{k}: {v}' for k, v in manifest.items())
    
    return VISUAL_TRANSLATION_TEMPLATE.format(
        content_json=content_json,
        extra_visual_rules=extra_rules,
        manifest_lines=manifest_lines,
        canvas_line=canvas_line,
    )


# ═══════════════════════════════════════════
# 组合: 兼容旧接口的增强版 generate_image_prompt
# ═══════════════════════════════════════════

def build_two_phase_prompt(card: dict, card_type: str, subject: str,
                            grade: str, semester: str,
                            max_chars: int = 15) -> tuple[str, str]:
    """生成两阶段 prompt (内容决策 + 视觉翻译)。
    
    返回两个 prompt 字符串，由调用方分别发送给 LLM。
    
    Returns:
        (content_decision_prompt, visual_translation_template)
        - content_decision_prompt: 发给 LLM，获取 JSON 输出
        - visual_translation_template: 等 JSON 解析后，调用
          build_visual_translation_prompt(parsed_json, ...) 生成
    """
    prompt_1a = build_content_decision_prompt(
        card, card_type, subject, grade, semester, max_chars=max_chars
    )
    # 1b 需要等 1a 的输出，这里只返回模板标识
    return prompt_1a, '[AWAIT_1A_OUTPUT]'


# ═══════════════════════════════════════════
# 快速测试
# ═══════════════════════════════════════════
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
        'why_explanation': '拆数法的本质是利用乘法分配律：(a+b)÷c = a÷c + b÷c',
        'difficulty': 2,
    }
    
    print('=== Step 1a: Content Decision Prompt ===')
    p1a = build_content_decision_prompt(test_card, '方法卡', '数学', '三年级', '下册')
    print(p1a[:500])
    print(f'... ({len(p1a)} chars total)')
    
    print('\n=== Step 1b: Visual Translation Template ===')
    # Simulated content decision output
    mock_decision = {
        'blocks': [
            {'id': 'TITLE', 'text': '口除', 'font_size': '72pt'},
            {'id': 'EXAMPLE', 'text': '840 ÷ 4 = ?'},
            {'id': 'CORE', 'visual_type': 'color_blocks', 'steps': ['800÷4=200', '40÷4=10']},
            {'id': 'ANSWER', 'text': '=210'},
            {'id': 'SLOGAN', 'text': '拆开除,再合体'},
        ],
        'text_manifest': {'TITLE': '口除', 'SLOGAN': '拆除合'},
        'total_chinese_chars': 5,
    }
    p1b = build_visual_translation_prompt(mock_decision, '方法卡', '数学')
    print(p1b[:500])
    print(f'... ({len(p1b)} chars total)')
