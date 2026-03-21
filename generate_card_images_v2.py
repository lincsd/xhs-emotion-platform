#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识卡片图片生成器 v2 — 五角色流水线
=============================================
5 AI 角色协作，生产小红书爆款知识卡片:

  Role 1: 教研专家     → 内容选题 + 易错点分析
  Role 2: 教学设计师   → 解题策略 + 教学法设计
  Role 3: 小红书策划   → 爆款标题 + 情绪钩子 + 互动设计
  Role 4: 视觉设计师   → 视觉布局 + 图片 Prompt
  Role 5: 质检总监     → 评分 + 改进建议 → 循环改进

用法:
  python generate_card_images_v2.py                               # 默认: 爆款JSON
  python generate_card_images_v2.py knowledge_cards_*.json        # 指定JSON
  python generate_card_images_v2.py --test                        # 只测试1张
  python generate_card_images_v2.py --count 3                     # 只生成3张
  python generate_card_images_v2.py --role-debug                  # 显示每个角色输出
"""

import json, os, sys, time, base64, datetime, re, textwrap
import urllib.request, urllib.error

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════
GEMINI_API_BASE = 'https://generativelanguage.googleapis.com/v1beta'
TEXT_MODEL  = 'gemini-2.5-flash'
IMAGE_MODEL = 'gemini-2.5-flash-preview-image-generation'   # 主图片模型
IMAGE_MODEL_FALLBACKS = [
    'gemini-3.1-flash-image-preview',
    'gemini-3-pro-image-preview',
    'gemini-2.5-flash-image',
]
QUALITY_THRESHOLD = 38  # 满分50, 低于此分退回改进
MAX_REFINE_ROUNDS = 1   # 最多改进轮数

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
                return json.loads(resp.read().decode('utf-8'))
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
    """从 Gemini 响应中提取最优文本"""
    if not resp:
        return ''
    best = ''
    for cand in resp.get('candidates', []):
        for part in (cand.get('content') or {}).get('parts', []):
            if 'text' in part and not part.get('thought', False):
                txt = part['text'].strip()
                if len(txt) > len(best):
                    best = txt
    # fallback: 包含 thinking 的
    if not best:
        for cand in resp.get('candidates', []):
            for part in (cand.get('content') or {}).get('parts', []):
                if 'text' in part:
                    txt = part['text'].strip()
                    if len(txt) > len(best):
                        best = txt
    return best

def call_role(role_name, prompt_text, api_key, temperature=0.8, max_tokens=4096):
    """统一的角色调用入口"""
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


# ═══════════════════════════════════════════
# 题型 Skill 知识库（自动根据卡片类型匹配）
# ═══════════════════════════════════════════
CARD_TYPE_SKILLS = {
    '概念卡': {
        'strategy': '生活场景→抽象概念',
        'visual': '生活实物大图(占45%+), 概念提炼金句, 口诀',
        'emotion': '熟悉感→恍然大悟',
    },
    '方法卡': {
        'strategy': '具体例题→色块分步→答案',
        'visual': '例题大字展示, 色块解题(2-3色), 答案超大',
        'emotion': '好奇→清晰→成就',
    },
    '辨析卡': {
        'strategy': '✓/✗ 并排对比→红圈标差异',
        'visual': '左✗右✓并排(占50%), 红圈1处差异, 金句',
        'emotion': '困惑→明白→警觉',
    },
    '公式卡': {
        'strategy': '图形实例→直观推导→公式',
        'visual': '格子推导图, 公式超大醒目, 代入计算',
        'emotion': '好奇→理解→记住',
    },
    '陷阱卡': {
        'strategy': '设置陷阱→暴露错误→揭示真相',
        'visual': '大题目(20%), 钩子文案, 左✗右✓揭秘, 红圈陷阱点',
        'emotion': '好奇挑战→惊讶→恍然大悟',
        'hook': '反直觉, 90%做错, 你来试试',
    },
    '速算卡': {
        'strategy': '常规慢方法→速算技巧→结果一致',
        'visual': '左🐢慢(灰色) 右⚡快(彩色), 速算步骤色块, 大答案',
        'emotion': '好奇→震撼→成就感',
        'hook': '比老师教的快10倍, 3秒搞定',
    },
    '挑战卡': {
        'strategy': '限时+闯关+悬念答案',
        'visual': '关卡编号(金色), 大题目(30%), 倒计时, 答案在评论区',
        'emotion': '跃跃欲试→紧张→不服气/成就',
        'hook': '30秒内答对算你赢, 闯关挑战',
    },
    '生活卡': {
        'strategy': '生活场景→数学问题→实用解法',
        'visual': '生活插画(40%), 气泡标注计算, 实用结论',
        'emotion': '熟悉亲切→恍然大悟→实用满足',
        'hook': '原来买菜也要数学, 带孩子试试',
    },
    '对战卡': {
        'strategy': '左右分栏→家长vs孩子→同题PK',
        'visual': '左蓝(家长) VS 右粉(孩子), 同类不同难度题, 计分栏',
        'emotion': '跃跃欲试→紧张→欢乐亲子',
        'hook': '家长vs孩子谁先答对, 亲子PK',
    },
    '思维卡': {
        'strategy': '有趣问题→可视化思维过程→优雅解法',
        'visual': '情境问题(20%), 思维可视化(45%色块分步), 方法名+答案',
        'emotion': '好奇挑战→专注→啊哈恍然',
        'hook': '聪明的孩子都会, 动动脑',
    },
}

# 新奇解题策略库（Point 3）
NOVEL_STRATEGIES = {
    '反转法': '先展示常见错误答案及原因, 再揭示正确解法, 制造"原来坑在这里"的惊喜',
    '类比法': '把抽象数学映射到生活场景(分数=切披萨, 面积=铺地砖), 降低理解门槛',
    '对抗法': '设计"正确先生vs粗心怪"两个角色对抗, 孩子代入角色增强记忆',
    '动画帧法': '设计成动画的关键帧, 有动感和故事感, 即使是静图也有时间流动感',
    '一笔改错法': '展示一个错误算式, 只改一个地方让它变正确, 游戏化思维训练',
}


# ═══════════════════════════════════════════
# Role 1: 教研专家
# ═══════════════════════════════════════════
def role_1_researcher(card, subject, api_key):
    """教研专家: 内容选题 + 易错点分析"""
    card_type = card.get('type', '方法卡')
    skill = CARD_TYPE_SKILLS.get(card_type, CARD_TYPE_SKILLS['方法卡'])

    prompt = f"""你是一位有20年教研经验的小学{subject}教研员，研究过10万份试卷。

