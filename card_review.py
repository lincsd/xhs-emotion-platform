#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识卡片内容审校模块 (Card Review Gate)
========================================
在出图前拦截低质量 / 有硬伤的卡片内容。

三层审校:
  Layer 1 — 硬规则校验 (validate_hard_rules)      纯代码，零延迟
  Layer 2 — AI 教学审稿 (review_teaching_quality)  调 Gemini，~3s
  Layer 3 — Prompt 压缩 (build_structured_payload)  结构化输出

接入方式:
  from card_review import run_review_gate
  result = run_review_gate(card, subject, api_key)
  if not result['pass']:
      skip ...
"""

import re, json

# ═══════════════════════════════════════════
# 常量 & 阈值
# ═══════════════════════════════════════════
LANGUAGE_SCORE_THRESHOLD = 90   # 语言分 < 此值 → 不出图
TEACHING_SCORE_THRESHOLD = 85   # 教学分 < 此值 → 不出图
MAX_KNOWLEDGE_POINTS = 1        # 单卡最大主知识点数
MAX_REWRITE_ATTEMPTS = 2        # 最多自动重写次数

# 英语语法卡检测关键词
ENGLISH_GRAMMAR_KEYWORDS = [
    '语法', '时态', '词性', '搭配', '句型', '从句', '虚拟语气',
    '被动语态', '主谓一致', '冠词', '介词', '连词', '代词',
    'grammar', 'tense', 'collocation', 'phrase',
    # 英语卡片类型
    '语法辨析', '高频活用', '易混辨析', '词性辨析',
]

# 常见重复词模式 (英文)
REPEATED_WORD_PATTERN = re.compile(
    r'\b(\w{2,})\s+\1\b', re.IGNORECASE
)

# 常见残缺表达模式 (英文短语末尾不完整)
INCOMPLETE_PHRASE_PATTERNS = [
    # "success in" 后面没有名词/动名词
    re.compile(r'\b(success|successful|succeed)\s+in\s*[.,;!?\s]*$', re.IGNORECASE),
    # "pay attention to" 后面没有宾语
    re.compile(r'\bpay\s+(?:close\s+)?attention\s+to\s*[.,;!?\s]*$', re.IGNORECASE),
    # "is important to" 后面没有动词
    re.compile(r'\bis\s+important\s+to\s*[.,;!?\s]*$', re.IGNORECASE),
    # "depend on" 后面没有宾语
    re.compile(r'\bdepend(?:s)?\s+on\s*[.,;!?\s]*$', re.IGNORECASE),
]

# 笼统错因关键词 —— 这些单独出现时说明错因不够具体
VAGUE_REASON_PATTERNS = [
    '词性错', '搭配错', '语法错', '用法错',
    '词性不对', '搭配不对', '用错了',
]


# ═══════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════

def _first_mistake(card, field='wrong'):
    """从 card['mistakes'] 里取第一条的指定字段"""
    mistakes = card.get('mistakes', [])
    if not mistakes:
        return ''
    m = mistakes[0]
    if isinstance(m, dict):
        return str(m.get(field, ''))
    return str(m)


def _all_text(card):
    """把卡片里所有文本拼成一个大字符串，用于全局检测"""
    parts = [
        card.get('title', ''),
        card.get('definition', ''),
        ' '.join(str(p) for p in card.get('core_points', [])),
        card.get('memory_tip', ''),
        _first_mistake(card, 'wrong'),
        _first_mistake(card, 'correct'),
    ]
    ex = card.get('example', {})
    if ex:
        parts.append(str(ex.get('question', '')))
        parts.append(str(ex.get('answer', '')))
        parts.extend(str(s) for s in ex.get('steps', []))
    return '\n'.join(parts)


def _has_english(text):
    """检测文本中是否包含英文单词"""
    return bool(re.search(r'[a-zA-Z]{2,}', text))


def is_english_grammar_card(card, subject=''):
    """判断是否为英语语法类卡片"""
    if subject == '英语':
        return True
    text = _all_text(card).lower()
    return any(kw in text for kw in ENGLISH_GRAMMAR_KEYWORDS)


def detect_knowledge_candidates(card):
    """
    检测卡片中包含多少个独立知识点。
    策略: 检查 core_points 里是否有明显不同主题的条目。
    返回去重后的知识点列表。
    """
    points = card.get('core_points', [])
    if len(points) <= 1:
        return points[:1]

    # 简单策略: 如果 core_points 里有明显不同的英文短语/语法结构，算多个知识点
    unique_topics = []
    seen_roots = set()
    for p in points:
        # 提取英文关键短语
        eng_phrases = re.findall(r'[a-zA-Z][a-zA-Z\s]{2,}[a-zA-Z]', str(p))
        root = ' '.join(eng_phrases).lower().strip() if eng_phrases else str(p)[:10].lower()
        if root and root not in seen_roots:
            seen_roots.add(root)
            unique_topics.append(str(p))

    # 如果没有英文，按中文主题去重
    if not unique_topics:
        for p in points:
            stub = str(p)[:8]
            if stub not in seen_roots:
                seen_roots.add(stub)
                unique_topics.append(str(p))

    return unique_topics


def has_repeated_word(text):
    """检测是否有连续重复的英文单词，如 'can can'"""
    return bool(REPEATED_WORD_PATTERN.search(text))


def has_incomplete_phrase(text):
    """检测是否有残缺的英文表达"""
    # 按句子拆分后逐句检查
    sentences = re.split(r'[.!?。！？]', text)
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        for pat in INCOMPLETE_PHRASE_PATTERNS:
            if pat.search(sent):
                return True
    return False


def looks_like_complete_sentence(text):
    """
    判断一段英文文本是否看起来像完整句子。
    至少要有: 主语 + 谓语动词 + 一定长度
    """
    text = text.strip()
    if not text:
        return False
    # 太短不可能是完整句
    if len(text) < 10:
        return False
    # 至少包含一个动词的痕迹(简化判断)
    words = text.split()
    if len(words) < 3:
        return False
    # 如果全是中文，跳过英文句子检查
    if not re.search(r'[a-zA-Z]', text):
        return True
    # 英文句子: 至少3个单词，首字母大写或全小写都算
    return True


def vague_error_reason(card):
    """检测 mistakes 里的错因是否过于笼统"""
    mistakes = card.get('mistakes', [])
    if not mistakes:
        return False  # 没有 mistakes 不算笼统（可能不需要）
    for m in mistakes:
        if not isinstance(m, dict):
            continue
        wrong = str(m.get('wrong', ''))
        correct = str(m.get('correct', ''))
        # 如果 wrong 和 correct 都很短且笼统
        combined = wrong + correct
        for vague in VAGUE_REASON_PATTERNS:
            if vague in combined and len(combined) < 20:
                return True
    return False


# ═══════════════════════════════════════════
# Layer 1: 硬规则校验
# ═══════════════════════════════════════════

def validate_hard_rules(card, subject=''):
    """
    纯代码校验，零延迟。
    返回: { 'pass': bool, 'issues': list[str], 'stage': 'hard_rule' }
    """
    issues = []
    is_eng = is_english_grammar_card(card, subject)
    text = _all_text(card)

    # ── 规则 1: 重复词 ──
    if has_repeated_word(text):
        match = REPEATED_WORD_PATTERN.search(text)
        word = match.group(1) if match else '?'
        issues.append(f'存在重复词: "{word} {word}"')

    # ── 规则 2: 残缺表达 ──
    if _has_english(text) and has_incomplete_phrase(text):
        issues.append('存在残缺英文表达 (短语末尾缺宾语/补语)')

    # ── 规则 3: 正误对比完整性 ──
    wrong = _first_mistake(card, 'wrong')
    correct = _first_mistake(card, 'correct')
    if card.get('mistakes'):
        if not wrong:
            issues.append('mistakes 缺少 wrong 字段')
        if not correct:
            issues.append('mistakes 缺少 correct 字段')

    # ── 规则 4: 英语卡正确例句必须像完整句 ──
    if is_eng and correct and _has_english(correct):
        if not looks_like_complete_sentence(correct):
            issues.append('正确例句不是完整句')

    # ── 规则 5: 单卡知识点过多 ──
    if is_eng:
        candidates = detect_knowledge_candidates(card)
        if len(candidates) > MAX_KNOWLEDGE_POINTS + 1:
            issues.append(f'单卡知识点过多 ({len(candidates)}个), 建议拆分')

    # ── 规则 6: 错因过于笼统 ──
    if is_eng and vague_error_reason(card):
        issues.append('错因解释过于笼统 (如"词性错"), 需要具体说明')

    # ── 规则 7: 标题过长 ──
    title = card.get('title', '')
    if len(title) > 20:
        issues.append(f'标题过长 ({len(title)}字), 建议≤12字')

    # ── 规则 8: 定义缺失 ──
    if not card.get('definition', '').strip():
        issues.append('缺少 definition 字段')

    return {
        'pass': len(issues) == 0,
        'issues': issues,
        'stage': 'hard_rule',
    }


# ═══════════════════════════════════════════
# Layer 2: AI 教学审稿
# ═══════════════════════════════════════════

# 审稿 system prompt —— 只负责挑错，不负责创作
_REVIEW_SYSTEM_PROMPT = """你是一位严格的英语教学内容审稿员。
你只负责审稿，绝不负责创作。

