#!/usr/bin/env python3
"""
知识卡片 HTML 渲染器 v2 — 小红书精美卡片
========================================
用 HTML/CSS 模板 + Chrome headless 截图生成卡片图片。
v2: 全新精美设计，海报级视觉效果，适合小红书/社交媒体发布。

用法:
  python generate_card_images_html.py knowledge_cards/小学/数学_三下.json
  python generate_card_images_html.py knowledge_cards/小学/数学_三下.json --card 05-03
  python generate_card_images_html.py knowledge_cards/小学/数学_三下.json --test
  python generate_card_images_html.py knowledge_cards/小学/数学_三下.json --output card_images
"""

import json, os, sys, time, base64, tempfile, html as html_module

# ─── Card type → color theme mapping (v2: richer palettes) ───
CARD_TYPE_THEMES = {
    '方法卡': {
        'bg1': '#6C5CE7', 'bg2': '#a855f7',
        'banner': '#7C3AED', 'bannerLight': 'rgba(124,58,237,0.12)',
        'accent': '#8B5CF6', 'accent2': '#C084FC',
        'cardBg': 'rgba(255,255,255,0.92)', 'textDark': '#1E1B4B',
        'decoColor': 'rgba(139,92,246,0.12)', 'decoColor2': 'rgba(192,132,252,0.15)',
        'icon': '📐', 'tagBg': '#EDE9FE', 'tagColor': '#6D28D9',
    },
    '概念卡': {
        'bg1': '#0EA5E9', 'bg2': '#38BDF8',
        'banner': '#0284C7', 'bannerLight': 'rgba(2,132,199,0.12)',
        'accent': '#0EA5E9', 'accent2': '#7DD3FC',
        'cardBg': 'rgba(255,255,255,0.92)', 'textDark': '#0C4A6E',
        'decoColor': 'rgba(14,165,233,0.12)', 'decoColor2': 'rgba(125,211,252,0.15)',
        'icon': '💡', 'tagBg': '#E0F2FE', 'tagColor': '#0369A1',
    },
    '辨析卡': {
        'bg1': '#9333EA', 'bg2': '#C084FC',
        'banner': '#7E22CE', 'bannerLight': 'rgba(126,34,206,0.12)',
        'accent': '#A855F7', 'accent2': '#D8B4FE',
        'cardBg': 'rgba(255,255,255,0.92)', 'textDark': '#3B0764',
        'decoColor': 'rgba(168,85,247,0.12)', 'decoColor2': 'rgba(216,180,254,0.15)',
        'icon': '🔍', 'tagBg': '#F3E8FF', 'tagColor': '#7E22CE',
    },
    '公式卡': {
        'bg1': '#2563EB', 'bg2': '#60A5FA',
        'banner': '#1D4ED8', 'bannerLight': 'rgba(29,78,216,0.12)',
        'accent': '#3B82F6', 'accent2': '#93C5FD',
        'cardBg': 'rgba(255,255,255,0.92)', 'textDark': '#1E3A5F',
        'decoColor': 'rgba(59,130,246,0.12)', 'decoColor2': 'rgba(147,197,253,0.15)',
        'icon': '📏', 'tagBg': '#DBEAFE', 'tagColor': '#1D4ED8',
    },
    '陷阱卡': {
        'bg1': '#DC2626', 'bg2': '#F87171',
        'banner': '#B91C1C', 'bannerLight': 'rgba(185,28,28,0.12)',
        'accent': '#EF4444', 'accent2': '#FCA5A5',
        'cardBg': 'rgba(255,255,255,0.92)', 'textDark': '#450A0A',
        'decoColor': 'rgba(239,68,68,0.12)', 'decoColor2': 'rgba(252,165,165,0.15)',
        'icon': '⚠️', 'tagBg': '#FEE2E2', 'tagColor': '#B91C1C',
    },
    '速算卡': {
        'bg1': '#EA580C', 'bg2': '#FB923C',
        'banner': '#C2410C', 'bannerLight': 'rgba(194,65,12,0.12)',
        'accent': '#F97316', 'accent2': '#FDBA74',
        'cardBg': 'rgba(255,255,255,0.92)', 'textDark': '#431407',
        'decoColor': 'rgba(249,115,22,0.12)', 'decoColor2': 'rgba(253,186,116,0.15)',
        'icon': '⚡', 'tagBg': '#FFEDD5', 'tagColor': '#C2410C',
    },
    '挑战卡': {
        'bg1': '#E11D48', 'bg2': '#FB7185',
        'banner': '#BE123C', 'bannerLight': 'rgba(190,18,60,0.12)',
        'accent': '#F43F5E', 'accent2': '#FDA4AF',
        'cardBg': 'rgba(255,255,255,0.92)', 'textDark': '#4C0519',
        'decoColor': 'rgba(244,63,94,0.12)', 'decoColor2': 'rgba(253,164,175,0.15)',
        'icon': '🏆', 'tagBg': '#FFE4E6', 'tagColor': '#BE123C',
    },
    '生活卡': {
        'bg1': '#059669', 'bg2': '#34D399',
        'banner': '#047857', 'bannerLight': 'rgba(4,120,87,0.12)',
        'accent': '#10B981', 'accent2': '#6EE7B7',
        'cardBg': 'rgba(255,255,255,0.92)', 'textDark': '#022C22',
        'decoColor': 'rgba(16,185,129,0.12)', 'decoColor2': 'rgba(110,231,183,0.15)',
        'icon': '🏠', 'tagBg': '#D1FAE5', 'tagColor': '#047857',
    },
    '对战卡': {
        'bg1': '#7C3AED', 'bg2': '#F59E0B',
        'banner': '#6D28D9', 'bannerLight': 'rgba(109,40,217,0.12)',
        'accent': '#8B5CF6', 'accent2': '#FBBF24',
        'cardBg': 'rgba(255,255,255,0.92)', 'textDark': '#1C1917',
        'decoColor': 'rgba(139,92,246,0.12)', 'decoColor2': 'rgba(251,191,36,0.15)',
        'icon': '⚔️', 'tagBg': '#EDE9FE', 'tagColor': '#6D28D9',
    },
    '思维卡': {
        'bg1': '#4F46E5', 'bg2': '#818CF8',
        'banner': '#4338CA', 'bannerLight': 'rgba(67,56,202,0.12)',
        'accent': '#6366F1', 'accent2': '#A5B4FC',
        'cardBg': 'rgba(255,255,255,0.92)', 'textDark': '#1E1B4B',
        'decoColor': 'rgba(99,102,241,0.12)', 'decoColor2': 'rgba(165,180,252,0.15)',
        'icon': '🧠', 'tagBg': '#E0E7FF', 'tagColor': '#4338CA',
    },
    # 语文/英语额外卡型
    '基础卡': {
        'bg1': '#0891B2', 'bg2': '#22D3EE',
        'banner': '#0E7490', 'bannerLight': 'rgba(14,116,144,0.12)',
        'accent': '#06B6D4', 'accent2': '#67E8F9',
        'cardBg': 'rgba(255,255,255,0.92)', 'textDark': '#083344',
        'decoColor': 'rgba(6,182,212,0.12)', 'decoColor2': 'rgba(103,232,249,0.15)',
        'icon': '📚', 'tagBg': '#CFFAFE', 'tagColor': '#0E7490',
    },
    '阅读卡': {
        'bg1': '#7C3AED', 'bg2': '#A78BFA',
        'banner': '#6D28D9', 'bannerLight': 'rgba(109,40,217,0.12)',
        'accent': '#8B5CF6', 'accent2': '#C4B5FD',
        'cardBg': 'rgba(255,255,255,0.92)', 'textDark': '#2E1065',
        'decoColor': 'rgba(139,92,246,0.12)', 'decoColor2': 'rgba(196,181,253,0.15)',
        'icon': '📖', 'tagBg': '#EDE9FE', 'tagColor': '#6D28D9',
    },
    '写作卡': {
        'bg1': '#DB2777', 'bg2': '#F472B6',
        'banner': '#BE185D', 'bannerLight': 'rgba(190,24,93,0.12)',
        'accent': '#EC4899', 'accent2': '#F9A8D4',
        'cardBg': 'rgba(255,255,255,0.92)', 'textDark': '#500724',
        'decoColor': 'rgba(236,72,153,0.12)', 'decoColor2': 'rgba(249,168,212,0.15)',
        'icon': '✍️', 'tagBg': '#FCE7F3', 'tagColor': '#BE185D',
    },
    '词汇卡': {
        'bg1': '#0D9488', 'bg2': '#2DD4BF',
        'banner': '#0F766E', 'bannerLight': 'rgba(15,118,110,0.12)',
        'accent': '#14B8A6', 'accent2': '#5EEAD4',
        'cardBg': 'rgba(255,255,255,0.92)', 'textDark': '#042F2E',
        'decoColor': 'rgba(20,184,166,0.12)', 'decoColor2': 'rgba(94,234,212,0.15)',
        'icon': '🔤', 'tagBg': '#CCFBF1', 'tagColor': '#0F766E',
    },
    '语法卡': {
        'bg1': '#4F46E5', 'bg2': '#818CF8',
        'banner': '#4338CA', 'bannerLight': 'rgba(67,56,202,0.12)',
        'accent': '#6366F1', 'accent2': '#A5B4FC',
        'cardBg': 'rgba(255,255,255,0.92)', 'textDark': '#1E1B4B',
        'decoColor': 'rgba(99,102,241,0.12)', 'decoColor2': 'rgba(165,180,252,0.15)',
        'icon': '📝', 'tagBg': '#E0E7FF', 'tagColor': '#4338CA',
    },
    '口语卡': {
        'bg1': '#D97706', 'bg2': '#FBBF24',
        'banner': '#B45309', 'bannerLight': 'rgba(180,83,9,0.12)',
        'accent': '#F59E0B', 'accent2': '#FCD34D',
        'cardBg': 'rgba(255,255,255,0.92)', 'textDark': '#451A03',
        'decoColor': 'rgba(245,158,11,0.12)', 'decoColor2': 'rgba(252,211,77,0.15)',
        'icon': '🗣️', 'tagBg': '#FEF3C7', 'tagColor': '#B45309',
    },
}