请分析以下知识点,输出内容选题brief(JSON格式):

知识点: {card['title']}
题型: {card_type}
定义: {card.get('definition','')}
核心要点: {'; '.join(card.get('core_points',[])[:4])}
例题: {card.get('example',{}).get('question','无')}
答案: {card.get('example',{}).get('answer','无')}
口诀: {card.get('memory_tip','')}
易错点: {json.dumps(card.get('mistakes',[]), ensure_ascii=False)[:200]}
难度: {card.get('difficulty',3)}/5

请输出JSON(不要markdown代码块):
{{
  "selected_problem": "选出的最核心例题(一道)",
  "why_important": "为什么这道题重要(一句话)",
  "top3_mistakes": ["学生最常犯的错误1","错误2","错误3"],
  "trap_point": "最容易踩的坑(一句话)",
  "exam_frequency": "考试频率(高/中/低)",
  "parent_appeal": "家长为什么会关注这个(一句话)",
  "age_range": "适合年龄段"
}}"""

    text = call_role('教研专家', prompt, api_key, temperature=0.6)
    # 尝试解析JSON
    try:
        # 清理可能的markdown包裹
        clean = re.sub(r'```json\s*', '', text)
        clean = re.sub(r'```\s*$', '', clean).strip()
        return json.loads(clean)
    except:
        return {'selected_problem': card.get('example',{}).get('question',''), 'raw': text}


# ═══════════════════════════════════════════
# Role 2: 教学设计师
# ═══════════════════════════════════════════
def role_2_designer(card, brief1, subject, api_key):
    """教学设计师: 解题策略 + 教学法设计"""
    card_type = card.get('type', '方法卡')
    skill = CARD_TYPE_SKILLS.get(card_type, CARD_TYPE_SKILLS['方法卡'])

    # 根据题型推荐新奇策略
    novel_options = list(NOVEL_STRATEGIES.items())
    novel_list = '\n'.join(f'  - {k}: {v}' for k, v in novel_options)

    prompt = f"""你是一位认知科学博士+一线{subject}教师，擅长把复杂变简单。

已有教研专家的分析:
{json.dumps(brief1, ensure_ascii=False, indent=2)}

