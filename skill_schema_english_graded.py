"""
分年级段英语 Skill Schema v2.0 — 全面优化版。

v2.0 核心改进 (相比 v1.0):
  1. sub_types 从「话题分类」改为「教学策略分类」→ 视觉差异化
  2. 每种卡片定义独特 visual_language → 不再千篇一律四段式
  3. 加入 attention_priority → 引导学生视线
  4. 加入 l1_interference → 针对中国学生母语干扰
  5. 加入 max_info_chunks → 认知负荷控制
  6. 加入 emotion_design + hook_strategy → 小红书传播性
  7. 加入 visual_variants → 视觉多样性
  8. 加入 ColorConfig → 结构化配色

  查找优先级: _GRADED_SKILL_REGISTRY[(type, grade_level)] > _SKILL_REGISTRY[type]

版本: 2.0 (2026-04-01)
"""

from skill_schema import (
    SkillSchema, LayoutBlock, SubType, ColorConfig,
    _register_graded,
)


# ╔════════════════════════════════════════════╗
# ║           小 学 (三~六年级)                ║
# ╚════════════════════════════════════════════╝

# ── 词汇卡@小学 ──
_register_graded(SkillSchema(
    card_type='词汇卡',
    teaching_goal='认识一个简单英语单词，会读、会拼、知道意思',
    core_strategy='大图片联想 → 单词大字 + 音标 → 简单例句 → 趣味记忆法',
    layout_blocks=[
        LayoutBlock('单词大字+插图', 'center', min_area_pct=45, description='单词超大字居中+卡通插图环绕，图文一体',
                    attention_priority=1),
        LayoutBlock('迷你例句', 'lower', max_chars=15, description='1个简短例句(3-5词)+中文',
                    attention_priority=2),
        LayoutBlock('趣味记忆法', 'bottom', max_chars=10, description='谐音/图形/动作记忆法',
                    attention_priority=3),
    ],
    sub_types=[
        SubType('形象联想型', '图片锚定记忆', '单词嵌入到卡通插图中, 字母融入画面(如apple的a变成苹果)',
                '看到图就想到词', '拼写与发音不对应', l1_interference='中文没有字母拼写概念, 易死记硬背'),
        SubType('动作编码型', '全身反应法TPR', '动作示意图+单词, 人物做出动词动作',
                '做动作记单词', '只记中文不记英文', l1_interference='中文用动作表意, 英文靠字母拼写'),
        SubType('韵律拼读型', '自然拼读+韵律', '字母发音规则可视化+朗朗上口的chant',
                '唱着记单词', '混淆相似发音', l1_interference='中文声调语言, 英文重音语言'),
        SubType('对比记忆型', '正反义/近义配对', '两个词双栏对比+反义图片(big🐘 vs small🐭)',
                '一对一对记', '混淆形近词', l1_interference='中文反义词形式无关, 英文常词根相关'),
    ],
    visual_rule_summary='中心辐射型: 单词+插图居中(45%), 例句/记忆法像卫星环绕, 色彩活泼',
    visual_language='贴纸墙风: 圆角色块+卡通贴纸+手绘箭头, 像小学生的趣味笔记本',
    forbidden=[
        '例句不超过5个英文单词',
        '中文不超过15字总量',
        '不写复杂语法解释',
        '不能没有图片/插图元素',
        '不能出现中式英语(如"good good study")',
    ],
    required_elements=['单词大字', '卡通图片', '简单例句', '趣味记忆法'],
    l1_interference=[
        '中国学生倾向从中文翻译到英文, 要用图片直接联想英文',
        '容易混淆b/d, p/q等镜像字母',
        '不习惯英文字母大小写区分',
    ],
    max_info_chunks=3,
    hook_strategy='"这个单词, 看一眼图就忘不了!"',
    emotion_design='好奇(什么词?) → 看图秒懂 → 想自己试试',
    visual_variants=[
        '贴纸墙风: 多张彩色贴纸+手绘边框+胶带装饰',
        '绘本翻页风: 像打开一本绘本, 左图右文',
        '冰箱贴风: 深色冰箱背景+彩色磁铁贴字母',
        '涂鸦本风: 牛皮纸背景+蜡笔手绘插图',
    ],
    color_config=ColorConfig(
        primary='#FFE066', secondary='#74B9FF', accent='#FD79A8',
        error='#FF6B6B', success='#2ED573', bg_style='pattern',
    ),
    color_scheme='童趣彩虹：明黄#FFE066 + 天蓝#74B9FF + 粉红#FD79A8',
), '小学')

# ── 句型卡@小学 ──
_register_graded(SkillSchema(
    card_type='句型卡',
    teaching_goal='学会一个基础句型, 能模仿造句',
    core_strategy='句型积木模板 → 色块填空示范 → 自己搭一个',
    layout_blocks=[
        LayoutBlock('句型积木区', 'center', min_area_pct=40,
                    description='句型模板做成彩色积木块, 可替换部分用虚线框/亮色块',
                    attention_priority=1),
        LayoutBlock('示范搭建', 'middle', min_area_pct=25,
                    description='1个填好的例句(3-6词), 替换部分用不同颜色高亮',
                    attention_priority=2),
        LayoutBlock('小贴士', 'bottom', max_chars=10,
                    description='朗朗上口的口诀或表情提示',
                    attention_priority=3, required=False),
    ],
    sub_types=[
        SubType('填空模板型', '挖空替换', '大字句型模板+色块挖空, 像填字游戏',
                '像搭积木', '忘了添助动词', l1_interference='中文无助动词, "你喜欢吗"→"Do you like?"漏Do'),
        SubType('问答配对型', '一问一答', '问号泡泡+回答泡泡对角排列',
                '你问我答', '问句语序不对', l1_interference='中文疑问句不变语序, 英文要倒装'),
        SubType('看图说话型', '情景激活', '简单情景图+句型泡泡从图中冒出',
                '看图说句子', '漏了is/are', l1_interference='中文无系动词, "他高"→"He tall"漏is'),
    ],
    visual_rule_summary='积木拼接型: 句型成分做成可拆组的彩色积木块, 替换部分像拼图缺口; 例句融入场景插图, 用箭头标注连接图与文',
    visual_language='乐高积木风: 圆角方块+拼接接口+明亮色块, 句子成分一目了然; 带手绘装饰(星星/箭头/虚线)增加趣味; 关键词用语法色码高亮',
    forbidden=[
        '不列超过2个例句',
        '例句不超过6个英文单词',
        '不讲语法术语(如"主语""谓语")',
        '中文不超过12字',
        '❌ 禁止把结构标签或 prompt 指令渲染为可见文字',
        '❌ 例句前只能用 ①②③ 圆圈数字或彩色圆点标记, 不能用英文标签',
    ],
    required_elements=['句型积木模板', '填空示范', '简单例句'],
    l1_interference=[
        '中文 "我喜欢苹果" 直译 "I like apple" → 忘记冠词/复数',
        '中文疑问句不倒装: "你是学生?" → "You are student?"',
    ],
    max_info_chunks=3,
    hook_strategy='"用这个万能句型, 造100个句子!"',
    emotion_design='简单(就这几块) → 搭出来了! → 我也会造句了',
    visual_variants=[
        '乐高积木风: 句子成分是可拼接的立体积木块',
        '拼图风: 句型是个拼图, 替换部分是缺失的拼图片',
        '火车车厢风: 每个句子成分是一节彩色车厢',
    ],
    color_config=ColorConfig(
        primary='#74B9FF', secondary='#DFE6E9', accent='#FECA57',
        error='#FF6B6B', success='#2ED573', bg_style='solid',
    ),
    color_scheme='清新活泼：结构蓝#74B9FF + 重点橙#FECA57',
), '小学')

# ── 语法卡@小学 ──
_register_graded(SkillSchema(
    card_type='语法卡',
    teaching_goal='用图示理解一个简单语法规则(如名词复数、be动词)',
    core_strategy='卡通规则图示 → 简单例句 → 表情对错 → 顺口溜',
    layout_blocks=[
        LayoutBlock('规则卡通图', 'center', min_area_pct=45,
                    description='卡通角色演示规则(如: 小猫变成很多小猫, 加s), 避免术语',
                    attention_priority=1),
        LayoutBlock('例句泡泡', 'middle', max_chars=15,
                    description='1-2个简短例句(3-6词)从图中冒出',
                    attention_priority=2),
        LayoutBlock('表情对错', 'lower',
                    description='😊✅正确 vs 😰❌错误, 用表情代替文字',
                    attention_priority=2),
        LayoutBlock('速记口诀', 'bottom', max_chars=10,
                    description='顺口溜/口诀',
                    attention_priority=3, required=False),
    ],
    sub_types=[
        SubType('数量变化型', '单复数规则可视化', '1个物品→多个物品的卡通数量对比+变化标注',
                '一个变多个', '不规则复数', l1_interference='中文名词无复数变化, "两个苹果"→"two apple"忘加s'),
        SubType('配对匹配型', 'be动词/代词匹配', '人物卡片+动词卡片配对连线, 像连连看',
                '谁配谁', 'is/are用错', l1_interference='中文 "我是/你是/他是" 都一个"是", 英文am/is/are三个'),
        SubType('判断流程型', '简单决策树', '2-3步判断流程图(用是/否岔路), 卡通路标',
                '走迷宫选对路', '跳过判断步骤', l1_interference='中文靠语感, 英文需要走规则'),
    ],
    visual_rule_summary='卡通剧场型: 卡通角色"演"出语法规则, 不说术语只演故事',
    visual_language='卡通剧场风: 可爱角色+对话泡泡+表情符号, 像看动画片截图',
    forbidden=[
        '不用语法术语(主语、谓语、宾语等)',
        '例句不超过6个英文单词',
        '不列超过2个例句',
        '中文不超过12字',
        '不能没有卡通图示',
    ],
    required_elements=['卡通图示化规则', '简单例句', '表情对错'],
    l1_interference=[
        '中文动词不变形, "他跑/她跑" → "He run"忘了三单加s',
        '中文无冠词概念, "我有猫" → "I have cat"漏a',
    ],
    max_info_chunks=3,
    hook_strategy='"这个语法规则, 看完动画就会了!"',
    emotion_design='看不懂(术语) → 看图秒懂 → 原来这么简单',
    visual_variants=[
        '卡通剧场风: 可爱角色在舞台上演示规则',
        '漫画四格风: 4格漫画讲一个语法故事',
        '游乐场风: 语法规则变成游乐园的路线图',
    ],
    color_config=ColorConfig(
        primary='#74B9FF', secondary='#FFEAA7', accent='#FD79A8',
        error='#FF6B6B', success='#2ED573', bg_style='solid',
    ),
    color_scheme='童趣理性：规则蓝#74B9FF + 提示橙#FECA57',
), '小学')

# ── 易混词卡@小学 ──
_register_graded(SkillSchema(
    card_type='易混词卡',
    teaching_goal='用图片对比分清两个容易混淆的简单单词',
    core_strategy='卡通图片左右PK → 各配1句 → 趣味区分口诀',
    layout_blocks=[
        LayoutBlock('VS对决区', 'center', min_area_pct=55,
                    description='左图word_a vs 右图word_b, 中间大VS闪电, 各含卡通图+大字',
                    attention_priority=1),
        LayoutBlock('配对例句', 'lower', max_chars=15,
                    description='左右各1个简短例句(3-5词)',
                    attention_priority=2),
        LayoutBlock('秒记口诀', 'bottom', max_chars=12,
                    description='趣味区分口诀, 朗朗上口',
                    attention_priority=3),
    ],
    sub_types=[
        SubType('形近词型', '字母差异放大', '两词并排, 不同字母用红色3倍放大+闪光标注',
                '找不同', '看太快看错', l1_interference='中文靠字形区分, 英文靠拼写+发音'),
        SubType('图义区分型', '画面对比', '同一构图两张不同场景图, 差异一目了然',
                '看图就分清', '翻译记忆导致混淆', l1_interference='中文一词多义靠语境, 英文see/sea靠拼写'),
    ],
    # v10.27 P2: 强化对比度 — 左右必须用明显不同色
    visual_rule_summary='擂台PK型: 左右分屏对决+中间VS闪电, 图片占主导(55%); ⚠️左右区域必须用对比色(蓝#74B9FF vs 粉#FD79A8), 色差TLE≥30',
    visual_language='擂台对决风: 左蓝#74B9FF右粉#FD79A8+中间VS闪电+拳击手套装饰, 对抗感强烈; '
                    '⚠️ 左右两侧必须用明显不同的背景色, 绝不能用相同或相近颜色',
    forbidden=[
        '不超过2个词对比',
        '例句不超过5个英文单词',
        '不写复杂词性分析',
        '中文不超过12字',
        '❌ 左右两侧不能用相同背景色(必须一蓝一粉或一冷一暖)',
        '❌ 对比区域不能没有视觉分隔(必须有VS闪电/分割线/天平)',
    ],
    required_elements=['左右对比图', '简单例句', '趣味口诀'],
    l1_interference=[
        '中国学生靠中文翻译记单词, 形近词的中文意思不同但拼写像',
    ],
    max_info_chunks=3,
    hook_strategy='"这两个词你分得清吗? 90%的同学都搞混!"',
    emotion_design='自信(我知道!) → 翻车(居然选错) → 记住了!',
    visual_variants=[
        '擂台PK风: 蓝红角+VS闪电+对战氛围',
        '找不同游戏风: 两张相似图, 圈出不同',
        '天平称量风: 两个词放在天平两端',
    ],
    color_config=ColorConfig(
        primary='#74B9FF', secondary='#FD79A8', accent='#FDCB6E',
        error='#FF6B6B', success='#2ED573', bg_style='gradient',
    ),
    color_scheme='对比分明：左蓝#74B9FF 右粉#FD79A8',
), '小学')

