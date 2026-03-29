"""
修复深层复审发现的 18 个知识卡内容问题
P0-HIGH: 2张 (分子原子微观图解、灭火原理知识网络)
P1-MEDIUM: 16张

同步修改 knowledge_cards/ 和 public/knowledge_cards/ 两个目录
"""
import json, os, copy

BASE = os.path.dirname(os.path.abspath(__file__))
KC_DIRS = [
    os.path.join(BASE, 'knowledge_cards'),
    os.path.join(BASE, 'public', 'knowledge_cards'),
]

def load_json(fp):
    return json.loads(open(fp, encoding='utf-8').read())

def save_json(fp, data):
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Ensure file ends with newline
    with open(fp, 'a', encoding='utf-8') as f:
        f.write('\n')

def find_card(data, card_id):
    """Find card by card_id in units structure"""
    for unit in data.get('units', []):
        for card in unit.get('cards', []):
            if card.get('card_id') == card_id:
                return card
    return None

stats = {'fixed': 0, 'files': set()}

def patch_file(stage, fname, patches):
    """Apply patches to a file in both KC dirs"""
    for d in KC_DIRS:
        fp = os.path.join(d, stage, fname)
        if not os.path.isfile(fp):
            print(f"  ⚠️ 文件不存在: {fp}")
            continue
        data = load_json(fp)
        changed = False
        for card_id, patch_fn in patches:
            card = find_card(data, card_id)
            if not card:
                print(f"  ⚠️ 找不到卡片 {card_id} in {fp}")
                continue
            patch_fn(card)
            changed = True
            stats['fixed'] += 1
        if changed:
            save_json(fp, data)
            stats['files'].add(fp)
            print(f"  ✅ {fp}")


# ═══════════════════════════════════════════
# P0-HIGH 修复
# ═══════════════════════════════════════════

def fix_S3_01_chem9up(card):
    """P0: 分子原子微观图解 — 配平化学计量"""
    card['core_points'][1] = (
        "微观本质：2H₂O分子 → 4个H原子 + 2个O原子 → "
        "重新组合 → 2个H₂分子 + 1个O₂分子"
    )
    # memory_tip 也需要配平
    card['memory_tip'] = (
        "「分子可分原子拼，化学变化原子不变心。"
        "2H₂O → 2H₂ + O₂，数原子两边要相等。」"
    )

def fix_S5_01_chem9up(card):
    """P0: 灭火原理知识网络 — 修正氧化反应分类"""
    card['core_points'][4] = (
        "氧化反应分类：缓慢氧化(铁生锈、食物腐烂) / "
        "剧烈氧化即燃烧 / 爆炸(有限空间急速燃烧)"
    )


# ═══════════════════════════════════════════
# P1-MEDIUM 修复 — 化学
# ═══════════════════════════════════════════

def fix_S1_02_chem9up(card):
    """量筒读数表述修正"""
    card['core_points'][0] = (
        "「量筒读数」：视线与凹液面最低处保持水平，"
        "读取该处对应的刻度值"
    )

def fix_S4_02_chem9up(card):
    """化学方程式配平 — 最小公倍数法描述修正"""
    card['core_points'][1] = (
        "方法一：最小公倍数法 → 找出两边原子个数"
        "相差较大的元素 → 求最小公倍数 → 确定系数"
    )

def fix_S3_01_chem9down(card):
    """酸碱指示剂 — 修正example"""
    card['example']['question'] = (
        "用pH试纸测定某溶液的酸碱度，说明操作步骤和如何判断结果。"
    )
    card['example']['steps'] = [
        "1. 取一小片pH试纸放在白瓷板或玻璃片上",
        "2. 用玻璃棒蘸取少量待测液，滴在pH试纸上",
        "3. 观察试纸颜色变化，与标准比色卡对照",
        "4. 读出pH值，判断酸碱性（<7酸性，=7中性，>7碱性）",
    ]
    card['example']['answer'] = (
        "用玻璃棒蘸取液体滴在pH试纸上（不可直接浸入），"
        "对照比色卡读出pH值。若pH<7则为酸性溶液。"
    )


# ═══════════════════════════════════════════
# P1-MEDIUM 修复 — 物理
# ═══════════════════════════════════════════

