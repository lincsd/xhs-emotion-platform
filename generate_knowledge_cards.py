#!/usr/bin/env python3
"""
批量生成知识卡片 — 全学段 × 全学科
=================================
使用 Gemini API 按人教版教材大纲，生成结构化知识卡片 JSON。

用法:
  python generate_knowledge_cards.py                     # 生成小学数学全年级
  python generate_knowledge_cards.py --stage 小学         # 同上
  python generate_knowledge_cards.py --stage 初中         # 生成初中数学全年级
  python generate_knowledge_cards.py --grade 四上          # 只生成四年级上册
  python generate_knowledge_cards.py --subject 语文       # 生成小学语文
  python generate_knowledge_cards.py --stage 小学 --subject 语文 --grade 二上
  python generate_knowledge_cards.py --boom 四上          # 为四上生成爆款卡
"""

import os, sys, json, time, re, argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============ API 配置 ============
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

def call_gemini(prompt, keys, model="gemini-2.5-flash", temperature=0.7, max_retries=5):
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
            resp = urllib.request.urlopen(req, timeout=300, context=ctx)
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
    },
    '初中': {
        'grades': ['七上','七下','八上','八下','九上','九下'],
        'grade_full': {
            '七上':'七年级上册','七下':'七年级下册','八上':'八年级上册','八下':'八年级下册',
            '九上':'九年级上册','九下':'九年级下册',
        },
        'subjects': ['数学','语文','英语','物理','化学'],
        'dir': '初中'
    },
    '高中': {
        'grades': ['高一上','高一下','高二上','高二下','高三'],
        'grade_full': {
            '高一上':'高一上学期','高一下':'高一下学期','高二上':'高二上学期','高二下':'高二下学期',
            '高三':'高三总复习',
        },
        'subjects': ['数学','语文','英语','物理','化学','生物'],
        'dir': '高中'
    }
}

# ============ Prompt 模板 ============

# --- 数学 标准卡 ---
CARD_GEN_PROMPT_MATH = """你是一位资深的中国{stage}{subject}教研员，精通人教版教材。
请为 **人教版{subject} {grade_full}** 生成一套完整的知识卡片（JSON格式）。

要求：
1. 按教材单元编排，每个单元3-6张卡片
2. 卡片类型包括：概念卡、方法卡、公式卡、辨析卡（根据学科灵活选用）
3. 每张卡片必须包含以下字段：
   - card_id: 格式 "单元号-序号" 如 "01-01"
   - full_id: 格式 "{subject}-{grade_short}-01-01"
   - title: 知识点名称
   - type: 卡片类型
   - difficulty: 难度 1-5
   - importance: 重要性 1-5
   - definition: 核心定义/概念（一句话）
   - core_points: 要点列表（3-5条）
   - why_explanation: 本质原因/底层逻辑（用通俗语言解释"为什么是这样"，而非只告诉结论）
   - example: {{question, steps[], answer}}
   - mistakes: [{{wrong: "常见错误做法", correct: "正确做法", reason: "为什么这样做是错的（一句话解释根本原因）"}}]（1-2个常见错误）
   - memory_tip: 记忆口诀/助记
   - related: {{prerequisite, next}}

4. 知识点要覆盖该册教材的所有主要单元
5. 难度和重要性要符合实际教学情况
6. 例题要典型、易懂，步骤清晰
7. 记忆口诀要朗朗上口
8. ⚠️ 深度教学原则（非常重要！）：
   - 每张卡片必须回答"为什么"，不能只告诉"是什么"和"怎么做"
   - why_explanation 必须解释知识点的本质原因（例如：为什么乘法交换律成立？因为3组4个和4组3个的总数相同）
   - mistakes的reason必须解释错误的根本原因，不能只标注对错（例如：不是只说"应该用×不是÷"，而要说"因为'每组3个，5组'是重复相加，所以用乘法"）
   - 步骤(steps)中至少有一步解释"为什么这样做"而非只说"怎么做"
   - 记忆口诀不能为了押韵而牺牲准确性，必须涵盖关键例外情况

请直接输出完整JSON（不要markdown代码块），格式如下：
{{
  "subject": "{subject}",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "人教版",
  "grade_short": "{grade_short}",
  "units": [
    {{
      "unit_id": "01",
      "unit_name": "单元名称",
      "cards": [...]
    }}
  ]
}}
"""

