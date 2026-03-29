"""
深层复审脚本 — 6 维度全面审计知识卡 + 生成图
═══════════════════════════════════════════════════════════
维度 1  教学有效性 (Teaching Effectiveness)
        — 考点覆盖 / 前置依赖 / 认知负荷 / 记忆锚点
维度 2  对抗性内容审 (Adversarial Content)
        — 自我矛盾 / 跨卡冲突 / 伪原创 / mistakes 真实性
维度 3  闭环考试测试 (Closed-Loop Exam)
        — 模拟学生学完卡片后答题，量化教学效果
维度 4  图片语义审 (Image Semantic)
        — 视觉模型审查图文一致 / 乱码 / 美观度 / 科学规范
维度 5  教材对标 (Textbook Alignment)
        — 对比人教版教材目录，找知识点盲区
维度 6  稳定性统计 (Stability)
        — 同卡多次生成 prompt，检查输出一致性

用法:
  python _deep_review.py                   # 全部6个维度
  python _deep_review.py --dims 1,3        # 只跑维度1和3
  python _deep_review.py --dims 4 --img-dir _test_science_output
  python _deep_review.py --sample 3        # 每科目每类型抽样3张卡

版本: v1.0  (2026-03-29)
"""

import sys, os, json, re, time, base64, traceback
from collections import defaultdict
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ═══════════════════════════════════════════
# API 基础设施 (复用 generate_card_images_v3 的 gemini_call)
# ═══════════════════════════════════════════

from generate_card_images_v3 import (
    gemini_call, TEXT_MODEL, load_api_keys,
    _SCIENCE_CARD_TYPES, _SCIENCE_SUBJECTS,
)

def _load_keys():
    keys = load_api_keys()
    if not keys:
        print("❌ 未找到 API key, 退出")
        sys.exit(1)
    return keys

def llm_ask(prompt: str, keys: list[str], temperature: float = 0.2) -> str | None:
    """简单文本问答 — 返回模型回复文本"""
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    gen_config = {"temperature": temperature, "maxOutputTokens": 8192, "responseMimeType": "application/json"}
    resp = gemini_call(TEXT_MODEL, contents, keys[0], gen_config=gen_config, all_keys=keys)
    if not resp:
        return None
    try:
        return resp['candidates'][0]['content']['parts'][0]['text']
    except (KeyError, IndexError):
        return None

def llm_vision(prompt: str, image_path: str, keys: list[str]) -> str | None:
    """视觉问答 — 发送图片 + prompt，返回模型回复"""
    with open(image_path, 'rb') as f:
        img_data = base64.b64encode(f.read()).decode('utf-8')
    ext = os.path.splitext(image_path)[1].lower()
    mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}.get(ext.lstrip('.'), 'image/jpeg')
    contents = [{"role": "user", "parts": [
        {"inlineData": {"mimeType": mime, "data": img_data}},
        {"text": prompt},
    ]}]
    gen_config = {"temperature": 0.2, "maxOutputTokens": 8192, "responseMimeType": "application/json"}
    resp = gemini_call(TEXT_MODEL, contents, keys[0], gen_config=gen_config, all_keys=keys)
    if not resp:
        return None
    try:
        return resp['candidates'][0]['content']['parts'][0]['text']
    except (KeyError, IndexError):
        return None


# ═══════════════════════════════════════════
# 数据加载
# ═══════════════════════════════════════════

KC_DIRS = [
    os.path.join(BASE_DIR, 'knowledge_cards'),
    os.path.join(BASE_DIR, 'public', 'knowledge_cards'),
]

def load_all_science_cards() -> list[dict]:
    """加载所有理科知识卡，返回 [{card, subject, stage, grade_short, file, unit_name}]"""
    results = []
    seen_ids = set()
    for d in KC_DIRS:
        for stage in ['初中', '高中']:
            sd = os.path.join(d, stage)
            if not os.path.isdir(sd):
                continue
            for fname in sorted(os.listdir(sd)):
                if not fname.endswith('.json'):
                    continue
                subj = fname.split('_')[0]
                if subj not in _SCIENCE_SUBJECTS:
                    continue
                fp = os.path.join(sd, fname)
                try:
                    data = json.loads(open(fp, encoding='utf-8').read())
                except:
                    continue
                gs = data.get('grade_short', '')
                for unit in data.get('units', []):
                    for card in unit.get('cards', []):
                        cid = card.get('full_id') or card.get('card_id', '')
                        if cid in seen_ids:
                            continue
                        seen_ids.add(cid)
                        results.append({
                            'card': card,
                            'subject': subj,
                            'stage': stage,
                            'grade_short': gs,
                            'file': fp,
                            'unit_name': unit.get('unit_name', ''),
                        })
    return results

def sample_cards(all_cards: list[dict], n_per_bucket: int = 2) -> list[dict]:
    """按 (subject, type) 分桶抽样"""
    buckets = defaultdict(list)
    for c in all_cards:
        key = (c['subject'], c['card']['type'])
        buckets[key].append(c)
    sampled = []
    for key, cards in sorted(buckets.items()):
        sampled.extend(cards[:n_per_bucket])
    return sampled

def card_text(card: dict) -> str:
    """把卡片所有文本字段拼成一段"""
    parts = [card.get('title', ''), card.get('definition', '')]
    parts.extend(card.get('core_points', []))
    ex = card.get('example', {})
    if isinstance(ex, dict):
        parts.append(ex.get('question', ''))
        parts.extend(ex.get('steps', []))
        parts.append(ex.get('answer', ''))
    for m in card.get('mistakes', []):
        if isinstance(m, dict):
            parts.append(m.get('wrong', ''))
            parts.append(m.get('correct', ''))
    parts.append(card.get('memory_tip', ''))
    return '\n'.join(p for p in parts if p)


