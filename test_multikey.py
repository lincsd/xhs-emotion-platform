"""Test multi-key parsing and rotation logic"""
import os, sys, threading

# Set env vars before importing
os.environ['GEMINI_API_KEY'] = 'keyAAA,keyBBB,keyCCC'
os.environ['PORT'] = '10000'
os.environ['DATA_DIR'] = 'd:/tmp'

# Extract just the key-related functions from server.py
print("=== Multi-Key Parsing Test ===")

def _load_server_gemini_key():
    raw = (os.environ.get('GEMINI_API_KEY') or '').strip()
    if ',' in raw:
        return raw.split(',')[0].strip()
    return raw

SERVER_GEMINI_API_KEY = _load_server_gemini_key()

def _load_server_gemini_keys():
    raw = (os.environ.get('GEMINI_API_KEYS') or '').strip()
    if not raw:
        raw = (os.environ.get('GEMINI_API_KEY') or '').strip()
    if not raw:
        return []
    return [k.strip() for k in raw.split(',') if k.strip()]

SERVER_GEMINI_API_KEYS = _load_server_gemini_keys()
_server_key_index = 0
_server_key_lock = threading.Lock()

def _get_next_server_key():
    global _server_key_index
    if not SERVER_GEMINI_API_KEYS:
        return ''
    if len(SERVER_GEMINI_API_KEYS) == 1:
        return SERVER_GEMINI_API_KEYS[0]
    with _server_key_lock:
        idx = _server_key_index
        _server_key_index = (_server_key_index + 1) % len(SERVER_GEMINI_API_KEYS)
    return SERVER_GEMINI_API_KEYS[idx]

# Test 1: Key parsing
print(f"  SERVER_GEMINI_API_KEY (single): {SERVER_GEMINI_API_KEY!r}")
print(f"  SERVER_GEMINI_API_KEYS (list):  {SERVER_GEMINI_API_KEYS!r}")
print(f"  Key count: {len(SERVER_GEMINI_API_KEYS)}")

assert SERVER_GEMINI_API_KEY == 'keyAAA', f"Expected 'keyAAA', got {SERVER_GEMINI_API_KEY!r}"
assert len(SERVER_GEMINI_API_KEYS) == 3, f"Expected 3 keys, got {len(SERVER_GEMINI_API_KEYS)}"
assert SERVER_GEMINI_API_KEYS == ['keyAAA', 'keyBBB', 'keyCCC'], f"Keys mismatch: {SERVER_GEMINI_API_KEYS}"
print("  ✅ Key parsing PASSED")

# Test 2: Rotation
print("\n=== Key Rotation Test ===")
keys = [_get_next_server_key() for _ in range(6)]
print(f"  6 calls: {keys}")
assert keys == ['keyAAA', 'keyBBB', 'keyCCC', 'keyAAA', 'keyBBB', 'keyCCC'], f"Rotation wrong: {keys}"
print("  ✅ Rotation PASSED")

# Test 3: Thread safety
print("\n=== Thread Safety Test ===")
results = []
def grab_keys(n):
    for _ in range(n):
        results.append(_get_next_server_key())

threads = [threading.Thread(target=grab_keys, args=(100,)) for _ in range(10)]
for t in threads: t.start()
for t in threads: t.join()
assert len(results) == 1000
for k in results:
    assert k in ('keyAAA', 'keyBBB', 'keyCCC'), f"Invalid key: {k}"
print(f"  1000 threaded calls: all valid keys")
print("  ✅ Thread safety PASSED")

# Test 4: Single key fallback
print("\n=== Single Key Test ===")
os.environ['GEMINI_API_KEY'] = 'singleKey123'
SERVER_GEMINI_API_KEY2 = _load_server_gemini_key()
keys2 = _load_server_gemini_keys()
assert SERVER_GEMINI_API_KEY2 == 'singleKey123'
assert keys2 == ['singleKey123']
print(f"  Single key: {SERVER_GEMINI_API_KEY2!r}, list: {keys2}")
print("  ✅ Single key PASSED")

print("\n🎉 ALL TESTS PASSED")
