import json

# Add is_summary flag to all summary manifest entries
for manifest_path in [
    'd:/Users/Administrator/Desktop/ls/xhsqg/public/knowledge_cards/manifest.json',
    'd:/Users/Administrator/Desktop/ls/xhsqg/knowledge_cards/manifest.json'
]:
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    count = 0
    for entry in manifest['stages'].get('小学', []):
        if entry.get('card_pack') == '知识总结':
            entry['is_summary'] = True
            count += 1

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f'{manifest_path}: marked {count} entries with is_summary=true')
