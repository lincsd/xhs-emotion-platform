# 项目优化模式与关键逻辑上下文

> 本文件记录了项目中经过验证的优化逻辑、设计模式和Bug修复策略，供后续开发时作为上下文参考。
> 最后更新: BUILD 20260324e

---

## 📂 项目基本信息

| 项          | 值                                                   |
| ----------- | ---------------------------------------------------- |
| 仓库        | `git@github.com:lincsd/xhs-emotion-platform.git`    |
| 分支        | `master`                                             |
| 部署        | Render (`xhs-gemini-proxy.onrender.com`) + GitHub Pages |
| Tunnel      | `https://xhs.xiaohsai.com` (cloudflared)            |
| Python      | `C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe` |
| 前端文件    | `public/index.html` (21000+ 行 SPA)                 |
| 后端文件    | `server.py` (3600+ 行)                              |
| **关键规则** | **`index.html` 和 `public/index.html` 必须保持同步** |

---

## 🏗️ 前端模块架构

所有模块为 IIFE (立即执行函数表达式)，通过全局变量通信：

```
KnowledgeCards  (知识卡片, ~line 9034)
    ↓ _goToPromptLib(fullId)        ← 全局异步跳转函数
PromptLib       (Prompt工程库, ~line 9698)
    ↓ PromptLib._goNote(fullId)     ← 跳到笔记工坊
NoteWorkshop    (笔记工坊, ~line 10650)
```

### 跨模块通信机制: `_pipelineState`

```javascript
var _pipelineState = {
  card: null,          // 当前卡片对象
  cardFullId: null,    // full_id 字符串
  subject: null,       // '数学'|'语文'|'英语'
  gradeShort: null,    // '三下' 等
  promptRecord: null,  // R1→R2→R3 五角色记录
  fromModule: null     // 来源模块
};
```

**规则 1**: 跳转函数 `_goToNoteWorkshop()` 和 `_goToPromptLib()` 都要先关闭所有弹层：
```javascript
document.querySelectorAll('[id$="-overlay"]').forEach(el => el.style.display = 'none');
```

---

## ✅ 已验证的优化模式

### 模式 1: 异步跳转 + await init（替代 setTimeout）

**问题**: 模块间跳转用 `setTimeout(300)` 等待数据加载，时间不够则 showDetail 找不到卡片。

**正确写法**:
```javascript
async function _goToPromptLib(fullId) {
  document.querySelectorAll('[id$="-overlay"]').forEach(el => el.style.display = 'none');
  switchPage('prompt-lib');
  await PromptLib.init();           // 等数据加载完成
  PromptLib.showDetail(fullId);     // 确保有数据后再打开详情
}
```

**关键**: 不要用 `setTimeout` 猜时间，用 `await` 等真正的异步操作完成。

---

### 模式 2: 共享 Promise 防并发（替代 boolean guard）

**问题**: 用 `if (loaded) return;` 做加载保护，当多处并发调用时第二个调用直接返回但数据还没就绪。

**正确写法**:
```javascript
let _loadPromise = null;

async function _loadAllCards() {
  if (_loadPromise) return _loadPromise;   // 已有加载中/完成的 Promise，复用
  _loadPromise = (async () => {
    const base = _getBasePath();
    const manifestResp = await fetch(encodeURI(base + 'manifest.json'));
    // ... 加载逻辑 ...
  })();
  return _loadPromise;
}
```

**关键**: 第二个调用者会拿到同一个 Promise 并 await 它完成，而不是直接跳过。

---

### 模式 3: 增量合并数据（替代 "空则加载" 一次性逻辑）

**问题**: `PromptLib.init()` 中 `if (allCards.length === 0)` 只加载一次。用户先浏览数学 → `allCards` 有数学 → 切英语 → 点查看Prompt → `allCards` 不为空不再加载 → 英语卡片找不到。

**正确写法**:
```javascript
async function init() {
  // 每次都从 KnowledgeCards 合并最新数据（防止切换学科后缓存不全）
  try {
    const packs = KnowledgeCards._getPacks();
    if (packs.length > 0) {
      const existingIds = new Set(allCards.map(c => c.full_id));
      for (const pack of packs) for (const u of pack.units) {
        for (const c of (u.cards || [])) {
          if (!existingIds.has(c.full_id)) {
            allCards.push({ ...c, unit_name: u.unit_name, unit_id: u.unit_id,
              _subject: pack.subject || '', _grade: pack.grade_short || '' });
            existingIds.add(c.full_id);
          }
        }
      }
    }
  } catch(e) {}
  if (allCards.length === 0) {
    await _loadAllCards();
  }
  switchTab('overview');
}
```

