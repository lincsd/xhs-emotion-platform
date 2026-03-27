# -*- coding: utf-8 -*-
"""
内容设计引擎 (Content Design Engine)
====================================
在 JSON 卡片数据 → 图片 Prompt 之间加入「教学设计」中间层。

三大子系统:
  1. 认知负荷优化器 — 自动分析卡片信息密度，超载时建议拆分
  2. 教学策略匹配器 — 12卡类 × 6教学模式 = 72种精准路径
  3. 单元序列检查器 — 确保同一unit内卡片构成学习阶梯

作者: AI Auto-Arch    版本: 2026-03-26
"""

import json, re, os, sqlite3, hashlib, time
from typing import Dict, List, Tuple, Optional, Any

# ────────────────────────────────────────────────────
# 1. 教学策略库 (Teaching Strategy Library)
# ────────────────────────────────────────────────────

# 六种核心教学模式
TEACHING_MODES = {
    "对比式": {
        "id": "contrast",
        "description": "通过错误vs正确、概念A vs 概念B对比引发认知冲突",
        "visual_pattern": "双栏对比布局，左红(✗)右绿(✓)，中间分割线",
        "cognitive_hook": "先呈现常见错误，触发'我也这样做'的共鸣，再揭示正确答案",
        "best_for": ["对比", "纠错", "辨析", "区分"],
        "prompt_injection": (
            "Use a SPLIT-SCREEN layout: LEFT side shows the WRONG approach with "
            "red cross mark (✗), RIGHT side shows the CORRECT approach with green "
            "checkmark (✓). A bold dividing line separates them. The wrong side should "
            "look slightly messy/scratched, the correct side clean and highlighted."
        )
    },
    "递进式": {
        "id": "progressive",
        "description": "从简单到复杂，逐步搭建知识脚手架",
        "visual_pattern": "阶梯式从下到上布局，每级一个知识层次",
        "cognitive_hook": "每个步骤都在前一步基础上扩展，让学生感受掌握的成就感",
        "best_for": ["方法", "步骤", "计算", "公式推导"],
        "prompt_injection": (
            "Use a STAIRCASE/STEP layout flowing from bottom-left to top-right. "
            "Each step is a rounded block, numbered ①②③, with an arrow connecting "
            "to the next. Color intensity increases with each step (light→deep). "
            "The final step is the LARGEST and brightest, showing the answer/conclusion."
        )
    },
    "发现式": {
        "id": "discovery",
        "description": "设置悬念→抛问题→引导推理→揭示规律",
        "visual_pattern": "问号开场→推理线索→'原来如此！'揭晓",
        "cognitive_hook": "利用好奇心驱动学习，让学生自己推导出结论",
        "best_for": ["规律发现", "数学思维", "逻辑推理"],
        "prompt_injection": (
            "Start with a BIG QUESTION MARK and an intriguing question at top. "
            "Middle section shows 2-3 visual CLUES (patterns, examples) with "
            "magnifying glass icons. Bottom reveals the RULE/ANSWER with a lightbulb "
            "emoji and 'eureka!' feeling. Use mystery-themed colors (deep blue→gold)."
        )
    },
    "类比式": {
        "id": "analogy",
        "description": "用熟悉事物解释陌生概念，建立认知桥梁",
        "visual_pattern": "生活场景→抽象概念的映射图",
        "cognitive_hook": "用学生已知的经验解释未知概念，降低理解门槛",
        "best_for": ["抽象概念", "定义理解", "原理解释"],
        "prompt_injection": (
            "Split into TWO ZONES connected by a BRIDGE/ARROW: LEFT zone shows a "
            "familiar real-life scene (cartoon style), RIGHT zone shows the abstract "
            "concept/formula. A dotted bridge connects matching elements. Add labels "
            "'生活中的...' on left and '数学中的...' on right."
        )
    },
    "故事式": {
        "id": "narrative",
        "description": "将知识点嵌入生动小故事/场景中",
        "visual_pattern": "漫画分格叙事，2-3帧讲述微故事",
        "cognitive_hook": "故事记忆比纯知识记忆强10倍，情景化让知识'活'起来",
        "best_for": ["文化知识", "历史典故", "生活应用", "情感共鸣"],
        "prompt_injection": (
            "Use COMIC PANEL layout with 2-3 frames telling a mini-story. Frame 1: "
            "a cute character encounters a problem. Frame 2: character tries/discovers. "
            "Frame 3: character succeeds with the knowledge point highlighted as "
            "a glowing speech bubble. Warm storytelling colors."
        )
    },
    "挑战式": {
        "id": "challenge",
        "description": "设置'你能做到吗？'的挑战，激发竞胜心",
        "visual_pattern": "游戏化界面，BOSS关卡感，倒计时/难度星级",
        "cognitive_hook": "利用挑战心理，让学生主动投入，'打败'这道题",
        "best_for": ["真题突破", "难题攻克", "速算挑战", "易错陷阱"],
        "prompt_injection": (
            "Use GAME/CHALLENGE theme: top has a difficulty rating (★★★☆☆) and "
            "'挑战' banner. The problem is presented as a BOSS card with dramatic "
            "lighting. The solution path shows 'COMBO' steps. Bottom has a trophy "
            "or 'PASSED!' badge area. Use bold gaming colors (black/gold/red)."
        )
    }
}

