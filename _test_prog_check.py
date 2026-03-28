"""Test _programmatic_text_check function"""
import sys
sys.path.insert(0, '.')
from generate_card_images_v3 import _programmatic_text_check

# Test 1: truncated text should be caught
ocr = {'found_texts': ['提升语言运用能'], 'errors': [], 'overall_score': 90, 'summary': 'ok'}
manifest = {'SLOGAN': '提升语言运用能力'}
result = _programmatic_text_check(ocr, manifest)
assert len(result['errors']) == 1, f"Expected 1 error, got {result['errors']}"
assert result['errors'][0]['type'] == 'truncated'
assert result['overall_score'] == 80  # -10
print('Test1 PASS: truncated text detected')

# Test 2: exact match should NOT trigger
ocr2 = {'found_texts': ['提升语言运用能力'], 'errors': [], 'overall_score': 90, 'summary': 'ok'}
result2 = _programmatic_text_check(ocr2, manifest)
assert len(result2['errors']) == 0, f"Expected 0 errors, got {result2['errors']}"
print('Test2 PASS: exact match no error')

# Test 3: short text (< 3 chars) should be skipped
ocr3 = {'found_texts': ['记'], 'errors': [], 'overall_score': 90, 'summary': 'ok'}
manifest3 = {'TIP': '记住'}
result3 = _programmatic_text_check(ocr3, manifest3)
assert len(result3['errors']) == 0
print('Test3 PASS: short text skipped')

# Test 4: multiple truncations
ocr4 = {
    'found_texts': ['提升语言运用能', '实则考试快速概'],
    'errors': [],
    'overall_score': 95,
    'summary': 'ok'
}
manifest4 = {'SLOGAN': '提升语言运用能力', 'LINE1': '实则考试快速概忆'}
result4 = _programmatic_text_check(ocr4, manifest4)
assert len(result4['errors']) == 2, f"Expected 2 errors, got {result4['errors']}"
print('Test4 PASS: multiple truncations')

# Test 5: already-reported error should not duplicate
ocr5 = {
    'found_texts': ['提升语言运用能'],
    'errors': [{'expected': '提升语言运用能力', 'actual': '提升语言运用能', 'type': 'truncated', 'severity': 'high'}],
    'overall_score': 80,
    'summary': 'truncated'
}
result5 = _programmatic_text_check(ocr5, manifest)
assert len(result5['errors']) == 1, f"Expected 1 error (no dup), got {result5['errors']}"
print('Test5 PASS: no duplicate errors')

print('\nALL TESTS PASSED')
