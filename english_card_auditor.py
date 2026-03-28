"""
英语卡片审核器 — 对 AI 生成的英语学习卡片做多维度质量审核。

两层架构:
  规则层 (Rule Layer):  基于 OCR 文本 + JSON 源数据的确定性比对，免费，快速
  语义层 (Semantic Layer): 基于 Vision LLM 的教学评判，按需触发（仅规则层通过后）

审核8维度:
  ┌─ 规则层 ─────────────────────────────────────────────────┐
  │ D1. 英文文字准确性  — 拼写/语法/大小写/标点              │
  │ D2. 中文文字准确性  — 中文释义/口诀/术语 vs 源数据        │
  │ D7. 格式规范性      — 标题/区块/对比符号/留白             │
  │ D8. 防废片检测      — 空洞内容/卡通替代/万能废话          │
  └──────────────────────────────────────────────────────────┘
  ┌─ 语义层 (Vision LLM) ──────────────────────────────────┐
  │ D3. 教学内容正确性  — 用法/例句/语法规则是否正确          │
  │ D4. 教学完整性      — 用法+对比+口诀 三要素齐全？        │
  │ D5. 布局与信息层次  — 视觉层次/阅读流畅/信息密度         │
  │ D6. 视觉质量        — 配色/留白/小红书风格               │
  └──────────────────────────────────────────────────────────┘

集成方式:
  在 generate_card_images_v3.py 的 Step 3 之后插入:
    1. rule_audit_english() — 条件: subject=='英语'，输入 OCR 文本 + 源数据
    2. semantic_audit_english() — 条件: 规则层 verdict != 'fail'

版本: 1.0 (2026-03-28)
"""

from __future__ import annotations
import re
import json
from dataclasses import dataclass, field
from typing import Optional


# ═══════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════

@dataclass
class AuditIssue:
    """单条审核问题"""
    dimension: str          # 'D1'..'D8'
    category: str           # e.g. 'spelling', 'missing_contrast', 'junk_filler'
    severity: str           # 'critical' | 'major' | 'minor'
    description: str        # 人类可读描述
    evidence: str = ''      # 具体证据 (actual text / expected text)
    deduction: int = 0      # 扣分

@dataclass
class EnglishAuditResult:
    """英语卡片完整审核结果"""
    card_id: str = ''
    rule_score: int = 100           # 规则层得分 (0-100)
    semantic_score: int = -1        # 语义层得分 (-1=未执行, 0-100)
    final_score: int = 100          # 综合得分
    issues: list[AuditIssue] = field(default_factory=list)
    verdict: str = 'pass'           # 'pass' | 'warn' | 'fail'
    summary: str = ''
    dimension_scores: dict = field(default_factory=dict)  # D1..D8 → score

    @property
    def issue_count(self) -> dict:
        counts = {'critical': 0, 'major': 0, 'minor': 0}
        for i in self.issues:
            counts[i.severity] = counts.get(i.severity, 0) + 1
        return counts


# ═══════════════════════════════════════════
# 常量 & 词典
# ═══════════════════════════════════════════

# 万能废话（出现即扣分）
_JUNK_FILLERS = {
    '记住哦', '来看看', '一起学', '加油哦', '注意哦', '要记住',
    '来学习', '很简单', '不难哦', '看这里', '真棒',
    '搭配固定要多记', '重点词汇要掌握', '语法规则记清楚',
    '多练就会', '记住就好', '背了就行', '牢记即可', '熟能生巧',
}

# 常见 AI 拼写错误 (实际出错 → 正确)
_KNOWN_TYPOS = {
    'grammer': 'grammar', 'pronounciation': 'pronunciation',
    'occured': 'occurred', 'recieve': 'receive', 'seperate': 'separate',
    'definately': 'definitely', 'accomodate': 'accommodate',
    'enviroment': 'environment', 'goverment': 'government',
    'neccessary': 'necessary', 'occurence': 'occurrence',
    'recomend': 'recommend', 'succesful': 'successful',
    'untill': 'until', 'writting': 'writing',
    'progres': 'progress', 'beleive': 'believe',
    'calender': 'calendar', 'committment': 'commitment',
    'concious': 'conscious', 'dilemna': 'dilemma',
    'existance': 'existence', 'foriegn': 'foreign',
    'happend': 'happened', 'independant': 'independent',
    'millenium': 'millennium', 'noticable': 'noticeable',
    'persistant': 'persistent', 'priviledge': 'privilege',
    'publically': 'publicly', 'refered': 'referred',
    'relevent': 'relevant', 'rythm': 'rhythm',
    'sincerly': 'sincerely', 'tommorow': 'tomorrow',
    'truely': 'truly', 'wierd': 'weird',
}

