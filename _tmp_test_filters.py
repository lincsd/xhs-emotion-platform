#!/usr/bin/env python3
"""Test the full-field off-topic filters"""
import sys, json
sys.path.insert(0, r'd:\Users\Administrator\Desktop\ls\xhsqg')

# Force reload
for m in list(sys.modules):
    if 'generate_card_images_v3' in m or 'card_review' in m:
        del sys.modules[m]

from generate_card_images_v3 import (
    _filter_off_topic_steps, _filter_off_topic_core_points,
    _filter_off_topic_mistakes, _clean_answer
)

# Simulate the exact card data from the screenshot
card = {
    'title': '固定搭配',
    'type': '搭配卡',
    'definition': 'pay close attention to的搭配',
    'core_points': ['pay attention to', 'close attention', 'modal verb + V_base', 'succeed/success/successful'],
    'example': {
        'question': 'It is important to ___ (pay) close attention ___ (to) details',
        'steps': [
            'close attention -> pay, Fixed collocation',
            'pay attention -> to, Preposition for collocation',
            'Modal verb + V_base -> succeed'
        ],
        'answer': 'pay; to; succeed'
    },
    'mistakes': [
        {'wrong': 'He made a great successful in his career', 'correct': 'He made great success in his career', 'reason': 'successful (adj.) needed a noun'},
        {'wrong': 'pay attention at', 'correct': 'pay attention to', 'reason': '固定搭配介词用to'}
    ],
    'memory_tip': '搭配要记清',
}

print("=== Before filtering ===")
print(f"core_points: {card['core_points']}")
print(f"steps: {card['example']['steps']}")
print(f"answer: {card['example']['answer']}")
print(f"mistakes: {[m['wrong'][:40] for m in card['mistakes']]}")

print("\n=== After filtering ===")
clean_steps = _filter_off_topic_steps(card)
print(f"steps: {clean_steps}")

clean_pts = _filter_off_topic_core_points(card)
print(f"core_points: {clean_pts}")

clean_mistakes = _filter_off_topic_mistakes(card)
print(f"mistakes: {[m['wrong'][:40] for m in clean_mistakes]}")

clean_ans = _clean_answer(card)
print(f"answer: {clean_ans}")

print("\n=== Summary ===")
print(f"Steps: {len(card['example']['steps'])} -> {len(clean_steps)}")
print(f"Points: {len(card['core_points'])} -> {len(clean_pts)}")
print(f"Mistakes: {len(card['mistakes'])} -> {len(clean_mistakes)}")
print(f"Answer: '{card['example']['answer']}' -> '{clean_ans}'")
