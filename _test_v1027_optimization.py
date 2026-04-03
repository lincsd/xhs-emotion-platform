# -*- coding: utf-8 -*-
"""
v10.27 优化对比测试
测试 4 项优化 (P0不规则动词卡Schema, P1a情景对话卡对齐, P1b字数收紧, P2对比强化)
对比基线: Phase 1 测试报告 v10.26 数据

每种卡片类型 2 轮，优化涉及的 5 种类型 + 1 个对照组 = 6 种
"""
import urllib.request
import json
import time
import sys
import os
import base64
import datetime
import traceback

# ── Config ──
BASE = 'http://localhost:3000'
TOKEN = '8ebz1cyLh1tEkhzHy0P5cduuuO2E94nbhtjl2xtOmtXeYQ4IIQAaNxy4wk9xcSRN'
ROUNDS = 2
POLL_INTERVAL = 10
MAX_POLL = 120
REPORT_FILE = '_test_v1027_optimization_report.html'
JSON_FILE = '_test_v1027_optimization_result.json'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_KC_DIR = os.path.join(SCRIPT_DIR, 'public', 'knowledge_cards')

# ── 基线数据 (来自 Phase 1 测试报告 v10.26) ──
BASELINE = {
    '不规则动词卡': {'audit': 84, 'quality': 99, 'note': 'v10.26 无Schema, 仅1样本'},
    '情景对话卡':   {'audit': 99, 'quality': 99, 'note': 'v10.25 专属增强后'},
    '易混词卡':     {'audit': 95, 'quality': 99, 'note': 'v10.26'},
    '易混词陷阱卡': {'audit': 90, 'quality': 95, 'note': 'v10.26 估算'},
    '词汇卡':       {'audit': 96, 'quality': 99, 'note': 'v10.26 对照组'},
    '句型卡':       {'audit': 97, 'quality': 99, 'note': 'v10.26 对照组'},
}

# ── 测试卡片 (优化目标类型 + 对照组) ──
# (type_name, card_full_id, grade_short, optimization_tag)
TEST_CARDS = [
    # P0: 不规则动词卡 — 新增 Schema
    ('不规则动词卡', '英语-六下-05-03', '六下', 'P0'),
    # P1a: 情景对话卡 — 角色气泡对齐 + 单气泡≤6词
    ('情景对话卡',   '英语-三上-01-02', '三上', 'P1a'),
    ('情景对话卡',   '英语-六上-01-05', '六上', 'P1a'),
    # P2: 易混词卡 — 对比色强化
    ('易混词卡',     '英语-三上-03-03', '三上', 'P2'),
    # P2: 易混词陷阱卡 — 对错色差强化
    # 爆款卡需要特殊处理
    ('易混词陷阱卡', '英语-三上-T1-01', '三上', 'P2'),
    # 对照组 — 不应受影响的类型
    ('词汇卡',       '英语-三上-01-01', '三上', 'CTRL'),
    ('句型卡',       '英语-三上-03-02', '三上', 'CTRL'),
]


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
    for i in range(MAX_POLL):
        time.sleep(POLL_INTERVAL)
        elapsed = (i + 1) * POLL_INTERVAL
        try:
            poll_req = urllib.request.Request(
                f'{BASE}/api/task-status/{task_id}',
                headers={'Authorization': f'Bearer {TOKEN}'}
            )
            poll_resp = urllib.request.urlopen(poll_req, timeout=15)
            sr = json.loads(poll_resp.read().decode())
        except Exception as e:
            print(f'    [{elapsed}s] poll error: {e}', flush=True)
            continue

        status = sr.get('status', '')
        progress = sr.get('progress', '')
        if elapsed % 30 == 0 or status in ('done', 'error', 'failed'):
            print(f'    [{elapsed}s] {status} {progress[:80]}', flush=True)

        if status == 'done':
            return sr.get('result', {}), elapsed
        elif status in ('error', 'failed'):
            return {'error': sr.get('result', {}).get('error', str(sr))}, elapsed

    return {'error': 'TIMEOUT'}, MAX_POLL * POLL_INTERVAL


