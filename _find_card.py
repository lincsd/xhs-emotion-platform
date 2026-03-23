import json, os, glob

base = 'D:/Users/Administrator/Desktop/ls/xhsqg/knowledge_cards/小学'
for fp in glob.glob(os.path.join(base, '数学_*.json')):
    raw = json.load(open(fp, 'r', encoding='utf-8'))
    # handle both dict and list formats
    if isinstance(raw, dict):
        cards = []
        for k, v in raw.items():
            if isinstance(v, dict):
                v['_key'] = k
                cards.append(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        item['_key'] = k
                        cards.append(item)
    elif isinstance(raw, list):
        cards = raw
    else:
        continue
    
    for card in cards:
        t = card.get('title', '')
        if '乘法' in t and ('笔算' in t or '两位' in t or '竖式' in t or '乘积' in t or '错位' in t or '秘诀' in t):
            print(f"=== FILE: {os.path.basename(fp)} ===")
            print(f"  key: {card.get('_key', '')}")
            print(f"  full_id: {card.get('full_id', '')}")
            print(f"  title: {t}")
            print(f"  type: {card.get('type', '')}")
            print(f"  definition: {card.get('definition', '')}")
            print(f"  core_points: {json.dumps(card.get('core_points', []), ensure_ascii=False)}")
            print(f"  example: {json.dumps(card.get('example', {}), ensure_ascii=False)}")
            print(f"  mistakes: {json.dumps(card.get('mistakes', []), ensure_ascii=False)}")
            print(f"  memory_tip: {card.get('memory_tip', '')}")
            print()
