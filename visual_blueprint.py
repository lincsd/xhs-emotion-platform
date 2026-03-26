# -*- coding: utf-8 -*-
"""
知识呈现蓝图引擎 (Knowledge Visual Blueprint Engine)
=====================================================
为每种知识类型建立详细的视觉呈现指导。

四大子系统:
  1. 认知视觉模式库 — 12种知识呈现模板(步骤流/对比栏/气泡图等)
  2. 智能信息分层 — 自动识别核心/辅助/装饰信息，分配视觉权重
  3. 记忆策略匹配库 — 按知识类型选择最佳记忆法
  4. 15字符智能压缩 — 在字符限制下选择最高信息密度表述

作者: AI Auto-Arch    版本: 2026-03-26
"""

import json, re, os
from typing import Dict, List, Optional, Tuple, Any

# ────────────────────────────────────────────────────
# 1. 认知视觉模式库 (Cognitive Visual Patterns)
# ────────────────────────────────────────────────────

VISUAL_PATTERNS = {
    "step_flow": {
        "name": "步骤流程图",
        "description": "从上到下或从左到右的步骤递进",
        "layout": "vertical_cascade",
        "prompt_template": (
            "Layout: VERTICAL FLOW with {n_steps} rounded rectangle blocks connected "
            "by downward arrows (→). Each block: pastel background, bold step number "
            "(①②③), key operation text. Arrow color deepens with each step. "
            "Final block is 1.5× larger with golden border = ANSWER. "
            "Left margin has a thin decorative line as progress bar."
        ),
        "best_for": ["calculation", "method", "procedure"],
        "max_items": 5,
        "visual_weight": {"title": 0.15, "steps": 0.55, "answer": 0.20, "decoration": 0.10}
    },
    "split_compare": {
        "name": "双栏对比图",
        "description": "左右对照展示错误vs正确/概念A vs 概念B",
        "layout": "horizontal_split",
        "prompt_template": (
            "Layout: SPLIT SCREEN. Left 45% has light red/pink background with "
            "a subtle ✗ watermark, showing the WRONG approach. Right 45% has light "
            "green background with ✓ watermark, showing the CORRECT approach. "
            "Center 10% has a bold VS or divider line. Top banner spans full width "
            "with the topic title. Each side has the same structure: problem → process → result."
        ),
        "best_for": ["error_comparison", "grammar", "distinction"],
        "max_items": 2,
        "visual_weight": {"title": 0.10, "left_panel": 0.40, "right_panel": 0.40, "decoration": 0.10}
    },
    "concept_bubble": {
        "name": "概念气泡图",
        "description": "中心概念向外发散出关联知识点",
        "layout": "radial",
        "prompt_template": (
            "Layout: MIND MAP / BUBBLE CHART. Center has a large circle with the "
            "CORE CONCEPT (biggest text, vivid color). 3-4 smaller bubbles surround "
            "it, connected by curved lines. Each bubble contains one key point. "
            "Outermost ring has tiny detail bubbles. Colors go from warm center to cool edges."
        ),
        "best_for": ["summary", "concept", "definition"],
        "max_items": 6,
        "visual_weight": {"center": 0.35, "branches": 0.45, "details": 0.10, "decoration": 0.10}
    },
    "timeline_path": {
        "name": "时间线路径",
        "description": "线性时间/因果链条展示",
        "layout": "horizontal_timeline",
        "prompt_template": (
            "Layout: HORIZONTAL TIMELINE with a winding path from left to right. "
            "Each checkpoint is a circle with an icon inside. Between checkpoints, "
            "the path has subtle arrows. Labels above/below alternate. "
            "Start point is small, end point is a star/trophy. "
            "Background has a gentle gradient from dawn colors (left) to sunset (right)."
        ),
        "best_for": ["history", "process", "story"],
        "max_items": 5,
        "visual_weight": {"title": 0.10, "checkpoints": 0.60, "path": 0.15, "decoration": 0.15}
    },
    "layered_stack": {
        "name": "层级堆叠图",
        "description": "从基础到高级的层级结构",
        "layout": "pyramid_or_layers",
        "prompt_template": (
            "Layout: LAYERED STACK / PYRAMID. Bottom layer is widest = FOUNDATION "
            "(basic concept). Each layer above is narrower = more advanced. "
            "3-4 layers total. Each layer has distinct pastel color and large label. "
            "Left side has a vertical bracket showing difficulty progression ↑. "
            "Top layer glows slightly = TARGET KNOWLEDGE."
        ),
        "best_for": ["knowledge_hierarchy", "progressive_learning"],
        "max_items": 4,
        "visual_weight": {"title": 0.10, "layers": 0.65, "labels": 0.15, "decoration": 0.10}
    },
    "cause_effect": {
        "name": "因果链图",
        "description": "原因→过程→结果的因果关系",
        "layout": "left_to_right_chain",
        "prompt_template": (
            "Layout: CAUSE-EFFECT CHAIN. Three large blocks arranged left→center→right. "
            "Left block (warm orange): CAUSE/PROBLEM. Center block (blue): PROCESS/METHOD. "
            "Right block (green): RESULT/ANSWER. Thick arrows connect them. "
            "Each block has an icon at top and text below. "
            "Below the chain, a thin strip shows the KEY TAKEAWAY."
        ),
        "best_for": ["problem_solving", "reasoning", "application"],
        "max_items": 3,
        "visual_weight": {"title": 0.10, "blocks": 0.60, "arrows": 0.10, "takeaway": 0.15, "decoration": 0.05}
    },
    "flashcard_duo": {
        "name": "闪卡双面",
        "description": "问题面+答案面的翻转效果",
        "layout": "front_back_card",
        "prompt_template": (
            "Layout: TWO OVERLAPPING CARDS with slight rotation (3°). "
            "Front card (slightly behind, tilted): shows QUESTION in large text. "
            "Back card (foreground, straight): shows ANSWER with explanation. "
            "Both cards have rounded corners and subtle shadow. "
            "Front uses warm tone, back uses cool tone. "
            "A curved 'flip' arrow connects them."
        ),
        "best_for": ["vocabulary", "character", "definition_recall"],
        "max_items": 2,
        "visual_weight": {"question": 0.35, "answer": 0.45, "decoration": 0.20}
    },
    "checklist_board": {
        "name": "清单看板",
        "description": "勾选式要点列表",
        "layout": "vertical_checklist",
        "prompt_template": (
            "Layout: CHECKLIST/BOARD style like a sticky note board. "
            "Title at top with pushpin/tape decoration. "
            "Below: 3-5 items, each with a checkbox (☑ or ☐) and concise text. "
            "Items alternate light/dark row backgrounds. "
            "Most important items have ☑ checked and GOLD highlight. "
            "Bottom has a motivational micro-text. Notebook paper texture background."
        ),
        "best_for": ["summary_checklist", "exam_prep", "health_tips"],
        "max_items": 5,
        "visual_weight": {"title": 0.15, "items": 0.65, "decoration": 0.20}
    },
    "analogy_bridge": {
        "name": "类比桥接图",
        "description": "从熟悉事物到新概念的映射",
        "layout": "dual_zone_bridge",
        "prompt_template": (
            "Layout: TWO ZONES with a BRIDGE connecting them. "
            "Left zone (圆角矩形, warm): shows a FAMILIAR real-life scene as cartoon. "
            "Right zone (圆角矩形, cool): shows the ABSTRACT concept/formula. "
            "A decorative bridge/rainbow/arrow connects matching elements between zones. "
            "Labels: left = '生活中' right = '知识中'. "
            "Matching pairs connected by dotted lines with '=' signs."
        ),
        "best_for": ["abstract_concept", "definition", "principle"],
        "max_items": 3,
        "visual_weight": {"familiar": 0.35, "abstract": 0.35, "bridge": 0.15, "decoration": 0.15}
    },
    "challenge_arena": {
        "name": "挑战竞技场",
        "description": "游戏化挑战/BOSS风格",
        "layout": "game_ui",
        "prompt_template": (
            "Layout: GAME CHALLENGE interface. Top: difficulty stars (★★★☆☆) and "
            "level banner. Center: the problem presented as a CHALLENGE CARD with "
            "dramatic border and glow. Below: SOLUTION shown as combo attack moves "
            "(STEP1→STEP2→FINISH!). Bottom: VICTORY badge with score. "
            "Dark background with neon accents. Gaming font style."
        ),
        "best_for": ["exam_challenge", "difficult_problem", "speed_test"],
        "max_items": 4,
        "visual_weight": {"challenge": 0.25, "solution": 0.45, "badges": 0.15, "decoration": 0.15}
    },
    "story_comic": {
        "name": "故事漫画",
        "description": "2-3帧漫画叙事",
        "layout": "comic_panels",
        "prompt_template": (
            "Layout: COMIC STRIP with 2-3 panels side by side. "
            "Panel 1: cute character discovers a problem (surprised expression). "
            "Panel 2: character tries the method (thinking expression). "
            "Panel 3: character succeeds (happy expression) with knowledge point "
            "highlighted in a glowing speech bubble. Comic-style borders, "
            "hand-drawn feel, warm colors, subtle halftone dots."
        ),
        "best_for": ["story", "culture", "emotion", "life_application"],
        "max_items": 3,
        "visual_weight": {"panels": 0.70, "speech_bubble": 0.15, "decoration": 0.15}
    },
    "formula_card": {
        "name": "公式展示卡",
        "description": "大字公式+注解的卡片",
        "layout": "centered_hero",
        "prompt_template": (
            "Layout: HERO FORMULA design. Center 60%: the FORMULA in EXTRA LARGE "
            "bold text on a contrasting background panel. Surrounding the formula: "
            "small annotation arrows pointing to each part with brief labels. "
            "Top: topic title. Bottom: one application example in smaller text. "
            "Background has subtle mathematical symbols watermark. "
            "Formula panel has gradient border and soft shadow."
        ),
        "best_for": ["formula", "rule", "theorem"],
        "max_items": 3,
        "visual_weight": {"formula": 0.45, "annotations": 0.25, "example": 0.20, "decoration": 0.10}
    }
}


