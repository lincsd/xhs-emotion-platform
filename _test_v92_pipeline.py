"""
v9.2 全链路验证 — 用真实卡片数据测试 skill_schema + prompt_builder + prompt_auditor
对比 有/无模块 的 Prompt 结构差异，收集审核报告。

用法: python _test_v92_pipeline.py
不需要 API 调用（本测试只验证模块输出质量，不生成图片）。
"""

import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skill_schema import get_skill_schema, match_sub_type, build_skill_injection, get_layout_checklist
from prompt_builder import build_skill_enhanced_prompt, build_layout_skeleton, build_content_fill, get_visual_strategy
from prompt_auditor import audit_prompt, format_audit_summary

# ═════════════════════════════════════════
# 12 张真实卡片数据 (从 knowledge_cards 提取)
# ═════════════════════════════════════════

SAMPLE_CARDS = [
    # ── 数学 ──
    {
        "_source": "数学_三下.json (方法卡)",
        "card_id": "01-03", "full_id": "数学-三下-01-03",
        "title": "根据一个方向确定其他方向", "type": "方法卡",
        "difficulty": 3, "importance": 4,
        "definition": "只要知道一个方向，我们就能利用方向之间的关系，找出其他所有的方向。",
        "core_points": [
            "东和西是相对的，南和北是相对的。",
            "面朝北，背面是南，左边是西，右边是东。",
            "面朝南，背面是北，左边是东，右边是西。",
        ],
        "example": {
            "question": "小丽面朝南方站立。请问，她的背面是什么方向？",
            "steps": ["小丽面朝南方，与南相对的方向是北，背面是北方。", "面朝南时，左手边是东方。"],
            "answer": "她的背面是北方，左手边是东方，右手边是西方。"
        },
        "mistakes": [{"wrong": "混淆左右手对应的方向", "correct": "用口诀'面北背南，左西右东'来判断。"}],
        "memory_tip": "面北背南，左西右东；面南背北，左东右西。",
        "subject": "数学", "grade": "三年级", "semester": "下册",
    },
    {
        "_source": "数学_四上.json (概念卡)",
        "card_id": "01-01", "full_id": "数学-四上-01-01",
        "title": "数位、计数单位和数级", "type": "概念卡",
        "difficulty": 2, "importance": 5,
        "definition": "计数单位是数位的名称，如个、十、百、千等，每相邻两个计数单位间的进率都是十。",
        "core_points": [
            "十进制计数法：每相邻两个计数单位间的进率都是十。",
            "数位：数字所在的位，如个位、十位。",
            "数级：个级、万级、亿级。",
        ],
        "example": {
            "question": "说出345678901这个数中，数字'5'在哪个数位上？",
            "steps": ["从右往左数。", "'5'在十万位上，表示5个十万。"],
            "answer": "数字'5'在十万位上，表示5个十万。"
        },
        "mistakes": [
            {"wrong": "将数位和计数单位混淆", "correct": "'5'在十万位上，它的计数单位是十万。"},
        ],
        "memory_tip": "数位是位置，单位是名称，四位一分级，十进是根本。",
        "subject": "数学", "grade": "四年级", "semester": "上册",
    },
    {
        "_source": "数学_五上.json (公式卡)",
        "card_id": "05-01", "full_id": "数学-五上-05-01",
        "title": "平行四边形的面积", "type": "公式卡",
        "difficulty": 2, "importance": 4,
        "definition": "平行四边形的面积等于它的底乘以高。",
        "core_points": [
            "公式：S = a × h",
            "底和高是对应的，高必须是底边上的高。",
            "可以将平行四边形剪拼成长方形来推导公式。",
        ],
        "example": {
            "question": "一个平行四边形的底是5厘米，高是3厘米，面积是多少？",
            "steps": ["确定底a=5厘米，高h=3厘米", "S = a × h = 5 × 3 = 15"],
            "answer": "15平方厘米。"
        },
        "mistakes": [
            {"wrong": "将平行四边形的邻边作为高", "correct": "高必须是底边上的垂线段的长度。"},
        ],
        "memory_tip": "平行四边形，底乘高，面积公式记心房。",
        "subject": "数学", "grade": "五年级", "semester": "上册",
    },
    {
        "_source": "数学_五上.json (辨析卡)",
        "card_id": "02-05", "full_id": "数学-五上-02-05",
        "title": "解决问题中的近似数（进一法、去尾法）", "type": "辨析卡",
        "difficulty": 4, "importance": 5,
        "definition": "根据具体情况，除了四舍五入法，有时需要采用进一法或去尾法来取商的近似值。",
        "core_points": [
            "进一法：有余数就进1。求至少需要多少个容器。",
            "去尾法：舍去小数部分。求最多能做多少件。",
            "关键是理解题目的实际意义。",
        ],
        "example": {
            "question": "一根绳子长25米，剪成每段1.8米，最多能剪多少段？",
            "steps": ["25 ÷ 1.8 ≈ 13.88…", "去尾法，最多能剪13段。"],
            "answer": "最多能剪13段。"
        },
        "mistakes": [
            {"wrong": "25÷1.8≈14 (四舍五入)", "correct": "应采用去尾法，最多能剪13段。"},
        ],
        "memory_tip": "实际问题多变化，取舍方法要细察。",
        "subject": "数学", "grade": "五年级", "semester": "上册",
    },
    # ── 英语 ──
    {
        "_source": "英语_四上.json (词汇卡)",
        "card_id": "01-01", "full_id": "英语-四上-01-01",
        "title": "词汇：教室物品", "type": "词汇卡",
        "difficulty": 2, "importance": 5,
        "definition": "学习描述教室里的常见物品的英语单词。",
        "core_points": [
            "desk /dɛsk/ n. 课桌",
            "chair /tʃɛər/ n. 椅子",
            "board /bɔːrd/ n. 黑板",
            "light /laɪt/ n. 灯",
        ],
        "example": {"question": "看图写单词：这是一张课桌。", "steps": ["图片提示：一张课桌"], "answer": "desk"},
        "mistakes": [{"wrong": "desck", "correct": "desk"}],
        "memory_tip": "desk和chair是好朋友，一个用来写，一个用来坐。",
        "subject": "英语", "grade": "四年级", "semester": "上册",
    },
    {
        "_source": "英语_四上.json (句型卡)",
        "card_id": "01-02", "full_id": "英语-四上-01-02",
        "title": "句型：询问和回答物品", "type": "句型卡",
        "difficulty": 2, "importance": 5,
        "definition": "学习用 What's this? 和 What's that? 询问物品，并用 It's a... 回答。",
        "core_points": [
            "What's this? (指近处的物品)",
            "What's that? (指远处的物品)",
            "It's a [物品]. / It's an [物品].",
        ],
        "example": {"question": "远处有一扇门。提问并回答。", "steps": ["选择正确疑问句 What's that?"], "answer": "A: What's that? B: It's a door."},
        "mistakes": [
            {"wrong": "What's this? It's door.", "correct": "What's this? It's a door."},
        ],
        "memory_tip": "近处用this，远处用that，回答都是It's a/an...",
        "subject": "英语", "grade": "四年级", "semester": "上册",
    },
    {
        "_source": "英语_四上.json (语法卡)",
        "card_id": "02-03", "full_id": "英语-四上-02-03",
        "title": "一般疑问句 Is this/that...?", "type": "语法卡",
        "difficulty": 3, "importance": 4,
        "definition": "学习用 Is this/that...? 提问，并用 Yes, it is. 或 No, it isn't. 回答。",
        "core_points": [
            "结构：Is + this/that + a/an + 名词?",
            "肯定回答：Yes, it is.",
            "否定回答：No, it isn't.",
        ],
        "example": {"question": "老师指着一个橡皮问：Is this an eraser?", "steps": ["判断物品是否是橡皮"], "answer": "Yes, it is."},
        "mistakes": [
            {"wrong": "Is this a book? Yes, it.", "correct": "Is this a book? Yes, it is."},
        ],
        "memory_tip": "Is this/that开头问，Yes, it is.或No, it isn't.来回答。",
        "subject": "英语", "grade": "四年级", "semester": "上册",
    },
    {
        "_source": "英语_四上_爆款.json (易混词陷阱卡)",
        "card_id": "T1-01", "full_id": "英语-四上-T1-01",
        "title": "this和that分不清？一张图搞定！", "type": "易混词陷阱卡",
        "difficulty": 2, "importance": 4,
        "definition": "this (这个) 指代近处的事物；that (那个) 指代远处的事物。",
        "core_points": [
            "this：离说话人近的东西。",
            "that：离说话人远的东西。",
            "两者都用于指代单数名词。",
        ],
        "example": {"question": "看图选择：指着桌子上的书本，应该说 What's ______?", "steps": ["图片展示近处"], "answer": "A. this"},
        "mistakes": [
            {"wrong": "What's that? (指着手边的铅笔)", "correct": "What's this? (指着手边的铅笔)"},
        ],
        "memory_tip": "近用this，远用that！",
        "emotion_hook": "别再傻傻分不清啦！",
        "subject": "英语", "grade": "四年级", "semester": "上册",
    },
]