# ═══════════════════════════════════════════
# 维度 1: 教学有效性
# ═══════════════════════════════════════════

DIM1_PROMPT = """你是一位资深中学理科教研员。请严格审查下面这张知识卡的教学有效性。

## 被审知识卡
- 科目: {subject}  年级: {grade_short} ({stage})
- 标题: {title}
- 类型: {card_type}
- 难度: {difficulty}/5
- 完整内容:
{card_json}

## 请逐项评估并打分 (每项1-10分, 10=优秀):

1. **考点命中** — 这张卡覆盖的知识点是否是该年级该科目的真正考点/重点？是否遗漏了关键考点？
2. **前置依赖** — 这张卡是否暗含了学生尚未学到的知识？(比如初二的卡用了高中的概念)
3. **认知负荷** — 信息量是否适合该年级学生？core_points 条数是否合理(建议3-7条)？
4. **记忆锚点** — memory_tip 是否有效、适龄、好记？
5. **示例质量** — example 是否具有代表性、解题步骤是否清晰完整？
6. **易错点真实性** — mistakes 中列出的错误是否是学生真正会犯的典型错误？

请严格按以下 JSON 格式输出 (不要多余文字):
```json
{{
  "scores": {{
    "exam_relevance": 8,
    "prerequisite_ok": 9,
    "cognitive_load": 7,
    "memory_anchor": 6,
    "example_quality": 8,
    "mistakes_realism": 7
  }},
  "overall": 7.5,
  "issues": ["具体问题1", "具体问题2"],
  "suggestions": ["改进建议1"]
}}
```"""

def run_dim1_teaching(cards: list[dict], keys: list[str]) -> list[dict]:
    """维度1: 教学有效性审计"""
    results = []
    for i, entry in enumerate(cards):
        card = entry['card']
        prompt = DIM1_PROMPT.format(
            subject=entry['subject'], grade_short=entry['grade_short'],
            stage=entry['stage'], title=card['title'],
            card_type=card.get('type', ''), difficulty=card.get('difficulty', '?'),
            card_json=json.dumps(card, ensure_ascii=False, indent=2),
        )
        print(f"  [{i+1}/{len(cards)}] {entry['subject']}_{entry['grade_short']} {card['title']}...", end=' ', flush=True)
        resp = llm_ask(prompt, keys)
        parsed = _parse_json_response(resp)
        if parsed:
            parsed['card_id'] = card.get('card_id', '?')
            parsed['title'] = card['title']
            parsed['subject'] = entry['subject']
            parsed['grade'] = entry['grade_short']
            print(f"overall={parsed.get('overall', '?')}")
        else:
            parsed = {'card_id': card.get('card_id'), 'title': card['title'], 'error': 'parse_failed', 'raw': (resp or '')[:200]}
            print("❌ 解析失败")
        results.append(parsed)
        time.sleep(1)  # rate limit
    return results


# ═══════════════════════════════════════════
# 维度 2: 对抗性内容审
# ═══════════════════════════════════════════

DIM2_PROMPT = """你是一位严格的学科内容审查员。请对下面这张知识卡进行对抗性审查，专门找"看起来对但实际有问题"的内容。

## 被审知识卡
- 科目: {subject} | {grade_short} ({stage})
- 标题: {title}
- 完整内容:
{card_json}

## 请检查以下维度:

1. **自我矛盾** — definition 和 core_points 之间有没有说法不一致的地方？
2. **知识性错误** — 公式、数据、概念是否准确？(化学方程式是否配平？物理公式是否正确？生物概念是否准确？)
3. **伪原创** — definition 和 example 是否在用不同的词说同一句话？学生看完能否真正获得新信息？
4. **mistakes 真实性** — 列出的"常见错误"是否是学生真正会犯的？有没有编造的、实际不存在的错误？
5. **答案正确性** — example 中的 answer 和 steps 是否推导正确、计算无误？

请严格按以下 JSON 格式输出:
```json
{{
  "self_contradiction": {{"found": false, "details": ""}},
  "factual_errors": {{"found": true, "details": "具体错误描述"}},
  "pseudo_original": {{"found": false, "details": ""}},
  "fake_mistakes": {{"found": false, "details": ""}},
  "answer_errors": {{"found": false, "details": ""}},
  "severity": "none|low|medium|high|critical",
  "summary": "一句话总结"
}}
```"""

def run_dim2_adversarial(cards: list[dict], keys: list[str]) -> list[dict]:
    """维度2: 对抗性内容审查"""
    results = []
    for i, entry in enumerate(cards):
        card = entry['card']
        prompt = DIM2_PROMPT.format(
            subject=entry['subject'], grade_short=entry['grade_short'],
            stage=entry['stage'], title=card['title'],
            card_json=json.dumps(card, ensure_ascii=False, indent=2),
        )
        print(f"  [{i+1}/{len(cards)}] {entry['subject']}_{entry['grade_short']} {card['title']}...", end=' ', flush=True)
        resp = llm_ask(prompt, keys)
        parsed = _parse_json_response(resp)
        if parsed:
            parsed['card_id'] = card.get('card_id', '?')
            parsed['title'] = card['title']
            sev = parsed.get('severity', 'none')
            icon = {'none': '✅', 'low': '🟡', 'medium': '🟠', 'high': '🔴', 'critical': '💀'}.get(sev, '?')
            print(f"{icon} {sev}")
        else:
            parsed = {'card_id': card.get('card_id'), 'title': card['title'], 'error': 'parse_failed', 'raw': (resp or '')[:200]}
            print("❌ 解析失败")
        results.append(parsed)
        time.sleep(1)
    return results


