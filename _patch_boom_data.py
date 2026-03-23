"""Patch all boom card JSON files to add missing 'related', 'mistakes', 'memory_tip' fields."""
import json, glob, os

base = 'D:/Users/Administrator/Desktop/ls/xhsqg/public/knowledge_cards/小学/'
patched = 0
total_cards = 0

for fp in sorted(glob.glob(base + '*爆款*.json')):
    fname = os.path.basename(fp)
    with open(fp, encoding='utf-8') as f:
        data = json.load(f)
    
    changed = False
    for u in data.get('units', []):
        for c in u.get('cards', []):
            total_cards += 1
            if 'related' not in c:
                c['related'] = {
                    'prerequisite': '见同年级标准卡片包',
                    'next': '见同年级标准卡片包'
                }
                changed = True
            if 'mistakes' not in c:
                # Build a sensible default from trap_point if available
                trap = c.get('trap_point', '')
                if trap:
                    c['mistakes'] = [{'wrong': trap, 'correct': '注意审题，仔细检查。'}]
                else:
                    c['mistakes'] = [{'wrong': '粗心大意导致计算错误。', 'correct': '认真审题，仔细检查每一步。'}]
                changed = True
            if 'memory_tip' not in c:
                c['memory_tip'] = c.get('emotion_hook', '多练多记，熟能生巧！')
                changed = True
    
    if changed:
        # Also update knowledge_cards dir (same place)
        with open(fp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        patched += 1
        print(f'[PATCHED] {fname}')
    else:
        print(f'[OK] {fname}')

print(f'\n=== Done: {patched} files patched, {total_cards} cards checked ===')
