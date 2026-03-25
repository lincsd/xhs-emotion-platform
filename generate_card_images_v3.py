#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识卡片图片生成器 v3 — 终极流水线
=============================================
5 步流水线，兼得 AI 艺术感 + 文字 100% 准确：

  Step 1: Gemini 2.5 Flash 生成优化英文提示词
  Step 2: Gemini 3 Pro Image 生成卡片图片（强模型）
  Step 3: Gemini 2.5 Flash Vision OCR 审计
  Step 4: 对比期望文字 vs OCR → 不通过则重生成（最多3轮）
  Step 5: PIL 精确叠加修补残留文字错误 + 质量评分

用法:
  python generate_card_images_v3.py                          # 默认: 找 knowledge_cards/小学/*.json
  python generate_card_images_v3.py cards.json               # 指定JSON
  python generate_card_images_v3.py --test                   # 只测试1张
  python generate_card_images_v3.py --count 3                # 只生成3张
  python generate_card_images_v3.py --no-audit               # 跳过OCR审计（快速模式）
  python generate_card_images_v3.py --force                  # 强制重新生成已有图片
"""

import json, os, sys, time, base64, datetime, re, io, textwrap
import urllib.request, urllib.error

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════
GEMINI_API_BASE = 'https://generativelanguage.googleapis.com/v1beta'

TEXT_MODEL      = 'gemini-2.5-flash'            # 提示词生成 + OCR审计
IMAGE_MODELS    = [                              # 图片生成（按优先级尝试）
    'gemini-3.1-flash-image-preview',            # Nano Banana 2: 高精度多语言文字，最均衡
    'gemini-3-pro-image-preview',                 # Nano Banana Pro: 电影级画质，深度推理
    'nano-banana-pro-preview',                    # 兜底: 已验证可用
]

MAX_AUDIT_ROUNDS = 3    # OCR审计最大重试轮数
AUDIT_PASS_SCORE = 70   # OCR审计通过分数 (0-100)

# ═══════════════════════════════════════════
# API 基础设施
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

def gemini_call(model, contents, api_key, gen_config=None, retries=2, all_keys=None):
    """通用 Gemini API 调用。
    
    支持多 key 轮换：当遇到 429/503 时自动切换 API key 重试。
    all_keys: 所有可用的 API key 列表，为 None 时只用 api_key。
    总尝试次数 = len(all_keys) * retries（每个key各试retries次）
    """
    key_list = all_keys if all_keys else [api_key]
    body = {'contents': contents}
    if gen_config:
        body['generationConfig'] = gen_config
    data = json.dumps(body).encode('utf-8')

    total_attempts = len(key_list) * retries
    attempt_num = 0

    for ki, current_key in enumerate(key_list):
        url = f'{GEMINI_API_BASE}/models/{model}:generateContent?key={current_key}'
        key_label = f'key{ki+1}/{len(key_list)}'
        for retry in range(retries):
            attempt_num += 1
            try:
                req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    return json.loads(resp.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8', errors='replace')
                print(f'\n      [HTTP {e.code}] {key_label} attempt {attempt_num}/{total_attempts}: {err_body[:200]}')
                if e.code == 404:
                    print(f'      ❌ 模型 {model} 不存在')
                    return None
                if e.code in (429, 503):
                    # 429/503: 换下一个 key（跳出内层循环）
                    if ki < len(key_list) - 1:
                        print(f'      🔄 切换到下一个 API key...')
                        time.sleep(3)
                        break  # 跳到下一个key
                    else:
                        # 已经是最后一个key，短暂等待后重试
                        wait = 5 * (retry + 1)
                        print(f'      ⏳ 所有key均受限, 等待{wait}秒...')
                        time.sleep(wait)
                elif attempt_num < total_attempts:
                    time.sleep(5 * (retry + 1))
            except Exception as e:
                print(f'\n      [Error] {key_label} attempt {attempt_num}/{total_attempts}: {e}')
                if attempt_num < total_attempts:
                    time.sleep(5 * (retry + 1))
        else:
            # 内层for正常结束（没break），说明retries用完，继续下一个key
            continue
        # 内层break到这里，继续外层下一个key
        continue
    return None


# ═══════════════════════════════════════════
# 卡片类型视觉策略
# ═══════════════════════════════════════════
CARD_TYPE_VISUAL_RULES = {
    '方法卡': """运算方法类（笔算/竖式/列式）：画彩色分层竖式，色块对齐，正误对比
   其他方法类（口算/估算/简便）：色块拆分步骤，不画竖式
   几何方法类：画图形+标注+辅助线，公式代入""",
    '概念卡': "用生活实物图解释抽象概念；概念名超大，定义浓缩≤6字金句",
    '辨析卡': "左右并排对比：左❌红色错误 vs 右✅绿色正确，红圈标差异",
    '公式卡': "格子图推导→公式超大展示→代入验证小例子",
    '陷阱卡': "先设坑→展示错误答案画叉→揭示正确答案，标'90%同学做错'",
    '速算卡': "左🐢慢方法(灰色划掉) vs 右⚡速算技巧(彩色高亮)",
    '挑战卡': "关卡编号金色+大题目+倒计时元素+答案刮刮卡样式",
    '生活卡': "生活场景插画(40%)+气泡标注计算+实用结论大字",
    '对战卡': "左蓝(家长) VS 右粉(孩子)同类不同难度+计分栏",
    '思维卡': "情境问题→色块分步可视化(45%)→方法名+答案醒目",
}

def _detect_vertical_calc(card):
    keywords = ['笔算', '竖式', '列式', '列竖式']
    text = card.get('title', '') + card.get('definition', '') + card.get('example', {}).get('question', '')
    return any(k in text for k in keywords)


# ═══════════════════════════════════════════
# Step 1: 生成图片提示词（Gemini Flash）
# ═══════════════════════════════════════════
PROMPT_SYSTEM_TEMPLATE = """你是小红书爆款知识卡片 AI 图片 Prompt 工程师。