# 中文语法术语常见渲染错误 (字形相似导致的OCR级错误)
_GRAMMAR_TERM_TYPOS = {
    '应语': '同位语', '宝语': '宾语', '壮语': '状语',
    '订语': '定语', '谓语': '谓语', '祈使句': '祈使句',
    '被洞句': '被动句', '虚你语气': '虚拟语气',
}

# 英语卡必需的视觉区块标识
_REQUIRED_BLOCKS = {
    'title': ['title', 'header', 'banner', '标题'],
    'usage': ['usage', 'structure', 'pattern', 'example', '用法', '搭配'],
    'contrast': ['contrast', 'wrong', 'correct', '❌', '✅', '✗', '✓', 'error', 'mistake'],
    'mnemonic': ['mnemonic', 'memory', 'tip', 'slogan', '口诀', '记忆'],
}

# 区块B（用法区）被卡通人物替代的信号词
_CARTOON_SIGNALS = [
    'cartoon', 'mascot', 'character', 'cute animal', 'teacher character',
    'speech bubble only', 'waving', 'chibi', 'kawaii',
]


# ═══════════════════════════════════════════
# 规则层审核 (D1, D2, D7, D8) — 无需 API 调用
# ═══════════════════════════════════════════

def rule_audit_english(
    ocr_texts: list[str],
    card_data: dict,
    manifest: dict,
    prompt_text: str = '',
    eng_key_phrase: str = '',
) -> EnglishAuditResult:
    """
    规则层审核: 基于 OCR 文本 + 源数据 JSON 的确定性比对。
    
    参数:
      ocr_texts: OCR 识别出的图片文字列表 (from ocr_audit['found_texts'])
      card_data: 卡片 JSON 源数据 (含 core_points, mistakes, memory_tip 等)
      manifest: TEXT_MANIFEST 字典 (期望文字)
      prompt_text: 生成的 prompt 文本 (用于检测废话/区块)
      eng_key_phrase: 核心英文短语 (由 _build_card_info_grammar 注入)
    
    返回: EnglishAuditResult (rule_score 已填充, semantic_score=-1)
    """
    result = EnglishAuditResult(
        card_id=card_data.get('full_id', card_data.get('card_id', '')),
    )
    
    # 将所有 OCR 文本拼成一个大字符串供全局搜索
    all_ocr = '\n'.join(str(t) for t in ocr_texts).lower()
    all_ocr_raw = '\n'.join(str(t) for t in ocr_texts)  # 保留大小写
    
    # 同时检查 prompt
    prompt_lower = prompt_text.lower() if prompt_text else ''
    
    issues = []
    
    # ── D1: 英文文字准确性 ──
    d1_issues = _check_d1_english_accuracy(all_ocr, all_ocr_raw, ocr_texts, card_data, eng_key_phrase)
    issues.extend(d1_issues)
    
    # ── D2: 中文文字准确性 ──
    d2_issues = _check_d2_chinese_accuracy(all_ocr, all_ocr_raw, card_data, manifest)
    issues.extend(d2_issues)
    
    # ── D7: 格式规范性 ──
    d7_issues = _check_d7_format(all_ocr, all_ocr_raw, prompt_lower, prompt_text, card_data, eng_key_phrase)
    issues.extend(d7_issues)
    
    # ── D8: 防废片检测 ──
    d8_issues = _check_d8_anti_junk(all_ocr, all_ocr_raw, prompt_lower, prompt_text, card_data)
    issues.extend(d8_issues)
    
    result.issues = issues
    
    # 计算得分
    total_deduction = sum(i.deduction for i in issues)
    result.rule_score = max(0, 100 - total_deduction)
    
    # 各维度得分
    for dim in ('D1', 'D2', 'D7', 'D8'):
        dim_ded = sum(i.deduction for i in issues if i.dimension == dim)
        result.dimension_scores[dim] = max(0, 25 - dim_ded)  # 每维度占25分
    
    # 判定
    crit = sum(1 for i in issues if i.severity == 'critical')
    major = sum(1 for i in issues if i.severity == 'major')
    
    if crit >= 1 or result.rule_score < 40:
        result.verdict = 'fail'
    elif major >= 2 or result.rule_score < 70:
        result.verdict = 'warn'
    else:
        result.verdict = 'pass'
    
    result.final_score = result.rule_score
    result.summary = _build_rule_summary(result)
    
    return result


