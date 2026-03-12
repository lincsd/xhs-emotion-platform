# 🎯 Skill 系统架构文档

> 小红书运营平台 — 多账号类型复用框架

---

## 一、概述

Skill 系统允许同一套运营平台代码适配多种小红书账号类型。通过切换 Skill，平台的 UI 文案、AI 提示词、分类体系、变现策略、发布时间推荐等全部自动切换，无需修改代码。

**当前支持的 7 种账号类型：**

| Skill | ID | Icon | 主色 | 分类数 |
|-------|----|------|------|--------|
| 情感 | `emotion` | 🌸 | `#ff2442` | 8 |
| 美食 | `food` | 🍜 | `#ff6b35` | 8 |
| 旅行 | `travel` | ✈️ | `#1da1f2` | 8 |
| 健身 | `fitness` | 💪 | `#27ae60` | 8 |
| 穿搭 | `fashion` | 👗 | `#9b59b6` | 8 |
| 科技数码 | `tech` | 📱 | `#2c3e50` | 8 |

---

## 二、Skill 配置结构

每个 Skill 是一个 JS 对象，挂载在 `SKILL_TEMPLATES` registry 中，key 为中文名。完整字段定义如下：

### 2.1 基础信息

```js
{
  id: 'emotion',          // 英文标识
  name: '情感',           // 中文名
  icon: '🌸',            // 图标
  color: '#ff2442',       // 主色调
  title: '小红书情感账号 · 运营管理平台',  // 浏览器标题
  sidebarTitle: '🌸 情感运营台',          // 侧边栏标题
  subtitle: '一键自动生成小红书情感笔记',    // 内容生成区副标题
  monetizationSubtitle: '情感账号系统化变现策略', // 变现区副标题
  categoryLabel: '情感分类',               // 分类标签文字
}
```

### 2.2 分类体系

```js
{
  categories: ['治愈','成长','爱情','友情','自我','离别','温暖','释怀'],
  categoryColors: {
    '治愈': '#FFB6C1',
    '成长': '#90EE90',
    // ...
  },
  categoryEmojis: {
    '治愈': '🌸',
    '成长': '🌱',
    // ...
  },
  defaultCategory: '治愈',  // 默认分类（新建笔记 / fallback 用）
}
```

### 2.3 图片风格

```js
{
  imageStyles: {
    xiaohongshu: '小红书情感风格',   // 下拉选项显示名
    minimalist: '极简文艺风',
    watercolor: '水彩插画风',
    gradient: '渐变文字风',
    photo: '治愈摄影风',
  },
  imageStylePrompts: {
    xiaohongshu: '小红书风格，柔和的色调，文艺感...',  // AI 图片生成提示词
    minimalist: '极简设计，大面积留白...',
    // ...
  },
}
```

### 2.4 品牌化配置 (branding)

```js
{
  branding: {
    // 默认值（用户未填时的 fallback）
    niche: '小红书情感成长账号',
    audience: '20-35岁希望被治愈、获得情绪价值和成长启发的女生',
    persona: '温柔但有边界感，像一个清醒又会共情的朋友',
    keywords: '治愈,成长,边界感,清醒,温柔坚定',

    // 表单 placeholder
    nichePlaceholder: '例如：治愈系情感 / 女性成长 / 清醒恋爱观',
    audiencePlaceholder: '例如：20-35岁女生、失恋恢复期...',
    personaPlaceholder: '例如：温柔知性、清醒通透...',
    keywordsPlaceholder: '例如：治愈,清醒,边界感...',
    tagsPlaceholder: '治愈文字,情感语录,正能量',

    // 预览区
    previewChips: ['治愈语录','清醒成长','关系边界'],
    avatarFallback: '🌸',

    // 名称风格选项
    nameStyles: ['温柔治愈','高级故事感','简短好记','有记忆点'],

    // AI 生图用
    promptPrefix: '情感成长类账号',
    avatarSuffix: '小红书情感成长账号头像，正方形构图...',
    bannerSuffix: '为小红书个人主页顶部封面生成横版视觉图...',
  },
}
```

### 2.5 AI 配置

