#!/usr/bin/env python3
"""
知识卡片 HTML 渲染器
====================
用 HTML/CSS 模板 + Selenium Chrome 截图生成卡片图片。
解决 AI 图片模型中文乱码问题：文字由 HTML 精确渲染，保证 100% 准确。

用法:
  python generate_card_images_html.py knowledge_cards/小学/数学_三下.json
  python generate_card_images_html.py knowledge_cards/小学/数学_三下.json --card 05-03
  python generate_card_images_html.py knowledge_cards/小学/数学_三下.json --test
  python generate_card_images_html.py knowledge_cards/小学/数学_三下.json --output card_images
"""

import json, os, sys, time, base64, tempfile, html as html_module

# ─── Card type → color theme mapping ───
CARD_TYPE_THEMES = {
    '方法卡': {
        'gradient': 'linear-gradient(135deg, #FFD89B 0%, #FFA7A7 100%)',
        'banner': '#FF9F43',
        'accent': '#FF6B6B',
        'icon': '📐',
    },
    '概念卡': {
        'gradient': 'linear-gradient(135deg, #A1C4FD 0%, #C2E9FB 100%)',
        'banner': '#54A0FF',
        'accent': '#2E86DE',
        'icon': '💡',
    },
    '辨析卡': {
        'gradient': 'linear-gradient(135deg, #E8D5F5 0%, #D9AAF5 100%)',
        'banner': '#A55EEA',
        'accent': '#8854D0',
        'icon': '🔍',
    },
    '公式卡': {
        'gradient': 'linear-gradient(135deg, #C2E9FB 0%, #A1C4FD 100%)',
        'banner': '#2E86DE',
        'accent': '#54A0FF',
        'icon': '📏',
    },
    '陷阱卡': {
        'gradient': 'linear-gradient(135deg, #FFA7A7 0%, #FF6B6B 100%)',
        'banner': '#FF4757',
        'accent': '#FF6348',
        'icon': '⚠️',
    },
    '速算卡': {
        'gradient': 'linear-gradient(135deg, #FFECD2 0%, #FCB69F 100%)',
        'banner': '#FF9F43',
        'accent': '#EE5A24',
        'icon': '⚡',
    },
    '挑战卡': {
        'gradient': 'linear-gradient(135deg, #FFD89B 0%, #FF9A9E 100%)',
        'banner': '#FF6348',
        'accent': '#FF4757',
        'icon': '🏆',
    },
    '生活卡': {
        'gradient': 'linear-gradient(135deg, #D4FC79 0%, #96E6A1 100%)',
        'banner': '#5ECE7B',
        'accent': '#2ED573',
        'icon': '🏠',
    },
    '对战卡': {
        'gradient': 'linear-gradient(135deg, #A1C4FD 0%, #FFD89B 100%)',
        'banner': '#54A0FF',
        'accent': '#FF9F43',
        'icon': '⚔️',
    },
    '思维卡': {
        'gradient': 'linear-gradient(135deg, #E8D5F5 0%, #C2E9FB 100%)',
        'banner': '#5F27CD',
        'accent': '#341F97',
        'icon': '🧠',
    },
}

DEFAULT_THEME = CARD_TYPE_THEMES['方法卡']

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
    """生成单张知识卡片的完整 HTML"""
    card_type = card.get('type', '方法卡')
    t = theme or CARD_TYPE_THEMES.get(card_type, DEFAULT_THEME)
    
    title = _esc(card.get('title', ''))
    definition = _esc(card.get('definition', ''))
    memory_tip = _esc(card.get('memory_tip', ''))
    card_id = _esc(card.get('full_id', ''))
    difficulty = card.get('difficulty', 3)
    importance = card.get('importance', 3)
    
    # Core points
    core_html = ''
    for i, p in enumerate(card.get('core_points', [])[:4]):
        core_html += f'<div class="core-point"><span class="point-num">{i+1}</span> {_esc(p)}</div>\n'
    
    # Example
    example_html = ''
    ex = card.get('example', {})
    if ex:
        q = _esc(ex.get('question', ''))
        a = _esc(ex.get('answer', ''))
        steps_html = ''
        for i, s in enumerate(ex.get('steps', [])):
            colors = ['#2ED573', '#FF9F43', '#54A0FF', '#A55EEA']
            c = colors[i % len(colors)]
            steps_html += f'''<div class="step">
                <span class="step-badge" style="background:{c};">{i+1}</span>
                <span class="step-text">{_esc(s)}</span>
            </div>\n'''
        
        example_html = f'''
        <div class="example-box">
            <div class="example-question">📝 {q}</div>
            <div class="steps-container">{steps_html}</div>
            <div class="example-answer">✅ 答案：<strong>{a}</strong></div>
        </div>'''
    
    # Mistakes (正误对比)
    mistakes_html = ''
    mistakes = card.get('mistakes', [])
    if mistakes:
        m = mistakes[0]
        wrong = _esc(m.get('wrong', '')).replace('\\n', '<br>')
        correct = _esc(m.get('correct', '')).replace('\\n', '<br>')
        mistakes_html = f'''
        <div class="mistakes-compare">
            <div class="mistake-col wrong-col">
                <div class="mistake-header">❌ 常见错误</div>
                <div class="mistake-body">{wrong}</div>
            </div>
            <div class="mistake-col correct-col">
                <div class="mistake-header">✅ 正确做法</div>
                <div class="mistake-body">{correct}</div>
            </div>
        </div>'''
    
    # Difficulty stars
    stars = '⭐' * difficulty + '☆' * (5 - difficulty)
    
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
    background: {t['gradient']};
    font-family: 'Noto Sans SC', 'Microsoft YaHei', 'PingFang SC', sans-serif;
    padding: 0;
    overflow: hidden;
}}

