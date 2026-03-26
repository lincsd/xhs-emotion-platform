import urllib.request, json

checks = [
    ("Local", "http://localhost:3000/api/version"),
    ("Tunnel", "https://xhs.xiaohsai.com/api/version"),
    ("Render", "https://xhs-gemini-proxy.onrender.com/api/version"),
]

for name, url in checks:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        r = urllib.request.urlopen(req, timeout=20)
        print(f"{name}: {r.read().decode().strip()}")
    except Exception as e:
        print(f"{name}: FAIL - {e}")

# GitHub Pages manifest
try:
    r = urllib.request.urlopen("https://lincsd.github.io/xhs-emotion-platform/knowledge_cards/manifest.json", timeout=10)
    d = json.loads(r.read())
    total_files = sum(len(v) for v in d.get("stages", {}).values())
    summary_count = sum(1 for v in d.get("stages", {}).values() for e in v if e.get("is_summary"))
    print(f"GH Pages: {total_files} files, {d.get('total_cards','?')} cards, {summary_count} summary packs")
except Exception as e:
    print(f"GH Pages: FAIL - {e}")
