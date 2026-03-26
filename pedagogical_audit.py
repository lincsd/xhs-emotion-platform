# -*- coding: utf-8 -*-
"""
教学效果审核引擎 (Pedagogical Audit Engine)
=============================================
在现有知识准确性审核之上增加「教得好不好」的评判。

四大子系统:
  1. 可理解性评分 — 评估解释清晰度，检测认知跳跃
  2. 助记有效性评分 — 记忆提示的实际记忆辅助效果
  3. 参与度预测 — 预测收藏/分享概率
  4. 用户反馈闭环 — 采集前端用户评分，反哺质量系统

作者: AI Auto-Arch    版本: 2026-03-26
"""

import json, re, os, sqlite3, time, hashlib
from typing import Dict, List, Optional, Any, Tuple

# ────────────────────────────────────────────────────
# 数据库初始化
# ────────────────────────────────────────────────────

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pedagogical_audit.db')

def _get_db():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_tables(conn)
    return conn

_TABLES_CREATED = False

def _init_tables(conn):
    global _TABLES_CREATED
    if _TABLES_CREATED:
        return
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS pedagogical_audits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_id TEXT NOT NULL,
        card_type TEXT NOT NULL,
        subject TEXT DEFAULT '',
        grade TEXT DEFAULT '',
        understandability_score REAL DEFAULT 0,
        mnemonic_score REAL DEFAULT 0,
        engagement_score REAL DEFAULT 0,
        total_pedagogical_score REAL DEFAULT 0,
        detail_json TEXT DEFAULT '{}',
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_ped_card ON pedagogical_audits(card_id);
    CREATE INDEX IF NOT EXISTS idx_ped_type ON pedagogical_audits(card_type);

    CREATE TABLE IF NOT EXISTS user_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_id TEXT NOT NULL,
        user_id TEXT DEFAULT 'anonymous',
        rating INTEGER DEFAULT 0,
        feedback_type TEXT DEFAULT 'general',
        feedback_text TEXT DEFAULT '',
        tags TEXT DEFAULT '[]',
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_fb_card ON user_feedback(card_id);

    CREATE TABLE IF NOT EXISTS engagement_predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_id TEXT NOT NULL,
        predicted_save_rate REAL DEFAULT 0,
        predicted_share_rate REAL DEFAULT 0,
        predicted_engagement REAL DEFAULT 0,
        actual_saves INTEGER DEFAULT 0,
        actual_shares INTEGER DEFAULT 0,
        actual_views INTEGER DEFAULT 0,
        prediction_accuracy REAL DEFAULT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_eng_card ON engagement_predictions(card_id);

    CREATE TABLE IF NOT EXISTS feedback_insights (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_type TEXT NOT NULL,
        subject TEXT DEFAULT '',
        insight_type TEXT DEFAULT 'pattern',
        insight_text TEXT DEFAULT '',
        sample_count INTEGER DEFAULT 0,
        avg_rating REAL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );
    """)
    conn.commit()
    _TABLES_CREATED = True


# ────────────────────────────────────────────────────
# 1. 可理解性评分 (Understandability Scoring)
# ────────────────────────────────────────────────────

# 可理解性评估维度
UNDERSTANDABILITY_RUBRIC = {
    "explanation_clarity": {
        "weight": 0.30,
        "description": "解释是否清晰简洁，无歧义",
        "check_items": [
            "definition是否用简单语句(无嵌套从句)",
            "steps是否逻辑连贯，无跳跃",
            "答案是否明确，不模棱两可"
        ]
    },
    "cognitive_gap": {
        "weight": 0.25,
        "description": "有无认知跳跃(步骤之间缺少衔接)",
        "check_items": [
            "步骤间是否有逻辑断层",
            "是否使用了未解释的术语",
            "前置知识假设是否合理"
        ]
    },
    "scaffolding": {
        "weight": 0.20,
        "description": "是否提供了理解脚手架(提示、类比、铺垫)",
        "check_items": [
            "是否有从已知到未知的过渡",
            "是否有类比或比喻辅助理解",
            "memory_tip是否建立了知识联结"
        ]
    },
    "example_quality": {
        "weight": 0.15,
        "description": "例题是否典型、完整、可操作",
        "check_items": [
            "例题是否覆盖核心知识点",
            "解题过程是否完整(题→步骤→答)",
            "例题难度是否匹配目标年级"
        ]
    },
    "language_level": {
        "weight": 0.10,
        "description": "用语难度是否匹配目标受众",
        "check_items": [
            "专业术语是否有解释",
            "句子长度是否适合年级",
            "是否避免歧义表述"
        ]
    }
}


def score_understandability(card: Dict, card_type: str, grade: str = "") -> Dict:
    """
    本地评估卡片可理解性 (不调API，纯规则引擎)
    
    Returns: {
        'total': float (0-100),
        'dimensions': {name: {score, issues}},
        'cognitive_gaps': [str],  # 发现的认知跳跃
        'improvement_hints': [str]
    }
    """
    dimensions = {}
    issues_all = []
    cognitive_gaps = []
    hints = []
    
    # ---- 维度1: 解释清晰度 ----
    clarity_score = 80
    clarity_issues = []
    
    definition = card.get('definition', '')
    if not definition:
        clarity_score -= 20
        clarity_issues.append("缺少definition字段")
    elif len(definition) > 100:
        clarity_score -= 10
        clarity_issues.append(f"definition过长({len(definition)}字)，建议精简到50字内")
    
    # 检查嵌套从句
    if definition and (definition.count('，') > 3 or definition.count('的') > 4):
        clarity_score -= 10
        clarity_issues.append("definition含过多嵌套修饰语，建议拆分为短句")
    
    example = card.get('example', {})
    answer = example.get('answer', '')
    if not answer:
        clarity_score -= 15
        clarity_issues.append("缺少明确答案")
    
    dimensions["explanation_clarity"] = {
        "score": max(0, clarity_score),
        "issues": clarity_issues
    }
    
    # ---- 维度2: 认知跳跃检测 ----
    gap_score = 85
    gap_issues = []
    
    steps = example.get('steps', [])
    if len(steps) >= 2:
        for i in range(1, len(steps)):
            prev = str(steps[i-1])
            curr = str(steps[i])
            
            # 检查是否引入了新概念但未说明
            # 看prev_step的结果是否在curr_step中使用
            prev_numbers = set(re.findall(r'\d+', prev))
            curr_has_prev_result = any(n in curr for n in prev_numbers) if prev_numbers else True
            
            if not curr_has_prev_result and len(prev) > 10 and len(curr) > 10:
                gap_score -= 8
                cognitive_gaps.append(
                    f"步骤{i}→{i+1}可能存在跳跃: '{prev[:20]}...' → '{curr[:20]}...'"
                )
    
    # 检查是否使用了未在前文出现的专业术语
    all_text = json.dumps(card, ensure_ascii=False)
    # 常见数学术语
    advanced_terms = re.findall(
        r'(因式分解|配方法|韦达定理|判别式|渐近线|极限|导数|微分|积分|矩阵|向量|概率分布)',
        all_text
    )
    for term in advanced_terms:
        # 检查是否在definition或core_points中解释了
        if term not in card.get('definition', '') and \
           not any(term in str(cp) for cp in card.get('core_points', [])):
            gap_score -= 5
            cognitive_gaps.append(f"使用了高级术语'{term}'但未在知识点中解释")
    
    if not steps:
        gap_score -= 10
        gap_issues.append("缺少解题步骤，学生无法跟踪推理过程")
    
    dimensions["cognitive_gap"] = {
        "score": max(0, gap_score),
        "issues": gap_issues
    }
    
    # ---- 维度3: 理解脚手架 ----
    scaffold_score = 70
    scaffold_issues = []
    
    memory_tip = card.get('memory_tip', '')
    if memory_tip:
        scaffold_score += 10
        # 好的memory_tip特征: 短、有韵律、有类比
        if len(memory_tip) <= 15:
            scaffold_score += 5  # 精炼
        if re.search(r'[像就如同好比]', memory_tip):
            scaffold_score += 5  # 有类比
    else:
        scaffold_issues.append("缺少memory_tip记忆辅助")
    
    # 检查是否有类比/比喻
    if re.search(r'(好比|就像|类似|想象|如同|比如)', all_text):
        scaffold_score += 5
    
    # 检查core_points是否提供了渐进式知识铺垫
    core_points = card.get('core_points', [])
    if len(core_points) >= 2:
        scaffold_score += 5  # 有多个知识点构建层次
    
    dimensions["scaffolding"] = {
        "score": min(100, max(0, scaffold_score)),
        "issues": scaffold_issues
    }
    
    # ---- 维度4: 例题质量 ----
    example_score = 75
    example_issues = []
    
    question = example.get('question', '')
    if not question:
        example_score -= 25
        example_issues.append("缺少例题")
    elif len(question) < 10:
        example_score -= 10
        example_issues.append("题目过短，可能不够完整")
    
    if steps and len(steps) >= 2:
        example_score += 10  # 有完整解题步骤
    elif steps and len(steps) == 1:
        example_score += 5
    
    if answer:
        example_score += 10  # 有答案
        # 答案是否明确(不是'略'或'自行判断')
        if re.search(r'(略|自行|参考|略去)', answer):
            example_score -= 10
            example_issues.append("答案不够明确")
    
    dimensions["example_quality"] = {
        "score": min(100, max(0, example_score)),
        "issues": example_issues
    }
    
    # ---- 维度5: 语言适配度 ----
    lang_score = 85
    lang_issues = []
    
    # 年级适配: 低年级应避免长句
    grade_level = {"一上":1,"一下":1,"二上":2,"二下":2,"三上":3,"三下":3,
                   "四上":4,"四下":4,"五上":5,"五下":5,"六上":6,"六下":6}.get(grade, 4)
    
    # 平均句长检查
    sentences = re.split(r'[。！？\n]', all_text)
    sentences = [s for s in sentences if len(s.strip()) > 5]
    if sentences:
        avg_len = sum(len(s) for s in sentences) / len(sentences)
        max_recommended = 15 + grade_level * 3  # 一年级18字, 六年级33字
        if avg_len > max_recommended:
            lang_score -= 10
            lang_issues.append(f"平均句长({avg_len:.0f}字)偏长，{grade}年级建议≤{max_recommended}字")
    
    dimensions["language_level"] = {
        "score": max(0, lang_score),
        "issues": lang_issues
    }
    
    # ---- 加权总分 ----
    total = sum(
        dimensions[k]["score"] * UNDERSTANDABILITY_RUBRIC[k]["weight"]
        for k in UNDERSTANDABILITY_RUBRIC
    )
    
    # 生成改进建议
    for dim_name, dim_data in dimensions.items():
        if dim_data["score"] < 60:
            rubric = UNDERSTANDABILITY_RUBRIC[dim_name]
            hints.append(f"[{rubric['description']}] 需要改进: {'; '.join(dim_data['issues'][:2])}")
    
    return {
        "total": round(total, 1),
        "dimensions": dimensions,
        "cognitive_gaps": cognitive_gaps,
        "improvement_hints": hints
    }


# ────────────────────────────────────────────────────
# 2. 助记有效性评分 (Mnemonic Effectiveness Scoring)
# ────────────────────────────────────────────────────

# 助记法类型及其有效性系数
MNEMONIC_STRATEGIES = {
    "口诀法": {
        "patterns": [r'[，。！\n].*[，。！\n]', r'\w{2,4}[，,]\w{2,4}[，,]\w{2,4}'],
        "keywords": ['口诀', '歌', '诀', '律'],
        "effectiveness": 0.85,
        "description": "韵律口诀，朗朗上口便于背诵"
    },
    "谐音法": {
        "patterns": [r'谐音', r'[像].*[谐音]', r'sounds? like'],
        "keywords": ['谐音', '读音', '发音像'],
        "effectiveness": 0.80,
        "description": "利用谐音联想记忆"
    },
    "联想法": {
        "patterns": [r'(想[到成象]|联想|想一想|脑海)'],
        "keywords": ['联想', '想象', '想到', '画面'],
        "effectiveness": 0.85,
        "description": "建立知识与已有经验的联想桥梁"
    },
    "图式法": {
        "patterns": [r'(图|画|看|形状|像.*形)'],
        "keywords": ['像', '形状', '图形', '画'],
        "effectiveness": 0.80,
        "description": "通过视觉图形记忆"
    },
    "故事法": {
        "patterns": [r'(故事|曾经|有一天|从前)'],
        "keywords": ['故事', '场景', '情境'],
        "effectiveness": 0.90,
        "description": "用故事化场景承载知识点"
    },
    "对比法": {
        "patterns": [r'(vs|VS|对比|区别|不同|相反)'],
        "keywords": ['vs', '对比', '区别', '相反'],
        "effectiveness": 0.75,
        "description": "通过对比差异加深印象"
    },
    "首字母法": {
        "patterns": [r'[A-Z]{3,}', r'首字母'],
        "keywords": ['首字母', '缩写'],
        "effectiveness": 0.70,
        "description": "首字母缩写速记"
    }
}


def score_mnemonic_effectiveness(card: Dict, card_type: str) -> Dict:
    """
    评估卡片助记法的有效性
    
    Returns: {
        'total': float (0-100),
        'has_mnemonic': bool,
        'detected_strategy': str,
        'strategy_effectiveness': float,
        'quality_factors': {factor: score},
        'suggestions': [str]
    }
    """
    memory_tip = card.get('memory_tip', '')
    emotion_hook = card.get('emotion_hook', '')
    
    if not memory_tip:
        return {
            "total": 30,
            "has_mnemonic": False,
            "detected_strategy": "无",
            "strategy_effectiveness": 0,
            "quality_factors": {},
            "suggestions": ["添加memory_tip字段: 用口诀/谐音/联想等方法辅助记忆"]
        }
    
    # 检测使用的助记策略
    detected = "通用"
    best_effectiveness = 0.60
    
    for strategy_name, strategy in MNEMONIC_STRATEGIES.items():
        for kw in strategy['keywords']:
            if kw in memory_tip:
                detected = strategy_name
                best_effectiveness = strategy['effectiveness']
                break
        if detected != "通用":
            break
        for pattern in strategy['patterns']:
            if re.search(pattern, memory_tip):
                detected = strategy_name
                best_effectiveness = strategy['effectiveness']
                break
        if detected != "通用":
            break
    
    # 质量因素评分
    quality_factors = {}
    
    # 1. 简洁性 (越短越好记)
    if len(memory_tip) <= 8:
        quality_factors["simplicity"] = 95
    elif len(memory_tip) <= 15:
        quality_factors["simplicity"] = 85
    elif len(memory_tip) <= 25:
        quality_factors["simplicity"] = 70
    else:
        quality_factors["simplicity"] = 50
    
    # 2. 韵律性 (有押韵或节奏)
    # 检查是否有押韵
    has_rhythm = bool(re.search(r'(.)\1', memory_tip))  # 重复音
    syllable_groups = re.split(r'[，,。！、\s]', memory_tip)
    syllable_groups = [g for g in syllable_groups if g]
    
    equal_length = len(set(len(g) for g in syllable_groups)) == 1 if len(syllable_groups) >= 2 else False
    
    rhythm_score = 60
    if has_rhythm:
        rhythm_score += 10
    if equal_length:
        rhythm_score += 20  # 等长句式有节奏感
    if len(syllable_groups) >= 2 and len(syllable_groups) <= 4:
        rhythm_score += 10  # 2-4个短句最佳
    quality_factors["rhythm"] = min(100, rhythm_score)
    
    # 3. 知识相关性 (是否和核心知识有关)
    core_points = card.get('core_points', [])
    title = card.get('title', '')
    relevance_score = 50
    
    # 检查memory_tip是否包含标题关键词
    title_chars = set(title)
    tip_chars = set(memory_tip)
    overlap = len(title_chars & tip_chars - set('的了是在有和'))
    if overlap >= 2:
        relevance_score += 25
    
    # 检查是否和core_points有关联
    for cp in core_points:
        cp_str = str(cp)
        if any(c in memory_tip for c in cp_str if len(c.strip()) > 0 and c not in '的了是在有和，。'):
            relevance_score += 10
            break
    
    quality_factors["relevance"] = min(100, relevance_score)
    
    # 4. 独特性 (不是通用废话)
    generic_phrases = ['好好学', '认真', '记住', '注意', '小心', '多练习']
    is_generic = any(p in memory_tip for p in generic_phrases)
    quality_factors["uniqueness"] = 40 if is_generic else 80
    
    # 加权总分
    factor_weights = {"simplicity": 0.25, "rhythm": 0.25, "relevance": 0.30, "uniqueness": 0.20}
    factor_total = sum(quality_factors.get(k, 50) * w for k, w in factor_weights.items())
    
    # 策略有效性加成
    total = factor_total * best_effectiveness + (1 - best_effectiveness) * 50
    total = round(total, 1)
    
    # 建议
    suggestions = []
    if quality_factors.get("simplicity", 100) < 70:
        suggestions.append(f"助记法过长({len(memory_tip)}字)，建议精简到10字以内")
    if quality_factors.get("rhythm", 100) < 60:
        suggestions.append("建议改为等长对仗句式，增强节奏感(如: 'xxx，xxx')")
    if quality_factors.get("relevance", 100) < 60:
        suggestions.append("助记法与核心知识关联弱，建议包含标题或关键概念的谐音/联想")
    if is_generic:
        suggestions.append("当前助记法过于通用，建议针对本卡具体知识点定制")
    
    return {
        "total": total,
        "has_mnemonic": True,
        "detected_strategy": detected,
        "strategy_effectiveness": best_effectiveness,
        "quality_factors": quality_factors,
        "suggestions": suggestions
    }


# ────────────────────────────────────────────────────
# 3. 参与度预测 (Engagement Prediction)
# ────────────────────────────────────────────────────

# 参与度影响因子
ENGAGEMENT_FACTORS = {
    "hook_strength": {
        "weight": 0.25,
        "description": "标题/钩子的吸引力"
    },
    "visual_appeal": {
        "weight": 0.20,
        "description": "视觉美感预期"
    },
    "practical_value": {
        "weight": 0.25,
        "description": "实用价值(学了就能用)"
    },
    "emotional_resonance": {
        "weight": 0.15,
        "description": "情感共鸣度"
    },
    "share_trigger": {
        "weight": 0.15,
        "description": "分享驱动力(让人想转发)"
    }
}

# 高参与度钩子模式
HIGH_ENGAGEMENT_HOOKS = [
    (r'\d+%.*同学', 15, "数据恐吓型"),
    (r'(99%|90%|80%)', 15, "高比例触发"),
    (r'(秒[懂杀会]|一[招看]就)', 12, "速成承诺"),
    (r'(千万别|万万不|绝对不)', 12, "禁忌引导"),
    (r'(你.*[吗？]|是不是)', 10, "提问互动"),
    (r'(学霸|学渣|老师)', 10, "身份带入"),
    (r'(妈妈|爸爸|家长|孩子)', 10, "亲子场景"),
    (r'(偷偷|悄悄|私藏|独家)', 12, "稀缺暗示"),
    (r'(必考|必背|必记|考前)', 12, "考试紧迫"),
    (r'[！!]{2,}', 5, "感叹加强"),
]


def predict_engagement(card: Dict, card_type: str, subject: str = "") -> Dict:
    """
    预测卡片的用户参与度
    
    Returns: {
        'total': float (0-100 engagement score),
        'predicted_save_rate': float (0-1),
        'predicted_share_rate': float (0-1),
        'factors': {name: score},
        'hook_analysis': {type, score, matched_patterns},
        'improvements': [str]
    }
    """
    factors = {}
    improvements = []
    
    title = card.get('title', '')
    emotion_hook = card.get('emotion_hook', '')
    hook_text = emotion_hook or title
    
    # ---- 因子1: 钩子强度 ----
    hook_score = 40  # 基础分
    matched_patterns = []
    
    for pattern, bonus, pattern_type in HIGH_ENGAGEMENT_HOOKS:
        if re.search(pattern, hook_text):
            hook_score += bonus
            matched_patterns.append(pattern_type)
    
    if not emotion_hook:
        hook_score -= 15
        improvements.append("添加emotion_hook: 用'XX%同学做错'/'一招就会'等钩子")
    
    factors["hook_strength"] = min(100, hook_score)
    
    # ---- 因子2: 视觉美感预期 ----
    # 基于卡片数据预测生成图片的视觉效果
    visual_score = 65
    
    # 有例题 → 图中有具体内容展示
    if card.get('example', {}).get('question'):
        visual_score += 10
    
    # 有步骤 → 有流程图潜力
    if len(card.get('example', {}).get('steps', [])) >= 2:
        visual_score += 10
    
    # 有对比 → 双栏视觉冲击
    if card.get('mistakes'):
        visual_score += 10
    
    factors["visual_appeal"] = min(100, visual_score)
    
    # ---- 因子3: 实用价值 ----
    practical_score = 55
    
    # 有明确答案/方法 → 高实用
    if card.get('example', {}).get('answer'):
        practical_score += 15
    if card.get('example', {}).get('steps'):
        practical_score += 10
    
    # 考试相关 → 高实用
    all_text = json.dumps(card, ensure_ascii=False)
    if re.search(r'(考试|真题|考卷|必考|期末|期中)', all_text):
        practical_score += 15
    
    # 有trap_point → 防错实用
    if card.get('trap_point'):
        practical_score += 10
    
    factors["practical_value"] = min(100, practical_score)
    
    # ---- 因子4: 情感共鸣 ----
    emotional_score = 45
    
    # 检查情感元素
    emotion_keywords = {
        "共鸣": ['都会', '每次', '是不是', '你也', '我也', '同感'],
        "挫折安慰": ['没关系', '别担心', '很正常', '都会错'],
        "成就激励": ['你能行', '加油', '学会了', '厉害', '进步'],
        "好奇心": ['为什么', '你知道', '原来', '居然', '竟然'],
    }
    
    for emo_type, keywords in emotion_keywords.items():
        if any(kw in all_text for kw in keywords):
            emotional_score += 8
    
    # 情感类&养生类天然高共鸣
    if subject in ('情感', '养生'):
        emotional_score += 15
    
    factors["emotional_resonance"] = min(100, emotional_score)
    
    # ---- 因子5: 分享驱动 ----
    share_score = 40
    
    # 实用知识点 → 收藏
    if card.get('core_points') and len(card.get('core_points', [])) >= 2:
        share_score += 10
    
    # 有趣/意外 → 分享
    surprise_words = ['居然', '竟然', '没想到', '原来', '秘密', '真相']
    if any(w in all_text for w in surprise_words):
        share_score += 15
    
    # 有memory_tip → 值得收藏
    if card.get('memory_tip'):
        share_score += 10
    
    # 卡片类型的天然分享性
    type_share_bonus = {
        "考卷真题卡": 15, "易错题卡": 12, "知识总结卡": 10,
        "养生卡": 12, "情感卡": 10, "国学卡": 8
    }
    share_score += type_share_bonus.get(card_type, 5)
    
    factors["share_trigger"] = min(100, share_score)
    
    # ---- 综合计算 ----
    total = sum(factors[k] * ENGAGEMENT_FACTORS[k]["weight"] for k in ENGAGEMENT_FACTORS)
    total = round(total, 1)
    
    # 预测收藏率和分享率
    predicted_save = round(min(0.8, total / 150), 3)  # 最高80%
    predicted_share = round(min(0.4, total / 300), 3)  # 最高40%
    
    # 低分因子的改进建议
    sorted_factors = sorted(factors.items(), key=lambda x: x[1])
    for fname, fscore in sorted_factors[:2]:
        if fscore < 60:
            factor_info = ENGAGEMENT_FACTORS[fname]
            improvements.append(f"提升[{factor_info['description']}]({fscore}分): ", )
    
    # 具体改进建议
    if factors["hook_strength"] < 60:
        improvements.append("考虑添加数据型钩子，如'95%的同学第一次都做错了！'")
    if factors["practical_value"] < 60:
        improvements.append("增加可直接使用的方法/公式/模板，提升实用感")
    if factors["share_trigger"] < 50:
        improvements.append("添加'意外感'元素（如反常识知识点）提升分享欲")
    
    return {
        "total": total,
        "predicted_save_rate": predicted_save,
        "predicted_share_rate": predicted_share,
        "factors": factors,
        "hook_analysis": {
            "type": matched_patterns[0] if matched_patterns else "无匹配模式",
            "score": factors["hook_strength"],
            "matched_patterns": matched_patterns
        },
        "improvements": improvements
    }


# ────────────────────────────────────────────────────
# 4. 用户反馈闭环 (User Feedback Loop)
# ────────────────────────────────────────────────────

def record_user_feedback(card_id: str, rating: int, 
                         feedback_type: str = "general",
                         feedback_text: str = "",
                         tags: List[str] = None,
                         user_id: str = "anonymous") -> Dict:
    """
    记录用户对卡片的反馈评分
    
    Args:
        card_id: 卡片ID
        rating: 1-5 星评分
        feedback_type: 'content_quality'|'visual_design'|'usefulness'|'general'
        feedback_text: 用户文字反馈
        tags: ['太难了','看不懂','很有用','好看'] 等标签
        
    Returns: {'ok': True, 'feedback_id': int}
    """
    rating = max(1, min(5, int(rating)))
    tags = tags or []
    
    db = _get_db()
    try:
        cur = db.execute(
            """INSERT INTO user_feedback 
               (card_id, user_id, rating, feedback_type, feedback_text, tags)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (card_id, user_id, rating, feedback_type, feedback_text, json.dumps(tags, ensure_ascii=False))
        )
        db.commit()
        return {"ok": True, "feedback_id": cur.lastrowid}
    finally:
        db.close()