# ── 易混词陷阱卡@小学 ──
_register_graded(SkillSchema(
    card_type='易混词陷阱卡',
    teaching_goal='用趣味陷阱让小学生记住两个容易混的单词',
    core_strategy='趣味选择题钩子 → 揭秘翻转 → 图片辅助记忆 → 口诀',
    layout_blocks=[
        LayoutBlock('选择题钩子', 'top', min_area_pct=20,
                    description='趣味大字题目, 像游戏关卡',
                    attention_priority=1),
        LayoutBlock('翻转揭秘区', 'middle', min_area_pct=35,
                    description='❌ vs ✅ 用卡通图+简短说明, 翻牌效果',
                    attention_priority=1),
        LayoutBlock('速记口诀', 'bottom', max_chars=10,
                    description='趣味口诀',
                    attention_priority=3),
    ],
    sub_types=[],
    # v10.27 P2: 强化对错对比度 — ❌红底 vs ✅绿底
    visual_rule_summary='翻牌游戏型: 先看题→翻牌揭秘→恍然大悟, 游戏感强; ⚠️ ❌区域用红底(#FF6B6B), ✅区域用绿底(#2ED573), 色差TLE≥30',
    visual_language='翻牌游戏风: 卡牌翻转效果+问号装饰+惊叹号揭秘; '
                    '⚠️ 错误选项用红色系背景(#FF6B6B), 正确选项用绿色系背景(#2ED573), 形成强烈视觉反差',
    forbidden=[
        '不写复杂语法分析',
        '中文不超过12字',
        '题目不超过6个英文单词',
        '❌ ❌区和✅区不能用相同或相近背景色(必须红绿/冷暖强对比)',
        '❌ 对错选项不能只靠文字区分, 必须有颜色+图标双重区分',
    ],
    required_elements=['趣味陷阱题', '卡通揭秘', '口诀'],
    l1_interference=['中国学生靠中文翻译区分词义, 容易在拼写上犯错'],
    max_info_chunks=3,
    hook_strategy='"猜猜哪个是对的? 答对有奖!"',
    emotion_design='好奇(哪个对?) → 答错惊讶 → 恍然大悟',
    visual_variants=[
        '翻牌游戏风: 正面问号, 翻转后显示答案',
        '刮刮卡风: 灰色遮罩, 刮开显示正确答案',
    ],
    color_config=ColorConfig(
        primary='#FF6B6B', secondary='#FFEAA7', accent='#2ED573',
        error='#FF6B6B', success='#2ED573', bg_style='solid',
    ),
    color_scheme='反转冲击：陷阱红#FF6B6B → 正确绿#2ED573',
), '小学')

# ── 知识总结卡@小学 ──
_register_graded(SkillSchema(
    card_type='知识总结卡',
    teaching_goal='用思维导图帮小学生回顾一个单元的核心词汇和句型',
    core_strategy='中心主题辐射 → 2-3个彩色分支 → 每支配图标 → 易错1条',
    layout_blocks=[
        LayoutBlock('中心主题', 'center', min_area_pct=15,
                    description='单元主题大字+可爱图标, 像太阳',
                    attention_priority=1),
        LayoutBlock('彩色分支', 'middle', min_area_pct=50,
                    description='2-3个分支(词汇/句型/规则), 每支用不同颜色+图标+英文要点',
                    attention_priority=2),
        LayoutBlock('易错闪光', 'bottom', max_chars=12,
                    description='⚠️ 最常见错误1条, 闪光灯标记',
                    attention_priority=3, required=False),
    ],
    sub_types=[
        SubType('放射导图型', '中心辐射', '太阳中心+光芒分支, 每条光芒是一个知识点',
                '像太阳发光', '分支太多记不住', l1_interference='中文思维是线性的, 导图训练发散思维'),
        SubType('路线图型', '学习路径', '起点→终点的彩色路线图, 沿途标知识点',
                '走知识地图', '跳过中间步骤', l1_interference='中文学习偏背诵, 英文需要理解连接'),
    ],
    visual_rule_summary='信息太阳型: 中心主题辐射彩色分支, 每支带图标, ≤3个分支',
    visual_language='手绘导图风: 彩色手绘线条+小图标+便签条, 像小学生的漂亮笔记',
    forbidden=[
        '分支不超过3个',
        '每个要点不超过5字',
        '中文不超过15字',
        '不堆砌大量单词列表',
    ],
    required_elements=['中心主题', '彩色分支', '图标'],
    l1_interference=['中国学生习惯列表式复习, 导图帮助建立知识网络'],
    max_info_chunks=3,
    hook_strategy='"一张图搞定整个单元!"',
    emotion_design='多(这么多知识) → 一张图就够 → 全记住了',
    visual_variants=[
        '手绘导图风: 彩色手绘线条+小图标+便签条',
        '宝藏地图风: 复古地图上标注知识宝藏点',
        '太空探索风: 星球=知识点, 航线=连接',
    ],
    color_config=ColorConfig(
        primary='#E17055', secondary='#74B9FF', accent='#00B894',
        error='#FF6B6B', success='#2ED573', bg_style='pattern',
    ),
    color_scheme='复习彩色：多色分支+主题色圆心',
), '小学')

# ── v10.27: 不规则动词卡@小学 (P0 — 全新注册) ──
_register_graded(SkillSchema(
    card_type='不规则动词卡',
    teaching_goal='用"魔法变身"效果记住不规则动词的原形→过去式变化,不靠死记硬背',
    core_strategy='魔法变身大图(原形→过去式) → 3-4组动词变化表(色彩编码) → 分组口诀',
    layout_blocks=[
        LayoutBlock('魔法变身大图', 'center', min_area_pct=45,
                    description='卡通魔法师(戴帽猫头鹰)挥魔法棒,动词"变身"过程: '
                                '左侧原形(如go)被魔法光包裹→右侧闪亮过去式(went); '
                                '魔法闪光+星星特效+烟雾过渡; '
                                '⚠️ 原形和过去式单词必须超大字清晰可读(≥18pt); '
                                '⚠️ 英文单词拼写必须100%正确',
                    attention_priority=1),
        LayoutBlock('动词变化表', 'lower', min_area_pct=30,
                    description='3-4组动词变化横排展示: '
                                '每组格式"原形 → 过去式", 用不同颜色区分每组; '
                                '变化部分(不同字母)用红色/粗体高亮; '
                                '如: go→went(全变), see→saw(换元音), read→read(不变); '
                                '⚠️ 所有英文单词完整拼写,不能截断',
                    attention_priority=2),
        LayoutBlock('分组口诀', 'bottom', max_chars=12,
                    description='朗朗上口的分组记忆口诀(中文≤10字)',
                    attention_priority=3, required=False),
    ],
    sub_types=[
        SubType('全变型', '形态完全改变', '魔法变身最剧烈: go→went, buy→bought, 整个词都变了, '
                '用爆炸特效表示巨大变化',
                '大变身', '套用规则加ed', l1_interference='中文动词无变化,"去"永远是"去", 英文go→went完全不同'),
        SubType('换元音型', '中间元音替换', '温和魔法: swim→swam, sing→sang, 只换中间字母, '
                '用渐变色过渡标注换掉的字母',
                '换芯不换壳', '换错元音', l1_interference='中文无元音交替概念, 学生不知道该换哪个字母'),
        SubType('不变型', '原形=过去式', '魔法无效! read→read, cut→cut, put→put, '
                '魔法棒打上去没变化+问号特效',
                '不变也是一种变', '以为都要变', l1_interference='中文动词本来就不变, 学生难以理解"不变也需要记"'),
    ],
    visual_rule_summary='魔法变身型: 原形→过去式的视觉变换过程(45%), 配色彩编码变化表(30%), 口诀(10%)',
    visual_language='魔法变身风: 魔法棒+闪光星星+渐变过渡+烟雾特效, 像卡通动画变身场景',
    forbidden=[
        '不超过4组动词变化(认知负荷)',
        '不写过去分词(小学不需要)',
        '中文不超过12字',
        '不列表式堆砌(必须有魔法变身视觉效果)',
        '不写语法术语(不说"不规则变化"说"魔法变身")',
        '每个英文单词必须完整正确拼写',
    ],
    required_elements=['魔法变身大图', '动词变化表', '分组口诀'],
    l1_interference=[
        '中文动词永远不变形: "我去/他去/昨天去" 都是"去", 英文go/goes/went三种',
        '学生倾向套用-ed规则: goed, eated, drinked 等错误形式',
        '不规则动词数量有限但高频, 必须逐个记忆',
    ],
    max_info_chunks=3,
    hook_strategy='"这些动词会魔法变身! 你能记住它们的新样子吗?"',
    emotion_design='好奇(魔法变身!) → 惊讶(变这么多!) → 找规律(有些有窍门) → 记住了',
    visual_variants=[
        '魔法变身风: 魔法棒+闪光+渐变, 像变身动画',
        '进化链风: 像宝可梦进化, 原形→过去式连锁进化',
        '变装秀风: 动词穿上不同"衣服"(字母外套)',
        '时光机风: 动词坐时光机从现在飞到过去',
    ],
    color_config=ColorConfig(
        primary='#A29BFE', secondary='#FECA57', accent='#FD79A8',
        error='#FF6B6B', success='#2ED573', bg_style='gradient',
    ),
    color_scheme='魔法紫金：变身紫#A29BFE + 闪光金#FECA57 + 高亮粉#FD79A8',
), '小学')

# ── v10.25: 情景对话卡@小学 (P4增强版 — 重点修复text_accuracy) ──
_register_graded(SkillSchema(
    card_type='情景对话卡',
    teaching_goal='在贴近小学生日常的卡通情景中，学会2-3句实用英语对话',
    core_strategy='漫画场景大图(含角色对话气泡) → 句型提炼色块 → 替换练习 → 模仿口诀',
    layout_blocks=[
        LayoutBlock('漫画场景大图', 'center', min_area_pct=50,
                    description='漫画风格完整场景: 2个可爱卡通角色在具体场景中对话(商店/教室/操场/家里); '
                                '角色表情生动(大眼睛、夸张表情)，有肢体动作; '
                                '场景物品丰富有细节(货架/黑板/树木/家具等); '
                                '对话以圆形气泡直接画在图中，每轮问+答; '
                                '⚠️ 气泡内英文必须100%正确拼写、完整无截断、字号≥14pt; '
                                '全英文对话，关键句型用粗体+彩色高亮; '
                                '每句3-5个英文单词，像绘本故事; '
                                '⚠️ 气泡文字是教学核心，可读性优先于场景细节',
                    attention_priority=1),
        LayoutBlock('句型提炼框', 'lower-left', max_chars=20,
                    description='从对话中提炼核心句型公式(圆角色块+箭头): 如 "Can I have ___?" + 小字中文提示; '
                                '⚠️ 句型公式中的英文单词必须完整正确拼写',
                    attention_priority=2),
        LayoutBlock('替换练习区', 'lower-right', max_chars=25,
                    description='关键词替换练习(2-3个变体), 用不同颜色标注可替换部分, '
                                '如 an apple 🍎 → a banana 🍌 → some water 💧, 配小图标; '
                                '⚠️ 替换词必须完整拼写，不能截断',
                    attention_priority=2),
        LayoutBlock('模仿口诀', 'bottom', max_chars=10,
                    description='朗朗上口的模仿练习口诀(中文≤8字)',
                    attention_priority=3, required=False),
    ],
    sub_types=[
        SubType('日常问候型', '固定问答', '完整场景(校门口/教室): 两个小学生挥手打招呼+对话气泡',
                '你问我答', '回答不完整', l1_interference='中文问候常省略主语, 英文不能省'),
        SubType('请求许可型', '请求+回应', '完整场景(教室/商店): 一个角色举手请求+另一个微笑回应+对话气泡',
                '礼貌问答', '忘说please', l1_interference='中文请求不需要情态动词, 英文Can I/May I?'),
        SubType('购物场景型', '角色扮演', '完整商店场景(货架+商品+价签): 顾客+店员对话气泡',
                '去超市买东西', '"Can I have..."不是"I want..."',
                l1_interference='中文"给我一个"直译会很不礼貌'),
        SubType('问路场景型', '情境导航', '完整街道场景(路牌+建筑): 问路者+指路者对话气泡',
                '出门找路', '"Where is..."不是"Where has..."',
                l1_interference='中文"在哪里"和英文"Where is"语序不同'),
    ],
    visual_rule_summary='漫画场景大图(50%)+角色对话气泡(全英文·正确拼写·大字号·关键词高亮)+句型提炼色块+替换练习(配emoji)+口诀',
    visual_language='Cartoon comic-strip style: cute characters with big expressive eyes, speech bubbles with LARGE CLEAR TEXT integrated in detailed scene, vibrant colors, HIGH CONTRAST text on bubble background',
    forbidden=[
        '对话不超过3轮(小学生记不住)',
        '每句不超过5个英文单词',
        '不写成人化场景(必须用可爱卡通角色)',
        '中文不超过12字(极简中文)',
        '不能缺少完整场景大图只画对话文字',
        '对话气泡文字不能太小(小学生视力保护, 最小14pt)',
        '气泡内英文绝对不能有拼写错误或截断',
        '气泡背景必须是浅色/白色，文字必须是深色，确保清晰可读',
        '不能把文字画进场景背景中导致难以辨认',
    ],
    required_elements=['漫画场景大图', '角色对话气泡', '句型提炼', '替换练习'],
    l1_interference=[
        '中文对话常省主语, 英文每句都要主语',
        '中文无冠词 → 学生常忘记 a/an/the',
        '中文语序"我想要苹果" → 英文 "I\'d like an apple"',
    ],
    max_info_chunks=4,
    hook_strategy='"学完这组对话, 跟外国小朋友聊天没问题!"',
    emotion_design='好奇(看漫画) → 简单(才几个词) → 想试试(替换练习) → 自信(我也会说!)',
    visual_variants=[
        'Bright cartoon store: 2 child characters, product shelves, price tags, shopping cart',
        'Colorful school scene: students chatting near playground, trees, blue sky',
        'Warm kitchen: parent and child at breakfast table, food items, cozy decor',
        'Fun street scene: child asking directions from friendly adult, road signs, buildings',
    ],
    color_config=ColorConfig(
        primary='#FECA57', secondary='#74B9FF', accent='#FF6B81',
        error='#FF6B6B', success='#2ED573', bg_style='solid',
    ),
    color_scheme='情景暖色：场景橙#FECA57 + 气泡蓝#74B9FF + 高亮粉#FF6B81',
), '小学')

