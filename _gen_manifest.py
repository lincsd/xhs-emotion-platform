import json, os

base = 'public/knowledge_cards/小学'
entries = []
for f in sorted(os.listdir(base)):
    if not f.endswith('.json') or f == 'manifest.json':
        continue
    fp = os.path.join(base, f)
    try:
        data = json.loads(open(fp, encoding='utf-8').read())
    except:
        continue
    is_boom = '爆款' in f
    parts = f.replace('.json','').split('_')
    subject = parts[0]
    grade_short = parts[1]
    grade_map = {'一':'一年级','二':'二年级','三':'三年级','四':'四年级','五':'五年级','六':'六年级'}
    sem_map = {'上':'上册','下':'下册'}
    grade = grade_map.get(grade_short[0], grade_short[0])
    semester = sem_map.get(grade_short[1], grade_short[1])
    
    total_cards = 0
    total_units = 0
    if isinstance(data, dict) and 'units' in data:
        for u in data['units']:
            total_units += 1
            total_cards += len(u.get('cards', []))
    elif isinstance(data, dict) and 'packs' in data:
        for p in data['packs']:
            total_units += 1
            total_cards += len(p.get('cards', []))
    elif isinstance(data, list):
        for p in data:
            total_units += 1
            total_cards += len(p.get('cards', []))
    
    entries.append({
        'file': f,
        'subject': subject,
        'grade': grade,
        'semester': semester,
        'grade_short': grade_short,
        'is_boom': is_boom,
        'units': total_units,
        'cards': total_cards
    })

manifest = {'stages': {'小学': entries}}
with open('public/knowledge_cards/manifest.json', 'w', encoding='utf-8') as mf:
    json.dump(manifest, mf, ensure_ascii=False, indent=2)
print(f'Written {len(entries)} entries')
for e in entries:
    boom = '🔥' if e['is_boom'] else '📘'
    print(f"  {boom} {e['subject']}_{e['grade_short']} u={e['units']} c={e['cards']}")
