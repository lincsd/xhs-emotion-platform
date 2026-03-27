#!/usr/bin/env python3
"""
知识卡片图片生成器 (两步法)
Step 1: Gemini 2.5 Flash 生成图片提示词 (Prompt)
Step 2: Gemini 原生图片生成模型 生成可爱童趣风格卡片图片

用法:
  python generate_card_images.py                          # 默认: 找 knowledge_cards*.json
  python generate_card_images.py cards.json               # 指定JSON
  python generate_card_images.py cards.json card_images   # 指定JSON + 输出目录
  python generate_card_images.py --test                   # 只测试1张卡片
"""

import json, os, sys, time, base64, datetime
import urllib.request, urllib.error

# ─── 审校模块 ───
try:
    from card_review import (
        run_review_gate, is_english_grammar_card,
        generate_english_grammar_prompt, build_structured_payload,
    )
    _HAS_REVIEW = True
except ImportError:
    _HAS_REVIEW = False
    print('[WARN] card_review.py not found, 审校层未启用')

GEMINI_API_BASE = 'https://generativelanguage.googleapis.com/v1beta'
TEXT_MODEL = 'gemini-2.5-flash'
IMAGE_MODEL = 'nano-banana-pro-preview'  # nano banana 原生图片生成

# ─── API Key ───
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

# ─── Gemini API call ───
def gemini_call(model, contents, api_key, gen_config=None, retries=3):
    url = f'{GEMINI_API_BASE}/models/{model}:generateContent?key={api_key}'
    body = {'contents': contents}
    if gen_config:
        body['generationConfig'] = gen_config
    data = json.dumps(body).encode('utf-8')
    
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='replace')
            print(f'\n    [HTTP {e.code}] attempt {attempt+1}/{retries}: {err_body[:300]}')
            if e.code == 429:
                wait = 10 * (attempt + 1)
                print(f'    ⏳ 频率限制, 等待{wait}秒...')
                time.sleep(wait)
            elif e.code == 404:
                print(f'    ❌ 模型不存在, 跳过重试')
                return None
            elif attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
        except Exception as e:
            print(f'\n    [Error] attempt {attempt+1}/{retries}: {e}')
            if attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
    return None

# ─── Card-Type Visual Strategy Rules ───
CARD_TYPE_VISUAL_RULES = {
    '方法卡': {
        'solve_strategy': """运算方法类（含"笔算""竖式""列式"）：
   - ✅ 必须画出简化竖式！竖式是核心教学内容，不能省略
   - 竖式用彩色分层：第一层积(绿色)、第二层积(橙色)、最终和(红色大字)
   - 用色块+箭头标注关键步骤（如"错位"用虚线框高亮）
   - 竖式旁边放正误对比（✓正确对齐 vs ✗错误对齐）
   其他方法类（口算/估算/简便计算）：
   - 把数拆开→用色块区分→得到答案
   - 不画竖式，用直观色块分步
   几何方法类（面积/周长/体积）：
   - 画出实际图形+标注+辅助线
   - 公式代入用色块对应""",
    },
    '概念卡': {
        'solve_strategy': """用生活场景/实物图解释抽象概念：
   - 优先画生活实物（如分数=切披萨，千克=一袋米）
   - 概念名称超大展示，定义浓缩为≤6字金句
   - 不画运算过程，重在"是什么"而非"怎么算" """,
    },
    '辨析卡': {
        'solve_strategy': """左右并排对比，一目了然：
   - 左边 ✗(红色标记) 展示常见错误
   - 右边 ✓(绿色标记) 展示正确做法
   - 红圈/红框高亮差异点（只标1处最关键的）
   - 底部一句话总结区别""",
    },
    '公式卡': {
        'solve_strategy': """图形推导→公式→代入验证：
   - 用格子图/拼图直观推导公式由来
   - 公式本身超大醒目展示（占30%面积）
   - 举一个代入计算的小例子""",
    },
    '陷阱卡': {
        'solve_strategy': """先设坑→再揭秘：
   - 大字展示容易错的题目（设置悬念）
   - 展示错误答案并画叉
   - 揭示正确答案，红圈标出陷阱在哪
   - 钩子文案："90%同学做错" """,
    },
    '速算卡': {
        'solve_strategy': """慢方法vs快技巧对比：
   - 左边🐢常规慢方法(灰色，划掉)
   - 右边⚡速算技巧(彩色，高亮)
   - 速算步骤用色块分步展示
   - 强调"比普通方法快N倍" """,
    },
    '挑战卡': {
        'solve_strategy': """限时闯关+悬念：
   - 关卡编号金色醒目
   - 大题目展示（占30%）
   - 倒计时元素增加紧迫感
   - 答案区域用刮刮卡/折叠样式""",
    },
    '生活卡': {
        'solve_strategy': """生活场景→数学问题→实用解法：
   - 生活场景插画（占40%）
   - 气泡标注数学计算过程
   - 实用结论大字展示""",
    },
    '对战卡': {
        'solve_strategy': """左右分栏PK：
   - 左蓝(家长) VS 右粉(孩子)
   - 同类不同难度的题目
   - 计分栏增加互动感""",
    },
    '思维卡': {
        'solve_strategy': """有趣问题→可视化思维→优雅解法：
   - 情境问题大字展示
   - 思维过程用色块分步可视化（占45%）
   - 方法名+答案醒目展示""",
    },
}