你的任务：为一张{subject}知识卡片写一段**英文** AI 图片生成提示词。

══════ 核心教学思路 ══════

每张卡片 = 一道具体例题的"一图秒懂"讲解。

设计三步：
1. 选一道最典型的例题，大号醒目展示
2. 用最简视觉方式画出解题关键步骤
{solve_strategy_block}
3. 大字答案 + 口诀(≤10字)

══════ 视觉设计 ══════

- 竖屏 3:4 画布
- 核心教学图占 ≥ 45%
- 全卡最多4个区块：标题/核心图/金句对比/口诀
- ≥ 25% 留白
- 一个可爱小老师卡通 + ≤6字气泡
- 小红书风格：鲜明渐变背景，饱和色banner，白色圆角内容卡片

══════ ⚠️ 中文文字极简原则 ══════

这是最重要的规则！AI 图片模型渲染中文容易出错，必须极度精简：

- 全卡中文 **≤ 20字**（越少越好！）
- 标题 ≤ 4字（72pt 超大粗体）
- 核心金句 ≤ 6字
- 口诀 ≤ 8字
- 气泡 ≤ 4字
- ❌ 绝不超过6个连续中文字符
- ❌ 不写段落、定义、解释
- 数字和数学符号用阿拉伯数字/符号(不用中文写数字)
- 能用图/箭头/色块表达的，不用文字

══════ 你必须列出的文字清单 ══════

在 prompt 末尾，用 [TEXT_MANIFEST] 标签列出图片中出现的所有中文文字：
[TEXT_MANIFEST]
TITLE: 标题文字
LINE1: 第一处文字
LINE2: 第二处文字
...
[/TEXT_MANIFEST]

这个清单将用于后续OCR审计对照，务必精确！

══════ 配色 ══════

鲜明渐变背景(珊瑚粉/薄荷蓝/蜜桃橙/薰衣草紫选一)
标题banner饱和色，内容区白色圆角卡片
重点数字用鲜明对比色超大加粗
✓翠绿 #2ED573, ✗亮红 #FF4757

══════ 输出格式 ══════

只输出英文提示词 + TEXT_MANIFEST，不要其他内容。

提示词开头必须写:
"IMPORTANT: All visible text MUST be Simplified Chinese (简体中文). LARGE BOLD thick-stroke rounded sans-serif. Max 20 Chinese chars total, each block ≤6 chars. No English text in the image. Clean spacious layout, ≥25% whitespace."

提示词长度: 350-500 英文单词。"""

# ─── 养生减脂类专用模板 ───
_WELLNESS_SUBJECTS = {'养生', '减脂', '养生减脂'}

PROMPT_SYSTEM_TEMPLATE_WELLNESS = """你是小红书爆款知识卡片 AI 图片 Prompt 工程师。

你的任务：为一张{subject}知识卡片写一段**英文** AI 图片生成提示词。

══════ 核心思路 ══════

每张卡片 = 一个养生/减脂知识的"一图秒懂"呈现。

设计三步：
1. 用最吸引眼球的视觉对比/清单/图解展示核心知识
{visual_strategy_block}
2. 关键数据/步骤用图标+色块清晰呈现
3. 大字金句 + 行动口诀(≤10字)

══════ 视觉设计 ══════

- 竖屏 3:4 画布
- 核心知识图占 ≥ 45%
- 全卡最多4个区块：标题/核心图/知识要点/口诀
- ≥ 25% 留白
- 一个可爱养生博主卡通形象 + ≤6字气泡
- 小红书风格：鲜明渐变背景，饱和色banner，白色圆角内容卡片
- 养生减脂主题：抹茶绿/樱花粉/暖杏色为主

══════ ⚠️ 中文文字极简原则 ══════

这是最重要的规则！AI 图片模型渲染中文容易出错，必须极度精简：