# ── 自然拼读卡@小学 (小学专属) ──
_register_graded(SkillSchema(
    card_type='自然拼读卡',
    teaching_goal='掌握字母/字母组合的发音规则, 看到就能读',
    core_strategy='字母大字+口型 → 3个配图例词 → 找一找练习',
    layout_blocks=[
        LayoutBlock('字母/发音大字', 'top', min_area_pct=25,
                    description='字母/组合超大字+嘴型图标, 像语音按钮',
                    attention_priority=1),
        LayoutBlock('配图例词', 'middle', min_area_pct=35,
                    description='3个含该发音的单词+卡通配图, 横排展示',
                    attention_priority=2),
        LayoutBlock('找一找', 'bottom',
                    description='找一找: 哪个单词也有这个读音? (趣味互动)',
                    attention_priority=2),
    ],
    sub_types=[
        SubType('单字母发音型', '字母-音素对应', '字母大字+嘴型示意+3个词图片横排',
                'a-apple-ant', '长短音混淆', l1_interference='中文拼音a≠英文a, 发音迁移错误'),
        SubType('字母组合型', '组合读音', '两个字母合并动画效果+3个词图片',
                'sh一起发/ʃ/', '拆开读两个音', l1_interference='中文拼音sh和英文sh发音不同'),
        SubType('魔法e型', '不发音e规则', '词尾e消失效果+前元音变长音标注',
                'cap变cape', '忘了e不发音', l1_interference='中文每个字都发音, 不习惯哑音'),
    ],
    visual_rule_summary='语音按钮型: 超大字母+嘴型示意+3个配图例词横排, 互动感',
    visual_language='语音播放器风: 字母像播放按钮, 嘴型卡片, 例词像播放列表',
    forbidden=[
        '不用国际音标术语',
        '示例单词不超过3个',
        '中文不超过8字',
        '不写复杂发音规则',
    ],
    required_elements=['字母大字', '嘴型提示', '配图例词', '趣味练习'],
    l1_interference=[
        '中文拼音与英文字母发音不同(如: c在拼音中读/ts/, 在英文中读/k/)',
        '中文声调语言, 英文重音语言, 节奏感不同',
    ],
    max_info_chunks=3,
    hook_strategy='"学会这个读音, 100个单词都会读了!"',
    emotion_design='新奇(这么读?) → 跟读成功 → 自信',
    visual_variants=[
        '语音播放器风: 字母像按钮, 例词像播放列表',
        '发音工厂风: 字母进入机器, 出来变成单词',
        '音乐盒风: 字母在音符上跳动',
    ],
    color_config=ColorConfig(
        primary='#FF6B6B', secondary='#74B9FF', accent='#FECA57',
        error='#FF6B6B', success='#2ED573', bg_style='gradient',
    ),
    color_scheme='拼读彩色：字母红#FF6B6B + 例词蓝#74B9FF',
), '小学')

# ── 发音挑战卡@小学 ──
_register_graded(SkillSchema(
    card_type='发音挑战卡',
    teaching_goal='通过趣味挑战纠正常见发音错误',
    core_strategy='挑战闯关 → ❌错误示范 vs ✅正确示范 → 嘴型提示 → 练习',
    layout_blocks=[
        LayoutBlock('挑战关卡标题', 'top', max_chars=8,
                    description='游戏化标题, 如"发音闯关第3关"',
                    attention_priority=1),
        LayoutBlock('嘴型对比区', 'middle', min_area_pct=40,
                    description='❌ 错误嘴型 vs ✅ 正确嘴型, 卡通口型大图',
                    attention_priority=1),
        LayoutBlock('闯关练习', 'lower',
                    description='读一读: 跟着正确发音练3遍, 像通关',
                    attention_priority=2),
        LayoutBlock('闯关口诀', 'bottom', max_chars=10,
                    description='发音记忆口诀',
                    attention_priority=3, required=False),
    ],
    sub_types=[],
    visual_rule_summary='闯关游戏型: 挑战关卡+嘴型对比(40%)+练习闯关',
    visual_language='游戏闯关风: 关卡标题+星星评分+进度条, 像手机游戏界面',
    forbidden=[
        '不用专业语音学术语',
        '中文不超过10字',
        '不写太多理论知识',
    ],
    required_elements=['挑战标题', '嘴型对比', '练习'],
    l1_interference=[
        '中国小学生常见: th→s, v→w, r/l不分',
        '中文卷舌与英文卷舌位置不同',
    ],
    max_info_chunks=3,
    hook_strategy='"你能通关吗? 这个发音90%的同学都读错!"',
    emotion_design='挑战(我能行!) → 对比发现差别 → 闯关成功',
    visual_variants=[
        '游戏闯关风: 关卡门+星星评分',
        '擂台挑战风: ❌ vs ✅像拳击手对决',
    ],
    color_config=ColorConfig(
        primary='#FF6B6B', secondary='#00B894', accent='#FDCB6E',
        error='#FF6B6B', success='#00B894', bg_style='gradient',
    ),
    color_scheme='挑战色：错误红#FF6B6B + 正确绿#00B894',
), '小学')


# ╔════════════════════════════════════════════╗
# ║           初 中 (七~九年级)                ║
# ╚════════════════════════════════════════════╝

# ── 词汇卡@初中 ──
_register_graded(SkillSchema(
    card_type='词汇卡',
    teaching_goal='掌握一个英语单词的词性、用法和常见搭配',
    core_strategy='单词中心 → 词性/搭配/例句卫星环绕 → ❌/✅ → 速记',
    layout_blocks=[
        LayoutBlock('单词中心区', 'center', min_area_pct=20,
                    description='单词超大字+词性+中文核心义(≤4字), 像logo',
                    attention_priority=1),
        LayoutBlock('用法卫星区', 'middle', min_area_pct=40,
                    description='2-3个用法环绕中心, 每个含完整例句(6-10词)+搭配, 不同色块',
                    attention_priority=2),
        LayoutBlock('误用对比', 'lower',
                    description='❌ 常见误用(含中式英语) vs ✅ 正确用法',
                    attention_priority=2),
        LayoutBlock('词根速记', 'bottom', max_chars=12,
                    description='词根词缀/英中混搭口诀, 一行搞定',
                    attention_priority=3),
    ],
    sub_types=[
        SubType('词性变换型', '一词多性', '中心词→词形变化放射图(名/动/形/副), 每个分支配例句',
                '一个词变四种', '词性搞混', l1_interference='中文词无词形变化, "快乐"既是形容词也是名词'),
        SubType('搭配网络型', '固定搭配', '单词+搭配词用连线图, 像社交网络',
                '看它跟谁搭配', '搭配错误', l1_interference='中文"开灯"→英文不是"open light"而是"turn on"'),
        SubType('语境推断型', '上下文猜义', '语境段落(遮住单词)+线索词高亮→推断→揭晓',
                '像侦探推理', '只记中文不记用法', l1_interference='中国学生习惯查字典, 不习惯猜词义'),
        SubType('词根拆解型', '构词法', '词根/前缀/后缀拆解图, 像拆乐高',
                '拆开看里面', '不规则词汇', l1_interference='中文偏旁类似词根, 可做类比迁移'),
    ],
    visual_rule_summary='中心辐射型: 单词居中(20%)+用法卫星环绕(40%)+对比+速记',
    visual_language='信息星球风: 中心词像行星, 用法/搭配/例句像卫星环绕, 结构清晰',
    forbidden=[
        '中文不超过20字总量',
        '例句不能短于6个英文单词',
        '不写纯中文解释(必须有英文例句)',
        '不能有中式英语出现在例句中(只能出现在❌区)',
    ],
    required_elements=['单词+词性', '用法例句', '误用对比', '搭配速记'],
    l1_interference=[
        '"I very like" → "I really like" (中文"很"直译为very放错位)',
        '"open/close the light" → "turn on/off the light" (中式搭配)',
        '中文无时态变化, "我昨天去" → "I go yesterday"忘了用went',
    ],
    max_info_chunks=4,
    hook_strategy='"这个词的搭配, 90%的初中生都用错了!"',
    emotion_design='常用(以为会) → 发现用错了 → 正确用法get',
    visual_variants=[
        '信息星球风: 中心词+卫星用法环绕',
        '杂志排版风: 大字标题+色块分栏+底部速记条',
        '便签墙风: 多张彩色便签贴满画面, 每张一个搭配',
        '单词护照风: 护照风格, 单词是"个人信息", 用法是"签证记录"',
    ],
    color_config=ColorConfig(
        primary='#00B894', secondary='#DFE6E9', accent='#0984E3',
        error='#D63031', success='#00B894', bg_style='gradient',
    ),
    color_scheme='活力双色：薄荷绿#00B894 + 天蓝#0984E3',
), '初中')

# ── 句型卡@初中 ──
_register_graded(SkillSchema(
    card_type='句型卡',
    teaching_goal='掌握一个核心句型的结构、变换和实际运用',
    core_strategy='句型公式色块标注 → 肯/否/疑变换 → ❌/✅ → 考点口诀',
    layout_blocks=[
        LayoutBlock('句型公式框', 'top', min_area_pct=25,
                    description='句型结构大字, 主语/谓语/宾语用不同色块, 像代码高亮',
                    attention_priority=1),
        LayoutBlock('三变区', 'middle', min_area_pct=30,
                    description='肯定→否定→疑问三行变换, 变化部分红色高亮, 关键词标注',
                    attention_priority=2),
        LayoutBlock('中式英语陷阱', 'lower',
                    description='❌ 中式语序错误(标注出中文思维) vs ✅ 正确英语语序',
                    attention_priority=2),
        LayoutBlock('考点口诀', 'bottom', max_chars=12,
                    description='考试速记口诀, 一句话',
                    attention_priority=3),
    ],
    sub_types=[
        SubType('语序翻转型', '倒装/前置', '正常语序→倒装语序动画, 箭头标注移动',
                '谁搬到前面了', '忘了倒装', l1_interference='中文疑问句不变语序, 英文必须主谓倒装'),
        SubType('公式套用型', '结构公式', '句型公式+填空槽位, 像数学公式代入',
                '套公式就行', '混淆相似句型', l1_interference='中文靠语气词变疑问, 英文靠结构变换'),
        SubType('情境运用型', '场景驱动', '实际场景图+句型在场景中的应用泡泡',
                '这个场景这么说', '用错时态', l1_interference='中文同一句型不变形, 英文随时态/人称变化'),
    ],
    visual_rule_summary='代码高亮型: 句型结构像代码一样色块标注, 三行对比变换',
    visual_language='代码编辑器风: 深色/浅色代码高亮背景, 句子成分用语法着色',
    forbidden=[
        '不列超过3个例句',
        '例句不能短于6个英文单词',
        '中文不超过20字',
        '不能遗漏中式英语陷阱对比',
    ],
    required_elements=['句型公式', '三变换(肯/否/疑)', '中式英语对比', '考点口诀'],
    l1_interference=[
        '"I don\'t know what is it" → "what it is" (宾语从句不倒装)',
        '"Because...so..." 不能连用(中文"因为…所以…"直译)',
        '"He said he will" → "would" (中文无主过从必过)',
    ],
    max_info_chunks=4,
    hook_strategy='"这个句型的变换, 中考必考!"',
    emotion_design='规则(有公式) → 套用成功 → 考试不怕了',
    visual_variants=[
        '代码编辑器风: 语法高亮+行号标注',
        '公式墙风: 数学公式风格展示句型结构',
        '变形金刚风: 句子成分像零件可以"变形"',
    ],
    color_config=ColorConfig(
        primary='#0984E3', secondary='#DFE6E9', accent='#E17055',
        error='#D63031', success='#00B894', bg_style='solid',
    ),
    color_scheme='结构蓝橙：主语蓝#0984E3 + 谓语橙#E17055 + 宾语绿#00B894',
), '初中')

