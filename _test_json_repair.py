"""Test _safe_parse_json robustness"""
import sys
sys.path.insert(0, '.')
from generate_card_images_v3 import _safe_parse_json

tests = [
    ("trailing comma", '{"a": 1, "b": [1, 2,], "c": {"x": 3,},}'),
    ("comment", '{"score": 85, // good\n"text": "hello"}'),
    ("code block", '```json\n{"found_texts": ["hello"], "overall_score": 90}\n```'),
    ("valid", '{"found_texts": ["test"], "overall_score": 100}'),
    ("missing comma in array", '{"found_texts": ["hello" "world"], "overall_score": 80}'),
    ("real LLM trailing + comment", '{\n  "found_texts": ["口算整百整十除法", "300÷5=60",],\n  // audit results\n  "overall_score": 85,\n  "errors": [],\n  "summary": "good",\n  "quality": {"teaching": 16, "text_accuracy": 18, "visual": 17, "layout": 15, "saveable": 16, "total": 82, "comment": "nice",}\n}'),
]

for name, raw in tests:
    r = _safe_parse_json(raw)
    status = "OK" if r else "FAIL"
    print(f"  {status}: {name}")
    if r:
        keys = list(r.keys())[:4]
        print(f"       keys={keys}")

print("\nDone.")