def _detect_vertical_calc(card):
    """检测是否为需要画竖式的卡片（笔算/竖式/列式计算类）"""
    keywords = ['笔算', '竖式', '列式', '列竖式']
    title = card.get('title', '')
    definition = card.get('definition', '')
    question = card.get('example', {}).get('question', '')
    text = title + definition + question
    return any(k in text for k in keywords)

# ─── Step 1: Generate image prompt ───
PROMPT_SYSTEM_TEMPLATE = """你是一位拥有25年{subject}教学经验的特级教师 + 小红书爆款卡片设计师。

你的核心使命：用一道具体例题，让一个完全没学过的孩子，看一眼就「懂了！」

你的任务：将知识点转化为一段英文AI图片生成提示词。

══════ 教学思路（最重要！）══════

⚠️ 每张卡片 = 一道具体例题的"一图秒懂"讲解！

设计思路（必须严格按这个顺序）：

第一步：选择一道真实例题
   - 从知识点的例题中选一道最典型的题目
   - 这道题必须在卡片上清晰展示出来！
   - 例："840 ÷ 4 = ?"（大号，醒目）
   - 例："边长6dm的正方形，面积=?"
   - ⚠️ 题目是整张卡片的核心！没有题目的卡片是失败的

第二步：画出解题的关键步骤
{solve_strategy_block}

第三步：大字展示答案 + 口诀
   - 答案用超大字+鲜明色（"= 210"）
   - 一句口诀帮助记忆（≤10字）

⚠️ 绝对不要做的事：
   - ❌ 不画没有标签的裸箭头（看的人不知道箭头什么意思）
   - ❌ 箭头不超过3个
   - ❌ 不要让人猜"这是在解什么题"——题目必须清晰可见
   - ❌ 不要只有口诀/结论，没有具体例题
   - ❌ 不要把解题过程中的数字写错（必须和提供的例题数字完全一致！）

══════ 视觉设计 ══════

1. 核心教学图（占 ≥ 45%）：
   - 大、简洁、直观——用最简方式把知识点"画"出来
   - 优先用实物/场景图，而非抽象符号
   - 颜色编码区分不同概念

2. 简洁原则：
   - 全卡最多4个视觉区块：标题 / 核心图 / 金句+对比 / 口诀
   - 每个区块之间有大间距
   - ≥ 25% 留白
   - 箭头 ≤ 3个，都带标签

3. 小老师卡通：一个可爱角色 + ≤6字气泡

══════ 配色（要吸引人！）══════

⚠️ 小红书风格：鲜明、温暖、有活力！不要太淡！

- 背景：渐变色（不是纯色！）
  选一个主题渐变：珊瑚粉渐变(#FF9A9E→#FAD0C4) 或 薄荷蓝渐变(#A1C4FD→#C2E9FB) 或 蜜桃橙渐变(#FFD89B→#FFA7A7) 或 薰衣草紫渐变(#E8D5F5→#D9AAF5)
- 标题banner：鲜明饱和色（如亮珊瑚#FF6B6B / 活力橙#FF9F43 / 明亮蓝#54A0FF / 清新绿#5ECE7B）
- 内容区块：白色或浅奶油色圆角卡片(带微妙阴影)
- 重点数字/公式：用鲜明对比色（红/橙/蓝）超大加粗
- ✓ 用翠绿 #2ED573, ✗ 用亮红 #FF4757
- 装饰：2-3个手绘小图标（铅笔/灯泡/星星），颜色与主题色呼应
- 整体：饱和度中高，温暖有活力，像一张让人想收藏的笔记

══════ 文字原则 ══════

- 全卡中文 ≤ 35字
- 标题 ≤ 4字（超大72pt粗体，白色/深色看背景）
- 核心金句 ≤ 6字（大号48pt加粗，鲜明色）
- 口诀 ≤ 10字（便签纸风格）
- 气泡 ≤ 6字
- ❌ 没有任何超过6字的连续文字
- ❌ 不写段落/定义/解释
- 字体：圆体/黑体粗笔画，❌ 不用细体/草书

══════ 布局（从上到下，围绕例题展开）══════

[CANVAS] 竖屏3:4, 渐变背景, 风格
[TITLE] 顶部10%: 鲜色banner + 标题(≤4字白色超大) + 小标签
[PROBLEM] 15%: ⚠️例题(白色圆角卡片内, 超大醒目字体展示具体题目, 如"840 ÷ 4 = ?")
[SOLVE] 中间40%: 解题关键步骤(根据题型选择最合适的视觉方式: 竖式/色块分步/图形/对比)
[ANSWER] 12%: 答案(超大鲜明色, 如 "= 210") + 口诀(色彩便签风, ≤10字)
[BOTTOM] 底部8%: 小老师卡通+气泡(≤6字)
[STYLE] 风格关键词

══════ 输出 ══════

只输出英文提示词，不输出其他文字。

提示词要求：
- 开头写: "IMPORTANT: All visible text MUST be Simplified Chinese (简体中文). LARGE BOLD thick-stroke rounded sans-serif. Max 35 Chinese chars total, each block ≤6 chars. No English. Clean spacious layout, ≥25% whitespace."
- 中文用引号包裹
- 指定字号（"72pt bold", "48pt"等）
- ⚠️ 必须有一道清晰的例题展示在卡面上（如"840 ÷ 4 = ?"），字号要大，位置要醒目
- ⚠️ 解题过程中所有数字必须和例题完全一致，不能编造或搞混数字
- ⚠️ 根据题型选择最佳视觉方式：笔算类画竖式（彩色分层），口算类用色块拆分，几何类画图形
- ⚠️ 箭头≤3个且必须有中文标签，不画裸箭头
- ✓/✗对比只一组（如有），大图并排，红圈标差异
- 答案用超大鲜明色展示
- 背景用渐变色（写具体色号），标题用饱和色banner
- 解题图描述要详细但图本身要简洁直观
- 长度: 350-500英文单词"""