DEFAULT_THEME = CARD_TYPE_THEMES['方法卡']

# ─── Fuzzy card type → theme mapping ───
_CARD_TYPE_ALIAS = {
    '易错字卡': '陷阱卡', '写作方法卡': '写作卡', '阅读技巧卡': '阅读卡',
    '古诗理解卡': '阅读卡', '词语辨析卡': '辨析卡', '易混词卡': '辨析卡',
    '多音字卡': '辨析卡', '修辞手法卡': '写作卡', '成语卡': '词汇卡',
    '拼音卡': '基础卡', '自然拼读卡': '基础卡', '标点符号卡': '基础卡',
    '句型卡': '语法卡', '情景对话卡': '口语卡', '不规则动词卡': '语法卡',
}

def _get_theme(card_type):
    """智能查找卡片类型对应的配色主题"""
    if card_type in CARD_TYPE_THEMES:
        return CARD_TYPE_THEMES[card_type]
    if card_type in _CARD_TYPE_ALIAS:
        return CARD_TYPE_THEMES.get(_CARD_TYPE_ALIAS[card_type], DEFAULT_THEME)
    # Fuzzy: try suffix match (e.g. '写作方法卡' contains '方法卡')
    for key in CARD_TYPE_THEMES:
        if key in card_type:
            return CARD_TYPE_THEMES[key]
    return DEFAULT_THEME

