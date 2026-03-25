import json, os, glob

# Update both manifests (public/ and root)
for manifest_path in [
    'd:/Users/Administrator/Desktop/ls/xhsqg/public/knowledge_cards/manifest.json',
    'd:/Users/Administrator/Desktop/ls/xhsqg/knowledge_cards/manifest.json'
]:
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    # Remove any existing summary entries to avoid duplicates
    manifest['stages']['小学'] = [
        e for e in manifest['stages']['小学']
        if not e['file'].endswith('_总结.json')
    ]

    # Add all summary files
    new_cards = 0
    new_files = 0
    for fp in sorted(glob.glob('d:/Users/Administrator/Desktop/ls/xhsqg/public/knowledge_cards/小学/*_总结.json')):
        with open(fp, 'r', encoding='utf-8') as f:
            data = json.load(f)
        fname = os.path.basename(fp)
        cards = sum(len(u['cards']) for u in data['units'])
        units = len(data['units'])
        entry = {
            "file": fname,
            "subject": data['subject'],
            "grade": data['grade'],
            "semester": data['semester'],
            "grade_short": data.get('grade_short', ''),
            "card_pack": "知识总结",
            "is_boom": False,
            "units": units,
            "cards": cards
        }
        manifest['stages']['小学'].append(entry)
        new_cards += cards
        new_files += 1

    # Update totals
    old_files = manifest.get('total_files', 0)
    old_cards = manifest.get('total_cards', 0)
    manifest['total_files'] = old_files + new_files
    manifest['total_cards'] = old_cards + new_cards

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f'Updated {manifest_path}:')
    print(f'  Added {new_files} summary files with {new_cards} cards')
    print(f'  Total: {manifest["total_files"]} files, {manifest["total_cards"]} cards')