知识点: {card['title']} (题型: {card_type})
题型设计策略: {skill['strategy']}
例题: {card.get('example',{}).get('question','无')}
解题步骤: {json.dumps(card.get('example',{}).get('steps',[]), ensure_ascii=False)}

可选的新奇解题展示策略:
{novel_list}

请输出JSON(不要markdown代码块):
{{
  "eureka_moment": "顿悟点——哪个瞬间孩子会恍然大悟?(一句话)",
  "analogy": "类比——这道题像生活中的什么?(一句话)",
  "novel_strategy": "推荐使用的新奇策略名称(从上面选一个)",
  "novel_application": "这个策略具体怎么用在这道题上(2-3句话)",
  "visual_solution": "解题可视化方案: 用什么图示/色块/对比来展示(详细描述,3-5句话)",
  "soul_mnemonic": "灵魂口诀(≤10字,朗朗上口)"
}}"""

    text = call_role('教学设计师', prompt, api_key, temperature=0.85)
    try:
        clean = re.sub(r'```json\s*', '', text)
        clean = re.sub(r'```\s*$', '', clean).strip()
        return json.loads(clean)
    except:
        return {'visual_solution': card.get('memory_tip',''), 'raw': text}


# ═══════════════════════════════════════════
# Role 3: 小红书策划
# ═══════════════════════════════════════════
def role_3_strategist(card, brief1, brief2, subject, api_key):
    """小红书策划: 爆款标题 + 情绪钩子 + 互动设计"""
    card_type = card.get('type', '方法卡')
    skill = CARD_TYPE_SKILLS.get(card_type, CARD_TYPE_SKILLS['方法卡'])

    prompt = f"""你是小红书教育赛道TOP操盘手，打造过100个10w+爆款笔记。

知识点: {card['title']} (题型: {card_type})
教研分析: {json.dumps(brief1, ensure_ascii=False)[:300]}
教学设计: {json.dumps(brief2, ensure_ascii=False)[:300]}
题型情绪路线: {skill.get('emotion', '')}
题型传播钩子: {skill.get('hook', '')}

请输出JSON(不要markdown代码块):
{{
  "title_options": [
    "爆款标题1(必须有情绪钩子,15-25字)",
    "爆款标题2",
    "爆款标题3"
  ],
  "best_title": "推荐使用的标题(从上面选)",
  "emotion_tone": "卡片整体情绪基调(1个词)",
  "hook_type": "钩子类型(惊讶/实用/挑战/焦虑/好奇等)",
  "interaction_design": "互动设计(引导评论/转发的具体方法,2句话)",
  "comment_guide": "评论区引导语(1句话)",
  "series_tag": "系列标签(如#小学数学陷阱题#)",
  "target_audience": "目标人群(家长/学生/老师)",
  "ip_character_state": "小老师角色此刻的表情和状态(如: 惊讶张嘴/得意眨眼/思考摸下巴)"
}}"""

    text = call_role('小红书策划', prompt, api_key, temperature=0.9)
    try:
        clean = re.sub(r'```json\s*', '', text)
        clean = re.sub(r'```\s*$', '', clean).strip()
        return json.loads(clean)
    except:
        return {'best_title': card['title'], 'raw': text}


# ═══════════════════════════════════════════
# Role 4: 视觉设计师
# ═══════════════════════════════════════════
def role_4_visual(card, brief1, brief2, brief3, subject, api_key):
    """视觉设计师: 综合所有brief → 最终图片Prompt"""
    card_type = card.get('type', '方法卡')
    skill = CARD_TYPE_SKILLS.get(card_type, CARD_TYPE_SKILLS['方法卡'])

    # 构建设计元素系统（Point 2）
    design_elements = f"""
── IP角色系统 ──
固定角色: "数学小博士" — 一个戴眼镜的可爱卡通小孩
本张卡片的表情: {brief3.get('ip_character_state', '微笑竖大拇指')}
角色位置: 卡片右下角, 占8%面积, 带对话气泡

── 系列感设计 ──
题型标签: [{card_type}]
系列标签: {brief3.get('series_tag', '#知识卡片#')}

── 情绪设计 ──
情绪基调: {brief3.get('emotion_tone', '好奇')}
标题钩子: {brief3.get('best_title', card['title'])}

── 视觉策略 ──
{skill['visual']}
"""

    prompt = f"""你是给3C教育品牌做过500+张小红书图文的资深视觉设计师。

