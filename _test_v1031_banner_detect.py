#!/usr/bin/env python3
"""v10.31 Banner视觉检测验证 v3
==================================
方向A + 方向B:
  A: typed_quality_score 已包含「无标题栏」维度（content_quality.py）
  B: 独立的视觉Banner检测（YES/NO），用 Gemini Vision 单独判断
- 14张卡片: 三年级6 + 四年级2 + 五年级3 + 六年级3
- 7种英语卡片类型全覆盖
- 每张卡片额外做一次Banner视觉检测（独立于质量评分）
"""
import json, time, urllib.request, os, base64, datetime, sqlite3, shutil, re

BASE = "http://localhost:3000"
TOKEN = "8ebz1cyLh1tEkhzHy0P5cduuuO2E94nbhtjl2xtOmtXeYQ4IIQAaNxy4wk9xcSRN"
POLL_INTERVAL = 10
MAX_POLL = 240          # 最多等 40 分钟
REPORT_HTML = "_test_v1031_banner_detect.html"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_KC_DIR = os.path.join(SCRIPT_DIR, 'public', 'knowledge_cards')
DB_PATH = os.path.join(SCRIPT_DIR, 'optimizer.db')
IMG_DIR = os.path.join(SCRIPT_DIR, 'card_best_images')

# ══════ API Key (for banner detection direct Gemini call) ══════
GEMINI_API_KEYS = []
_key_path = os.path.join(SCRIPT_DIR, 'api_key.txt')
if os.path.exists(_key_path):
    with open(_key_path, encoding='utf-8') as f:
        for line in f:
            m = re.match(r'GEMINI_API_KEY\s*=\s*(.+)', line.strip())
            if m:
                raw = m.group(1).strip()
                GEMINI_API_KEYS = [k.strip() for k in raw.split(',') if k.strip()]
                break
if not GEMINI_API_KEYS:
    print("⚠️ 未找到 api_key.txt 中的 GEMINI_API_KEY，Banner检测将使用 fallback")

_key_idx = 0
def _next_api_key():
    global _key_idx
    if not GEMINI_API_KEYS:
        return ''
    k = GEMINI_API_KEYS[_key_idx % len(GEMINI_API_KEYS)]
    _key_idx += 1
    return k


# ══════ 14张测试卡 (full_id, grade_short, tag, card_type_cn) ══════
TEST_CARDS = [
    # ── 三年级 6张 ──
    ('英语-三上-01-01', '三上', '词汇A', '词汇卡'),
    ('英语-三上-03-02', '三上', '句型A', '句型卡'),
    ('英语-三上-04-02', '三上', '语法A', '语法卡'),
    ('英语-三上-01-03', '三上', '拼读A', '自然拼读卡'),
    ('英语-三上-01-02', '三上', '对话A', '情景对话卡'),
    ('英语-三上-03-03', '三上', '易混A', '易混词卡'),
    # ── 四年级 2张 (新增) ──
    ('英语-四上-01-03', '四上', '拼读C', '自然拼读卡'),
    ('英语-四下-06-06', '四下', '易混C', '易混词卡'),
    # ── 五年级 3张 (新增) ──
    ('英语-五上-06-06', '五上', '对话C', '情景对话卡'),
    ('英语-五下-03-02', '五下', '语法C', '语法卡'),
    ('英语-五下-03-04', '五下', '易混D', '易混词卡'),
    # ── 六年级 3张 (新增) ──
    ('英语-六上-06-02', '六上', '语法D', '语法卡'),
    ('英语-六下-03-04', '六下', '易混E', '易混词卡'),
    ('英语-六下-05-03', '六下', '不规则', '不规则动词卡'),
]


# ══════ Banner视觉检测 (方向B) ══════

BANNER_DETECT_PROMPT = """看这张知识卡片图片的**顶部区域**。

请判断：卡片最顶部是否有一条"深色横幅/渐变条"，上面写着白色中文标题（比如"句型卡：XXX"、"词汇卡"、"语法卡"、"自然拼读卡"、"情景对话卡"、"易混词卡"等）？

⚠️ 判断标准：
- 深色背景横幅（黑/深蓝/深绿/深紫等深色渐变条）+ 白色中文大字 = 有Banner
- 浅色/白色背景 + 彩色小图标/装饰 = 没有Banner（这不算）
- 底部的暖色口诀条/标语条 = 不算Banner（只看顶部）

只输出JSON（不要代码块标记）：
{"has_banner": true或false, "top_description": "简述卡片顶部区域的视觉样子(20字以内)", "confidence": "high或medium或low"}"""


