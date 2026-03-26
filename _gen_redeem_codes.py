#!/usr/bin/env python3
"""
兑换码批量生成工具
====================

功能:
  1. 直接操作本地数据库生成兑换码（不需要服务器运行）
  2. 支持多种套餐批量生成
  3. 输出格式：CSV文件（可直接导入小红书商家后台自动发货）
  4. 输出格式：TXT文件（方便手动发送）

使用方法:
  python _gen_redeem_codes.py                    # 交互模式
  python _gen_redeem_codes.py --体验包 10        # 生成10个体验包(100积分)
  python _gen_redeem_codes.py --月卡 5           # 生成5个月卡(500积分)
  python _gen_redeem_codes.py --季卡 3           # 生成3个季卡(2000积分)
  python _gen_redeem_codes.py --年卡 2           # 生成2个年卡(10000积分)
  python _gen_redeem_codes.py --custom 50 20     # 生成20个自定义50积分码
  python _gen_redeem_codes.py --all              # 各套餐各生成5个（测试用）
  python _gen_redeem_codes.py --list              # 查看所有未使用的兑换码
"""

import sqlite3
import secrets
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data.db')

# 套餐定义
PACKAGES = {
    '体验包': {'credits': 100,   'price': 9.9,   'prefix': 'XHS'},
    '月卡':   {'credits': 500,   'price': 39.9,  'prefix': 'XHS'},
    '季卡':   {'credits': 2000,  'price': 99.9,  'prefix': 'XHS'},
    '年卡':   {'credits': 10000, 'price': 399.9, 'prefix': 'XHS'},
}

def gen_code(prefix='XHS'):
    """生成格式为 XHS-XXXX-XXXX-XXXX 的兑换码"""
    seg = secrets.token_hex(6).upper()
    return f'{prefix}-{seg[:4]}-{seg[4:8]}-{seg[8:12]}'


def generate_codes(package_name, count, credits=None, prefix='XHS'):
    """生成兑换码并写入数据库"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    if credits is None:
        pkg = PACKAGES.get(package_name)
        if not pkg:
            print(f'❌ 未知套餐: {package_name}')
            return []
        credits = pkg['credits']
        prefix = pkg.get('prefix', 'XHS')

    codes = []
    for _ in range(count):
        code = gen_code(prefix)
        try:
            conn.execute('INSERT INTO redeem_codes(code, credits) VALUES(?,?)', (code, credits))
            codes.append(code)
        except sqlite3.IntegrityError:
            # 极小概率重复，重试
            code = gen_code(prefix)
            conn.execute('INSERT INTO redeem_codes(code, credits) VALUES(?,?)', (code, credits))
            codes.append(code)
    
    conn.commit()
    conn.close()
    return codes


def save_codes(codes, credits, package_name, output_dir=None):
    """保存兑换码到文件"""
    if output_dir is None:
        output_dir = os.path.join(BASE_DIR, 'redeem_codes')
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # CSV格式（小红书商家后台自动发货用）
    csv_file = os.path.join(output_dir, f'codes_{package_name}_{credits}积分_{timestamp}.csv')
    with open(csv_file, 'w', encoding='utf-8-sig') as f:
        f.write('卡密,面值\n')
        for code in codes:
            f.write(f'{code},{credits}\n')
    
    # TXT格式（手动发送用）
    txt_file = os.path.join(output_dir, f'codes_{package_name}_{credits}积分_{timestamp}.txt')
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write(f'=== {package_name} 兑换码 ({credits}积分) ===\n')
        f.write(f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write(f'数量: {len(codes)} 个\n')
        f.write(f'{"=" * 40}\n\n')
        for i, code in enumerate(codes, 1):
            f.write(f'{i:3d}. {code}\n')
        f.write(f'\n{"=" * 40}\n')
        f.write(f'使用方法:\n')
        f.write(f'1. 打开平台 → 登录\n')
        f.write(f'2. 点击「💎 AI积分」或「积分商城」\n')
        f.write(f'3. 输入兑换码 → 点击「兑换」\n')
        f.write(f'4. 积分自动到账\n')
    
    return csv_file, txt_file


def list_unused_codes():
    """列出所有未使用的兑换码"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT code, credits, created_at FROM redeem_codes WHERE used_by IS NULL ORDER BY credits, created_at'
    ).fetchall()
    conn.close()
    
    if not rows:
        print('📭 没有未使用的兑换码')
        return
    
    print(f'\n📋 未使用的兑换码（共 {len(rows)} 个）:')
    print(f'{"─" * 50}')
    
    current_credits = None
    for row in rows:
        if row['credits'] != current_credits:
            current_credits = row['credits']
            pkg_name = next((k for k, v in PACKAGES.items() if v['credits'] == current_credits), '自定义')
            print(f'\n  💎 {current_credits} 积分 ({pkg_name}):')
        print(f'    {row["code"]}  ({row["created_at"]})')
    
    # 统计
    print(f'\n{"─" * 50}')
    print(f'📊 统计:')
    stats = {}
    for row in rows:
        c = row['credits']
        stats[c] = stats.get(c, 0) + 1
    for credits, count in sorted(stats.items()):
        pkg_name = next((k for k, v in PACKAGES.items() if v['credits'] == credits), '自定义')
        print(f'   {pkg_name}({credits}积分): {count} 个')


