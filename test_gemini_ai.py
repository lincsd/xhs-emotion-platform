#!/usr/bin/env python3
"""
测试 Gemini AI 联网搜索分析 + 生成内容 完整流程
两步走：
  Step 1: 使用 Gemini + Google Search Grounding 搜索分析小红书爆款笔记
  Step 2: 基于分析结果调用 Gemini 生成高质量笔记内容
"""
import urllib.request
import urllib.error
import json
import ssl
import os
import sys
import time
import re

# ========== 配置 ==========
API_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_key.txt")
MODEL = "gemini-2.5-flash"
CATEGORY = "治愈"
GENERATE_COUNT = 3

# 读取 API Key
def load_api_key():
    with open(API_KEY_FILE, "r", encoding="utf-8") as f:
        text = f.read().strip()
    # 支持 GEMINI_API_KEY=xxx 或直接 xxx
    if "=" in text:
        text = text.split("=", 1)[1].strip()
    return text

# SSL context (忽略证书验证，方便测试)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def gemini_request(api_key, model, payload):
    """发送请求到 Gemini API"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=120)
        return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  [HTTP {e.code}] {body[:500]}")
        return {"error": json.loads(body) if body.startswith("{") else {"message": body}}

# ========== Step 1: 联网搜索+分析 ==========
def step1_search_and_analyze(api_key, model, category):
    print(f"\n{'='*60}")
    print(f"  Step 1: 联网搜索小红书「{category}」爆款笔记")
    print(f"{'='*60}")
    
    search_prompt = f"""请你搜索小红书平台上「{category}」分类的情感类热门笔记/爆款笔记。

请搜索以下关键词，获取真实的小红书热门内容数据：
- "小红书 {category} 情感文案 爆款"
- "小红书 {category} 语录 点赞高"
- "xiaohongshu {category} 情感 热门笔记"
- "小红书 情感赛道 {category} 流量"

搜索完成后，请基于搜索到的真实数据，输出详细的分析报告，格式如下：

## 搜索到的真实爆款笔记案例
列出你搜索找到的5-10个真实的小红书「{category}」情感类高赞笔记，包括：
- 笔记标题（原文）
- 大致点赞/收藏量级
- 内容特点摘要

## 标题规律总结
从真实案例中提炼标题特征、常用句式、字数范围、emoji使用模式

## 内容结构规律
从真实案例中总结正文的结构模式、开头hook手法、叙述节奏、金句位置

## 当前热门话题/趋势
当前小红书情感赛道「{category}」子分类的热点话题、流行关键词、用户讨论焦点

## 标签使用规律
热门笔记常用的标签组合，区分大标签和精准小标签

## 封面文字规律
爆款笔记的封面文字特征，字数、句式、情绪表达方式

## 流量密码总结
综合分析这些爆款笔记能获得高流量的核心原因（至少5点）"""

    payload = {
        "contents": [{"parts": [{"text": search_prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.9,
            "maxOutputTokens": 8192
        }
    }

    print("  -> 正在调用 Gemini API (带 Google Search Grounding)...")
    t0 = time.time()
    data = gemini_request(api_key, model, payload)
    elapsed = time.time() - t0
    print(f"  -> API 响应耗时: {elapsed:.1f}s")

    # 检查错误 -> 降级
    if "error" in data:
        err_msg = data.get("error", {}).get("message", str(data.get("error")))
        print(f"  [!] Google Search 不可用: {err_msg}")
        print("  -> 降级为不带搜索的知识库分析...")
        return step1_fallback_analyze(api_key, model, category)

    # 提取分析文本
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    analysis_text = ""
    for part in parts:
        if "text" in part:
            analysis_text += part["text"] + "\n"

    # 提取 grounding 来源
    grounding = data.get("candidates", [{}])[0].get("groundingMetadata", {})
    sources = []
    for chunk in grounding.get("groundingChunks", []):
        web = chunk.get("web", {})
        if web:
            sources.append({"title": web.get("title", ""), "uri": web.get("uri", "")})
    sources = sources[:10]

    search_used = True
    print(f"  [OK] 联网搜索完成!")
    print(f"  -> 搜索到 {len(sources)} 个相关来源")
    print(f"  -> 分析报告长度: {len(analysis_text)} 字符")
    
    if sources:
        print(f"\n  参考来源:")
        for i, s in enumerate(sources[:5], 1):
            title = s['title'][:50] if s['title'] else '(无标题)'
            print(f"    {i}. {title}")
            print(f"       {s['uri'][:80]}")

    # 打印分析摘要(前500字)
    print(f"\n  分析报告摘要:")
    print(f"  {'-'*50}")
    preview = analysis_text[:800].replace('\n', '\n  ')
    print(f"  {preview}")
    if len(analysis_text) > 800:
        print(f"  ... (共 {len(analysis_text)} 字符)")
    print(f"  {'-'*50}")

    return {"analysisText": analysis_text, "sources": sources, "searchUsed": search_used}


def step1_fallback_analyze(api_key, model, category):
    """降级方案：不带搜索的分析"""
    prompt = f"""你是一位拥有百万粉丝的资深小红书情感类博主，精通平台算法和爆款内容创作。