def detect_banner(image_b64, mime_type='image/png'):
    """
    方向B: 独立视觉Banner检测。
    直接调用 Gemini Vision API，判断卡片顶部是否有深色标题栏。
    返回: {'has_banner': bool, 'top_description': str, 'confidence': str, 'error': str}
    """
    api_key = _next_api_key()
    if not api_key:
        return {'has_banner': None, 'top_description': 'no API key', 'confidence': 'none', 'error': 'no key'}

    api_base = 'https://generativelanguage.googleapis.com/v1beta'
    model = 'gemini-2.5-flash'
    url = f'{api_base}/models/{model}:generateContent?key={api_key}'

    body = {
        'contents': [{'role': 'user', 'parts': [
            {'text': BANNER_DETECT_PROMPT},
            {'inlineData': {'mimeType': mime_type, 'data': image_b64}}
        ]}],
        'generationConfig': {
            'maxOutputTokens': 512,
            'temperature': 0.1,
            'thinkingConfig': {'thinkingBudget': 512}
        }
    }

    for attempt in range(2):
        if attempt > 0:
            # retry with different key
            api_key = _next_api_key()
            url = f'{api_base}/models/{model}:generateContent?key={api_key}'
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            resp = urllib.request.urlopen(req, timeout=30)
            data = json.loads(resp.read())
            candidates = data.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                all_text = ''
                for part in parts:
                    if 'text' in part and not part.get('thought'):
                        all_text += part['text']
                if all_text:
                    json_match = re.search(r'\{[\s\S]*?\}', all_text.strip())
                    if json_match:
                        result = json.loads(json_match.group())
                        return result
        except Exception as e:
            if attempt == 0:
                time.sleep(2)
                continue
            return {'has_banner': None, 'top_description': '', 'confidence': 'none', 'error': str(e)[:100]}

    return {'has_banner': None, 'top_description': '', 'confidence': 'none', 'error': 'all attempts failed'}


# ══════ 工具函数 ══════

def _extract_no_banner_score(quality_detail):
    """从 quality_detail 中提取 NoBanner 分数（兼容 typed 和 generic 两种格式）"""
    # 格式1: 通用路径 — quality_detail = {"no_banner": 15, ...}
    nb = quality_detail.get('no_banner')
    if isinstance(nb, (int, float)):
        return nb
    # 格式2: typed路径 — quality_detail = {"dimensions": {"无标题栏": {"score": 15, "max": 15}}}
    dims = quality_detail.get('dimensions', {})
    if isinstance(dims, dict):
        nb_dim = dims.get('无标题栏', {})
        if isinstance(nb_dim, dict) and 'score' in nb_dim:
            return nb_dim['score']
    return '?'


def find_card(card_full_id, grade_short):
    """从 public/knowledge_cards/ 中查找卡片 JSON"""
    for root, _, files in os.walk(PUBLIC_KC_DIR):
        for fn in sorted(files):
            if not fn.endswith('.json'):
                continue
            fp = os.path.join(root, fn)
            with open(fp, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict) or 'units' not in data:
                continue
            if data.get('grade_short', '') != grade_short:
                continue
            semester = data.get('semester', '上册')
            for unit in data.get('units', []):
                if isinstance(unit, dict) and 'cards' in unit:
                    for c in unit['cards']:
                        if c.get('full_id') == card_full_id:
                            return c, grade_short, semester
    return None, None, None


def api_post(path, body):
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        f"{BASE}{path}", data=data,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {TOKEN}"}
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode('utf-8'))


def api_get(path):
    req = urllib.request.Request(
        f"{BASE}{path}",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode('utf-8'))


def clear_cache(card_ids):
    """直接删除 optimizer.db 中的缓存记录 + 磁盘文件"""
    if not os.path.exists(DB_PATH):
        print("  (No optimizer.db found, skip)")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    for cid in card_ids:
        row = conn.execute(
            "SELECT card_id, image_path FROM card_best_images WHERE card_id = ?",
            (cid,)
        ).fetchone()
        if row:
            img_path = row['image_path']
            if img_path and os.path.exists(img_path):
                os.remove(img_path)
            prompt_path = os.path.join(IMG_DIR, f"{cid}.prompt")
            if os.path.exists(prompt_path):
                os.remove(prompt_path)
            conn.execute("DELETE FROM card_best_images WHERE card_id = ?", (cid,))
            print(f"  ✅ {cid}: cache cleared")
        else:
            print(f"  ⏭️  {cid}: no cache")
    conn.commit()
    conn.close()


