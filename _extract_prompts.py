#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 card_prompt_lib/prompts/ 提取所有已生成的 prompt 记录，输出为可嵌入前端的 JSON"""
import json, os, re

base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'card_prompt_lib', 'prompts', '\u6570\u5b66_\u4e09\u4e0b')
idx_file = os.path.join(base, '_index.json')

with open(idx_file, 'r', encoding='utf-8') as f:
    idx = json.load(f)

records = {}
for card_id, info in idx.items():
    md_path = os.path.join(base, info['prompt_file'])
    if not os.path.exists(md_path):
        continue
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract final prompt (Role 4)
    m = re.search(r'## Role 4.*?```\n(.*?)\n```', content, re.DOTALL)
    prompt = m.group(1).strip() if m else ''

    # Extract Role briefs as JSON
    briefs = {}
    for role_num in ['1', '2', '3', '5']:
        rm = re.search(r'## Role ' + role_num + r'.*?```json\n(.*?)\n```', content, re.DOTALL)
        if rm:
            try:
                briefs['R' + role_num] = json.loads(rm.group(1))
            except:
                briefs['R' + role_num] = rm.group(1).strip()[:200]

    records[card_id] = {
        'title': info['title'],
        'type': info['type'],
        'pipeline': info.get('pipeline', 'v1'),
        'score': info.get('audit_score', 0),
        'verdict': info.get('audit_verdict', '?'),
        'generated_at': info['generated_at'],
        'prompt_length': info['prompt_length'],
        'prompt': prompt[:3000],
        'briefs': briefs
    }

# Output
out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'card_prompt_lib', 'prompts_embed.json')
with open(out_file, 'w', encoding='utf-8') as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"Extracted {len(records)} records -> {out_file}")
for k, v in records.items():
    print(f"  {k}: {v['title']} [{v['type']}] prompt={len(v['prompt'])}chars score={v['score']} {v['verdict']}")