def generate_image_prompt(card, subject, grade, semester, api_key, payload=None):
    """Step 1: 用文字模型生成精简但视觉丰富的提示词（按卡片类型选择视觉策略）
    
    如果 payload 传入且 is_english_grammar=True，走英语语法卡专用分支。
    """
    # ── 英语语法卡专用分支 ──
    if payload and payload.get('is_english_grammar') and _HAS_REVIEW:
        print('      [英语语法卡专用 prompt]')
        return generate_english_grammar_prompt(payload, gemini_call, api_key, TEXT_MODEL)
    
    # ── 根据卡片类型选择视觉策略 ──
    card_type = card.get('type', '方法卡')
    type_rules = CARD_TYPE_VISUAL_RULES.get(card_type, CARD_TYPE_VISUAL_RULES['方法卡'])
    is_vertical_calc = _detect_vertical_calc(card)
    
    # 构建解题策略指导块
    if is_vertical_calc:
        solve_block = """   ⚠️ 这是笔算/竖式类卡片，竖式本身就是教学内容！
   - ✅ 必须画出简化竖式（这是本卡的核心！）
   - 竖式用彩色分层：第一层积(绿色)、第二层积(橙色)、最终和(红色超大)
   - 十位乘的那层必须明确画出"向左错一位"（用虚线/色块高亮错位）
   - 竖式旁可放一个正误对比小图（✓正确对齐 vs ✗错误对齐）
   - 竖式中每个数字必须和例题完全一致，不能编造数字！
   - 竖式保持简洁清晰，用颜色区分而非文字堆砌"""
    else:
        solve_block = type_rules['solve_strategy']
    
    system_prompt = PROMPT_SYSTEM_TEMPLATE.format(
        subject=subject,
        solve_strategy_block=solve_block
    )
    
    # 精简卡片信息
    points = card['core_points'][:4]
    
    # 提取公式（扩大截取长度）
    formulas = []
    clean_points = []
    for p in points:
        if any(c in p for c in '=÷×+−≥≤<>°²³∠'):
            formulas.append(p[:80])
        else:
            clean_points.append(p[:80])
    
    # 提取易错点作为正误对比素材（扩大到200字，保留完整竖式布局）
    mistakes_info = ''
    if card.get('mistakes'):
        m = card['mistakes'][0]
        mistakes_info = f"\n常见错误(⚠️ 必须用于正误对比图示，确保数字正确):\n  ❌ 错误做法: {m['wrong'][:200]}\n  ✅ 正确做法: {m['correct'][:200]}"
    
    # 提取例题的完整信息（题目+解题步骤，给AI完整上下文）
    example_info = ''
    example_steps = ''
    if card.get('example'):
        ex = card['example']
        example_info = ex['question'][:120]
        # 传递完整的解题步骤，让AI理解正确的解法
        if ex.get('steps'):
            steps_text = '\n'.join(f'  {i+1}. {s}' for i, s in enumerate(ex['steps']))
            example_steps = f"\n【解题步骤】(图片中的解法必须与此一致！):\n{steps_text[:600]}"
        if ex.get('answer'):
            example_steps += f"\n【正确答案】: {ex['answer']}"
    
    card_info = f"""学科: {subject}
年级: {grade}{semester}
标题: {card['title']}
类型: {card_type}

【⚠️ 必须展示的例题】(这是整张卡片的核心！题目必须醒目显示在卡片上):
{example_info if example_info else '请根据知识点自行构造一道最典型的例题'}
{example_steps}

【知识点核心】: {card['definition'][:120]}
【关键词】(提炼≤3个，每个≤6字):
{chr(10).join('• ' + p for p in clean_points[:3])}
{('【公式/数字】(超大展示): ' + ' | '.join(formulas)) if formulas else ''}
【口诀】(≤10字): {card['memory_tip'][:50]}
{mistakes_info if mistakes_info else ''}
难度: {card['difficulty']}/5
{'⚠️ 特别提醒：这是笔算竖式类卡片，图片中必须画出正确的竖式，每个数字不能错！' if is_vertical_calc else ''}"""

    contents = [
        {'role': 'user', 'parts': [{'text': f'{system_prompt}\n\n--- 知识点信息 ---\n{card_info}'}]}
    ]
    
    # thinking budget 单独控制，不占用 maxOutputTokens
    gen_config = {
        'maxOutputTokens': 8192,
        'temperature': 0.85,
        'thinkingConfig': {'thinkingBudget': 2048}
    }
    resp = gemini_call(TEXT_MODEL, contents, api_key, gen_config=gen_config)
    if not resp:
        return None
    
    try:
        candidates = resp.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            # Debug: 列出所有 parts 的类型和长度
            for i, part in enumerate(parts):
                if 'thought' in part and part.get('thought'):
                    print(f'      [part {i}] thinking, {len(part.get("text",""))} chars')
                elif 'text' in part:
                    print(f'      [part {i}] text, {len(part["text"])} chars')
            
            # 取最长的非 thinking text part
            best_text = ''
            for part in parts:
                if 'text' in part and not part.get('thought', False):
                    txt = part['text'].strip()
                    if len(txt) > len(best_text):
                        best_text = txt
            if len(best_text) > 50:
                return best_text
            
            # fallback: 取最长的任意 text part
            for part in parts:
                if 'text' in part:
                    txt = part['text'].strip()
                    if len(txt) > len(best_text):
                        best_text = txt
            if len(best_text) > 50:
                return best_text
    except Exception as e:
        print(f'    [Parse error] {e}')
    return None

