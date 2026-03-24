#!/usr/bin/env python3
"""Quick deployment status check"""
import urllib.request, re, subprocess, os, time

def check(name, url, headers=None, timeout=15):
    try:
        req = urllib.request.Request(url, headers=headers or {})
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, r.read().decode('utf-8', errors='replace')[:500]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace')[:300]
    except Exception as e:
        return 0, str(e)[:200]

# Check cloudflared process
result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq cloudflared.exe'], 
                       capture_output=True, text=True)
has_cf = 'cloudflared.exe' in result.stdout
print(f"cloudflared process: {'RUNNING' if has_cf else 'NOT RUNNING'}")

if not has_cf:
    print("Starting cloudflared...")
    cf_path = os.path.expanduser('~') + '\\cloudflared.exe'
    subprocess.Popen([cf_path, 'tunnel', '--protocol', 'http2', 'run'],
                     creationflags=0x08000000)
    time.sleep(10)
    print("cloudflared started, waiting for connections...")

browser_ua = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'}

# 1. Tunnel
print("\n=== TUNNEL (xhs.xiaohsai.com) ===")
code, body = check("tunnel", "https://xhs.xiaohsai.com/", browser_ua)
if code == 200:
    m = re.search(r"BUILD='([^']+)'", body)
    build = m.group(1) if m else 'N/A'
    print(f"  Status: {code} OK, BUILD={build}")
elif code == 403:
    print(f"  Status: {code} (Cloudflare Bot Fight Mode - normal for CLI, works in browser)")
else:
    print(f"  Status: {code} - {body[:100]}")

# 2. Render
print("\n=== RENDER (xhs-gemini-proxy.onrender.com) ===")
code, body = check("render", "https://xhs-gemini-proxy.onrender.com/", browser_ua, timeout=30)
if code == 200:
    m = re.search(r"v=([^&\"']+)", body)
    ver = m.group(1) if m else 'N/A'
    print(f"  Status: {code} OK, version={ver}")
else:
    print(f"  Status: {code} - {body[:100]}")

# 3. GitHub Pages
print("\n=== GITHUB PAGES ===")
code, body = check("github", "https://lincsd.github.io/xhs-emotion-platform/public/index.html")
if code == 200:
    m = re.search(r"BUILD='([^']+)'", body)
    build = m.group(1) if m else 'N/A'
    print(f"  Status: {code} OK, BUILD={build}")
else:
    print(f"  Status: {code} - {body[:100]}")

# 4. Localhost
print("\n=== LOCALHOST ===")
code, body = check("localhost", "http://localhost:3000/")
if code == 200:
    m = re.search(r"v=([^&\"']+)", body)
    ver = m.group(1) if m else 'N/A'
    print(f"  Status: {code} OK, version={ver}")
else:
    print(f"  Status: {code} - {body[:100]}")

print("\n=== DONE ===")
