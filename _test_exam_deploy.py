#!/usr/bin/env python3
"""测试考卷真题功能在所有服务上的部署状态"""
import urllib.request, json, ssl, sys, time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_peer = False

SERVICES = {
    'Localhost': 'http://localhost:3000',
    'Tunnel':    'https://xhs.xiaohsai.com',
    'Render':    'https://xhs-gemini-proxy.onrender.com',
    'GitHub':    'https://lincsd.github.io/xhs-emotion-platform',
}

def fetch(url, timeout=15):
    try:
        # 对中文路径进行正确的 URL 编码
        from urllib.parse import quote, urlparse, urlunparse
        parsed = urlparse(url)
        encoded_path = quote(parsed.path, safe='/:@!$&\'()*+,;=-._~')
        url = urlunparse(parsed._replace(path=encoded_path))
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        r = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return r.status, r.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        return e.code, ''
    except Exception as e:
        return 0, str(e)

print('='*70)
print('考卷真题功能部署测试')
print('='*70)

results = {}

for name, base in SERVICES.items():
    print(f'\n{"─"*50}')
    print(f'📡 {name}: {base}')
    print(f'{"─"*50}')
    
    checks = {}
    
    # 1) 版本/可达性
    if name == 'GitHub':
        ver_url = base + '/index.html'
    else:
        ver_url = base + '/api/version'
    
    status, body = fetch(ver_url)
    if status == 200:
        if name == 'GitHub':
            # 从 HTML 中提取版本
            import re
            m = re.search(r'version.*?(\d{8}\w*)', body)
            ver = m.group(1) if m else 'unknown'
            print(f'  ✅ 可达 (version={ver})')
        else:
            try:
                d = json.loads(body)
                ver = d.get('version', 'unknown')
                print(f'  ✅ 可达 (version={ver})')
            except:
                print(f'  ✅ 可达 (非JSON)')
        checks['reachable'] = True
    else:
        print(f'  ❌ 不可达 (HTTP {status})')
        checks['reachable'] = False
        results[name] = checks
        continue
    
    # 2) Manifest 检查
    if name == 'GitHub':
        manifest_url = base + '/knowledge_cards/manifest.json'
    else:
        manifest_url = base + '/knowledge_cards/manifest.json'
    
    status, body = fetch(manifest_url)
    if status == 200:
        try:
            manifest = json.loads(body)
            entries = manifest.get('stages', {}).get('小学', [])
            total = len(entries)
            exam_entries = [e for e in entries if e.get('is_exam')]
            print(f'  ✅ Manifest: {total} 条目, {len(exam_entries)} 条考卷')
            for e in exam_entries:
                print(f'     📋 {e["file"]} ({e["subject"]} {e["grade_short"]}, {e["cards"]}张卡片)')
            checks['manifest'] = len(exam_entries) > 0
        except Exception as ex:
            print(f'  ❌ Manifest JSON 解析失败: {ex}')
            checks['manifest'] = False
    else:
        print(f'  ❌ Manifest 404 (HTTP {status})')
        checks['manifest'] = False
    
    # 3) 考卷JSON 检查
    if name == 'GitHub':
        exam_url = base + '/knowledge_cards/小学/数学_三下_考卷.json'
    else:
        exam_url = base + '/knowledge_cards/小学/数学_三下_考卷.json'
    
    status, body = fetch(exam_url)
    if status == 200:
        try:
            data = json.loads(body)
            units = data.get('units', [])
            cards = sum(len(u.get('cards', [])) for u in units)
            pack = data.get('card_pack', 'N/A')
            print(f'  ✅ 考卷JSON: card_pack="{pack}", {len(units)}单元, {cards}张卡片')
            # 检查卡片字段完整性
            if units and units[0].get('cards'):
                c = units[0]['cards'][0]
                fields = ['card_id', 'title', 'type', 'definition', 'core_points', 'example', 'mistakes', 'memory_tip']
                missing = [f for f in fields if f not in c]
                if missing:
                    print(f'  ⚠️  首张卡片缺少字段: {missing}')
                else:
                    print(f'  ✅ 卡片字段完整 (首张: {c["card_id"]} {c["title"]})')
            checks['exam_json'] = True
        except Exception as ex:
            print(f'  ❌ 考卷JSON 解析失败: {ex}')
            checks['exam_json'] = False
    else:
        print(f'  ❌ 考卷JSON 不可达 (HTTP {status})')
        checks['exam_json'] = False
    
    # 4) 前端代码检查（是否包含 examFiles 逻辑）
    if name == 'GitHub':
        html_url = base + '/index.html'
    else:
        html_url = base + '/'
    
    status, body = fetch(html_url)
    if status == 200:
        has_exam_files = 'examFiles' in body
        has_exam_resps = 'examResps' in body
        has_is_exam_filter = '!e.is_exam' in body
        if has_exam_files and has_exam_resps and has_is_exam_filter:
            print(f'  ✅ 前端代码: 包含考卷加载逻辑 (examFiles✓ examResps✓ is_exam过滤✓)')
            checks['frontend'] = True
        else:
            print(f'  ❌ 前端代码: 缺少考卷逻辑 (examFiles={has_exam_files} examResps={has_exam_resps} is_exam={has_is_exam_filter})')
            checks['frontend'] = False
    else:
        print(f'  ❌ 前端不可达 (HTTP {status})')
        checks['frontend'] = False
    
    results[name] = checks

# 汇总
print(f'\n{"="*70}')
print('📊 汇总')
print(f'{"="*70}')
all_ok = True
for name, checks in results.items():
    items = []
    for k, v in checks.items():
        items.append(f'{k}:{"✅" if v else "❌"}')
    overall = '✅' if all(checks.values()) else '❌'
    print(f'  {overall} {name:12s} → {", ".join(items)}')
    if not all(checks.values()):
        all_ok = False

print()
if all_ok:
    print('🎉 所有服务均已正确部署考卷真题功能！')
else:
    print('⚠️  部分服务存在问题，请检查上方详情。')

sys.exit(0 if all_ok else 1)
