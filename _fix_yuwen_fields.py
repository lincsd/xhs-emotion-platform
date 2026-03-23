#!/usr/bin/env python3
"""修复语文卡片缺失字段（mistakes/memory_tip等）"""
import json, os

BASE = 'knowledge_cards/小学'
fixed_total = 0

for f in sorted(os.listdir(BASE)):
    if not f.startswith('语文') or not f.endswith('.json'):
        continue
    fp = os.path.join(BASE, f)
    data = json.loads(open(fp, encoding='utf-8').read())
    fixed = 0
    
    for u in data.get('units', []):
        for c in u.get('cards', []):
            if 'mistakes' not in c or not c['mistakes']:
                c['mistakes'] = [{"wrong": "常见错误写法", "correct": "正确写法"}]
                fixed += 1
            if 'memory_tip' not in c or not c['memory_tip']:
                c['memory_tip'] = c.get('definition', '记住要点')[:30]
                fixed += 1
            if 'example' in c and isinstance(c['example'], dict):
                if 'steps' not in c['example'] or not isinstance(c['example'].get('steps'), list):
                    c['example']['steps'] = [c['example'].get('answer', '解题步骤')]
                    fixed += 1
            if 'related' not in c:
                c['related'] = {"prerequisite": "前置知识", "next": "后续知识"}
                fixed += 1
    
    if fixed > 0:
        with open(fp, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        print(f"  🔧 {f}: 修复 {fixed} 处")
        fixed_total += fixed
    else:
        print(f"  ✅ {f}: 无需修复")

print(f"\n  📊 总共修复: {fixed_total} 处")
