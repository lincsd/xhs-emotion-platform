"""
分年级段英语 Skill Schema — 小学 / 初中 / 高中 差异化教学策略。

设计理念:
  同一种英语卡片类型（如词汇卡）在不同学段需要不同的:
    - 教学目标 (小学=基础认知, 初中=运用拓展, 高中=深度辨析)
    - 词汇难度 (小学≤4字母, 初中6-8字母, 高中多音节)
    - 例句要求 (小学3-5词, 初中6-10词, 高中10-15词)
    - 子类型 (小学=日常/动物, 初中=学术/话题, 高中=高级词汇/学术写作)
    - 布局复杂度 (小学=大图+少字, 初中=结构化, 高中=信息密集)

  查找优先级: _GRADED_SKILL_REGISTRY[(type, grade_level)] > _SKILL_REGISTRY[type]

版本: 1.0 (2025-07-01)
"""

from skill_schema import (
    SkillSchema, LayoutBlock, SubType,
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
        LayoutBlock('标题', 'top', max_chars=6, description='单词大字 + 中文≤3字'),
        LayoutBlock('图片联想区', 'middle', min_area_pct=35, description='卡通图片/实物插图，直观展示单词含义'),
        LayoutBlock('用法拓展区', 'middle', min_area_pct=20, description='1-2个简短例句(3-5词)，配中文翻译'),
        LayoutBlock('对错对比', 'lower', description='❌ 常见拼写错误 vs ✅ 正确拼写'),
        LayoutBlock('记忆口诀', 'bottom', max_chars=10, description='谐音/图形记忆法，趣味性优先'),
    ],
    sub_types=[
        SubType('教室物品类', '实物联想', '大幅卡通物品图+英文标签', '指着课桌说desk', '别混chair和desk'),
        SubType('动物类', '拟声联想', '可爱卡通动物+声音泡泡', '学猫叫cat', '别忘复数加s'),
        SubType('颜色形状类', '色块联想', '大色块/形状+英文标注', '看到红色说red', 'blue不是black'),
        SubType('家庭成员类', '人物图示', '简笔画家庭图+称呼标签', '叫妈妈mother', 'father不是farther'),
        SubType('食物类', '美食联想', '卡通食物图+英文', '苹果apple', '别漏双写字母'),
    ],
    visual_rule_summary='大幅卡通图(35%)+单词超大字+简短例句+趣味记忆，小学生友好、色彩活泼',
    forbidden=[
        '例句不超过5个英文单词',
        '中文不超过15字总量',
        '不写复杂语法解释',
        '不用音标以外的注音方式',
        '不能没有图片/插图元素',
    ],
    required_elements=['单词大字', '卡通图片', '简单例句', '趣味记忆法'],
    color_scheme='童趣彩虹：明黄#FFE066 + 天蓝#74B9FF + 粉红#FD79A8',
), '小学')

# ── 句型卡@小学 ──
_register_graded(SkillSchema(
    card_type='句型卡',
    teaching_goal='学会一个基础句型，能模仿造句',
    core_strategy='句型模板 → 填空示范 → 1-2个模仿例句 → 趣味口诀',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='句型名，如"I like ___"'),
        LayoutBlock('句型公式区', 'upper', min_area_pct=25, description='大字句型模板，可替换部分用色块/下划线'),
        LayoutBlock('例句展示区', 'middle', min_area_pct=25, description='1-2个简单例句(3-6词)，替换部分高亮'),
        LayoutBlock('对错对比', 'lower', description='❌ 常见词序错误 vs ✅ 正确语序'),
        LayoutBlock('记忆口诀', 'bottom', max_chars=10, description='朗朗上口的口诀'),
    ],
    sub_types=[
        SubType('自我介绍句型', '模板填空', '大字模板+色块填空', '介绍自己My name is', '别忘is'),
        SubType('询问句型', '问答配对', '问句+答句配对展示', '问How are you', '别忘问号'),
        SubType('描述句型', '看图说话', '图片+描述句模板', '看图说It is big', '别漏is/are'),
    ],
    visual_rule_summary='大字句型模板+色块填空+简短例句+趣味口诀，低年级友好',
    forbidden=[
        '不列超过2个例句',
        '例句不超过6个英文单词',
        '不讲语法术语（如"主语""谓语"）',
        '中文不超过15字',
    ],
    required_elements=['句型模板', '填空示范', '简单例句', '口诀'],
    color_scheme='清新活泼：结构蓝#74B9FF + 重点橙#FECA57',
), '小学')

# ── 语法卡@小学 ──
_register_graded(SkillSchema(
    card_type='语法卡',
    teaching_goal='用图示理解一个简单语法规则（如名词复数、be动词）',
    core_strategy='规则图示化 → 简单例句 → 对错对比 → 顺口溜',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='规则名称，用儿童化语言'),
        LayoutBlock('规则可视化区', 'middle', min_area_pct=40, description='卡通图示/流程图展示规则，避免术语'),
        LayoutBlock('例句区', 'lower', min_area_pct=15, description='1-2个简短例句(3-6词)'),
        LayoutBlock('对错对比', 'lower', description='❌/✅ 对比，用表情图标辅助'),
        LayoutBlock('速记公式', 'bottom', max_chars=10, description='顺口溜/口诀'),
    ],
    sub_types=[
        SubType('名词复数', '加s规则', '单数→复数变化图+卡通数量对比', '一个苹果变两个', '别忘加es的情况'),
        SubType('be动词', 'I am/you are', '人物配对图: I→am, you→are', '我是am你是are', '别把is给you'),
        SubType('冠词', 'a/an选择', '元音辅音首字母判断流程图', 'apple前用an', '不是看拼写看读音'),
    ],
    visual_rule_summary='卡通图示化语法规则(40%)+简短例句+表情辅助❌/✅+顺口溜',
    forbidden=[
        '不用语法术语（主语、谓语、宾语等）',
        '例句不超过6个英文单词',
        '不列超过2个例句',
        '中文不超过15字',
        '不能没有图示',
    ],
    required_elements=['图示化规则', '简单例句', '对错对比', '顺口溜'],
    color_scheme='童趣理性：规则蓝#74B9FF + 提示橙#FECA57',
), '小学')

# ── 易混词卡@小学 ──
_register_graded(SkillSchema(
    card_type='易混词卡',
    teaching_goal='用图片对比分清两个容易混淆的简单单词',
    core_strategy='卡通图片双栏对比 → 各配简短例句 → 趣味区分口诀',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='"word_a vs word_b" 大字'),
        LayoutBlock('双栏对比区', 'middle', min_area_pct=50, description='左图word_a vs 右图word_b，各含卡通图+简单例句(3-5词)'),
        LayoutBlock('速记区分', 'bottom', max_chars=12, description='趣味区分口诀'),
    ],
    sub_types=[
        SubType('形近词', '字母差异高亮', '两词并排，不同字母红色放大', '对比bat和bag', '看最后一个字母'),
        SubType('同音异义', '图片区分', '同一读音两张不同图片', 'see看到vs sea大海', '看上下文'),
    ],
    visual_rule_summary='大幅卡通双栏对比(50%)+简短例句+趣味口诀，图片为主文字为辅',
    forbidden=[
        '不超过2个词对比',
        '例句不超过5个英文单词',
        '不写复杂词性分析',
        '中文不超过12字',
    ],
    required_elements=['卡通对比图', '简单例句', '趣味口诀'],
    color_scheme='对比分明：左蓝#74B9FF 右粉#FD79A8',
), '小学')