# ─── Prompt Library: 保存 prompt 到 card_prompt_lib ───
PROMPT_LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'card_prompt_lib', 'prompts')

def save_prompt_to_lib(card, prompt, subject, grade, semester, image_path=''):
    """将生成的 prompt 保存到 card_prompt_lib/prompts/ 目录"""
    try:
        # 目录: card_prompt_lib/prompts/数学_三下/
        # 简化: 三年级→三, 下册→下
        g = grade.replace('年级', '') if grade else ''
        s = semester.replace('册', '') if semester else ''
        subdir = f'{subject}_{g}{s}'
        lib_dir = os.path.join(PROMPT_LIB_DIR, subdir)
        os.makedirs(lib_dir, exist_ok=True)
        
        # 文件名: 02_06_商末尾有0的除法.md
        # 从full_id提取单元+卡片编号 (如 数学-三下-02-06 → 02_06)
        parts = card['full_id'].split('-')
        fid = '_'.join(parts[-2:]) if len(parts) >= 2 else card['full_id'].replace('-', '_')
        safe_title = card['title'].replace('/', '_').replace('\\', '_')[:20]
        md_file = os.path.join(lib_dir, f'{fid}_{safe_title}.md')
        
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        card_type = card.get('type', '未知')
        
        content = f"""# {card['full_id']} {card['title']}

> 题型: {card_type} | 难度: {card['difficulty']}/5 | 生成时间: {now}

## 知识点信息

- **定义**: {card['definition'][:100]}
- **核心要点**: {', '.join(card['core_points'][:3])}
- **口诀**: {card['memory_tip'][:50]}
"""
        if card.get('example'):
            content += f"- **例题**: {card['example']['question'][:120]}\n"
        if card.get('mistakes'):
            m = card['mistakes'][0]
            content += f"- **易错**: ❌{m['wrong'][:50]} → ✅{m['correct'][:50]}\n"
        
        content += f"""
## 生成的 Prompt (英文)

```
{prompt}
```

## 元数据

| 字段 | 值 |
|------|-----|
| card_id | {card['full_id']} |
| 题型 | {card_type} |
| prompt长度 | {len(prompt)} chars |
| 图片 | {image_path} |
| 模型 | Text: {TEXT_MODEL}, Image: {IMAGE_MODEL} |
| prompt版本 | v9 |
"""
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 更新 index.json
        index_file = os.path.join(lib_dir, '_index.json')
        index = {}
        if os.path.exists(index_file):
            with open(index_file, 'r', encoding='utf-8') as f:
                index = json.load(f)
        
        index[card['full_id']] = {
            'title': card['title'],
            'type': card_type,
            'prompt_file': os.path.basename(md_file),
            'prompt_length': len(prompt),
            'image': image_path,
            'generated_at': now,
            'prompt_version': 'v9'
        }
        
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f'    [prompt-lib save error] {e}')