# --- 语文 标准卡 ---
CARD_GEN_PROMPT_YUWEN = """你是一位资深的中国{stage}语文教研员，精通统编版（部编版）语文教材。
请为 **统编版语文 {grade_full}** 生成一套完整的知识卡片（JSON格式）。

要求：
1. 按教材单元编排，每个单元3-6张卡片
2. 卡片类型包括（根据年级灵活选用）：
   - **易错字卡**: 本单元最容易写错/混淆的汉字，含正确写法、笔顺要点、易错部分标注
   - **多音字卡**: 多音字辨析，列出不同读音及对应词语、例句
   - **词语辨析卡**: 近义词/形近字辨析，区分用法和语境
   - **古诗理解卡**: 古诗/古文的重点字词翻译、主题思想、作者背景（三年级及以上）
   - **阅读技巧卡**: 阅读理解答题方法，归纳中心思想/人物描写/修辞手法识别等
   - **写作方法卡**: 写作技巧，如开头方法、过渡句、细节描写、总分总结构等
   - **修辞手法卡**: 比喻、拟人、排比、夸张等修辞手法辨析及仿写（三年级及以上）
   - **标点符号卡**: 标点符号用法辨析（低年级侧重）
   - **成语卡**: 重点成语的含义、出处、易错用法
   - **拼音卡**: 声母韵母整体认读/拼读规则（一二年级侧重）

3. 每张卡片必须包含以下字段：
   - card_id: 格式 "单元号-序号" 如 "01-01"
   - full_id: 格式 "语文-{grade_short}-01-01"
   - title: 知识点名称（如"易错字：已vs己"、"古诗：静夜思"）
   - type: 卡片类型（易错字卡/多音字卡/词语辨析卡/古诗理解卡/阅读技巧卡/写作方法卡/修辞手法卡/标点符号卡/成语卡/拼音卡）
   - difficulty: 难度 1-5
   - importance: 重要性 1-5
   - definition: 核心知识点（一句话概括）
   - core_points: 要点列表（3-5条）
   - why_explanation: 本质原因/底层逻辑（用通俗语言解释"为什么是这样"，如：为什么"己"和"已"容易混？因为只差一笔封口，"己"开口像张开的自己，"已"封口表示已经完成）
   - example: {{question, steps[], answer}}（示例题目或练习）
   - mistakes: [{{wrong: "常见错误", correct: "正确写法/用法", reason: "为什么这样是错的（根本原因）"}}]（1-2个常见错误）
   - memory_tip: 记忆口诀/顺口溜/助记方法
   - related: {{prerequisite, next}}

4. 知识点要覆盖该册教材的所有主要单元
5. 一二年级侧重拼音卡、易错字卡、标点符号卡；三四年级增加古诗理解卡、修辞手法卡；五六年级增加阅读技巧卡、写作方法卡
6. 例题要贴合课文内容，步骤清晰
7. 记忆口诀要朗朗上口，适合小学生记忆
8. ⚠️ 深度教学原则（非常重要！）：
   - 每张卡片必须回答"为什么"，不能只告诉"是什么"
   - why_explanation 要用孩子能懂的比喻解释本质（如：比喻句为什么生动？因为把陌生事物变成了你熟悉的东西，大脑自动"看到"画面）
   - mistakes的reason必须解释根本原因（如：不是只说"应写'已'不是'己'"，而要说"因为'已经'表示完成、封住了，所以上面那笔要封口"）
   - 修辞手法/阅读技巧类卡片必须解释"为什么这种方法有效"而非只给模板

请直接输出完整JSON（不要markdown代码块），格式如下：
{{
  "subject": "语文",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "统编版",
  "grade_short": "{grade_short}",
  "units": [
    {{
      "unit_id": "01",
      "unit_name": "单元名称",
      "cards": [...]
    }}
  ]
}}
"""

# --- 通用 fallback ---
CARD_GEN_PROMPT = CARD_GEN_PROMPT_MATH