**关键**: 用 `Set` 去重，每次调用都合并当前 KnowledgeCards 已加载的数据。

---

### 模式 4: showDetail 兜底查找

**问题**: 即使 init 做了增量合并，某些极端路径下 allCards 仍可能缺卡片。

**正确写法**:
```javascript
function showDetail(fullId) {
  let card = allCards.find(c => c.full_id === fullId);
  // 若缓存中找不到，从 KnowledgeCards 当前加载的数据中查找
  if (!card) {
    try {
      const packs = KnowledgeCards._getPacks();
      for (const pack of packs) {
        for (const u of (pack.units || [])) {
          const found = (u.cards || []).find(c => c.full_id === fullId);
          if (found) {
            card = { ...found, unit_name: u.unit_name, unit_id: u.unit_id,
              _subject: pack.subject || '', _grade: pack.grade_short || '' };
            allCards.push(card);    // 缓存起来下次直接用
            break;
          }
        }
        if (card) break;
      }
    } catch(e) {}
  }
  if (!card) return;
  // ... 渲染逻辑 ...
}
```

**关键**: 先查缓存，miss 则实时从源数据搜索并回写缓存。典型的 read-through cache 模式。

---

### 模式 5: 智能检测学科/年级（替代盲信管线参数）

**问题**: `_applyPipelineContext()` 直接用 `_pipelineState.subject`，但管线传入的值可能是默认值（如用户从数学切英语但 state 仍是"数学"）。

**正确写法**: 多级检测，从可信度高到低：

```javascript
function _detectSubjectFromCard(card, fallback) {
  // 1. 卡片自带 _subject 字段
  if (card._subject && ['数学','语文','英语'].includes(card._subject)) return card._subject;
  // 2. 从 full_id 解析 (如 "语文-五下-T3-01")
  const fid = card.full_id || '';
  if (/语文/.test(fid)) return '语文';
  if (/英语/.test(fid)) return '英语';
  if (/数学/.test(fid)) return '数学';
  // 3. 从 type 推断 (如 "古诗卡" → 语文, "词汇卡" → 英语)
  const type = card.type || '';
  if (/古诗|默写|拼音|笔顺|阅读|写作|易错字|作文/.test(type)) return '语文';
  if (/发音|词汇|语法|句型|英语|对话/.test(type)) return '英语';
  // 4. 最终 fallback
  return fallback || '数学';
}

function _detectGradeFromCard(card, fallback) {
  if (card._grade) return card._grade;
  const fid = card.full_id || '';
  const m = fid.match(/(一|二|三|四|五|六|[1-6])([上下])/);
  if (m) {
    const gradeMap = {'1':'一','2':'二','3':'三','4':'四','5':'五','6':'六'};
    return (gradeMap[m[1]] || m[1]) + m[2];
  }
  return fallback || '三下';
}
```

**关键**: 多层 fallback，永远优先信任卡片自身数据而非外部传入参数。

---

### 模式 6: infoOnly 参数控制行为

**问题**: `_autoMatchFromCards()` 分析卡片后自动设置模板下拉，但管线模式下已根据卡片类型精确选了模板，不应被覆盖。

**正确写法**:
```javascript
async function _autoMatchFromCards(infoOnly) {
  // ... 分析逻辑 ...
  _applyMatchResult(result, info, infoOnly ? null : tmplSel);
}

function _applyMatchResult(result, info, tmplSel) {
  // 只有 tmplSel 非 null 时才修改下拉选择
  if (tmplSel) tmplSel.value = bestTmpl;
  // info 面板始终显示（分布信息）
  if (info) info.innerHTML = '...';
}
```

**关键**: 管线模式传 `infoOnly=true` → 只显示分布面板不改模板；下拉 onchange 不传 → 完整匹配。

---

### 模式 7: CARD_TYPE_MAP 共享映射表

26种卡片类型 → 4种模板，单一数据源避免不一致：

```javascript
const CARD_TYPE_MAP = {
  '概念卡': '干货型', '公式卡': '干货型', '方法卡': '干货型',
  '易错卡': '反差型', '易错题': '反差型', '对比卡': '反差型',
  '挑战卡': '挑战型', '思维卡': '挑战型', '进阶题': '挑战型',
  '趣味卡': '故事型', '故事卡': '故事型', '古诗卡': '故事型',
  '词汇卡': '干货型', '句型卡': '干货型', '语法卡': '干货型',
  // ... 共26种
};
```

**关键**: 在 NoteWorkshop 模块顶部定义，`_applyPipelineContext` 和 `_autoMatchFromCards` 共用同一张表。

---

## 🔧 服务器关键事项