def _check_d1_english_accuracy(
    all_ocr: str, all_ocr_raw: str, ocr_texts: list,
    card_data: dict, eng_key_phrase: str
) -> list[AuditIssue]:
    """D1: 英文文字准确性 — 拼写/关键短语缺失/已知错词"""
    issues = []
    
    # 1a. 核心英文短语是否出现在图片中
    if eng_key_phrase:
        phrase_lower = eng_key_phrase.lower().strip()
        # 允许部分匹配 (至少主要词出现)
        phrase_words = [w for w in phrase_lower.split() if len(w) >= 3]
        found_words = sum(1 for w in phrase_words if w in all_ocr)
        if phrase_words and found_words == 0:
            issues.append(AuditIssue(
                dimension='D1', category='eng_key_missing', severity='critical',
                description=f'核心英文短语 "{eng_key_phrase}" 在图片中完全不可见',
                evidence=f'expected="{eng_key_phrase}", found_words=0/{len(phrase_words)}',
                deduction=20,
            ))
        elif phrase_words and found_words < len(phrase_words) * 0.5:
            issues.append(AuditIssue(
                dimension='D1', category='eng_key_partial', severity='major',
                description=f'核心英文短语 "{eng_key_phrase}" 仅部分可见 ({found_words}/{len(phrase_words)}词)',
                evidence=f'missing words: {[w for w in phrase_words if w not in all_ocr]}',
                deduction=10,
            ))
    
    # 1b. 已知拼写错误检测
    # 在 OCR 文本中查找所有英文单词
    all_eng_words = re.findall(r'[a-zA-Z]{3,}', all_ocr_raw)
    for word in all_eng_words:
        word_lower = word.lower()
        if word_lower in _KNOWN_TYPOS:
            issues.append(AuditIssue(
                dimension='D1', category='spelling', severity='major',
                description=f'英文拼写错误: "{word}" → "{_KNOWN_TYPOS[word_lower]}"',
                evidence=f'OCR detected: {word}',
                deduction=8,
            ))
    
    # 1c. 英文乱码检测 — 检查是否有无意义字母串
    # 连续≥6个辅音字母 = 疑似乱码
    gibberish_pattern = re.findall(r'[bcdfghjklmnpqrstvwxyz]{6,}', all_ocr)
    for g in gibberish_pattern[:3]:
        issues.append(AuditIssue(
            dimension='D1', category='gibberish_en', severity='major',
            description=f'疑似英文乱码: "{g}"',
            evidence=g,
            deduction=8,
        ))
    
    # 1d. 检查 core_points 中的英文内容是否在图片中有对应
    core_eng_phrases = []
    for p in card_data.get('core_points', [])[:4]:
        # 提取英文短语
        phrases = re.findall(r'[a-zA-Z][a-zA-Z\s]{4,}', str(p))
        core_eng_phrases.extend(phrases[:2])
    
    if core_eng_phrases:
        found_any = False
        for phrase in core_eng_phrases:
            key_word = phrase.strip().split()[0].lower()
            if len(key_word) >= 3 and key_word in all_ocr:
                found_any = True
                break
        if not found_any and len(core_eng_phrases) >= 2:
            issues.append(AuditIssue(
                dimension='D1', category='core_content_missing', severity='major',
                description=f'core_points 中的英文内容在图片中完全不可见',
                evidence=f'checked phrases: {core_eng_phrases[:3]}',
                deduction=10,
            ))
    
    return issues


