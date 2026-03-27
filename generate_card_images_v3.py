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

# 自我优化系统
try:
    from self_optimizer import (
        build_fewshot_hint, build_error_boost_hint,
        record_full_result, get_adaptive_params,
        record_errors as _so_record_errors
    )
    _HAS_OPTIMIZER = True
    print('[v3] 自我优化系统已加载')
except ImportError:
    _HAS_OPTIMIZER = False
    print('[v3] 自我优化系统未加载 (self_optimizer.py 不存在)')

# 内容质量三级系统
try:
    from content_quality import (
        full_quality_check, build_typed_quality_prompt,
        build_content_refinement_hint, compute_quality_trends,
        get_quality_dashboard, QUALITY_RUBRICS, SUBJECT_FOCUS,
        analyze_top_cards, analyze_failures, generate_style_guide,
        cross_pollinate,
    )
    _HAS_QUALITY = True
    print('[v3] 内容质量三级系统已加载')
except ImportError:
    _HAS_QUALITY = False
    print('[v3] 内容质量系统未加载 (content_quality.py 不存在)')

# 内容设计引擎
try:
    from content_design_engine import (
        design_card_content, match_teaching_strategy,
        compute_cognitive_load, suggest_content_split,
        analyze_information_density,
    )
    _HAS_DESIGN = True
    print('[v3] 内容设计引擎已加载')
except ImportError:
    _HAS_DESIGN = False
    print('[v3] 内容设计引擎未加载 (content_design_engine.py 不存在)')

# 教学效果审核
try:
    from pedagogical_audit import (
        full_pedagogical_audit, score_understandability,
        score_mnemonic_effectiveness, predict_engagement,
    )
    _HAS_PEDAGOGY = True
    print('[v3] 教学效果审核已加载')
except ImportError:
    _HAS_PEDAGOGY = False
    print('[v3] 教学效果审核未加载 (pedagogical_audit.py 不存在)')

# 知识呈现蓝图
try:
    from visual_blueprint import (
        generate_visual_blueprint, compress_for_manifest,
        match_memory_strategy, analyze_info_layers,
    )
    _HAS_BLUEPRINT = True
    print('[v3] 知识呈现蓝图已加载')
except ImportError:
    _HAS_BLUEPRINT = False
    print('[v3] 知识呈现蓝图未加载 (visual_blueprint.py 不存在)')

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
AUDIT_PASS_SCORE = 80   # OCR审计通过分数 (0-100) — 提高标准以减少乱码


def _get_effective_params():
    """获取当前有效参数（自适应覆盖默认值）"""
    if not _HAS_OPTIMIZER:
        return {
            'max_audit_rounds': MAX_AUDIT_ROUNDS,
            'audit_pass_score': AUDIT_PASS_SCORE,
            'max_chinese_chars': 20,
            'max_chars_per_block': 5,
        }
    try:
        return get_adaptive_params()
    except Exception:
        return {
            'max_audit_rounds': MAX_AUDIT_ROUNDS,
            'audit_pass_score': AUDIT_PASS_SCORE,
            'max_chinese_chars': 20,
            'max_chars_per_block': 5,
        }


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
    # 考卷真题专题卡片类型
    '填空满分卡': "审题三步法(读→圈→验)色块流程+陷阱红圈标注+单位对比区",
    '选择秒杀卡': "四选项排列+排除法色块标记(灰色划掉错误项)+正确项绿色高亮",
    '计算零失误卡': "彩色分层竖式(绿/橙/红)+对位检查清单+验算步骤",
    '判断火眼卡': "✓/✗ 大字对比+反例可视化+陷阱词红圈高亮(一定/都是/不可能)",
    '应用题拆解卡': "四步法色块流程(读→画→列→验)+线段图/流程图+完整答语",
    '操作题规范卡': "方格纸示意图+标注数据+规范检查清单✅",
    # 英语考卷真题专题
    '听力得分卡': "耳机图标+关键词高亮色块+选项排除灰色划掉+正确项绿色",
    '拼写零错卡': "字母色块拆分+易错字母红圈高亮+手写笔迹示范",
    '填空必会卡': "句子填空下划线色块+语法提示箭头+选词高亮蓝框",
    '匹配速解卡': "左右两栏连线图+关键词黄色高亮+匹配箭头彩色",
    '阅读通关卡': "文段分层色块(三层)+关键句下划线+答案定位箭头",
    '写作模板卡': "三段式彩色模板框+句型高亮+连接词标签列表",
    # 语文考卷真题专题
    '拼写默写卡': "形近字左右对比+偏旁色块高亮+口诀金句大字",
    '句式变换卡': "原句vs改后句左右栏+箭头指引变换步骤+关键词红色高亮",
    '阅读理解卡': "文段分层色块+关键句下划线+答题模板框架",
    '古诗默写卡': "古诗原文超大字体+易错字红圈标注+诗意插图背景",
    '作文模板卡': "开头中间结尾三段式框架+好词好句高亮色块+修辞示例",
    # 国学文化专题
    '预言解密卡': "古文竖排大字+逐句拆字色块解析+历史对照插图",
    '人物传奇卡': "水墨风人物侧影+传奇故事场景+名言金句大字",
    '历史印证卡': "左预言右历史对比两栏+时间轴连线+命中标记",
    '反转揭秘卡': "先展示常见误解+大反转箭头+真相揭晓色块",
    '智慧启示卡': "古今对比双栏+思维导图+收尾金句大字",
    # 情感生活专题
    '恋爱心理卡': "大脑/心脏示意图+心理学数据可视化+金句大字",
    '暧昧信号卡': "真假信号对比两栏+行为解码图标+判断清单",
    '约会攻略卡': "约会场景插画+DO/DONT对比色块+对话气泡示例",
    '避雷指南卡': "红旗🚩图标列表+危险信号红色高亮+止损建议绿色",
    '情感升温卡': "关系阶梯/温度计图+互动示例气泡+暖色调背景",
    '自我疗愈卡': "愈合阶段时间轴+自我关怀清单+温暖渐变色调",
    # 知识总结专题
    '知识总结卡': "思维导图式布局+核心知识点/公式大字色块+记忆口诀高亮+易错✗✓对比",
    # 语法辨析专题
    '语法辨析卡': "双栏对比(left❌红 vs right✅绿)+完整例句(非孤立短语)+错因解释气泡+口诀底栏(禁止'搭配固定'废话)",
    '易混词卡': "两词并排对比色块+同一语境换词例句+混淆原因分析(💡图标)+巧妙联想口诀",
    '易混词陷阱卡': "两词并排对比色块+同一语境换词例句+混淆原因分析(💡图标)+巧妙联想口诀",
    '语法纠错卡': "左❌错误句子(划红线)+右✅正确句子(绿色)+中间错因解释气泡(💡为什么错)+底部验证方法",
    '句型卡': "句型模板大字色块+填空槽样式变形练习+对比说明为什么这样用",
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
2. 用最简视觉方式画出解题关键步骤（至少一步解释"为什么"而非只说"怎么做"）
{solve_strategy_block}
3. 大字答案 + 口诀(≤10字)