# ────────────────────────────────────────────────────
# 2. 卡片类型 → 视觉模式映射
# ────────────────────────────────────────────────────

CARD_TYPE_VISUAL_MAP = {
    "方法卡": {
        "primary": "step_flow",
        "alternatives": ["cause_effect", "formula_card"],
        "info_hierarchy": ["title", "steps", "answer", "formula", "tip"]
    },
    "易错题卡": {
        "primary": "split_compare",
        "alternatives": ["challenge_arena", "cause_effect"],
        "info_hierarchy": ["title", "wrong_answer", "correct_answer", "error_reason", "tip"]
    },
    "计算零失误卡": {
        "primary": "step_flow",
        "alternatives": ["formula_card", "challenge_arena"],
        "info_hierarchy": ["title", "calculation_process", "answer", "verification", "tip"]
    },
    "生字卡": {
        "primary": "flashcard_duo",
        "alternatives": ["analogy_bridge", "concept_bubble"],
        "info_hierarchy": ["character", "pinyin", "meaning", "usage", "mnemonic"]
    },
    "阅读理解卡": {
        "primary": "step_flow",
        "alternatives": ["checklist_board", "cause_effect"],
        "info_hierarchy": ["title", "method_steps", "template", "keywords", "tip"]
    },
    "语法辨析卡": {
        "primary": "split_compare",
        "alternatives": ["flashcard_duo", "checklist_board"],
        "info_hierarchy": ["grammar_rule", "correct_example", "wrong_example", "comparison", "mnemonic"]
    },
    "单词卡": {
        "primary": "flashcard_duo",
        "alternatives": ["analogy_bridge", "concept_bubble"],
        "info_hierarchy": ["word", "pronunciation", "meaning", "example_sentence", "mnemonic"]
    },
    "考卷真题卡": {
        "primary": "challenge_arena",
        "alternatives": ["step_flow", "cause_effect"],
        "info_hierarchy": ["question", "solution_steps", "answer", "scoring_criteria", "variant"]
    },
    "知识总结卡": {
        "primary": "concept_bubble",
        "alternatives": ["checklist_board", "layered_stack"],
        "info_hierarchy": ["topic", "key_concepts", "formulas", "connections", "exam_tips"]
    },
    "养生卡": {
        "primary": "checklist_board",
        "alternatives": ["story_comic", "cause_effect"],
        "info_hierarchy": ["title", "core_advice", "method", "cautions", "benefit"]
    },
    "国学卡": {
        "primary": "story_comic",
        "alternatives": ["timeline_path", "analogy_bridge"],
        "info_hierarchy": ["original_text", "translation", "story", "modern_lesson", "source"]
    },
    "情感卡": {
        "primary": "story_comic",
        "alternatives": ["checklist_board", "analogy_bridge"],
        "info_hierarchy": ["core_insight", "practical_tips", "scenario", "emotional_hook", "self_care"]
    }
}


