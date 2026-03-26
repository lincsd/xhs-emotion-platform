#!/usr/bin/env python3
"""
考卷真题专题 — 小红书笔记生成模板
=================================
新增2种考卷专用笔记模板：考前冲刺型、满分攻略型
可集成到 server.py 的 _generate_xhs_note 中使用
"""

# ============ 考卷专题笔记模板定义 ============

# 新增模板名称和对应的卡片类型映射
EXAM_TEMPLATE_CARD_MAP = {
    '考前冲刺型': [
        '填空满分卡', '选择秒杀卡', '计算零失误卡', '判断火眼卡',
        '应用题拆解卡', '操作题规范卡',
        '拼写零错卡', '默写满分卡', '作文得分卡',
        '听力得分卡', '填空必会卡', '写作模板卡'
    ],
    '满分攻略型': [
        '填空满分卡', '选择秒杀卡', '选择审题卡', '选择攻略卡',
        '计算零失误卡', '判断火眼卡', '应用题拆解卡', '操作题规范卡',
        '拼写零错卡', '默写满分卡', '阅读答题卡', '句子变换卡', '作文得分卡',
        '听力得分卡', '填空必会卡', '匹配速解卡', '阅读通关卡', '写作模板卡'
    ],
}

# 考卷专题笔记模板 Prompt 风格说明（注入到 note_prompt 中）
EXAM_TEMPLATE_STYLES = """
- 考前冲刺型：倒计时紧迫感→必考清单→快速提分技巧→检查提醒→加油打气
  适用于考前1-2周发布，标题带"考前""冲刺""最后X天"等关键词
  正文结构：⏰考前提醒 → 📋必考清单 → ⚡提分技巧 → ✅考场注意事项 → 💪加油鼓励
  情绪曲线：紧迫→安心→自信→从容

- 满分攻略型：题型拆解→得分策略→答题模板→避坑清单→满分示范
  适用于平时复习和系统备考，标题带"满分""攻略""不丢分"等关键词  
  正文结构：🎯题型分析 → 📝审题技巧 → 💡答题模板 → ⚠️易错清单 → 🏆满分示范
  情绪曲线：认识问题→掌握方法→反复练习→信心满满
"""

# 考卷卡片特有字段提取（用于 note prompt 中）
EXAM_CARD_FIELDS = [
    'exam_frequency',    # 考试频率
    'score_weight',      # 分值占比
    'fill_strategy',     # 填空审题策略
    'choice_tricks',     # 选择秒杀技巧
    'calc_checklist',    # 计算检查清单
    'judge_traps',       # 判断陷阱类型
    'problem_model',     # 应用题建模方法
    'operation_steps',   # 操作规范步骤
    'high_freq_words',   # 高频必考词
    'audit_points',      # 审题关键点
    'must_dictate',      # 必默篇目
    'answer_templates',  # 答题模板
    'transform_rules',   # 句子变换规则
    'writing_formulas',  # 作文得分公式
    'listening_strategy', # 听力策略
    'choice_focus',      # 选择题考点
    'must_know_words',   # 必会词汇
    'match_method',      # 匹配解题法
    'reading_skills',    # 阅读技巧
    'writing_frames',    # 写作框架
]