def run_one(card_full_id, grade_short, tag, card_type_cn):
    """生成一张卡片（异步API + 轮询）+ Banner视觉检测"""
    card, gs, semester = find_card(card_full_id, grade_short)
    if not card:
        return {'tag': tag, 'error': f'Card not found: {card_full_id}'}

    card_type = card.get('type', card_type_cn)
    title = card.get('title', '')
    print(f"\n  [{tag}] {card_type} | {card_full_id} | {title[:40]}")

    body = {
        "card": card,
        "subject": "英语",
        "grade": gs,
        "semester": semester,
    }

    t0 = time.time()
    try:
        resp = api_post("/api/generate-card-image-v3-async", body)
    except Exception as e:
        return {'tag': tag, 'error': f'API call failed: {e}'}

    task_id = resp.get('taskId', '') or resp.get('task_id', '')
    if not task_id:
        return {'tag': tag, 'error': f'No taskId: {resp}'}

    for _ in range(MAX_POLL):
        time.sleep(POLL_INTERVAL)
        elapsed = int(time.time() - t0)
        try:
            st = api_get(f"/api/task-status/{task_id}")
        except Exception as e:
            print(f"    [{elapsed}s] poll error: {e}")
            continue

        status = st.get('status', '')
        if status == 'done':
            result = st.get('result', {})
            audit = result.get('auditScore', 0)
            quality_detail = result.get('qualityDetail', {})
            quality = quality_detail.get('total', result.get('qualityScore', 0))
            text_model = result.get('textModel', '?')
            image_model = result.get('model', '?')
            image_b64 = result.get('image', '')
            mime = result.get('mimeType', 'image/png')
            rounds = result.get('rounds', 0)
            pipeline = result.get('pipeline', [])
            elapsed = int(time.time() - t0)

            # 检测缓存状态
            cache_status = 'fresh'
            for log_line in pipeline:
                ll = str(log_line).lower()
                if 'skip-all' in ll:
                    cache_status = 'skip-all'; break
                elif 'skip-fresh' in ll or '跳过从头生成' in str(log_line):
                    cache_status = 'skip-fresh'; break
                elif '无历史缓存' in str(log_line):
                    cache_status = 'cold-start'; break

            passed = audit >= 80 and quality >= 60
            nb_score = _extract_no_banner_score(quality_detail)
            eng_sp = quality_detail.get('english_specific', '?')

            # ── 方向B: 独立Banner视觉检测 ──
            banner_result = {'has_banner': None, 'top_description': 'skipped', 'confidence': 'none'}
            if image_b64:
                print(f"    🔍 Banner视觉检测...", end='', flush=True)
                banner_result = detect_banner(image_b64, mime)
                hb = banner_result.get('has_banner')
                td = banner_result.get('top_description', '')[:30]
                conf = banner_result.get('confidence', '?')
                marker = '🚫有Banner!' if hb else ('✅无Banner' if hb is False else '❓未知')
                print(f" {marker} ({conf}) — {td}")

            print(f"    {'✅' if passed else '❌'} A={audit} Q={quality} NoBanner={nb_score} EngSp={eng_sp} "
                  f"| {cache_status} | {elapsed}s")
            if quality_detail.get('comment'):
                print(f"    💬 {str(quality_detail['comment'])[:120]}")

            return {
                'tag': tag, 'card_id': card_full_id, 'card_type': card_type,
                'grade': grade_short, 'title': title,
                'audit': audit, 'quality': quality, 'quality_detail': quality_detail,
                'cache_status': cache_status, 'elapsed': elapsed,
                'text_model': text_model, 'image_model': image_model,
                'image_b64': image_b64, 'mime': mime, 'rounds': rounds,
                'passed': passed,
                'banner_detect': banner_result,  # 方向B结果
            }
        elif status == 'error':
            err = st.get('error', st.get('result', {}).get('error', '?'))
            print(f"    ❌ ERROR: {err}")
            return {'tag': tag, 'error': str(err)[:200]}
        else:
            prog = st.get('progress', '')
            print(f"    [{elapsed}s] {status} {prog[:60]}", end='\r')

    return {'tag': tag, 'error': 'timeout'}