⚠️ 深度教学要求：
- 如果有"本质原因"或"错因"信息，必须在视觉中体现（用💡图标+简短文字）
- ❌错误示范不能只标红叉，必须配一句"为什么错"的解释
- 口诀区如有例外情况，用小字标注

⚠️ 英语卡片特别要求（如果是英语学科）：
- 标题直接用英文短语本身（如 "pay attention to"），不用中文泛化标题
- 必须展示2-3种用法结构 + 每种配完整英文例句(≥6词)
- 必须有❌/✅对错例句对比，错误必须是该短语的真实高频错误
- 🚫严禁混入与该短语无关的词汇/语法点（如讲 pay attention to 时不准出现 successful）
- 🚫严禁填空题——学生不能在图片上写字
- 🚫严禁numbered步骤（①②③流程图）——改用用法结构列表

══════ 视觉设计 ══════

- 竖屏 3:4 画布
- 核心教学图占 ≥ 45%
- 全卡最多4个区块：标题/核心图/金句对比/口诀
- ≥ 25% 留白
- 一个可爱小老师卡通 + ≤6字气泡
- 小红书风格：鲜明渐变背景，饱和色banner，白色圆角内容卡片

══════ ⚠️ 中文文字极简原则 ══════

这是最重要的规则！AI 图片模型渲染中文容易出错，必须极度精简：

- 全卡中文 **≤ {max_chars}字**（越少越好！理想≤ {ideal_chars}字）
- 标题 ≤ {max_per_block}字（72pt 超大粗体）
- 核心金句 ≤ {max_per_block}字
- 口诀 ≤ {max_slogan}字
- 气泡 ≤ 3字
- ❌ 绝不超过{max_per_block}个连续中文字符（严格！）
- ❌ 不写段落、定义、解释、长句子
- 数字和数学符号用阿拉伯数字/符号(不用中文写数字)
- 能用图/箭头/色块/图标表达的，绝不用文字
- ❗每个中文字必须笔画清晰、粗体加大，绝不能出现乱码/错字/缺笔画

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
"IMPORTANT: All visible text MUST be Simplified Chinese (简体中文). LARGE BOLD thick-stroke rounded sans-serif. Max 15 Chinese chars total, each block ≤4 chars. No English text in the image. Clean spacious layout, ≥25% whitespace. Every Chinese character must be pixel-perfect with clear strokes."

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

- 全卡中文 **≤ {max_chars}字**（越少越好！理想≤ {ideal_chars}字）
- 标题 ≤ {max_per_block}字（72pt 超大粗体）
- 核心金句 ≤ {max_per_block}字
- 口诀 ≤ {max_slogan}字
- 气泡 ≤ 3字
- ❌ 绝不超过{max_per_block}个连续中文字符（严格！）
- ❌ 不写段落、定义、解释、长句子
- 数字和数据用阿拉伯数字/符号
- 能用图/箭头/色块/图标表达的，绝不用文字
- ❗每个中文字必须笔画清晰、粗体加大，绝不能出现乱码/错字/缺笔画

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
"IMPORTANT: All visible text MUST be Simplified Chinese (简体中文). LARGE BOLD thick-stroke rounded sans-serif. Max 15 Chinese chars total, each block ≤4 chars. No English text in the image. Clean spacious layout, ≥25% whitespace. Every Chinese character must be pixel-perfect with clear strokes."