# ── 易混词陷阱卡@小学 ──
_register_graded(SkillSchema(
    card_type='易混词陷阱卡',
    teaching_goal='用趣味陷阱让小学生记住两个容易混的单词',
    core_strategy='趣味选择题 → 揭秘正确答案 → 图片辅助记忆 → 口诀',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='趣味钩子标题'),
        LayoutBlock('陷阱题', 'upper', min_area_pct=15, description='简单选择题，大字+图片辅助'),
        LayoutBlock('揭秘对比区', 'middle', min_area_pct=35, description='❌ vs ✅ 用卡通图+简短说明'),
        LayoutBlock('速记区', 'bottom', max_chars=10, description='趣味口诀'),
    ],
    sub_types=[],
    visual_rule_summary='趣味钩子→简单陷阱题→卡通揭秘→口诀，低年级友好',
    forbidden=[
        '不写复杂语法分析',
        '中文不超过12字',
        '题目不超过6个英文单词',
    ],
    required_elements=['趣味陷阱题', '卡通揭秘', '口诀'],
    color_scheme='反转冲击：陷阱红#FF6B6B → 正确绿#2ED573',
    emotion_design='好奇 → 答错惊讶 → 恍然大悟',
), '小学')

# ── 知识总结卡@小学 ──
_register_graded(SkillSchema(
    card_type='知识总结卡',
    teaching_goal='用思维导图帮小学生回顾一个单元的核心词汇和句型',
    core_strategy='中心主题 → 2-3个分支(词汇/句型/语法) → 每支配图 → 易错提醒',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='单元主题 + 复习标签'),
        LayoutBlock('知识树/导图', 'middle', min_area_pct=50, description='中心主题辐射2-3个分支，每支含图标+英文要点'),
        LayoutBlock('易错提醒', 'lower', max_chars=12, description='⚠️ 最常见错误1条'),
        LayoutBlock('真题速记', 'bottom', max_chars=15, description='简单练习题1道'),
    ],
    sub_types=[],
    visual_rule_summary='简洁思维导图(50%)+图标辅助+少量文字+1条易错提醒',
    forbidden=[
        '分支不超过3个',
        '每个要点不超过5字',
        '中文不超过20字',
        '不堆砌大量单词列表',
    ],
    required_elements=['思维导图', '图标', '易错提醒'],
    color_scheme='复习彩色：多色分支+主题色圆心',
), '小学')

# ── 情景对话卡@小学 ──
_register_graded(SkillSchema(
    card_type='情景对话卡',
    teaching_goal='在卡通情景中学会2-3句日常英语对话',
    core_strategy='卡通情景图 → 2轮简单对话泡泡 → 替换词 → 口诀',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='情景名称，如"Say Hello"'),
        LayoutBlock('情景区', 'middle', min_area_pct=50, description='卡通场景 + 2轮对话泡泡(每句3-5词)'),
        LayoutBlock('替换练习', 'lower', description='1-2个替换词选项'),
        LayoutBlock('口诀', 'bottom', max_chars=10, description='模仿练习口诀'),
    ],
    sub_types=[],
    visual_rule_summary='大幅卡通场景(50%)+简短对话泡泡+替换词+口诀',
    forbidden=[
        '对话不超过2轮',
        '每句不超过5个英文单词',
        '不写成人化场景',
        '中文不超过12字',
    ],
    required_elements=['卡通情景图', '简短对话', '替换词'],
    color_scheme='情景暖色：场景橙#FECA57 + 对话蓝#74B9FF',
), '小学')

# ── 自然拼读卡@小学 (小学专属) ──
_register_graded(SkillSchema(
    card_type='自然拼读卡',
    teaching_goal='掌握字母/字母组合的发音规则，看到就能读',
    core_strategy='字母/组合大字 → 发音规则 → 3个示例单词+图 → 练习',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=6, description='字母/组合大字，如"ph"'),
        LayoutBlock('发音规则区', 'upper', min_area_pct=20, description='发音说明+口型图/音标'),
        LayoutBlock('示例单词区', 'middle', min_area_pct=35, description='3个含该发音的单词+卡通配图'),
        LayoutBlock('练习区', 'lower', description='找一找：哪个单词也有这个读音？'),
    ],
    sub_types=[
        SubType('单字母发音', '字母-音素对应', '字母大字+嘴型图+例词图片', 'a-apple-ant', '长短音之分'),
        SubType('字母组合', '组合读音规则', '两个字母合并+新读音+例词', 'sh-ship-fish', '别拆开读'),
        SubType('魔法e', '不发音e规则', '词尾e消失+前元音变化', 'cap→cape', '别忘了e不发音'),
    ],
    visual_rule_summary='字母大字+口型图+3个配图例词+趣味练习',
    forbidden=[
        '不用国际音标术语',
        '示例单词不超过3个',
        '中文不超过10字',
        '不写复杂发音规则',
    ],
    required_elements=['字母大字', '发音说明', '配图例词', '练习'],
    color_scheme='拼读彩色：字母红#FF6B6B + 例词蓝#74B9FF',
), '小学')

# ── 发音挑战卡@小学 ──
_register_graded(SkillSchema(
    card_type='发音挑战卡',
    teaching_goal='通过趣味挑战纠正常见发音错误',
    core_strategy='易错发音展示 → ❌错误读法 vs ✅正确读法 → 口型提示 → 练习',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='挑战标题，吸引小学生'),
        LayoutBlock('发音对比区', 'middle', min_area_pct=40, description='❌ 错误读音 vs ✅ 正确读音，配口型图'),
        LayoutBlock('练习区', 'lower', description='读一读：跟着正确发音练3遍'),
        LayoutBlock('口诀', 'bottom', max_chars=10, description='发音记忆口诀'),
    ],
    sub_types=[],
    visual_rule_summary='发音对比(40%)+口型图+趣味练习+口诀',
    forbidden=[
        '不用专业语音学术语',
        '中文不超过12字',
        '不写太多理论知识',
    ],
    required_elements=['发音对比', '口型提示', '练习'],
    color_scheme='挑战色：错误红#FF6B6B + 正确绿#00B894',
), '小学')


# ╔════════════════════════════════════════════╗
# ║           初 中 (七~九年级)                ║
# ╚════════════════════════════════════════════╝

