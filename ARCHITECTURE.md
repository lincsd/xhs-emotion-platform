# 小红书 AI 平台 — 系统架构文档

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户浏览器                                │
│                  (手机/电脑/微信内嵌)                             │
└──────────────────────┬──────────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌──────────────────┐     ┌─────────────────────────┐
│   GitHub Pages   │     │   API 请求 (智能路由)     │
│   静态前端托管    │     │                          │
│                  │     │  ┌─────────────────────┐ │
│  index.html      │     │  │ 路径1: CF Tunnel    │ │
│  style.css       │     │  │ (优先，本地快速)     │ │
│                  │     │  └──────────┬──────────┘ │
│  lincsd.github   │     │            │             │
│  .io/xhs-emotion │     │  ┌─────────▼──────────┐ │
│  -platform/      │     │  │ 路径2: Render 云端  │ │
│                  │     │  │ (备用，自动降级)     │ │
└──────────────────┘     │  └─────────────────────┘ │
                         └─────────────────────────┘
```

## 二、两条后端路径

### 路径 1：Cloudflare Tunnel（优先）

```
用户浏览器
  → https://xhs.xiaohsai.com/api/xxx
  → Cloudflare CDN (全球边缘节点)
  → Cloudflare Tunnel 加密隧道
  → 你的本地电脑 localhost:3000 (server.py)
  → 本地梯子代理 127.0.0.1:10808
  → Google Gemini API (generativelanguage.googleapis.com)
  → 原路返回
```

| 项目 | 值 |
|---|---|
| 地址 | `https://xhs.xiaohsai.com` |
| 类型 | Cloudflare Named Tunnel (固定域名) |
| Tunnel 名称 | `xhs-local` |
| Tunnel ID | `0131346c-d3ec-4746-abb5-193c4fe7098f` |
| 本地端口 | 3000 |
| 需要 | 本地电脑开机 + 运行 `start_tunnel.ps1` + 梯子开启 |
| 速度 | 快（内容生成 ~46s，图片 ~18s/张） |

### 路径 2：Render 云端（备用）

```
用户浏览器
  → https://xhs-gemini-proxy.onrender.com/api/xxx
  → Render 美国服务器 (server.py)
  → 直连 Google Gemini API
  → 原路返回
```

| 项目 | 值 |
|---|---|
| 地址 | `https://xhs-gemini-proxy.onrender.com` |
| 类型 | Render Web Service (免费版) |
| 需要 | 无，24/7 自动运行 |
| 缺点 | 冷启动延迟 30-60s，网络稍慢 |
| 速度 | 较慢（内容生成 ~48s，图片 ~22s/张） |

## 三、智能后端选择机制

### 3.1 启动时自动检测

```javascript
// 页面加载时自动执行
async function _selectBestBackend() {
    // 1. 尝试 CF Tunnel（5s超时）
    fetch('https://xhs.xiaohsai.com/api/version', { timeout: 5000 })
    // 成功 → 使用 Tunnel     → UI显示 🚀Tunnel
    // 失败 → 回退 Render     → UI显示 ☁️Render
}
```

### 3.2 运行时自动切换

```
用户正常使用中
  → API 调用失败 → 失败计数+1
  → 连续失败 2 次 → 触发 _tryBackendFailover()
  → 重新检测后端 → 切换到可用的那个
  → 用新后端自动重试请求
```

### 3.3 UI 指示器

页面右下角始终显示当前后端状态：
- 🚀 **Tunnel** (绿色) — 走本地快速通道
- ☁️ **Render** (紫色) — 走云端备用
- ⏳ **检测中** (灰色) — 正在切换

点击指示器可手动触发重新检测。

## 四、用户请求完整流程

### 场景：用户点击「生成内容」