def extract_exam_card_text(card):
    """
    提取考卷卡片的文本信息（比通用卡片多提取考卷专有字段）
    """
    text = f"[{card.get('type', '')}] {card.get('title', '')}\n"
    
    if card.get('definition'):
        text += f"  核心策略: {card['definition']}\n"
    
    if card.get('exam_frequency'):
        text += f"  考试频率: {card['exam_frequency']}\n"
    
    if card.get('score_weight'):
        text += f"  分值占比: {card['score_weight']}\n"
    
    points = card.get('core_points', [])
    if points:
        text += f"  答题要点: {'; '.join(points[:5])}\n"
    
    ex = card.get('example', {})
    if isinstance(ex, dict) and ex:
        text += f"  真题示例: {ex.get('question', '')} → {ex.get('answer', '')}\n"
    
    if card.get('memory_tip'):
        text += f"  答题口诀: {card['memory_tip']}\n"
    
    if card.get('emotion_hook'):
        text += f"  情绪钩子: {card['emotion_hook']}\n"
    
    mistakes = card.get('mistakes', [])
    if mistakes:
        for m in mistakes[:2]:
            if isinstance(m, dict):
                text += f"  ❌错误: {m.get('wrong', '')} → ✅正确: {m.get('correct', '')}\n"
    
    # 提取考卷专有字段
    for field in EXAM_CARD_FIELDS:
        val = card.get(field)
        if val:
            if isinstance(val, list):
                text += f"  {field}: {'; '.join(str(v) for v in val[:5])}\n"
            else:
                text += f"  {field}: {val}\n"
    
    return text


# ============ 考卷专题笔记 Prompt 模板 ============

EXAM_NOTE_PROMPT_TEMPLATE = """你是一位小红书教育垂类TOP博主，专注制作"考前冲刺"和"满分攻略"类高互动笔记。
你对整理考试真题、提炼答题技巧、制作考前必看清单非常在行，你的笔记平均收藏率超过20%。

以下是{subject} {grade_short}的考卷真题攻略卡片数据：
{cards_text}

请基于以上卡片内容，用「{template}」模板风格，生成一篇完整的小红书笔记。

模板风格说明：
{template_style}

笔记内容要求：
1. 标题要有紧迫感/实用感，让家长忍不住点击
2. 正文要按题型清晰分区，每个题型用emoji标记
3. 必须包含具体的真题示例（来自卡片数据）
4. 必须包含答题口诀（朗朗上口，便于记忆）
5. 末尾要有互动引导（评论区打卡/收藏备用）
6. 语气亲切自然，像一个经验丰富的家长在分享

⚠️ 严格字数限制：
- 标题 ≤ 20字（含emoji）
- 正文 ≤ 800字
- 候选标题每条 ≤ 20字

请输出JSON格式（不要markdown代码块），包含：
{{
  "note_id": "{subject}_{grade_short}_{template}_考卷",
  "title": "标题（≤20字）",
  "template": "{template}",
  "card_ids": [使用的card_id列表],
  "hashtags": "#小学数学 #期末复习 ... （8-12个标签，包含科目+年级+考试相关）",
  "narrative_arc": "叙事弧线",
  "emotion_curve": ["紧迫/好奇", "焦虑", "掌握方法", "信心", "分享"],
  "carousel": [
    {{"slide": 1, "type": "封面", "desc": "封面描述（体现考试主题+紧迫感）"}},
    {{"slide": 2, "type": "题型攻略", "desc": "第一个题型攻略"}},
    {{"slide": 3, "type": "题型攻略", "desc": "第二个题型攻略"}},
    {{"slide": 4, "type": "口诀总结", "desc": "所有口诀汇总一张图"}},
    {{"slide": 5, "type": "互动页", "desc": "考前加油+互动引导"}}
  ],
  "title_candidates": [
    {{"title": "候选1", "score": 8}},
    {{"title": "候选2", "score": 9}},
    {{"title": "候选3", "score": 7}}
  ],
  "body": "正文（≤800字）",
  "pinned_comment": "置顶评论",
  "interaction_hooks": {{
    "comment_guide": "评论引导",
    "save_guide": "收藏引导",
    "share_guide": "转发引导"
  }},
  "best_post_time": "发布时间建议",
  "scores": {{
    "title_appeal": 9,
    "content_quality": 9,
    "visual_design": 8,
    "interaction_potential": 9,
    "monetization": 7
  }},
  "total": 85,
  "verdict": "评级（S/A/B/C）",
  "predicted": {{
    "likes": "预估点赞",
    "saves": "预估收藏",
    "comments": "预估评论"
  }},
  "strengths": ["优势1", "优势2"],
  "issues": ["可改进1"],
  "suggestions": ["优化建议1"]
}}
"""


