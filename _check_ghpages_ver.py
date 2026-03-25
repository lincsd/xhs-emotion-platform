import urllib.request, re
r = urllib.request.urlopen(
    urllib.request.Request('https://lincsd.github.io/xhs-emotion-platform/', 
                          headers={'User-Agent':'Mozilla/5.0'}), timeout=15)
html = r.read().decode()[:5000]
m = re.search(r"BUILD='([^']+)'", html)
print('GitHub Pages BUILD:', m.group(1) if m else 'not found')
