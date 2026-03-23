import json, os, glob

base = 'D:/Users/Administrator/Desktop/ls/xhsqg/knowledge_cards/小学'
for fp in sorted(glob.glob(os.path.join(base, '数学_*.json'))):
    raw = json.load(open(fp, 'r', encoding='utf-8'))
    fname = os.path.basename(fp)
    
    units = raw.get('units', [])
    for unit in units:
        for card in unit.get('cards', []):
            t = card.get('title', '')
            if '乘' in t:
                fid = card.get('full_id', '?')
                print(f"{fname} | {fid} | {t}")