# --- 英语 标准卡 ---
CARD_GEN_PROMPT_ENGLISH = """你是一位资深的中国{stage}英语教研员，精通人教版英语教材体系（小学PEP/初中Go for it!/高中人教版新课标）。
请为 **{grade_full} 英语** 生成一套【知识点全覆盖】的知识卡片（JSON格式）。

⚠️ 核心原则：知识点必须穷举，宁多勿少！
- 每个单元的【所有词汇、所有语法点、所有句型、所有语音规则】都必须有对应卡片
- 不限数量，一个单元如果有10个知识点就出10张卡，有20个就出20张
- 绝对不能为了控制数量而遗漏任何教材涉及的知识点

要求：
1. 按教材单元编排，每个单元不限卡片数量（务必覆盖单元所有知识点，通常需要8-15张甚至更多）
2. 卡片类型（根据学段和年级灵活选用）：

   ### 基础类（所有学段必须覆盖）:
   - **词汇卡**: 本单元【全部】重点单词/短语（不是挑几个，是全部！），按主题分组（食物类/动物类/动作类等），每组一张卡。含音标、词性、例句、记忆方法
   - **语法卡**: 本单元涉及的【每一个】语法点都要单独出卡。含结构规则、变化规律、肯/否/疑/特殊疑问句变形
   - **句型卡**: 本单元【所有】重要句型结构，含模板句、替换词练习、实际运用
   - **易混词卡**: 本单元出现的所有容易混淆的词汇/用法对比

   ### 小学侧重（三~六年级额外增加）:
   - **自然拼读卡**: 每个单元涉及的字母/字母组合发音规则（三四年级侧重）
   - **情景对话卡**: 本单元话题相关的实用对话场景
   - **不规则动词卡**: 不规则动词过去式/过去分词变化（五六年级）

   ### 初中增加（七~九年级额外增加）:
   - **时态卡**: 一般现在/过去/将来、现在/过去进行、现在/过去完成、过去将来时——每种时态的构成、标志词、用法区分
   - **从句卡**: 宾语从句、定语从句、状语从句的引导词、语序、时态呼应
   - **词法卡**: 词性转换（名→形→副）、前后缀规则、合成词
   - **写作卡**: 书面表达常用句型、连接词、篇章结构
   - **不规则动词卡**: 按变化规律分组（AAA/ABB/ABC/ABA型）

   ### 高中增加（高一~高三额外增加）:
   - **高级语法卡**: 虚拟语气、倒装句、强调句、省略句、独立主格
   - **从句进阶卡**: 非限制性定语从句、名词性从句、让步/条件/目的状语从句
   - **词汇深度卡**: 一词多义、熟词生义、高频搭配、词根词缀
   - **阅读技巧卡**: 主旨大意、推理判断、词义猜测、篇章结构
   - **写作进阶卡**: 高级句式替换、衔接过渡、观点论证模板

3. 每张卡片必须包含以下字段：
   - card_id: 格式 "单元号-序号" 如 "01-01"
   - full_id: 格式 "英语-{grade_short}-01-01"
   - title: 知识点名称（如"词汇：食物类单词"、"语法：一般过去时的构成与用法"）
   - type: 卡片类型
   - difficulty: 难度 1-5
   - importance: 重要性 1-5
   - definition: 核心知识点（一句话概括）
   - core_points: 要点列表（3-8条，知识点多的卡可以更多）
   - why_explanation: 底层逻辑（解释"为什么英语这样说/这样变化"，不能只说"规则如此"）
   - example: {{question, steps[], answer}}
   - mistakes: [{{wrong, correct, reason: "根本原因"}}]（1-3个常见错误，必须是完整句子对比）
   - memory_tip: 记忆口诀/助记（禁止"搭配固定""多练就会"这类废话，必须有巧妙联想）
   - related: {{prerequisite, next}}

4. 【全覆盖检查清单】每个单元生成完后，自查是否遗漏了：
   □ 该单元的全部新词汇（每个单词都要出现在某张卡里）
   □ 该单元涉及的每一个语法点
   □ 该单元的核心句型和变换
   □ 该单元容易混淆/出错的知识点
   □ 该单元的语音/发音规则（小学适用）
5. 知识点准确性第一：不能把正确用法标为错误！每个正误标注必须反复检查
6. why_explanation必须解释底层逻辑，每个语法卡必须包含肯定句、否定句、疑问句的完整变形示例
7. 例题要典型实用，步骤中至少一步解释"为什么这样做"
请直接输出完整JSON（不要markdown代码块），格式如下：
{{
  "subject": "英语",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "人教版",
  "grade_short": "{grade_short}",
  "units": [
    {{
      "unit_id": "01",
      "unit_name": "单元名称",
      "cards": [...]
    }}
  ]
}}
"""