def _esc(text):
    """HTML escape"""
    return html_module.escape(str(text))

def _fmt_vertical_calc(card):
    """为笔算类卡片生成竖式 HTML"""
    ex = card.get('example', {})
    steps = ex.get('steps', [])
    if not steps:
        return ''
    
    # 尝试从标题/步骤中检测是否为竖式类
    title = card.get('title', '')
    keywords = ['笔算', '竖式', '列式', '列竖式']
    is_vertical = any(k in title for k in keywords)
    
    if not is_vertical:
        return ''
    
    # 从步骤中提取数字信息来构建竖式
    # 通用的竖式展示
    question = ex.get('question', '')
    answer = ex.get('answer', '')
    
    html = '<div class="vertical-calc">'
    for i, step in enumerate(steps):
        color = ['#2ED573', '#FF9F43', '#FF4757', '#54A0FF'][i % 4]
        html += f'<div class="calc-step" style="border-left: 3px solid {color}; padding-left: 12px; margin: 8px 0;">'
        html += f'<span style="color: {color}; font-weight: bold;">Step {i+1}</span> '
        html += f'<span>{_esc(step)}</span>'
        html += '</div>'
    html += '</div>'
    return html

def generate_card_html(card, subject, grade, semester, theme=None):
    """生成单张知识卡片的完整 HTML — v2 小红书精美海报级设计"""
    card_type = card.get('type', '方法卡')
    t = theme or _get_theme(card_type)
    
    title = _esc(card.get('title', ''))
    definition = _esc(card.get('definition', ''))
    memory_tip = _esc(card.get('memory_tip', ''))
    card_id = _esc(card.get('full_id', ''))
    difficulty = card.get('difficulty', 3)
    importance = card.get('importance', 3)
    
    # Core points
    core_html = ''
    step_colors = ['#10B981', '#F59E0B', '#3B82F6', '#EF4444', '#8B5CF6', '#EC4899']
    for i, p in enumerate(card.get('core_points', [])[:5]):
        c = step_colors[i % len(step_colors)]
        core_html += f'''<div class="core-point">
            <div class="point-marker" style="background: {c};">{i+1}</div>
            <div class="point-text">{_esc(p)}</div>
        </div>\n'''
    
    # Example
    example_html = ''
    ex = card.get('example', {})
    if ex:
        q = _esc(ex.get('question', ''))
        a = _esc(ex.get('answer', ''))
        steps_html = ''
        for i, s in enumerate(ex.get('steps', [])):
            c = step_colors[i % len(step_colors)]
            is_last = (i == len(ex.get('steps', [])) - 1)
            line_class = ' last' if is_last else ''
            steps_html += f'''<div class="tl-step{line_class}">
                <div class="tl-dot" style="background: {c}; box-shadow: 0 0 0 4px {c}33;"></div>
                <div class="tl-line"></div>
                <div class="tl-content">
                    <span class="tl-num" style="color: {c};">Step {i+1}</span>
                    <span class="tl-text">{_esc(s)}</span>
                </div>
            </div>\n'''
        
        example_html = f'''
    <div class="glass-card">
        <div class="section-head">
            <span class="section-icon">📝</span>
            <span class="section-title">经典例题</span>
        </div>
        <div class="question-box">
            <div class="q-label">题目</div>
            <div class="q-text">{q}</div>
        </div>
        <div class="timeline">{steps_html}</div>
        <div class="answer-reveal">
            <div class="answer-label">✅ 答案</div>
            <div class="answer-text">{a}</div>
        </div>
    </div>'''
    
    # Mistakes (正误对比)
    mistakes_html = ''
    mistakes = card.get('mistakes', [])
    if mistakes:
        m = mistakes[0]
        wrong = _esc(m.get('wrong', '')).replace('\\n', '<br>')
        correct = _esc(m.get('correct', '')).replace('\\n', '<br>')
        mistakes_html = f'''
    <div class="compare-row">
        <div class="compare-card wrong">
            <div class="compare-badge wrong-badge">✗</div>
            <div class="compare-label">常见错误</div>
            <div class="compare-body">{wrong}</div>
        </div>
        <div class="compare-vs">VS</div>
        <div class="compare-card correct">
            <div class="compare-badge correct-badge">✓</div>
            <div class="compare-label">正确做法</div>
            <div class="compare-body">{correct}</div>
        </div>
    </div>'''
    
    # Difficulty stars
    stars_html = ''
    for i in range(5):
        if i < difficulty:
            stars_html += f'<span class="star filled">★</span>'
        else:
            stars_html += f'<span class="star empty">★</span>'
    
    # Decorative SVG shapes (inline, no external deps)
    deco_svg = f'''
    <svg class="deco-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1440">
        <!-- Dot pattern -->
        <defs>
            <pattern id="dots" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
                <circle cx="4" cy="4" r="2" fill="{t['decoColor']}"/>
            </pattern>
        </defs>
        <rect width="1080" height="1440" fill="url(#dots)" opacity="0.6"/>
        <!-- Decorative circles -->
        <circle cx="950" cy="120" r="180" fill="{t['decoColor2']}" opacity="0.5"/>
        <circle cx="100" cy="350" r="120" fill="{t['decoColor']}" opacity="0.4"/>
        <circle cx="980" cy="800" r="100" fill="{t['decoColor2']}" opacity="0.35"/>
        <circle cx="60" cy="1100" r="80" fill="{t['decoColor']}" opacity="0.3"/>
        <circle cx="900" cy="1350" r="140" fill="{t['decoColor2']}" opacity="0.25"/>
        <!-- Wavy line decoration -->
        <path d="M0,400 Q270,370 540,400 T1080,400" stroke="{t['decoColor2']}" stroke-width="2" fill="none" opacity="0.4"/>
        <path d="M0,1050 Q270,1020 540,1050 T1080,1050" stroke="{t['decoColor']}" stroke-width="2" fill="none" opacity="0.3"/>
    </svg>'''
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700;900&display=swap');

* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    width: 1080px;
    min-height: 1440px;
    background: linear-gradient(165deg, {t['bg1']} 0%, {t['bg2']} 50%, {t['bg1']}dd 100%);
    font-family: 'Noto Sans SC', 'Microsoft YaHei', 'PingFang SC', sans-serif;
    padding: 0;
    overflow: hidden;
    -webkit-font-smoothing: antialiased;
}}

/* ── Canvas ── */
.canvas {{
    width: 1080px;
    min-height: 1440px;
    padding: 48px 44px;
    position: relative;
}}

.deco-svg {{
    position: absolute;
    top: 0; left: 0;
    width: 1080px;
    height: 1440px;
    pointer-events: none;
    z-index: 0;
}}

/* ── Hero Header ── */
.hero {{
    position: relative;
    z-index: 1;
    background: rgba(255,255,255,0.15);
    border: 1px solid rgba(255,255,255,0.25);
    border-radius: 32px;
    padding: 44px 48px 40px;
    margin-bottom: 28px;
    overflow: hidden;
}}
.hero::before {{
    content: '';
    position: absolute;
    top: -60px; right: -40px;
    width: 220px; height: 220px;
    background: rgba(255,255,255,0.08);
    border-radius: 50%;
}}
.hero::after {{
    content: '';
    position: absolute;
    bottom: -30px; left: 60px;
    width: 100px; height: 100px;
    background: rgba(255,255,255,0.06);
    border-radius: 50%;
}}
.hero-top {{
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 20px;
}}
.type-badge {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(255,255,255,0.95);
    color: {t['banner']};
    font-size: 24px;
    font-weight: 700;
    padding: 10px 24px;
    border-radius: 28px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
}}
.type-badge .badge-icon {{
    font-size: 28px;
}}
.subject-tag {{
    display: inline-block;
    background: rgba(255,255,255,0.25);
    color: white;
    font-size: 20px;
    font-weight: 500;
    padding: 8px 20px;
    border-radius: 20px;
    letter-spacing: 1px;
}}
.hero-title {{
    color: white;
    font-size: 56px;
    font-weight: 900;
    letter-spacing: 3px;
    line-height: 1.25;
    text-shadow: 0 3px 12px rgba(0,0,0,0.2);
    margin-bottom: 16px;
    position: relative;
}}
.hero-meta {{
    display: flex;
    align-items: center;
    gap: 24px;
    position: relative;
}}
.hero-id {{
    color: rgba(255,255,255,0.7);
    font-size: 20px;
    font-weight: 400;
    letter-spacing: 1px;
}}
.hero-stars {{
    display: flex;
    gap: 4px;
}}
.star {{
    font-size: 22px;
}}
.star.filled {{
    color: #FBBF24;
    text-shadow: 0 1px 4px rgba(251,191,36,0.4);
}}
.star.empty {{
    color: rgba(255,255,255,0.3);
}}

