#!/usr/bin/env python3
"""
批量生成「考点笔记总结」卡片 — 增强版
=====================================
在原有知识总结卡基础上，新增 exam_focus 字段：
  - frequency: 考试出现频率 ★~★★★★★
  - question_types: 题型列表
  - scoring_key: 得分关键
  - common_trap: 考试陷阱
  - real_exam_example: 模拟真题

用法:
  python _gen_summary_exam.py                         # 生成全部(跳过已有)
  python _gen_summary_exam.py --force                 # 强制覆盖全部
  python _gen_summary_exam.py --subject 数学 --grade 三下  # 单科单年级
  python _gen_summary_exam.py --subject 语文           # 单科全年级
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
    return json.loads(text)

# ============ 学段配置 ============
GRADES_ALL = ['一上','一下','二上','二下','三上','三下','四上','四下','五上','五下','六上','六下']
GRADES_ENGLISH = ['三上','三下','四上','四下','五上','五下','六上','六下']

GRADE_FULL = {
    '一上':'一年级上册','一下':'一年级下册','二上':'二年级上册','二下':'二年级下册',
    '三上':'三年级上册','三下':'三年级下册','四上':'四年级上册','四下':'四年级下册',
    '五上':'五年级上册','五下':'五年级下册','六上':'六年级上册','六下':'六年级下册',
}

# ============ Prompt 模板 ============

SUMMARY_PROMPT_MATH = """你是中国顶级小学数学教研专家，同时也是考试命题组成员，深谙人教版教材和考试出题规律。

请为 **人教版数学 {grade_full}** 生成一套「考点笔记总结」卡片（JSON格式）。

## 设计理念
这不是普通的知识总结——而是「考试得分宝典」。每张卡片要同时解决5个问题：
1. 这个知识点的核心是什么？（概念+公式）
2. 考试怎么考这个点？（出什么题型）
3. 怎么答才能拿满分？（得分要诀）
4. 最容易丢分在哪？（考试陷阱）
5. 用什么方法快速记住？（记忆口诀）

## 严格要求
1. **知识点覆盖完整**：必须覆盖该册教材的所有主要单元（通常5-8个单元），每个单元1-3张卡
2. **总卡片数 8-15 张**，确保知识点不遗漏
3. 严格按照人教版 {grade_full} 的实际教材内容出
4. JSON中所有引号内的中文引号用「」而非""

## 每张卡片必须包含以下字段

```
card_id: "S单元号-序号" 如 "S1-01"
full_id: "数学-{grade_short}-S1-01"
title: 知识点名称（简洁有力，如「小数乘法竖式」「三角形面积公式」）
type: "知识总结卡"
difficulty: 1-5 (该年级视角)
importance: 1-5 (考试重要程度)
definition: 核心概念一句话（≤30字）
core_points: [3-5条要点，每条≤20字，用关键词+数字]
example: {{question, steps[], answer}} 一道典型例题
mistakes: [{{wrong, correct}}] 1-2个常见错误
memory_tip: 记忆口诀/助记法（生动有趣）
related: {{prerequisite, next}} 前后衔接
exam_focus: {{
  frequency: "★★★★★" 到 "★"（考试出现频率，★★★★★=必考）
  question_types: ["填空", "选择", "计算", "应用题", "判断", "画图", "操作题"] 中选
  scoring_key: 得分关键一句话（如「单位不能忘」「竖式要对齐」「答句写完整」）
  common_trap: 最常见的考试陷阱（如「面积和周长混淆」「余数比除数大」）
  real_exam_example: {{
    source: "期末真题" / "单元测试" / "小升初真题"
    question: 一道模拟真题
    answer: 标准答案
    scoring_notes: 阅卷得分/扣分点
  }}
}}
```

## 数学各年级考试题型对照
- 一二年级：口算、填空、看图列式、比大小、连线、简单应用题
- 三四年级：竖式计算、填空、选择、判断、画图、应用题
- 五六年级：计算(含简便运算)、填空、选择、判断、操作题(画图/测量)、解决问题(应用题)

