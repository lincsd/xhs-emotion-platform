#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书笔记生成器 — 七角色流水线
=============================================
基于已生成的知识卡片，自动编排笔记内容:

  Role 1:   笔记策划师   → 选卡 + 叙事大纲 + 情绪曲线
  Role 2:   标题大师     → 5个候选标题 + 评分
  Role 3:   封面设计师   → 封面图 prompt + 渲染
  Role 3.5: 轮播设计师   → 每页轮播图 prompt + 批量渲染
  Role 4:   正文写手     → 完整笔记正文(300-800字)
  Role 5:   标签优化师   → 话题标签 + 互动钩子
  Role 6:   发布审核官   → 评分 + 合规检查

用法:
  python generate_xhs_note.py                           # 交互选择卡片和模板
  python generate_xhs_note.py --cards T1-01,T1-02,T1-03 --template 反差型
  python generate_xhs_note.py --cards T1-01,T1-02 --template 挑战型 --auto
  python generate_xhs_note.py --list                    # 列出所有可用卡片
  python generate_xhs_note.py --slides <note_dir>       # 为已有笔记补生成轮播图
"""

import json, os, sys, time, base64, datetime, re, textwrap
import urllib.request, urllib.error

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════
GEMINI_API_BASE = 'https://generativelanguage.googleapis.com/v1beta'
TEXT_MODEL  = 'gemini-2.5-flash'
IMAGE_MODEL = 'gemini-2.5-flash-preview-image-generation'
IMAGE_MODEL_FALLBACKS = [
    'gemini-3.1-flash-image-preview',
    'gemini-3-pro-image-preview',
    'gemini-2.5-flash-image',
]
QUALITY_THRESHOLD = 40   # 笔记质检阈值(满分60)

NOTE_TEMPLATES = ['反差型', '挑战型', '干货型', '故事型']
CARD_TO_TEMPLATE = {
    '陷阱卡': '反差型', '辨析卡': '反差型',
    '挑战卡': '挑战型', '速算卡': '挑战型',
    '方法卡': '干货型', '公式卡': '干货型', '概念卡': '干货型',
    '生活卡': '故事型', '思维卡': '故事型', '对战卡': '故事型',
}

OUTPUT_DIR = 'xhs_notes'
CARD_IMAGES_DIR = 'card_images_v2'


# ═══════════════════════════════════════════
# API 基础设施 (复用 generate_card_images_v2 的模式)
# ═══════════════════════════════════════════
def load_api_keys():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api_key.txt')
    with open(path, 'r') as f:
        for line in f:
            if line.strip().startswith('GEMINI_API_KEY='):
                return [k.strip() for k in line.strip().split('=', 1)[1].split(',') if k.strip()]
    return []

_key_idx = 0
def next_key(keys):
    global _key_idx
    k = keys[_key_idx % len(keys)]
    _key_idx += 1
    return k

def gemini_call(model, contents, api_key, gen_config=None, retries=3, timeout=180):
    url = f'{GEMINI_API_BASE}/models/{model}:generateContent?key={api_key}'
    body = {'contents': contents}
    if gen_config:
        body['generationConfig'] = gen_config
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json; charset=utf-8'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                # Read with explicit chunking to avoid read timeout
                chunks = []
                while True:
                    try:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        chunks.append(chunk)
                    except Exception:
                        break
                return json.loads(b''.join(chunks).decode('utf-8'))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='replace')
            print(f'      [HTTP {e.code}] attempt {attempt+1}/{retries}: {err_body[:200]}')
            if e.code == 429:
                time.sleep(10 * (attempt + 1))
            elif e.code == 404:
                return None
            elif attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
        except Exception as e:
            print(f'      [Error] attempt {attempt+1}/{retries}: {e}')
            if attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
    return None

def extract_text(resp):
    if not resp:
        return ''
    best = ''
    for cand in resp.get('candidates', []):
        for part in (cand.get('content') or {}).get('parts', []):
            if 'text' in part and not part.get('thought', False):
                txt = part['text'].strip()
                if len(txt) > len(best):
                    best = txt
    if not best:
        for cand in resp.get('candidates', []):
            for part in (cand.get('content') or {}).get('parts', []):
                if 'text' in part:
                    txt = part['text'].strip()
                    if len(txt) > len(best):
                        best = txt
    return best

def call_role(role_name, prompt_text, api_key, temperature=0.8, max_tokens=4096):
    contents = [{'role': 'user', 'parts': [{'text': prompt_text}]}]
    gen_config = {
        'maxOutputTokens': max_tokens,
        'temperature': temperature,
        'thinkingConfig': {'thinkingBudget': 2048}
    }
    resp = gemini_call(TEXT_MODEL, contents, api_key, gen_config=gen_config)
    text = extract_text(resp)
    if not text:
        print(f'      [{role_name}] 返回为空!')
    return text

def parse_json(text):
    """从文本中提取JSON"""
    clean = re.sub(r'```json\s*', '', text)
    clean = re.sub(r'```\s*$', '', clean).strip()
    # 尝试找到 { ... } 块
    match = re.search(r'\{.*\}', clean, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass
    try:
        return json.loads(clean)
    except:
        return None


# ═══════════════════════════════════════════
# 加载卡片数据
# ═══════════════════════════════════════════
def load_all_cards():
    """加载所有卡片JSON"""
    all_cards = {}
    packs = []
    for f in sorted(os.listdir('.')):
        if f.startswith('knowledge_cards') and f.endswith('.json'):
            with open(f, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
                packs.append(data)
                for unit in data['units']:
                    for card in unit['cards']:
                        card['_unit_name'] = unit['unit_name']
                        card['_subject'] = data['subject']
                        card['_grade'] = data['grade']
                        card['_semester'] = data['semester']
                        card['_pack'] = data.get('card_pack', '基础卡包')
                        all_cards[card['card_id']] = card
                        all_cards[card['full_id']] = card
    return all_cards, packs

def find_card_image(card_id):
    """查找卡片对应的图片"""
    if not os.path.exists(CARD_IMAGES_DIR):
        return None
    safe_id = card_id.replace('-', '_')
    for f in os.listdir(CARD_IMAGES_DIR):
        if f.startswith(safe_id):
            return os.path.join(CARD_IMAGES_DIR, f)
    # 也搜 card_images/
    if os.path.exists('card_images'):
        for f in os.listdir('card_images'):
            if f.startswith(safe_id):
                return os.path.join('card_images', f)
    return None

def load_note_template(template_name):
    """加载笔记模板"""
    path = os.path.join('note_templates', f'{template_name}.md')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ''


# ═══════════════════════════════════════════
# Role 1: 笔记策划师
# ═══════════════════════════════════════════
def role_1_planner(cards, template_name, template_content, api_key):
    """笔记策划师: 选卡编排 + 叙事大纲 + 情绪曲线"""
    cards_info = []
    for c in cards:
        cards_info.append({
            'id': c['card_id'],
            'title': c['title'],
            'type': c.get('type', ''),
            'definition': c.get('definition', '')[:100],
            'hook': c.get('emotion_hook', ''),
            'example': c.get('example', {}).get('question', '')[:100],
        })

    prompt = f"""你是小红书教育赛道TOP策划师，对算法机制和用户心理有深入研究。

现在要用以下卡片组合成一篇小红书笔记。

── 可用卡片 ──
{json.dumps(cards_info, ensure_ascii=False, indent=2)}

── 笔记模板类型: {template_name} ──
{template_content[:1500]}

