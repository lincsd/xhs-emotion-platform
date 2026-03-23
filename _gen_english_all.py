#!/usr/bin/env python3
"""批量生成英语知识卡（三上~六下，标准+爆款）"""
import subprocess, sys, time

PYTHON = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe"
SCRIPT = "generate_knowledge_cards.py"
GRADES = ['三上','三下','四上','四下','五上','五下','六上','六下']
DELAY = 3

def run(grade, boom=False):
    args = [PYTHON, SCRIPT, '--stage', '小学', '--subject', '英语', '--grade', grade]
    if boom:
        args = [PYTHON, SCRIPT, '--stage', '小学', '--subject', '英语', '--boom', grade]
    label = f"{'爆款' if boom else '标准'} 英语_{grade}"
    print(f"\n{'='*50}")
    print(f"  🚀 {label}")
    print(f"{'='*50}")
    r = subprocess.run(args, timeout=180)
    return r.returncode == 0

results = []
for i, g in enumerate(GRADES):
    # 标准卡
    ok1 = run(g, boom=False)
    results.append((f'英语_{g}', ok1))
    time.sleep(DELAY)
    # 爆款卡
    ok2 = run(g, boom=True)
    results.append((f'英语_{g}_爆款', ok2))
    if i < len(GRADES) - 1:
        time.sleep(DELAY)

print(f"\n{'='*50}")
print(f"  📊 英语卡片生成汇总")
print(f"{'='*50}")
ok = sum(1 for _, r in results if r)
for name, r in results:
    print(f"  {'✅' if r else '❌'} {name}")
print(f"\n  总计: {len(results)} 个, {ok} 成功, {len(results)-ok} 失败")