你需要检查以下 5 个维度:
1. 语言自然度 — 英文例句是否地道自然
2. 语法准确性 — 语法、搭配、词性是否正确
3. 知识点聚焦 — 是否只聚焦一个主知识点，有无混杂
4. 正误对比清晰度 — 错句是否真错，正句是否真对，错因是否具体
5. 秒懂适配度 — 内容是否适合压缩成一张图片教学卡

严格按 JSON 格式输出，不要输出其他内容:
{
  "pass": true或false,
  "language_score": 0到100的整数,
  "teaching_score": 0到100的整数,
  "issues": ["问题1", "问题2"],
  "rewrite_suggestion": "如果不通过，给出具体修改建议；通过则留空"
}

评分标准:
- language_score ≥ 90: 英文地道自然，无语法错误
- language_score 70-89: 有小瑕疵但不影响理解
- language_score < 70: 有硬伤，不能出图

- teaching_score ≥ 85: 知识点聚焦，正误清晰，适合做卡
- teaching_score 70-84: 有改进空间但基本可用
- teaching_score < 70: 不适合出图

pass = true 的条件: language_score ≥ 90 且 teaching_score ≥ 85 且 issues 为空"""


def _build_review_user_prompt(card, subject=''):
    """构建审稿用户 prompt"""
    wrong = _first_mistake(card, 'wrong')
    correct = _first_mistake(card, 'correct')
    ex = card.get('example', {})

    lines = [
        f'学科: {subject}',
        f'标题: {card.get("title", "")}',
        f'定义: {card.get("definition", "")}',
        f'核心点: {json.dumps(card.get("core_points", []), ensure_ascii=False)}',
        f'例题: {ex.get("question", "")}',
        f'答案: {ex.get("answer", "")}',
        f'错句: {wrong}',
        f'正句: {correct}',
        f'口诀: {card.get("memory_tip", "")}',
    ]
    return '\n'.join(lines)


def review_teaching_quality(card, subject, gemini_call_fn, api_key, text_model='gemini-2.5-flash'):
    """
    调用 AI 进行教学质量审稿。

    参数:
      card          — 卡片 dict
      subject       — 学科名
      gemini_call_fn — generate_card_images.gemini_call 函数引用
      api_key       — Gemini API Key
      text_model    — 文字模型名

    返回:
      {
        'pass': bool,
        'language_score': int,
        'teaching_score': int,
        'issues': list[str],
        'rewrite_suggestion': str,
        'stage': 'ai_review',
        'raw': str  # 原始返回，便于调试
      }
    """
    user_prompt = _build_review_user_prompt(card, subject)
    contents = [
        {'role': 'user', 'parts': [{'text': f'{_REVIEW_SYSTEM_PROMPT}\n\n--- 待审稿卡片 ---\n{user_prompt}'}]}
    ]
    gen_config = {
        'maxOutputTokens': 2048,
        'temperature': 0.1,  # 审稿要稳定
    }

    resp = gemini_call_fn(text_model, contents, api_key, gen_config=gen_config)

    # 默认结果 (调用失败时放行，避免阻塞管线)
    default = {
        'pass': True,
        'language_score': 95,
        'teaching_score': 90,
        'issues': [],
        'rewrite_suggestion': '',
        'stage': 'ai_review',
        'raw': '',
    }

    if not resp:
        print('    [review] AI 审稿调用失败, 默认放行')
        return default

    # 解析返回
    try:
        candidates = resp.get('candidates', [])
        if not candidates:
            return default

        text = ''
        for part in candidates[0].get('content', {}).get('parts', []):
            if 'text' in part and not part.get('thought', False):
                text += part['text']

        # 尝试提取 JSON
        text = text.strip()
        # 去掉 markdown 代码块
        if text.startswith('```'):
            text = re.sub(r'^```\w*\n?', '', text)
            text = re.sub(r'\n?```$', '', text)
            text = text.strip()

        parsed = json.loads(text)
        result = {
            'pass': bool(parsed.get('pass', True)),
            'language_score': int(parsed.get('language_score', 95)),
            'teaching_score': int(parsed.get('teaching_score', 90)),
            'issues': list(parsed.get('issues', [])),
            'rewrite_suggestion': str(parsed.get('rewrite_suggestion', '')),
            'stage': 'ai_review',
            'raw': text,
        }

        # 强制执行阈值 (不信任模型自己的 pass 判断)
        if result['language_score'] < LANGUAGE_SCORE_THRESHOLD:
            result['pass'] = False
            if f'语言分 {result["language_score"]} < {LANGUAGE_SCORE_THRESHOLD}' not in result['issues']:
                result['issues'].append(f'语言分 {result["language_score"]} < {LANGUAGE_SCORE_THRESHOLD}')
        if result['teaching_score'] < TEACHING_SCORE_THRESHOLD:
            result['pass'] = False
            if f'教学分 {result["teaching_score"]} < {TEACHING_SCORE_THRESHOLD}' not in result['issues']:
                result['issues'].append(f'教学分 {result["teaching_score"]} < {TEACHING_SCORE_THRESHOLD}')

        return result

    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        print(f'    [review] 解析审稿结果失败: {e}')
        default['raw'] = text if 'text' in dir() else ''
        return default


# ═══════════════════════════════════════════
# Layer 3: 结构化 Payload 构建
# ═══════════════════════════════════════════

def build_structured_payload(card, subject='', review_result=None):
    """
    把卡片信息压缩成结构化的 prompt 输入。
    后续 prompt 生成只从这些字段里取值，不再自由抓原始 card。
    """
    review_result = review_result or {}
    wrong = _first_mistake(card, 'wrong')
    correct = _first_mistake(card, 'correct')
    ex = card.get('example', {})

    return {
        'title': card.get('title', ''),
        'card_type': card.get('type', ''),
        'subject': subject,
        'definition': card.get('definition', ''),
        'core_points': card.get('core_points', [])[:3],
        'example_question': ex.get('question', ''),
        'example_answer': ex.get('answer', ''),
        'example_steps': ex.get('steps', []),
        'wrong_example': wrong,
        'correct_example': correct,
        'memory_tip': card.get('memory_tip', ''),
        'difficulty': card.get('difficulty', 3),
        'is_english_grammar': is_english_grammar_card(card, subject),
        'review_hint': review_result.get('rewrite_suggestion', ''),
    }


# ═══════════════════════════════════════════
# 英语语法卡专用 Prompt 模板
# ═══════════════════════════════════════════

ENGLISH_GRAMMAR_PROMPT_TEMPLATE = """你是英语语法教学卡图片设计师。

