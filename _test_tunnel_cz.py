import urllib.request, json, re

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    return urllib.request.urlopen(req, timeout=10)

# 1. Test Tunnel JSON files
print("=== Tunnel JSON Tests ===")
for name, path in [
    ("初中 数学_七上_总结", "/knowledge_cards/%E5%88%9D%E4%B8%AD/%E6%95%B0%E5%AD%A6_%E4%B8%83%E4%B8%8A_%E6%80%BB%E7%BB%93.json"),
    ("小学 数学_三下", "/knowledge_cards/%E5%B0%8F%E5%AD%A6/%E6%95%B0%E5%AD%A6_%E4%B8%89%E4%B8%8B.json"),
    ("manifest", "/knowledge_cards/manifest.json"),
]:
    try:
        r = fetch("https://xhs.xiaohsai.com" + path)
        d = json.loads(r.read().decode('utf-8'))
        if 'stages' in d:
            print(f"  OK {name}: stages={list(d['stages'].keys())}")
        else:
            print(f"  OK {name}: pack={d.get('pack_name','?')} units={len(d.get('units',[]))}")
    except Exception as e:
        print(f"  FAIL {name}: {e}")

# 2. Test if HTML has the summaryOnly fix
print("\n=== HTML Fix Check ===")
try:
    r = fetch("https://xhs.xiaohsai.com/")
    c = r.read().decode('utf-8')
    print(f"  Has isSummaryOnly: {'isSummaryOnly' in c}")
    m = re.search(r"PAGE_BUILD = '([^']+)'", c)
    print(f"  PAGE_BUILD: {m.group(1) if m else 'N/A'}")
except Exception as e:
    print(f"  FAIL: {e}")

# 3. Test GitHub Pages
print("\n=== GitHub Pages Tests ===")
for name, path in [
    ("manifest", "/xhs-emotion-platform/knowledge_cards/manifest.json"),
    ("初中 数学_七上_总结", "/xhs-emotion-platform/knowledge_cards/%E5%88%9D%E4%B8%AD/%E6%95%B0%E5%AD%A6_%E4%B8%83%E4%B8%8A_%E6%80%BB%E7%BB%93.json"),
]:
    try:
        r = fetch("https://lincsd.github.io" + path)
        d = json.loads(r.read().decode('utf-8'))
        if 'stages' in d:
            print(f"  OK {name}: stages={list(d['stages'].keys())}")
        else:
            print(f"  OK {name}: pack={d.get('pack_name','?')} units={len(d.get('units',[]))}")
    except Exception as e:
        print(f"  FAIL {name}: {e}")

# HTML fix
try:
    r = fetch("https://lincsd.github.io/xhs-emotion-platform/")
    c = r.read().decode('utf-8')
    print(f"  Has isSummaryOnly: {'isSummaryOnly' in c}")
    m = re.search(r"PAGE_BUILD = '([^']+)'", c)
    print(f"  PAGE_BUILD: {m.group(1) if m else 'N/A'}")
except Exception as e:
    print(f"  HTML FAIL: {e}")

# 4. Test local
print("\n=== Local Tests ===")
try:
    r = urllib.request.urlopen("http://localhost:3000/knowledge_cards/%E5%88%9D%E4%B8%AD/%E6%95%B0%E5%AD%A6_%E4%B8%83%E4%B8%8A_%E6%80%BB%E7%BB%93.json", timeout=5)
    d = json.loads(r.read().decode('utf-8'))
    print(f"  OK local 初中: pack={d.get('pack_name','?')} units={len(d.get('units',[]))}")
except Exception as e:
    print(f"  FAIL local 初中: {e}")

try:
    r = urllib.request.urlopen("http://localhost:3000/", timeout=5)
    c = r.read().decode('utf-8')
    print(f"  Has isSummaryOnly: {'isSummaryOnly' in c}")
    m = re.search(r"PAGE_BUILD = '([^']+)'", c)
    print(f"  PAGE_BUILD: {m.group(1) if m else 'N/A'}")
except Exception as e:
    print(f"  FAIL local HTML: {e}")