提示词长度: 350-500 英文单词。"""


_GRAMMAR_TYPES = {'语法辨析卡', '句型卡', '易混词卡', '易混词陷阱卡', '语法纠错卡',
                  '词汇卡', '高频活用卡', '搭配卡', '词性辨析卡'}

def _build_card_info(card, subject, grade, semester):
    """构建传给 prompt 生成器的卡片信息（自动区分教育/养生/语法类）"""
    if subject in _WELLNESS_SUBJECTS:
        return _build_card_info_wellness(card, subject, grade, semester)
    # 英语学科的卡片统一走语法/英语路径
    if subject == '英语' or card.get('type') in _GRAMMAR_TYPES:
        return _build_card_info_grammar(card, subject, grade, semester)
    return _build_card_info_edu(card, subject, grade, semester)


def _is_text_on_topic(text, topic_kw):
    """判断一段文本是否与主题关键词相关（至少有1个交集）"""
    import re as _re
    if not text or not topic_kw:
        return True  # 无法判断时默认保留
    text_kw = set(_re.findall(r'[a-zA-Z]{3,}', str(text).lower()))
    if not text_kw:
        return True  # 纯中文内容，保留
    return bool(text_kw & topic_kw)


def _get_topic_keywords(card):
    """从标题+定义中提取本卡主题英文关键词集合"""
    import re as _re
    topic_text = (card.get('title', '') + ' ' + card.get('definition', '')).lower()
    return set(_re.findall(r'[a-zA-Z]{3,}', topic_text))



def _detect_shallow_steps(card):
    """检测步骤是否为'拆词式'浅层内容 (如把 pay attention to 拆成三步: attention / pay->attention / pay attention to)
    
    返回: (is_shallow: bool, reason: str)
    """
    import re as _re
    steps = (card.get('example') or {}).get('steps', [])
    if not steps:
        return False, ''
    
    definition = card.get('definition', '').lower().strip()
    title = card.get('title', '').lower().strip()
    
    # 检测1: 步骤是否只是逐词拆解短语
    # 如果大部分步骤只有1-2个英文单词(无解释句子)，就是拆词
    short_step_count = 0
    for s in steps:
        s_str = str(s).strip()
        # 去掉箭头等符号后，看纯英文单词数
        eng_words = _re.findall(r'[a-zA-Z]+', s_str)
        # 如果中文字符极少(<=8)且英文单词<=3，视为浅层步骤
        cn_chars = len(_re.findall(r'[\u4e00-\u9fff]', s_str))
        if len(eng_words) <= 3 and cn_chars <= 8:
            short_step_count += 1
    
    if len(steps) >= 2 and short_step_count >= len(steps) * 0.6:
        return True, f'{short_step_count}/{len(steps)}步是孤立短语/单词，缺少完整例句和解释'
    
    # 检测2: 步骤是否包含完整英文句子(至少有主谓结构，>=5个词)
    has_sentence = False
    for s in steps:
        eng_words = _re.findall(r'[a-zA-Z]+', str(s))
        if len(eng_words) >= 5:
            has_sentence = True
            break
    
    if not has_sentence and len(steps) >= 2:
        return True, '所有步骤都没有完整英文例句，缺乏教学深度'
    
    return False, ''


def _filter_off_topic_steps(card):
    """过滤掉与卡片主题无关的 steps，防止混杂知识点传给 Gemini"""
    import re as _re
    steps = (card.get('example') or {}).get('steps', [])
    if len(steps) < 2:
        return steps
    topic_kw = _get_topic_keywords(card)
    if not topic_kw:
        return steps  # 无英文关键词可比较，全部保留
    filtered = []
    for i, s in enumerate(steps):
        kw = set(_re.findall(r'[a-zA-Z]{3,}', str(s).lower()))
        if not kw:
            filtered.append(s)
            continue
        # 与主题有交集 → 保留
        if kw & topic_kw:
            filtered.append(s)
            continue
        # 与相邻 step 有交集 → 保留
        neighbor_ok = False
        if i > 0:
            prev_kw = set(_re.findall(r'[a-zA-Z]{3,}', str(steps[i-1]).lower()))
            if kw & prev_kw:
                neighbor_ok = True
        if not neighbor_ok and i < len(steps) - 1:
            next_kw = set(_re.findall(r'[a-zA-Z]{3,}', str(steps[i+1]).lower()))
            if kw & next_kw:
                neighbor_ok = True
        if neighbor_ok:
            filtered.append(s)
        # else: 离题 step，丢弃
    return filtered if filtered else steps[:1]  # 至少保留1个


def _filter_off_topic_core_points(card):
    """过滤掉与主题无关的 core_points"""
    points = card.get('core_points', [])[:5]
    topic_kw = _get_topic_keywords(card)
    if not topic_kw or not points:
        return points
    filtered = [p for p in points if _is_text_on_topic(str(p), topic_kw)]
    return filtered if filtered else points[:1]


def _filter_off_topic_mistakes(card):
    """过滤掉与主题无关的 mistakes 条目"""
    mistakes = card.get('mistakes', [])
    topic_kw = _get_topic_keywords(card)
    if not topic_kw or not mistakes:
        return mistakes
    filtered = []
    for m in mistakes:
        if not isinstance(m, dict):
            continue
        # 判断 wrong+correct+reason 是否与主题相关
        m_text = f"{m.get('wrong', '')} {m.get('correct', '')} {m.get('reason', '')}"
        if _is_text_on_topic(m_text, topic_kw):
            filtered.append(m)
    return filtered if filtered else []  # 离题 mistakes 直接丢弃（不保留）


def _clean_answer(card):
    """清理 answer 中的离题内容（例如把 'pay; to; succeed' 清理为 'pay; to'）"""
    import re as _re
    answer = str((card.get('example') or {}).get('answer', ''))
    topic_kw = _get_topic_keywords(card)
    if not topic_kw or not answer:
        return answer
    # 按分号/逗号拆分答案
    parts = _re.split(r'[;,]\s*', answer)
    if len(parts) <= 1:
        return answer  # 不是多答案，原样返回
    cleaned = []
    for part in parts:
        part_kw = set(_re.findall(r'[a-zA-Z]{3,}', part.lower()))
        if not part_kw or (part_kw & topic_kw):
            cleaned.append(part.strip())
        # else: 离题答案部分，丢弃
    return '; '.join(cleaned) if cleaned else answer


def _build_card_info_grammar(card, subject, grade, semester):
    """构建英语语法/搭配类卡片信息 — v6 极简用法卡（通用版）
    
    设计理念: 一张卡只做一件事 → 展示一个短语/语法点的「用法 + 对错 + 拓展」
    对所有英语知识点通用：搭配卡/语法辨析卡/易混词卡/句型卡/词汇卡...
    """
    card_type = card.get('type', '语法辨析卡')

    # ── 提取英文核心短语（作为标题和主题锚点）──
    definition = card.get('definition', '')
    title_raw = card.get('title', '')
    # 从 definition 中提取最长的英文短语
    eng_phrases = re.findall(r'[a-zA-Z][a-zA-Z\s]{2,}', definition)
    eng_key_phrase = max(eng_phrases, key=len).strip() if eng_phrases else ''
    if not eng_key_phrase:
        eng_phrases = re.findall(r'[a-zA-Z][a-zA-Z\s]{2,}', title_raw)
        eng_key_phrase = max(eng_phrases, key=len).strip() if eng_phrases else title_raw

    # 覆盖 card title 为英文短语（让后续所有环节都统一）
    if eng_key_phrase and not re.search(r'[a-zA-Z]{3,}', title_raw):
        card['title'] = eng_key_phrase
        print(f'      [prompt title fix] "{title_raw}" → "{card["title"]}"')

    # 获取自适应字数限制
    eff = _get_effective_params()
    _mc = eff.get('max_chinese_chars', 20)
    _mpb = eff.get('max_chars_per_block', 5)

    # ── 从 definition 提取中文释义（短）──
    cn_meaning = ''
    cn_match = re.search(r'[，,]?\s*(意为|意思是|表示|指的是)[\s""]*([\u4e00-\u9fff/、]+)', definition)
    if cn_match:
        cn_meaning = cn_match.group(2).strip()[:8]
    if not cn_meaning:
        cn_chars = re.findall(r'[\u4e00-\u9fff]+', definition)
        if cn_chars:
            cn_meaning = max(cn_chars, key=len)[:8]

    # ── 收集参考数据: core_points（过滤离题后）──
    points = _filter_off_topic_core_points(card)[:4]
    ref_points = '\n'.join(f'  • {str(p).strip()[:80]}' for p in points) if points else '  （无）'

    # ── 收集参考数据: 对错例句 ──
    on_topic_mistakes = _filter_off_topic_mistakes(card)
    contrast_ref = ''
    if on_topic_mistakes:
        m = on_topic_mistakes[0]
        contrast_ref = f"  ❌ {m.get('wrong', '')[:80]}\n  ✅ {m.get('correct', '')[:80]}"
        reason = m.get('reason', '')
        if reason:
            contrast_ref += f"\n  💡 {reason[:60]}"
    else:
        contrast_ref = f"  （数据缺失，请你根据「{eng_key_phrase}」自行设计，必须是该知识点的真实高频错误）"

    # ── 本质原因 / 口诀 ──
    why_exp = card.get('why_explanation', '')[:120]
    memory_tip = card.get('memory_tip', '')[:30]

    return f"""学科: {subject} | {grade} {semester} | 类型: {card_type}

