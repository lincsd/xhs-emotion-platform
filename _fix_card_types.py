"""Fix card type aliases in knowledge card JSONs"""
import os, json

base = os.path.dirname(os.path.abspath(__file__))
replacements = {'对比辨析卡': '辨析卡', '生活应用卡': '生活卡', '易错陷阱卡': '陷阱卡'}
count = 0

for kc_dir in ['knowledge_cards', os.path.join('public', 'knowledge_cards')]:
    full_dir = os.path.join(base, kc_dir)
    if not os.path.isdir(full_dir):
        continue
    for root, dirs, files in os.walk(full_dir):
        for f in files:
            if not f.endswith('.json'):
                continue
            fp = os.path.join(root, f)
            data = json.loads(open(fp, encoding='utf-8').read())
            changed = False
            for unit in data.get('units', []):
                for card in unit.get('cards', []):
                    old_type = card.get('type', '')
                    if old_type in replacements:
                        new_type = replacements[old_type]
                        print(f"  {os.path.relpath(fp, base)} [{card.get('card_id','?')}]: {old_type} -> {new_type}")
                        card['type'] = new_type
                        changed = True
                        count += 1
            if changed:
                with open(fp, 'w', encoding='utf-8') as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=2)

print(f"\nFixed {count} cards")