# 12种卡片类型 → 最佳教学模式匹配 (优先级排序)
CARD_TYPE_STRATEGY_MAP = {
    "方法卡": {
        "primary": "递进式",
        "secondary": "类比式",
        "fallback": "发现式",
        "rationale": "方法类内容天然适合逐步拆解，从简到繁",
        "content_focus": {
            "must_show": ["解题步骤(numbered)", "公式/规则", "一个完整例题", "为什么这样做的解释(至少一步)"],
            "nice_to_have": ["变式练习提示", "常见变形"],
            "avoid": ["过多文字解释", "多个例题混杂", "只给步骤不解释原理"]
        }
    },
    "易错题卡": {
        "primary": "对比式",
        "secondary": "挑战式",
        "fallback": "发现式",
        "rationale": "对比式最能突出'错在哪→为什么错→正确是什么'的核心教学目标",
        "content_focus": {
            "must_show": ["错误示范(标红)", "正确解法(标绿)", "错因分析(为什么会错的根本原因)"],
            "nice_to_have": ["同类易错变体", "防错口诀"],
            "avoid": ["只展示正确答案不展示错误", "错因分析过长", "只标注对错不解释原因"]
        }
    },
    "计算零失误卡": {
        "primary": "递进式",
        "secondary": "对比式",
        "fallback": "挑战式",
        "rationale": "计算类需要展示清晰的步骤流程",
        "content_focus": {
            "must_show": ["清晰竖式/算式", "每步结果", "最终答案(醒目)"],
            "nice_to_have": ["验算方法", "进位/退位标记"],
            "avoid": ["跳步", "过多辅助文字覆盖算式"]
        }
    },
    "生字卡": {
        "primary": "类比式",
        "secondary": "故事式",
        "fallback": "发现式",
        "rationale": "汉字教学通过形义联想最有效",
        "content_focus": {
            "must_show": ["大字展示(笔画清晰)", "拼音+声调", "释义"],
            "nice_to_have": ["字源演变", "形近字对比", "组词"],
            "avoid": ["文字太小看不清", "过多词语挤压主字"]
        }
    },
    "阅读理解卡": {
        "primary": "递进式",
        "secondary": "发现式",
        "fallback": "类比式",
        "rationale": "阅读方法需要分步骤操作指南",
        "content_focus": {
            "must_show": ["答题步骤(numbered)", "答题模板/句式", "关键词标记法", "为什么这样答的原理"],
            "nice_to_have": ["真题示例", "得分技巧"],
            "avoid": ["大段原文", "抽象方法论", "只给模板不解释为什么有效"]
        }
    },
    "语法辨析卡": {
        "primary": "对比式",
        "secondary": "类比式",
        "fallback": "递进式",
        "rationale": "语法辨析的核心就是对比不同用法",
        "content_focus": {
            "must_show": ["语法规则(中英双语)", "完整正确例句(非孤立短语)", "完整错误例句+错因(为什么错，不只标❌)", "本质原因(语法规则背后的逻辑/中英思维差异)"],
            "nice_to_have": ["引导词对照表", "口诀(需标注例外且禁止'搭配固定'类废话)"],
            "avoid": ["纯中文解释无英文", "例句过长", "只标注对错不解释原因", "把正确用法标为错误", "废话口诀(搭配固定/多练就会)", "视觉隐喻与内容逻辑不匹配(如用阶梯图表示非递进关系)"]
        }
    },
    "易混词陷阱卡": {
        "primary": "对比式",
        "secondary": "故事式",
        "fallback": "类比式",
        "rationale": "易混词的核心是对比辨析+真实语境区分",
        "content_focus": {
            "must_show": ["两词并排对比(含词性/用法差异)", "完整对比例句(同一语境换词)", "错因分析(为什么会混：中文翻译相同? 拼写相似? 用法交叉?)"],
            "nice_to_have": ["记忆联想(有巧妙关联)", "例外情况标注"],
            "avoid": ["把正确用法标为错误", "只给中文释义不给例句", "口诀过于简化导致新错误"]
        }
    },
    "语法纠错卡": {
        "primary": "对比式",
        "secondary": "递进式",
        "fallback": "挑战式",
        "rationale": "纠错卡的核心是错误vs正确的对比+错因解释",
        "content_focus": {
            "must_show": ["完整错误句子(真实常见错误)", "完整正确句子", "错因分析(中英思维差异/母语负迁移)", "验证方法(如何自查)"],
            "nice_to_have": ["同类错误扩展", "正确率统计Hook"],
            "avoid": ["编造不真实的错误", "把正确用法标为错误", "只标对错不解释原因"]
        }
    },
    "词汇卡": {
        "primary": "类比式",
        "secondary": "故事式",
        "fallback": "对比式",
        "rationale": "词汇记忆通过联想和场景化最有效",
        "content_focus": {
            "must_show": ["单词(大字)", "音标", "词性+释义", "完整例句(贴近学生生活)"],
            "nice_to_have": ["词根词缀拆解", "联想图", "发音易错点", "搭配短语"],
            "avoid": ["堆砌多个无关单词", "例句太学术/脱离生活", "只有释义没有语境"]
        }
    },
    "考卷真题卡": {
        "primary": "挑战式",
        "secondary": "递进式",
        "fallback": "对比式",
        "rationale": "真题天然带有'挑战'属性，激发竞胜心",
        "content_focus": {
            "must_show": ["题目原文", "完整解答过程", "标准答案", "为什么这样解的原理"],
            "nice_to_have": ["评分标准", "出题意图", "同类变式"],
            "avoid": ["解题步骤跳跃", "没有答案只有题目", "只给答案不解释思路"]
        }
    },
    "知识总结卡": {
        "primary": "递进式",
        "secondary": "发现式",
        "fallback": "类比式",
        "rationale": "总结类需要层级清晰的知识结构",
        "content_focus": {
            "must_show": ["知识点树形结构", "核心公式/规则集合", "关键词高亮"],
            "nice_to_have": ["思维导图", "考点标记", "难度分级"],
            "avoid": ["知识点平铺无层次", "信息过密无留白"]
        }
    },
    "养生卡": {
        "primary": "故事式",
        "secondary": "递进式",
        "fallback": "对比式",
        "rationale": "健康知识通过生活场景讲述最易接受",
        "content_focus": {
            "must_show": ["核心健康建议(1-2条)", "操作方法", "注意事项"],
            "nice_to_have": ["科学依据简述", "禁忌提醒", "效果时间线"],
            "avoid": ["医学术语堆砌", "过度承诺效果", "恐吓式表述"]
        }
    },
    "国学卡": {
        "primary": "故事式",
        "secondary": "发现式",
        "fallback": "类比式",
        "rationale": "文化典故天然适合叙事呈现",
        "content_focus": {
            "must_show": ["原文/出处", "白话译文", "现代启示"],
            "nice_to_have": ["历史背景", "人物插图", "相关典故"],
            "avoid": ["纯文言无解释", "断章取义", "说教感过重"]
        }
    },
    "情感卡": {
        "primary": "故事式",
        "secondary": "类比式",
        "fallback": "对比式",
        "rationale": "情感内容通过共鸣场景最能打动人",
        "content_focus": {
            "must_show": ["核心观点(1句话)", "实用建议(2-3条)", "情绪共鸣点"],
            "nice_to_have": ["场景化描述", "反面案例", "心理学依据"],
            "avoid": ["空洞鸡汤", "过度说教", "负面情绪放大"]
        }
    }
}