# 按学科选择标准卡模板
CARD_GEN_PROMPTS = {
    '数学': CARD_GEN_PROMPT_MATH,
    '语文': CARD_GEN_PROMPT_YUWEN,
    '英语': CARD_GEN_PROMPT_ENGLISH,
}

# --- 数学 爆款卡 ---
BOOM_CARD_PROMPT_MATH = """你是一位小红书教育类爆款内容策划专家，同时精通人教版{stage}{subject}教材。
请为 **人教版{subject} {grade_full}** 设计一套爆款知识卡片（JSON格式），用于生成高传播力的小红书笔记。

爆款卡类型（共6种）：
1. **陷阱卡** (T1): 学生/家长最容易犯的错误，制造"你也做错了吗？"的冲突感
2. **速算卡** (T2): 巧妙的速算技巧，制造"原来还能这么算？"的惊喜
3. **挑战卡** (T3): 设计挑战题，"你能xx秒内做完吗？"的互动
4. **生活卡** (T4): 数学在生活中的应用，"原来买菜也要用到这个？"
5. **对战卡** (T5): 家长vs孩子的PK题，制造家庭互动场景
6. **思维卡** (T6): 思维拓展题，"学霸才能想到的解法"

每种类型2-3张卡片。每张卡片需包含：
- card_id: "T类型号-序号" 如 "T1-01"
- full_id: "{subject}-{grade_short}-T1-01"
- title: 简短有冲击力的标题
- type: 具体类型名（陷阱卡/速算卡/挑战卡/生活卡/对战卡/思维卡）
- difficulty: 1-5
- importance: 1-5
- definition: 核心知识点
- core_points: 要点3-5条
- why_explanation: 本质原因/底层逻辑（解释"为什么会错/为什么要这样做"，让学生真正理解而非死记）
- example: {{question, steps[], answer}}
- mistakes: [{{wrong, correct, reason: "为什么这样做是错的（根本原因）"}}]
- memory_tip: 口诀
- emotion_hook: 情绪钩子（一句话引发好奇或共鸣）
- trap_point / speed_tip / challenge_rule / life_scene / battle_rule / think_expand: 对应类型的特有字段

知识点必须准确，符合该年级教材范围！不要超纲！
⚠️ 深度教学：每张卡片的why_explanation和mistakes.reason必须解释根本原因，不能只标注对错！陷阱卡要解释"为什么会踩这个坑"，速算卡要解释"为什么这个巧算成立"。

请直接输出JSON（不要markdown代码块），格式如下：
{{
  "subject": "{subject}",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "人教版",
  "grade_short": "{grade_short}",
  "card_pack": "爆款卡片",
  "description": "面向小红书传播优化的6种新题型卡片",
  "units": [
    {{
      "unit_id": "T1",
      "unit_name": "陷阱题集",
      "cards": [...]
    }},
    ...T2到T6...
  ]
}}
"""