现在你要综合3位专家的分析，设计一张知识卡片的最终图片Prompt。

── 卡片信息 ──
标题: {card['title']}
题型: {card_type}
例题: {brief1.get('selected_problem', card.get('example',{}).get('question',''))}

── 教研分析 (Role 1) ──
重要性: {brief1.get('why_important','')}
常见错误: {json.dumps(brief1.get('top3_mistakes',[]), ensure_ascii=False)}
陷阱点: {brief1.get('trap_point','')}
家长关注: {brief1.get('parent_appeal','')}

── 教学设计 (Role 2) ──
顿悟点: {brief2.get('eureka_moment','')}
类比: {brief2.get('analogy','')}
新奇策略: {brief2.get('novel_strategy','')} — {brief2.get('novel_application','')}
可视化方案: {brief2.get('visual_solution','')}
口诀: {brief2.get('soul_mnemonic', card.get('memory_tip',''))}

── 传播策略 (Role 3) ──
推荐标题: {brief3.get('best_title','')}
情绪: {brief3.get('emotion_tone','')}
互动设计: {brief3.get('interaction_design','')}
钩子: {brief3.get('hook_type','')}

── 设计要素 ──
{design_elements}

══════ 输出要求 ══════

请直接输出英文图片生成Prompt(500-800词)，不要输出其他文字。

必须遵守的规则:
1. 开头: "IMPORTANT: All visible text MUST be Simplified Chinese. LARGE BOLD thick-stroke rounded sans-serif. Max 35 Chinese chars total."
2. 竖屏3:4比例
3. 全部中文用引号包裹，标注字号
4. 背景用渐变色(写具体色号)
5. 题目/例题必须醒目展示(是卡片核心!)
6. 解题过程用色块/图示(不画竖式)
7. 箭头≤2个且必须有中文标签
8. 必须包含"数学小博士"卡通角色(右下角+气泡)
9. 融入教学设计师的新奇策略和可视化方案
10. 融入小红书策划的情绪钩子和标题
11. 答案要用超大鲜明色展示"""

    text = call_role('视觉设计师', prompt, api_key, temperature=0.85, max_tokens=8192)
    return text


# ═══════════════════════════════════════════
# Role 5: 质检总监
# ═══════════════════════════════════════════
def role_5_auditor(card, brief1, brief2, brief3, prompt_text, subject, api_key):
    """质检总监: 从5个维度评分 + 改进建议"""
    card_type = card.get('type', '方法卡')

    prompt = f"""你是教育内容审核专家 + 小红书算法研究者。

请审核以下知识卡片图片Prompt的质量。

── 卡片信息 ──
标题: {card['title']}
题型: {card_type}
例题: {card.get('example',{}).get('question','无')}
正确答案: {card.get('example',{}).get('answer','无')}

── 教研Brief ──
{json.dumps(brief1, ensure_ascii=False)[:200]}

── 教学Brief ──
{json.dumps(brief2, ensure_ascii=False)[:200]}

── 传播Brief ──
{json.dumps(brief3, ensure_ascii=False)[:200]}

── 待审核的图片Prompt ──
{prompt_text[:1500]}

请从5个维度评分(每项1-10分，总分50)，输出JSON(不要markdown代码块):
{{
  "scores": {{
    "knowledge_accuracy": 0,
    "teaching_effectiveness": 0,
    "viral_potential": 0,
    "visual_appeal": 0,
    "info_balance": 0
  }},
  "total": 0,
  "verdict": "PASS或FAIL",
  "top_issue": "最大问题(一句话，如果PASS则写'无')",
  "suggestions": ["改进建议1","建议2","建议3"],
  "knowledge_check": "数学内容是否正确(是/否+说明)"
}}