# ═══════════════════════════════════════════
# 维度 3: 闭环考试测试
# ═══════════════════════════════════════════

DIM3_GEN_EXAM_PROMPT = """你是一位{subject}老师。请根据以下知识点，出一道适合{grade_short}学生的考试题。
要求：题目必须需要用到该知识卡中的知识才能解答。难度适中。

知识卡标题: {title}
知识卡内容:
{card_json}

请严格按 JSON 格式输出:
```json
{{
  "question": "题目内容",
  "standard_answer": "标准答案",
  "key_knowledge": "解题需要用到的核心知识点"
}}
```"""

DIM3_STUDENT_PROMPT = """你是一个刚学完以下知识卡的{grade_short}学生。你只知道这张卡片上的内容，不知道其他任何内容。

## 你学到的知识卡
{card_json}

## 考试题
{question}

请用你从知识卡中学到的知识解答这道题。如果知识卡中的内容不足以解答，请明确说"知识不够"。

请严格按 JSON 格式输出:
```json
{{
  "student_answer": "你的答案",
  "reasoning": "解题过程",
  "knowledge_sufficient": true,
  "confidence": 8
}}
```"""

DIM3_GRADE_PROMPT = """你是一位阅卷老师。请对比标准答案和学生答案，判断学生是否答对。

## 题目
{question}

## 标准答案
{standard_answer}

## 学生答案
{student_answer}

## 学生推理过程
{reasoning}

请严格按 JSON 格式输出:
```json
{{
  "correct": true,
  "score": 85,
  "feedback": "评价",
  "knowledge_gap": "如果答错了，说明知识卡缺少什么内容"
}}
```"""

def run_dim3_closedloop(cards: list[dict], keys: list[str]) -> list[dict]:
    """维度3: 闭环考试 — 出题→模拟学生答题→评分"""
    results = []
    for i, entry in enumerate(cards):
        card = entry['card']
        cid = card.get('card_id', '?')
        print(f"  [{i+1}/{len(cards)}] {entry['subject']}_{entry['grade_short']} {card['title']}")

        # Step 1: 出题
        print(f"    📝 出题...", end=' ', flush=True)
        exam_prompt = DIM3_GEN_EXAM_PROMPT.format(
            subject=entry['subject'], grade_short=entry['grade_short'],
            title=card['title'],
            card_json=json.dumps(card, ensure_ascii=False, indent=2),
        )
        exam_resp = llm_ask(exam_prompt, keys, temperature=0.5)
        exam = _parse_json_response(exam_resp)
        if not exam or 'question' not in exam:
            print("❌ 出题失败")
            results.append({'card_id': cid, 'title': card['title'], 'error': 'exam_gen_failed'})
            continue
        print(f"✅")

        time.sleep(1)

        # Step 2: 模拟学生答题
        print(f"    🎓 模拟答题...", end=' ', flush=True)
        student_prompt = DIM3_STUDENT_PROMPT.format(
            grade_short=entry['grade_short'],
            card_json=json.dumps(card, ensure_ascii=False, indent=2),
            question=exam['question'],
        )
        student_resp = llm_ask(student_prompt, keys, temperature=0.3)
        student = _parse_json_response(student_resp)
        if not student or 'student_answer' not in student:
            print("❌ 答题失败")
            results.append({'card_id': cid, 'title': card['title'], 'error': 'student_failed'})
            continue
        print(f"✅ confidence={student.get('confidence', '?')}")

        time.sleep(1)

        # Step 3: 评分
        print(f"    📊 评分...", end=' ', flush=True)
        grade_prompt = DIM3_GRADE_PROMPT.format(
            question=exam['question'],
            standard_answer=exam.get('standard_answer', ''),
            student_answer=student.get('student_answer', ''),
            reasoning=student.get('reasoning', ''),
        )
        grade_resp = llm_ask(grade_prompt, keys)
        grade = _parse_json_response(grade_resp)
        if not grade:
            print("❌ 评分失败")
            results.append({'card_id': cid, 'title': card['title'], 'error': 'grading_failed'})
            continue

        icon = '✅' if grade.get('correct') else '❌'
        print(f"{icon} score={grade.get('score', '?')}")

        results.append({
            'card_id': cid,
            'title': card['title'],
            'subject': entry['subject'],
            'grade': entry['grade_short'],
            'exam_question': exam['question'],
            'standard_answer': exam.get('standard_answer', ''),
            'student_answer': student.get('student_answer', ''),
            'student_sufficient': student.get('knowledge_sufficient', None),
            'correct': grade.get('correct', False),
            'score': grade.get('score', 0),
            'knowledge_gap': grade.get('knowledge_gap', ''),
        })
        time.sleep(1)
    return results


# ═══════════════════════════════════════════
# 维度 4: 图片语义审
# ═══════════════════════════════════════════

DIM4_VISION_PROMPT = """你是一位教育内容质量审查员。请仔细审查这张学习卡片图片。

这张图片应该是一张"{title}"({card_type})的知识卡片，科目是{subject}。

请从以下维度审查并评分 (1-10分):

1. **文字可读性** — 图中有没有乱码、截断、重叠、模糊的文字？所有中文是否都清晰可读？
2. **图文一致性** — 图片展示的内容和标题"{title}"是否匹配？是否张冠李戴？
3. **视觉美观度** — 布局是否合理？配色是否和谐？有没有大片空白或过度拥挤？
4. **科学规范性** — 如果有公式/方程式/结构图，格式是否正确？符号是否规范？
5. **教学价值** — 看这张图能学到什么？是纯装饰还是真正有教学意义？

请严格按 JSON 格式输出:
```json
{{
  "scores": {{
    "text_readability": 8,
    "content_match": 9,
    "visual_aesthetics": 7,
    "scientific_accuracy": 8,
    "teaching_value": 7
  }},
  "overall": 7.8,
  "text_found": "列出你在图中读到的主要文字",
  "issues": ["问题1", "问题2"],
  "verdict": "一句话总结"
}}
```"""