def run_card_test(type_name, card_full_id, grade_short, opt_tag):
    print(f'\n{"=" * 60}', flush=True)
    print(f'卡片类型: {type_name} [{opt_tag}] | ID: {card_full_id} | 年级: {grade_short}', flush=True)
    print(f'{"=" * 60}', flush=True)

    card, gs, semester = find_card(card_full_id, grade_short)
    if not card:
        print(f'  ❌ Card {card_full_id} not found!', flush=True)
        return [{'error': f'Card {card_full_id} not found'}] * ROUNDS, card_full_id, '?'

    card_title = card.get('title', card_full_id)
    card_type = card.get('type', type_name)
    print(f'  标题: {card_title}', flush=True)
    print(f'  类型: {card_type}', flush=True)

    results = []
    for rnd in range(1, ROUNDS + 1):
        print(f'  --- Round {rnd}/{ROUNDS} ---', flush=True)
        t0 = time.time()

        try:
            task_id = submit_task(card, gs, semester)
            print(f'    task_id: {task_id}', flush=True)
        except Exception as e:
            err_msg = str(e)
            if hasattr(e, 'read'):
                try:
                    err_msg = e.read().decode('utf-8', 'replace')[:200]
                except:
                    pass
            print(f'    Submit error: {err_msg}', flush=True)
            results.append({'error': err_msg, 'elapsed': round(time.time() - t0, 1)})
            continue

        result, poll_elapsed = poll_task(task_id)
        result['elapsed'] = round(time.time() - t0, 1)

        if 'error' in result:
            print(f'    ❌ ERROR: {result["error"][:100]}', flush=True)
        else:
            audit = result.get('auditScore', '?')
            quality = result.get('qualityScore', '?')
            eng_audit = result.get('englishAuditScore', '?')
            model = result.get('model', '?')
            print(f'    ✅ audit={audit} quality={quality} eng_audit={eng_audit} model={model} elapsed={result["elapsed"]}s', flush=True)

        results.append(result)

    return results, card_full_id, card_title