def _check_d2_chinese_accuracy(
    all_ocr: str, all_ocr_raw: str, card_data: dict, manifest: dict
) -> list[AuditIssue]:
    """D2: 中文文字准确性 — 中文与源数据/manifest 的一致性"""
    issues = []
    
    # 2a. manifest 中的期望中文 vs OCR 实际
    for key, expected in manifest.items():
        # 提取期望文字中的中文部分
        cn_chars = re.findall(r'[\u4e00-\u9fff]+', expected)
        if not cn_chars:
            continue
        cn_text = ''.join(cn_chars)
        if len(cn_text) < 2:
            continue
        
        # 检查是否在 OCR 中出现
        if cn_text not in all_ocr_raw:
            # 宽松匹配: 至少关键词出现
            key_part = cn_text[:4] if len(cn_text) >= 4 else cn_text
            if key_part not in all_ocr_raw:
                issues.append(AuditIssue(
                    dimension='D2', category='cn_text_missing', severity='major',
                    description=f'Manifest 期望文字 [{key}]="{expected}" 在图片中未找到',
                    evidence=f'expected_cn="{cn_text}", key_part="{key_part}"',
                    deduction=6,
                ))
    
    # 2b. 语法术语渲染错误检测
    for wrong, correct in _GRAMMAR_TERM_TYPOS.items():
        if wrong in all_ocr_raw:
            issues.append(AuditIssue(
                dimension='D2', category='grammar_term_typo', severity='critical',
                description=f'语法术语渲染错误: "{wrong}" → 应为 "{correct}"',
                evidence=f'OCR found: {wrong}',
                deduction=15,
            ))
    
    # 2c. 口诀/memory_tip 如果在 manifest 中，检查是否截断
    memory_tip = card_data.get('memory_tip', '').strip()
    if memory_tip and len(memory_tip) > 4:
        tip_cn = ''.join(re.findall(r'[\u4e00-\u9fff]+', memory_tip))
        if tip_cn:
            # 检查 OCR 中是否有被截断的版本
            for ocr_t in (str(t) for t in [all_ocr_raw]):
                truncated_pattern = re.findall(
                    r'([\u4e00-\u9fff]{3,})[了的得地]?$',
                    ocr_t.strip()
                )
                for trunc in truncated_pattern:
                    if trunc in tip_cn and len(trunc) < len(tip_cn) - 2:
                        issues.append(AuditIssue(
                            dimension='D2', category='truncated_text', severity='major',
                            description=f'口诀文字疑似被截断: "{trunc}..."',
                            evidence=f'full tip: "{memory_tip}"',
                            deduction=8,
                        ))
    
    return issues