def build_html(results):
    """生成包含7维Quality + Banner检测 + 视觉检测结果的HTML报告"""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    total = len(results)
    ok_results = [r for r in results if 'error' not in r]
    passed_count = sum(1 for r in ok_results if r.get('passed'))
    avg_audit = sum(r['audit'] for r in ok_results) / max(len(ok_results), 1)
    avg_quality = sum(r['quality'] for r in ok_results) / max(len(ok_results), 1)

    # NoBanner 从 typed scorer 或 generic scorer 中提取
    nb_scores = [_extract_no_banner_score(r['quality_detail']) for r in ok_results]
    nb_valid = [s for s in nb_scores if isinstance(s, (int, float))]
    avg_nb = sum(nb_valid) / max(len(nb_valid), 1) if nb_valid else 0

    # Banner视觉检测统计
    banner_results = [r.get('banner_detect', {}) for r in ok_results]
    banner_no = sum(1 for b in banner_results if b.get('has_banner') is False)
    banner_yes = sum(1 for b in banner_results if b.get('has_banner') is True)
    banner_unknown = len(ok_results) - banner_no - banner_yes

    # ── 卡片行 ──
    cards_html = ''
    for r in results:
        if 'error' in r:
            cards_html += f'''<div class="card" style="border-left:4px solid #e74c3c">
  <div class="card-header"><span class="card-title">{r['tag']}</span>
  <span class="badge badge-fail">ERROR</span></div>
  <pre style="color:#d32f2f;font-size:13px;padding:12px">{r.get('error','?')[:200]}</pre></div>\n'''
            continue

        qd = r.get('quality_detail', {})
        nb_score = _extract_no_banner_score(qd)
        nb_class = 'nb-ok' if isinstance(nb_score, (int, float)) and nb_score >= 10 else 'nb-alert'
        badge = '<span class="badge badge-pass">PASS</span>' if r['passed'] else '<span class="badge badge-fail">FAIL</span>'

        # Banner视觉检测结果
        bd = r.get('banner_detect', {})
        hb = bd.get('has_banner')
        if hb is True:
            banner_badge = '<span class="badge" style="background:#e74c3c;color:white">🚫 有Banner</span>'
        elif hb is False:
            banner_badge = '<span class="badge" style="background:#27ae60;color:white">✅ 无Banner</span>'
        else:
            banner_badge = '<span class="badge" style="background:#95a5a6;color:white">❓ 未知</span>'
        banner_desc = bd.get('top_description', '')[:40]
        banner_conf = bd.get('confidence', '?')

        img_html = ''
        if r.get('image_b64'):
            img_html = f'<img class="card-img" src="data:{r["mime"]};base64,{r["image_b64"]}">'

        def sb(val, maxv, color='#3498db'):
            pct = min(100, 100 * val / max(maxv, 1)) if isinstance(val, (int, float)) else 0
            return f'<div class="score-bar"><div class="score-fill" style="width:{pct}%;background:{color}"></div></div>'

        # 尝试解析 typed 维度（dimensions dict）和 generic 维度
        dims = qd.get('dimensions', {})
        dim_rows = ''
        if isinstance(dims, dict) and dims:
            # Typed scorer format: {维度名: {score, max, reason}}
            for dname, dval in dims.items():
                if isinstance(dval, dict):
                    dscore = dval.get('score', 0)
                    dmax = dval.get('max', 15)
                    dreason = dval.get('reason', '')[:60]
                    dim_rows += f'<tr><td>{dname}({dmax})</td><td>{dscore} {sb(dscore, dmax)} <span style="color:#888;font-size:11px">{dreason}</span></td></tr>\n'
        else:
            # Generic scorer format: {teaching: 15, text_accuracy: 15, ...}
            generic_dims = [
                ('教学清晰度', 'teaching', 15),
                ('文字准确性', 'text_accuracy', 15),
                ('视觉美感', 'visual', 15),
                ('布局合理性', 'layout', 15),
                ('可收藏感', 'saveable', 15),
                ('🚫无Banner', 'no_banner', 15),
                ('英语专项', 'english_specific', 10),
            ]
            for label, key, maxv in generic_dims:
                val = qd.get(key, '?')
                color = '#e74c3c' if key == 'no_banner' and isinstance(val, (int, float)) and val < 10 else '#3498db'
                dim_rows += f'<tr><td>{label}({maxv})</td><td>{val} {sb(val, maxv, color)}</td></tr>\n'

        cards_html += f'''<div class="card">
  <div class="card-header">
    <span class="card-title">{r['tag']} | {r['card_type']} | {r['grade']} — {r['card_id']}</span>
    {badge} {banner_badge}
  </div>
  <div class="card-body">
    {img_html}
    <div class="card-info">
      <table>
        <tr><td>Audit</td><td><b>{r['audit']}</b> {sb(r['audit'], 100, '#27ae60')}</td></tr>
        <tr><td>Quality</td><td><b>{r['quality']}</b> {sb(r['quality'], 100, '#3498db')}</td></tr>
        {dim_rows}
        <tr><td>🔍Banner检测</td><td>{banner_badge} <span style="font-size:12px;color:#666">{banner_desc} (confidence:{banner_conf})</span></td></tr>
        <tr><td>缓存/轮次</td><td>{r.get('cache_status','?')} | {r.get('rounds','?')}轮 | {r.get('elapsed',0)}s</td></tr>
        <tr><td>Models</td><td style="font-size:0.82em">📝{r.get('text_model','?')} 🎨{r.get('image_model','?')}</td></tr>
      </table>
      <div class="comment">{str(qd.get('comment', '无评价'))[:300]}</div>
    </div>
  </div>
</div>\n'''

    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>v10.31 Banner检测验证 — {now}</title>