# ────────────────────────────────────────────────────
# 2. 认知负荷模型 (Cognitive Load Model)
# ────────────────────────────────────────────────────

# 认知负荷指标权重
COGNITIVE_LOAD_WEIGHTS = {
    "text_density":     0.30,  # 文字密度 (字符数/卡片)
    "concept_count":    0.25,  # 概念数量
    "step_count":       0.15,  # 步骤数量
    "formula_complexity": 0.15,  # 公式复杂度
    "vocabulary_level": 0.15,  # 词汇难度
}

# 各年级认知负荷上限 (0-100 scale)
GRADE_LOAD_LIMITS = {
    "一上": 35, "一下": 40,
    "二上": 45, "二下": 50,
    "三上": 55, "三下": 60,
    "四上": 65, "四下": 70,
    "五上": 75, "五下": 80,
    "六上": 85, "六下": 90,
    "状语从句": 85,
    # 非学科
    "经期调理": 70, "中老年": 70, "减脂食谱": 65,
    "古代预言故事": 75,
    "恋爱": 70, "暧昧": 70, "约会": 65,
}

def _estimate_text_density(card: Dict) -> float:
    """估算卡片文字密度 (0-100)"""
    text_parts = []
    text_parts.append(card.get('title', ''))
    text_parts.append(card.get('definition', ''))
    for cp in card.get('core_points', []):
        text_parts.append(str(cp))
    ex = card.get('example', {})
    text_parts.append(ex.get('question', ''))
    for s in ex.get('steps', []):
        text_parts.append(str(s))
    text_parts.append(ex.get('answer', ''))
    text_parts.append(card.get('memory_tip', ''))
    
    total_chars = sum(len(str(t)) for t in text_parts)
    # 基准: 200字 = 50分, 400字 = 100分
    return min(100, total_chars / 4.0)