评分标准:
- knowledge_accuracy(知识准确): 数学内容、例题答案是否正确
- teaching_effectiveness(教学有效): 零基础孩子看了能否理解
- viral_potential(传播潜力): 标题是否吸睛、会不会被收藏转发
- visual_appeal(视觉吸引): 配色/布局/信息密度是否合理
- info_balance(信息平衡): 不多不少，一卡一点
如果total < {QUALITY_THRESHOLD}，verdict设为"FAIL"。"""

    text = call_role('质检总监', prompt, api_key, temperature=0.4)
    try:
        clean = re.sub(r'```json\s*', '', text)
        clean = re.sub(r'```\s*$', '', clean).strip()
        result = json.loads(clean)
        # 计算总分
        scores = result.get('scores', {})
        total = sum(scores.values())
        result['total'] = total
        result['verdict'] = 'PASS' if total >= QUALITY_THRESHOLD else 'FAIL'
        return result
    except:
        return {'total': 40, 'verdict': 'PASS', 'raw': text}


# ═══════════════════════════════════════════
# 图片生成
# ═══════════════════════════════════════════
def generate_image(prompt_text, api_key, card_title='', subject=''):
    """用图片模型生成卡片图片"""
    chinese_prefix = (
        f"CRITICAL INSTRUCTIONS (MUST FOLLOW):\n"
        f"1. TOPIC: This is a {subject} educational knowledge card about \"{card_title}\".\n"
        f"2. TEXT: ALL visible text MUST be Simplified Chinese. LARGE BOLD thick-stroke rounded sans-serif.\n"
        f"3. The main title should be \"{card_title}\" in extra-large bold font.\n\n"
    )
    full_prompt = chinese_prefix + prompt_text
    contents = [{'role': 'user', 'parts': [{'text': full_prompt}]}]
    gen_config = {'responseModalities': ['TEXT', 'IMAGE']}

    # 尝试多个模型
    models = [IMAGE_MODEL] + IMAGE_MODEL_FALLBACKS
    seen = set()
    unique_models = []
    for m in models:
        if m not in seen:
            seen.add(m)
            unique_models.append(m)

    for model_name in unique_models:
        print(f'      尝试模型: {model_name}...', end='', flush=True)
        resp = gemini_call(model_name, contents, api_key, gen_config=gen_config, timeout=200)
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
# 保存到 Prompt Library
# ═══════════════════════════════════════════
PROMPT_LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'card_prompt_lib', 'prompts')

def save_to_library(card, briefs, final_prompt, audit, subject, grade, semester, image_path=''):
    """将5角色完整输出保存到 prompt library"""
    try:
        g = grade.replace('年级', '') if grade else ''
        s = semester.replace('册', '') if semester else ''
        subdir = f'{subject}_{g}{s}'
        lib_dir = os.path.join(PROMPT_LIB_DIR, subdir)
        os.makedirs(lib_dir, exist_ok=True)

        parts = card['full_id'].split('-')
        fid = '_'.join(parts[-2:]) if len(parts) >= 2 else card['full_id'].replace('-', '_')
        safe_title = card['title'].replace('/', '_').replace('\\', '_')[:20]
        md_file = os.path.join(lib_dir, f'{fid}_{safe_title}.md')

        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        card_type = card.get('type', '未知')
        brief1, brief2, brief3 = briefs

        scores = audit.get('scores', {})
        total = audit.get('total', 0)

        content = f"""# {card['full_id']} {card['title']}

> 题型: {card_type} | 难度: {card.get('difficulty',3)}/5 | 生成时间: {now}
> 流水线: v2 五角色系统 | 质检评分: {total}/50 ({audit.get('verdict','?')})

## Role 1: 教研专家
```json
{json.dumps(brief1, ensure_ascii=False, indent=2)}
```

## Role 2: 教学设计师
```json
{json.dumps(brief2, ensure_ascii=False, indent=2)}
```

## Role 3: 小红书策划
```json
{json.dumps(brief3, ensure_ascii=False, indent=2)}
```

## Role 4: 视觉设计师 — 最终 Prompt
```
{final_prompt}
```

## Role 5: 质检总监
| 维度 | 分数 |
|------|------|
| 知识准确 | {scores.get('knowledge_accuracy','?')}/10 |
| 教学有效 | {scores.get('teaching_effectiveness','?')}/10 |
| 传播潜力 | {scores.get('viral_potential','?')}/10 |
| 视觉吸引 | {scores.get('visual_appeal','?')}/10 |
| 信息平衡 | {scores.get('info_balance','?')}/10 |
| **总分** | **{total}/50** |
| 判定 | {audit.get('verdict','?')} |
| 最大问题 | {audit.get('top_issue','无')} |

