# 📚 知识卡片图片提示词规范 v2.0

> 基于小红书爆款知识卡片分析 + 3张高质量参考图总结
> v2.0 新增: 内容审校规范 + 英语语法卡专属规则

---

## 一、参考图深度分析

### 图1: 直线、射线、线段基础知识
| 维度 | 分析 |
|------|------|
| 布局 | **三栏对比布局**，直线/射线/线段并排，底部附加「线段中点」「距离」两个补充卡片 |
| 文字量 | **极精简**：每个概念只用 2-3 行关键短语，不写完整句子 |
| 视觉元素 | 点A/B标注的几何图示、箭头、彩色高亮框、手绘星星/叶子装饰 |
| 配色 | 暖米色底 + 粉/蓝/绿三色区分三栏 + 黄色/橙色高亮框 |
| 信息密度 | **高但不杂**：每栏=图示+定义框+关键属性，一眼扫完 |
| 标题 | 顶部横幅式大标题 + 「基本公理」副标题丝带 |

### 图2: 角(Angles) 定义、度量、分类与应用
| 维度 | 分析 |
|------|------|
| 布局 | **分区块布局**（4段），每段有明确边框和标题标签 |
| 文字量 | 极精简。「静态：有公共端点的两条射线组成的图形」一句话搞定 |
| 视觉元素 | 时钟图(度量)、卡通小人(特殊角)、量角器、三角尺、放大镜 |
| 配色 | 暖米色底 + 蓝/绿/粉/橙区块边框 |
| 信息密度 | 5个特殊角用图示+角度一排展示，极高效 |
| 标题 | 大字标题 + 英文副标题(Angles)，增加专业感 |

### 图3: 角的关系与性质—余角与补角
| 维度 | 分析 |
|------|------|
| 布局 | **对称对比**（余角 vs 补角）+ **性质推导区** + **应用区（方位角）** |
| 文字量 | 定义只用一句话，公式突出展示（∠1+∠2=90°） |
| 视觉元素 | 几何图示、指南针、帆船、圆规、三角尺、灯泡icon |
| 配色 | 复古暖色调 + 金/蓝/粉区分区块 |
| 特色 | 底部方位角是**实际应用**场景，增加实用性 |

---

## 二、爆款知识卡片共性规律（核心发现）

### 🎯 文字法则：「3-5-8」原则
- 标题: **≤8个字**（如「直线、射线、线段」）
- 每个知识点: **≤5行**，每行≤15字
- 全卡总文字量: **≤150字**（不含公式符号）
- ❌ 绝不写段落/长句，只写**关键词+短语+公式**

### 🎨 视觉法则：「图>字」
- 每个知识点**必须配图示**（几何图、示意图、对比图）
- 图示占比 ≥ 40%，文字占比 ≤ 35%，留白+装饰 ≈ 25%
- 公式/数字要**放大突出**（如 ∠1+∠2=90° 比文字定义醒目10x）

### 📐 布局法则：「结构化 > 堆砌」
- **对比型**：2-3栏并排（适合相似概念：直线vs射线vs线段）
- **分层型**：从上到下3-4个区块（适合单一概念深入：角的定义→度量→分类→应用）
- **中心型**：中间核心概念 + 四周展开（适合知识网络）
- 每个区块有**明确边框+标题标签**，扫一眼就知道结构

### 🌈 配色法则
- 底色：暖色系（米色/牛皮纸/浅黄），**绝不用纯白**
- 区分色：每个知识点/栏位用不同**柔和色**（粉/蓝/绿/橙/紫）
- 强调色：关键公式/数字用**对比色**高亮

### ✏️ 风格法则
- 整体风格：**手绘插画 + 笔记本风**（非PPT风、非教科书风）
- 装饰元素：小星星★、云朵☁、铅笔✏、尺子📏、灯泡💡、书本📖
- 字体感觉：标题手写感、正文圆体、公式衬线体
- **不加水印/Logo**（后期可加）

---

## 三、提示词规范标准

### Step 1: 知识点精简（Gemini 2.5 Flash 负责）

输入知识点JSON后，AI需要做：

1. **精简文字**：
   - 标题缩到 ≤8字
   - 定义压缩到1句话（≤20字）
   - 核心要点 → 关键短语（每条≤12字，最多3条）
   - 公式/数字提取单独展示
   - 记忆口诀压缩到≤20字

