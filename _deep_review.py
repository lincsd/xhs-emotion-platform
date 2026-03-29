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

# 全学科集合
_ALL_SUBJECTS = {'数学', '语文', '英语', '物理', '化学', '生物'}
_ALL_STAGES   = ['小学', '初中', '高中']

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
    """加载所有理科知识卡(向后兼容)"""
    return load_all_cards(subjects=_SCIENCE_SUBJECTS, stages=['初中', '高中'])


def load_all_cards(subjects: set | None = None, stages: list | None = None) -> list[dict]:
    """加载知识卡，可按学科/学段筛选。
    subjects=None → 加载全部学科; stages=None → 全部学段"""
    if stages is None:
        stages = _ALL_STAGES
    if subjects is None:
        subjects = _ALL_SUBJECTS
    results = []
    seen_ids = set()
    for d in KC_DIRS:
        for stage in stages:
            sd = os.path.join(d, stage)
            if not os.path.isdir(sd):
                continue
            for fname in sorted(os.listdir(sd)):
                if not fname.endswith('.json'):
                    continue
                subj = fname.split('_')[0]
                if subj not in subjects:
                    continue
                fp = os.path.join(sd, fname)
                try:
                    data = json.loads(open(fp, encoding='utf-8').read())
                except Exception:
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

