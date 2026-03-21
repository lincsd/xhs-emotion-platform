"""Generate specific sample cards from different units"""
import json, sys, os, time
sys.path.insert(0, '.')
import generate_card_images as g

data = json.load(open('knowledge_cards_数学_三下.json', encoding='utf-8'))
keys = g.load_api_keys()
subject = data['subject']
grade = data['grade']
semester = data['semester']

targets = ['数学-三下-02-01', '数学-三下-04-01']
os.makedirs('card_images', exist_ok=True)

for unit in data['units']:
    for card in unit['cards']:
        if card['full_id'] not in targets:
            continue
        fid = card['full_id'].replace('-', '_')
        # Skip if exists
        if any(f.startswith(fid) for f in os.listdir('card_images')):
            print(f'  [skip] {fid} already exists')
            continue
        print(f'=== {card["full_id"]} {card["title"]} ===')
        key = g.next_key(keys)
        print('  Step1: prompt...', end='', flush=True)
        prompt = g.generate_image_prompt(card, subject, grade, semester, key)
        if not prompt:
            print(' FAIL')
            continue
        print(f' OK ({len(prompt)} chars)')
        time.sleep(1)
        key = g.next_key(keys)
        print('  Step2: image...', end='', flush=True)
        result = g.generate_card_image(prompt, key, card_title=card['title'], subject=subject)
        if not result:
            print(' FAIL')
            continue
        img, ext = result
        fp = f'card_images/{fid}.{ext}'
        open(fp, 'wb').write(img)
        print(f' OK {fp} ({len(img)//1024}KB)')
        # Save prompt to library
        g.save_prompt_to_lib(card, prompt, subject, grade, semester, image_path=fp)
        time.sleep(2)

print('Done!')