def _count_concepts(card: Dict) -> int:
    """计算卡片中的概念/知识点数量"""
    count = 0
    count += len(card.get('core_points', []))
    if card.get('definition'):
        count += 1
    if card.get('example', {}).get('question'):
        count += 1
    mistakes = card.get('mistakes', [])
    count += len(mistakes)
    if card.get('trap_point'):
        count += 1
    return count


def _estimate_formula_complexity(card: Dict) -> float:
    """估算公式复杂度 (0-100)"""
    text = json.dumps(card, ensure_ascii=False)
    # 检测数学符号密度
    math_symbols = re.findall(r'[+\-×÷=≈≠><≤≥√∑∏∫πΔ²³⁴⁵∞±]', text)
    fraction_patterns = re.findall(r'\d+/\d+', text)
    parenthesis = re.findall(r'[()（）\[\]{}]', text)
    
    score = len(math_symbols) * 3 + len(fraction_patterns) * 8 + len(parenthesis) * 2
    return min(100, score)


def _estimate_vocabulary_level(card: Dict, grade: str) -> float:
    """估算词汇难度 (0-100)"""
    text = json.dumps(card, ensure_ascii=False)
    # 高级词汇指标
    advanced_chars = len(re.findall(r'[矩阵向量微积分概率排列组合对数指数]', text))
    english_words = len(re.findall(r'[a-zA-Z]{4,}', text))
    
    # 年级越低，同样的词汇难度感受越高
    grade_multiplier = {
        "一上": 2.0, "一下": 1.8, "二上": 1.6, "二下": 1.5,
        "三上": 1.3, "三下": 1.2, "四上": 1.1, "四下": 1.0,
        "五上": 0.9, "五下": 0.85, "六上": 0.8, "六下": 0.75,
    }.get(grade, 1.0)
    
    raw = advanced_chars * 5 + english_words * 3
    return min(100, raw * grade_multiplier)


def compute_cognitive_load(card: Dict, grade: str = "") -> Dict:
    """
    计算卡片认知负荷综合评分
    
    Returns: {
        'total_load': float (0-100),
        'dimensions': {name: score},
        'grade_limit': int,
        'overloaded': bool,
        'overload_ratio': float,  # >1 means overloaded
        'suggestions': [str]
    }
    """
    text_density = _estimate_text_density(card)
    concept_count = _count_concepts(card)
    step_count = len(card.get('example', {}).get('steps', []))
    formula_comp = _estimate_formula_complexity(card)
    vocab_level = _estimate_vocabulary_level(card, grade)
    
    # 概念数归一化: 3个=50分, 6个=100分
    concept_score = min(100, concept_count / 6.0 * 100)
    # 步骤数归一化: 3步=50分, 6步=100分
    step_score = min(100, step_count / 6.0 * 100)
    
    dimensions = {
        "text_density": round(text_density, 1),
        "concept_count": round(concept_score, 1),
        "step_count": round(step_score, 1),
        "formula_complexity": round(formula_comp, 1),
        "vocabulary_level": round(vocab_level, 1),
    }
    
    # 加权总分
    total = sum(
        dimensions[k] * COGNITIVE_LOAD_WEIGHTS[k]
        for k in COGNITIVE_LOAD_WEIGHTS
    )
    total = round(total, 1)
    
    grade_limit = GRADE_LOAD_LIMITS.get(grade, 75)
    overloaded = total > grade_limit
    overload_ratio = round(total / max(grade_limit, 1), 2)
    
    suggestions = []
    if overloaded:
        # 找出最高的维度给出建议
        sorted_dims = sorted(dimensions.items(), key=lambda x: x[1], reverse=True)
        top_dim = sorted_dims[0][0]
        
        if top_dim == "text_density":
            suggestions.append("文字密度过高，建议精简解题步骤描述，合并相似步骤")
        elif top_dim == "concept_count":
            suggestions.append(f"概念数({concept_count})过多，建议拆分为核心卡+扩展卡")
        elif top_dim == "step_count":
            suggestions.append(f"步骤数({step_count})过多，建议合并简单步骤或拆分为多卡")
        elif top_dim == "formula_complexity":
            suggestions.append("公式复杂度高，建议用图解替代纯公式表达")
        elif top_dim == "vocabulary_level":
            suggestions.append("词汇难度偏高，建议用更通俗的表述替代专业术语")
        
        if concept_count > 4:
            suggestions.append(
                f"建议将{concept_count}个知识点拆为: 核心卡(保留前2个)+扩展卡(剩余{concept_count-2}个)"
            )
    
    return {
        "total_load": total,
        "dimensions": dimensions,
        "grade_limit": grade_limit,
        "overloaded": overloaded,
        "overload_ratio": overload_ratio,
        "suggestions": suggestions,
        "raw_stats": {
            "total_chars": int(text_density * 4),
            "concept_count": concept_count,
            "step_count": step_count
        }
    }