- 全卡中文 **≤ 20字**（越少越好！）
- 标题 ≤ 4字（72pt 超大粗体）
- 核心金句 ≤ 6字
- 口诀 ≤ 8字
- 气泡 ≤ 4字
- ❌ 绝不超过6个连续中文字符
- ❌ 不写段落、定义、解释
- 数字和数据用阿拉伯数字/符号
- 能用图/箭头/色块/图标表达的，不用文字

══════ 你必须列出的文字清单 ══════

在 prompt 末尾，用 [TEXT_MANIFEST] 标签列出图片中出现的所有中文文字：
[TEXT_MANIFEST]
TITLE: 标题文字
LINE1: 第一处文字
LINE2: 第二处文字
...
[/TEXT_MANIFEST]

这个清单将用于后续OCR审计对照，务必精确！

══════ 配色 ══════

鲜明渐变背景(抹茶绿/樱花粉/暖杏色/薰衣草紫选一)
标题banner饱和色，内容区白色圆角卡片
重点数据用鲜明对比色超大加粗
✓翠绿 #2ED573, ✗亮红 #FF4757

══════ 输出格式 ══════

只输出英文提示词 + TEXT_MANIFEST，不要其他内容。

提示词开头必须写:
"IMPORTANT: All visible text MUST be Simplified Chinese (简体中文). LARGE BOLD thick-stroke rounded sans-serif. Max 20 Chinese chars total, each block ≤6 chars. No English text in the image. Clean spacious layout, ≥25% whitespace."

提示词长度: 350-500 英文单词。"""


def _build_card_info(card, subject, grade, semester):
    """构建传给 prompt 生成器的卡片信息（自动区分教育/养生类）"""
    if subject in _WELLNESS_SUBJECTS:
        return _build_card_info_wellness(card, subject, grade, semester)
    return _build_card_info_edu(card, subject, grade, semester)


def _build_card_info_wellness(card, subject, grade, semester):
    """构建养生减脂类卡片信息"""
    card_type = card.get('type', '干货卡')

    example_info = ''
    example_steps = ''
    if card.get('example'):
        ex = card['example']
        example_info = (ex.get('question') or '')[:120]
        if ex.get('steps'):
            steps_text = '\n'.join(f'  {i+1}. {s}' for i, s in enumerate(ex['steps'][:5]))
            example_steps = f"\n【步骤】:\n{steps_text[:500]}"
        if ex.get('answer'):
            example_steps += f"\n【结论】: {str(ex['answer'])[:150]}"

    points = card.get('core_points', [])[:4]
    clean_pts = [str(p)[:80] for p in points]

    mistakes_info = ''
    if card.get('mistakes'):
        m = card['mistakes'][0]
        mistakes_info = f"\n常见误区: ❌{m.get('wrong', '')[:100]} → ✅{m.get('correct', '')[:100]}"

    hook = ''
    if card.get('emotion_hook'):
        hook = f"\n情绪钩子: {card['emotion_hook'][:100]}"

    return f"""主题: {subject} | 分类: {grade} {semester}
标题: {card.get('title', '')} | 类型: {card_type}

【案例】: {example_info or '根据知识点展示最典型场景'}
{example_steps}

【定义】: {card.get('definition', '')[:120]}
【要点】: {chr(10).join('• ' + p for p in clean_pts[:3])}
【口诀】: {card.get('memory_tip', '')[:60]}
{mistakes_info}
{hook}
难度: {card.get('difficulty', 2)}/5"""


def _build_card_info_edu(card, subject, grade, semester):
    """构建教育类卡片信息"""
    card_type = card.get('type', '方法卡')

    example_info = ''
    example_steps = ''
    if card.get('example'):
        ex = card['example']
        if isinstance(ex, str):
            example_info = ex[:120]
        else:
            example_info = (ex.get('question') or '')[:120]
            if ex.get('steps'):
                steps_text = '\n'.join(f'  {i+1}. {s}' for i, s in enumerate(ex['steps']))
                example_steps = f"\n【解题步骤】:\n{steps_text[:500]}"
            if ex.get('answer'):
                example_steps += f"\n【正确答案】: {ex['answer']}"

    points = card.get('core_points', [])[:4]
    formulas = [p[:80] for p in points if any(c in p for c in '=÷×+−≥≤<>°²³∠')]
    clean_pts = [p[:80] for p in points if not any(c in p for c in '=÷×+−≥≤<>°²³∠')]

    mistakes_info = ''
    if card.get('mistakes'):
        m = card['mistakes'][0]
        mistakes_info = f"\n常见错误: ❌{m.get('wrong', '')[:150]} → ✅{m.get('correct', '')[:150]}"

    is_vert = _detect_vertical_calc(card)

    return f"""学科: {subject} | 年级: {grade}{semester}
标题: {card.get('title', '')} | 类型: {card_type}

【例题】: {example_info or '根据知识点构造一道最典型例题'}
{example_steps}

