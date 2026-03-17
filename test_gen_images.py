"""测试内容生成 + 3张配图的完整流程耗时"""
import urllib.request, urllib.error, json, time, re

BASE = "https://xhs-gemini-proxy.onrender.com"
TOKEN = None

def api(method, path, body=None, timeout=200):
    url = BASE + path
    data = json.dumps(body).encode('utf-8') if body else None
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            return True, result, time.time() - t0
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        try: err = json.loads(body_text)
        except: err = {"raw": body_text[:500]}
        return False, {"status": e.code, "error": err}, time.time() - t0
    except Exception as e:
        return False, {"exception": str(e)}, time.time() - t0

def gemini(prompt, model="gemini-2.5-flash", feature="generateContent", max_tokens=4096, timeout=120):
    body = {
        "model": model, "feature": feature, "action": "generateContent",
        "payload": {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens}
        }
    }
    return api("POST", "/api/gemini-proxy", body, timeout=timeout)

def gemini_image(prompt, model="gemini-3.1-flash-image-preview", timeout=180):
    body = {
        "model": model, "feature": "图片生成", "action": "generateContent",
        "payload": {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 8192, "responseModalities": ["TEXT", "IMAGE"]}
        }
    }
    return api("POST", "/api/gemini-proxy", body, timeout=timeout)

# === 登录 ===
print("=" * 60)
print("测试：内容生成 1条笔记 + 1封面 + 3张配图（串行）")
print("=" * 60)

ok, r, _ = api("POST", "/api/auth/login", {"username": "lin", "password": "950320"})
if ok:
    TOKEN = r.get("token")
    print(f"✅ 登录成功")
else:
    print(f"❌ 登录失败: {r}")
    exit(1)

# 查积分
ok, c, _ = api("GET", "/api/user/credits")
print(f"💰 当前积分: {c.get('credits')}, 今日已用: {c.get('todayUsed')}")

total_t0 = time.time()

# === Step 1: 内容生成（搜索分析 + 创作）===
print(f"\n--- Step 1: AI 内容生成 ---")
t0 = time.time()

gen_prompt = """你是小红书爆款内容创作专家。请为「治愈」分类生成1条高质量小红书笔记。

要求：
1. 标题要有小红书爆款标题的特点（数字、emoji、悬念、对比等）
2. 正文200-400字，符合小红书调性
3. 包含5-8个标签
4. 封面文字（8-15字，吸引眼球）

返回JSON格式（不要markdown代码块）：
{"posts":[{"title":"标题","content":"正文","tags":"标签1,标签2","cover_text":"封面文字","category":"治愈"}]}"""

ok, r, elapsed = gemini(gen_prompt, feature="内容生成", max_tokens=4096)
if ok:
    text = r.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
    jm = re.search(r'\{[\s\S]*\}', text)
    if jm:
        parsed = json.loads(jm.group(0))
        post = parsed.get('posts', [{}])[0]
        print(f"✅ 内容生成完成 | {elapsed:.1f}s")
        print(f"   标题: {post.get('title', '?')[:50]}")
        print(f"   封面: {post.get('cover_text', '?')}")
    else:
        print(f"⚠️ 内容生成JSON解析失败 | {elapsed:.1f}s")
        post = {"title": "测试标题", "content": "测试内容", "category": "治愈", "cover_text": "治愈你的心"}
else:
    print(f"❌ 内容生成失败 | {elapsed:.1f}s")
    post = {"title": "测试标题", "content": "测试内容", "category": "治愈", "cover_text": "治愈你的心"}

step1_time = time.time() - t0

# === Step 2: 封面图（串行第1张）===
print(f"\n--- Step 2: 生成封面图 ---")
t0 = time.time()

cover_prompt = f"""Generate a beautiful cover image for a Chinese social media post (Xiaohongshu/小红书 style).
Category: {post.get('category', '治愈')}
Cover text: {post.get('cover_text', '治愈你的心')}
Title: {post.get('title', '')}
Style: 小红书风格，柔和的色调，文艺感，适合情感类账号
Important: Vertical portrait orientation (3:4 ratio), include Chinese text "{post.get('cover_text', '')}" as main visual text, Simplified Chinese only, NO Traditional Chinese."""

ok, r, elapsed = gemini_image(cover_prompt)
has_image = False
if ok:
    parts = r.get('candidates', [{}])[0].get('content', {}).get('parts', [])
    for p in parts:
        if 'inlineData' in p:
            has_image = True
            img_size = len(p['inlineData'].get('data', '')) * 3 // 4
            print(f"✅ 封面图生成成功 | {elapsed:.1f}s | ~{img_size//1024}KB")
            break
    if not has_image:
        print(f"⚠️ 封面图无图片数据 | {elapsed:.1f}s")
else:
    print(f"❌ 封面图生成失败 | {elapsed:.1f}s | {json.dumps(r, ensure_ascii=False)[:200]}")

step2_time = time.time() - t0

# === Step 3-5: 3张配图（串行）===
content_snippet = (post.get('content', '') or '测试内容')[:150]
tags = post.get('tags', '治愈,成长')

image_prompts = [
    f"""Create a beautiful aesthetic image for a Chinese social media post.
Theme: "{post.get('title', '治愈')}"
Category: {post.get('category', '治愈')} (情感类)
Style: 小红书风格，柔和色调，文艺感
Requirements: Vertical 3:4 ratio, NO text overlay, artistic, dreamy""",

    f"""Create an artistic scene illustration inspired by this text:
"{content_snippet}"
Style: 小红书风格，柔和色调
Requirements: Vertical 3:4 ratio, NO text, soft, aesthetic, emotionally resonant""",

    f"""Create a visually stunning image for keywords: {tags}
Category mood: {post.get('category', '治愈')}
Style: 小红书风格
Requirements: Vertical 3:4 ratio, NO text, abstract or symbolic, harmonious colors"""
]

step3_times = []
for i, prompt in enumerate(image_prompts):
    print(f"\n--- Step {3+i}: 生成配图 {i+1}/3 ---")
    t0 = time.time()
    ok, r, elapsed = gemini_image(prompt)
    has_image = False
    if ok:
        parts = r.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        for p in parts:
            if 'inlineData' in p:
                has_image = True
                img_size = len(p['inlineData'].get('data', '')) * 3 // 4
                print(f"✅ 配图{i+1} 生成成功 | {elapsed:.1f}s | ~{img_size//1024}KB")
                break
        if not has_image:
            print(f"⚠️ 配图{i+1} 无图片数据 | {elapsed:.1f}s")
    else:
        status = r.get('status', '?')
        print(f"❌ 配图{i+1} 生成失败(HTTP {status}) | {elapsed:.1f}s")
    step3_times.append(time.time() - t0)

total_time = time.time() - total_t0

# === 汇总 ===
print(f"\n{'=' * 60}")
print(f"📊 测试结果汇总")
print(f"{'=' * 60}")
print(f"  内容生成:  {step1_time:.1f}s")
print(f"  封面图:    {step2_time:.1f}s")
for i, t in enumerate(step3_times):
    print(f"  配图{i+1}:     {t:.1f}s")
print(f"  ─────────────────")
print(f"  总耗时:    {total_time:.1f}s")

# 查最终积分
ok, c2, _ = api("GET", "/api/user/credits")
credits_used = (c.get('credits', 0)) - (c2.get('credits', 0))
print(f"\n💰 积分消耗: {credits_used} (剩余 {c2.get('credits')})")