<style>
body {{ font-family: 'Segoe UI', system-ui, sans-serif; max-width: 1400px; margin: 0 auto; padding: 20px; background: #f0f2f5; color: #222; }}
.header {{ background: linear-gradient(135deg, #e74c3c, #c0392b); color: white; padding: 24px; border-radius: 12px; margin-bottom: 20px; }}
.header h1 {{ margin: 0; font-size: 24px; }}
.header .stats {{ display: flex; gap: 20px; margin-top: 12px; flex-wrap: wrap; }}
.header .stat {{ background: rgba(255,255,255,0.15); padding: 8px 16px; border-radius: 8px; }}
.stat-label {{ font-size: 12px; opacity: 0.8; }}
.stat-value {{ font-size: 20px; font-weight: bold; }}
.card {{ background: white; border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
.card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap: 8px; flex-wrap: wrap; }}
.card-title {{ font-weight: bold; font-size: 16px; }}
.badge {{ padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }}
.badge-pass {{ background: #27ae60; color: white; }}
.badge-fail {{ background: #e74c3c; color: white; }}
.card-body {{ display: flex; gap: 16px; }}
.card-img {{ max-width: 350px; max-height: 500px; border-radius: 8px; border: 1px solid #eee; }}
.card-info {{ flex: 1; font-size: 13px; }}
.card-info table {{ width: 100%; border-collapse: collapse; }}
.card-info td {{ padding: 4px 8px; border-bottom: 1px solid #f0f0f0; }}
.card-info td:first-child {{ color: #666; width: 130px; }}
.score-bar {{ height: 8px; background: #eee; border-radius: 4px; overflow: hidden; display: inline-block; width: 100px; vertical-align: middle; margin-left: 6px; }}
.score-fill {{ height: 100%; border-radius: 4px; }}
.comment {{ font-size: 12px; color: #555; margin-top: 8px; padding: 8px; background: #f9f9f9; border-radius: 6px; white-space: pre-wrap; }}
.nb-alert {{ color: #e74c3c; font-weight: bold; font-size: 1.1em; }}
.nb-ok {{ color: #27ae60; font-weight: bold; font-size: 1.1em; }}
.banner-summary {{ background: linear-gradient(135deg, #2c3e50, #34495e); color: white; padding: 20px; border-radius: 12px; margin-bottom: 20px; }}
.banner-summary h2 {{ margin: 0 0 12px 0; font-size: 18px; }}
.banner-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; }}
.banner-stat {{ text-align: center; padding: 12px; border-radius: 8px; }}
</style></head><body>

<div class="header">
  <h1>🔍 v10.31 Banner检测验证 (方向A+B)</h1>
  <p style="opacity:0.8;margin:4px 0">测试时间: {now} | {total}张卡 | 年级: 三~六 | 类型: 7种</p>
  <div class="stats">
    <div class="stat"><div class="stat-label">通过率</div><div class="stat-value">{passed_count}/{len(ok_results)} ({100*passed_count//max(len(ok_results),1)}%)</div></div>
    <div class="stat"><div class="stat-label">平均Audit</div><div class="stat-value">{avg_audit:.0f}</div></div>
    <div class="stat"><div class="stat-label">平均Quality</div><div class="stat-value">{avg_quality:.1f}</div></div>
    <div class="stat"><div class="stat-label">NoBanner均分</div><div class="stat-value">{avg_nb:.1f}</div></div>
  </div>
</div>

<div class="banner-summary">
  <h2>🔍 方向B: 独立Banner视觉检测结果</h2>
  <p style="opacity:0.8;margin:0 0 12px 0">每张卡片由 Gemini Vision 单独判断顶部是否有深色Banner标题栏</p>
  <div class="banner-grid">
    <div class="banner-stat" style="background:rgba(39,174,96,0.3)">
      <div style="font-size:28px;font-weight:bold">{banner_no}</div>
      <div style="font-size:12px">✅ 无Banner</div>
    </div>
    <div class="banner-stat" style="background:rgba(231,76,60,0.3)">
      <div style="font-size:28px;font-weight:bold">{banner_yes}</div>
      <div style="font-size:12px">🚫 有Banner</div>
    </div>
    <div class="banner-stat" style="background:rgba(149,165,166,0.3)">
      <div style="font-size:28px;font-weight:bold">{banner_unknown}</div>
      <div style="font-size:12px">❓ 未知</div>
    </div>
    <div class="banner-stat" style="background:rgba(52,152,219,0.3)">
      <div style="font-size:28px;font-weight:bold">{banner_no}/{len(ok_results)}</div>
      <div style="font-size:12px">去Banner成功率</div>
    </div>
  </div>
</div>

{cards_html}

</body></html>'''

    path = os.path.join(SCRIPT_DIR, REPORT_HTML)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\n📄 Report saved: {path}")
    return path


# ── MAIN ──
if __name__ == '__main__':
    print("=" * 70)
    print("  v10.31 Banner检测验证 (方向A+B)")
    print(f"  {len(TEST_CARDS)} 张卡, 1 轮, 清缓存")
    print(f"  方向A: typed质量评分含「无标题栏」维度")
    print(f"  方向B: 独立Gemini Vision Banner检测(YES/NO)")
    print(f"  API Keys: {len(GEMINI_API_KEYS)} 个")
    print("=" * 70)

    # Step 0: 清除缓存
    print("\n🗑️  Step 0: 清除选中卡片的缓存...")
    card_ids = [c[0] for c in TEST_CARDS]
    clear_cache(card_ids)

    # Step 1: 生成所有卡片 + Banner检测
    print(f"\n🔄 Step 1: 生成 {len(TEST_CARDS)} 张卡片 + Banner视觉检测...")
    all_results = []
    for card_id, gs, tag, ct in TEST_CARDS:
        r = run_one(card_id, gs, tag, ct)
        all_results.append(r)

    # Step 2: 生成报告
    print(f"\n📊 Step 2: 生成 HTML 报告...")
    report_path = build_html(all_results)

    # Copy to public/
    pub_path = os.path.join(SCRIPT_DIR, 'public', REPORT_HTML)
    shutil.copy2(report_path, pub_path)
    print(f"📂 Copied to: {pub_path}")

    # Summary
    ok_results = [r for r in all_results if 'error' not in r]
    errors = [r for r in all_results if 'error' in r]
    passed = sum(1 for r in ok_results if r.get('passed'))
    avg_a = sum(r['audit'] for r in ok_results) / max(len(ok_results), 1)
    avg_q = sum(r['quality'] for r in ok_results) / max(len(ok_results), 1)

    nb_scores = [_extract_no_banner_score(r['quality_detail']) for r in ok_results]
    nb_valid = [s for s in nb_scores if isinstance(s, (int, float))]
    avg_nb = sum(nb_valid) / max(len(nb_valid), 1) if nb_valid else 0

    banner_no = sum(1 for r in ok_results if r.get('banner_detect', {}).get('has_banner') is False)
    banner_yes = sum(1 for r in ok_results if r.get('banner_detect', {}).get('has_banner') is True)

    print(f"\n{'='*70}")
    print(f"  🏁 生成结果: {passed}/{len(ok_results)} 通过 | {len(errors)} 错误")
    print(f"  📊 平均: Audit={avg_a:.0f}  Quality={avg_q:.1f}  NoBanner={avg_nb:.1f}")
    print(f"  🔍 Banner检测: ✅无Banner={banner_no}  🚫有Banner={banner_yes}  去Banner率={banner_no}/{len(ok_results)}")
    print(f"  📄 报告: {REPORT_HTML}")
    print(f"  🌐 URL: {BASE}/{REPORT_HTML}")
    print(f"{'='*70}")