# ────────────────────────────────────────────────────
# 3. 智能信息分层 (Information Layering)
# ────────────────────────────────────────────────────

# 信息优先级定义
INFO_PRIORITY = {
    # Priority 1: 必须出现在图中 (大字/核心区)
    "P1_CRITICAL": {
        "fields": ["title", "answer", "formula"],
        "visual_treatment": "最大字号, 最鲜艳颜色, 中心位置",
        "char_allocation": 6  # 15字中分配6字
    },
    # Priority 2: 应该出现 (中等字号/次要区)
    "P2_IMPORTANT": {
        "fields": ["steps", "question", "memory_tip", "grammar_rule"],
        "visual_treatment": "中等字号, 柔和颜色, 围绕核心",
        "char_allocation": 6
    },
    # Priority 3: 可以出现 (小字/边缘)
    "P3_SUPPLEMENTARY": {
        "fields": ["definition", "core_points", "trap_point"],
        "visual_treatment": "小字号, 淡色, 边缘或底部",
        "char_allocation": 3
    },
    # Priority 4: 不在图中显示 (仅影响图片整体设计)
    "P4_CONTEXTUAL": {
        "fields": ["emotion_hook", "related", "difficulty", "importance"],
        "visual_treatment": "不显示文字, 但影响配色/风格选择",
        "char_allocation": 0
    }
}