请基于你对小红书平台的深入了解，详细分析「{category}」分类情感类爆款笔记的规律：

## 典型爆款笔记案例
列出5-8个典型的「{category}」情感类高赞笔记标题示例及内容特点

## 标题规律
## 内容结构规律
## 热门话题方向
## 标签策略
## 封面文字规律
## 流量密码"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.8, "topP": 0.9, "maxOutputTokens": 4096}
    }

    t0 = time.time()
    data = gemini_request(api_key, model, payload)
    elapsed = time.time() - t0
    print(f"  -> 降级分析耗时: {elapsed:.1f}s")

    if "error" in data:
        raise Exception(f"Gemini API 错误: {data['error']}")

    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    print(f"  [OK] 知识库分析完成 ({len(text)} 字符)")
    return {"analysisText": text, "sources": [], "searchUsed": False}


# ========== Step 2: 基于分析生成内容 ==========
def step2_generate_from_analysis(api_key, model, category, count, analysis):
    print(f"\n{'='*60}")
    print(f"  Step 2: 基于分析结果生成 {count} 条笔记")
    print(f"{'='*60}")

    analysis_text = analysis["analysisText"]
    sources = analysis["sources"]
    search_used = analysis["searchUsed"]

    source_info = ""
    if sources:
        source_info = "\n\n## 参考来源\n" + "\n".join(
            f"{i+1}. {s['title']} ({s['uri']})" for i, s in enumerate(sources)
        )

    prompt = f"""你是一位拥有百万粉丝的资深小红书情感类博主。

## 背景：真实爆款笔记分析

以下是{'通过搜索获取的' if search_used else '基于经验总结的'}小红书「{category}」分类情感类爆款笔记的分析报告：

---
{analysis_text}
---
{source_info}

## 你的任务

基于以上真实的爆款笔记分析，请生成 {count} 条高质量小红书情感笔记。

### 核心要求
1. **标题**：必须参考分析中发现的爆款标题规律来创作，使用相同的句式结构和情绪节奏
2. **正文**：300-500字，严格套用分析中总结的内容结构（hook→转折→升华），金句密度要高
3. **标签**：5个，参考分析中的标签策略，混合大标签和精准小标签，用逗号分隔
4. **封面文字**：4-10字，参考分析中的封面文字规律
5. **差异化**：{count} 条笔记必须覆盖不同的子主题/场景/切入角度
6. **风格**：必须贴近真实用户的语气，像是一个真实的人在诉说，避免说教感
7. **互动**：结尾必须有引导点赞/收藏/评论的话术（搭配emoji）

### 特别注意
- 直接参考搜索到的爆款笔记的成功要素来创作
- 融入当前热门话题和流行表达
- 每条笔记的 ai_analysis 字段要说明借鉴了哪个爆款笔记的什么策略

## 输出格式

请严格输出如下 JSON 数组格式（不要输出任何其他内容，不要输出 markdown 代码块标记）：
[
  {{
    "title": "笔记标题",
    "content": "笔记正文内容（包含换行符\\n）",
    "tags": "标签1,标签2,标签3,标签4,标签5",
    "cover_text": "封面短句",
    "category": "{category}",
    "ai_analysis": "借鉴了[某爆款笔记特点]，运用了[具体流量策略]"
  }}
]

请确保输出是合法的 JSON，content字段中的换行请用 \\n 表示。不要在JSON前后添加任何其他文字。"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.95,
            "topP": 0.95,
            "maxOutputTokens": 8192
        }
    }

    print("  -> 正在调用 Gemini API 生成内容...")
    t0 = time.time()
    data = gemini_request(api_key, model, payload)
    elapsed = time.time() - t0
    print(f"  -> API 响应耗时: {elapsed:.1f}s")

    if "error" in data:
        raise Exception(f"Gemini API 错误: {data['error']}")

    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

    # 提取 JSON
    posts = extract_json(text)
    if not isinstance(posts, list):
        posts = [posts]

    # 规范化
    result = []
    for p in posts:
        result.append({
            "title": p.get("title", "未命名笔记"),
            "content": p.get("content", "").replace("\\n", "\n"),
            "tags": p.get("tags", ""),
            "cover_text": p.get("cover_text", ""),
            "category": p.get("category", category),
            "ai_analysis": p.get("ai_analysis", "") + (" [基于联网搜索]" if search_used else "")
        })

    return result


def extract_json(text):
    """从文本中提取 JSON"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 尝试 markdown code block
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # 尝试找 JSON 数组
    m = re.search(r'(\[\s*\{[\s\S]*\}\s*\])', text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"无法从返回文本中提取 JSON。原文前200字: {text[:200]}")


