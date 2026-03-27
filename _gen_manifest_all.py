"""Generate manifest.json for ALL stages (小学/初中/高中/养生减脂/国学文化/情感生活)."""
import json, os, re, shutil

PUBLIC_BASE = 'public/knowledge_cards'

def scan_stage(folder, stage_name):
    """Scan a stage folder and return manifest entries."""
    base = os.path.join(PUBLIC_BASE, folder)
    if not os.path.isdir(base):
        print(f'  [SKIP] {base} not found')
        return []
    entries = []
    for f in sorted(os.listdir(base)):
        if not f.endswith('.json') or f == 'manifest.json':
            continue
        fp = os.path.join(base, f)
        try:
            data = json.loads(open(fp, encoding='utf-8').read())
        except Exception as e:
            print(f'  [ERR] {f}: {e}')
            continue

        is_boom = '爆款' in f
        is_exam = '考卷' in f
        is_summary = '总结' in f
        parts = f.replace('.json', '').split('_')
        subject = parts[0]
        grade_short = parts[1]

        # Remove type suffixes from grade_short
        for suffix in ['爆款', '考卷', '总结']:
            if grade_short == suffix and len(parts) > 2:
                grade_short = parts[1]
            if len(parts) > 2 and parts[-1] == suffix:
                grade_short = parts[1]

        # Grade / semester mapping
        grade, semester = grade_short, ''
        if stage_name == '小学':
            grade_map = {'一': '一年级', '二': '二年级', '三': '三年级', '四': '四年级', '五': '五年级', '六': '六年级'}
            sem_map = {'上': '上册', '下': '下册'}
            if len(grade_short) >= 2:
                grade = grade_map.get(grade_short[0], grade_short)
                semester = sem_map.get(grade_short[-1], '')
        elif stage_name == '初中':
            grade_map = {'七': '七年级', '八': '八年级', '九': '九年级'}
            sem_map = {'上': '上册', '下': '下册'}
            if len(grade_short) >= 2:
                grade = grade_map.get(grade_short[0], grade_short)
                semester = sem_map.get(grade_short[-1], '')
        elif stage_name == '高中':
            # grade_short like 高一上, 高二下, etc.
            m = re.match(r'(高[一二三])(上|下)', grade_short)
            if m:
                grade = m.group(1)
                semester = {'上': '上册', '下': '下册'}.get(m.group(2), '')
            else:
                grade = grade_short
        else:
            # 养生减脂, 国学文化, 情感生活
            grade = grade_short
            semester = '核心'

        # Count units and cards
        total_cards = 0
        total_units = 0
        if isinstance(data, dict) and 'units' in data:
            for u in data['units']:
                total_units += 1
                total_cards += len(u.get('cards', []))
        elif isinstance(data, dict) and 'packs' in data:
            for p in data['packs']:
                total_units += 1
                total_cards += len(p.get('cards', []))
        elif isinstance(data, list):
            for p in data:
                total_units += 1
                total_cards += len(p.get('cards', []))

        entry = {
            'file': f,
            'subject': subject,
            'grade': grade,
            'semester': semester,
            'grade_short': grade_short,
        }
        if is_boom:
            entry['is_boom'] = True
        elif is_exam:
            entry['is_exam'] = True
        elif is_summary:
            entry['is_summary'] = True
        else:
            entry['is_boom'] = False  # standard card
        entry['units'] = total_units
        entry['cards'] = total_cards
        entries.append(entry)

    return entries


def main():
    stages = {
        '小学': '小学',
        '初中': '初中',
        '高中': '高中',
        '养生减脂': '养生减脂',
        '国学文化': '国学文化',
        '情感生活': '情感生活',
    }

    manifest = {'stages': {}}
    total_cards = 0
    total_files = 0

    for stage_name, folder in stages.items():
        entries = scan_stage(folder, stage_name)
        if entries:
            manifest['stages'][stage_name] = entries
            sc = sum(e['cards'] for e in entries)
            total_cards += sc
            total_files += len(entries)
            print(f'{stage_name}: {len(entries)} files, {sc} cards')
            for e in entries:
                tag = '🔥' if e.get('is_boom') == True else ('📝' if e.get('is_exam') else ('📋' if e.get('is_summary') else '📘'))
                print(f'  {tag} {e["file"]} u={e["units"]} c={e["cards"]}')

    manifest['total_cards'] = total_cards
    manifest['total_files'] = total_files

    out = os.path.join(PUBLIC_BASE, 'manifest.json')
    with open(out, 'w', encoding='utf-8') as mf:
        json.dump(manifest, mf, ensure_ascii=False, indent=2)
    print(f'\nWritten {out}: {total_files} files, {total_cards} cards')

    # Also copy to source
    src_out = 'knowledge_cards/manifest.json'
    shutil.copy2(out, src_out)
    print(f'Copied to {src_out}')


if __name__ == '__main__':
    main()
