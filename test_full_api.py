"""
全功能 API 测试 — 用真实账号测试所有核心功能
"""
import urllib.request, urllib.error, urllib.parse, json, time, base64, sys

BASE = "https://xhs-gemini-proxy.onrender.com"
TOKEN = None  # 登录后获取

def api(method, path, body=None, timeout=120, feature=None):
    """通用 API 调用"""
    url = BASE + path
    if feature:
        sep = '&' if '?' in url else '?'
        url += sep + 'feature=' + urllib.parse.quote(feature)
    data = json.dumps(body).encode('utf-8') if body else None
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            elapsed = time.time() - t0
            return True, result, elapsed
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        try:
            err_json = json.loads(body_text)
        except:
            err_json = {"raw": body_text[:500]}
        return False, {"status": e.code, "error": err_json}, time.time() - t0
    except Exception as e:
        return False, {"exception": str(e)}, 0

def test(name, ok, result, elapsed):
    status = "✅ PASS" if ok else "❌ FAIL"
    print(f"\n{status} | {name} | {elapsed:.1f}s")
    if not ok:
        print(f"  错误: {json.dumps(result, ensure_ascii=False)[:300]}")
    return ok

# ========== 测试开始 ==========
print("=" * 60)
print("小红书 AI 平台 — 全功能 API 测试")
print("=" * 60)

results = {}

# 1. 登录
print("\n--- 1. 登录 ---")
ok, r, t = api("POST", "/api/auth/login", {"username": "lin", "password": "950320"})
results["登录"] = test("登录 (lin)", ok, r, t)
if ok:
    TOKEN = r["token"]
    print(f"  用户: {r['user']['username']} (ID: {r['user']['id']})")

# 2. 积分查询
print("\n--- 2. 积分查询 ---")
ok, r, t = api("GET", "/api/user/credits")
results["积分查询"] = test("积分查询", ok, r, t)
if ok:
    print(f"  积分: {r['credits']}, 今日已用: {r['todayUsed']}/{r['freeLimit']}, 免费剩余: {r['freeRemaining']}")
    print(f"  图片生成费率: {r['featureCosts'].get('图片生成')}积分")
    print(f"  AI修图费率: {r['featureCosts'].get('AI修图')}积分")
    print(f"  热门话题费率: {r['featureCosts'].get('热门话题搜索')}积分")
    initial_credits = r['credits']

# 3. 内容生成 (通过 Gemini 代理)
print("\n--- 3. AI 内容生成（笔记评分优化）---")
score_body = {
    "contents": [{"role": "user", "parts": [{"text": "请用10个字评价这个标题的质量：'今天心情好开心'"}]}],
    "generationConfig": {"maxOutputTokens": 100}
}
ok, r, t = api("POST", "/api/gemini/v1beta/models/gemini-2.0-flash:generateContent", score_body, feature="AI评分优化")
results["AI评分优化"] = test("AI评分优化 (1积分)", ok, r, t)
if ok and 'candidates' in r:
    text = r['candidates'][0]['content']['parts'][0].get('text', '')[:100]
    print(f"  AI回复: {text}")

# 4. 标签生成
print("\n--- 4. 标签生成 ---")
tag_body = {
    "contents": [{"role": "user", "parts": [{"text": "为以下笔记生成5个小红书标签：治愈系文案，分享每日的温暖瞬间"}]}],
    "generationConfig": {"maxOutputTokens": 200}
}
ok, r, t = api("POST", "/api/gemini/v1beta/models/gemini-2.0-flash:generateContent", tag_body, feature="标签生成")
results["标签生成"] = test("标签生成 (1积分)", ok, r, t)
if ok and 'candidates' in r:
    text = r['candidates'][0]['content']['parts'][0].get('text', '')[:150]
    print(f"  标签: {text}")

# 5. 笔记改写
print("\n--- 5. 笔记改写 ---")
rewrite_body = {
    "contents": [{"role": "user", "parts": [{"text": "用小红书爆款风格改写：今天吃了一碗很好吃的面条，味道不错。"}]}],
    "generationConfig": {"maxOutputTokens": 300}
}
ok, r, t = api("POST", "/api/gemini/v1beta/models/gemini-2.0-flash:generateContent", rewrite_body, feature="笔记改写")
results["笔记改写"] = test("笔记改写 (1积分)", ok, r, t)
if ok and 'candidates' in r:
    text = r['candidates'][0]['content']['parts'][0].get('text', '')[:150]
    print(f"  改写: {text}")