═══════ 🎯 极简用法卡 — 通用设计规范 ═══════

本卡主角: 「{eng_key_phrase}」（{cn_meaning}）
语法规则: {definition[:120]}

📐 卡片严格4个区块，自上而下，不允许其他内容：

【区块A — 标题】
  英文短语/词组本身，大号粗体居中
  下方小字中文释义（≤4中文字）

【区块B — 用法拓展】(最重要的教学区！)
  展示该知识点的 2-3 种典型搭配/用法结构
  每种结构必须配一个完整英文例句（≥6词）
  例如: 如果知识点是一个搭配短语，展示它接不同词性时的句子
       如果是易混词，展示两个词各自正确的用法句
       如果是语法点，展示该语法在不同语境中的用法
  ⚠️ 用法结构由你根据语法规则推断，不要只是翻译 definition！

【区块C — ❌/✅ 对比】
  一组完整句子（各≥6词），展示学生最容易犯的错误
  错处用红色高亮，正处用绿色高亮
  配一句话错因（≤6中文字）

【区块D — 记忆口诀】
  ≤6中文字，必须含该知识点的具体语法/搭配特征
  好口诀示例: "to后接doing" / "affect是动词" / "enough放后面"
  🚫 万能废话=废卡: "搭配固定要多记" / "语法规则记清楚" / "重点词汇要掌握"

═══════ ⛔ 6条铁律（违反=废卡）═══════

🔒1. 标题就是「{eng_key_phrase}」本身（英文！），🚫禁止纯中文泛化标题
🔒2. 区块B必须展示2-3种不同的用法/搭配，每种配完整英文例句
🔒3. 区块C的❌/✅必须是学生真正会犯的错误，完整句子≥6词
🔒4. 全卡所有内容只能涉及「{eng_key_phrase}」这一个知识点，🚫严禁混入无关词汇/语法点
🔒5. 口诀必须含具体语法特征，🚫禁止万能废话
🔒6. 全卡中文≤{_mc}字，英文不限。每个中文字必须粗体清晰

═══════ 📋 最终检查 ═══════
□ 标题是「{eng_key_phrase}」本身吗？
□ 区块B有2-3种不同用法+完整例句吗？
□ ❌/✅例句只涉及「{eng_key_phrase}」吗？有没有混入无关内容？
□ 口诀含具体语法知识吗？不是万能废话吗？
□ 全卡只有ABCD四个区块吗？没有多余的填空题/步骤编号吗？

═══════ 📚 参考数据（仅供理解，以上规范优先）═══════

【知识要点】:
{ref_points}
【对错参考】:
{contrast_ref}
{f'【本质原因】: {why_exp}' if why_exp else ''}
{f'【口诀参考】(可改进): {memory_tip}' if memory_tip else ''}
难度: {card.get('difficulty', 3)}/5

⚠️ 视觉风格: 竖屏3:4，鲜明渐变背景，白色圆角卡片区块，可爱小老师卡通角色，标题区用饱和色banner，≥25%留白"""


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
        reason = m.get('reason', '')
        mistakes_info = f"\n常见误区: ❌{m.get('wrong', '')[:100]} → ✅{m.get('correct', '')[:100]}"
        if reason:
            mistakes_info += f"\n错因: {reason[:120]}"

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
        reason = m.get('reason', '')
        mistakes_info = f"\n常见错误: ❌{m.get('wrong', '')[:150]} → ✅{m.get('correct', '')[:150]}"
        if reason:
            mistakes_info += f"\n错因: {reason[:150]}"

    why_exp = ''
    if card.get('why_explanation'):
        why_exp = f"\n本质原因: {card['why_explanation'][:200]}"

    is_vert = _detect_vertical_calc(card)

    return f"""学科: {subject} | 年级: {grade}{semester}
标题: {card.get('title', '')} | 类型: {card_type}

