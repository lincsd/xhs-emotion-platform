import json, os
d = json.load(open('knowledge_cards_数学_三下.json', encoding='utf-8'))
existing = set(f.replace('.jpg','') for f in os.listdir('card_images') if f.endswith('.jpg'))
for u in d['units']:
    for c in u['cards']:
        fid = c['full_id'].replace('-','_')
        mark = '[V]' if fid in existing else '[X]'
        ex = str(c.get('example',''))[:80]
        print(f"{mark} {c['full_id']} {c['title']}")
        print(f"    例: {ex}")