def divider(title):
    return f'\n{"═" * 60}\n  {title}\n{"═" * 60}'


def run_tests():
    print(divider('v9.2 全链路验证 — 12张真实卡片'))
    
    results = []
    
    for i, card in enumerate(SAMPLE_CARDS, 1):
        source = card.pop('_source', '')
        card_type = card.get('type', '?')
        title = card.get('title', '?')
        subject = card.pop('subject', '数学')
        grade = card.pop('grade', '三年级')
        semester = card.pop('semester', '下册')
        
        print(f'\n{"─" * 50}')
        print(f'  Card #{i}: [{card_type}] {title}')
        print(f'  Source: {source}')
        print(f'{"─" * 50}')
        
        # ── A: Skill Schema 查询 ──
        schema = get_skill_schema(card_type)
        if schema:
            print(f'  Schema: ✅ {schema.card_type} ({len(schema.layout_blocks)} blocks, {len(schema.sub_types)} sub-types)')
            sub = match_sub_type(card_type, card)
            if sub:
                print(f'  SubType: {sub.name} → {sub.visual_method}')
            else:
                print(f'  SubType: (no match)')
            
            checklist = get_layout_checklist(card_type)
            block_names = [c['name'] for c in checklist[:5]]
            print(f'  Layout: {" > ".join(block_names)}')
        else:
            print(f'  Schema: ⏭️ 未注册 (英语/{card_type} 无 SkillSchema)')
        
        # ── B: Visual Strategy ──
        vs = get_visual_strategy(card_type, card)
        if vs:
            print(f'  Visual Strategy: {vs[:80]}...' if len(vs) > 80 else f'  Visual Strategy: {vs}')
        else:
            print(f'  Visual Strategy: (none)')
        
        # ── C: Prompt Builder (两阶段) ──
        enhanced = build_skill_enhanced_prompt(card_type, card, subject, grade, semester)
        if enhanced:
            # 统计字符
            lines = enhanced.strip().split('\n')
            print(f'  Enhanced Prompt: ✅ {len(enhanced)}字, {len(lines)}行')
            
            # 检查关键元素
            has_skeleton = 'LAYOUT' in enhanced.upper() or '区块' in enhanced or 'zone' in enhanced.lower()
            has_fill = 'CONTENT' in enhanced.upper() or card.get('title', '') in enhanced
            has_rules = 'RULE' in enhanced.upper() or '禁止' in enhanced or 'forbidden' in enhanced.lower()
            print(f'  Skeleton: {"✅" if has_skeleton else "❌"} | Fill: {"✅" if has_fill else "❌"} | Rules: {"✅" if has_rules else "❌"}')
        else:
            print(f'  Enhanced Prompt: ⏭️ (无 Schema，跳过)')
        
        # ── D: Prompt Auditor (模拟 prompt) ──
        # 构造一个模拟的 AI 生成 prompt，包含基本元素
        mock_prompt = _build_mock_prompt(card, card_type, subject)
        mock_manifest = _build_mock_manifest(card)
        
        audit = audit_prompt(mock_prompt, card_type, card, mock_manifest)
        summary = format_audit_summary(audit)
        print(f'  Audit: {summary}')
        
        # 详细问题
        for iss in audit.issues[:3]:
            sev_icon = {'high': '🔴', 'medium': '🟡', 'low': '🔵'}.get(iss.severity, '⚪')
            print(f'    {sev_icon} [{iss.category}] {iss.description[:60]}')
        
        # ── E: 英语专用审核 ──
        if subject == '英语':
            try:
                from english_card_auditor import rule_audit_english, is_english_card
                if is_english_card(card, subject):
                    # 模拟 OCR 文本
                    mock_ocr = _build_mock_ocr(card)
                    eng_result = rule_audit_english(
                        mock_ocr, card, mock_manifest,
                        prompt_text=mock_prompt,
                        eng_key_phrase=card.get('_eng_key_phrase', card.get('title', '')),
                    )
                    print(f'  English Audit: {eng_result.summary}')
                    for iss in eng_result.issues[:3]:
                        sev_icon = {'critical': '🔴', 'major': '🟡', 'minor': '🔵'}.get(iss.severity, '⚪')
                        print(f'    {sev_icon} [{iss.dimension}] {iss.description[:60]}')
            except ImportError:
                print(f'  English Audit: ⏭️ (english_card_auditor 不可用)')
        
        results.append({
            'card_type': card_type,
            'title': title,
            'has_schema': schema is not None,
            'has_enhanced': enhanced is not None and len(enhanced) > 0,
            'audit_coverage': audit.coverage_pct,
            'audit_verdict': audit.verdict,
            'audit_issues': len(audit.issues),
        })
    
    # ── 汇总 ──
    print(divider('汇总'))
    print(f'{"#":>2} {"类型":<10} {"Schema":<8} {"Enhanced":<10} {"Coverage":>8} {"Verdict":<7} {"Issues":>6}')
    print(f'{"─"*2} {"─"*10} {"─"*8} {"─"*10} {"─"*8} {"─"*7} {"─"*6}')
    for i, r in enumerate(results, 1):
        sch = '✅' if r['has_schema'] else '⏭️'
        enh = '✅' if r['has_enhanced'] else '⏭️'
        print(f'{i:>2} {r["card_type"]:<10} {sch:<8} {enh:<10} {r["audit_coverage"]:>6.0f}% {r["audit_verdict"]:<7} {r["audit_issues"]:>6}')
    
    # 统计
    with_schema = sum(1 for r in results if r['has_schema'])
    with_enhanced = sum(1 for r in results if r['has_enhanced'])
    avg_coverage = sum(r['audit_coverage'] for r in results) / max(len(results), 1)
    pass_count = sum(1 for r in results if r['audit_verdict'] == 'pass')
    
    print(f'\nSchema覆盖: {with_schema}/{len(results)}')
    print(f'Enhanced覆盖: {with_enhanced}/{len(results)}')
    print(f'平均审计覆盖率: {avg_coverage:.1f}%')
    print(f'审计通过率: {pass_count}/{len(results)}')
    
    if with_schema < len(results):
        missing = [r['card_type'] for r in results if not r['has_schema']]
        unique_missing = list(set(missing))
        print(f'\n⚠️ 缺少 Schema 的类型: {", ".join(unique_missing)}')
        print(f'   建议: 在 skill_schema.py 中注册这些类型')