# ────────────────────────────────────────────────────
# 3. 教学策略匹配器 (Teaching Strategy Matcher)
# ────────────────────────────────────────────────────

def match_teaching_strategy(card: Dict, card_type: str, subject: str = "") -> Dict:
    """
    为卡片匹配最佳教学策略
    
    Returns: {
        'strategy': str (模式名),
        'mode': dict (TEACHING_MODES entry),
        'prompt_injection': str,  # 直接注入prompt的视觉指令
        'content_guidance': dict, # must_show / nice_to_have / avoid
        'rationale': str
    }
    """
    type_config = CARD_TYPE_STRATEGY_MAP.get(card_type)
    if not type_config:
        # 默认策略
        type_config = CARD_TYPE_STRATEGY_MAP.get("方法卡")
    
    # 分析卡片内容特征选择策略
    strategy_name = type_config["primary"]
    
    # 内容特征分析 — 可能覆盖默认策略
    card_text = json.dumps(card, ensure_ascii=False)
    
    has_comparison = bool(card.get('mistakes')) or 'vs' in card_text.lower() or '对比' in card_text
    has_story = any(kw in card_text for kw in ['故事', '典故', '传说', '曾经', '有一天'])
    has_steps = len(card.get('example', {}).get('steps', [])) >= 3
    has_challenge = any(kw in card_text for kw in ['挑战', '真题', '考试', '90%', '难倒'])
    has_abstract = any(kw in card_text for kw in ['定义', '概念', '原理', '什么是'])
    
    # 如果内容特征强烈匹配某策略，覆盖默认
    if has_comparison and strategy_name != "对比式":
        if card_type not in ("知识总结卡",):  # 总结卡不适合对比
            strategy_name = "对比式"
    elif has_story and strategy_name != "故事式":
        if card_type in ("国学卡", "情感卡", "养生卡"):
            strategy_name = "故事式"
    elif has_challenge and card_type in ("考卷真题卡",):
        strategy_name = "挑战式"
    elif has_abstract and strategy_name != "类比式":
        if card_type in ("方法卡", "生字卡"):
            strategy_name = "类比式"
    
    mode = TEACHING_MODES[strategy_name]
    
    return {
        "strategy": strategy_name,
        "mode": mode,
        "prompt_injection": mode["prompt_injection"],
        "content_guidance": type_config.get("content_focus", {}),
        "rationale": type_config.get("rationale", ""),
        "all_strategies": {
            "primary": type_config["primary"],
            "secondary": type_config["secondary"],
            "fallback": type_config["fallback"]
        }
    }


# ────────────────────────────────────────────────────
# 4. 单元序列检查器 (Unit Sequence Checker)
# ────────────────────────────────────────────────────

