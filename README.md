# 🌸 小红书情感账号 · 自动化运营管理平台

一套完整的小红书情感账号运营工具，支持内容自动生成、发布排期、变现追踪。

## ✨ 功能特色

- **一键生成** 8大情感分类笔记（治愈/成长/爱情/友情/自我/离别/温暖/释怀）
- **批量产出** 支持一次生成7天/14天/30天的内容
- **发布日历** 可视化排期管理
- **变现追踪** 记录收入来源和金额
- **账号数据** 跟踪粉丝/点赞/收藏增长
- **变现方案** 系统化变现策略指导
- **双模式运行** 本地服务器模式 + GitHub Pages 纯静态模式

## 🚀 快速开始

### 方式一：GitHub Pages 在线访问（无需安装）

直接访问部署后的 GitHub Pages 链接即可使用，数据保存在浏览器 localStorage 中。

### 方式二：本地服务器模式（推荐，支持数据持久化）

```bash
# 只需要 Python 3，无需任何第三方依赖
python server.py
# 访问 http://localhost:3000
```

## 🌍 无梯子可用方案（GitHub Pages + 云端 Gemini 代理）

如果本地浏览器无法直连 Google API，可将 `server.py` 部署到海外云（如 Render），让前端通过 HTTPS 代理调用 Gemini。

### 1) 一键部署代理（Render）

本仓库已内置 [render.yaml](render.yaml)，可直接使用 Blueprint 部署：

1. 打开 Render → New → Blueprint
2. 连接本仓库并创建服务（自动读取 `render.yaml`）
3. 部署完成后获得代理地址，例如：`https://xhs-gemini-proxy.onrender.com`

建议在 Render 服务中设置环境变量（更安全）：

- Key: `GEMINI_API_KEY`
- Value: 你的 Gemini API Key

设置后，前端可不再填写 API Key，仅填写代理地址即可调用。

### 2) 在前端配置代理地址

打开你的 GitHub Pages 页面后：

1. 进入「⚙️ API 设置」
2. `Gemini API Key` 可留空（若 Render 已配置 `GEMINI_API_KEY`）
3. 在「Gemini 代理地址（可选）」填写你的 Render HTTPS 域名
4. 点击「测试连接」和「保存设置」

完成后，前端会优先通过 `https://你的代理域名/api/gemini-proxy` 调用 Gemini，无需本地开梯子。

## 📁 项目结构

```
├── index.html         # 前端管理面板（GitHub Pages 入口，支持离线模式）
├── server.py          # Python 后端服务（纯标准库，无需pip安装）
├── public/
│   └── index.html     # 前端管理面板（本地服务器使用）
├── .gitignore
└── README.md
```

## 🌐 GitHub Pages 部署

1. Fork 或 Push 本仓库到你的 GitHub
2. 进入仓库 Settings → Pages
3. Source 选择 `main` 分支，目录选 `/ (root)`
4. 保存后等待部署，访问 `https://你的用户名.github.io/仓库名/`

> GitHub Pages 模式下数据存储在浏览器 localStorage 中，所有功能均可正常使用（内容生成、排期、收入记录等）。

> 注意：请勿将 API Key 提交到 Git 仓库；如有泄露请立即在 Google AI Studio 里删除并重建。

## 💰 变现路线

| 阶段 | 时间 | 粉丝 | 策略 |
|------|------|-------|------|
| 冷启动 | 1-2个月 | 0-1000 | 每天发2-3条，积累内容 |
| 成长期 | 2-4个月 | 1000-5000 | 入驻蒲公英，接广告 |
| 变现期 | 4-6个月 | 5000-2万 | 稳定广告+付费产品 |
| 规模化 | 6个月+ | 2万+ | 矩阵运营，品牌化 |

## 📝 License

MIT