def list_used_codes():
    """列出已使用的兑换码"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        '''SELECT r.code, r.credits, r.used_at, u.username, u.nickname 
           FROM redeem_codes r LEFT JOIN users u ON r.used_by = u.id 
           WHERE r.used_by IS NOT NULL 
           ORDER BY r.used_at DESC LIMIT 50'''
    ).fetchall()
    conn.close()
    
    if not rows:
        print('📭 没有已使用的兑换码')
        return
    
    print(f'\n📋 已使用的兑换码（最近50条）:')
    print(f'{"─" * 70}')
    print(f'  {"兑换码":<22} {"积分":>6} {"用户":<12} {"时间"}')
    print(f'{"─" * 70}')
    for row in rows:
        user = row['nickname'] or row['username'] or '未知'
        print(f'  {row["code"]:<22} {row["credits"]:>6} {user:<12} {row["used_at"]}')


def interactive_mode():
    """交互模式"""
    print('\n🎟️  兑换码批量生成工具')
    print('=' * 40)
    print('\n选择套餐:')
    for i, (name, pkg) in enumerate(PACKAGES.items(), 1):
        print(f'  {i}. {name}  ({pkg["credits"]}积分, ¥{pkg["price"]})')
    print(f'  5. 自定义积分')
    print(f'  6. 查看未使用的兑换码')
    print(f'  7. 查看已使用的兑换码')
    
    choice = input('\n请选择 (1-7): ').strip()
    
    if choice == '6':
        list_unused_codes()
        return
    if choice == '7':
        list_used_codes()
        return
    
    if choice == '5':
        credits = int(input('输入积分数量: ').strip())
        package_name = '自定义'
    elif choice in ('1', '2', '3', '4'):
        names = list(PACKAGES.keys())
        package_name = names[int(choice) - 1]
        credits = PACKAGES[package_name]['credits']
    else:
        print('❌ 无效选择')
        return
    
    count = int(input(f'生成数量 (1-100): ').strip())
    if count < 1 or count > 100:
        print('❌ 数量须在 1-100 之间')
        return
    
    print(f'\n⏳ 正在生成 {count} 个 {package_name}({credits}积分) 兑换码...')
    codes = generate_codes(package_name, count, credits)
    csv_file, txt_file = save_codes(codes, credits, package_name)
    
    print(f'\n✅ 成功生成 {len(codes)} 个兑换码!\n')
    for i, code in enumerate(codes, 1):
        print(f'  {i:3d}. {code}')
    print(f'\n📁 已保存到:')
    print(f'  CSV: {csv_file}')
    print(f'  TXT: {txt_file}')


def main():
    args = sys.argv[1:]
    
    if not args:
        interactive_mode()
        return
    
    if args[0] == '--list':
        list_unused_codes()
        return
    
    if args[0] == '--used':
        list_used_codes()
        return
    
    if args[0] == '--all':
        print('⏳ 生成测试兑换码（每种5个）...\n')
        for name, pkg in PACKAGES.items():
            codes = generate_codes(name, 5)
            csv_file, txt_file = save_codes(codes, pkg['credits'], name)
            print(f'✅ {name}({pkg["credits"]}积分) x5:')
            for c in codes:
                print(f'   {c}')
            print()
        print('📁 文件已保存到 redeem_codes/ 目录')
        return
    
    if args[0] == '--custom' and len(args) >= 3:
        credits = int(args[1])
        count = int(args[2])
        codes = generate_codes('自定义', count, credits)
        csv_file, txt_file = save_codes(codes, credits, '自定义')
        print(f'✅ 生成 {count} 个自定义({credits}积分) 兑换码:')
        for c in codes:
            print(f'   {c}')
        print(f'\n📁 CSV: {csv_file}\n📁 TXT: {txt_file}')
        return
    
    # 套餐参数: --体验包 10
    pkg_name = args[0].lstrip('-')
    count = int(args[1]) if len(args) > 1 else 5
    
    if pkg_name in PACKAGES:
        codes = generate_codes(pkg_name, count)
        csv_file, txt_file = save_codes(codes, PACKAGES[pkg_name]['credits'], pkg_name)
        print(f'✅ 生成 {count} 个 {pkg_name}({PACKAGES[pkg_name]["credits"]}积分) 兑换码:')
        for c in codes:
            print(f'   {c}')
        print(f'\n📁 CSV: {csv_file}\n📁 TXT: {txt_file}')
    else:
        print(f'❌ 未知套餐: {pkg_name}')
        print(f'可用套餐: {", ".join(PACKAGES.keys())}')


if __name__ == '__main__':
    main()
