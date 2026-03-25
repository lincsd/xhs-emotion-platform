"""测试 20260324h: 异步v3 + 全局超时240s + 减少重试"""
import requests, time, json, sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"

# 1) 登录
print(f"[1] 登录 {BASE}...")
s = requests.Session()
r = s.post(f"{BASE}/api/auth/login", json={"username": "lin", "password": "950320"}, timeout=15)
assert r.status_code == 200, f"登录失败: {r.status_code}"
token = r.json().get("token","")
print(f"    ✓ 登录成功, token={token[:20]}...")

# 2) 检查版本
r = s.get(f"{BASE}/api/version", timeout=10)
ver = r.json()
print(f"    版本: {ver}")

# 3) 异步提交 v3 生图（使用测试卡片数据）
test_card = {
    "full_id": "小学_数学_三年级_下册_test_001",
    "title": "分数的初步认识",
    "type": "方法卡",
    "definition": "分数是表示一个物体被平均分成若干份中取其中一份或几份的数",
    "example": {
        "question": "一个圆被平均分成4份，取其中的1份，怎样用分数表示？",
        "steps": ["把一个圆平均分成4份", "取其中的1份", "写成分数：分母是4，分子是1"],
        "answer": "1/4"
    },
    "core_points": ["分母表示平均分成的总份数", "分子表示取的份数", "分数线表示平均分"],
    "memory_tip": "分母在下面，分子在上面",
    "difficulty": 2,
    "grade": "三年级",
    "semester": "下册"
}
print("[3] 异步提交 v3 生图...")
t0 = time.time()
r = s.post(f"{BASE}/api/generate-card-image-v3-async", 
           json={"card": test_card, "subject": "数学", "grade": "三年级", "semester": "下册"},
           timeout=30)
assert r.status_code == 200, f"提交失败: {r.status_code} {r.text[:200]}"
task_id = r.json().get("task_id")
print(f"    ✓ task_id={task_id} ({time.time()-t0:.1f}s)")

# 4) 轮询
print("[4] 轮询任务状态...")
for i in range(120):
    time.sleep(3)
    elapsed = time.time() - t0
    try:
        r = s.get(f"{BASE}/api/task-status/{task_id}", timeout=15)
        data = r.json()
    except Exception as e:
        print(f"    [{elapsed:.0f}s] poll error: {e}")
        continue
    
    status = data.get("status")
    progress = data.get("progress", "")
    
    if status == "done":
        result = data.get("result", {})
        ok = result.get("ok", False)
        pipeline = result.get("pipeline", [])
        quality = result.get("quality_score") or result.get("qualityScore")
        has_image = bool(result.get("image"))
        img_size = len(result.get("image", "")) * 3 // 4 // 1024 if result.get("image") else 0
        final_action = result.get("finalAction", "?")
        print(f"    ✓ [{elapsed:.0f}s] DONE! ok={ok}, quality={quality}, image={img_size}KB, action={final_action}")
        if pipeline:
            print("    Pipeline:")
            for l in pipeline:
                print(f"      {l}")
        break
    elif status == "error":
        result = data.get("result", {})
        err = result.get("error", "unknown")
        pipeline = result.get("pipeline", [])
        print(f"    ✗ [{elapsed:.0f}s] ERROR: {err}")
        if pipeline:
            print("    Pipeline:")
            for l in pipeline:
                print(f"      {l}")
        break
    else:
        if i % 5 == 0:
            print(f"    [{elapsed:.0f}s] running... {progress}")
else:
    print(f"    ✗ [{time.time()-t0:.0f}s] 轮询超时!")

total = time.time() - t0
print(f"\n总耗时: {total:.1f}s")
