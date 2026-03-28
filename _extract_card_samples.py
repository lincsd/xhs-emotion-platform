"""Extract sample card data from knowledge_cards for analysis."""
import json, os, sys

base = r'd:\Users\Administrator\Desktop\ls\xhsqg\knowledge_cards\小学'
mid_base = r'd:\Users\Administrator\Desktop\ls\xhsqg\knowledge_cards\初中'

results = []

def find_card(filepath, type_filter=None, limit=1):
    """Find cards matching type in a file."""
    found = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"  [SKIP] {filepath}: {e}", file=sys.stderr)
        return found
    
    units = data.get('units', [])
    for u in units:
        uid = u.get('unit_id', '?')
        uname = u.get('unit_name', '?')
        for c in u.get('cards', []):
            if type_filter is None or c.get('type') == type_filter:
                found.append({
                    'source_file': filepath,
                    'unit_id': uid,
                    'unit_name': uname,
                    'card': c
                })
                if len(found) >= limit:
                    return found
    return found

def find_any_card(filepath, limit=1):
    """Find any card from a file."""
    return find_card(filepath, type_filter=None, limit=limit)

# ============================================================
# 1. MATH CARDS
# ============================================================

# 1a. 方法卡 from 三下
print("=== 1. 方法卡 (三下数学) ===")
r = find_card(os.path.join(base, '数学_三下.json'), '方法卡', 1)
if r: results.extend(r)

# 1b. 概念卡 from 四上
print("=== 2. 概念卡 (四上数学) ===")
r = find_card(os.path.join(base, '数学_四上.json'), '概念卡', 1)
if r: results.extend(r)

# 1c. 公式卡 - search across multiple files
print("=== 3. 公式卡 (数学) ===")
for grade in ['五上', '五下', '六上', '六下', '四上', '四下', '三上', '三下']:
    fp = os.path.join(base, f'数学_{grade}.json')
    r = find_card(fp, '公式卡', 1)
    if r:
        results.extend(r)
        break

# 1d. 辨析卡 - search across multiple files
print("=== 4. 辨析卡 (数学) ===")
found_bianxi = False
for grade in ['五上', '五下', '六上', '六下', '四上', '四下', '三上', '三下']:
    fp = os.path.join(base, f'数学_{grade}.json')
    r = find_card(fp, '辨析卡', 1)
    if r:
        results.extend(r)
        found_bianxi = True
        break
if not found_bianxi:
    # Try 初中
    if os.path.exists(mid_base):
        for fn in os.listdir(mid_base):
            if fn.startswith('数学') and not any(x in fn for x in ['总结', '爆款', '考卷']):
                r = find_card(os.path.join(mid_base, fn), '辨析卡', 1)
                if r:
                    results.extend(r)
                    found_bianxi = True
                    break

# ============================================================
# 2. ENGLISH CARDS
# ============================================================

# 2a. 词汇卡
print("=== 5. 词汇卡 (英语) ===")
for grade in ['四上', '四下', '五上', '五下', '六上']:
    fp = os.path.join(base, f'英语_{grade}.json')
    r = find_card(fp, '词汇卡', 1)
    if r:
        results.extend(r)
        break

# 2b. 句型卡
print("=== 6. 句型卡 (英语) ===")
for grade in ['四上', '四下', '五上', '五下', '六上']:
    fp = os.path.join(base, f'英语_{grade}.json')
    r = find_card(fp, '句型卡', 1)
    if r:
        results.extend(r)
        break

# 2c. 语法辨析卡 or 易混词卡
print("=== 7. 语法辨析卡/易混词卡 (英语) ===")
found_grammar = False
for grade in ['四上', '四下', '五上', '五下', '六上', '六下', '三上', '三下']:
    fp = os.path.join(base, f'英语_{grade}.json')
    for ttype in ['语法辨析卡', '易混词卡', '语法卡', '辨析卡']:
        r = find_card(fp, ttype, 1)
        if r:
            results.extend(r)
            found_grammar = True
            break
    if found_grammar:
        break
# If not found, try 初中
if not found_grammar and os.path.exists(mid_base):
    for fn in sorted(os.listdir(mid_base)):
        if fn.startswith('英语') and not any(x in fn for x in ['总结', '爆款', '考卷']):
            for ttype in ['语法辨析卡', '易混词卡', '语法卡', '辨析卡']:
                r = find_card(os.path.join(mid_base, fn), ttype, 1)
                if r:
                    results.extend(r)
                    found_grammar = True
                    break
        if found_grammar:
            break

# 2d. 爆款 English card
print("=== 8. 英语爆款卡 ===")
for grade in ['四上', '四下', '五上', '五下', '六上']:
    fp = os.path.join(base, f'英语_{grade}_爆款.json')
    r = find_any_card(fp, 1)
    if r:
        results.extend(r)
        break

# ============================================================
# 3. ENGLISH 考卷/总结
# ============================================================

# 3a. 英语考卷
print("=== 9. 英语考卷卡 ===")
for grade in ['四上', '四下', '五上', '五下', '六上']:
    fp = os.path.join(base, f'英语_{grade}_考卷.json')
    r = find_any_card(fp, 1)
    if r:
        results.extend(r)
        break

# 3b. 英语总结
print("=== 10. 英语总结卡 ===")
for grade in ['四上', '四下', '五上', '五下', '六上']:
    fp = os.path.join(base, f'英语_{grade}_总结.json')
    r = find_any_card(fp, 1)
    if r:
        results.extend(r)
        break

# ============================================================
# ALSO: list all unique card types found across files
# ============================================================
print("\n=== Scanning all unique card types ===")
all_types = {}
for folder in [base, mid_base]:
    if not os.path.exists(folder):
        continue
    for fn in sorted(os.listdir(folder)):
        if fn.endswith('.json'):
            fp = os.path.join(folder, fn)
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for u in data.get('units', []):
                    for c in u.get('cards', []):
                        t = c.get('type', '?')
                        if t not in all_types:
                            all_types[t] = fn
            except:
                pass

print("All unique card types found:")
for t, fn in sorted(all_types.items()):
    print(f"  {t} (first seen in: {fn})")

# ============================================================
# OUTPUT
# ============================================================
print(f"\n=== TOTAL CARDS COLLECTED: {len(results)} ===\n")

output = []
for i, r in enumerate(results):
    entry = {
        'index': i + 1,
        'source_file': r['source_file'].replace(base, '小学/').replace(mid_base, '初中/'),
        'unit_id': r['unit_id'],
        'unit_name': r['unit_name'],
        'card': r['card']
    }
    output.append(entry)

# Write to file
outpath = r'd:\Users\Administrator\Desktop\ls\xhsqg\_card_samples_output.json'
with open(outpath, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"Written to: {outpath}")

# Also print summary
for entry in output:
    c = entry['card']
    print(f"\n--- Card #{entry['index']} ---")
    print(f"Source: {entry['source_file']}")
    print(f"Unit: [{entry['unit_id']}] {entry['unit_name']}")
    print(f"Type: {c.get('type')}, Title: {c.get('title')}")
    print(f"Keys: {list(c.keys())}")
