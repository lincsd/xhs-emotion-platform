"""
v10.27 优化重测 — 仅测 P1a + P2 (清缓存后)
4张卡 × 2轮 = 8次生成
复用 _test_v1027_optimization.py 的 find_card + submit_task 逻辑
"""
import urllib.request
import json
import time
import os
import datetime
import traceback

# ── Config ──
BASE = 'http://localhost:3000'
TOKEN = '8ebz1cyLh1tEkhzHy0P5cduuuO2E94nbhtjl2xtOmtXeYQ4IIQAaNxy4wk9xcSRN'
ROUNDS = 2
POLL_INTERVAL = 10
MAX_POLL = 120

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_KC_DIR = os.path.join(SCRIPT_DIR, 'public', 'knowledge_cards')

# 被 skip-all 的4张卡 (缓存已清除)
# (type_name, card_full_id, grade_short, opt_tag)
TEST_CARDS = [
    ('情景对话卡', '英语-三上-01-02', '三上', 'P1a'),
    ('情景对话卡', '英语-六上-01-05', '六上', 'P1a'),
    ('易混词卡',   '英语-三上-03-03', '三上', 'P2'),
    ('易混词陷阱卡', '英语-三上-T1-01', '三上', 'P2'),
]

# 旧缓存分数 (v10.26 baseline)
BASELINE = {
    '情景对话卡':   {'audit': 99, 'quality': 99},
    '易混词卡':     {'audit': 95, 'quality': 99},
    '易混词陷阱卡': {'audit': 90, 'quality': 95},
}


def find_card(card_full_id, grade_short):
    """Find a card by full_id in public knowledge_cards directory."""
    for root, dirs, files in os.walk(PUBLIC_KC_DIR):
        for fn in sorted(files):
            if not fn.endswith('.json'):
                continue
            fp = os.path.join(root, fn)
            with open(fp, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict) or 'units' not in data:
                continue
            gs = data.get('grade_short', '')
            semester = data.get('semester', '上册')
            if gs != grade_short:
                continue
            for unit in data.get('units', []):
                if isinstance(unit, dict) and 'cards' in unit:
                    for c in unit['cards']:
                        if c.get('full_id') == card_full_id:
                            return c, gs, semester
    return None, None, None


def submit_task(card, grade_short, semester):
    body = {
        "card": card,
        "subject": "英语",
        "grade": grade_short,
        "semester": semester,
        "quality": "high",
    }
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        f'{BASE}/api/generate-card-image-v3-async',
        data=payload,
        headers={
            'Authorization': f'Bearer {TOKEN}',
            'Content-Type': 'application/json'
        },
        method='POST'
    )
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read().decode())
    return data.get('taskId') or data.get('task_id')


def poll_task(task_id):
    url = f'{BASE}/api/task-status/{task_id}'
    for _ in range(MAX_POLL):
        time.sleep(POLL_INTERVAL)
        try:
            req = urllib.request.Request(url, headers={'Authorization': f'Bearer {TOKEN}'})
            resp = urllib.request.urlopen(req, timeout=15)
            sr = json.loads(resp.read().decode())
            status = sr.get('status', '')
            if 'done' in status or '完成' in status:
                return sr.get('result', sr)
            if 'fail' in status or 'error' in status or '失败' in status:
                return {'ok': False, 'error': status}
        except Exception as e:
            print(f'    poll error: {e}', flush=True)
    return {'ok': False, 'error': 'timeout'}


def main():
    t0 = time.time()
    all_results = []
    print(f"=== v10.27 重测 (清缓存) 开始 {datetime.datetime.now():%H:%M:%S} ===", flush=True)
    print(f"卡片数: {len(TEST_CARDS)}, 每卡轮数: {ROUNDS}, 共: {len(TEST_CARDS)*ROUNDS}次", flush=True)
    print()

    for ci, (type_name, card_full_id, grade_short, opt_tag) in enumerate(TEST_CARDS):
        print(f"[{ci+1}/{len(TEST_CARDS)}] {type_name} ({card_full_id}) [{opt_tag}]", flush=True)

        card, gs, semester = find_card(card_full_id, grade_short)
        if not card:
            print(f"  ❌ 找不到卡片JSON!", flush=True)
            all_results.append({"card_id": card_full_id, "type_name": type_name, "opt_tag": opt_tag, "results": []})
            continue

        results = []
        for r in range(ROUNDS):
            print(f"  Round {r+1}/{ROUNDS}...", flush=True)
            rt0 = time.time()
            try:
                tid = submit_task(card, gs, semester)
                print(f"    taskId={tid}", flush=True)
                result = poll_task(tid)
                elapsed = time.time() - rt0

                audit = result.get("auditScore", 0)
                quality = 0
                qd = result.get("qualityDetail")
                if isinstance(qd, dict):
                    quality = qd.get("total", 0)
                if quality == 0:
                    quality = result.get("qualityScore", 0)

                final_action = result.get("finalAction", "unknown")

                print(f"    ✅ audit={audit} quality={quality} action={final_action} ({elapsed:.0f}s)", flush=True)

                results.append({
                    "ok": result.get("ok", True),
                    "auditScore": audit,
                    "qualityScore": quality,
                    "qualityDetail": qd,
                    "finalAction": final_action,
                    "pipeline": result.get("pipeline", []),
                    "manifest": result.get("manifest", {}),
                    "model": result.get("model", ""),
                    "elapsed": elapsed,
                    "has_image": bool(result.get("mimeType")),
                    "image_size": result.get("size", 0),
                })
            except Exception as e:
                print(f"    ❌ 错误: {e}", flush=True)
                traceback.print_exc()
                results.append({"ok": False, "error": str(e), "elapsed": time.time()-rt0})

        bl = BASELINE.get(type_name, {})
        all_results.append({
            "card_id": card_full_id,
            "type_name": type_name,
            "opt_tag": opt_tag,
            "baseline_audit": bl.get("audit", 0),
            "baseline_quality": bl.get("quality", 0),
            "results": results,
        })
        print(flush=True)

    total_time = time.time() - t0
    print(f"=== 完成! 总耗时 {total_time/60:.1f}分钟 ===", flush=True)

    # 保存结果
    out_path = os.path.join(SCRIPT_DIR, "_test_v1027_retest_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"结果已保存: {out_path}", flush=True)

    # 打印摘要
    print("\n=== 摘要 ===")
    print(f"{'卡片类型':<12} {'Tag':<5} {'R1 Audit':>8} {'R1 Qual':>8} {'R2 Audit':>8} {'R2 Qual':>8} {'旧Audit':>8} {'旧Qual':>8} {'Δ Audit':>8}")
    for item in all_results:
        r = item["results"]
        if len(r) >= 2:
            r1a, r1q = r[0].get("auditScore",0), r[0].get("qualityScore",0)
            r2a, r2q = r[1].get("auditScore",0), r[1].get("qualityScore",0)
            avg_a = (r1a + r2a) / 2
            ba = item.get("baseline_audit", 0)
            bq = item.get("baseline_quality", 0)
            delta = avg_a - ba
            sign = "+" if delta > 0 else ""
            print(f"{item['type_name']:<12} {item['opt_tag']:<5} {r1a:>8} {r1q:>8} {r2a:>8} {r2q:>8} {ba:>8} {bq:>8} {sign}{delta:>7.1f}")

if __name__ == "__main__":
    main()