# ── 词汇卡@初中 ──
_register_graded(SkillSchema(
    card_type='词汇卡',
    teaching_goal='掌握一个英语单词的词性、用法和常见搭配',
    core_strategy='单词+词性 → 2-3个用法例句(6-10词) → ❌/✅对比 → 搭配速记',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='单词大字 + 词性 + 中文含义≤4字'),
        LayoutBlock('用法拓展区', 'middle', min_area_pct=40, description='2-3个用法，含完整英文例句(6-10词)，不同词性/搭配分色'),
        LayoutBlock('对错对比', 'lower', description='❌ 常见误用 vs ✅ 正确用法(含完整英文句子)'),
        LayoutBlock('记忆口诀', 'bottom', max_chars=12, description='词根词缀记忆法/英中混搭口诀'),
    ],
    sub_types=[
        SubType('动词类', '时态+搭配', '动词原形→过去式→过去分词变化表+例句', '动词变形三兄弟', '不规则变化'),
        SubType('名词类', '可数/不可数', '可数vs不可数分栏+量词搭配', '能数的用many', 'much/many别混'),
        SubType('形容词类', '比较级+搭配', '原级→比较→最高三栏+例句', '高更高最高', '双音节前加more'),
        SubType('介词搭配', '固定搭配', '常见介词搭配表+例句', '动词+介词=新含义', 'look at/for/after'),
    ],
    visual_rule_summary='单词+词性大字+2-3用法色块例句+❌/✅搭配对比+词根记忆',
    forbidden=[
        '中文不超过20字总量',
        '例句不能短于6个英文单词',
        '不写纯中文解释（必须有英文例句）',
        '不能有万能废话',
        '口诀区不能只有中文',
    ],
    required_elements=['单词+词性', '用法例句', '对错对比', '搭配速记'],
    color_scheme='活力双色：薄荷绿#00B894 + 天蓝#0984E3',
), '初中')

# ── 句型卡@初中 ──
_register_graded(SkillSchema(
    card_type='句型卡',
    teaching_goal='掌握一个核心句型的结构、变换和实际运用',
    core_strategy='句型公式+结构标注 → 2-3个变换例句 → ❌/✅对比 → 考点口诀',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='句型名+核心结构，含英文'),
        LayoutBlock('句型公式区', 'upper', min_area_pct=20, description='句型结构大字，主语/谓语/宾语用不同色块'),
        LayoutBlock('例句展示区', 'middle', min_area_pct=30, description='2-3个完整例句(6-10词)，肯定/否定/疑问变换'),
        LayoutBlock('对错对比', 'lower', description='❌ 常见语序/时态错误 vs ✅ 正确形式'),
        LayoutBlock('记忆口诀', 'bottom', max_chars=12, description='考试速记口诀'),
    ],
    sub_types=[
        SubType('特殊疑问句', '疑问词前置', '疑问词+助动词+主语框架图', '问什么放什么前面', '别忘助动词'),
        SubType('There be句型', '就近原则', 'There is/are+名词位置图', '离谁近听谁的', 'is/are由最近名词定'),
        SubType('感叹句', 'What/How选择', 'What+名词 vs How+形容词判断流程', '有名词用What', '别看中文看英文结构'),
        SubType('宾语从句', '语序+时态', '主句+从句结构图+时态一致箭头', '从句用陈述语序', '主过从必过'),
    ],
    visual_rule_summary='句型公式色块标注(20%)+变换例句高亮+❌/✅对比+考试口诀',
    forbidden=[
        '不列超过3个例句',
        '例句不能短于6个英文单词',
        '中文不超过20字',
        '不能遗漏对错对比区',
    ],
    required_elements=['句型公式', '变换例句', '对错对比', '考点口诀'],
    color_scheme='结构蓝橙：主语蓝#0984E3 + 谓语橙#E17055 + 宾语绿#00B894',
), '初中')

# ── 语法卡@初中 ──
_register_graded(SkillSchema(
    card_type='语法卡',
    teaching_goal='用时间轴/结构图理解语法规则并能在考试中正确运用',
    core_strategy='语法规则+信号词 → 时间轴/结构图 → 例句(含信号词标注) → ❌/✅对比 → 考试公式',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='语法点名称+英文术语'),
        LayoutBlock('规则可视化区', 'middle', min_area_pct=45, description='时间轴/流程图/树状图，信号词色块标注'),
        LayoutBlock('例句区', 'lower', min_area_pct=15, description='2-3个完整句子(6-10词)，信号词高亮红色'),
        LayoutBlock('对错对比', 'lower', description='❌ 时态/语态错误 vs ✅ 正确形式(标注信号词)'),
        LayoutBlock('速记公式', 'bottom', max_chars=12, description='时态公式+信号词列表'),
    ],
    sub_types=[
        SubType('时态类', '时间轴法', '横轴past─now─future+色块+信号词表', '看日历翻页', '信号词是关键线索'),
        SubType('语态类', '主被动翻转', '主动→被动箭头翻转+be+done公式', '主角变配角', 'by+动作者可省'),
        SubType('从句类', '拆分拼接', '主句+从句色块+连接词高亮+语序箭头', '搭积木拼句子', '从句用陈述语序'),
        SubType('非谓语', '三种形式对比', 'to do/doing/done三栏+功能对比', '三种打扮同一人', '做主语用doing/to do'),
    ],
    visual_rule_summary='时间轴/结构图(45%)+信号词色块高亮+❌/✅对比+考试公式',
    forbidden=[
        '不列超过3个例句',
        '不堆砌语法术语',
        '例句不能短于6个英文单词',
        '中文不超过20字',
        '不能缺少可视化图示',
    ],
    required_elements=['语法规则', '可视化图示', '信号词', '例句', '对错对比', '速记公式'],
    color_scheme='理科清晰：规则蓝#0984E3 + 信号词红#D63031 + 公式金#FDCB6E',
), '初中')

# ── 易混词卡@初中 ──
_register_graded(SkillSchema(
    card_type='易混词卡',
    teaching_goal='从词性、搭配、语境三维度区分两个易混词',
    core_strategy='"A vs B" 双栏 → 词性+搭配+语境例句 → 考题陷阱 → 速记',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='"word_a vs word_b" 大字'),
        LayoutBlock('双栏对比区', 'middle', min_area_pct=50, description='左栏vs右栏: 词性+用法+完整例句(6-10词)+常见搭配'),
        LayoutBlock('考题陷阱', 'lower', max_chars=20, description='中考常考的选择题陷阱1道'),
        LayoutBlock('速记区分', 'bottom', max_chars=15, description='区分口诀+助记法'),
    ],
    sub_types=[
        SubType('动词辨析', '语境选词', '两个动词+各自搭配+语境例句', 'speak/say/tell/talk', '看搭配定选择'),
        SubType('介词辨析', '时空图示', '时间/空间位置图+介词标注', 'in/on/at对应大中小', '从范围大小选'),
        SubType('形容词辨析', '修饰对象', '修饰对象分类+例句对比', 'fun/funny/interesting', '看修饰人还是物'),
    ],
    visual_rule_summary='双栏对比(50%)+词性/搭配/例句三维+考题陷阱+速记口诀',
    forbidden=[
        '不超过2个词对比',
        '例句不能短于6个英文单词',
        '不写长段中文解释',
        '中文不超过20字',
    ],
    required_elements=['双栏对比', '词性搭配', '英文例句', '考题陷阱', '速记口诀'],
    color_scheme='辨析双色：左蓝#0984E3 右紫#6C5CE7',
), '初中')