.card {{
    width: 1080px;
    min-height: 1440px;
    padding: 40px;
    position: relative;
}}

/* ── Banner ── */
.banner {{
    background: {t['banner']};
    border-radius: 24px;
    padding: 32px 40px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
}}
.banner::after {{
    content: '';
    position: absolute;
    top: -30px; right: -30px;
    width: 120px; height: 120px;
    background: rgba(255,255,255,0.1);
    border-radius: 50%;
}}
.banner-icon {{
    font-size: 48px;
    position: absolute;
    top: 20px; right: 30px;
    opacity: 0.3;
}}
.banner-tag {{
    display: inline-block;
    background: rgba(255,255,255,0.25);
    color: white;
    font-size: 22px;
    font-weight: 500;
    padding: 6px 18px;
    border-radius: 20px;
    margin-bottom: 12px;
}}
.banner-title {{
    color: white;
    font-size: 52px;
    font-weight: 900;
    letter-spacing: 2px;
    text-shadow: 0 2px 8px rgba(0,0,0,0.15);
}}
.banner-sub {{
    color: rgba(255,255,255,0.85);
    font-size: 22px;
    font-weight: 300;
    margin-top: 8px;
}}

/* ── Definition ── */
.definition-box {{
    background: white;
    border-radius: 20px;
    padding: 28px 32px;
    margin-bottom: 24px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.06);
    border-left: 5px solid {t['accent']};
}}
.definition-label {{
    color: {t['accent']};
    font-size: 20px;
    font-weight: 700;
    margin-bottom: 8px;
}}
.definition-text {{
    color: #333;
    font-size: 28px;
    font-weight: 400;
    line-height: 1.6;
}}

/* ── Core Points ── */
.core-points {{
    background: white;
    border-radius: 20px;
    padding: 28px 32px;
    margin-bottom: 24px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.06);
}}
.core-points-title {{
    font-size: 26px;
    font-weight: 700;
    color: {t['banner']};
    margin-bottom: 16px;
}}
.core-point {{
    display: flex;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 14px;
    font-size: 24px;
    color: #444;
    line-height: 1.5;
}}
.point-num {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 32px;
    height: 32px;
    background: {t['banner']};
    color: white;
    border-radius: 50%;
    font-size: 18px;
    font-weight: 700;
    flex-shrink: 0;
}}

/* ── Example ── */
.example-box {{
    background: white;
    border-radius: 20px;
    padding: 28px 32px;
    margin-bottom: 24px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.06);
}}
.example-question {{
    font-size: 32px;
    font-weight: 700;
    color: {t['accent']};
    margin-bottom: 20px;
    padding: 16px 20px;
    background: linear-gradient(135deg, rgba(255,107,107,0.08), rgba(255,159,67,0.08));
    border-radius: 14px;
}}
.steps-container {{
    margin: 16px 0;
}}
.step {{
    display: flex;
    align-items: flex-start;
    gap: 14px;
    margin-bottom: 14px;
    font-size: 23px;
    color: #444;
    line-height: 1.55;
}}
.step-badge {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 34px;
    height: 34px;
    color: white;
    border-radius: 10px;
    font-size: 18px;
    font-weight: 700;
    flex-shrink: 0;
}}
.step-text {{
    flex: 1;
}}
.example-answer {{
    font-size: 30px;
    color: #FF4757;
    font-weight: 700;
    padding: 14px 20px;
    background: #FFF5F5;
    border-radius: 14px;
    margin-top: 16px;
}}