2. **选择布局**：
   - 2-3个相关概念 → 对比型（并排）
   - 单一概念 → 分层型（上→下）
   - 概念+应用 → 混合型

3. **确定视觉元素**：
   - 每个知识点指定1个配图（几何图示/示意图/对比表）
   - 指定2-3个装饰元素
   - 确定配色方案

### Step 2: 图片生成提示词模板

```
[STRUCTURE]
A vertical educational knowledge card poster (3:4 aspect ratio, 900x1200px).
Warm {color_tone} gradient background (NOT pure white).
Hand-drawn notebook style, flat illustration, cute kawaii aesthetic.

[TITLE AREA - Top 15%]
Large decorative banner with title text "{title_cn}" in bold hand-drawn style.
{Subtitle or English name if applicable}
Decorated with {2-3 small icons: stars, sparkles, pencils, etc.}

[MAIN CONTENT - Middle 65%]
{Layout type: comparison/layered/center}

{For each knowledge block:}
- Section with {color} rounded border and label tag "{section_title}"
- Inside: {diagram description} showing {geometric/visual representation}
- Key text: "{concise_text_cn}" in clear readable Chinese font
- Formula/number: "{formula}" displayed prominently in larger size
- Small icon decoration: {icon description}

[BOTTOM AREA - Bottom 20%]
{Memory tip or additional concept}
"{memory_phrase_cn}" in handwritten style on a sticky-note shaped element
{1-2 cute decorative elements}

[STYLE KEYWORDS]
cute, kawaii, hand-drawn, flat illustration, educational infographic,
warm color palette, notebook aesthetic, Chinese text clearly readable,
high contrast text, organized layout, visual hierarchy
```

### Step 3: 质量检查清单

生成的提示词必须满足：
- [ ] 中文文字总量 ≤ 150字
- [ ] 每个知识点有配图/图示描述
- [ ] 指定了具体配色（不说"colorful"，而说"soft pink, sky blue, mint green"）
- [ ] 布局结构明确（提到几栏/几行/对齐方式）
- [ ] 标题文字在引号内，确保生成
- [ ] 关键公式单独放大展示
- [ ] 有2-3个具体装饰元素描述
- [ ] 风格关键词完整
- [ ] 提示词长度 250-400 英文单词

---

## 四、针对不同年级的风格微调

| 年级 | 风格倾向 | 配色 | 装饰 |
|------|---------|------|------|
| 1-2年级 | 超可爱卡通 | 彩虹色系 | 动物、气球、彩虹 |
| 3-4年级 | 可爱+清晰 | 柔和暖色 | 星星、铅笔、书本 |
| 5-6年级 | 清爽+专业 | 蓝绿为主 | 尺子、计算器、灯泡 |
| 初中 | 手绘笔记风 | 复古暖色 | 圆规、三角尺、公式符号 |

---

## 五、关键差异：当前做法 vs 新规范

| 维度 | 旧做法（v1） | 新规范（v2） |
|------|-------------|-------------|
| 文字量 | 200-300字/卡 | **≤150字/卡** |
| 定义 | 完整句子（30-50字）| **关键短语（≤20字）** |
| 核心要点 | 4-5条完整句 | **2-3条短语（≤12字/条）** |
| 例题 | 完整题+步骤 | **仅展示关键公式/图示** |
| 布局 | 只说"educational poster" | **明确指定栏数/分区/对齐** |
| 图示 | 无具体描述 | **每个知识点配图示描述** |
| 配色 | "colorful" | **具体色名 soft pink, mint green** |
| 公式 | 混在文字里 | **单独放大突出展示** |

---

## 六、内容审校规范 (v2.0 新增)

> 模块文件: `card_review.py`
> 接入位置: `generate_card_images.py` 主循环 Step 0

### 6.1 审校流程 (三层闸门)

```
卡片 JSON
   │
   ▼
Layer 1: 硬规则校验 (validate_hard_rules)
   │  纯代码，零延迟
   │  不通过 → 直接跳过，记录 rejected_hard_rule
   ▼
Layer 2: AI 教学审稿 (review_teaching_quality)
   │  调 Gemini 2.5 Flash，~3s
   │  仅英语语法卡启用，其他学科跳过
   │  不通过 → 跳过，记录 rejected_teaching_review
   ▼
Layer 3: 结构化 Payload 构建 (build_structured_payload)
   │  将卡片信息压缩为固定槽位
   ▼
Prompt 生成 → 图片生成
```