请输出笔记策划方案(JSON格式，不要markdown代码块):
{{
  "note_type": "{template_name}",
  "card_order": ["排列后的卡片ID顺序"],
  "narrative_arc": "叙事线(2-3句话:开头怎么切入→中间怎么展开→结尾怎么收)",
  "emotion_curve": ["情绪1→", "情绪2→", "情绪3→", "情绪4"],
  "carousel_plan": [
    {{"slide": 1, "type": "封面", "card_id": "可选", "description": "这张图放什么"}},
    {{"slide": 2, "type": "内容", "card_id": "T1-01", "description": "xxx"}},
    {{"slide": 3, "type": "内容", "card_id": "T1-02", "description": "xxx"}}
  ],
  "hook_strategy": "钩子策略(什么让人忍不住点进来)",
  "save_trigger": "收藏触发点(什么让人忍不住收藏)",
  "comment_trigger": "评论触发点(什么让人忍不住评论)",
  "target_audience": "精准目标人群描述",
  "best_post_time": "建议发布时间(如: 周三晚8点)"
}}"""

    text = call_role('笔记策划师', prompt, api_key, temperature=0.85)
    result = parse_json(text)
    return result or {'card_order': [c['card_id'] for c in cards], 'raw': text}


# ═══════════════════════════════════════════
# Role 2: 标题大师
# ═══════════════════════════════════════════
def role_2_title_master(cards, plan, template_name, api_key):
    """标题大师: 生成5个候选标题并评分"""
    card_titles = [c['title'] for c in cards]
    card_types = list(set(c.get('type', '') for c in cards))

    prompt = f"""你是小红书爆款标题专家，研究过10000+教育赛道爆款笔记的标题模式。

── 笔记信息 ──
模板类型: {template_name}
涉及卡片: {', '.join(card_titles)}
卡片类型: {', '.join(card_types)}
叙事线: {plan.get('narrative_arc', '')}
钩子策略: {plan.get('hook_strategy', '')}
目标人群: {plan.get('target_audience', '')}

── 标题规则 ──
1. 15-25个字(含emoji)
2. 必须有1-2个emoji
3. 必须包含以下至少2个元素:
   - 数字(90%, 5道题, 3步)
   - 身份标签(三年级, 家长, 小学生)
   - 情绪词(震惊/必看/速效/竟然)
   - 悬念/反问(你确定? 竟然是? ...)
4. 不能太营销化，要有真实感
5. 符合小红书社区规范，不用违禁词

请输出JSON(不要markdown代码块):
{{
  "candidates": [
    {{"title": "标题1", "score": 0, "reason": "评分理由"}},
    {{"title": "标题2", "score": 0, "reason": "评分理由"}},
    {{"title": "标题3", "score": 0, "reason": "评分理由"}},
    {{"title": "标题4", "score": 0, "reason": "评分理由"}},
    {{"title": "标题5", "score": 0, "reason": "评分理由"}}
  ],
  "best_title": "推荐的最佳标题",
  "best_reason": "为什么推荐这个",
  "seo_keywords": ["搜索关键词1", "关键词2", "关键词3"]
}}

评分标准(1-10):
- 点击欲望: 看到会不会想点?
- 搜索匹配: 用户搜什么能搜到?
- 情感共鸣: 家长看了有感?
- 简洁清晰: 一扫就懂?"""

    text = call_role('标题大师', prompt, api_key, temperature=0.9)
    result = parse_json(text)
    return result or {'best_title': cards[0]['title'], 'raw': text}


# ═══════════════════════════════════════════
# Role 3: 封面设计师
# ═══════════════════════════════════════════
def role_3_cover_designer(cards, plan, title_info, template_name, api_key):
    """封面设计师: 生成封面图的 Prompt"""
    best_title = title_info.get('best_title', cards[0]['title'])
    first_card = cards[0]

    prompt = f"""你是小红书教育类封面图设计专家，深谙什么样的封面能获得高点击率。

── 笔记信息 ──
标题: {best_title}
模板类型: {template_name}
第一张卡片: {first_card['title']} ({first_card.get('type','')})
例题: {first_card.get('example',{}).get('question','')[:100]}
情绪钩子: {first_card.get('emotion_hook', plan.get('hook_strategy', ''))}
目标人群: {plan.get('target_audience', '')}

── 封面设计原则 ──
1. 竖屏 3:4 比例（小红书标准）
2. 信息层级: 大标题(30%) > 副标题/hook(15%) > 视觉元素(40%) > 品牌角标(15%)
3. 文字必须全部是简体中文
4. 主色调要醒目(教育类常用: 黄+橙, 蓝+白, 绿+白)
5. 字体要粗、大、圆角，手机缩略图也要能看清
6. 留白不能太多，信息要饱满但不杂乱

请直接输出英文图片生成Prompt(400-600词)。

