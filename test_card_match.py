"""测试AI卡片模板匹配功能 - 验证JSON截断修复"""
import urllib.request, urllib.error, json, time

BASE = "https://xhs-gemini-proxy.onrender.com"
TOKEN = None

def api(method, path, body=None, timeout=200):
    url = BASE + path
    data = json.dumps(body).encode('utf-8') if body else None
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        try: err = json.loads(body_text)
        except: err = {"raw": body_text[:500]}
        return False, {"status": e.code, "error": err}
    except Exception as e:
        return False, {"exception": str(e)}

# Login
ok, r = api("POST", "/api/auth/login", {"username": "lin", "password": "950320"})
if ok:
    TOKEN = r.get("token")
    print("✅ 登录成功")
else:
    print(f"❌ 登录失败: {r}")
    exit(1)

# 模拟前端 AI 卡片匹配
title = "空气炸锅做麻薯巴斯克？我天！软糯拉丝爆浆，好吃到原地转圈圈🤩"
content = """姐妹们！谁能想到，咱们家里的空气炸锅，居然能做出这种神仙甜品？！🤯第一次做就成功了，那个拉丝效果，简直像在拍广告！一口下去真的魂穿天堂！😭那些说空气炸锅只能炸鸡翅的，简直是浪费它的功能！

材料超级简单，零失败率，厨房小白也能轻松搞定！准备好你的小本本吧：

** 【准备材料】 **
* 奶油奶酪 200g（提前软化）
* 鸡蛋 1个
* 细砂糖 40g
* 淡奶油 80g
* 玉米淀粉 10g
* 麻薯预拌粉 100g"""

# 模拟 CardEngine templates (just some template ids)
tmplList = """sweet_fresh: 🌸甜美清新 — 甜美清新风格，粉色系渐变背景 [适合: 美食分享,甜品制作,烘焙教程]
product_showcase: 🛒种草带货 — 种草推荐模板 [适合: 好物推荐,产品测评,购物分享]
nature_healing: 🍃自然治愈 — 治愈系模板 [适合: 心情分享,日常记录,治愈文案]
minimal_literary: 📖极简文艺 — 极简文艺模板 [适合: 读书笔记,文案分享,生活感悟]
ins_aesthetic: ✨INS美学 — INS风格模板 [适合: 穿搭分享,美妆教程,生活方式]
ootd_collage: 👗穿搭拼图 — 穿搭拼图模板 [适合: 穿搭分享,搭配灵感,OOTD]
color_palette: 🎨配色灵感 — 配色灵感板 [适合: 设计灵感,配色方案,艺术创作]
retro_film: 📷复古胶片 — 复古胶片风 [适合: 旅行日记,胶片摄影,怀旧记录]"""

prompt = f"""你是小红书图文排版设计专家。根据以下笔记内容，从模板列表中选择最合适的前3个模板，并说明原因。

笔记标题: {title}
笔记内容: {content[:500]}
无配图

可选模板列表:
{tmplList}

严格返回JSON（不要markdown代码块）:
{{"matches":[{{"id":"模板id","score":90,"reason":"选择原因(15字内)"}},{{"id":"","score":80,"reason":""}},{{"id":"","score":70,"reason":""}}]}}"""

payload = {
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3, "maxOutputTokens": 8192}
}

body = {
    "model": "gemini-2.5-flash",
    "feature": "ai_card_match",
    "action": "generateContent",
    "payload": payload
}

print("\n--- 测试 AI 卡片模板匹配 ---")
t0 = time.time()
ok, r = api("POST", "/api/gemini-proxy", body, timeout=120)
elapsed = time.time() - t0

if ok:
    print(f"✅ API 调用成功 | {elapsed:.1f}s")
    candidates = r.get('candidates', [])
    if candidates:
        c = candidates[0]
        finish_reason = c.get('finishReason', '?')
        text = c.get('content', {}).get('parts', [{}])[0].get('text', '')
        print(f"   finishReason: {finish_reason}")
        print(f"   响应文本长度: {len(text)} chars")
        print(f"   响应文本: {text[:500]}")
        
        # Parse
        try:
            parsed = json.loads(text)
            print(f"\n✅ JSON 解析成功!")
            matches = parsed.get('matches', [])
            for i, m in enumerate(matches):
                print(f"   [{i+1}] {m.get('id')} - 匹配度 {m.get('score')} - {m.get('reason')}")
        except json.JSONDecodeError as e:
            print(f"\n❌ JSON 解析失败: {e}")
            print(f"   文本末尾: ...{text[-100:]}")
            
            # Test truncation repair
            import re
            s = text.strip()
            opens = len(re.findall(r'[\[{]', s))
            closes = len(re.findall(r'[\]}]', s))
            print(f"   开括号: {opens}, 闭括号: {closes}")
            
            if opens > closes:
                lastComplete = max(s.rfind('},'), s.rfind('}]'))
                if lastComplete > 0:
                    s = s[:lastComplete + 1]
                depth = []
                for ch in s:
                    if ch == '{': depth.append('}')
                    elif ch == '[': depth.append(']')
                    elif ch in ']}' and depth: depth.pop()
                s += ''.join(reversed(depth))
                try:
                    repaired = json.loads(s)
                    print(f"✅ JSON 修复成功!")
                    for i, m in enumerate(repaired.get('matches', [])):
                        print(f"   [{i+1}] {m.get('id')} - 匹配度 {m.get('score')} - {m.get('reason')}")
                except:
                    print(f"❌ JSON 修复也失败")
    else:
        print(f"   无 candidates: {json.dumps(r, ensure_ascii=False)[:300]}")
else:
    print(f"❌ API 调用失败 | {elapsed:.1f}s")
    print(f"   {json.dumps(r, ensure_ascii=False)[:300]}")

# 查积分
ok, c = api("GET", "/api/user/credits")
if ok:
    print(f"\n💰 积分: {c.get('credits')}, 今日已用: {c.get('todayUsed')}")
