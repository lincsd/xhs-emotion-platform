import json, sys

# Read 爆款 JSON
with open('knowledge_cards_数学_三下_爆款.json', 'r', encoding='utf-8') as f:
    boom = json.load(f)
boom_str = json.dumps(boom, ensure_ascii=False, separators=(',', ':'))

# Read index.html
with open('public/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Find the PACKS array end marker and insert 爆款 pack before it
old_marker = ',"total_cards":34}];'
new_marker = ',"total_cards":34},' + boom_str + '];'
if old_marker in html:
    html = html.replace(old_marker, new_marker, 1)
    print('PACKS updated: added boom pack')
else:
    print('ERROR: PACKS marker not found')
    sys.exit(1)

# Fix PromptLib init() to iterate ALL packs
old_init = 'for (const u of packs[0].units) {'
new_init = 'for (const pack of packs) for (const u of pack.units) {'
if old_init in html:
    html = html.replace(old_init, new_init, 1)
    print('PromptLib init() updated: iterate all packs')
else:
    print('ERROR: init marker not found')

with open('public/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Done!')