def fix_S1_02_phys9up(card):
    """内能与比热容 — 修正标题类型和定义"""
    # 类型从"公式推导卡"改为更准确的
    # 标题不改（保持原有结构），但修正定义和core_points
    card['definition'] = (
        "物体内部所有分子的动能和势能总和叫内能。"
        "比热容是物质的一种物理属性，与物质种类和状态有关。Q=cmΔt。"
    )
    card['core_points'][2] = (
        "比热容c：单位质量的某种物质温度升高（或降低）1℃"
        "所吸收（或放出）的热量，单位J/(kg·℃)"
    )

def fix_S1_04_phys8up(card):
    """s-t图斜率修正"""
    card['core_points'][0] = (
        "s-t图：过原点的直线 → 匀速直线运动，"
        "斜率=速率（初中阶段常表述为速度）"
    )

def fix_S1_01_phys9up(card):
    """分子间作用力 — 补充平衡距离概念"""
    card['core_points'][3] = (
        "分子间同时存在引力和斥力：间距<平衡距离→斥力>引力，"
        "表现为斥力为主；间距>平衡距离→引力>斥力，表现为引力为主"
    )

def fix_S2_01_phys9up(card):
    """串并联电路 — 补充电压规律"""
    card['core_points'][1] = (
        "并联：电流多通道，干路=各支路之和 I=I₁+I₂+…+Iₙ"
    )
    # 补充电压规律
    card['core_points'].insert(2, 
        "串联电压：U=U₁+U₂（总电压=各处电压之和）；"
        "并联电压：U=U₁=U₂（各支路电压相等）"
    )

def fix_S2_01_phys9down(card):
    """电功率 — 补充纯电阻限制"""
    card['definition'] = (
        "电功率是电流做功的快慢，P=UI（通用）。"
        "纯电阻电路中P=I²R=U²/R。额定功率是在额定电压下的功率。"
    )
    card['core_points'][1] = (
        "P=UI（通用公式）; P=I²R、P=U²/R（仅限纯电阻电路，"
        "串联中常用I²R，并联中常用U²/R）"
    )

def fix_S2_03_phys8up(card):
    """音色定义统一"""
    card['definition'] = (
        "声音的三个特性：音调（高低）、响度（大小）、音色（特色），"
        "分别由频率、振幅、发声体材料结构（波形不同）决定。"
    )
    card['core_points'][2] = (
        "音色：声音的特色，取决于发声体的材料和结构，"
        "在波形图上表现为不同的波形"
    )

def fix_S3_01_phys9down(card):
    """电磁感应条件统一"""
    card['core_points'][1] = (
        "电磁感应：闭合电路的一部分导体做切割磁感线运动"
        "→产生感应电流（法拉第发现）"
    )

def fix_S4_02_phys8up(card):
    """镜像描述修正"""
    card['core_points'][2] = (
        "陷阱3：平面镜成像是关于镜面对称（前后翻转），"
        "像与物等大、等距、连线与镜面垂直"
    )


# ═══════════════════════════════════════════
# P1-MEDIUM 修复 — 生物
# ═══════════════════════════════════════════

def fix_S1_02_bio8down(card):
    """遗传图谱 — 修正显性遗传判断规则"""
    card['core_points'][2] = (
        "常染色体显性：后代患病时，其父母中至少有一方是患者"
        "（有中生无为显性）"
    )
    card['core_points'][3] = (
        "伴X遗传判断：父病女必病→X显性；"
        "母病子必病→X隐性。男女发病率不等提示性染色体遗传"
    )

def fix_S2_01_bio7up(card):
    """显微镜操作步骤精确化"""
    card['core_points'][2] = (
        "观察：标本放载物台→压片夹固定→"
        "从侧面注视物镜，转粗准焦螺旋使镜筒缓缓下降至接近标本→"
        "左眼看目镜，转粗准焦螺旋使镜筒缓缓上升至看到物像→"
        "转细准焦螺旋调至清晰"
    )

def fix_S2_03_bio7up(card):
    """细胞分裂 — 修正两处错误"""
    # 修正core_points中的载体关系
    card['core_points'][5] = (
        "染色体是DNA的载体，染色体=DNA+蛋白质"
    )
    # 修正core_points中的加倍描述
    card['core_points'][4] = (
        "关键：分裂前DNA复制（DNA数目加倍，染色体数不变），"
        "分裂时着丝点分裂（染色体暂时加倍），最终均分到两个子细胞"
    )
    # 修正example steps if exists
    ex = card.get('example', {})
    steps = ex.get('steps', [])
    if steps and '染色体数目暂时加倍' in steps[0]:
        steps[0] = (
            "1. 分裂前：DNA复制→每条染色体含两条姐妹染色单体"
            "（DNA数加倍，染色体数不变）"
        )