def run_dim4_image_semantic(img_dir: str, keys: list[str]) -> list[dict]:
    """维度4: 图片语义审查"""
    if not os.path.isdir(img_dir):
        print(f"  ⚠️  图片目录不存在: {img_dir}")
        return [{'error': f'目录不存在: {img_dir}'}]

    images = [f for f in os.listdir(img_dir) if f.endswith(('.jpg', '.png', '.webp'))]
    if not images:
        print(f"  ⚠️  目录中无图片: {img_dir}")
        return [{'error': '无图片'}]

    results = []
    for i, fname in enumerate(sorted(images)):
        # 从文件名解析信息
        parts = fname.rsplit('.', 1)[0].split('_')
        subject = parts[0] if len(parts) > 0 else '?'
        grade = parts[1] if len(parts) > 1 else '?'
        card_type = parts[2] if len(parts) > 2 else '?'
        title = f"{subject}_{grade}_{card_type}"

        img_path = os.path.join(img_dir, fname)
        size_kb = os.path.getsize(img_path) / 1024

        print(f"  [{i+1}/{len(images)}] {fname} ({size_kb:.0f}KB)...", end=' ', flush=True)

        prompt = DIM4_VISION_PROMPT.format(
            title=title, card_type=card_type, subject=subject,
        )
        resp = llm_vision(prompt, img_path, keys)
        parsed = _parse_json_response(resp)
        if parsed:
            parsed['file'] = fname
            parsed['size_kb'] = round(size_kb)
            print(f"overall={parsed.get('overall', '?')}")
        else:
            parsed = {'file': fname, 'error': 'parse_failed', 'raw': (resp or '')[:200]}
            print("❌ 解析失败")
        results.append(parsed)
        time.sleep(2)  # vision calls are heavier
    return results


# ═══════════════════════════════════════════
# 维度 5: 教材对标
# ═══════════════════════════════════════════