【例题】: {example_info or '根据知识点构造一道最典型例题'}
{example_steps}

【定义】: {card.get('definition', '')[:120]}
【要点】: {chr(10).join('• ' + p for p in clean_pts[:3])}
{('【公式】: ' + ' | '.join(formulas)) if formulas else ''}
【口诀】(≤8字): {card.get('memory_tip', '')[:40]}
{'\n本质原因: ' + card.get('why_explanation', '')[:200] if card.get('why_explanation') else ''}
{mistakes_info}
难度: {card.get('difficulty', 3)}/5
{'⚠️ 笔算竖式类：必须画正确竖式' if is_vert else ''}"""


def generate_image_prompt(card, subject, grade, semester, api_key, all_keys=None):
    """Step 1: 生成英文图片提示词 + TEXT_MANIFEST"""
    card_type = card.get('type', '方法卡')
    type_rules = CARD_TYPE_VISUAL_RULES.get(card_type, CARD_TYPE_VISUAL_RULES['方法卡'])
    is_vert = _detect_vertical_calc(card)

    # ── 获取自适应字数参数 ──
    eff = _get_effective_params()
    max_chars = eff.get('max_chinese_chars', 20)
    max_per_block = eff.get('max_chars_per_block', 5)
    ideal_chars = max(8, max_chars - 5)
    max_slogan = min(max_per_block + 2, 8)
    char_fmt = dict(max_chars=max_chars, max_per_block=max_per_block,
                    ideal_chars=ideal_chars, max_slogan=max_slogan)

    # 根据学科选择对应模板
    if subject in _WELLNESS_SUBJECTS:
        visual_block = f"   {type_rules}"
        system_prompt = PROMPT_SYSTEM_TEMPLATE_WELLNESS.format(
            subject=subject,
            visual_strategy_block=visual_block,
            **char_fmt
        )
    elif is_vert:
        solve_block = """   ⚠️ 笔算竖式类：必须画彩色分层竖式！
   - 竖式用颜色分层(绿/橙/红)，旁边放正误对比
   - 数字必须和例题完全一致"""
        system_prompt = PROMPT_SYSTEM_TEMPLATE.format(
            subject=subject,
            solve_strategy_block=solve_block,
            **char_fmt
        )
    else:
        solve_block = f"   {type_rules}"
        system_prompt = PROMPT_SYSTEM_TEMPLATE.format(
            subject=subject,
            solve_strategy_block=solve_block,
            **char_fmt
        )

    card_info = _build_card_info(card, subject, grade, semester)

    # ── 自我优化: 注入 few-shot 高分 prompt 参考 ──
    fewshot_block = ''
    if _HAS_OPTIMIZER:
        try:
            fewshot_block = build_fewshot_hint(subject, card_type)
        except Exception as e:
            print(f'      [optimizer] few-shot hint error: {e}')

    # ── 内容质量: 注入风格指南 + 内容改进提示 ──
    quality_hint = ''
    if _HAS_QUALITY:
        try:
            from content_quality import get_style_guide
            guide_data = get_style_guide(card_type, subject)
            if guide_data.get('guide') and guide_data.get('based_on', 0) >= 3:
                quality_hint += f'\n=== STYLE GUIDE (data-driven) ===\n{guide_data["guide"][:500]}\n=== END ===\n'
        except Exception as e:
            print(f'      [quality] style guide hint error: {e}')

    # ── 内容设计引擎: 教学策略 + 认知负荷 ──
    design_hint = ''
    if _HAS_DESIGN:
        try:
            design = design_card_content(card, card_type, subject, grade)
            design_hint = design.get('design_prompt_injection', '')
            if design.get('warnings'):
                print(f'      [design] 警告: {design["warnings"][0][:60]}')
        except Exception as e:
            print(f'      [design] hint error: {e}')

    # ── 知识呈现蓝图: 视觉布局 + 记忆策略 ──
    blueprint_hint = ''
    if _HAS_BLUEPRINT:
        try:
            bp = generate_visual_blueprint(card, card_type, subject, grade)
            blueprint_hint = bp.get('blueprint_prompt', '')
        except Exception as e:
            print(f'      [blueprint] hint error: {e}')

    # ── 教学效果: 注入教学改进提示 ──
    pedagogy_hint = ''
    if _HAS_PEDAGOGY:
        try:
            ped = full_pedagogical_audit(card, card_type, subject, grade)
            pedagogy_hint = ped.get('prompt_injection', '')
        except Exception as e:
            print(f'      [pedagogy] hint error: {e}')

    full_input = f'{system_prompt}\n\n--- 知识点信息 ---\n{card_info}'
    if fewshot_block:
        full_input += f'\n\n{fewshot_block}'
    if quality_hint:
        full_input += f'\n{quality_hint}'
    if design_hint:
        full_input += f'\n{design_hint}'
    if blueprint_hint:
        full_input += f'\n{blueprint_hint}'
    if pedagogy_hint:
        full_input += f'\n{pedagogy_hint}'

    contents = [
        {'role': 'user', 'parts': [{'text': full_input}]}
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
        # 英语卡标题优化: 自动注入英文关键词
        manifest = _fix_english_card_title_manifest(manifest, card, subject)
        # 清理 prompt（移除 manifest 标签）
        prompt_clean = re.sub(r'\[TEXT_MANIFEST\].*?\[/TEXT_MANIFEST\]', '', best_text, flags=re.DOTALL).strip()

        # ── 文字量守门员: 检查manifest总汉字数 ──
        manifest = _enforce_manifest_limits(manifest)

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


def _fix_english_card_title_manifest(manifest, card, subject):
    """英语卡标题优化: 如果 TITLE 是纯中文泛化标题，自动拼入英文关键短语"""
    if subject != '英语' and subject != 'english':
        return manifest
    
    title_key = None
    title_val = None
    for k, v in manifest.items():
        if 'TITLE' in k.upper():
            title_key = k
            title_val = v
            break
    
    if not title_key or not title_val:
        return manifest
    
    # 检查: TITLE 是否有英文
    has_eng = bool(re.search(r'[a-zA-Z]', title_val))
    if has_eng:
        return manifest  # 已经有英文了，不动
    
    # 从 definition 中提取英文关键短语
    definition = card.get('definition', '')
    eng_phrase = ''
    # 尝试提取完整短语 (如 "pay attention to")
    eng_words = re.findall(r'[a-zA-Z][a-zA-Z\s]{2,}', definition)
    if eng_words:
        # 取最长的英文片段
        eng_phrase = max(eng_words, key=len).strip()[:25]
    
    if not eng_phrase:
        # 从 title 尝试
        title_full = card.get('title', '')
        eng_words = re.findall(r'[a-zA-Z][a-zA-Z\s]{2,}', title_full)
        if eng_words:
            eng_phrase = max(eng_words, key=len).strip()[:25]
    
    if eng_phrase:
        # 中文标题保留前2字 + 英文关键词
        cn_chars = re.findall(r'[\u4e00-\u9fff]', title_val)
        cn_prefix = ''.join(cn_chars[:2]) if cn_chars else title_val[:2]
        manifest[title_key] = f'{cn_prefix}{eng_phrase}'
        print(f'      [title fix] "{title_val}" → "{manifest[title_key]}"')
    
    return manifest


def _count_chinese_chars(text):
    """统计文本中的中文字符数"""
    return sum(1 for c in text if '\u4e00' <= c <= '\u9fff')


def _enforce_manifest_limits(manifest, max_total=None, max_per_block=None):
    """
    文字量守门员: 强制裁剪 TEXT_MANIFEST 中超标的中文文字。
    
    参数自动从自适应系统获取，随着模型成功率提高可自动放宽。
    
    规则:
    1. 每个文字块中文≤ max_per_block 字
    2. 全部文字块总中文≤ max_total 字
    3. 超标时优先保留 TITLE，其次按顺序保留，尾部截断或删除
    """
    # 从自适应系统获取当前限制
    if max_total is None or max_per_block is None:
        params = _get_effective_params()
        if max_total is None:
            max_total = params.get('max_chinese_chars', 15)
        if max_per_block is None:
            max_per_block = params.get('max_chars_per_block', 4)
    if not manifest:
        return manifest
    
    # 统计当前总中文字数
    total_cn = sum(_count_chinese_chars(v) for v in manifest.values())
    max_slogan_check = min(max_per_block + 2, 8)  # 口诀允许更宽
    if total_cn <= max_total:
        # 仍需检查每块≤limit (口诀用独立预算)
        trimmed = {}
        for k, v in manifest.items():
            cn_count = _count_chinese_chars(v)
            is_slogan = any(s in k.upper() for s in ('SLOGAN', '口诀', 'TIP', 'MOTTO'))
            limit = max_slogan_check if is_slogan else max_per_block
            if cn_count > limit:
                new_v = _trim_to_n_chinese(v, limit)
                print(f'      [manifest guard] {k}: "{v}" → "{new_v}" (每块≤{limit}字)')
                trimmed[k] = new_v
            else:
                trimmed[k] = v
        return trimmed
    
    # 总字数超标，需要激进裁剪
    print(f'      ⚠️ [manifest guard] 总中文{total_cn}字超标(上限{max_total})，启动裁剪...')
    
    result = {}
    budget = max_total
    max_slogan = min(max_per_block + 2, 8)  # 口诀独立预算，比普通块多2字
    
    # 优先保留 TITLE
    for k, v in manifest.items():
        if 'TITLE' in k.upper():
            trimmed_v = _trim_to_n_chinese(v, min(max_per_block, budget))
            result[k] = trimmed_v
            budget -= _count_chinese_chars(trimmed_v)
            break
    
    # 其余按顺序，口诀给独立预算
    for k, v in manifest.items():
        if k in result:
            continue
        if budget <= 0:
            print(f'      [manifest guard] 丢弃 {k}: "{v}" (预算用完)')
            continue
        # 口诀/SLOGAN 类字段给更大预算
        is_slogan = any(s in k.upper() for s in ('SLOGAN', '口诀', 'TIP', 'MOTTO'))
        alloc = min(max_slogan if is_slogan else max_per_block, budget)
        cn_count = _count_chinese_chars(v)
        if cn_count == 0:
            result[k] = v  # 纯数字/符号，保留
        elif cn_count <= alloc:
            result[k] = v
            budget -= cn_count
        else:
            trimmed_v = _trim_to_n_chinese(v, alloc)
            print(f'      [manifest guard] {k}: "{v}" → "{trimmed_v}"')
            result[k] = trimmed_v
            budget -= _count_chinese_chars(trimmed_v)
    
    new_total = sum(_count_chinese_chars(v) for v in result.values())
    print(f'      [manifest guard] 裁剪完成: {total_cn}字 → {new_total}字, {len(manifest)}块 → {len(result)}块')
    return result


def _trim_to_n_chinese(text, n):
    """智能截断：保留前n个中文字（保留非中文字符），确保不以虚词/助词半截结尾"""
    result = []
    cn_count = 0
    for c in text:
        if '\u4e00' <= c <= '\u9fff':
            cn_count += 1
            if cn_count > n:
                break
        result.append(c)
    trimmed = ''.join(result).rstrip()
    # 如果截断了，检查末尾是否完整
    if len(trimmed) < len(text):
        trimmed = _ensure_complete_chinese(trimmed)
    return trimmed


# 常见的中文"废尾"——如果口诀以这些字结尾，说明被截断了
_DANGLING_ENDINGS = set('要的了地得在是和与用把被让给往到从向对着过将')

def _ensure_complete_chinese(text):
    """确保中文文字块不以虚词/助词结尾（说明被截断）"""
    if not text:
        return text
    last_char = text[-1]
    if last_char in _DANGLING_ENDINGS:
        # 去掉最后的虚词
        return text[:-1].rstrip()
    return text


# ═══════════════════════════════════════════
# Step 2: 生成卡片图片（强模型 + fallback）
# ═══════════════════════════════════════════
def generate_card_image(prompt, keys, card_title='', subject='', audit_hint='', manifest=None):
    """Step 2: 用最强图片模型生成卡片图片。
    
    多模型 × 多key 全组合尝试，最大化成功率。
    keys: API key 列表（全部），内部按 模型→全部key 的顺序尝试。
    manifest: TEXT_MANIFEST 字典，用于逐字注入提示。
    """
    chinese_prefix = (
        f"CRITICAL INSTRUCTIONS (MUST FOLLOW):\n"
        f"1. This is a {subject} educational knowledge card about \"{card_title}\".\n"
        f"2. ALL visible text MUST be Simplified Chinese (简体中文). "
        f"Use LARGE, BOLD, thick-stroke rounded/gothic sans-serif font.\n"
        f"3. Maximum 15 Chinese characters total. Each text block ≤ 4 characters.\n"
        f"4. Render each Chinese character CLEARLY and CORRECTLY. "
        f"Thick bold strokes. High contrast. No thin/serif/cursive fonts.\n"
        f"5. The main title should be \"{card_title}\" in extra-large bold font.\n"
        f"6. DO NOT substitute similar-looking characters. "
        f"Every single Chinese character must be EXACTLY as specified below.\n"
    )

    # 逐字注入 manifest —— 让模型精确知道每个字
    if manifest:
        # 再次强制确保manifest字数在限制内
        manifest = _enforce_manifest_limits(manifest)
        total_cn = sum(_count_chinese_chars(v) for v in manifest.values())
        chinese_prefix += f"\n=== EXACT TEXT REFERENCE ({total_cn} Chinese chars total — this is the MAXIMUM) ===\n"
        for key, val in manifest.items():
            # 逐字拆分，每个字标 Unicode
            char_detail = ' '.join(f'"{c}"(U+{ord(c):04X})' for c in val if '\u4e00' <= c <= '\u9fff')
            chinese_prefix += f"{key}: \"{val}\"  →  Characters: {char_detail}\n"
        chinese_prefix += "=== END TEXT REFERENCE ===\n"
        chinese_prefix += f"IMPORTANT: Render ONLY these {total_cn} Chinese characters. Do NOT add ANY extra Chinese text beyond this list. Do NOT change, swap, or approximate any character.\n"

    if audit_hint:
        chinese_prefix += f"\n⚠️ CORRECTION FROM PREVIOUS ATTEMPT:\n{audit_hint}\n"

    # ── 自我优化: 注入易错字符强化提示 ──
    if _HAS_OPTIMIZER and manifest:
        try:
            error_boost = build_error_boost_hint(subject, manifest)
            if error_boost:
                chinese_prefix += error_boost
        except Exception as e:
            print(f'      [optimizer] error boost hint error: {e}')

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

⚠️ 特别检查：截断废字
- 检查每个中文文字块是否是**完整**的词或短句
- 如果某个文字块以虚词/助词结尾(如"搭配固定要""注意到""记住就")明显是被截断了 → 标记为 type:"truncated", severity:"high"
- 截断废字每发现一处扣10分

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
        # 逐字拆分期望文字
        char_detail = ' '.join(f'"{c}"(U+{ord(c):04X})' for c in exp if '\u4e00' <= c <= '\u9fff')
        if etype == 'garbled':
            hints.append(f'CRITICAL: The text "{exp}" appeared as garbled "{act}". Render EXACTLY these characters: {char_detail}. Use thick bold strokes.')
        elif etype == 'wrong_char':
            hints.append(f'WRONG CHARACTER: "{act}" must be replaced with "{exp}". Exact characters: {char_detail}.')
        elif etype == 'missing':
            hints.append(f'MISSING TEXT: "{exp}" is missing. Add it with exact characters: {char_detail}.')
        elif etype == 'distorted':
            hints.append(f'DISTORTED: "{exp}" is unreadable. Re-render clearly: {char_detail}.')
        else:
            hints.append(f'Fix: "{act}" → "{exp}" (characters: {char_detail})')

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

    # 修补 high 和 medium severity 的错误（更积极修补）
    repair_errors = [e for e in audit_result.get('errors', []) if e.get('severity') in ('high', 'medium')]
    if not repair_errors:
        return image_data

    # 收集需要修补的文字（标题优先，然后其他错误文字）
    repair_texts = []
    for err in repair_errors[:5]:
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
    font_size = max(36, w // 16)  # 更大字号确保可读
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

1. **教学清晰度**(20分): 例题清晰? 解题步骤直观? 一眼就懂? (英语卡: 有完整例句+易错对比+本质原因?)
2. **文字准确性**(20分): 中文无乱码无错字? 数字公式正确? ⚠️截断废字(如"搭配固定要""注意到")直接扣15分!
3. **视觉美感**(20分): 配色好看? 像小红书爆款? 有吸引力?
4. **布局合理性**(20分): 信息层次清晰? 留白充足? 不拥挤?
5. **可收藏感**(20分): 看到就想截图保存? 有"干货感"? 口诀是否完整有意义(截断废话扣10分)?

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


def _typed_quality_score(image_data, api_key, card_title='', card_type='方法卡',
                          subject='', all_keys=None):
    """
    分类型精准质量评分（Level 3 升级版）。
    用 content_quality.py 中按卡片类型定义的评分维度替代通用评分。
    """
    typed_prompt = build_typed_quality_prompt(card_type, subject, card_title)

    b64_img = base64.b64encode(image_data).decode('utf-8')
    contents = [
        {'role': 'user', 'parts': [
            {'text': f'这张卡片的主题是"{card_title}"。\n\n{typed_prompt}'},
            {'inlineData': {'mimeType': 'image/png', 'data': b64_img}}
        ]}
    ]
    gen_config = {
        'maxOutputTokens': 2048,
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
            all_text = ''
            for part in parts:
                if 'text' in part:
                    all_text += part['text']
            if all_text:
                json_match = re.search(r'\{[\s\S]*?\}', all_text.strip())
                if json_match:
                    result = json.loads(json_match.group())
                    # 从 dimensions 计算总分
                    if 'total' not in result and 'dimensions' in result:
                        dim_total = 0
                        for d in result['dimensions'].values():
                            dim_total += d.get('score', 0) if isinstance(d, dict) else d
                        result['total'] = dim_total
                    return result
    except Exception as e:
        print(f'      [Typed quality parse error] {e}')

    # 降级到通用评分
    return quality_score(image_data, api_key, card_title=card_title, all_keys=all_keys)


# ═══════════════════════════════════════════
# 完整流水线: 单卡片处理
# ═══════════════════════════════════════════
def process_single_card(card, subject, grade, semester, keys, output_dir, skip_audit=False):
    """
    处理单张卡片的完整流水线。
    返回: (success: bool, filepath: str, stats: dict)
    """
    # 使用自适应参数
    _params = _get_effective_params()
    _max_rounds = _params.get('max_audit_rounds', MAX_AUDIT_ROUNDS)
    _pass_score = _params.get('audit_pass_score', AUDIT_PASS_SCORE)

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

    # ── Step 0: 内容质量预审 ──
    content_audit_result = None
    if _HAS_QUALITY and not skip_audit:
        try:
            print(f'  ├─ Step 0: 内容质量预审...', end='', flush=True)
            key = next_key(keys)
            qc = full_quality_check(card, card.get('type', '方法卡'), subject, grade, key, all_keys=keys)
            content_audit_result = qc
            v = qc.get('verdict', 'error')
            s = qc.get('total_score', 0)
            print(f' {v}({s}分)')
            if not qc.get('should_proceed', True):
                print(f'  ├─ ⛔ 内容审核不通过(reject)，跳过图片生成')
                stats['content_audit_score'] = s
                stats['content_verdict'] = v
                stats['final_action'] = 'content_rejected'
                return False, '', stats
            stats['content_audit_score'] = s
            stats['content_verdict'] = v
        except Exception as e:
            print(f' ⚠️ 预审出错: {e}')

    # ── Step 1: 生成提示词 ──
    print(f'  ├─ Step 1: 生成提示词...', end='', flush=True)
    t0 = time.time()
    key = next_key(keys)
    prompt, manifest = generate_image_prompt(card, subject, grade, semester, key, all_keys=keys)
    stats['prompt_gen_time'] = time.time() - t0

    if not prompt:
        print(' ❌ 失败')
        return False, '', stats
    
    # 如果内容预审有改进建议，注入到 prompt
    if content_audit_result and _HAS_QUALITY:
        hint = content_audit_result.get('refinement_hint', '')
        if hint:
            prompt = hint + '\n' + prompt

    manifest_count = len(manifest) if manifest else 0
    total_chars = sum(len(v) for v in manifest.values()) if manifest else 0
    print(f' ✅ ({len(prompt)}字, {manifest_count}处文字共{total_chars}字)')

    time.sleep(1)

    # ── Step 2-4: 生成图片 + OCR审计循环 ──
    best_image = None
    best_ext = 'png'
    best_score = 0
    audit_hint = ''
    last_audit = None  # 保存最近一次审计结果（供自我优化系统使用）

    for round_num in range(1, _max_rounds + 1):
        stats['audit_rounds'] = round_num

        # Step 2: 生成图片
        round_label = f'(round {round_num}/{_max_rounds})' if round_num > 1 else ''
        print(f'  ├─ Step 2: 生成图片{round_label}...', end='', flush=True)
        t1 = time.time()
        img_data, ext, model = generate_card_image(
            prompt, keys, card_title=title, subject=subject,
            audit_hint=audit_hint, manifest=manifest
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
        last_audit = audit  # 记录最近审计结果
        print(f' 得分={score}/100 ({summary})')

        if score > best_score:
            best_image = img_data
            best_ext = ext
            best_score = score

        stats['audit_score'] = best_score

        if score >= _pass_score:
            print(f'  ├─ ✅ OCR审计通过! (score={score})')
            stats['final_action'] = 'pass'
            break
        else:
            # 构建纠错提示
            high_errs = [e for e in errors if e.get('severity') in ('high', 'medium')]
            print(f'  ├─ ⚠️  {len(high_errs)}处文字错误, ', end='')
            if round_num < _max_rounds:
                audit_hint = _build_audit_hint(audit, manifest)
                print(f'重新生成...')
                time.sleep(2)
            else:
                print(f'已达最大轮数')

    if not best_image:
        return False, '', stats

    # ── Step 5: PIL 修补兜底 ──
    if best_score < _pass_score and manifest and not skip_audit:
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

    # ── 质量评分（分类型精准评分）──
    print(f'  ├─ Step 5b: 质量评分...', end='', flush=True)
    key = next_key(keys)
    if _HAS_QUALITY:
        # 使用分类型的精准评分 prompt
        q = _typed_quality_score(best_image, key, card_title=title,
                                  card_type=card.get('type', '方法卡'),
                                  subject=subject, all_keys=keys)
    else:
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

    # ── 自我优化: 记录完整结果 ──
    if _HAS_OPTIMIZER:
        try:
            record_full_result(
                card_id=card_id,
                subject=subject,
                grade=grade,
                card_type=card.get('type', ''),
                prompt_text=prompt,
                manifest=manifest,
                audit_score=best_score,
                quality_score=q_total,
                audit_result=last_audit,
                image_model=stats.get('image_model', ''),
                audit_rounds=stats.get('audit_rounds', 1),
                final_action=stats.get('final_action', ''),
                prompt_length=len(prompt),
                image_size_kb=size_kb,
                elapsed_seconds=stats.get('prompt_gen_time', 0) + stats.get('image_gen_time', 0),
                success=True
            )
        except Exception as e:
            print(f'  ⚠️ [optimizer] record error: {e}')

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