def _check_d7_format(
    all_ocr: str, all_ocr_raw: str, prompt_lower: str, prompt_text: str,
    card_data: dict, eng_key_phrase: str
) -> list[AuditIssue]:
    """D7: 格式规范性 — 标题/区块结构/对比符号"""
    issues = []
    
    # 检查源: 优先用 prompt (图片生成前)，兼顾 OCR (图片生成后)
    check_text = prompt_lower or all_ocr
    
    # 7a. 标题区必须包含英文关键短语
    if eng_key_phrase:
        # 检查 prompt 中标题区是否有英文
        title_area = card_data.get('title', '')
        if title_area and not re.search(r'[a-zA-Z]{3,}', title_area):
            issues.append(AuditIssue(
                dimension='D7', category='title_no_english', severity='major',
                description=f'标题区缺少英文: title="{title_area}"',
                evidence=f'expected: "{eng_key_phrase}"',
                deduction=8,
            ))
    
    # 7b. ❌/✅ 对比区域是否存在
    has_contrast = any(sym in all_ocr_raw for sym in ('❌', '✅', '✗', '✓', '×', '✔'))
    if not has_contrast:
        # 也检查英文标记
        has_contrast = bool(re.search(r'(wrong|correct|error|right)\b', all_ocr))
    if not has_contrast and prompt_lower:
        has_contrast = '❌' in prompt_text or '✅' in prompt_text or '✗' in prompt_text
    if not has_contrast:
        issues.append(AuditIssue(
            dimension='D7', category='no_contrast_block', severity='major',
            description='缺少 ❌/✅ 对错对比区域',
            evidence='no contrast symbols found in OCR/prompt',
            deduction=10,
        ))
    
    # 7c. 口诀格式: 应为「英文关键词 + ≤4中文字」混合格式
    memory_tip = card_data.get('memory_tip', '').strip()
    if memory_tip:
        has_eng = bool(re.search(r'[a-zA-Z]{2,}', memory_tip))
        cn_count = len(re.findall(r'[\u4e00-\u9fff]', memory_tip))
        if not has_eng and cn_count > 4:
            issues.append(AuditIssue(
                dimension='D7', category='mnemonic_format', severity='minor',
                description=f'口诀应用「英文+≤4中文字」混合格式，当前纯中文: "{memory_tip[:30]}"',
                evidence=f'cn_chars={cn_count}, has_eng={has_eng}',
                deduction=3,
            ))
    
    # 7d. 检查错因标注是否用了中文句子 (应该用英文箭头标注)
    mistakes = card_data.get('mistakes', [])
    if mistakes:
        for m in mistakes[:2]:
            reason = m.get('reason', '')
            if reason:
                cn_in_reason = len(re.findall(r'[\u4e00-\u9fff]', reason))
                if cn_in_reason > 10:
                    issues.append(AuditIssue(
                        dimension='D7', category='contrast_cn_reason', severity='minor',
                        description=f'错因标注用了过长中文({cn_in_reason}字)，应用英文箭头格式',
                        evidence=f'reason: "{reason[:40]}"',
                        deduction=3,
                    ))
    
    return issues


def _check_d8_anti_junk(
    all_ocr: str, all_ocr_raw: str, prompt_lower: str, prompt_text: str,
    card_data: dict
) -> list[AuditIssue]:
    """D8: 防废片检测 — 万能废话/卡通替代/空洞内容"""
    issues = []
    
    # 8a. 万能废话检测
    check_text = all_ocr_raw or prompt_text or ''
    for filler in _JUNK_FILLERS:
        if filler in check_text:
            issues.append(AuditIssue(
                dimension='D8', category='junk_filler', severity='major',
                description=f'检测到万能废话: "{filler}"',
                evidence=f'found in {"OCR" if filler in all_ocr_raw else "prompt"}',
                deduction=5,
            ))
    
    # 8b. 卡通人物替代教学内容
    if prompt_lower:
        cartoon_found = [s for s in _CARTOON_SIGNALS if s in prompt_lower]
        # 检查: 如果有 cartoon 但缺少 usage/example 内容
        has_teaching = bool(re.search(
            r'(usage|structure|pattern|example sentence|搭配|用法)\s*[:：]',
            prompt_lower
        ))
        if cartoon_found and not has_teaching:
            issues.append(AuditIssue(
                dimension='D8', category='cartoon_replace', severity='critical',
                description=f'卡通人物可能替代了教学内容区域',
                evidence=f'cartoon signals: {cartoon_found[:3]}, teaching content not found',
                deduction=20,
            ))
    
    # 8c. 英文例句不足 — 英语卡应有≥2处完整英文例句(≥6词)
    # 从 OCR 文本中提取英文句子
    eng_sentences = re.findall(r'[A-Z][a-zA-Z\s,\']{10,}[.!?]', all_ocr_raw)
    # 补充: 不以大写开头但足够长的英文片段
    eng_fragments = re.findall(r'[a-zA-Z][a-zA-Z\s,\']{15,}', all_ocr_raw)
    total_eng = len(eng_sentences) + len(eng_fragments)
    
    if total_eng < 2 and all_ocr_raw:  # 只有有 OCR 文本时才检查
        issues.append(AuditIssue(
            dimension='D8', category='insufficient_examples', severity='major',
            description=f'英文例句不足: 仅检测到 {total_eng} 处，要求≥2处',
            evidence=f'sentences={len(eng_sentences)}, fragments={len(eng_fragments)}',
            deduction=10,
        ))
    
    # 8d. 完全无教学内容 (图片只有装饰)
    if all_ocr_raw:
        total_meaningful = len(re.findall(r'[a-zA-Z]{3,}', all_ocr_raw))
        cn_meaningful = len(re.findall(r'[\u4e00-\u9fff]', all_ocr_raw))
        if total_meaningful < 5 and cn_meaningful < 5:
            issues.append(AuditIssue(
                dimension='D8', category='empty_card', severity='critical',
                description=f'图片几乎无教学内容 (英文词{total_meaningful}个, 中文{cn_meaningful}字)',
                evidence='possible decoration-only card',
                deduction=25,
            ))
    
    return issues