/* ── Mistakes Compare ── */
.mistakes-compare {{
    display: flex;
    gap: 16px;
    margin-bottom: 24px;
}}
.mistake-col {{
    flex: 1;
    border-radius: 18px;
    padding: 22px 24px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
}}
.wrong-col {{
    background: #FFF5F5;
    border: 2px solid #FFD5D5;
}}
.correct-col {{
    background: #F0FFF4;
    border: 2px solid #C6F6D5;
}}
.mistake-header {{
    font-size: 24px;
    font-weight: 700;
    margin-bottom: 12px;
}}
.wrong-col .mistake-header {{ color: #FF4757; }}
.correct-col .mistake-header {{ color: #2ED573; }}
.mistake-body {{
    font-size: 20px;
    color: #555;
    line-height: 1.6;
    white-space: pre-line;
    font-family: 'Consolas', 'Noto Sans SC', monospace;
}}

/* ── Memory Tip ── */
.memory-tip {{
    background: linear-gradient(135deg, #FFF9C4, #FFE082);
    border-radius: 20px;
    padding: 24px 32px;
    margin-bottom: 24px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.06);
    position: relative;
}}
.memory-tip::before {{
    content: '💡';
    font-size: 36px;
    position: absolute;
    top: -12px;
    left: 20px;
}}
.memory-tip-label {{
    font-size: 20px;
    font-weight: 700;
    color: #F59E0B;
    margin-bottom: 8px;
    padding-left: 8px;
}}
.memory-tip-text {{
    font-size: 28px;
    font-weight: 700;
    color: #92400E;
    line-height: 1.5;
}}

/* ── Footer ── */
.footer {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 8px;
    color: rgba(0,0,0,0.35);
    font-size: 18px;
}}
.footer-right {{
    display: flex;
    gap: 16px;
    align-items: center;
}}
.difficulty {{
    font-size: 16px;
}}
</style>
</head>
<body>
<div class="card">
    <!-- Banner -->
    <div class="banner">
        <span class="banner-icon">{t['icon']}</span>
        <div class="banner-tag">{_esc(card_type)} · {_esc(subject)}{_esc(grade)}</div>
        <div class="banner-title">{title}</div>
        <div class="banner-sub">{card_id}</div>
    </div>
    
    <!-- Definition -->
    <div class="definition-box">
        <div class="definition-label">📖 知识要点</div>
        <div class="definition-text">{definition}</div>
    </div>
    
    <!-- Core Points -->
    <div class="core-points">
        <div class="core-points-title">🎯 核心要点</div>
        {core_html}
    </div>
    
    <!-- Example -->
    {example_html}
    
    <!-- Mistakes Compare -->
    {mistakes_html}
    
    <!-- Memory Tip -->
    <div class="memory-tip">
        <div class="memory-tip-label">记忆口诀</div>
        <div class="memory-tip-text">{memory_tip}</div>
    </div>
    
    <!-- Footer -->
    <div class="footer">
        <span>小红薯学习平台</span>
        <div class="footer-right">
            <span class="difficulty">难度 {stars}</span>
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
        cmd = [
            chrome,
            '--headless=new',
            '--no-sandbox',
            '--disable-gpu',
            '--disable-dev-shm-usage',
            '--hide-scrollbars',
            f'--window-size={width},2400',
            '--force-device-scale-factor=1',
            f'--screenshot={png_path}',
            f'file:///{tmp.name}',
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        
        if not os.path.exists(png_path):
            raise RuntimeError(f'截图文件未生成. stderr={result.stderr[:500]}')
        
        # Convert PNG→JPG, crop whitespace
        img = Image.open(png_path)
        img = img.convert('RGB')
        
        # Auto-crop bottom whitespace using PIL getbbox on inverted image
        from PIL import ImageChops
        bg = Image.new('RGB', img.size, (255, 255, 255))
        diff = ImageChops.difference(img, bg)
        bbox = diff.getbbox()  # (left, top, right, bottom)
        if bbox:
            bottom = min(bbox[3] + 20, img.height)  # 20px padding
            img = img.crop((0, 0, width, bottom))
        
        img.save(output_path, 'JPEG', quality=92, optimize=True)
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