def analyze_info_layers(card: Dict, card_type: str) -> Dict:
    """
    分析卡片信息层级，决定每个部分的视觉优先级
    
    Returns: {
        'layers': [
            {'field': str, 'priority': str, 'content': str, 
             'char_count': int, 'visual_treatment': str,
             'compressed': str}  # 15字符限制下的压缩版
        ],
        'total_source_chars': int,
        'compression_ratio': float,
        'visual_budget': {field: allocated_chars}
    }
    """
    type_config = CARD_TYPE_VISUAL_MAP.get(card_type, {})
    hierarchy = type_config.get('info_hierarchy', [
        "title", "steps", "answer", "tip"
    ])
    
    layers = []
    
    # 卡片字段到信息内容的映射
    field_content_map = {
        "title": card.get('title', ''),
        "answer": card.get('example', {}).get('answer', ''),
        "formula": '',  # 从core_points中提取公式
        "steps": ' → '.join(str(s) for s in card.get('example', {}).get('steps', [])),
        "question": card.get('example', {}).get('question', ''),
        "memory_tip": card.get('memory_tip', ''),
        "grammar_rule": '',  # 从definition提取
        "definition": card.get('definition', ''),
        "core_points": ' | '.join(str(cp) for cp in card.get('core_points', [])),
        "trap_point": card.get('trap_point', ''),
        "emotion_hook": card.get('emotion_hook', ''),
        "character": card.get('title', ''),  # 生字卡的主字
        "pinyin": '',
        "meaning": card.get('definition', ''),
        "word": card.get('title', ''),
        "pronunciation": '',
        "correct_example": '',
        "wrong_example": '',
        "correct_answer": card.get('example', {}).get('answer', ''),
        "wrong_answer": '',
    }
    
    # 从mistakes提取错误示范
    mistakes = card.get('mistakes', [])
    if mistakes:
        field_content_map['wrong_answer'] = str(mistakes[0].get('wrong', ''))
        field_content_map['wrong_example'] = str(mistakes[0].get('wrong', ''))
        field_content_map['correct_example'] = str(mistakes[0].get('correct', ''))
    
    # 公式检测
    all_text = json.dumps(card, ensure_ascii=False)
    formulas = re.findall(r'[A-Za-z]+\s*[=×÷+\-]\s*[A-Za-z0-9×÷+\-]+', all_text)
    if formulas:
        field_content_map['formula'] = formulas[0]
    
    # 按hierarchy顺序分配优先级
    total_source = 0
    for i, field in enumerate(hierarchy):
        content = field_content_map.get(field, '')
        if not content:
            continue
        
        char_count = len(str(content))
        total_source += char_count
        
        # 确定优先级
        if i < 2:
            priority = "P1_CRITICAL"
        elif i < 4:
            priority = "P2_IMPORTANT"
        else:
            priority = "P3_SUPPLEMENTARY"
        
        # 生成压缩版 (用于图片中的中文文字)
        compressed = _compress_text(content, field, priority)
        
        layers.append({
            "field": field,
            "priority": priority,
            "content": content[:100],
            "char_count": char_count,
            "visual_treatment": INFO_PRIORITY[priority]["visual_treatment"],
            "compressed": compressed
        })
    
    # 视觉字符预算
    visual_budget = {}
    remaining = 15
    for layer in layers:
        alloc = INFO_PRIORITY[layer['priority']]['char_allocation']
        actual = min(alloc, remaining, len(layer['compressed']))
        visual_budget[layer['field']] = actual
        remaining -= actual
    
    return {
        "layers": layers,
        "total_source_chars": total_source,
        "compression_ratio": round(15 / max(total_source, 1), 3),
        "visual_budget": visual_budget
    }