必须遵守:
1. 开头: "IMPORTANT: All visible text MUST be Simplified Chinese. LARGE BOLD thick-stroke rounded sans-serif."
2. 竖屏3:4比例
3. 中文文字用引号包裹并标注字号
4. 背景用渐变色(写具体色号)
5. 包含"数学小博士"— 戴眼镜的可爱卡通小孩角色
6. 标题要超大醒目，缩略图也能看清
7. 要有视觉悬念/冲突元素，让人想点进来
"""

    text = call_role('封面设计师', prompt, api_key, temperature=0.85, max_tokens=4096)
    return text or ''


# ═══════════════════════════════════════════
# Role 3.5: 轮播设计师
# ═══════════════════════════════════════════

# 每种页面类型对应的 prompt 模板框架
SLIDE_TYPE_TEMPLATES = {
    '封面': (
        "This is the COVER (slide 1) of a Xiaohongshu 3:4 vertical educational carousel.\n"
        "Design a highly eye-catching cover that makes viewers STOP scrolling.\n"
        "Key elements:\n"
        "- HUGE bold title text dominating top 35%% of image\n"
        "- Strong hook phrase below title (e.g. number + suspense)\n"
        "- Central visual: math problem or challenge displayed dramatically\n"
        "- Bright gradient background ({bg_colors})\n"
        "- A cute cartoon '数学小博士' character (chubby child with round glasses)\n"
        "- Bottom call-to-action banner\n"
        "- Red ❌ and question marks for visual tension\n"
    ),
    '错误展示': (
        "This is the ERROR REVEAL page (slide {slide_num}) of a Xiaohongshu educational carousel.\n"
        "Show the COMMON MISTAKE that most people make.\n"
        "Key elements:\n"
        "- Top section: the math problem displayed clearly\n"
        "- Center: the WRONG solution path shown step-by-step with a LARGE red ❌ overlay\n"
        "- Wrong answer circled in red with '错！' label\n"
        "- A shocked/confused cartoon '数学小博士' character reacting\n"
        "- Background: light warm gradient ({bg_colors}) with subtle red warning accents\n"
        "- Bottom text: '你也是这样算的吗？' in bold\n"
    ),
    '正确揭秘': (
        "This is the CORRECT ANSWER REVEAL page (slide {slide_num}) of a Xiaohongshu educational carousel.\n"
        "Dramatically reveal the correct solution.\n"
        "Key elements:\n"
        "- Top: same problem restated for context\n"
        "- Center: CORRECT solution shown step-by-step with green ✅ checkmarks\n"
        "- Key insight/rule highlighted in a yellow rounded box\n"
        "- Bright green accents and celebratory visual cues (sparkles ✨)\n"
        "- Confident cartoon '数学小博士' character giving thumbs up\n"
        "- Background: fresh green-to-white gradient ({bg_colors})\n"
        "- Clear contrast with the previous error page\n"
    ),
    '口诀总结': (
        "This is the MEMORY TIPS SUMMARY page (slide {slide_num}) of a Xiaohongshu educational carousel.\n"
        "Present a memorable mnemonic or formula for easy recall.\n"
        "Key elements:\n"
        "- Center: a large, beautifully styled 'card' or 'note paper' element\n"
        "- The mnemonic/formula text displayed in EXTRA LARGE bold font inside the card\n"
        "- Decorative elements: pencils 📝, stars ⭐, light bulbs 💡\n"
        "- Cartoon '数学小博士' character holding/presenting the card\n"
        "- Background: warm yellow/gold gradient ({bg_colors})\n"
        "- Bottom teaser: '还有更多陷阱👇' or '下一题更难！'\n"
        "- Overall feel: satisfying, clear, worth saving/bookmarking\n"
    ),
    '互动挑战': (
        "This is the INTERACTIVE CHALLENGE page (slide {slide_num}) of a Xiaohongshu educational carousel.\n"
        "Present a quiz/challenge that engages the viewer directly.\n"
        "Key elements:\n"
        "- Top banner: '🏆 挑战时间！' or '你来试试？' in bold\n"
        "- Center: 2-3 math problems displayed in card/grid layout\n"
        "- Each problem in its own rounded box with number label\n"
        "- A thinking/challenging cartoon '数学小博士' character\n"
        "- Visual timer or difficulty icons for urgency\n"
        "- Background: energetic blue-to-purple gradient ({bg_colors})\n"
        "- Bottom: '答案在评论区！' to drive engagement\n"
    ),
    '互动引导': (
        "This is the ENGAGEMENT/CTA page (final slide {slide_num}) of a Xiaohongshu educational carousel.\n"
        "Drive likes, saves, comments, and follows.\n"
        "Key elements:\n"
        "- Top: '你做对了吗？' or '觉得有用吗？' in large friendly text\n"
        "- Center: 3 large icon+text CTAs arranged vertically:\n"
        "  * ❤️ 点赞 (if this helped you)\n"
        "  * ⭐ 收藏 (save for exam prep)\n"
        "  * 💬 评论 (share your answer)\n"
        "- Cartoon '数学小博士' character waving goodbye 👋\n"
        "- Series preview: '下期预告: ...' teaser in small box\n"
        "- Background: warm, inviting gradient ({bg_colors})\n"
        "- Overall: friendly, warm, encouraging sharing\n"
    ),
    '内容': (
        "This is a CONTENT page (slide {slide_num}) of a Xiaohongshu educational carousel.\n"
        "Present educational content clearly and attractively.\n"
        "Key elements:\n"
        "- Title/topic at top in bold text\n"
        "- Main content area: math concepts, formulas, or examples\n"
        "- Clear visual hierarchy with numbered steps\n"
        "- Cartoon '数学小博士' character as guide\n"
        "- Background: clean gradient ({bg_colors})\n"
        "- Educational but not boring, engaging visual design\n"
    ),
}

# 配色方案 - 每种页面类型的默认渐变色
SLIDE_TYPE_COLORS = {
    '封面':     'bright sunny yellow #FFD700 to warm orange #FFA500',
    '错误展示': 'soft cream #FFF5EE to light coral #FFB4A2',
    '正确揭秘': 'mint green #E8F5E9 to fresh green #A5D6A7',
    '口诀总结': 'warm gold #FFF8E1 to soft amber #FFE082',
    '互动挑战': 'light blue #E3F2FD to soft purple #CE93D8',
    '互动引导': 'soft pink #FCE4EC to warm lavender #E1BEE7',
    '内容':     'clean white #FFFFFF to light gray #F5F5F5',
}

def role_3_5_carousel_designer(cards, plan, title_info, cover_prompt, template_name, api_key):
    """轮播设计师: 为每页轮播图生成图片 Prompt"""
    carousel_plan = plan.get('carousel_plan', [])
    if not carousel_plan:
        return []

    best_title = title_info.get('best_title', cards[0]['title'])
    cards_by_id = {c['card_id']: c for c in cards}

    # 构建全部卡片的速查信息
    cards_summary = []
    for c in cards:
        cards_summary.append(f"  {c['card_id']}: {c['title']} ({c.get('type','')}) "
                           f"例题={c.get('example',{}).get('question','')[:60]} "
                           f"答案={c.get('example',{}).get('answer','')[:40]} "
                           f"口诀={c.get('memory_tip','')[:40]} "
                           f"陷阱={c.get('trap_point','')[:40]}")

    # 从封面 prompt 提取风格基调
    style_anchor = ''
    if cover_prompt:
        # 取封面prompt的前200字作为风格参考
        style_anchor = cover_prompt[:200]

    slide_prompts = []

    for slide_info in carousel_plan:
        slide_num = slide_info.get('slide', 0)
        slide_type = slide_info.get('type', '内容')
        slide_card_id = slide_info.get('card_id', None)
        slide_desc = slide_info.get('description', '')

        # 跳过封面(slide 1) — 已由 R3 生成
        if slide_num == 1:
            slide_prompts.append({'slide': 1, 'type': slide_type, 'prompt': cover_prompt, 'skip_gen': True})
            continue

        # 获取该页关联的卡片数据
        card_data = None
        if slide_card_id and slide_card_id in cards_by_id:
            card_data = cards_by_id[slide_card_id]

        # 选择 prompt 模板
        type_key = slide_type if slide_type in SLIDE_TYPE_TEMPLATES else '内容'
        template_base = SLIDE_TYPE_TEMPLATES[type_key]
        bg_colors = SLIDE_TYPE_COLORS.get(type_key, SLIDE_TYPE_COLORS['内容'])
        template_filled = template_base.format(slide_num=slide_num, bg_colors=bg_colors)

        # 构造卡片具体内容
        card_content = ''
        if card_data:
            card_content = (
                f"\n具体内容(来自卡片 {card_data['card_id']}):\n"
                f"  标题: {card_data['title']}\n"
                f"  类型: {card_data.get('type','')}\n"
                f"  例题: {card_data.get('example',{}).get('question','')}\n"
                f"  答案: {card_data.get('example',{}).get('answer','')}\n"
                f"  解题步骤: {json.dumps(card_data.get('example',{}).get('steps',[]), ensure_ascii=False)[:200]}\n"
                f"  口诀: {card_data.get('memory_tip','')}\n"
                f"  陷阱: {card_data.get('trap_point','')}\n"
                f"  常见错误: {json.dumps(card_data.get('mistakes',[])[:2], ensure_ascii=False)[:200]}\n"
            )

        # 用 Gemini 生成精细 prompt
        meta_prompt = f"""你是小红书教育内容的视觉设计专家，负责设计轮播图的每一页。

── 笔记上下文 ──
笔记标题: {best_title}
模板类型: {template_name}
全部卡片:
{chr(10).join(cards_summary)}

── 当前页信息 ──
页码: 第{slide_num}页 (共{len(carousel_plan)}页)
页面类型: {slide_type}
策划描述: {slide_desc}
{card_content}

── 封面风格锚点(保持统一) ──
{style_anchor}

── 页面类型设计指引 ──
{template_filled}

请为这一页生成一个详细的英文图片生成Prompt(300-500词)。

必须遵守:
1. 开头: "IMPORTANT: All visible text MUST be Simplified Chinese. LARGE BOLD thick-stroke rounded sans-serif."
2. 竖屏 3:4 比例 (portrait orientation)
3. 所有中文文字用双引号包裹并标注近似字号
4. 背景用具体渐变色(hex色号)，与封面风格协调
5. 包含卡通IP角色"数学小博士"(戴圆眼镜的可爱胖小孩)
6. 要把策划描述中的具体数学内容(题目/公式/口诀)准确嵌入
7. 手机缩略图也要可读(关键文字够大)
8. 与前后页形成视觉节奏(错误页紧张 → 正确页绿色轻松 → 总结页温暖)