```js
{
  aiRole: '资深小红书情感类博主',    // AI 人设
  aiNiche: '情感类',                // AI 领域标识
  searchKeywords: (cat) => [         // 搜索关键词生成函数
    `小红书 ${cat} 情感文案 爆款`,
    `小红书 ${cat} 语录 点赞高`,
    // ...
  ],
}
```

### 2.6 发布时间推荐

```js
{
  postingTimeTips: {
    '治愈': '💡 治愈类内容在深夜和清晨效果最佳...',
    '成长': '💡 成长类内容适合早起时段...',
    // ... 每个分类一条提示
  },
  postingTimeBonus: {
    '治愈': { '07:00': 2, '22:00': 3, '23:00': 2 },
    '成长': { '07:00': 3, '08:00': 2, '21:00': 1 },
    // ... 每个分类的时段加权分数
  },
}
```

### 2.7 变现方案

```js
{
  monetization: {
    strategies: [
      {
        name: '广告合作',
        icon: '📢',
        threshold: '1000粉丝起',
        income: '200-2000元/条',
        description: '品牌方找你投放情感类软文...',
        tips: ['保持内容调性一致', '选择与情感相关的品牌', '...'],
      },
      // ... 共 7 种策略
    ],
    roadmap: [
      {
        phase: '冷启动期',
        duration: '1-2个月',
        followers: '0-1000',
        tasks: ['每天发2-3条优质笔记', '...'],
      },
      // 成长期、变现期、规模化
    ],
  },
}
```

### 2.8 内容生成引擎数据（contentEngine）

> 注：当前 `ContentEngine` 是全局对象，仅情感类有完整内容模板。其他 Skill 的 `contentEngine` 值为 `null`，使用 AI 模式生成内容。

```js
{
  contentEngine: null,  // 或关联 ContentEngine 数据
}
```

---

## 三、运行机制

### 3.1 核心变量与函数

```
index.html 中的位置:
├── SKILL_TEMPLATES        (L1811~L2268)  — 7 个 Skill 完整定义
├── currentSkillName       (L2270)        — 当前激活的 Skill 名（localStorage 持久化）
├── getCurrentSkill()      (L2271)        — 返回当前 Skill 对象
├── _s()                   (L2275)        — getCurrentSkill() 的简写
├── switchSkill(name)      (L2280)        — 切换 Skill，刷新UI
├── applySkillToUI()       (L2294)        — 将 Skill 配置写入 DOM
├── _fillCategorySelect()  (L2330)        — 动态填充分类下拉
├── _fillImageStyleSelect()(L2345)        — 动态填充图片风格下拉
├── _fillNameStyleSelect() (L2356)        — 动态填充名称风格下拉
├── _applyBrandingDefaults()(L2365)       — 设置品牌化表单 placeholder
├── _applyBrandingPlaceholders() (L2377)  — 设置标签 placeholder
└── _applyPreviewChips()   (L2383)        — 设置预览区 chips 和头像 fallback
```

### 3.2 切换流程

```
用户在侧边栏选择新 Skill
       │
       ▼
  switchSkill(skillName)
       │
       ├── 保存到 localStorage('xhs_current_skill')
       ├── 更新 categoryColors / categoryEmojis 变量
       ├── 调用 applySkillToUI()
       │      ├── document.title = sk.title
       │      ├── 侧边栏标题
       │      ├── 各区域副标题
       │      ├── 分类标签文字
       │      ├── 填充所有 <select> 下拉
       │      ├── 品牌化表单 placeholder
       │      ├── 预览区 chips
       │      └── Skill 切换器回显
       ├── toast 提示
       └── showPage(currentPage) 重新渲染当前页面
```

### 3.3 动态常量

以下全局常量通过 ES6 getter 动态引用当前 Skill 的数据：

| 常量 | 位置 | getter 引用 |
|------|------|------------|
| `POSTING_TIME_GUIDE.categoryBonus` | L2573 | `_s().postingTimeBonus` |
| `POSTING_TIME_GUIDE.tips` | L2573 | `_s().postingTimeTips` |
| `MONETIZATION_DATA.strategies` | L2840 | `_s().monetization.strategies` |
| `MONETIZATION_DATA.roadmap` | L2840 | `_s().monetization.roadmap` |
| `IMAGE_STYLE_PROMPTS` | L3358 | `Proxy → _s().imageStylePrompts` |