# --- 语文 爆款卡 ---
BOOM_CARD_PROMPT_YUWEN = """你是一位小红书教育类爆款内容策划专家，同时精通统编版（部编版）{stage}语文教材。
请为 **统编版语文 {grade_full}** 设计一套爆款知识卡片（JSON格式），用于生成高传播力的小红书笔记。

爆款卡类型（共6种）：
1. **易错字陷阱卡** (T1): 本册最容易写错的字/词，制造"10个孩子9个写错！"的冲突感。展示错误写法vs正确写法，标注易错部首/笔画。
2. **多音字辨析卡** (T2): 最容易读错的多音字，制造"这个字你读对了吗？"的惊喜。给出不同读音和对应词语。
3. **古诗默写挑战卡** (T3): 古诗填空/默写挑战，"你能不看书写出来吗？"的互动。挖空关键字让用户填写。（三年级及以上）
4. **成语纠错卡** (T4): 成语误用场景，"这些成语你一直用错了！"。给出常见误用例句，引导正确理解。（三年级及以上）
5. **亲子古诗PK卡** (T5): 家长vs孩子的诗词PK题，"妈妈居然输给了二年级的娃！"。设计适合亲子互动的诗词抢答。
6. **阅读理解技巧卡** (T6): 阅读理解答题万能公式，"背下这个模板，阅读理解不丢分！"。给出分题型的答题模板和技巧。（三年级及以上）

注意：一二年级没有古诗默写挑战卡(T3)、成语纠错卡(T4)、阅读理解技巧卡(T6)的，可以替换为：
- **拼音闯关卡** (T3替代): 拼音拼读挑战，"这些拼音你能全拼对吗？"
- **笔顺挑战卡** (T4替代): 笔顺易错字，"这个字的笔顺你写对了吗？"
- **看图写话卡** (T6替代): 看图说话/写话引导，"用3句话描述这幅图"

每种类型2-3张卡片。每张卡片需包含：
- card_id: "T类型号-序号" 如 "T1-01"
- full_id: "语文-{grade_short}-T1-01"
- title: 简短有冲击力的标题（如"这个字全班80%写错！"）
- type: 具体类型名（易错字陷阱卡/多音字辨析卡/古诗默写挑战卡/成语纠错卡/亲子古诗PK卡/阅读理解技巧卡，或低年级替代类型）
- difficulty: 1-5
- importance: 1-5
- definition: 核心知识点
- core_points: 要点3-5条
- why_explanation: 本质原因/底层逻辑（解释"为什么会错/为什么是这样"，如：为什么"己"和"已"容易混？因为只差一笔封口）
- example: {{question, steps[], answer}}
- mistakes: [{{wrong, correct, reason: "为什么这样是错的（根本原因）"}}]
- memory_tip: 口诀/顺口溜
- emotion_hook: 情绪钩子（一句话引发好奇或共鸣，如"看完这张卡，默写不丢分！"）
- trap_point / pinyin_tip / challenge_rule / idiom_correction / battle_rule / reading_formula: 对应类型的特有字段

知识点必须准确，符合该年级统编版教材范围！不要超纲！
⚠️ 深度教学：每张卡片的why_explanation和mistakes.reason必须解释根本原因，不能只标注对错！易错字要解释"为什么这个部首/笔画容易错"，多音字要解释"为什么这个词语里读这个音"。

请直接输出JSON（不要markdown代码块），格式如下：
{{
  "subject": "语文",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "统编版",
  "grade_short": "{grade_short}",
  "card_pack": "爆款卡片",
  "description": "面向小红书传播优化的6种语文爆款题型卡片",
  "units": [
    {{
      "unit_id": "T1",
      "unit_name": "易错字陷阱",
      "cards": [...]
    }},
    ...T2到T6...
  ]
}}
"""

# 通用 fallback
BOOM_CARD_PROMPT = BOOM_CARD_PROMPT_MATH

