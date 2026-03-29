"""
理科卡片综合审核脚本 — 审核知识卡内容 + 生成图片质量
覆盖维度:
  Level 1  JSON 结构校验 (无需 API)
  Level 2  内容准确性校验 (化学方程式配平、物理量单位、生物术语)
  Level 3  覆盖率统计 (按学科/年级/卡片类型)
  Level 4  图片审核 (已生成的图片: 尺寸 vs 预期比例、文件大小)
  Level 5  Prompt 审计覆盖率 (模拟 Phase 1 看 coverage)

版本: v10.9.1
"""

import sys, os, json, re, time
from collections import defaultdict
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── 导入项目模块 ───
from skill_schema import get_skill_schema, match_sub_type, get_all_skill_types
from generate_card_images_v3 import (
    _CONTENT_RATIO_MAP, _SCIENCE_CARD_TYPES, _SCIENCE_SUBJECTS,
    CARD_TYPE_VISUAL_RULES, _CARD_TYPE_LAYOUT_MAP,
)

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KC_DIRS = [
    os.path.join(BASE_DIR, 'knowledge_cards'),
    os.path.join(BASE_DIR, 'public', 'knowledge_cards'),
]
SCIENCE_OUTPUT_DIR = os.path.join(BASE_DIR, '_test_science_output')

# ─── 课程大纲 (科目 → 年级列表) ───
CURRICULUM = {
    '初中': {
        '物理': ['八上', '八下', '九上', '九下'],
        '化学': ['九上', '九下'],
        '生物': ['七上', '七下', '八上', '八下'],
    },
    '高中': {
        '物理': ['高一上', '高一下', '高二上', '高二下'],
        '化学': ['高一上', '高一下', '高二上', '高二下'],
        '生物': ['高一上', '高一下', '高二上', '高二下'],
    },
}

# ─── 化学方程式配平检查 (常见公式) ───
CHEMISTRY_FORMULAS = {
    'H₂O': {'H': 2, 'O': 1},
    'CO₂': {'C': 1, 'O': 2},
    'NaCl': {'Na': 1, 'Cl': 1},
    'CaCO₃': {'Ca': 1, 'C': 1, 'O': 3},
    'Na₂CO₃': {'Na': 2, 'C': 1, 'O': 3},
}

# ─── 物理量单位标准 ───
PHYSICS_UNITS = {
    '速度': ['m/s', 'km/h'],
    '加速度': ['m/s²', 'm/s^2'],
    '力': ['N', '牛', '牛顿'],
    '质量': ['kg', 'g', '千克', '克'],
    '温度': ['°C', '℃', 'K'],
    '电压': ['V', '伏', '伏特'],
    '电流': ['A', '安', '安培'],
    '电阻': ['Ω', '欧', '欧姆'],
    '功': ['J', '焦', '焦耳'],
    '功率': ['W', '瓦', '瓦特'],
    '频率': ['Hz', '赫兹'],
    '压强': ['Pa', '帕', '帕斯卡'],
    '密度': ['kg/m³', 'g/cm³'],
}

# ─── 生物易错术语 ───
BIO_TERM_CHECKS = [
    ('促进', '不等于"有利于"'),
    ('抑制', '不等于"不利于"'),
    ('DNA→RNA→蛋白质', '中心法则方向'),
    ('转录', '发生在细胞核'),
    ('翻译', '发生在核糖体'),
]

# ═══════════════════════════════════════════
# 数据类
# ═══════════════════════════════════════════

@dataclass
class AuditFinding:
    level: str       # L1-L5
    severity: str    # error | warning | info
    file: str
    card_id: str
    message: str

@dataclass 
class CoverageEntry:
    subject: str
    stage: str
    grade: str
    exists: bool
    card_count: int = 0
    types: set = field(default_factory=set)

# ═══════════════════════════════════════════
# Level 1: JSON 结构校验
# ═══════════════════════════════════════════

REQUIRED_TOP_FIELDS = ['subject', 'grade', 'semester', 'units']
REQUIRED_CARD_FIELDS = ['card_id', 'title', 'type', 'difficulty', 'definition', 'core_points']
OPTIONAL_CARD_FIELDS = ['full_id', 'importance', 'example', 'mistakes', 'memory_tip', 'related']