def _build_mock_prompt(card, card_type, subject):
    """构造一个模拟的 AI 输出 prompt (用于审计测试)"""
    title = card.get('title', '')
    definition = card.get('definition', '')
    example = card.get('example', {})
    q = example.get('question', '') if isinstance(example, dict) else str(example)
    answer = example.get('answer', '') if isinstance(example, dict) else ''
    tip = card.get('memory_tip', '')
    
    prompt = f"""Create a 3:4 vertical knowledge card about "{title}".

HEADER ZONE: Title "{title}" in large bold colorful text at the top center.
Background: vibrant gradient (coral to peach), white rounded-corner card.

MAIN TEACHING ZONE:
- Definition: {definition}
- Example problem: {q}
- Show the solution using color-coded blocks with step-by-step breakdown.
- Answer displayed prominently: "{answer}"

CONTRAST ZONE:
- ❌ Common mistake highlighted in red
- ✅ Correct approach highlighted in green

BOTTOM ZONE:
- Mnemonic slogan: "{tip}"
- Small teacher mascot character (≤10% area) in bottom-right corner.

Style: Xiaohongshu viral card aesthetic, ≥25% whitespace, thick bold Chinese text.
Total Chinese characters ≤ 35.
"""
    return prompt


def _build_mock_manifest(card):
    """构造模拟的 TEXT_MANIFEST"""
    title = card.get('title', '')
    tip = card.get('memory_tip', '')
    manifest = {'TITLE': title[:8]}
    if tip:
        manifest['SLOGAN'] = tip[:12]
    return manifest


def _build_mock_ocr(card):
    """构造模拟的 OCR 文本 (假设图片渲染正确)"""
    texts = []
    title = card.get('title', '')
    texts.append(title)
    
    # 添加 core_points 中的关键词
    for p in card.get('core_points', [])[:3]:
        texts.append(str(p)[:40])
    
    # 添加对比符号
    if card.get('mistakes'):
        texts.extend(['❌', '✅'])
        m = card['mistakes'][0]
        if m.get('wrong'):
            texts.append(str(m['wrong'])[:40])
        if m.get('correct'):
            texts.append(str(m['correct'])[:40])
    
    # 添加口诀
    if card.get('memory_tip'):
        texts.append(card['memory_tip'][:30])
    
    return texts


if __name__ == '__main__':
    run_tests()