DIM1_PROMPT = """你是一位资深{subject}教研员。请严格审查下面这张知识卡的教学有效性。

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

    # ═══════════════════════════════════════════
    # 数学 (人教版)
    # ═══════════════════════════════════════════
    ('数学', '一上'): [
        '数一数', '比一比', '1-5的认识和加减法', '认识图形(一)',
        '6-10的认识和加减法', '11-20各数的认识', '认识钟表',
        '20以内的进位加法', '总复习',
    ],
    ('数学', '一下'): [
        '认识图形(二)', '20以内的退位减法', '分类与整理',
        '100以内数的认识', '认识人民币', '100以内的加法和减法(一)',
        '找规律',
    ],
    ('数学', '二上'): [
        '长度单位', '100以内的加法和减法(二)', '角的初步认识',
        '表内乘法(一)', '观察物体(一)', '表内乘法(二)',
        '量一量比一比', '认识时间', '数学广角-搭配',
    ],
    ('数学', '二下'): [
        '数据收集整理', '表内除法(一)', '图形的运动(一)',
        '表内除法(二)', '混合运算', '有余数的除法',
        '万以内数的认识', '克和千克', '数学广角-推理',
    ],
    ('数学', '三上'): [
        '时分秒', '万以内的加法和减法(一)', '测量',
        '万以内的加法和减法(二)', '倍的认识', '多位数乘一位数',
        '长方形和正方形', '分数的初步认识', '数学广角-集合',
    ],
    ('数学', '三下'): [
        '位置与方向(一)', '除数是一位数的除法', '复式统计表',
        '两位数乘两位数', '面积', '年月日',
        '小数的初步认识', '数学广角-搭配(二)',
    ],
    ('数学', '四上'): [
        '大数的认识', '公顷和平方千米', '角的度量',
        '三位数乘两位数', '平行四边形和梯形', '除数是两位数的除法',
        '条形统计图', '数学广角-优化',
    ],
    ('数学', '四下'): [
        '四则运算', '观察物体(二)', '运算定律',
        '小数的意义和性质', '三角形', '小数的加法和减法',
        '图形的运动(二)', '平均数与条形统计图', '数学广角-鸡兔同笼',
    ],
    ('数学', '五上'): [
        '小数乘法', '位置', '小数除法', '可能性',
        '简易方程', '多边形的面积', '植树问题',
    ],
    ('数学', '五下'): [
        '观察物体(三)', '因数与倍数', '长方体和正方体',
        '分数的意义和性质', '图形的运动(三)',
        '分数的加法和减法', '折线统计图', '数学广角-找次品',
    ],
    ('数学', '六上'): [
        '分数乘法', '位置与方向(二)', '分数除法', '比',
        '圆', '百分数(一)', '扇形统计图', '数学广角-数与形',
    ],
    ('数学', '六下'): [
        '负数', '百分数(二)', '圆柱与圆锥', '比例',
        '数学广角-鸽巢问题', '小学总复习',
    ],
    ('数学', '七上'): [
        '有理数', '有理数的运算', '整式的加减',
        '一元一次方程', '几何图形初步',
    ],
    ('数学', '七下'): [
        '相交线与平行线', '实数', '平面直角坐标系',
        '二元一次方程组', '不等式与不等式组', '数据的收集整理描述',
    ],
    ('数学', '八上'): [
        '三角形', '全等三角形', '轴对称',
        '整式的乘法与因式分解', '分式',
    ],
    ('数学', '八下'): [
        '二次根式', '勾股定理', '平行四边形',
        '一次函数', '数据的分析',
    ],
    ('数学', '九上'): [
        '一元二次方程', '二次函数', '旋转',
        '圆', '概率初步',
    ],
    ('数学', '九下'): [
        '反比例函数', '相似', '锐角三角函数',
        '投影与视图', '总复习',
    ],
    ('数学', '高一上'): [
        '集合', '常用逻辑用语', '不等式',
        '函数的概念与性质', '幂函数', '指数函数', '对数函数',
        '三角函数',
    ],
    ('数学', '高一下'): [
        '三角恒等变换', '平面向量',
        '复数', '立体几何初步', '空间几何体',
        '统计', '概率',
    ],
    ('数学', '高二上'): [
        '数列', '等差数列', '等比数列',
        '空间向量与立体几何', '直线与方程', '圆与方程',
    ],
    ('数学', '高二下'): [
        '圆锥曲线', '椭圆', '双曲线', '抛物线',
        '计数原理', '排列组合', '二项式定理',
        '概率与统计', '条件概率', '随机变量',
    ],
    ('数学', '高三上'): [
        '导数及其应用', '导数与函数单调性', '极值最值',
        '定积分初步', '综合复习',
    ],
    ('数学', '高三下'): [
        '高考综合复习', '函数综合', '几何综合',
        '概率统计综合', '数列综合', '解析几何综合',
    ],

    # ═══════════════════════════════════════════
    # 语文 (人教版/部编版)
    # ═══════════════════════════════════════════
    ('语文', '一上'): [
        '汉语拼音', '识字(一)', '课文(一)', '识字(二)', '课文(二)',
        '口语交际', '语文园地',
    ],
    ('语文', '一下'): [
        '识字', '课文', '口语交际', '语文园地',
        '快乐读书吧',
    ],
    ('语文', '二上'): [
        '场景歌', '树之歌', '拍手歌', '田家四季歌',
        '小蝌蚪找妈妈', '我是什么', '植物妈妈有办法',
        '曹冲称象', '玲玲的画', '一封信', '妈妈睡了',
    ],
    ('语文', '二下'): [
        '古诗二首', '找春天', '开满鲜花的小路',
        '邓小平爷爷植树', '雷锋叔叔你在哪里',
        '千人糕', '一匹出色的马', '神州谣', '传统节日',
    ],
    ('语文', '三上'): [
        '大青树下的小学', '花的学校', '不懂就要问',
        '古诗三首', '铺满金色巴掌的水泥道', '秋天的雨', '听听秋的声音',
        '去年的树', '那一定会很好', '在牛肚子里旅行', '一块奶酪',
        '总也倒不了的老屋',
    ],
    ('语文', '三下'): [
        '古诗三首', '燕子', '荷花', '昆虫备忘录',
        '守株待兔', '陶罐和铁罐', '鹿角和鹿腿', '池子与河流',
        '小虾', '纸的发明', '赵州桥', '一幅名扬中外的画',
    ],
    ('语文', '四上'): [
        '观潮', '走月亮', '现代诗二首', '繁星',
        '一个豆荚里的五粒豆', '蝙蝠和雷达', '呼风唤雨的世纪',
        '古诗三首', '爬山虎的脚', '蟋蟀的住宅',
        '盘古开天地', '精卫填海', '普罗米修斯', '女娲补天',
    ],
    ('语文', '四下'): [
        '古诗词三首', '乡下人家', '天窗', '三月桃花水',
        '琥珀', '飞向蓝天的恐龙', '纳米技术就在我们身边',
        '短诗三首', '绿', '白桦', '在天晴了的时候',
        '猫', '母鸡', '白鹅',
    ],
    ('语文', '五上'): [
        '白鹭', '落花生', '桂花雨', '珍珠鸟',
        '搭石', '将相和', '什么比猎豹的速度更快',
        '古诗词三首', '少年中国说', '圆明园的毁灭', '小岛',
        '太阳', '松鼠',
    ],
    ('语文', '五下'): [
        '古诗三首', '祖父的园子', '月是故乡明', '梅花魂',
        '草船借箭', '景阳冈', '猴王出世', '红楼春趣',
        '人物描写一组', '刷子李',
        '威尼斯的小艇', '牧场之国', '金字塔',
    ],
    ('语文', '六上'): [
        '草原', '丁香结', '古诗词三首', '花之歌',
        '七律长征', '狼牙山五壮士', '开国大典', '灯光',
        '竹节人', '宇宙生命之谜', '故宫博物院',
        '桥', '穷人', '在柏林',
    ],
    ('语文', '六下'): [
        '北京的春节', '腊八粥', '古诗三首', '藏戏',
        '鲁滨逊漂流记', '骑鹅旅行记', '汤姆索亚历险记',
        '匆匆', '那个星期天', '古诗三首',
        '真理诞生于一百个问号之后', '表里的生物',
    ],
    ('语文', '七上'): [
        '春', '济南的冬天', '雨的四季',
        '古代诗歌四首', '散步', '秋天的怀念', '散文诗二首',
        '从百草园到三味书屋', '再塑生命的人', '窃读记',
        '纪念白求恩', '植树的牧羊人', '走一步再走一步',
    ],
    ('语文', '七下'): [
        '邓稼先', '说和做', '回忆鲁迅先生', '孙权劝学',
        '黄河颂', '老山界', '谁是最可爱的人',
        '阿长与山海经', '台阶', '卖油翁',
        '叶圣陶先生二三事', '驿路梨花', '短文两篇',
    ],
    ('语文', '八上'): [
        '消息二则', '首届诺贝尔奖颁发', '飞天凌空', '一着惊海天',
        '藤野先生', '回忆我的母亲', '列夫托尔斯泰', '美丽的颜色',
        '三峡', '短文二篇', '与朱元思书', '唐诗五首',
        '背影', '白杨礼赞', '散文二篇', '昆明的雨',
    ],
    ('语文', '八下'): [
        '社戏', '回延安', '安塞腰鼓', '灯笼',
        '大自然的语言', '阿西莫夫短文两篇', '大雁归来', '时间的脚印',
        '桃花源记', '小石潭记', '核舟记', '诗经二首',
        '最后一次讲演', '应有格物致知精神', '我一生中的重要抉择',
    ],
    ('语文', '九上'): [
        '沁园春雪', '我爱这土地', '乡愁', '你是人间的四月天',
        '敬业与乐业', '就英法联军远征中国致巴特勒上尉的信',
        '岳阳楼记', '醉翁亭记', '湖心亭看雪',
        '故乡', '我的叔叔于勒', '孤独之旅',
        '中国人失掉自信力了吗', '怀疑与学问', '谈创造性思维',
    ],
    ('语文', '九下'): [
        '祖国啊我亲爱的祖国', '梅岭三章', '短诗五首',
        '孔乙己', '变色龙', '溜索',
        '鱼我所欲也', '送东阳马生序', '词四首',
        '屈原', '天下第一楼', '枣儿',
    ],
    ('语文', '高一上'): [
        '沁园春长沙', '立在地球边上放号', '红烛', '百合花',
        '哦香雪', '喜看稻菽千重浪', '心有一团火温暖众人心',
        '短歌行', '梦游天姥吟留别', '登高', '琵琶行',
        '静女', '涉江采芙蓉', '虞美人', '鹊桥仙',
        '劝学', '师说', '反对党八股',
    ],
    ('语文', '高一下'): [
        '祝福', '林教头风雪山神庙', '装在套子里的人',
        '窦娥冤', '雷雨', '哈姆莱特',
        '青蒿素:人类征服疾病的一小步', '一名物理学家的教育历程',
        '谏太宗十思疏', '答司马谏议书', '阿房宫赋',
        '六国论', '烛之武退秦师', '鸿门宴',
    ],
    ('语文', '高二上'): [
        '荷塘月色', '故都的秋', '我与地坛',
        '论语十二章', '大学之道', '人皆有不忍人之心',
        '复活', '老人与海', '百年孤独',
        '以工匠精神雕琢时代品质', '在民族复兴的历史丰碑上',
    ],
    ('语文', '高二下'): [
        '社会历史的决定性基础', '改造我们的学习', '人的正确思想是从哪里来的',
        '修辞立其诚', '怜悯是人的天性',
        '边城', '一个消逝了的山村', '秦腔',
        '陈情表', '项脊轩志', '兰亭集序', '归去来兮辞',
        '种树郭橐驼传', '石钟山记',
    ],
    ('语文', '高三上'): [
        '中国建筑的特征', '说木叶', '作为生物的社会',
        '信息时代的语文生活', '整本书阅读', '经典常谈选读',
    ],
    ('语文', '高三下'): [
        '红楼梦整本书阅读', '高考作文复习', '文言文综合复习',
        '诗歌鉴赏复习', '现代文阅读复习', '语言知识运用',
    ],

    # ═══════════════════════════════════════════
    # 英语 (人教版PEP / 人教版Go for it / 人教版)
    # ═══════════════════════════════════════════
    ('英语', '三上'): [
        'Hello', 'Colours', 'Look at me', 'We love animals',
        'Lets eat', 'Happy birthday',
    ],
    ('英语', '三下'): [
        'Welcome back to school', 'My family', 'At the zoo',
        'Where is my car', 'Do you like pears', 'How many',
    ],
    ('英语', '四上'): [
        'My classroom', 'My schoolbag', 'My friends',
        'My home', 'Dinner is ready', 'Meet my family',
    ],
    ('英语', '四下'): [
        'My school', 'What time is it', 'Weather',
        'At the farm', 'My clothes', 'Shopping',
    ],
    ('英语', '五上'): [
        'Whats he like', 'My week', 'What would you like',
        'What can you do', 'There is a big bed', 'In a nature park',
    ],
    ('英语', '五下'): [
        'My day', 'My favourite season', 'My school calendar',
        'When is Easter', 'Whose dog is it', 'Work quietly',
    ],
    ('英语', '六上'): [
        'How can I get there', 'Ways to go to school',
        'My weekend plan', 'I have a pen pal',
        'What does he do', 'How do you feel',
    ],
    ('英语', '六下'): [
        'How tall are you', 'Last weekend', 'Where did you go',
        'Then and now', 'A farewell party',
    ],
    ('英语', '七上'): [
        'My names Gina', 'This is my sister', 'Is this your pencil',
        'Wheres my schoolbag', 'Do you have a soccer ball',
        'Do you like bananas', 'How much are these socks',
        'When is your birthday', 'My favorite subject is science',
    ],
    ('英语', '七下'): [
        'Can you play the guitar', 'What time do you go to school',
        'How do you get to school', 'Dont eat in class',
        'Why do you like pandas', 'Im watching TV',
        'Its raining', 'Is there a post office near here',
        'What does he look like', 'Id like some noodles',
        'How was your school trip', 'What did you do last weekend',
    ],
    ('英语', '八上'): [
        'Where did you go on vacation', 'How often do you exercise',
        'Im more outgoing than my sister', 'Whats the best movie theater',
        'Do you want to watch a game show', 'Im going to study computer science',
        'Will people have robots', 'How do you make a banana milk shake',
        'Can you come to my party', 'If you go to the party youll have a great time',
    ],
    ('英语', '八下'): [
        'Whats the matter', 'Ill help to clean up the city parks',
        'Could you please clean your room', 'Why dont you talk to your parents',
        'What were you doing when the rainstorm came',
        'An old man tried to move the mountains',
        'Whats the highest mountain in the world',
        'Have you read Treasure Island yet',
        'Have you ever been to a museum',
        'Ive had this bike for three years',
    ],
    ('英语', '九上'): [
        'How can we become good learners',
        'I think that mooncakes are delicious',
        'Could you please tell me where the restrooms are',
        'I used to be afraid of the dark',
        'What are the shirts made of',
        'When was it invented',
        'Teenagers should be allowed to choose their own clothes',
        'It must belong to Carla',
    ],
    ('英语', '九下'): [
        'I like music that I can dance to',
        'You are supposed to shake hands',
        'Sad movies make me cry',
        'Life is full of the unexpected',
        'I remember meeting all of you in Grade 7',
        'Grammar Review', 'Reading Comprehension',
    ],
    ('英语', '高一上'): [
        'Teenage Life', 'Travelling Around', 'Sports and Fitness',
        'Natural Disasters', 'Languages Around the World',
        '定语从句', '现在进行时表将来', '虚拟语气初步',
    ],
    ('英语', '高一下'): [
        'Cultural Heritage', 'Wildlife Protection', 'The Internet',
        'History and Traditions', 'Music',
        '非谓语动词', '定语从句(续)', '被动语态',
    ],
    ('英语', '高二上'): [
        'Science and Scientists', 'Looking into the Future',
        'The Art of Painting', 'Festivals and Customs',
        '名词性从句', '倒装句', '过去分词作状语',
    ],
    ('英语', '高二下'): [
        'Space Exploration', 'Healthy Lifestyle',
        'Environment Protection', 'Literature and Art',
        '虚拟语气', '独立主格', '强调句',
    ],
    ('英语', '高三上'): [
        '高考阅读理解', '完形填空', '语法填空', '短文改错',
        '书面表达', '听力训练', '词汇综合复习',
    ],
    ('英语', '高三下'): [
        '高考综合冲刺', '模拟训练', '真题精练',
        '查漏补缺', '写作模板', '高频考点回顾',
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

DIM6_PROMPT = """你是一位资深{subject}教师，负责为知识卡片生成教学图片的 prompt。

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