def get_card_feedback_summary(card_id: str) -> Dict:
    """获取单张卡片的反馈汇总"""
    db = _get_db()
    try:
        rows = db.execute(
            "SELECT rating, feedback_type, feedback_text, tags FROM user_feedback WHERE card_id = ?",
            (card_id,)
        ).fetchall()
        
        if not rows:
            return {"card_id": card_id, "total_feedbacks": 0, "avg_rating": 0}
        
        ratings = [r['rating'] for r in rows]
        
        # 标签统计
        all_tags = []
        for r in rows:
            try:
                all_tags.extend(json.loads(r['tags'] or '[]'))
            except:
                pass
        
        tag_counts = {}
        for t in all_tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1
        
        return {
            "card_id": card_id,
            "total_feedbacks": len(rows),
            "avg_rating": round(sum(ratings) / len(ratings), 2),
            "rating_distribution": {
                str(i): ratings.count(i) for i in range(1, 6)
            },
            "top_tags": sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5],
            "feedback_texts": [r['feedback_text'] for r in rows if r['feedback_text']][:10]
        }
    finally:
        db.close()


def get_type_feedback_summary(card_type: str, subject: str = "", days: int = 30) -> Dict:
    """获取某类卡片的整体反馈趋势"""
    db = _get_db()
    try:
        query = """
            SELECT uf.rating, uf.tags, uf.feedback_type, uf.feedback_text, uf.card_id
            FROM user_feedback uf
            WHERE uf.card_id LIKE ?
            AND uf.created_at >= datetime('now', ?)
        """
        like_pattern = f'%{card_type}%' if card_type else '%'
        rows = db.execute(query, (like_pattern, f'-{days} days')).fetchall()
        
        if not rows:
            return {"card_type": card_type, "total": 0, "avg_rating": 0}
        
        ratings = [r['rating'] for r in rows]
        
        return {
            "card_type": card_type,
            "total": len(rows),
            "avg_rating": round(sum(ratings) / len(ratings), 2),
            "satisfaction_rate": round(sum(1 for r in ratings if r >= 4) / len(ratings), 3),
            "unique_cards": len(set(r['card_id'] for r in rows))
        }
    finally:
        db.close()