def check_unit_sequence(cards: List[Dict]) -> Dict:
    """
    检查同一单元内卡片的学习递进性
    
    Args:
        cards: 同一unit内的所有卡片列表
        
    Returns: {
        'is_progressive': bool,
        'sequence_score': float (0-100),
        'issues': [str],
        'suggested_order': [card_id],
        'difficulty_curve': [(card_id, difficulty)]
    }
    """
    if len(cards) <= 1:
        return {
            "is_progressive": True,
            "sequence_score": 100,
            "issues": [],
            "suggested_order": [c.get('card_id', '') for c in cards],
            "difficulty_curve": [(c.get('card_id', ''), c.get('difficulty', 3)) for c in cards]
        }
    
    issues = []
    
    # 提取难度序列
    difficulties = [(c.get('card_id', f'card_{i}'), c.get('difficulty', 3)) 
                     for i, c in enumerate(cards)]
    
    # 检查: 难度应该整体递增（允许小波动）
    diffs = [d[1] for d in difficulties]
    inversions = 0
    for i in range(1, len(diffs)):
        if diffs[i] < diffs[i-1] - 1:  # 允许降1的波动
            inversions += 1
            issues.append(
                f"卡片{difficulties[i][0]}(难度{diffs[i]})在"
                f"{difficulties[i-1][0]}(难度{diffs[i-1]})之后，难度反降"
            )
    
    # 检查: 知识点是否有prerequisite链
    prereq_chain_ok = True
    for i, card in enumerate(cards):
        related = card.get('related', {})
        prereq = related.get('prerequisite', '')
        if prereq and i > 0:
            # 检查prerequisite是否在前面的卡片中
            prev_titles = [c.get('title', '') for c in cards[:i]]
            if not any(prereq in t or t in prereq for t in prev_titles):
                prereq_chain_ok = False
                issues.append(
                    f"卡片{card.get('card_id', '')}的前置知识'{prereq}'不在之前的卡片中"
                )
    
    # 检查: 概念复杂度递增
    load_scores = []
    for card in cards:
        load = compute_cognitive_load(card)
        load_scores.append(load['total_load'])
    
    load_inversions = 0
    for i in range(1, len(load_scores)):
        if load_scores[i] < load_scores[i-1] - 10:  # 允许10分波动
            load_inversions += 1
    
    if load_inversions > len(cards) * 0.3:
        issues.append("认知负荷序列不递进，部分复杂内容出现在简单内容之前")
    
    # 检查: 内容覆盖无重复
    titles = [c.get('title', '') for c in cards]
    core_points_all = []
    for c in cards:
        core_points_all.extend(c.get('core_points', []))
    
    # 简单去重检查
    seen_points = set()
    duplicates = []
    for p in core_points_all:
        p_clean = re.sub(r'[，。、！？\s]', '', str(p))
        if len(p_clean) > 5 and p_clean in seen_points:
            duplicates.append(p)
        seen_points.add(p_clean)
    
    if duplicates:
        issues.append(f"发现{len(duplicates)}个重复知识点: {duplicates[:3]}")
    
    # 建议排序: 按difficulty + cognitive_load综合排序
    scored_cards = []
    for i, card in enumerate(cards):
        diff = card.get('difficulty', 3)
        load = load_scores[i] if i < len(load_scores) else 50
        combined = diff * 10 + load * 0.5
        scored_cards.append((card.get('card_id', f'card_{i}'), combined, diff))
    scored_cards.sort(key=lambda x: x[1])
    
    # 评分
    sequence_score = 100
    sequence_score -= inversions * 15
    sequence_score -= load_inversions * 10
    sequence_score -= len(duplicates) * 5
    if not prereq_chain_ok:
        sequence_score -= 10
    sequence_score = max(0, sequence_score)
    
    return {
        "is_progressive": sequence_score >= 70,
        "sequence_score": round(sequence_score, 1),
        "issues": issues,
        "suggested_order": [sc[0] for sc in scored_cards],
        "difficulty_curve": [(sc[0], sc[2]) for sc in scored_cards],
        "cognitive_loads": load_scores
    }


# ────────────────────────────────────────────────────
# 5. 内容设计综合报告 (Design Report)
# ────────────────────────────────────────────────────