# ═══════════════════════════════════════════
# Skill 沉淀 — 将审查结果持久化到 optimizer.db
# ═══════════════════════════════════════════

def _init_content_review_table():
    """在 optimizer.db 中创建 content_review 表"""
    from self_optimizer import _get_conn as _opt_conn
    conn = _opt_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS content_review (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            grade TEXT DEFAULT '',
            dimension TEXT NOT NULL,
            severity TEXT DEFAULT 'none',
            overall_score REAL DEFAULT 0,
            issues_json TEXT DEFAULT '[]',
            suggestions_json TEXT DEFAULT '[]',
            raw_json TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_cr_card ON content_review(card_id);
        CREATE INDEX IF NOT EXISTS idx_cr_subject ON content_review(subject);
        CREATE INDEX IF NOT EXISTS idx_cr_severity ON content_review(severity);
        CREATE INDEX IF NOT EXISTS idx_cr_dim ON content_review(dimension);
    """)
    conn.commit()
    conn.close()


def save_review_to_skill(all_results: dict) -> int:
    """将 dim1/dim2/dim3/dim5 的审查结果存入 optimizer.db/content_review 表。
    返回写入的记录数。"""
    _init_content_review_table()
    from self_optimizer import _get_conn as _opt_conn
    conn = _opt_conn()
    count = 0

    # dim1: 教学有效性
    for r in all_results.get('dim1_teaching', []):
        if 'error' in r:
            continue
        conn.execute("""
            INSERT INTO content_review (card_id, subject, grade, dimension, severity, overall_score,
                                        issues_json, suggestions_json, raw_json)
            VALUES (?, ?, ?, 'dim1_teaching', ?, ?, ?, ?, ?)
        """, (
            r.get('card_id', ''), r.get('subject', ''), r.get('grade', ''),
            'low' if r.get('overall', 10) >= 7 else ('medium' if r.get('overall', 10) >= 5 else 'high'),
            r.get('overall', 0),
            json.dumps(r.get('issues', []), ensure_ascii=False),
            json.dumps(r.get('suggestions', []), ensure_ascii=False),
            json.dumps(r, ensure_ascii=False),
        ))
        count += 1

    # dim2: 对抗性内容
    for r in all_results.get('dim2_adversarial', []):
        if 'error' in r:
            continue
        conn.execute("""
            INSERT INTO content_review (card_id, subject, grade, dimension, severity, overall_score,
                                        issues_json, suggestions_json, raw_json)
            VALUES (?, ?, ?, 'dim2_adversarial', ?, ?, ?, ?, ?)
        """, (
            r.get('card_id', ''), r.get('subject', ''), r.get('grade', ''),
            r.get('severity', 'none'), 0,
            json.dumps([r.get('summary', '')], ensure_ascii=False),
            json.dumps([], ensure_ascii=False),
            json.dumps(r, ensure_ascii=False),
        ))
        count += 1

    # dim3: 闭环考试
    for r in all_results.get('dim3_exam', []):
        if 'error' in r:
            continue
        sev = 'none' if r.get('correct') else 'medium'
        conn.execute("""
            INSERT INTO content_review (card_id, subject, grade, dimension, severity, overall_score,
                                        issues_json, suggestions_json, raw_json)
            VALUES (?, ?, ?, 'dim3_exam', ?, ?, ?, ?, ?)
        """, (
            r.get('card_id', ''), r.get('subject', ''), r.get('grade', ''),
            sev, r.get('score', 0),
            json.dumps([r.get('knowledge_gap', '')] if r.get('knowledge_gap') else [], ensure_ascii=False),
            json.dumps([], ensure_ascii=False),
            json.dumps(r, ensure_ascii=False),
        ))
        count += 1

    # dim5: 教材对标
    for r in all_results.get('dim5_textbook', []):
        if 'error' in r:
            continue
        cov = r.get('coverage_pct', 100)
        sev = 'none' if cov >= 80 else ('low' if cov >= 60 else 'medium')
        conn.execute("""
            INSERT INTO content_review (card_id, subject, grade, dimension, severity, overall_score,
                                        issues_json, suggestions_json, raw_json)
            VALUES (?, ?, ?, 'dim5_textbook', ?, ?, ?, ?, ?)
        """, (
            f"{r.get('subject', '')}_{r.get('grade', '')}", r.get('subject', ''), r.get('grade', ''),
            sev, cov,
            json.dumps(r.get('blind_spots', []), ensure_ascii=False),
            json.dumps(r.get('out_of_scope', []), ensure_ascii=False),
            json.dumps(r, ensure_ascii=False),
        ))
        count += 1

    conn.commit()
    conn.close()
    return count


def get_skill_insights(subject: str = '', severity_min: str = 'low') -> list[dict]:
    """查询沉淀的审查结果，供 prompt 生成时参考。
    severity_min: 'low' / 'medium' / 'high' — 只返回≥此严重度的记录"""
    _init_content_review_table()
    from self_optimizer import _get_conn as _opt_conn
    sev_order = {'none': 0, 'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
    min_val = sev_order.get(severity_min, 1)

    conn = _opt_conn()
    if subject:
        rows = conn.execute("""
            SELECT card_id, subject, grade, dimension, severity, overall_score,
                   issues_json, suggestions_json, created_at
            FROM content_review
            WHERE subject = ?
            ORDER BY created_at DESC
            LIMIT 100
        """, (subject,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT card_id, subject, grade, dimension, severity, overall_score,
                   issues_json, suggestions_json, created_at
            FROM content_review
            ORDER BY created_at DESC
            LIMIT 200
        """).fetchall()
    conn.close()

    results = []
    for r in rows:
        row = dict(r)
        if sev_order.get(row['severity'], 0) >= min_val:
            row['issues'] = json.loads(row.pop('issues_json', '[]'))
            row['suggestions'] = json.loads(row.pop('suggestions_json', '[]'))
            results.append(row)
    return results


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
    parser.add_argument('--subjects', default='science',
                        help='学科范围: science(理科) / all(全学科) / 逗号分隔的科目名')
    parser.add_argument('--stages', default='初中,高中',
                        help='学段范围: 逗号分隔 (小学,初中,高中)')
    parser.add_argument('--save-skill', action='store_true',
                        help='将审查结果沉淀到 optimizer.db 的 content_review 表')
    args = parser.parse_args()

    dims = [int(x.strip()) for x in args.dims.split(',')]

    # 解析学科范围
    if args.subjects == 'science':
        subjects = _SCIENCE_SUBJECTS
    elif args.subjects == 'all':
        subjects = _ALL_SUBJECTS
    else:
        subjects = set(s.strip() for s in args.subjects.split(','))
    stages = [s.strip() for s in args.stages.split(',')]

    subj_label = '理科' if subjects == _SCIENCE_SUBJECTS else (
        '全学科' if subjects == _ALL_SUBJECTS else ','.join(sorted(subjects)))

    print("═" * 64)
    print("  知识卡深层复审 — 6 维度全面审计")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  维度: {dims}")
    print(f"  学科: {subj_label}  学段: {','.join(stages)}")
    print("═" * 64)

    keys = _load_keys()
    print(f"✅ 加载 {len(keys)} 个 API key")

    all_cards = load_all_cards(subjects=subjects, stages=stages)
    print(f"✅ 加载 {len(all_cards)} 张知识卡 ({subj_label})")

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
    print(f"  学科: {subj_label}  学段: {','.join(stages)}")
    print(f"  总卡片: {len(all_cards)}")

    # 保存 JSON
    output_path = args.output or os.path.join(BASE_DIR, '_deep_review_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"  结果已保存: {output_path}")

    # ── Skill 沉淀 ──
    if args.save_skill:
        print_header("Skill 沉淀")
        saved = save_review_to_skill(all_results)
        print(f"  ✅ 已沉淀 {saved} 条记录到 optimizer.db / content_review")


if __name__ == '__main__':
    main()