def analyze_feedback_for_improvement(card_type: str, min_samples: int = 5) -> Dict:
    """分析用户反馈，提取改进洞察"""
    db = _get_db()
    try:
        rows = db.execute(
            "SELECT * FROM user_feedback WHERE card_id LIKE ? ORDER BY created_at DESC LIMIT 200",
            (f'%{card_type}%' if card_type else '%',)
        ).fetchall()
        
        if len(rows) < min_samples:
            return {"enough_data": False, "sample_count": len(rows)}
        
        # 分析评分分布
        ratings = [r['rating'] for r in rows]
        avg = sum(ratings) / len(ratings)
        
        # 分析低评分共性
        low_rated = [r for r in rows if r['rating'] <= 2]
        high_rated = [r for r in rows if r['rating'] >= 4]
        
        low_tags = []
        for r in low_rated:
            try: low_tags.extend(json.loads(r['tags'] or '[]'))
            except: pass
        
        high_tags = []
        for r in high_rated:
            try: high_tags.extend(json.loads(r['tags'] or '[]'))
            except: pass
        
        # 提取洞察
        insights = []
        low_tag_counts = {}
        for t in low_tags:
            low_tag_counts[t] = low_tag_counts.get(t, 0) + 1
        
        for tag, count in sorted(low_tag_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
            insights.append(f"低评分用户常反馈: '{tag}' ({count}次)")
        
        return {
            "enough_data": True,
            "sample_count": len(rows),
            "avg_rating": round(avg, 2),
            "low_rate": round(len(low_rated) / len(rows), 3),
            "high_rate": round(len(high_rated) / len(rows), 3),
            "insights": insights,
            "low_rate_common_tags": dict(sorted(low_tag_counts.items(), key=lambda x: x[1], reverse=True)[:5])
        }
    finally:
        db.close()


# ────────────────────────────────────────────────────
# 5. 综合教学效果评估 (Combined Pedagogical Assessment)
# ────────────────────────────────────────────────────

def full_pedagogical_audit(card: Dict, card_type: str, 
                            subject: str = "", grade: str = "") -> Dict:
    """
    综合教学效果评估 — 三维度本地评分(不调API)
    
    Returns: {
        'pedagogical_score': float (0-100),
        'understandability': {...},
        'mnemonic': {...},
        'engagement': {...},
        'verdict': 'excellent'|'good'|'needs_improvement'|'poor',
        'top_improvements': [str],
        'prompt_injection': str  # 可直接注入生成prompt的教学质量提示
    }
    """
    # 三维度评分
    understand = score_understandability(card, card_type, grade)
    mnemonic = score_mnemonic_effectiveness(card, card_type)
    engagement = predict_engagement(card, card_type, subject)
    
    # 加权总分 (可理解性最重要)
    weights = {"understand": 0.45, "mnemonic": 0.25, "engagement": 0.30}
    total = (understand['total'] * weights['understand'] +
             mnemonic['total'] * weights['mnemonic'] +
             engagement['total'] * weights['engagement'])
    total = round(total, 1)
    
    # 判定等级
    if total >= 80:
        verdict = "excellent"
    elif total >= 65:
        verdict = "good"
    elif total >= 50:
        verdict = "needs_improvement"
    else:
        verdict = "poor"
    
    # 收集所有改进建议，按优先级排序
    all_improvements = []
    all_improvements.extend(understand.get('improvement_hints', []))
    all_improvements.extend(mnemonic.get('suggestions', []))
    all_improvements.extend(engagement.get('improvements', []))
    top_improvements = all_improvements[:5]
    
    # 构建prompt注入
    injection_parts = []
    
    if understand['cognitive_gaps']:
        gaps_str = '; '.join(understand['cognitive_gaps'][:2])
        injection_parts.append(
            f"⚠️ COGNITIVE GAP DETECTED: {gaps_str}. "
            "Ensure the visual shows CLEAR STEP-BY-STEP progression with NO gaps."
        )
    
    if mnemonic['total'] < 50:
        injection_parts.append(
            "ENHANCE MNEMONIC: Add a catchy, rhythmic memory aid (≤8 chars) "
            "as a highlighted bubble/badge on the card."
        )
    
    if engagement['factors'].get('hook_strength', 100) < 50:
        injection_parts.append(
            "BOOST ENGAGEMENT: Add a hook element like '90% get this wrong!' "
            "or '1-minute mastery' at the top of the card."
        )
    
    prompt_injection = '\n'.join(injection_parts) if injection_parts else ''
    
    # 记录到数据库
    _record_pedagogical_audit(
        card.get('full_id', card.get('card_id', '')),
        card_type, subject, grade,
        understand['total'], mnemonic['total'], engagement['total'], total,
        {"understand": understand, "mnemonic": mnemonic, "engagement": engagement}
    )
    
    return {
        "pedagogical_score": total,
        "understandability": understand,
        "mnemonic": mnemonic,
        "engagement": engagement,
        "verdict": verdict,
        "top_improvements": top_improvements,
        "prompt_injection": prompt_injection
    }


def _record_pedagogical_audit(card_id, card_type, subject, grade,
                               under_score, mnem_score, engage_score, total,
                               detail):
    """记录教学审核结果到数据库"""
    try:
        db = _get_db()
        db.execute(
            """INSERT INTO pedagogical_audits 
               (card_id, card_type, subject, grade,
                understandability_score, mnemonic_score, engagement_score,
                total_pedagogical_score, detail_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (card_id, card_type, subject, grade,
             under_score, mnem_score, engage_score, total,
             json.dumps(detail, ensure_ascii=False, default=str))
        )
        db.commit()
        db.close()
    except Exception as e:
        print(f"[pedagogical_audit] DB write error: {e}")


# ────────────────────────────────────────────────────
# 6. 反馈数据仪表盘 (Feedback Dashboard)
# ────────────────────────────────────────────────────

def get_pedagogical_dashboard() -> Dict:
    """获取教学审核仪表盘数据"""
    db = _get_db()
    try:
        # 审核统计
        audit_stats = db.execute("""
            SELECT 
                COUNT(*) as total,
                AVG(total_pedagogical_score) as avg_score,
                AVG(understandability_score) as avg_understand,
                AVG(mnemonic_score) as avg_mnemonic,
                AVG(engagement_score) as avg_engagement,
                SUM(CASE WHEN total_pedagogical_score >= 80 THEN 1 ELSE 0 END) as excellent_count,
                SUM(CASE WHEN total_pedagogical_score < 50 THEN 1 ELSE 0 END) as poor_count
            FROM pedagogical_audits
        """).fetchone()
        
        # 按类型统计
        type_stats = db.execute("""
            SELECT card_type,
                   COUNT(*) as cnt,
                   AVG(total_pedagogical_score) as avg_score
            FROM pedagogical_audits
            GROUP BY card_type
            ORDER BY avg_score DESC
        """).fetchall()
        
        # 反馈统计
        feedback_stats = db.execute("""
            SELECT COUNT(*) as total,
                   AVG(rating) as avg_rating,
                   SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END) as satisfied
            FROM user_feedback
        """).fetchone()
        
        return {
            "ok": True,
            "audits": {
                "total": audit_stats['total'] or 0,
                "avg_score": round(audit_stats['avg_score'] or 0, 1),
                "avg_understand": round(audit_stats['avg_understand'] or 0, 1),
                "avg_mnemonic": round(audit_stats['avg_mnemonic'] or 0, 1),
                "avg_engagement": round(audit_stats['avg_engagement'] or 0, 1),
                "excellent_count": audit_stats['excellent_count'] or 0,
                "poor_count": audit_stats['poor_count'] or 0,
            },
            "by_type": [
                {"type": r['card_type'], "count": r['cnt'], "avg": round(r['avg_score'], 1)}
                for r in type_stats
            ],
            "user_feedback": {
                "total": feedback_stats['total'] or 0,
                "avg_rating": round(feedback_stats['avg_rating'] or 0, 2),
                "satisfaction_rate": round(
                    (feedback_stats['satisfied'] or 0) / max(feedback_stats['total'] or 1, 1), 3
                )
            }
        }
    finally:
        db.close()


# ────────────────────────────────────────────────────
# 7. 预定义反馈标签 (Feedback Tags)
# ────────────────────────────────────────────────────

FEEDBACK_TAGS = {
    "positive": [
        "讲得清楚", "一看就懂", "很有用", "已收藏",
        "口诀好记", "颜色好看", "排版舒服", "想分享给同学"
    ],
    "negative": [
        "看不懂", "太难了", "太简单了", "字太小",
        "内容有误", "排版混乱", "不实用", "信息太多"
    ],
    "suggestion": [
        "希望有更多例题", "希望字更大", "希望有视频讲解",
        "希望有练习题", "希望更简洁"
    ]
}


# ────────────────────────────────────────────────────
# 8. 模块导出
# ────────────────────────────────────────────────────

__all__ = [
    'score_understandability', 'score_mnemonic_effectiveness',
    'predict_engagement', 'full_pedagogical_audit',
    'record_user_feedback', 'get_card_feedback_summary',
    'get_type_feedback_summary', 'analyze_feedback_for_improvement',
    'get_pedagogical_dashboard', 'FEEDBACK_TAGS',
    'UNDERSTANDABILITY_RUBRIC', 'MNEMONIC_STRATEGIES',
    'ENGAGEMENT_FACTORS',
]
