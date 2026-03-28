import base64, os

out = r'd:\Users\Administrator\Desktop\ls\xhsqg\_test_v10_output'
files = [f for f in os.listdir(out) if f.endswith(('.jpg', '.png'))]

html = '''<html><head><meta charset="utf-8"><title>v10.4 E2E</title>
<style>body{background:#1a1a2e;color:#fff;font-family:sans-serif;text-align:center;padding:20px}
img{max-width:480px;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.5);margin:20px;display:inline-block}
h2{color:#f0a}h1{color:#eee}</style></head><body>
<h1>v10.4 AI Full Render - E2E Results</h1>'''

for f in sorted(files):
    path = os.path.join(out, f)
    b64 = base64.b64encode(open(path, 'rb').read()).decode()
    html += f'<h2>{f}</h2><img src="data:image/jpeg;base64,{b64}"><br>\n'

html += '</body></html>'
p = os.path.join(out, '_preview.html')
with open(p, 'w', encoding='utf-8') as fp:
    fp.write(html)
print(f'Preview: {p}')
