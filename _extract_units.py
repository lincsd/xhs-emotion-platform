import json, os

base = r'd:\Users\Administrator\Desktop\ls\xhsqg\public\knowledge_cards\小学'
files = ['数学_一上','数学_一下','数学_二上','数学_二下','数学_三上','数学_三下',
         '数学_四上','数学_四下','数学_五上','数学_五下','数学_六上','数学_六下']

for f in files:
    path = os.path.join(base, f + '.json')
    with open(path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    print(f'\n===== {f} =====')
    units = data.get('units', [])
    total = 0
    for u in units:
        n = len(u.get('cards', []))
        total += n
        uid = u.get('unit_id', '?')
        uname = u.get('unit_name', '?')
        print(f'  {uid}. {uname}: {n} cards')
    print(f'  [Total: {total} cards, {len(units)} units]')