# ────────────────────────────────────────────────────
# 4. 15字符智能压缩 (Smart Text Compression)
# ────────────────────────────────────────────────────

# 常见缩写规则
COMPRESSION_RULES = {
    # 数学术语缩写
    "三角形": "△",
    "平行四边形": "▱",
    "正方形": "□",
    "长方形": "▭",
    "圆形": "○",
    "乘以": "×",
    "除以": "÷",
    "等于": "=",
    "大于": ">",
    "小于": "<",
    "不等于": "≠",
    "约等于": "≈",
    "平方": "²",
    "立方": "³",
    "的平方": "²",
    "的立方": "³",
    "加上": "+",
    "减去": "-",
    "面积": "S",
    "周长": "C",
    "体积": "V",
    "半径": "r",
    "直径": "d",
    "底面积": "S底",
    "高": "h",
    "长": "a",
    "宽": "b",
    
    # 通用缩写
    "例如": "如",
    "比如": "如",
    "因此": "∴",
    "所以": "∴",
    "因为": "∵",
    "并且": "&",
    "或者": "/",
    "厘米": "cm",
    "分米": "dm",
    "毫米": "mm",
    "千米": "km",
    "千克": "kg",
    "平方米": "m²",
    "平方厘米": "cm²",
}

# 可删除的虚词
REMOVABLE_WORDS = ['的', '了', '着', '过', '呢', '啊', '吧', '吗', '很', '非常',
                    '比较', '一定', '要', '需要', '必须', '肯定', '已经', '正在']


def _compress_text(text: str, field_type: str, priority: str) -> str:
    """
    将文本智能压缩到适合卡片显示的长度
    
    Args:
        text: 原始文本
        field_type: 字段类型 (title/answer/steps/...)
        priority: 优先级 (P1/P2/P3/P4)
    
    Returns: 压缩后的文本
    """
    if not text:
        return ""
    
    text = str(text)
    
    # P4不显示文字
    if priority == "P4_CONTEXTUAL":
        return ""
    
    # 目标长度
    target_len = {
        "P1_CRITICAL": 4,
        "P2_IMPORTANT": 4,
        "P3_SUPPLEMENTARY": 3,
    }.get(priority, 3)
    
    # 如果已经够短
    if len(text) <= target_len:
        return text
    
    # 步骤1: 应用符号替换
    compressed = text
    for full, short in COMPRESSION_RULES.items():
        compressed = compressed.replace(full, short)
    
    if len(compressed) <= target_len:
        return compressed
    
    # 步骤2: 删除虚词
    for word in REMOVABLE_WORDS:
        compressed = compressed.replace(word, '')
    
    if len(compressed) <= target_len:
        return compressed
    
    # 步骤3: 提取核心词
    # 对于title: 取前N个字
    if field_type in ('title', 'character', 'word'):
        return compressed[:target_len]
    
    # 对于answer: 取数字+单位
    if field_type in ('answer', 'correct_answer'):
        numbers = re.findall(r'[\d.]+\s*[a-zA-Z%°℃个只条元]?', compressed)
        if numbers:
            return numbers[0][:target_len]
        return compressed[:target_len]
    
    # 对于steps: 取关键动词
    if field_type in ('steps',):
        # 取第一个动词短语
        verbs = re.findall(r'[\u4e00-\u9fff]{2,4}', compressed)
        if verbs:
            return verbs[0][:target_len]
    
    # 默认: 截取
    return compressed[:target_len]


def compress_for_manifest(card: Dict, card_type: str) -> Dict:
    """
    为TEXT_MANIFEST生成15字符以内的中文文字集
    
    Returns: {
        'manifest_suggestion': [
            {'text': str, 'role': 'title'|'key'|'accent'|'tip', 
             'max_chars': int, 'source_field': str}
        ],
        'total_chinese_chars': int,
        'within_limit': bool
    }
    """
    info_layers = analyze_info_layers(card, card_type)
    
    manifest = []
    total_chars = 0
    
    for layer in info_layers['layers']:
        if layer['priority'] == "P4_CONTEXTUAL":
            continue
        
        compressed = layer['compressed']
        if not compressed:
            continue
        
        # 角色映射
        role_map = {
            "P1_CRITICAL": "title" if layer['field'] in ('title', 'character', 'word') else "key",
            "P2_IMPORTANT": "key",
            "P3_SUPPLEMENTARY": "accent"
        }
        role = role_map.get(layer['priority'], "accent")
        
        max_chars = info_layers['visual_budget'].get(layer['field'], 3)
        final_text = compressed[:max_chars] if max_chars > 0 else ""
        
        if final_text:
            manifest.append({
                "text": final_text,
                "role": role,
                "max_chars": max_chars,
                "source_field": layer['field']
            })
            total_chars += len(final_text)
    
    return {
        "manifest_suggestion": manifest,
        "total_chinese_chars": total_chars,
        "within_limit": total_chars <= 15
    }