# ═══════════════════════════════════════════
# 语义层审核 (D3, D4, D5, D6) — 需要 Vision LLM
# ═══════════════════════════════════════════

# 语义层审核 Prompt 模板
_SEMANTIC_AUDIT_PROMPT = """你是一位严格的英语教学卡片质量审核员。请从以下4个维度评估这张英语学习卡片图片。

本卡片的核心知识点: "{eng_key_phrase}"
卡片类型: {card_type}
年级: {grade}

═══ 维度 D3: 教学内容正确性 (25分) ═══
- 英文用法/搭配是否正确？语法规则有无错误？
- 例句语法是否正确？用词是否地道？
- ❌/✅ 对比中的错误是否是学生真正会犯的？
- 扣分: 语法错误每处-8，用法错误每处-5，例句不地道-3

═══ 维度 D4: 教学完整性 (25分) ═══
- 是否展示了≥2种不同用法/搭配？
- 是否有❌/✅对错对比（完整句子≥6词）？
- 是否有记忆口诀（含具体知识，非废话）？
- 缺少一个核心区块-10分

═══ 维度 D5: 布局与信息层次 (25分) ═══
- 标题→用法→对比→口诀 是否层次清晰？
- 重点信息是否突出？次要信息是否收敛？
- 阅读是否流畅？视觉动线是否自然？
- 是否有足够留白(≥25%)？

═══ 维度 D6: 视觉质量 (25分) ═══
- 配色是否鲜明和谐？是否有小红书爆款感？
- 英文是否清晰可读？中文是否粗体清晰？
- 是否竖屏3:4？是否有圆角卡片区块？
- 装饰元素是否克制（卡通角色≤10%面积）？

请用严格JSON格式回复：
{{
  "D3_teaching_correctness": {{
    "score": 20,
    "issues": ["issue1", "issue2"],
    "comment": "一句话评价"
  }},
  "D4_teaching_completeness": {{
    "score": 22,
    "issues": [],
    "comment": "一句话评价"
  }},
  "D5_layout_hierarchy": {{
    "score": 18,
    "issues": ["issue1"],
    "comment": "一句话评价"
  }},
  "D6_visual_quality": {{
    "score": 21,
    "issues": [],
    "comment": "一句话评价"
  }},
  "total": 81,
  "overall_comment": "一句话总评"
}}

只输出JSON，不要其他文字。"""


def build_semantic_audit_prompt(card_data: dict, eng_key_phrase: str = '') -> str:
    """构建语义层审核 Prompt"""
    card_type = card_data.get('type', '语法辨析卡')
    grade = card_data.get('grade', '')
    if not grade:
        # 从 full_id 推断
        fid = card_data.get('full_id', '')
        grade = fid.split('-')[1] if '-' in fid else ''
    
    return _SEMANTIC_AUDIT_PROMPT.format(
        eng_key_phrase=eng_key_phrase or card_data.get('_eng_key_phrase', card_data.get('title', '')),
        card_type=card_type,
        grade=grade,
    )