```
① 用户在浏览器点击「生成」按钮
   ↓
② 前端 JS 构建请求
   POST /api/generate
   Body: { prompt: "...", model: "gemini-2.0-flash" }
   ↓
③ 前端检查 _activeBackend 决定发送到哪
   → 如果 Tunnel 在线: https://xhs.xiaohsai.com/api/generate
   → 如果 Tunnel 离线: https://xhs-gemini-proxy.onrender.com/api/generate
   ↓
④ [Tunnel路径] 请求到达你的电脑
   Cloudflare CDN → CF Tunnel → localhost:3000
   ↓
⑤ server.py 接收请求
   - 验证用户登录态 (Cookie/Token)
   - 检查 AI 积分余额
   - 扣减积分
   ↓
⑥ server.py 转发到 Gemini API
   → 通过本地梯子 127.0.0.1:10808
   → POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent
   → 携带 API Key: AIzaSyAtoy...
   ↓
⑦ Gemini 返回生成结果
   ↓
⑧ server.py 将结果返回给前端
   → 经 Tunnel 原路返回浏览器
   ↓
⑨ 前端渲染结果到页面
```

### 场景：用户生成图片

```
① 前端发送图片生成请求
   POST /api/generate-image
   ↓
② server.py 调用 Gemini imagen 模型
   → Gemini 生成图片 → 返回 base64 数据
   ↓
③ server.py 返回图片数据给前端
   ↓
④ 前端展示图片，用户可下载
```

### 场景：Tunnel 挂了，自动降级

```
① 用户点击「生成」
   → 发送到 https://xhs.xiaohsai.com/api/generate
   → 超时/失败
   ↓
② 失败计数 +1（第2次连续失败）
   ↓
③ 触发 _tryBackendFailover()
   → 重新检测: xhs.xiaohsai.com 不通
   → 切换到: xhs-gemini-proxy.onrender.com
   → UI 变为 ☁️Render
   ↓
④ 用新后端自动重试原请求
   → 发送到 https://xhs-gemini-proxy.onrender.com/api/generate
   → 成功返回结果
   ↓
⑤ 用户无感知，只是稍慢一些
```

## 五、关键文件清单

| 文件 | 作用 |
|---|---|
| `public/index.html` | 前端页面（~15800行，包含全部 JS/CSS/HTML） |
| `server.py` | 后端服务器（API 代理 + 用户系统 + 数据库） |
| `start_tunnel.ps1` | 一键启动脚本（server.py + CF Tunnel） |
| `api_key.txt` | Gemini API Key 配置 |
| `data.db` | SQLite 数据库（用户、积分、历史记录） |
| `~/.cloudflared/config.yml` | Tunnel 配置文件 |
| `~/.cloudflared/cert.pem` | Cloudflare 账号认证证书 |

## 六、部署与启动

### 前端部署（自动）
```
git push origin master
→ GitHub Pages 自动更新
→ https://lincsd.github.io/xhs-emotion-platform/ 生效
```

### 后端启动（手动）
```powershell
# 在本机运行，启动 server.py + Cloudflare Tunnel
powershell -ExecutionPolicy Bypass -File start_tunnel.ps1

# 脚本自动完成：
# 1. 检测 Python、cloudflared、梯子
# 2. 加载 API Key
# 3. 启动 server.py (localhost:3000)
# 4. 启动 Named Tunnel (xhs.xiaohsai.com)
# 5. 保持运行，Ctrl+C 停止
```

### 不启动本机时
- Render 云端自动兜底，网站照常可用
- 只是速度稍慢，有冷启动延迟

## 七、网络拓扑总结

```
                    ┌─────────────┐
                    │  Gemini API  │
                    │  (Google)    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │                         │
    ┌─────────▼─────────┐    ┌─────────▼─────────┐
    │  你的电脑 (本地)    │    │  Render (美国)     │
    │                    │    │                    │
    │  server.py :3000   │    │  server.py         │
    │  梯子 :10808       │    │  直连 Gemini       │
    │  cloudflared       │    │                    │
    └─────────┬──────────┘    └─────────┬──────────┘
              │                         │
    ┌─────────▼──────────┐              │
    │  Cloudflare CDN    │              │
    │  xhs.xiaohsai.com  │              │
    └─────────┬──────────┘              │
              │                         │
              └────────────┬────────────┘
                           │
                  ┌────────▼────────┐
                  │  GitHub Pages    │
                  │  (前端静态页面)   │
                  │  index.html      │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │   用户浏览器     │
                  └─────────────────┘
```
