"""
Prompt 结构审计器 — 检查生成的 prompt 是否完整覆盖 Skill 规则要求。

设计理念:
  插入位置: Step 1 (prompt 生成) 之后、Step 2 (图片生成) 之前
  作用: 对生成的英文 prompt 做结构化检查，发现遗漏/违规后有两种处理:
    1. 轻微遗漏 → 自动补丁 (append missing instructions)
    2. 严重违规 → 标记警告 (供日志/统计用)

  检查维度:
    (a) 必需区块覆盖: 每个 required LayoutBlock 是否在 prompt 中有对应描述
    (b) 必需教学元素: required_elements 是否被提及
    (c) 禁止项检测: forbidden 规则是否被违反
    (d) 字数限制: TEXT_MANIFEST 中中文字数是否超标
    (e) 子类型一致性: 如果匹配了子类型，视觉方法是否被采用

版本: 1.0 (2025-06-27)
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

from skill_schema import (
    get_skill_schema, match_sub_type, get_required_elements,
    get_layout_checklist, get_forbidden_rules,
    SkillSchema,
)


# ═══════════════════════════════════════════
# 审计结果
# ═══════════════════════════════════════════

@dataclass
class AuditIssue:
    """单条审计问题"""
    category: str       # 'missing_block' | 'missing_element' | 'forbidden_violation' | 'char_overflow' | 'subtype_mismatch' | 'insufficiency'
    severity: str       # 'high' | 'medium' | 'low'
    description: str    # 人类可读描述
    auto_fix: str = ''  # 自动补丁文本（为空则不可自动修复）


@dataclass
class AuditResult:
    """完整审计结果"""
    card_type: str
    total_checks: int = 0
    passed_checks: int = 0
    issues: list[AuditIssue] = field(default_factory=list)
    coverage_pct: float = 0.0       # 覆盖率 (0-100)
    auto_patch: str = ''            # 可自动追加的补丁文本
    verdict: str = 'pass'           # 'pass' | 'warn' | 'fail'

    @property
    def score(self) -> int:
        """审计得分 (0-100)"""
        return round(self.coverage_pct)


# ═══════════════════════════════════════════
# 关键词映射: 教学元素 → prompt 中可能出现的英文关键词
# ═══════════════════════════════════════════

_ELEMENT_KEYWORDS: dict[str, list[str]] = {
    # NOTE: 每个条目都包含中文元素名本身，确保 skeleton/fill 中的中文能被匹配
    # 方法卡
    '例题': ['例题', 'example', 'problem', 'question', 'exercise', '题'],
    '色块分步解法': ['色块', '分步', '解法', 'color block', 'color-coded', 'color coded', 'step', 'split', 'break down', 'chunk', 'colored section', 'colored block'],
    '答案': ['答案', 'answer', 'result', 'solution', '='],
    '口诀': ['口诀', 'mnemonic', 'slogan', 'rhyme', 'tip', 'memory'],
    # 概念卡
    '生活场景图': ['生活场景', '场景图', 'life scene', 'daily', 'real life', 'illustration', 'scenario', 'object'],
    '概念金句': ['概念金句', '金句', 'key phrase', 'golden', 'one-liner', 'essence', 'concept'],
    # 辨析卡
    '左右对比区': ['对比区', '左右对比', 'compare', 'contrast', 'left', 'right', 'side by side', '✗', '✓', 'wrong', 'correct'],
    '红圈差异标注': ['红圈', '差异标注', 'red circle', 'highlight', 'mark the difference', 'annotate'],
    '金句': ['金句', 'key phrase', 'golden', 'summary', 'conclusion'],
    # 公式卡
    '可视化推导': ['可视化推导', '推导', 'visual derivation', 'grid', 'demonstrate', 'show why', 'derive'],
    '公式大字': ['公式', 'formula', 'large', 'prominent', 'oversized'],
    '代入计算': ['代入', '计算', 'substitute', 'plug in', 'calculate', 'compute'],
    # 陷阱卡
    '题目': ['题目', 'problem', 'question', 'exercise', 'challenge'],
    '钩子文案': ['钩子', '钩子文案', 'hook', '90%', 'trap', 'trick', 'most people'],
    '错误答案(划掉)': ['错误答案', '划掉', 'wrong', 'crossed', 'strike', '✗', 'incorrect'],
    '正确答案': ['正确答案', 'correct', 'right', '✓', 'actual answer'],
    '陷阱标注': ['陷阱', '标注', 'trap', 'pitfall', 'red circle', 'gotcha'],
    # 速算卡
    '慢方法vs速算法对比': ['慢方法', '速算', 'slow', 'fast', 'compare', 'turtle', 'lightning', 'conventional'],
    '速算步骤(≤2步)': ['速算步骤', 'shortcut step', 'quick step', 'trick step'],
    # 挑战卡
    '关卡编号': ['关卡', 'level', 'stage', 'round', 'challenge #'],
    '倒计时/挑战元素': ['倒计时', '挑战', 'timer', 'countdown', 'second', 'clock', 'challenge'],
    # 生活卡
    '场景大图': ['场景大图', '场景', 'scene', 'illustration', 'real life', 'daily'],
    '数学问题': ['数学问题', 'math problem', 'question', 'calculate'],
    '解法标注': ['解法标注', '标注', 'annotate', 'label', 'bubble', 'calculation'],
    '结论': ['结论', 'conclusion', 'result', 'summary'],
    # 对战卡
    'VS大字': ['VS', 'vs', 'versus', 'battle', 'compete'],
    '家长区题目': ['家长区', 'parent', 'adult', 'blue section'],
    '孩子区题目': ['孩子区', 'kid', 'child', 'pink section'],
    '计分栏': ['计分栏', 'score', 'point', 'scoreboard'],
    # 思维卡
    '趣味问题': ['趣味', '趣味问题', 'interesting', 'puzzle', 'think', 'brain'],
    '可视化思维过程': ['可视化思维', '思维过程', 'visual thinking', 'reasoning', 'diagram', 'step by step thinking'],
    '方法名': ['方法名', 'method name', 'technique', 'approach'],
    # ── 英语卡教学元素 ──
    # 词汇卡
    '英文关键词': ['英文关键词', 'key phrase', 'keyword', 'vocabulary', 'word'],
    '用法例句': ['用法例句', '例句', 'usage', 'sentence', 'example sentence'],
    '对错对比': ['对错对比', '❌', '✅', 'wrong', 'correct', 'contrast'],
    '记忆口诀': ['记忆口诀', '口诀', 'mnemonic', 'slogan', 'memory'],
    # 句型卡
    '句型公式': ['句型公式', '句型', 'sentence pattern', 'structure', 'formula'],
    '英文例句': ['英文例句', '例句', 'english sentence', 'example sentence', 'sentence'],
    # 语法卡
    '语法规则': ['语法规则', '语法', 'grammar rule', 'rule'],
    '可视化图示': ['可视化', '图示', '时间轴', 'visual', 'timeline', 'diagram', 'chart'],
    '速记公式': ['速记公式', '速记', 'quick formula', 'signal word'],
    # 易混词卡
    'vs对比标题': ['vs', 'versus', '对比标题', 'vs对比'],
    '双栏对比': ['双栏对比', '双栏', 'two column', 'side by side'],
    '速记区分': ['速记区分', '速记', 'distinction', 'mnemonic'],
    # 易混词陷阱卡
    '陷阱题': ['陷阱题', '陷阱', 'trap', 'trick'],
    '对错揭秘': ['对错揭秘', '揭秘', 'reveal', 'truth'],
    '速记口诀': ['速记口诀', '速记', '口诀', 'quick mnemonic'],
    # 语法辨析卡
    # (reuses 双栏对比, 英文例句, 速记口诀)
    # 知识总结卡
    '知识树/导图': ['知识树', '导图', '思维导图', 'mind map', 'tree'],
    '英文要点': ['英文要点', '要点', 'key point', 'english point'],
    '易错提醒': ['易错提醒', '易错', '陷阱', 'common trap', 'warning'],
    '真题速记': ['真题速记', '真题', 'real exam', 'exam example'],
    # 情景对话卡
    '情景图': ['情景图', '情景', '场景', 'scenario', 'scene'],
    '英文对话': ['英文对话', '对话', 'dialogue', 'conversation'],
    '替换练习': ['替换练习', '替换', 'substitution', 'practice'],
    # ── 理科卡教学元素 ──
    # 实验卡
    '实验目的': ['实验目的', '目的', 'purpose', 'objective', 'aim', 'goal'],
    '器材': ['器材', 'apparatus', 'equipment', 'instrument', 'material', 'tool'],
    '现象': ['现象', 'phenomenon', 'observation', 'observe', 'result'],
    # 公式推导卡
    '逐步推导': ['逐步推导', '推导', 'derive', 'derivation', 'proof', 'step-by-step'],
    # 过程流卡
    '流程图': ['流程图', '流程', 'flowchart', 'flow chart', 'process', 'pipeline', 'arrow'],
    '阶段色块': ['阶段', '色块', 'stage', 'phase', 'color block', 'section'],
    '物质/能量箭头': ['物质', '能量', '箭头', 'arrow', 'material flow', 'energy flow', 'input', 'output'],
    '关键方程': ['关键方程', '方程', 'equation', 'reaction', 'formula'],
    # 微观图解卡
    '微观图解': ['微观图解', '微观', 'micro', 'microscopic', 'particle', 'atom', 'molecule'],
    '宏微对应': ['宏微对应', '宏观', '微观', 'macro-micro', 'correspondence', 'relation'],
    # 图像解读卡
    '示例图像': ['示例图像', '图像', 'graph', 'chart', 'plot', 'curve', 'diagram'],
    '坐标轴标注': ['坐标轴', '标注', 'axis', 'label', 'x-axis', 'y-axis', 'coordinate'],
    '读图方法': ['读图方法', '读图', 'reading method', 'interpret', 'slope', 'trend'],
    '考法提示': ['考法提示', '考法', 'exam tip', 'test type', 'common question'],
    # 模型卡
    '模型示意图': ['模型示意图', '模型', 'model', 'schematic', 'diagram', 'illustration'],
    '核心假设': ['核心假设', '假设', 'assumption', 'hypothesis', 'premise', 'key idea'],
    '适用范围': ['适用范围', '适用', 'applicable', 'scope', 'valid', 'can explain'],
    '局限性': ['局限性', '局限', 'limitation', 'cannot explain', 'shortcoming'],
    # 解题策略卡
    '步骤方法': ['步骤方法', '步骤', '方法', 'step', 'method', 'strategy', 'procedure'],
    '每步要点': ['要点', 'key point', 'note', 'annotation', 'emphasis'],
    '检查清单': ['检查清单', '检查', 'checklist', 'verify', 'double check'],
    # 知识网络卡
    '知识网络图': ['知识网络', '网络图', 'knowledge network', 'mind map', 'concept map'],
    '核心节点': ['核心节点', '节点', 'core node', 'center', 'central concept'],
    '分支连线': ['分支', '连线', 'branch', 'connection', 'link', 'edge'],
    '核心公式/规律': ['核心公式', '规律', 'core formula', 'key law', 'principle'],
    # 术语精准卡
    '错误表述': ['错误表述', '错误', 'wrong', 'incorrect', '❌', 'mistake'],
    '精准表述': ['精准表述', '精准', '正确', 'precise', 'accurate', '✅', 'correct'],
    '扣分原因': ['扣分原因', '扣分', 'deduction', 'why wrong', 'scoring'],
}

# 布局区块名 → prompt 关键词
_BLOCK_KEYWORDS: dict[str, list[str]] = {
    # NOTE: 每个条目都包含中文区块名本身，确保 skeleton 中的 "BLOCK X: [中文名]" 能被匹配
    '标题': ['标题', 'title', 'heading', 'banner', 'header'],
    '例题': ['例题', 'example', 'problem', 'question'],
    '解法': ['解法', 'solution', 'method', 'step', 'approach', 'color block', 'color-coded', 'split', 'derive'],
    '答案': ['答案', 'answer', 'result', 'final'],
    '易错': ['易错', 'error', 'caution', 'warning', 'mistake', '⚠️'],
    '气泡(含类比)': ['气泡', '类比', 'bubble', 'analogy', 'teacher', 'mascot'],
    '生活场景大图': ['生活场景', '场景大图', 'scene', 'illustration', 'real life'],
    '概念提炼': ['概念提炼', '概念', 'concept', 'essence', 'key phrase'],
    '口诀+小老师': ['口诀', '小老师', 'mnemonic', 'slogan', 'teacher'],
    '对比区': ['对比区', '对比', 'compare', 'contrast', 'vs', 'left right'],
    '金句': ['金句', 'key phrase', 'summary', 'golden'],
    '推导图': ['推导图', '推导', 'derive', 'grid', 'proof', 'demonstrate'],
    '公式': ['公式', 'formula', 'equation'],
    '大题目': ['大题目', 'big problem', 'large text', 'prominent question'],
    '钩子': ['钩子', 'hook', '90%', 'most people'],
    '揭秘区': ['揭秘', 'reveal', 'truth', 'correct answer'],
    '关键点': ['关键点', 'key point', 'trap annotation'],
    '口诀': ['口诀', 'mnemonic', 'slogan', 'rhyme'],
    '题目': ['题目', 'problem', 'question'],
    '场景大图': ['场景大图', '场景', 'scene', 'illustration'],
    '数学问题': ['数学问题', 'math problem', 'word problem'],
    '结论': ['结论', 'conclusion', 'takeaway'],
    '关卡编号': ['关卡', 'level', 'stage', 'round'],
    '挑战元素': ['挑战', 'timer', 'countdown', 'challenge'],
    '选项区': ['选项', 'option', 'choice', 'A B C D'],
    '底部提示': ['底部提示', 'bottom hint', 'comment section'],
    'VS大字': ['VS', 'vs', 'versus'],
    '题目区-左': ['题目区-左', 'left problem', 'parent', 'blue'],
    '题目区-右': ['题目区-右', 'right problem', 'child', 'pink'],
    '底部计分栏': ['计分栏', 'scoreboard', 'scoring'],
    '问题': ['问题', 'question', 'puzzle', 'scenario'],
    '思维区': ['思维区', '思维', 'thinking', 'reasoning', 'diagram'],
    '小老师': ['小老师', 'teacher', 'mascot', 'character'],
    '口诀+气泡(含类比)': ['口诀', '气泡', '类比', 'mnemonic', 'bubble', 'analogy'],
    # ── 英语卡区块 ──
    '用法拓展区': ['用法拓展', '用法', 'usage', 'pattern', 'expand'],
    '对错对比': ['对错对比', '对错', '❌', '✅', 'wrong', 'correct', 'contrast'],
    '记忆口诀': ['记忆口诀', '口诀', 'mnemonic', 'slogan', 'memory tip'],
    '句型公式区': ['句型公式', '句型', 'sentence pattern', 'formula', 'structure'],
    '例句展示区': ['例句展示', '例句', 'example sentence', 'sentence'],
    '规则可视化区': ['规则可视化', '时间轴', 'timeline', 'rule visual', 'visual'],
    '例句区': ['例句区', '例句', 'sentence', 'example'],
    '速记公式': ['速记公式', '速记', 'quick formula', 'shortcut'],
    '双栏对比区': ['双栏对比', '双栏', 'two column', 'side by side', 'vs'],
    '速记区分': ['速记区分', '速记', 'distinction', 'mnemonic'],
    '陷阱题': ['陷阱题', '陷阱', 'trap', 'trick question'],
    '揭秘对比区': ['揭秘对比', '揭秘', 'reveal', '❌', '✅'],
    '速记区': ['速记区', '速记', 'quick memory', 'mnemonic'],
    '知识树/导图': ['知识树', '导图', '思维导图', 'mind map', 'knowledge tree'],
    '易错提醒': ['易错提醒', '易错', '⚠️', 'common trap', 'warning'],
    '真题速记': ['真题', '速记', 'real exam', 'exam example'],
    '情景区': ['情景区', '情景', '对话', 'scenario', 'dialogue', 'conversation'],
    '替换练习': ['替换练习', '替换', 'substitution', 'practice', 'variation'],
    # ── 理科卡区块 ──
    # 实验卡
    '目的与器材': ['目的与器材', '目的', '器材', 'purpose', 'apparatus', 'equipment', 'material', 'instrument', 'objective'],
    '步骤流程': ['步骤流程', '步骤', '流程', 'step', 'procedure', 'process', 'flow', 'method'],
    '现象与结论': ['现象与结论', '现象', '结论', 'phenomenon', 'observation', 'conclusion', 'result'],
    '安全/易错': ['安全', '易错', 'safety', 'caution', 'warning', 'common mistake', '⚠️'],
    # 公式推导卡
    '已知条件': ['已知条件', '已知', 'known', 'given', 'starting point', 'premise', 'axiom', 'law'],
    '推导过程': ['推导过程', '推导', 'derivation', 'derive', 'proof', 'step-by-step', 'algebraic'],
    '最终公式': ['最终公式', '公式', 'final formula', 'equation', 'result formula', 'formula'],
    '适用条件': ['适用条件', '适用', 'condition', 'applicable', 'limitation', 'prerequisite', 'valid when'],
    # 过程流卡
    '流程主体': ['流程主体', '流程', 'flow chart', 'process', 'pipeline', 'stage', 'phase', 'step'],
    '关键转化': ['关键转化', '转化', 'key reaction', 'transformation', 'conversion', 'equation'],
    # 微观图解卡
    '宏观现象': ['宏观现象', '宏观', 'macro', 'macroscopic', 'visible', 'observable', 'phenomenon'],
    '微观图解': ['微观图解', '微观', 'micro', 'microscopic', 'particle', 'molecular', 'atom', 'molecule'],
    '本质总结': ['本质总结', '本质', 'essence', 'fundamental', 'underlying', 'root cause', 'summary'],
    # 图像解读卡
    '示例图像': ['示例图像', '示例', 'graph', 'chart', 'plot', 'curve', 'coordinate', 'diagram', 'example graph'],
    '读图方法': ['读图方法', '读图', 'reading method', 'interpret', 'how to read', 'axis', 'trend', 'slope'],
    '考法提示': ['考法提示', '考法', 'exam tip', 'test pattern', 'common question', 'exam type'],
    '易错点': ['易错点', '易错', 'common mistake', 'pitfall', 'trap', 'error', '⚠️'],
    # 模型卡
    '模型图示': ['模型图示', '模型', 'model', 'diagram', 'schematic', 'illustration', 'structure'],
    '适用与局限': ['适用与局限', '适用', '局限', 'applicable', 'limitation', 'can explain', 'cannot explain', '✅', '❌'],
    '口诀/记忆': ['口诀', '记忆', 'mnemonic', 'memory', 'slogan', 'key idea'],
    # 解题策略卡
    '步骤方法': ['步骤方法', '步骤', '方法', 'step', 'method', 'strategy', 'approach', 'procedure'],
    '检查清单': ['检查清单', '检查', 'checklist', 'check', 'verify', 'common omission'],
    # 知识网络卡
    '知识网络图': ['知识网络图', '知识网络', '网络图', 'knowledge network', 'mind map', 'concept map', 'tree', 'radial'],
    '核心公式/规律': ['核心公式', '规律', 'core formula', 'key law', 'principle', 'equation'],
    '记忆口诀': ['记忆口诀', '口诀', 'mnemonic', 'slogan', 'memory tip'],
    # 术语精准卡
    '对比区': ['对比区', '对比', 'compare', 'contrast', 'vs', 'left right', '❌', '✅', 'wrong', 'correct'],
    '扣分解析': ['扣分解析', '扣分', 'deduction', 'why wrong', 'scoring', 'penalty', 'explanation'],
    '记忆技巧': ['记忆技巧', '记忆', 'memory trick', 'mnemonic', 'tip', 'technique'],
}


# ═══════════════════════════════════════════
# 审计引擎
# ═══════════════════════════════════════════

def audit_prompt(prompt_text: str, card_type: str, card_data: dict,
                  manifest: dict = None, grade: str = '') -> AuditResult:
    """对生成的 prompt 进行结构审计。
    
    Args:
        prompt_text: Step 1 生成的英文图片 prompt
        card_type: 卡片类型名
        card_data: 原始卡片 JSON 数据
        manifest: TEXT_MANIFEST 字典（可选）
        grade: 年级名（可选），用于分年级段 Skill 查找
    
    Returns:
        AuditResult 包含覆盖率、问题列表、自动补丁
    """
    schema = get_skill_schema(card_type, grade)
    if not schema:
        return AuditResult(card_type=card_type, total_checks=0, passed_checks=0,
                           coverage_pct=100.0, verdict='pass')

    result = AuditResult(card_type=card_type)
    patch_lines = []
    prompt_lower = prompt_text.lower()

    # ── Check 1: 必需布局区块覆盖 ──
    for block in schema.layout_blocks:
        result.total_checks += 1
        keywords = _BLOCK_KEYWORDS.get(block.name, [block.name.lower()])
        found = any(kw.lower() in prompt_lower for kw in keywords)

        if found:
            result.passed_checks += 1
        elif block.required:
            result.issues.append(AuditIssue(
                category='missing_block',
                severity='high',
                description=f'必需区块 [{block.name}] 未在 prompt 中找到',
                auto_fix=_generate_block_patch(block, card_data, schema),
            ))
        else:
            # 可选区块缺失 → low severity
            result.issues.append(AuditIssue(
                category='missing_block',
                severity='low',
                description=f'可选区块 [{block.name}] 未在 prompt 中出现',
            ))
            result.passed_checks += 1  # 可选的，不扣分

    # ── Check 2: 必需教学元素覆盖 ──
    for elem in schema.required_elements:
        result.total_checks += 1
        keywords = _ELEMENT_KEYWORDS.get(elem, [elem.lower()])
        found = any(kw.lower() in prompt_lower for kw in keywords)

        if found:
            result.passed_checks += 1
        else:
            desc = f'必需教学元素 [{elem}] 未在 prompt 中体现'
            fix = _generate_element_patch(elem, card_data)
            result.issues.append(AuditIssue(
                category='missing_element',
                severity='high',
                description=desc,
                auto_fix=fix,
            ))

    # ── Check 3: 禁止项检测 (反向检查) ──
    _check_forbidden(prompt_lower, schema, card_data, result)

    # ── Check 4: 字数限制 (通过 manifest) ──
    if manifest:
        _check_manifest_chars(manifest, schema, result)

    # ── Check 5: 子类型一致性 ──
    matched_sub = match_sub_type(card_type, card_data)
    if matched_sub:
        result.total_checks += 1
        # 检查视觉方法是否在 prompt 中有体现
        vm_keywords = matched_sub.visual_method.lower().split('/')
        vm_found = any(kw.strip() in prompt_lower for kw in vm_keywords if len(kw.strip()) > 2)
        if vm_found:
            result.passed_checks += 1
        else:
            result.issues.append(AuditIssue(
                category='subtype_mismatch',
                severity='medium',
                description=f'子类型 [{matched_sub.name}] 的视觉方法 "{matched_sub.visual_method}" 未在 prompt 中体现',
                auto_fix=f'\nADDITIONAL: Use {matched_sub.visual_method} for the main teaching area.',
            ))

    # ── Check 6 (L2): 充分性检查 — 关键内容是否具体而非空泛 ──
    _check_sufficiency(prompt_text, card_data, manifest, result)

    # ── Check 7 (v2.0): 认知负荷上限检查 ──
    _check_info_chunks(prompt_text, manifest, schema, result)

    # ── 计算覆盖率 ──
    result.coverage_pct = (result.passed_checks / max(result.total_checks, 1)) * 100

    # ── 聚合自动补丁 ──
    patches = [iss.auto_fix for iss in result.issues if iss.auto_fix]
    if patches:
        result.auto_patch = '\n=== AUTO-PATCH (appended by auditor) ===\n' + '\n'.join(patches) + '\n=== END PATCH ==='

    # ── 判定 ──
    high_issues = sum(1 for iss in result.issues if iss.severity == 'high')
    if high_issues >= 3 or result.coverage_pct < 50:
        result.verdict = 'fail'
    elif high_issues >= 1 or result.coverage_pct < 80:
        result.verdict = 'warn'
    else:
        result.verdict = 'pass'

    return result


# ═══════════════════════════════════════════
# 内部辅助
# ═══════════════════════════════════════════

def _generate_block_patch(block: LayoutBlock, card_data: dict, schema: SkillSchema) -> str:
    """为缺失的区块生成补丁指令"""
    patches = {
        '例题': lambda: f'MUST include a clear example problem: "{_get_example_question(card_data)}"',
        '解法': lambda: 'MUST include a visual solution area using color-coded blocks showing key steps.',
        '答案': lambda: 'MUST include a prominently displayed answer in large, bold text.',
        '易错': lambda: 'Consider adding a small red warning text for common mistakes.',
        '标题': lambda: f'MUST include a title (≤4 chars) at the top.',
        '生活场景大图': lambda: 'MUST include a large real-life scenario illustration (≥45% area).',
        '概念提炼': lambda: 'MUST include a one-line concept summary (≤6 chars).',
        '对比区': lambda: 'MUST include a side-by-side comparison area (≥50%): left ❌ vs right ✅.',
        '金句': lambda: 'MUST include a key summary phrase in extra-large text.',
        '推导图': lambda: 'MUST include a visual derivation (grid/diagram) showing WHY the formula works.',
        '公式': lambda: 'MUST include the formula in extra-large colored text + substitution calculation.',
        '大题目': lambda: 'MUST include the problem in extra-large text (≥20% area).',
        '揭秘区': lambda: 'MUST include a reveal section: left ❌ wrong (red) vs right ✅ correct (green).',
        '对比区': lambda: 'MUST include comparison: left 🐢slow method (gray) vs right ⚡fast method (colorful).',
    }

    gen = patches.get(block.name)
    if gen:
        return gen()
    return f'MUST include [{block.name}] block in the {block.placement} area.'


def _generate_element_patch(elem: str, card_data: dict) -> str:
    """为缺失的教学元素生成补丁指令"""
    if '例题' in elem:
        q = _get_example_question(card_data)
        return f'CRITICAL: Include this example problem prominently: "{q}"' if q else ''
    if '答案' in elem:
        return 'CRITICAL: The answer must be displayed in large bold colorful text.'
    if '口诀' in elem:
        tip = card_data.get('memory_tip', '')
        return f'Include mnemonic/slogan: "{tip}"' if tip else 'Include a mnemonic rhyme (≤8 chars).'
    if '对比' in elem:
        return 'Include a ❌/✅ comparison section showing common mistakes.'
    if '公式' in elem:
        return 'The formula must be the most prominent element on the card.'
    return f'MISSING: Ensure [{elem}] is included in the card design.'


def _get_example_question(card_data: dict) -> str:
    """从 card_data 提取例题"""
    ex = card_data.get('example', {})
    if isinstance(ex, str):
        return ex[:80]
    return (ex.get('question') or '')[:80]


def _check_forbidden(prompt_lower: str, schema: SkillSchema, card_data: dict, result: AuditResult):
    """检查禁止项"""
    # 通用禁止项检测关键词
    forbidden_detection = {
        '不画完整竖式': ['full vertical calculation', 'complete column'],
        '不省略题目': [],  # 通过必需元素检查
        '不写多于2步': [],  # 难以自动检测
        '类比不能太抽象': [],
        '不写教科书定义': ['textbook definition', 'formally defined as'],
        '不列多个概念': [],
        '不超过1组对比': [],
        '差异点不超过1个': [],
    }

    for rule in schema.forbidden:
        kws = forbidden_detection.get(rule, [])
        if kws:
            result.total_checks += 1
            violated = any(kw in prompt_lower for kw in kws)
            if violated:
                result.issues.append(AuditIssue(
                    category='forbidden_violation',
                    severity='high',
                    description=f'违反禁止规则: {rule}',
                ))
            else:
                result.passed_checks += 1


# ═══════════════════════════════════════════
# v2.0: 认知负荷检查
# ═══════════════════════════════════════════

def _check_info_chunks(prompt_text: str, manifest: dict,
                        schema: SkillSchema, result: AuditResult):
    """检查信息量是否超过认知负荷上限。
    
    通过统计 manifest 中的文本条目数和 prompt 中的教学要点数来估算
    信息块数量，若超过 schema.max_info_chunks 则发出警告。
    """
    max_chunks = schema.max_info_chunks
    if max_chunks <= 0:
        return

    result.total_checks += 1

    # 估算方法 1: manifest 中的条目数
    chunk_count = 0
    if manifest:
        chunk_count = len(manifest)

    # 估算方法 2: prompt 中的 BLOCK 数量 (粗略)
    block_mentions = len(re.findall(r'BLOCK \d+:', prompt_text, re.IGNORECASE))

    estimated_chunks = max(chunk_count, block_mentions)

    if estimated_chunks > max_chunks + 2:  # 容忍2个缓冲
        result.issues.append(AuditIssue(
            category='cognitive_overload',
            severity='medium',
            description=f'信息块数 ~{estimated_chunks} 超过认知负荷上限 {max_chunks}',
            auto_fix=f'REDUCE content to ≤{max_chunks} key information chunks. '
                     f'Remove lower-priority supplementary information.',
        ))
    else:
        result.passed_checks += 1


# ═══════════════════════════════════════════
# L2 充分性检查 — 超越 L1 关键词存在性
# ═══════════════════════════════════════════

def _check_sufficiency(prompt_text: str, card_data: dict, manifest: dict,
                        result: AuditResult):
    """L2 充分性检查: 验证 prompt 是否足够具体。
    
    L1 只检查 "是否提及了例题/答案/口诀" → 关键词匹配
    L2 进一步检查:
      (a) 例题是否包含实际题目文本，而不是泛化的 "include a problem"
      (b) 答案是否包含实际数值
      (c) 口诀是否包含实际文本
      (d) prompt长度是否在合理范围（过短=空泛, 过长=注意力衰减）
      (e) manifest 中文是否和 card_data 匹配（而不是 hallucinated）
      (f) 英语卡: 是否包含英文关键词
    """
    prompt_lower = prompt_text.lower()

    # ── L2-a: 例题具体性 ──
    result.total_checks += 1
    example = card_data.get('example', {})
    if isinstance(example, dict):
        q = example.get('question', '')
    else:
        q = str(example)[:80]
    
    if q and len(q) > 3:
        # 检查题目中的数字是否出现在 prompt 中
        nums_in_q = re.findall(r'\d+', q)
        if nums_in_q:
            nums_found = sum(1 for n in nums_in_q if n in prompt_text)
            if nums_found >= len(nums_in_q) * 0.5:
                result.passed_checks += 1
            else:
                result.issues.append(AuditIssue(
                    category='insufficiency',
                    severity='medium',
                    description=f'L2: 例题数字 {nums_in_q[:3]} 在 prompt 中只找到 {nums_found}/{len(nums_in_q)}',
                    auto_fix=f'CRITICAL: The example problem must use EXACT numbers: "{q}"',
                ))
        else:
            result.passed_checks += 1
    else:
        result.passed_checks += 1  # 无例题则跳过

    # ── L2-b: 答案具体性 ──
    result.total_checks += 1
    answer = ''
    if isinstance(example, dict):
        answer = str(example.get('answer', ''))
    
    if answer and len(answer) > 0:
        ans_nums = re.findall(r'\d+', answer)
        if ans_nums:
            ans_found = any(n in prompt_text for n in ans_nums)
            if ans_found:
                result.passed_checks += 1
            else:
                result.issues.append(AuditIssue(
                    category='insufficiency',
                    severity='medium',
                    description=f'L2: 答案 "{answer}" 的数值未在 prompt 中出现',
                    auto_fix=f'The answer section MUST show the exact result: {answer}',
                ))
        else:
            result.passed_checks += 1
    else:
        result.passed_checks += 1

    # ── L2-c: 口诀/记忆提示文本具体性 ──
    result.total_checks += 1
    memory_tip = card_data.get('memory_tip', '')
    if memory_tip and len(memory_tip) > 2:
        # 检查口诀文字是否出现在 manifest 或 prompt
        tip_chars = set(c for c in memory_tip if '\u4e00' <= c <= '\u9fff')
        if tip_chars:
            manifest_text = ' '.join(manifest.values()) if manifest else ''
            combined = prompt_text + ' ' + manifest_text
            chars_found = sum(1 for c in tip_chars if c in combined)
            if chars_found >= len(tip_chars) * 0.3:
                result.passed_checks += 1
            else:
                result.issues.append(AuditIssue(
                    category='insufficiency',
                    severity='low',
                    description=f'L2: 口诀 "{memory_tip[:15]}" 关键字 {chars_found}/{len(tip_chars)} 出现在 prompt/manifest',
                    auto_fix=f'The mnemonic/slogan MUST include: "{memory_tip[:12]}"',
                ))
        else:
            result.passed_checks += 1
    else:
        result.passed_checks += 1

    # ── L2-d: Prompt 长度合理性 ──
    result.total_checks += 1
    prompt_len = len(prompt_text)
    if prompt_len < 200:
        result.issues.append(AuditIssue(
            category='insufficiency',
            severity='high',
            description=f'L2: prompt 过短 ({prompt_len}字), 可能不够具体',
        ))
    elif prompt_len > 3000:
        result.issues.append(AuditIssue(
            category='insufficiency',
            severity='medium',
            description=f'L2: prompt 过长 ({prompt_len}字), 可能导致注意力衰减',
        ))
        result.passed_checks += 1  # 过长只扣半分
    else:
        result.passed_checks += 1

    # ── L2-e: Manifest 一致性 — 检查 manifest 是否匹配 card_data ──
    if manifest:
        result.total_checks += 1
        title = card_data.get('title', '')
        if title:
            # TITLE 字段应包含标题的关键字 (至少一个中文字匹配)
            title_in_manifest = False
            for k, v in manifest.items():
                if 'TITLE' in k.upper():
                    title_chars = set(c for c in title if '\u4e00' <= c <= '\u9fff')
                    v_chars = set(c for c in v if '\u4e00' <= c <= '\u9fff')
                    if title_chars and v_chars and title_chars & v_chars:
                        title_in_manifest = True
                    break
            if title_in_manifest:
                result.passed_checks += 1
            else:
                result.issues.append(AuditIssue(
                    category='insufficiency',
                    severity='low',
                    description=f'L2: manifest TITLE 与卡片标题 "{title[:12]}" 无交集',
                ))
        else:
            result.passed_checks += 1

    # ── L2-f: 英语卡英文关键词 ──
    card_type = card_data.get('type', '')
    is_english = any(kw in card_type for kw in ('词汇', '句型', '语法', '易混', '总结', '对话'))
    if is_english:
        result.total_checks += 1
        # 检查 prompt 中是否有引号包裹的英文短语
        english_phrases = re.findall(r'"([A-Za-z][\w\s]{2,})"', prompt_text)
        if english_phrases:
            result.passed_checks += 1
        else:
            result.issues.append(AuditIssue(
                category='insufficiency',
                severity='medium',
                description='L2: 英语卡的 prompt 中未找到引号包裹的英文关键短语',
                auto_fix='English card MUST include the target English phrase in double quotes.',
            ))


def _check_manifest_chars(manifest: dict, schema: SkillSchema, result: AuditResult):
    """检查 TEXT_MANIFEST 中文字数"""
    result.total_checks += 1

    total_cn = 0
    for v in manifest.values():
        total_cn += sum(1 for c in v if '\u4e00' <= c <= '\u9fff')

    if total_cn > 40:  # 全局上限 (与 v9.1 的 40字 对齐)
        result.issues.append(AuditIssue(
            category='char_overflow',
            severity='high',
            description=f'TEXT_MANIFEST 中文总字数 {total_cn} 超过上限 40',
        ))
    elif total_cn > 30:
        result.issues.append(AuditIssue(
            category='char_overflow',
            severity='medium',
            description=f'TEXT_MANIFEST 中文总字数 {total_cn} 偏多（建议≤30）',
        ))
        result.passed_checks += 1
    else:
        result.passed_checks += 1

    # 从 Schema 获取标题字数限制（如已注册），否则用默认值
    title_limit = 8  # 默认值（P1 放宽后）
    if schema:
        for b in schema.layout_blocks:
            if b.name == '标题' and b.max_chars > 0:
                title_limit = b.max_chars
                break

    # 逐块检查
    for k, v in manifest.items():
        cn_count = sum(1 for c in v if '\u4e00' <= c <= '\u9fff')
        block_limit = 8  # 默认每块上限
        if 'TITLE' in k.upper():
            block_limit = title_limit
        elif any(s in k.upper() for s in ('SLOGAN', '口诀', 'TIP')):
            block_limit = 10

        if cn_count > block_limit:
            result.issues.append(AuditIssue(
                category='char_overflow',
                severity='medium',
                description=f'文字块 {k}="{v}" 中文 {cn_count}字 超过 {block_limit}字限制',
            ))


# ═══════════════════════════════════════════
# 便捷 API
# ═══════════════════════════════════════════

def quick_audit(prompt_text: str, card_type: str, card_data: dict,
                manifest: dict = None) -> tuple[str, float, str]:
    """快速审计，返回 (verdict, coverage_pct, auto_patch)。
    
    用于流水线中快速判断是否需要补丁。
    
    Returns:
        (verdict, coverage_pct, auto_patch)
        - verdict: 'pass' | 'warn' | 'fail'
        - coverage_pct: 0-100
        - auto_patch: 自动补丁文本（空=不需要补丁）
    """
    result = audit_prompt(prompt_text, card_type, card_data, manifest)
    return result.verdict, result.coverage_pct, result.auto_patch


def audit_and_patch(prompt_text: str, card_type: str, card_data: dict,
                     manifest: dict = None, grade: str = '') -> tuple[str, AuditResult]:
    """审计并自动补丁 (如需要)。
    
    如果审计发现遗漏且有可用补丁，自动追加到 prompt 末尾。
    
    Returns:
        (patched_prompt, audit_result)
    """
    result = audit_prompt(prompt_text, card_type, card_data, manifest, grade)

    if result.auto_patch and result.verdict in ('warn', 'fail'):
        patched_prompt = prompt_text + '\n' + result.auto_patch
        return patched_prompt, result

    return prompt_text, result


def format_audit_summary(result: AuditResult) -> str:
    """格式化审计结果为人类可读的单行摘要"""
    issue_strs = []
    for iss in result.issues:
        if iss.severity == 'high':
            issue_strs.append(f'❌{iss.description[:30]}')
        elif iss.severity == 'medium':
            issue_strs.append(f'⚠️{iss.description[:30]}')

    issues_text = '; '.join(issue_strs[:3]) if issue_strs else '无问题'
    return (f'[审计] {result.card_type} coverage={result.coverage_pct:.0f}% '
            f'verdict={result.verdict} checks={result.passed_checks}/{result.total_checks} '
            f'| {issues_text}')


# ── 快速测试 ──
if __name__ == '__main__':
    # 模拟一个简单的 prompt 和卡片
    test_prompt = """
    Create a 3:4 vertical knowledge card about oral division.
    Title: "口除" in large bold text at top.
    Main area: Show the example problem "840 ÷ 4 = ?" prominently.
    Use color-coded blocks to split 840 into 800 and 40, showing step-by-step division.
    Answer section: Large bold "= 210" with mnemonic slogan.
    Small teacher character in corner with bubble.
    """

    test_card = {
        'title': '口算整十整百÷一位数',
        'type': '方法卡',
        'definition': '用拆数法',
        'example': {'question': '840 ÷ 4 = ?', 'steps': ['800÷4=200'], 'answer': '210'},
        'memory_tip': '拆开除再合体',
        'difficulty': 2,
    }

    test_manifest = {
        'TITLE': '口除',
        'LINE1': '拆开除',
        'SLOGAN': '再合体',
    }

    result = audit_prompt(test_prompt, '方法卡', test_card, test_manifest)
    print(format_audit_summary(result))
    print(f'\nCoverage: {result.coverage_pct:.1f}%')
    print(f'Verdict: {result.verdict}')
    print(f'Issues ({len(result.issues)}):')
    for iss in result.issues:
        print(f'  [{iss.severity}] {iss.category}: {iss.description}')
    if result.auto_patch:
        print(f'\nAuto-patch:\n{result.auto_patch}')