# 人教版教材知识点大纲 (核心考点)
TEXTBOOK_OUTLINE = {
    ('物理', '八上'): [
        '机械运动', '参照物', '速度', '平均速度', '测量平均速度',
        '声音的产生与传播', '声音的特性', '噪声', '声的利用',
        '温度', '熔化和凝固', '汽化和液化', '升华和凝华',
        '光的直线传播', '光的反射', '平面镜成像', '光的折射', '色散',
        '透镜', '凸透镜成像规律', '眼睛和眼镜', '显微镜和望远镜',
        '质量', '密度', '测量密度',
    ],
    ('物理', '八下'): [
        '力', '弹力', '重力', '牛顿第一定律', '惯性',
        '二力平衡', '摩擦力', '压强', '液体压强', '大气压强',
        '流体压强与流速', '浮力', '阿基米德原理', '浮沉条件',
        '功', '功率', '机械效率', '杠杆', '滑轮', '机械能',
    ],
    ('物理', '九上'): [
        '分子热运动', '内能', '比热容', '热机', '热机效率',
        '电荷', '电流', '电路', '串联和并联', '电流规律',
        '电压', '电阻', '变阻器', '欧姆定律', '电阻的测量',
        '电功', '电功率', '焦耳定律', '安全用电',
    ],
    ('物理', '九下'): [
        '磁现象', '磁场', '电生磁', '电磁铁', '电动机',
        '磁生电', '发电机', '电能的输送',
        '能源', '核能', '太阳能', '能量转化和守恒',
    ],
    ('化学', '九上'): [
        '物质的变化和性质', '化学实验基本操作', '走进化学实验室',
        '空气', '氧气', '制取氧气',
        '分子和原子', '原子的结构', '元素', '离子',
        '化学式与化合价', '化学方程式', '质量守恒定律',
        '碳和碳的氧化物', '二氧化碳制取', '一氧化碳',
    ],
    ('化学', '九下'): [
        '金属材料', '金属的化学性质', '金属活动性顺序', '金属资源保护',
        '溶液', '溶解度', '溶液的浓度',
        '常见的酸和碱', '中和反应', '盐', '化学肥料',
        '化学与生活', '有机合成材料',
    ],
    ('生物', '七上'): [
        '生物的特征', '调查周边环境中的生物',
        '生物与环境的关系', '生态系统', '生物圈',
        '练习使用显微镜', '植物细胞', '动物细胞', '细胞的生活',
        '细胞的分裂', '动物体的结构层次', '植物体的结构层次',
        '种子植物', '被子植物的一生', '绿色植物与生物圈的水循环',
        '光合作用', '呼吸作用', '绿色植物与碳氧平衡',
    ],
    ('生物', '七下'): [
        '食物中的营养物质', '消化和吸收', '合理营养与食品安全',
        '呼吸道与肺', '发生在肺内的气体交换',
        '血液循环', '心脏', '血管', '血液',
        '尿的形成和排出', '人粪尿的处理',
        '眼球与视觉', '耳的结构与听觉',
        '神经系统', '神经调节', '激素调节',
    ],
    ('生物', '八上'): [
        '动物的运动', '先天性行为和学习行为', '社会行为',
        '腔肠动物和扁形动物', '线形动物和环节动物',
        '软体动物和节肢动物', '鱼', '两栖动物和爬行动物', '鸟', '哺乳动物',
        '细菌', '真菌', '病毒',
        '生物的分类',
    ],
    ('生物', '八下'): [
        '植物的生殖', '昆虫的生殖和发育', '两栖动物的生殖和发育', '鸟的生殖和发育',
        '基因控制生物的性状', '基因和染色体', '基因的显性和隐性',
        '人的性别遗传', '生物的变异',
        '地球上生命的起源', '生物进化的证据', '生物进化的原因',
        '传染病及其预防', '免疫',
        '人类对生物圈的影响',
    ],
    ('物理', '高一上'): [
        '质点', '参考系', '时间位移', '速度', '加速度',
        '匀变速直线运动', '自由落体', '运动图像',
        '重力', '弹力', '摩擦力', '力的合成与分解',
        '牛顿第一定律', '牛顿第二定律', '牛顿第三定律', '超重失重',
    ],
    ('物理', '高一下'): [
        '曲线运动', '运动的合成与分解', '抛体运动',
        '圆周运动', '向心力', '生活中的圆周运动',
        '万有引力定律', '天体运动', '宇宙速度',
        '功', '功率', '动能定理', '重力势能', '弹性势能', '机械能守恒',
    ],
    ('物理', '高二上'): [
        '电荷守恒', '库仑定律', '电场强度', '电势', '电容器',
        '电流', '电阻', '欧姆定律', '焦耳定律',
        '闭合电路欧姆定律', '电功率',
        '磁场', '安培力', '洛伦兹力', '带电粒子在磁场中运动',
    ],
    ('物理', '高二下'): [
        '电磁感应', '楞次定律', '法拉第电磁感应定律',
        '交变电流', '变压器', '远距离输电',
        '电磁波', '光的折射', '全反射', '光的干涉', '光的衍射',
    ],
    ('化学', '高一上'): [
        '化学实验安全', '混合物的分离和提纯',
        '物质的量', '摩尔质量', '气体摩尔体积', '物质的量浓度',
        '物质的分类', '离子反应', '氧化还原反应',
        '钠及其化合物', '氯及其化合物', '铁及其化合物',
    ],
    ('化学', '高一下'): [
        '元素周期表', '元素周期律', '化学键',
        '化学能与热能', '化学能与电能', '原电池',
        '化学反应速率', '化学平衡', '影响化学平衡的因素',
        '有机化合物概述', '甲烷', '乙烯', '苯', '乙醇', '乙酸',
    ],
    ('化学', '高二上'): [
        '化学反应与能量变化', '热化学方程式', '盖斯定律',
        '化学反应速率', '化学平衡常数', '平衡移动',
        '弱电解质的电离', '水的电离', 'pH',
        '盐类的水解', '沉淀溶解平衡',
    ],
    ('化学', '高二下'): [
        '原子结构', '电子云', '杂化轨道',
        '分子间作用力', '氢键', '共价键',
        '晶体类型', '离子晶体', '分子晶体', '共价晶体', '金属晶体',
        '配位键', '配合物',
    ],
    ('生物', '高一上'): [
        '细胞学说', '细胞中的元素和化合物',
        '蛋白质', '核酸', '糖类', '脂质', '水和无机盐',
        '细胞膜', '细胞器', '细胞核', '生物膜系统',
        '物质跨膜运输', '渗透作用', '主动运输',
    ],
    ('生物', '高一下'): [
        '酶', '酶的特性', 'ATP',
        '细胞呼吸', '有氧呼吸', '无氧呼吸',
        '光合作用', '光反应', '暗反应', '影响光合作用因素',
        '细胞增殖', '有丝分裂', '减数分裂',
        '细胞分化', '细胞衰老', '细胞凋亡', '细胞癌变',
    ],
    ('生物', '高二上'): [
        '孟德尔遗传', '分离定律', '自由组合定律',
        '基因在染色体上', '伴性遗传',
        'DNA是遗传物质', 'DNA的结构', 'DNA的复制',
        '基因的表达', '转录', '翻译', '中心法则',
        '基因突变', '基因重组', '染色体变异',
    ],
    ('生物', '高二下'): [
        '内环境与稳态', '神经调节', '反射弧', '兴奋传导',
        '体液调节', '激素调节', '免疫调节',
        '植物激素', '生长素', '其他植物激素',
        '种群', '群落', '生态系统', '物质循环', '能量流动',
        '生态平衡', '生物多样性',
    ],
}

DIM5_ALIGNMENT_PROMPT = """你是一位教育内容分析师。请对比以下知识卡覆盖的知识点和教材大纲，找出差距。

## 科目: {subject}  年级: {grade_short}

## 教材大纲知识点 (人教版):
{textbook_points}

## 知识卡覆盖的内容 (共{card_count}张卡):
{card_titles}

## 请分析:
1. 教材中有但知识卡没覆盖的知识点 (盲区)
2. 知识卡有但教材中不属于本学期的知识点 (超纲)
3. 覆盖率估算 (百分比)

请严格按 JSON 格式输出:
```json
{{
  "coverage_pct": 75,
  "blind_spots": ["教材有但卡片没覆盖的知识点1", "知识点2"],
  "out_of_scope": ["超纲知识点1"],
  "well_covered": ["覆盖良好的知识点1", "知识点2"],
  "verdict": "一句话总结"
}}
```"""