def generate_report(all_results):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Build summary
    summary_rows = ''
    type_sections = ''

    for item in all_results:
        type_name = item['type_name']
        card_id = item['card_id']
        card_title = item['card_title']
        opt_tag = item['opt_tag']
        results = item['results']

        successes = [r for r in results if 'error' not in r]
        audit_scores = [r.get('auditScore', 0) for r in successes if isinstance(r.get('auditScore'), (int, float))]
        quality_scores = [r.get('qualityScore', 0) for r in successes if isinstance(r.get('qualityScore'), (int, float))]
        eng_scores = [r.get('englishAuditScore', 0) for r in successes if isinstance(r.get('englishAuditScore'), (int, float))]

        avg_audit = round(sum(audit_scores) / len(audit_scores), 1) if audit_scores else 0
        avg_quality = round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else 0
        avg_eng = round(sum(eng_scores) / len(eng_scores), 1) if eng_scores else 0
        avg_combined = round((avg_audit + avg_quality) / 2, 1) if audit_scores else 0

        # Baseline comparison
        bl = BASELINE.get(type_name, {})
        bl_audit = bl.get('audit', '?')
        bl_quality = bl.get('quality', '?')

        def delta_str(new, old):
            if not isinstance(old, (int, float)):
                return '(N/A)'
            d = round(new - old, 1)
            if d > 0:
                return f'<span style="color:#00b894;font-weight:bold">↑{d}</span>'
            elif d < 0:
                return f'<span style="color:#d63031;font-weight:bold">↓{abs(d)}</span>'
            return f'<span style="color:#636e72">→{d}</span>'

        audit_delta = delta_str(avg_audit, bl_audit)
        quality_delta = delta_str(avg_quality, bl_quality)

        tag_color = {'P0': '#6c5ce7', 'P1a': '#e17055', 'P1b': '#00b894', 'P2': '#fdcb6e', 'CTRL': '#b2bec3'}
        tag_bg = tag_color.get(opt_tag, '#dfe6e9')

        summary_rows += f'''
        <tr>
          <td><span class="tag" style="background:{tag_bg}">{opt_tag}</span> <strong>{type_name}</strong></td>
          <td><small>{card_title[:30]}</small></td>
          <td>{bl_audit}</td>
          <td>{avg_audit} {audit_delta}</td>
          <td>{bl_quality}</td>
          <td>{avg_quality} {quality_delta}</td>
          <td>{avg_eng if avg_eng else '—'}</td>
          <td><strong>{avg_combined}</strong></td>
          <td>{len(successes)}/{ROUNDS}</td>
        </tr>'''

        # Detail section
        detail_rows = ''
        for i, r in enumerate(results):
            rnd = i + 1
            if 'error' in r:
                detail_rows += f'<tr class="error-row"><td>{rnd}</td><td colspan="6" class="error">❌ {str(r["error"])[:120]}</td><td>{r.get("elapsed", "?")}s</td></tr>'
                continue

            img_b64 = r.get('image', '')
            mime = r.get('mimeType', 'image/png')
            audit = r.get('auditScore', '?')
            quality = r.get('qualityScore', '?')
            eng = r.get('englishAuditScore', '—')
            elapsed = r.get('elapsed', '?')
            manifest = r.get('manifest', {})
            title_val = next((v for k, v in manifest.items() if 'TITLE' in k.upper()), '')

            combined = '?'
            try:
                combined = round((float(audit) + float(quality)) / 2, 1)
            except:
                pass

            css = 'pass' if (isinstance(audit, (int, float)) and audit >= 80) else 'warn'
            detail_rows += f'''
            <tr class="{css}-row">
              <td>{rnd}</td>
              <td class="img-cell"><img src="data:{mime};base64,{img_b64}" alt="R{rnd}" /></td>
              <td class="title-cell">{title_val}</td>
              <td class="score">{audit}</td>
              <td class="score">{quality}</td>
              <td class="score">{eng}</td>
              <td class="score combined">{combined}</td>
              <td>{elapsed}s</td>
            </tr>'''

        type_sections += f'''
        <div class="type-section" id="type-{card_id}">
          <h2><span class="tag" style="background:{tag_bg}">{opt_tag}</span> {type_name} <small>({card_title})</small></h2>
          <p class="type-meta">ID: {card_id} | 基线Audit: {bl_audit} → 新Audit: {avg_audit} | 基线Quality: {bl_quality} → 新Quality: {avg_quality}</p>
          <table class="detail-table">
            <thead><tr><th>#</th><th>生成图片</th><th>TITLE</th><th>审计</th><th>质量</th><th>英8维</th><th>综合</th><th>耗时</th></tr></thead>
            <tbody>{detail_rows}</tbody>
          </table>
        </div>'''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>v10.27 优化对比测试报告</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, 'Segoe UI', 'Microsoft YaHei', sans-serif; max-width: 1500px; margin: 20px auto; padding: 0 20px; background: #f0f2f5; color: #333; }}
  h1 {{ color: #1a1a2e; border-bottom: 3px solid #6c5ce7; padding-bottom: 12px; }}
  h2 {{ color: #2d3436; border-left: 4px solid #6c5ce7; padding-left: 12px; margin-top: 30px; }}
  h2 small {{ color: #636e72; font-weight: normal; font-size: 0.7em; }}
  .tag {{ padding: 2px 8px; border-radius: 4px; color: white; font-size: 0.8em; font-weight: bold; }}
  .meta {{ background: #fff; padding: 18px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
  .meta p {{ margin: 4px 0; font-size: 0.95em; }}
  .opt-legend {{ background: #fff; padding: 15px 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); display: flex; gap: 15px; flex-wrap: wrap; }}
  .opt-legend .item {{ display: flex; align-items: center; gap: 5px; font-size: 0.9em; }}
  .summary-table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 30px; }}
  .summary-table th {{ background: #6c5ce7; color: white; padding: 12px 10px; text-align: center; font-size: 0.85em; }}
  .summary-table td {{ padding: 10px 8px; text-align: center; border-bottom: 1px solid #eee; font-size: 0.9em; }}
  .type-section {{ background: #fff; border-radius: 10px; padding: 20px; margin-bottom: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
  .type-meta {{ color: #636e72; font-size: 0.9em; margin: -5px 0 15px 16px; }}
  .detail-table {{ width: 100%; border-collapse: collapse; }}
  .detail-table th {{ background: #dfe6e9; color: #2d3436; padding: 10px 8px; text-align: center; font-size: 0.85em; }}
  .detail-table td {{ padding: 8px 6px; text-align: center; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }}
  .img-cell img {{ max-width: 200px; max-height: 280px; border-radius: 6px; box-shadow: 0 2px 6px rgba(0,0,0,0.12); cursor: pointer; transition: transform 0.3s; }}
  .img-cell img:hover {{ transform: scale(2.5); z-index: 100; position: relative; }}
  .title-cell {{ max-width: 140px; word-break: break-all; font-size: 0.8em; text-align: left; }}
  .score {{ font-size: 1.1em; font-weight: bold; }}
  .combined {{ color: #6c5ce7; }}
  .pass-row {{ background: #f0fff4; }}
  .warn-row {{ background: #fffaf0; }}
  .error-row {{ background: #fff5f5; }}
  .error {{ color: #d63031; text-align: left; font-size: 0.85em; }}
  .footer {{ text-align: center; color: #b2bec3; margin-top: 30px; font-size: 0.8em; }}
</style>
</head>
<body>
<h1>🧪 v10.27 优化对比测试报告</h1>
<div class="meta">
  <p><strong>测试范围:</strong> v10.27 优化涉及的 4 项修改 + 2 个对照组</p>
  <p><strong>基线版本:</strong> v10.26 Phase 1 报告数据</p>
  <p><strong>测试版本:</strong> v10.27 (P0 不规则动词卡Schema + P1a 情景对话对齐 + P1b 字数收紧 + P2 对比强化)</p>
  <p><strong>每张:</strong> {ROUNDS} 轮 | <strong>测试时间:</strong> {now}</p>
</div>

<div class="opt-legend">
  <div class="item"><span class="tag" style="background:#6c5ce7">P0</span> 不规则动词卡 Schema 注册</div>
  <div class="item"><span class="tag" style="background:#e17055">P1a</span> 情景对话卡 角色-气泡对齐</div>
  <div class="item"><span class="tag" style="background:#fdcb6e;color:#333">P2</span> 易混词/陷阱卡 对比色强化</div>
  <div class="item"><span class="tag" style="background:#b2bec3">CTRL</span> 对照组(不应受影响)</div>
</div>

<h2>📊 v10.26 → v10.27 对比总览</h2>
<table class="summary-table">
  <thead>
    <tr><th>优化项 · 类型</th><th>样本</th><th>基线Audit</th><th>v10.27 Audit</th><th>基线Quality</th><th>v10.27 Quality</th><th>英8维</th><th>综合</th><th>成功率</th></tr>
  </thead>
  <tbody>{summary_rows}</tbody>
</table>

{type_sections}

<div class="footer">v10.27 优化对比测试 | {now} | P0+P1a+P1b+P2</div>
</body>
</html>'''
    return html


def main():
    print('=' * 60, flush=True)
    print('v10.27 优化对比测试', flush=True)
    print(f'测试卡: {len(TEST_CARDS)} 张  每张 {ROUNDS} 轮  总计 {len(TEST_CARDS) * ROUNDS} 轮', flush=True)
    print('=' * 60, flush=True)

    all_results = []
    grand_start = time.time()

    for idx, (type_name, card_id, grade, opt_tag) in enumerate(TEST_CARDS, 1):
        print(f'\n\n{"#" * 60}', flush=True)
        print(f'# [{idx}/{len(TEST_CARDS)}] {opt_tag}: {type_name}', flush=True)
        print(f'{"#" * 60}', flush=True)

        results, cid, ctitle = run_card_test(type_name, card_id, grade, opt_tag)
        all_results.append({
            'type_name': type_name,
            'card_id': cid,
            'card_title': ctitle,
            'opt_tag': opt_tag,
            'results': results,
        })

        successes = [r for r in results if 'error' not in r]
        audit_scores = [r.get('auditScore', 0) for r in successes if isinstance(r.get('auditScore'), (int, float))]
        avg_a = round(sum(audit_scores) / len(audit_scores), 1) if audit_scores else 0
        print(f'\n  📊 {type_name} [{opt_tag}]: {len(successes)}/{ROUNDS} 成功, avg_audit={avg_a}', flush=True)

    grand_elapsed = round(time.time() - grand_start, 1)
    print(f'\n\n{"=" * 60}', flush=True)
    print(f'全部完成! 总耗时: {grand_elapsed}s ({round(grand_elapsed/60, 1)}min)', flush=True)

    # Generate HTML report
    print(f'\n生成报告: {REPORT_FILE}', flush=True)
    html = generate_report(all_results)
    report_path = os.path.join(SCRIPT_DIR, REPORT_FILE)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'Report saved: {report_path}', flush=True)

    # Save JSON (without images)
    json_path = os.path.join(SCRIPT_DIR, JSON_FILE)
    json_out = []
    for t in all_results:
        tj = {
            'type_name': t['type_name'],
            'card_id': t['card_id'],
            'card_title': t['card_title'],
            'opt_tag': t['opt_tag'],
            'results': [],
        }
        for r in t['results']:
            jr = {k: v for k, v in r.items() if k != 'image'}
            if 'image' in r:
                jr['has_image'] = True
                jr['image_size'] = len(r['image'])
            tj['results'].append(jr)
        json_out.append(tj)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_out, f, ensure_ascii=False, indent=2)
    print(f'JSON saved: {json_path}', flush=True)

    # Grand summary
    all_audit = []
    all_quality = []
    for t in all_results:
        for r in t['results']:
            if 'error' not in r:
                if isinstance(r.get('auditScore'), (int, float)):
                    all_audit.append(r['auditScore'])
                if isinstance(r.get('qualityScore'), (int, float)):
                    all_quality.append(r['qualityScore'])

    g_a = round(sum(all_audit) / len(all_audit), 1) if all_audit else 0
    g_q = round(sum(all_quality) / len(all_quality), 1) if all_quality else 0
    print(f'\n全局: avg_audit={g_a} avg_quality={g_q}', flush=True)
    print(f'总耗时: {grand_elapsed}s ({round(grand_elapsed/60, 1)}min)', flush=True)
    print(f'{"=" * 60}', flush=True)


if __name__ == '__main__':
    main()
