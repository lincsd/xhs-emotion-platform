#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skill 反向学习闭环模块 — 从生成结果反哺 SkillSchema 参数。

设计理念:
  当前流程: SkillSchema → Prompt → 图片 → OCR审计 → 评分
  信息是单向的: Schema 只输出、不接收反馈

  本模块增加反向通道:
    生成统计 → 分析 Top 10% / Bottom 10% → 提取模式 → 优化建议
  
  具体优化项:
    1. max_chars 自适应: 如果某卡片类型的高分结果都在 10字以内 → 收紧上限
    2. color_scheme 优化: 从高分结果的 prompt 中提取常用配色
    3. forbidden 规则扩充: 从低分结果中提取反复出现的失败模式
    4. visual_method 排行: 哪个子类型策略效果最好
    5. 教学链路推荐: 最佳 teaching_chain 模式

版本: 1.0 (2026-03-28)
"""

from __future__ import annotations
import json
import os
import re
import sqlite3
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH = os.path.join(_BASE_DIR, 'optimizer.db')


@dataclass
class SkillFeedback:
    """单个卡片类型的反馈分析结果"""
    card_type: str
    sample_count: int = 0
    avg_score: float = 0.0
    top_10_avg: float = 0.0
    bottom_10_avg: float = 0.0
    
    # 自适应参数建议
    suggested_max_chars: Optional[int] = None
    suggested_max_per_block: Optional[int] = None
    
    # 高分模式提取
    top_color_schemes: list[str] = field(default_factory=list)
    top_visual_methods: list[str] = field(default_factory=list)
    
    # 低分失败模式
    failure_patterns: list[str] = field(default_factory=list)
    suggested_forbidden: list[str] = field(default_factory=list)
    
    # 教学链
    best_teaching_chains: list[str] = field(default_factory=list)
    
    confidence: float = 0.0  # 0-1, 基于样本量


def _get_conn():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def analyze_card_type(card_type: str, min_samples: int = 10) -> Optional[SkillFeedback]:
    """分析指定卡片类型的生成历史，提取优化建议。
    
    需要 optimizer.db 中有足够的 prompt_memory 记录。
    """
    if not os.path.exists(_DB_PATH):
        return None
    
    conn = _get_conn()
    try:
        # 获取该类型的所有生成记录
        rows = conn.execute("""
            SELECT prompt_text, manifest_json, combined_score, audit_score, quality_score
            FROM prompt_memory
            WHERE card_type = ? AND combined_score > 0
            ORDER BY combined_score DESC
        """, (card_type,)).fetchall()
        
        if len(rows) < min_samples:
            return None
        
        fb = SkillFeedback(card_type=card_type, sample_count=len(rows))
        scores = [r['combined_score'] for r in rows]
        fb.avg_score = statistics.mean(scores)
        
        # Top 10% / Bottom 10%
        n10 = max(1, len(rows) // 10)
        top_rows = rows[:n10]
        bottom_rows = rows[-n10:]
        fb.top_10_avg = statistics.mean(r['combined_score'] for r in top_rows)
        fb.bottom_10_avg = statistics.mean(r['combined_score'] for r in bottom_rows)
        
        # ── 1. max_chars 自适应 ──
        top_cn_counts = []
        for r in top_rows:
            manifest = _safe_json(r['manifest_json'])
            if manifest:
                cn = sum(
                    sum(1 for c in v if '\u4e00' <= c <= '\u9fff')
                    for v in manifest.values()
                )
                top_cn_counts.append(cn)
        
        if top_cn_counts:
            p90 = sorted(top_cn_counts)[int(len(top_cn_counts) * 0.9)]
            fb.suggested_max_chars = min(p90 + 3, 25)  # P90 + 3字余量
            
            # 每块字数
            top_per_block = []
            for r in top_rows:
                manifest = _safe_json(r['manifest_json'])
                if manifest:
                    for v in manifest.values():
                        cn = sum(1 for c in v if '\u4e00' <= c <= '\u9fff')
                        if cn > 0:
                            top_per_block.append(cn)
            if top_per_block:
                fb.suggested_max_per_block = min(
                    sorted(top_per_block)[int(len(top_per_block) * 0.9)] + 1, 8
                )
        
        # ── 2. 配色方案提取 ──
        color_counter = Counter()
        for r in top_rows:
            prompt = r['prompt_text'] or ''
            # 匹配常见配色描述
            colors = re.findall(
                r'(pastel|gradient|vivid|warm|cool|blue|green|orange|pink|purple|yellow|mint|coral|teal)',
                prompt.lower()
            )
            color_counter.update(colors)
        fb.top_color_schemes = [c for c, _ in color_counter.most_common(5)]
        
        # ── 3. 视觉方法排行 ──
        method_counter = Counter()
        for r in top_rows:
            prompt = r['prompt_text'] or ''
            methods = re.findall(
                r'(color.?coded blocks?|timeline|comparison|tree|flow|grid|split|side.?by.?side|mind map|diagram)',
                prompt.lower()
            )
            method_counter.update(methods)
        fb.top_visual_methods = [m for m, _ in method_counter.most_common(5)]
        
        # ── 4. 低分失败模式 ──
        fail_patterns = Counter()
        for r in bottom_rows:
            prompt = r['prompt_text'] or ''
            # 检测常见问题
            if len(prompt) > 2000:
                fail_patterns['prompt过长'] += 1
            if len(prompt) < 200:
                fail_patterns['prompt过短'] += 1
            manifest = _safe_json(r['manifest_json'])
            if manifest:
                cn = sum(
                    sum(1 for c in v if '\u4e00' <= c <= '\u9fff')
                    for v in manifest.values()
                )
                if cn > 20:
                    fail_patterns['中文字数过多'] += 1
                if cn == 0:
                    fail_patterns['无中文manifest'] += 1
            if 'background' in prompt.lower() and 'chinese' in prompt.lower():
                fail_patterns['背景含中文指令'] += 1
        
        fb.failure_patterns = [f'{p} ({c}次)' for p, c in fail_patterns.most_common(5)]
        
        # 建议新的 forbidden 规则
        if fail_patterns.get('prompt过长', 0) >= n10 * 0.5:
            fb.suggested_forbidden.append('prompt 不超过 1500 字')
        if fail_patterns.get('中文字数过多', 0) >= n10 * 0.5:
            fb.suggested_forbidden.append(f'中文总计不超过 {fb.suggested_max_chars or 15} 字')
        
        # ── 5. 教学链 (如果 v2 两阶段有记录) ──
        chain_counter = Counter()
        for r in top_rows:
            manifest = _safe_json(r['manifest_json'])
            if manifest and 'teaching_chain' in str(manifest):
                # v2 会把 teaching_chain 存在 manifest
                chain = manifest.get('teaching_chain', '')
                if chain:
                    chain_counter[chain] += 1
        fb.best_teaching_chains = [c for c, _ in chain_counter.most_common(3)]
        
        # 置信度
        fb.confidence = min(1.0, len(rows) / 50)
        
        return fb
    
    except Exception as e:
        print(f'[skill_feedback] analyze error: {e}')
        return None
    finally:
        conn.close()


def analyze_all_types(min_samples: int = 5) -> dict[str, SkillFeedback]:
    """分析所有已有数据的卡片类型"""
    if not os.path.exists(_DB_PATH):
        return {}
    
    conn = _get_conn()
    try:
        types = [r[0] for r in conn.execute(
            "SELECT DISTINCT card_type FROM prompt_memory WHERE card_type != ''"
        ).fetchall()]
    except:
        return {}
    finally:
        conn.close()
    
    results = {}
    for ct in types:
        fb = analyze_card_type(ct, min_samples=min_samples)
        if fb:
            results[ct] = fb
    return results


def get_feedback_summary(card_type: str) -> str:
    """获取人类可读的单卡片类型反馈摘要"""
    fb = analyze_card_type(card_type, min_samples=5)
    if not fb:
        return f'[feedback] {card_type}: 样本不足，无反馈'
    
    lines = [
        f'[feedback] {card_type}: {fb.sample_count}样本, avg={fb.avg_score:.0f}, '
        f'top10={fb.top_10_avg:.0f}, bottom10={fb.bottom_10_avg:.0f}, '
        f'confidence={fb.confidence:.0%}',
    ]
    
    if fb.suggested_max_chars:
        lines.append(f'  建议 max_chars: {fb.suggested_max_chars}')
    if fb.top_color_schemes:
        lines.append(f'  高分配色: {", ".join(fb.top_color_schemes[:3])}')
    if fb.top_visual_methods:
        lines.append(f'  高分视觉: {", ".join(fb.top_visual_methods[:3])}')
    if fb.failure_patterns:
        lines.append(f'  低分模式: {"; ".join(fb.failure_patterns[:3])}')
    if fb.suggested_forbidden:
        lines.append(f'  建议禁止: {"; ".join(fb.suggested_forbidden)}')
    
    return '\n'.join(lines)


def build_feedback_prompt_hint(card_type: str) -> str:
    """构建可注入 prompt 的反馈提示 (供 prompt_builder_v2 使用)。
    
    如果有足够数据，返回一段精简的提示，否则返回空字符串。
    """
    fb = analyze_card_type(card_type, min_samples=10)
    if not fb or fb.confidence < 0.3:
        return ''
    
    hints = []
    if fb.top_color_schemes:
        hints.append(f'Preferred colors: {", ".join(fb.top_color_schemes[:3])}')
    if fb.top_visual_methods:
        hints.append(f'Best visual methods: {", ".join(fb.top_visual_methods[:3])}')
    if fb.suggested_max_chars:
        hints.append(f'Optimal Chinese chars: ≤{fb.suggested_max_chars}')
    if fb.failure_patterns:
        avoid = '; '.join(p.split('(')[0].strip() for p in fb.failure_patterns[:2])
        hints.append(f'AVOID: {avoid}')
    
    if not hints:
        return ''
    
    return (
        '\n=== DATA-DRIVEN FEEDBACK (from generation history) ===\n'
        + '\n'.join(f'- {h}' for h in hints)
        + '\n=== END FEEDBACK ===\n'
    )


def apply_feedback_overrides(card_type: str, schema_dict: dict) -> dict:
    """基于生成历史动态覆盖 SkillSchema 参数 (v2.0 反馈闭环)。
    
    从 optimizer.db 分析高分/低分结果, 动态调整:
      - max_chars (如果高分结果普遍字数更少)
      - forbidden (如果低分结果有反复出现的失败模式)
      - visual_variants (如果某些变体得分明显更高)
    
    Args:
        card_type: 卡片类型名
        schema_dict: 可修改的 schema 参数字典
    
    Returns:
        覆盖后的 schema_dict (原地修改)
    """
    fb = analyze_card_type(card_type, min_samples=10)
    if not fb or fb.confidence < 0.4:
        return schema_dict
    
    # 1. 收紧 max_chars (如果高分结果字数更少)
    if fb.suggested_max_chars and fb.suggested_max_chars > 0:
        current_max = schema_dict.get('max_chars_overall', 0)
        if current_max == 0 or fb.suggested_max_chars < current_max:
            schema_dict['_feedback_max_chars'] = fb.suggested_max_chars
    
    # 2. 扩充 forbidden (如果低分有失败模式)
    if fb.suggested_forbidden:
        existing = schema_dict.get('forbidden', [])
        for new_rule in fb.suggested_forbidden:
            if new_rule not in existing:
                existing.append(f'[DATA] {new_rule}')
        schema_dict['forbidden'] = existing
    
    # 3. 记录最佳视觉方法 (供 visual_variants 排序)
    if fb.top_visual_methods:
        schema_dict['_feedback_best_visuals'] = fb.top_visual_methods[:3]
    
    return schema_dict


def _safe_json(text: str) -> dict:
    """安全解析 JSON"""
    if not text:
        return {}
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}


# ═══════════════════════════════════════════
# CLI Dashboard
# ═══════════════════════════════════════════
if __name__ == '__main__':
    print('=== Skill 反向学习闭环 Dashboard ===\n')
    
    all_fb = analyze_all_types(min_samples=3)
    if not all_fb:
        print('暂无足够数据 (需要 optimizer.db 中有 prompt_memory 记录)')
        print(f'DB路径: {_DB_PATH}')
        print(f'DB存在: {os.path.exists(_DB_PATH)}')
    else:
        for ct, fb in sorted(all_fb.items()):
            print(get_feedback_summary(ct))
            print()
        
        print(f'--- 总计 {len(all_fb)} 个卡片类型有反馈数据 ---')
