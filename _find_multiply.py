import json, os, glob

base = 'D:/Users/Administrator/Desktop/ls/xhsqg/knowledge_cards/小学'
for fp in sorted(glob.glob(os.path.join(base, '数学_*.json'))):
    raw = json.load(open(fp, 'r', encoding='utf-8'))
    fname = os.path.basename(fp)
    
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, dict):
                t = v.get('title', '')
                if '乘' in t:
                    print(f"{fname} | {k} | {t}")
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        t = item.get('title', '')
                        if '乘' in t:
                            print(f"{fname} | {k} | {t}")
    elif isinstance(raw, list):
        for c in raw:
            if isinstance(c, dict):
                t = c.get('title', '')
                fid = c.get('full_id', '?')
                if '乘' in t:
                    print(f"{fname} | {fid} | {t}")