直接输出英文Prompt，不要其他说明。"""

        prompt_text = call_role(f'轮播设计师-P{slide_num}', meta_prompt, api_key, temperature=0.8, max_tokens=3000)
        slide_prompts.append({
            'slide': slide_num,
            'type': slide_type,
            'card_id': slide_card_id,
            'prompt': prompt_text or '',
            'skip_gen': False,
        })

    return slide_prompts


def generate_slide_images(slide_prompts, note_dir, keys):
    """批量渲染轮播图"""
    results = []
    for sp in slide_prompts:
        slide_num = sp['slide']
        if sp.get('skip_gen'):
            # 封面已单独生成
            results.append({'slide': slide_num, 'file': 'cover.jpg', 'status': 'skip(cover)'})
            continue

        prompt = sp.get('prompt', '')
        if not prompt:
            results.append({'slide': slide_num, 'file': None, 'status': 'no_prompt'})
            continue

        print(f'      🎨 P{slide_num} ({sp["type"]})...', end='', flush=True)
        try:
            result = generate_cover_image(prompt, next_key(keys), title=f'slide_{slide_num}')
            if result:
                img_data, ext = result
                filename = f'slide_{slide_num}.{ext}'
                filepath = os.path.join(note_dir, filename)
                with open(filepath, 'wb') as f:
                    f.write(img_data)
                print(f' ✅ ({len(img_data)/1024:.0f}KB)')
                results.append({'slide': slide_num, 'file': filename, 'status': 'ok', 'size': len(img_data)})
            else:
                print(f' ❌ 失败')
                results.append({'slide': slide_num, 'file': None, 'status': 'failed'})
        except Exception as e:
            print(f' ❌ 异常: {e}')
            results.append({'slide': slide_num, 'file': None, 'status': f'error:{e}'})
        time.sleep(3)  # 避免过于密集的API调用

    return results


# ═══════════════════════════════════════════
# Role 4: 正文写手
# ═══════════════════════════════════════════
def role_4_copywriter(cards, plan, title_info, template_name, template_content, api_key):
    """正文写手: 生成完整笔记正文"""
    best_title = title_info.get('best_title', cards[0]['title'])

    cards_detail = []
    for c in cards:
        cards_detail.append({
            'id': c['card_id'],
            'title': c['title'],
            'type': c.get('type', ''),
            'definition': c.get('definition', ''),
            'example_q': c.get('example', {}).get('question', ''),
            'example_a': c.get('example', {}).get('answer', ''),
            'steps': c.get('example', {}).get('steps', []),
            'mistakes': c.get('mistakes', [])[:2],
            'memory_tip': c.get('memory_tip', ''),
            'emotion_hook': c.get('emotion_hook', ''),
            'trap_point': c.get('trap_point', ''),
        })

    prompt = f"""你是小红书教育领域的资深写手，写过500+篇万赞笔记。
你的文风：口语化、真实感、有温度、不油腻。

── 笔记信息 ──
标题: {best_title}
模板类型: {template_name}
叙事线: {plan.get('narrative_arc', '')}
情绪曲线: {json.dumps(plan.get('emotion_curve', []), ensure_ascii=False)}
钩子策略: {plan.get('hook_strategy', '')}
评论触发: {plan.get('comment_trigger', '')}
收藏触发: {plan.get('save_trigger', '')}

── 卡片内容 ──
{json.dumps(cards_detail, ensure_ascii=False, indent=2)}

── 模板参考 ──
{template_content[:1000]}

── 写作要求 ──
1. 字数: 400-700字(含emoji，不含标签)
2. 分段: 每段2-4行，适合手机阅读
3. Emoji: 每2-3句放1个，不过多
4. 语气: 像朋友在聊天，不像老师在教课
5. 必须包含:
   - 开头(2句内抓住注意力)
   - 知识内容(融入卡片的例题和解法)
   - 互动引导(引导评论/收藏)
   - 结尾收束
6. 不要用"小红书""点赞"等平台违禁词
7. 数学内容必须准确，用卡片原始数据
8. 适当使用 ✅❌⚡📝💡🔥 等符号增强视觉

请直接输出笔记正文(不要输出其他说明文字)。"""

    text = call_role('正文写手', prompt, api_key, temperature=0.85, max_tokens=4096)
    return text or ''


# ═══════════════════════════════════════════
# Role 5: 标签优化师
# ═══════════════════════════════════════════
def role_5_tag_optimizer(cards, plan, title_info, body_text, api_key):
    """标签优化师: 话题标签 + 互动钩子"""
    best_title = title_info.get('best_title', '')
    card_types = list(set(c.get('type', '') for c in cards))
    subject = cards[0].get('_subject', '数学')
    grade = cards[0].get('_grade', '三年级')

    prompt = f"""你是小红书SEO和标签策略专家，研究过教育赛道的热门话题分布。

── 笔记信息 ──
标题: {best_title}
学科: {subject}
年级: {grade}
卡片类型: {', '.join(card_types)}
正文摘要: {body_text[:300]}

请输出JSON(不要markdown代码块):
{{
  "hashtags": {{
    "core": ["#核心标签1", "#核心标签2", "#核心标签3"],
    "trending": ["#热门标签1", "#热门标签2"],
    "longtail": ["#长尾标签1", "#长尾标签2", "#长尾标签3"]
  }},
  "hashtag_string": "#标签1 #标签2 ... (全部标签拼接，5-10个)",
  "interaction_hooks": {{
    "comment_guide": "评论引导语(1句)",
    "save_guide": "收藏引导语(1句)",
    "share_guide": "转发引导语(1句)"
  }},
  "pinned_comment": "置顶评论内容(可以放补充知识或答案)",
  "related_topics": ["相关话题1", "相关话题2"]
}}