### 3.4 AI 提示词中的引用

所有 AI 生成函数都使用 `_s()` 获取当前 Skill 配置：

| 函数 | 引用字段 |
|------|----------|
| `_searchAndAnalyzeXHS()` | `sk.searchKeywords(cat)`, `sk.aiRole`, `sk.aiNiche` |
| `_analyzeWithoutSearch()` | `sk.aiRole`, `sk.aiNiche` |
| `_generateFromAnalysis()` | `sk.aiRole`, `sk.aiNiche` |
| `generateCoverImage()` | `_s().aiNiche` |
| `generateContentImagesForPost()` | `_s().aiNiche` (用于 5 张内容图) |
| `generateBrandingPackage()` | `sk.branding.*`, `sk.aiRole`, `sk.branding.avatarSuffix/bannerSuffix` |

---

## 四、各 Skill 详细配置

### 🌸 情感 (emotion)

| 字段 | 值 |
|------|-----|
| 分类 | 治愈、成长、爱情、友情、自我、离别、温暖、释怀 |
| AI 角色 | 资深小红书情感类博主 |
| 默认定位 | 小红书情感成长账号 |
| 目标人群 | 20-35岁希望被治愈、获得情绪价值和成长启发的女生 |
| 变现策略 | 广告合作、蒲公英、付费咨询、课程/电子书、表情包/壁纸、直播打赏、账号矩阵 |

### 🍜 美食 (food)

| 字段 | 值 |
|------|-----|
| 分类 | 家常菜、烘焙、探店、减脂餐、甜品、早餐、宵夜、饮品 |
| AI 角色 | 资深小红书美食类博主 |
| 默认定位 | 小红书美食分享账号 |
| 目标人群 | 20-40岁爱做饭、爱吃的年轻人，上班族、宝妈 |
| 变现策略 | 品牌推广、蒲公英、食谱电子书、团购带货、探店合作、直播做饭、账号矩阵 |

### ✈️ 旅行 (travel)

| 字段 | 值 |
|------|-----|
| 分类 | 城市探索、Nature徒步、住宿推荐、穷游攻略、亲子游、摄影旅拍、自驾游、美食旅行 |
| AI 角色 | 资深小红书旅行类博主 |
| 默认定位 | 小红书旅行攻略账号 |
| 目标人群 | 20-35岁爱旅行的年轻人、自由职业者 |
| 变现策略 | 酒店/民宿合作、旅游品牌推广、蒲公英、攻略付费、旅拍约拍、直播旅行、账号矩阵 |

### 💪 健身 (fitness)

| 字段 | 值 |
|------|-----|
| 分类 | 减脂、增肌、瑜伽、跑步、居家健身、饮食搭配、体态矫正、健身穿搭 |
| AI 角色 | 资深小红书健身类博主 |
| 默认定位 | 小红书健身减脂账号 |
| 目标人群 | 20-35岁想减肥塑形、改善体态的年轻人 |
| 变现策略 | 运动品牌推广、蒲公英、私教课程、健身食品带货、体态评估、直播健身、账号矩阵 |

### 👗 穿搭 (fashion)

| 字段 | 值 |
|------|-----|
| 分类 | 日常穿搭、通勤OL、约会穿搭、季节穿搭、小个子、微胖穿搭、大牌平替、配饰搭配 |
| AI 角色 | 资深小红书穿搭时尚博主 |
| 默认定位 | 小红书穿搭分享账号 |
| 目标人群 | 18-35岁爱美的女生，学生/上班族 |
| 变现策略 | 服装品牌推广、蒲公英、好物带货、穿搭咨询、穿搭课程、直播试穿、账号矩阵 |

### 📱 科技数码 (tech)

| 字段 | 值 |
|------|-----|
| 分类 | 手机评测、电脑数码、好物推荐、App推荐、摄影技巧、智能家居、游戏、效率工具 |
| AI 角色 | 资深小红书科技数码博主 |
| 默认定位 | 小红书科技数码账号 |
| 目标人群 | 18-35岁数码爱好者、学生、上班族 |
| 变现策略 | 品牌推广、蒲公英、好物带货、付费教程、技术咨询、直播评测、账号矩阵 |

---

## 五、如何新增一个 Skill

