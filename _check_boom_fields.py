import json, glob, os

base = 'D:/Users/Administrator/Desktop/ls/xhsqg/public/knowledge_cards/小学/'
required = ['full_id','title','definition','core_points','example','mistakes','memory_tip','related']

for fp in sorted(glob.glob(base + '*爆款*.json')):
    fname = os.path.basename(fp)
    with open(fp, encoding='utf-8') as f:
        data = json.load(f)
    issues = []
    for u in data.get('units', []):
        for c in u.get('cards', []):
            cid = c.get('card_id', '?')
            missing = [field for field in required if field not in c]
            if missing:
                issues.append(f"  {cid}: MISSING {missing}")
            elif 'related' in c:
                r = c['related']
                if 'prerequisite' not in r or 'next' not in r:
                    issues.append(f"  {cid}: related has keys={list(r.keys())}, missing prerequisite/next")
    if issues:
        print(f"[PROBLEM] {fname}")
        for i in issues:
            print(i)
    else:
        print(f"[OK] {fname}")
print("\n=== Done ===")