# ── 易混词陷阱卡@初中 ──
_register_graded(SkillSchema(
    card_type='易混词陷阱卡',
    teaching_goal='用"中考真题陷阱"的紧迫感帮初中生记住易混词区别',
    core_strategy='真题级选择题 → 错误率统计 → 详细解析+例句 → 考试口诀',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='情绪钩子: "中考必考""每年都错"等'),
        LayoutBlock('陷阱题', 'upper', min_area_pct=15, description='中考难度选择题，大字展示'),
        LayoutBlock('揭秘对比区', 'middle', min_area_pct=40, description='❌ 错误分析(为什么选错) vs ✅ 正确解析+英文例句'),
        LayoutBlock('速记区', 'bottom', max_chars=15, description='考试速记口诀'),
    ],
    sub_types=[],
    visual_rule_summary='考试钩子→真题陷阱(15%)→❌/✅详细解析(40%)→考试口诀',
    forbidden=[
        '不写纯中文解释',
        '必须有完整英文例句',
        '中文不超过20字',
        '考题难度要符合中考水平',
    ],
    required_elements=['真题陷阱', '对错解析', '英文例句', '考试口诀'],
    color_scheme='考试警示：错误红#D63031 → 正确绿#00B894',
    emotion_design='紧张 → 翻车 → 恍然大悟 → 信心满满',
), '初中')

# ── 语法辨析卡@初中 ──
_register_graded(SkillSchema(
    card_type='语法辨析卡',
    teaching_goal='理清中考常考的两个语法结构差异',
    core_strategy='语法A vs B双栏 → 结构对比+信号词 → 真题例句 → 速记',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='语法A vs 语法B + 英文术语'),
        LayoutBlock('双栏对比区', 'middle', min_area_pct=50, description='左栏vs右栏: 结构公式+用法+信号词+完整例句(6-10词)'),
        LayoutBlock('对错对比', 'lower', description='❌ 常见混淆真题 vs ✅ 正确选择'),
        LayoutBlock('速记区', 'bottom', max_chars=15, description='区分口诀+信号词速查'),
    ],
    sub_types=[],
    visual_rule_summary='双栏结构对比(50%)+信号词标注+真题❌/✅+速记口诀',
    forbidden=[
        '不堆砌语法术语',
        '必须有完整英文例句',
        '中文不超过20字',
        '不能只有中文无英文',
    ],
    required_elements=['双栏对比', '信号词', '英文例句', '对错对比', '速记口诀'],
    color_scheme='语法双蓝：左#0984E3 右#00CEC9',
), '初中')

# ── 知识总结卡@初中 ──
_register_graded(SkillSchema(
    card_type='知识总结卡',
    teaching_goal='系统梳理一个语法专题或单元考点，形成考前记忆框架',
    core_strategy='思维导图 → 核心考点(含公式) → 信号词速查 → 真题例句 → 易错陷阱',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='专题名+考频标签(★★★)'),
        LayoutBlock('知识树/导图', 'middle', min_area_pct=50, description='中心辐射3-4个分支，每支含: 英文公式+信号词+考频'),
        LayoutBlock('易错提醒', 'lower', max_chars=15, description='⚠️ 最常见考试陷阱1-2条'),
        LayoutBlock('真题速记', 'bottom', max_chars=20, description='中考真题1道+得分提示'),
    ],
    sub_types=[],
    visual_rule_summary='思维导图/放射布局(50%)+考频标签+信号词+真题+易错',
    forbidden=[
        '分支不超过4个',
        '每个要点不超过8字',
        '中文不超过25字',
        '不能没有英文内容',
        '不堆砌知识点列表',
    ],
    required_elements=['知识导图', '英文公式', '信号词', '真题', '易错陷阱'],
    color_scheme='考试复习：主题紫#6C5CE7 + 考点红#D63031 + 公式蓝#0984E3',
), '初中')

# ── 情景对话卡@初中 ──
_register_graded(SkillSchema(
    card_type='情景对话卡',
    teaching_goal='在真实交际情景中学会一组实用对话并能变换运用',
    core_strategy='情景图 → 3轮对话(6-10词/句) → 功能句型提炼 → 替换练习 → 口诀',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='情景名称，如"At the doctor\'s"'),
        LayoutBlock('情景区', 'middle', min_area_pct=45, description='场景图+2-3轮对话泡泡(全英文6-10词/句)'),
        LayoutBlock('功能句型', 'lower', description='提炼1-2个核心功能句型+替换部分色块'),
        LayoutBlock('替换练习', 'lower', description='关键词替换2个变体'),
        LayoutBlock('口诀', 'bottom', max_chars=12, description='交际口诀'),
    ],
    sub_types=[],
    visual_rule_summary='场景图(45%)+全英文对话泡泡(3轮)+功能句型提炼+替换练习',
    forbidden=[
        '对话不超过3轮',
        '每轮不超过10个英文单词',
        '不能只有中文翻译',
        '中文不超过20字',
    ],
    required_elements=['情景图', '英文对话', '功能句型', '替换练习'],
    color_scheme='交际暖色：场景橙#E17055 + 对话蓝#0984E3',
), '初中')

# ── 时态卡@初中 (初中专属) ──
_register_graded(SkillSchema(
    card_type='时态卡',
    teaching_goal='用时间轴彻底理解一个时态的结构、用法和信号词',
    core_strategy='时间轴定位 → 结构公式 → 信号词 → 例句 → ❌/✅ → 考试口诀',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='时态名称+英文，如"现在完成时 Present Perfect"'),
        LayoutBlock('时间轴区', 'upper', min_area_pct=25, description='past─NOW─future 时间轴，标注该时态的时间范围'),
        LayoutBlock('结构公式区', 'middle', min_area_pct=20, description='肯定/否定/疑问三种结构公式'),
        LayoutBlock('例句+信号词', 'lower', min_area_pct=15, description='2-3个例句(6-10词)，信号词红色高亮'),
        LayoutBlock('对错对比', 'lower', description='❌ 时态混用错误 vs ✅ 正确选时'),
        LayoutBlock('速记公式', 'bottom', max_chars=15, description='时态口诀+信号词清单'),
    ],
    sub_types=[
        SubType('一般时', '基本结构', '时间轴单点标注+do/does/did', '拍照片定格', '三单加s'),
        SubType('进行时', '时间段', '时间轴色块段+be+doing', '正在拍视频', 'be别忘'),
        SubType('完成时', '从过去到现在', '时间轴箭头past→now+have/has+done', '从过去延续到现在', 'have/has选择'),
    ],
    visual_rule_summary='时间轴(25%)+三种结构公式(20%)+信号词高亮例句+❌/✅+口诀',
    forbidden=[
        '不列超过3个例句',
        '例句不能短于6个英文单词',
        '不堆砌时态术语',
        '中文不超过20字',
    ],
    required_elements=['时间轴', '三种结构公式', '信号词', '例句', '对错对比'],
    color_scheme='时态色轴：过去蓝#0984E3 → 现在绿#00B894 → 将来橙#E17055',
), '初中')