# 6. AI卡片模板匹配
print("\n--- 6. AI卡片模板匹配 ---")
match_body = {
    "contents": [{"role": "user", "parts": [{"text": "从以下模板ID中选择最适合'治愈系晚安文案'的模板，只返回模板ID：emotion_warm_card, minimal_text_card, photo_overlay_card"}]}],
    "generationConfig": {"maxOutputTokens": 50}
}
ok, r, t = api("POST", "/api/gemini/v1beta/models/gemini-2.0-flash:generateContent", match_body, feature="template_match")
results["模板匹配"] = test("AI模板匹配 (1积分)", ok, r, t)
if ok and 'candidates' in r:
    text = r['candidates'][0]['content']['parts'][0].get('text', '')[:100]
    print(f"  匹配结果: {text}")

# 7. 图片生成
print("\n--- 7. 图片生成 ---")
img_body = {
    "contents": [{"role": "user", "parts": [{"text": "生成一张小红书风格的治愈系图片：粉色天空，一朵白云，温暖夕阳"}]}],
    "generationConfig": {"maxOutputTokens": 8192, "responseModalities": ["TEXT", "IMAGE"]}
}
ok, r, t = api("POST", "/api/gemini/v1beta/models/gemini-2.0-flash-preview-image-generation:generateContent", img_body, timeout=120, feature="图片生成")
results["图片生成"] = test("图片生成 (2积分)", ok, r, t)
if ok and 'candidates' in r:
    parts = r['candidates'][0]['content']['parts']
    has_image = any(p.get('inlineData') for p in parts)
    has_text = any(p.get('text') for p in parts)
    print(f"  包含图片: {has_image}, 包含文本: {has_text}")
    if has_image:
        for p in parts:
            if p.get('inlineData'):
                img_size = len(p['inlineData']['data']) * 3 // 4
                print(f"  图片大小: ~{img_size // 1024}KB, 类型: {p['inlineData'].get('mimeType')}")
                break

# 8. 爆款标题生成
print("\n--- 8. 爆款标题 ---")
title_body = {
    "contents": [{"role": "user", "parts": [{"text": "为'如何早起不困'生成3个小红书爆款标题"}]}],
    "generationConfig": {"maxOutputTokens": 300}
}
ok, r, t = api("POST", "/api/gemini/v1beta/models/gemini-2.0-flash:generateContent", title_body, feature="爆款标题")
results["爆款标题"] = test("爆款标题 (1积分)", ok, r, t)
if ok and 'candidates' in r:
    text = r['candidates'][0]['content']['parts'][0].get('text', '')[:200]
    print(f"  标题: {text}")

# 9. 再次查询积分（验证扣费）
print("\n--- 9. 积分变化验证 ---")
ok, r, t = api("GET", "/api/user/credits")
results["积分验证"] = test("积分变化验证", ok, r, t)
if ok:
    final_credits = r['credits']
    used = initial_credits - final_credits
    print(f"  初始积分: {initial_credits} → 当前: {final_credits}")
    print(f"  本轮消耗: {used}积分, 今日总用: {r['todayUsed']}/{r['freeLimit']}")

# 10. 套餐列表
print("\n--- 10. 套餐列表 ---")
ok, r, t = api("GET", "/api/packages")
results["套餐列表"] = test("套餐列表", ok, r, t)
if ok:
    for pkg in r.get('packages', []):
        print(f"  {pkg['name']}: {pkg['credits']}积分 / ¥{pkg['price']} {pkg.get('badge','')}")

# ========== 汇总 ==========
print("\n" + "=" * 60)
print("测试结果汇总")
print("=" * 60)
passed = sum(1 for v in results.values() if v)
total = len(results)
for name, ok in results.items():
    print(f"  {'✅' if ok else '❌'} {name}")
print(f"\n通过: {passed}/{total}")
if passed == total:
    print("🎉 全部通过！")
else:
    print(f"⚠️ {total - passed} 项失败，请检查")
