import json
d = json.load(open(r'd:\Users\Administrator\Desktop\ls\xhsqg\public\knowledge_cards\国学文化\国学_预言.json', 'r', encoding='utf-8'))
cards = sum(len(u['cards']) for u in d['units'])
print(f"Units={len(d['units'])} Cards={cards}")