# ────────────────────────────────────────────────────
# 5. 记忆策略匹配库 (Memory Strategy Library)
# ────────────────────────────────────────────────────

MEMORY_STRATEGIES = {
    "谐音法": {
        "applicable_to": ["单词卡", "生字卡"],
        "description": "利用发音相似的词语建立联想",
        "prompt_hint": "Include a phonetic similarity hint as a small speech bubble, "
                       "e.g. 'sounds like...' or '谐音: ...'",
        "example": "ambulance → '俺不能死' (谐音联想)",
        "effectiveness_for": {"vocabulary": 0.85, "character": 0.75, "formula": 0.40}
    },
    "口诀法": {
        "applicable_to": ["方法卡", "计算零失误卡", "知识总结卡"],
        "description": "编成朗朗上口的韵律口诀",
        "prompt_hint": "Feature a RHYMING MNEMONIC in a decorative ribbon/banner "
                       "at bottom of card. Use rhythm-like layout (2-4 equal phrases).",
        "example": "正正得正，负负得正，一正一负取绝大，符号跟着大来跑",
        "effectiveness_for": {"formula": 0.90, "rule": 0.85, "vocabulary": 0.60}
    },
    "图式法": {
        "applicable_to": ["生字卡", "方法卡", "概念卡"],
        "description": "把知识转化为图形/图像记忆",
        "prompt_hint": "Transform the key concept into a VISUAL METAPHOR or PICTORIAL "
                       "representation. Show the abstract idea as a concrete shape/scene.",
        "example": "'休' → 人靠在木头上休息 (字形联想)",
        "effectiveness_for": {"character": 0.90, "concept": 0.80, "vocabulary": 0.70}
    },
    "故事法": {
        "applicable_to": ["国学卡", "情感卡", "养生卡"],
        "description": "用微故事包裹知识点",
        "prompt_hint": "Present the knowledge through a MINI-STORY with character, "
                       "conflict, and resolution. Use 2-3 comic panels.",
        "example": "孟母三迁 → 通过搬家3次的故事讲述环境对成长的影响",
        "effectiveness_for": {"culture": 0.95, "emotion": 0.85, "health": 0.75}
    },
    "对比法": {
        "applicable_to": ["易错题卡", "语法辨析卡"],
        "description": "通过对比差异加深印象",
        "prompt_hint": "Emphasize DIFFERENCES by placing contrasting elements side-by-side. "
                       "Use color coding: green=correct, red=incorrect.",
        "example": "in/on/at → in大范围, on接触面, at精确点",
        "effectiveness_for": {"grammar": 0.90, "error": 0.85, "distinction": 0.90}
    },
    "关联法": {
        "applicable_to": ["知识总结卡", "方法卡"],
        "description": "将新知识与已知知识建立连接",
        "prompt_hint": "Add BRIDGE ARROWS connecting the new concept to something "
                       "the student already knows. Show 'you know X → this is similar' pattern.",
        "example": "平行四边形面积 = 底×高 ← 和长方形面积(长×宽)是亲兄弟！",
        "effectiveness_for": {"concept": 0.85, "formula": 0.80, "method": 0.75}
    },
    "首字母法": {
        "applicable_to": ["知识总结卡", "语法辨析卡"],
        "description": "关键词首字母组合成易记词",
        "prompt_hint": "Create an ACRONYM from key points and display it prominently. "
                       "Each letter expands to the full term below.",
        "example": "HOMES = Huron, Ontario, Michigan, Erie, Superior (五大湖)",
        "effectiveness_for": {"summary": 0.75, "list": 0.80, "vocabulary": 0.65}
    },
    "场景法": {
        "applicable_to": ["养生卡", "情感卡", "单词卡"],
        "description": "放入具体生活场景中理解",
        "prompt_hint": "Show the knowledge in a REAL-LIFE SCENE. Draw a familiar setting "
                       "(kitchen, classroom, park) where this knowledge applies.",
        "example": "early bird catches the worm → 早起的鸟儿有虫吃 (公园场景)",
        "effectiveness_for": {"health": 0.85, "emotion": 0.80, "vocabulary": 0.75}
    }
}


