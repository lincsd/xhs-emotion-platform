#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PIL 全文字渲染引擎 v4 — 为结构化卡片版式设计的轻量文字渲染。

v10.3 核心策略:
  AI 负责: 设计卡片版面（渐变Banner + 白色内容卡 + 强调条 + 角落吉祥物）
  PIL 负责: 100% 的文字渲染 — 直接印在 AI 设计好的色块区域上
  
  关键改进（vs v3 毛玻璃）:
    1. 无需毛玻璃 — AI 设计的色块区域本身就已为文字量身定制
    2. 极简叠层 — 仅用微半透明白底保证可读性（alpha 50-80），不用模糊
    3. 亮度自适应 — 深色区域用白字，浅色区域用深字
    4. 文字阴影 — 保证任何背景下的可读性
    5. 更快速 — 无需 GaussianBlur，渲染速度快

版本: 4.0 (2026-03-28)
"""

from __future__ import annotations
import io
import os
import re
from typing import Optional

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════
PIL_MODE_OVERLAY = 'overlay'
PIL_MODE_REPLACE = 'replace'
PIL_MODE_DISABLED = 'disabled'

DEFAULT_PIL_MODE = PIL_MODE_REPLACE

# 中文字体搜索路径
_FONT_SEARCH_PATHS_BOLD = [
    'C:/Windows/Fonts/msyhbd.ttc',   # 微软雅黑粗体
    'C:/Windows/Fonts/simhei.ttf',   # 黑体
]
_FONT_SEARCH_PATHS_REGULAR = [
    'C:/Windows/Fonts/msyh.ttc',     # 微软雅黑
    'C:/Windows/Fonts/simsun.ttc',   # 宋体
    '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc',
    '/System/Library/Fonts/PingFang.ttc',
]

_font_cache: dict[tuple[int, bool], object] = {}


def _load_font(size: int, bold: bool = False):
    """加载中文字体，带缓存"""
    cache_key = (size, bold)
    if cache_key in _font_cache:
        return _font_cache[cache_key]
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    paths = _FONT_SEARCH_PATHS_BOLD if bold else _FONT_SEARCH_PATHS_REGULAR
    for fp in paths + _FONT_SEARCH_PATHS_REGULAR + _FONT_SEARCH_PATHS_BOLD:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, size)
                _font_cache[cache_key] = font
                return font
            except Exception:
                continue
    font = ImageFont.load_default()
    _font_cache[cache_key] = font
    return font


# ═══════════════════════════════════════════
# 工具函数
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
    if 'SLOGAN' in k or 'MOTTO' in k:
        return 'slogan'
    if 'TIP' in k or 'ERROR' in k:
        return 'tip'
    if 'BUBBLE' in k:
        return 'bubble'
    # ANSWER goes to content — part of the main card body
    return 'content'


def _get_luminance(img_region) -> float:
    """获取图片区域的平均亮度 (0=黑, 255=白)"""
    try:
        from PIL import ImageStat
        stat = ImageStat.Stat(img_region.convert('RGB'))
        r, g, b = stat.mean[:3]
        return 0.299 * r + 0.587 * g + 0.114 * b
    except Exception:
        return 180


def _draw_text_shadow(draw, pos, text, font, fill, bold=False, shadow_strength=2):
    """绘制带阴影的文字 — 轻量级，不需要毛玻璃"""
    x, y = pos
    c = fill if len(fill) >= 4 else fill + (255,)
    # 阴影: 根据文字颜色自动选择
    is_light_text = (c[0] + c[1] + c[2]) / 3 > 160
    shadow_c = (0, 0, 0, 80) if is_light_text else (255, 255, 255, 60)
    for d_offset in range(1, shadow_strength + 1):
        draw.text((x + d_offset, y + d_offset), text, fill=shadow_c, font=font)
    if bold:
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text((x + dx, y + dy), text, fill=c, font=font)
    draw.text((x, y), text, fill=c, font=font)


def _auto_text_color(lum: float, zone: str = 'content') -> tuple:
    """根据背景亮度自动选择文字颜色"""
    if zone == 'title':
        return (30, 30, 50, 255) if lum > 180 else (255, 255, 255, 255)
    elif zone == 'slogan':
        return (180, 50, 50, 255) if lum > 160 else (255, 240, 230, 255)
    elif zone == 'tip':
        return (120, 60, 60, 200) if lum > 140 else (255, 200, 200, 200)
    else:  # content
        if lum > 160:
            return (40, 40, 50, 255)
        elif lum < 80:
            return (240, 240, 245, 255)
        else:
            return (35, 35, 45, 255)


def _fit_font(draw, text, font_size, max_w, min_size=18, bold=False):
    """缩小字体直到文字宽度 ≤ max_w"""
    font = _load_font(font_size, bold=bold)
    if not font:
        return font, font_size
    bbox = draw.textbbox((0, 0), text, font=font)
    while bbox[2] - bbox[0] > max_w and font_size > min_size:
        font_size = max(min_size, font_size - 2)
        font = _load_font(font_size, bold=bold)
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


def _rrect(draw, bbox, radius, fill):
    """圆角矩形"""
    try:
        draw.rounded_rectangle(bbox, radius=radius, fill=fill)
    except AttributeError:
        draw.rectangle(bbox, fill=fill)


# ═══════════════════════════════════════════
# 区域配置 v4 — 适配 AI 卡片版式设计
# ═══════════════════════════════════════════
# AI 被要求画出:
#   顶部 Banner (约 2%-12%): 深色渐变横幅
#   中间内容区 (约 14%-78%): 白色/浅色圆角卡片
#   底部口诀条 (约 80%-92%): 暖色调强调条
#   底部提示 (约 93%-98%): 无背景
# PIL 只需在这些区域里填字 — 无需额外创建背景块

_ZONE = {
    'title': {
        'y_start': 0.02, 'y_end': 0.12,
        'font_scale': 1.8,
        'bold': True, 'align': 'center',
        'mx': 0.06,
        'readability_overlay': True,
        'overlay_alpha': 60,
    },
    'content': {
        'y_start': 0.14, 'y_end': 0.78,
        'font_scale': 1.0,
        'bold': False, 'align': 'left',
        'mx': 0.05,
        'line_sp': 1.6,
        'item_gap': 12,
        'inner_pad': 18,
        'readability_overlay': True,
        'overlay_alpha': 50,
        'overlay_radius': 16,
    },
    'slogan': {
        'y_start': 0.80, 'y_end': 0.92,
        'font_scale': 1.3,
        'bold': True, 'align': 'center',
        'mx': 0.08,
        'readability_overlay': True,
        'overlay_alpha': 55,
    },
    'tip': {
        'y_start': 0.93, 'y_end': 0.98,
        'font_scale': 0.7,
        'bold': False, 'align': 'center',
        'mx': 0.10,
        'readability_overlay': False,
    },
    'bubble': {
        'y_start': 0.02, 'y_end': 0.08,
        'font_scale': 0.65,
        'bold': False, 'align': 'right',
        'mx': 0.05,
        'readability_overlay': False,
    },
}


# ═══════════════════════════════════════════
# 核心渲染 v4 — 轻量级直接渲染
# ═══════════════════════════════════════════

def pil_full_render(image_data: bytes, manifest: dict) -> tuple[bytes, list[str]]:
    """
    在 AI 设计的卡片版式上渲染全部文字。

    v4 核心改进:
      1. AI 已经画好结构化版式（Banner + 白卡 + 强调条），不需要毛玻璃
      2. 用微半透明叠层（alpha 50-80）保证可读，比毛玻璃轻量且自然
      3. 背景亮度自适应文字颜色
      4. 文字阴影确保可读性
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

    tmp_draw = ImageDraw.Draw(img)
    base = max(28, w // 16)
    applied = []

    # 分组
    groups: dict[str, list[tuple[str, str]]] = {
        'title': [], 'content': [], 'slogan': [], 'tip': [], 'bubble': []
    }
    for k, v in manifest.items():
        if _has_text(v):
            groups[_classify_key(k)].append((k, v))

    # ── 标题 — 居中大字直接印在 Banner 上 ──
    for key, text in groups['title']:
        z = _ZONE['title']
        fs = int(base * z['font_scale'])
        margin = int(w * z['mx'])
        font, fs = _fit_font(tmp_draw, text, fs, w - margin * 2 - 40, bold=z['bold'])
        if not font:
            continue
        y_c = int(h * (z['y_start'] + z['y_end']) / 2)
        bb = tmp_draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        tx = (w - tw) // 2
        ty = y_c - th // 2

        pad_x, pad_y = 20, 10
        rgn_x1, rgn_y1 = max(0, tx - pad_x), max(0, ty - pad_y)
        rgn_x2, rgn_y2 = min(w, tx + tw + pad_x), min(h, ty + th + pad_y)
        bg_region = img.crop((rgn_x1, rgn_y1, rgn_x2, rgn_y2))
        lum = _get_luminance(bg_region)
        text_color = _auto_text_color(lum, 'title')

        if z.get('readability_overlay'):
            overlay = Image.new('RGBA', (rgn_x2 - rgn_x1, rgn_y2 - rgn_y1))
            ov_draw = ImageDraw.Draw(overlay)
            ov_color = (0, 0, 0, z['overlay_alpha']) if lum > 140 else (255, 255, 255, z['overlay_alpha'])
            r = min(rgn_x2 - rgn_x1, rgn_y2 - rgn_y1) // 2
            _rrect(ov_draw, [0, 0, overlay.width, overlay.height], r, ov_color)
            img.paste(Image.alpha_composite(
                img.crop((rgn_x1, rgn_y1, rgn_x2, rgn_y2)).convert('RGBA'), overlay),
                (rgn_x1, rgn_y1))

        draw = ImageDraw.Draw(img)
        _draw_text_shadow(draw, (tx, ty), text, font, text_color, bold=z['bold'])
        applied.append(f'{key}="{text}"')

    # ── 内容行 — 在白色内容卡区域逐行渲染 ──
    items = groups['content']
    if items:
        z = _ZONE['content']
        y_cur = int(h * z['y_start'])
        y_max = int(h * z['y_end'])
        margin = int(w * z['mx'])
        inner_pad = z.get('inner_pad', 18)
        item_gap = z.get('item_gap', 12)

        content_x1, content_y1 = margin, y_cur
        content_x2, content_y2 = w - margin, y_max
        if z.get('readability_overlay'):
            content_region = img.crop((content_x1, content_y1, content_x2, content_y2))
            lum_content = _get_luminance(content_region)
            if lum_content < 220:
                overlay = Image.new('RGBA', (content_x2 - content_x1, content_y2 - content_y1))
                ov_draw = ImageDraw.Draw(overlay)
                alpha = z['overlay_alpha'] if lum_content > 120 else z['overlay_alpha'] + 30
                _rrect(ov_draw, [0, 0, overlay.width, overlay.height],
                       z.get('overlay_radius', 16), (255, 255, 255, alpha))
                img.paste(Image.alpha_composite(content_region.convert('RGBA'), overlay),
                          (content_x1, content_y1))

        y_cur += inner_pad

        for key, text in items:
            if y_cur >= y_max - inner_pad:
                break
            fs = int(base * z['font_scale'])
            font = _load_font(fs, bold=z['bold'])
            if not font:
                continue
            avail = (content_x2 - content_x1) - inner_pad * 2
            lines = _wrap_text(text, font, avail, tmp_draw)
            lh = fs
            sp = int(lh * (z.get('line_sp', 1.6) - 1.0))
            blk_h = len(lines) * lh + max(0, len(lines) - 1) * sp

            if y_cur + blk_h > y_max - inner_pad:
                fs = max(16, int(fs * 0.75))
                font = _load_font(fs, bold=z['bold'])
                lines = _wrap_text(text, font, avail, tmp_draw)
                lh = fs
                sp = int(lh * (z.get('line_sp', 1.6) - 1.0))
                blk_h = len(lines) * lh + max(0, len(lines) - 1) * sp

            line_rgn_y2 = min(h, y_cur + blk_h + 4)
            if line_rgn_y2 > y_cur:
                line_rgn = img.crop((content_x1, y_cur, content_x2, line_rgn_y2))
                lum_line = _get_luminance(line_rgn)
            else:
                lum_line = 220
            text_color = _auto_text_color(lum_line, 'content')

            draw = ImageDraw.Draw(img)
            cur_ty = y_cur
            for line in lines:
                if z['align'] == 'center':
                    bb = tmp_draw.textbbox((0, 0), line, font=font)
                    line_tx = (w - (bb[2] - bb[0])) // 2
                else:
                    line_tx = content_x1 + inner_pad
                _draw_text_shadow(draw, (line_tx, cur_ty), line, font, text_color,
                                  bold=z['bold'])
                cur_ty += lh + sp

            label = f'{key}="{text[:20]}..."' if len(text) > 20 else f'{key}="{text}"'
            applied.append(label)
            y_cur = cur_ty + item_gap

    # ── 口诀 — 居中大字印在强调条上 ──
    for key, text in groups['slogan']:
        z = _ZONE['slogan']
        fs = int(base * z['font_scale'])
        margin = int(w * z['mx'])
        font, fs = _fit_font(tmp_draw, text, fs, w - margin * 2 - 40, bold=z['bold'])
        if not font:
            continue
        y_c = int(h * (z['y_start'] + z['y_end']) / 2)
        bb = tmp_draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        tx, ty = (w - tw) // 2, y_c - th // 2

        pad_x, pad_y = 20, 10
        rgn_x1, rgn_y1 = max(0, tx - pad_x), max(0, ty - pad_y)
        rgn_x2, rgn_y2 = min(w, tx + tw + pad_x), min(h, ty + th + pad_y)
        bg_region = img.crop((rgn_x1, rgn_y1, rgn_x2, rgn_y2))
        lum = _get_luminance(bg_region)
        text_color = _auto_text_color(lum, 'slogan')

        if z.get('readability_overlay'):
            overlay = Image.new('RGBA', (rgn_x2 - rgn_x1, rgn_y2 - rgn_y1))
            ov_draw = ImageDraw.Draw(overlay)
            ov_color = (0, 0, 0, z['overlay_alpha']) if lum > 150 else (255, 255, 255, z['overlay_alpha'])
            r = min(rgn_x2 - rgn_x1, rgn_y2 - rgn_y1) // 2
            _rrect(ov_draw, [0, 0, overlay.width, overlay.height], r, ov_color)
            img.paste(Image.alpha_composite(
                img.crop((rgn_x1, rgn_y1, rgn_x2, rgn_y2)).convert('RGBA'), overlay),
                (rgn_x1, rgn_y1))

        draw = ImageDraw.Draw(img)
        _draw_text_shadow(draw, (tx, ty), text, font, text_color, bold=z['bold'])
        applied.append(f'{key}="{text}"')

    # ── 提示 — 小字+阴影，无背景 ──
    for key, text in groups['tip']:
        z = _ZONE['tip']
        fs = int(base * z['font_scale'])
        font = _load_font(fs)
        if not font:
            continue
        y_c = int(h * (z['y_start'] + z['y_end']) / 2)
        bb = tmp_draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        tx, ty = (w - tw) // 2, y_c - th // 2
        safe_y1, safe_y2 = max(0, ty - 5), min(h, ty + th + 5)
        if safe_y2 > safe_y1:
            bg_region = img.crop((max(0, tx - 10), safe_y1, min(w, tx + tw + 10), safe_y2))
            lum = _get_luminance(bg_region)
        else:
            lum = 180
        text_color = _auto_text_color(lum, 'tip')
        draw = ImageDraw.Draw(img)
        _draw_text_shadow(draw, (tx, ty), text, font, text_color, shadow_strength=1)
        applied.append(f'{key}="{text}"')

    # ── 气泡 — 右上小字 ──
    for key, text in groups['bubble']:
        z = _ZONE['bubble']
        fs = int(base * z['font_scale'])
        font = _load_font(fs)
        if not font:
            continue
        bb = tmp_draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        margin = int(w * z['mx'])
        tx = w - margin - tw - 14
        ty = int(h * z['y_start']) + 5
        safe_y1, safe_y2 = max(0, ty - 3), min(h, ty + th + 3)
        if safe_y2 > safe_y1:
            bg_region = img.crop((max(0, tx - 5), safe_y1, min(w, tx + tw + 5), safe_y2))
            lum = _get_luminance(bg_region)
        else:
            lum = 180
        text_color = (255, 255, 255, 230) if lum < 140 else (80, 80, 80, 230)
        draw = ImageDraw.Draw(img)
        _draw_text_shadow(draw, (tx, ty), text, font, text_color, shadow_strength=1)
        applied.append(f'{key}="{text}"')

    # 输出
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
    """顶部标题条（旧接口兼容）"""
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
    font = _load_font(font_size, bold=True)
    if not font:
        return image_data
    draw = ImageDraw.Draw(img)
    bb = draw.textbbox((0, 0), title, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x, y = (w - tw) // 2, (bar_h - th) // 2
    _draw_text_shadow(draw, (x, y), title, font, (255, 255, 255, 255), bold=True)
    buf = io.BytesIO()
    img.convert('RGB').save(buf, format='JPEG', quality=93)
    return buf.getvalue()


# ═══════════════════════════════════════════
# 集成 API
# ═══════════════════════════════════════════

def pil_primary_render(image_data: bytes, manifest: dict,
                       card_title: str = '', mode: str = DEFAULT_PIL_MODE) -> tuple[bytes, bool]:
    """
    PIL 主路径渲染 — v10.3 轻量级卡片版式文字渲染。
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
        print(f'      🎨 PIL卡片版式渲染: {labels_str}')
        return rendered, True
    return image_data, False


# ═══════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════
if __name__ == '__main__':
    print('=== PIL Text Renderer v4 (Card Layout) ===')
    print(f'Default mode: {DEFAULT_PIL_MODE}')
    font = _load_font(36, bold=True)
    print(f'Font loaded: {font is not None}')

    try:
        from PIL import Image, ImageDraw as ID
        import random
        random.seed(42)

        # 模拟 AI 生成的「卡片版式设计」— 有明确的 Banner/卡片/强调条
        w, h = 600, 800
        img = Image.new('RGB', (w, h), (245, 245, 250))
        d = ID.Draw(img)

        # 背景: 柔和渐变
        for y in range(h):
            r = int(240 + 15 * (y / h))
            g = int(235 + 10 * (y / h))
            b = int(245 - 10 * (y / h))
            d.line([(0, y), (w, y)], fill=(min(255, r), min(255, g), max(200, b)))

        # Banner 区域 (top 12%): 深色渐变
        banner_h = int(h * 0.12)
        for y in range(banner_h):
            ratio = y / banner_h
            r = int(80 + 40 * ratio)
            g = int(50 + 30 * ratio)
            b = int(130 + 30 * ratio)
            d.line([(0, y), (w, y)], fill=(r, g, b))

        # 内容卡片区 (14%-78%): 白色圆角卡片
        card_margin = int(w * 0.05)
        card_y1, card_y2 = int(h * 0.14), int(h * 0.78)
        d.rounded_rectangle(
            [card_margin, card_y1, w - card_margin, card_y2],
            radius=18, fill=(255, 255, 255))

        # 口诀强调条 (80%-92%): 暖色
        strip_y1, strip_y2 = int(h * 0.80), int(h * 0.92)
        for y in range(strip_y1, strip_y2):
            ratio = (y - strip_y1) / (strip_y2 - strip_y1)
            d.line([(0, y), (w, y)],
                   fill=(int(255 - 15 * ratio), int(160 + 30 * ratio), int(120 + 20 * ratio)))

        buf = io.BytesIO()
        img.save(buf, format='PNG')

        manifest = {
            'TITLE': '口算拆数法',
            'LINE1': '840 ÷ 4 = ?',
            'LINE2': '先拆: 840 = 800 + 40',
            'LINE3': '800÷4=200, 40÷4=10',
            'ANSWER': '答案: 200+10 = 210 ✓',
            'SLOGAN': '拆开除 再合体',
            'TIP': '⚠️ 先拆成整百整十',
        }
        rendered, applied = pil_full_render(buf.getvalue(), manifest)
        print(f'Rendered: {len(applied)} texts, {len(rendered)} bytes')
        with open('_test_pil_render_v4.jpg', 'wb') as f:
            f.write(rendered)
        print('Saved: _test_pil_render_v4.jpg')
    except ImportError:
        print('PIL not available')