请直接输出完整JSON（不要markdown代码块），格式：
{{
  "subject": "数学",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "人教版",
  "grade_short": "{grade_short}",
  "card_pack": "知识总结",
  "description": "{grade_full}数学考点笔记总结",
  "units": [
    {{
      "unit_id": "S1",
      "unit_name": "单元名称",
      "cards": [卡片数组]
    }}
  ]
}}"""

SUMMARY_PROMPT_YUWEN = """你是中国顶级小学语文教研专家，同时也是考试命题组成员，深谙统编版教材和考试出题规律。

请为 **统编版语文 {grade_full}** 生成一套「考点笔记总结」卡片（JSON格式）。

## 设计理念
这是一本「语文考试随身宝典」。每张卡片聚焦一个高频考点，帮学生在考试中精准拿分。

## 语文考点分类体系
- **字词基础**（每次考试 30-40 分）：
  - 看拼音写词语、组词造句、多音字、形近字、近反义词
  - 这是最容易拿分也最容易丢分的板块！
- **句子运用**（每次考试 10-15 分）：
  - 修改病句、句式转换(把字句/被字句/陈述句/反问句)、仿写、修辞判断
- **古诗文积累**（每次考试 10-15 分）：
  - 古诗默写填空、名句理解、作者朝代
- **阅读理解**（每次考试 15-25 分）：
  - 概括段意/主要内容、理解词语在文中含义、体会人物感情、修辞作用
- **写作**（每次考试 25-30 分）：
  - 审题、开头结尾、细节描写、过渡衔接、总分总结构

## 严格要求
1. **覆盖完整**：覆盖全册所有主要单元（通常 5-8 个专题），每专题 1-3 张
2. **总卡片数 8-15 张**
3. 一二年级侧重字词拼音，三四年级增加古诗阅读，五六年级强化阅读写作
4. JSON中所有引号内的中文引号用「」而非""

## 每张卡片字段

```
card_id, full_id, title, type: "知识总结卡"
difficulty: 1-5, importance: 1-5
definition: 核心概念一句话
core_points: [3-5条要点]
example: {{question, steps[], answer}}
mistakes: [{{wrong, correct}}]
memory_tip: 记忆口诀
related: {{prerequisite, next}}
exam_focus: {{
  frequency: "★" ~ "★★★★★"
  question_types: ["看拼音写词语", "组词", "造句", "选词填空", "修改病句",
    "句式转换", "默写", "阅读理解", "作文", "判断", "连线", "填空"] 中选
  scoring_key: 得分关键
  common_trap: 考试陷阱（如「的地得混用」「把字句主语搞错」）
  real_exam_example: {{source, question, answer, scoring_notes}}
}}
```

## 各年级考点侧重（必须严格遵循）
- 一年级：声母韵母前后鼻音、基本笔画笔顺、常用量词、简单造句
- 二年级：多音字、形近字、看拼音写词语、基本标点、简单阅读
- 三年级：近反义词、修辞入门(比喻拟人)、古诗理解、写人写事作文
- 四年级：成语运用、句式转换、概括文章大意、缩写扩写
- 五年级：关联词、修改病句、阅读理解(概括+赏析)、材料作文
- 六年级：高频易错字词总复习、文言文入门、深层阅读理解、小升初作文

请直接输出完整JSON（不要markdown代码块），格式：
{{
  "subject": "语文",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "统编版",
  "grade_short": "{grade_short}",
  "card_pack": "知识总结",
  "description": "{grade_full}语文考点笔记总结",
  "units": [
    {{
      "unit_id": "S1",
      "unit_name": "专题名称",
      "cards": [卡片数组]
    }}
  ]
}}"""

SUMMARY_PROMPT_ENGLISH = """你是中国顶级小学英语教研专家，同时也是考试命题组成员，深谙人教版PEP英语教材和考试出题规律。

请为 **人教版(PEP)英语 {grade_full}** 生成一套「考点笔记总结」卡片（JSON格式）。

## 设计理念
这是一本「英语考试通关秘籍」。每张卡片聚焦一个核心考点，让学生看完就会做。

## 英语考点分类体系
- **词汇识记**（每次考试 20-30 分）：
  - 单词拼写、看图写单词、英汉互译、分类归纳
- **语法规则**（每次考试 15-20 分）：
  - be动词选用、人称代词、名词单复数、一般现在时/现在进行时/一般过去时/一般将来时
- **句型应用**（每次考试 15-20 分）：
  - 特殊疑问句、there be句型、情景交际选择、按要求改句子
