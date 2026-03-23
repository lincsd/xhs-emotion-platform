import json
data = json.load(open(r'knowledge_cards_数学_三下_爆款.json', 'r', encoding='utf-8'))
traps = [c for u in data['units'] for c in u['cards'] if c['type'] == '陷阱卡']
print(f'{len(traps)} 张陷阱卡:')
for c in traps:
    print(f"  {c['card_id']} | {c['title']} | {c['trap_point']}")
total = sum(len(u['cards']) for u in data['units'])
print(f'\n爆款卡总数: {total}')
