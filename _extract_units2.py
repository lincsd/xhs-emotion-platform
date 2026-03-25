import json, os, collections

base = r'd:\Users\Administrator\Desktop\ls\xhsqg\public\knowledge_cards\小学'

files = [
    '语文_一上','语文_一下','语文_二上','语文_二下','语文_三上','语文_三下',
    '语文_四上','语文_四下','语文_五上','语文_五下','语文_六上','语文_六下',
    '英语_三上','英语_三下','英语_四上','英语_四下','英语_五上','英语_五下','英语_六上','英语_六下'
]

for fname in files:
    fp = os.path.join(base, fname + '.json')
    if not os.path.exists(fp):
        print(f'\n=== {fname} === FILE NOT FOUND')
        continue
    with open(fp, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    units = data.get('units', [])
    total_cards = 0
    type_counts = collections.Counter()
    
    print(f'\n=== {fname} ===')
    for u in units:
        un = u.get('unit_name', '(missing)')
        cards = u.get('cards', [])
        total_cards += len(cards)
        for c in cards:
            tp = c.get('type', '(missing)')
            type_counts[tp] += 1
        print(f'  [{u.get("unit_id","")}] {un}: {len(cards)} cards')
    
    print(f'  TOTAL: {total_cards} cards')
    print(f'  Types: {dict(type_counts)}')

# Print sample cards
print('\n\n========== SAMPLE CARD: 语文_三下 ==========')
with open(os.path.join(base, '语文_三下.json'), 'r', encoding='utf-8') as f:
    d = json.load(f)
card = d['units'][0]['cards'][0]
print(json.dumps(card, ensure_ascii=False, indent=2))

print('\n\n========== SAMPLE CARD: 英语_三下 ==========')
with open(os.path.join(base, '英语_三下.json'), 'r', encoding='utf-8') as f:
    d = json.load(f)
card = d['units'][0]['cards'][0]
print(json.dumps(card, ensure_ascii=False, indent=2))