- **阅读理解**（每次考试 10-15 分）：
  - 阅读判断对错、阅读选择、阅读回答问题
- **书面表达**（每次考试 10-15 分）：
  - 看图写话、介绍类（My family/My day/My friend）、对话补全

## 严格要求
1. **覆盖完整**：覆盖全册所有主要单元（通常 4-6 个单元），每单元 1-2 张
2. **总卡片数 8-12 张**
3. 三四年级侧重词汇和简单句型，五六年级强化语法和阅读写作
4. JSON中所有引号内的中文引号用「」而非""

## 每张卡片字段

```
card_id, full_id, title, type: "知识总结卡"
difficulty: 1-5, importance: 1-5
definition: 核心知识点一句话
core_points: [3-5条要点，中英对照]
example: {{question, steps[], answer}}
mistakes: [{{wrong, correct}}]
memory_tip: 记忆口诀（可用谐音/联想/韵律）
related: {{prerequisite, next}}
exam_focus: {{
  frequency: "★" ~ "★★★★★"
  question_types: ["听力选图", "听力判断", "选择填空", "连线", "看图写单词",
    "按要求改句子", "情景交际", "阅读理解", "补全对话", "书面表达"] 中选
  scoring_key: 得分关键（如「大小写和标点」「时态一致」「三单不忘s」）
  common_trap: 考试陷阱（如「he用does不用do」「不可数名词无复数」）
  real_exam_example: {{source, question, answer, scoring_notes}}
}}
```

## 各年级考点侧重
- 三年级：26个字母大小写、基础词汇(颜色/数字/动物/食物)、This is/I have/I like句型
- 四年级：教室/家庭相关词汇、What/Where/How many疑问句、there be句型
- 五年级：日程与频率词汇、一般现在时三单变化、现在进行时、作文入门
- 六年级：出行方式/职业/情绪词汇、一般过去时(规则+不规则)、一般将来时、综合阅读写作

