#!/usr/bin/env python3
import sys, json
sys.path.insert(0, r'd:\Users\Administrator\Desktop\ls\xhsqg')

# Force fresh import
for m in list(sys.modules):
    if 'card_review' in m:
        del sys.modules[m]

from card_review import validate_hard_rules

card = {
    'full_id': 'test_collocation_01',
    'title': '搭配活用',
    'type': '搭配卡',
    'definition': 'pay close attention to的搭配',
    'core_points': ['pay attention to', 'close attention', 'modal verb + V_base'],
    'example': {
        'question': 'It is important to ___ close attention ___ details',
        'steps': [
            'close attention -> pay, Fixed collocation',
            'pay attention -> to, Preposition',
            'Modal verb + V_base -> succeed'
        ],
        'answer': 'pay; to'
    },
    'mistakes': [{'wrong': 'pay attention at', 'correct': 'pay attention to', 'reason': '固定搭配'}],
    'memory_tip': '搭配固定要',
    'difficulty': 3
}

r = validate_hard_rules(card, '英语')
print(f"pass={r['pass']} count={len(r['issues'])}", flush=True)
for i, x in enumerate(r['issues']):
    print(f"[{i+1}] {x}", flush=True)
print("DONE", flush=True)