# --- 英语 爆款卡 ---
BOOM_CARD_PROMPT_ENGLISH = """你是一位小红书教育类爆款内容策划专家，同时精通人教版{stage}英语教材体系。
请为 **{grade_full} 英语** 设计一套【知识点全覆盖】的爆款知识卡片（JSON格式），用于生成高传播力的小红书笔记。

⚠️ 核心原则：知识点必须穷举，覆盖该年级该学期的所有重要知识点！
- 每种爆款类型下，要把该学期涉及的所有相应知识点都做成卡片
- 不限数量，宁多勿少

爆款卡类型（共6种，根据学段灵活调整内容深度）：
1. **易混词陷阱卡** (T1): 该学期所有容易混淆的单词/用法/语法结构，每对易混内容一张卡
2. **发音挑战卡** (T2): 该学期所有容易读错的单词/音标/连读规则
3. **情景闯关卡** (T3): 该学期涉及的所有话题场景的实际运用挑战
4. **语法纠错卡** (T4): 该学期所有语法点的常见错误（初高中覆盖每个时态/从句/特殊句式的典型错误）
5. **PK挑战卡** (T5): 小学为亲子PK，初高中为同学PK/考试真题挑战
6. **速记卡** (T6): 该学期所有需要记忆的内容的高效记忆法（词汇/语法/句型/不规则动词等）

每种类型不限数量（覆盖该学期所有对应知识点）。每张卡片需包含：
- card_id: "T类型号-序号" 如 "T1-01"
- full_id: "英语-{grade_short}-T1-01"
- title: 简短有冲击力的标题
- type: 具体类型名
- difficulty: 1-5
- importance: 1-5
- definition: 核心知识点
- core_points: 要点3-8条
- why_explanation: 底层逻辑（解释"为什么会混/为什么容易错"）
- example: {{question, steps[], answer}}
- mistakes: [{{wrong, correct, reason: "根本原因"}}]（完整句子对比）
- memory_tip: 口诀/顺口溜（禁止废话口诀）
- emotion_hook: 情绪钩子
- trap_point / pronunciation_tip / scene_dialogue / grammar_fix / battle_rule / speed_method: 对应类型的特有字段

知识点必须准确，符合该年级教材范围！
请直接输出JSON（不要markdown代码块），格式如下：
{{
  "subject": "英语",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "人教版",
  "grade_short": "{grade_short}",
  "card_pack": "爆款卡片",
  "description": "面向小红书传播优化的6种英语爆款题型卡片（全知识点覆盖版）",
  "units": [
    {{
      "unit_id": "T1",
      "unit_name": "易混词陷阱",
      "cards": [...]
    }},
    ...T2到T6...
  ]
}}
"""

# 按学科选择爆款卡模板
BOOM_CARD_PROMPTS = {
    '数学': BOOM_CARD_PROMPT_MATH,
    '语文': BOOM_CARD_PROMPT_YUWEN,
    '英语': BOOM_CARD_PROMPT_ENGLISH,
}