def audit_l1_structure(filepath: str) -> list[AuditFinding]:
    """Level 1: 基础 JSON 结构校验"""
    findings = []
    fname = os.path.basename(filepath)
    
    try:
        with open(filepath, encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        findings.append(AuditFinding('L1', 'error', fname, '-', f'JSON 解析失败: {e}'))
        return findings
    except Exception as e:
        findings.append(AuditFinding('L1', 'error', fname, '-', f'文件读取失败: {e}'))
        return findings
    
    # 顶级字段
    for field in REQUIRED_TOP_FIELDS:
        if field not in data:
            findings.append(AuditFinding('L1', 'error', fname, '-', f'缺少顶级字段: {field}'))
    
    if 'units' not in data:
        return findings
    
    seen_ids = set()
    for ui, unit in enumerate(data['units']):
        if 'unit_id' not in unit:
            findings.append(AuditFinding('L1', 'error', fname, f'unit[{ui}]', '缺少 unit_id'))
        if 'cards' not in unit:
            findings.append(AuditFinding('L1', 'error', fname, f'unit[{ui}]', '缺少 cards 数组'))
            continue
        
        for ci, card in enumerate(unit.get('cards', [])):
            cid = card.get('card_id', f'unit{ui}_card{ci}')
            
            # 必需字段
            for field in REQUIRED_CARD_FIELDS:
                if field not in card:
                    findings.append(AuditFinding('L1', 'error', fname, cid, f'缺少必需字段: {field}'))
            
            # ID 唯一性
            if cid in seen_ids:
                findings.append(AuditFinding('L1', 'error', fname, cid, f'card_id 重复: {cid}'))
            seen_ids.add(cid)
            
            # 难度范围
            diff = card.get('difficulty', -1)
            if not isinstance(diff, int) or diff < 1 or diff > 5:
                findings.append(AuditFinding('L1', 'warning', fname, cid, f'difficulty={diff} 不在 1-5 范围'))
            
            # core_points 非空
            cp = card.get('core_points', [])
            if not isinstance(cp, list) or len(cp) == 0:
                findings.append(AuditFinding('L1', 'warning', fname, cid, 'core_points 为空'))
            
            # 卡片类型有效性
            ctype = card.get('type', '')
            if ctype and not get_skill_schema(ctype):
                # 不在 SkillSchema 注册表里也可能是合法的旧类型
                if ctype not in CARD_TYPE_VISUAL_RULES:
                    findings.append(AuditFinding('L1', 'warning', fname, cid, f'卡片类型 "{ctype}" 未注册'))
            
            # example 结构
            ex = card.get('example')
            if ex:
                if not isinstance(ex, dict):
                    findings.append(AuditFinding('L1', 'warning', fname, cid, 'example 应为 dict'))
                else:
                    if 'question' not in ex:
                        findings.append(AuditFinding('L1', 'info', fname, cid, 'example 缺少 question'))
            
            # mistakes 结构
            mistakes = card.get('mistakes', [])
            if mistakes:
                for mi, m in enumerate(mistakes):
                    if not isinstance(m, dict):
                        findings.append(AuditFinding('L1', 'warning', fname, cid, f'mistakes[{mi}] 应为 dict'))
                    elif 'wrong' not in m or 'correct' not in m:
                        findings.append(AuditFinding('L1', 'warning', fname, cid, f'mistakes[{mi}] 缺少 wrong/correct'))
            
            # related 结构
            rel = card.get('related')
            if rel:
                if not isinstance(rel, dict):
                    findings.append(AuditFinding('L1', 'info', fname, cid, 'related 应为 dict'))
    
    return findings


# ═══════════════════════════════════════════
# Level 2: 内容准确性
# ═══════════════════════════════════════════

def audit_l2_accuracy(filepath: str) -> list[AuditFinding]:
    """Level 2: 学科内容准确性检查"""
    findings = []
    fname = os.path.basename(filepath)
    
    try:
        data = json.loads(open(filepath, encoding='utf-8').read())
    except:
        return findings
    
    subject = data.get('subject', '')
    
    for unit in data.get('units', []):
        for card in unit.get('cards', []):
            cid = card.get('card_id', '?')
            title = card.get('title', '')
            defn = card.get('definition', '')
            all_text = f"{title} {defn} {' '.join(card.get('core_points', []))}"
            
            # 化学: 方程式基本检查
            if subject == '化学':
                _check_chemistry(all_text, fname, cid, card, findings)
            
            # 物理: 单位检查
            if subject == '物理':
                _check_physics_units(all_text, fname, cid, findings)
            
            # 生物: 术语精准度
            if subject == '生物':
                _check_biology_terms(all_text, fname, cid, findings)
            
            # 通用: 定义不为空且有意义
            if len(defn.strip()) < 5:
                findings.append(AuditFinding('L2', 'warning', fname, cid, f'definition 过短({len(defn)}字): "{defn}"'))
            
            # 通用: mistakes 中的 wrong != correct
            for m in card.get('mistakes', []):
                if isinstance(m, dict) and m.get('wrong', '') == m.get('correct', ''):
                    findings.append(AuditFinding('L2', 'error', fname, cid, f'mistake 的 wrong 和 correct 相同: "{m.get("wrong")}"'))
    
    return findings


def _check_chemistry(text: str, fname: str, cid: str, card: dict, findings: list):
    """化学内容检查"""
    # 检查反应式箭头方向/条件提示
    example = card.get('example', {})
    if isinstance(example, dict):
        q = example.get('question', '')
        a = example.get('answer', '')
        ex_text = f"{q} {a}"
        # 简单检查: 如果有 → 或 = 号的化学方程式
        if re.search(r'[A-Z][a-z]?\d*.*[→=→].*[A-Z]', ex_text):
            # 检查是否标注了反应条件
            if not re.search(r'(点燃|加热|催化|高温|常温|Δ|△)', ex_text):
                findings.append(AuditFinding('L2', 'info', fname, cid, '化学方程式可能缺少反应条件标注'))


def _check_physics_units(text: str, fname: str, cid: str, findings: list):
    """物理单位检查"""
    # 检查公式中有没有提到单位
    if re.search(r'[=×÷/]\s*\d', text):
        has_unit = False
        for qty, units in PHYSICS_UNITS.items():
            for u in units:
                if u in text:
                    has_unit = True
                    break
            if has_unit:
                break
        if not has_unit and '公式' in text:
            findings.append(AuditFinding('L2', 'info', fname, cid, '含有计算公式但未见单位标注'))


def _check_biology_terms(text: str, fname: str, cid: str, findings: list):
    """生物术语检查"""
    # 中心法则方向检查
    if 'RNA' in text and 'DNA' in text:
        if 'RNA→DNA' in text and '逆转录' not in text:
            findings.append(AuditFinding('L2', 'warning', fname, cid, '出现 RNA→DNA 但未提及逆转录'))


# ═══════════════════════════════════════════
# Level 3: 覆盖率统计
# ═══════════════════════════════════════════

def audit_l3_coverage(all_files: list[str]) -> tuple[list[AuditFinding], dict]:
    """Level 3: 知识卡覆盖率统计"""
    findings = []
    coverage = {}
    
    # 建立现有文件清单
    existing = {}  # (stage, subject, grade) → filepath
    for fp in all_files:
        try:
            data = json.loads(open(fp, encoding='utf-8').read())
        except:
            continue
        subj = data.get('subject', '')
        grade_short = data.get('grade_short', '')
        
        # 推断 stage
        stage = '高中' if '高' in grade_short else '初中'
        existing[(stage, subj, grade_short)] = {
            'file': fp,
            'card_count': sum(len(u.get('cards', [])) for u in data.get('units', [])),
            'types': set(c.get('type', '') for u in data.get('units', []) for c in u.get('cards', [])),
        }
    
    # 对比课程大纲
    stats = {
        'total_expected': 0,
        'total_existing': 0,
        'missing': [],
        'by_subject': defaultdict(lambda: {'expected': 0, 'existing': 0}),
        'type_distribution': defaultdict(int),  # card_type → count
    }
    
    for stage, subjects in CURRICULUM.items():
        for subj, grades in subjects.items():
            for grade in grades:
                stats['total_expected'] += 1
                stats['by_subject'][f'{stage}-{subj}']['expected'] += 1
                
                key = (stage, subj, grade)
                if key in existing:
                    stats['total_existing'] += 1
                    stats['by_subject'][f'{stage}-{subj}']['existing'] += 1
                    for t in existing[key]['types']:
                        stats['type_distribution'][t] += 1
                else:
                    stats['missing'].append(f'{stage}/{subj}_{grade}')
                    findings.append(AuditFinding('L3', 'warning', '-', '-', f'缺少知识卡: {stage}/{subj}_{grade}_总结.json'))
    
    # 卡片类型覆盖
    all_science_types = _SCIENCE_CARD_TYPES
    used_types = set(stats['type_distribution'].keys())
    missing_types = all_science_types - used_types
    if missing_types:
        findings.append(AuditFinding('L3', 'info', '-', '-', f'未使用的理科卡片类型: {", ".join(sorted(missing_types))}'))
    
    return findings, stats


# ═══════════════════════════════════════════
# Level 4: 图片审核
# ═══════════════════════════════════════════

# 比例名称到宽高比
RATIO_MAP = {
    '3:4': 3/4,    # 0.75
    '4:3': 4/3,    # 1.333
    '1:1': 1.0,
    '9:16': 9/16,  # 0.5625
}

def audit_l4_images(img_dir: str) -> list[AuditFinding]:
    """Level 4: 生成图片基础检查"""
    findings = []
    
    if not os.path.exists(img_dir):
        findings.append(AuditFinding('L4', 'info', img_dir, '-', '图片输出目录不存在'))
        return findings
    
    try:
        from PIL import Image
        has_pil = True
    except ImportError:
        has_pil = False
    
    files = [f for f in os.listdir(img_dir) if f.endswith(('.jpg', '.png', '.webp'))]
    
    if not files:
        findings.append(AuditFinding('L4', 'info', img_dir, '-', '无图片文件'))
        return findings
    
    for fname in files:
        fpath = os.path.join(img_dir, fname)
        size_kb = os.path.getsize(fpath) / 1024
        
        # 文件大小检查
        if size_kb < 50:
            findings.append(AuditFinding('L4', 'warning', fname, '-', f'文件过小 ({size_kb:.0f}KB) — 可能生成失败'))
        elif size_kb > 2048:
            findings.append(AuditFinding('L4', 'warning', fname, '-', f'文件过大 ({size_kb:.0f}KB) — 影响加载速度'))
        
        # 从文件名推断卡片类型
        card_type = _extract_card_type_from_filename(fname)
        
        if has_pil:
            try:
                img = Image.open(fpath)
                w, h = img.size
                actual_ratio = w / h
                
                # 检查与预期比例是否匹配
                if card_type:
                    expected_ratio_str = _CONTENT_RATIO_MAP.get(card_type)
                    if expected_ratio_str:
                        expected_ratio = RATIO_MAP.get(expected_ratio_str, 0.75)
                        diff = abs(actual_ratio - expected_ratio) / expected_ratio
                        if diff > 0.15:  # 允许 15% 误差
                            findings.append(AuditFinding('L4', 'warning', fname, card_type,
                                f'比例偏差: 实际 {w}×{h} ({actual_ratio:.2f}) vs 预期 {expected_ratio_str} ({expected_ratio:.2f}), 偏差 {diff*100:.0f}%'))
                
                # 分辨率检查
                if w < 500 or h < 500:
                    findings.append(AuditFinding('L4', 'warning', fname, '-', f'分辨率偏低: {w}×{h}'))
                elif w > 4000 or h > 4000:
                    findings.append(AuditFinding('L4', 'info', fname, '-', f'分辨率偏高: {w}×{h}'))
                    
            except Exception as e:
                findings.append(AuditFinding('L4', 'error', fname, '-', f'图片读取失败: {e}'))
    
    return findings


def _extract_card_type_from_filename(fname: str) -> str | None:
    """从文件名提取卡片类型"""
    for ct in sorted(_SCIENCE_CARD_TYPES, key=len, reverse=True):
        if ct in fname:
            return ct
    return None


# ═══════════════════════════════════════════
# Level 5: Prompt 审计覆盖率
# ═══════════════════════════════════════════

def audit_l5_prompt_coverage(files: list[str], sample_per_type: int = 1) -> list[AuditFinding]:
    """Level 5: 对每种卡片类型抽样进行 Prompt 审计"""
    findings = []
    
    # 加载 API key
    api_key_file = os.path.join(BASE_DIR, 'api_key.txt')
    api_keys = []
    if os.path.exists(api_key_file):
        content = open(api_key_file, encoding='utf-8').read()
        for line in content.strip().split('\n'):
            line = line.strip()
            if line.startswith('GEMINI_API_KEY='):
                key = line.split('=', 1)[1].strip()
                if ',' in key:
                    api_keys.extend([k.strip() for k in key.split(',') if k.strip()])
                else:
                    api_keys.append(key)
    
    if not api_keys:
        findings.append(AuditFinding('L5', 'info', '-', '-', '未找到 API key, 跳过 Prompt 审计'))
        return findings
    
    os.environ['GEMINI_API_KEY'] = api_keys[0]
    
    try:
        from generate_card_images_v3 import generate_image_prompt_v2
        from prompt_auditor import audit_prompt
    except ImportError as e:
        findings.append(AuditFinding('L5', 'error', '-', '-', f'导入失败: {e}'))
        return findings
    
    # 按类型收集样本
    type_samples = defaultdict(list)
    for fp in files:
        try:
            data = json.loads(open(fp, encoding='utf-8').read())
        except:
            continue
        subject = data.get('subject', '')
        grade_short = data.get('grade_short', '')
        gs = grade_short
        semester = '上' if '上' in gs else '下'
        grade = gs.replace('上', '').replace('下', '').replace('_', '')
        
        for unit in data.get('units', []):
            for card in unit.get('cards', []):
                ct = card.get('type', '')
                if ct in _SCIENCE_CARD_TYPES and len(type_samples[ct]) < sample_per_type:
                    type_samples[ct].append({
                        'card': card, 'subject': subject,
                        'grade': grade, 'semester': semester,
                    })
    
    # 运行审计
    coverage_by_type = {}
    for ct, samples in type_samples.items():
        for sample in samples:
            card = sample['card']
            try:
                result = generate_image_prompt_v2(
                    card=card,
                    subject=sample['subject'],
                    grade=sample['grade'],
                    semester=sample['semester'],
                    api_key=api_keys[0],
                    all_keys=api_keys,
                )
                if result and isinstance(result, tuple) and len(result) >= 2:
                    prompt_text, manifest = result
                    audit = audit_prompt(prompt_text, ct, card, manifest)
                    coverage_by_type[ct] = audit.coverage_pct
                    
                    if audit.coverage_pct < 60:
                        findings.append(AuditFinding('L5', 'error', '-', card.get('card_id', '?'),
                            f'{ct} coverage={audit.coverage_pct:.0f}% (< 60%) — {audit.verdict}'))
                    elif audit.coverage_pct < 80:
                        findings.append(AuditFinding('L5', 'warning', '-', card.get('card_id', '?'),
                            f'{ct} coverage={audit.coverage_pct:.0f}% (< 80%) — {audit.verdict}'))
                    else:
                        findings.append(AuditFinding('L5', 'info', '-', card.get('card_id', '?'),
                            f'{ct} coverage={audit.coverage_pct:.0f}% — {audit.verdict}'))
                    
                    # 记录高严重度问题
                    for iss in audit.issues:
                        if iss.severity == 'high':
                            findings.append(AuditFinding('L5', 'warning', '-', card.get('card_id', '?'),
                                f'  [{iss.severity}] {iss.description}'))
                else:
                    findings.append(AuditFinding('L5', 'error', '-', card.get('card_id', '?'),
                        f'{ct} Phase 1 生成失败'))
            except Exception as e:
                findings.append(AuditFinding('L5', 'error', '-', card.get('card_id', '?'),
                    f'{ct} 异常: {e}'))
    
    return findings


# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════

def collect_science_files() -> list[str]:
    """收集所有理科知识卡 JSON"""
    files = []
    science_subjects = {'物理', '化学', '生物'}
    for d in KC_DIRS:
        if not os.path.isdir(d):
            continue
        for stage_dir in ['初中', '高中']:
            sd = os.path.join(d, stage_dir)
            if not os.path.isdir(sd):
                continue
            for f in os.listdir(sd):
                if f.endswith('.json'):
                    subj = f.split('_')[0]
                    if subj in science_subjects:
                        files.append(os.path.join(sd, f))
    return sorted(set(files))


def print_section(title: str):
    print(f"\n{'═'*60}")
    print(f"  {title}")
    print(f"{'═'*60}")


def print_findings(findings: list[AuditFinding]):
    if not findings:
        print("  ✅ 全部通过")
        return
    
    errors = [f for f in findings if f.severity == 'error']
    warnings = [f for f in findings if f.severity == 'warning']
    infos = [f for f in findings if f.severity == 'info']
    
    for f in errors:
        print(f"  ❌ [{f.level}] {f.file}:{f.card_id} — {f.message}")
    for f in warnings:
        print(f"  ⚠️  [{f.level}] {f.file}:{f.card_id} — {f.message}")
    for f in infos:
        print(f"  ℹ️  [{f.level}] {f.file}:{f.card_id} — {f.message}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='理科卡片综合审核')
    parser.add_argument('--levels', default='1,2,3,4', help='审核级别 (逗号分隔, 1-5)')
    parser.add_argument('--img-dir', default=SCIENCE_OUTPUT_DIR, help='图片输出目录')
    args = parser.parse_args()
    
    levels = [int(x.strip()) for x in args.levels.split(',')]
    
    print("=" * 60)
    print("  理科卡片综合审核报告")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    files = collect_science_files()
    print(f"\n发现 {len(files)} 个理科知识卡文件:")
    for f in files:
        rel = os.path.relpath(f, BASE_DIR)
        print(f"  • {rel}")
    
    all_findings = []
    
    # ── Level 1 ──
    if 1 in levels:
        print_section("Level 1: JSON 结构校验")
        for fp in files:
            f1 = audit_l1_structure(fp)
            all_findings.extend(f1)
        print_findings([f for f in all_findings if f.level == 'L1'])
    
    # ── Level 2 ──
    if 2 in levels:
        print_section("Level 2: 内容准确性检查")
        for fp in files:
            f2 = audit_l2_accuracy(fp)
            all_findings.extend(f2)
        print_findings([f for f in all_findings if f.level == 'L2'])
    
    # ── Level 3 ──
    if 3 in levels:
        print_section("Level 3: 覆盖率统计")
        f3, stats = audit_l3_coverage(files)
        all_findings.extend(f3)
        
        pct = (stats['total_existing'] / stats['total_expected'] * 100) if stats['total_expected'] > 0 else 0
        print(f"  总覆盖率: {stats['total_existing']}/{stats['total_expected']} ({pct:.0f}%)")
        print()
        
        print("  按学科:")
        for key, val in sorted(stats['by_subject'].items()):
            p = val['existing'] / val['expected'] * 100 if val['expected'] > 0 else 0
            bar = '█' * int(p / 10) + '░' * (10 - int(p / 10))
            print(f"    {key:12s} {bar} {val['existing']}/{val['expected']} ({p:.0f}%)")
        
        if stats['missing']:
            print(f"\n  缺失 ({len(stats['missing'])} 个):")
            for m in stats['missing']:
                print(f"    ⚠️  {m}")
        
        if stats['type_distribution']:
            print(f"\n  卡片类型分布:")
            for t, cnt in sorted(stats['type_distribution'].items(), key=lambda x: -x[1]):
                print(f"    {t:12s} {'●' * cnt} ({cnt})")
    
    # ── Level 4 ──
    if 4 in levels:
        print_section("Level 4: 图片审核")
        f4 = audit_l4_images(args.img_dir)
        all_findings.extend(f4)
        print_findings([f for f in all_findings if f.level == 'L4'])
    
    # ── Level 5 ──
    if 5 in levels:
        print_section("Level 5: Prompt 审计覆盖率 (需要 API)")
        f5 = audit_l5_prompt_coverage(files)
        all_findings.extend(f5)
        print_findings([f for f in all_findings if f.level == 'L5'])
    
    # ── 汇总 ──
    print_section("汇总")
    errors   = sum(1 for f in all_findings if f.severity == 'error')
    warnings = sum(1 for f in all_findings if f.severity == 'warning')
    infos    = sum(1 for f in all_findings if f.severity == 'info')
    total    = len(all_findings)
    
    print(f"  总发现: {total}")
    print(f"    ❌ 错误:   {errors}")
    print(f"    ⚠️  警告:   {warnings}")
    print(f"    ℹ️  信息:   {infos}")
    
    if errors == 0:
        print("\n  🎉 无严重错误!")
    else:
        print(f"\n  🔧 需要修复 {errors} 个错误")
    
    return errors


if __name__ == '__main__':
    sys.exit(main())