# ── PK挑战卡@初中 (初中专属) ──
_register_graded(SkillSchema(
    card_type='PK挑战卡',
    teaching_goal='通过快速PK二选一锻炼语法/词汇判断力',
    core_strategy='PK题目(A or B) → 倒计时紧迫感 → 正确解析 → 举一反三',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='PK挑战标题，如"秒杀选择题"'),
        LayoutBlock('PK题目区', 'upper', min_area_pct=25, description='A vs B 大字对决展示'),
        LayoutBlock('解析区', 'middle', min_area_pct=35, description='✅ 正确选项+解析理由+英文例句'),
        LayoutBlock('举一反三', 'lower', description='同类型变换题1道'),
        LayoutBlock('速记', 'bottom', max_chars=12, description='判断口诀'),
    ],
    sub_types=[],
    visual_rule_summary='A vs B对决展示(25%)+正确解析(35%)+举一反三+口诀',
    forbidden=[
        '不写太长的解析',
        '例句不能短于6个英文单词',
        '中文不超过20字',
    ],
    required_elements=['PK题目', '正确解析', '英文例句', '举一反三'],
    color_scheme='PK对决：A蓝#0984E3 vs B红#D63031 → 胜出绿#00B894',
    emotion_design='紧张选择 → 揭晓答案 → 成就感',
), '初中')

# ── 速记卡@初中 ──
_register_graded(SkillSchema(
    card_type='速记卡',
    teaching_goal='用最精简的方式快速记住一个考点/规则',
    core_strategy='核心规则大字 → 口诀/公式 → 1个例句验证 → 易错提醒',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='速记主题'),
        LayoutBlock('核心规则', 'middle', min_area_pct=40, description='规则公式/口诀超大字展示'),
        LayoutBlock('验证例句', 'lower', description='1个完整英文例句验证规则'),
        LayoutBlock('易错提醒', 'bottom', max_chars=10, description='⚠️ 最常见的1个错误'),
    ],
    sub_types=[],
    visual_rule_summary='规则超大字(40%)+口诀+1例句验证+易错提醒',
    forbidden=[
        '不写多余解释',
        '中文不超过15字',
        '不列超过1个例句',
    ],
    required_elements=['核心规则', '口诀', '验证例句'],
    color_scheme='速记黄蓝：规则金#FDCB6E + 例句蓝#0984E3',
), '初中')

# ── 发音挑战卡@初中 ──
_register_graded(SkillSchema(
    card_type='发音挑战卡',
    teaching_goal='纠正初中生常见的发音/重音错误，提升口语准确性',
    core_strategy='易错发音展示 → 发音规则 → ❌/✅音标对比 → 练习词组',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='发音挑战点'),
        LayoutBlock('发音对比区', 'middle', min_area_pct=40, description='❌ 常见错误发音 vs ✅ 正确发音+音标+重音标注'),
        LayoutBlock('规则区', 'lower', description='发音规则1条+重音位置说明'),
        LayoutBlock('练习', 'bottom', max_chars=15, description='3个练习词/短语'),
    ],
    sub_types=[],
    visual_rule_summary='发音对比(40%)+音标标注+规则+练习词组',
    forbidden=[
        '不写太专业的语音学术语',
        '中文不超过15字',
        '练习词不超过3个',
    ],
    required_elements=['发音对比', '音标', '发音规则', '练习'],
    color_scheme='发音双色：错误红#D63031 + 正确蓝#0984E3',
), '初中')


# ╔════════════════════════════════════════════╗
# ║           高 中 (高一~高三)                ║
# ╚════════════════════════════════════════════╝

# ── 词汇卡@高中 ──
_register_graded(SkillSchema(
    card_type='词汇卡',
    teaching_goal='深度掌握高频词的词族、多义辨析、学术搭配和写作运用',
    core_strategy='词根词缀拆解 → 多义项辨析 → 高级搭配+学术例句 → 写作替换升级 → 速记',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='单词+词根拆解+中文核心义'),
        LayoutBlock('词根拆解区', 'upper', min_area_pct=15, description='词根+前缀+后缀拆解图示'),
        LayoutBlock('用法拓展区', 'middle', min_area_pct=35, description='2-3个义项，各配高级例句(10-15词)+高考真题搭配'),
        LayoutBlock('对错对比', 'lower', description='❌ 低分表达 vs ✅ 高分替换(写作升级)'),
        LayoutBlock('记忆口诀', 'bottom', max_chars=12, description='词根联想法/词族记忆网'),
    ],
    sub_types=[
        SubType('多义词', '语境辨义', '义项树状图+各义项例句', '一词多面像变脸', '看上下文定义项'),
        SubType('词族扩展', '词根发散', '词根 → 衍生词族网络图', '一个根长出一棵树', '词性转换拼写变化'),
        SubType('学术词汇', '高频搭配', '搭配表+学术写作例句', '写作高分词', '避免口语化搭配'),
        SubType('易混高级词', '细微差异', '语义光谱: 同义词细微程度对比', '都是"重要"但程度不同', 'significant≠important≠vital'),
    ],
    visual_rule_summary='词根拆解图(15%)+多义项/搭配(35%)+低分→高分写作替换+词族网',
    forbidden=[
        '中文不超过20字总量',
        '例句不能短于8个英文单词',
        '不写初中水平的基础用法',
        '不能缺少高级搭配/写作替换',
        '口诀区不能只有中文',
    ],
    required_elements=['词根拆解', '多义辨析', '高级例句', '写作替换', '速记'],
    color_scheme='学术深色：词根紫#6C5CE7 + 义项蓝#0984E3 + 写作金#FDCB6E',
), '高中')

