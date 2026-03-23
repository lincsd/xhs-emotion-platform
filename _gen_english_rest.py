"""继续生成英语卡片: 四下~六下 (之前在四下超时)"""
import subprocess, sys

PYTHON = sys.executable
GRADES = ['四下','五上','五下','六上','六下']

def run(grade, boom=False):
    args = [PYTHON, 'generate_knowledge_cards.py', '--stage', '小学', '--subject', '英语', '--grade', grade]
    if boom:
        args.append('--boom')
    print(f"\n{'='*50}\n  🚀 {'爆款' if boom else '标准'} 英语_{grade}\n{'='*50}\n")
    try:
        r = subprocess.run(args, timeout=300)  # 增加到5分钟
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"  ⏰ 超时: 英语_{grade} {'爆款' if boom else '标准'}")
        return False

ok, fail = 0, 0
for g in GRADES:
    if run(g, boom=False):
        ok += 1
    else:
        fail += 1
    if run(g, boom=True):
        ok += 1
    else:
        fail += 1

print(f"\n{'='*50}")
print(f"  ✅ 完成: {ok} 成功, {fail} 失败")
print(f"{'='*50}")
