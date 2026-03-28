"""
P3: 端到端 Gemini 集成测试 — 验证 v9.2 全链路真实效果。

流程:
  1. 加载 API Key
  2. 选 3 张真实卡片 (1 数学 + 2 英语)
  3. 对每张卡: Step 1 调 Gemini 生成 prompt → 用 v9.2 审计器打分
  4. 对比「有 Schema 增强」vs「无增强(baseline)」的审计差异

注意: 仅调用 TEXT_MODEL (gemini-2.5-flash)，不生成图片，API 成本极低。
"""

import json
import os
import sys
import time

# ── 加载 API Key ──
API_KEYS = []
key_file = os.path.join(os.path.dirname(__file__), 'api_key.txt')
with open(key_file) as f:
    for line in f:
        if line.startswith('GEMINI_API_KEY='):
            keys_str = line.split('=', 1)[1].strip()
            API_KEYS = [k.strip() for k in keys_str.split(',') if k.strip()]

if not API_KEYS:
    print('ERROR: No API keys found in api_key.txt')
    sys.exit(1)

print(f'Loaded {len(API_KEYS)} API key(s): {API_KEYS[0][:12]}...')

# ── Imports ──
from generate_card_images_v3 import generate_image_prompt
from skill_schema import get_skill_schema
from prompt_builder import build_skill_enhanced_prompt, get_visual_strategy
from prompt_auditor import audit_prompt, format_audit_summary
try:
    from english_card_auditor import is_english_card, rule_audit_english
    HAS_ENG = True
except ImportError:
    HAS_ENG = False

# ── 真实卡片数据 ──
CARDS_DIR = os.path.join(os.path.dirname(__file__), 'knowledge_cards')


def load_card(filename, unit_idx=0, card_idx=0):
    """从 JSON 文件加载一张卡片"""
    path = os.path.join(CARDS_DIR, filename)
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    units = data.get('units', [])
    if unit_idx < len(units):
        cards = units[unit_idx].get('cards', [])
        if card_idx < len(cards):
            return cards[card_idx], data.get('subject', ''), data.get('grade', ''), data.get('semester', '')
    return None, '', '', ''


# 选择 3 张测试卡
TEST_CASES = [
    # (filename, unit_idx, card_idx, label)
    ('小学/数学_三下.json', 0, 0, '数学方法卡'),
    ('小学/英语_四上.json', 0, 0, '英语词汇卡'),
    ('小学/英语_四上.json', 2, 0, '英语语法卡'),
]