# ── 句型卡@高中 ──
_register_graded(SkillSchema(
    card_type='句型卡',
    teaching_goal='掌握高考高频/高级句型，提升写作和阅读理解能力',
    core_strategy='句型结构+语法分析 → 高考真题例句 → 写作升级对比 → 仿写模板',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='句型名+语法标签'),
        LayoutBlock('句型公式区', 'upper', min_area_pct=20, description='句型结构图，主从句用不同色块+语法成分标注'),
        LayoutBlock('例句展示区', 'middle', min_area_pct=30, description='2-3个高考级别例句(10-15词)，关键结构高亮'),
        LayoutBlock('写作升级', 'lower', description='❌ 低分简单句 → ✅ 高分升级句'),
        LayoutBlock('仿写模板', 'bottom', max_chars=15, description='留空仿写模板+写作场景提示'),
    ],
    sub_types=[
        SubType('倒装句', '主谓倒装', '正常语序→倒装语序对比图+触发条件', '把重点提前说', '看否定词/only/not until'),
        SubType('强调句', 'It is...that', '强调句结构图+可强调部分标注', '给重点加高光', '去掉It is/that句子完整'),
        SubType('独立主格', '名词+非谓语', '主句+独立主格附加结构图', '独立小分句挂在旁边', '逻辑主语不能缺'),
        SubType('复杂从句', '定语/状语/名词性', '多层从句嵌套结构图', '句子里套句子', '先找主干再拆从句'),
    ],
    visual_rule_summary='句型结构图(20%)+语法成分标注+高考例句+低→高分写作升级+仿写',
    forbidden=[
        '不列超过3个例句',
        '例句不能短于8个英文单词',
        '不写初中水平的基础句型',
        '中文不超过20字',
    ],
    required_elements=['句型结构图', '语法标注', '高考例句', '写作升级', '仿写模板'],
    color_scheme='高级蓝金：结构蓝#0984E3 + 升级金#FDCB6E + 从句紫#6C5CE7',
), '高中')

# ── 语法卡@高中 ──
_register_graded(SkillSchema(
    card_type='语法卡',
    teaching_goal='深度理解高中语法体系，能在阅读和写作中灵活运用',
    core_strategy='语法规则体系化 → 高考真题分析 → 多维对比 → 写作运用 → 速查表',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='语法专题+高考考频标签'),
        LayoutBlock('规则可视化区', 'middle', min_area_pct=45, description='语法体系树/时态矩阵/从句结构图，信息密度高'),
        LayoutBlock('例句区', 'lower', min_area_pct=15, description='2-3个高考真题级例句(10-15词)'),
        LayoutBlock('对错对比', 'lower', description='❌ 高考真题易错选项分析 vs ✅ 正确思路'),
        LayoutBlock('速记公式', 'bottom', max_chars=15, description='速查公式表+高频考点'),
    ],
    sub_types=[
        SubType('虚拟语气', '时态倒退法', '现实→虚拟时态对照表+if条件句', '如果穿越时空', '主从句时态搭配'),
        SubType('定语从句', '关系词选择', '先行词→关系词判断流程图', '给名词穿衣服', 'which/that/who/whose选择'),
        SubType('名词性从句', '四种从句', '主语/宾语/表语/同位语从句对比图', '句子当零件用', 'that是否可省'),
        SubType('非谓语动词', '三选一判断', 'to do/doing/done判断流程图+做什么成分', '三种变装', '主被动+时间关系'),
    ],
    visual_rule_summary='语法体系图(45%)+高考真题+❌/✅解题分析+速查公式表',
    forbidden=[
        '不列超过3个例句',
        '例句不能短于8个英文单词',
        '不写初中基础内容',
        '中文不超过20字',
        '不能缺少高考真题链接',
    ],
    required_elements=['语法体系图', '高考真题', '对错分析', '速查表'],
    color_scheme='深度蓝紫：体系蓝#0984E3 + 真题紫#6C5CE7 + 速查金#FDCB6E',
), '高中')

# ── 易混词卡@高中 ──
_register_graded(SkillSchema(
    card_type='易混词卡',
    teaching_goal='精准辨析高级近义词/易混词在学术写作和高考中的区别',
    core_strategy='语义光谱 → 搭配差异 → 语域/语体差异 → 高考真题 → 替换升级',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='"word_a vs word_b" + 考频'),
        LayoutBlock('双栏对比区', 'middle', min_area_pct=50, description='语义细微差异+搭配+语域+高考级例句(10-15词)'),
        LayoutBlock('考题陷阱', 'lower', max_chars=20, description='高考真题/模拟题1道'),
        LayoutBlock('速记区分', 'bottom', max_chars=15, description='辨析口诀+语义光谱图'),
    ],
    sub_types=[
        SubType('近义动词', '语义细微差异', '语义强度光谱图+各自搭配', 'affect/influence/impact', '程度和方向不同'),
        SubType('近义形容词', '修饰范围', '适用语境Venn图+例句', 'big/large/great/huge', '看正式程度和语境'),
        SubType('学术近义词', '写作替换', '初级词→高级替换表+例句', 'important→significant/crucial', '高分词精准替换'),
    ],
    visual_rule_summary='双栏对比(50%)+语义光谱+搭配差异+高考真题+写作替换',
    forbidden=[
        '不超过2个词对比',
        '例句不能短于8个英文单词',
        '不写基础义项',
        '中文不超过20字',
    ],
    required_elements=['语义辨析', '搭配差异', '高级例句', '高考真题', '速记'],
    color_scheme='辨析渐变：浅蓝#74B9FF → 深紫#6C5CE7',
), '高中')

# ── 易混词陷阱卡@高中 ──
_register_graded(SkillSchema(
    card_type='易混词陷阱卡',
    teaching_goal='用高考真题陷阱帮高中生精准掌握高级词汇辨析',
    core_strategy='高考真题/模拟题 → 选项分析 → 语义/搭配/语域解析 → 高分口诀',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='高考钩子: "高考必考辨析""阅卷老师最看重"'),
        LayoutBlock('陷阱题', 'upper', min_area_pct=15, description='高考级别选择/填空题'),
        LayoutBlock('揭秘对比区', 'middle', min_area_pct=40, description='❌ 各选项错误原因 vs ✅ 正确选项+语义/搭配/语域分析'),
        LayoutBlock('速记区', 'bottom', max_chars=15, description='高考速记口诀'),
    ],
    sub_types=[],
    visual_rule_summary='高考钩子→真题陷阱(15%)→全选项分析(40%)→高考口诀',
    forbidden=[
        '不写纯中文解释',
        '必须有高级英文例句',
        '中文不超过20字',
        '难度要达到高考水平',
    ],
    required_elements=['高考真题', '全选项分析', '语义辨析', '高考口诀'],
    color_scheme='高考警示：错误红#D63031 → 正确金#FDCB6E',
    emotion_design='自信满满 → 陷阱翻车 → 深度恍然 → 举一反三',
), '高中')