def run_dim5_textbook(all_cards: list[dict], keys: list[str]) -> list[dict]:
    """维度5: 教材对标"""
    # 按 (subject, grade_short) 分组
    groups = defaultdict(list)
    for entry in all_cards:
        key = (entry['subject'], entry['grade_short'])
        groups[key].append(entry)

    results = []
    sorted_keys = sorted(groups.keys())
    for i, (subj, gs) in enumerate(sorted_keys):
        tb_key = (subj, gs)
        if tb_key not in TEXTBOOK_OUTLINE:
            continue

        cards_in_group = groups[(subj, gs)]
        card_titles = '\n'.join(
            f"  - [{c['card']['card_id']}] {c['card']['title']} ({c['card'].get('type', '')}) — {c['card'].get('definition', '')[:60]}"
            for c in cards_in_group
        )
        tb_points = '\n'.join(f"  - {p}" for p in TEXTBOOK_OUTLINE[tb_key])

        print(f"  [{i+1}/{len(sorted_keys)}] {subj}_{gs} ({len(cards_in_group)}张卡 vs {len(TEXTBOOK_OUTLINE[tb_key])}个知识点)...", end=' ', flush=True)

        prompt = DIM5_ALIGNMENT_PROMPT.format(
            subject=subj, grade_short=gs,
            textbook_points=tb_points,
            card_count=len(cards_in_group),
            card_titles=card_titles,
        )
        resp = llm_ask(prompt, keys)
        parsed = _parse_json_response(resp)
        if parsed:
            parsed['subject'] = subj
            parsed['grade'] = gs
            parsed['card_count'] = len(cards_in_group)
            parsed['textbook_points'] = len(TEXTBOOK_OUTLINE[tb_key])
            cov = parsed.get('coverage_pct', 0)
            blinds = len(parsed.get('blind_spots', []))
            print(f"覆盖{cov}% | 盲区{blinds}个")
        else:
            parsed = {'subject': subj, 'grade': gs, 'error': 'parse_failed'}
            print("❌ 解析失败")
        results.append(parsed)
        time.sleep(1)
    return results


# ═══════════════════════════════════════════
# 维度 6: 稳定性统计
# ═══════════════════════════════════════════

DIM6_PROMPT = """你是一位资深理科教师，负责为知识卡片生成教学图片的 prompt。

请为以下知识卡生成一段英文图片 prompt (用于 AI 图片生成)，要求：
- 描述一张教学卡片的视觉设计
- 包含标题、核心知识点的视觉展现
- 适合{subject}学科风格

知识卡:
{card_json}

请直接输出英文 prompt，不要 JSON 包装。"""

def run_dim6_stability(cards: list[dict], keys: list[str], repeats: int = 3) -> list[dict]:
    """维度6: 稳定性测试 — 同一张卡多次生成 prompt，比较一致性"""
    results = []
    test_cards = cards[:3]  # 只取3张卡做稳定性测试

    for i, entry in enumerate(test_cards):
        card = entry['card']
        print(f"  [{i+1}/{len(test_cards)}] {entry['subject']}_{entry['grade_short']} {card['title']}")

        prompts = []
        for r in range(repeats):
            print(f"    第{r+1}/{repeats}次生成...", end=' ', flush=True)
            prompt = DIM6_PROMPT.format(
                subject=entry['subject'],
                card_json=json.dumps(card, ensure_ascii=False, indent=2),
            )
            resp = llm_ask(prompt, keys, temperature=0.7)  # 稍高温度看变化
            if resp:
                prompts.append(resp.strip())
                print(f"✅ ({len(resp)}字)")
            else:
                prompts.append('')
                print("❌")
            time.sleep(2)

        # 分析一致性: 用 LLM 比较
        if len([p for p in prompts if p]) >= 2:
            valid_prompts = [p for p in prompts if p]
            compare_prompt = f"""请比较以下{len(valid_prompts)}个 prompt 的一致性。它们都是为同一张知识卡"{card['title']}"生成的图片描述。

{"".join(f'--- Prompt {j+1} ---{chr(10)}{p}{chr(10)}{chr(10)}' for j, p in enumerate(valid_prompts))}

请评估:
1. 核心元素一致性 (标题、知识点是否都包含)
2. 风格一致性 (布局描述是否类似)
3. 关键词重叠度

请严格按 JSON 格式输出:
```json
{{
  "core_consistency": 85,
  "style_consistency": 70,
  "keyword_overlap_pct": 60,
  "overall_stability": 72,
  "divergent_elements": ["不一致的元素1"],
  "verdict": "一句话总结"
}}
```"""
            print(f"    📊 分析一致性...", end=' ', flush=True)
            comp_resp = llm_ask(compare_prompt, keys)
            comp = _parse_json_response(comp_resp)
            if comp:
                comp['card_id'] = card.get('card_id', '?')
                comp['title'] = card['title']
                comp['prompt_count'] = len(valid_prompts)
                comp['prompt_lengths'] = [len(p) for p in valid_prompts]
                print(f"stability={comp.get('overall_stability', '?')}%")
            else:
                comp = {'card_id': card.get('card_id'), 'title': card['title'], 'error': 'analysis_failed'}
                print("❌")
            results.append(comp)
        else:
            results.append({'card_id': card.get('card_id'), 'title': card['title'], 'error': 'insufficient_prompts'})
        time.sleep(1)
    return results


# ═══════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════