### 启动命令（必须用 Python 3.13，不能用 conda 环境的 python）
```powershell
$env:GEMINI_API_KEY = (Get-Content api_key.txt -Raw).Trim().Replace('GEMINI_API_KEY=','')
& "C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe" server.py
```

### API Key 格式
`api_key.txt` 内容: `GEMINI_API_KEY=key1,key2,key3`（逗号分隔多 key）

### 验证服务器状态
```powershell
(Invoke-WebRequest -Uri "http://localhost:3000/api/version" -UseBasicParsing).Content
# 应返回: {"version": "xxx", "keyCount": 3, "hasServerKey": true}
```

---

## 📦 发布 Checklist

1. 修改 `public/index.html` 中的代码
2. 更新 BUILD 版本号（两处）:
   - `var BUILD='20260324e';` (line ~13)
   - `const PAGE_BUILD = '20260324e';` (line ~3823)
3. 同步到根目录: `copy public\index.html index.html`
4. 提交推送:
   ```powershell
   git add -A
   git commit -m "feat/fix: 描述 (BUILD 2026xxxx)"
   git push
   ```
5. Render 自动部署 (master push 触发)
6. GitHub Pages 自动更新
7. 本地服务器需手动重启

---

## 🐛 已修复的典型 Bug 记录

| BUILD    | Bug                                   | Root Cause                                     | Fix                                     |
| -------- | ------------------------------------- | ---------------------------------------------- | --------------------------------------- |
| 20260324c | NoteWorkshop 手动选学科/年级无反应     | 缺少 onchange 事件绑定                          | 添加 `_autoMatchFromCards()` onchange   |
| 20260324d | 语文卡片显示为"数学+干货型"            | `_applyPipelineContext` 盲信管线默认值           | 添加 `_detectSubjectFromCard()` 多级检测 |
| 20260324d | 管线模式下自动匹配覆盖已选模板         | `_autoMatchFromCards()` 总是设 tmplSel          | 添加 `infoOnly` 参数，管线模式传 true    |
| 20260324e | 英语卡片点"查看Prompt"无内容           | `init()` 只在空时加载，切学科后缓存不全          | 增量合并 + showDetail 兜底查找           |
| 20260324e | `_goToPromptLib` 偶尔白屏             | `setTimeout(300)` 竞态                          | 改为 `await PromptLib.init()`           |
| 20260324e | `_loadAllCards` 并发调用数据不全       | boolean flag 保护，第二调用直接跳过              | 改为共享 Promise (`_loadPromise`)        |

---

## 📊 卡片数据结构

### JSON 卡片包格式 (`public/knowledge_cards/小学/*.json`)
```json
{
  "subject": "英语",
  "grade": "三年级",
  "semester": "下册",
  "grade_short": "三下",
  "units": [{
    "unit_id": "01",
    "unit_name": "My schoolbag",
    "cards": [{
      "card_id": "01-01",
      "full_id": "英语-三下-01-01",
      "title": "词汇：学校用品",
      "type": "词汇卡",
      "difficulty": 2,
      "definition": "...",
      "core_points": ["..."],
      "example": { "question": "...", "steps": ["..."], "answer": "..." },
      "mistakes": [{ "wrong": "...", "correct": "..." }],
      "memory_tip": "..."
    }]
  }]
}
```

### full_id 命名规则
- 格式: `{学科}-{年级短码}-{单元}-{卡片序号}`
- 示例: `数学-三下-02-03`, `英语-三下-01-01`, `语文-五下-T3-01`

### manifest.json 结构
```json
{
  "stages": {
    "小学": [
      { "file": "数学_三下.json", "subject": "数学", "grade_short": "三下", "is_boom": false },
      { "file": "数学_三下_爆款.json", "subject": "数学", "grade_short": "三下", "is_boom": true },
      { "file": "英语_三下.json", "subject": "英语", ... }
    ]
  }
}
```

---

## 🔑 设计原则总结

1. **永远不用 setTimeout 做异步等待** → 用 await + Promise
2. **跨模块数据要增量合并** → 用 Set 去重，每次 init 都 merge 最新
3. **showDetail 必须有兜底查找** → 缓存 miss 则实时搜索源数据
4. **检测逻辑要多级 fallback** → 卡片字段 > full_id 解析 > type 推断 > 默认值
5. **共享映射表放在模块顶部** → 所有用到的地方引用同一份
6. **infoOnly 模式控制副作用** → 纯展示 vs 有副作用要分开控制
7. **共享 Promise 防并发** → 多处 await 同一个加载 Promise
8. **发布时两个 index.html 必须同步** → `copy public\index.html index.html`