请直接输出完整JSON（不要markdown代码块），格式：
{{
  "subject": "英语",
  "grade": "{grade_name}",
  "semester": "{semester}",
  "textbook": "人教PEP版",
  "grade_short": "{grade_short}",
  "card_pack": "知识总结",
  "description": "{grade_full}英语考点笔记总结",
  "units": [
    {{
      "unit_id": "S1",
      "unit_name": "单元/专题名称",
      "cards": [卡片数组]
    }}
  ]
}}"""

PROMPTS = {
    '数学': SUMMARY_PROMPT_MATH,
    '语文': SUMMARY_PROMPT_YUWEN,
    '英语': SUMMARY_PROMPT_ENGLISH,
}

# ============ 生成逻辑 ============

def get_grade_info(grade_short):
    grade_full = GRADE_FULL[grade_short]
    if '上' in grade_short:
        semester = '上册'
        grade_name = grade_full.replace('上册','')
    else:
        semester = '下册'
        grade_name = grade_full.replace('下册','')
    return grade_full, grade_name, semester


def generate_one(subject, grade_short, keys, force=False):
    """为单个年级学科生成考点笔记总结"""
    grade_full, grade_name, semester = get_grade_info(grade_short)

    output_dir = os.path.join(BASE_DIR, 'knowledge_cards', '小学')
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f'{subject}_{grade_short}_总结.json')

    if os.path.exists(output_file) and not force:
        # 检查是否已有 exam_focus
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            has_exam = any(
                c.get('exam_focus') 
                for u in data.get('units', []) 
                for c in u.get('cards', [])
            )
            if has_exam:
                total = sum(len(u.get('cards',[])) for u in data.get('units',[]))
                print(f"  ⏭️  已有考点版({total}张): {subject}_{grade_short}_总结.json，跳过")
                return output_file
            else:
                print(f"  🔄 现有版本无考点字段，将重新生成...")
        except:
            pass

    print(f"\n{'='*60}")
    print(f"  🎯 生成 {subject} {grade_full} 考点笔记总结")
    print(f"{'='*60}")

    template = PROMPTS[subject]
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
    data.setdefault('description', f'{grade_full}{subject}考点笔记总结')

    total_cards = sum(len(u.get('cards', [])) for u in data.get('units', []))
    total_units = len(data.get('units', []))
    has_exam = sum(1 for u in data.get('units',[]) for c in u.get('cards',[]) if c.get('exam_focus'))

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  ✅ {subject}_{grade_short}: {total_units}单元 {total_cards}张卡 ({has_exam}张含考点)")
    print(f"  📁 {output_file}")

    return output_file


def sync_to_public():
    """同步到 public/knowledge_cards/小学/ 目录"""
    import shutil
    src_dir = os.path.join(BASE_DIR, 'knowledge_cards', '小学')
    dst_dir = os.path.join(BASE_DIR, 'public', 'knowledge_cards', '小学')
    os.makedirs(dst_dir, exist_ok=True)

    count = 0
    for f in os.listdir(src_dir):
        if f.endswith('_总结.json'):
            shutil.copy2(os.path.join(src_dir, f), os.path.join(dst_dir, f))
            count += 1
    print(f"\n  📦 已同步 {count} 个文件到 public/knowledge_cards/小学/")


def update_manifest():
    """更新 manifest.json"""
    manifest_path = os.path.join(BASE_DIR, 'public', 'knowledge_cards', 'manifest.json')
    if not os.path.exists(manifest_path):
        print("  ⚠️ manifest.json 不存在，跳过更新")
        return

    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    # manifest 格式: {"stages": {"小学": [...], ...}}
    src_dir = os.path.join(BASE_DIR, 'knowledge_cards', '小学')
    updated = 0
    entries = manifest.get('stages', {}).get('小学', [])
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get('is_summary'):
            continue
        fname = entry.get('file', '')
        fpath = os.path.join(src_dir, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                new_units = len(data.get('units', []))
                new_cards = sum(len(u.get('cards',[])) for u in data.get('units',[]))
                if entry.get('units') != new_units or entry.get('cards') != new_cards:
                    entry['units'] = new_units
                    entry['cards'] = new_cards
                    updated += 1
            except:
                pass

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"  📋 manifest.json 已更新 ({updated} 个条目)")


def main():
    parser = argparse.ArgumentParser(description='生成考点笔记总结卡片')
    parser.add_argument('--subject', default=None, help='指定学科: 数学/语文/英语')
    parser.add_argument('--grade', default=None, help='指定年级: 如 三下')
    parser.add_argument('--force', action='store_true', help='强制覆盖已有文件')
    parser.add_argument('--delay', type=int, default=3, help='API调用间隔秒数')
    parser.add_argument('--no-sync', action='store_true', help='不同步到public')
    args = parser.parse_args()

    keys = load_keys()

    # 确定要生成的科目和年级
    subjects = [args.subject] if args.subject else ['数学', '语文', '英语']

    print(f"""
╔════════════════════════════════════════════════╗
║  📝 考点笔记总结卡片生成器（增强版）              ║
║  科目: {', '.join(subjects)}                            ║
║  强制覆盖: {'是' if args.force else '否'}                             ║
║  API Keys: {len(keys)} 个                               ║
╚════════════════════════════════════════════════╝
""")

    results = []
    total_start = time.time()

    for subject in subjects:
        if args.grade:
            grades = [args.grade]
        elif subject == '英语':
            grades = GRADES_ENGLISH
        else:
            grades = GRADES_ALL

        print(f"\n{'━'*60}")
        print(f"  📚 {subject} ({len(grades)}个年级)")
        print(f"{'━'*60}")

        for i, grade in enumerate(grades):
            result = generate_one(subject, grade, keys, force=args.force)
            results.append((f"{subject}_{grade}", result))

            if i < len(grades) - 1 and result and '跳过' not in str(result):
                print(f"  ⏳ 等待 {args.delay}s...")
                time.sleep(args.delay)

    # 同步
    if not args.no_sync:
        sync_to_public()
        update_manifest()

    # 汇总
    total_time = time.time() - total_start
    success = sum(1 for _, r in results if r)
    print(f"\n{'='*60}")
    print(f"  📊 生成汇总 (耗时 {total_time:.0f}s)")
    print(f"{'='*60}")
    for name, result in results:
        status = '✅' if result else '❌'
        print(f"  {status} {name}")
    print(f"\n  总计: {len(results)} 个, 成功: {success}")

if __name__ == '__main__':
    main()