def _parse_json_response(resp: str | None) -> dict | None:
    """从 LLM 回复中提取 JSON"""
    if not resp:
        return None
    # 尝试从 ```json...``` 块中提取
    m = re.search(r'```json\s*\n?(.*?)\n?\s*```', resp, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试直接解析
    try:
        return json.loads(resp)
    except json.JSONDecodeError:
        pass
    # 去掉 ```json 前缀后解析
    cleaned = re.sub(r'^\s*```json\s*', '', resp).rstrip().rstrip('`')
    if cleaned != resp:
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
    # 尝试找 { ... } 块
    m = re.search(r'\{.*\}', resp, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    # 截断修复: 找最长可解析 JSON 前缀
    m = re.search(r'\{', resp)
    if m:
        text = resp[m.start():]
        for end in range(len(text), 10, -1):
            try:
                # 尝试补齐截断的 JSON
                candidate = text[:end]
                # 数未闭合的 { 和 [
                opens_b = candidate.count('{') - candidate.count('}')
                opens_a = candidate.count('[') - candidate.count(']')
                fix = ']' * max(opens_a, 0) + '}' * max(opens_b, 0)
                return json.loads(candidate + fix)
            except json.JSONDecodeError:
                continue
    return None


def print_header(title: str):
    print(f"\n{'═' * 64}")
    print(f"  {title}")
    print(f"{'═' * 64}")


def print_dim1_report(results: list[dict]):
    print_header("维度 1 报告: 教学有效性")
    if not results:
        print("  (无结果)")
        return
    scores_summary = defaultdict(list)
    for r in results:
        if 'scores' in r:
            for k, v in r['scores'].items():
                scores_summary[k].append(v)
    if scores_summary:
        print(f"\n  {'指标':<20s} {'平均':>6s} {'最低':>6s} {'最高':>6s}")
        print(f"  {'─'*44}")
        labels = {'exam_relevance': '考点命中', 'prerequisite_ok': '前置依赖',
                  'cognitive_load': '认知负荷', 'memory_anchor': '记忆锚点',
                  'example_quality': '示例质量', 'mistakes_realism': '易错真实性'}
        for key in ['exam_relevance', 'prerequisite_ok', 'cognitive_load', 'memory_anchor', 'example_quality', 'mistakes_realism']:
            vals = scores_summary.get(key, [])
            if vals:
                avg = sum(vals) / len(vals)
                print(f"  {labels.get(key, key):<20s} {avg:>5.1f} {min(vals):>6d} {max(vals):>6d}")
    # 低分项
    low_cards = [r for r in results if isinstance(r.get('overall'), (int, float)) and r['overall'] < 6]
    if low_cards:
        print(f"\n  ⚠️  低分卡片 (overall < 6):")
        for r in low_cards:
            print(f"    {r.get('card_id', '?')} {r.get('title', '?')} — overall={r['overall']}")
            for iss in r.get('issues', []):
                print(f"      • {iss}")


def print_dim2_report(results: list[dict]):
    print_header("维度 2 报告: 对抗性内容审")
    if not results:
        print("  (无结果)")
        return
    severity_count = defaultdict(int)
    issues_found = []
    for r in results:
        sev = r.get('severity', 'unknown')
        severity_count[sev] += 1
        if sev in ('medium', 'high', 'critical'):
            issues_found.append(r)
    print(f"\n  严重度分布:")
    for s in ['none', 'low', 'medium', 'high', 'critical']:
        if severity_count[s]:
            icon = {'none': '✅', 'low': '🟡', 'medium': '🟠', 'high': '🔴', 'critical': '💀'}.get(s, '?')
            print(f"    {icon} {s}: {severity_count[s]}")
    if issues_found:
        print(f"\n  🔍 需关注的问题卡片:")
        for r in issues_found:
            print(f"    [{r.get('card_id', '?')}] {r.get('title', '?')} — severity={r['severity']}")
            print(f"      {r.get('summary', '')}")
            for dim in ['factual_errors', 'self_contradiction', 'answer_errors']:
                info = r.get(dim, {})
                if isinstance(info, dict) and info.get('found'):
                    print(f"      • {dim}: {info.get('details', '')[:100]}")


def print_dim3_report(results: list[dict]):
    print_header("维度 3 报告: 闭环考试测试")
    if not results:
        print("  (无结果)")
        return
    pass_count = sum(1 for r in results if r.get('correct'))
    fail_count = sum(1 for r in results if 'correct' in r and not r.get('correct'))
    error_count = sum(1 for r in results if 'error' in r)
    total = len(results)
    scores = [r['score'] for r in results if isinstance(r.get('score'), (int, float))]
    avg_score = sum(scores) / len(scores) if scores else 0

    print(f"\n  考试通过率: {pass_count}/{pass_count + fail_count} ({pass_count / (pass_count + fail_count) * 100:.0f}%)" if (pass_count + fail_count) > 0 else "")
    print(f"  平均分: {avg_score:.0f}/100")
    if error_count:
        print(f"  ⚠️  {error_count} 个测试流程异常")

    fail_cards = [r for r in results if 'correct' in r and not r['correct']]
    if fail_cards:
        print(f"\n  ❌ 未通过的闭环测试:")
        for r in fail_cards:
            print(f"    [{r.get('card_id', '?')}] {r.get('title', '?')} — score={r.get('score', '?')}")
            print(f"      题目: {r.get('exam_question', '')[:80]}")
            print(f"      知识缺口: {r.get('knowledge_gap', '无')[:80]}")


def print_dim4_report(results: list[dict]):
    print_header("维度 4 报告: 图片语义审")
    if not results:
        print("  (无结果)")
        return
    for r in results:
        if 'error' in r and 'file' not in r:
            print(f"  ⚠️  {r['error']}")
            continue
        fname = r.get('file', '?')
        overall = r.get('overall', '?')
        verdict = r.get('verdict', '')
        print(f"\n  📷 {fname} — overall={overall}")
        if 'scores' in r:
            labels = {'text_readability': '文字可读', 'content_match': '图文一致',
                      'visual_aesthetics': '视觉美观', 'scientific_accuracy': '科学规范',
                      'teaching_value': '教学价值'}
            for k, v in r['scores'].items():
                print(f"    {labels.get(k, k)}: {v}/10")
        if r.get('text_found'):
            print(f"    读到的文字: {r['text_found'][:100]}")
        for iss in r.get('issues', []):
            print(f"    • {iss}")
        print(f"    结论: {verdict}")


def print_dim5_report(results: list[dict]):
    print_header("维度 5 报告: 教材对标")
    if not results:
        print("  (无结果)")
        return
    total_cov = []
    all_blinds = []
    for r in results:
        if 'error' in r:
            continue
        subj = r.get('subject', '?')
        gs = r.get('grade', '?')
        cov = r.get('coverage_pct', 0)
        blinds = r.get('blind_spots', [])
        oos = r.get('out_of_scope', [])
        total_cov.append(cov)

        bar = '█' * (cov // 10) + '░' * (10 - cov // 10)
        print(f"\n  {subj}_{gs}: {bar} {cov}%  ({r.get('card_count', '?')}卡 vs {r.get('textbook_points', '?')}考点)")
        if blinds:
            all_blinds.extend([(subj, gs, b) for b in blinds])
            print(f"    盲区: {', '.join(blinds[:5])}" + (f" ...+{len(blinds)-5}" if len(blinds) > 5 else ""))
        if oos:
            print(f"    超纲: {', '.join(oos[:3])}")

    if total_cov:
        avg = sum(total_cov) / len(total_cov)
        print(f"\n  📊 总平均覆盖率: {avg:.0f}%")
    if all_blinds:
        print(f"  ⚠️  总计 {len(all_blinds)} 个知识点盲区")


def print_dim6_report(results: list[dict]):
    print_header("维度 6 报告: 稳定性统计")
    if not results:
        print("  (无结果)")
        return
    for r in results:
        if 'error' in r:
            print(f"  ⚠️  [{r.get('card_id', '?')}] {r.get('title', '?')} — {r['error']}")
            continue
        stability = r.get('overall_stability', '?')
        print(f"\n  [{r.get('card_id', '?')}] {r.get('title', '?')}")
        print(f"    核心一致性: {r.get('core_consistency', '?')}%")
        print(f"    风格一致性: {r.get('style_consistency', '?')}%")
        print(f"    关键词重叠: {r.get('keyword_overlap_pct', '?')}%")
        print(f"    总体稳定性: {stability}%")
        divs = r.get('divergent_elements', [])
        if divs:
            print(f"    不一致元素: {', '.join(divs[:3])}")


# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description='知识卡深层复审 (6维度)')
    parser.add_argument('--dims', default='1,2,3,4,5,6', help='要执行的维度 (逗号分隔)')
    parser.add_argument('--sample', type=int, default=2, help='每(科目,类型)分桶抽样数')
    parser.add_argument('--img-dir', default=os.path.join(BASE_DIR, '_test_science_output'), help='图片目录')
    parser.add_argument('--repeats', type=int, default=3, help='维度6稳定性重复次数')
    parser.add_argument('--output', default='', help='JSON结果输出路径')
    args = parser.parse_args()

    dims = [int(x.strip()) for x in args.dims.split(',')]

    print("═" * 64)
    print("  知识卡深层复审 — 6 维度全面审计")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  维度: {dims}")
    print("═" * 64)

    keys = _load_keys()
    print(f"✅ 加载 {len(keys)} 个 API key")

    all_cards = load_all_science_cards()
    print(f"✅ 加载 {len(all_cards)} 张理科知识卡")

    sampled = sample_cards(all_cards, n_per_bucket=args.sample)
    print(f"✅ 抽样 {len(sampled)} 张卡片 (每桶 {args.sample})")

    all_results = {}
    t_start = time.time()

    # ── 维度 1: 教学有效性 ──
    if 1 in dims:
        print_header("维度 1: 教学有效性审计")
        print(f"  审查 {len(sampled)} 张卡片...")
        r1 = run_dim1_teaching(sampled, keys)
        all_results['dim1_teaching'] = r1
        print_dim1_report(r1)

    # ── 维度 2: 对抗性内容 ──
    if 2 in dims:
        print_header("维度 2: 对抗性内容审查")
        print(f"  审查 {len(sampled)} 张卡片...")
        r2 = run_dim2_adversarial(sampled, keys)
        all_results['dim2_adversarial'] = r2
        print_dim2_report(r2)

    # ── 维度 3: 闭环考试 ──
    if 3 in dims:
        print_header("维度 3: 闭环考试测试")
        # 闭环是最耗时的(3次API/卡)，用更小的样本
        exam_sample = sample_cards(all_cards, n_per_bucket=1)
        print(f"  测试 {len(exam_sample)} 张卡片 (出题→答题→评分)...")
        r3 = run_dim3_closedloop(exam_sample, keys)
        all_results['dim3_exam'] = r3
        print_dim3_report(r3)

    # ── 维度 4: 图片语义 ──
    if 4 in dims:
        print_header("维度 4: 图片语义审查")
        r4 = run_dim4_image_semantic(args.img_dir, keys)
        all_results['dim4_images'] = r4
        print_dim4_report(r4)

    # ── 维度 5: 教材对标 ──
    if 5 in dims:
        print_header("维度 5: 教材对标")
        r5 = run_dim5_textbook(all_cards, keys)
        all_results['dim5_textbook'] = r5
        print_dim5_report(r5)

    # ── 维度 6: 稳定性 ──
    if 6 in dims:
        print_header("维度 6: 稳定性统计")
        stab_sample = sample_cards(all_cards, n_per_bucket=1)
        r6 = run_dim6_stability(stab_sample, keys, repeats=args.repeats)
        all_results['dim6_stability'] = r6
        print_dim6_report(r6)

    # ── 总结 ──
    elapsed = time.time() - t_start
    print_header("总 结")
    print(f"  耗时: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"  维度数: {len(dims)}")
    print(f"  总卡片: {len(all_cards)}")

    # 保存 JSON
    output_path = args.output or os.path.join(BASE_DIR, '_deep_review_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"  结果已保存: {output_path}")


if __name__ == '__main__':
    main()
