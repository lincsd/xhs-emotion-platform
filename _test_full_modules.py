# -*- coding: utf-8 -*-
"""
全面功能测试脚本 - LOCAL + TUNNEL 环境
测试模块: 知识卡片 / Prompt工程库 / 笔记工坊
"""
import json, time, sys, urllib.request, urllib.error, urllib.parse, ssl

# ── 配置 ──
ALL_TARGETS = {
    "local":  ("http://localhost:3000", "LOCAL"),
    "tunnel": ("https://xhs.xiaohsai.com", "TUNNEL"),
    "render": ("https://xhs-gemini-proxy.onrender.com", "RENDER"),
}
# 命令行参数选择目标: local / tunnel / render / all (默认 local+tunnel)
_arg = sys.argv[1].lower() if len(sys.argv) > 1 else ""
if _arg == "all":
    TARGETS = list(ALL_TARGETS.values())
elif _arg in ALL_TARGETS:
    TARGETS = [ALL_TARGETS[_arg]]
else:
    TARGETS = [ALL_TARGETS["local"], ALL_TARGETS["tunnel"]]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
}

BASE = None
PASS = 0
FAIL = 0
RESULTS = []

def log(ok, name, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        RESULTS.append(f"  ✅ {name}")
    else:
        FAIL += 1
        RESULTS.append(f"  ❌ {name}: {detail}")
    print(RESULTS[-1])

def GET(path, timeout=15):
    url = BASE + path
    req = urllib.request.Request(url, headers=HEADERS)
    r = urllib.request.urlopen(req, timeout=timeout, context=ctx)
    return json.loads(r.read().decode())

def GET_FILE(path, timeout=15):
    url = BASE + "/" + urllib.parse.quote(path)
    req = urllib.request.Request(url, headers=HEADERS)
    r = urllib.request.urlopen(req, timeout=timeout, context=ctx)
    return json.loads(r.read().decode())

def POST(path, body, timeout=60):
    url = BASE + path
    data = json.dumps(body).encode()
    h = {**HEADERS, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=h)
    r = urllib.request.urlopen(req, timeout=timeout, context=ctx)
    return json.loads(r.read().decode())

def GET_RAW(path, timeout=15):
    url = BASE + path
    req = urllib.request.Request(url, headers=HEADERS)
    r = urllib.request.urlopen(req, timeout=timeout, context=ctx)
    return r.read(), r.status


def run_all_tests():
    global PASS, FAIL, RESULTS

    # ═══ 1. 基础健康检查 ═══
    print("\n" + "="*60)
    print("📋 1. 基础健康检查")
    print("="*60)

    try:
        d = GET("/api/version")
        ok = d.get("version") == "20260323e" and d.get("keyCount") == 3
        log(ok, "API Version", f"got: {d}")
    except Exception as e:
        log(False, "API Version", str(e))

    try:
        d = GET("/healthz")
        log(d.get("status") == "ok", "Healthz", f"got: {d}")
    except Exception as e:
        log(False, "Healthz", str(e))

    # ═══ 2. 知识卡片模块 ═══
    print("\n" + "="*60)
    print("📚 2. 知识卡片模块")
    print("="*60)

    # 2a. 标准卡片包
    try:
        data = GET_FILE("knowledge_cards/小学/数学_五下.json")
        has_units = len(data.get("units", [])) > 0
        first_card = data["units"][0]["cards"][0]
        has_req = all(k in first_card for k in ["full_id","title","definition","core_points","example","mistakes","memory_tip","related"])
        log(has_units and has_req, "标准卡片_数学_五下", f"units={len(data['units'])}, cards={sum(len(u['cards']) for u in data['units'])}")
    except Exception as e:
        log(False, "标准卡片_数学_五下", str(e))

    # 2b. 爆款卡片包 - 数学 (修复后)
    try:
        data = GET_FILE("knowledge_cards/小学/数学_五下_爆款.json")
        first_card = data["units"][0]["cards"][0]
        has_boom = all(k in first_card for k in ["emotion_hook", "trap_point"])
        has_fix = all(k in first_card for k in ["related", "mistakes", "memory_tip"])
        log(has_boom and has_fix, "爆款卡片_数学_五下(修复验证)", f"boom_fields={'✓' if has_boom else '✗'}, fixed={'✓' if has_fix else '✗'}")
    except Exception as e:
        log(False, "爆款卡片_数学_五下(修复验证)", str(e))

    # 2c. 语文爆款
    try:
        data = GET_FILE("knowledge_cards/小学/语文_三下_爆款.json")
        first_card = data["units"][0]["cards"][0]
        ok = all(k in first_card for k in ["full_id","title","related","mistakes","memory_tip"])
        log(ok, "爆款卡片_语文_三下", f"units={len(data['units'])}")
    except Exception as e:
        log(False, "爆款卡片_语文_三下", str(e))

    # 2d. 英语爆款 (修复后)
    try:
        data = GET_FILE("knowledge_cards/小学/英语_四下_爆款.json")
        first_card = data["units"][0]["cards"][0]
        ok = all(k in first_card for k in ["full_id","title","related","mistakes","memory_tip"])
        log(ok, "爆款卡片_英语_四下(修复验证)", f"units={len(data['units'])}")
    except Exception as e:
        log(False, "爆款卡片_英语_四下(修复验证)", str(e))

    # 2e. 全年级覆盖率
    sg = {
        "数学": ["一上","一下","二上","二下","三上","三下","四上","四下","五上","五下","六上","六下"],
        "语文": ["一上","一下","二上","二下","三上","三下","四上","四下","五上","五下","六上","六下"],
        "英语": ["三上","三下","四上","四下","五上","五下","六上","六下"]
    }
    std_ok, boom_ok, std_total, boom_total = 0, 0, 0, 0
    missing_std, missing_boom = [], []
    for subj, grades in sg.items():
        for g in grades:
            std_total += 1
            boom_total += 1
            try:
                GET_FILE(f"knowledge_cards/小学/{subj}_{g}.json")
                std_ok += 1
            except:
                missing_std.append(f"{subj}_{g}")
            try:
                GET_FILE(f"knowledge_cards/小学/{subj}_{g}_爆款.json")
                boom_ok += 1
            except:
                missing_boom.append(f"{subj}_{g}_爆款")

    log(std_ok == std_total, f"标准卡片覆盖率 {std_ok}/{std_total}", f"missing: {missing_std}")
    log(boom_ok == boom_total, f"爆款卡片覆盖率 {boom_ok}/{boom_total}", f"missing: {missing_boom}")

    # 2f. AI卡片搜索
    for query, subj in [("分数除法怎么算","数学"), ("古诗默写","语文"), ("past tense","英语")]:
        try:
            d = POST("/api/ai-match-cards", {"query": query, "subject": subj}, timeout=30)
            ok = d.get("ok") and len(d.get("results", [])) > 0
            log(ok, f"AI卡片搜索({subj})", f"results={len(d.get('results',[]))}, total={d.get('total')}")
        except Exception as e:
            log(False, f"AI卡片搜索({subj})", str(e))

    # ═══ 3. Prompt工程库模块 ═══
    print("\n" + "="*60)
    print("🧪 3. Prompt工程库模块")
    print("="*60)

    # 3a. Gemini代理 - 文本生成
    try:
        d = POST("/api/gemini-proxy", {
            "model": "gemini-2.5-flash",
            "payload": {
                "contents": [{"parts":[{"text":"请用一句话介绍小红书平台"}]}],
                "generationConfig": {"maxOutputTokens": 100}
            },
            "action": "generateContent",
            "feature": "test"
        }, timeout=60)
        has_text = False
        if "candidates" in d:
            parts = d["candidates"][0].get("content",{}).get("parts",[])
            has_text = any(p.get("text","") for p in parts)
        log(has_text, "Gemini代理_文本生成", f"resp_keys={list(d.keys())[:5]}")
    except Exception as e:
        log(False, "Gemini代理_文本生成", str(e))

    # 3b. 生成 Prompt Record (R1→R2→R3) - 耗时较长
    try:
        d = POST("/api/generate-prompt-record", {
            "card": {
                "full_id": "数学-五下-U1-01",
                "type": "概念卡",
                "title": "分数的意义",
                "definition": "把一个整体平均分成若干份，取其中的一份或几份",
                "core_points": ["分数的意义", "分数的组成"]
            },
            "subject": "数学"
        }, timeout=180)
        ok = d.get("ok", False)
        record = d.get("record", {})
        log(ok, f"生成Prompt Record(R1→R2→R3)", f"ok={ok}, record_keys={list(record.keys())[:6]}")
    except Exception as e:
        log(False, "生成Prompt Record(R1→R2→R3)", str(e))

    # ═══ 4. 笔记工坊模块 ═══
    print("\n" + "="*60)
    print("📝 4. 笔记工坊模块")
    print("="*60)

    # 4a. 获取已生成笔记列表
    try:
        d = GET("/api/generated-notes")
        notes = d.get("notes", [])
        log(True, f"笔记列表获取", f"count={len(notes)}")
        if notes:
            n = notes[0]
            has_fields = all(k in n for k in ["title", "body"])
            log(has_fields, "笔记结构完整性", f"keys={list(n.keys())[:8]}")
    except Exception as e:
        log(False, "笔记列表获取", str(e))

    # 4b. AI一键生成笔记 - 耗时较长
    try:
        d = POST("/api/generate-note", {
            "card_id": "数学-五下-T1-01",
            "card_title": "90%的娃都算错！长方体拼接表面积",
            "card_type": "陷阱卡",
            "subject": "数学",
            "grade": "五下",
            "style": "干货型",
            "note_type": "干货型"
        }, timeout=180)
        ok = d.get("ok", False)
        note = d.get("note", {})
        has_title = bool(note.get("title", ""))
        has_body = bool(note.get("body", ""))
        has_carousel = "carousel" in note or "carousel_plan" in note
        log(ok and has_title and has_body, "AI生成笔记",
            f"title={note.get('title','')[:30]}…, body_len={len(note.get('body',''))}, carousel={'✓' if has_carousel else '✗'}")
    except Exception as e:
        log(False, "AI生成笔记", str(e))

    # 4c. AI-Proxy
    try:
        d = POST("/api/ai-proxy", {
            "model": "gemini-2.5-flash",
            "payload": {
                "contents": [{"parts":[{"text":"1+1=?"}]}],
                "generationConfig": {"maxOutputTokens": 50}
            },
            "action": "generateContent",
            "feature": "test"
        }, timeout=30)
        has_resp = "candidates" in d
        log(has_resp, "AI-Proxy代理", f"resp_keys={list(d.keys())[:5]}")
    except Exception as e:
        log(False, "AI-Proxy代理", str(e))

    # ═══ 5. 前端页面加载 ═══
    print("\n" + "="*60)
    print("🌐 5. 前端页面加载")
    print("="*60)

    try:
        body, status = GET_RAW("/", timeout=15)
        html = body.decode('utf-8', errors='ignore')
        has_kc = 'KnowledgeCards' in html
        has_pl = 'PromptLib' in html
        has_nw = 'NoteWorkshop' in html
        has_gen_img = 'generateCarouselImages' in html
        size_kb = len(body) / 1024
        log(has_kc and has_pl and has_nw, f"首页加载({size_kb:.0f}KB)",
            f"KC={'✓' if has_kc else '✗'} PL={'✓' if has_pl else '✗'} NW={'✓' if has_nw else '✗'} CarouselGen={'✓' if has_gen_img else '✗'}")
    except Exception as e:
        log(False, "首页加载", str(e))

    try:
        encoded_path = "/knowledge_cards/" + urllib.parse.quote("小学") + "/" + urllib.parse.quote("数学_三下.json")
        body, status = GET_RAW(encoded_path, timeout=10)
        d = json.loads(body.decode('utf-8'))
        has_units = len(d.get('units', [])) > 0
        log(status == 200 and has_units, f"静态JSON加载({len(body)/1024:.1f}KB)", f"units={len(d.get('units',[]))}")
    except Exception as e:
        log(False, "静态JSON加载", str(e))

    # ═══ 总结 ═══
    print("\n" + "="*60)
    print(f"📊 测试总结: {PASS} 通过 / {FAIL} 失败 / {PASS+FAIL} 总计")
    print("="*60)
    print(f"  环境: {BASE}")
    for r in RESULTS:
        print(r)
    if FAIL > 0:
        print(f"\n⚠️ 有 {FAIL} 项测试失败!")
    else:
        print(f"\n🎉 全部通过!")
    return PASS, FAIL


# ── 主循环 ──
all_pass = 0
all_fail = 0
for base_url, label in TARGETS:
    BASE = base_url
    PASS = 0
    FAIL = 0
    RESULTS = []
    print("\n" + "#"*70)
    print(f"### 测试环境: {label} ({base_url})")
    print("#"*70)
    p, f = run_all_tests()
    all_pass += p
    all_fail += f

print("\n" + "#"*70)
print(f"### 全局总计: {all_pass} 通过 / {all_fail} 失败")
print("#"*70)
if all_fail > 0:
    sys.exit(1)