核心原则:
- 一张卡只讲一个主知识点
- 只允许以下信息块: 标题 / 主规则 / 正误对比 / 错因 / 记忆点
- 不要混入第二个知识点
- 正句必须是完整自然英语
- 错因必须具体 (不能只写"词性错", 要写"succeed是动词, 这里需要名词success")

══════ 信息块固定结构 ══════

[标题] ≤8个中文字, 如"高频搭配: pay attention to"
[主规则] 一句话说清楚核心语法规则, ≤15字
[正确例句] 一个完整自然的英文例句
[错误例句] 一个典型错误的英文例句
[错因解释] 用中文具体说明为什么错, 标注词性/搭配/句法
[记忆点] ≤10字的口诀或助记

══════ 视觉设计 ══════

- 竖版 3:4 比例
- 渐变背景, 小红书风格 (鲜明温暖有活力)
- 标题用鲜色 banner, 超大加粗字体
- 正确例句: 绿色高亮关键词, 带 ✓ 标记
- 错误例句: 红色删除线关键词, 带 ✗ 标记
- 错因: 用箭头或色块指向错误位置
- 记忆点: 便签纸风格, 手写感
- 最多 3 处高亮重点
- 最多 3 个视觉区块
- ≥ 25% 留白
- 可爱小老师卡通角色 + ≤6字气泡

