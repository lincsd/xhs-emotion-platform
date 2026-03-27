#!/usr/bin/env python3
"""
端到端测试: 用真实英语卡片数据跑 card_review 审校闸门 (只跑硬规则层, 不调AI)
"""
import json, os, glob

from card_review import validate_hard_rules, is_english_grammar_card, detect_fabricated_words

BASE = os.path.dirname(os.path.abspath(__file__))
CARDS_DIR = os.path.join(BASE, 'public', 'knowledge_cards')

def find_english_jsons():
    """找到所有英语卡片 JSON 文件"""
    results = []
    for root, dirs, files in os.walk(CARDS_DIR):
        for f in files:
            if '英语' in f and f.endswith('.json') and '总结' not in f and '爆款' not in f and '考卷' not in f:
                results.append(os.path.join(root, f))
    return sorted(results)

def test_all_english_cards():
    files = find_english_jsons()
    print(f'找到 {len(files)} 个英语卡片文件\n')
    
    total_cards = 0
    passed = 0
    failed = 0
    issues_summary = {}  # issue类型 → 次数
    failed_cards = []
    
    for fp in files:
        fname = os.path.basename(fp)
        with open(fp, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        subject = data.get('subject', '英语')
        cards_in_file = 0
        fails_in_file = 0
        
        for unit in data.get('units', []):
            for card in unit.get('cards', []):
                total_cards += 1
                cards_in_file += 1
                
                result = validate_hard_rules(card, subject)
                if result['pass']:
                    passed += 1
                else:
                    failed += 1
                    fails_in_file += 1
                    for iss in result['issues']:
                        # 归类 issue
                        key = iss.split(':')[0].split('(')[0].strip()
                        issues_summary[key] = issues_summary.get(key, 0) + 1
                    
                    if len(failed_cards) < 10:  # 最多记录10个失败案例
                        failed_cards.append({
                            'card_id': card.get('full_id', '?'),
                            'title': card.get('title', '?'),
                            'issues': result['issues'],
                        })
        
        status = '✅' if fails_in_file == 0 else f'⚠️ {fails_in_file}张不通过'
        print(f'  {fname}: {cards_in_file}张卡 {status}')
    
    # 汇总
    print(f'\n{"="*50}')
    print(f'📊 审校结果汇总')
    print(f'{"="*50}')
    print(f'  总卡片数: {total_cards}')
    print(f'  ✅ 通过: {passed} ({passed/total_cards*100:.1f}%)')
    print(f'  ❌ 不通过: {failed} ({failed/total_cards*100:.1f}%)')
    
    if issues_summary:
        print(f'\n📋 问题类型分布:')
        for iss, count in sorted(issues_summary.items(), key=lambda x: -x[1]):
            print(f'  {count:3d}x  {iss}')
    
    if failed_cards:
        print(f'\n🔍 失败案例 (前{len(failed_cards)}个):')
        for fc in failed_cards:
            print(f'  [{fc["card_id"]}] {fc["title"]}')
            for iss in fc['issues']:
                print(f'    ⚠️  {iss}')
    
    # 额外: AI 造词检测专项
    print(f'\n{"="*50}')
    print(f'🔤 AI 造词专项检测')
    print(f'{"="*50}')
    fabricated_found = 0
    for fp in files:
        with open(fp, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for unit in data.get('units', []):
            for card in unit.get('cards', []):
                # 拼接所有文本
                parts = [card.get('title',''), card.get('definition',''), card.get('memory_tip','')]
                parts.extend(str(p) for p in card.get('core_points', []))
                for m in card.get('mistakes', []):
                    if isinstance(m, dict):
                        parts.append(str(m.get('wrong','')))
                        parts.append(str(m.get('correct','')))
                ex = card.get('example', {})
                if ex:
                    parts.append(str(ex.get('question','')))
                    parts.append(str(ex.get('answer','')))
                    parts.extend(str(s) for s in ex.get('steps', []))
                
                text = ' '.join(parts)
                fab = detect_fabricated_words(text)
                if fab:
                    fabricated_found += 1
                    if fabricated_found <= 5:
                        print(f'  [{card.get("full_id","?")}] 可疑词: {", ".join(fab[:3])}')
    
    if fabricated_found == 0:
        print('  ✅ 未检测到可疑 AI 造词')
    else:
        print(f'\n  共 {fabricated_found} 张卡含可疑词汇')
    
    return failed == 0

if __name__ == '__main__':
    ok = test_all_english_cards()
    print(f'\n{"✅ 全部通过!" if ok else "⚠️ 存在未通过卡片"}')
