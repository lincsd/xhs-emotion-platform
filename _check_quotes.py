import re

fp = r'd:\Users\Administrator\Desktop\ls\xhsqg\public\knowledge_cards\情感生活\恋爱_谈恋爱.json'
with open(fp, encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
for i, line in enumerate(lines, 1):
    s = line.strip()
    if not s:
        continue
    qcount = s.count('"')
    if qcount > 6:
        print(f'L{i} ({qcount}q): {s[:120]}')
