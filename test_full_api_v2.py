"""
全功能 API 测试 v2 — 使用正确的 /api/gemini-proxy 路由
"""
import urllib.request, urllib.error, urllib.parse, json, time, sys

BASE = "https://xhs-gemini-proxy.onrender.com"
TOKEN = None

def api(method, path, body=None, timeout=120):
    url = BASE + path
    data = json.dumps(body).encode('utf-8') if body else None
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            return True, result, time.time() - t0
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        try: err = json.loads(body_text)
        except: err = {"raw": body_text[:500]}
        return False, {"status": e.code, "error": err}, time.time() - t0
    except Exception as e:
        return False, {"exception": str(e)}, 0

def gemini(prompt, model="gemini-2.5-flash", feature="generateContent", max_tokens=500, timeout=120):
    """调用 Gemini 代理"""
    body = {
        "model": model,
        "feature": feature,
        "action": "generateContent",
        "payload": {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens}
        }
    }
    return api("POST", "/api/gemini-proxy", body, timeout=timeout)

def gemini_image(prompt, model="gemini-3.1-flash-image-preview", timeout=120):
    """图片生成"""
    body = {
        "model": model,
        "feature": "图片生成",
        "action": "generateContent",
        "payload": {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 8192, "responseModalities": ["TEXT", "IMAGE"]}
        }
    }
    return api("POST", "/api/gemini-proxy", body, timeout=timeout)

def test(name, ok, result, elapsed):
    status = "✅ PASS" if ok else "❌ FAIL"
    print(f"\n{status} | {name} | {elapsed:.1f}s")
    if not ok:
        print(f"  错误: {json.dumps(result, ensure_ascii=False)[:300]}")
    return ok

def get_ai_text(r):
    try: return r['candidates'][0]['content']['parts'][0].get('text', '')
    except: return ''

# ========== 测试开始 ==========
print("=" * 60)
print("小红书 AI 平台 — 全功能 API 测试 v2")
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
    print(f"  图片生成={r['featureCosts'].get('图片生成')}分, AI修图={r['featureCosts'].get('AI修图')}分, 热门话题={r['featureCosts'].get('热门话题搜索')}分")
    initial_credits = r['credits']

# 3. AI评分优化
print("\n--- 3. AI评分优化 (1积分) ---")
ok, r, t = gemini("用10个字评价标题质量：'今天心情好开心'", feature="AI评分优化")
results["AI评分优化"] = test("AI评分优化", ok, r, t)
if ok: print(f"  回复: {get_ai_text(r)[:100]}")

# 4. 标签生成
print("\n--- 4. 标签生成 (1积分) ---")
ok, r, t = gemini("为笔记生成5个小红书标签：治愈系文案分享每日温暖", feature="标签生成")
results["标签生成"] = test("标签生成", ok, r, t)
if ok: print(f"  标签: {get_ai_text(r)[:150]}")

# 5. 笔记改写
print("\n--- 5. 笔记改写 (1积分) ---")
ok, r, t = gemini("用小红书爆款风格改写：今天吃了一碗很好吃的面条。", feature="笔记改写")
results["笔记改写"] = test("笔记改写", ok, r, t)
if ok: print(f"  改写: {get_ai_text(r)[:150]}")

# 6. AI模板匹配
print("\n--- 6. AI模板匹配 (1积分) ---")
ok, r, t = gemini("从模板中选最适合'治愈晚安文案'的，只返回ID：emotion_warm, minimal_text, photo_overlay", feature="template_match")
results["模板匹配"] = test("AI模板匹配", ok, r, t)
if ok: print(f"  匹配: {get_ai_text(r)[:100]}")

# 7. 爆款标题
print("\n--- 7. 爆款标题 (1积分) ---")
ok, r, t = gemini("为'如何早起不困'生成3个小红书爆款标题", feature="爆款标题")
results["爆款标题"] = test("爆款标题", ok, r, t)
if ok: print(f"  标题: {get_ai_text(r)[:200]}")

# 8. 一键润色
print("\n--- 8. 一键润色 (1积分) ---")
ok, r, t = gemini("润色为小红书风格：最近开始跑步了，感觉身体好了很多。", feature="一键润色")
results["一键润色"] = test("一键润色", ok, r, t)
if ok: print(f"  润色: {get_ai_text(r)[:150]}")

# 9. 图片生成
print("\n--- 9. 图片生成 (2积分) ---")
ok, r, t = gemini_image("一张小红书风格治愈系图片：粉色天空白云夕阳", timeout=120)
results["图片生成"] = test("图片生成", ok, r, t)
if ok and 'candidates' in r:
    parts = r['candidates'][0]['content']['parts']
    has_image = any(p.get('inlineData') for p in parts)
    print(f"  包含图片: {has_image}")
    if has_image:
        for p in parts:
            if p.get('inlineData'):
                img_size = len(p['inlineData']['data']) * 3 // 4
                print(f"  图片大小: ~{img_size // 1024}KB, 类型: {p['inlineData'].get('mimeType')}")
                break

# 10. 竞品分析
print("\n--- 10. 竞品分析 (2积分) ---")
ok, r, t = gemini("简要分析小红书治愈类账号的运营策略，50字以内", feature="竞品分析")
results["竞品分析"] = test("竞品分析", ok, r, t)
if ok: print(f"  分析: {get_ai_text(r)[:150]}")

# 11. 积分变化验证
print("\n--- 11. 积分变化验证 ---")
ok, r, t = api("GET", "/api/user/credits")
results["积分验证"] = test("积分变化验证", ok, r, t)
if ok:
    final = r['credits']
    used = initial_credits - final
    print(f"  初始: {initial_credits} → 当前: {final}, 本轮消耗: {used}积分")
    print(f"  今日总用: {r['todayUsed']}/{r['freeLimit']}")

# 12. 套餐列表
print("\n--- 12. 套餐列表 ---")
ok, r, t = api("GET", "/api/packages")
results["套餐列表"] = test("套餐列表", ok, r, t)
if ok:
    for pkg in r.get('packages', []):
        print(f"  {pkg['name']}: {pkg['credits']}积分 ¥{pkg['price']} {pkg.get('badge','')}")

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
    print("🎉 全部测试通过！所有功能正常运行！")
else:
    print(f"⚠️ {total - passed} 项失败")
