#!/usr/bin/env python3
"""Patch generate_card_images.py: replace the system prompt and generate_image_prompt function"""
import re

filepath = 'generate_card_images.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# ═══════════════════════════════════════════════════════
# 1. Find and replace: from "# ─── Step 1:" to end of generate_image_prompt function  
# ═══════════════════════════════════════════════════════

# Locate the section to replace
start_marker = '# ─── Step 1: Generate image prompt ───'
end_marker = '# ─── Prompt Library: 保存 prompt 到 card_prompt_lib ───'

start_idx = content.index(start_marker)
end_idx = content.index(end_marker)

old_section = content[start_idx:end_idx]
print(f"Found section to replace: {len(old_section)} chars (line range)")

new_section = r'''# ─── Card-Type Visual Strategy Rules ───
CARD_TYPE_VISUAL_RULES = {
    '方法卡': {
        'solve_strategy': """运算方法类（含"笔算""竖式""列式"）：
   - ✅ 必须画出简化竖式！竖式是核心教学内容，不能省略
   - 竖式用彩色分层：第一层积(绿色)、第二层积(橙色)、最终和(红色大字)
   - 用色块+箭头标注关键步骤（如"错位"用虚线框高亮）
   - 竖式旁边放正误对比（✓正确对齐 vs ✗错误对齐）
   其他方法类（口算/估算/简便计算）：
   - 把数拆开→用色块区分→得到答案
   - 不画竖式，用直观色块分步
   几何方法类（面积/周长/体积）：
   - 画出实际图形+标注+辅助线
   - 公式代入用色块对应""",
    },
    '概念卡': {
        'solve_strategy': """用生活场景/实物图解释抽象概念：
   - 优先画生活实物（如分数=切披萨，千克=一袋米）
   - 概念名称超大展示，定义浓缩为≤6字金句
   - 不画运算过程，重在"是什么"而非"怎么算" """,
    },
    '辨析卡': {
        'solve_strategy': """左右并排对比，一目了然：
   - 左边 ✗(红色标记) 展示常见错误
   - 右边 ✓(绿色标记) 展示正确做法
   - 红圈/红框高亮差异点（只标1处最关键的）
   - 底部一句话总结区别""",
    },
    '公式卡': {
        'solve_strategy': """图形推导→公式→代入验证：
   - 用格子图/拼图直观推导公式由来
   - 公式本身超大醒目展示（占30%面积）
   - 举一个代入计算的小例子""",
    },
    '陷阱卡': {
        'solve_strategy': """先设坑→再揭秘：
   - 大字展示容易错的题目（设置悬念）
   - 展示错误答案并画叉
   - 揭示正确答案，红圈标出陷阱在哪
   - 钩子文案："90%同学做错" """,
    },
    '速算卡': {
        'solve_strategy': """慢方法vs快技巧对比：
   - 左边🐢常规慢方法(灰色，划掉)
   - 右边⚡速算技巧(彩色，高亮)
   - 速算步骤用色块分步展示
   - 强调"比普通方法快N倍" """,
    },
    '挑战卡': {
        'solve_strategy': """限时闯关+悬念：
   - 关卡编号金色醒目
   - 大题目展示（占30%）
   - 倒计时元素增加紧迫感
   - 答案区域用刮刮卡/折叠样式""",
    },
    '生活卡': {
        'solve_strategy': """生活场景→数学问题→实用解法：
   - 生活场景插画（占40%）
   - 气泡标注数学计算过程
   - 实用结论大字展示""",
    },
    '对战卡': {
        'solve_strategy': """左右分栏PK：
   - 左蓝(家长) VS 右粉(孩子)
   - 同类不同难度的题目
   - 计分栏增加互动感""",
    },
    '思维卡': {
        'solve_strategy': """有趣问题→可视化思维→优雅解法：
   - 情境问题大字展示
   - 思维过程用色块分步可视化（占45%）
   - 方法名+答案醒目展示""",
    },
}

def _detect_vertical_calc(card):
    """检测是否为需要画竖式的卡片（笔算/竖式/列式计算类）"""
    keywords = ['笔算', '竖式', '列式', '列竖式']
    title = card.get('title', '')
    definition = card.get('definition', '')
    question = card.get('example', {}).get('question', '')
    text = title + definition + question
    return any(k in text for k in keywords)

# ─── Step 1: Generate image prompt ───
PROMPT_SYSTEM_TEMPLATE = """你是一位拥有25年{subject}教学经验的特级教师 + 小红书爆款卡片设计师。

你的核心使命：用一道具体例题，让一个完全没学过的孩子，看一眼就「懂了！」

你的任务：将知识点转化为一段英文AI图片生成提示词。

══════ 教学思路（最重要！）══════

⚠️ 每张卡片 = 一道具体例题的"一图秒懂"讲解！

设计思路（必须严格按这个顺序）：

第一步：选择一道真实例题
   - 从知识点的例题中选一道最典型的题目
   - 这道题必须在卡片上清晰展示出来！
   - 例："840 ÷ 4 = ?"（大号，醒目）
   - 例："边长6dm的正方形，面积=?"
   - ⚠️ 题目是整张卡片的核心！没有题目的卡片是失败的

第二步：画出解题的关键步骤
{solve_strategy_block}

第三步：大字展示答案 + 口诀
   - 答案用超大字+鲜明色（"= 210"）
   - 一句口诀帮助记忆（≤10字）

⚠️ 绝对不要做的事：
   - ❌ 不画没有标签的裸箭头（看的人不知道箭头什么意思）
   - ❌ 箭头不超过3个
   - ❌ 不要让人猜"这是在解什么题"——题目必须清晰可见
   - ❌ 不要只有口诀/结论，没有具体例题
   - ❌ 不要把解题过程中的数字写错（必须和提供的例题数字完全一致！）

══════ 视觉设计 ══════

1. 核心教学图（占 ≥ 45%）：
   - 大、简洁、直观——用最简方式把知识点"画"出来
   - 优先用实物/场景图，而非抽象符号
   - 颜色编码区分不同概念

2. 简洁原则：
   - 全卡最多4个视觉区块：标题 / 核心图 / 金句+对比 / 口诀
   - 每个区块之间有大间距
   - ≥ 25% 留白
   - 箭头 ≤ 3个，都带标签

3. 小老师卡通：一个可爱角色 + ≤6字气泡

══════ 配色（要吸引人！）══════

⚠️ 小红书风格：鲜明、温暖、有活力！不要太淡！

- 背景：渐变色（不是纯色！）
  选一个主题渐变：珊瑚粉渐变(#FF9A9E→#FAD0C4) 或 薄荷蓝渐变(#A1C4FD→#C2E9FB) 或 蜜桃橙渐变(#FFD89B→#FFA7A7) 或 薰衣草紫渐变(#E8D5F5→#D9AAF5)
- 标题banner：鲜明饱和色（如亮珊瑚#FF6B6B / 活力橙#FF9F43 / 明亮蓝#54A0FF / 清新绿#5ECE7B）
- 内容区块：白色或浅奶油色圆角卡片(带微妙阴影)
- 重点数字/公式：用鲜明对比色（红/橙/蓝）超大加粗
- ✓ 用翠绿 #2ED573, ✗ 用亮红 #FF4757
- 装饰：2-3个手绘小图标（铅笔/灯泡/星星），颜色与主题色呼应
- 整体：饱和度中高，温暖有活力，像一张让人想收藏的笔记

══════ 文字原则 ══════

- 全卡中文 ≤ 35字
- 标题 ≤ 4字（超大72pt粗体，白色/深色看背景）
- 核心金句 ≤ 6字（大号48pt加粗，鲜明色）
- 口诀 ≤ 10字（便签纸风格）
- 气泡 ≤ 6字
- ❌ 没有任何超过6字的连续文字
- ❌ 不写段落/定义/解释
- 字体：圆体/黑体粗笔画，❌ 不用细体/草书

══════ 布局（从上到下，围绕例题展开）══════

[CANVAS] 竖屏3:4, 渐变背景, 风格
[TITLE] 顶部10%: 鲜色banner + 标题(≤4字白色超大) + 小标签
[PROBLEM] 15%: ⚠️例题(白色圆角卡片内, 超大醒目字体展示具体题目, 如"840 ÷ 4 = ?")
[SOLVE] 中间40%: 解题关键步骤(根据题型选择最合适的视觉方式: 竖式/色块分步/图形/对比)
[ANSWER] 12%: 答案(超大鲜明色, 如 "= 210") + 口诀(色彩便签风, ≤10字)
[BOTTOM] 底部8%: 小老师卡通+气泡(≤6字)
[STYLE] 风格关键词

══════ 输出 ══════

只输出英文提示词，不输出其他文字。

提示词要求：
- 开头写: "IMPORTANT: All visible text MUST be Simplified Chinese (简体中文). LARGE BOLD thick-stroke rounded sans-serif. Max 35 Chinese chars total, each block ≤6 chars. No English. Clean spacious layout, ≥25% whitespace."
- 中文用引号包裹
- 指定字号（"72pt bold", "48pt"等）
- ⚠️ 必须有一道清晰的例题展示在卡面上（如"840 ÷ 4 = ?"），字号要大，位置要醒目
- ⚠️ 解题过程中所有数字必须和例题完全一致，不能编造或搞混数字
- ⚠️ 根据题型选择最佳视觉方式：笔算类画竖式（彩色分层），口算类用色块拆分，几何类画图形
- ⚠️ 箭头≤3个且必须有中文标签，不画裸箭头
- ✓/✗对比只一组（如有），大图并排，红圈标差异
- 答案用超大鲜明色展示
- 背景用渐变色（写具体色号），标题用饱和色banner
- 解题图描述要详细但图本身要简洁直观
- 长度: 350-500英文单词"""

def generate_image_prompt(card, subject, grade, semester, api_key):
    """Step 1: 用文字模型生成精简但视觉丰富的提示词（按卡片类型选择视觉策略）"""
    
    # ── 根据卡片类型选择视觉策略 ──
    card_type = card.get('type', '方法卡')
    type_rules = CARD_TYPE_VISUAL_RULES.get(card_type, CARD_TYPE_VISUAL_RULES['方法卡'])
    is_vertical_calc = _detect_vertical_calc(card)
    
    # 构建解题策略指导块
    if is_vertical_calc:
        solve_block = """   ⚠️ 这是笔算/竖式类卡片，竖式本身就是教学内容！
   - ✅ 必须画出简化竖式（这是本卡的核心！）
   - 竖式用彩色分层：第一层积(绿色)、第二层积(橙色)、最终和(红色超大)
   - 十位乘的那层必须明确画出"向左错一位"（用虚线/色块高亮错位）
   - 竖式旁可放一个正误对比小图（✓正确对齐 vs ✗错误对齐）
   - 竖式中每个数字必须和例题完全一致，不能编造数字！
   - 竖式保持简洁清晰，用颜色区分而非文字堆砌"""
    else:
        solve_block = type_rules['solve_strategy']
    
    system_prompt = PROMPT_SYSTEM_TEMPLATE.format(
        subject=subject,
        solve_strategy_block=solve_block
    )
    
    # 精简卡片信息
    points = card['core_points'][:4]
    
    # 提取公式（扩大截取长度）
    formulas = []
    clean_points = []
    for p in points:
        if any(c in p for c in '=÷×+−≥≤<>°²³∠'):
            formulas.append(p[:80])
        else:
            clean_points.append(p[:80])
    
    # 提取易错点作为正误对比素材（扩大到200字，保留完整竖式布局）
    mistakes_info = ''
    if card.get('mistakes'):
        m = card['mistakes'][0]
        mistakes_info = f"\n常见错误(⚠️ 必须用于正误对比图示，确保数字正确):\n  ❌ 错误做法: {m['wrong'][:200]}\n  ✅ 正确做法: {m['correct'][:200]}"
    
    # 提取例题的完整信息（题目+解题步骤，给AI完整上下文）
    example_info = ''
    example_steps = ''
    if card.get('example'):
        ex = card['example']
        example_info = ex['question'][:120]
        # 传递完整的解题步骤，让AI理解正确的解法
        if ex.get('steps'):
            steps_text = '\n'.join(f'  {i+1}. {s}' for i, s in enumerate(ex['steps']))
            example_steps = f"\n【解题步骤】(图片中的解法必须与此一致！):\n{steps_text[:600]}"
        if ex.get('answer'):
            example_steps += f"\n【正确答案】: {ex['answer']}"
    
    card_info = f"""学科: {subject}
年级: {grade}{semester}
标题: {card['title']}
类型: {card_type}

【⚠️ 必须展示的例题】(这是整张卡片的核心！题目必须醒目显示在卡片上):
{example_info if example_info else '请根据知识点自行构造一道最典型的例题'}
{example_steps}

【知识点核心】: {card['definition'][:120]}
【关键词】(提炼≤3个，每个≤6字):
{chr(10).join('• ' + p for p in clean_points[:3])}
{('【公式/数字】(超大展示): ' + ' | '.join(formulas)) if formulas else ''}
【口诀】(≤10字): {card['memory_tip'][:50]}
{mistakes_info if mistakes_info else ''}
难度: {card['difficulty']}/5
{'⚠️ 特别提醒：这是笔算竖式类卡片，图片中必须画出正确的竖式，每个数字不能错！' if is_vertical_calc else ''}"""

    contents = [
        {'role': 'user', 'parts': [{'text': f'{system_prompt}\n\n--- 知识点信息 ---\n{card_info}'}]}
    ]
    
    # thinking budget 单独控制，不占用 maxOutputTokens
    gen_config = {
        'maxOutputTokens': 8192,
        'temperature': 0.85,
        'thinkingConfig': {'thinkingBudget': 2048}
    }
    resp = gemini_call(TEXT_MODEL, contents, api_key, gen_config=gen_config)
    if not resp:
        return None
    
    try:
        candidates = resp.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            # Debug: 列出所有 parts 的类型和长度
            for i, part in enumerate(parts):
                if 'thought' in part and part.get('thought'):
                    print(f'      [part {i}] thinking, {len(part.get("text",""))} chars')
                elif 'text' in part:
                    print(f'      [part {i}] text, {len(part["text"])} chars')
            
            # 取最长的非 thinking text part
            best_text = ''
            for part in parts:
                if 'text' in part and not part.get('thought', False):
                    txt = part['text'].strip()
                    if len(txt) > len(best_text):
                        best_text = txt
            if len(best_text) > 50:
                return best_text
            
            # fallback: 取最长的任意 text part
            for part in parts:
                if 'text' in part:
                    txt = part['text'].strip()
                    if len(txt) > len(best_text):
                        best_text = txt
            if len(best_text) > 50:
                return best_text
    except Exception as e:
        print(f'    [Parse error] {e}')
    return None

'''

content = content[:start_idx] + new_section + content[end_idx:]

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"✅ Patched {filepath}")
print(f"   Old section: {len(old_section)} chars")
print(f"   New section: {len(new_section)} chars")

# Verify
with open(filepath, 'r', encoding='utf-8') as f:
    verify = f.read()

assert 'CARD_TYPE_VISUAL_RULES' in verify, "Missing CARD_TYPE_VISUAL_RULES"
assert '_detect_vertical_calc' in verify, "Missing _detect_vertical_calc"
assert 'solve_strategy_block' in verify, "Missing solve_strategy_block"
assert "m['wrong'][:200]" in verify, "Truncation not updated"
assert 'example_steps' in verify, "Missing example_steps"
assert '不画完整竖式' not in verify, "Old rule still present"
print("✅ All assertions passed")