# ─── Step 2: Generate image ───
def generate_card_image(prompt, api_key, card_title='', subject=''):
    """Step 2: 用原生图片生成模型生成卡片图片"""
    # 在提示词前追加强制指令：简体中文 + 内容主题
    chinese_prefix = (
        f"CRITICAL INSTRUCTIONS (MUST FOLLOW):\n"
        f"1. TOPIC: This is a {subject} educational knowledge card about \"{card_title}\".\n"
        f"2. TEXT RULES: ALL visible text MUST be Simplified Chinese (简体中文). "
        f"Use LARGE, BOLD, thick-stroke rounded/gothic sans-serif font. "
        f"Maximum 60 Chinese characters total in the entire image. "
        f"Each text block must be ≤10 characters. Make text as large as possible.\n"
        f"3. TEXT QUALITY: Render each Chinese character clearly with no distortion. "
        f"Use simple, common characters. Thick bold strokes. High contrast against background. "
        f"Do NOT use thin/serif/cursive fonts. Do NOT cram many characters in small space.\n"
        f"4. The main title should be \"{card_title}\" in extra-large bold font.\n\n"
    )
    full_prompt = chinese_prefix + prompt
    contents = [
        {'role': 'user', 'parts': [{'text': full_prompt}]}
    ]
    gen_config = {
        'responseModalities': ['TEXT', 'IMAGE']
    }
    
    resp = gemini_call(IMAGE_MODEL, contents, api_key, gen_config=gen_config)
    if not resp:
        return None
    
    try:
        candidates = resp.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            for part in parts:
                if 'inlineData' in part:
                    mime = part['inlineData'].get('mimeType', 'image/png')
                    b64data = part['inlineData'].get('data', '')
                    if b64data:
                        ext = 'png' if 'png' in mime else 'jpg'
                        return base64.b64decode(b64data), ext
    except Exception as e:
        print(f'    [Parse error] {e}')
    return None

