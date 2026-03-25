#!/usr/bin/env python3
"""
生成考卷真题专题卡片 — 全学段 × 全学科
==========================================
基于真实考卷题型分析，生成备考策略型知识卡片。

用法:
  python generate_exam_cards.py                          # 生成小学数学全年级考卷卡
  python generate_exam_cards.py --subject 语文            # 生成小学语文全年级考卷卡
  python generate_exam_cards.py --subject 英语            # 生成小学英语全年级考卷卡
  python generate_exam_cards.py --grade 三下              # 只生成三年级下册
  python generate_exam_cards.py --subject 数学 --grade 五上
  python generate_exam_cards.py --all                    # 生成所有学科全年级
"""

import os, sys, json, time, re, argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============ API 配置（复用 generate_knowledge_cards.py 的逻辑）============
def load_keys():
    kp = os.path.join(BASE_DIR, 'api_key.txt')
    if not os.path.exists(kp):
        print("❌ api_key.txt 不存在"); sys.exit(1)
    keys = []
    for line in open(kp, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('GEMINI_API_KEY='):
            val = line.split('=', 1)[1]
            keys.extend([k.strip() for k in val.split(',') if k.strip()])
    if not keys:
        print("❌ api_key.txt 中无有效 Gemini Key"); sys.exit(1)
    return keys

def call_gemini(prompt, keys, model="gemini-2.5-flash", temperature=0.7, max_retries=3):
    """调用 Gemini API，返回文本结果"""
    import urllib.request, urllib.error, ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for attempt in range(max_retries):
        key = keys[attempt % len(keys)]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": 65536}
        }).encode('utf-8')
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            # 使用代理
            proxy_handler = urllib.request.ProxyHandler({
                'http': 'http://127.0.0.1:10808',
                'https': 'http://127.0.0.1:10808'
            })
            opener = urllib.request.build_opener(proxy_handler, urllib.request.HTTPSHandler(context=ctx))
            resp = opener.open(req, timeout=180)
            data = json.loads(resp.read().decode('utf-8'))
            text = data['candidates'][0]['content']['parts'][0]['text']
            return text
        except Exception as e:
            print(f"  ⚠️ API 调用失败 (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
    return None

# ============ 学段配置 ============
STAGES = {
    '小学': {
        'grades': ['一上','一下','二上','二下','三上','三下','四上','四下','五上','五下','六上','六下'],
        'grade_full': {
            '一上':'一年级上册','一下':'一年级下册','二上':'二年级上册','二下':'二年级下册',
            '三上':'三年级上册','三下':'三年级下册','四上':'四年级上册','四下':'四年级下册',
            '五上':'五年级上册','五下':'五年级下册','六上':'六年级上册','六下':'六年级下册',
        },
        'subjects': ['数学','语文','英语'],
        'dir': '小学'
    }
}

# ============ 考卷专题 Prompt 模板 ============

# --- 数学 考卷卡 ---
EXAM_CARD_PROMPT_MATH = """你是一位拥有20年出题经验的小学数学命题研究员，同时是小红书教育赛道的爆款内容策划专家。
你深入研究了2020-2026年全国各地（北京、上海、江苏、浙江、广东等）数百份小学数学期中/期末真题试卷。

请为 **人教版数学 {grade_full}** 设计一套"考卷真题攻略"卡片（JSON格式），帮助学生精准备考。

## 6种考卷卡类型

### E1 - 填空满分卡 (fill_blank)
- 分析该年级填空题最常考的知识点和最易错的坑
- 提供"填空题审题三步法"：读→圈（关键词）→验
- 列出3-5个高频填空题型及其解题套路
- 特有字段 `fill_strategy`: 填空审题策略

### E2 - 选择秒杀卡 (choice_kill)  
- 总结选择题的4种干扰项设置套路（张冠李戴/偷换概念/计算陷阱/单位混淆）
- 提供快速排除法和代入法
- 特有字段 `choice_tricks`: 选择题秒杀技巧列表

### E3 - 计算零失误卡 (calc_perfect)
- 涵盖口算、竖式、脱式、简便运算
- 提供"计算三查法"：查符号→查进退位→查得数
- 列出该年级最常见的计算失误点
- 特有字段 `calc_checklist`: 计算检查清单

### E4 - 判断火眼卡 (judge_eye)
- 收集该年级判断题中最具迷惑性的命题
- 分析出题人设置陷阱的3种手法（绝对化用词/特殊情况/概念偷换）
- 特有字段 `judge_traps`: 判断题陷阱类型列表

### E5 - 应用题拆解卡 (word_problem)
- 按该年级常考应用题类型分类（行程/工程/比率/盈亏等，根据年级调整）
- 提供"应用题拆解四步法"：读题→画图→列式→验算
- 给出标准答题格式模板
- 特有字段 `problem_model`: 应用题建模方法

### E6 - 操作题规范卡 (operation)
- 涵盖画图、测量、统计图表等操作题
- 提供规范作图步骤和得分要点
- 特有字段 `operation_steps`: 操作规范步骤

## 卡片字段要求

每种类型2-3张卡片，每张卡包含：
- card_id: "E类型号-序号" 如 "E1-01"
- full_id: "数学-{grade_short}-E1-01"  
- title: 简短有冲击力的标题（≤15字，如"填空题4大隐形坑"）
- type: 卡片类型（填空满分卡/选择秒杀卡/计算零失误卡/判断火眼卡/应用题拆解卡/操作题规范卡）
- difficulty: 1-5
- importance: 1-5（按考试频率排）
- exam_frequency: 考试出现频率 "高/中/低"
- score_weight: 该题型在试卷中的典型分值占比（如"20-25%"）
- definition: 核心策略一句话
- core_points: 答题要点3-5条（每条≤15字）
- example: {{question: "真题示例", steps: ["解题步骤"], answer: "标准答案"}}（必须是真实考试风格的题目）
- mistakes: [{{wrong: "典型错误", correct: "正确做法"}}]（1-2个）
- memory_tip: 答题口诀/顺口溜
- emotion_hook: 小红书情绪钩子
- 各类型特有字段（见上）

## 重要约束
1. 知识点必须严格匹配 **人教版数学{grade_full}** 的教学范围，不超纲！
2. 例题必须是真实考试风格，不要编造不合理的题目
3. 低年级(1-2年级)无应用题拆解卡(E5)，改为"看图列式卡"；无操作题规范卡(E6)，改为"数数与排列卡"
4. 每张卡片文字精炼，适合做成小红书图文卡片

请直接输出JSON（不要markdown代码块），格式如下：
{{
  "subject": "数学",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "人教版",
  "grade_short": "{grade_short}",
  "card_pack": "考卷真题",
  "description": "基于真题分析的6种题型满分攻略卡片",
  "units": [
    {{
      "unit_id": "E1",
      "unit_name": "填空满分攻略",
      "cards": [...]
    }},
    {{
      "unit_id": "E2",
      "unit_name": "选择秒杀攻略",
      "cards": [...]
    }},
    {{
      "unit_id": "E3",
      "unit_name": "计算零失误攻略",
      "cards": [...]
    }},
    {{
      "unit_id": "E4",
      "unit_name": "判断火眼攻略",
      "cards": [...]
    }},
    {{
      "unit_id": "E5",
      "unit_name": "应用题拆解攻略",
      "cards": [...]
    }},
    {{
      "unit_id": "E6",
      "unit_name": "操作题规范攻略",
      "cards": [...]
    }}
  ]
}}
"""

# --- 语文 考卷卡 ---
EXAM_CARD_PROMPT_YUWEN = """你是一位拥有20年出题经验的小学语文命题研究员，同时是小红书教育赛道的爆款内容策划专家。
你深入研究了2020-2026年全国各地数百份小学语文期中/期末真题试卷。

请为 **统编版语文 {grade_full}** 设计一套"考卷真题攻略"卡片（JSON格式）。

## 6种考卷卡类型

### E1 - 拼写零错卡 (pinyin_write)
- 分析该册课文中"看拼音写词语"最高频考词和最易错字
- 提供"拼写三关法"：拼准音→想准字→写规范
- 列出本册10个必考高频词
- 特有字段 `high_freq_words`: 高频必考词语列表（含拼音）

### E2 - 选择审题卡 (choice_audit)
- 总结语文选择题的干扰项类型（字音混淆/字形相近/词义偷换/语法陷阱）
- 高年级增加修辞手法辨析、关联词选用等
- 特有字段 `audit_points`: 选择审题关键点列表

### E3 - 默写满分卡 (dictation)
- 本册必考古诗/名句/课文重点段落的默写清单
- 标注易错字（加粗/标红提示）
- 提供"默写防错三招"：理解意思→记住画面→特别留意易错字
- 特有字段 `must_dictate`: 必默篇目及易错字标注
- 注意：一二年级改为"课文填空卡"，内容为课文重点句填空

### E4 - 阅读答题卡 (reading_answer)
- 按题型分类提供阅读理解答题模板：
  - 概括主要内容（谁+在哪+做了什么+结果如何）
  - 理解词语含义（联系上下文+本义+引申义）
  - 体会句子含义（修辞手法+表达效果+作者情感）
  - 分析人物形象（事例+品质词）
- 特有字段 `answer_templates`: 各题型答题模板
- 注意：一二年级简化为"短文理解基础卡"

### E5 - 句子变换卡 (sentence_transform)
- 涵盖该年级要求的句子变换类型：
  - 低年级：把字句↔被字句
  - 中年级：+陈述句↔反问句、缩句扩句
  - 高年级：+直述句↔转述句、双重否定句
- 提供每种变换的"万能口诀"
- 特有字段 `transform_rules`: 句子变换规则列表

### E6 - 作文得分卡 (composition)
- 按该年级作文要求提供得分要素：
  - 低年级：看图写话（时间+地点+人物+事件+想法）
  - 中年级：命题作文（凤头+猪肚+豹尾结构）
  - 高年级：半命题/话题作文（立意+选材+详略+修辞）
- 提供"开头5法""结尾3招"的具体模板
- 特有字段 `writing_formulas`: 作文得分公式

## 卡片字段要求

每种类型2-3张卡片，每张卡包含：
- card_id: "E类型号-序号" 如 "E1-01"
- full_id: "语文-{grade_short}-E1-01"
- title: 简短有冲击力的标题（≤15字）
- type: 卡片类型（拼写零错卡/选择审题卡/默写满分卡/阅读答题卡/句子变换卡/作文得分卡）
- difficulty: 1-5
- importance: 1-5
- exam_frequency: "高/中/低"
- score_weight: 该题型分值占比
- definition: 核心策略一句话
- core_points: 答题要点3-5条
- example: {{question, steps[], answer}}
- mistakes: [{{wrong, correct}}]
- memory_tip: 答题口诀
- emotion_hook: 小红书钩子
- 各类型特有字段

## 约束
1. 严格匹配 **统编版语文{grade_full}** 教材范围
2. 古诗/课文引用必须准确
3. 一二年级侧重拼写和基础填空，无阅读理解深度分析
4. 文字精炼，适合小红书卡片呈现

请直接输出JSON（不要markdown代码块），格式如下：
{{
  "subject": "语文",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "统编版",
  "grade_short": "{grade_short}",
  "card_pack": "考卷真题",
  "description": "基于真题分析的6种题型满分攻略卡片",
  "units": [
    {{
      "unit_id": "E1",
      "unit_name": "拼写零错攻略",
      "cards": [...]
    }},
    ...E2到E6...
  ]
}}
"""

# --- 英语 考卷卡 ---
EXAM_CARD_PROMPT_ENGLISH = """你是一位拥有20年出题经验的小学英语命题研究员，同时是小红书教育赛道的爆款内容策划专家。
你深入研究了2020-2026年全国各地数百份小学英语期中/期末真题试卷。

请为 **人教版(PEP)英语 {grade_full}** 设计一套"考卷真题攻略"卡片（JSON格式）。

## 6种考卷卡类型

### E1 - 听力得分卡 (listening)
- 分析该年级听力题的3种常见题型（听音选图/听音判断/听音填空）
- 提供"听力黄金3秒"预读技巧
- 特有字段 `listening_strategy`: 听力答题策略

### E2 - 选择攻略卡 (choice_strategy)
- 总结英语选择题的高频考点（词汇辨析/语法选用/情景交际）
- 提供排除法和语感判断技巧
- 特有字段 `choice_focus`: 高频选择题考点列表

### E3 - 填空必会卡 (fill_master)
- 列出该册必考高频词汇和句型的填空题型
- 提供单词拼写检查法和语法填空策略
- 特有字段 `must_know_words`: 必会词汇清单

### E4 - 匹配速解卡 (match_solve)
- 分析图文匹配、问答匹配的快速解题法
- 提供"先易后难+排除法"策略
- 特有字段 `match_method`: 匹配题解题方法

### E5 - 阅读通关卡 (reading_pass)
- 提供英语阅读理解的"关键词定位法"
- 按题型分类：细节查找/判断正误/主旨理解
- 特有字段 `reading_skills`: 阅读理解技巧列表

### E6 - 写作模板卡 (writing_template)
- 按年级提供写作题型模板：
  - 三四年级：抄写/补全句子/看图写1-2句话
  - 五六年级：看图写话/小短文/自我介绍/描述日常
- 提供万能句型和连接词
- 特有字段 `writing_frames`: 写作框架模板

## 卡片字段要求

每种类型2-3张卡片，每张卡包含：
- card_id: "E类型号-序号" 如 "E1-01"
- full_id: "英语-{grade_short}-E1-01"
- title: 简短有冲击力的标题（≤15字）
- type: 卡片类型（听力得分卡/选择攻略卡/填空必会卡/匹配速解卡/阅读通关卡/写作模板卡）
- difficulty: 1-5
- importance: 1-5
- exam_frequency: "高/中/低"
- score_weight: 分值占比
- definition: 核心策略一句话
- core_points: 答题要点3-5条
- example: {{question, steps[], answer}}
- mistakes: [{{wrong, correct}}]
- memory_tip: 口诀
- emotion_hook: 小红书钩子
- 各类型特有字段

## 约束
1. 严格匹配 **人教版(PEP)英语{grade_full}** 教材范围
2. 小学英语从三年级开始，三四年级侧重词汇和基础句型
3. 听力题描述要具体（因为是文字卡片，需要描述听力场景和策略）
4. 文字简洁，中英结合

请直接输出JSON（不要markdown代码块），格式如下：
{{
  "subject": "英语",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "人教版(PEP)",
  "grade_short": "{grade_short}",
  "card_pack": "考卷真题",
  "description": "基于真题分析的6种题型满分攻略卡片",
  "units": [
    {{
      "unit_id": "E1",
      "unit_name": "听力得分攻略",
      "cards": [...]
    }},
    ...E2到E6...
  ]
}}
"""

# 按学科选择考卷卡模板
EXAM_CARD_PROMPTS = {
    '数学': EXAM_CARD_PROMPT_MATH,
    '语文': EXAM_CARD_PROMPT_YUWEN,
    '英语': EXAM_CARD_PROMPT_ENGLISH,
}

def extract_json(text):
    """从API返回文本中提取JSON"""
    text = re.sub(r'^```json\s*', '', text.strip())
    text = re.sub(r'^```\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        text = text[start:end+1]
    return json.loads(text)

def get_grade_info(stage_name, grade_short):
    """获取年级的完整信息"""
    stage = STAGES[stage_name]
    grade_full = stage['grade_full'].get(grade_short, grade_short)
    if '上' in grade_short:
        semester = '上册'
        grade_name = grade_full.replace('上册','').replace('上学期','')
    elif '下' in grade_short:
        semester = '下册'
        grade_name = grade_full.replace('下册','').replace('下学期','')
    else:
        semester = '全册'
        grade_name = grade_full
    return grade_full, grade_name, semester

def generate_exam_cards(stage_name, grade_short, subject, keys):
    """为指定年级学科生成考卷真题卡"""
    stage = STAGES[stage_name]
    grade_full, grade_name, semester = get_grade_info(stage_name, grade_short)

    # 英语从三年级开始
    if subject == '英语' and grade_short in ['一上','一下','二上','二下']:
        print(f"  ⏭️  {subject} {grade_short}: 英语从三年级开始，跳过")
        return None

    output_dir = os.path.join(BASE_DIR, 'public', 'knowledge_cards', stage['dir'])
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, f'{subject}_{grade_short}_考卷.json')

    if os.path.exists(output_file):
        print(f"  ⏭️  已存在: {output_file}，跳过")
        return output_file

    print(f"\n{'='*60}")
    print(f"  📝 生成 {stage_name} {subject} {grade_full} 考卷真题卡")
    print(f"{'='*60}")

    template = EXAM_CARD_PROMPTS.get(subject)
    if not template:
        print(f"  ❌ 不支持学科: {subject}")
        return None

    prompt = template.format(
        stage=stage_name,
        subject=subject,
        grade_full=grade_full,
        grade_name=grade_name,
        semester=semester,
        grade_short=grade_short,
    )

    print(f"  📤 调用 Gemini API (考卷真题专题)...")
    text = call_gemini(prompt, keys, temperature=0.7)
    if not text:
        print(f"  ❌ API 调用失败，跳过 {grade_short}")
        return None

    try:
        data = extract_json(text)
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON 解析失败: {e}")
        err_file = output_file.replace('.json', '_raw.txt')
        with open(err_file, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"  📄 原始响应已保存: {err_file}")
        return None

    # 统计
    total_cards = sum(len(u.get('cards', [])) for u in data.get('units', []))
    total_units = len(data.get('units', []))

    # 保存
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  ✅ 生成完成: {total_units} 个题型, {total_cards} 张卡片")
    print(f"  📁 保存至: {output_file}")

    return output_file

def main():
    parser = argparse.ArgumentParser(description='生成考卷真题专题卡片')
    parser.add_argument('--stage', default='小学', choices=['小学'], help='学段（目前支持小学）')
    parser.add_argument('--subject', default='数学', help='学科（数学/语文/英语）')
    parser.add_argument('--grade', default=None, help='指定年级 (如 三下)，不指定则生成全部')
    parser.add_argument('--all', action='store_true', help='生成所有学科全年级')
    parser.add_argument('--delay', type=int, default=8, help='每次API调用间隔秒数')
    args = parser.parse_args()

    keys = load_keys()
    stage = STAGES[args.stage]

    print(f"""
╔══════════════════════════════════════════════╗
║   📝 考卷真题专题卡片生成器                    ║
║   学段: {args.stage}  学科: {args.subject}              ║
║   API Keys: {len(keys)} 个                          ║
╚══════════════════════════════════════════════╝
""")

    subjects = stage['subjects'] if args.all else [args.subject]
    grades = [args.grade] if args.grade else stage['grades']

    results = []
    for subject in subjects:
        for i, grade in enumerate(grades):
            result = generate_exam_cards(args.stage, grade, subject, keys)
            results.append((subject, grade, result))

            if result and (i < len(grades) - 1 or subject != subjects[-1]):
                print(f"\n  ⏳ 等待 {args.delay} 秒...")
                time.sleep(args.delay)

    # 汇总
    print(f"\n{'='*60}")
    print(f"  📊 生成汇总")
    print(f"{'='*60}")
    success = sum(1 for _, _, r in results if r)
    for subject, grade, result in results:
        status = '✅' if result else '⏭️ '
        print(f"  {status} {subject}_{grade}_考卷")
    print(f"\n  总计: {len(results)} 项, {success} 个成功生成")

if __name__ == '__main__':
    main()