# ── 语法卡@初中 ──
_register_graded(SkillSchema(
    card_type='语法卡',
    teaching_goal='用时间轴/结构图理解语法规则并能在考试中正确运用',
    core_strategy='可视化图示 → 信号词色块 → 例句(信号词红色) → ❌/✅ → 公式',
    layout_blocks=[
        LayoutBlock('语法图示区', 'center', min_area_pct=45,
                    description='时间轴/流程图/树状图, 信号词用红色标签贴, 视觉占主导',
                    attention_priority=1),
        LayoutBlock('信号词+例句', 'lower', min_area_pct=20,
                    description='2-3个完整句(6-10词), 信号词红色高亮, 像荧光笔划重点',
                    attention_priority=2),
        LayoutBlock('中考陷阱', 'lower',
                    description='❌ 时态/语态错误(标注中文思维干扰原因) vs ✅ 正确',
                    attention_priority=2),
        LayoutBlock('速记公式条', 'bottom', max_chars=12,
                    description='公式+信号词列表, 一行速查',
                    attention_priority=3),
    ],
    sub_types=[
        SubType('时间轴型', '时间线定位', '横轴past─NOW─future+色块+信号词标签贴, 像历史时间线',
                '看日历翻页', '时态混用', l1_interference='中文动词不变形+用时间词表时态, 难以理解英文时态变化'),
        SubType('判断流程型', '决策树', '3-4步判断流程图, 每步yes/no岔路, 最终到达正确答案',
                '走迷宫找答案', '跳步骤', l1_interference='中文靠语感, 英文需要走判断流程'),
        SubType('对比矩阵型', '表格对比', '2-3个语法点横向对比表, 差异用颜色高亮',
                '一表看清区别', '只记一个忘其他', l1_interference='中文无对应概念, 需要建立全新认知框架'),
    ],
    visual_rule_summary='数据仪表盘型: 语法规则像数据图表一样可视化, 信号词是标签贴',
    visual_language='数据仪表盘风: 图表+标签贴+荧光笔标注, 像学习工具界面',
    forbidden=[
        '不列超过3个例句',
        '不堆砌语法术语',
        '例句不能短于6个英文单词',
        '中文不超过20字',
        '不能缺少可视化图示',
    ],
    required_elements=['语法图示', '信号词红色标注', '例句', '中考陷阱对比', '速记公式'],
    l1_interference=[
        '中文无时态系统: "我去/我去了/我将去" 靠时间词不靠动词变化',
        '中文无语态: "门被开了"≠英文被动态的结构',
        '中文靠语序表意, 英文靠词形变化+语序共同表意',
    ],
    max_info_chunks=4,
    hook_strategy='"一张图搞定中考最易混的语法!"',
    emotion_design='困惑(规则好多) → 图示秒懂 → 考试有底了',
    visual_variants=[
        '数据仪表盘风: 图表+标签贴+荧光笔高亮',
        '地铁线路图风: 语法规则像地铁线, 信号词是站名',
        '实验室风: 语法规则像化学公式, 信号词是元素符号',
    ],
    color_config=ColorConfig(
        primary='#0984E3', secondary='#FFEAA7', accent='#D63031',
        error='#D63031', success='#00B894', bg_style='solid',
    ),
    color_scheme='理科清晰：规则蓝#0984E3 + 信号词红#D63031 + 公式金#FDCB6E',
), '初中')

# ── 易混词卡@初中 ──
_register_graded(SkillSchema(
    card_type='易混词卡',
    teaching_goal='从词性、搭配、语境三维度区分两个易混词',
    core_strategy='"A vs B" 三维对比 → 考题陷阱 → 速记',
    layout_blocks=[
        LayoutBlock('VS标题', 'top', max_chars=8,
                    description='"word_a vs word_b" 对决标题, 大字醒目',
                    attention_priority=1),
        LayoutBlock('三维对比区', 'middle', min_area_pct=50,
                    description='左栏vs右栏: ①词性②搭配③语境例句(6-10词), 差异红色高亮',
                    attention_priority=2),
        LayoutBlock('中考陷阱题', 'lower', max_chars=20,
                    description='一道中考真题选择题, 用到这组易混词',
                    attention_priority=2),
        LayoutBlock('区分口诀', 'bottom', max_chars=15,
                    description='一句话区分口诀',
                    attention_priority=3),
    ],
    sub_types=[
        SubType('搭配差异型', '搭配网络对比', '两个词各自的搭配网络图并列, 重叠区域标注',
                '看搭配就知选谁', '搭配记混', l1_interference='中文"说"→speak/say/tell/talk, 同一个中文多个英文'),
        SubType('语境切换型', '场景驱动选词', '同一句子, A填/B填效果不同, 场景图辅助',
                '换个场景换个词', '不看语境乱选', l1_interference='中文学习靠背词, 英文需要根据语境选词'),
        SubType('词源辨析型', '词根差异', '两个词的词根/来源对比, 追本溯源',
                '查族谱分家', '只看中文义不看英文义', l1_interference='中文翻译相同但英文词源不同'),
    ],
    visual_rule_summary='天平称量型: 两词放天平两端, 三维(词性/搭配/语境)逐项比较',
    visual_language='天平称量风: 天平/对比秤+三维雷达图, 差异一目了然',
    forbidden=[
        '不超过2个词对比',
        '例句不能短于6个英文单词',
        '不写长段中文解释',
        '中文不超过20字',
    ],
    required_elements=['三维对比', '英文例句', '中考陷阱题', '速记口诀'],
    l1_interference=[
        '中文一个"说"→英文speak/say/tell/talk, 中国学生靠中文选词',
        '中文"看"→look/see/watch/read, 需要根据语境选用',
    ],
    max_info_chunks=4,
    hook_strategy='"这两个词, 中考每年都考, 每年都有人错!"',
    emotion_design='自信(我会) → 做题翻车 → 三维对比搞清了',
    visual_variants=[
        '天平称量风: 两词在天平上, 逐维度比较',
        '对战卡牌风: 两张卡牌属性对比(如宝可梦卡)',
        '规格参数风: 像产品参数对比表, 每维度打勾/叉',
    ],
    color_config=ColorConfig(
        primary='#0984E3', secondary='#6C5CE7', accent='#FDCB6E',
        error='#D63031', success='#00B894', bg_style='solid',
    ),
    color_scheme='辨析双色：左蓝#0984E3 右紫#6C5CE7',
), '初中')

# ── 易混词陷阱卡@初中 ──
_register_graded(SkillSchema(
    card_type='易混词陷阱卡',
    teaching_goal='用中考真题陷阱帮初中生记住易混词区别',
    core_strategy='真题钩子 → 错误率数据 → 全选项解析 → 考试口诀',
    layout_blocks=[
        LayoutBlock('紧迫标题', 'top', max_chars=8,
                    description='情绪钩子: "中考必考""错误率80%"',
                    attention_priority=1),
        LayoutBlock('真题区', 'upper', min_area_pct=15,
                    description='中考难度选择题大字展示',
                    attention_priority=1),
        LayoutBlock('全选项解析', 'middle', min_area_pct=40,
                    description='每个选项分析: ❌为什么错+✅为什么对, 含英文例句',
                    attention_priority=2),
        LayoutBlock('防错口诀', 'bottom', max_chars=15,
                    description='考试速记口诀, 下次不再错',
                    attention_priority=3),
    ],
    sub_types=[],
    visual_rule_summary='考试倒计时型: 紧迫标题+真题+全选项分析, 考试备战感',
    visual_language='考试倒计时风: 红色警示+倒计时元素+错题本样式',
    forbidden=[
        '不写纯中文解释',
        '必须有完整英文例句',
        '中文不超过20字',
        '考题难度要符合中考水平',
    ],
    required_elements=['情绪钩子', '真题', '全选项分析', '英文例句', '防错口诀'],
    l1_interference=['中考选择题中, 中国学生常因中文翻译相似而选错易混词'],
    max_info_chunks=4,
    hook_strategy='"中考英语必考陷阱! 去年80%的考生都选错了!"',
    emotion_design='紧张(要考了!) → 做错了 → 解析搞懂 → 下次不错',
    visual_variants=[
        '考试倒计时风: 红色警示+错题标记',
        '推理破案风: 线索→排除→锁定正确答案',
    ],
    color_config=ColorConfig(
        primary='#D63031', secondary='#FFEAA7', accent='#00B894',
        error='#D63031', success='#00B894', bg_style='solid',
    ),
    color_scheme='考试警示：错误红#D63031 → 正确绿#00B894',
), '初中')

# ── 语法辨析卡@初中 ──
_register_graded(SkillSchema(
    card_type='语法辨析卡',
    teaching_goal='理清中考常考的两个语法结构差异',
    core_strategy='语法A vs B双栏 → 结构对比+信号词 → 真题 → 速记',
    layout_blocks=[
        LayoutBlock('对比标题', 'top', max_chars=8,
                    description='语法A vs 语法B大字, 英文术语辅助',
                    attention_priority=1),
        LayoutBlock('结构双栏', 'middle', min_area_pct=50,
                    description='左栏vs右栏: 结构公式+信号词+完整例句(6-10词), 差异高亮',
                    attention_priority=2),
        LayoutBlock('真题验证', 'lower',
                    description='❌ 常见混淆真题 vs ✅ 正确选择, 含解题思路',
                    attention_priority=2),
        LayoutBlock('速记条', 'bottom', max_chars=15,
                    description='区分口诀+信号词速查, 一条搞定',
                    attention_priority=3),
    ],
    sub_types=[],
    visual_rule_summary='档案对比型: 两个语法的"个人档案"并列对比, 每项逐一比较',
    visual_language='档案卡对比风: 两张档案卡并列, 每项(结构/信号词/用法)逐行对比',
    forbidden=[
        '不堆砌语法术语',
        '必须有完整英文例句',
        '中文不超过20字',
        '不能只有中文无英文',
    ],
    required_elements=['双栏对比', '信号词', '英文例句', '真题验证', '速记口诀'],
    l1_interference=['中文表达时态靠时间词不靠动词变化, 所以初中生常混淆英语时态结构'],
    max_info_chunks=4,
    hook_strategy='"这两个语法, 中考年年考, 年年有人混!"',
    emotion_design='迷糊(长得好像) → 对比发现差异 → 清楚了',
    visual_variants=[
        '档案卡对比风: 两张个人档案并列',
        '产品规格对比风: 像电子产品参数比较',
    ],
    color_config=ColorConfig(
        primary='#0984E3', secondary='#00CEC9', accent='#FDCB6E',
        error='#D63031', success='#00B894', bg_style='solid',
    ),
    color_scheme='语法双蓝：左#0984E3 右#00CEC9',
), '初中')

# ── 知识总结卡@初中 ──
_register_graded(SkillSchema(
    card_type='知识总结卡',
    teaching_goal='系统梳理一个语法专题或单元考点, 形成考前速查框架',
    core_strategy='知识地图 → 考频分级 → 信号词 → 真题 → 易错陷阱',
    layout_blocks=[
        LayoutBlock('专题中心', 'center', min_area_pct=10,
                    description='专题名+考频标签(★★★), 像地图中心点',
                    attention_priority=1),
        LayoutBlock('知识分支网', 'middle', min_area_pct=55,
                    description='3-4个分支, 每支含: 英文公式+信号词+考频指数, 像地铁线路图',
                    attention_priority=2),
        LayoutBlock('易错红灯', 'lower', max_chars=15,
                    description='⚠️ 最常见考试陷阱1-2条, 红色警示灯',
                    attention_priority=2),
        LayoutBlock('真题速练', 'bottom', max_chars=20,
                    description='中考真题1道+解题关键词',
                    attention_priority=3),
    ],
    sub_types=[],
    visual_rule_summary='地铁线路图型: 知识点像站点, 考频是客流量, 形成考前速查网络',
    visual_language='地铁线路图风: 彩色线路+站点标注+换乘提示, 像城市交通图',
    forbidden=[
        '分支不超过4个',
        '每个要点不超过8字',
        '中文不超过25字',
        '不能没有英文内容',
        '不堆砌知识点列表',
    ],
    required_elements=['知识网络图', '英文公式', '信号词', '考频标签', '易错陷阱'],
    l1_interference=['中国学生习惯背单个知识点, 需要用网络图看到知识之间的联系'],
    max_info_chunks=4,
    hook_strategy='"中考前必看! 一张图胜过翻一本书!"',
    emotion_design='焦虑(要复习好多) → 一图全览 → 胸有成竹',
    visual_variants=[
        '地铁线路图风: 知识站点+换乘提示',
        '思维导图风: 中心辐射+层级分支',
        '棋盘攻略风: 考点像棋子, 分布在棋盘上',
    ],
    color_config=ColorConfig(
        primary='#6C5CE7', secondary='#0984E3', accent='#D63031',
        error='#D63031', success='#00B894', bg_style='solid',
    ),
    color_scheme='考试复习：主题紫#6C5CE7 + 考点红#D63031 + 公式蓝#0984E3',
), '初中')

