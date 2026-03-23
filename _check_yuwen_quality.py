#!/usr/bin/env python3
"""语文知识卡片质量抽检脚本"""
import json, os, random

BASE = 'knowledge_cards/小学'
ISSUES = []

def check_card(card, filename, unit_name):
    """检查单张卡片的质量"""
    problems = []
    cid = card.get('full_id', card.get('card_id', '?'))
    
    # 必填字段检查
    required = ['card_id', 'full_id', 'title', 'type', 'difficulty', 'importance',
                'definition', 'core_points', 'example', 'mistakes', 'memory_tip']
    for f in required:
        if f not in card or not card[f]:
            problems.append(f'缺少字段: {f}')
    
    # 类型检查
    if card.get('difficulty') and not (1 <= card['difficulty'] <= 5):
        problems.append(f'难度超范围: {card["difficulty"]}')
    if card.get('importance') and not (1 <= card['importance'] <= 5):
        problems.append(f'重要性超范围: {card["importance"]}')
    
    # example 结构检查
    ex = card.get('example', {})
    if isinstance(ex, dict):
        if 'question' not in ex:
            problems.append('example缺少question')
        if 'steps' not in ex or not isinstance(ex.get('steps'), list):
            problems.append('example缺少steps或格式错误')
        if 'answer' not in ex:
            problems.append('example缺少answer')
    else:
        problems.append('example格式非dict')
    
    # mistakes 检查
    mistakes = card.get('mistakes', [])
    if isinstance(mistakes, list):
        for m in mistakes:
            if not isinstance(m, dict) or 'wrong' not in m or 'correct' not in m:
                problems.append('mistakes条目缺少wrong/correct')
                break
    
    # core_points 检查
    cp = card.get('core_points', [])
    if not isinstance(cp, list) or len(cp) < 2:
        problems.append(f'core_points过少: {len(cp) if isinstance(cp, list) else "非list"}')
    
    # 内容质量抽检 (简单检查)
    title = card.get('title', '')
    if len(title) > 50:
        problems.append(f'标题过长: {len(title)}字')
    
    definition = card.get('definition', '')
    if len(definition) < 5:
        problems.append(f'definition过短: {len(definition)}字')
    
    memory_tip = card.get('memory_tip', '')
    if isinstance(memory_tip, str) and len(memory_tip) < 3:
        problems.append(f'memory_tip过短: {len(memory_tip)}字')
    
    return problems

def check_file(filepath):
    """检查单个文件"""
    fname = os.path.basename(filepath)
    try:
        data = json.loads(open(filepath, encoding='utf-8').read())
    except Exception as e:
        ISSUES.append((fname, 'FILE', f'JSON解析失败: {e}'))
        return
    
    # 顶层结构检查
    for key in ['subject', 'grade', 'semester', 'grade_short', 'units']:
        if key not in data:
            ISSUES.append((fname, 'STRUCT', f'缺少顶层字段: {key}'))
    
    units = data.get('units', [])
    if not units:
        ISSUES.append((fname, 'STRUCT', '无单元数据'))
        return
    
    total_cards = 0
    for u in units:
        uid = u.get('unit_id', '?')
        uname = u.get('unit_name', '?')
        cards = u.get('cards', [])
        
        if not cards:
            ISSUES.append((fname, f'U{uid}', '单元无卡片'))
            continue
        
        for card in cards:
            total_cards += 1
            problems = check_card(card, fname, uname)
            for p in problems:
                ISSUES.append((fname, card.get('full_id', '?'), p))
    
    return total_cards

def main():
    files = sorted([f for f in os.listdir(BASE) if f.startswith('语文') and f.endswith('.json')])
    
    print(f"📋 语文知识卡片质量抽检")
    print(f"{'='*60}")
    print(f"  检查文件数: {len(files)}")
    print()
    
    total = 0
    stats = {}
    for f in files:
        fp = os.path.join(BASE, f)
        n = check_file(fp)
        if n:
            total += n
            stats[f] = n
            print(f"  ✅ {f}: {n} 张卡片")
        else:
            print(f"  ⚠️ {f}: 检查失败")
    
    print(f"\n  📊 总计: {len(files)} 个文件, {total} 张卡片")
    
    # 报告问题
    if ISSUES:
        print(f"\n{'='*60}")
        print(f"  ⚠️ 发现 {len(ISSUES)} 个问题:")
        print(f"{'='*60}")
        for fname, location, problem in ISSUES:
            print(f"  [{fname}] {location}: {problem}")
    else:
        print(f"\n  🎉 全部通过！无结构性问题。")
    
    # 内容抽样展示
    print(f"\n{'='*60}")
    print(f"  📖 随机抽样展示 (3张卡片)")
    print(f"{'='*60}")
    
    all_cards = []
    for f in files:
        fp = os.path.join(BASE, f)
        try:
            data = json.loads(open(fp, encoding='utf-8').read())
            for u in data.get('units', []):
                for c in u.get('cards', []):
                    all_cards.append((f, c))
        except:
            pass
    
    if all_cards:
        samples = random.sample(all_cards, min(3, len(all_cards)))
        for fname, card in samples:
            print(f"\n  📄 {fname} → {card.get('full_id','?')}")
            print(f"     标题: {card.get('title','?')}")
            print(f"     类型: {card.get('type','?')}")
            print(f"     定义: {card.get('definition','?')[:80]}...")
            print(f"     要点: {card.get('core_points',['?'])[0][:60]}...")
            ex = card.get('example', {})
            print(f"     例题: {ex.get('question','?')[:60]}...")
            print(f"     口诀: {card.get('memory_tip','?')[:60]}...")

if __name__ == '__main__':
    main()