# ─── Main ───
def main():
    test_mode = '--test' in sys.argv
    # --count N: 只生成前N张
    count_limit = 0
    for i, a in enumerate(sys.argv):
        if a == '--count' and i + 1 < len(sys.argv):
            count_limit = int(sys.argv[i + 1])
    args = [a for a in sys.argv[1:] if not a.startswith('--') and not a.isdigit()]
    
    # Find input JSON
    json_file = args[0] if args else None
    if not json_file:
        for f in sorted(os.listdir('.')):
            if f.startswith('knowledge_cards') and f.endswith('.json'):
                json_file = f
                break
    
    if not json_file or not os.path.exists(json_file):
        print('❌ 未找到知识卡片JSON文件')
        print('用法: python generate_card_images.py [cards.json] [output_dir]')
        sys.exit(1)
    
    output_dir = args[1] if len(args) > 1 else 'card_images'
    os.makedirs(output_dir, exist_ok=True)
    
    # Load data
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    keys = load_api_keys()
    if not keys:
        print('❌ 未找到API密钥 (api_key.txt)')
        sys.exit(1)
    
    subject = data['subject']
    grade = data['grade']
    semester = data['semester']
    total_cards = data.get('total_cards', sum(len(u['cards']) for u in data['units']))
    
    print(f'╔══════════════════════════════════════════╗')
    print(f'║  📚 知识卡片图片生成器 (两步法)          ║')
    print(f'╠══════════════════════════════════════════╣')
    print(f'║  学科: {subject}  年级: {grade}{semester}')
    print(f'║  教材: {data.get("textbook","N/A")}')
    print(f'║  卡片: {total_cards} 张  输出: {output_dir}/')
    print(f'║  文字模型: {TEXT_MODEL}')
    print(f'║  图片模型: {IMAGE_MODEL}')
    if test_mode:
        print(f'║  ⚡ 测试模式: 只生成第1张')
    elif count_limit:
        print(f'║  🔢 限量模式: 只生成前{count_limit}张')
    print(f'╚══════════════════════════════════════════╝')
    print()
    
    total = 0
    success = 0
    prompts_log = []
    
    for unit in data['units']:
        print(f'📖 单元 {unit["unit_id"]}: {unit["unit_name"]}')
        
        for card in unit['cards']:
            total += 1
            print(f'  ┌─ [{total}/{total_cards}] {card["full_id"]} {card["title"]}')
            
            # Check if image already exists
            out_name = card['full_id'].replace('-', '_')
            existing = [f for f in os.listdir(output_dir) if f.startswith(out_name)]
            if existing:
                print(f'  └─ ⏭️  已存在 {existing[0]}, 跳过')
                success += 1
                continue
            
            # ── Step 0: 审校闸门 ──
            review_payload = None
            review_result_data = None
            if _HAS_REVIEW:
                print(f'  ├─ Step 0: 审校检查...', end='', flush=True)
                review_key = next_key(keys)
                gate = run_review_gate(card, subject, gemini_call, review_key, TEXT_MODEL)
                if not gate['pass']:
                    print(f' ❌ 未通过 [{gate["stage"]}]')
                    for iss in gate['issues']:
                        print(f'  │   ⚠️  {iss}')
                    print(f'  └─ 🚫 跳过此卡片 (审校不通过)')
                    # 记录到 self_optimizer (如果可用)
                    try:
                        from self_optimizer import record_generation
                        record_generation(
                            card_id=card['full_id'], subject=subject, grade=grade,
                            audit_score=gate.get('review_result', {}).get('teaching_score', 0) if gate.get('review_result') else 0,
                            quality_score=gate.get('review_result', {}).get('language_score', 0) if gate.get('review_result') else 0,
                            final_action=f'rejected_{gate["stage"]}',
                            success=False,
                        )
                    except Exception:
                        pass
                    continue
                review_payload = gate.get('payload')
                review_result_data = gate.get('review_result')
                print(' ✅ 通过')
            
            # Step 1: Generate prompt
            print(f'  ├─ Step 1: 生成提示词...', end='', flush=True)
            key = next_key(keys)
            prompt = generate_image_prompt(card, subject, grade, semester, key, payload=review_payload)
            if not prompt:
                print(' ❌ 失败')
                print(f'  └─ ❌ 跳过此卡片')
                continue
            print(f' ✅ ({len(prompt)} chars)')
            
            prompts_log.append({
                'card_id': card['full_id'],
                'title': card['title'],
                'prompt': prompt
            })
            
            time.sleep(1)
            
            # Step 2: Generate image
            print(f'  ├─ Step 2: 生成图片...', end='', flush=True)
            key = next_key(keys)
            result = generate_card_image(prompt, key, card_title=card['title'], subject=subject)
            if not result:
                print(' ❌ 失败')
                print(f'  └─ ❌ 图片生成失败')
                # Save prompt for retry
                continue
            
            img_data, ext = result
            filename = f'{out_name}.{ext}'
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'wb') as f:
                f.write(img_data)
            
            size_kb = len(img_data) / 1024
            print(f' ✅ {filename} ({size_kb:.0f}KB)')
            print(f'  └─ ✅ 保存成功')
            success += 1
            
            # Save prompt to library
            save_prompt_to_lib(card, prompt, subject, grade, semester, image_path=filepath)
            
            # 记录到 self_optimizer
            try:
                from self_optimizer import record_generation
                record_generation(
                    card_id=card['full_id'], subject=subject, grade=grade,
                    audit_score=review_result_data.get('teaching_score', 0) if review_result_data else 0,
                    quality_score=review_result_data.get('language_score', 0) if review_result_data else 0,
                    final_action='pass',
                    prompt_length=len(prompt),
                    image_size_kb=size_kb,
                    success=True,
                )
            except Exception:
                pass
            
            # Save prompts incrementally
            prompts_file = os.path.join(output_dir, '_prompts.json')
            with open(prompts_file, 'w', encoding='utf-8') as f:
                json.dump(prompts_log, f, ensure_ascii=False, indent=2)
            
            if test_mode:
                print(f'\n⚡ 测试模式完成, 查看 {filepath}')
                break
            if count_limit and success >= count_limit:
                print(f'\n🔢 已生成{count_limit}张, 停止')
                break
            
            time.sleep(2)  # Rate limiting between cards
        
        if test_mode and success > 0:
            break
        if count_limit and success >= count_limit:
            break
        print()
    
    # Final prompts save
    prompts_file = os.path.join(output_dir, '_prompts.json')
    with open(prompts_file, 'w', encoding='utf-8') as f:
        json.dump(prompts_log, f, ensure_ascii=False, indent=2)
    
    print(f'╔══════════════════════════════════════════╗')
    print(f'║  🎉 生成完成!                             ║')
    print(f'║  成功: {success}/{total} 张卡片图片')
    print(f'║  图片目录: {output_dir}/')
    print(f'║  提示词日志: {output_dir}/_prompts.json')
    print(f'╚══════════════════════════════════════════╝')

if __name__ == '__main__':
    main()