# ── 情景对话卡@初中 ──
_register_graded(SkillSchema(
    card_type='情景对话卡',
    teaching_goal='在真实交际情景中学会一组实用对话并能变换运用',
    core_strategy='情景漫画3格 → 功能句型提炼 → 替换练习 → 口诀',
    layout_blocks=[
        LayoutBlock('漫画分镜', 'center', min_area_pct=45,
                    description='3格漫画: 真实场景+2-3轮对话泡泡(全英文6-10词/句)',
                    attention_priority=1),
        LayoutBlock('功能句型框', 'lower', min_area_pct=15,
                    description='提炼1-2个核心功能句型, 替换部分色块标注',
                    attention_priority=2),
        LayoutBlock('替换练习', 'lower',
                    description='关键词替换2个变体',
                    attention_priority=2),
        LayoutBlock('交际口诀', 'bottom', max_chars=12,
                    description='交际口诀, 一句话',
                    attention_priority=3),
    ],
    sub_types=[
        SubType('功能交际型', '目标驱动', '漫画分镜+每格一个交际功能(打招呼→请求→感谢)',
                '一个场景三个功能', '中式直译', l1_interference='中文"有空吗?"→"Are you free?"太直接, 英文用"Would you like to..."'),
        SubType('角色扮演型', '身份代入', '角色名牌+对话, 像剧本朗读',
                '演一个角色', '语气不合身份', l1_interference='中文不区分正式/非正式, 英文场合用语差异大'),
    ],
    visual_rule_summary='漫画连载型: 3格漫画分镜(45%)+功能句型提炼+替换练习',
    visual_language='漫画连载风: 分格漫画+角色一致+剧情递进, 像看连载漫画',
    forbidden=[
        '对话不超过3轮',
        '每轮不超过10个英文单词',
        '不能只有中文翻译',
        '中文不超过15字',
    ],
    required_elements=['漫画场景', '全英文对话', '功能句型', '替换练习'],
    l1_interference=['中文请求直接说"帮我一下", 英文需要Would you mind/Could you please等'],
    max_info_chunks=4,
    hook_strategy='"学完这组对话, 出国旅游不怕了!"',
    emotion_design='有趣(看漫画) → 实用(真能用!) → 想练习',
    visual_variants=[
        '漫画连载风: 3格分镜+连贯剧情',
        '聊天记录风: 手机聊天界面风格的对话展示',
        '电影分镜风: 宽银幕比例+电影字幕',
    ],
    color_config=ColorConfig(
        primary='#E17055', secondary='#0984E3', accent='#FDCB6E',
        error='#D63031', success='#00B894', bg_style='solid',
    ),
    color_scheme='交际暖色：场景橙#E17055 + 对话蓝#0984E3',
), '初中')

# ── 时态卡@初中 (初中专属) ──
_register_graded(SkillSchema(
    card_type='时态卡',
    teaching_goal='用时间轴彻底理解一个时态的结构、用法和信号词',
    core_strategy='时间轴定位 → 三种结构 → 信号词标签 → 例句 → ❌/✅',
    layout_blocks=[
        LayoutBlock('时间轴大图', 'center', min_area_pct=30,
                    description='past─NOW─future时间轴, 该时态的时间范围用醒目色块标注',
                    attention_priority=1),
        LayoutBlock('结构公式区', 'middle', min_area_pct=20,
                    description='肯定/否定/疑问三种结构公式, 像数学三行等式',
                    attention_priority=2),
        LayoutBlock('信号词标签贴', 'middle',
                    description='信号词用彩色标签贴展示, 像行李箱贴纸',
                    attention_priority=2),
        LayoutBlock('例句+陷阱', 'lower', min_area_pct=15,
                    description='2个例句(6-10词)+❌中式时态错误 vs ✅正确',
                    attention_priority=2),
        LayoutBlock('速记条', 'bottom', max_chars=15,
                    description='时态口诀+信号词清单, 一条',
                    attention_priority=3),
    ],
    sub_types=[
        SubType('时间定位型', '时间轴锚定', '时间轴上精确标注时态范围, 过去/现在/将来色块分明',
                '在时间线上找位置', '时态选错', l1_interference='中文用"了/过/着"表时态, 位置灵活, 英文靠动词变形, 位置固定'),
        SubType('信号词驱动型', '关键词判断', '信号词分类卡片(always→一般现在, yesterday→一般过去)',
                '看到信号词就知道', '信号词记混', l1_interference='中文"已经/曾经/正在"不影响动词形态, 英文看到already就选完成时'),
        SubType('结构变形型', '三变换练习', '同一句话: 肯定→否定→疑问三行变换+标注变化点',
                '一句变三句', '否定/疑问忘了加助动词', l1_interference='中文否定加"不", 疑问加"吗", 不改动词, 英文要加do/does/did'),
    ],
    visual_rule_summary='时间旅行型: 时间轴(30%)+结构公式(20%)+信号词标签贴+中式错误对比',
    visual_language='时间旅行风: 时间轴像时光隧道, 信号词像路标, 公式像密码锁',
    forbidden=[
        '不列超过3个例句',
        '例句不能短于6个英文单词',
        '不堆砌时态术语',
        '中文不超过20字',
    ],
    required_elements=['时间轴', '三种结构公式', '信号词标签', '例句', '中式错误对比'],
    l1_interference=[
        '中文 "我昨天买了一本书" → "I buy a book yesterday" (忘了用bought)',
        '中文 "我正在吃饭" → "I eating" (忘了be动词)',
        '中文动词永远不变形, 这是中国学生学时态的根本困难',
    ],
    max_info_chunks=4,
    hook_strategy='"搞懂这个时态, 中考选择题秒杀!"',
    emotion_design='混乱(时态好多) → 时间轴定位 → 清楚了',
    visual_variants=[
        '时间旅行风: 时光隧道+路标+时间胶囊',
        '日历翻页风: 过去/今天/未来的日历页',
        '电影胶片风: 时间轴像电影胶片, 每格一个时态',
    ],
    color_config=ColorConfig(
        primary='#0984E3', secondary='#00B894', accent='#E17055',
        error='#D63031', success='#00B894', bg_style='gradient',
    ),
    color_scheme='时态色轴：过去蓝#0984E3 → 现在绿#00B894 → 将来橙#E17055',
), '初中')

# ── PK挑战卡@初中 ──
_register_graded(SkillSchema(
    card_type='PK挑战卡',
    teaching_goal='通过快速PK二选一锻炼语法/词汇判断力',
    core_strategy='PK大屏 → A vs B → 揭晓+解析 → 举一反三',
    layout_blocks=[
        LayoutBlock('PK大屏', 'top', min_area_pct=30,
                    description='A vs B大字对决, 像综艺投票, 背景分左右阵营色',
                    attention_priority=1),
        LayoutBlock('揭晓解析', 'middle', min_area_pct=35,
                    description='✅ 正确选项+解析+英文例句, ❌标注为什么错',
                    attention_priority=2),
        LayoutBlock('举一反三', 'lower',
                    description='同类型变换题1道, 巩固练习',
                    attention_priority=2),
        LayoutBlock('判断口诀', 'bottom', max_chars=12,
                    description='判断口诀, 一句话',
                    attention_priority=3),
    ],
    sub_types=[],
    visual_rule_summary='综艺投票型: A vs B大屏对决(30%)+投票揭晓+举一反三',
    visual_language='综艺投票风: 大屏分两半+VS闪电+投票百分比+音效感文字',
    forbidden=[
        '不写太长的解析',
        '例句不能短于6个英文单词',
        '中文不超过20字',
    ],
    required_elements=['PK对决', '全选项分析', '英文例句', '举一反三'],
    l1_interference=['中国学生常靠"语感"选答案, PK训练帮助建立规则意识'],
    max_info_chunks=4,
    hook_strategy='"A还是B? 3秒内选出来! 选错说明你中了陷阱!"',
    emotion_design='紧张(选哪个!) → 揭晓(答对/错) → 搞懂了',
    visual_variants=[
        '综艺投票风: 大屏投票+百分比+VS',
        '格斗游戏风: 选手血条+VS闪光+KO',
    ],
    color_config=ColorConfig(
        primary='#0984E3', secondary='#D63031', accent='#00B894',
        error='#D63031', success='#00B894', bg_style='gradient',
    ),
    color_scheme='PK对决：A蓝#0984E3 vs B红#D63031 → 胜出绿#00B894',
), '初中')

# ── 速记卡@初中 ──
_register_graded(SkillSchema(
    card_type='速记卡',
    teaching_goal='用最精简的方式快速记住一个考点/规则',
    core_strategy='核心规则超大字 → 口诀/公式 → 1个例句验证 → 易错提醒',
    layout_blocks=[
        LayoutBlock('规则超大字', 'center', min_area_pct=45,
                    description='规则/公式/口诀用超大字居中, 像海报slogan',
                    attention_priority=1),
        LayoutBlock('验证例句', 'lower',
                    description='1个完整英文例句验证规则, 关键词高亮',
                    attention_priority=2),
        LayoutBlock('易错红旗', 'bottom', max_chars=10,
                    description='⚠️ 最常见的1个错误, 红色小旗标记',
                    attention_priority=3, required=False),
    ],
    sub_types=[],
    visual_rule_summary='海报slogan型: 规则超大字居中(45%)+验证例句+易错标记, 极简',
    visual_language='海报标语风: 超大字+极简背景+一句话验证, 像广告海报',
    forbidden=[
        '不写多余解释',
        '中文不超过12字',
        '不列超过1个例句',
    ],
    required_elements=['核心规则超大字', '口诀', '验证例句'],
    l1_interference=['中国学生习惯死记硬背, 口诀帮助理解性记忆'],
    max_info_chunks=3,
    hook_strategy='"一句话搞定这个考点, 考前必看!"',
    emotion_design='焦虑(记不住) → 看到口诀 → 秒记',
    visual_variants=[
        '海报标语风: 超大字+极简背景',
        '霓虹灯风: 深色背景+发光文字',
    ],
    color_config=ColorConfig(
        primary='#FDCB6E', secondary='#0984E3', accent='#D63031',
        error='#D63031', success='#00B894', bg_style='solid',
    ),
    color_scheme='速记黄蓝：规则金#FDCB6E + 例句蓝#0984E3',
), '初中')

# ── 发音挑战卡@初中 ──
_register_graded(SkillSchema(
    card_type='发音挑战卡',
    teaching_goal='纠正初中生常见的发音/重音错误, 提升口语准确性',
    core_strategy='易错发音 → 音标对比 → 重音规则 → 练习词组',
    layout_blocks=[
        LayoutBlock('发音挑战点', 'top', max_chars=8,
                    description='挑战主题, 如"th发音大挑战"',
                    attention_priority=1),
        LayoutBlock('音标对比区', 'middle', min_area_pct=40,
                    description='❌ 中式发音+音标 vs ✅ 正确发音+音标, 嘴型对比',
                    attention_priority=1),
        LayoutBlock('规则+练习', 'lower',
                    description='发音规则1条 + 3个练习词/短语',
                    attention_priority=2),
    ],
    sub_types=[],
    visual_rule_summary='发音诊所型: 错误→正确对比(40%)+嘴型图+练习处方',
    visual_language='发音诊所风: 像看医生, 诊断(错误发音)→处方(正确方法)→康复练习',
    forbidden=[
        '不写太专业的语音学术语',
        '中文不超过12字',
        '练习词不超过3个',
    ],
    required_elements=['发音对比', '音标', '发音规则', '练习词'],
    l1_interference=[
        '中国初中生: th→/s/(think→sink), v→/w/(very→wery)',
        '重音位置: 中文等长, 英文有轻重, 中国学生习惯每个音节等重',
    ],
    max_info_chunks=3,
    hook_strategy='"这个音, 连英语老师都纠正过你10次!"',
    emotion_design='不以为意 → 听到对比差别大 → 决心纠正',
    visual_variants=[
        '发音诊所风: 诊断→处方→康复',
        '雷达波形风: 声波可视化对比',
    ],
    color_config=ColorConfig(
        primary='#D63031', secondary='#0984E3', accent='#00B894',
        error='#D63031', success='#0984E3', bg_style='solid',
    ),
    color_scheme='发音双色：错误红#D63031 + 正确蓝#0984E3',
), '初中')