def fix_S1_01_bio7up(card):
    """生物基本特征 — 修正呼吸描述"""
    card['core_points'][1] = (
        "②生物能进行呼吸（通过细胞呼吸分解有机物获取能量，"
        "包括有氧呼吸和无氧呼吸）"
    )

def fix_S1_02_bio7up(card):
    """生态因素 — 修正概念分类"""
    # 改标题更准确
    card['title'] = "生物与环境的关系"
    card['definition'] = (
        "生物与环境相互影响：环境中的生态因素（非生物因素和生物因素）"
        "影响生物的生存和分布，生物也能适应和影响环境。"
    )
    # 重组core_points
    card['core_points'] = [
        "生态因素分类：非生物因素（光、温度、水、空气、土壤等）"
        " + 生物因素（种内关系和种间关系）",
        "种间关系：捕食、竞争、寄生、共生",
        "生物对环境的适应：保护色、警戒色、拟态（长期自然选择结果）",
        "生物对环境的影响：蚯蚓松土、植物蒸腾增加空气湿度",
        "探究实例：光→影响分布（如林下阴生/阳生植物）| "
        "温度→影响分布（如候鸟迁徙）| 水→影响生存（沙漠植物根系发达）",
    ]


# ═══════════════════════════════════════════
# 执行所有修复
# ═══════════════════════════════════════════

def main():
    print("=" * 60)
    print("  知识卡内容修复 — 深层复审 P0+P1 共 18 卡")
    print("=" * 60)

    # ── 化学_九上 (4张) ──
    print("\n📁 化学_九上_总结.json (4张)")
    patch_file('初中', '化学_九上_总结.json', [
        ('S3-01', fix_S3_01_chem9up),    # P0: 微观图解配平
        ('S5-01', fix_S5_01_chem9up),    # P0: 灭火原理分类
        ('S1-02', fix_S1_02_chem9up),    # P1: 量筒读数
        ('S4-02', fix_S4_02_chem9up),    # P1: 配平策略
    ])

    # ── 化学_九下 (1张) ──
    print("\n📁 化学_九下_总结.json (1张)")
    patch_file('初中', '化学_九下_总结.json', [
        ('S3-01', fix_S3_01_chem9down),  # P1: pH试纸操作
    ])

    # ── 物理_九上 (3张) ──
    print("\n📁 物理_九上_总结.json (3张)")
    patch_file('初中', '物理_九上_总结.json', [
        ('S1-01', fix_S1_01_phys9up),    # P1: 分子间力
        ('S1-02', fix_S1_02_phys9up),    # P1: 比热容定义
        ('S2-01', fix_S2_01_phys9up),    # P1: 串并联电压
    ])

    # ── 物理_八上 (3张) ──
    print("\n📁 物理_八上_总结.json (3张)")
    patch_file('初中', '物理_八上_总结.json', [
        ('S1-04', fix_S1_04_phys8up),    # P1: s-t斜率
        ('S2-03', fix_S2_03_phys8up),    # P1: 音色定义  
        ('S4-02', fix_S4_02_phys8up),    # P1: 镜像描述
    ])

    # ── 物理_九下 (2张) ──
    print("\n📁 物理_九下_总结.json (2张)")
    patch_file('初中', '物理_九下_总结.json', [
        ('S2-01', fix_S2_01_phys9down),  # P1: 电功率纯电阻
        ('S3-01', fix_S3_01_phys9down),  # P1: 电磁感应条件
    ])

    # ── 生物_八下 (1张) ──
    print("\n📁 生物_八下_总结.json (1张)")
    patch_file('初中', '生物_八下_总结.json', [
        ('S1-02', fix_S1_02_bio8down),   # P1: 遗传图谱判断
    ])

    # ── 生物_七上 (4张) ──
    print("\n📁 生物_七上_总结.json (4张)")
    patch_file('初中', '生物_七上_总结.json', [
        ('S1-01', fix_S1_01_bio7up),     # P1: 呼吸特征
        ('S1-02', fix_S1_02_bio7up),     # P1: 生态因素分类
        ('S2-01', fix_S2_01_bio7up),     # P1: 显微镜操作
        ('S2-03', fix_S2_03_bio7up),     # P1: 细胞分裂
    ])

    print(f"\n{'=' * 60}")
    print(f"  修复完成: {stats['fixed']} 处修改, {len(stats['files'])} 个文件")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
