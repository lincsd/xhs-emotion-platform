import json, re
# 查看触发'正确例句不完整'的卡片
for fname in ['public/knowledge_cards/小学/英语_三下.json', 'public/knowledge_cards/小学/英语_五上.json']:
    d = json.load(open(fname, 'r', encoding='utf-8'))
    for u in d['units']:
        for c in u['cards']:
            for m in c.get('mistakes', []):
                if isinstance(m, dict):
                    correct = str(m.get('correct', ''))
                    has_eng = bool(re.search(r'[a-zA-Z]', correct))
                    eng_chars = len(re.findall(r'[a-zA-Z]', correct))
                    total_chars = len(correct.replace(' ', ''))
                    if has_eng and total_chars > 0:
                        ratio = eng_chars / total_chars
                        if ratio > 0.8 and len(correct) < 10:
                            print(f'[{c["full_id"]}] ratio={ratio:.2f} len={len(correct)} correct={repr(correct)}')