def parse_semantic_audit_response(response_text: str) -> tuple[dict, list[AuditIssue]]:
    """
    解析语义层审核 LLM 响应。
    
    返回: (dimension_scores, issues)
    """
    dim_scores = {}
    issues = []
    
    try:
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            return {}, []
        
        data = json.loads(json_match.group())
        
        dim_map = {
            'D3_teaching_correctness': ('D3', 'teaching_correctness'),
            'D4_teaching_completeness': ('D4', 'teaching_completeness'),
            'D5_layout_hierarchy': ('D5', 'layout_hierarchy'),
            'D6_visual_quality': ('D6', 'visual_quality'),
        }
        
        for key, (dim, cat) in dim_map.items():
            block = data.get(key, {})
            score = block.get('score', 0)
            dim_scores[dim] = min(25, max(0, score))
            
            for issue_text in block.get('issues', []):
                severity = 'minor'
                deduction = 3
                if score < 15:
                    severity = 'critical'
                    deduction = 8
                elif score < 20:
                    severity = 'major'
                    deduction = 5
                
                issues.append(AuditIssue(
                    dimension=dim,
                    category=cat,
                    severity=severity,
                    description=str(issue_text)[:100],
                    deduction=deduction,
                ))
        
        return dim_scores, issues
    
    except (json.JSONDecodeError, Exception):
        return {}, []


def semantic_audit_english(
    image_data: bytes,
    card_data: dict,
    api_key: str,
    eng_key_phrase: str = '',
    gemini_call_fn=None,
    all_keys: list = None,
) -> tuple[int, dict, list[AuditIssue]]:
    """
    语义层审核: 调用 Vision LLM 评估教学质量。
    
    参数:
      image_data: 图片二进制数据
      card_data: 卡片 JSON
      api_key: API key
      eng_key_phrase: 核心英文短语
      gemini_call_fn: gemini_call 函数引用 (避免 circular import)
      all_keys: 所有可用 API key
    
    返回: (semantic_score, dimension_scores, issues)
    """
    import base64
    
    if not gemini_call_fn:
        return -1, {}, []
    
    prompt = build_semantic_audit_prompt(card_data, eng_key_phrase)
    
    b64_img = base64.b64encode(image_data).decode('utf-8')
    contents = [
        {'role': 'user', 'parts': [
            {'text': prompt},
            {'inlineData': {'mimeType': 'image/png', 'data': b64_img}}
        ]}
    ]
    gen_config = {
        'maxOutputTokens': 2048,
        'temperature': 0.1,
    }
    
    # 使用 TEXT_MODEL (Gemini Flash)
    try:
        resp = gemini_call_fn('gemini-2.5-flash', contents, api_key,
                              gen_config=gen_config, all_keys=all_keys)
    except Exception:
        return -1, {}, []
    
    if not resp:
        return -1, {}, []
    
    try:
        candidates = resp.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            for part in parts:
                if 'text' in part and not part.get('thought', False):
                    dim_scores, issues = parse_semantic_audit_response(part['text'])
                    if dim_scores:
                        total = sum(dim_scores.values())
                        return total, dim_scores, issues
    except Exception:
        pass
    
    return -1, {}, []


# ═══════════════════════════════════════════
# 组合审核入口
# ═══════════════════════════════════════════

def full_english_audit(
    ocr_result: dict,
    image_data: bytes,
    card_data: dict,
    manifest: dict,
    prompt_text: str = '',
    eng_key_phrase: str = '',
    api_key: str = '',
    gemini_call_fn=None,
    all_keys: list = None,
    skip_semantic: bool = False,
) -> EnglishAuditResult:
    """
    执行完整英语卡片审核 (规则层 + 语义层)。
    
    参数:
      ocr_result: ocr_audit() 的返回结果
      image_data: 图片二进制数据
      card_data: 卡片源数据
      manifest: TEXT_MANIFEST  
      prompt_text: 生成的 prompt
      eng_key_phrase: 核心英文短语
      api_key: API key (语义层用)
      gemini_call_fn: gemini_call 函数引用
      all_keys: 所有 API key
      skip_semantic: 是否跳过语义层 (省 API 调用)
    
    返回: EnglishAuditResult (完整)
    """
    
    # ── Step A: 规则层审核 ──
    ocr_texts = ocr_result.get('found_texts', [])
    result = rule_audit_english(
        ocr_texts=ocr_texts,
        card_data=card_data,
        manifest=manifest,
        prompt_text=prompt_text,
        eng_key_phrase=eng_key_phrase,
    )
    
    # ── Step B: 是否触发语义层 ──
    if skip_semantic or result.verdict == 'fail':
        # 规则层已 fail，不浪费 API 调用
        if result.verdict == 'fail':
            result.summary += ' | 规则层已失败，跳过语义层'
        return result
    
    if not api_key or not gemini_call_fn or not image_data:
        return result
    
    # ── Step C: 语义层审核 ──
    sem_score, sem_dims, sem_issues = semantic_audit_english(
        image_data=image_data,
        card_data=card_data,
        api_key=api_key,
        eng_key_phrase=eng_key_phrase,
        gemini_call_fn=gemini_call_fn,
        all_keys=all_keys,
    )
    
    if sem_score >= 0:
        result.semantic_score = sem_score
        result.dimension_scores.update(sem_dims)
        result.issues.extend(sem_issues)
        
        # 综合得分: 规则层 50% + 语义层 50%
        result.final_score = round(result.rule_score * 0.5 + sem_score * 0.5)
        
        # 重新判定
        sem_crit = sum(1 for i in sem_issues if i.severity == 'critical')
        if sem_crit >= 1 or result.final_score < 40:
            result.verdict = 'fail'
        elif result.final_score < 70:
            result.verdict = 'warn'
        else:
            result.verdict = 'pass'
        
        result.summary = _build_full_summary(result)
    
    return result