══════ 配色 ══════

- 背景: 渐变 (如薰衣草紫 #E8D5F5→#D9AAF5 或 薄荷蓝 #A1C4FD→#C2E9FB)
- ✓ 正确: 翠绿 #2ED573
- ✗ 错误: 亮红 #FF4757
- 标题: 饱和色 banner
- 错因: 橙色或蓝色色块

══════ 文字原则 ══════

- 全卡中文 ≤ 30 字
- 英文例句保持原样, 关键词高亮
- 标题 ≤ 8 字
- 错因 ≤ 15 字
- 记忆点 ≤ 10 字
- 不写段落, 不写解释性长文

══════ 输出 ══════

只输出一段英文图片生成提示词, 不输出其他内容。
提示词开头必须写: "IMPORTANT: All visible text must be Simplified Chinese (简体中文) except for English example sentences. LARGE BOLD font. Clean layout."
长度: 300-450 英文单词"""


def generate_english_grammar_prompt(payload, gemini_call_fn, api_key, text_model='gemini-2.5-flash'):
    """
    英语语法卡专用: 用结构化 payload 生成图片提示词。
    """
    card_info = f"""标题: {payload['title']}
主规则: {payload['definition'][:80]}
核心点: {', '.join(str(p) for p in payload['core_points'][:3])}
错误例句: {payload['wrong_example']}
正确例句: {payload['correct_example']}
例题: {payload['example_question'][:100]}
答案: {payload['example_answer'][:60]}
记忆点: {payload['memory_tip'][:30]}
{('审稿建议: ' + payload['review_hint'][:200]) if payload.get('review_hint') else ''}"""

    contents = [
        {'role': 'user', 'parts': [{'text': f'{ENGLISH_GRAMMAR_PROMPT_TEMPLATE}\n\n--- 卡片信息 ---\n{card_info}'}]}
    ]
    gen_config = {
        'maxOutputTokens': 8192,
        'temperature': 0.7,
        'thinkingConfig': {'thinkingBudget': 1024}
    }

    resp = gemini_call_fn(text_model, contents, api_key, gen_config=gen_config)
    if not resp:
        return None

    try:
        candidates = resp.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            best_text = ''
            for part in parts:
                if 'text' in part and not part.get('thought', False):
                    txt = part['text'].strip()
                    if len(txt) > len(best_text):
                        best_text = txt
            if len(best_text) > 50:
                return best_text
            # fallback
            for part in parts:
                if 'text' in part:
                    txt = part['text'].strip()
                    if len(txt) > len(best_text):
                        best_text = txt
            if len(best_text) > 50:
                return best_text
    except Exception as e:
        print(f'    [eng-prompt parse error] {e}')
    return None


# ═══════════════════════════════════════════
# 统一入口: 审校闸门
# ═══════════════════════════════════════════

def run_review_gate(card, subject, gemini_call_fn=None, api_key=None, text_model='gemini-2.5-flash'):
    """
    完整审校流程: 硬规则 → AI审稿 → 结构化输出。

    返回:
    {
        'pass': bool,
        'stage': 'hard_rule' | 'ai_review' | 'passed',
        'issues': list[str],
        'hard_result': dict,
        'review_result': dict | None,
        'payload': dict | None,
    }
    """
    is_eng = is_english_grammar_card(card, subject)

    # ── Layer 1: 硬规则 ──
    hard_result = validate_hard_rules(card, subject)
    if not hard_result['pass']:
        return {
            'pass': False,
            'stage': 'hard_rule',
            'issues': hard_result['issues'],
            'hard_result': hard_result,
            'review_result': None,
            'payload': None,
        }

    # ── Layer 2: AI 审稿 (只对英语语法卡启用, 其他学科跳过) ──
    review_result = None
    if is_eng and gemini_call_fn and api_key:
        review_result = review_teaching_quality(card, subject, gemini_call_fn, api_key, text_model)
        if not review_result['pass']:
            return {
                'pass': False,
                'stage': 'ai_review',
                'issues': review_result['issues'],
                'hard_result': hard_result,
                'review_result': review_result,
                'payload': None,
            }

    # ── Layer 3: 结构化 payload ──
    payload = build_structured_payload(card, subject, review_result)

    return {
        'pass': True,
        'stage': 'passed',
        'issues': [],
        'hard_result': hard_result,
        'review_result': review_result,
        'payload': payload,
    }
