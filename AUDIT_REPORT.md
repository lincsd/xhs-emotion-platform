# 前端代码审计报告

**目标文件**: `public/index.html` (~13,850 行)  
**后端参考**: `server.py` (~2,491 行)  
**审计日期**: 2025-07  
**类型**: 只读分析（不修改任何文件）

---

## 目录

1. [JavaScript Bugs](#1-javascript-bugs)
2. [Security Vulnerabilities](#2-security-vulnerabilities)
3. [Performance Issues](#3-performance-issues)
4. [Dead / Unreachable Code](#4-dead--unreachable-code)
5. [UX / Accessibility](#5-ux--accessibility)
6. [CSS Issues](#6-css-issues)
7. [Architecture / Maintainability](#7-architecture--maintainability)
8. [Data Consistency (Frontend ↔ Backend)](#8-data-consistency-frontend--backend)

每项使用严重级别: **CRITICAL** / **HIGH** / **MEDIUM** / **LOW** / **INFO**

---

## 1. JavaScript Bugs

### 1.1 `showToast()` 未定义 — TemplateLibrary 全面受损
| 项 | 值 |
|---|---|
| **严重级别** | **CRITICAL** |
| **行号** | 7360, 7375, 7666, 7716, 7758, 7824, 7835, 7836, 7854, 7880, 7908, 7942, 7983, 8010, 8023, 8026, 8043, 8052, 8089, 8099, 8107, 8116, 8131 |
| **描述** | `TemplateLibrary` 对象内所有用户反馈均调用 `showToast()`，但全局实际定义的函数名为 `toast()`（约第 8690 行）。任何涉及模板保存、删除、导入、导出、AI 生成、分享的操作都会抛 `ReferenceError: showToast is not defined` 并中断。共 23 处调用。 |
| **建议修复** | 在全局作用域添加 `const showToast = toast;`，或批量替换为 `toast()`。 |

### 1.2 `setCropRatio()` 使用隐式 `event` 全局变量
| 项 | 值 |
|---|---|
| **严重级别** | **HIGH** |
| **行号** | ~12590 |
| **描述** | `setCropRatio(w, h)` 内部使用 `event.target.classList.add('active')` 但未声明 `event` 参数。在严格模式或 Firefox 中 `event` 为 `undefined`，引发 TypeError。 |
| **建议修复** | 将函数签名改为 `setCropRatio(w, h, event)` 并在 HTML `onclick` 传入 `event`，或改用 `addEventListener`。 |

### 1.3 `_key_lock` 竞态条件 — `_getNextServerKey` 前端缺少同步
| 项 | 值 |
|---|---|
| **严重级别** | **MEDIUM** |
| **行号** | ~4208 (`_imageKeyIndex`) |
| **描述** | `getNextImageKey()` 使用全局 `_imageKeyIndex` 自增取模实现轮询，但在 `generateContentImagesForPost()` 中通过 `Promise.all` 并发调用，多个 Promise 在同一 tick 读取相同的 `_imageKeyIndex` 值，可能导致所有并行请求使用同一个 Key，无法真正均衡轮询。 |
| **建议修复** | 在分配时一次性预分配 Key，例如 `const keyList = images.map((_, i) => keys[i % keys.length])`。 |

### 1.4 `openABTestModal` 引用可能未定义的 `categories`
| 项 | 值 |
|---|---|
| **严重级别** | **MEDIUM** |
| **行号** | ~12903 |
| **描述** | `const cats = (typeof categories !== 'undefined' && categories.length) ? categories : [...]`。`categories` 是全局变量，在页面加载后才通过 `applySkillToUI()` 赋值。若在赋值前打开模态框，回退到硬编码列表而非当前 Skill 的分类。 |
| **建议修复** | 始终使用 `_s().categories` 获取当前技能的分类列表。 |

### 1.5 `downloadAllCards()` / `downloadAllAICards()` 使用 `setTimeout` 链式下载
| 项 | 值 |
|---|---|
| **严重级别** | **MEDIUM** |
| **行号** | ~6550–6560 |
| **描述** | 使用 `setTimeout(() => a.click(), i * 500)` 逐个触发下载。现代浏览器会阻止快速连续触发的 programmatic downloads（Chrome 会将其视为弹窗行为），导致只有第一张图片被下载。 |
| **建议修复** | 使用 JSZip 将所有图片打包为 ZIP 文件一次性下载，或使用用户交互触发的逐个下载队列。 |

### 1.6 `aiGenerateWeekPlan()` — 循环内 sequential await 静默忽略错误
| 项 | 值 |
|---|---|
| **严重级别** | **MEDIUM** |
| **行号** | ~12540 |
| **描述** | `for (const p of json.plans)` 循环内 `try { await api('/api/content-plans', ...); added++; } catch {}` 错误被完全吞掉，用户不知道哪些计划创建失败。 |
| **建议修复** | 收集失败项并在循环后统一提示 `toast('X 条失败')`。 |

### 1.7 `applyImageFilters()` — 锐化在大图上造成阻塞
| 项 | 值 |
|---|---|
| **严重级别** | **MEDIUM** |
| **行号** | ~12630–12660 |
| **描述** | 像素级锐化遍历 `imageData.data` (w×h×4 bytes)，在 4000×3000 分辨率图片上需处理 4800 万字节，阻塞主线程数秒且无进度提示。 |
| **建议修复** | 使用 `OffscreenCanvas` + Web Worker 进行像素操作，或限制处理分辨率。 |

### 1.8 `generateViralTitles()` — onclick 中的单引号转义不足
| 项 | 值 |
|---|---|
| **严重级别** | **HIGH** |
| **行号** | ~12183 |
| **描述** | `onclick="copyTitleItem(this, '${item.title.replace(/'/g, "\\\\'")}')"` — 仅转义单引号，AI 生成的标题若包含反斜杠 `\` 或换行 `\n` 等特殊字符，会导致 JS 语法错误或意外行为，是 XSS 注入向量。 |
| **建议修复** | 移除内联 onclick，改用 `data-*` 属性 + `addEventListener`，或对整个字符串做 JSON.stringify 转义。 |

### 1.9 `_extractJsonFromText()` — JSON 截断恢复逻辑可能产生畸形数据
| 项 | 值 |
|---|---|
| **严重级别** | **LOW** |
| **行号** | ~9170–9200 |
| **描述** | 当 AI 输出被截断时，函数尝试补全缺失的 `]}`，但补全逻辑可能产生结构正确但语义不完整的 JSON（如半截的文章内容），随后被当作有效数据处理和保存。 |
| **建议修复** | 在补全后标记 `truncated: true`，并在 UI 提示用户数据可能不完整。 |

---

## 2. Security Vulnerabilities

### 2.1 大范围 innerHTML XSS（AI 生成内容 + 用户输入均未转义）
| 项 | 值 |
|---|---|
| **严重级别** | **CRITICAL** |
| **行号** | 12034, 12036, 12087, 12183, 12314, 12360, 11604, 11647, 11939, 10691, 9683 … (50+ 处) |
| **描述** | 文件中大量使用 `.innerHTML = \`...\${variable}...\`` 模式直接插入 AI 返回的文本、用户输入的标题/内容、从 API 获取的数据。`_escapeHtml()` 函数存在（第 9289 行）但仅在 `viewAnalysisReport()`（约 5 处）和 `renderBrandingPackage()` 中使用。其余 50+ 处 innerHTML 赋值均未转义。关键受影响路径包括：(1) AI 生成的笔记标题/正文 → `renderGeneratedList`, `viewPost`, `loadPosts` 等列表渲染；(2) 改写/润色/标题生成结果 → 直接插入 DOM；(3) 关键词分析结果中用户提供的 `kw.word` 直接嵌入 onclick 字符串属性；(4) 竞品分析/A/B测试结果直接插入。 |
| **攻击场景** | 若 Gemini API 受中间人攻击或返回恶意内容（如 `<img onerror=alert(1)>`），该内容将直接执行。亦适用于存储型 XSS：攻击者提交含 `<script>` 标签的笔记标题，其他用户查看时触发。 |
| **建议修复** | (1) 为所有动态内容统一使用 `_escapeHtml()`；(2) 考虑使用 `textContent` 替代 `innerHTML`；(3) 设置 CSP header `Content-Security-Policy: default-src 'self'; script-src 'self'`。 |

### 2.2 模板分享链接可用于注入恶意模板数据
| 项 | 值 |
|---|---|
| **严重级别** | **HIGH** |
| **行号** | ~8120–8135 (`importFromShareLink`) |
| **描述** | `generateShareLink()` 将模板 JSON 经 `btoa()` 编码放入 URL `#tmpl_share=` 片段。`importFromShareLink()` 解码后直接 `JSON.parse` 并保存为自定义模板，无任何属性白名单检验或长度限制。恶意构造的分享链接可注入含 XSS payload 的模板名称（在渲染时通过 innerHTML 执行）或超大数据导致 localStorage 被撑满 (DoS)。 |
| **建议修复** | (1) 对导入的模板对象进行严格的 schema 验证 + 属性白名单；(2) 对模板名称/描述执行 HTML 转义；(3) 限制模板 JSON 大小（如 < 50KB）。 |

### 2.3 Auth Token 及 API Key 存储在 localStorage
| 项 | 值 |
|---|---|
| **严重级别** | **HIGH** |
| **行号** | 4192 (`getGeminiKey`), ~13240 (`getAuthToken`), ~13290–13300 (`doLogin/doRegister`) |
| **描述** | `xhs_auth_token` 和 `xhs_gemini_key` 以明文存储于 localStorage。任何能在同源执行 JavaScript 的 XSS 漏洞（如 2.1 所述）都可以窃取这些凭证。localStorage 没有 `httpOnly` / `secure` 属性保护。 |
| **建议修复** | (1) Auth token 改用 `httpOnly` + `secure` + `SameSite=Strict` 的 cookie；(2) API Key 改为仅存于服务器端，前端通过 session proxy 调用。 |

### 2.4 管理密钥以 query parameter 明文传输
| 项 | 值 |
|---|---|
| **严重级别** | **HIGH** |
| **行号** | ~13550 (`loadAdminOrders`) |
| **描述** | `let url = API_BASE + '/api/admin/orders?adminKey=' + encodeURIComponent(key)` — 管理密钥在 URL query string 中传输，会被浏览器历史记录、服务器 access log、Referer header、任何中间代理记录。 |
| **建议修复** | 将 adminKey 放入请求 header（如 `X-Admin-Key`）或 POST body 中。 |

### 2.5 关键词分析 onclick 注入
| 项 | 值 |
|---|---|
| **严重级别** | **HIGH** |
| **行号** | ~12300–12310 |
| **描述** | `onclick="navigator.clipboard.writeText('${kw.word}').then(()=>toast('已复制: ${kw.word}','success'))"` — `kw.word` 来自 AI API 响应，直接嵌入 onclick 属性字符串中，未经任何转义。若 `kw.word` 包含单引号，则可突破字符串边界执行任意 JS。 |
| **建议修复** | 移除内联 onclick，使用 `data-word` 属性 + 事件代理。 |

### 2.6 `doLogin`/`doRegister` — 无 CSRF 保护
| 项 | 值 |
|---|---|
| **严重级别** | **MEDIUM** |
| **行号** | ~13310–13380 |
| **描述** | 登录/注册使用 `fetch(API_BASE + '/api/auth/login', ...)` 的 JSON POST 请求，但无 CSRF token。虽然 `Content-Type: application/json` 提供了部分保护（简单请求无法设置该 header），但若 CORS 配置宽松（服务端接受 `*`），则仍有风险。 |
| **建议修复** | 在服务端添加 CSRF token 验证，或确保 CORS 只允许特定 origin。 |

### 2.7 `_SSL_CTX.verify_mode = ssl.CERT_NONE` (后端)
| 项 | 值 |
|---|---|
| **严重级别** | **MEDIUM** |
| **行号** | server.py:128-129 |
| **描述** | 后端 Python 服务完全禁用 SSL 证书验证，使得：(1) 代理到 Gemini API 的请求容易遭 MITM 攻击；(2) 百度搜索等功能的请求同样不安全。 |
| **建议修复** | 在生产环境启用证书验证 (`ssl.CERT_REQUIRED`)，仅在开发环境可选禁用。 |

---

## 3. Performance Issues

### 3.1 模板缩略图创建 50+ 全尺寸 Canvas
| 项 | 值 |
|---|---|
| **严重级别** | **HIGH** |
| **行号** | ~7200–7260 (`_renderMiniPreview`) |
| **描述** | `_renderMiniPreview()` 为每个模板创建 1080×1440 像素的临时 Canvas（约 6MB 位图内存），渲染后用 `toDataURL()` 转出缩略图，再设置到 `<img>` 标签。模板库共约 50 个模板 = **~300MB** GPU/位图内存峰值使用。Canvas 创建完后虽然会被 GC，但 GC 时机不确定，移动端极易触发 OOM。 |
| **建议修复** | (1) 降低渲染画布分辨率为目标缩略图尺寸 (~300×400)；(2) 使用虚拟滚动，仅渲染可视区域的缩略图；(3) 缓存已生成的缩略图 dataURL 到 localStorage/IndexedDB。 |

### 3.2 模板编辑器预览无防抖
| 项 | 值 |
|---|---|
| **严重级别** | **MEDIUM** |
| **行号** | ~7550–7600 (`_editorPreview`) |
| **描述** | 颜色选择器/输入框的 `oninput` 事件直接调用 `_editorPreview()` 触发完整的 Canvas 重绘，无任何防抖。用户拖动颜色滑条时每帧都会触发，造成卡顿。 |
| **建议修复** | 添加 `requestAnimationFrame` 或 150ms `debounce` 保护。 |

### 3.3 批量操作使用 sequential await
| 项 | 值 |
|---|---|
| **严重级别** | **MEDIUM** |
| **行号** | ~10800 (`batchDelete`), ~10750 (`batchPublish`), ~10900 (`batchExport`), ~12540 (`aiGenerateWeekPlan`) |
| **描述** | `for (const id of selectedPosts) { await api(\`/api/posts/\${id}\`, {method:'DELETE'}); }` — 对每个笔记逐个发送 DELETE 请求，N 篇笔记需 N 次 RTT。50 篇笔记在 200ms 延迟下需 10 秒。 |
| **建议修复** | (1) 后端新增批量操作端点 `POST /api/posts/batch-delete`；(2) 或使用 `Promise.all` 并行（但需控制并发量）。 |

### 3.4 `updateQualityLabel()` 每次调用 `canvas.toBlob()` 估算大小
| 项 | 值 |
|---|---|
| **严重级别** | **LOW** |
| **行号** | ~12700 |
| **描述** | 图片质量滑条 `oninput` 触发 `applyImageFilters()` → `updateQualityLabel()` → `canvas.toBlob()`，toBlob 是异步但代价高（JPEG 编码），拖动滑条时每帧触发一次。 |
| **建议修复** | 对 `updateQualityLabel` 添加 500ms+ 防抖。 |

### 3.5 `loadImageFile` 对大图不进行预缩放
| 项 | 值 |
|---|---|
| **严重级别** | **LOW** |
| **行号** | ~12570 |
| **描述** | 用户上传 20MP 相机照片时，`_imgOriginal` 保存原始 Image 对象，所有后续 Canvas 操作（裁剪、滤镜、锐化、水印）均在全分辨率下进行，移动端可能 OOM。 |
| **建议修复** | 上传后限制最大边为 2048px 或 4096px。 |

---

## 4. Dead / Unreachable Code

### 4.1 `initForbiddenPage()` 为空函数
| 项 | 值 |
|---|---|
| **严重级别** | **LOW** |
| **行号** | ~11500 |
| **描述** | `function initForbiddenPage() {}` — 空函数体，但在 `switchPage` 中被调用。功能初始化逻辑可能遗漏。 |

### 4.2 `showDayPlans()` 仅 toast 提示
| 项 | 值 |
|---|---|
| **严重级别** | **LOW** |
| **行号** | ~12440 |
| **描述** | `function showDayPlans(dateStr) { toast(\`查看 \${dateStr} 的计划\`, 'info'); }` — 应当滚动到列表对应日期或弹出详情，但实际只弹了个 toast，是未完成的 TODO。 |

### 4.3 `openImageUploadForAssign()` — 存储的图片无法在非生成场景下使用
| 项 | 值 |
|---|---|
| **严重级别** | **INFO** |
| **行号** | ~12820 |
| **描述** | 函数将图片分配到 `window._lastGeneratedPosts` 或 localStorage 的草稿列表，但若两者都为空则直接 toast 后返回，不提供创建新笔记的入口。 |

### 4.4 `MONETIZATION_DATA` Proxy 对象可能无法被序列化
| 项 | 值 |
|---|---|
| **严重级别** | **INFO** |
| **行号** | ~8630 |
| **描述** | `MONETIZATION_DATA = new Proxy({...})` 通过 getter 动态返回 `_s().monetization` 的值。若任何代码尝试 `JSON.stringify(MONETIZATION_DATA)` 会得到空对象 `{}`（Proxy traps 不含 `ownKeys`）。 |

---

## 5. UX / Accessibility

### 5.1 零 ARIA 标签
| 项 | 值 |
|---|---|
| **严重级别** | **HIGH** |
| **行号** | 全文 |
| **描述** | 整个 13,850 行文件中无 `role=`, `aria-label=`, `aria-describedby=`, `aria-expanded=` 等可访问性属性。侧边栏导航、模态框、可折叠区域、自定义 tabs、轮播均不可被屏幕阅读器识别。 |
| **建议修复** | (1) 为模态框添加 `role="dialog" aria-modal="true"` + `aria-labelledby`；(2) 导航链接添加 `role="navigation"` + `aria-current="page"`；(3) 自定义按钮添加 `role="button"` + `aria-label`。 |

### 5.2 无键盘导航支持
| 项 | 值 |
|---|---|
| **严重级别** | **HIGH** |
| **行号** | 全文 |
| **描述** | 关键交互大量使用 `<div onclick="...">` / `<span onclick="...">` 而非 `<button>` 或 `<a>`，无 `tabindex`、无 `onkeydown` 处理。模态框无焦点陷阱（focus trap），Escape 键不关闭模态框（仅部分模态框通过点击背景关闭）。 |
| **建议修复** | 将交互元素改为语义化 `<button>`，添加 focus trap 和 Escape 键监听。 |

### 5.3 满屏 inline style
| 项 | 值 |
|---|---|
| **严重级别** | **MEDIUM** |
| **行号** | 全文 JS 模板字符串 |
| **描述** | 动态生成的 HTML 中布满 `style="display:flex;gap:12px;padding:12px;..."` 等 inline style（粗略估计 1000+ 处），无法被用户自定义 CSS 覆写，也使深色模式适配极为困难。 |
| **建议修复** | 抽取为 CSS class，在 `<style>` 中统一定义。 |

### 5.4 模态框关闭方式不一致
| 项 | 值 |
|---|---|
| **严重级别** | **LOW** |
| **行号** | 多处 |
| **描述** | 有些模态框使用 `closeModal('modal-xxx')`，有些使用 `document.getElementById('modal-xxx').classList.remove('active')`，有些使用 `.style.display = 'none'`。至少三种关闭方式导致部分模态框无法通过通用逻辑统一关闭。`modal-payment` 使用 `display: flex/none` 而非 `active` class。 |
| **建议修复** | 统一使用 `openModal/closeModal` 函数并始终使用 CSS class 控制显隐。 |

---

## 6. CSS Issues

### 6.1 HTML 结构错误 — 多余 `</section>` 闭合标签
| 项 | 值 |
|---|---|
| **严重级别** | **MEDIUM** |
| **行号** | ~2189 |
| **描述** | 存在一个多余的 `</section>` 标签，导致后续所有 section 的 DOM 层级上移一层。虽然浏览器的错误恢复机制通常能处理，但可能导致 CSS 选择器（如 `.main-content > .page-section`）在特定 section 失效。 |
| **建议修复** | 删除多余的 `</section>` 标签。 |

### 6.2 `1080px` Canvas 硬编码在 CSS 和 JS 中不同步
| 项 | 值 |
|---|---|
| **严重级别** | **LOW** |
| **行号** | CSS ~1160, JS ~5050 |
| **描述** | CardEngine 的 canvas 尺寸 (1080×1440) 在 JS 中硬编码（`const W = 1080, H = 1440`），而 CSS 中的卡片预览通过 `max-width: 100%` 自适应，二者没有明确关联。若修改 JS 中的尺寸常量，CSS 不会自动适配。 |
| **建议修复** | 在 CSS 变量中定义 `--card-aspect-ratio` 并在 JS 中读取。 |

### 6.3 深色模式未实现
| 项 | 值 |
|---|---|
| **严重级别** | **INFO** |
| **行号** | 全文 CSS |
| **描述** | CSS 使用了 CSS 变量 (`--primary`, `--bg`, `--text` 等)，但没有 `@media (prefers-color-scheme: dark)` 规则，也没有手动切换深色模式的功能。加上大量 inline style 中的硬编码颜色 (`#f8f9ff`, `#fff3e0`, `white` 等)，实现深色模式工作量极大。 |

---

## 7. Architecture / Maintainability

### 7.1 13,850 行单文件 — 极度不可维护
| 项 | 值 |
|---|---|
| **严重级别** | **CRITICAL** |
| **行号** | 全文 |
| **描述** | 全部 HTML、CSS、JavaScript 在一个文件中，包含：~1500 行 CSS、~500 行 HTML、~12,000+ 行 JS。7 个主要对象/类 (`SKILL_TEMPLATES`, `CardEngine`, `TemplateLibrary`, `TemplateV2Engine`, `ContentEngine`, `LocalDB`, `POSTING_TIMES`) + 200+ 全局函数 + 20+ 全局变量。任何修改都需要搜索整个文件，冲突风险极高，无法进行模块化测试。 |
| **建议修复** | 拆分为模块化架构：`styles/` (CSS Modules)、`components/` (各页面组件)、`services/` (API/AI/Storage 层)、`utils/` (toast/escape/debounce)。采用构建工具 (Vite/esbuild) 进行打包。 |

### 7.2 全局命名空间污染
| 项 | 值 |
|---|---|
| **严重级别** | **HIGH** |
| **行号** | 全文 |
| **描述** | 200+ 函数和 20+ 变量直接定义在全局作用域（`window`），包括通用名如 `init`, `toast`, `categories`, `api`。极易与第三方脚本或浏览器扩展冲突。所有 HTML inline `onclick` 也须依赖全局函数。 |
| **建议修复** | 将函数归入命名空间对象或 ES Module。 |

### 7.3 重复实现模式
| 项 | 值 |
|---|---|
| **严重级别** | **MEDIUM** |
| **行号** | 多处 |
| **描述** | (1) **3 个 lightbox 实现**：`openCardLightbox` (~6540), `openAICardLightbox` (~6690), 图片 lightbox (~9683)，功能几乎一致但逻辑各自独立。(2) **2 个兑换码函数**：`redeemCode` (~13680) 和 `redeemFromQuotaModal` (~13700)，代码 90% 相同。(3) **2 个保存草稿函数**：`saveRewriteAsDraft` 和 `savePolishAsDraft`，代码结构完全一致。(4) **多处动态创建模态框**的代码模式完全相同但每次都手写。 |
| **建议修复** | 抽取通用 `openLightbox(src)`, `redeemCodeGeneric(inputId, resultId)`, `saveAsDraft(text)`, `createDynamicModal(id, html)` 等工具函数。 |

### 7.4 `localApi()` — 客户端完整重现后端路由
| 项 | 值 |
|---|---|
| **严重级别** | **MEDIUM** |
| **行号** | ~8720–8820 |
| **描述** | `localApi()` 用正则匹配路由并调用 `LocalDB` 方法，相当于在客户端重新实现了一遍后端 API。这意味着每次后端新增/修改 API，前端也须同步修改 `localApi()`，维护成本翻倍。且两者的业务逻辑可能出现偏差。 |
| **建议修复** | 如果需要离线支持，使用 Service Worker + Cache API 做离线缓存，移除 `localApi`。 |

### 7.5 无错误监控/日志收集
| 项 | 值 |
|---|---|
| **严重级别** | **LOW** |
| **行号** | 全文 |
| **描述** | 无 `window.onerror`、`window.onunhandledrejection` 全局错误处理器。无错误上报机制。生产环境的 JS 错误（如 2.1 的 `showToast` bug）完全静默对开发者不可见。 |
| **建议修复** | 添加全局错误处理器，至少 `console.error` + `toast` 通知用户，理想情况下上报到后端 `/api/client-errors`。 |

---

## 8. Data Consistency (Frontend ↔ Backend)

### 8.1 前后端 API 路由匹配完整性 — 总体一致 ✅

经对比 `server.py` 的 `do_GET/do_POST/do_PUT/do_DELETE` 路由表与前端 `api()` / `fetch()` 调用，**主路由全部吻合**：

| 前端调用 | 后端路由 | 状态 |
|---|---|---|
| `GET /api/stats` | `do_GET` → `_get_stats` | ✅ |
| `GET /api/posts` | `do_GET` → `_get_posts` | ✅ |
| `POST /api/posts` | `do_POST` → `_create_post` | ✅ |
| `PUT /api/posts/:id` | `do_PUT` → `_update_post` | ✅ |
| `DELETE /api/posts/:id` | `do_DELETE` → `_delete_post` | ✅ |
| `GET /api/calendar` | `do_GET` → `_get_calendar` | ✅ |
| `POST /api/income` | `do_POST` → `_create_income` | ✅ |
| `DELETE /api/income/:id` | `do_DELETE` → `_delete_income` | ✅ |
| `GET /api/content-plans` | `do_GET` → `_get_content_plans` | ✅ |
| `POST /api/content-plans` | `do_POST` → `_create_content_plan` | ✅ |
| `PUT /api/content-plans/:id` | `do_PUT` → `_update_content_plan` | ✅ |
| `DELETE /api/content-plans/:id` | `do_DELETE` → `_delete_content_plan` | ✅ |
| `POST /api/gemini-proxy` | `do_POST` → `_gemini_proxy` | ✅ |
| `POST /api/ai-proxy` | `do_POST` → `_gemini_proxy` | ✅ |
| `POST /api/orders/create` | `do_POST` → `_create_order` | ✅ |
| `POST /api/orders/notify-paid` | `do_POST` → `_notify_paid` | ✅ |
| `POST /api/orders/cancel` | `do_POST` → `_cancel_order` | ✅ |
| `POST /api/redeem` | `do_POST` → `_redeem_code` | ✅ |
| 其他 auth/invite/admin 路由 | | ✅ |

### 8.2 `localApi()` 路由覆盖不完整
| 项 | 值 |
|---|---|
| **严重级别** | **HIGH** |
| **行号** | ~8720–8820 |
| **描述** | `localApi()` 仅覆盖了基础的 posts/calendar/income/account-stats/generate/schedule/categories/stats/monetization-guide/export 等路由。以下后端路由在离线模式下**不可用且无 fallback**：`/api/content-plans` (CRUD)、`/api/user/credits`、`/api/packages`、`/api/orders/*`、`/api/invite/*`、`/api/admin/*`、`/api/auth/*`、`/api/payment-config`。在网络断开时调用这些 API 会导致 `api()` 函数抛错，用户看到 "网络错误" 提示，部分页面功能完全无法加载（积分商城、邀请页面、内容规划页面）。 |
| **建议修复** | (1) 在 `localApi()` 中为缺失路由返回合理的空数据 fallback（如空数组/默认值）；(2) 或在 UI 层判断离线状态并禁用相关功能入口。 |

### 8.3 前端 `canUseAI()` 与后端积分检查不同步
| 项 | 值 |
|---|---|
| **严重级别** | **MEDIUM** |
| **行号** | 前端 4236, 后端 1157 |
| **描述** | 前端 `canUseAI()` 仅检查 `getGeminiKey() || getGeminiProxyBase()`（即"是否配置了 AI 能力"）。后端 `_check_ai_quota()` 还检查免费额度和积分余额。前端没有在发起 AI 请求前预检查积分，导致用户在积分不足时仍能发起请求，直到后端返回 403 后才通过 `callGeminiAPI()` 的错误处理弹出配额超限提示。用户体验突兀。 |
| **建议修复** | 在 `loadCreditsInfo()` 拉取积分信息后，让 AI 功能的按钮根据 `userCreditsInfo` 判断是否显示"积分不足"状态，点击时先预检查再调用。 |

### 8.4 注册请求缺少 `smsCode` 字段
| 项 | 值 |
|---|---|
| **严重级别** | **MEDIUM** |
| **行号** | 前端 ~13350 (`doRegister`), 后端 ~1758 (`_auth_register`) |
| **描述** | 前端 `doRegister()` 的 `body` 字段为 `{ phone, username, password, nickname, inviteCode, captchaToken, captchaAnswer }`，未包含 `smsCode`。但后端 `_auth_register` 读取 `body.get('smsCode')` 用于验证手机验证码。若后端启用了 SMS 验证（非 captcha-only 模式），注册会失败。目前看起来后端可能在 captcha 通过后跳过了 SMS 检查（需确认），但这表明前后端对注册流程的理解不完全一致。 |
| **建议修复** | 确认注册流程是"手机号 + 图形验证码"还是"手机号 + 短信验证码 + 图形验证码"，然后统一前后端字段。 |

### 8.5 `loadPurchasePage` 与 `loadCreditsInfo` 重复拉取积分
| 项 | 值 |
|---|---|
| **严重级别** | **LOW** |
| **行号** | 前端 ~13430 (`loadPurchasePage`), ~13650 (`loadCreditsInfo`) |
| **描述** | `loadPurchasePage()` 直接 `fetch(API_BASE + '/api/user/credits', ...)` 拉取积分，而 `loadCreditsInfo()` 也通过 `api('/api/user/credits')` 做同样的事。前者不更新 `userCreditsInfo` 全局状态，后者更新。切换到购买页面后全局积分状态可能与页面显示不一致。 |
| **建议修复** | `loadPurchasePage()` 改为调用 `loadCreditsInfo()` 后读取 `userCreditsInfo` 对象。 |

---

## 高优先级修复清单（Top 10）

| # | 类别 | 发现项 | 严重级别 |
|---|---|---|---|
| 1 | Bug | `showToast` 未定义，TemplateLibrary 23处全部失效 | CRITICAL |
| 2 | Security | innerHTML XSS — 50+ 处 AI/用户内容未转义直插 DOM | CRITICAL |
| 3 | Architecture | 13,850 行单文件无模块化 | CRITICAL |
| 4 | Security | 模板分享链接注入 (base64 URL → 直接保存) | HIGH |
| 5 | Security | Auth token / API Key 明文存储 localStorage | HIGH |
| 6 | Security | 关键词分析 onclick 属性注入 | HIGH |
| 7 | Security | Admin key 在 URL query string 明文传输 | HIGH |
| 8 | Performance | 50 个 1080×1440 Canvas 缩略图 ~300MB 内存 | HIGH |
| 9 | Accessibility | 零 ARIA 标签 + 无键盘导航 | HIGH |
| 10 | Data | `localApi()` 路由覆盖不完整，离线模式多页面崩溃 | HIGH |

---

*报告结束 — 本次审计为只读分析，未修改任何文件。*