def match_memory_strategy(card: Dict, card_type: str, subject: str = "") -> Dict:
    """
    为卡片匹配最佳记忆策略
    
    Returns: {
        'primary_strategy': str,
        'strategy_detail': dict,
        'prompt_hint': str,
        'fallback_strategy': str,
        'existing_mnemonic_analysis': str
    }
    """
    # 找出适用于该卡片类型的策略
    applicable = {}
    for strategy_name, strategy in MEMORY_STRATEGIES.items():
        if card_type in strategy['applicable_to']:
            # 计算该策略对当前内容的有效性
            effectiveness = 0.5  # 默认
            for content_type, eff in strategy['effectiveness_for'].items():
                if _content_type_matches(card, card_type, subject, content_type):
                    effectiveness = max(effectiveness, eff)
            applicable[strategy_name] = {
                **strategy,
                "calculated_effectiveness": effectiveness
            }
    
    if not applicable:
        # 默认使用关联法
        applicable["关联法"] = {**MEMORY_STRATEGIES["关联法"], "calculated_effectiveness": 0.6}
    
    # 按有效性排序
    sorted_strategies = sorted(
        applicable.items(), 
        key=lambda x: x[1]['calculated_effectiveness'], 
        reverse=True
    )
    
    primary = sorted_strategies[0]
    fallback = sorted_strategies[1] if len(sorted_strategies) > 1 else sorted_strategies[0]
    
    # 分析现有memory_tip
    existing_tip = card.get('memory_tip', '')
    existing_analysis = "无memory_tip"
    if existing_tip:
        for sname, sdata in MEMORY_STRATEGIES.items():
            for kw in sdata.get('applicable_to', []):
                if any(k in existing_tip for k in ['谐音', '像', '口诀', '故事', '对比', '联想']):
                    existing_analysis = f"当前使用: {sname}"
                    break
        if existing_analysis == "无memory_tip":
            existing_analysis = f"当前有memory_tip但策略不明确: '{existing_tip[:30]}'"
    
    return {
        "primary_strategy": primary[0],
        "strategy_detail": primary[1],
        "prompt_hint": primary[1]['prompt_hint'],
        "fallback_strategy": fallback[0],
        "existing_mnemonic_analysis": existing_analysis,
        "all_applicable": {k: v['calculated_effectiveness'] for k, v in sorted_strategies}
    }


def _content_type_matches(card, card_type, subject, content_type):
    """检查内容是否匹配某种内容分类"""
    mapping = {
        "vocabulary": card_type in ("单词卡",) or subject == "英语",
        "character": card_type in ("生字卡",) or subject == "语文",
        "formula": bool(re.search(r'[=×÷+\-]', json.dumps(card, ensure_ascii=False))),
        "rule": card_type in ("方法卡", "语法辨析卡"),
        "concept": card_type in ("方法卡", "知识总结卡"),
        "grammar": card_type in ("语法辨析卡",) or subject == "英语",
        "error": card_type in ("易错题卡",),
        "distinction": card_type in ("语法辨析卡", "易错题卡"),
        "culture": card_type in ("国学卡",) or subject == "国学",
        "emotion": card_type in ("情感卡",) or subject == "情感",
        "health": card_type in ("养生卡",) or subject == "养生",
        "summary": card_type in ("知识总结卡",),
        "list": len(card.get('core_points', [])) >= 3,
        "method": card_type in ("方法卡", "阅读理解卡"),
    }
    return mapping.get(content_type, False)


# ────────────────────────────────────────────────────
# 6. 综合蓝图生成 (Full Blueprint)
# ────────────────────────────────────────────────────

