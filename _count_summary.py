import json, os, glob

total_new_cards = 0
file_entries = []
for f in sorted(glob.glob('public/knowledge_cards/小学/*_总结.json')):
    with open(f, encoding='utf-8') as fh:
        data = json.load(fh)
    cards = sum(len(u['cards']) for u in data['units'])
    units = len(data['units'])
    fname = os.path.basename(f)
    total_new_cards += cards
    file_entries.append((fname, data['subject'], data.get('grade_short',''), units, cards))
    print(f'{fname}: {units} units, {cards} cards')

print(f'\nTotal: {len(file_entries)} files, {total_new_cards} cards')