def design_card_content(card: Dict, card_type: str, subject: str, 
                         grade: str, unit_cards: Optional[List[Dict]] = None) -> Dict:
    """
    生成完整的内容设计报告
    
    Args:
        card: 单张卡片数据
        card_type: 卡片类型
        subject: 科目
        grade: 年级
        unit_cards: 同单元其他卡片(可选)
        
    Returns: {
        'cognitive_load': {...},
        'teaching_strategy': {...},
        'unit_sequence': {...},  # 仅当提供unit_cards时
        'design_prompt_injection': str,  # 综合设计指令,直接注入prompt
        'warnings': [str],
        'design_score': float,  # 内容设计综合评分 0-100
    }
    """
    warnings = []
    
    # 1. 认知负荷分析
    cog_load = compute_cognitive_load(card, grade)
    if cog_load['overloaded']:
        warnings.append(f"⚠️ 认知负荷({cog_load['total_load']})超过年级上限({cog_load['grade_limit']})")
        warnings.extend(cog_load['suggestions'])
    
    # 2. 教学策略匹配
    strategy = match_teaching_strategy(card, card_type, subject)
    
    # 3. 单元序列检查
    unit_seq = None
    if unit_cards and len(unit_cards) > 1:
        unit_seq = check_unit_sequence(unit_cards)
        if not unit_seq['is_progressive']:
            warnings.append(f"⚠️ 单元内卡片序列递进性不足(得分{unit_seq['sequence_score']})")
            warnings.extend(unit_seq['issues'][:3])
    
    # 4. 构建综合设计Prompt注入
    design_injection_parts = []
    
    # 教学策略注入
    design_injection_parts.append(
        f"=== TEACHING STRATEGY: {strategy['strategy']} ===\n"
        f"{strategy['prompt_injection']}\n"
        f"=== END STRATEGY ==="
    )
    
    # 内容焦点注入
    guidance = strategy.get('content_guidance', {})
    if guidance.get('must_show'):
        must_items = ', '.join(guidance['must_show'][:3])
        design_injection_parts.append(
            f"MUST SHOW: {must_items}"
        )
    if guidance.get('avoid'):
        avoid_items = ', '.join(guidance['avoid'][:2])
        design_injection_parts.append(
            f"AVOID: {avoid_items}"
        )
    
    # 认知负荷调整
    if cog_load['overloaded']:
        design_injection_parts.append(
            "⚠️ COGNITIVE OVERLOAD: Simplify visuals. Show only the MOST essential "
            "information. Use visual hierarchy to let eyes focus on ONE thing first. "
            "Reduce text blocks, increase whitespace."
        )
    elif cog_load['total_load'] < 30:
        design_injection_parts.append(
            "NOTE: Content is light — add visual richness. Use larger illustrations, "
            "decorative elements, or expand the visual metaphor."
        )
    
    design_prompt_injection = '\n'.join(design_injection_parts)
    
    # 5. 设计评分
    design_score = 80  # 基准分
    
    # 认知负荷适配性 (+/-15)
    if not cog_load['overloaded']:
        design_score += 10
        if cog_load['overload_ratio'] > 0.5:  # 有一定挑战性
            design_score += 5
    else:
        design_score -= 10
        if cog_load['overload_ratio'] > 1.3:
            design_score -= 5
    
    # 教学策略匹配度 (+/-10)
    # 如果primary策略就是内容特征匹配的，+10
    type_cfg = CARD_TYPE_STRATEGY_MAP.get(card_type, {})
    if strategy['strategy'] == type_cfg.get('primary', ''):
        design_score += 5
    
    # 单元递进性 (+/-10)
    if unit_seq:
        if unit_seq['sequence_score'] >= 80:
            design_score += 5
        elif unit_seq['sequence_score'] < 50:
            design_score -= 10
    
    design_score = max(0, min(100, design_score))
    
    result = {
        "cognitive_load": cog_load,
        "teaching_strategy": strategy,
        "design_prompt_injection": design_prompt_injection,
        "warnings": warnings,
        "design_score": round(design_score, 1)
    }
    if unit_seq:
        result["unit_sequence"] = unit_seq
    
    return result


# ────────────────────────────────────────────────────
# 6. 内容拆分建议器 (Content Splitter)
# ────────────────────────────────────────────────────