# ── 知识总结卡@高中 ──
_register_graded(SkillSchema(
    card_type='知识总结卡',
    teaching_goal='构建高考语法/词汇知识体系，形成考前速查框架',
    core_strategy='知识体系图 → 考频分级 → 高考真题速查 → 写作提分点 → 易错陷阱清单',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='专题名+考频(★★★★★)'),
        LayoutBlock('知识树/导图', 'middle', min_area_pct=50, description='体系化导图3-4分支，每支含: 规则+公式+真题+考频'),
        LayoutBlock('写作提分', 'lower', max_chars=20, description='该知识点在写作中的高分运用1-2条'),
        LayoutBlock('易错提醒', 'lower', max_chars=15, description='⚠️ 高考高频陷阱2条'),
        LayoutBlock('真题速记', 'bottom', max_chars=20, description='经典高考真题1道+解题思路'),
    ],
    sub_types=[],
    visual_rule_summary='体系化导图(50%)+考频分级+写作提分+高考真题+易错陷阱',
    forbidden=[
        '分支不超过4个',
        '不堆砌知识点',
        '中文不超过25字',
        '不能没有高考真题',
        '不写初中基础内容',
    ],
    required_elements=['知识体系图', '考频标签', '写作提分', '高考真题', '易错陷阱'],
    color_scheme='高考冲刺：体系紫#6C5CE7 + 真题红#D63031 + 提分金#FDCB6E',
), '高中')

# ── 词汇深度卡@高中 (高中专属) ──
_register_graded(SkillSchema(
    card_type='词汇深度卡',
    teaching_goal='深挖一个核心词的词族网络、多义辨析和学术写作应用',
    core_strategy='词根拆解 → 词族网络(名/动/形/副) → 多义语境辨析 → 高考真题 → 写作替换',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='核心词+词根+考频'),
        LayoutBlock('词族网络', 'upper', min_area_pct=25, description='词根→衍生词网络图(名/形/动/副)'),
        LayoutBlock('多义辨析', 'middle', min_area_pct=30, description='2-3个义项+高级例句(10-15词)+搭配'),
        LayoutBlock('写作替换', 'lower', description='❌ 低分表达 → ✅ 该词高分替换'),
        LayoutBlock('真题', 'bottom', max_chars=15, description='高考真题1道'),
    ],
    sub_types=[],
    visual_rule_summary='词族网络(25%)+多义辨析(30%)+写作升级+高考真题',
    forbidden=[
        '例句不能短于8个英文单词',
        '不写初中基础义项',
        '中文不超过20字',
    ],
    required_elements=['词族网络', '多义辨析', '高级例句', '写作替换'],
    color_scheme='深度紫金：词根紫#6C5CE7 + 义项蓝#0984E3 + 写作金#FDCB6E',
), '高中')

# ── 高级语法卡@高中 (高中专属) ──
_register_graded(SkillSchema(
    card_type='高级语法卡',
    teaching_goal='掌握高考高难语法(虚拟/倒装/强调/独立主格)的判断和运用',
    core_strategy='语法结构图 → 判断流程 → 高考真题分析 → 写作运用 → 速查口诀',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='高级语法点+考频'),
        LayoutBlock('结构图', 'upper', min_area_pct=25, description='语法结构/判断流程图'),
        LayoutBlock('真题分析', 'middle', min_area_pct=30, description='2-3个高考真题+解题过程，关键信号词标注'),
        LayoutBlock('写作运用', 'lower', description='该语法在写作中的高分用法+模板句'),
        LayoutBlock('速查', 'bottom', max_chars=15, description='判断口诀+信号词清单'),
    ],
    sub_types=[
        SubType('虚拟语气', '时态倒退', '现实vs虚拟时态对照表', '如果穿越改变过去', '与事实相反倒退一个时态'),
        SubType('倒装句', '触发条件', '正常→倒装对比+触发词清单', '把重要的提前说', 'Only/Not until/否定词'),
        SubType('强调句', 'It is...that', '强调句判断流程+去框架测试', '给重点加聚光灯', '去掉It is和that句子完整'),
        SubType('独立主格', '名词+非谓语', '主句+附加结构图示', '独立小句挂旁边', '逻辑主语≠主句主语'),
    ],
    visual_rule_summary='结构/流程图(25%)+高考真题分析(30%)+写作运用+速查口诀',
    forbidden=[
        '不列超过3道真题',
        '例句不能短于8个英文单词',
        '不写初中基础',
        '中文不超过20字',
    ],
    required_elements=['结构图', '判断流程', '高考真题', '写作运用', '速查口诀'],
    color_scheme='高级深蓝：结构蓝#0984E3 + 真题紫#6C5CE7 + 写作金#FDCB6E',
), '高中')

# ── 从句进阶卡@高中 (高中专属) ──
_register_graded(SkillSchema(
    card_type='从句进阶卡',
    teaching_goal='掌握复杂从句(定/状/名词性)的辨析、嵌套和写作运用',
    core_strategy='三种从句对比 → 关系词选择流程 → 嵌套结构分析 → 高考真题 → 写作模板',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='从句类型+考频'),
        LayoutBlock('对比区', 'upper', min_area_pct=25, description='定/状/名词性从句特征对比表'),
        LayoutBlock('判断流程', 'middle', min_area_pct=25, description='关系词/连接词选择流程图'),
        LayoutBlock('真题区', 'lower', min_area_pct=15, description='高考真题1-2道+解题标注'),
        LayoutBlock('写作模板', 'bottom', max_chars=15, description='从句在写作中的高分模板句'),
    ],
    sub_types=[],
    visual_rule_summary='三种从句对比(25%)+判断流程(25%)+高考真题+写作模板',
    forbidden=[
        '不堆砌概念',
        '例句不能短于8个英文单词',
        '不写初中基础',
        '中文不超过20字',
    ],
    required_elements=['从句对比', '判断流程', '高考真题', '写作模板'],
    color_scheme='从句三色：定语蓝#0984E3 + 状语绿#00B894 + 名词紫#6C5CE7',
), '高中')

# ── 写作进阶卡@高中 (高中专属) ──
_register_graded(SkillSchema(
    card_type='写作进阶卡',
    teaching_goal='掌握一个高考写作高分技巧/句型，直接提分',
    core_strategy='低分→高分对比 → 升级技巧+模板 → 高考范文片段 → 仿写练习',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='写作技巧名+提分标签'),
        LayoutBlock('对比升级区', 'upper', min_area_pct=30, description='❌ 低分表达 → ✅ 高分升级，2-3组对比'),
        LayoutBlock('技巧+模板', 'middle', min_area_pct=25, description='升级技巧说明+可套用的写作模板'),
        LayoutBlock('范文片段', 'lower', description='高考满分作文片段展示'),
        LayoutBlock('仿写练习', 'bottom', max_chars=15, description='留空仿写1句'),
    ],
    sub_types=[
        SubType('开头升级', '引人入胜开头', '低分开头→高分开头3种方式对比', '好文章靠开头', '不写Dear/Hello'),
        SubType('连接升级', '逻辑连接词', '初级连接→高级连接替换表', '让句子手拉手', 'and→furthermore/moreover'),
        SubType('结尾升级', '总结+呼应', '低分结尾→高分结尾对比', '好结尾余味无穷', '不写That is all'),
    ],
    visual_rule_summary='低→高分对比(30%)+技巧模板(25%)+范文片段+仿写练习',
    forbidden=[
        '不超过3组对比',
        '例句不能短于8个英文单词',
        '不写初中水平表达',
        '中文不超过20字',
    ],
    required_elements=['低高分对比', '写作技巧', '模板句', '范文片段', '仿写'],
    color_scheme='写作进阶：低分灰#636E72 → 高分金#FDCB6E',
), '高中')