def run_e2e():
    print()
    print('=' * 60)
    print('  P3: 端到端 Gemini 集成测试')
    print('=' * 60)
    print()

    results = []

    for fname, uidx, cidx, label in TEST_CASES:
        card, subject, grade, semester = load_card(fname, uidx, cidx)
        if not card:
            print(f'[{label}] SKIP: 无法加载 {fname}')
            continue

        card_type = card.get('type', '')
        title = card.get('title', '')
        print(f'── [{label}] {card_type}: {title}')
        print(f'   Source: {fname} unit={uidx} card={cidx}')

        # ── A: Schema 检查 ──
        schema = get_skill_schema(card_type)
        has_schema = schema is not None
        print(f'   Schema: {"✅ " + card_type if has_schema else "⏭️ 未注册"}')

        # ── B: 生成增强 prompt 段 (本地，不调 API) ──
        enhanced_segment = ''
        if has_schema:
            enhanced_segment = build_skill_enhanced_prompt(card_type, card, subject, grade, semester)
            print(f'   Enhanced段: {len(enhanced_segment)}字')

        # ── C: 调 Gemini Step 1 生成 prompt (真实 API) ──
        print(f'   调用 Gemini Step 1 (TEXT_MODEL)...')
        t0 = time.time()
        try:
            prompt_text, manifest = generate_image_prompt(
                card, subject, grade, semester,
                API_KEYS[0], all_keys=API_KEYS
            )
            elapsed = time.time() - t0
            print(f'   ✅ Gemini 返回 {len(prompt_text)}字 prompt, {len(manifest)}个 manifest | {elapsed:.1f}s')
        except Exception as e:
            elapsed = time.time() - t0
            print(f'   ❌ Gemini 调用失败 ({elapsed:.1f}s): {e}')
            results.append({'label': label, 'card_type': card_type, 'error': str(e)})
            continue

        # ── D: 审计 Gemini 输出的 prompt ──
        audit = audit_prompt(prompt_text, card_type, card, manifest)
        summary = format_audit_summary(audit)
        print(f'   审计: {summary}')

        # 显示问题
        for iss in audit.issues[:5]:
            sev = {'high': '🔴', 'medium': '🟡', 'low': '🔵'}.get(iss.severity, '⚪')
            print(f'     {sev} [{iss.category}] {iss.description[:70]}')

        # ── E: 英语专项审计 ──
        eng_score = None
        if HAS_ENG and is_english_card(card, subject):
            # 用 manifest values 模拟 OCR
            mock_ocr = list(manifest.values()) + [title]
            for p in card.get('core_points', [])[:2]:
                mock_ocr.append(str(p)[:40])
            eng_result = rule_audit_english(
                ocr_texts=mock_ocr,
                card_data=card,
                manifest=manifest,
                prompt_text=prompt_text,
            )
            eng_score = eng_result.final_score
            eng_v = eng_result.verdict
            print(f'   英语审核: {eng_score}/100 {eng_v}')
            for iss in eng_result.issues[:3]:
                sev = {'critical': '🔴', 'major': '🟡', 'minor': '🔵'}.get(iss.severity, '⚪')
                print(f'     {sev} [{iss.dimension}] {iss.description[:70]}')

        # ── F: Manifest 质量检查 ──
        total_cn = sum(sum(1 for c in v if '\u4e00' <= c <= '\u9fff') for v in manifest.values())
        print(f'   Manifest: {dict(manifest)} (中文{total_cn}字)')

        results.append({
            'label': label,
            'card_type': card_type,
            'title': title,
            'prompt_len': len(prompt_text),
            'manifest_keys': len(manifest),
            'manifest_cn': total_cn,
            'has_schema': has_schema,
            'coverage': audit.coverage_pct,
            'verdict': audit.verdict,
            'issues': len(audit.issues),
            'eng_score': eng_score,
        })

        print()
        time.sleep(1)  # 避免 rate limit

    # ── 汇总 ──
    print('=' * 60)
    print('  汇总')
    print('=' * 60)
    print(f'{"#":>2} {"类型":<10} {"Schema":<8} {"Prompt长":<10} {"Coverage":<10} {"Verdict":<8} {"Issues":<7} {"英语":<6}')
    print('─' * 65)
    for i, r in enumerate(results, 1):
        if 'error' in r:
            print(f'{i:>2} {r["label"]:<10} ERROR: {r["error"][:40]}')
            continue
        eng_str = f'{r["eng_score"]}/100' if r["eng_score"] is not None else 'N/A'
        sch = '✅' if r['has_schema'] else '⏭️'
        print(f'{i:>2} {r["card_type"]:<10} {sch:<8} {r["prompt_len"]:>6}字  {r["coverage"]:>6.0f}%  {r["verdict"]:<8} {r["issues"]:>4}    {eng_str}')

    # 统计
    valid = [r for r in results if 'error' not in r]
    if valid:
        avg_cov = sum(r['coverage'] for r in valid) / len(valid)
        pass_count = sum(1 for r in valid if r['verdict'] == 'pass')
        avg_prompt = sum(r['prompt_len'] for r in valid) / len(valid)
        print(f'\n平均覆盖率: {avg_cov:.1f}%')
        print(f'审计通过率: {pass_count}/{len(valid)}')
        print(f'平均 prompt 长度: {avg_prompt:.0f}字')


if __name__ == '__main__':
    run_e2e()