### 6.2 硬规则清单 (Layer 1)

| # | 规则 | 适用范围 | 说明 |
|---|------|---------|------|
| R1 | 不允许重复词 | 全部 | 如 `can can`、`the the` |
| R2 | 不允许残缺表达 | 含英文卡 | 如 `success in` 末尾无宾语 |
| R3 | mistakes 必须成对 | 全部 | wrong + correct 都不能为空 |
| R4 | 正确例句必须完整 | 英语卡 | 至少 3 个单词，像完整句子 |
| R5 | 单卡知识点 ≤ 1 | 英语卡 | core_points 中主题不能分裂 |
| R6 | 错因不能笼统 | 英语卡 | 不能只写"词性错"/"搭配错" |
| R7 | 标题 ≤ 20 字 | 全部 | 过长标题无法在卡片上展示 |
| R8 | definition 不能为空 | 全部 | 基础字段必填 |

### 6.3 AI 审稿标准 (Layer 2)

审稿输出固定 JSON 格式:

```json
{
  "pass": true,
  "language_score": 92,
  "teaching_score": 88,
  "issues": [],
  "rewrite_suggestion": ""
}
```

**通过条件:**
- `language_score ≥ 90`
- `teaching_score ≥ 85`
- `issues` 为空

**评分维度:**

| 维度 | 权重 | 说明 |
|------|------|------|
| 语言自然度 | language_score | 英文是否地道自然，无语法错 |
| 语法准确性 | language_score | 搭配、词性、句法是否正确 |
| 知识点聚焦 | teaching_score | 是否只聚焦一个主知识点 |
| 正误对比清晰度 | teaching_score | 错句真错、正句真对、错因具体 |
| 秒懂适配度 | teaching_score | 是否适合压缩成图片教学卡 |

### 6.4 self_optimizer 记录规范

审校结果通过 `final_action` 字段记录:

| final_action 值 | 含义 |
|-----------------|------|
| `pass` | 审校通过，成功出图 |
| `rejected_hard_rule` | 硬规则拦截 |
| `rejected_ai_review` | AI 审稿拦截 |

---

## 七、英语语法卡专属规范 (v2.0 新增)

> 模块: `card_review.py` → `generate_english_grammar_prompt()`
> 条件: `subject == '英语'` 或卡片内容命中语法关键词

### 7.1 核心原则

1. **一张卡只讲一个主知识点**
2. 正句必须是完整自然英语
3. 错因必须具体（标注词性/搭配/句法）
4. 不能混入第二个知识点
5. 不能把词组碎片当作最终正确答案

### 7.2 固定信息块 (6 个槽位)

| 槽位 | 字数限制 | 示例 |
|------|---------|------|
| 标题 | ≤ 8 字 | 高频搭配: pay attention to |
| 主规则 | ≤ 15 字 | pay attention to + 名词/动名词 |
| 正确例句 | 完整英文句 | It is important to pay close attention to details so you can succeed. |
| 错误例句 | 完整英文句 | ✗ ...so you can can successful in career. |
| 错因解释 | ≤ 15 字 | succeed 是动词，这里不能用形容词 successful |
| 记忆点 | ≤ 10 字 | 搭配多记 熟能生巧 |

### 7.3 视觉规则

- 最多 3 个视觉区块
- 最多 3 处高亮重点
- ≥ 25% 留白
- ✓ 正确用翠绿 `#2ED573`
- ✗ 错误用亮红 `#FF4757`
- 全卡中文 ≤ 30 字
- 英文例句保持原样，关键词高亮

### 7.4 禁止事项

- ❌ 一张卡同时讲搭配 + 词性辨析
- ❌ 只展示短语碎片充当"正确答案"
- ❌ 错因只写"词性错"不解释具体是哪个词
- ❌ 出现 `can can` 等重复词
- ❌ 出现 `success in` 等残缺表达
- ❌ 高亮颜色超过 3 种
- ❌ 信息块超过 3 个