def build_exam_note_prompt(subject, grade_short, template, cards):
    """
    构建考卷专题笔记的完整 Prompt
    
    Args:
        subject: 学科（数学/语文/英语）
        grade_short: 年级简称（如"三下"）
        template: 笔记模板（考前冲刺型/满分攻略型）
        cards: 卡片列表
    
    Returns:
        完整的 prompt 字符串
    """
    # 提取卡片文本
    cards_text = ""
    for i, c in enumerate(cards, 1):
        cards_text += f"\n卡片{i}: {extract_exam_card_text(c)}"
    
    # 获取模板风格描述
    if template == '考前冲刺型':
        template_style = """考前冲刺型：倒计时紧迫感→必考清单→快速提分技巧→检查提醒→加油打气
  适用于考前1-2周发布
  正文结构：⏰考前提醒 → 📋必考清单 → ⚡提分技巧 → ✅考场注意事项 → 💪加油鼓励
  情绪曲线：紧迫→安心→自信→从容"""
    else:
        template_style = """满分攻略型：题型拆解→得分策略→答题模板→避坑清单→满分示范
  适用于平时复习和系统备考
  正文结构：🎯题型分析 → 📝审题技巧 → 💡答题模板 → ⚠️易错清单 → 🏆满分示范
  情绪曲线：认识问题→掌握方法→反复练习→信心满满"""
    
    return EXAM_NOTE_PROMPT_TEMPLATE.format(
        subject=subject,
        grade_short=grade_short,
        template=template,
        cards_text=cards_text,
        template_style=template_style,
    )


# ============ 集成说明 ============
"""
要将考卷专题集成到 server.py，需要修改以下部分：

1. 在 template_card_map 中添加考卷专题模板：
   template_card_map['考前冲刺型'] = EXAM_TEMPLATE_CARD_MAP['考前冲刺型']
   template_card_map['满分攻略型'] = EXAM_TEMPLATE_CARD_MAP['满分攻略型']

2. 在模板风格说明中添加：
   - 考前冲刺型：倒计时紧迫感→必考清单→快速提分技巧→检查提醒→加油打气
   - 满分攻略型：题型拆解→得分策略→答题模板→避坑清单→满分示范

3. 在卡片文本提取部分，添加考卷专有字段的提取：
   for field in ['exam_frequency', 'score_weight', 'fill_strategy', ...]:
       val = c.get(field)
       if val:
           cards_text += f"  {field}: {val}\n"

4. manifest.json 中添加考卷卡片文件的记录
"""

if __name__ == '__main__':
    # 简单测试：读取样例数据并构建 prompt
    import os, json
    sample_file = os.path.join(
        os.path.dirname(__file__), 
        'public', 'knowledge_cards', '小学', '数学_三下_考卷.json'
    )
    if os.path.exists(sample_file):
        with open(sample_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        all_cards = []
        for unit in data.get('units', []):
            all_cards.extend(unit.get('cards', []))
        
        print(f"加载了 {len(all_cards)} 张考卷卡片")
        print(f"\n{'='*60}")
        print("📝 考前冲刺型 Prompt 预览（前500字）：")
        print('='*60)
        prompt = build_exam_note_prompt('数学', '三下', '考前冲刺型', all_cards[:5])
        print(prompt[:500] + "...")
        
        print(f"\n{'='*60}")
        print("📝 满分攻略型 Prompt 预览（前500字）：")
        print('='*60)
        prompt2 = build_exam_note_prompt('数学', '三下', '满分攻略型', all_cards[:5])
        print(prompt2[:500] + "...")
    else:
        print(f"❌ 未找到样例文件: {sample_file}")
        print("请先运行 generate_exam_cards.py 生成数据")
