#!/usr/bin/env python3
"""Test content generation API"""
import urllib.request
import json

BASE = "http://localhost:3000"

def test_stats():
    r = urllib.request.urlopen(f"{BASE}/api/stats")
    data = json.loads(r.read())
    print(f"[OK] /api/stats - totalPosts: {data['totalPosts']}")
    return True

def test_generate():
    body = json.dumps({"count": 3, "category": ""}).encode()
    req = urllib.request.Request(f"{BASE}/api/generate", data=body, 
                                 headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req)
    data = json.loads(r.read())
    posts = data.get("posts", [])
    print(f"[OK] /api/generate - {data['message']}")
    for p in posts:
        print(f"     [{p['category']}] {p['title'][:30]}...")
        print(f"       tags: {p['tags']}")
        print(f"       cover: {p['cover_text']}")
        assert p['content'], "Content should not be empty"
        assert p['tags'], "Tags should not be empty"
        assert p['cover_text'], "Cover text should not be empty"
    return True

def test_posts_crud():
    # List
    r = urllib.request.urlopen(f"{BASE}/api/posts")
    data = json.loads(r.read())
    print(f"[OK] GET /api/posts - {data['total']} posts")
    
    # Get single
    if data['total'] > 0:
        pid = data['posts'][0]['id']
        r = urllib.request.urlopen(f"{BASE}/api/posts/{pid}")
        post = json.loads(r.read())
        print(f"[OK] GET /api/posts/{pid} - {post['title'][:30]}")
    return True

if __name__ == "__main__":
    tests = [test_stats, test_generate, test_posts_crud]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1
    
    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("All tests PASSED!")
    else:
        print("Some tests FAILED!")