# ╔════════════════════════════════════════════╗
# ║           高 中 (高一~高三)                ║
# ╚════════════════════════════════════════════╝

# ── 词汇卡@高中 ──
_register_graded(SkillSchema(
    card_type='词汇卡',
    teaching_goal='深度掌握高频词的词族、多义辨析、学术搭配和写作运用',
    core_strategy='词根拆解 → 词族网络 → 多义语境 → 写作替换升级 → 速记',
    layout_blocks=[
        LayoutBlock('词根拆解图', 'top', min_area_pct=15,
                    description='词根+前缀+后缀拆解, 像拆乐高, 每部分标注含义',
                    attention_priority=1),
        LayoutBlock('词族网络+多义', 'middle', min_area_pct=35,
                    description='词根发散→衍生词网络(名/形/动/副)+各义项高级例句(10-15词)',
                    attention_priority=2),
        LayoutBlock('写作升级对比', 'lower',
                    description='❌ 低分表达(初中词) → ✅ 高分替换(本词), 直接提分',
                    attention_priority=2),
        LayoutBlock('速记+真题', 'bottom', max_chars=15,
                    description='词根联想口诀+高考真题1道',
                    attention_priority=3),
    ],
    sub_types=[
        SubType('词根构词型', '词根发散', '词根→衍生词网络图, 像家族族谱',
                '一个根生一棵树', '不规则衍生', l1_interference='中文偏旁类似词根, 可做正迁移: 氵=水相关, un-=不'),
        SubType('语境辨析型', '上下文选义', '同一词在不同语境中的义项切换+例句对比',
                '换个场景变个义', '只记第一义项', l1_interference='中文一词多义靠语境, 英文多义词更多更细'),
        SubType('写作替换型', '低→高级', '初中词→高中词替换对照表+高考范文片段',
                '换个词就加分', '用错语域', l1_interference='中国学生写作用初中词汇够用, 不知道替换为高级词'),
        SubType('搭配图谱型', '搭配网络', '单词+高频搭配网络图, 标注正式/非正式/学术搭配',
                '看它跟谁搭配', '中式搭配', l1_interference='"提高能力"→不是"improve ability"而是"develop skills"'),
    ],
    visual_rule_summary='知识图谱型: 词根拆解(15%)+词族网络+多义(35%)+写作升级+真题',
    visual_language='知识图谱风: 节点+连线+标签, 像学术论文的概念图, 信息密集但结构清晰',
    forbidden=[
        '中文不超过20字总量',
        '例句不能短于8个英文单词',
        '不写初中水平的基础用法',
        '不能缺少写作替换升级',
    ],
    required_elements=['词根拆解', '词族网络', '多义辨析', '写作替换', '高考真题'],
    l1_interference=[
        '"make progress"→用advance/improve替换, 中国学生不知道高级替换',
        '"I think"→In my perspective/From my standpoint, 写作升级',
        '中文写作不分正式/口语, 英文academic writing严格区分',
    ],
    max_info_chunks=5,
    hook_strategy='"掌握这个词根, 一下子多认识20个词!"',
    emotion_design='一个词(好简单) → 发现这么多用法 → 写作能用了',
    visual_variants=[
        '知识图谱风: 节点+连线+标签, 信息密集',
        '词汇宇宙风: 核心词是恒星, 衍生词是行星',
        '杂志专栏风: 高端排版+色块引用+底部速查表',
        '单词档案风: FBI档案风格, 每项信息逐条列出',
    ],
    color_config=ColorConfig(
        primary='#6C5CE7', secondary='#0984E3', accent='#FDCB6E',
        error='#D63031', success='#00B894', bg_style='gradient',
    ),
    color_scheme='学术深色：词根紫#6C5CE7 + 义项蓝#0984E3 + 写作金#FDCB6E',
), '高中')

# ── 句型卡@高中 ──
_register_graded(SkillSchema(
    card_type='句型卡',
    teaching_goal='掌握高考高频/高级句型, 提升写作和阅读理解能力',
    core_strategy='句型结构分析 → 高考真题 → 写作低→高升级 → 仿写模板',
    layout_blocks=[
        LayoutBlock('句型结构图', 'top', min_area_pct=20,
                    description='句型结构图, 主从句不同色块+语法成分标注, 像电路图',
                    attention_priority=1),
        LayoutBlock('高考真题区', 'middle', min_area_pct=25,
                    description='2-3个高考级别例句(10-15词), 关键结构高亮',
                    attention_priority=2),
        LayoutBlock('写作升级', 'lower',
                    description='❌ 低分简单句 → ✅ 高分升级句, 直接加分',
                    attention_priority=2),
        LayoutBlock('仿写模板', 'bottom', max_chars=15,
                    description='留空仿写模板+适用写作场景提示',
                    attention_priority=3),
    ],
    sub_types=[
        SubType('句式升级型', '简→复转换', '简单句→复合句的改写过程图, 像变形金刚',
                '简单句穿高级外套', '生搬硬套', l1_interference='中文写作习惯短句并列, 英文学术写作需要复合长句'),
        SubType('结构分析型', '语法拆解', '复杂句子像电路图一样拆为主干+分支',
                '找主干剥枝叶', '找不到主干', l1_interference='中文句子结构靠语序, 英文靠连接词+从句标记'),
        SubType('模板套用型', '万能模板', '高考写作万能句型模板+多场景适用示例',
                '背一个用十次', '模板过于死板', l1_interference='中国学生习惯背模板, 需要在理解基础上灵活变通'),
    ],
    visual_rule_summary='电路图型: 句型结构像电路(20%)+真题验证+写作升级+仿写模板',
    visual_language='电路蓝图风: 深色背景+电路线条+节点标注, 技术感强, 结构清晰',
    forbidden=[
        '不列超过3个例句',
        '例句不能短于8个英文单词',
        '不写初中水平的基础句型',
        '中文不超过20字',
    ],
    required_elements=['句型结构图', '高考真题', '写作升级对比', '仿写模板'],
    l1_interference=[
        '中文 "虽然...但是..." → 英文Although...不能加but',
        '中文短句并列风格 → 英文需要从句连接',
        '中文被动少用, 英文学术写作大量被动句',
    ],
    max_info_chunks=5,
    hook_strategy='"高考满分作文都用这个句型!"',
    emotion_design='敬畏(好复杂) → 结构图看懂了 → 仿写成功!',
    visual_variants=[
        '电路蓝图风: 深色背景+电路线条',
        '建筑蓝图风: 句子结构像建筑设计图',
        '代码编辑器风: 深色IDE主题+语法高亮',
    ],
    color_config=ColorConfig(
        primary='#0984E3', secondary='#6C5CE7', accent='#FDCB6E',
        error='#D63031', success='#00B894', bg_style='gradient',
    ),
    color_scheme='高级蓝金：结构蓝#0984E3 + 升级金#FDCB6E + 从句紫#6C5CE7',
), '高中')

# ── 语法卡@高中 ──
_register_graded(SkillSchema(
    card_type='语法卡',
    teaching_goal='深度理解高中语法体系, 能在阅读和写作中灵活运用',
    core_strategy='语法体系图 → 高考真题分析 → 写作运用 → 速查表',
    layout_blocks=[
        LayoutBlock('语法体系图', 'center', min_area_pct=45,
                    description='语法体系树/时态矩阵/从句结构图, 信息密度高, 像学术论文配图',
                    attention_priority=1),
        LayoutBlock('真题剖析', 'lower', min_area_pct=20,
                    description='2-3个高考真题(10-15词)+解题思路, 信号词/关键点高亮',
                    attention_priority=2),
        LayoutBlock('写作运用', 'lower',
                    description='该语法在写作中的高分用法+❌低→✅高分对比',
                    attention_priority=2),
        LayoutBlock('速查公式', 'bottom', max_chars=15,
                    description='速查公式表+高频考点, 考前速看',
                    attention_priority=3),
    ],
    sub_types=[
        SubType('体系构建型', '知识网络', '语法体系树/矩阵, 展示各知识点之间的关系',
                '先看全景再看细节', '只见树木不见森林', l1_interference='中文语法隐性(无形态变化), 英文语法显性(词形变化+语序), 需要系统构建'),
        SubType('判断决策型', '流程图判断', '复杂语法判断流程图, 每步yes/no, 像编程if-else',
                '跟着流程走', '跳过关键判断', l1_interference='中文靠语感, 英文复杂语法需要走逻辑判断流程'),
        SubType('真题解码型', '解题拆解', '高考真题+逐步解题拆解+陷阱标注',
                '像破案一样解题', '被干扰项误导', l1_interference='中国学生靠翻译做题, 需要直接在英文语境中判断'),
    ],
    visual_rule_summary='学术论文型: 语法体系图(45%)+真题剖析+写作运用+速查表',
    visual_language='学术论文风: 高信息密度+体系图+参考标注, 严谨但清晰',
    forbidden=[
        '不列超过3个例句',
        '例句不能短于8个英文单词',
        '不写初中基础内容',
        '中文不超过20字',
    ],
    required_elements=['语法体系图', '高考真题', '写作运用', '速查表'],
    l1_interference=[
        '虚拟语气: 中文无虚拟语气概念, "如果我是你"→"If I were you"为什么用were',
        '非谓语: 中文动词不变形, to do/doing/done三选一是高中生最大痛点',
        '定语从句: 中文定语前置, 英文定语后置, 思维方式完全不同',
    ],
    max_info_chunks=5,
    hook_strategy='"高考语法大题, 一张图看懂命题套路!"',
    emotion_design='恐惧(语法太难) → 体系图看到全貌 → 掌控感',
    visual_variants=[
        '学术论文风: 体系图+参考标注+结论框',
        '思维矩阵风: 二维表格+交叉对比',
        '解剖图风: 句子像生物体, 解剖标注各部分',
    ],
    color_config=ColorConfig(
        primary='#0984E3', secondary='#6C5CE7', accent='#FDCB6E',
        error='#D63031', success='#00B894', bg_style='solid',
    ),
    color_scheme='深度蓝紫：体系蓝#0984E3 + 真题紫#6C5CE7 + 速查金#FDCB6E',
), '高中')

# ── 易混词卡@高中 ──
_register_graded(SkillSchema(
    card_type='易混词卡',
    teaching_goal='精准辨析高级近义词在学术写作和高考中的区别',
    core_strategy='语义光谱 → 搭配/语域差异 → 高考真题 → 写作替换',
    layout_blocks=[
        LayoutBlock('语义光谱区', 'top', min_area_pct=20,
                    description='近义词语义强度光谱图: 从轻到重排列, 标注程度差异',
                    attention_priority=1),
        LayoutBlock('深度对比区', 'middle', min_area_pct=40,
                    description='搭配差异+语域差异+高考级例句(10-15词), 差异精确标注',
                    attention_priority=2),
        LayoutBlock('高考真题', 'lower', max_chars=20,
                    description='高考真题/模拟题1道, 考到这组词',
                    attention_priority=2),
        LayoutBlock('辨析口诀', 'bottom', max_chars=15,
                    description='辨析口诀+语义光谱速查',
                    attention_priority=3),
    ],
    sub_types=[
        SubType('语义光谱型', '程度排序', '近义词按语义强度排成光谱, 从轻到重+各自例句',
                '都是"重要"但程度不同', '程度搞反', l1_interference='中文"重要"一个词, 英文important/significant/crucial/vital/essential程度递进'),
        SubType('语域分层型', '正式度判断', '同义词按正式程度分层: 口语/一般/学术/法律',
                '看场合选词', '不分正式与否', l1_interference='中文写作不严格区分正式/口语, 英文学术写作必须用正式词'),
        SubType('搭配图谱型', '搭配差异', '两个词各自的搭配Venn图, 重叠与差异一目了然',
                '看搭配就知选谁', '中式搭配', l1_interference='"do research"不是"make research", 中文"做研究"→英文不能直译'),
    ],
    visual_rule_summary='语义光谱型: 光谱图(20%)+深度对比(40%)+高考真题+辨析口诀',
    visual_language='光谱分析风: 渐变色光谱+刻度标注+数据面板, 像科学仪器界面',
    forbidden=[
        '不超过2个词对比(光谱可展示3-4个)',
        '例句不能短于8个英文单词',
        '不写基础义项',
        '中文不超过20字',
    ],
    required_elements=['语义光谱', '搭配差异', '高级例句', '高考真题', '辨析口诀'],
    l1_interference=[
        '中文 "影响" 一个词 → 英文affect/influence/impact三个, 程度和方向不同',
        '中文不严格区分语域, 英文口语/学术/正式用词差异大',
    ],
    max_info_chunks=5,
    hook_strategy='"这组近义词, 高考完形填空年年考!"',
    emotion_design='模糊(不都一个意思吗) → 光谱看到差异 → 精准选词',
    visual_variants=[
        '光谱分析风: 渐变光谱+刻度+数据面板',
        '温度计风: 从冷到热展示词义程度变化',
        '雷达图风: 多维度雷达对比+差异高亮',
    ],
    color_config=ColorConfig(
        primary='#74B9FF', secondary='#6C5CE7', accent='#FDCB6E',
        error='#D63031', success='#00B894', bg_style='gradient',
    ),
    color_scheme='辨析渐变：浅蓝#74B9FF → 深紫#6C5CE7',
), '高中')

