import json
m = json.load(open('public/knowledge_cards/manifest.json','r',encoding='utf-8'))
es = m['stages']['小学']
print(f'Total entries: {len(es)}')
for e in es:
    if '英语' in e.get('subject',''):
        t = 'boom' if e['is_boom'] else 'std'
        print(f"  {t} {e['subject']}_{e['grade_short']} u={e['units']} c={e['cards']}")