# ========== 主测试流程 ==========
def main():
    print("=" * 60)
    print("  Gemini AI 联网搜索+生成 完整测试")
    print("=" * 60)

    # 加载 key
    api_key = load_api_key()
    print(f"  API Key: {api_key[:8]}...{api_key[-4:]}")
    print(f"  Model: {MODEL}")
    print(f"  Category: {CATEGORY}")
    print(f"  Count: {GENERATE_COUNT}")

    # 检查代理
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        print(f"  Proxy: {proxy}")
        proxy_handler = urllib.request.ProxyHandler({
            "https": proxy,
            "http": os.environ.get("HTTP_PROXY") or proxy
        })
        opener = urllib.request.build_opener(proxy_handler, urllib.request.HTTPSHandler(context=ctx))
        urllib.request.install_opener(opener)
    else:
        print("  Proxy: (none)")

    total_start = time.time()

    # Step 1
    try:
        analysis = step1_search_and_analyze(api_key, MODEL, CATEGORY)
    except Exception as e:
        print(f"\n  [FAIL] Step 1 失败: {e}")
        return False

    # Step 2
    try:
        posts = step2_generate_from_analysis(api_key, MODEL, CATEGORY, GENERATE_COUNT, analysis)
    except Exception as e:
        print(f"\n  [FAIL] Step 2 失败: {e}")
        return False

    total_elapsed = time.time() - total_start

    # 输出结果
    print(f"\n{'='*60}")
    print(f"  生成结果: {len(posts)} 条笔记")
    print(f"{'='*60}")

    for i, p in enumerate(posts, 1):
        print(f"\n  --- 笔记 {i} ---")
        print(f"  标题: {p['title']}")
        print(f"  分类: {p['category']}")
        print(f"  标签: {p['tags']}")
        print(f"  封面: {p['cover_text']}")
        print(f"  AI分析: {p['ai_analysis'][:80]}")
        # 显示正文前150字
        content_preview = p['content'][:150].replace('\n', '\n  ')
        print(f"  正文预览: {content_preview}...")
        print(f"  正文字数: {len(p['content'])}")

    print(f"\n{'='*60}")
    print(f"  总耗时: {total_elapsed:.1f}s")
    print(f"  搜索模式: {'联网搜索 (Google Search Grounding)' if analysis['searchUsed'] else '知识库分析 (降级)'}")
    print(f"  来源数量: {len(analysis['sources'])}")
    print(f"  生成笔记: {len(posts)} 条")
    print(f"  测试结果: ALL PASSED!")
    print(f"{'='*60}")
    return True


if __name__ == "__main__":
    # 设置 stdout 为 UTF-8
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    success = main()
    sys.exit(0 if success else 1)
