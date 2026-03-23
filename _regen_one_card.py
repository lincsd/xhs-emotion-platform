#!/usr/bin/env python3
"""Regenerate a single card image by full_id"""
import json, os, sys

# Target card
TARGET_ID = '数学-三下-05-03'

# Load the card data
json_file = os.path.join('knowledge_cards', '小学', '数学_三下.json')
with open(json_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Find the card
card = None
for unit in data['units']:
    for c in unit['cards']:
        if c['full_id'] == TARGET_ID:
            card = c
            break
    if card:
        break

if not card:
    print(f'❌ Card {TARGET_ID} not found')
    sys.exit(1)

print(f'✅ Found card: {card["full_id"]} - {card["title"]}')
print(f'   Type: {card["type"]}, Difficulty: {card["difficulty"]}')
print(f'   Example: {card["example"]["question"]}')

# Create a temporary JSON with just this card
temp_data = {
    'subject': data['subject'],
    'grade': data['grade'],
    'semester': data['semester'],
    'textbook': data.get('textbook', ''),
    'grade_short': data.get('grade_short', ''),
    'units': [{
        'unit_id': '05',
        'unit_name': '两位数乘两位数',
        'cards': [card]
    }],
    'total_cards': 1
}

temp_file = '_temp_single_card.json'
with open(temp_file, 'w', encoding='utf-8') as f:
    json.dump(temp_data, f, ensure_ascii=False, indent=2)

print(f'\n📝 Temp file: {temp_file}')
print(f'🚀 Now run: python generate_card_images.py {temp_file} card_images')