# ═══════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════

def _build_rule_summary(result: EnglishAuditResult) -> str:
    """构建规则层审核摘要"""
    ic = result.issue_count
    parts = []
    if ic['critical']:
        parts.append(f'{ic["critical"]}严重')
    if ic['major']:
        parts.append(f'{ic["major"]}重要')
    if ic['minor']:
        parts.append(f'{ic["minor"]}轻微')
    
    issue_str = '/'.join(parts) if parts else '无问题'
    return f'[英语规则审核] {result.rule_score}/100 {result.verdict.upper()} ({issue_str})'


def _build_full_summary(result: EnglishAuditResult) -> str:
    """构建完整审核摘要"""
    dims = result.dimension_scores
    dim_str = ' '.join(f'{k}={v}' for k, v in sorted(dims.items()))
    return (
        f'[英语审核] 规则={result.rule_score} 语义={result.semantic_score} '
        f'综合={result.final_score}/100 {result.verdict.upper()} | {dim_str}'
    )


def format_english_audit(result: EnglishAuditResult) -> str:
    """格式化完整审核报告 (用于日志)"""
    lines = [
        f'╔══ 英语卡片审核报告 ══╗',
        f'║ 卡片: {result.card_id}',
        f'║ 规则层: {result.rule_score}/100',
    ]
    if result.semantic_score >= 0:
        lines.append(f'║ 语义层: {result.semantic_score}/100')
    lines.append(f'║ 综合: {result.final_score}/100 [{result.verdict.upper()}]')
    
    if result.dimension_scores:
        lines.append(f'║ 维度得分:')
        for dim in sorted(result.dimension_scores):
            lines.append(f'║   {dim}: {result.dimension_scores[dim]}')
    
    if result.issues:
        lines.append(f'║ 问题 ({len(result.issues)}):')
        for i, issue in enumerate(result.issues[:10], 1):
            sev_icon = {'critical': '🔴', 'major': '🟡', 'minor': '🔵'}.get(issue.severity, '⚪')
            lines.append(f'║   {i}. {sev_icon} [{issue.dimension}] {issue.description}')
    
    lines.append(f'╚{"═" * 30}╝')
    return '\n'.join(lines)


def is_english_card(card_data: dict, subject: str = '') -> bool:
    """判断是否为英语卡片，供 pipeline 调用"""
    if subject == '英语' or subject.lower() == 'english':
        return True
    _eng_types = {
        '语法辨析卡', '句型卡', '易混词卡', '易混词陷阱卡', '语法纠错卡',
        '词汇卡', '高频活用卡', '搭配卡', '词性辨析卡',
        '自然拼读卡', '情景对话卡',
        '听力得分卡', '拼写零错卡', '填空必会卡', '匹配速解卡',
        '阅读通关卡', '写作模板卡', '选择秒杀卡',
        '发音挑战卡', '情景闯关卡', '亲子英语PK卡', '速记卡',
    }
    return card_data.get('type', '') in _eng_types