def suggest_content_split(card: Dict, cog_load: Dict) -> Optional[Dict]:
    """
    当认知负荷超标时，建议如何拆分卡片
    
    Returns: None if no split needed, or {
        'should_split': True,
        'core_card': {...},  # 核心卡保留内容
        'extension_card': {...},  # 扩展卡内容
        'reason': str
    }
    """
    if not cog_load.get('overloaded'):
        return None
    
    core_points = card.get('core_points', [])
    steps = card.get('example', {}).get('steps', [])
    mistakes = card.get('mistakes', [])
    
    # 策略1: 概念太多 → 拆知识点
    if len(core_points) > 3:
        return {
            "should_split": True,
            "reason": f"知识点({len(core_points)})过多，拆为核心+扩展",
            "core_card": {
                "keep_fields": ["title", "definition", "example", "memory_tip"],
                "core_points": core_points[:2],
                "description": "保留标题、定义、例题和前2个核心知识点"
            },
            "extension_card": {
                "core_points": core_points[2:],
                "include": ["mistakes", "trap_point"] if mistakes else ["trap_point"],
                "description": f"扩展卡包含剩余{len(core_points)-2}个知识点和易错/陷阱分析"
            }
        }
    
    # 策略2: 步骤太多 → 拆步骤
    if len(steps) > 4:
        mid = len(steps) // 2
        return {
            "should_split": True,
            "reason": f"解题步骤({len(steps)})过多，拆为上下两卡",
            "core_card": {
                "keep_fields": ["title", "definition", "core_points"],
                "steps": steps[:mid],
                "description": f"卡片(上): 题目理解 + 步骤1-{mid}"
            },
            "extension_card": {
                "steps": steps[mid:],
                "include": ["answer", "memory_tip"],
                "description": f"卡片(下): 步骤{mid+1}-{len(steps)} + 答案 + 记忆技巧"
            }
        }
    
    # 策略3: 文字密度过高 → 精简提示
    return {
        "should_split": False,
        "reason": "文字密度偏高但无需拆分",
        "simplification_hints": [
            "精简definition到1句话",
            "每个step用≤15字表达",
            "memory_tip用口诀式(≤10字)"
        ]
    }


# ────────────────────────────────────────────────────
# 7. 内容信息密度分析 (Information Density Analyzer)
# ────────────────────────────────────────────────────

def analyze_information_density(card: Dict) -> Dict:
    """
    分析卡片各部分的信息密度，识别可视化展示优先级
    
    Returns: {
        'total_chars': int,
        'sections': [{name, chars, priority, visual_strategy}],
        'char_budget_15': {...},  # 15字符限制下的分配方案
        'visualization_ratio': float  # 建议图文比
    }
    """
    sections = []
    
    def _add_section(name, content, priority, visual_strategy):
        if content:
            chars = len(str(content))
            sections.append({
                "name": name,
                "chars": chars,
                "content_preview": str(content)[:50],
                "priority": priority,  # 1=最高, 5=最低
                "visual_strategy": visual_strategy
            })
    
    _add_section("title", card.get('title', ''), 1, "大字标题,必须出现在图中")
    _add_section("definition", card.get('definition', ''), 3, "可简化为图标+关键词")
    
    example = card.get('example', {})
    _add_section("question", example.get('question', ''), 2, "题目区域,需要清晰展示")
    _add_section("steps", example.get('steps', []), 2, "步骤流程图,用箭头连接")
    _add_section("answer", example.get('answer', ''), 1, "答案高亮,最大字号")
    _add_section("memory_tip", card.get('memory_tip', ''), 2, "口诀/助记,特殊视觉处理")
    _add_section("core_points", card.get('core_points', []), 3, "可用图标列表展示")
    _add_section("trap_point", card.get('trap_point', ''), 4, "小字提醒或角标")
    _add_section("emotion_hook", card.get('emotion_hook', ''), 4, "标题上方引导语")
    
    # 按优先级排序
    sections.sort(key=lambda x: x['priority'])
    
    total_chars = sum(s['chars'] for s in sections)
    
    # 15字符中文限制下的分配方案 (卡片图上能显示的中文)
    char_budget = {}
    remaining = 15
    for s in sections:
        if s['priority'] == 1:
            alloc = min(4, remaining)
        elif s['priority'] == 2:
            alloc = min(4, remaining)
        elif s['priority'] == 3:
            alloc = min(3, remaining)
        else:
            alloc = 0
        char_budget[s['name']] = alloc
        remaining -= alloc
        if remaining <= 0:
            break
    
    # 图文比建议
    if total_chars > 300:
        viz_ratio = 0.6  # 重图轻文
    elif total_chars > 150:
        viz_ratio = 0.5  # 均衡
    else:
        viz_ratio = 0.4  # 可以多些文字装饰
    
    return {
        "total_chars": total_chars,
        "sections": sections,
        "char_budget_15": char_budget,
        "visualization_ratio": viz_ratio,
        "compression_needed": total_chars > 200
    }


# ────────────────────────────────────────────────────
# 8. 模块导出
# ────────────────────────────────────────────────────

__all__ = [
    'TEACHING_MODES', 'CARD_TYPE_STRATEGY_MAP',
    'compute_cognitive_load', 'match_teaching_strategy',
    'check_unit_sequence', 'design_card_content',
    'suggest_content_split', 'analyze_information_density',
    'GRADE_LOAD_LIMITS', 'COGNITIVE_LOAD_WEIGHTS',
]
