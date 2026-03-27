#!/usr/bin/env python3
"""Quick smoke test for card_review.py"""
from card_review import validate_hard_rules, is_english_grammar_card, detect_fabricated_words

# Test 1: repeated word 'can can'
card1 = {
    'title': '高频活用',
    'definition': 'pay attention to',
    'core_points': ['pay attention to', 'succeed/success/successful'],
    'memory_tip': '搭配多记',
    'mistakes': [{'wrong': 'so you can can succeed', 'correct': 'so you can succeed'}],
    'example': {'question': 'fill in blank', 'answer': 'pay', 'steps': []},
}
r1 = validate_hard_rules(card1, '英语')
print(f"Test 1 (repeated word): pass={r1['pass']}, issues={r1['issues']}")
assert not r1['pass'], "Should fail: repeated word"

# Test 2: incomplete phrase 'success in'
card2 = {
    'title': '词性辨析',
    'definition': 'succeed vs success vs successful',
    'core_points': ['succeed是动词'],
    'memory_tip': '动名形要分清',
    'mistakes': [{'wrong': 'successful in career', 'correct': 'success in'}],
    'example': {'question': 'choose', 'answer': 'success', 'steps': []},
}
r2 = validate_hard_rules(card2, '英语')
print(f"Test 2 (incomplete phrase): pass={r2['pass']}, issues={r2['issues']}")
assert not r2['pass'], "Should fail: incomplete phrase"

# Test 3: clean card should pass
card3 = {
    'title': '搭配: pay attention to',
    'definition': 'pay attention to 后接名词或动名词',
    'core_points': ['pay attention to sth'],
    'memory_tip': '搭配多记 熟能生巧',
    'mistakes': [{'wrong': 'He pay attention to details.', 'correct': 'He pays attention to details.'}],
    'example': {'question': 'fill in blank', 'answer': 'pays', 'steps': ['主语是第三人称单数']},
}
r3 = validate_hard_rules(card3, '英语')
print(f"Test 3 (clean card): pass={r3['pass']}, issues={r3['issues']}")
assert r3['pass'], f"Should pass but got: {r3['issues']}"

# Test 4: math card no mistakes should pass
card4 = {
    'title': '两位数乘法',
    'definition': '两位数乘一位数的笔算方法',
    'core_points': ['先乘个位再乘十位', '注意进位'],
    'memory_tip': '个十分步算 进位别忘加',
    'example': {'question': '23 × 4 = ?', 'answer': '92', 'steps': ['4×3=12', '4×20=80', '12+80=92']},
}
r4 = validate_hard_rules(card4, '数学')
print(f"Test 4 (math card no mistakes): pass={r4['pass']}, issues={r4['issues']}")
assert r4['pass'], f"Math card should pass: {r4['issues']}"

# Test 5: is_english_grammar_card detection
assert is_english_grammar_card(card1, '英语') == True
assert is_english_grammar_card(card4, '数学') == False
print("Test 5 (english detection): OK")

# Test 6: vague error reason
card6 = {
    'title': '词性辨析',
    'definition': 'succeed vs success',
    'core_points': ['注意词性'],
    'memory_tip': '记住',
    'mistakes': [{'wrong': '词性错', 'correct': '词性不对'}],
    'example': {'question': 'q', 'answer': 'a', 'steps': []},
}
r6 = validate_hard_rules(card6, '英语')
print(f"Test 6 (vague reason): pass={r6['pass']}, issues={r6['issues']}")
assert not r6['pass'], "Should fail: vague error reason"

# Test 7: AI fabricated word detection
fab = detect_fabricated_words("He made a guestioneful attention in his career")
print(f"Test 7 (fabricated word): found={fab}")
assert 'guestioneful' in fab, f"Should detect 'guestioneful' but got: {fab}"

# Test 8: real words should not be flagged
fab2 = detect_fabricated_words("He made great success in his career successfully")
print(f"Test 8 (real words): found={fab2}")
assert len(fab2) == 0, f"Should not flag real words but got: {fab2}"

# Test 9: vague title detection
card9 = {
    'title': '高频词汇',
    'definition': 'pay attention to 后接名词',
    'core_points': ['pay attention to'],
    'memory_tip': '搭配记忆',
    'mistakes': [{'wrong': 'He pay attention to it.', 'correct': 'He pays attention to it.'}],
    'example': {'question': 'q', 'answer': 'a', 'steps': []},
}
r9 = validate_hard_rules(card9, '英语')
print(f"Test 9 (vague title): pass={r9['pass']}, issues={r9['issues']}")
assert not r9['pass'], "Should fail: vague title"

# Test 10: fabricated word in card should be caught by hard rules
card10 = {
    'title': '搭配辨析',
    'definition': 'pay attention to usage',
    'core_points': ['pay attention to'],
    'memory_tip': '搭配记忆',
    'mistakes': [{'wrong': 'He made a guestioneful attention.', 'correct': 'He paid close attention.'}],
    'example': {'question': 'q', 'answer': 'a', 'steps': []},
}
r10 = validate_hard_rules(card10, '英语')
print(f"Test 10 (fabricated in card): pass={r10['pass']}, issues={r10['issues']}")
assert not r10['pass'], "Should fail: fabricated word in card"

print("\n✅ All 10 tests passed!")