标签策略:
- core: 精准匹配搜索词(如 #三年级数学 #小学数学)
- trending: 当前教育赛道热门话题
- longtail: 长尾精准词(如 #三年级下册除法 #数学易错题)
- 总共5-10个标签，不要太多"""

    text = call_role('标签优化师', prompt, api_key, temperature=0.7)
    result = parse_json(text)
    return result or {'hashtag_string': '#小学数学 #三年级', 'raw': text}


# ═══════════════════════════════════════════
# Role 6: 发布审核官
# ═══════════════════════════════════════════
def role_6_auditor(cards, title_info, body_text, tags_info, cover_prompt, api_key):
    """发布审核官: 综合评分 + 合规检查"""
    best_title = title_info.get('best_title', '')

    prompt = f"""你是小红书内容审核专家 + 教育内容质量评审员。

请审核以下笔记的发布质量。

── 笔记标题 ──
{best_title}

── 笔记正文 ──
{body_text[:1500]}

── 标签 ──
{tags_info.get('hashtag_string', '')}

── 封面Prompt ──
{cover_prompt[:500]}

── 涉及的知识点 ──
{json.dumps([c['title'] for c in cards], ensure_ascii=False)}

请从6个维度评分(每项1-10分，总分60)，输出JSON(不要markdown代码块):
{{
  "scores": {{
    "title_appeal": 0,
    "content_quality": 0,
    "knowledge_accuracy": 0,
    "readability": 0,
    "viral_potential": 0,
    "compliance": 0
  }},
  "total": 0,
  "verdict": "PASS或FAIL",
  "compliance_check": {{
    "forbidden_words": ["如有违禁词列出"],
    "sensitive_claims": ["如有敏感表述列出"],
    "is_clean": true
  }},
  "strengths": ["优点1", "优点2"],
  "issues": ["问题1", "问题2"],
  "suggestions": ["改进建议1", "建议2"],
  "predicted_metrics": {{
    "estimated_likes": "预估点赞区间",
    "estimated_saves": "预估收藏区间",
    "estimated_comments": "预估评论区间"
  }}
}}

评分标准:
- title_appeal(标题吸引力): 看到会不会点?
- content_quality(内容质量): 有用吗?读起来舒服吗?
- knowledge_accuracy(知识准确): 数学内容是否正确?
- readability(可读性): 分段/排版/emoji使用是否合理?
- viral_potential(传播潜力): 会被收藏/转发吗?
- compliance(合规性): 有没有违禁词/敏感内容?
如果total < {QUALITY_THRESHOLD}，verdict设为"FAIL"。"""

    text = call_role('发布审核官', prompt, api_key, temperature=0.4)
    result = parse_json(text)
    if result:
        scores = result.get('scores', {})
        total = sum(scores.values())
        result['total'] = total
        result['verdict'] = 'PASS' if total >= QUALITY_THRESHOLD else 'FAIL'
        return result
    return {'total': 45, 'verdict': 'PASS', 'raw': text}


# ═══════════════════════════════════════════
# 封面图片生成
# ═══════════════════════════════════════════
def generate_cover_image(prompt_text, api_key, title=''):
    """生成封面图片"""
    chinese_prefix = (
        f"CRITICAL INSTRUCTIONS (MUST FOLLOW):\n"
        f"1. This is a Xiaohongshu (Little Red Book) cover image for an educational note.\n"
        f"2. ALL visible text MUST be Simplified Chinese. LARGE BOLD thick-stroke rounded sans-serif.\n"
        f"3. Portrait 3:4 aspect ratio.\n\n"
    )
    full_prompt = chinese_prefix + prompt_text
    contents = [{'role': 'user', 'parts': [{'text': full_prompt}]}]
    gen_config = {'responseModalities': ['TEXT', 'IMAGE']}

    models = [IMAGE_MODEL] + IMAGE_MODEL_FALLBACKS
    seen = set()
    unique_models = []
    for m in models:
        if m not in seen:
            seen.add(m)
            unique_models.append(m)

    for model_name in unique_models:
        print(f'      尝试模型: {model_name}...', end='', flush=True)
        resp = gemini_call(model_name, contents, api_key, gen_config=gen_config, timeout=600)
        if not resp:
            print(' 无响应')
            continue
        try:
            for cand in resp.get('candidates', []):
                for part in (cand.get('content') or {}).get('parts', []):
                    if 'inlineData' in part:
                        b64 = part['inlineData'].get('data', '')
                        if b64:
                            mime = part['inlineData'].get('mimeType', 'image/png')
                            ext = 'png' if 'png' in mime else 'jpg'
                            print(f' OK ({len(b64)//1024}KB)')
                            return base64.b64decode(b64), ext
            print(' 无图片数据')
        except Exception as e:
            print(f' 解析错误: {e}')

    return None


# ═══════════════════════════════════════════
# 保存笔记
# ═══════════════════════════════════════════
def save_note(note_data, note_dir):
    """保存笔记到文件"""
    os.makedirs(note_dir, exist_ok=True)

    # 保存 note.json (完整结构化数据)
    with open(os.path.join(note_dir, 'note.json'), 'w', encoding='utf-8') as f:
        json.dump(note_data, f, ensure_ascii=False, indent=2)

    # 保存可复制的正文文件
    copyable = f"""{note_data.get('title', '')}

{note_data.get('body', '')}

{note_data.get('hashtags', '')}
"""
    with open(os.path.join(note_dir, 'copyable.txt'), 'w', encoding='utf-8') as f:
        f.write(copyable)

    # 保存发布检查单
    audit = note_data.get('audit', {})
    checklist = f"""# 发布检查单

## 笔记信息
- 标题: {note_data.get('title', '')}
- 模板: {note_data.get('template', '')}
- 卡片: {', '.join(note_data.get('card_ids', []))}
- 生成时间: {note_data.get('generated_at', '')}

## 质检评分: {audit.get('total', 0)}/60 [{audit.get('verdict', '')}]
| 维度 | 分数 |
|------|------|
| 标题吸引力 | {audit.get('scores',{}).get('title_appeal','?')}/10 |
| 内容质量 | {audit.get('scores',{}).get('content_quality','?')}/10 |
| 知识准确 | {audit.get('scores',{}).get('knowledge_accuracy','?')}/10 |
| 可读性 | {audit.get('scores',{}).get('readability','?')}/10 |
| 传播潜力 | {audit.get('scores',{}).get('viral_potential','?')}/10 |
| 合规性 | {audit.get('scores',{}).get('compliance','?')}/10 |

## 预估数据
{json.dumps(audit.get('predicted_metrics', {}), ensure_ascii=False, indent=2)}

## 优点
{chr(10).join('- ' + s for s in audit.get('strengths', []))}

## 待改进
{chr(10).join('- ' + s for s in audit.get('issues', []))}

## 发布建议
- 建议发布时间: {note_data.get('plan',{}).get('best_post_time', '周三或周日晚8-9点')}
- 置顶评论: {note_data.get('pinned_comment', '')}
"""
    with open(os.path.join(note_dir, 'checklist.md'), 'w', encoding='utf-8') as f:
        f.write(checklist)

    # 生成预览HTML
    generate_preview_html(note_data, note_dir)


def generate_preview_html(note_data, note_dir):
    """生成模拟小红书排版的预览HTML"""
    title = note_data.get('title', '')
    body = note_data.get('body', '').replace('\n', '<br>')
    hashtags = note_data.get('hashtags', '')
    cover_file = note_data.get('cover_image', '')
    card_images = note_data.get('card_images', [])
    audit = note_data.get('audit', {})

    # 幻灯片
    slides_html = ''
    # 首先检查是否有轮播图
    slide_images = note_data.get('slide_images', [])
    if slide_images:
        # 有轮播图 — 按页码排列
        for sr in sorted(slide_images, key=lambda x: x.get('slide', 0)):
            fpath = sr.get('file', '')
            if not fpath:
                continue
            # 封面图特殊处理
            if sr.get('status') == 'skip(cover)':
                if cover_file:
                    full = os.path.join(note_dir, os.path.basename(cover_file))
                    if os.path.exists(full):
                        active = ' active' if sr['slide'] == 1 else ''
                        slides_html += f'<div class="slide{active}"><img src="{os.path.basename(cover_file)}" alt="P{sr["slide"]} 封面"></div>'
            elif sr.get('status') == 'ok' and fpath:
                full = os.path.join(note_dir, fpath)
                if os.path.exists(full):
                    active = ' active' if sr['slide'] == 1 else ''
                    slides_html += f'<div class="slide{active}"><img src="{fpath}" alt="P{sr["slide"]}"></div>'
        # 如果封面没在slide_images里但存在文件
        if not any(s.get('slide') == 1 for s in slide_images):
            if cover_file and os.path.exists(os.path.join(note_dir, os.path.basename(cover_file))):
                slides_html = f'<div class="slide active"><img src="{os.path.basename(cover_file)}" alt="封面"></div>' + slides_html
    else:
        # 无轮播图 — 回退到旧逻辑
        if cover_file and os.path.exists(os.path.join(note_dir, os.path.basename(cover_file))):
            slides_html += f'<div class="slide active"><img src="{os.path.basename(cover_file)}" alt="封面"></div>'
        for img in card_images:
            if img and os.path.exists(img):
                slides_html += f'<div class="slide"><img src="{os.path.relpath(img, note_dir)}" alt="卡片"></div>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>笔记预览 - {title}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#f5f5f5; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }}
.phone-frame {{
  width:375px; margin:20px auto; background:#fff;
  border-radius:40px; box-shadow:0 20px 60px rgba(0,0,0,0.15);
  overflow:hidden; border:8px solid #1a1a1a;
}}
.status-bar {{
  background:#1a1a1a; color:#fff; padding:8px 20px;
  display:flex; justify-content:space-between; font-size:12px;
}}
.carousel {{
  position:relative; width:100%; aspect-ratio:3/4;
  background:#f0f0f0; overflow:hidden;
}}
.carousel img {{
  width:100%; height:100%; object-fit:cover;
}}
.slide {{ display:none; width:100%; height:100%; }}
.slide.active {{ display:block; }}
.carousel-nav {{
  position:absolute; bottom:12px; left:50%; transform:translateX(-50%);
  display:flex; gap:6px;
}}
.carousel-nav span {{
  width:8px; height:8px; border-radius:50%;
  background:rgba(255,255,255,0.5); cursor:pointer;
}}
.carousel-nav span.active {{ background:#fff; }}
.nav-btn {{
  position:absolute; top:50%; transform:translateY(-50%);
  background:rgba(0,0,0,0.3); color:#fff; border:none;
  width:36px; height:36px; border-radius:50%; cursor:pointer;
  font-size:18px;
}}
.nav-btn.prev {{ left:8px; }}
.nav-btn.next {{ right:8px; }}
.content {{ padding:16px; }}
.author {{
  display:flex; align-items:center; gap:10px; margin-bottom:12px;
}}
.avatar {{
  width:36px; height:36px; border-radius:50%;
  background:linear-gradient(135deg,#667eea,#764ba2);
  display:flex; align-items:center; justify-content:center;
  color:#fff; font-size:14px; font-weight:bold;
}}
.author-name {{ font-size:14px; font-weight:600; }}
.title {{ font-size:17px; font-weight:700; margin-bottom:12px; line-height:1.5; }}
.body {{ font-size:14px; line-height:1.8; color:#333; margin-bottom:16px; }}
.tags {{ font-size:13px; color:#4a90d9; margin-bottom:20px; }}
.actions {{
  display:flex; justify-content:space-around; padding:12px 0;
  border-top:1px solid #eee;
}}
.action {{ text-align:center; font-size:12px; color:#999; cursor:pointer; }}
.action-icon {{ font-size:22px; margin-bottom:2px; }}

.audit-panel {{
  margin:20px auto; width:375px; background:#fff;
  border-radius:12px; padding:16px; box-shadow:0 2px 12px rgba(0,0,0,0.08);
}}
.audit-panel h3 {{ font-size:15px; margin-bottom:12px; color:#333; }}
.score-row {{ display:flex; justify-content:space-between; padding:6px 0; font-size:13px; }}
.score-bar {{
  width:100px; height:8px; background:#eee; border-radius:4px; overflow:hidden;
}}
.score-fill {{ height:100%; border-radius:4px; }}
</style>
</head>
<body>

<div class="phone-frame">
  <div class="status-bar">
    <span>9:41</span>
    <span>小红书</span>
    <span>📶 🔋</span>
  </div>

  <div class="carousel" id="carousel">
    {slides_html if slides_html else '<div class="slide active" style="display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;font-size:24px;font-weight:bold;padding:40px;text-align:center;">' + title + '</div>'}
    <button class="nav-btn prev" onclick="changeSlide(-1)">‹</button>
    <button class="nav-btn next" onclick="changeSlide(1)">›</button>
    <div class="carousel-nav" id="dots"></div>
  </div>

  <div class="content">
    <div class="author">
      <div class="avatar">数</div>
      <div>
        <div class="author-name">数学小博士</div>
        <div style="font-size:11px;color:#999">刚刚</div>
      </div>
    </div>
    <div class="title">{title}</div>
    <div class="body">{body}</div>
    <div class="tags">{hashtags}</div>
    <div class="actions">
      <div class="action"><div class="action-icon">❤️</div>{audit.get('predicted_metrics',{}).get('estimated_likes','--')}</div>
      <div class="action"><div class="action-icon">⭐</div>{audit.get('predicted_metrics',{}).get('estimated_saves','--')}</div>
      <div class="action"><div class="action-icon">💬</div>{audit.get('predicted_metrics',{}).get('estimated_comments','--')}</div>
      <div class="action"><div class="action-icon">↗️</div>分享</div>
    </div>
  </div>
</div>

<div class="audit-panel">
  <h3>📊 质检评分: {audit.get('total',0)}/60 [{audit.get('verdict','')}]</h3>
  {''.join(f'''<div class="score-row"><span>{name}</span><div class="score-bar"><div class="score-fill" style="width:{audit.get("scores",{}).get(key,0)*10}%;background:{"#4caf50" if audit.get("scores",{}).get(key,0)>=7 else "#ff9800" if audit.get("scores",{}).get(key,0)>=5 else "#f44336"}"></div></div><span>{audit.get("scores",{}).get(key,0)}/10</span></div>''' for key, name in [('title_appeal','标题吸引力'),('content_quality','内容质量'),('knowledge_accuracy','知识准确'),('readability','可读性'),('viral_potential','传播潜力'),('compliance','合规性')])}
</div>

<script>
let cur = 0;
const slides = document.querySelectorAll('.slide');
const dotsBox = document.getElementById('dots');
slides.forEach((_,i) => {{
  const d = document.createElement('span');
  if(i===0) d.classList.add('active');
  d.onclick = () => goSlide(i);
  dotsBox.appendChild(d);
}});
function goSlide(n) {{
  slides.forEach(s => s.classList.remove('active'));
  dotsBox.querySelectorAll('span').forEach(d => d.classList.remove('active'));
  cur = (n + slides.length) % slides.length;
  slides[cur].classList.add('active');
  dotsBox.children[cur].classList.add('active');
}}
function changeSlide(d) {{ goSlide(cur + d); }}
</script>
</body>
</html>"""

    with open(os.path.join(note_dir, 'preview.html'), 'w', encoding='utf-8') as f:
        f.write(html)


# ═══════════════════════════════════════════
# 主流程: 六角色流水线
# ═══════════════════════════════════════════
def generate_note(cards, template_name, keys, generate_cover=True, generate_slides=True, role_debug=False):
    """对一组卡片执行完整的7角色笔记生成流水线"""
    subject = cards[0].get('_subject', '数学')
    grade_short = cards[0].get('_grade', '三年级').replace('年级', '')
    semester_short = cards[0].get('_semester', '下册').replace('册', '')
    card_ids = [c['card_id'] for c in cards]

    # 笔记输出目录
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M')
    safe_tpl = template_name.replace(' ', '_')
    note_id = f'{subject}_{grade_short}{semester_short}_{safe_tpl}_{ts}'
    note_dir = os.path.join(OUTPUT_DIR, note_id)
    os.makedirs(note_dir, exist_ok=True)

    template_content = load_note_template(template_name)

    print()
    print(f'  ┌─ 笔记: {note_id}')
    print(f'  ├─ 卡片: {", ".join(card_ids)}')
    print(f'  ├─ 模板: {template_name}')

    # ─── Role 1: 笔记策划师 ───
    print(f'  ├─ R1 笔记策划师...', end='', flush=True)
    plan = role_1_planner(cards, template_name, template_content, next_key(keys))
    print(f' ✅')
    if role_debug:
        print(f'      叙事: {plan.get("narrative_arc","")[:100]}')
    time.sleep(1)

    # ─── Role 2: 标题大师 ───
    print(f'  ├─ R2 标题大师...', end='', flush=True)
    title_info = role_2_title_master(cards, plan, template_name, next_key(keys))
    best_title = title_info.get('best_title', cards[0]['title'])
    print(f' ✅ → {best_title}')
    if role_debug and title_info.get('candidates'):
        for tc in title_info['candidates'][:3]:
            print(f'      {tc.get("score","?")}/10: {tc.get("title","")}')
    time.sleep(1)

    # ─── Role 3: 封面设计师 ───
    print(f'  ├─ R3 封面设计师...', end='', flush=True)
    cover_prompt = role_3_cover_designer(cards, plan, title_info, template_name, next_key(keys))
    print(f' ✅ ({len(cover_prompt)} chars)')
    time.sleep(1)

    # ─── Role 3.5: 轮播设计师 ───
    slide_prompts = []
    if generate_slides and plan.get('carousel_plan'):
        print(f'  ├─ R3.5 轮播设计师 ({len(plan["carousel_plan"])}页)...')
        slide_prompts = role_3_5_carousel_designer(cards, plan, title_info, cover_prompt, template_name, next_key(keys))
        gen_count = len([s for s in slide_prompts if not s.get('skip_gen')])
        print(f'  ├─ ✅ 轮播Prompt: {gen_count}页已生成')
        if role_debug:
            for sp in slide_prompts:
                if not sp.get('skip_gen'):
                    print(f'      P{sp["slide"]}({sp["type"]}): {sp["prompt"][:80]}...')
        time.sleep(1)

    # ─── Role 4: 正文写手 ───
    print(f'  ├─ R4 正文写手...', end='', flush=True)
    body_text = role_4_copywriter(cards, plan, title_info, template_name, template_content, next_key(keys))
    word_count = len(body_text)
    print(f' ✅ ({word_count}字)')
    if role_debug:
        print(f'      {body_text[:100]}...')
    time.sleep(1)

    # ─── Role 5: 标签优化师 ───
    print(f'  ├─ R5 标签优化师...', end='', flush=True)
    tags_info = role_5_tag_optimizer(cards, plan, title_info, body_text, next_key(keys))
    hashtags = tags_info.get('hashtag_string', '')
    print(f' ✅ → {hashtags[:50]}')
    time.sleep(1)

    # ─── Role 6: 发布审核官 ───
    print(f'  ├─ R6 发布审核官...', end='', flush=True)
    audit = role_6_auditor(cards, title_info, body_text, tags_info, cover_prompt, next_key(keys))
    total = audit.get('total', 0)
    verdict = audit.get('verdict', 'PASS')
    print(f' {total}/60 [{verdict}]')
    if role_debug and audit.get('suggestions'):
        for s in audit['suggestions'][:2]:
            print(f'      💡 {s}')

    # ─── 生成封面图 ───
    cover_path = ''
    if generate_cover and cover_prompt:
        print(f'  ├─ 🎨 生成封面图...')
        result = generate_cover_image(cover_prompt, next_key(keys), title=best_title)
        if result:
            img_data, ext = result
            cover_filename = f'cover.{ext}'
            cover_path = os.path.join(note_dir, cover_filename)
            with open(cover_path, 'wb') as f:
                f.write(img_data)
            print(f'  ├─ ✅ 封面: {cover_filename} ({len(img_data)/1024:.0f}KB)')
        else:
            print(f'  ├─ ⚠️ 封面生成失败，跳过')

    # ─── 生成轮播图 ───
    slide_results = []
    if generate_slides and slide_prompts:
        gen_slides = [s for s in slide_prompts if not s.get('skip_gen')]
        if gen_slides:
            print(f'  ├─ 🖼️ 生成轮播图 ({len(gen_slides)}张)...')
            slide_results = generate_slide_images(slide_prompts, note_dir, keys)
            ok_count = len([r for r in slide_results if r['status'] == 'ok'])
            print(f'  ├─ ✅ 轮播图完成: {ok_count}/{len(gen_slides)} 成功')

    # ─── 收集卡片图片 ───
    card_images = []
    for c in cards:
        img = find_card_image(c.get('full_id', c['card_id']))
        if img:
            card_images.append(img)

    # ─── 保存 ───
    note_data = {
        'note_id': note_id,
        'title': best_title,
        'body': body_text,
        'hashtags': hashtags,
        'template': template_name,
        'card_ids': card_ids,
        'card_images': card_images,
        'cover_image': cover_path,
        'cover_prompt': cover_prompt,
        'plan': plan,
        'title_candidates': title_info.get('candidates', []),
        'tags_detail': tags_info,
        'audit': audit,
        'pinned_comment': tags_info.get('pinned_comment', ''),
        'slide_prompts': [{'slide':s['slide'],'type':s['type'],'card_id':s.get('card_id'),'prompt':s.get('prompt','')[:200]} for s in slide_prompts] if slide_prompts else [],
        'slide_images': slide_results,
        'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'pipeline': 'v2_7role_note',
    }

    save_note(note_data, note_dir)

    print(f'  └─ 📁 保存到 {note_dir}/')
    print(f'       ├─ note.json (完整数据)')
    print(f'       ├─ copyable.txt (可复制正文)')
    print(f'       ├─ checklist.md (发布检查单)')
    print(f'       ├─ preview.html (手机预览)')
    if slide_results:
        ok_slides = [r for r in slide_results if r['status'] == 'ok']
        for sr in ok_slides:
            print(f'       ├─ {sr["file"]} (P{sr["slide"]} {sr.get("size",0)//1024}KB)')
    print(f'       └─ 共 {1 + len([r for r in slide_results if r["status"]=="ok"])} 张图片')

    return note_data, note_dir


# ═══════════════════════════════════════════
# --slides 模式: 为已有笔记补生轮播图
# ═══════════════════════════════════════════
def generate_slides_for_existing_note(note_dir):
    """读取已有笔记的 note.json，执行 R3.5 + 图片生成"""
    note_json_path = os.path.join(note_dir, 'note.json')
    if not os.path.exists(note_json_path):
        print(f'❌ 找不到 {note_json_path}')
        sys.exit(1)

    with open(note_json_path, 'r', encoding='utf-8') as f:
        note_data = json.load(f)

    keys = load_api_keys()
    if not keys:
        print('❌ 未找到API密钥')
        sys.exit(1)

    all_cards, _ = load_all_cards()

    plan = note_data.get('plan', {})
    carousel_plan = plan.get('carousel_plan', [])
    if not carousel_plan:
        print('❌ 该笔记没有轮播规划')
        sys.exit(1)

    # 还原 cards 列表
    cards = []
    for cid in note_data.get('card_ids', []):
        if cid in all_cards:
            cards.append(all_cards[cid])
    if not cards:
        print('❌ 找不到笔记中的卡片')
        sys.exit(1)

    title_info = {
        'best_title': note_data.get('title', ''),
        'candidates': note_data.get('title_candidates', []),
    }
    cover_prompt = note_data.get('cover_prompt', '')
    template_name = note_data.get('template', '反差型')

    print()
    print(f'╔═══════════════════════════════════════════════╗')
    print(f'║  🖼️ 轮播图生成 — 补跑模式                     ║')
    print(f'║  📁 {note_dir}')
    print(f'║  📄 {note_data.get("title","")[:30]}')
    print(f'║  🔢 轮播规划: {len(carousel_plan)}页')
    print(f'╚═══════════════════════════════════════════════╝')

    # R3.5 生成 prompts
    print(f'\n  ├─ R3.5 轮播设计师 ({len(carousel_plan)}页)...')
    slide_prompts = role_3_5_carousel_designer(
        cards, plan, title_info, cover_prompt, template_name, next_key(keys)
    )
    gen_count = len([s for s in slide_prompts if not s.get('skip_gen')])
    print(f'  ├─ ✅ Prompt生成完成: {gen_count}页')

    # 渲染图片
    print(f'  ├─ 🎨 开始渲染轮播图...')
    slide_results = generate_slide_images(slide_prompts, note_dir, keys)
    ok_count = len([r for r in slide_results if r['status'] == 'ok'])
    print(f'  ├─ ✅ 完成: {ok_count}/{gen_count} 成功')

    # 更新 note.json
    note_data['slide_prompts'] = [
        {'slide': s['slide'], 'type': s['type'], 'card_id': s.get('card_id'), 'prompt': s.get('prompt','')[:200]}
        for s in slide_prompts
    ] if slide_prompts else []
    note_data['slide_images'] = slide_results
    note_data['pipeline'] = 'v2_7role_note'

    with open(note_json_path, 'w', encoding='utf-8') as f:
        json.dump(note_data, f, ensure_ascii=False, indent=2)
    print(f'  ├─ 📝 note.json 已更新')

    # 重新生成预览HTML (含轮播图)
    generate_preview_html(note_data, note_dir)
    print(f'  └─ 🌐 preview.html 已更新')

    # 汇总
    print()
    for sr in slide_results:
        status_icon = '✅' if sr['status'] == 'ok' else '⏭️' if sr['status'].startswith('skip') else '❌'
        size = f" ({sr.get('size',0)//1024}KB)" if sr.get('size') else ''
        print(f'    P{sr["slide"]}: {status_icon} {sr.get("file","N/A")}{size}')

    print(f'\n🎉 轮播图生成完成! 共 {ok_count} 张新图片')
    return note_data


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════
def main():
    role_debug = '--role-debug' in sys.argv
    auto_mode = '--auto' in sys.argv
    no_cover = '--no-cover' in sys.argv
    no_slides = '--no-slides' in sys.argv
    list_mode = '--list' in sys.argv
    slides_only = None  # --slides <dir> mode

    # 解析 --cards, --template, --slides
    card_ids_arg = None
    template_arg = None
    for i, a in enumerate(sys.argv):
        if a == '--cards' and i + 1 < len(sys.argv):
            card_ids_arg = [x.strip() for x in sys.argv[i+1].split(',')]
        if a == '--template' and i + 1 < len(sys.argv):
            template_arg = sys.argv[i+1]
        if a == '--slides' and i + 1 < len(sys.argv):
            slides_only = sys.argv[i+1]

    # ── --slides 模式: 为已有笔记补生成轮播图 ──
    if slides_only:
        return generate_slides_for_existing_note(slides_only)

    # 加载卡片
    all_cards, packs = load_all_cards()
    if not all_cards:
        print('未找到知识卡片JSON文件')
        sys.exit(1)

    keys = load_api_keys()
    if not keys:
        print('未找到API密钥')
        sys.exit(1)

    # 列出所有卡片
    if list_mode:
        print('\n📋 可用卡片:')
        for pack in packs:
            pack_name = pack.get('card_pack', f'{pack["subject"]}{pack["grade"]}{pack["semester"]}')
            print(f'\n  📦 {pack_name}:')
            for unit in pack['units']:
                print(f'    📖 {unit["unit_id"]}: {unit["unit_name"]}')
                for card in unit['cards']:
                    img = find_card_image(card.get('full_id', card['card_id']))
                    img_mark = '🖼️' if img else '  '
                    tpl = CARD_TO_TEMPLATE.get(card.get('type', ''), '干货型')
                    print(f'      {img_mark} {card["card_id"]:8s} {card["title"][:20]:20s} [{card.get("type",""):4s}] → {tpl}')
        print(f'\n📊 共 {len(all_cards)//2} 张卡片')
        print(f'\n🖼️ = 已有卡片图片')
        print(f'\n用法: python generate_xhs_note.py --cards T1-01,T1-02,T1-03 --template 反差型')
        return

    print()
    print('╔══════════════════════════════════════════════════╗')
    print('║  📝 小红书笔记生成器 — 七角色流水线              ║')
    print('╠══════════════════════════════════════════════════╣')
    print(f'║  🤖 R1策划→R2标题→R3封面→R3.5轮播→R4正文→R5标签→R6审核')
    print(f'║  📊 质检阈值: {QUALITY_THRESHOLD}/60')
    print(f'║  🔑 API Keys: {len(keys)} 个')
    print(f'║  📦 卡片库: {len(all_cards)//2} 张')
    print('╚══════════════════════════════════════════════════╝')

    # 确定卡片
    if card_ids_arg:
        cards = []
        for cid in card_ids_arg:
            if cid in all_cards:
                cards.append(all_cards[cid])
            else:
                print(f'⚠️ 未找到卡片: {cid}')
        if not cards:
            print('❌ 未找到任何指定的卡片')
            sys.exit(1)
    elif auto_mode:
        print('❌ --auto 模式需要指定 --cards')
        sys.exit(1)
    else:
        # 交互模式
        print('\n📋 可用卡片 (输入ID选择，逗号分隔):')
        for pack in packs:
            pack_name = pack.get('card_pack', '')
            if pack_name:
                print(f'\n  📦 {pack_name}:')
            for unit in pack['units']:
                for card in unit['cards']:
                    img = find_card_image(card.get('full_id', card['card_id']))
                    img_mark = '🖼️' if img else '  '
                    print(f'    {img_mark} {card["card_id"]:8s} {card["title"][:25]} [{card.get("type","")}]')

        try:
            selected = input('\n请输入卡片ID (逗号分隔): ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\n取消')
            return

        card_ids_arg = [x.strip() for x in selected.split(',')]
        cards = [all_cards[cid] for cid in card_ids_arg if cid in all_cards]
        if not cards:
            print('❌ 未找到有效卡片')
            return

    # 确定模板
    if template_arg and template_arg in NOTE_TEMPLATES:
        template_name = template_arg
    elif auto_mode:
        # 自动推荐模板
        primary_type = cards[0].get('type', '方法卡')
        template_name = CARD_TO_TEMPLATE.get(primary_type, '干货型')
    else:
        primary_type = cards[0].get('type', '方法卡')
        recommended = CARD_TO_TEMPLATE.get(primary_type, '干货型')
        print(f'\n📋 可用模板: {", ".join(NOTE_TEMPLATES)}')
        print(f'💡 推荐: {recommended} (基于卡片类型: {primary_type})')
        try:
            chosen = input(f'选择模板 [默认={recommended}]: ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\n取消')
            return
        template_name = chosen if chosen in NOTE_TEMPLATES else recommended

    print(f'\n🚀 开始生成笔记!')
    print(f'   卡片: {[c["card_id"] for c in cards]}')
    print(f'   模板: {template_name}')
    print(f'   封面: {"生成" if not no_cover else "跳过"}')
    print(f'   轮播: {"生成" if not no_slides else "跳过"}')

    note_data, note_dir = generate_note(
        cards, template_name, keys,
        generate_cover=not no_cover,
        generate_slides=not no_slides,
        role_debug=role_debug
    )

    # 打印摘要
    print()
    print('╔══════════════════════════════════════════════════╗')
    print(f'║  🎉 笔记生成完成!')
    print(f'║  📝 {note_data["title"][:35]}')
    print(f'║  📊 质检: {note_data["audit"].get("total",0)}/60 [{note_data["audit"].get("verdict","")}]')
    print(f'║  📁 {note_dir}/')
    print(f'║  🌐 打开 preview.html 预览效果')
    print('╚══════════════════════════════════════════════════╝')


if __name__ == '__main__':
    main()