def extract_json(text):
    """从API返回文本中提取JSON，支持修复截断/尾逗号等常见问题"""
    # 去掉可能的 markdown 代码块
    text = re.sub(r'^```json\s*', '', text.strip())
    text = re.sub(r'^```\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    # 找到第一个 {
    start = text.find('{')
    if start < 0:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    text = text[start:]

    # 修复1: 去除尾逗号 (trailing comma before } or ])
    cleaned = re.sub(r',(\s*[}\]])', r'\1', text)

    # 尝试直接解析
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 修复2: 处理截断的JSON（API输出被截断导致JSON不完整）
    # 策略: 找到最后一个完整的unit对象 }]} 然后关闭外层 ]}
    import re as _re
    unit_ends = [m.end() for m in _re.finditer(r'\}\s*\]\s*\}', cleaned)]
    
    for end_pos in reversed(unit_ends):
        candidate = cleaned[:end_pos] + '\n  ]\n}'
        candidate = re.sub(r',(\s*[}\]])', r'\1', candidate)
        try:
            data = json.loads(candidate)
            n_units = len(data.get('units', []))
            n_cards = sum(len(u.get('cards', [])) for u in data.get('units', []))
            print(f"  ⚠️ JSON被截断，已自动修复（保留 {n_units} 个完整单元, {n_cards} 张卡片）")
            return data
        except json.JSONDecodeError:
            continue
    
    # 修复3: 更暴力的方法 - 逐步缩短直到解析成功
    truncated = cleaned.rstrip()
    last_close = max(truncated.rfind('}'), truncated.rfind(']'))
    if last_close > 0:
        truncated = truncated[:last_close + 1]
    ob = truncated.count('{') - truncated.count('}')
    oq = truncated.count('[') - truncated.count(']')
    truncated += ']' * max(0, oq) + '}' * max(0, ob)
    truncated = re.sub(r',(\s*[}\]])', r'\1', truncated)
    
    try:
        data = json.loads(truncated)
        print(f"  ⚠️ JSON已自动修复截断问题（补齐括号）")
        return data
    except json.JSONDecodeError as e:
        raise e

def get_grade_info(stage_name, grade_short, subject):
    """获取年级的完整信息"""
    stage = STAGES[stage_name]
    grade_full = stage['grade_full'].get(grade_short, grade_short)
    # 解析年级名和学期
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

def generate_cards(stage_name, grade_short, subject, keys, boom=False):
    """为指定年级学科生成知识卡"""
    stage = STAGES[stage_name]
    grade_full, grade_name, semester = get_grade_info(stage_name, grade_short, subject)
    
    card_type = "爆款" if boom else "知识"
    output_dir = os.path.join(BASE_DIR, 'knowledge_cards', stage['dir'])
    os.makedirs(output_dir, exist_ok=True)
    
    suffix = '_爆款' if boom else ''
    output_file = os.path.join(output_dir, f'{subject}_{grade_short}{suffix}.json')
    
    if os.path.exists(output_file):
        print(f"  ⏭️  已存在: {output_file}，跳过")
        return output_file
    
    print(f"\n{'='*60}")
    print(f"  🎯 生成 {stage_name} {subject} {grade_full} {card_type}卡片")
    print(f"{'='*60}")
    
    template = BOOM_CARD_PROMPTS.get(subject, BOOM_CARD_PROMPT) if boom else CARD_GEN_PROMPTS.get(subject, CARD_GEN_PROMPT)
    prompt = template.format(
        stage=stage_name,
        subject=subject,
        grade_full=grade_full,
        grade_name=grade_name,
        semester=semester,
        grade_short=grade_short,
    )
    
    print(f"  📤 调用 Gemini API...")
    text = call_gemini(prompt, keys, temperature=0.7)
    if not text:
        print(f"  ❌ API 调用失败，跳过 {grade_short}")
        return None
    
    try:
        data = extract_json(text)
    except json.JSONDecodeError as e:
        print(f"  ❌ JSON 解析失败: {e}")
        # 保存原始响应用于调试
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
    
    print(f"  ✅ 生成完成: {total_units} 个单元, {total_cards} 张卡片")
    print(f"  📁 保存至: {output_file}")
    
    return output_file

def main():
    parser = argparse.ArgumentParser(description='批量生成知识卡片')
    parser.add_argument('--stage', default='小学', choices=['小学','初中','高中'], help='学段')
    parser.add_argument('--subject', default='数学', help='学科')
    parser.add_argument('--grade', default=None, help='指定年级 (如 四上)，不指定则生成全部')
    parser.add_argument('--boom', default=None, help='为指定年级生成爆款卡 (如 --boom 四上)')
    parser.add_argument('--boom-all', action='store_true', help='为所有年级生成爆款卡')
    parser.add_argument('--delay', type=int, default=5, help='每次API调用间隔秒数')
    args = parser.parse_args()
    
    keys = load_keys()
    stage = STAGES[args.stage]
    
    print(f"""
╔══════════════════════════════════════════════╗
║   📚 知识卡片批量生成器                       ║
║   学段: {args.stage}  学科: {args.subject}              ║
║   API Keys: {len(keys)} 个                          ║
╚══════════════════════════════════════════════╝
""")
    
    # 爆款卡模式
    if args.boom:
        generate_cards(args.stage, args.boom, args.subject, keys, boom=True)
        return
    
    # 确定要生成的年级列表
    if args.grade:
        grades = [args.grade]
    else:
        grades = stage['grades']
    
    results = []
    for i, grade in enumerate(grades):
        result = generate_cards(args.stage, grade, args.subject, keys, boom=False)
        results.append((grade, result))
        
        # 如果也需要爆款卡
        if args.boom_all:
            generate_cards(args.stage, grade, args.subject, keys, boom=True)
        
        # API 调用间隔
        if i < len(grades) - 1 and result:
            print(f"\n  ⏳ 等待 {args.delay} 秒...")
            time.sleep(args.delay)
    
    # 汇总
    print(f"\n{'='*60}")
    print(f"  📊 生成汇总")
    print(f"{'='*60}")
    success = sum(1 for _, r in results if r)
    skip = sum(1 for _, r in results if r and '跳过' not in str(r))
    for grade, result in results:
        status = '✅' if result else '❌'
        print(f"  {status} {args.subject}_{grade}")
    print(f"\n  总计: {len(results)} 个年级, {success} 个成功")

if __name__ == '__main__':
    main()