【定义】: {card.get('definition', '')[:120]}
【要点】: {chr(10).join('• ' + p for p in clean_pts[:3])}
{('【公式】: ' + ' | '.join(formulas)) if formulas else ''}
【口诀】(≤8字): {card.get('memory_tip', '')[:40]}
{mistakes_info}
难度: {card.get('difficulty', 3)}/5
{'⚠️ 笔算竖式类：必须画正确竖式' if is_vert else ''}"""


def generate_image_prompt(card, subject, grade, semester, api_key, all_keys=None):
    """Step 1: 生成英文图片提示词 + TEXT_MANIFEST"""
    card_type = card.get('type', '方法卡')
    type_rules = CARD_TYPE_VISUAL_RULES.get(card_type, CARD_TYPE_VISUAL_RULES['方法卡'])
    is_vert = _detect_vertical_calc(card)

    # 根据学科选择对应模板
    if subject in _WELLNESS_SUBJECTS:
        visual_block = f"   {type_rules}"
        system_prompt = PROMPT_SYSTEM_TEMPLATE_WELLNESS.format(
            subject=subject,
            visual_strategy_block=visual_block
        )
    elif is_vert:
        solve_block = """   ⚠️ 笔算竖式类：必须画彩色分层竖式！
   - 竖式用颜色分层(绿/橙/红)，旁边放正误对比
   - 数字必须和例题完全一致"""
        system_prompt = PROMPT_SYSTEM_TEMPLATE.format(
            subject=subject,
            solve_strategy_block=solve_block
        )
    else:
        solve_block = f"   {type_rules}"
        system_prompt = PROMPT_SYSTEM_TEMPLATE.format(
            subject=subject,
            solve_strategy_block=solve_block
        )

    card_info = _build_card_info(card, subject, grade, semester)

    contents = [
        {'role': 'user', 'parts': [{'text': f'{system_prompt}\n\n--- 知识点信息 ---\n{card_info}'}]}
    ]
    gen_config = {
        'maxOutputTokens': 8192,
        'temperature': 0.8,
        'thinkingConfig': {'thinkingBudget': 2048}
    }

    resp = gemini_call(TEXT_MODEL, contents, api_key, gen_config=gen_config, all_keys=all_keys)
    if not resp:
        return None, None

    try:
        candidates = resp.get('candidates', [])
        if not candidates:
            return None, None
        parts = candidates[0].get('content', {}).get('parts', [])
        best_text = ''
        for part in parts:
            if 'text' in part and not part.get('thought', False):
                txt = part['text'].strip()
                if len(txt) > len(best_text):
                    best_text = txt
        if not best_text:
            for part in parts:
                if 'text' in part:
                    txt = part['text'].strip()
                    if len(txt) > len(best_text):
                        best_text = txt

        if len(best_text) < 50:
            return None, None

        # 解析 TEXT_MANIFEST
        manifest = _parse_text_manifest(best_text)
        # 清理 prompt（移除 manifest 标签）
        prompt_clean = re.sub(r'\[TEXT_MANIFEST\].*?\[/TEXT_MANIFEST\]', '', best_text, flags=re.DOTALL).strip()

        return prompt_clean, manifest

    except Exception as e:
        print(f'      [Parse error] {e}')
    return None, None


def _parse_text_manifest(text):
    """从 prompt 输出中解析 TEXT_MANIFEST"""
    manifest = {}
    m = re.search(r'\[TEXT_MANIFEST\](.*?)\[/TEXT_MANIFEST\]', text, re.DOTALL)
    if m:
        for line in m.group(1).strip().split('\n'):
            line = line.strip()
            if ':' in line:
                key, val = line.split(':', 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if val:
                    manifest[key] = val
    return manifest


# ═══════════════════════════════════════════
# Step 2: 生成卡片图片（强模型 + fallback）
# ═══════════════════════════════════════════
def generate_card_image(prompt, keys, card_title='', subject='', audit_hint=''):
    """Step 2: 用最强图片模型生成卡片图片。
    
    多模型 × 多key 全组合尝试，最大化成功率。
    keys: API key 列表（全部），内部按 模型→全部key 的顺序尝试。
    """
    chinese_prefix = (
        f"CRITICAL INSTRUCTIONS (MUST FOLLOW):\n"
        f"1. This is a {subject} educational knowledge card about \"{card_title}\".\n"
        f"2. ALL visible text MUST be Simplified Chinese (简体中文). "
        f"Use LARGE, BOLD, thick-stroke rounded/gothic sans-serif font.\n"
        f"3. Maximum 20 Chinese characters total. Each text block ≤ 6 characters.\n"
        f"4. Render each Chinese character CLEARLY and CORRECTLY. "
        f"Thick bold strokes. High contrast. No thin/serif/cursive fonts.\n"
        f"5. The main title should be \"{card_title}\" in extra-large bold font.\n"
    )
    if audit_hint:
        chinese_prefix += f"\n⚠️ CORRECTION FROM PREVIOUS ATTEMPT:\n{audit_hint}\n"

    full_prompt = chinese_prefix + "\n" + prompt
    contents = [
        {'role': 'user', 'parts': [{'text': full_prompt}]}
    ]
    gen_config = {
        'responseModalities': ['TEXT', 'IMAGE']
    }

    # 按模型优先级尝试（遇到成功立即返回，失败换下一个模型）
    # retries=1 减少单模型重试次数，加速失败切换
    for model in IMAGE_MODELS:
        resp = gemini_call(model, contents, keys[0], gen_config=gen_config, retries=1, all_keys=keys)
        if not resp:
            continue
        try:
            candidates = resp.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                for part in parts:
                    if 'inlineData' in part:
                        b64data = part['inlineData'].get('data', '')
                        mime = part['inlineData'].get('mimeType', 'image/png')
                        if b64data:
                            ext = 'png' if 'png' in mime else 'jpg'
                            print(f' ✅ (model={model})', end='')
                            return base64.b64decode(b64data), ext, model
        except Exception as e:
            print(f'      [Parse error with {model}] {e}')
            continue

    return None, None, None


# ═══════════════════════════════════════════
# Step 3: Vision OCR 审计
# ═══════════════════════════════════════════
OCR_AUDIT_PROMPT = """你是一个严格的中文文字审计员。

