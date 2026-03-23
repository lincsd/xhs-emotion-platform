import json, os

base = 'D:/Users/Administrator/Desktop/ls/xhsqg/knowledge_cards/小学'

# Check both standard and boom versions
for fname in ['数学_三下.json', '数学_三下_爆款.json']:
    fp = os.path.join(base, fname)
    raw = json.load(open(fp, 'r', encoding='utf-8'))
    units = raw.get('units', [])
    for unit in units:
        for card in unit.get('cards', []):
            t = card.get('title', '')
            fid = card.get('full_id', '')
            if '笔算' in t and '乘' in t:
                print(f"=== {fname} | {fid} ===")
                print(json.dumps(card, ensure_ascii=False, indent=2))
                print()
