"""
Skill 规则 JSON Schema 化 — 将 Markdown Skill 文档转换为可编程的结构化数据。

设计理念:
  之前 Skill 规则以 Markdown 形式存在，注入 prompt 时依赖 AI "阅读理解"。
  结构化后:
    1. prompt_builder 可精确注入每个字段 → 减少遗漏
    2. prompt_auditor 可逐条检查必需元素 → 量化覆盖率
    3. 新增 Skill 只需填 JSON，无需改代码

版本: 1.0 (2025-06-27)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

# ═══════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════

@dataclass
class LayoutBlock:
    """布局区块定义"""
    name: str               # 区块名称，如 "标题", "例题", "解法"
    placement: str           # 位置描述: "top", "middle", "bottom", "left", "right"
    min_area_pct: int = 0    # 最小面积百分比 (0=不限)
    max_chars: int = 0       # 最大中文字数 (0=不限或非文字区)
    required: bool = True    # 是否必需
    description: str = ''    # 对该区块的补充说明


@dataclass
class SubType:
    """卡片子类型（如方法卡的 口算类、估算类）"""
    name: str                # 子类型名
    core_technique: str      # 核心技巧
    visual_method: str       # 视觉表达方式
    analogy: str = ''        # 推荐生活类比 (≤6字)
    typical_error: str = ''  # 典型易错提示
    examples: list[str] = field(default_factory=list)  # 例题示例


@dataclass
class SkillSchema:
    """一种卡片类型的完整 Skill 结构"""
    card_type: str                  # 卡片类型名: "方法卡", "概念卡" 等
    teaching_goal: str              # 教学目标 (一句话)
    core_strategy: str              # 核心设计思路 (如 "具体例题→色块分步→答案")
    layout_blocks: list[LayoutBlock]  # 布局区块定义
    sub_types: list[SubType]        # 子类型列表
    visual_rule_summary: str        # 一段话视觉策略摘要 (兼容 CARD_TYPE_VISUAL_RULES)
    forbidden: list[str]            # 禁止事项
    required_elements: list[str]    # 必须出现的教学元素名 (供审计器校验)
    color_scheme: str = ''          # 配色建议
    emotion_design: str = ''        # 情绪设计 (传播型卡片专属)


# ═══════════════════════════════════════════
# 10 种 Skill 定义
# ═══════════════════════════════════════════

_SKILL_REGISTRY: dict[str, SkillSchema] = {}


def _register(schema: SkillSchema):
    _SKILL_REGISTRY[schema.card_type] = schema
    return schema


# ── 方法卡 ──────────────────────────────────
_register(SkillSchema(
    card_type='方法卡',
    teaching_goal='看一道具体例题，就会做同类题',
    core_strategy='具体例题 → 色块分步 → 答案 + 口诀',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='≤8字 + 学科标签'),
        LayoutBlock('例题', 'upper', min_area_pct=15, description='白色卡片内，大字展示具体题目'),
        LayoutBlock('解法', 'middle', min_area_pct=30, description='色块/图示分步，只展示关键1-2步'),
        LayoutBlock('答案', 'lower', description='超大鲜明色 + 口诀便签'),
        LayoutBlock('易错', 'lower', max_chars=8, required=False, description='⚠️ 红色小字提示'),
        LayoutBlock('气泡(含类比)', 'corner', max_chars=6, required=False, description='小老师 + 生活类比'),
    ],
    sub_types=[
        SubType('口算类', '拆数法', '2-3个不同颜色色块', '拆快递分开称', '别忘添0'),
        SubType('估算类', '找近似数', '原数与近似数并排+≈箭头', '走路估距离', '估成整十数'),
        SubType('验算类', '反向检验', '左右并排原式|验算式', '买东西找零钱', '只验不写'),
        SubType('时间计算类', '时间轴可视化', '横轴起点→终点+经过时间', '坐公交数站', '别跨小时'),
        SubType('搭配问题类', '有序罗列', '树形图/连线图', '点菜搭套餐', '别重复'),
        SubType('统计类', '图表+数据读取', '简化条形图+箭头', '看身高表', '别看错格'),
    ],
    visual_rule_summary='运算方法类：色块拆分步骤；几何方法类：画图形+标注+辅助线',
    forbidden=[
        '不画完整竖式（拥挤、抽象）',
        '不省略题目直接讲方法',
        '不写多于2步的解题过程',
        '类比不能太抽象',
        '易错提示不能超过1条',
    ],
    required_elements=['例题', '色块分步解法', '答案', '口诀'],
    color_scheme='鲜明渐变背景，色块对比分步',
))

# ── 概念卡 ──────────────────────────────────
_register(SkillSchema(
    card_type='概念卡',
    teaching_goal='零基础学生一眼理解一个新概念是什么',
    core_strategy='生活场景 → 抽象概念 → 一句金句',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='≤8字 + 学科标签'),
        LayoutBlock('生活场景大图', 'middle', min_area_pct=45, description='实物/场景，标注清晰'),
        LayoutBlock('概念提炼', 'lower', max_chars=6, description='一句金句，从图到概念的桥梁'),
        LayoutBlock('易错', 'lower', max_chars=8, required=False, description='仅极易混淆概念加'),
        LayoutBlock('口诀+小老师', 'bottom', max_chars=10, description='帮助记忆'),
    ],
    sub_types=[],
    visual_rule_summary='用生活实物图解释抽象概念；概念名超大，定义浓缩≤6字金句',
    forbidden=[
        '不写教科书定义',
        '不列多个概念（一卡一概念）',
        '不用抽象符号代替实物图',
        '易错提示不强制',
    ],
    required_elements=['生活场景图', '概念金句', '口诀'],
    color_scheme='温暖明亮，薄荷蓝或蜜桃橙渐变',
))

# ── 辨析卡 ──────────────────────────────────
_register(SkillSchema(
    card_type='辨析卡',
    teaching_goal='一眼看出两个易混概念的区别在哪',
    core_strategy='✓/✗ 并排对比 → 红圈标差异 → 金句总结',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='≤8字 + ⚠️易错标签'),
        LayoutBlock('例题', 'upper', description='大字展示最易做错的题'),
        LayoutBlock('对比区', 'middle', min_area_pct=50, description='左✗右✓并排，红圈标差异点'),
        LayoutBlock('金句', 'lower', max_chars=6, description='超大字总结差异'),
        LayoutBlock('口诀+小老师', 'bottom', max_chars=10),
    ],
    sub_types=[],
    visual_rule_summary='左右并排对比：左❌红色错误 vs 右✅绿色正确，红圈标差异',
    forbidden=[
        '不超过1组对比',
        '差异点不超过1个',
        '不写长文字解释差异',
    ],
    required_elements=['例题', '左右对比区', '红圈差异标注', '金句'],
    color_scheme='对比强烈：✗红#FF4757 / ✓绿#2ED573',
))

# ── 公式卡 ──────────────────────────────────
_register(SkillSchema(
    card_type='公式卡',
    teaching_goal='理解公式从哪来 + 记住怎么用',
    core_strategy='图形实例 → 直观推导 → 公式 + 代入 + 类比',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='≤8字 + 学科标签'),
        LayoutBlock('例题', 'upper', description='具体数字题目'),
        LayoutBlock('推导图', 'middle', min_area_pct=30, description='可视化推导（格子图/流程图）'),
        LayoutBlock('公式', 'lower', description='超大醒目 + 代入计算 = 答案'),
        LayoutBlock('易错', 'lower', max_chars=8, required=False, description='红色小字'),
        LayoutBlock('口诀+气泡(含类比)', 'bottom', max_chars=10, description='小老师气泡含类比'),
    ],
    sub_types=[
        SubType('面积公式类', '格子推导', '长方形内画格子→数格子→长×宽', '铺地砖数几块', '别忘写平方'),
        SubType('判断规则类', '流程图', '÷4→÷100→÷400 判断流程图', '过关斗', '整百年要÷400'),
    ],
    visual_rule_summary='格子图推导→公式超大展示→代入验证小例子',
    forbidden=[
        '不只写公式不解释',
        '不写多个公式（一卡一公式）',
        '推导过程不超过3步',
        '类比不能脱离孩子生活经验',
        '易错提示不超过1条',
    ],
    required_elements=['例题', '可视化推导', '公式大字', '代入计算', '口诀'],
    color_scheme='清晰理性，公式用亮橙#FF9F43或亮蓝#54A0FF',
))

# ── 陷阱卡 ──────────────────────────────────
_register(SkillSchema(
    card_type='陷阱卡',
    teaching_goal='识别常见陷阱，利用先错后对的反转感加深记忆',
    core_strategy='设置陷阱 → 暴露错误 → 揭示真相',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='⚠️陷阱！+ 话题'),
        LayoutBlock('大题目', 'upper', min_area_pct=20, description='超大字展示题目'),
        LayoutBlock('钩子', 'upper', max_chars=8, description='"90%做错！"'),
        LayoutBlock('揭秘区', 'middle', min_area_pct=30, description='左✗红色错误 右✓绿色正确'),
        LayoutBlock('关键点', 'lower', max_chars=6, description='红圈标陷阱+≤6字说明'),
        LayoutBlock('口诀', 'bottom', max_chars=10, description='防踩坑口诀便签'),
    ],
    sub_types=[],
    visual_rule_summary="先设坑→展示错误答案画叉→揭示正确答案，标'90%同学做错'",
    forbidden=[
        '不选太偏的题',
        '不解释太多',
        '不居高临下的语气',
    ],
    required_elements=['题目', '钩子文案', '错误答案(划掉)', '正确答案', '陷阱标注'],
    color_scheme='警告感：蜜桃橙渐变，✗红#FF4757 ✓绿#2ED573',
    emotion_design='好奇+挑战 → 惊讶+恍然大悟',
))

# ── 速算卡 ──────────────────────────────────
_register(SkillSchema(
    card_type='速算卡',
    teaching_goal='掌握一种比常规方法更快更巧的计算技巧',
    core_strategy='常规慢方法 → 速算技巧 → 结果一致！',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='⚡速算 + 技巧名'),
        LayoutBlock('题目', 'upper', description='超大字展示具体计算题'),
        LayoutBlock('对比区', 'middle', min_area_pct=40, description='左🐢慢方法(灰) 右⚡快方法(彩)'),
        LayoutBlock('答案', 'lower', description='超大字 + "3秒搞定！"'),
        LayoutBlock('口诀', 'bottom', max_chars=10),
    ],
    sub_types=[
        SubType('口算加速类', '拆数凑整', '色块展示拆的过程'),
        SubType('乘法技巧类', '找规律/公式', '色块标注位置关系'),
        SubType('巧算类', '变换等式形式', '色块展示等价变换'),
    ],
    visual_rule_summary='左🐢慢方法(灰色划掉) vs 右⚡速算技巧(彩色高亮)',
    forbidden=[
        '不选只适用极少数字的技巧',
        '不展示复杂公式推导',
        '常规法不需完整展示',
    ],
    required_elements=['题目', '慢方法vs速算法对比', '速算步骤(≤2步)', '答案'],
    color_scheme='活力感：灰色(慢法) vs 彩色(速算)',
    emotion_design='好奇 → 惊喜("原来还能这样算！")',
))

# ── 挑战卡 ──────────────────────────────────
_register(SkillSchema(
    card_type='挑战卡',
    teaching_goal='通过游戏化挑战激发学生主动思考',
    core_strategy='限时 + 闯关 + 悬念答案',
    layout_blocks=[
        LayoutBlock('关卡编号', 'top', description='🏆 关卡编号 + 难度星标'),
        LayoutBlock('大题目', 'middle', min_area_pct=30, description='居中超大字展示'),
        LayoutBlock('挑战元素', 'middle', max_chars=6, description='⏱️30秒 / 🧠动动脑'),
        LayoutBlock('选项区', 'lower', required=False, description='A B C D 四选一'),
        LayoutBlock('底部提示', 'bottom', max_chars=8, description='"答案在评论区👇"'),
    ],
    sub_types=[],
    visual_rule_summary='关卡编号金色+大题目+倒计时元素+答案刮刮卡样式',
    forbidden=[
        '不一次放多道题',
        '不把答案放在同一张图上',
    ],
    required_elements=['关卡编号', '题目', '倒计时/挑战元素'],
    color_scheme='游戏感：亮紫蓝紫渐变，金色关卡编号',
    emotion_design='跃跃欲试 → 紧张专注 → 成就感',
))

# ── 生活卡 ──────────────────────────────────
_register(SkillSchema(
    card_type='生活卡',
    teaching_goal='理解数学是每天都在用的工具',
    core_strategy='生活场景 → 数学问题 → 实用解法',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='🏠 + 场景名'),
        LayoutBlock('场景大图', 'middle', min_area_pct=40, description='生活插画'),
        LayoutBlock('数学问题', 'middle', description='从场景中提取的具体问题'),
        LayoutBlock('解法', 'lower', description='在场景上标注+气泡计算'),
        LayoutBlock('结论', 'bottom', max_chars=8, description='实用小Tips'),
    ],
    sub_types=[],
    visual_rule_summary='生活场景插画(40%)+气泡标注计算+实用结论大字',
    forbidden=[
        '不变成纯应用题（要有场景氛围）',
        '不要太多文字（场景图为主）',
        '数字要真实合理',
    ],
    required_elements=['场景大图', '数学问题', '解法标注', '结论'],
    color_scheme='温暖生活感：暖黄渐变#FFD89B→#FFA7A7',
    emotion_design='熟悉感 → 恍然大悟 → 实用满足',
))

# ── 对战卡 ──────────────────────────────────
_register(SkillSchema(
    card_type='对战卡',
    teaching_goal='通过亲子/同学对战，在玩中复习',
    core_strategy='左右分栏 → 家长区/孩子区 → 同题PK',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=6, description='🆚 对战！+ 主题'),
        LayoutBlock('VS大字', 'upper', min_area_pct=20, description='左👨家长 中VS 右👧孩子'),
        LayoutBlock('题目区-左', 'middle-left', description='家长版题目（蓝色卡片）'),
        LayoutBlock('题目区-右', 'middle-right', description='孩子版题目（粉色卡片）'),
        LayoutBlock('底部计分栏', 'bottom', description='计分框 + "翻页看答案"'),
    ],
    sub_types=[],
    visual_rule_summary='左蓝(家长) VS 右粉(孩子)同类不同难度+计分栏',
    forbidden=[
        '家长版不能太难',
        '孩子版要让孩子有可能赢',
        '题目不要太多（一次一组）',
    ],
    required_elements=['VS大字', '家长区题目', '孩子区题目', '计分栏'],
    color_scheme='对抗活力：左蓝(家长) 右粉(孩子)',
    emotion_design='竞争欲 → 开心互动 → 亲子温馨',
))

# ── 思维卡 ──────────────────────────────────
_register(SkillSchema(
    card_type='思维卡',
    teaching_goal='培养数学思维能力，训练逻辑推理和模式识别',
    core_strategy='有趣问题 → 可视化思维过程 → 优雅解法',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='🧩 + "动动脑"/"巧解题"'),
        LayoutBlock('问题', 'upper', min_area_pct=20, description='趣味情境+具体问题'),
        LayoutBlock('思维区', 'middle', min_area_pct=45, description='可视化思考过程'),
        LayoutBlock('答案', 'lower', description='大字答案 + "思维妙招"一句话'),
        LayoutBlock('小老师', 'corner', max_chars=3, description='🧠 + "动动脑！"'),
    ],
    sub_types=[],
    visual_rule_summary='情境问题→色块分步可视化(45%)→方法名+答案醒目',
    forbidden=[
        '不是单纯计算题',
        '不要展示太多公式推导',
    ],
    required_elements=['趣味问题', '可视化思维过程', '答案', '方法名'],
    color_scheme='智慧感：亮紫→蓝紫渐变',
    emotion_design='好奇 → 专注思考 → "啊哈！"',
))


# ═══════════════════════════════════════════
# 英语卡片 Skill 定义 (6 种核心 + 3 种考试/传播)
# ═══════════════════════════════════════════

# ── 词汇卡 (英语) ──────────────────────────
_register(SkillSchema(
    card_type='词汇卡',
    teaching_goal='一眼记住一个英语单词/短语的含义、用法和拼写',
    core_strategy='英文关键词超大 → 2-3个用法例句 → ❌/✅ 对比 → 口诀便签',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='英文关键词大字 + 中文含义≤4字'),
        LayoutBlock('用法拓展区', 'middle', min_area_pct=40, description='2-3个用法，每个配完整英文例句≥6词'),
        LayoutBlock('对错对比', 'lower', description='❌ 错误用法 vs ✅ 正确用法，英文标注'),
        LayoutBlock('记忆口诀', 'bottom', max_chars=12, description='"English keyword + ≤4中文字" 混搭格式'),
    ],
    sub_types=[
        SubType('教室物品类', '实物联想', '图片化物品+英文标签', '指着课桌说desk', '别混chair和desk'),
        SubType('动物类', '拟声联想', '卡通动物+声音泡泡', '学猫叫cat', '别忘复数加s'),
        SubType('日常用语类', '场景对话', '对话泡泡+情景插图', '早上说morning', '别忘说please'),
    ],
    visual_rule_summary='英文关键词超大居中，2-3用法色块分栏，❌/✅对比醒目',
    forbidden=[
        '中文不能超过20字总量',
        '不写纯中文解释（必须有英文例句）',
        '例句不能短于6个英文单词',
        '不能有万能废话（如"一起来学习吧"）',
        '口诀区不能只有中文',
    ],
    required_elements=['英文关键词', '用法例句', '对错对比', '记忆口诀'],
    color_scheme='活力明亮：薄荷绿→天蓝渐变',
))

# ── 句型卡 (英语) ──────────────────────────
_register(SkillSchema(
    card_type='句型卡',
    teaching_goal='掌握一个核心句型的结构和实际运用',
    core_strategy='句型公式 → 2-3个替换例句 → ❌/✅ 对比 → 速记口诀',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='句型名 + 核心结构，含英文'),
        LayoutBlock('句型公式区', 'upper', min_area_pct=20, description='句型结构大字展示，可替换部分用色块标注'),
        LayoutBlock('例句展示区', 'middle', min_area_pct=30, description='2-3个完整英文例句，替换部分高亮'),
        LayoutBlock('对错对比', 'lower', description='❌ 常见语序错误 vs ✅ 正确语序'),
        LayoutBlock('记忆口诀', 'bottom', max_chars=12, description='结构速记口诀'),
    ],
    sub_types=[
        SubType('疑问句型', '变序法', '原句→打乱→重排动画效果', '排队换位置', '别忘问号'),
        SubType('There be句型', '存在图示', '场景图+箭头指物品+There is/are标注', '看房间数东西', 'is/are别混'),
        SubType('祈使句型', '命令场景', '人物指令泡泡+动作', '老师喊口令', '开头用动词原形'),
    ],
    visual_rule_summary='句型公式大字+可替换色块，例句高亮变化部分，❌/✅对比',
    forbidden=[
        '不列超过3个例句',
        '不写纯中文翻译（必须展示英文结构）',
        '中文不超过20字',
        '不能遗漏对错对比区',
    ],
    required_elements=['句型公式', '英文例句', '对错对比', '记忆口诀'],
    color_scheme='清新蓝橙：结构蓝#4ECDC4 + 重点橙#FF6B6B',
))

# ── 语法卡 (英语) ──────────────────────────
_register(SkillSchema(
    card_type='语法卡',
    teaching_goal='理解一个语法规则的本质并能正确运用',
    core_strategy='语法规则 → 时间轴/结构图 → 例句 → ❌/✅ 对比',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='语法点名称，含英文术语'),
        LayoutBlock('规则可视化区', 'middle', min_area_pct=45, description='时间轴/流程图/结构图展示规则'),
        LayoutBlock('例句区', 'lower', min_area_pct=15, description='2-3个完整英文例句，信号词高亮'),
        LayoutBlock('对错对比', 'lower', description='❌/✅ 对比常见错误'),
        LayoutBlock('速记公式', 'bottom', max_chars=12, description='公式 + 信号词总结'),
    ],
    sub_types=[
        SubType('时态类', '时间轴法', '横轴 past─now─future + 色块标时间范围 + 结构公式', '看日历翻页', '信号词别忘'),
        SubType('语态类', '主被动翻转', '主动句→箭头翻转→被动句，施受者换色', '点菜vs被端上来', 'be+过去分词'),
        SubType('从句类', '拆分拼接', '主句+从句色块拼接图，连接词高亮', '搭积木', '别丢连接词'),
    ],
    visual_rule_summary='时间轴/结构图为核心(45%)，信号词色块高亮，❌/✅对比',
    forbidden=[
        '不列超过3个例句',
        '不机械罗列语法术语',
        '中文不超过20字',
        '例句不能短于6个英文单词',
        '不能缺少可视化图示',
    ],
    required_elements=['语法规则', '可视化图示', '英文例句', '对错对比', '速记公式'],
    color_scheme='理性清晰：规则蓝#54A0FF + 信号词橙#FF9F43',
))

# ── 易混词卡 (英语) ──────────────────────────
_register(SkillSchema(
    card_type='易混词卡',
    teaching_goal='一眼看出两个易混英语词的核心区别',
    core_strategy='"A vs B" 双栏对比 → 各配例句 → 速记区分',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='"word_a vs word_b" 居中大字'),
        LayoutBlock('双栏对比区', 'middle', min_area_pct=50, description='左栏word_a vs 右栏word_b，各含词性+用法+完整例句'),
        LayoutBlock('速记区分', 'bottom', max_chars=15, description='区分口诀，英文关键词+≤4中文字'),
    ],
    sub_types=[
        SubType('指示代词类', '远近图示', '近处this圈+远处that圈，距离线标注', '伸手够不够得到', '近this远that'),
        SubType('冠词类', 'a/an/the规则', '元音辅音首字母+定/不定色块', '第一次见用a', 'a辅an元'),
        SubType('介词类', '空间位置图', '物体在容器内/外/上方的示意图', '球在盒子里外', 'in里on上'),
    ],
    visual_rule_summary='双栏对比(50%)+不同色底，各栏含英文例句，速记区醒目',
    forbidden=[
        '不超过2个词对比',
        '不写长段中文解释',
        '每栏必须有完整英文例句',
        '中文不超过20字',
    ],
    required_elements=['vs对比标题', '双栏对比', '英文例句', '速记区分'],
    color_scheme='对比分明：左蓝#4ECDC4 右绿#A8E6CE',
))

# ── 易混词陷阱卡 (英语·爆款) ──────────────
_register(SkillSchema(
    card_type='易混词陷阱卡',
    teaching_goal='用"90%同学做错"的反转感帮助记住易混词区别',
    core_strategy='设置陷阱 → 暴露错误 → 揭示区别 → 速记',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='情绪钩子标题，含英文词'),
        LayoutBlock('陷阱题', 'upper', min_area_pct=15, description='易错选择题，大字展示'),
        LayoutBlock('揭秘对比区', 'middle', min_area_pct=40, description='❌ 错误理解 vs ✅ 正确区别，双栏+英文例句'),
        LayoutBlock('速记区', 'bottom', max_chars=15, description='区分口诀'),
    ],
    sub_types=[],
    visual_rule_summary='钩子标题→陷阱题(15%)→❌/✅双栏揭秘(40%)→速记',
    forbidden=[
        '不写纯中文解释',
        '必须有完整英文例句',
        '卡通人物不能替代教学内容',
        '中文不超过20字',
    ],
    required_elements=['陷阱题', '对错揭秘', '英文例句', '速记口诀'],
    color_scheme='反转冲击：陷阱红#FF4757 → 正确绿#2ED573',
    emotion_design='自信 → 翻车震惊 → 恍然大悟',
))

# ── 语法辨析卡 (英语·专题) ──────────────
_register(SkillSchema(
    card_type='语法辨析卡',
    teaching_goal='理清两个易混语法结构的核心差异',
    core_strategy='语法点A vs B → 双栏结构对比 → 各配例句 → 速记',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='语法A vs 语法B，含英文术语'),
        LayoutBlock('双栏对比区', 'middle', min_area_pct=50, description='左栏语法A vs 右栏语法B：结构+用法+完整英文例句'),
        LayoutBlock('对错对比', 'lower', description='❌ 常见混淆错误 vs ✅ 正确用法'),
        LayoutBlock('速记区', 'bottom', max_chars=15, description='区分口诀'),
    ],
    sub_types=[],
    visual_rule_summary='双栏结构对比(50%) + ❌/✅对比 + 速记口诀',
    forbidden=[
        '不写大段语法术语',
        '每栏必须有完整英文例句',
        '中文不超过20字',
        '不能只有中文解释没有英文',
    ],
    required_elements=['双栏对比', '英文例句', '对错对比', '速记口诀'],
    color_scheme='语法蓝：左#54A0FF 右#48DBFB',
))

# ── 知识总结卡 (英语·总结) ──────────────
_register(SkillSchema(
    card_type='知识总结卡',
    teaching_goal='系统回顾一个单元/知识点的核心内容，备考复习',
    core_strategy='思维导图/知识树 → 核心考点 → 易错点 → 真题例句',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='知识点主题 + 考频标签'),
        LayoutBlock('知识树/导图', 'middle', min_area_pct=50, description='中心主题辐射2-4个分支，每支含英文要点'),
        LayoutBlock('易错提醒', 'lower', max_chars=15, description='⚠️ 最常见陷阱1条'),
        LayoutBlock('真题速记', 'bottom', max_chars=20, description='真题例句 + 得分要点'),
    ],
    sub_types=[],
    visual_rule_summary='思维导图/放射布局(50%) + 考频标签 + 易错提醒 + 真题',
    forbidden=[
        '不列超过4个分支',
        '不写大段文字（每个要点≤8字）',
        '中文不超过25字',
        '不能没有英文内容',
    ],
    required_elements=['知识树/导图', '英文要点', '易错提醒', '真题速记'],
    color_scheme='复习紫：主题紫#A55EEA + 考点橙#FF9F43',
))

# ── 情景对话卡 (英语) ──────────────────────
_register(SkillSchema(
    card_type='情景对话卡',
    teaching_goal='在真实情景中学会一组实用对话表达',
    core_strategy='情景图 → 对话泡泡 → 替换练习 → 口诀',
    layout_blocks=[
        LayoutBlock('标题', 'top', max_chars=8, description='情景名称，如"At the store"'),
        LayoutBlock('情景区', 'middle', min_area_pct=45, description='场景插图 + 2-3轮对话泡泡(全英文)'),
        LayoutBlock('替换练习', 'lower', description='关键词替换，2个变体'),
        LayoutBlock('口诀', 'bottom', max_chars=12, description='场景速记口诀'),
    ],
    sub_types=[],
    visual_rule_summary='场景插图(45%)+对话泡泡全英文，替换练习+场景口诀',
    forbidden=[
        '对话不能超过3轮',
        '不能只有中文翻译',
        '中文不超过20字',
    ],
    required_elements=['情景图', '英文对话', '替换练习', '口诀'],
    color_scheme='情景暖色：日常场景橙#FECA57 + 对话蓝#48DBFB',
))


# ═══════════════════════════════════════════
# 公共 API
# ═══════════════════════════════════════════

def get_skill_schema(card_type: str) -> SkillSchema | None:
    """获取指定卡片类型的 Skill Schema。
    
    Args:
        card_type: 卡片类型名，如 "方法卡", "概念卡"
    
    Returns:
        SkillSchema 实例，未找到则返回 None
    """
    return _SKILL_REGISTRY.get(card_type)


def get_all_skill_types() -> list[str]:
    """返回所有已注册的 Skill 类型名"""
    return list(_SKILL_REGISTRY.keys())


def get_layout_checklist(card_type: str) -> list[dict]:
    """获取指定类型的布局检查清单（供审计器使用）。
    
    Returns:
        [{'name': '标题', 'required': True, 'max_chars': 4, 'min_area_pct': 0}, ...]
    """
    schema = get_skill_schema(card_type)
    if not schema:
        return []
    return [
        {
            'name': b.name,
            'required': b.required,
            'max_chars': b.max_chars,
            'min_area_pct': b.min_area_pct,
            'description': b.description,
        }
        for b in schema.layout_blocks
    ]


def get_required_elements(card_type: str) -> list[str]:
    """获取必须出现的教学元素名列表（供审计器校验）"""
    schema = get_skill_schema(card_type)
    return schema.required_elements if schema else []


def get_forbidden_rules(card_type: str) -> list[str]:
    """获取禁止事项列表"""
    schema = get_skill_schema(card_type)
    return schema.forbidden if schema else []


def match_sub_type(card_type: str, card_data: dict) -> SubType | None:
    """根据卡片 JSON 数据匹配最佳子类型。
    
    匹配逻辑:
      - 从 title / definition / type 中提取关键词
      - 与每个 SubType.name 做关键词匹配
    
    Returns:
        匹配到的 SubType，无匹配则返回 None
    """
    schema = get_skill_schema(card_type)
    if not schema or not schema.sub_types:
        return None

    text = f"{card_data.get('title', '')} {card_data.get('definition', '')} {card_data.get('type', '')}"
    text = text.lower()

    # 关键词映射 (数学 + 英语)
    keyword_map = {
        # 数学
        '口算': ['口算', '心算'],
        '估算': ['估算', '估计', '大约'],
        '验算': ['验算', '检验', '验证'],
        '时间': ['时间', '时刻', '经过', '钟', '24时'],
        '搭配': ['搭配', '组合', '选择'],
        '统计': ['统计', '条形图', '数据', '图表'],
        '面积公式': ['面积', '公式', '长方形面积', '正方形面积'],
        '判断规则': ['闰年', '平年', '判断', '规则'],
        '口算加速': ['凑十', '凑整'],
        '乘法技巧': ['×11', '首同末合'],
        '巧算': ['巧算', '分配律', '简便'],
        # 英语 — 词汇卡
        '教室物品': ['classroom', '教室', 'desk', 'chair', 'pencil', '文具'],
        '动物': ['animal', '动物', 'cat', 'dog', 'bird', 'fish'],
        '日常用语': ['daily', '日常', 'greeting', 'hello', 'morning', 'please'],
        # 英语 — 句型卡
        '疑问句': ['疑问', 'question', 'who', 'what', 'where', 'how', '?'],
        'there be': ['there is', 'there are', '存在'],
        '祈使句': ['祈使', 'imperative', 'please', '动词原形'],
        # 英语 — 语法卡
        '时态': ['时态', 'tense', '现在时', '过去时', '将来时', 'present', 'past', 'future'],
        '语态': ['语态', 'voice', '被动', 'passive', 'active'],
        '从句': ['从句', 'clause', '定语从句', '状语从句', 'which', 'that'],
        # 英语 — 易混词卡
        '指示代词': ['this', 'that', 'these', 'those', '指示代词'],
        '冠词': ['a', 'an', 'the', '冠词', 'article'],
        '介词': ['in', 'on', 'at', '介词', 'preposition'],
    }

    best_match = None
    best_score = 0

    for st in schema.sub_types:
        score = 0
        st_lower = st.name.lower()
        # 直接名称匹配
        if st_lower in text:
            score += 10

        # 关键词匹配
        for kw_group, keywords in keyword_map.items():
            if kw_group.lower() in st_lower:
                for kw in keywords:
                    if kw in text:
                        score += 5

        # 核心技巧关键词匹配
        for word in st.core_technique.split('/')[:3]:
            if word.strip() in text:
                score += 3

        if score > best_score:
            best_score = score
            best_match = st

    return best_match if best_score > 0 else None


def build_skill_injection(card_type: str, card_data: dict) -> str:
    """构建可注入 prompt 的 Skill 结构化文本。
    
    将 SkillSchema 转换为可直接拼接到 prompt 中的指令文本，
    比原始 Markdown 更精确、更结构化。
    
    Returns:
        格式化的 Skill 注入文本；如果类型不存在返回空字符串
    """
    schema = get_skill_schema(card_type)
    if not schema:
        return ''

    lines = []
    lines.append(f'═══ SKILL规则: {schema.card_type} ═══')
    lines.append(f'教学目标: {schema.teaching_goal}')
    lines.append(f'核心策略: {schema.core_strategy}')

    # 布局区块
    lines.append('')
    lines.append('【布局结构】(必须严格遵守):')
    for b in schema.layout_blocks:
        req_flag = '★必需' if b.required else '☆可选'
        area_hint = f' ≥{b.min_area_pct}%面积' if b.min_area_pct else ''
        char_hint = f' ≤{b.max_chars}字' if b.max_chars else ''
        lines.append(f'  [{b.name}] ({b.placement}) {req_flag}{area_hint}{char_hint}')
        if b.description:
            lines.append(f'    → {b.description}')

    # 子类型匹配
    matched_sub = match_sub_type(card_type, card_data)
    if matched_sub:
        lines.append('')
        lines.append(f'【匹配子类型: {matched_sub.name}】')
        lines.append(f'  核心技巧: {matched_sub.core_technique}')
        lines.append(f'  视觉表达: {matched_sub.visual_method}')
        if matched_sub.analogy:
            lines.append(f'  💡 生活类比: "{matched_sub.analogy}"')
        if matched_sub.typical_error:
            lines.append(f'  ⚠️ 易错提示: "{matched_sub.typical_error}"')

    # 禁止事项
    if schema.forbidden:
        lines.append('')
        lines.append('【⛔ 禁止事项】:')
        for f in schema.forbidden:
            lines.append(f'  ❌ {f}')

    # 必须元素检查清单
    lines.append('')
    lines.append('【✅ 必须包含的教学元素】:')
    for elem in schema.required_elements:
        lines.append(f'  □ {elem}')

    lines.append(f'═══ END SKILL ═══')
    return '\n'.join(lines)


# ── 快速测试 ──
if __name__ == '__main__':
    print('=== Skill Schema Registry ===')
    for name in get_all_skill_types():
        schema = get_skill_schema(name)
        print(f'\n{name}: {schema.teaching_goal}')
        print(f'  布局: {len(schema.layout_blocks)} blocks')
        print(f'  子类型: {len(schema.sub_types)}')
        print(f'  必须元素: {schema.required_elements}')
        print(f'  禁止: {len(schema.forbidden)} rules')

    # 测试注入
    test_card = {'title': '口算整十÷一位数', 'definition': '口算除法方法', 'type': '方法卡'}
    print('\n=== 注入文本 ===')
    print(build_skill_injection('方法卡', test_card))