# ── 阅读技巧卡@高中 (高中专属) ──
_register_graded(SkillSchema(
    card_type='阅读技巧卡',
    teaching_goal='掌握高考阅读理解的解题技巧和信息定位方法',
    core_strategy='题型分类 → 解题步骤 → 信号词/关键句 → 真题示范 → 速查口诀',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='阅读技巧名+题型标签'),
        LayoutBlock('解题流程', 'upper', min_area_pct=30, description='解题步骤流程图(3-4步)'),
        LayoutBlock('信号词区', 'middle', min_area_pct=20, description='该题型的关键信号词/句型清单'),
        LayoutBlock('真题示范', 'lower', description='高考阅读真题片段+标注解题过程'),
        LayoutBlock('速查口诀', 'bottom', max_chars=15, description='解题口诀'),
    ],
    sub_types=[
        SubType('主旨大意', '首尾段法', '首段+尾段+各段首句标注图', '看头看尾知全貌', '别被细节诱导'),
        SubType('细节查找', '定位法', '题目关键词→原文定位→答案提取', '按图索骥找答案', '看原文别靠记忆'),
        SubType('推断题', '逻辑推理', '原文信息→逻辑推导→排除→选择', '不是猜是推理', '必须有原文依据'),
        SubType('词义猜测', '上下文线索', '未知词+上下文线索词标注', '像侦探找线索', '看转折/同义/定义'),
    ],
    visual_rule_summary='解题流程图(30%)+信号词表(20%)+真题标注示范+口诀',
    forbidden=[
        '解题步骤不超过4步',
        '不写太多理论',
        '中文不超过20字',
    ],
    required_elements=['解题流程', '信号词', '真题示范', '解题口诀'],
    color_scheme='阅读科技蓝：流程蓝#0984E3 + 信号绿#00B894 + 答案金#FDCB6E',
), '高中')

# ── 发音挑战卡@高中 ──
_register_graded(SkillSchema(
    card_type='发音挑战卡',
    teaching_goal='纠正高级词汇的发音/重音错误，提升口语和听力能力',
    core_strategy='高级词汇发音 → 重音规则 → 音标精准对比 → 连读/弱读规则 → 练习',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='发音难点/规则'),
        LayoutBlock('发音对比区', 'middle', min_area_pct=40, description='❌ 中式发音错误 vs ✅ 准确发音+完整音标+重音标注'),
        LayoutBlock('规则区', 'lower', description='发音规则+连读/弱读规律说明'),
        LayoutBlock('练习', 'bottom', max_chars=20, description='5个高频词发音练习+易错标注'),
    ],
    sub_types=[],
    visual_rule_summary='精确音标对比(40%)+重音标注+连读弱读规则+高频词练习',
    forbidden=[
        '中文不超过15字',
        '不写基础发音',
        '练习词不超过5个',
    ],
    required_elements=['音标对比', '重音规则', '连读弱读', '发音练习'],
    color_scheme='发音精准：错误红#D63031 + 正确蓝#0984E3 + 技巧紫#6C5CE7',
), '高中')

# ── 速记卡@高中 ──
_register_graded(SkillSchema(
    card_type='速记卡',
    teaching_goal='用最精简方式速记高考高频考点/规则/公式',
    core_strategy='核心规则/公式 → 高考考频 → 1道真题验证 → 易错速查',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='速记主题+考频★'),
        LayoutBlock('核心规则', 'middle', min_area_pct=40, description='规则/公式/口诀超大字，信息密度高'),
        LayoutBlock('真题验证', 'lower', description='高考真题1道验证该规则'),
        LayoutBlock('易错速查', 'bottom', max_chars=15, description='⚠️ 2条高考易错点'),
    ],
    sub_types=[],
    visual_rule_summary='规则超大字(40%)+考频标签+真题验证+易错速查',
    forbidden=[
        '不写多余解释',
        '中文不超过15字',
        '不列超过1道真题',
    ],
    required_elements=['核心规则', '考频标签', '真题验证', '易错速查'],
    color_scheme='速记金紫：规则金#FDCB6E + 真题紫#6C5CE7',
), '高中')

# ── PK挑战卡@高中 ──
_register_graded(SkillSchema(
    card_type='PK挑战卡',
    teaching_goal='通过高考级别PK二选一锻炼高级语法/词汇辨析能力',
    core_strategy='高考难度PK题 → 陷阱分析 → 精准解析+高级例句 → 举一反三+写作运用',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='PK挑战标题+难度标签'),
        LayoutBlock('PK题目区', 'upper', min_area_pct=25, description='A vs B 高考级别对决'),
        LayoutBlock('解析区', 'middle', min_area_pct=35, description='✅ 正确+❌ 错误全分析+高级例句(10-15词)'),
        LayoutBlock('举一反三', 'lower', description='同类高考真题1道+写作应用'),
        LayoutBlock('速记', 'bottom', max_chars=12, description='考试判断口诀'),
    ],
    sub_types=[],
    visual_rule_summary='高考PK对决(25%)+全选项分析(35%)+举一反三+写作运用',
    forbidden=[
        '不写太长解析',
        '例句不能短于8个英文单词',
        '中文不超过20字',
    ],
    required_elements=['高考PK题', '全选项分析', '高级例句', '举一反三'],
    color_scheme='PK高考：A蓝#0984E3 vs B紫#6C5CE7 → 胜出金#FDCB6E',
    emotion_design='紧张 → 陷阱揭秘 → 深度理解',
), '高中')


# ═══════════════════════════════════════════
# 汇总统计
# ═══════════════════════════════════════════

def _print_summary():
    """打印分年级段注册汇总"""
    from collections import defaultdict
    by_level = defaultdict(list)
    for (ct, gl) in sorted(_GRADED_SKILL_REGISTRY_KEYS()):
        by_level[gl].append(ct)
    
    for gl in ('小学', '初中', '高中'):
        types = by_level.get(gl, [])
        print(f'{gl}: {len(types)} types → {", ".join(types)}')


def _GRADED_SKILL_REGISTRY_KEYS():
    """内部用: 获取所有 graded key"""
    from skill_schema import _GRADED_SKILL_REGISTRY
    return _GRADED_SKILL_REGISTRY.keys()