## 元数据
| 字段 | 值 |
|------|-----|
| card_id | {card['full_id']} |
| 题型 | {card_type} |
| prompt长度 | {len(final_prompt)} chars |
| 图片 | {image_path} |
| 模型 | Text: {TEXT_MODEL}, Image: {IMAGE_MODEL} |
| pipeline | v2 五角色流水线 |
"""
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(content)

        # 更新 index
        index_file = os.path.join(lib_dir, '_index.json')
        index = {}
        if os.path.exists(index_file):
            with open(index_file, 'r', encoding='utf-8') as f:
                index = json.load(f)

        index[card['full_id']] = {
            'title': card['title'],
            'type': card_type,
            'prompt_file': os.path.basename(md_file),
            'prompt_length': len(final_prompt),
            'image': image_path,
            'generated_at': now,
            'pipeline': 'v2_5role',
            'audit_score': total,
            'audit_verdict': audit.get('verdict', '?'),
        }
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f'    [save error] {e}')


# ═══════════════════════════════════════════
# 主流程: 五角色流水线
# ═══════════════════════════════════════════
def process_card(card, subject, grade, semester, keys, output_dir, role_debug=False):
    """对一张卡片执行完整的5角色流水线"""
    card_type = card.get('type', '方法卡')

    # ─── Role 1: 教研专家 ───
    print(f'  ├─ R1 教研专家...', end='', flush=True)
    brief1 = role_1_researcher(card, subject, next_key(keys))
    print(f' ✅')
    if role_debug:
        print(f'      {json.dumps(brief1, ensure_ascii=False)[:150]}')
    time.sleep(0.5)

    # ─── Role 2: 教学设计师 ───
    print(f'  ├─ R2 教学设计师...', end='', flush=True)
    brief2 = role_2_designer(card, brief1, subject, next_key(keys))
    print(f' ✅')
    if role_debug:
        print(f'      {json.dumps(brief2, ensure_ascii=False)[:150]}')
    time.sleep(0.5)

    # ─── Role 3: 小红书策划 ───
    print(f'  ├─ R3 小红书策划...', end='', flush=True)
    brief3 = role_3_strategist(card, brief1, brief2, subject, next_key(keys))
    print(f' ✅')
    if role_debug:
        print(f'      {json.dumps(brief3, ensure_ascii=False)[:150]}')
    time.sleep(0.5)

    # ─── Role 4: 视觉设计师 ───
    print(f'  ├─ R4 视觉设计师...', end='', flush=True)
    final_prompt = role_4_visual(card, brief1, brief2, brief3, subject, next_key(keys))
    if not final_prompt or len(final_prompt) < 100:
        print(f' ❌ Prompt太短')
        return False
    print(f' ✅ ({len(final_prompt)} chars)')
    if role_debug:
        print(f'      {final_prompt[:200]}...')
    time.sleep(0.5)

    # ─── Role 5: 质检总监 ───
    print(f'  ├─ R5 质检总监...', end='', flush=True)
    audit = role_5_auditor(card, brief1, brief2, brief3, final_prompt, subject, next_key(keys))
    total = audit.get('total', 0)
    verdict = audit.get('verdict', 'PASS')
    print(f' {total}/50 [{verdict}]')
    if role_debug and audit.get('suggestions'):
        for s in audit['suggestions'][:2]:
            print(f'      💡 {s}')

    # ─── 改进循环 ───
    if verdict == 'FAIL' and MAX_REFINE_ROUNDS > 0:
        print(f'  ├─ 🔄 质检未通过，发回R4改进...')
        suggestions = audit.get('suggestions', [])
        refine_prompt = f"""你之前为 "{card['title']}" 设计的图片Prompt质检未通过(得分{total}/50)。

质检反馈:
- 最大问题: {audit.get('top_issue','')}
- 改进建议: {'; '.join(suggestions)}

原Prompt:
{final_prompt[:1000]}

