#!/usr/bin/env python3
"""
批量生成「初中+高中 考点笔记总结」卡片
======================================
扩展小学版，新增初中(七~九年级)和高中(高一~高三) 语数英考点卡片。
每张卡片含 exam_focus 字段，对标中考/高考。

用法:
  python _gen_summary_middle_high.py                              # 全部(跳过已有)
  python _gen_summary_middle_high.py --stage 初中                 # 仅初中
  python _gen_summary_middle_high.py --stage 高中                 # 仅高中
  python _gen_summary_middle_high.py --stage 初中 --subject 数学  # 初中数学
  python _gen_summary_middle_high.py --stage 初中 --subject 数学 --grade 八上  # 单册
  python _gen_summary_middle_high.py --force                      # 强制覆盖
"""

import os, sys, json, time, re, argparse, shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============ API 配置 ============
def load_keys():
    kp = os.path.join(BASE_DIR, 'api_key.txt')
    if not os.path.exists(kp):
        print("❌ api_key.txt 不存在"); sys.exit(1)
    keys = []
    for line in open(kp, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#'): continue
        if line.startswith('GEMINI_API_KEY='):
            val = line.split('=', 1)[1]
            keys.extend([k.strip() for k in val.split(',') if k.strip()])
    if not keys:
        print("❌ api_key.txt 中无有效 Gemini Key"); sys.exit(1)
    return keys

_call_count = 0

def call_gemini(prompt, keys, model="gemini-2.5-flash", temperature=0.7, max_retries=3):
    global _call_count
    import urllib.request, urllib.error, ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for attempt in range(max_retries):
        _call_count += 1
        key = keys[_call_count % len(keys)]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": 65536}
        }).encode('utf-8')
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=180, context=ctx)
            data = json.loads(resp.read().decode('utf-8'))
            text = data['candidates'][0]['content']['parts'][0]['text']
            return text
        except Exception as e:
            print(f"  ⚠️ API 调用失败 (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(8 * (attempt + 1))
    return None

def extract_json(text):
    text = re.sub(r'^```json\s*', '', text.strip())
    text = re.sub(r'^```\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        text = text[start:end+1]
    # 先尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 修复常见问题
    # 0. 移除控制字符 (除了\n\r\t)
    fixed = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    # 1. 移除trailing commas: ,] 和 ,}
    fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
    # 2. 修复中文引号
    fixed = fixed.replace('\u201c', '"').replace('\u201d', '"')
    fixed = fixed.replace('\u2018', "'").replace('\u2019', "'")
    # 3. 修复单引号key (JSON要求双引号)
    # 4. 尝试修复缺少逗号的情况: }\n{ -> },\n{  和 ]\n[ -> ],\n[
    fixed = re.sub(r'}\s*\n\s*{', '},\n{', fixed)
    fixed = re.sub(r'"\s*\n\s*"', '",\n"', fixed)
    # 5. 去掉多行注释 // ...
    fixed = re.sub(r'//[^\n]*', '', fixed)
    # 5b. 修复换行在字符串值内部 (JSON不允许裸换行在字符串中)
    # 替换字符串内的真实换行为\\n
    def fix_newlines_in_strings(s):
        result = []
        in_string = False
        escaped = False
        for ch in s:
            if escaped:
                result.append(ch)
                escaped = False
                continue
            if ch == '\\':
                escaped = True
                result.append(ch)
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                continue
            if in_string and ch == '\n':
                result.append('\\n')
                continue
            if in_string and ch == '\r':
                continue
            result.append(ch)
        return ''.join(result)
    fixed = fix_newlines_in_strings(fixed)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    # 6. 最后尝试: 截断到最外层 {} 匹配
    depth = 0
    real_end = -1
    for i, ch in enumerate(text):
        if ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                real_end = i
                break
    if real_end > 0:
        truncated = text[:real_end+1]
        truncated = re.sub(r',\s*([}\]])', r'\1', truncated)
        truncated = truncated.replace('\u201c', '"').replace('\u201d', '"')
        truncated = re.sub(r'//[^\n]*', '', truncated)
        return json.loads(truncated)
    raise json.JSONDecodeError("Cannot fix JSON", text, 0)

# ============ 学段配置 ============
MIDDLE_GRADES = ['七上','七下','八上','八下','九上','九下']
HIGH_GRADES   = ['高一上','高一下','高二上','高二下','高三上','高三下']

GRADE_FULL_MIDDLE = {
    '七上':'七年级上册','七下':'七年级下册',
    '八上':'八年级上册','八下':'八年级下册',
    '九上':'九年级上册','九下':'九年级下册',
}
GRADE_FULL_HIGH = {
    '高一上':'高一上册','高一下':'高一下册',
    '高二上':'高二上册','高二下':'高二下册',
    '高三上':'高三上册','高三下':'高三下册',
}

STAGE_CONFIG = {
    '初中': {
        'grades': MIDDLE_GRADES,
        'grade_full': GRADE_FULL_MIDDLE,
        'folder': '初中',
        'subjects': ['数学', '语文', '英语'],
    },
    '高中': {
        'grades': HIGH_GRADES,
        'grade_full': GRADE_FULL_HIGH,
        'folder': '高中',
        'subjects': ['数学', '语文', '英语'],
    },
}

# ============ 初中 Prompts ============

PROMPT_MIDDLE_MATH = """你是中国顶级初中数学教研专家，同时也是中考命题组成员，深谙人教版初中教材和中考出题规律。

请为 **人教版数学 {grade_full}** 生成一套「中考考点笔记总结」卡片（JSON格式）。

## 设计理念
这是「中考数学冲刺宝典」。每张卡片同时解决5个问题：
1. 这个知识点的核心是什么？（定义+定理+公式）
2. 中考怎么考？（题型+分值+频率）
3. 怎么答才能拿满分？（解题步骤+规范书写）
4. 最容易丢分在哪？（计算陷阱+概念混淆）
5. 什么记忆方法最高效？（口诀+图示+联想）

## 人教版初中数学各年级核心内容
- **七年级上**：有理数及其运算、整式的加减、一元一次方程、几何初步（线段/角）
- **七年级下**：相交线与平行线、实数、平面直角坐标系、二元一次方程组、不等式与不等式组、数据的收集整理
- **八年级上**：三角形(全等三角形)、轴对称、整式的乘除与因式分解、分式
- **八年级下**：二次根式、勾股定理、平行四边形、一次函数、数据分析
- **九年级上**：一元二次方程、二次函数、旋转、圆、概率初步
- **九年级下**：反比例函数、相似三角形、锐角三角函数、投影与视图

## 严格要求
1. **知识点覆盖完整**：覆盖该册所有章节（通常4-6章），每章2-3张卡
2. **总卡片数 10-18 张**
3. 严格按照人教版 {grade_full} 实际教材内容
4. 难度和考点对标 **中考**（不是单元测试）
5. JSON中所有引号内的中文引号用「」而非""

## 每张卡片必须包含以下字段

```
card_id: "S章号-序号" 如 "S1-01"
full_id: "数学-{grade_short}-S1-01"
title: 知识点名称（简洁有力）
type: "知识总结卡"
difficulty: 1-5 (中考视角)
importance: 1-5 (中考重要程度)
definition: 核心概念一句话（≤40字）
core_points: [3-5条要点，每条≤25字]
example: {{question, steps[], answer}} 一道中考级典型例题
mistakes: [{{wrong, correct}}] 1-2个常见错误
memory_tip: 记忆口诀/助记法
related: {{prerequisite, next}} 前后衔接
exam_focus: {{
  frequency: "★★★★★" 到 "★"（中考出现频率）
  question_types: ["选择", "填空", "计算", "证明", "综合题", "动点题", "函数图像", "几何作图", "应用题", "阅读理解题"] 中选
  scoring_key: 得分关键（如「证明步骤要完整」「辅助线是关键」）
  common_trap: 中考常见陷阱（如「负数开偶次方无意义」「平行线判定vs性质混淆」）
  real_exam_example: {{
    source: "中考真题" / "模拟考" / "期末真题"
    question: 一道模拟中考真题
    answer: 标准答案
    scoring_notes: 阅卷得分/扣分点
  }}
}}
```

请直接输出完整JSON（不要markdown代码块），格式：
{{
  "subject": "数学",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "人教版",
  "grade_short": "{grade_short}",
  "card_pack": "知识总结",
  "description": "初中{grade_full}数学中考考点笔记总结",
  "units": [
    {{
      "unit_id": "S1",
      "unit_name": "章节名称",
      "cards": [卡片数组]
    }}
  ]
}}"""

PROMPT_MIDDLE_YUWEN = """你是中国顶级初中语文教研专家，同时也是中考命题组成员，深谙统编版初中语文教材和中考出题规律。

请为 **统编版语文 {grade_full}** 生成一套「中考考点笔记总结」卡片（JSON格式）。

## 设计理念
这是「中考语文高分密码」。每张卡片聚焦一个核心考点，让学生看完就知道怎么答。

## 统编版初中语文各年级核心内容
- **七年级上**：记叙文阅读基础、朝花夕拾名著、古诗词(观沧海/次北固山下/天净沙秋思等)、写人记事作文、字词积累
- **七年级下**：抒情散文、名著(骆驼祥子/海底两万里)、古诗文(木兰诗/竹里馆等)、状物抒情作文
- **八年级上**：新闻与传记、名著(红星照耀中国/昆虫记)、古诗文(三峡/答谢中书书/记承天寺夜游等)、说明文写作
- **八年级下**：演讲词与游记、名著(傅雷家书/钢铁是怎样炼成的)、古诗文(桃花源记/小石潭记等)、议论文入门
- **九年级上**：小说阅读(故乡/我的叔叔于勒)、名著(艾青诗选/水浒传)、古诗文(岳阳楼记/醉翁亭记等)、议论文写作
- **九年级下**：戏剧与诗歌、名著(简爱/儒林外史)、古诗文(鱼我所欲也/送东阳马生序等)、中考总复习

## 中考语文考点体系（满分120/150分）
- **积累与运用**（25-30分）：字音字形、词语运用、病句修改、文学常识、名句默写、综合性学习
- **古诗文**（15-20分）：文言文翻译、古诗鉴赏、名句理解性默写
- **现代文阅读**（30-40分）：记叙文/散文阅读、说明文阅读、议论文阅读
- **名著阅读**（5-10分）：情节概述、人物分析、主题理解
- **写作**（50-60分）：命题/半命题/材料作文

## 严格要求
1. **覆盖完整**：覆盖该册所有重点单元和考点（通常6-8个专题），每专题1-2张
2. **总卡片数 10-18 张**
3. 考点对标 **中考**，含答题模板和得分技巧
4. JSON中所有引号内的中文引号用「」而非""

## 每张卡片字段

```
card_id, full_id, title, type: "知识总结卡"
difficulty: 1-5, importance: 1-5
definition: 核心要点一句话
core_points: [3-5条]
example: {{question, steps[], answer}} 中考级例题
mistakes: [{{wrong, correct}}]
memory_tip: 记忆/答题口诀
related: {{prerequisite, next}}
exam_focus: {{
  frequency: "★" ~ "★★★★★"
  question_types: ["字音字形", "词语运用", "病句修改", "名句默写", "文言翻译", "古诗鉴赏",
    "记叙文阅读", "说明文阅读", "议论文阅读", "名著阅读", "综合性学习", "作文"] 中选
  scoring_key: 得分关键（如「翻译要逐字落实」「赏析要点手法+内容+情感」）
  common_trap: 中考陷阱（如「虚词一词多义」「论点和论据混淆」）
  real_exam_example: {{source, question, answer, scoring_notes}}
}}
```

请直接输出完整JSON（不要markdown代码块），格式：
{{
  "subject": "语文",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "统编版",
  "grade_short": "{grade_short}",
  "card_pack": "知识总结",
  "description": "初中{grade_full}语文中考考点笔记总结",
  "units": [
    {{
      "unit_id": "S1",
      "unit_name": "专题名称",
      "cards": [卡片数组]
    }}
  ]
}}"""

PROMPT_MIDDLE_ENGLISH = """你是中国顶级初中英语教研专家，同时也是中考命题组成员，深谙人教版Go for it!英语教材和中考出题规律。

请为 **人教版(Go for it!)英语 {grade_full}** 生成一套「中考考点笔记总结」卡片（JSON格式）。

## 设计理念
这是「中考英语通关宝典」。每张卡片聚焦一个核心语法/词汇考点，配合中考真题训练。

## 人教版初中英语各年级核心内容
- **七年级上**：be动词、指示代词、名词单复数、一般现在时、特殊疑问句、介词、基础词汇(家庭/学校/数字/颜色等)
- **七年级下**：现在进行时、一般过去时(规则+不规则)、情态动词can/must、方位介词、There be句型
- **八年级上**：比较级最高级、频率副词、不定代词、will将来时、条件状语从句(if)、时间状语从句(when)
- **八年级下**：现在完成时、被动语态、宾语从句、直接引语间接引语、不定式to do
- **九年级全一册**：定语从句(who/which/that)、过去完成时、虚拟语气(could/would)、主谓一致、构词法(前缀后缀)

## 中考英语考点体系（满分120分）
- **听力理解**（25-30分）：图片选择、短对话、长对话、短文理解
- **完形填空**（15分）：词义辨析、固定搭配、语法结构、上下文逻辑
- **阅读理解**（30-40分）：细节理解、推理判断、主旨大意、词义猜测
- **语法填空/单选**（10-15分）：时态语态、从句、词性转换
- **书面表达**（15-20分）：话题作文、应用文(邮件/通知/日记)

## 严格要求
1. **覆盖完整**：覆盖该册所有核心语法和话题单元（通常4-6章），每章1-3张
2. **总卡片数 10-16 张**
3. 考点对标 **中考**，含真题级例句和易错点
4. JSON中所有引号内的中文引号用「」而非""

## 每张卡片字段

```
card_id, full_id, title, type: "知识总结卡"
difficulty: 1-5, importance: 1-5
definition: 核心语法/词汇规则一句话
core_points: [3-5条，中英对照]
example: {{question, steps[], answer}} 中考级例题
mistakes: [{{wrong, correct}}]
memory_tip: 记忆口诀（谐音/联想/韵律）
related: {{prerequisite, next}}
exam_focus: {{
  frequency: "★" ~ "★★★★★"
  question_types: ["单选", "完形填空", "阅读理解", "语法填空", "短文改错",
    "选词填空", "补全对话", "书面表达", "任务型阅读", "首字母填空"] 中选
  scoring_key: 得分关键（如「时态一致看时间状语」「三单变化别忘s/es」）
  common_trap: 中考陷阱（如「since+过去时间用现在完成时」「定语从句that不能省的情况」）
  real_exam_example: {{source, question, answer, scoring_notes}}
}}
```

请直接输出完整JSON（不要markdown代码块），格式：
{{
  "subject": "英语",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "人教Go for it!版",
  "grade_short": "{grade_short}",
  "card_pack": "知识总结",
  "description": "初中{grade_full}英语中考考点笔记总结",
  "units": [
    {{
      "unit_id": "S1",
      "unit_name": "单元/专题名称",
      "cards": [卡片数组]
    }}
  ]
}}"""

# ============ 高中 Prompts ============

PROMPT_HIGH_MATH = """你是中国顶级高中数学教研专家，同时也是高考命题研究组成员，深谙人教A版高中数学教材和高考出题规律。

请为 **人教A版数学 {grade_full}** 生成一套「高考考点笔记总结」卡片（JSON格式）。

## 设计理念
这是「高考数学满分攻略」。每张卡片同时解决5个关键问题：
1. 定义/定理/公式是什么？（精准表述）
2. 高考怎么考？（题型+分值+年份频率）
3. 标准解题步骤？（通法+技巧）
4. 最易丢分在哪？（计算/逻辑/审题陷阱）
5. 跨章节综合怎么联系？（知识网络）

## 人教A版高中数学各年级核心内容
- **高一上**：集合与常用逻辑用语、一元二次函数/方程/不等式、函数的概念与性质（单调性/奇偶性）
- **高一下**：指数函数与对数函数、三角函数（正弦/余弦/正切/诱导公式/图像变换）、向量初步
- **高二上**：平面向量应用、复数、立体几何初步（空间点线面位置关系/平行与垂直）、统计
- **高二下**：等差等比数列、解析几何（直线方程/圆的方程/椭圆/双曲线/抛物线）
- **高三上**：导数及其应用（切线/单调性/极值/最值）、排列组合、概率与统计（条件概率/正态分布）
- **高三下**：高考总复习综合（函数与导数综合、解析几何综合、数列与不等式综合、概率统计综合、选填题技巧）

## 高考数学考点体系（满分150分）
- **选择题**（8×5=40分）：集合/逻辑/复数/向量/三角/概率/立几/函数
- **填空题**（4×5=20分）：计算为主，陷阱多
- **解答题**（6题共90分）：
  - 三角函数/解三角形（12分）
  - 数列（12分）
  - 概率统计（12分）
  - 立体几何（12分）
  - 解析几何（12分，压轴2）
  - 导数（12分，压轴1）

## 严格要求
1. **覆盖完整**：覆盖该册所有章节（通常3-5章），每章2-4张卡
2. **总卡片数 12-20 张**
3. 考点对标 **高考**，含解题通法和秒杀技巧
4. JSON中所有引号内的中文引号用「」而非""

## 每张卡片字段

```
card_id: "S章号-序号"
full_id: "数学-{grade_short}-S1-01"
title: 知识点名称
type: "知识总结卡"
difficulty: 1-5 (高考视角)
importance: 1-5 (高考重要程度)
definition: 核心定义/定理/公式（≤50字）
core_points: [3-5条要点，含公式]
example: {{question, steps[], answer}} 高考级典型例题
mistakes: [{{wrong, correct}}] 1-2个易错点
memory_tip: 记忆口诀/秒杀技巧
related: {{prerequisite, next}}
exam_focus: {{
  frequency: "★★★★★" 到 "★"（高考出现频率）
  question_types: ["选择", "填空", "解答题", "证明题", "压轴题", "综合题"] 中选
  scoring_key: 得分关键（如「向量坐标化计算」「导数符号讨论要全面」）
  common_trap: 高考陷阱（如「定义域要先求」「分类讨论不遗漏」「隐含条件Δ≥0」）
  real_exam_example: {{
    source: "高考真题" / "模拟考" / "期末真题"
    question: 一道模拟高考真题
    answer: 标准答案
    scoring_notes: 阅卷得分/扣分点
  }}
}}
```

请直接输出完整JSON（不要markdown代码块），格式：
{{
  "subject": "数学",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "人教A版",
  "grade_short": "{grade_short}",
  "card_pack": "知识总结",
  "description": "高中{grade_full}数学高考考点笔记总结",
  "units": [
    {{
      "unit_id": "S1",
      "unit_name": "章节名称",
      "cards": [卡片数组]
    }}
  ]
}}"""

PROMPT_HIGH_YUWEN = """你是中国顶级高中语文教研专家，同时也是高考命题研究组成员，深谙统编版高中语文教材和高考出题规律。

请为 **统编版语文 {grade_full}** 生成一套「高考考点笔记总结」卡片（JSON格式）。

## 设计理念
这是「高考语文高分突破手册」。每张卡片都是一个得分模块，配合答题模板和阅卷标准。

## 统编版高中语文各年级核心内容
- **高一上**：现代诗歌(沁园春长沙)、散文(荷塘月色/故都的秋)、古诗文(劝学/师说/赤壁赋)、新闻写作
- **高一下**：小说(祝福/林教头风雪山神庙)、古诗文(阿房宫赋/琵琶行/念奴娇赤壁怀古)、实用类文本
- **高二上**：议论文(拿来主义/反对党八股)、古诗文(论语十二章/大学之道)、诗歌鉴赏进阶(杜甫/李白)
- **高二下**：戏剧(窦娥冤/雷雨)、古诗文(陈情表/归去来兮辞/兰亭集序)、科普类文本
- **高三上**：高考一轮复习（文言文断句+翻译+文化常识、古诗鉴赏专题、现代文阅读Ⅰ信息类、现代文阅读Ⅱ文学类、语言文字运用专题）
- **高三下**：高考二轮冲刺（作文审题立意、作文结构模板、选填题秒杀、名篇默写总结、考场策略与时间分配）

## 高考语文考点体系（满分150分）
- **现代文阅读Ⅰ·信息类**（17分）：主观+客观，论证分析、概括归纳
- **现代文阅读Ⅱ·文学类**（16分）：小说/散文赏析、人物形象、主题探究
- **古诗文阅读**（37分）：文言文断句(3)+翻译(8)+内容理解(3)、古诗鉴赏(9)+默写(6)+文化常识(3)
- **语言文字运用**（20分）：成语病句、补写、压缩、修辞、仿写
- **写作**（60分）：命题/材料议论文为主

## 严格要求
1. **覆盖完整**：覆盖该册所有核心模块（通常5-8个），每模块1-3张
2. **总卡片数 10-18 张**
3. 对标 **高考** 评分标准，含答题模板
4. JSON中所有引号内的中文引号用「」而非""

## 每张卡片字段

```
card_id, full_id, title, type: "知识总结卡"
difficulty: 1-5, importance: 1-5
definition: 核心考点一句话
core_points: [3-5条，含答题步骤/模板]
example: {{question, steps[], answer}} 高考级例题
mistakes: [{{wrong, correct}}]
memory_tip: 记忆口诀/答题框架
related: {{prerequisite, next}}
exam_focus: {{
  frequency: "★" ~ "★★★★★"
  question_types: ["信息类阅读", "文学类阅读", "文言断句", "文言翻译", "文化常识",
    "古诗鉴赏", "名篇默写", "成语辨析", "病句修改", "补写", "压缩", "作文"] 中选
  scoring_key: 得分关键（如「翻译采分点：关键实词+虚词+句式」「鉴赏三步：手法+内容+情感」）
  common_trap: 高考陷阱（如「选项偷换概念」「因果关系颠倒」「古今异义」）
  real_exam_example: {{source, question, answer, scoring_notes}}
}}
```

请直接输出完整JSON（不要markdown代码块），格式：
{{
  "subject": "语文",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "统编版",
  "grade_short": "{grade_short}",
  "card_pack": "知识总结",
  "description": "高中{grade_full}语文高考考点笔记总结",
  "units": [
    {{
      "unit_id": "S1",
      "unit_name": "专题名称",
      "cards": [卡片数组]
    }}
  ]
}}"""

PROMPT_HIGH_ENGLISH = """你是中国顶级高中英语教研专家，同时也是高考命题研究组成员，深谙人教版高中英语教材和高考出题规律。

请为 **人教版英语 {grade_full}** 生成一套「高考考点笔记总结」卡片（JSON格式）。

## 设计理念
这是「高考英语冲刺手册」。每张卡片对应一个高频考点，配合高考真题和答题技巧。

## 人教版高中英语各年级核心内容
- **高一上**：时态综合复习(一般现在/过去/将来+进行时)、名词性从句(主语从句/宾语从句/表语从句)、定语从句进阶、基础词汇3500第一批
- **高一下**：非谓语动词(不定式/动名词/分词)、情态动词+虚拟语气入门、被动语态综合、阅读技巧入门
- **高二上**：定语从句复杂用法(非限制性)、状语从句(时间/条件/让步/目的/结果)、倒装句、强调句、词汇3500第二批
- **高二下**：虚拟语气(wish/if/as if)、主谓一致、it用法(形式主语/强调)、完形阅读技巧进阶、应用文写作
- **高三上**：高考一轮（语法填空专项、完形填空技巧、阅读理解四大题型、七选五策略、短文改错规律、书面表达模板）
- **高三下**：高考二轮冲刺（读后续写技巧、应用文万能模板、长难句分析、高频语法易错点、考场策略）

## 高考英语考点体系（满分150分）
- **听力**（30分）：短对话+长对话+独白
- **阅读理解**（37.5分）：4篇+七选五，细节/推理/主旨/词义
- **完形填空**（15分）：词义辨析+语境推断+固定搭配
- **语法填空**（15分）：时态语态/非谓语/从句/词性转换
- **短文改错**（10分）：冠词/代词/时态/名词单复数/连词
- **书面表达**（25分）：应用文(15)+读后续写(25) 或 概要写作

## 严格要求
1. **覆盖完整**：覆盖该册核心语法和题型（通常4-6个模块），每模块2-3张
2. **总卡片数 10-18 张**
3. 对标 **高考**，含解题技巧和答题模板
4. JSON中所有引号内的中文引号用「」而非""

## 每张卡片字段

```
card_id, full_id, title, type: "知识总结卡"
difficulty: 1-5, importance: 1-5
definition: 核心语法/技巧一句话
core_points: [3-5条，含规则+例句]
example: {{question, steps[], answer}} 高考级例题
mistakes: [{{wrong, correct}}]
memory_tip: 记忆口诀/秒杀技巧
related: {{prerequisite, next}}
exam_focus: {{
  frequency: "★" ~ "★★★★★"
  question_types: ["语法填空", "完形填空", "阅读理解", "七选五", "短文改错",
    "书面表达", "读后续写", "听力"] 中选
  scoring_key: 得分关键（如「语法填空先判断有无提示词」「完形先通读再逐空」）
  common_trap: 高考陷阱（如「非谓语vs谓语判断」「虚拟语气时态后移」「熟词僻义」）
  real_exam_example: {{source, question, answer, scoring_notes}}
}}
```

请直接输出完整JSON（不要markdown代码块），格式：
{{
  "subject": "英语",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "人教版",
  "grade_short": "{grade_short}",
  "card_pack": "知识总结",
  "description": "高中{grade_full}英语高考考点笔记总结",
  "units": [
    {{
      "unit_id": "S1",
      "unit_name": "模块/专题名称",
      "cards": [卡片数组]
    }}
  ]
}}"""

# ============ Prompt 映射 ============
PROMPTS = {
    '初中': {
        '数学': PROMPT_MIDDLE_MATH,
        '语文': PROMPT_MIDDLE_YUWEN,
        '英语': PROMPT_MIDDLE_ENGLISH,
    },
    '高中': {
        '数学': PROMPT_HIGH_MATH,
        '语文': PROMPT_HIGH_YUWEN,
        '英语': PROMPT_HIGH_ENGLISH,
    },
}

# ============ 生成逻辑 ============

def get_grade_info(grade_short, stage):
    grade_full_map = STAGE_CONFIG[stage]['grade_full']
    grade_full = grade_full_map[grade_short]
    if '上' in grade_short:
        semester = '上册'
        grade_name = grade_full.replace('上册','')
    else:
        semester = '下册'
        grade_name = grade_full.replace('下册','')
    return grade_full, grade_name, semester


def generate_one(stage, subject, grade_short, keys, force=False):
    """为单个学段/年级/学科生成考点笔记总结"""
    grade_full, grade_name, semester = get_grade_info(grade_short, stage)
    folder = STAGE_CONFIG[stage]['folder']

    # 输出到 knowledge_cards/初中 或 knowledge_cards/高中
    output_dir = os.path.join(BASE_DIR, 'knowledge_cards', folder)
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f'{subject}_{grade_short}_总结.json')

    if os.path.exists(output_file) and not force:
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            has_exam = any(
                c.get('exam_focus')
                for u in data.get('units', [])
                for c in u.get('cards', [])
            )
            if has_exam:
                total = sum(len(u.get('cards', [])) for u in data.get('units', []))
                print(f"  ⏭️  已有考点版({total}张): {subject}_{grade_short}_总结.json，跳过")
                return output_file
            else:
                print(f"  🔄 现有版本无考点字段，将重新生成...")
        except:
            pass

    print(f"\n{'='*60}")
    print(f"  🎯 生成 [{stage}] {subject} {grade_full} 考点笔记总结")
    print(f"{'='*60}")

    template = PROMPTS[stage][subject]
    prompt = template.format(
        grade_full=grade_full,
        grade_name=grade_name,
        semester=semester,
        grade_short=grade_short,
    )

    print(f"  📤 调用 Gemini API (model=gemini-2.5-flash)...")
    t0 = time.time()
    text = call_gemini(prompt, keys, temperature=0.7)
    elapsed = time.time() - t0
    print(f"  ⏱️  API 用时: {elapsed:.1f}s")

    if not text:
        print(f"  ❌ API 调用失败，跳过 {subject}_{grade_short}")
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

    # 确保关键字段
    data.setdefault('card_pack', '知识总结')
    exam_label = '中考' if stage == '初中' else '高考'
    data.setdefault('description', f'{stage}{grade_full}{subject}{exam_label}考点笔记总结')

    total_cards = sum(len(u.get('cards', [])) for u in data.get('units', []))
    total_units = len(data.get('units', []))
    has_exam = sum(1 for u in data.get('units', []) for c in u.get('cards', []) if c.get('exam_focus'))

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  ✅ {subject}_{grade_short}: {total_units}单元 {total_cards}张卡 ({has_exam}张含考点)")
    print(f"  📁 {output_file}")

    return output_file


def sync_to_public(stages):
    """同步到 public/knowledge_cards/ 目录"""
    for stage in stages:
        folder = STAGE_CONFIG[stage]['folder']
        src_dir = os.path.join(BASE_DIR, 'knowledge_cards', folder)
        dst_dir = os.path.join(BASE_DIR, 'public', 'knowledge_cards', folder)
        os.makedirs(dst_dir, exist_ok=True)

        if not os.path.exists(src_dir):
            continue

        count = 0
        for f in os.listdir(src_dir):
            if f.endswith('_总结.json'):
                shutil.copy2(os.path.join(src_dir, f), os.path.join(dst_dir, f))
                count += 1
        print(f"  📦 已同步 {count} 个文件到 public/knowledge_cards/{folder}/")


def update_manifest(stages):
    """更新 manifest.json，为初中/高中添加条目"""
    manifest_path = os.path.join(BASE_DIR, 'public', 'knowledge_cards', 'manifest.json')
    if not os.path.exists(manifest_path):
        print("  ⚠️ manifest.json 不存在，跳过更新")
        return

    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    if 'stages' not in manifest:
        manifest['stages'] = {}

    for stage in stages:
        folder = STAGE_CONFIG[stage]['folder']
        src_dir = os.path.join(BASE_DIR, 'public', 'knowledge_cards', folder)
        if not os.path.exists(src_dir):
            continue

        # 获取已有条目
        existing = manifest['stages'].get(stage, [])
        existing_files = {e.get('file') for e in existing if isinstance(e, dict)}

        # 扫描所有 _总结.json
        for fname in sorted(os.listdir(src_dir)):
            if not fname.endswith('_总结.json'):
                continue

            fpath = os.path.join(src_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except:
                continue

            total_units = len(data.get('units', []))
            total_cards = sum(len(u.get('cards', [])) for u in data.get('units', []))
            subject = data.get('subject', '')
            grade = data.get('grade', '')
            semester = data.get('semester', '')
            grade_short = data.get('grade_short', '')

            if fname in existing_files:
                # 更新已有条目
                for entry in existing:
                    if isinstance(entry, dict) and entry.get('file') == fname:
                        entry['units'] = total_units
                        entry['cards'] = total_cards
                        break
            else:
                # 新增条目
                existing.append({
                    'file': fname,
                    'subject': subject,
                    'grade': grade,
                    'semester': semester,
                    'grade_short': grade_short,
                    'is_summary': True,
                    'units': total_units,
                    'cards': total_cards,
                })

        manifest['stages'][stage] = existing

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"  📋 manifest.json 已更新")


def main():
    parser = argparse.ArgumentParser(description='生成初中+高中考点笔记总结卡片')
    parser.add_argument('--stage', default=None, help='指定学段: 初中/高中')
    parser.add_argument('--subject', default=None, help='指定学科: 数学/语文/英语')
    parser.add_argument('--grade', default=None, help='指定年级: 如 八上 / 高一上')
    parser.add_argument('--force', action='store_true', help='强制覆盖已有文件')
    parser.add_argument('--delay', type=int, default=3, help='API调用间隔秒数')
    parser.add_argument('--no-sync', action='store_true', help='不同步到public')
    args = parser.parse_args()

    keys = load_keys()

    target_stages = [args.stage] if args.stage else ['初中', '高中']

    print(f"""
╔══════════════════════════════════════════════════════╗
║  📝 初中+高中 考点笔记总结卡片生成器                    ║
║  学段: {', '.join(target_stages)}                                       ║
║  学科: {args.subject or '全部(数学/语文/英语)'}                          ║
║  强制覆盖: {'是' if args.force else '否'}                                ║
║  API Keys: {len(keys)} 个                                  ║
╚══════════════════════════════════════════════════════╝
""")

    results = []
    total_start = time.time()

    for stage in target_stages:
        cfg = STAGE_CONFIG[stage]
        subjects = [args.subject] if args.subject else cfg['subjects']

        for subject in subjects:
            if args.grade:
                grades = [args.grade]
            else:
                grades = cfg['grades']

            print(f"\n{'━'*60}")
            print(f"  📚 [{stage}] {subject} ({len(grades)}个学期)")
            print(f"{'━'*60}")

            for i, grade in enumerate(grades):
                result = generate_one(stage, subject, grade, keys, force=args.force)
                results.append((f"[{stage}]{subject}_{grade}", result))

                if i < len(grades) - 1 and result and '跳过' not in str(result):
                    print(f"  ⏳ 等待 {args.delay}s...")
                    time.sleep(args.delay)

    # 同步
    if not args.no_sync:
        sync_to_public(target_stages)
        update_manifest(target_stages)

    # 汇总
    total_time = time.time() - total_start
    success = sum(1 for _, r in results if r)
    total_cards = 0

    print(f"\n{'='*60}")
    print(f"  📊 生成汇总 (耗时 {total_time:.0f}s)")
    print(f"{'='*60}")
    for name, result in results:
        status = '✅' if result else '❌'
        print(f"  {status} {name}")
        if result and os.path.exists(result):
            try:
                with open(result, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                c = sum(len(u.get('cards', [])) for u in d.get('units', []))
                total_cards += c
            except:
                pass
    print(f"\n  总计: {len(results)} 个, 成功: {success}, 总卡片: {total_cards}")


if __name__ == '__main__':
    main()