/* ── Glass Card (common) ── */
.glass-card {{
    position: relative;
    z-index: 1;
    background: {t['cardBg']};
    border: 1px solid rgba(255,255,255,0.6);
    border-radius: 28px;
    padding: 32px 36px;
    margin-bottom: 24px;
    box-shadow:
        0 8px 32px rgba(0,0,0,0.08),
        0 2px 8px rgba(0,0,0,0.04),
        inset 0 1px 0 rgba(255,255,255,0.8);
}}

.section-head {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    padding-bottom: 14px;
    border-bottom: 2px solid {t['bannerLight']};
}}
.section-icon {{
    font-size: 32px;
}}
.section-title {{
    font-size: 28px;
    font-weight: 800;
    color: {t['banner']};
    letter-spacing: 1px;
}}

/* ── Definition ── */
.def-text {{
    color: {t['textDark']};
    font-size: 28px;
    font-weight: 400;
    line-height: 1.7;
    padding: 4px 0;
}}
.def-highlight {{
    display: inline;
    background: linear-gradient(transparent 60%, {t['bannerLight']} 60%);
}}

/* ── Core Points ── */
.core-point {{
    display: flex;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 18px;
    padding: 12px 16px;
    background: rgba(0,0,0,0.02);
    border-radius: 16px;
    transition: background 0.2s;
}}
.point-marker {{
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 36px;
    height: 36px;
    color: white;
    border-radius: 12px;
    font-size: 18px;
    font-weight: 800;
    flex-shrink: 0;
    box-shadow: 0 3px 8px rgba(0,0,0,0.12);
}}
.point-text {{
    color: {t['textDark']};
    font-size: 24px;
    line-height: 1.6;
    flex: 1;
    padding-top: 4px;
}}

