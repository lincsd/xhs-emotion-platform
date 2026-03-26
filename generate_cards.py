#!/usr/bin/env python3
"""
知识卡片批量生成脚本
使用 Gemini API 生成小学知识卡片 JSON 数据
用法: python generate_cards.py [学科] [年级] [学期] [教材版本]
示例: python generate_cards.py 数学 三年级 下册 人教版
"""
import json, sys, os, time, re, urllib.request, urllib.error

# ── 配置 ───────────────────────────────────────────────────────
def load_api_keys():
    """从 api_key.txt 或环境变量加载 Gemini API Key"""
    keys = []
    txt = os.path.join(os.path.dirname(__file__), 'api_key.txt')
    if os.path.exists(txt):
        for line in open(txt, encoding='utf-8'):
            if line.strip().startswith('GEMINI_API_KEY='):
                raw = line.strip().split('=', 1)[1]
                keys.extend([k.strip() for k in raw.split(',') if k.strip()])
    if not keys:
        raw = os.environ.get('GEMINI_API_KEY', '')
        keys = [k.strip() for k in raw.split(',') if k.strip()]
    return keys

API_KEYS = load_api_keys()
MODEL = 'gemini-2.5-flash'
API_BASE = 'https://generativelanguage.googleapis.com/v1beta'

_key_idx = 0
def next_key():
    global _key_idx
    k = API_KEYS[_key_idx % len(API_KEYS)]
    _key_idx += 1
    return k

def gemini_generate(prompt, temperature=0.3, max_tokens=16384):
    """调用 Gemini API 生成文本"""
    key = next_key()
    url = f"{API_BASE}/models/{MODEL}:generateContent?key={key}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json"
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            # Gemini 2.5 may have thinking parts, extract the text part
            parts = data['candidates'][0]['content']['parts']
            text = ''
            for p in parts:
                if 'text' in p:
                    text = p['text']  # Use the last text part (skip thinking)
            return text
    except urllib.error.HTTPError as e:
        print(f"  ⚠️ API Error {e.code}: {e.read().decode()[:300]}")
        return None
    except Exception as e:
        print(f"  ⚠️ Error: {e}")
        return None

def try_parse_json(text):
    """尝试解析 JSON，处理截断和格式问题"""
    if not text:
        return None
    text = text.strip()
    # 去掉 markdown code block
    if text.startswith('```'):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试修复截断的 JSON：补全缺失的括号
        for fix in [']', ']}', ']}]', ']}]}']:
            try:
                return json.loads(text + fix)
            except:
                continue
        return None

# ── Step 1: 生成知识点索引 ────────────────────────────────────────
def generate_index(subject, grade, semester, textbook):
    grade_short = grade.replace('年级', '')
    sem_short = '上' if '上' in semester else '下'
    prompt = f"""你是一位拥有20年小学{subject}教学经验的特级教师。
请为 {textbook}小学{subject} {grade}{semester} 制定完整的知识卡片清单。

要求：
1. 列出该学期所有单元名称（含"数学广角"等小单元，不可遗漏）
2. 为每个单元列出核心知识点（一个知识点=1张卡片）
3. 粒度标准：一个公式=一张、一个概念=一张、一个方法=一张

请直接输出 JSON 格式：
{{
  "subject": "{subject}",
  "grade": "{grade}",
  "semester": "{semester}",
  "textbook": "{textbook}",
  "grade_short": "{grade_short}{sem_short}",
  "units": [
    {{
      "unit_id": "01",
      "unit_name": "单元名称",
      "cards": [
        {{
          "card_id": "01-01",
          "title": "知识点名称",
          "type": "概念卡|公式卡|方法卡|辨析卡",
          "difficulty": 1-5,
          "importance": 1-5
        }}
      ]
    }}
  ]
}}

注意：
- 不要遗漏任何小单元
- 总卡片数 25-40 张
- difficulty 和 importance 用 1-5 的整数
- type 只能是：概念卡、公式卡、方法卡、辨析卡 四选一
"""
    print("📋 Step 1: 生成知识点索引...")
    result = gemini_generate(prompt, max_tokens=8192)
    if not result:
        print("  ❌ 索引生成失败")
        return None
    index = try_parse_json(result)
    if not index or 'units' not in index:
        print(f"  ❌ JSON 解析失败")
        print(f"  原始响应前500字: {result[:500]}")
        return None
    total = sum(len(u['cards']) for u in index['units'])
    print(f"  ✅ 索引生成成功: {len(index['units'])}个单元, {total}张卡片")
    return index