我给你一张知识卡片图片。请仔细检查图片中所有可见的中文文字。

任务：
1. 列出图片中所有可见的中文文字（逐条列出）
2. 检查是否有乱码、错字、缺笔画、变形
3. 将图片中的文字与期望文字对照，标记差异

期望的文字清单：
{expected_texts}

请用以下严格 JSON 格式回复（不要加 markdown 代码块标记）：
{{
  "found_texts": ["图中实际读到的每一处中文文字"],
  "errors": [
    {{"expected": "期望文字", "actual": "实际看到的", "type": "garbled|wrong_char|missing|distorted", "severity": "high|medium|low"}}
  ],
  "overall_score": 85,
  "summary": "一句话总结"
}}

评分标准(0-100)：
- 100: 所有中文完美无误
- 80+: 有轻微瑕疵但可读
- 60-79: 有明显错字但整体可理解
- <60: 严重乱码，需要重新生成

只输出JSON，不要其他文字。"""


def ocr_audit(image_data, expected_manifest, api_key, all_keys=None):
    """Step 3: 用 Vision 模型审计图片中的中文文字"""
    if not expected_manifest:
        return {'overall_score': 100, 'errors': [], 'found_texts': [], 'summary': '无期望文字，跳过审计'}

    expected_lines = '\n'.join(f'- {k}: "{v}"' for k, v in expected_manifest.items())
    prompt_text = OCR_AUDIT_PROMPT.format(expected_texts=expected_lines)

    b64_img = base64.b64encode(image_data).decode('utf-8')
    contents = [
        {'role': 'user', 'parts': [
            {'text': prompt_text},
            {'inlineData': {'mimeType': 'image/png', 'data': b64_img}}
        ]}
    ]
    gen_config = {
        'maxOutputTokens': 4096,
        'temperature': 0.1,
    }

    resp = gemini_call(TEXT_MODEL, contents, api_key, gen_config=gen_config, all_keys=all_keys)
    if not resp:
        return {'overall_score': 0, 'errors': [], 'found_texts': [], 'summary': 'OCR调用失败'}

    try:
        candidates = resp.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            for part in parts:
                if 'text' in part and not part.get('thought', False):
                    text = part['text'].strip()
                    # 提取 JSON（兼容 markdown 代码块和纯 JSON）
                    json_match = re.search(r'\{[\s\S]*\}', text)
                    if json_match:
                        return json.loads(json_match.group())
    except (json.JSONDecodeError, Exception) as e:
        print(f'      [OCR parse error] {e}')

    return {'overall_score': 50, 'errors': [], 'found_texts': [], 'summary': 'OCR解析失败'}


def _build_audit_hint(audit_result, expected_manifest):
    """根据审计结果构建纠错提示"""
    if not audit_result.get('errors'):
        return ''

    hints = []
    for err in audit_result['errors'][:5]:  # 最多5个错误
        exp = err.get('expected', '?')
        act = err.get('actual', '?')
        etype = err.get('type', 'unknown')
        if etype == 'garbled':
            hints.append(f'The text "{exp}" appeared as garbled/unreadable "{act}". Please render "{exp}" clearly with thick bold strokes.')
        elif etype == 'wrong_char':
            hints.append(f'"{act}" should be "{exp}". Please fix this character.')
        elif etype == 'missing':
            hints.append(f'The text "{exp}" is missing from the image. Please add it.')
        elif etype == 'distorted':
            hints.append(f'The text "{exp}" is distorted. Please render it more clearly.')
        else:
            hints.append(f'Fix: "{act}" → "{exp}"')

    return '\n'.join(hints)


# ═══════════════════════════════════════════
# Step 5: PIL 文字修补兜底
# ═══════════════════════════════════════════
def _try_pil_text_repair(image_data, audit_result, expected_manifest):
    """
    审计仍有错误时，用 PIL 在图片底部叠加一条精确文字条。
    这是最终兜底——确保关键文字正确可读。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print('      [PIL not available for text repair]')
        return image_data

    # 只修补 high severity 的错误
    high_errors = [e for e in audit_result.get('errors', []) if e.get('severity') == 'high']
    if not high_errors:
        return image_data

    # 收集需要修补的文字
    repair_texts = []
    for err in high_errors[:3]:
        exp = err.get('expected', '')
        if exp and exp in [v for v in expected_manifest.values()]:
            repair_texts.append(exp)

    if not repair_texts:
        return image_data

    # 打开图片
    img = Image.open(io.BytesIO(image_data))
    w, h = img.size
    draw = ImageDraw.Draw(img)

    # 尝试加载中文字体
    font = None
    font_size = max(28, w // 20)
    font_paths = [
        'C:/Windows/Fonts/msyh.ttc',       # 微软雅黑
        'C:/Windows/Fonts/simhei.ttf',      # 黑体
        'C:/Windows/Fonts/simsun.ttc',      # 宋体
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc',
        '/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc',
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except Exception:
                continue
    if not font:
        font = ImageFont.load_default()

    # 在底部绘制修补文字条
    repair_line = ' | '.join(repair_texts)
    bbox = draw.textbbox((0, 0), repair_line, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    bar_h = text_h + 20
    bar_y = h - bar_h

    # 半透明白底
    overlay = Image.new('RGBA', (w, bar_h), (255, 255, 255, 220))
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    img.paste(overlay, (0, bar_y), overlay)

    draw = ImageDraw.Draw(img)
    text_x = (w - text_w) // 2
    text_y = bar_y + 10
    draw.text((text_x, text_y), repair_line, fill=(50, 50, 50, 255), font=font)

    # 保存
    buf = io.BytesIO()
    img.convert('RGB').save(buf, format='JPEG', quality=92)
    print(f'      🔧 PIL修补: 叠加了 "{repair_line}"')
    return buf.getvalue()


# ═══════════════════════════════════════════
# 质量评分
# ═══════════════════════════════════════════
QUALITY_PROMPT = """你是知识卡片质量评审员。请从5个维度评分(每项0-20分，满分100)：

1. **教学清晰度**(20分): 例题清晰? 解题步骤直观? 一眼就懂?
2. **文字准确性**(20分): 中文无乱码无错字? 数字公式正确?
3. **视觉美感**(20分): 配色好看? 像小红书爆款? 有吸引力?
4. **布局合理性**(20分): 信息层次清晰? 留白充足? 不拥挤?
5. **可收藏感**(20分): 看到就想截图保存? 有"干货感"?

只输出JSON格式（不要代码块标记）：
{{"teaching": 16, "text_accuracy": 18, "visual": 17, "layout": 15, "saveable": 16, "total": 82, "comment": "一句话点评"}}"""


def quality_score(image_data, api_key, card_title='', all_keys=None):
    """对生成的图片进行质量评分"""
    b64_img = base64.b64encode(image_data).decode('utf-8')
    contents = [
        {'role': 'user', 'parts': [
            {'text': f'这张卡片的主题是"{card_title}"。\n\n{QUALITY_PROMPT}'},
            {'inlineData': {'mimeType': 'image/png', 'data': b64_img}}
        ]}
    ]
    # 禁用 thinking mode 避免解析干扰
    gen_config = {
        'maxOutputTokens': 1024,
        'temperature': 0.1,
        'thinkingConfig': {'thinkingBudget': 0}
    }

    resp = gemini_call(TEXT_MODEL, contents, api_key, gen_config=gen_config, all_keys=all_keys)
    if not resp:
        return {'total': 0, 'comment': '评分调用失败'}

    try:
        candidates = resp.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            # 收集所有文字 parts
            all_text = ''
            for part in parts:
                if 'text' in part:
                    all_text += part['text']
            if all_text:
                json_match = re.search(r'\{[\s\S]*?\}', all_text.strip())
                if json_match:
                    result = json.loads(json_match.group())
                    # 确保有 total 字段
                    if 'total' not in result:
                        scores = [result.get(k, 0) for k in ('teaching', 'text_accuracy', 'visual', 'layout', 'saveable')]
                        result['total'] = sum(scores)
                    return result
    except Exception as e:
        print(f'      [Quality parse error] {e}')
    return {'total': 0, 'comment': '评分解析失败'}


# ═══════════════════════════════════════════
# 完整流水线: 单卡片处理
# ═══════════════════════════════════════════
def process_single_card(card, subject, grade, semester, keys, output_dir, skip_audit=False):
    """
    处理单张卡片的完整流水线。
    返回: (success: bool, filepath: str, stats: dict)
    """
    card_id = card['full_id']
    title = card['title']
    stats = {
        'card_id': card_id,
        'title': title,
        'prompt_gen_time': 0,
        'image_gen_time': 0,
        'audit_rounds': 0,
        'audit_score': 0,
        'quality_score': 0,
        'image_model': '',
        'final_action': '',  # 'pass' / 'repaired' / 'best_effort'
    }

    # ── Step 1: 生成提示词 ──
    print(f'  ├─ Step 1: 生成提示词...', end='', flush=True)
    t0 = time.time()
    key = next_key(keys)
    prompt, manifest = generate_image_prompt(card, subject, grade, semester, key, all_keys=keys)
    stats['prompt_gen_time'] = time.time() - t0

    if not prompt:
        print(' ❌ 失败')
        return False, '', stats
    
    manifest_count = len(manifest) if manifest else 0
    total_chars = sum(len(v) for v in manifest.values()) if manifest else 0
    print(f' ✅ ({len(prompt)}字, {manifest_count}处文字共{total_chars}字)')

    time.sleep(1)

    # ── Step 2-4: 生成图片 + OCR审计循环 ──
    best_image = None
    best_ext = 'png'
    best_score = 0
    audit_hint = ''

    for round_num in range(1, MAX_AUDIT_ROUNDS + 1):
        stats['audit_rounds'] = round_num

        # Step 2: 生成图片
        round_label = f'(round {round_num}/{MAX_AUDIT_ROUNDS})' if round_num > 1 else ''
        print(f'  ├─ Step 2: 生成图片{round_label}...', end='', flush=True)
        t1 = time.time()
        img_data, ext, model = generate_card_image(
            prompt, keys, card_title=title, subject=subject, audit_hint=audit_hint
        )
        stats['image_gen_time'] += time.time() - t1
        stats['image_model'] = model or ''

        if not img_data:
            print(' ❌ 图片生成失败')
            if best_image:
                break  # 用之前最好的
            return False, '', stats

        size_kb = len(img_data) / 1024
        print(f' ({size_kb:.0f}KB)')

        if skip_audit:
            best_image = img_data
            best_ext = ext
            best_score = 100
            stats['audit_score'] = 100
            stats['final_action'] = 'no_audit'
            break

        # Step 3: OCR 审计
        print(f'  ├─ Step 3: OCR审计...', end='', flush=True)
        key = next_key(keys)
        audit = ocr_audit(img_data, manifest, key, all_keys=keys)
        score = audit.get('overall_score', 0)
        errors = audit.get('errors', [])
        summary = audit.get('summary', '')
        print(f' 得分={score}/100 ({summary})')

        if score > best_score:
            best_image = img_data
            best_ext = ext
            best_score = score

        stats['audit_score'] = best_score

        if score >= AUDIT_PASS_SCORE:
            print(f'  ├─ ✅ OCR审计通过! (score={score})')
            stats['final_action'] = 'pass'
            break
        else:
            # 构建纠错提示
            high_errs = [e for e in errors if e.get('severity') in ('high', 'medium')]
            print(f'  ├─ ⚠️  {len(high_errs)}处文字错误, ', end='')
            if round_num < MAX_AUDIT_ROUNDS:
                audit_hint = _build_audit_hint(audit, manifest)
                print(f'重新生成...')
                time.sleep(2)
            else:
                print(f'已达最大轮数')

    if not best_image:
        return False, '', stats

    # ── Step 5: PIL 修补兜底 ──
    if best_score < AUDIT_PASS_SCORE and manifest and not skip_audit:
        print(f'  ├─ Step 5: PIL文字修补...', end='', flush=True)
        # 重新审计最佳图片获取错误详情
        key = next_key(keys)
        final_audit = ocr_audit(best_image, manifest, key, all_keys=keys)
        repaired = _try_pil_text_repair(best_image, final_audit, manifest)
        if repaired != best_image:
            best_image = repaired
            best_ext = 'jpg'
            stats['final_action'] = 'repaired'
            print(f' ✅')
        else:
            stats['final_action'] = 'best_effort'
            print(f' (无需修补)')

    if not stats['final_action']:
        stats['final_action'] = 'pass'

    # ── 质量评分 ──
    print(f'  ├─ Step 5b: 质量评分...', end='', flush=True)
    key = next_key(keys)
    q = quality_score(best_image, key, card_title=title, all_keys=keys)
    q_total = q.get('total', 0)
    q_comment = q.get('comment', '')
    stats['quality_score'] = q_total
    stats['quality_detail'] = q
    print(f' {q_total}/100 ({q_comment})')

    # ── 保存 ──
    out_name = card_id.replace('-', '_')
    filename = f'{out_name}.{best_ext}'
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(best_image)
    size_kb = len(best_image) / 1024
    print(f'  └─ 💾 保存 {filename} ({size_kb:.0f}KB) [审计={best_score} 质量={q_total}]')

    return True, filepath, stats


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════
def main():
    test_mode = '--test' in sys.argv
    skip_audit = '--no-audit' in sys.argv
    force = '--force' in sys.argv
    count_limit = 0
    for i, a in enumerate(sys.argv):
        if a == '--count' and i + 1 < len(sys.argv):
            count_limit = int(sys.argv[i + 1])

    # 找输入文件
    args = [a for a in sys.argv[1:] if not a.startswith('--') and not a.isdigit()]
    json_files = []

    if args:
        # 指定了文件
        json_files = [args[0]]
    else:
        # 自动扫描 knowledge_cards/小学/
        cards_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'knowledge_cards', '小学')
        if os.path.isdir(cards_dir):
            for f in sorted(os.listdir(cards_dir)):
                if f.endswith('.json') and '爆款' not in f:
                    json_files.append(os.path.join(cards_dir, f))
        # fallback: 当前目录
        if not json_files:
            for f in sorted(os.listdir('.')):
                if f.startswith('knowledge_cards') and f.endswith('.json'):
                    json_files.append(f)

    if not json_files:
        print('❌ 未找到知识卡片JSON文件')
        print('用法: python generate_card_images_v3.py [cards.json] [--test] [--count N]')
        sys.exit(1)

    output_dir = 'card_images_v3'
    if len(args) > 1:
        output_dir = args[1]
    os.makedirs(output_dir, exist_ok=True)

    keys = load_api_keys()
    if not keys:
        print('❌ 未找到API密钥 (api_key.txt)')
        sys.exit(1)

    print(f'╔══════════════════════════════════════════════════╗')
    print(f'║  🚀 知识卡片图片生成器 v3 — 终极流水线            ║')
    print(f'╠══════════════════════════════════════════════════╣')
    print(f'║  文字模型: {TEXT_MODEL}')
    print(f'║  图片模型: {" → ".join(IMAGE_MODELS)}')
    print(f'║  审计: {"关闭" if skip_audit else f"开启 (最多{MAX_AUDIT_ROUNDS}轮, 通过≥{AUDIT_PASS_SCORE}分)"}')
    print(f'║  输入: {len(json_files)} 个JSON文件')
    print(f'║  输出: {output_dir}/')
    if test_mode:
        print(f'║  ⚡ 测试模式: 只生成1张')
    elif count_limit:
        print(f'║  🔢 限量模式: 只生成前{count_limit}张')
    print(f'╚══════════════════════════════════════════════════╝\n')

    total = 0
    success = 0
    all_stats = []
    global_start = time.time()

    for json_file in json_files:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        subject = data['subject']
        grade = data['grade']
        semester = data['semester']
        card_count = sum(len(u['cards']) for u in data['units'])
        print(f'📚 {subject} {grade}{semester} ({card_count}张)')
        print(f'   文件: {os.path.basename(json_file)}\n')

        for unit in data['units']:
            print(f'  📖 单元 {unit["unit_id"]}: {unit["unit_name"]}')

            for card in unit['cards']:
                total += 1

                # 检查已存在
                out_name = card['full_id'].replace('-', '_')
                if not force:
                    existing = [f for f in os.listdir(output_dir) if f.startswith(out_name)]
                    if existing:
                        print(f'  ⏭️  [{total}] {card["full_id"]} {card["title"]} → 已存在 {existing[0]}')
                        success += 1
                        continue

                print(f'\n  ┌─ [{total}] {card["full_id"]} {card["title"]} (类型={card.get("type","?")}, 难度={card["difficulty"]})')

                ok, fpath, stats = process_single_card(
                    card, subject, grade, semester, keys, output_dir, skip_audit=skip_audit
                )
                all_stats.append(stats)

                if ok:
                    success += 1

                if test_mode:
                    break
                if count_limit and success >= count_limit:
                    break
                time.sleep(2)

            if test_mode and success > 0:
                break
            if count_limit and success >= count_limit:
                break

        if test_mode and success > 0:
            break
        if count_limit and success >= count_limit:
            break
        print()

    elapsed = time.time() - global_start

    # 保存统计报告
    report_file = os.path.join(output_dir, '_report.json')
    report = {
        'generated_at': datetime.datetime.now().isoformat(),
        'total_cards': total,
        'success': success,
        'elapsed_seconds': round(elapsed, 1),
        'avg_seconds_per_card': round(elapsed / max(success, 1), 1),
        'models': IMAGE_MODELS,
        'audit_enabled': not skip_audit,
        'cards': all_stats,
    }
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 统计摘要
    audit_scores = [s['audit_score'] for s in all_stats if s['audit_score'] > 0]
    quality_scores = [s['quality_score'] for s in all_stats if s['quality_score'] > 0]
    avg_audit = sum(audit_scores) / len(audit_scores) if audit_scores else 0
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

    print(f'\n╔══════════════════════════════════════════════════╗')
    print(f'║  🎉 生成完成!                                     ║')
    print(f'╠══════════════════════════════════════════════════╣')
    print(f'║  成功: {success}/{total} 张')
    print(f'║  耗时: {elapsed:.0f}秒 (平均 {elapsed/max(success,1):.1f}秒/张)')
    print(f'║  OCR审计均分: {avg_audit:.1f}/100')
    print(f'║  质量评分均分: {avg_quality:.1f}/100')
    print(f'║  输出目录: {output_dir}/')
    print(f'║  统计报告: {report_file}')
    print(f'╚══════════════════════════════════════════════════╝')


if __name__ == '__main__':
    main()
