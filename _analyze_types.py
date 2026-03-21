import json
d = json.load(open('knowledge_cards_数学_三下.json', encoding='utf-8'))
types = {}
for u in d['units']:
    for c in u['cards']:
        t = c['type']
        if t not in types:
            types[t] = []
        types[t].append(f"  {c['full_id']} {c['title']}")

for t, cards in types.items():
    print(f"\n【{t}】({len(cards)}张)")
    for c in cards:
        print(c)

# Also check existing prompts
import os
prompts_file = 'card_images/_prompts.json'
if os.path.exists(prompts_file):
    prompts = json.load(open(prompts_file, encoding='utf-8'))
    print(f"\n\n已保存的prompts: {len(prompts)} 条")
    for k in list(prompts.keys())[:3]:
        print(f"  {k}: {str(prompts[k])[:80]}...")
else:
    print("\n\n未找到prompts记录文件")
