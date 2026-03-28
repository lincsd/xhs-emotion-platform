#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PIL 全文字渲染引擎 v2 — AI 只生成纯视觉底图，PIL 渲染全部文字。

v10.1 核心策略:
  AI 负责: 渐变背景、色块区域、卡通形象、装饰图标、箭头
  PIL 负责: 100% 的文字渲染（标题、内容、公式、答案、口诀）
  
  这样做的原因:
    1. AI（尤其是 Nano Banana 2）无法准确渲染中文 → 错字、乱码、重复
    2. PIL 渲染文字 100% 正确，像素级清晰
    3. 解耦后 AI 模型只需关注视觉美感，prompt 更简短，成功率更高

版本: 2.0 (2026-03-28)
"""

from __future__ import annotations
import io
import os
import re
from typing import Optional

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════
PIL_MODE_OVERLAY = 'overlay'   # 兼容旧模式
PIL_MODE_REPLACE = 'replace'   # v2 主模式: 底图无文字，PIL 全量渲染
PIL_MODE_DISABLED = 'disabled'

DEFAULT_PIL_MODE = PIL_MODE_REPLACE   # v10.1: 全量 PIL 渲染

# 中文字体搜索路径
_FONT_SEARCH_PATHS = [
    'C:/Windows/Fonts/msyhbd.ttc',
    'C:/Windows/Fonts/msyh.ttc',
    'C:/Windows/Fonts/simhei.ttf',
    'C:/Windows/Fonts/simsun.ttc',
    '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc',
    '/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc',
    '/System/Library/Fonts/PingFang.ttc',
]

_font_cache: dict[int, object] = {}


def _load_font(size: int):
    """加载中文粗体字体，带缓存"""
    if size in _font_cache:
        return _font_cache[size]
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    for fp in _FONT_SEARCH_PATHS:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, size)
                _font_cache[size] = font
                return font
            except Exception:
                continue
    font = ImageFont.load_default()
    _font_cache[size] = font
    return font


# ═══════════════════════════════════════════
# 布局系统 v2
# ═══════════════════════════════════════════

def _count_cn(text: str) -> int:
    return sum(1 for c in text if '\u4e00' <= c <= '\u9fff')


def _has_text(text: str) -> bool:
    return bool(text and text.strip())


def _classify_key(key: str) -> str:
    """分类 manifest key → title/content/slogan/tip/bubble"""
    k = key.upper()
    if 'TITLE' in k:
        return 'title'
    if 'SLOGAN' in k or 'ANSWER' in k:
        return 'slogan'
    if 'TIP' in k or 'ERROR' in k:
        return 'tip'
    if 'BUBBLE' in k:
        return 'bubble'
    return 'content'


# 区域配置
_ZONE = {
    'title': {
        'y_start': 0.02, 'y_end': 0.12,
        'font_scale': 1.8, 'color': (255, 255, 255),
        'bg': (70, 130, 220, 200), 'bold': True,
        'align': 'center', 'mx': 0.08,
    },
    'content': {
        'y_start': 0.14, 'y_end': 0.78,
        'font_scale': 1.0, 'color': (50, 50, 50),
        'bg': (255, 255, 255, 210), 'bold': False,
        'align': 'left', 'mx': 0.06,
        'line_sp': 1.5, 'pad': 0.02, 'radius': 12,
    },
    'slogan': {
        'y_start': 0.80, 'y_end': 0.92,
        'font_scale': 1.3, 'color': (255, 75, 75),
        'bg': (255, 255, 230, 220), 'bold': True,
        'align': 'center', 'mx': 0.10,
    },
    'tip': {
        'y_start': 0.92, 'y_end': 0.98,
        'font_scale': 0.7, 'color': (220, 80, 80),
        'bg': None, 'bold': False,
        'align': 'center', 'mx': 0.10,
    },
    'bubble': {
        'y_start': 0.02, 'y_end': 0.08,
        'font_scale': 0.65, 'color': (100, 100, 100),
        'bg': (255, 255, 255, 180), 'bold': False,
        'align': 'right', 'mx': 0.05,
    },
}


def _rrect(draw, bbox, radius, fill):
    try:
        draw.rounded_rectangle(bbox, radius=radius, fill=fill)
    except AttributeError:
        draw.rectangle(bbox, fill=fill)


def _bold_text(draw, pos, text, font, fill, bold=False):
    x, y = pos
    c = fill if len(fill) == 4 else fill + (255,)
    if bold:
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1)]:
            draw.text((x + dx, y + dy), text, fill=c, font=font)
    draw.text((x, y), text, fill=c, font=font)


def _fit_font(draw, text, font_size, max_w, min_size=18):
    """缩小字体直到文字宽度 ≤ max_w"""
    font = _load_font(font_size)
    if not font:
        return font, font_size
    bbox = draw.textbbox((0, 0), text, font=font)
    while bbox[2] - bbox[0] > max_w and font_size > min_size:
        font_size = max(min_size, font_size - 2)
        font = _load_font(font_size)
        if not font:
            break
        bbox = draw.textbbox((0, 0), text, font=font)
    return font, font_size


def _wrap_text(text: str, font, max_w: int, draw) -> list[str]:
    """自动换行（中英文混排）"""
    if not text:
        return []
    bbox = draw.textbbox((0, 0), text, font=font)
    if bbox[2] - bbox[0] <= max_w:
        return [text]
    lines, cur = [], ''
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isascii() and ch.isalpha():
            word = ''
            while i < len(text) and text[i].isascii() and (text[i].isalpha() or text[i] in "'-"):
                word += text[i]
                i += 1
            trial = cur + word
        else:
            trial = cur + ch
            i += 1
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = trial[len(cur):]
    if cur:
        lines.append(cur)
    return lines


# ═══════════════════════════════════════════
# 核心渲染 v2
# ═══════════════════════════════════════════

def pil_full_render(image_data: bytes, manifest: dict) -> tuple[bytes, list[str]]:
    """
    在 AI 无文字底图上渲染全部文字。
    
    分区策略:
      title  → 顶部横幅
      content (LINE1, LINE2, ...) → 中部内容区，白色圆角卡片
      slogan / answer → 底部强调区
      tip / error → 底部小字
      bubble → 右上角
    """
    if not manifest:
        return image_data, []
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print('      [PIL not available]')
        return image_data, []

    img = Image.open(io.BytesIO(image_data))
    w, h = img.size
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    base = max(28, w // 16)
    applied = []

    # 分组
    groups: dict[str, list[tuple[str, str]]] = {
        'title': [], 'content': [], 'slogan': [], 'tip': [], 'bubble': []
    }
    for k, v in manifest.items():
        if _has_text(v):
            groups[_classify_key(k)].append((k, v))

    # ── 标题 ──
    for key, text in groups['title']:
        z = _ZONE['title']
        fs = int(base * z['font_scale'])
        margin = int(w * z['mx'])
        font, fs = _fit_font(draw, text, fs, w - margin * 2)
        if not font:
            continue
        y_c = int(h * (z['y_start'] + z['y_end']) / 2)
        bb = draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        x = (w - tw) // 2
        y = y_c - th // 2
        if z['bg']:
            _rrect(draw, [margin - 20, y - 10, w - margin + 20, y + th + 10], 14, z['bg'])
        _bold_text(draw, (x, y), text, font, z['color'], bold=z['bold'])
        applied.append(f'{key}="{text}"')

    # ── 内容行 ──
    items = groups['content']
    if items:
        z = _ZONE['content']
        y_cur = int(h * z['y_start'])
        y_max = int(h * z['y_end'])
        margin = int(w * z['mx'])
        pad = int(h * z.get('pad', 0.02))

        for key, text in items:
            if y_cur >= y_max:
                break
            fs = int(base * z['font_scale'])
            font = _load_font(fs)
            if not font:
                continue
            avail = w - margin * 2 - pad * 2
            lines = _wrap_text(text, font, avail, draw)
            lh = fs
            sp = int(lh * (z.get('line_sp', 1.4) - 1.0))
            blk_h = len(lines) * lh + max(0, len(lines) - 1) * sp + pad * 2

            # 缩小字体重试
            if y_cur + blk_h > y_max:
                fs = max(18, int(fs * 0.75))
                font = _load_font(fs)
                lines = _wrap_text(text, font, avail, draw)
                lh = fs
                sp = int(lh * (z.get('line_sp', 1.4) - 1.0))
                blk_h = len(lines) * lh + max(0, len(lines) - 1) * sp + pad * 2

            if z['bg']:
                _rrect(draw, [margin, y_cur, w - margin, y_cur + blk_h],
                       z.get('radius', 10), z['bg'])
            ty = y_cur + pad
            for line in lines:
                if z['align'] == 'center':
                    bb = draw.textbbox((0, 0), line, font=font)
                    tx = (w - (bb[2] - bb[0])) // 2
                else:
                    tx = margin + pad
                _bold_text(draw, (tx, ty), line, font, z['color'], bold=z['bold'])
                ty += lh + sp
            label = f'{key}="{text[:20]}..."' if len(text) > 20 else f'{key}="{text}"'
            applied.append(label)
            y_cur += blk_h + 8

    # ── 口诀/答案 ──
    for key, text in groups['slogan']:
        z = _ZONE['slogan']
        fs = int(base * z['font_scale'])
        margin = int(w * z['mx'])
        font, fs = _fit_font(draw, text, fs, w - margin * 2)
        if not font:
            continue
        y_c = int(h * (z['y_start'] + z['y_end']) / 2)
        bb = draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        x = (w - tw) // 2
        y = y_c - th // 2
        if z['bg']:
            _rrect(draw, [margin, y - 12, w - margin, y + th + 12], 14, z['bg'])
        _bold_text(draw, (x, y), text, font, z['color'], bold=z['bold'])
        applied.append(f'{key}="{text}"')

    # ── 提示/错误 ──
    for key, text in groups['tip']:
        z = _ZONE['tip']
        fs = int(base * z['font_scale'])
        font = _load_font(fs)
        if not font:
            continue
        y_c = int(h * (z['y_start'] + z['y_end']) / 2)
        bb = draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        _bold_text(draw, ((w - tw) // 2, y_c - th // 2), text, font, z['color'])
        applied.append(f'{key}="{text}"')

    # ── 气泡 ──
    for key, text in groups['bubble']:
        z = _ZONE['bubble']
        fs = int(base * z['font_scale'])
        font = _load_font(fs)
        if not font:
            continue
        bb = draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        margin = int(w * z['mx'])
        x = w - margin - tw - 10
        yt = int(h * z['y_start'])
        if z['bg']:
            _rrect(draw, [x - 8, yt - 8, x + tw + 8, yt + th + 8], 10, z['bg'])
        _bold_text(draw, (x, yt), text, font, z['color'])
        applied.append(f'{key}="{text}"')

    img = Image.alpha_composite(img, overlay)
    buf = io.BytesIO()
    img.convert('RGB').save(buf, format='JPEG', quality=93)
    return buf.getvalue(), applied


# ═══════════════════════════════════════════
# 兼容旧接口
# ═══════════════════════════════════════════

def pil_overlay_text(image_data: bytes, manifest: dict,
                     mode: str = PIL_MODE_OVERLAY) -> tuple[bytes, list[str]]:
    """v1 兼容 — 代理到 pil_full_render"""
    if mode == PIL_MODE_DISABLED:
        return image_data, []
    return pil_full_render(image_data, manifest)


def pil_render_title_bar(image_data: bytes, title: str,
                         bar_height_ratio: float = 0.10) -> bytes:
    """在图片顶部渲染标题条（旧接口兼容）"""
    if not title or _count_cn(title) == 0:
        return image_data
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return image_data
    img = Image.open(io.BytesIO(image_data))
    w, h = img.size
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    bar_h = int(h * bar_height_ratio)
    font_size = int(bar_h * 0.6)
    font = _load_font(font_size)
    if not font:
        return image_data
    bar = Image.new('RGBA', (w, bar_h), (50, 50, 50, 160))
    img.paste(bar, (0, 0), bar)
    draw = ImageDraw.Draw(img)
    bb = draw.textbbox((0, 0), title, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x, y = (w - tw) // 2, (bar_h - th) // 2
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        draw.text((x + dx, y + dy), title, fill=(255, 255, 255, 255), font=font)
    draw.text((x, y), title, fill=(255, 255, 255, 255), font=font)
    buf = io.BytesIO()
    img.convert('RGB').save(buf, format='JPEG', quality=93)
    return buf.getvalue()


# ═══════════════════════════════════════════
# 集成 API
# ═══════════════════════════════════════════

def pil_primary_render(image_data: bytes, manifest: dict,
                       card_title: str = '', mode: str = DEFAULT_PIL_MODE) -> tuple[bytes, bool]:
    """
    PIL 主路径渲染 — v10.1 全文字渲染。

    AI 底图完全没有文字 → PIL 渲染 manifest 中的全部内容。
    """
    if mode == PIL_MODE_DISABLED:
        return image_data, False
    if not manifest:
        return image_data, False

    rendered, applied = pil_full_render(image_data, manifest)
    if applied:
        labels_str = ', '.join(applied[:3])
        if len(applied) > 3:
            labels_str += f' +{len(applied) - 3}'
        print(f'      🎨 PIL全量渲染: {labels_str}')
        return rendered, True
    return image_data, False


# ═══════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════
if __name__ == '__main__':
    print('=== PIL Text Renderer v2 ===')
    print(f'Default mode: {DEFAULT_PIL_MODE}')
    font = _load_font(36)
    print(f'Font loaded: {font is not None}')

    try:
        from PIL import Image, ImageDraw as ID
        img = Image.new('RGB', (600, 800), (180, 210, 240))
        d = ID.Draw(img)
        d.rectangle([0, 10, 600, 90], fill=(70, 130, 220))
        try:
            d.rounded_rectangle([30, 110, 570, 580], radius=12, fill=(255, 255, 255))
        except AttributeError:
            d.rectangle([30, 110, 570, 580], fill=(255, 255, 255))
        d.rectangle([50, 620, 550, 700], fill=(255, 255, 230))
        buf = io.BytesIO()
        img.save(buf, format='PNG')

        manifest = {
            'TITLE': '拆数口算÷',
            'LINE1': '840 ÷ 4 = ?',
            'LINE2': '先拆: 840 = 800 + 40',
            'LINE3': '800÷4=200, 40÷4=10',
            'ANSWER': '200 + 10 = 210',
            'SLOGAN': '拆开除再合体',
        }
        rendered, applied = pil_full_render(buf.getvalue(), manifest)
        print(f'Rendered: {len(applied)} texts, {len(rendered)} bytes')
        with open('_test_pil_render_v2.jpg', 'wb') as f:
            f.write(rendered)
        print('Saved: _test_pil_render_v2.jpg')
    except ImportError:
        print('PIL not available')