### 步骤 1：在 `SKILL_TEMPLATES` 中添加新条目

在 `index.html` 中找到 `const SKILL_TEMPLATES = {`，在最后一个 Skill 后面添加：

```js
'母婴': {
  id: 'parenting',
  name: '母婴',
  icon: '👶',
  color: '#ff9ec6',
  title: '小红书母婴账号 · 运营管理平台',
  sidebarTitle: '👶 母婴运营台',
  subtitle: '一键自动生成小红书母婴笔记',
  monetizationSubtitle: '母婴账号系统化变现策略',
  categoryLabel: '母婴分类',
  categories: ['育儿经验','辅食食谱','孕期记录','产后恢复','童装推荐','绘本推荐','亲子活动','早教启蒙'],
  categoryColors: { /* 每个分类对应颜色 */ },
  categoryEmojis: { /* 每个分类对应 emoji */ },
  defaultCategory: '育儿经验',
  imageStyles: { /* 5种图片风格 */ },
  imageStylePrompts: { /* 5种风格的 AI 提示词 */ },
  branding: { /* 品牌化全套配置 */ },
  aiRole: '资深小红书母婴类博主',
  aiNiche: '母婴类',
  searchKeywords: (cat) => [/* 搜索关键词数组 */],
  postingTimeTips: { /* 每分类发布建议 */ },
  postingTimeBonus: { /* 每分类时段加权 */ },
  monetization: {
    strategies: [/* 7种变现策略 */],
    roadmap: [/* 4阶段成长路线 */],
  },
  contentEngine: null,
},
```

### 步骤 2：在侧边栏切换器中添加选项

找到 `<select id="skill-switcher">`，添加：

```html
<option value="母婴">👶 母婴账号</option>
```

### 步骤 3：（可选）添加 ContentEngine 模板

如果需要离线内容生成能力，在 `ContentEngine` 对象的 `hooks`、`bodyTemplates`、`titleTemplates`、`tagSets`、`coverTexts` 中为每个新分类添加模板数据。

---

## 六、数据持久化

| 数据项 | 存储方式 | key |
|--------|----------|-----|
| 当前 Skill | `localStorage` | `xhs_current_skill` |
| 笔记/收入/统计 | `localStorage` via `LocalDB` | `xhs_*` |
| 封面/内容图片 | `IndexedDB` | `xhs_images_db` |
| 品牌化包 | `localStorage` | `xhs_branding_pack` |

> **注意：** 切换 Skill 不会清除已有的笔记数据。不同 Skill 的笔记共享同一个数据库，通过 `category` 字段区分。

---

## 七、文件结构

```
xhsqg/
├── index.html          ← 主应用（包含全部 Skill 系统代码）
├── public/
│   └── index.html      ← index.html 的同步副本（GitHub Pages 部署用）
├── server.py           ← 本地开发服务器（可选）
├── SKILL.md            ← 本文档
└── README.md           ← 项目说明
```

---

## 八、架构图

```
┌─────────────────────────────────────────────────┐
│                    index.html                    │
│                                                  │
│  ┌──────────────┐    ┌────────────────────────┐ │
│  │  Sidebar UI  │    │    SKILL_TEMPLATES      │ │
│  │              │    │                          │ │
│  │ [Skill开关]──┼───▶│ 情感 │ 美食 │ 旅行 │...│ │
│  │              │    │                          │ │
│  └──────────────┘    └──────────┬─────────────┘ │
│                                  │               │
│                          getCurrentSkill()       │
│                           / _s()                 │
│                                  │               │
│         ┌────────────────────────┼──────────┐    │
│         ▼                        ▼          ▼    │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────┐ │
│  │ Dynamic     │  │ AI Prompts   │  │ UI      │ │
│  │ Constants   │  │              │  │ Apply   │ │
│  │             │  │ _search...() │  │         │ │
│  │ TIME_GUIDE  │  │ _analyze()   │  │ title   │ │
│  │ MONETIZE    │  │ _generate()  │  │ selects │ │
│  │ IMG_STYLES  │  │ branding()   │  │ chips   │ │
│  │             │  │ coverImg()   │  │ labels  │ │
│  └─────────────┘  └──────────────┘  └─────────┘ │
│                                                  │
└─────────────────────────────────────────────────┘
```