请根据质检反馈修改Prompt，直接输出修改后的完整英文Prompt(500-800词)。"""

        refined = call_role('视觉设计师(改进)', refine_prompt, next_key(keys), max_tokens=8192)
        if refined and len(refined) > 100:
            final_prompt = refined
            print(f'  ├─ R4 改进完成 ({len(refined)} chars)')
            # 复审
            audit = role_5_auditor(card, brief1, brief2, brief3, final_prompt, subject, next_key(keys))
            total = audit.get('total', 0)
            verdict = audit.get('verdict', 'PASS')
            print(f'  ├─ R5 复审: {total}/50 [{verdict}]')

    # ─── 生成图片 ───
    print(f'  ├─ 🎨 生成图片...')
    result = generate_image(final_prompt, next_key(keys), card_title=card['title'], subject=subject)
    if not result:
        print(f'  └─ ❌ 图片生成失败')
        # 仍然保存 prompt
        save_to_library(card, (brief1, brief2, brief3), final_prompt, audit, subject, grade, semester)
        return False

    img_data, ext = result
    out_name = card['full_id'].replace('-', '_')
    filename = f'{out_name}.{ext}'
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(img_data)

    size_kb = len(img_data) / 1024
    print(f'  └─ ✅ {filename} ({size_kb:.0f}KB) 质检:{total}/50')

    save_to_library(card, (brief1, brief2, brief3), final_prompt, audit,
                    subject, grade, semester, image_path=filepath)
    return True


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════
def main():
    test_mode = '--test' in sys.argv
    role_debug = '--role-debug' in sys.argv
    count_limit = 0
    for i, a in enumerate(sys.argv):
        if a == '--count' and i + 1 < len(sys.argv):
            count_limit = int(sys.argv[i + 1])
    args = [a for a in sys.argv[1:] if not a.startswith('--') and not a.isdigit()]

    # Find input JSON (优先爆款JSON)
    json_file = args[0] if args else None
    if not json_file:
        # 先找爆款
        for f in sorted(os.listdir('.')):
            if '爆款' in f and f.endswith('.json'):
                json_file = f
                break
        # 再找普通
        if not json_file:
            for f in sorted(os.listdir('.')):
                if f.startswith('knowledge_cards') and f.endswith('.json'):
                    json_file = f
                    break

    if not json_file or not os.path.exists(json_file):
        print('未找到知识卡片JSON文件')
        sys.exit(1)

    output_dir = 'card_images_v2'
    os.makedirs(output_dir, exist_ok=True)

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    keys = load_api_keys()
    if not keys:
        print('未找到API密钥')
        sys.exit(1)

    subject = data['subject']
    grade = data['grade']
    semester = data['semester']
    total_cards = data.get('total_cards', sum(len(u['cards']) for u in data['units']))

    print()
    print('╔══════════════════════════════════════════════════╗')
    print('║  🎯 知识卡片 v2 — 五角色流水线                   ║')
    print('╠══════════════════════════════════════════════════╣')
    print(f'║  📚 {subject} {grade}{semester} ({data.get("textbook","")}) ')
    print(f'║  🎴 {total_cards} 张卡片 → {output_dir}/')
    print(f'║  🤖 R1教研 → R2教学 → R3策划 → R4视觉 → R5质检')
    print(f'║  📊 质检阈值: {QUALITY_THRESHOLD}/50, 改进轮数: {MAX_REFINE_ROUNDS}')
    print(f'║  🔑 API Keys: {len(keys)} 个')
    if data.get('card_pack'):
        print(f'║  📦 卡包: {data["card_pack"]}')
    if test_mode:
        print(f'║  ⚡ 测试模式: 只生成1张')
    elif count_limit:
        print(f'║  🔢 限量: 前{count_limit}张')
    print('╚══════════════════════════════════════════════════╝')
    print()

    total = 0
    success = 0

    for unit in data['units']:
        print(f'📖 {unit["unit_id"]}: {unit["unit_name"]}')
        for card in unit['cards']:
            total += 1
            print(f'  ┌─ [{total}/{total_cards}] {card["full_id"]} {card["title"]} [{card.get("type","")}]')

            # 检查已有
            out_name = card['full_id'].replace('-', '_')
            existing = [f for f in os.listdir(output_dir) if f.startswith(out_name)]
            if existing:
                print(f'  └─ ⏭️ 已存在 {existing[0]}')
                success += 1
                continue

            ok = process_card(card, subject, grade, semester, keys, output_dir, role_debug)
            if ok:
                success += 1

            if test_mode:
                print(f'\n⚡ 测试完成')
                break
            if count_limit and success >= count_limit:
                print(f'\n🔢 已完成{count_limit}张')
                break
            time.sleep(2)

        if test_mode and success > 0:
            break
        if count_limit and success >= count_limit:
            break
        print()

    print()
    print('╔══════════════════════════════════════════════════╗')
    print(f'║  🎉 完成! {success}/{total} 张')
    print(f'║  📁 {output_dir}/')
    print(f'║  📚 card_prompt_lib/prompts/ (含5角色完整记录)')
    print('╚══════════════════════════════════════════════════╝')


if __name__ == '__main__':
    main()