# ── 易混词陷阱卡@高中 ──
_register_graded(SkillSchema(
    card_type='易混词陷阱卡',
    teaching_goal='用高考真题陷阱帮高中生精准掌握高级词汇辨析',
    core_strategy='高考真题 → 全选项语义/搭配/语域分析 → 高分口诀',
    layout_blocks=[
        LayoutBlock('高考钩子', 'top', max_chars=8,
                    description='高考标签: "高考必考""阅卷得分点"',
                    attention_priority=1),
        LayoutBlock('真题展示', 'upper', min_area_pct=15,
                    description='高考级别选择/填空题大字展示',
                    attention_priority=1),
        LayoutBlock('全选项分析', 'middle', min_area_pct=40,
                    description='每个选项: 语义+搭配+语域分析, ❌为什么错/✅为什么对',
                    attention_priority=2),
        LayoutBlock('高考口诀', 'bottom', max_chars=15,
                    description='高考速记口诀, 一句话',
                    attention_priority=3),
    ],
    sub_types=[],
    visual_rule_summary='法庭审判型: 每个选项像被告, 逐一审查证据, 判定对/错',
    visual_language='法庭审判风: 严肃布局+证据列举+判决标记, 逻辑严密',
    forbidden=[
        '不写纯中文解释',
        '必须有高级英文例句',
        '中文不超过20字',
        '难度要达到高考水平',
    ],
    required_elements=['高考真题', '全选项分析', '语义辨析', '高考口诀'],
    l1_interference=['中国学生靠中文翻译做完形填空, 同义词中文翻译一样但英文用法不同'],
    max_info_chunks=5,
    hook_strategy='"高考完形填空压轴题! 正确率只有23%!"',
    emotion_design='自信(我选C) → 全错 → 深度分析 → 真正掌握',
    visual_variants=[
        '法庭审判风: 证据列举+判决',
        '推理破案风: 线索→排除→锁定',
    ],
    color_config=ColorConfig(
        primary='#D63031', secondary='#FFEAA7', accent='#FDCB6E',
        error='#D63031', success='#FDCB6E', bg_style='solid',
    ),
    color_scheme='高考警示：错误红#D63031 → 正确金#FDCB6E',
), '高中')

# ── 知识总结卡@高中 ──
_register_graded(SkillSchema(
    card_type='知识总结卡',
    teaching_goal='构建高考语法/词汇知识体系, 形成考前速查框架',
    core_strategy='知识体系信息图 → 考频分级 → 写作提分 → 真题 → 陷阱清单',
    layout_blocks=[
        LayoutBlock('体系信息图', 'center', min_area_pct=50,
                    description='信息图/数据可视化: 3-4分支, 每支含规则+公式+考频, 像数据报告',
                    attention_priority=1),
        LayoutBlock('写作提分点', 'lower', max_chars=20,
                    description='该知识点在写作中的高分运用1-2条',
                    attention_priority=2),
        LayoutBlock('高考陷阱清单', 'lower', max_chars=15,
                    description='⚠️ 高考高频陷阱2条, 红色标记',
                    attention_priority=2),
        LayoutBlock('经典真题', 'bottom', max_chars=20,
                    description='经典高考真题1道+解题关键词',
                    attention_priority=3),
    ],
    sub_types=[],
    visual_rule_summary='数据报告型: 信息图/数据可视化(50%)+考频分级+写作+真题+陷阱',
    visual_language='信息图报告风: 数据可视化+图标+标签+分级色块, 像年度报告',
    forbidden=[
        '分支不超过4个',
        '不堆砌知识点',
        '中文不超过25字',
        '不能没有高考真题',
        '不写初中基础内容',
    ],
    required_elements=['知识体系图', '考频分级', '写作提分', '高考真题', '陷阱清单'],
    l1_interference=['中国学生习惯逐条背诵, 体系图帮助看到知识全景和内在联系'],
    max_info_chunks=5,
    hook_strategy='"高考前一晚, 只看这一张就够了!"',
    emotion_design='迷茫(知识点太多) → 体系化 → 全局掌控',
    visual_variants=[
        '信息图报告风: 数据可视化+图标+色块',
        '一页纸速查风: 极致压缩+表格化+编号',
        '知识星图风: 知识点像星座, 连线成图',
    ],
    color_config=ColorConfig(
        primary='#6C5CE7', secondary='#D63031', accent='#FDCB6E',
        error='#D63031', success='#00B894', bg_style='solid',
    ),
    color_scheme='高考冲刺：体系紫#6C5CE7 + 真题红#D63031 + 提分金#FDCB6E',
), '高中')

# ── 词汇深度卡@高中 (高中专属) ──
_register_graded(SkillSchema(
    card_type='词汇深度卡',
    teaching_goal='深挖一个核心词的词族网络、多义辨析和学术写作应用',
    core_strategy='词根拆解 → 词族网络 → 多义语境 → 高考真题 → 写作替换',
    layout_blocks=[
        LayoutBlock('词根拆解', 'top', min_area_pct=15,
                    description='词根+前缀+后缀拆解, 标注每部分含义',
                    attention_priority=1),
        LayoutBlock('词族太阳系', 'middle', min_area_pct=35,
                    description='核心词=太阳, 衍生词(名/形/动/副)=行星, 各配例句',
                    attention_priority=2),
        LayoutBlock('写作替换', 'lower',
                    description='❌ 初中词 → ✅ 本词高分替换, 含写作场景',
                    attention_priority=2),
        LayoutBlock('真题验证', 'bottom', max_chars=15,
                    description='高考真题1道, 验证该词的考法',
                    attention_priority=3),
    ],
    sub_types=[],
    visual_rule_summary='太阳系型: 词根=太阳核心, 衍生词=行星环绕, 写作升级+真题',
    visual_language='词汇太阳系风: 中心词像太阳发光, 衍生词像行星按轨道环绕',
    forbidden=[
        '例句不能短于8个英文单词',
        '不写初中基础义项',
        '中文不超过20字',
    ],
    required_elements=['词根拆解', '词族网络', '多义辨析', '写作替换', '高考真题'],
    l1_interference=['中文词不变形, 英文一个词根衍生出名/形/动/副四种形态, 需要系统学习'],
    max_info_chunks=5,
    hook_strategy='"学会这个词根, 秒杀高考20个生词!"',
    emotion_design='一个词(好无聊) → 发现词族网络 → 原来这么多词都认识了',
    visual_variants=[
        '太阳系风: 中心词=太阳, 衍生词=行星',
        '族谱/家族树风: 词根在顶部, 下方分支衍生',
        '矿石开采风: 词根是矿石, 拆解出各种宝石(词)',
    ],
    color_config=ColorConfig(
        primary='#6C5CE7', secondary='#0984E3', accent='#FDCB6E',
        error='#D63031', success='#00B894', bg_style='gradient',
    ),
    color_scheme='深度紫金：词根紫#6C5CE7 + 义项蓝#0984E3 + 写作金#FDCB6E',
), '高中')

# ── 高级语法卡@高中 (高中专属) ──
_register_graded(SkillSchema(
    card_type='高级语法卡',
    teaching_goal='掌握高考高难语法(虚拟/倒装/强调/独立主格)的判断和运用',
    core_strategy='判断流程图 → 高考真题解码 → 写作运用 → 速查口诀',
    layout_blocks=[
        LayoutBlock('判断流程图', 'top', min_area_pct=25,
                    description='语法判断流程图, 每步yes/no, 像编程的if-else决策树',
                    attention_priority=1),
        LayoutBlock('真题解码', 'middle', min_area_pct=30,
                    description='2-3个高考真题+逐步解题拆解, 信号词/关键点标注',
                    attention_priority=2),
        LayoutBlock('写作运用', 'lower',
                    description='该语法在写作中的高分用法+模板句, 直接提分',
                    attention_priority=2),
        LayoutBlock('速查口诀', 'bottom', max_chars=15,
                    description='判断口诀+信号词清单, 考前速看',
                    attention_priority=3),
    ],
    sub_types=[
        SubType('决策树型', '流程判断', '多步判断流程图+每步选择依据, 像编程逻辑',
                '跟着流程走不会错', '跳步骤', l1_interference='虚拟语气: 中文无此概念, "如果我是你"不需要变时态, 英文需要时态倒退'),
        SubType('正反对比型', '正常vs特殊', '正常句→改写后对比, 标注变化点+原因',
                '对比一下就懂了', '记住形式忘了条件', l1_interference='倒装: 中文句序固定, 英文否定词前置要倒装, 违反中文直觉'),
        SubType('拆解还原型', '结构拆解', '复杂句子拆成主干+附加成分, 逐步还原',
                '先拆再装', '找不到主干', l1_interference='独立主格: 中文无此结构, 需要从头建立认知'),
    ],
    visual_rule_summary='编程逻辑型: 判断流程图(25%)+真题解码(30%)+写作运用+速查口诀',
    visual_language='编程IDE风: 深色背景+代码流程+if-else判断+断点标注, 逻辑清晰',
    forbidden=[
        '不列超过3道真题',
        '例句不能短于8个英文单词',
        '不写初中基础',
        '中文不超过20字',
    ],
    required_elements=['判断流程图', '高考真题', '写作运用', '速查口诀'],
    l1_interference=[
        '虚拟语气: 中文 "如果我是你, 我就去" 完全不变形, 英文 "If I were you, I would go" 需要变',
        '倒装句: 中文 "我从来不迟到" SVO, 英文 "Never do I..." 强制倒装',
        '独立主格: 中文无此结构, 英文 "Weather permitting" 是全新概念',
    ],
    max_info_chunks=5,
    hook_strategy='"高考语法最难的一道题, 用这个流程图3步搞定!"',
    emotion_design='恐惧(太难了) → 流程图降维 → 原来有套路',
    visual_variants=[
        '编程IDE风: 深色+代码流程+断点',
        '侦探推理风: 线索→推理→结论',
        '密室逃脱风: 每步判断是一个密室机关',
    ],
    color_config=ColorConfig(
        primary='#0984E3', secondary='#6C5CE7', accent='#FDCB6E',
        error='#D63031', success='#00B894', bg_style='gradient',
    ),
    color_scheme='高级深蓝：结构蓝#0984E3 + 真题紫#6C5CE7 + 写作金#FDCB6E',
), '高中')

# ── 从句进阶卡@高中 (高中专属) ──
_register_graded(SkillSchema(
    card_type='从句进阶卡',
    teaching_goal='掌握复杂从句(定/状/名词性)的辨析、嵌套和写作运用',
    core_strategy='三种从句对比 → 判断流程 → 嵌套拆解 → 高考真题 → 写作模板',
    layout_blocks=[
        LayoutBlock('从句三分对比', 'top', min_area_pct=25,
                    description='定/状/名词性从句特征对比, 三栏三色, 像产品参数表',
                    attention_priority=1),
        LayoutBlock('判断流程', 'middle', min_area_pct=25,
                    description='关系词/连接词选择流程图, 逐步判断',
                    attention_priority=2),
        LayoutBlock('真题拆解', 'lower', min_area_pct=15,
                    description='高考真题1-2道+从句拆解标注',
                    attention_priority=2),
        LayoutBlock('写作模板', 'bottom', max_chars=15,
                    description='从句在写作中的高分模板句',
                    attention_priority=3),
    ],
    sub_types=[],
    visual_rule_summary='三分对比+流程图型: 三种从句三栏对比(25%)+判断流程(25%)+真题+写作',
    visual_language='产品参数对比风: 三款"产品"(三种从句)横向对比, 每项打勾/叉',
    forbidden=[
        '不堆砌概念',
        '例句不能短于8个英文单词',
        '不写初中基础',
        '中文不超过20字',
    ],
    required_elements=['三种从句对比', '判断流程', '高考真题', '写作模板'],
    l1_interference=[
        '中文定语前置("我昨天买的书"), 英文定语后置("the book that I bought yesterday")',
        '中文靠语序区分, 英文靠连接词(that/which/who/where/when等)',
    ],
    max_info_chunks=5,
    hook_strategy='"定状名三种从句, 一张图理清!"',
    emotion_design='混乱(三种从句搞不清) → 对比表看清区别 → 流程图稳选对',
    visual_variants=[
        '产品参数对比风: 三栏横向对比+打勾叉',
        '交通枢纽风: 三条线路交汇+换乘指南',
    ],
    color_config=ColorConfig(
        primary='#0984E3', secondary='#00B894', accent='#6C5CE7',
        error='#D63031', success='#00B894', bg_style='solid',
    ),
    color_scheme='从句三色：定语蓝#0984E3 + 状语绿#00B894 + 名词紫#6C5CE7',
), '高中')