/* ── Example: Question ── */
.question-box {{
    background: {t['bannerLight']};
    border-radius: 20px;
    padding: 24px 28px;
    margin-bottom: 24px;
    border-left: 5px solid {t['accent']};
}}
.q-label {{
    font-size: 18px;
    font-weight: 700;
    color: {t['accent']};
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 8px;
}}
.q-text {{
    font-size: 28px;
    font-weight: 600;
    color: {t['textDark']};
    line-height: 1.6;
}}

/* ── Example: Timeline Steps ── */
.timeline {{
    position: relative;
    margin: 20px 0 24px 18px;
    padding-left: 28px;
}}
.tl-step {{
    position: relative;
    padding-bottom: 20px;
    display: flex;
    align-items: flex-start;
}}
.tl-step.last {{
    padding-bottom: 0;
}}
.tl-dot {{
    position: absolute;
    left: -34px;
    top: 6px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    z-index: 2;
}}
.tl-line {{
    position: absolute;
    left: -27px;
    top: 22px;
    bottom: 0;
    width: 2px;
    background: linear-gradient(to bottom, {t['accent2']}88, {t['accent2']}22);
}}
.tl-step.last .tl-line {{
    display: none;
}}
.tl-content {{
    display: flex;
    flex-direction: column;
    gap: 4px;
}}
.tl-num {{
    font-size: 16px;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
.tl-text {{
    font-size: 24px;
    color: {t['textDark']};
    line-height: 1.55;
}}

/* ── Answer Reveal ── */
.answer-reveal {{
    background: linear-gradient(135deg, {t['banner']}12, {t['accent']}18);
    border: 2px solid {t['accent']}33;
    border-radius: 20px;
    padding: 22px 28px;
    margin-top: 8px;
}}
.answer-label {{
    font-size: 20px;
    font-weight: 700;
    color: {t['accent']};
    margin-bottom: 6px;
}}
.answer-text {{
    font-size: 34px;
    font-weight: 900;
    color: {t['banner']};
    line-height: 1.4;
}}

/* ── Mistakes Compare ── */
.compare-row {{
    position: relative;
    z-index: 1;
    display: flex;
    gap: 20px;
    margin-bottom: 24px;
    align-items: stretch;
}}
.compare-card {{
    flex: 1;
    border-radius: 24px;
    padding: 28px 24px 24px;
    position: relative;
    box-shadow: 0 6px 24px rgba(0,0,0,0.06);
}}
.compare-card.wrong {{
    background: linear-gradient(165deg, #FFF1F2, #FFE4E6);
    border: 2px solid #FECDD3;
}}
.compare-card.correct {{
    background: linear-gradient(165deg, #ECFDF5, #D1FAE5);
    border: 2px solid #A7F3D0;
}}
.compare-badge {{
    position: absolute;
    top: -14px;
    left: 24px;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    font-weight: 900;
    color: white;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}}
.wrong-badge {{ background: #EF4444; }}
.correct-badge {{ background: #10B981; }}
.compare-label {{
    font-size: 22px;
    font-weight: 800;
    margin-bottom: 12px;
    margin-top: 8px;
}}
.compare-card.wrong .compare-label {{ color: #DC2626; }}
.compare-card.correct .compare-label {{ color: #059669; }}
.compare-body {{
    font-size: 21px;
    color: #374151;
    line-height: 1.65;
    white-space: pre-line;
}}
.compare-vs {{
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    font-weight: 900;
    color: rgba(255,255,255,0.9);
    text-shadow: 0 2px 8px rgba(0,0,0,0.2);
    min-width: 40px;
}}

/* ── Memory Tip ── */
.tip-card {{
    position: relative;
    z-index: 1;
    background: linear-gradient(135deg, #FFFBEB, #FEF3C7, #FDE68A);
    border: 2px solid #FCD34D;
    border-radius: 28px;
    padding: 32px 36px;
    margin-bottom: 24px;
    box-shadow:
        0 8px 32px rgba(251,191,36,0.15),
        0 2px 8px rgba(0,0,0,0.04);
    overflow: hidden;
}}
.tip-card::before {{
    content: '💡';
    position: absolute;
    top: -8px;
    right: 28px;
    font-size: 64px;
    opacity: 0.15;
}}
.tip-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
}}
.tip-icon {{
    font-size: 28px;
}}
.tip-label {{
    font-size: 22px;
    font-weight: 800;
    color: #B45309;
    letter-spacing: 1px;
}}
.tip-text {{
    font-size: 30px;
    font-weight: 700;
    color: #78350F;
    line-height: 1.55;
    position: relative;
}}
.tip-text::before {{
    content: '"';
    font-size: 60px;
    color: #D97706;
    opacity: 0.3;
    position: absolute;
    left: -8px;
    top: -16px;
    font-family: Georgia, serif;
}}

/* ── Footer ── */
.card-footer {{
    position: relative;
    z-index: 1;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 8px 4px;
    border-top: 1px solid rgba(255,255,255,0.2);
    margin-top: 4px;
}}
.footer-brand {{
    display: flex;
    align-items: center;
    gap: 10px;
    color: rgba(255,255,255,0.8);
    font-size: 20px;
    font-weight: 500;
}}
.footer-logo {{
    width: 32px;
    height: 32px;
    background: rgba(255,255,255,0.9);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
}}
.footer-cta {{
    display: flex;
    align-items: center;
    gap: 16px;
}}
.footer-cta span {{
    color: rgba(255,255,255,0.65);
    font-size: 18px;
}}
.footer-save {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255,255,255,0.2);
    color: white;
    font-size: 18px;
    font-weight: 600;
    padding: 8px 18px;
    border-radius: 20px;
}}
</style>
</head>
<body>
<div class="canvas">
    <!-- Decorative SVG overlay -->
    {deco_svg}

    <!-- Hero Header -->
    <div class="hero">
        <div class="hero-top">
            <div class="type-badge">
                <span class="badge-icon">{t['icon']}</span>
                <span>{_esc(card_type)}</span>
            </div>
            <div class="subject-tag">{_esc(subject)} · {_esc(grade)}{_esc(semester)}</div>
        </div>
        <div class="hero-title">{title}</div>
        <div class="hero-meta">
            <span class="hero-id">{card_id}</span>
            <div class="hero-stars">{stars_html}</div>
        </div>
    </div>
    
    <!-- Definition -->
    <div class="glass-card">
        <div class="section-head">
            <span class="section-icon">📖</span>
            <span class="section-title">知识要点</span>
        </div>
        <div class="def-text">{definition}</div>
    </div>
    
    <!-- Core Points -->
    <div class="glass-card">
        <div class="section-head">
            <span class="section-icon">🎯</span>
            <span class="section-title">核心要点</span>
        </div>
        {core_html}
    </div>
    
    <!-- Example -->
    {example_html}
    
    <!-- Mistakes Compare -->
    {mistakes_html}
    
    <!-- Memory Tip -->
    <div class="tip-card">
        <div class="tip-header">
            <span class="tip-icon">💡</span>
            <span class="tip-label">记忆口诀</span>
        </div>
        <div class="tip-text">{memory_tip}</div>
    </div>
    
    <!-- Footer -->
    <div class="card-footer">
        <div class="footer-brand">
            <div class="footer-logo">📚</div>
            <span>小红薯学习平台</span>
        </div>
        <div class="footer-cta">
            <span>觉得有用？</span>
            <div class="footer-save">❤️ 收藏</div>
        </div>
    </div>
</div>
</body>
</html>'''
    return html


def _find_chrome():
    """查找 Chrome 浏览器路径"""
    candidates = [
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def render_card_to_image(html_content, output_path, width=1080):
    """用 Chrome headless --screenshot 直接截图（无需 ChromeDriver）"""
    import subprocess
    from PIL import Image
    import io
    
    chrome = _find_chrome()
    if not chrome:
        raise RuntimeError('未找到 Chrome/Edge 浏览器')
    
    # Write HTML to temp file
    tmp = tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8')
    tmp.write(html_content)
    tmp.close()
    
    # Screenshot output (Chrome outputs to --screenshot path)
    png_path = tmp.name.replace('.html', '.png')
    
    try:
        # Use 2x scale factor for sharper text rendering (retina quality)
        scale = 2
        cmd = [
            chrome,
            '--headless=new',
            '--no-sandbox',
            '--disable-gpu',
            '--disable-dev-shm-usage',
            '--hide-scrollbars',
            f'--window-size={width},{width * 3}',
            f'--force-device-scale-factor={scale}',
            f'--screenshot={png_path}',
            f'file:///{tmp.name}',
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        
        if not os.path.exists(png_path):
            raise RuntimeError(f'截图文件未生成. stderr={result.stderr[:500]}')
        
        # Convert PNG→JPG, crop whitespace, resize back from 2x to 1x for final output
        img = Image.open(png_path)
        img = img.convert('RGB')
        
        # Auto-crop bottom whitespace using PIL getbbox
        from PIL import ImageChops
        # Use the actual background color (not white) for cropping
        # Sample the bottom-right pixel as background reference
        bg_color = img.getpixel((img.width - 1, img.height - 1))
        bg = Image.new('RGB', img.size, bg_color)
        diff = ImageChops.difference(img, bg)
        bbox = diff.getbbox()  # (left, top, right, bottom)
        if bbox:
            bottom = min(bbox[3] + 40, img.height)  # padding
            img = img.crop((0, 0, width * scale, bottom))
        
        # Output at full 2x resolution (2160px wide) for crisp social media images
        img.save(output_path, 'JPEG', quality=93, optimize=True)
        return os.path.getsize(output_path)
    finally:
        for f in [tmp.name, png_path]:
            try: os.unlink(f)
            except: pass


def main():
    import argparse
    parser = argparse.ArgumentParser(description='知识卡片 HTML 渲染器')
    parser.add_argument('json_file', help='知识卡片 JSON 文件路径')
    parser.add_argument('--output', '-o', default='card_images', help='输出目录')
    parser.add_argument('--card', '-c', help='只生成指定 card_id 的卡片 (如 05-03)')
    parser.add_argument('--test', action='store_true', help='只生成第1张')
    parser.add_argument('--force', '-f', action='store_true', help='覆盖已存在的图片')
    parser.add_argument('--html-only', action='store_true', help='只输出 HTML 不截图(调试用)')
    args = parser.parse_args()
    
    if not os.path.exists(args.json_file):
        print(f'❌ 文件不存在: {args.json_file}')
        sys.exit(1)
    
    with open(args.json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    os.makedirs(args.output, exist_ok=True)
    
    subject = data['subject']
    grade = data['grade']
    semester = data['semester']
    
    # Collect cards to process
    cards = []
    for unit in data['units']:
        for card in unit['cards']:
            if args.card and card['card_id'] != args.card and card['full_id'] != args.card:
                continue
            cards.append(card)
    
    if not cards:
        print(f'❌ 未找到匹配的卡片' + (f' (filter: {args.card})' if args.card else ''))
        sys.exit(1)
    
    total_cards = len(cards)
    print(f'╔══════════════════════════════════════════╗')
    print(f'║  📚 知识卡片 HTML 渲染器                  ║')
    print(f'╠══════════════════════════════════════════╣')
    print(f'║  学科: {subject}  年级: {grade}{semester}')
    print(f'║  卡片: {total_cards} 张  输出: {args.output}/')
    print(f'║  模式: {"HTML调试" if args.html_only else "HTML→截图→JPG"}')
    print(f'╚══════════════════════════════════════════╝\n')
    
    success = 0
    for i, card in enumerate(cards):
        out_name = card['full_id'].replace('-', '_')
        out_path = os.path.join(args.output, f'{out_name}.jpg')
        
        print(f'  [{i+1}/{total_cards}] {card["full_id"]} {card["title"]}', end='')
        
        if os.path.exists(out_path) and not args.force:
            print(f' ⏭️  已存在, 跳过 (--force 覆盖)')
            success += 1
            continue
        
        # Generate HTML
        html = generate_card_html(card, subject, grade, semester)
        
        if args.html_only:
            html_path = os.path.join(args.output, f'{out_name}.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f' → {html_path}')
            success += 1
        else:
            try:
                size = render_card_to_image(html, out_path)
                print(f' ✅ {size/1024:.0f}KB')
                success += 1
            except Exception as e:
                print(f' ❌ {e}')
        
        if args.test:
            break
    
    print(f'\n🎉 完成: {success}/{min(total_cards, i+1)} 张')


if __name__ == '__main__':
    main()