def generate_visual_blueprint(card: Dict, card_type: str, 
                               subject: str = "", grade: str = "") -> Dict:
    """
    生成完整的知识呈现蓝图
    
    Returns: {
        'visual_pattern': {...},       # 选定的视觉模式
        'info_layers': {...},          # 信息分层分析
        'memory_strategy': {...},      # 记忆策略
        'manifest_suggestion': {...},  # TEXT_MANIFEST建议
        'blueprint_prompt': str,       # 综合蓝图prompt注入
        'blueprint_score': float       # 蓝图质量评分
    }
    """
    # 1. 选择视觉模式
    type_visual = CARD_TYPE_VISUAL_MAP.get(card_type, {})
    primary_pattern_id = type_visual.get('primary', 'step_flow')
    
    # 内容特征分析可能修改pattern选择
    pattern_id = _select_best_pattern(card, card_type, primary_pattern_id)
    visual_pattern = VISUAL_PATTERNS.get(pattern_id, VISUAL_PATTERNS['step_flow'])
    
    # 2. 信息分层
    info_layers = analyze_info_layers(card, card_type)
    
    # 3. 记忆策略
    memory = match_memory_strategy(card, card_type, subject)
    
    # 4. 文字压缩建议
    manifest = compress_for_manifest(card, card_type)
    
    # 5. 组装综合蓝图Prompt
    blueprint_parts = []
    
    # 视觉布局指令
    blueprint_parts.append(
        f"=== VISUAL BLUEPRINT: {visual_pattern['name']} ===\n"
        f"{visual_pattern['prompt_template']}\n"
        f"=== END LAYOUT ==="
    )
    
    # 信息层级指令
    if info_layers['layers']:
        p1_items = [l for l in info_layers['layers'] if l['priority'] == 'P1_CRITICAL']
        p2_items = [l for l in info_layers['layers'] if l['priority'] == 'P2_IMPORTANT']
        
        if p1_items:
            p1_desc = ', '.join(f"{l['field']}='{l['compressed']}'" for l in p1_items if l['compressed'])
            blueprint_parts.append(f"VISUAL PRIORITY 1 (largest, center): {p1_desc}")
        if p2_items:
            p2_desc = ', '.join(f"{l['field']}='{l['compressed']}'" for l in p2_items if l['compressed'])
            blueprint_parts.append(f"VISUAL PRIORITY 2 (medium, surrounding): {p2_desc}")
    
    # 记忆策略指令
    blueprint_parts.append(f"MEMORY AID: {memory['prompt_hint']}")
    
    blueprint_prompt = '\n'.join(blueprint_parts)
    
    # 6. 蓝图质量评分
    score = _score_blueprint(card, visual_pattern, info_layers, memory, manifest)
    
    return {
        "visual_pattern": {
            "id": pattern_id,
            "name": visual_pattern['name'],
            "layout": visual_pattern['layout'],
            "visual_weight": visual_pattern.get('visual_weight', {})
        },
        "info_layers": info_layers,
        "memory_strategy": memory,
        "manifest_suggestion": manifest,
        "blueprint_prompt": blueprint_prompt,
        "blueprint_score": score
    }


def _select_best_pattern(card: Dict, card_type: str, primary_id: str) -> str:
    """根据内容特征微调视觉模式选择"""
    text = json.dumps(card, ensure_ascii=False)
    
    steps = card.get('example', {}).get('steps', [])
    mistakes = card.get('mistakes', [])
    core_points = card.get('core_points', [])
    
    # 如果有对比内容但primary不是对比模式
    if mistakes and primary_id not in ('split_compare',):
        if card_type in ('易错题卡', '语法辨析卡'):
            return 'split_compare'
    
    # 如果有很多步骤
    if len(steps) >= 4 and primary_id not in ('step_flow',):
        return 'step_flow'
    
    # 如果是公式为主
    formulas = re.findall(r'[A-Za-z]+\s*[=]\s*[A-Za-z0-9×÷+\-]+', text)
    if formulas and primary_id not in ('formula_card', 'step_flow'):
        return 'formula_card'
    
    # 如果知识点很多(适合气泡图)
    if len(core_points) >= 4 and primary_id not in ('concept_bubble', 'checklist_board'):
        return 'concept_bubble'
    
    return primary_id


def _score_blueprint(card, pattern, info_layers, memory, manifest) -> float:
    """评估蓝图质量"""
    score = 70  # 基准
    
    # 信息层级清晰度
    if info_layers['layers']:
        p1_count = sum(1 for l in info_layers['layers'] if l['priority'] == 'P1_CRITICAL')
        if 1 <= p1_count <= 2:
            score += 10  # 核心信息1-2个最好
        elif p1_count > 3:
            score -= 5  # 核心太多
    
    # 文字在限制内
    if manifest['within_limit']:
        score += 10
    else:
        score -= 10
    
    # 有记忆策略
    if memory['primary_strategy'] != "关联法":  # 非默认
        score += 5
    
    # 有现有mnemonic
    if card.get('memory_tip'):
        score += 5
    
    return min(100, max(0, round(score, 1)))


# ────────────────────────────────────────────────────
# 7. 模块导出
# ────────────────────────────────────────────────────

__all__ = [
    'VISUAL_PATTERNS', 'CARD_TYPE_VISUAL_MAP',
    'INFO_PRIORITY', 'MEMORY_STRATEGIES',
    'COMPRESSION_RULES',
    'analyze_info_layers', 'compress_for_manifest',
    'match_memory_strategy', 'generate_visual_blueprint',
]