# ── 写作进阶卡@高中 (高中专属) ──
_register_graded(SkillSchema(
    card_type='写作进阶卡',
    teaching_goal='掌握一个高考写作高分技巧/句型, 直接提分',
    core_strategy='低分→高分并排对比 → 升级技巧 → 范文片段 → 仿写',
    layout_blocks=[
        LayoutBlock('低→高分对比', 'center', min_area_pct=35,
                    description='2-3组: 左灰色低分表达 → 右金色高分升级, 视觉冲击强',
                    attention_priority=1),
        LayoutBlock('升级技巧+模板', 'middle', min_area_pct=20,
                    description='升级技巧说明+可套用的写作模板, 一看就能用',
                    attention_priority=2),
        LayoutBlock('满分范文', 'lower',
                    description='高考满分作文片段, 高亮用到本技巧的句子',
                    attention_priority=2),
        LayoutBlock('仿写挑战', 'bottom', max_chars=15,
                    description='留空仿写1句+话题提示',
                    attention_priority=3),
    ],
    sub_types=[
        SubType('词汇升级型', '低→高级词', '初中词→高中词替换对照+例句, 像化妆前后对比',
                '给句子换高级装', '堆砌大词不自然', l1_interference='中国学生写作习惯用简单词, "good"通篇, 需要学会精准替换'),
        SubType('句式升级型', '简→复合句', '简单句→复合句改写过程+标注升级点',
                '短句变长句', '从句套错', l1_interference='中文写作短句并列, 英文需要用从句连接, 信息层级更清晰'),
        SubType('逻辑升级型', '连接词升级', 'and/but→moreover/nevertheless替换表',
                '逻辑更严密', '连接词用错', l1_interference='中文"而且"→furthermore/moreover/in addition, 程度和场合不同'),
    ],
    visual_rule_summary='变妆对比型: 低(灰)→高(金)分对比(35%), 视觉冲击+模板+范文',
    visual_language='化妆前后风: 左side灰色素颜(低分) → 右side金色精致(高分), 对比强烈',
    forbidden=[
        '不超过3组对比',
        '例句不能短于8个英文单词',
        '不写初中水平表达',
        '中文不超过20字',
    ],
    required_elements=['低→高分对比', '写作技巧', '模板句', '满分范文片段', '仿写'],
    l1_interference=[
        '中文作文不太区分词汇的高级程度, 英文写作评分明显偏好高级词汇',
        '"In my opinion" → "From my perspective" → "It is widely acknowledged that..."',
    ],
    max_info_chunks=5,
    hook_strategy='"把这三句换掉, 作文直接多5分!"',
    emotion_design='惊讶(只换几个词?) → 对比效果太明显 → 马上去改我的作文',
    visual_variants=[
        '化妆前后风: 左灰右金, 对比强烈',
        '装修改造风: 旧房(低分)→新房(高分)',
        '升级进化风: 普通→稀有→传说, 游戏进化效果',
    ],
    color_config=ColorConfig(
        primary='#636E72', secondary='#FDCB6E', accent='#6C5CE7',
        error='#636E72', success='#FDCB6E', bg_style='gradient',
    ),
    color_scheme='写作进阶：低分灰#636E72 → 高分金#FDCB6E',
), '高中')

# ── 阅读技巧卡@高中 (高中专属) ──
_register_graded(SkillSchema(
    card_type='阅读技巧卡',
    teaching_goal='掌握高考阅读理解的解题技巧和信息定位方法',
    core_strategy='题型识别 → 解题流程 → 信号词清单 → 真题示范 → 口诀',
    layout_blocks=[
        LayoutBlock('解题流程图', 'center', min_area_pct=30,
                    description='解题步骤3-4步流程图, 每步配操作说明, 像工厂流水线',
                    attention_priority=1),
        LayoutBlock('信号词弹药库', 'middle', min_area_pct=20,
                    description='该题型的关键信号词/句型, 用标签贴展示, 像弹药库的武器',
                    attention_priority=2),
        LayoutBlock('真题实战', 'lower',
                    description='高考阅读真题片段+标注解题过程, 像看实战视频',
                    attention_priority=2),
        LayoutBlock('解题口诀', 'bottom', max_chars=15,
                    description='解题口诀, 一句话',
                    attention_priority=3),
    ],
    sub_types=[
        SubType('定位型', '关键词回文定位', '题目关键词→原文定位→答案提取, 箭头标注路径',
                '按图索骥', '定位错误', l1_interference='中国学生习惯先读全文再做题, 英文阅读需要先看题再定位'),
        SubType('推断型', '逻辑推理', '原文信息→推理链条→排除干扰项→选答案',
                '不是猜是推理', '过度推断', l1_interference='中文阅读靠整体感悟, 英文阅读需要基于文本证据推理'),
        SubType('主旨型', '首尾段法', '首段+尾段+各段首句标注→提炼主旨',
                '看头看尾知全貌', '被细节带跑', l1_interference='中国学生习惯逐句翻译, 需要训练快速抓主旨'),
        SubType('词义猜测型', '上下文线索', '未知词+上下文线索词(同义/反义/定义)标注→推测',
                '像侦探找线索', '脱离上下文猜', l1_interference='中国学生遇到生词就卡住, 需要训练用上下文推断'),
    ],
    visual_rule_summary='作战地图型: 解题流程(30%)+信号词弹药库(20%)+实战示范+口诀',
    visual_language='军事作战风: 作战地图+弹药库+战术标注, 考试就是战场',
    forbidden=[
        '解题步骤不超过4步',
        '不写太多理论',
        '中文不超过20字',
    ],
    required_elements=['解题流程图', '信号词清单', '真题实战', '解题口诀'],
    l1_interference=[
        '中国学生阅读习惯: 逐句翻译→再理解, 英文需要: 扫读→定位→精读→选答案',
        '中文阅读环境: 所有字都认识, 英文阅读: 必须学会容忍生词',
    ],
    max_info_chunks=5,
    hook_strategy='"高考阅读理解, 不用全读完也能做对!"',
    emotion_design='害怕(文章好长) → 流程图看清套路 → 信心满满上考场',
    visual_variants=[
        '军事作战风: 作战地图+弹药库+战术标注',
        '工厂流水线风: 解题步骤像工厂生产线',
        '游戏攻略风: 关卡说明+道具(信号词)+BOSS(真题)',
    ],
    color_config=ColorConfig(
        primary='#0984E3', secondary='#00B894', accent='#FDCB6E',
        error='#D63031', success='#00B894', bg_style='solid',
    ),
    color_scheme='阅读科技蓝：流程蓝#0984E3 + 信号绿#00B894 + 答案金#FDCB6E',
), '高中')

# ── 发音挑战卡@高中 ──
_register_graded(SkillSchema(
    card_type='发音挑战卡',
    teaching_goal='纠正高级词汇的发音/重音错误, 提升口语和听力能力',
    core_strategy='精确音标对比 → 重音规则 → 连读弱读 → 高频词练习',
    layout_blocks=[
        LayoutBlock('音标对比区', 'center', min_area_pct=40,
                    description='❌ 中式发音+音标 vs ✅ 准确发音+音标, 声波可视化对比',
                    attention_priority=1),
        LayoutBlock('重音+连读规则', 'lower',
                    description='重音位置标注+连读/弱读规律说明, 规则简洁',
                    attention_priority=2),
        LayoutBlock('高频词练习', 'bottom', max_chars=20,
                    description='5个高频词发音练习+易错标注',
                    attention_priority=2),
    ],
    sub_types=[],
    visual_rule_summary='声波分析型: 音标精确对比(40%)+重音标注+连读规则+高频词练习',
    visual_language='声波频谱风: 声波可视化+频率对比+标注, 像音频编辑软件界面',
    forbidden=[
        '中文不超过15字',
        '不写基础发音',
        '练习词不超过5个',
    ],
    required_elements=['音标精确对比', '重音规则', '连读弱读', '发音练习'],
    l1_interference=[
        '高中常见: determine重音在第二音节不是第一, 中国学生按拼写猜重音',
        '连读: "not at all"→/nɒtətɔːl/, 中国学生逐词发音',
        '弱读: "can"在句中弱读为/kən/, 中国学生永远读/kæn/',
    ],
    max_info_chunks=4,
    hook_strategy='"这10个高频词, 你可能读了三年都是错的!"',
    emotion_design='不以为意(我会读) → 听到正确发音震惊 → 认真纠正',
    visual_variants=[
        '声波频谱风: 波形对比+标注',
        '发音X光风: 口腔截面图+舌位标注',
    ],
    color_config=ColorConfig(
        primary='#D63031', secondary='#0984E3', accent='#6C5CE7',
        error='#D63031', success='#0984E3', bg_style='solid',
    ),
    color_scheme='发音精准：错误红#D63031 + 正确蓝#0984E3 + 技巧紫#6C5CE7',
), '高中')

# ── 速记卡@高中 ──
_register_graded(SkillSchema(
    card_type='速记卡',
    teaching_goal='用最精简方式速记高考高频考点/规则/公式',
    core_strategy='核心规则超大字 → 考频标签 → 1道真题验证 → 易错速查',
    layout_blocks=[
        LayoutBlock('规则/公式超大', 'center', min_area_pct=45,
                    description='规则/公式/口诀超大字居中, 信息密度高但极度精炼',
                    attention_priority=1),
        LayoutBlock('真题验证', 'lower',
                    description='高考真题1道验证该规则, 关键词标注',
                    attention_priority=2),
        LayoutBlock('易错速查', 'bottom', max_chars=15,
                    description='⚠️ 2条高考易错点, 红色标记',
                    attention_priority=3),
    ],
    sub_types=[],
    visual_rule_summary='考前急救型: 规则超大字(45%)+考频标签+真题验证+易错, 考前30分钟看',
    visual_language='急救手册风: 红十字标记+大字规则+紧急提示, 像考前急救包',
    forbidden=[
        '不写多余解释',
        '中文不超过15字',
        '不列超过1道真题',
    ],
    required_elements=['核心规则超大字', '考频标签', '真题验证', '易错速查'],
    l1_interference=['中国学生考前容易死记硬背, 口诀化帮助快速提取'],
    max_info_chunks=4,
    hook_strategy='"高考前30分钟, 只看这张卡!"',
    emotion_design='焦虑(来不及了) → 看到精华 → 稳了',
    visual_variants=[
        '急救手册风: 红十字+大字+紧急标记',
        '霓虹灯广告风: 深色背景+发光文字',
    ],
    color_config=ColorConfig(
        primary='#FDCB6E', secondary='#6C5CE7', accent='#D63031',
        error='#D63031', success='#00B894', bg_style='gradient',
    ),
    color_scheme='速记金紫：规则金#FDCB6E + 真题紫#6C5CE7',
), '高中')

# ── PK挑战卡@高中 ──
_register_graded(SkillSchema(
    card_type='PK挑战卡',
    teaching_goal='通过高考级别PK二选一锻炼高级语法/词汇辨析能力',
    core_strategy='高考PK → 陷阱分析 → 精准解析 → 举一反三+写作运用',
    layout_blocks=[
        LayoutBlock('PK对决', 'top', min_area_pct=25,
                    description='A vs B高考级别对决, 大字+背景分屏, 视觉冲击',
                    attention_priority=1),
        LayoutBlock('陷阱+解析', 'middle', min_area_pct=35,
                    description='逐选项: 陷阱分析+高级例句(10-15词), ❌/✅全标注',
                    attention_priority=2),
        LayoutBlock('举一反三+写作', 'lower',
                    description='同类高考真题1道+写作应用场景',
                    attention_priority=2),
        LayoutBlock('判断口诀', 'bottom', max_chars=12,
                    description='考试判断口诀, 一句话',
                    attention_priority=3),
    ],
    sub_types=[],
    visual_rule_summary='电竞对决型: PK大屏(25%)+全选项分析(35%)+举一反三+写作运用',
    visual_language='电竞对决风: 大屏分屏+选手信息+VS特效+观众席(举一反三), 沉浸感',
    forbidden=[
        '不写太长解析',
        '例句不能短于8个英文单词',
        '中文不超过20字',
    ],
    required_elements=['高考PK', '全选项分析', '高级例句', '举一反三', '写作运用'],
    l1_interference=['高考选择题中, 中国学生靠语感+排除法, PK训练帮助建立精准判断逻辑'],
    max_info_chunks=5,
    hook_strategy='"这道高考真题, 全班只有3个人选对了!"',
    emotion_design='自信(我选A) → 全面分析后发现错了 → 深度理解',
    visual_variants=[
        '电竞对决风: 大屏+VS特效+选手信息',
        '辩论赛风: 正方vs反方+论据展示+裁判判决',
    ],
    color_config=ColorConfig(
        primary='#0984E3', secondary='#6C5CE7', accent='#FDCB6E',
        error='#D63031', success='#FDCB6E', bg_style='gradient',
    ),
    color_scheme='PK高考：A蓝#0984E3 vs B紫#6C5CE7 → 胜出金#FDCB6E',
), '高中')
