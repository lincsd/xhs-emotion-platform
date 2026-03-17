"""Quick test: AI card matching only"""
import urllib.request, urllib.error, json, time

BASE = "https://xhs-gemini-proxy.onrender.com"
TOKEN = None

def api(method, path, body=None, timeout=200):
    url = BASE + path
    data = json.dumps(body).encode('utf-8') if body else None
    headers = {"Content-Type": "application/json"}
    if TOKEN: headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, json.loads(resp.read().decode()), time.time()-t0
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        try: err = json.loads(body_text)
        except: err = {"raw": body_text[:300]}
        return False, {"status": e.code, "error": err}, time.time()-t0
    except Exception as e:
        return False, {"exception": str(e)}, time.time()-t0

ok, r, _ = api("POST", "/api/auth/login", {"username":"lin","password":"950320"})
if ok:
    TOKEN = r.get("token")
    print("Login OK")
else:
    print(f"Login failed: {r}")
    exit(1)

ok, c, _ = api("GET", "/api/user/credits")
print(f"Credits: {c.get('credits', 0)}")

post = {
    "title": "别只顾着焦虑！3个治愈小秘诀，把生活调成静音模式",
    "content": "今天分享3个简单却有效的自我治愈方法，从日落散步到睡前写日记，让你找到内心的宁静...",
    "category": "治愈",
    "tags": "治愈系,情绪疗愈,内耗自救,生活美学",
    "cover_text": "内耗患者请进！我的治愈秘方"
}

print("\nTesting AI card match...")
match_prompt = f"""你是小红书卡片模板匹配专家。根据笔记内容选择最合适的卡片模板。

笔记:
- 标题: {post['title']}
- 分类: {post['category']}
- 标签: {post['tags']}
- 用户已上传 2 张配图

可选模板:
1. minimal_literary(简约文艺): 情感,成长,读书,感悟
2. sweet_fresh(甜美清新): 日常,美食,手帐,种草
3. ins_aesthetic(INS美学): 穿搭,旅行,咖啡,生活
4. nature_healing(自然治愈): 治愈,心理,正能量,温暖,自然
5. handwrite_diary(手写日记): 日记,心情,记录
6. note_knowledge(笔记干货): 学习,干货,方法
7. candy_pop(活力彩虹): 彩虹,派对,活力

返回JSON（不要代码块）：
[{{"id":"模板id","reason":"推荐理由"}}]
最多返回3个"""

body = {
    "model": "gemini-2.5-flash",
    "feature": "ai_card_match",
    "action": "generateContent",
    "payload": {
        "contents": [{"role": "user", "parts": [{"text": match_prompt}]}],
        "generationConfig": {"maxOutputTokens": 8192, "responseMimeType": "application/json", "temperature": 0.3}
    }
}
ok, r, elapsed = api("POST", "/api/gemini-proxy", body, timeout=60)
if ok:
    text = r.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    clean = text.replace("```json", "").replace("```", "").strip()
    try:
        arr = json.loads(clean)
        print(f"AI match OK | {elapsed:.1f}s")
        for i, m in enumerate(arr):
            star = ">>>" if i == 0 else "   "
            print(f"  {star} {i+1}. {m.get('id', '?')} - {m.get('reason', '?')}")
    except Exception as e:
        print(f"JSON parse failed: {e}")
        print(f"Raw: {clean[:200]}")
else:
    print(f"AI match failed ({elapsed:.1f}s): {json.dumps(r, ensure_ascii=False)[:200]}")

ok, c2, _ = api("GET", "/api/user/credits")
print(f"Credits after: {c2.get('credits', 0)}")