# ── Step 2: 逐单元生成卡片详情 ─────────────────────────────────────
def generate_unit_cards(index, unit):
    subject = index['subject']
    grade = index['grade']
    semester = index['semester']
    textbook = index['textbook']
    grade_short = index['grade_short']
    target_user = f"{grade}小学生"

    cards_list = "\n".join([
        f"- {c['card_id']} | {c['title']} | {c['type']} | 难度{c['difficulty']} | 重要性{c['importance']}"
        for c in unit['cards']
    ])

    prompt = f"""你是一位小学{subject}特级教师兼知识卡片设计专家。
请为 {textbook}小学{subject} {grade}{semester} 第{unit['unit_id']}单元「{unit['unit_name']}」生成全部知识卡片的详细内容。

该单元需要生成以下卡片：
{cards_list}

请直接输出 JSON 数组格式，每张卡片包含以下字段：
[
  {{
    "card_id": "{unit['cards'][0]['card_id']}",
    "full_id": "{subject}-{grade_short}-{unit['cards'][0]['card_id']}",
    "title": "知识点名称",
    "type": "卡片类型",
    "difficulty": 数字1-5,
    "importance": 数字1-5,
    "definition": "用{target_user}能理解的最简单的话解释这个知识点（一句话）",
    "core_points": ["核心公式/要素1", "核心公式/要素2"],
    "why_explanation": "本质原因（用通俗语言解释'为什么是这样'，而非只说结论）",
    "example": {{
      "question": "一道贴近考试的真题（数字具体）",
      "steps": ["步骤1（含为什么这样做）", "步骤2", "步骤3"],
      "answer": "明确的数字答案"
    }},
    "mistakes": [
      {{"wrong": "常见错误做法", "correct": "正确做法", "reason": "为什么这样做是错的（根本原因）"}}
    ],
    "memory_tip": "口诀或记忆技巧",
    "related": {{
      "prerequisite": "需要先掌握的知识点",
      "next": "学好这个后接下来学什么"
    }}
  }}
]

质量要求：
1. 所有例题必须有具体数字和明确答案
2. 易错点必须是真实考试中学生常犯的错误
3. 语言标准：{target_user}独立阅读可理解
4. 公式中如用字母表示，必须注明含义
5. 不得出现超纲内容
6. ⚠️ 每张卡片的why_explanation必须回答"为什么"，不能只说"是什么"
7. ⚠️ mistakes的reason必须解释错误的根本原因，不能只标注对错
"""
    result = gemini_generate(prompt, max_tokens=16384)
    if not result:
        return None
    cards = try_parse_json(result)
    if cards is None:
        print(f"  ❌ JSON 解析失败，单元: {unit['unit_name']}")
        return None
    if isinstance(cards, dict) and 'cards' in cards:
        cards = cards['cards']
    if isinstance(cards, dict):
        cards = [cards]
    return cards

def generate_all_cards(subject='数学', grade='三年级', semester='下册', textbook='人教版'):
    """端到端生成全套知识卡片"""
    if not API_KEYS:
        print("❌ 未找到 Gemini API Key，请检查 api_key.txt")
        return None

    print(f"\n{'='*50}")
    print(f"  📚 知识卡片生成: {textbook} {grade}{semester} {subject}")
    print(f"{'='*50}\n")

    # Step 1: 生成索引
    index = generate_index(subject, grade, semester, textbook)
    if not index:
        return None

    # Step 2: 逐单元生成
    print(f"\n📝 Step 2: 逐单元生成卡片内容...")
    all_detailed_cards = {}
    for i, unit in enumerate(index['units']):
        unit_id = unit['unit_id']
        print(f"  [{i+1}/{len(index['units'])}] 第{unit_id}单元「{unit['unit_name']}」({len(unit['cards'])}张)...")
        
        cards = generate_unit_cards(index, unit)
        if cards:
            all_detailed_cards[unit_id] = cards
            print(f"    ✅ 成功生成 {len(cards)} 张卡片")
        else:
            print(f"    ⚠️ 生成失败，使用基础数据")
            # 回退：使用索引中的基本信息
            all_detailed_cards[unit_id] = [{
                "card_id": c['card_id'],
                "full_id": f"{subject}-{index['grade_short']}-{c['card_id']}",
                "title": c['title'],
                "type": c['type'],
                "difficulty": c['difficulty'],
                "importance": c['importance'],
                "definition": f"关于{c['title']}的知识点",
                "core_points": [f"{c['title']}的核心要点"],
                "example": {"question": "待补充", "steps": ["待补充"], "answer": "待补充"},
                "mistakes": [{"wrong": "待补充", "correct": "待补充"}],
                "memory_tip": "待补充",
                "related": {"prerequisite": "待补充", "next": "待补充"}
            } for c in unit['cards']]
        
        time.sleep(1)  # 避免 API 限频

    # 组装最终数据
    for unit in index['units']:
        uid = unit['unit_id']
        if uid in all_detailed_cards:
            unit['cards'] = all_detailed_cards[uid]

    total = sum(len(u['cards']) for u in index['units'])
    index['total_cards'] = total
    index['generated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')

    # 保存
    grade_short = index['grade_short']
    filename = f"knowledge_cards_{subject}_{grade_short}.json"
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*50}")
    print(f"  ✅ 全部完成!")
    print(f"  📊 {len(index['units'])} 个单元, {total} 张卡片")
    print(f"  📁 已保存: {filename}")
    print(f"{'='*50}\n")
    
    return index

# ── 入口 ──────────────────────────────────────────────────────
if __name__ == '__main__':
    args = sys.argv[1:]
    subject = args[0] if len(args) > 0 else '数学'
    grade = args[1] if len(args) > 1 else '三年级'
    semester = args[2] if len(args) > 2 else '下册'
    textbook = args[3] if len(args) > 3 else '人教版'
    
    generate_all_cards(subject, grade, semester, textbook)
