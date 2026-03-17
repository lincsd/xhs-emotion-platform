"""测试 AI 智能模板匹配 — 复现前端格式错误问题"""
import urllib.request, urllib.error, json, time

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

# 1. Login
print("=== 登录 ===")
ok, r, _ = api("POST", "/api/auth/login", {"username": "lin", "password": "950320"})
if ok:
    TOKEN = r.get("token")
    print(f"登录成功, 积分: {r.get('credits')}")
else:
    print(f"登录失败: {r}")
    exit(1)

# 2. 模拟前端 AI 模板匹配请求（和前端完全一致）
tmplList = """note_dry_goods: 📝笔记干货 — 专注知识分享和干货内容的排版 [适合: 教程,攻略,知识分享]
note_handwritten: ✍️笔记手账 — 手写风格笔记排版 [适合: 日常记录,手帐,日记]
minimal_text: 🎯极简文字 — 极简纯文字排版 [适合: 文案,语录,心情]
photo_literary: 📷照片文艺 — 文艺照片排版 [适合: 旅行,风景,摄影]
food_recommendation: 🍜美食推荐 — 美食推荐排版 [适合: 美食,餐厅,食谱]
product_grass: 🛍️种草带货 — 产品种草推荐 [适合: 好物推荐,购物,测评]"""

prompt = f"""你是小红书图文排版设计专家。根据以下笔记内容，从模板列表中选择最合适的前3个模板，并说明原因。

笔记标题: 懒人晚餐 | 10分钟封神！这碗葱油拌面，好吃到我连盘子都舔干净了🤤🔥
笔记分类: 美食
笔记内容: 姐妹们，有没有跟我一样，下班回家累趴，但又不想点外卖，一个人吃饭又懒得大动干戈的？今天这碗葱油拌面，就是我的"续命神器"！真的好吃到我连盘子都舔干净了，分分钟把你从"外卖深渊"里拉出来！巨简单，巨快，巨浓郁，碳水爱人狂喜！
无配图

可选模板列表:
{tmplList}


严格返回JSON（不要markdown代码块）:
{{"matches":[{{"id":"模板id","score":90,"reason":"选择原因(15字内)"}},{{"id":"","score":80,"reason":""}},{{"id":"","score":70,"reason":""}}]}}"""

print("\n=== 测试1: 不带 responseMimeType ===")
body1 = {
    "model": "gemini-2.5-flash",
    "feature": "ai_card_match",
    "action": "generateContent",
    "payload": {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 512}
    }
}
ok1, r1, t1 = api("POST", "/api/gemini-proxy", body1)
print(f"耗时: {t1:.1f}s, 成功: {ok1}")
if ok1:
    text1 = r1.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
    print(f"AI返回文本: {text1[:500]}")
    import re
    jm1 = re.search(r'\{[\s\S]*\}', text1)
    print(f"JSON匹配: {'成功' if jm1 else '失败 ❌'}")
    if jm1:
        try:
            parsed = json.loads(jm1.group(0))
            print(f"解析成功: {json.dumps(parsed, ensure_ascii=False)}")
        except Exception as e:
            print(f"JSON解析失败: {e}")
else:
    print(f"API错误: {json.dumps(r1, ensure_ascii=False)[:500]}")

print("\n=== 测试2: 修复版 — maxOutputTokens=2048 ===")
body2 = {
    "model": "gemini-2.5-flash",
    "feature": "ai_card_match",
    "action": "generateContent",
    "payload": {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3, "maxOutputTokens": 2048}
    }
}
ok2, r2, t2 = api("POST", "/api/gemini-proxy", body2)
print(f"耗时: {t2:.1f}s, 成功: {ok2}")
if ok2:
    text2 = r2.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
    print(f"AI返回文本: {text2[:500]}")
    import re
    jm2 = re.search(r'\{[\s\S]*\}', text2)
    print(f"JSON匹配: {'成功' if jm2 else '失败 ❌'}")
    if jm2:
        try:
            parsed = json.loads(jm2.group(0))
            print(f"解析成功: {json.dumps(parsed, ensure_ascii=False)}")
        except Exception as e:
            print(f"JSON解析失败: {e}")
else:
    print(f"API错误: {json.dumps(r2, ensure_ascii=False)[:500]}")

# 也测试完整response结构
print("\n=== 完整响应结构检查 ===")
if ok2:
    print(f"r2 keys: {list(r2.keys())}")
    if 'candidates' in r2:
        c = r2['candidates'][0]
        print(f"candidate keys: {list(c.keys())}")
        if 'content' in c:
            print(f"content keys: {list(c['content'].keys())}")
            if 'parts' in c['content']:
                for i, p in enumerate(c['content']['parts']):
                    print(f"  part[{i}] keys: {list(p.keys())}")
                    if 'text' in p:
                        print(f"  part[{i}].text = {p['text'][:200]}")
    print(f"\n完整响应:\n{json.dumps(r2, ensure_ascii=False, indent=2)[:1500]}")
