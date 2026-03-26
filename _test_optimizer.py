#!/usr/bin/env python3
"""Test self_optimizer module"""
import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from self_optimizer import *

print('=== Test Self-Optimizer Module ===')

# Test 1: record a fake generation
record_full_result(
    card_id='test-001', subject='数学', grade='三年级',
    card_type='方法卡', prompt_text='A test prompt about math addition...',
    manifest={'TITLE': '加法', 'LINE1': '巧算'},
    audit_score=85, quality_score=90,
    audit_result={'errors': [
        {'expected': '加法', 'actual': '加汰', 'type': 'wrong_char', 'severity': 'high'},
    ]},
    image_model='gemini-3.1-flash-image-preview',
    audit_rounds=2, final_action='pass',
    prompt_length=400, image_size_kb=120.5, elapsed_seconds=35.2, success=True
)
print('1. record_full_result OK')

# Test 2: dashboard
d = get_optimizer_dashboard()
print(f"2. Dashboard: prompts={d['summary']['total_prompts_memorized']}, errors={d['summary']['total_error_chars_tracked']}, gens={d['summary']['total_generations_recorded']}")

# Test 3: top prompts
p = get_top_prompts('数学')
print(f'3. Top prompts: {len(p)} found')

# Test 4: error dict
e = get_frequent_errors('数学', min_count=1)
chars = [x['char_text'] for x in e]
print(f'4. Error chars: {chars}')

# Test 5: few-shot hint
h = build_fewshot_hint('数学')
print(f'5. Few-shot hint: {len(h)} chars')

# Test 6: error boost
h2 = build_error_boost_hint('数学', {'TITLE': '加法'})
print(f'6. Error boost hint: {len(h2)} chars')

# Test 7: adaptive params
ap = get_adaptive_params()
print(f'7. Adaptive params: {ap}')

# Test 8: stats
s = get_stats_summary()
print(f'8. Stats: success_rate={s["success_rate"]}%, avg_audit={s["avg_audit"]}')

# Cleanup
reset_optimizer()
print('9. Reset OK')

# Verify reset
d2 = get_optimizer_dashboard()
assert d2['summary']['total_generations_recorded'] == 0
print('10. Verify reset OK')

# Clean up DB file
if os.path.exists('optimizer.db'):
    os.remove('optimizer.db')
    print('11. Removed test DB')

print('\n=== ALL TESTS PASSED ===')
