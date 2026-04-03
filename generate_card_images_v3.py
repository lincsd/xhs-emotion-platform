#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识卡片图片生成器 v3 — 终极流水线
=============================================
v10.17: 7大AI优化 — 字数精简/坐标锚定/两步生图/参考图/Best-of-N/定向精修/温度调优

  Step 1: Gemini 2.5 Flash 生成优化英文提示词 (v2两阶段)
  Step 2: Best-of-N 并行生成 + 两步生图(标题先出/内容后补)
  Step 3: Vision OCR 审计 + 质量评分（最多3轮）
  Step 3+: 后续轮用定向精修替代全图重生
  Step 4b: 5层审核矩阵全维度评估
  Step 4c: image-to-image 精修
  Step 5: 质量评分 + 英语专项审核

v10.17 新增:
  ① 字数精简: manifest 80→50字, 每块20→12字, 用符号压缩
  ② 坐标锚定: 每个文字块带精确y%/font/color定位
  ③ 两步生图: 先生标题+底图, 再image-to-image补内容(每步≤10汉字)
  ④ 参考图约束: 历史高分卡片作为few-shot style reference
  ⑤ Best-of-N: 第1轮并行生成多张, OCR审计选最优
  ⑥ 定向精修: 后续轮只修出错区域, 不全图重生
  ⑦ 温度调优: 文字密集0.15, 普通0.3, 精修0.15

用法:
  python generate_card_images_v3.py                          # 默认: 找 knowledge_cards/小学/*.json
  python generate_card_images_v3.py cards.json               # 指定JSON
  python generate_card_images_v3.py --test                   # 只测试1张
  python generate_card_images_v3.py --count 3                # 只生成3张
  python generate_card_images_v3.py --no-audit               # 跳过OCR审计（快速模式）
  python generate_card_images_v3.py --force                  # 强制重新生成已有图片
"""

import json, os, sys, time, base64, datetime, re, io, textwrap
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

# 自我优化系统
try:
    from self_optimizer import (
        build_fewshot_hint, build_error_boost_hint,
        record_full_result, get_adaptive_params,
        record_errors as _so_record_errors
    )
    _HAS_OPTIMIZER = True
    print('[v3] 自我优化系统已加载')
except ImportError:
    _HAS_OPTIMIZER = False
    print('[v3] 自我优化系统未加载 (self_optimizer.py 不存在)')

# 内容质量三级系统
try:
    from content_quality import (
        full_quality_check, build_typed_quality_prompt,
        build_content_refinement_hint, compute_quality_trends,
        get_quality_dashboard, QUALITY_RUBRICS, SUBJECT_FOCUS,
        analyze_top_cards, analyze_failures, generate_style_guide,
        cross_pollinate,
    )
    _HAS_QUALITY = True
    print('[v3] 内容质量三级系统已加载')
except ImportError:
    _HAS_QUALITY = False
    print('[v3] 内容质量系统未加载 (content_quality.py 不存在)')

# 内容设计引擎
try:
    from content_design_engine import (
        design_card_content, match_teaching_strategy,
        compute_cognitive_load, suggest_content_split,
        analyze_information_density,
    )
    _HAS_DESIGN = True
    print('[v3] 内容设计引擎已加载')
except ImportError:
    _HAS_DESIGN = False
    print('[v3] 内容设计引擎未加载 (content_design_engine.py 不存在)')

# 教学效果审核
try:
    from pedagogical_audit import (
        full_pedagogical_audit, score_understandability,
        score_mnemonic_effectiveness, predict_engagement,
    )
    _HAS_PEDAGOGY = True
    print('[v3] 教学效果审核已加载')
except ImportError:
    _HAS_PEDAGOGY = False
    print('[v3] 教学效果审核未加载 (pedagogical_audit.py 不存在)')

# 知识呈现蓝图
try:
    from visual_blueprint import (
        generate_visual_blueprint, compress_for_manifest,
        match_memory_strategy, analyze_info_layers,
    )
    _HAS_BLUEPRINT = True
    print('[v3] 知识呈现蓝图已加载')
except ImportError:
    _HAS_BLUEPRINT = False
    print('[v3] 知识呈现蓝图未加载 (visual_blueprint.py 不存在)')

# Skill 结构化 + Prompt 分段生成 + 结构审计
try:
    from skill_schema import get_skill_schema
    from prompt_builder import build_skill_enhanced_prompt, get_visual_strategy
    from prompt_auditor import audit_and_patch, format_audit_summary
    _HAS_SKILL_SCHEMA = True
    print('[v3] Skill结构化 + Prompt分段 + 结构审计 已加载')
except ImportError as _e:
    _HAS_SKILL_SCHEMA = False
    print(f'[v3] Skill结构化未加载 ({_e})')

# 英语卡片8维审核器
try:
    from english_card_auditor import (
        is_english_card, rule_audit_english, full_english_audit,
        format_english_audit, EnglishAuditResult,
    )
    _HAS_ENG_AUDIT = True
    print('[v3] 英语卡片审核器已加载')
except ImportError as _e:
    _HAS_ENG_AUDIT = False
    print(f'[v3] 英语卡片审核器未加载 ({_e})')

# PIL 文字渲染引擎（v10.4 已停用 — AI 直接渲染文字）
_HAS_PIL_RENDERER = False
print('[v3] v10.4: AI全量渲染模式 — PIL文字叠加已停用')

# Prompt 两阶段引擎 v2 (内容决策 + 视觉翻译)
try:
    from prompt_builder_v2 import (
        build_content_decision_prompt,
        parse_content_decision,
        build_visual_translation_prompt,
    )
    _HAS_PROMPT_V2 = True
    print('[v3] Prompt两阶段引擎 v2 已加载 (内容决策+视觉翻译)')
except ImportError as _e:
    _HAS_PROMPT_V2 = False
    print(f'[v3] Prompt两阶段引擎 v2 未加载 ({_e})')

# Skill 反向学习闭环 (从生成结果反哺参数)
try:
    from skill_feedback import build_feedback_prompt_hint
    _HAS_SKILL_FEEDBACK = True
    print('[v3] Skill反向学习闭环已加载')
except ImportError as _e:
    _HAS_SKILL_FEEDBACK = False
    print(f'[v3] Skill反向学习闭环未加载 ({_e})')

# 深层复审沉淀 (content_review → prompt 预防)
# 注意: 延迟导入, 避免与 _deep_review.py 的循环依赖


def build_content_review_hint(subject: str, card_id: str = '') -> str:
    """从 content_review 表查询该学科/卡片历史审查问题, 组装成 prompt 警告提示。
    仅返回 severity >= medium 的条目, 最多注入 8 条。"""
    try:
        from _deep_review import get_skill_insights as _get_content_review_insights
    except ImportError:
        return ''
    try:
        rows = _get_content_review_insights(subject, severity_min='medium')
        if not rows:
            return ''
        # 优先精确匹配 card_id, 再补充同学科通用问题
        card_rows = [r for r in rows if card_id and r.get('card_id', '') == card_id]
        subj_rows = [r for r in rows if r not in card_rows]
        selected = card_rows[:4] + subj_rows[:max(0, 8 - len(card_rows[:4]))]
        if not selected:
            return ''
        lines = ['\n=== CONTENT REVIEW WARNINGS (from deep audit history) ===']
        for r in selected:
            dim = r.get('dimension', '')
            sev = r.get('severity', '')
            issues = r.get('issues', [])
            issue_str = '; '.join(i for i in issues if i)[:150]
            if issue_str:
                lines.append(f'  - [{dim}|{sev}] {issue_str}')
        lines.append('IMPORTANT: Avoid repeating the above issues in this generation.')
        lines.append('=== END CONTENT REVIEW WARNINGS ===\n')
        return '\n'.join(lines) if len(lines) > 3 else ''
    except Exception as e:
        print(f'      [content_review] hint error: {e}')
        return ''

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════
GEMINI_API_BASE = 'https://generativelanguage.googleapis.com/v1beta'

TEXT_MODEL      = 'gemini-3.1-pro'              # 提示词生成 + OCR审计 (旗舰模型, 深度推理更强)
TEXT_MODEL_FALLBACK = 'gemini-2.5-flash'         # 文本模型兜底: 3.1-pro失败时自动降级
IMAGE_MODELS    = [                              # 图片生成（串行: pro优先, flash兜底）
    'gemini-3-pro-image-preview',                 # ★ Nano Banana Pro: 最优, audit=100 质量最高
    'gemini-3.1-flash-image-preview',            # 兜底: pro失败时才使用
]
# ── 模型优先级策略（v10.28）──
# 3个 API key 会优先全部用于两个主力模型:
#   1) gemini-3-pro-image-preview (Nano Banana Pro) — 图片生成主力
#   2) gemini-3.1-pro — 文本/审计主力
# 主力模型的3个key全部429后，才降级到备用模型 (flash系列)
# 主力模型每次调用 retries=3 (3轮×3key=9次尝试)，备用模型 retries=1

MAX_AUDIT_ROUNDS = 3    # OCR审计最大重试轮数
AUDIT_PASS_SCORE = 80   # OCR审计通过分数 (0-100) — 提高标准以减少乱码


def _get_effective_params():
    """获取当前有效参数（自适应覆盖默认值）"""
    if not _HAS_OPTIMIZER:
        return {
            'max_audit_rounds': MAX_AUDIT_ROUNDS,
            'audit_pass_score': AUDIT_PASS_SCORE,
            'max_chinese_chars': 15,
            'max_chars_per_block': 4,
        }
    try:
        return get_adaptive_params()
    except Exception:
        return {
            'max_audit_rounds': MAX_AUDIT_ROUNDS,
            'audit_pass_score': AUDIT_PASS_SCORE,
            'max_chinese_chars': 15,
            'max_chars_per_block': 4,
        }


# ═══════════════════════════════════════════
# API 基础设施
# ═══════════════════════════════════════════
def load_api_keys():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api_key.txt')
    with open(path, 'r') as f:
        for line in f:
            if line.strip().startswith('GEMINI_API_KEY='):
                return [k.strip() for k in line.strip().split('=', 1)[1].split(',') if k.strip()]
    return []

_key_idx = 0
def next_key(keys):
    global _key_idx
    k = keys[_key_idx % len(keys)]
    _key_idx += 1
    return k

def gemini_call(model, contents, api_key, gen_config=None, retries=2, all_keys=None):
    """通用 Gemini API 调用。
    
    支持多 key 轮换：当遇到 429/503 时自动切换 API key 重试。
    支持文本模型自动降级：TEXT_MODEL 失败时自动切换到 TEXT_MODEL_FALLBACK。
    all_keys: 所有可用的 API key 列表，为 None 时只用 api_key。
    总尝试次数 = len(all_keys) * retries（每个key各试retries次）
    """
    # 文本模型降级链: gemini-3.1-pro → gemini-2.5-flash
    if model == TEXT_MODEL and TEXT_MODEL_FALLBACK:
        models_to_try = [TEXT_MODEL, TEXT_MODEL_FALLBACK]
    else:
        models_to_try = [model]

    for mi, current_model in enumerate(models_to_try):
        result = _gemini_call_single(current_model, contents, api_key, gen_config, retries, all_keys)
        if result is not None:
            if mi > 0:
                print(f'      ✅ 降级模型 {current_model} 成功')
            return result
        if mi < len(models_to_try) - 1:
            print(f'      🔄 {current_model} 全部失败, 降级到 {models_to_try[mi+1]}...')
    return None


def _gemini_call_single(model, contents, api_key, gen_config=None, retries=2, all_keys=None):
    """单模型 Gemini API 调用（内部函数）。支持多 key 轮换（轮次制）。

    retries 表示轮数: 每轮依次尝试所有 API key，全部失败后等待再进入下一轮。
    总尝试次数 = len(key_list) * retries。
    确保每个 key 在每一轮都被公平使用，避免只有最后一个 key 享受重试。
    """
    key_list = all_keys if all_keys else [api_key]
    body = {'contents': contents}
    if gen_config:
        body['generationConfig'] = gen_config
    data = json.dumps(body).encode('utf-8')

    # 图片模型给更宽裕的超时（生图较慢），文本模型缩短超时
    # v10.16: 100→150s(image) — Gemini图片模型高负载时响应慢，避免频繁超时
    is_image_model = 'image' in model or 'imagen' in model
    call_timeout = 150 if is_image_model else 60

    total_attempts = len(key_list) * retries
    attempt_num = 0

    for round_num in range(retries):
        all_429_this_round = True  # 追踪本轮是否全部是配额问题
        for ki, current_key in enumerate(key_list):
            attempt_num += 1
            url = f'{GEMINI_API_BASE}/models/{model}:generateContent?key={current_key}'
            key_label = f'key{ki+1}/{len(key_list)}'
            try:
                req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=call_timeout) as resp:
                    return json.loads(resp.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8', errors='replace')
                print(f'\n      [HTTP {e.code}] {key_label} R{round_num+1} attempt {attempt_num}/{total_attempts}: {err_body[:200]}')
                if e.code == 404:
                    print(f'      ❌ 模型 {model} 不存在')
                    return None
                if e.code in (429, 503):
                    # 429/503: 配额受限，快速切换下一个 key
                    if ki < len(key_list) - 1:
                        print(f'      🔄 切换到下一个 API key...')
                        time.sleep(3)
                    # 否则本轮结束，下面会做轮间等待
                else:
                    all_429_this_round = False
                    if attempt_num < total_attempts:
                        time.sleep(5)
            except Exception as e:
                all_429_this_round = False
                print(f'\n      [Error] {key_label} R{round_num+1} attempt {attempt_num}/{total_attempts}: {e}')
                if attempt_num < total_attempts:
                    time.sleep(5)
        # 本轮所有 key 都尝试完毕，等待后进入下一轮
        if round_num < retries - 1:
            wait = 15 * (round_num + 1) if all_429_this_round else 8
            print(f'      ⏳ R{round_num+1}/{retries} 所有key均失败, 等待{wait}秒后下一轮...', flush=True)
            time.sleep(wait)
    return None


# ═══════════════════════════════════════════
# 卡片类型视觉策略
# ═══════════════════════════════════════════

# v10.15: 概念类卡片类型集合 — 共享图文融合策略
_CONCEPT_LIKE_TYPES = {'概念卡', '术语精准卡', '模型卡', '微观图解卡', '图像解读卡', '知识网络卡'}

# v10.15 方向2: 学科×概念 精确图形模板库 — 减少AI自由发挥的不确定性
_CONCEPT_GRAPH_TEMPLATES = {
    '物理': {
        '力': '画一个人推箱子的侧面简笔画，从手到箱子画一条带箭头的粗线(力)，箭头旁标"F"，箭头起点标"作用点"，箭头方向标"方向"，箭头长度标"大小"',
        '加速度': '画两辆并排的小车，上方车旁画短箭头(v小)，下方车旁画长箭头(v大)，两车之间画Δv箭头，右侧写 a=Δv/Δt',
        '速度': '画一条水平数轴(时间轴)，上方标3个等距点，每段标"Δs"，数轴下方写 v=s/t',
        '牛顿第一定律': '画冰面上滑行的冰壶(无摩擦→直线运动)，旁边画地面上的球(有摩擦→停下)，两者对比',
        '牛顿第二定律': '画一个物体，左侧画F箭头(推力)，物体上方标m，右侧画a箭头(加速度)，下方公式F=ma',
        '牛顿第三定律': '画两人站在冰面互推，各自向后退，双向箭头标F和F\'',
        '压强': '画同一块砖平放vs竖放在沙地上的对比图，竖放陷入更深，标注"面积小→压强大"',
        '浮力': '画水中物体，向上箭头(浮力F浮)vs向下箭头(重力G)，旁边标F浮=ρ液gV排',
        '电路': '画简单串联电路图(电池+灯泡+开关+导线)，标注电流方向箭头',
        '欧姆定律': '画一个电阻R，左标U(电压)右标I(电流)，下方公式I=U/R',
        '光的反射': '画一面镜子+入射光线+反射光线+法线，标注入射角=反射角',
        '光的折射': '画水面分界线+入射光+折射光+法线，折射角<入射角',
        '功': '画人推箱子移动距离s，力F箭头与位移同向，下方W=Fs',
        '功率': '画两人搬同样箱子上楼，一人快一人慢，快的标P大，公式P=W/t',
        '动能': '画一辆行驶的车，速度箭头v，下方Ek=½mv²',
        '势能': '画高处的球和低处的球对比，高处标Ep大，公式Ep=mgh',
        '杠杆': '画一根杠杆+支点三角+力臂标注，F1×L1=F2×L2',
        '密度': '画同体积的铁块和木块在天平两端，铁块下沉，ρ=m/V',
        '_default': '画该物理量的典型场景简笔画，用箭头标注关键物理量(≤4字标注)，底部放核心公式',
    },
    '化学': {
        '原子结构': '画一个原子模型(中心圆=原子核标+号，外圈虚线=电子轨道标-号)，旁标"质子数=核电荷数"',
        '离子': '画Na原子(2-8-1)失去1电子变成Na+(2-8)，箭头标"失去e-"',
        '化学键': '画两个原子靠近，中间画共用电子对(两个小点)，标"共价键"',
        '氧化还原': '画两个半反应箭头，上方"失电子→氧化"红色，下方"得电子→还原"蓝色',
        '溶液': '画烧杯中水+溶质粒子均匀分布，标"均一稳定"',
        '酸碱': '画pH数轴(0-14)，左红(酸)右蓝(碱)中间绿(中性)，下方标H+和OH-',
        '_default': '画微观粒子模型(不同颜色小圆=不同粒子)或实验装置简图，箭头标注变化过程',
    },
    '数学': {
        '函数': '画一个简单坐标系+一条递增曲线，x轴标自变量，y轴标因变量，旁标y=f(x)',
        '方程': '画天平模型，左右两端放不同物品，下方标等式',
        '比例': '画两条平行线段，长短不同，标注比值关系',
        '面积': '画方格纸上一个图形，数格子，旁标面积公式',
        '体积': '画一个长方体，标长宽高，旁标V=lwh',
        '角': '画两条射线从同一点出发，弧线标角度，量角器示意',
        '对称': '画一个蝴蝶/脸，中间画虚线对称轴',
        '概率': '画骰子/抽球示意图，标"可能结果数/总结果数"',
        '_default': '画几何图形或数轴或面积对比图，标注数值关系和公式',
    },
    '生物': {
        '细胞': '画细胞简图，标注细胞膜/细胞质/细胞核，动物细胞vs植物细胞对比',
        '光合作用': '画叶片+阳光箭头→CO₂+H₂O进入→O₂+有机物出来',
        '呼吸作用': '画线粒体，有机物+O₂进入→CO₂+H₂O+能量出来',
        '_default': '画生物结构简图或过程流程图，用不同颜色区分结构/物质，箭头标注过程方向',
    },
    '_default': {
        '_default': '画生活场景类比简笔画，用箭头连接到抽象概念，标注关键词(≤4字)',
    },
}

CARD_TYPE_VISUAL_RULES = {
    '方法卡': """【图文融合方法卡 — 步骤流程图为主】
   卡片50%面积画步骤流程图(编号色块①→②→③):
   - 运算方法类（笔算/竖式/列式）：画彩色分层竖式，色块对齐，正误对比
   - 其他方法类（口算/估算/简便）：色块拆分步骤流程图，每步用不同色块
   - 几何方法类：画图形+标注+辅助线，公式代入
   每个步骤旁用≤4字标注要点，而非写完整句子
   ⚠️ 流程图是教学核心，不是装饰！""",
    '概念卡': """【图文融合概念卡 — 图形是教学主力】
   整张卡片60%面积画一幅教学示意图(简笔画/示意图风格)，图形直接解释概念本质:
   - 物理概念: 画力学图/电路图/光路图等简明示意图，箭头标注关键物理量
   - 化学概念: 画微观粒子模型(不同颜色圆形=不同粒子)或实验装置简图
   - 数学概念: 画几何图形/数轴/面积对比图，标注数值关系
   - 其他学科: 画生活类比简笔画→对应抽象概念
   文字只做标注(每个标注≤4字)，不要独立文字段落！
   概念名大字放左上角，≤3行补充要点放右侧/底部(每行≤15字)，底部口诀栏
   ⚠️ 图形必须有教学功能(解释why/how)，绝不是装饰！""",
    '辨析卡': "左右并排对比：左❌红色错误 vs 右✅绿色正确，红圈标差异",
    '公式卡': """【图文融合公式卡 — 图形推导为主】
   卡片55%面积画推导过程的图形化表达:
   - 数学公式: 用面积模型/格子图/折纸图直观推导(如面积模型推(a+b)²)
   - 物理公式: 画实验场景简笔画→标注物理量→箭头推出公式
   - 化学方程: 画微观粒子重组图→宏观方程
   公式本体超大字号居中展示(占20%面积)
   底部放一个代入验证小例子(≤1行)
   ⚠️ 推导图形必须让人看图就懂"为什么是这个公式"!""",
    '陷阱卡': """【图文融合陷阱卡 — 对比图为主】
   卡片分上下两区或左右两栏:
   - 上/左区(40%): ❌错误做法的示意图(红色调)，画出"哪里错了"的图解
   - 下/右区(40%): ✅正确做法的示意图(绿色调)，画出"为什么对"的图解
   - 错误区标醒目"90%同学做错!"或"⚠️陷阱!"
   - 两区之间画放大镜/箭头指出关键差异点
   文字只做图形旁的短标注(≤4字/个)
   ⚠️ 读者看图就能瞬间理解"错在哪、对在哪"!""",
    '速算卡': "左🐢慢方法(灰色划掉) vs 右⚡速算技巧(彩色高亮)",
    '挑战卡': "关卡编号金色+大题目+倒计时元素+答案刮刮卡样式",
    '生活卡': "生活场景插画(40%)+气泡标注计算+实用结论大字",
    '对战卡': "左蓝(家长) VS 右粉(孩子)同类不同难度+计分栏",
    '思维卡': "情境问题→色块分步可视化(45%)→方法名+答案醒目",
    # 考卷真题专题卡片类型
    '填空满分卡': "审题三步法(读→圈→验)色块流程+陷阱红圈标注+单位对比区",
    '选择秒杀卡': "四选项排列+排除法色块标记(灰色划掉错误项)+正确项绿色高亮",
    '计算零失误卡': "彩色分层竖式(绿/橙/红)+对位检查清单+验算步骤",
    '判断火眼卡': "✓/✗ 大字对比+反例可视化+陷阱词红圈高亮(一定/都是/不可能)",
    '应用题拆解卡': "四步法色块流程(读→画→列→验)+线段图/流程图+完整答语",
    '操作题规范卡': "方格纸示意图+标注数据+规范检查清单✅",
    # 英语考卷真题专题
    '听力得分卡': "耳机图标+关键词高亮色块+选项排除灰色划掉+正确项绿色",
    '拼写零错卡': "字母色块拆分+易错字母红圈高亮+手写笔迹示范",
    '填空必会卡': "句子填空下划线色块+语法提示箭头+选词高亮蓝框",
    '匹配速解卡': "左右两栏连线图+关键词黄色高亮+匹配箭头彩色",
    '阅读通关卡': "文段分层色块(三层)+关键句下划线+答案定位箭头",
    '写作模板卡': "三段式彩色模板框+句型高亮+连接词标签列表",
    # 语文考卷真题专题
    '拼写默写卡': "形近字左右对比+偏旁色块高亮+口诀金句大字",
    '句式变换卡': "原句vs改后句左右栏+箭头指引变换步骤+关键词红色高亮",
    '阅读理解卡': "文段分层色块+关键句下划线+答题模板框架",
    '古诗默写卡': "古诗原文超大字体+易错字红圈标注+诗意插图背景",
    '作文模板卡': "开头中间结尾三段式框架+好词好句高亮色块+修辞示例",
    # 国学文化专题
    '预言解密卡': "古文竖排大字+逐句拆字色块解析+历史对照插图",
    '人物传奇卡': "水墨风人物侧影+传奇故事场景+名言金句大字",
    '历史印证卡': "左预言右历史对比两栏+时间轴连线+命中标记",
    '反转揭秘卡': "先展示常见误解+大反转箭头+真相揭晓色块",
    '智慧启示卡': "古今对比双栏+思维导图+收尾金句大字",
    # 情感生活专题
    '恋爱心理卡': "大脑/心脏示意图+心理学数据可视化+金句大字",
    '暧昧信号卡': "真假信号对比两栏+行为解码图标+判断清单",
    '约会攻略卡': "约会场景插画+DO/DONT对比色块+对话气泡示例",
    '避雷指南卡': "红旗🚩图标列表+危险信号红色高亮+止损建议绿色",
    '情感升温卡': "关系阶梯/温度计图+互动示例气泡+暖色调背景",
    '自我疗愈卡': "愈合阶段时间轴+自我关怀清单+温暖渐变色调",
    # 知识总结专题
    '知识总结卡': "思维导图式布局+核心知识点/公式大字色块+记忆口诀高亮+易错✗✓对比",
    # 语法辨析专题
    '语法辨析卡': "双栏对比(left❌红 vs right✅绿)+完整例句(非孤立短语)+错因解释气泡+口诀底栏(禁止'搭配固定'废话)",
    '易混词卡': "两词并排对比色块+同一语境换词例句+混淆原因分析(💡图标)+巧妙联想口诀",
    '易混词陷阱卡': "两词并排对比色块+同一语境换词例句+混淆原因分析(💡图标)+巧妙联想口诀",
    '语法纠错卡': "左❌错误句子(划红线)+右✅正确句子(绿色)+中间错因解释气泡(💡为什么错)+底部验证方法",
    '句型卡': "句型模板大字色块+对话场景图解(40%面积)+对比说明为什么这样用+问答箭头流程",
    # v10.9: 理科专属卡片类型 (物理/化学/生物)
    '实验卡': "🧪实验器材图标化+编号色块步骤①→②→③流程图+现象色彩描述+⚠️安全红色提示+对照组虚线框",
    '公式推导卡': "已知条件色块→逐步推导(每步标注物理意义箭头)→最终公式超大展示+各符号含义注释+适用条件⚠️红框",
    '过程流卡': "纵向流程图(55%)+每阶段不同色块+箭头标注输入/输出物质+核心方程居中大字+物质能量流向标注",
    '微观图解卡': "上方宏观现象实物图+中间放大镜式微观粒子图解(不同色圆=不同粒子)+底部一句话揭示本质",
    '图像解读卡': "示例坐标图(30%标注轴名+单位)+三步读图法色块(看轴/看点/看趋势)+标签式考法提示",
    '模型卡': "核心模型简化示意图(40%)+标注关键假设+✅能解释/❌不能解释双栏对比+一句话核心思想",
    '解题策略卡': "编号色块N步法(45%每步不同色)+每步要点注释+⚠️红色检查清单复选框+首字缩写口诀",
    '知识网络卡': "放射状知识网络图(60%中心节点→一级→二级分支)+重要连接加粗+核心公式大字+章节口诀",
    '术语精准卡': "左❌错误表述红色+右✅精准表述绿色逐条对比+💡扣分原因逐条解析蓝色+记忆口诀底栏",
}


def _lookup_concept_graph_template(card, subject):
    """v10.15 方向2: 从精确图形模板库中查找最匹配的模板描述。
    
    通过卡片标题中的关键词匹配学科→概念→图形描述，
    减少 AI 自由发挥的不确定性，提升图形教学价值的稳定性。
    """
    title = card.get('title', '')
    definition = card.get('definition', '')
    search_text = title + definition
    
    # 查找学科模板
    subject_templates = _CONCEPT_GRAPH_TEMPLATES.get(subject, _CONCEPT_GRAPH_TEMPLATES.get('_default', {}))
    
    # 尝试关键词匹配
    best_match = ''
    best_match_len = 0
    for keyword, template in subject_templates.items():
        if keyword == '_default':
            continue
        if keyword in search_text and len(keyword) > best_match_len:
            best_match = template
            best_match_len = len(keyword)
    
    if best_match:
        return best_match
    
    # 降级到学科默认模板
    return subject_templates.get('_default', _CONCEPT_GRAPH_TEMPLATES['_default']['_default'])


def _detect_vertical_calc(card):
    keywords = ['笔算', '竖式', '列式', '列竖式']
    text = card.get('title', '') + card.get('definition', '') + card.get('example', {}).get('question', '')
    return any(k in text for k in keywords)


# ═══════════════════════════════════════════
# Step 1: 生成图片提示词（Gemini Flash）
# ═══════════════════════════════════════════
PROMPT_SYSTEM_TEMPLATE = """你是小红书爆款知识卡片 AI 图片 Prompt 工程师。

你的任务：为一张{subject}知识卡片写一段**英文** AI 图片生成提示词。

══════ 核心教学思路 ══════

每张卡片 = 一道具体例题的"一图秒懂"讲解。

设计三步：
1. 选一道最典型的例题，大号醒目展示
2. 用最简视觉方式画出解题关键步骤（至少一步解释"为什么"而非只说"怎么做"）
{solve_strategy_block}
3. 大字答案 + 口诀(≤10字)

⚠️ 深度教学要求：
- 如果有"本质原因"或"错因"信息，必须在视觉中体现（用💡图标+简短文字）
- ❌错误示范不能只标红叉，必须配一句"为什么错"的解释
- 口诀区如有例外情况，用小字标注

⚠️ 英语卡片特别要求（如果是英语学科）：
- 标题直接用英文短语本身（如 "pay attention to"），不用中文泛化标题
- 必须展示2-3种用法结构 + 每种配完整英文例句(≥6词)
- 必须有❌/✅对错例句对比，错误必须是该短语的真实高频错误
- ❌/✅的错因标注用英文箭头格式（如 "✗ do → ✓ make"），不要写中文句子
- 口诀用「英文关键词+≤4中文字」混合格式（如 "progress用make"），减少纯中文
- 口诀≤10字，绝不能是长句截断（如 "Where is...? 位置 On/in/under 来回" 是错误示范）
- 好的英语口诀示例: "Where问位置" / "is单数it's答" / "on上in里under下"
- 🚫严禁混入与该短语无关的词汇/语法点
- 🚫严禁填空题——学生不能在图片上写字
- 🚫严禁用卡通人物/"记住哦"气泡替代教学内容
- 英语卡的卡通角色只能极小放角落，不能出现在卡片中央

══════ 视觉设计 — 完整卡片（含文字） ══════

{canvas_block}
- 一个可爱小老师卡通在右下角落（小于画面 10%）
- 小红书风格：精致卡片版式设计（Canva 模板风）

{layout_variant_block}

══════ ⚠️ 文字渲染要求（最重要！） ══════

AI 必须直接在图片中渲染所有文字！文字是卡片的核心内容。

- ✅ 所有中文必须字形完整、清晰可读，绝不能出现乱码/缺笔画/错字
- ✅ 英文字母和数字必须拼写完全正确
- ✅ 文字要与背景区块融为一体，像专业设计师排版的效果
- ✅ 标题区大字白色加粗，内容区黑色/深灰正文，口诀区白色醒目
- ✅ 文字大小层次分明：标题最大 > 内容正文 > 口诀 > 小提示
- ⚠️ 中文字符必须笔画正确——任何乱码都是致命错误！
- ⚠️ 数学公式/符号必须完全准确

══════ 文字清单 ══════

在 prompt 末尾，用 [TEXT_MANIFEST] 列出卡片中要渲染的所有文字：
[TEXT_MANIFEST]
TITLE: 标题文字 → 渲染到区块A（Banner白色大字）
LINE1: 核心内容第一行 → 渲染到区块B（⚠️ 每行不超过20个中文字！）
LINE2: 核心内容第二行 → 渲染到区块B
LINE3: 核心内容第三行 → 渲染到区块B
SLOGAN: 口诀金句 → 渲染到区块C（暖色条白字）
TIP: 小提示(可选) → 渲染到区块D
[/TEXT_MANIFEST]

⚠️ 每个 LINE 的中文字数不超过20字！如果内容过长，拆成多行 LINE1/LINE2/LINE3...
此清单中的文字必须原封不动地渲染到图片对应区域中！

⚠️⚠️⚠️ 标签名禁止渲染（违反=废卡）：
   "TITLE:", "LINE1:", "LINE2:", "LINE3:", "SLOGAN:", "TIP:" 这些是内部标签名，仅用于标识内容归属！
   ⛔ 绝对不能把 "LINE1:", "LINE2:", "SLOGAN:" 等标签前缀渲染到卡片画面上！
   ⛔ 错误示范: 画面上出现 "LINE1: Ask about location" → 废卡！
   ✅ 正确示范: 画面上只显示 "Ask about location"，不带任何 "LINE1:" 前缀
   只渲染冒号后面的实际内容文字，不渲染标签名本身！

⚠️⚠️⚠️ 最重要的防重复规则（违反=废卡）：
   TITLE(Banner标题) 和 LINE1(内容区第一行) 绝对不能是相同或相似的文字！！！
   如果 TITLE="pay attention to"，LINE1 绝不能写 "Pay Attention To (...)"！
   LINE1 应该直接写用法结构，如 "to + noun/gerund (prep., NOT infinitive)"
   Banner标题 = 知识点名称（英文短语），内容区 = 教学细节（用法/例句），两者绝不能重复！
   ⛔ 典型错误: TITLE="Where is...?" LINE1="Where is...?" → 重复了！
   ✅ 正确示范: TITLE="Where is...?" LINE1="Ask location: is+单数 / are+复数"

{color_scheme_block}

══════ 输出格式 ══════

只输出英文提示词 + TEXT_MANIFEST，不要其他内容。

提示词开头必须写:
"IMPORTANT: Generate a COMPLETE knowledge card with ALL text rendered directly in the image. The card must have: (1) a dark gradient BANNER at top with white title text, (2) a white rounded CONTENT CARD in the main body with clearly rendered teaching content, (3) a warm colored ACCENT STRIP near the bottom with white slogan text, (4) a small cute OWL mascot with graduation cap in corner (ALWAYS the same owl character — never a bear, pencil, or other animal). Text must be pixel-perfect: every Chinese character fully formed, every letter correct. ⚠️ Do NOT render any coordinates, percentages, pixel sizes, hex color codes, or layout metadata as visible text in the image! ⚠️ Do NOT render label prefixes like 'LINE1:', 'LINE2:', 'LINE3:', 'SLOGAN:', 'TIP:', 'TITLE:' in the image — these are internal tags, only render the content text AFTER the colon! Only render the actual card content text."

⚠️⚠️⚠️ 防重复三次提醒（最后警告）：
回头检查你写的 TEXT_MANIFEST — TITLE 和 LINE1 是不是写了一样的内容？？？
如果 TITLE 是一个英文短语（如 "pay attention to"），LINE1 里绝不能再出现这个短语！
LINE1 应该写：用法结构说明（如 "to + noun/gerund, NOT infinitive"）或者直接是第一个例句。
这是最常犯的错误，请一定检查！

══════ ⚠️ 文字质量核心要求 ══════

- ✅ 中文字符必须笔画完整，绝不能出现乱码
- ✅ 英文拼写必须100%正确
- ✅ 数字和数学符号必须准确
- ✅ 文字排版像专业设计师的作品——大小层次分明、对齐工整
- ✅ 文字与背景融为一体，是设计的一部分（不是贴上去的感觉）

提示词长度: 250-400 英文单词。"""

# ─── 养生减脂类专用模板 ───
_WELLNESS_SUBJECTS = {'养生', '减脂', '养生减脂'}

PROMPT_SYSTEM_TEMPLATE_WELLNESS = """你是小红书爆款知识卡片 AI 图片 Prompt 工程师。

你的任务：为一张{subject}知识卡片写一段**英文** AI 图片生成提示词。

══════ 核心思路 ══════

每张卡片 = 一个养生/减脂知识的"一图秒懂"呈现。

设计三步：
1. 用最吸引眼球的视觉对比/清单/图解展示核心知识
{visual_strategy_block}
2. 关键数据/步骤用图标+色块清晰呈现
3. 大字金句 + 行动口诀(≤10字)

══════ 视觉设计 — 完整卡片（含文字） ══════

{canvas_block}
- 一个可爱养生博主卡通在右下角落（小于画面 10%）
- 小红书风格：精致卡片版式设计
- 养生减脂配色: 抹茶绿/樱花粉/暖杏色为主

{layout_variant_block}

══════ ⚠️ 文字渲染要求（最重要！） ══════

AI 必须直接在图片中渲染所有文字！文字是卡片的核心内容。

- ✅ 所有中文必须字形完整、清晰可读，绝不能乱码/缺笔画/错字
- ✅ 英文和数字拼写100%正确
- ✅ 文字与背景融为一体，像专业设计师排版
- ✅ 标题白色大字、内容区深色正文、口诀白色醒目
- ⚠️ 中文字符笔画正确是硬性要求

══════ 文字清单 ══════

在 prompt 末尾，用 [TEXT_MANIFEST] 列出卡片要渲染的所有文字：
[TEXT_MANIFEST]
TITLE: 标题文字 → 渲染到区块A
LINE1: 第一行内容 → 渲染到区块B（⚠️ 每行不超过20个中文字！）
LINE2: 第二行内容 → 渲染到区块B
...
SLOGAN: 口诀金句 → 渲染到区块C
[/TEXT_MANIFEST]

⚠️ 每个 LINE 的中文字数不超过20字！内容长就拆成多行。
此清单中的文字必须原封不动渲染到图片中！

⚠️⚠️⚠️ 标签名禁止渲染（违反=废卡）：
   "TITLE:", "LINE1:", "LINE2:", "LINE3:", "SLOGAN:", "TIP:" 这些是内部标签名，仅用于标识内容归属！
   ⛔ 绝对不能把 "LINE1:", "LINE2:", "SLOGAN:" 等标签前缀渲染到卡片画面上！
   ⛔ 错误示范: 画面上出现 "LINE1: Ask about location" → 废卡！
   ✅ 正确示范: 画面上只显示 "Ask about location"，不带任何 "LINE1:" 前缀
   只渲染冒号后面的实际内容文字，不渲染标签名本身！

{color_scheme_block}

══════ 输出格式 ══════

只输出英文提示词 + TEXT_MANIFEST，不要其他内容。

提示词开头必须写:
"IMPORTANT: Generate a COMPLETE knowledge card with ALL text rendered directly in the image. The card must have: (1) a dark gradient BANNER at top with white title text, (2) a white rounded CONTENT CARD in the middle with teaching content, (3) a warm colored ACCENT STRIP at bottom with white slogan text, (4) a small cute OWL mascot with graduation cap in corner (ALWAYS the same owl character — never a bear, pencil, or other animal). All Chinese characters must be perfectly formed — no garbled text. ⚠️ Do NOT render label prefixes like 'LINE1:', 'LINE2:', 'LINE3:', 'SLOGAN:', 'TIP:', 'TITLE:' in the image — these are internal tags, only render the content text AFTER the colon!"

══════ ⚠️ 文字质量核心要求 ══════

- ✅ 中文字符笔画完整，不能乱码
- ✅ 英文拼写100%正确
- ✅ 文字排版专业——大小层次分明、对齐工整
- ✅ 文字与背景融为一体

提示词长度: 250-400 英文单词。"""


_GRAMMAR_TYPES = {'语法辨析卡', '句型卡', '易混词卡', '易混词陷阱卡', '语法纠错卡',
                  '词汇卡', '高频活用卡', '搭配卡', '词性辨析卡'}

# v10.9: 理科专属卡片类型集合
_SCIENCE_CARD_TYPES = {'实验卡', '公式推导卡', '过程流卡', '微观图解卡', '图像解读卡',
                       '模型卡', '解题策略卡', '知识网络卡', '术语精准卡'}

_SCIENCE_SUBJECTS = {'物理', '化学', '生物'}

# ── 高频语法术语保护表 ──
# 这些中文术语在 AI 图片渲染时极易出错，需要精确匹配 OCR 审计
_GRAMMAR_TERMS_PROTECTED = {
    '宾语从句', '表语从句', '同位语从句', '定语从句', '状语从句', '主语从句',
    '宾语', '表语', '同位语', '定语', '状语', '主语', '谓语', '补语',
    '名词性从句', '形容词性从句', '副词性从句',
    '现在完成时', '过去完成时', '一般现在时', '一般过去时', '现在进行时',
    '过去进行时', '将来时', '被动语态', '主动语态', '虚拟语气',
    '不定式', '动名词', '分词', '现在分词', '过去分词',
    '可数名词', '不可数名词', '冠词', '介词', '连词', '代词',
    '比较级', '最高级', '倒装句', '强调句', '感叹句', '祈使句',
}

# ── 全学科术语保护表 ──
# v10.6: 将英语的术语保护机制推广到所有学科
# 这些高频专业术语在 AI 渲染时容易出错，注入 manifest 后可精确 OCR 审计
_SUBJECT_TERMS_PROTECTED = {
    '英语': _GRAMMAR_TERMS_PROTECTED,

    '语文': {
        # 修辞手法
        '比喻', '拟人', '夸张', '排比', '对偶', '反问', '设问', '借代',
        '反复', '对比', '引用', '双关', '通感', '互文', '顶真', '回环',
        # 文言文术语
        '通假字', '古今异义', '词类活用', '一词多义', '特殊句式',
        '判断句', '省略句', '倒装句', '被动句', '宾语前置', '定语后置', '状语后置',
        # 诗词格律
        '平仄', '押韵', '对仗', '律诗', '绝句', '词牌', '曲牌',
        # 表达方式
        '记叙', '描写', '议论', '抒情', '说明',
        '直接抒情', '间接抒情', '借景抒情', '托物言志', '以小见大',
        # 文体知识
        '说明文', '议论文', '记叙文', '散文', '小说', '诗歌',
        '论点', '论据', '论证', '说明方法', '说明顺序',
    },

    '数学': {
        # 代数
        '一元一次方程', '一元二次方程', '二元一次方程',
        '因式分解', '公因式', '完全平方', '平方差',
        '函数', '一次函数', '二次函数', '反比例函数', '指数函数', '对数函数',
        '不等式', '绝对值', '根号', '平方根', '立方根',
        # 几何
        '全等三角形', '相似三角形', '等腰三角形', '直角三角形',
        '勾股定理', '平行线', '垂直', '中位线', '角平分线', '垂直平分线',
        '圆心角', '圆周角', '弧', '弦', '切线', '扇形',
        '对称轴', '旋转', '平移', '中心对称',
        # 统计概率
        '平均数', '中位数', '众数', '方差', '标准差',
        '概率', '频率', '样本', '总体',
    },

    '物理': {
        # 力学
        '重力', '弹力', '摩擦力', '合力', '分力', '力的合成', '力的分解',
        '牛顿第一定律', '牛顿第二定律', '牛顿第三定律',
        '惯性', '质量', '密度', '压强', '浮力', '阿基米德原理',
        '功', '功率', '机械能', '动能', '势能', '机械能守恒',
        '杠杆', '滑轮', '斜面', '机械效率',
        # 电学
        '电流', '电压', '电阻', '欧姆定律', '串联', '并联',
        '电功', '电功率', '焦耳定律', '安培', '伏特', '欧姆',
        '电磁感应', '电磁铁', '电动机', '发电机',
        # 光学
        '反射定律', '折射', '全反射', '凸透镜', '凹透镜',
        '实像', '虚像', '焦距', '光的色散',
        # 热学
        '比热容', '热量', '内能', '热传递',
        '熔化', '凝固', '汽化', '液化', '升华', '凝华',
    },

    '化学': {
        # 基本概念
        '原子', '分子', '离子', '元素', '化合物', '单质', '混合物',
        '化合价', '化学键', '共价键', '离子键', '金属键',
        '氧化还原', '氧化反应', '还原反应', '氧化剂', '还原剂',
        # 物质分类
        '酸', '碱', '盐', '氧化物',
        '饱和溶液', '不饱和溶液', '溶解度', '溶质', '溶剂',
        '质量守恒', '化学方程式', '配平',
        # 元素化学
        '摩尔', '摩尔质量', '阿伏伽德罗常数',
        '周期表', '周期律', '电子层', '最外层电子',
        '催化剂', '催化作用',
        # 实验
        '蒸馏', '过滤', '蒸发', '结晶', '萃取',
    },

    '生物': {
        # 细胞
        '细胞膜', '细胞壁', '细胞核', '细胞质', '线粒体', '叶绿体',
        '内质网', '高尔基体', '核糖体', '液泡', '溶酶体',
        '有丝分裂', '减数分裂', '细胞分化',
        # 遗传
        '基因', '染色体', 'DNA', 'RNA', '显性', '隐性',
        '基因型', '表现型', '等位基因', '纯合子', '杂合子',
        '孟德尔', '分离定律', '自由组合定律', '伴性遗传',
        # 代谢
        '光合作用', '呼吸作用', '有氧呼吸', '无氧呼吸',
        '酶', '催化', 'ATP',
        # 生态
        '种群', '群落', '生态系统', '食物链', '食物网',
        '生产者', '消费者', '分解者', '能量流动', '物质循环',
    },

    '历史': {
        # 中国古代史
        '封建制度', '郡县制', '科举制', '中央集权',
        '丝绸之路', '大运河', '长城',
        '春秋', '战国', '秦', '汉', '唐', '宋', '元', '明', '清',
        # 中国近现代史
        '鸦片战争', '太平天国', '洋务运动', '戊戌变法', '辛亥革命',
        '五四运动', '新文化运动', '北伐战争', '长征', '抗日战争',
        '解放战争', '新中国', '改革开放', '一国两制',
        # 世界史
        '文艺复兴', '宗教改革', '启蒙运动', '工业革命',
        '法国大革命', '美国独立战争', '俄国十月革命',
        '第一次世界大战', '第二次世界大战', '冷战',
        '联合国', '欧盟', '全球化',
    },

    '地理': {
        # 自然地理
        '经度', '纬度', '赤道', '回归线', '极圈',
        '板块构造', '地壳运动', '火山', '地震', '褶皱', '断层',
        '气候', '季风', '气压', '锋面', '气旋', '反气旋',
        '水循环', '洋流', '暖流', '寒流',
        '风化', '侵蚀', '搬运', '沉积', '地貌',
        # 人文地理
        '城市化', '工业化', '人口迁移', '产业转移',
        '农业区位', '工业区位', '交通运输',
        '可持续发展', '环境问题', '资源',
    },

    '政治': {
        # 政治常识
        '人民代表大会', '政治协商', '中国共产党', '多党合作',
        '民族区域自治', '基层群众自治', '依法治国',
        '公民权利', '公民义务', '民主选举', '民主决策', '民主管理', '民主监督',
        # 经济常识
        '市场经济', '宏观调控', '供给', '需求', '价值规律',
        '财政', '税收', '货币', '通货膨胀', '通货紧缩',
        # 哲学
        '唯物主义', '唯心主义', '辩证法', '形而上学',
        '矛盾', '对立统一', '量变', '质变', '否定之否定',
        '实践', '认识', '真理', '意识', '物质',
        '联系', '发展', '规律', '主要矛盾', '次要矛盾',
    },
}

def _get_subject_terms(subject):
    """获取指定学科的保护术语集合"""
    if subject in _SUBJECT_TERMS_PROTECTED:
        return _SUBJECT_TERMS_PROTECTED[subject]
    # 模糊匹配（如 "英语" 在 key 中）
    for k, v in _SUBJECT_TERMS_PROTECTED.items():
        if k in subject or subject in k:
            return v
    return set()


# ═══════════════════════════════════════════
#  Feature #5: 自动修复卡片数据 (审核reject → 修复 → 重审)
# ═══════════════════════════════════════════

_AUTO_FIX_PROMPT = """你是卡片数据修复助手。以下卡片数据在内容质量审核中被判定为 reject。
请根据审核反馈修复卡片数据，返回修复后的完整卡片 JSON。

== 原始卡片数据 ==
{card_json}

== 审核反馈 ==
知识性错误: {knowledge_errors}
缺失元素: {missing_elements}
红线问题: {red_flags}
改进建议: {improvements}
审核总评: {summary}

== 修复规则 ==
1. 修复所有知识性错误（替换错误的知识内容）
2. 补充所有缺失元素（missing）
3. 解决所有红线问题（red_flags）
4. 保持原始卡片结构不变（title/definition/core_points/mistakes/example/memory_tip/why_explanation）
5. 对于英语卡: 确保 mistakes 中的 wrong/correct 都是完整英文句子(≥6词)
6. 对于英语卡: 确保 core_points 有具体英文例句
7. memory_tip 不能是废话（如"记住就好""多练就会"）

== 输出格式 ==
只输出修复后的纯 JSON 对象（不要代码块标记）。保留所有原始字段和新增字段。"""


def _auto_fix_card_data(card, audit_result, api_key, all_keys=None):
    """
    根据内容审核的 reject 结果，调用 Gemini 自动修复卡片数据。
    
    返回: (fixed: bool, fixed_card: dict)
    """
    import urllib.request
    
    if not audit_result:
        return False, card
    
    # 提取审核反馈
    knowledge_errors = audit_result.get('knowledge_errors', [])
    missing = audit_result.get('must_have_check', {}).get('missing', [])
    red_flags = audit_result.get('red_flags', [])
    improvements = audit_result.get('improvements', [])
    summary = audit_result.get('summary', '')
    
    # 如果没有具体反馈，无法修复
    if not knowledge_errors and not missing and not red_flags and not improvements:
        return False, card
    
    # 构建修复请求
    # 去掉内部字段
    card_clean = {k: v for k, v in card.items() if not k.startswith('_')}
    prompt = _AUTO_FIX_PROMPT.format(
        card_json=json.dumps(card_clean, ensure_ascii=False, indent=2),
        knowledge_errors='\n'.join(f'  - {e}' for e in knowledge_errors) if knowledge_errors else '无',
        missing_elements='\n'.join(f'  - {m}' for m in missing) if missing else '无',
        red_flags='\n'.join(f'  - {r}' for r in red_flags) if red_flags else '无',
        improvements='\n'.join(f'  - {i}' for i in improvements[:5]) if improvements else '无',
        summary=summary or '无',
    )
    
    api_base = 'https://generativelanguage.googleapis.com/v1beta'
    text_models = [TEXT_MODEL, TEXT_MODEL_FALLBACK] if TEXT_MODEL_FALLBACK else [TEXT_MODEL]
    
    body = {
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {
            'maxOutputTokens': 8192,
            'temperature': 0.1,
            'thinkingConfig': {'thinkingBudget': 2048}
        }
    }
    
    data = None
    for mi, model in enumerate(text_models):
      url = f'{api_base}/models/{model}:generateContent?key={api_key}'
      try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read())
        if mi > 0:
            print(f'  │  ✅ 降级模型 {model} 修复成功')
        break
      except Exception as e:
        if mi < len(text_models) - 1:
            print(f'  │  ⚠️ {model} 失败({e}), 降级到 {text_models[mi+1]}...')
        else:
            print(f'  │  ⚠️ 自动修复API调用失败: {e}')
            return False, card

    if not data:
        return False, card
        
        candidates = data.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            all_text = ''
            for part in parts:
                if 'text' in part and not part.get('thought', False):
                    all_text += part['text']
            if all_text:
                json_match = re.search(r'\{[\s\S]*\}', all_text.strip())
                if json_match:
                    fixed = json.loads(json_match.group())
                    # 保留原始 id/full_id 等元数据
                    for meta_key in ('id', 'full_id', 'card_id', 'type', 'difficulty', '_eng_key_phrase'):
                        if meta_key in card and meta_key not in fixed:
                            fixed[meta_key] = card[meta_key]
                    return True, fixed
    
    return False, card


# ═══════════════════════════════════════════
# v10.11: 内容预处理 — 自动拆卡 + 内容压缩 + 文字量降级
# ═══════════════════════════════════════════

# ── 文字量预算常量 ──
_MAX_CARD_CHARS = 180         # 单张卡片文字总量上限（包含标题+定义+要点+例题+口诀）
_MAX_CORE_POINT_CHARS = 25    # 单条要点上限字数 (v10.12: 20→25, 保留更多语义)
_MAX_CORE_POINTS = 3          # 单张卡片最大要点数
_MAX_EXAMPLE_STEPS = 3        # 例题最大步骤数
_MAX_MEMORY_TIP_CHARS = 35    # 口诀上限字数 (v10.12: 16→35, 避免截断致无意义)
_MAX_LINE_CHARS = 14          # v10.17: manifest 单行最大中文字数(20→14)，每行更短AI渲染更准

# 可拆卡的类型（带有多个独立子项的卡片）
_SPLITTABLE_TYPES = {'陷阱卡', '辨析卡', '知识总结卡', '知识网络卡', '术语精准卡', '解题策略卡'}

# 拆卡时每个子组的子项上限
_SPLIT_GROUP_SIZE = 2


def _estimate_card_text_volume(card):
    """估算一张卡片的渲染文字总量（字符数）。
    
    返回: (total_chars, breakdown_dict)
    """
    title_chars = len(card.get('title', ''))
    definition_chars = len(card.get('definition', ''))
    
    points = card.get('core_points', [])
    points_chars = sum(len(str(p)) for p in points)
    
    example = card.get('example', {})
    example_chars = 0
    if isinstance(example, str):
        example_chars = len(example)
    elif isinstance(example, dict):
        example_chars += len(example.get('question', ''))
        for s in example.get('steps', []):
            example_chars += len(str(s))
        example_chars += len(example.get('answer', ''))
    
    tip_chars = len(card.get('memory_tip', ''))
    
    mistakes = card.get('mistakes', [])
    mistakes_chars = 0
    for m in mistakes[:1]:
        if isinstance(m, dict):
            mistakes_chars += len(m.get('wrong', '')) + len(m.get('correct', ''))
    
    total = title_chars + definition_chars + points_chars + example_chars + tip_chars + mistakes_chars
    
    breakdown = {
        'title': title_chars,
        'definition': definition_chars,
        'core_points': points_chars,
        'core_points_count': len(points),
        'example': example_chars,
        'memory_tip': tip_chars,
        'mistakes': mistakes_chars,
        'total': total,
    }
    return total, breakdown


def _auto_split_card(card, subject=''):
    """v10.11: 自动拆卡 — 将内容过多的卡片拆成多张子卡片。
    
    拆卡逻辑：
    1. 检测 core_points 中的独立子项（如 "陷阱1:", "陷阱2:" 等编号模式）
    2. 按每 _SPLIT_GROUP_SIZE 个子项拆成一张子卡
    3. 每张子卡继承原卡的 title/definition/type 等元数据
    4. 例题只分配给内容最相关的子卡
    
    返回: list[dict]  — 拆分后的卡片列表（至少1张）
    """
    card_type = card.get('type', '')
    points = card.get('core_points', [])
    
    # 条件1: 只有可拆类型才拆
    if card_type not in _SPLITTABLE_TYPES:
        return [card]
    
    # 条件2: 要点数 > _MAX_CORE_POINTS 才需要拆
    if len(points) <= _MAX_CORE_POINTS:
        return [card]
    
    # 条件3: 文字量不超标也不拆
    total_chars, _ = _estimate_card_text_volume(card)
    if total_chars <= _MAX_CARD_CHARS:
        return [card]
    
    # ── 检测编号模式（陷阱1, 陷阱2... 或 ①②③... 或 1. 2. 3.）──
    import re as _re
    numbered_pattern = _re.compile(
        r'^(?:陷阱|误区|易错|要点|知识点|规律|方法|步骤|特征|区别)?'
        r'\s*(?:\d+|[①②③④⑤⑥⑦⑧⑨⑩])[：:.\s、]'
    )
    
    # 检测要点是否有编号模式（或带"陷阱X"关键词）
    has_numbering = sum(1 for p in points if numbered_pattern.match(str(p).strip())) >= 2
    if not has_numbering:
        # 无编号也可以拆，按位置分组
        pass
    
    # ── 分组 ──
    groups = []
    for i in range(0, len(points), _SPLIT_GROUP_SIZE):
        group = points[i:i + _SPLIT_GROUP_SIZE]
        groups.append(group)
    
    if len(groups) <= 1:
        return [card]
    
    # ── 生成子卡片 ──
    sub_cards = []
    original_title = card.get('title', '')
    original_full_id = card.get('full_id', '')
    example = card.get('example', {})
    example_text = str(example)  # 用于匹配相关性
    
    # 判断方法/总结类要点（非编号的通用要点）单独成卡
    general_points = []
    specific_groups = []
    for g in groups:
        # 检查这组要点是否都是"判断方法"/"总结"等通用型
        is_general = all(
            any(kw in str(p) for kw in ['判断方法', '总结', '方法', '规律', '注意'])
            for p in g
        )
        if is_general:
            general_points.extend(g)
        else:
            specific_groups.append(g)
    
    # 如果有通用要点，加回最后一组
    if general_points:
        if specific_groups:
            specific_groups[-1] = specific_groups[-1] + general_points
        else:
            specific_groups = [general_points]
    
    for idx, group_points in enumerate(specific_groups):
        sub = {}
        # 复制原卡元数据
        for k, v in card.items():
            if k not in ('core_points', 'example', 'full_id', 'card_id', 'id'):
                sub[k] = v if not isinstance(v, (list, dict)) else (v.copy() if isinstance(v, list) else {**v})
        
        # 子卡 ID
        suffix = chr(ord('a') + idx)
        sub['full_id'] = f"{original_full_id}-{suffix}"
        sub['card_id'] = f"{card.get('card_id', card.get('id', ''))}-{suffix}"
        
        # 子卡标题：加上子组描述
        if len(specific_groups) > 1:
            # 从要点中提取子标题关键词
            first_point = str(group_points[0]).strip()
            # 尝试提取 "陷阱X" 或编号
            label_match = _re.match(r'^(陷阱|误区|易错)?[：:\s]*(\d+)(?:[：:.\s、])', first_point)
            last_point = str(group_points[-1]).strip()
            label_end = _re.match(r'^(?:陷阱|误区|易错)?[：:\s]*(\d+)', last_point)
            
            if label_match and label_end:
                start_num = label_match.group(2)
                end_num = label_end.group(1)
                prefix = label_match.group(1) or '要点'
                sub['title'] = f"{original_title}({prefix}{start_num}-{end_num})"
            else:
                sub['title'] = f"{original_title}(第{idx + 1}部分)"
        
        sub['core_points'] = group_points
        
        # 例题分配：只给内容最相关的子卡
        if example and isinstance(example, dict):
            example_q = example.get('question', '') + example.get('answer', '')
            # 计算这组要点与例题的关键词重叠度
            group_text = ' '.join(str(p) for p in group_points)
            overlap = sum(1 for c in set(example_q) if c in group_text and c not in '的是在了不也')
            if overlap >= 3 or idx == 0:
                sub['example'] = example
            else:
                sub['example'] = {}  # 其他子卡不分配例题
        
        # 精简定义（子卡不需要完整定义）
        orig_def = card.get('definition', '')
        if len(orig_def) > 60:
            sub['definition'] = orig_def[:60]
        
        # 口诀只分配给第一张子卡（或最后一张总结卡）
        if idx > 0:
            sub['memory_tip'] = ''
        
        sub['_split_source'] = original_full_id
        sub['_split_index'] = idx
        sub['_split_total'] = len(specific_groups)
        
        sub_cards.append(sub)
    
    return sub_cards if sub_cards else [card]


def _compress_card_content(card, subject='', keys=None):
    """v10.11: 内容压缩 — 将冗长的要点/定义/口诀压缩到渲染友好的长度。
    
    纯规则压缩（不调API），保证速度和可靠性：
    1. 每条 core_point 截断到 _MAX_CORE_POINT_CHARS 字（智能断句）
    2. definition 截断到 60 字
    3. memory_tip 截断到 _MAX_MEMORY_TIP_CHARS 字
    4. example.steps 最多 _MAX_EXAMPLE_STEPS 步
    5. core_points 最多 _MAX_CORE_POINTS 条
    
    返回: (card, compression_log: list[str])
    """
    import re as _re
    log = []
    card = {**card}  # shallow copy
    
    # ── 1. core_points 压缩 ──
    points = card.get('core_points', [])
    if isinstance(points, list):
        points = list(points)  # copy
    
    # 1a. 数量截断
    if len(points) > _MAX_CORE_POINTS:
        # 优先保留: 含公式的、含关键对比(❌/✅)的、排在前面的
        scored = []
        for i, p in enumerate(points):
            p_str = str(p)
            score = 0
            if any(c in p_str for c in '=÷×+−≥≤<>²³'):
                score += 10  # 公式型优先
            if '❌' in p_str or '✅' in p_str or '错' in p_str:
                score += 5   # 对比型优先
            score -= i * 0.1  # 靠前的优先
            scored.append((score, i, p))
        scored.sort(key=lambda x: -x[0])
        kept_indices = sorted([x[1] for x in scored[:_MAX_CORE_POINTS]])
        dropped = [str(points[i])[:30] for i in range(len(points)) if i not in kept_indices]
        points = [points[i] for i in kept_indices]
        log.append(f'📦 要点: {len(card["core_points"])}条→{len(points)}条 (丢弃: {", ".join(dropped)})')
    
    # 1b. 每条要点智能压缩
    compressed_points = []
    for p in points:
        p_str = str(p).strip()
        original_len = len(p_str)
        
        if original_len <= _MAX_CORE_POINT_CHARS:
            compressed_points.append(p_str)
            continue
        
        # 去掉编号前缀（"陷阱1：" → 保留内容部分）
        content = _re.sub(r'^(?:陷阱|误区|易错|要点|知识点)\s*\d*[：:.\s、]*', '', p_str).strip()
        
        # 如果有括号补充说明，去掉括号内容（优先，因为括号常是冗余）
        no_paren = _re.sub(r'[（(].+?[）)]', '', content).strip()
        if len(no_paren) <= _MAX_CORE_POINT_CHARS and len(no_paren) >= 6:
            compressed_points.append(no_paren)
            log.append(f'✂️ "{p_str[:25]}..." → "{no_paren}"')
            continue
        
        # 如果有"不是...而是..." 对比结构，提取核心
        contrast = _re.search(r'不是[「「]?(.{2,8})[」」]?[，,]\s*而是[「「]?(.{2,12})[」」]?', content)
        if contrast:
            short = f'非{contrast.group(1)}，而是{contrast.group(2)}'
            if len(short) <= _MAX_CORE_POINT_CHARS:
                compressed_points.append(short)
                log.append(f'✂️ "{p_str[:25]}..." → "{short}"')
                continue
        
        # 硬截断 — 在标点处断句
        truncated = content[:_MAX_CORE_POINT_CHARS]
        # 往回找最近的标点断点
        for cut_pos in range(len(truncated) - 1, max(len(truncated) - 6, 5), -1):
            if truncated[cut_pos] in '，。；、：':
                truncated = truncated[:cut_pos]
                break
        compressed_points.append(truncated)
        log.append(f'✂️ "{p_str[:25]}..." → "{truncated}"')
    
    card['core_points'] = compressed_points
    
    # ── 2. 定义压缩 ──
    definition = card.get('definition', '')
    if len(definition) > 60:
        # 在标点处断
        trunc_def = definition[:60]
        for i in range(len(trunc_def) - 1, max(len(trunc_def) - 10, 10), -1):
            if trunc_def[i] in '，。；':
                trunc_def = trunc_def[:i]
                break
        card['definition'] = trunc_def
        log.append(f'📦 定义: {len(definition)}字→{len(trunc_def)}字')
    
    # ── 3. 口诀压缩 ──
    tip = card.get('memory_tip', '')
    if len(tip) > _MAX_MEMORY_TIP_CHARS:
        # 保留前半段（通常更核心）
        trunc_tip = tip[:_MAX_MEMORY_TIP_CHARS]
        for i in range(len(trunc_tip) - 1, max(len(trunc_tip) - 4, 4), -1):
            if trunc_tip[i] in '，。；、':
                trunc_tip = trunc_tip[:i]
                break
        card['memory_tip'] = trunc_tip
        log.append(f'📦 口诀: {len(tip)}字→{len(trunc_tip)}字')
    
    # ── 4. 例题步骤压缩 ──
    example = card.get('example', {})
    if isinstance(example, dict):
        example = {**example}
        steps = example.get('steps', [])
        if len(steps) > _MAX_EXAMPLE_STEPS:
            example['steps'] = steps[:_MAX_EXAMPLE_STEPS]
            log.append(f'📦 步骤: {len(steps)}步→{_MAX_EXAMPLE_STEPS}步')
        # 每步截断
        if example.get('steps'):
            new_steps = []
            for s in example['steps']:
                s_str = str(s)
                if len(s_str) > 40:
                    s_str = s_str[:40]
                new_steps.append(s_str)
            example['steps'] = new_steps
        card['example'] = example
    
    # ── 5. mistakes.correct 保护（纠错内容是教学核心，不截断） ──
    mistakes = card.get('mistakes', [])
    if isinstance(mistakes, list) and mistakes:
        protected_mistakes = []
        for m in mistakes:
            if isinstance(m, dict):
                pm = {**m}
                # correct 字段是纠错核心语义，保留完整（最多80字）
                correct_text = pm.get('correct', '')
                if len(correct_text) > 80:
                    # 只在标点处截断，不做硬截断
                    trunc = correct_text[:80]
                    for ci in range(len(trunc) - 1, max(len(trunc) - 10, 10), -1):
                        if trunc[ci] in '，。；、':
                            trunc = trunc[:ci]
                            break
                    pm['correct'] = trunc
                    log.append(f'📦 纠错: {len(correct_text)}字→{len(trunc)}字')
                # wrong 可以适度截断（错误描述通常简短）
                wrong_text = pm.get('wrong', '')
                if len(wrong_text) > 30:
                    pm['wrong'] = wrong_text[:30]
                protected_mistakes.append(pm)
            else:
                protected_mistakes.append(m)
        card['mistakes'] = protected_mistakes

    # ── 6. 最终文字量检查 ──
    final_total, final_bd = _estimate_card_text_volume(card)
    if log:
        log.append(f'📊 压缩后总字数: {final_total}字 (上限{_MAX_CARD_CHARS})')
    
    return card, log


def _preprocess_card_for_rendering(card, subject='', keys=None):
    """v10.11 Step 0.5: 渲染预处理总入口。
    
    依次执行:
    1. 自动拆卡（内容过多的卡 → 多张子卡）
    2. 内容压缩（每张子卡独立压缩到渲染安全区间）
    
    返回: list[tuple(card, logs)]
    """
    # Step 1: 拆卡
    sub_cards = _auto_split_card(card, subject=subject)
    
    results = []
    for sc in sub_cards:
        # Step 2: 压缩
        compressed, comp_log = _compress_card_content(sc, subject=subject, keys=keys)
        results.append((compressed, comp_log))
    
    return results


def _validate_and_repair_card(card, subject, grade):
    """
    卡片数据源 schema 校验 + 自动修复。
    在进入图片生成管线前调用，确保关键字段质量。
    
    修复策略: 能修则修，不能修才拒绝。
    返回: (card_ok: bool, card: dict, issues: list[str])
    v10.6: 新增全学科专属校验
    """
    issues = []
    is_eng = subject == '英语' or card.get('type', '') in _GRAMMAR_TYPES
    
    # ── 1. 基础字段检查 ──
    if not card.get('title', '').strip():
        issues.append('❌ 缺少 title')
        return False, card, issues
    if not card.get('definition', '').strip():
        issues.append('❌ 缺少 definition')
        return False, card, issues
    
    # ── 2. 英语卡专属校验 ──
    if is_eng:
        # 2a. core_points 至少有 1 条含英文例句
        points = card.get('core_points', [])
        has_eng_sentence = False
        for p in points:
            eng_words = re.findall(r'[a-zA-Z]+', str(p))
            if len(eng_words) >= 4:  # ≥4个英文词视为含例句
                has_eng_sentence = True
                break
        if not has_eng_sentence and points:
            issues.append('⚠️ core_points 缺少英文例句，已标记')
        
        # 2b. mistakes 完整性检查 + 自动修复
        mistakes = card.get('mistakes', [])
        for i, m in enumerate(mistakes):
            if not isinstance(m, dict):
                continue
            wrong = m.get('wrong', '')
            correct = m.get('correct', '')
            # 如果 wrong/correct 少于 4 个英文词，标记为浅层
            wrong_words = len(re.findall(r'[a-zA-Z]+', wrong))
            correct_words = len(re.findall(r'[a-zA-Z]+', correct))
            if wrong and wrong_words < 4:
                issues.append(f'⚠️ mistakes[{i}].wrong 不是完整句 ({wrong_words}词): "{wrong[:50]}"')
            if correct and correct_words < 4:
                issues.append(f'⚠️ mistakes[{i}].correct 不是完整句 ({correct_words}词): "{correct[:50]}"')
            # 自动修复: 确保有 reason 字段
            if not m.get('reason', '').strip() and wrong and correct:
                m['reason'] = f'Note the difference between wrong and correct usage'
                issues.append(f'🔧 自动补充 mistakes[{i}].reason')
        
        # 2c. memory_tip 不能是废话
        tip = card.get('memory_tip', '').strip()
        _USELESS = {'多练就会', '记住就好', '背了就行', '牢记即可', '熟能生巧',
                     '搭配固定要多记', '重点词汇要掌握', '语法规则记清楚',
                     '记住哦', '来看看', '一起学', '加油哦', '注意哦'}
        if tip in _USELESS:
            card['memory_tip'] = ''  # 清空废话，让后续 prompt 生成自行构造
            issues.append(f'🔧 清空废话口诀: "{tip}"')
    
    # ── 2b. 全学科通用废话口诀检测 (v10.6) ──
    if not is_eng:
        tip = card.get('memory_tip', '').strip()
        _USELESS_GENERAL = {
            '多练就会', '记住就好', '背了就行', '牢记即可', '熟能生巧',
            '认真学习', '好好复习', '多做练习', '仔细审题', '注意细节',
            '记住哦', '来看看', '一起学', '加油哦', '注意哦',
            '要记住', '别忘了', '很重要',
        }
        if tip in _USELESS_GENERAL:
            card['memory_tip'] = ''
            issues.append(f'🔧 清空废话口诀: "{tip}"')
    
    # ── 3. 学科专属校验 (v10.6) ──
    if subject == '语文':
        _validate_yuwen(card, issues)
    elif subject == '物理':
        _validate_physics(card, issues)
    elif subject == '化学':
        _validate_chemistry(card, issues)
    elif subject == '生物':
        _validate_biology(card, issues)
    elif subject == '历史':
        _validate_history(card, issues)
    
    # ── 4. 认知负荷检查（如果引擎可用）──
    if _HAS_DESIGN:
        try:
            cog = compute_cognitive_load(card, grade)
            if cog.get('overloaded', False):
                ratio = cog.get('overload_ratio', 1.0)
                suggestions = cog.get('suggestions', [])
                issues.append(f'⚠️ 认知负荷过高 (ratio={ratio:.1f}): {"; ".join(suggestions[:2])}')
                # 自动修复: 截断过多的 core_points
                if len(card.get('core_points', [])) > 4:
                    card['core_points'] = card['core_points'][:4]
                    issues.append('🔧 自动截断 core_points 到 4 条')
                # 自动修复: 截断过多的 steps
                steps = card.get('example', {}).get('steps', [])
                if len(steps) > 5:
                    card['example']['steps'] = steps[:5]
                    issues.append('🔧 自动截断 steps 到 5 步')
        except Exception as e:
            pass  # 设计引擎出错不阻塞管线
    
    # issues 都是 warning 级别，不阻塞管线
    return True, card, issues


def _validate_yuwen(card, issues):
    """语文学科校验"""
    definition = card.get('definition', '')
    title = card.get('title', '')
    
    # 诗词类: 检查原文是否完整
    poetry_kw = ['古诗', '诗词', '默写', '文言文', '古文']
    is_poetry = any(k in title + definition for k in poetry_kw)
    if is_poetry:
        points = card.get('core_points', [])
        if not points:
            issues.append('⚠️ 语文诗词类缺少core_points（应含原文/注释）')
    
    # 修辞类: 检查是否有例句
    rhetoric_kw = ['修辞', '比喻', '拟人', '排比']
    is_rhetoric = any(k in title + definition for k in rhetoric_kw)
    if is_rhetoric:
        example = card.get('example', {})
        if isinstance(example, dict) and not example.get('question'):
            issues.append('⚠️ 语文修辞类缺少典型例句')


def _validate_physics(card, issues):
    """物理学科校验"""
    points = card.get('core_points', [])
    definition = card.get('definition', '')
    
    # 物理卡通常应包含公式或单位
    formula_chars = set('=÷×+−≥≤<>°²³∠NkgmsPaJWVAΩ')
    has_formula = any(any(c in str(p) for c in formula_chars) for p in points)
    has_formula = has_formula or any(c in definition for c in formula_chars)
    if not has_formula and len(points) > 0:
        issues.append('⚠️ 物理卡片core_points中未检测到公式/单位，请确认')


def _validate_chemistry(card, issues):
    """化学学科校验"""
    points = card.get('core_points', [])
    
    # 检查是否有化学相关符号
    chem_pattern = re.compile(r'[A-Z][a-z]?[\d]*|→|↑|↓|⁺|⁻')
    has_chem = any(chem_pattern.search(str(p)) for p in points)
    if not has_chem and len(points) > 0:
        # 不一定所有化学卡都有符号，但标记一下
        pass  # 化学概念卡可能纯文字


def _validate_biology(card, issues):
    """生物学科校验"""
    # 生物卡通常不需要特殊符号校验
    # 主要确保术语准确性（在 term injection 阶段处理）
    pass


def _validate_history(card, issues):
    """历史学科校验"""
    definition = card.get('definition', '')
    title = card.get('title', '')
    
    # 历史卡通常应包含年代信息
    has_year = bool(re.search(r'\d{3,4}年?', title + definition))
    if not has_year:
        # 不是所有历史卡都需要年代，但很多需要
        pass  # 历史概念卡可能无年代


def _build_card_info(card, subject, grade, semester, canvas=None):
    """构建传给 prompt 生成器的卡片信息（自动区分教育/养生/语法/语文类）"""
    if subject in _WELLNESS_SUBJECTS:
        return _build_card_info_wellness(card, subject, grade, semester)
    # 英语学科的卡片统一走语法/英语路径
    if subject == '英语' or card.get('type') in _GRAMMAR_TYPES:
        return _build_card_info_grammar(card, subject, grade, semester, canvas=canvas)
    # v10.6: 语文学科走专属路径（诗词/文言文/修辞需要特殊处理）
    if subject == '语文':
        return _build_card_info_yuwen(card, subject, grade, semester, canvas=canvas)
    return _build_card_info_edu(card, subject, grade, semester)


def _is_text_on_topic(text, topic_kw):
    """判断一段文本是否与主题关键词相关（至少有1个交集）"""
    import re as _re
    if not text or not topic_kw:
        return True  # 无法判断时默认保留
    text_kw = set(_re.findall(r'[a-zA-Z]{3,}', str(text).lower()))
    if not text_kw:
        return True  # 纯中文内容，保留
    return bool(text_kw & topic_kw)


def _get_topic_keywords(card):
    """从标题+定义中提取本卡主题英文关键词集合"""
    import re as _re
    topic_text = (card.get('title', '') + ' ' + card.get('definition', '')).lower()
    return set(_re.findall(r'[a-zA-Z]{3,}', topic_text))



def _detect_shallow_steps(card):
    """检测步骤是否为'拆词式'浅层内容 (如把 pay attention to 拆成三步: attention / pay->attention / pay attention to)
    
    返回: (is_shallow: bool, reason: str)
    """
    import re as _re
    steps = (card.get('example') or {}).get('steps', [])
    if not steps:
        return False, ''
    
    definition = card.get('definition', '').lower().strip()
    title = card.get('title', '').lower().strip()
    
    # 检测1: 步骤是否只是逐词拆解短语
    # 如果大部分步骤只有1-2个英文单词(无解释句子)，就是拆词
    short_step_count = 0
    for s in steps:
        s_str = str(s).strip()
        # 去掉箭头等符号后，看纯英文单词数
        eng_words = _re.findall(r'[a-zA-Z]+', s_str)
        # 如果中文字符极少(<=8)且英文单词<=3，视为浅层步骤
        cn_chars = len(_re.findall(r'[\u4e00-\u9fff]', s_str))
        if len(eng_words) <= 3 and cn_chars <= 8:
            short_step_count += 1
    
    if len(steps) >= 2 and short_step_count >= len(steps) * 0.6:
        return True, f'{short_step_count}/{len(steps)}步是孤立短语/单词，缺少完整例句和解释'
    
    # 检测2: 步骤是否包含完整英文句子(至少有主谓结构，>=5个词)
    has_sentence = False
    for s in steps:
        eng_words = _re.findall(r'[a-zA-Z]+', str(s))
        if len(eng_words) >= 5:
            has_sentence = True
            break
    
    if not has_sentence and len(steps) >= 2:
        return True, '所有步骤都没有完整英文例句，缺乏教学深度'
    
    return False, ''


def _filter_off_topic_steps(card):
    """过滤掉与卡片主题无关的 steps，防止混杂知识点传给 Gemini"""
    import re as _re
    steps = (card.get('example') or {}).get('steps', [])
    if len(steps) < 2:
        return steps
    topic_kw = _get_topic_keywords(card)
    if not topic_kw:
        return steps  # 无英文关键词可比较，全部保留
    filtered = []
    for i, s in enumerate(steps):
        kw = set(_re.findall(r'[a-zA-Z]{3,}', str(s).lower()))
        if not kw:
            filtered.append(s)
            continue
        # 与主题有交集 → 保留
        if kw & topic_kw:
            filtered.append(s)
            continue
        # 与相邻 step 有交集 → 保留
        neighbor_ok = False
        if i > 0:
            prev_kw = set(_re.findall(r'[a-zA-Z]{3,}', str(steps[i-1]).lower()))
            if kw & prev_kw:
                neighbor_ok = True
        if not neighbor_ok and i < len(steps) - 1:
            next_kw = set(_re.findall(r'[a-zA-Z]{3,}', str(steps[i+1]).lower()))
            if kw & next_kw:
                neighbor_ok = True
        if neighbor_ok:
            filtered.append(s)
        # else: 离题 step，丢弃
    return filtered if filtered else steps[:1]  # 至少保留1个


def _filter_off_topic_core_points(card):
    """过滤掉与主题无关的 core_points"""
    points = card.get('core_points', [])[:5]
    topic_kw = _get_topic_keywords(card)
    if not topic_kw or not points:
        return points
    filtered = [p for p in points if _is_text_on_topic(str(p), topic_kw)]
    return filtered if filtered else points[:1]


def _filter_off_topic_mistakes(card):
    """过滤掉与主题无关的 mistakes 条目"""
    mistakes = card.get('mistakes', [])
    topic_kw = _get_topic_keywords(card)
    if not topic_kw or not mistakes:
        return mistakes
    filtered = []
    for m in mistakes:
        if not isinstance(m, dict):
            continue
        # 判断 wrong+correct+reason 是否与主题相关
        m_text = f"{m.get('wrong', '')} {m.get('correct', '')} {m.get('reason', '')}"
        if _is_text_on_topic(m_text, topic_kw):
            filtered.append(m)
    return filtered if filtered else []  # 离题 mistakes 直接丢弃（不保留）


def _clean_answer(card):
    """清理 answer 中的离题内容（例如把 'pay; to; succeed' 清理为 'pay; to'）"""
    import re as _re
    answer = str((card.get('example') or {}).get('answer', ''))
    topic_kw = _get_topic_keywords(card)
    if not topic_kw or not answer:
        return answer
    # 按分号/逗号拆分答案
    parts = _re.split(r'[;,]\s*', answer)
    if len(parts) <= 1:
        return answer  # 不是多答案，原样返回
    cleaned = []
    for part in parts:
        part_kw = set(_re.findall(r'[a-zA-Z]{3,}', part.lower()))
        if not part_kw or (part_kw & topic_kw):
            cleaned.append(part.strip())
        # else: 离题答案部分，丢弃
    return '; '.join(cleaned) if cleaned else answer


def _build_concept_card_layout(eng_key_phrase, cn_meaning, grammar_terms):
    """构建语法概念卡（一词多用型）的布局指令 — 思维导图/放射状变体"""
    terms_display = '、'.join(grammar_terms[:4])
    return f"""📐 语法概念卡 — 思维导图布局（一词多用型）

本卡特点: 「{eng_key_phrase}」有多种语法用途（{terms_display}），需要用放射状/思维导图展示。

【整体布局 — 放射状/思维导图】
  中心: 「{eng_key_phrase}」大号粗体居中，下方小字（{cn_meaning}）
  分支: 从中心向外辐射 2-4 个分支，每个分支 = 一种语法用途

【每个分支 — 必须包含】
  ① 中文语法术语标签（如"宾语从句""表语从句"）— 用色块/气泡标注
  ② 一个完整英文例句（≥6词）— 作为可见文字渲染
  ⚠️ 中文语法术语必须100%拼写正确！"同位语从句"≠"应语从句"
  ⚠️ 如果不确定中文术语，改用英文标注（如 appositive clause）
  
【分支布局建议】
  - 每个分支用不同的柔和色块区分（蓝/绿/粉/紫）
  - 术语标签用粗体在色块上方或内部
  - 例句用较小字体在色块内
  - 整体形成清晰的放射状结构"""


def _build_standard_card_layout(eng_key_phrase, cn_meaning):
    """构建标准英语卡（搭配/易混词/单一语法点）的布局指令 — 线性ABCD"""
    return f"""📐 卡片严格4个区块，自上而下，不允许其他内容：

【区块A — 标题Banner】
  英文短语/词组本身「{eng_key_phrase}」，大号粗体居中
  下方小字中文释义（{cn_meaning}，≤4中文字）
  ⚠️ LINE1（内容区第一行）不能重复写「{eng_key_phrase}」！应直接写用法结构说明。

【区块B — 用法拓展】(最重要的教学区！占卡片≥40%面积！)
  ⚠️ 这个区块必须是 **纯文字教学内容**，不是卡通/插图/装饰！
  展示该知识点的 2-3 种典型搭配/用法结构
  每种结构必须配一个完整英文例句（≥6词），例句必须作为可见文字渲染在卡片上
  例如: 如果知识点是一个搭配短语，展示它接不同词性时的句子
       如果是易混词，展示两个词各自正确的用法句
       如果是语法点，展示该语法在不同语境中的用法
  ⚠️ 用法结构由你根据语法规则推断，不要只是翻译 definition！
  🚫 绝对禁止用卡通人物、"记住哦"气泡、装饰图案代替本区块的教学文字！"""


# ── 易混词卡 检测 + 双栏布局 ──────────────────────────────────────

def _is_confusion_card(card):
    """判断是否为「易混词卡」— 比较两个容易混淆的词/短语
    
    检测依据:
    1) card type 包含"易混"
    2) title/definition 包含 vs / VS / 与…区分 / 辨析
    3) mistakes 中同时含有两个不同英文动词/名词
    返回: (bool, word_a, word_b, meaning_a, meaning_b)
    """
    card_type = card.get('type', '')
    title = card.get('title', '')
    definition = card.get('definition', '')
    text = f'{card_type} {title} {definition}'
    
    # 明确的易混词标识
    is_confusion = '易混' in text or '辨析' in text
    
    # vs / VS 分隔的两个词
    import re as _re
    vs_match = _re.search(r'([a-zA-Z]+)\s*(?:vs\.?|VS\.?|v\.s\.?|与|和|还是)\s*([a-zA-Z]+)', text)
    if vs_match:
        is_confusion = True
    
    if not is_confusion:
        return False, '', '', '', ''
    
    # 提取两个对比词
    word_a, word_b = '', ''
    if vs_match:
        word_a, word_b = vs_match.group(1).strip(), vs_match.group(2).strip()
    else:
        # 从 title/definition 提取前两个不同的英文词
        eng_words = _re.findall(r'[a-zA-Z]{3,}', text)
        seen = []
        for w in eng_words:
            wl = w.lower()
            if wl not in [s.lower() for s in seen]:
                seen.append(w)
            if len(seen) >= 2:
                break
        if len(seen) >= 2:
            word_a, word_b = seen[0], seen[1]
    
    if not word_a or not word_b:
        return False, '', '', '', ''
    
    # 尝试从 definition 提取各自中文含义
    meaning_a = ''
    meaning_b = ''
    # 尝试: "affect 影响(动词), effect 效果(名词)"
    for word, attr in [(word_a, 'meaning_a'), (word_b, 'meaning_b')]:
        pat = _re.search(rf'{_re.escape(word)}[,，\s]*[=:：]?\s*([\u4e00-\u9fff]+)', definition)
        if pat:
            if attr == 'meaning_a':
                meaning_a = pat.group(1)[:6]
            else:
                meaning_b = pat.group(1)[:6]
    
    return True, word_a, word_b, meaning_a, meaning_b


def _build_confusion_card_layout(word_a, word_b, meaning_a, meaning_b):
    """构建易混词卡 — 双栏对比布局"""
    ma = f'（{meaning_a}）' if meaning_a else ''
    mb = f'（{meaning_b}）' if meaning_b else ''
    return f"""📐 易混词对比卡 — 左右双栏布局

本卡特点: 「{word_a}」vs「{word_b}」容易混淆，用双栏对比帮助学生区分。

【顶部标题栏】
  标题: 「{word_a} vs {word_b}」大号粗体居中
  副标题: 小字 "易混词辨析"

【双栏对比区 — 占卡片≥50%面积】(最重要的教学区！)
  ┌──────────────────┬──────────────────┐
  │   {word_a} {ma}  │   {word_b} {mb}  │
  ├──────────────────┼──────────────────┤
  │ 词性:            │ 词性:            │
  │ 用法:            │ 用法:            │
  │ 例句(≥6词):      │ 例句(≥6词):      │
  └──────────────────┴──────────────────┘
  
  ⚠️ 每列必须包含: 词性标注 + 核心用法说明 + 一个完整英文例句
  ⚠️ 两列用不同色块区分（如左蓝右绿），形成强烈视觉对比
  ⚠️ 例句中的关键词（{word_a}/{word_b}）用粗体或下划线高亮

【速记区 — 底部】
  一句简短的区分口诀，用英文关键词 + ≤4中文字
  好口诀: "{word_a}=动词做" / "{word_b}=名词果"
  🚫 禁止万能废话: "要区分""记清楚""多注意" """


# ── 时态卡 检测 + 时间轴布局 ──────────────────────────────────────

_TENSE_KEYWORDS = {
    '一般现在时', '一般过去时', '一般将来时',
    '现在进行时', '过去进行时', '将来进行时',
    '现在完成时', '过去完成时', '将来完成时',
    '现在完成进行时', '过去完成进行时',
    '过去将来时',
    'present simple', 'past simple', 'future simple',
    'present continuous', 'past continuous',
    'present perfect', 'past perfect', 'future perfect',
}

def _is_tense_card(card):
    """判断是否为「时态卡」— 讲解某个时态的用法
    
    检测依据: title/definition/type 包含时态关键词
    返回: (bool, tense_name)
    """
    text = f"{card.get('type', '')} {card.get('title', '')} {card.get('definition', '')}"
    text_lower = text.lower()
    
    for kw in _TENSE_KEYWORDS:
        if kw in text or kw in text_lower:
            return True, kw
    
    # 通用检测: "...时态" / "...时"
    import re as _re
    m = _re.search(r'([\u4e00-\u9fff]{2,6}时(?:态)?)', text)
    if m and '时态' in text:
        return True, m.group(1)
    
    return False, ''


def _build_tense_card_layout(eng_key_phrase, cn_meaning, tense_name):
    """构建时态卡 — 时间轴布局"""
    return f"""📐 时态卡 — 时间轴布局

本卡特点: 讲解「{tense_name}」时态，使用时间轴直观展示时间关系。

【顶部标题】
  标题: 「{tense_name}」大号粗体居中
  副标题: 英文时态名 + 中文释义（{cn_meaning}）

【时间轴区 — 占卡片≥45%面积】(核心教学区！)
  画一条水平时间轴线: ←── past ── now ── future ──→
  
  在时间轴上用箭头/标记/色块标出该时态的时间范围:
  - 标记动作发生的时间点/时间段
  - 用色块高亮该时态覆盖的时间区域
  - 在标记旁写出该时态的结构公式
  
  结构公式示例: "S + have/has + V-ed (past participle)"
  ⚠️ 结构公式必须作为可见文字渲染！

【例句区 — 时间轴下方】
  2-3 个完整英文例句（各≥6词），展示该时态在不同语境的用法:
  ① 基本用法例句
  ② 否定/疑问形式例句
  ③ 常见时间标志词（如 since, for, already, yet 等）
  
  时间标志词用色块标注，与时间轴上的标记颜色对应

【底部速记】
  公式 + 标志词的精炼总结
  如: "have+V-ed → 已完成" / "标志词: since/for/already"
  🚫 禁止万能废话"""


def _is_grammar_concept_card(card):
    """判断是否是「语法概念卡」— 一个词/结构有多种语法用途的卡片
    
    如: 连接that（宾语/表语/同位语从句）, 连接词when/if, 不定式的用法, 分词的用法
    特征: title 或 definition 中出现多种语法术语 (≥2种从句/时态/用法)
    """
    text = f"{card.get('title', '')} {card.get('definition', '')}"
    # 统计出现了几种受保护的语法术语
    found_terms = [t for t in _GRAMMAR_TERMS_PROTECTED if t in text]
    # 也检查 core_points 中是否有多种术语
    for p in card.get('core_points', [])[:6]:
        for t in _GRAMMAR_TERMS_PROTECTED:
            if t in str(p) and t not in found_terms:
                found_terms.append(t)
    return len(found_terms) >= 2, found_terms


def _find_subject_terms_in_card(card, subject):
    """v10.6: 通用版 — 在卡片中查找属于该学科的保护术语
    
    返回: list[str] — 卡片中出现的受保护术语列表
    """
    terms_set = _get_subject_terms(subject)
    if not terms_set:
        return []
    
    text = f"{card.get('title', '')} {card.get('definition', '')}"
    found = [t for t in terms_set if t in text]
    # 也检查 core_points
    for p in card.get('core_points', [])[:6]:
        p_str = str(p)
        for t in terms_set:
            if t in p_str and t not in found:
                found.append(t)
    # 检查 mistakes
    for m in card.get('mistakes', [])[:3]:
        if isinstance(m, dict):
            m_text = f"{m.get('wrong', '')} {m.get('correct', '')} {m.get('reason', '')}"
            for t in terms_set:
                if t in m_text and t not in found:
                    found.append(t)
    return found


def _build_card_info_grammar(card, subject, grade, semester, canvas=None):
    """构建英语语法/搭配类卡片信息 — v6 极简用法卡（通用版）
    
    设计理念: 一张卡只做一件事 → 展示一个短语/语法点的「用法 + 对错 + 拓展」
    对所有英语知识点通用：搭配卡/语法辨析卡/易混词卡/句型卡/词汇卡...
    支持两种布局:
    - 默认: 线性 ABCD 四区块（搭配/易混词/单一语法点）
    - 变体: 思维导图/放射状（一词多用型语法概念卡）
    """
    card_type = card.get('type', '语法辨析卡')

    # ── 提取英文核心短语（作为标题和主题锚点）──
    definition = card.get('definition', '')
    title_raw = card.get('title', '')
    # 1) 从 definition 中提取最长的英文短语
    eng_phrases = re.findall(r'[a-zA-Z][a-zA-Z\s]{2,}', definition)
    eng_key_phrase = max(eng_phrases, key=len).strip() if eng_phrases else ''
    # 2) 从 title 提取
    if not eng_key_phrase:
        eng_phrases = re.findall(r'[a-zA-Z][a-zA-Z\s]{2,}', title_raw)
        eng_key_phrase = max(eng_phrases, key=len).strip() if eng_phrases else ''
    # 3) ★ 当 title+definition 无英文时，从 core_points 提取第一个具体英文短语
    #    解决"综合类"知识点（如"高频词汇活用与固定搭配"）标题为纯中文的问题
    _cn_from_core_point = ''  # 从同一 core_point 提取的中文释义
    if not eng_key_phrase or not re.search(r'[a-zA-Z]{3,}', eng_key_phrase):
        for p in card.get('core_points', []):
            p_str = str(p)
            # 优先: 反引号内英文短语 `make progress`
            bt = re.findall(r'`([a-zA-Z][a-zA-Z\s]+?)`', p_str)
            if bt:
                eng_key_phrase = bt[0].strip()
                # ★ 同时提取同一 core_point 的中文释义（括号内中文）
                cn_in_paren = re.search(r'[（(]\s*([\u4e00-\u9fff/、]+)\s*[）)]', p_str)
                if cn_in_paren:
                    _cn_from_core_point = cn_in_paren.group(1).strip()[:8]
                break
            # 次优: 多词英文短语 (≥2 words)
            mw = re.findall(r'[a-zA-Z]+(?:\s+[a-zA-Z]+)+', p_str)
            if mw:
                eng_key_phrase = mw[0].strip()
                cn_in_paren = re.search(r'[（(]\s*([\u4e00-\u9fff/、]+)\s*[）)]', p_str)
                if cn_in_paren:
                    _cn_from_core_point = cn_in_paren.group(1).strip()[:8]
                break
            # v10.21: 兜底: 第一个 ≥6字母 英文单词(避免 were/bought 等短词)
            sw = re.findall(r'[a-zA-Z]{6,}', p_str)
            if sw:
                eng_key_phrase = sw[0].strip()
                cn_in_paren = re.search(r'[（(]\s*([\u4e00-\u9fff/、]+)\s*[）)]', p_str)
                if cn_in_paren:
                    _cn_from_core_point = cn_in_paren.group(1).strip()[:8]
                break
    if not eng_key_phrase:
        eng_key_phrase = title_raw  # 最终兜底

    # 注入到 card 以供后续 OCR 审计使用
    card['_eng_key_phrase'] = eng_key_phrase

    # ── 检测卡片子类型 ──
    is_concept_card, grammar_terms = _is_grammar_concept_card(card)
    if is_concept_card:
        print(f'      [grammar concept] 检测到语法概念卡, 术语: {grammar_terms[:5]}')

    is_confusion, conf_word_a, conf_word_b, conf_mean_a, conf_mean_b = _is_confusion_card(card)
    if is_confusion:
        print(f'      [confusion card] 检测到易混词卡: {conf_word_a} vs {conf_word_b}')

    is_tense, tense_name = _is_tense_card(card)
    if is_tense:
        print(f'      [tense card] 检测到时态卡: {tense_name}')

    # 覆盖 card title
    # 易混词卡: "word_a vs word_b" 样式标题
    # 时态卡: 允许中文时态名
    # 语法概念卡: 允许 "English + 中文语法功能" 混合标题 (如 "that 从句")
    # 普通卡: 强制英文标题
    if is_confusion and conf_word_a and conf_word_b:
        card['title'] = f'{conf_word_a} vs {conf_word_b}'
        print(f'      [prompt title fix] confusion: "{title_raw}" → "{card["title"]}"')
    elif is_tense and tense_name:
        # v10.21: 时态卡标题 — 用时态结构而非单词
        # 提取时态结构 (如 "was/were + done", "have/has + done")
        tense_structure = ''
        for p in card.get('core_points', []):
            p_str = str(p)
            # 匹配时态结构: "主语 + was/were + doing" 或 "have/has + p.p."
            struct = re.findall(r'[a-zA-Z]+(?:\s*/\s*[a-zA-Z]+)?(?:\s*\+\s*[a-zA-Z.]+)+', p_str)
            if struct:
                tense_structure = max(struct, key=len).strip()[:25]
                break
            # 匹配: "S + V + O" 类
            struct2 = re.findall(r'[a-zA-Z]+(?:\s+[a-zA-Z/+.]+){1,}', p_str)
            if struct2:
                candidate = max(struct2, key=len).strip()[:25]
                if len(candidate.split()) >= 2:
                    tense_structure = candidate
                    break
        
        if tense_structure:
            card['title'] = f'{tense_name} {tense_structure}'
        elif eng_key_phrase and len(eng_key_phrase.split()) >= 2:
            card['title'] = f'{tense_name} ({eng_key_phrase})'
        else:
            card['title'] = tense_name
        print(f'      [prompt title fix] tense: "{title_raw}" → "{card["title"]}"')
    elif is_concept_card and eng_key_phrase:
        # 保留中文语法功能词 + 英文关键词的混合标题
        cn_grammar_part = re.sub(r'[a-zA-Z\s]+', '', title_raw).strip()[:4]
        if cn_grammar_part:
            card['title'] = f'{cn_grammar_part}{eng_key_phrase}'
        else:
            card['title'] = eng_key_phrase
        print(f'      [prompt title fix] concept: "{title_raw}" → "{card["title"]}"')
    elif eng_key_phrase and not re.search(r'[a-zA-Z]{3,}', title_raw):
        card['title'] = eng_key_phrase
        print(f'      [prompt title fix] "{title_raw}" → "{card["title"]}"')

    # 获取自适应字数限制
    eff = _get_effective_params()
    _mc = eff.get('max_chinese_chars', 20)
    _mpb = eff.get('max_chars_per_block', 5)

    # ── 提取中文释义（短）──
    # ★ 优先使用从 core_point 提取的释义（与 eng_key_phrase 语义匹配）
    cn_meaning = _cn_from_core_point if _cn_from_core_point else ''
    if not cn_meaning:
        cn_match = re.search(r'[，,]?\s*(意为|意思是|表示|指的是)[\s""]*([\u4e00-\u9fff/、]+)', definition)
        if cn_match:
            cn_meaning = cn_match.group(2).strip()[:8]
    if not cn_meaning:
        cn_chars = re.findall(r'[\u4e00-\u9fff]+', definition)
        if cn_chars:
            cn_meaning = max(cn_chars, key=len)[:8]

    # ── 收集参考数据: core_points（过滤离题后）──
    points = _filter_off_topic_core_points(card)[:4]
    ref_points = '\n'.join(f'  • {str(p).strip()[:80]}' for p in points) if points else '  （无）'

    # ── 收集参考数据: 对错例句 ──
    on_topic_mistakes = _filter_off_topic_mistakes(card)
    contrast_ref = ''
    if on_topic_mistakes:
        m = on_topic_mistakes[0]
        contrast_ref = f"  ❌ {m.get('wrong', '')[:80]}\n  ✅ {m.get('correct', '')[:80]}"
        reason = m.get('reason', '')
        if reason:
            contrast_ref += f"\n  💡 {reason[:60]}"
    else:
        contrast_ref = f"  （数据缺失，请你根据「{eng_key_phrase}」自行设计，必须是该知识点的真实高频错误）"

    # ── 本质原因 / 口诀 ──
    why_exp = card.get('why_explanation', '')[:120]
    # v10.19: 英语句型卡口诀用「英文关键词+≤4中文字」格式，截断更短防乱拼
    raw_tip = card.get('memory_tip', '')
    if subject == '英语' and raw_tip:
        # 尝试提取口诀中最精华的片段（英文+短中文），避免长口诀被截断成乱拼
        import re as _re_tip
        # 优先取第一个短句（句号/逗号/感叹号分割）
        tip_parts = _re_tip.split(r'[。，！!,]', raw_tip)
        tip_parts = [p.strip() for p in tip_parts if p.strip()]
        if tip_parts:
            # 选最短且含英文的片段
            eng_tips = [p for p in tip_parts if _re_tip.search(r'[a-zA-Z]', p)]
            if eng_tips:
                memory_tip = min(eng_tips, key=len)[:20]
            else:
                memory_tip = tip_parts[0][:15]
        else:
            memory_tip = raw_tip[:15]
    else:
        memory_tip = raw_tip[:30]

    # ── 构建布局指令（优先级: 易混词 > 时态 > 概念 > 标准）──
    if is_confusion:
        layout_block = _build_confusion_card_layout(conf_word_a, conf_word_b, conf_mean_a, conf_mean_b)
    elif is_tense:
        layout_block = _build_tense_card_layout(eng_key_phrase, cn_meaning, tense_name)
    elif is_concept_card:
        layout_block = _build_concept_card_layout(eng_key_phrase, cn_meaning, grammar_terms)
    else:
        layout_block = _build_standard_card_layout(eng_key_phrase, cn_meaning)

    return f"""学科: {subject} | {grade} {semester} | 类型: {card_type}

═══════ 🎯 极简用法卡 — 通用设计规范 ═══════

本卡主角: 「{eng_key_phrase}」（{cn_meaning}）
语法规则: {definition[:120]}

{layout_block}

【区块C — ❌/✅ 对比】
  一组完整句子（各≥6词），展示学生最容易犯的错误
  错处用红色高亮，正处用绿色高亮
  错因标注用英文短语（如 "✗ do → ✓ make" 或 "wrong: adj → right: noun"）
  ⚠️ 错因不要写中文句子！中文渲染容易乱码，用英文箭头标注更清晰

【区块D — 记忆口诀】
  用「英文关键词 + ≤4中文字」的混合格式，减少纯中文渲染出错
  好口诀示例: "progress用make" / "affect=动词" / "enough放后面"
  🚫 万能废话=废卡: "搭配固定要多记" / "语法规则记清楚" / "重点词汇要掌握"

═══════ ⛔ 6条铁律（违反=废卡）═══════

🔒1. 标题包含「{eng_key_phrase}」（英文！），{'语法概念卡允许混合标题如"连接that"' if is_concept_card else '🚫禁止纯中文泛化标题'}
🔒2. {'每个分支必须有中文语法术语+完整英文例句，术语文字必须精确（如"同位语从句"不能写成"应语从句"）' if is_concept_card else '区块B必须展示2-3种不同的用法/搭配，每种配完整英文例句。区块B是纯文字教学区，🚫严禁用卡通人物或装饰替代'}
🔒3. 区块C的❌/✅必须是学生真正会犯的错误，完整句子≥6词，错因用英文标注（不写中文句子）
🔒4. 全卡所有内容只能涉及「{eng_key_phrase}」这一个知识点，🚫严禁混入无关词汇/语法点
🔒5. 口诀用「英文+≤4中文字」混合格式，🚫禁止万能废话
🔒6. 全卡中文≤{_mc}字，英文不限。每个中文字必须粗体清晰，中文越少越好
🔒7. 🚫严禁出现以下废话填充: "记住哦""来看看""一起学""加油""注意哦""要记住"——这些不是教学内容！
🔒8. {'⚠️ 中文语法术语必须100%精确！"同位语从句"不能写成"应语从句"，"宾语从句"不能写成"宝语从句"。如果不确定，用英文标注替代（如 appositive clause）' if is_concept_card else '教学内容不能被卡通角色替代'}

═══════ 📋 最终检查 ═══════
□ 标题包含「{eng_key_phrase}」吗？
{'□ 每个分支的语法术语拼写正确吗？（同位语从句≠应语从句）' if is_concept_card else '□ 区块B有2-3种不同用法+完整例句吗？(不是卡通人物/装饰图案？)'}
□ 英文例句是否作为可见文字渲染在卡面上？
□ ❌/✅例句只涉及「{eng_key_phrase}」吗？有没有混入无关内容？
□ 口诀含具体语法知识吗？不是万能废话吗？
□ 区块C的错因标注是英文吗？（不要写中文句子，防乱码）
□ 卡片中间有没有"记住哦""来看看"等废话？（如果有：删掉，替换为英文例句）

═══════ 📚 参考数据（仅供理解，以上规范优先）═══════

【知识要点】:
{ref_points}
【对错参考】:
{contrast_ref}
{f'【本质原因】: {why_exp}' if why_exp else ''}
{f'【口诀参考】(可改进): {memory_tip}' if memory_tip else ''}
难度: {card.get('difficulty', 3)}/5

⚠️ 视觉风格: {(canvas or _CANVAS_PRESETS['小红书'])['desc_cn']}，鲜明渐变背景，白色圆角卡片区块，标题区用饱和色banner，{(canvas or _CANVAS_PRESETS['小红书'])['breathing']}留白
⚠️ 卡通角色: 可以有一个极小的角色(≤10%面积)在角落装饰，但绝不能占据区块B/C的位置。区块B/C必须是文字教学内容！"""


def _build_card_info_wellness(card, subject, grade, semester):
    """构建养生减脂类卡片信息"""
    card_type = card.get('type', '干货卡')

    example_info = ''
    example_steps = ''
    if card.get('example'):
        ex = card['example']
        example_info = (ex.get('question') or '')[:120]
        if ex.get('steps'):
            steps_text = '\n'.join(f'  {i+1}. {s}' for i, s in enumerate(ex['steps'][:5]))
            example_steps = f"\n【步骤】:\n{steps_text[:500]}"
        if ex.get('answer'):
            example_steps += f"\n【结论】: {str(ex['answer'])[:150]}"

    points = card.get('core_points', [])[:4]
    clean_pts = [str(p)[:80] for p in points]

    mistakes_info = ''
    if card.get('mistakes'):
        m = card['mistakes'][0]
        reason = m.get('reason', '')
        mistakes_info = f"\n常见误区: ❌{m.get('wrong', '')[:100]} → ✅{m.get('correct', '')[:100]}"
        if reason:
            mistakes_info += f"\n错因: {reason[:120]}"

    hook = ''
    if card.get('emotion_hook'):
        hook = f"\n情绪钩子: {card['emotion_hook'][:100]}"

    return f"""主题: {subject} | 分类: {grade} {semester}
标题: {card.get('title', '')} | 类型: {card_type}

【案例】: {example_info or '根据知识点展示最典型场景'}
{example_steps}

【定义】: {card.get('definition', '')[:120]}
【要点】: {chr(10).join('• ' + p for p in clean_pts[:3])}
【口诀】: {card.get('memory_tip', '')[:60]}
{mistakes_info}
{hook}
难度: {card.get('difficulty', 2)}/5"""


def _build_card_info_yuwen(card, subject, grade, semester, canvas=None):
    """v10.6: 构建语文类卡片信息 — 诗词/文言文/修辞/阅读/作文
    
    语文与其他学科不同:
    - 诗词/文言文需要原文展示 + 注释 + 翻译
    - 修辞手法需要典型例句 + 对比分析
    - 中文字形准确度要求极高（易错字/多音字/形近字）
    """
    card_type = card.get('type', '方法卡')
    title = card.get('title', '')
    definition = card.get('definition', '')
    
    # 检测是否为诗词/文言文类
    poetry_keywords = ['古诗', '诗词', '诗句', '名句', '默写', '文言文', '古文',
                        '词牌', '律诗', '绝句', '赋', '词']
    is_poetry = any(k in title + definition + card_type for k in poetry_keywords)
    
    # 检测是否为修辞/阅读/写作技巧类
    rhetoric_keywords = ['修辞', '比喻', '拟人', '夸张', '排比', '对偶',
                          '表达方式', '写作手法', '阅读理解', '作文']
    is_rhetoric = any(k in title + definition + card_type for k in rhetoric_keywords)
    
    example_info = ''
    example_steps = ''
    if card.get('example'):
        ex = card['example']
        if isinstance(ex, str):
            example_info = ex[:200]  # 语文例句允许更长
        else:
            example_info = (ex.get('question') or '')[:200]
            if ex.get('steps'):
                steps_text = '\n'.join(f'  {i+1}. {s}' for i, s in enumerate(ex['steps']))
                example_steps = f"\n【解析步骤】:\n{steps_text[:600]}"
            if ex.get('answer'):
                example_steps += f"\n【参考答案】: {str(ex['answer'])[:200]}"
    
    points = card.get('core_points', [])[:5]
    clean_pts = [str(p)[:100] for p in points]
    
    mistakes_info = ''
    if card.get('mistakes'):
        m = card['mistakes'][0]
        reason = m.get('reason', '')
        mistakes_info = f"\n易错点: ❌{m.get('wrong', '')[:150]} → ✅{m.get('correct', '')[:150]}"
        if reason:
            mistakes_info += f"\n错因: {reason[:150]}"
    
    # 语文专属提示
    subject_hint = ''
    if is_poetry:
        subject_hint = """
⚠️ 语文诗词/文言文卡片要求:
- 原文必须逐字精确，不能有错别字/漏字/多字
- 易错字用特殊颜色标注（红色加粗）
- 注释用小字标注在对应词语旁
- 如有多音字，用注音标注（如 "行háng/xíng"）
- 翻译用现代文，简洁准确"""
    elif is_rhetoric:
        subject_hint = """
⚠️ 语文修辞/写作卡片要求:
- 典型例句完整准确，标注修辞手法名称
- 用颜色区分手法名称（蓝色）和例句（黑色）
- 对比分析用左右栏或上下排列
- 术语名称必须100%精确（如"借代"不能写成"借待"）"""
    
    return f"""学科: 语文 | 年级: {grade}{semester}
标题: {title} | 类型: {card_type}

【典型例句/原文】: {example_info or '选一个最经典的例句或名篇段落'}
{example_steps}

【定义/释义】: {definition[:150]}
【知识要点】: {chr(10).join('• ' + p for p in clean_pts[:4])}
【口诀】(≤8字): {card.get('memory_tip', '')[:40]}
{mistakes_info}
难度: {card.get('difficulty', 3)}/5
{subject_hint}"""


# ── 学科特定提示（注入到通用教育builder中）──
_SUBJECT_EDU_HINTS = {
    '物理': """
⚠️ 物理卡片要求:
- 公式必须完整准确，变量用斜体，单位不用斜体
- 物理量的单位必须标注（如 N, kg, m/s², Pa）
- 力的方向用箭头明确标注
- 电路图符号必须规范（电阻用矩形、电容用平行线）
- 实验图示要标注自变量和因变量""",
    
    '化学': """
⚠️ 化学卡片要求:
- 化学方程式必须配平，箭头方向正确
- 元素符号大小写严格正确（如 Na 不能写成 na 或 NA）
- 化合价标注在元素正上方
- 离子符号的电荷标在右上角（如 Na⁺, Cl⁻）
- 有机物结构简式要准确（键线式/分子式）""",
    
    '生物': """
⚠️ 生物卡片要求:
- 生物学术语必须准确（如"有丝分裂"不能写成"有死分裂"）
- 细胞/组织/器官示意图需标注名称
- 遗传图解用标准符号（P/F1/F2, ♀♂）
- 过程类知识用流程箭头连接各阶段
- 对比类（如动植物细胞）用表格或并排展示""",
    
    '历史': """
⚠️ 历史卡片要求:
- 时间(年代)必须准确，用醒目数字标注
- 人物名字不能有错别字
- 因果关系用箭头链接
- 时间轴类用清晰的年代标注 + 事件简述
- 历史概念用标准教科书表述""",
    
    '地理': """
⚠️ 地理卡片要求:
- 地图类必须标注方向（指北针）和比例尺
- 经纬度数值准确
- 气候类型名称完整准确（如"温带季风气候"）
- 地形/地貌术语不能写错
- 自然地理过程用箭头表示方向和顺序""",
    
    '政治': """
⚠️ 政治卡片要求:
- 政治术语必须使用标准表述（如"人民代表大会制度"不能简化错）
- 理论观点用框架图呈现逻辑关系
- 哲学原理必须准确区分（如唯物/唯心、辩证/形而上学）
- 经济学概念区分清楚（如"财政"vs"货币""通胀"vs"通缩"）
- 引用原文要准确""",
}


# ═══════════════════════════════════════════
# v10.8: 多尺寸画布系统
# ═══════════════════════════════════════════

# 平台 → 默认画布预设
_CANVAS_PRESETS = {
    '小红书': {
        'ratio': '3:4',
        'orientation': 'vertical',
        'desc_cn': '竖屏 3:4 画布',
        'desc_en': 'Canvas ratio 3:4 (vertical)',
        'breathing': '≥ 25%',
    },
    '抖音': {
        'ratio': '9:16',
        'orientation': 'vertical',
        'desc_cn': '竖屏 9:16 画布（全屏沉浸）',
        'desc_en': 'Canvas ratio 9:16 (full-screen vertical, immersive)',
        'breathing': '≥ 20%',
    },
    '微信': {
        'ratio': '1:1',
        'orientation': 'square',
        'desc_cn': '正方形 1:1 画布',
        'desc_en': 'Canvas ratio 1:1 (square)',
        'breathing': '≥ 25%',
    },
    'B站': {
        'ratio': '16:9',
        'orientation': 'horizontal',
        'desc_cn': '横屏 16:9 画布',
        'desc_en': 'Canvas ratio 16:9 (horizontal / landscape)',
        'breathing': '≥ 20%',
    },
    '朋友圈': {
        'ratio': '1:1',
        'orientation': 'square',
        'desc_cn': '正方形 1:1 画布',
        'desc_en': 'Canvas ratio 1:1 (square)',
        'breathing': '≥ 25%',
    },
    '公众号': {
        'ratio': '4:3',
        'orientation': 'horizontal',
        'desc_cn': '横屏 4:3 画布（公众号封面）',
        'desc_en': 'Canvas ratio 4:3 (horizontal, WeChat article cover)',
        'breathing': '≥ 20%',
    },
    '知乎': {
        'ratio': '3:4',
        'orientation': 'vertical',
        'desc_cn': '竖屏 3:4 画布',
        'desc_en': 'Canvas ratio 3:4 (vertical)',
        'breathing': '≥ 25%',
    },
    'PPT': {
        'ratio': '16:9',
        'orientation': 'horizontal',
        'desc_cn': '横屏 16:9 画布（演示文稿）',
        'desc_en': 'Canvas ratio 16:9 (presentation slide)',
        'breathing': '≥ 15%',
    },
}

# 内容类型 → 最优比例覆盖（当不指定平台时，根据内容智能推荐）
_CONTENT_RATIO_MAP = {
    # 对比类 — 左右并排更好看 → 4:3 横屏
    '辨析卡': '4:3', '对战卡': '4:3', '语法辨析卡': '4:3',
    '易混词卡': '4:3', '易混词陷阱卡': '4:3', '暧昧信号卡': '4:3',
    # 流程类 — 纵向更清晰 → 3:4 竖屏
    '方法卡': '3:4', '应用题拆解卡': '3:4', '计算零失误卡': '3:4',
    '情感升温卡': '3:4',
    # 公式突出 — 方形居中 → 1:1
    '公式卡': '1:1',
    # 诗词 — 古卷轴感 → 9:16 长屏
    '古诗默写卡': '9:16', '预言解密卡': '9:16',
    # 概念总结 — 标准竖屏
    '概念卡': '3:4', '思维卡': '3:4', '知识总结卡': '3:4',
    # v10.9: 理科专属比例
    '实验卡': '3:4', '公式推导卡': '1:1', '过程流卡': '9:16',
    '微观图解卡': '3:4', '图像解读卡': '4:3', '模型卡': '3:4',
    '解题策略卡': '3:4', '知识网络卡': '1:1', '术语精准卡': '3:4',
}

# 从比例字符串推断方向
_RATIO_ORIENTATION = {
    '3:4': 'vertical', '9:16': 'vertical', '2:3': 'vertical',
    '1:1': 'square',
    '4:3': 'horizontal', '16:9': 'horizontal', '3:2': 'horizontal',
}


def _resolve_canvas(platform: str = '', card_type: str = '',
                    subject: str = '', ratio_override: str = '') -> dict:
    """v10.8: 智能解析画布参数。

    优先级: ratio_override > platform > content_type > 默认(小红书 3:4)
    
    Returns:
        {ratio, orientation, desc_cn, desc_en, breathing}
    """
    # 1) 用户直接指定比例
    if ratio_override and ratio_override in _RATIO_ORIENTATION:
        orient = _RATIO_ORIENTATION[ratio_override]
        orient_cn = {'vertical': '竖屏', 'horizontal': '横屏', 'square': '正方形'}[orient]
        return {
            'ratio': ratio_override,
            'orientation': orient,
            'desc_cn': f'{orient_cn} {ratio_override} 画布',
            'desc_en': f'Canvas ratio {ratio_override} ({orient})',
            'breathing': '≥ 25%',
        }

    # 2) 平台预设
    if platform and platform in _CANVAS_PRESETS:
        return dict(_CANVAS_PRESETS[platform])

    # 3) 按内容类型推荐（当未指定已知平台时）
    if card_type and card_type in _CONTENT_RATIO_MAP and platform not in _CANVAS_PRESETS:
        ratio = _CONTENT_RATIO_MAP[card_type]
        orient = _RATIO_ORIENTATION.get(ratio, 'vertical')
        orient_cn = {'vertical': '竖屏', 'horizontal': '横屏', 'square': '正方形'}[orient]
        return {
            'ratio': ratio,
            'orientation': orient,
            'desc_cn': f'{orient_cn} {ratio} 画布',
            'desc_en': f'Canvas ratio {ratio} ({orient})',
            'breathing': '≥ 25%',
        }

    # 4) 默认 = 小红书 3:4
    return dict(_CANVAS_PRESETS['小红书'])


def _build_canvas_block_cn(canvas: dict) -> str:
    """生成中文画布 prompt 片段 (用于 PROMPT_SYSTEM_TEMPLATE)"""
    return f"- {canvas['desc_cn']}\n- {canvas['breathing']} 留白"


def _build_canvas_block_en(canvas: dict) -> str:
    """生成英文画布 prompt 片段 (用于 generate_card_image / refinement)"""
    return f"{canvas['desc_en']}. {canvas['breathing']} breathing room."


# ═══════════════════════════════════════════
# v10.7: 学科专属配色系统
# ═══════════════════════════════════════════
_SUBJECT_COLOR_SCHEMES = {
    '数学': {
        'name': '理性蓝',
        'banner_gradient': '深靛蓝渐变 (dark indigo blue gradient)',
        'accent_strip': '天蓝渐变 (sky blue gradient)',
        'content_bg': '极浅蓝底 (very pale blue)',
        'highlight': '金色强调关键数字 (golden yellow for key numbers)',
        'description': '冷静理性的蓝色系，金色强调关键数字，传达数学的精确与严谨',
    },
    '英语': {
        'name': '活力橙',
        'banner_gradient': '深橙渐变 (deep orange gradient)',
        'accent_strip': '暖橙渐变 (warm orange gradient)',
        'content_bg': '极浅橙底 (very pale orange)',
        'highlight': '青色对比词标注 (teal/cyan for contrast words)',
        'description': '活泼明亮的橙色系，青色点缀对比词，传达语言的活力与趣味',
    },
    '语文': {
        'name': '古韵棕',
        'banner_gradient': '深棕渐变 (dark brown gradient)',
        'accent_strip': '暖杏渐变 (warm apricot gradient)',
        'content_bg': '极浅米/宣纸色底 (very pale cream/rice paper)',
        'highlight': '朱砂红强调 (vermilion red for emphasis)',
        'description': '温暖人文的棕色系，朱砂红标注重点，宣纸质感传达中国文化底蕴',
    },
    '物理': {
        'name': '科技银蓝',
        'banner_gradient': '深蓝渐变 (deep blue gradient)',
        'accent_strip': '科技青渐变 (electric cyan gradient)',
        'content_bg': '极浅银灰底 (very pale silver gray)',
        'highlight': '橙色力/能量标注 (orange for force/energy)',
        'description': '深邃科技的蓝色系，亮青色强调实验数据，橙色标注力与能量',
    },
    '化学': {
        'name': '实验紫绿',
        'banner_gradient': '深紫渐变 (deep purple gradient)',
        'accent_strip': '薄荷绿渐变 (mint green gradient)',
        'content_bg': '极浅紫底 (very pale lavender)',
        'highlight': '试剂绿标注 (bright green for elements)',
        'description': '神秘紫色+清新绿色系，模拟化学反应的绚丽，绿色标注元素符号',
    },
    '生物': {
        'name': '生命绿',
        'banner_gradient': '深绿渐变 (deep forest green gradient)',
        'accent_strip': '嫩绿渐变 (fresh light green gradient)',
        'content_bg': '极浅绿底 (very pale green)',
        'highlight': '珊瑚红标注 (coral red for key terms)',
        'description': '自然生命力的绿色系，珊瑚红强调关键术语，传达生机与活力',
    },
    '历史': {
        'name': '复古金棕',
        'banner_gradient': '深咖啡渐变 (dark coffee brown gradient)',
        'accent_strip': '金色渐变 (golden gradient)',
        'content_bg': '极浅羊皮纸色底 (very pale parchment)',
        'highlight': '印章红标注 (stamp red for key dates)',
        'description': '厚重复古的咖啡色系，金色装饰边框，印章红标注关键年代与人物',
    },
    '地理': {
        'name': '地球蓝绿',
        'banner_gradient': '深青绿渐变 (deep teal gradient)',
        'accent_strip': '天蓝渐变 (sky blue gradient)',
        'content_bg': '极浅青底 (very pale cyan)',
        'highlight': '沙漠橙标注 (desert orange for key data)',
        'description': '海洋与大地的蓝绿色系，橙色标注关键地理数据，传达地球的广袤',
    },
    '政治': {
        'name': '庄重红蓝',
        'banner_gradient': '深红渐变 (deep crimson gradient)',
        'accent_strip': '稳重蓝渐变 (steady blue gradient)',
        'content_bg': '极浅红底 (very pale pink)',
        'highlight': '蓝色框架标注 (blue for frameworks)',
        'description': '庄重大气的红色系，蓝色呈现框架与逻辑，传达政治学科的严肃与正式',
    },
    '养生': {
        'name': '养生绿粉',
        'banner_gradient': '深抹茶渐变 (dark matcha green gradient)',
        'accent_strip': '樱花粉渐变 (cherry blossom pink gradient)',
        'content_bg': '极浅绿底 (very pale green)',
        'highlight': '暖杏标注 (warm apricot for key data)',
        'description': '清新自然的抹茶绿，樱花粉口诀条，暖杏色标注关键数据',
    },
    '减脂': {
        'name': '活力粉橙',
        'banner_gradient': '深珊瑚渐变 (deep coral red gradient)',
        'accent_strip': '蜜桃橙渐变 (peach orange gradient)',
        'content_bg': '极浅橙底 (very pale orange)',
        'highlight': '健康绿标注 (healthy green for data)',
        'description': '活力珊瑚红+蜜桃橙，绿色标注健康数据，传达运动的热情与活力',
    },
}

# ═══════════════════════════════════════════
# v10.7: 布局模板多样化
# ═══════════════════════════════════════════
_LAYOUT_VARIANTS = {
    'standard': {
        'name': '标准四区',
        'prompt_block': """请设计以下 4 个结构化区块：

🔹 区块A — 顶部 Banner：
   深色渐变横幅，带柔和光泽
   标题文字白色大字，居中显示

🔹 区块B — 中间内容卡（占据卡片主体）：
   白色或极浅色圆角矩形卡片，带轻微阴影
   卡片内排版教学内容：例题、步骤、对比等
   文字清晰、字号适当、行距舒适

🔹 区块C — 底部口诀条：
   暖色渐变横条，带圆角
   口诀/金句白字居中

🔹 区块D — 最底部窄条：
   极浅背景，小提示文字""",
    },
    'comparison': {
        'name': '左右对比式',
        'prompt_block': """请设计以下结构化区块（对比式布局）：

🔹 区块A — 顶部 Banner：
   深色渐变横幅，标题白色大字居中

🔹 区块B — 对比内容区（占据卡片主体）：
   白色圆角矩形卡片，内部分为左右两栏：
   ┌─────────────┬─────────────┐
   │   左栏 ❌    │   右栏 ✅    │
   │ 红色调浅底色  │ 绿色调浅底色  │
   │ 错误/旧方法   │ 正确/新方法   │
   └─────────────┴─────────────┘
   中间用虚线或VS图标分隔
   左栏淡红色底 = 错误/旧方法
   右栏淡绿色底 = 正确/新方法
   对比项目一一对齐，形成强烈视觉反差

🔹 区块C — 底部口诀条：
   暖色渐变横条，口诀白字居中

🔹 区块D — 最底部窄条：
   极浅背景，小提示文字""",
    },
    'flow': {
        'name': '步骤流程式',
        'prompt_block': """请设计以下结构化区块（流程式布局）：

🔹 区块A — 顶部 Banner：
   深色渐变横幅，标题白色大字居中

🔹 区块B — 步骤流程区（占据卡片主体）：
   白色圆角矩形卡片，内部用编号色块+箭头展示步骤：
   ① → ② → ③ → ④ 从上到下排列
   每步用不同颜色的圆角色块（浅蓝→浅绿→浅橙→浅粉递进）
   步骤之间用大号 → 箭头连接，形成清晰视觉流
   最后一步（答案/结论）用加粗+大号+⭐标记突出
   若有错误步骤，用红色虚线框+❌标记

🔹 区块C — 底部口诀条：
   暖色渐变横条，口诀白字居中

🔹 区块D — 最底部窄条：
   极浅背景，小提示文字""",
    },
    'concept_map': {
        'name': '思维导图式',
        'prompt_block': """请设计以下结构化区块（思维导图式布局）：

🔹 区块A — 顶部 Banner：
   深色渐变横幅，标题白色大字居中

🔹 区块B — 思维导图区：
   白色圆角矩形卡片，内部用思维导图/放射状布局：
   中心：核心概念 — 大圆角矩形（主色填充+白字）
   辐射：3-4 个分支，每个分支用不同浅色圆角矩形
   分支用细线/箭头连接到中心
   每个分支内 1-2 行精炼文字
   最重要的分支用加粗边框+⭐标记
   整体呈放射状/树状分布，层次清晰

🔹 区块C — 底部口诀条：
   暖色渐变横条，口诀白字居中

🔹 区块D — 最底部：
   极浅背景，小提示文字""",
    },
    'formula_hero': {
        'name': '公式突出式',
        'prompt_block': """请设计以下结构化区块（公式突出式布局）：

🔹 区块A — 顶部 Banner：
   深色渐变横幅，标题白色大字居中

🔹 区块B — 公式展示区：
   白色圆角矩形卡片，内部分为上下两部分：
   上半部分：核心公式/定理超大展示
     - 公式字号是正文的 2-3 倍
     - 公式用浅色圆角色块背景托底
     - 变量用主色标注，常数用黑色
   下半部分：代入实例验证
     - "例" 标签 + 具体数字代入
     - 关键步骤用色块高亮
     - 推导箭头连接各步骤

🔹 区块C — 底部口诀条：
   暖色渐变横条，口诀白字居中

🔹 区块D — 最底部：
   极浅背景，小提示文字""",
    },
    'poetry': {
        'name': '诗意水墨式',
        'prompt_block': """请设计以下结构化区块（诗意水墨式布局）：

🔹 区块A — 顶部 Banner：
   深棕/墨色渐变横幅，书法风标题白色大字居中

🔹 区块B — 诗词内容区：
   宣纸质感背景（极浅米/淡黄色）
   诗词原文用大号书法风字体居中排列
   每句独占一行，字间距宽松典雅
   重点字/易错字用朱红色标注
   意境装饰：角落淡墨山水/竹叶/梅花等中国风元素（≤15%面积）
   译文/赏析用小号字体排列在诗词下方

🔹 区块C — 底部口诀条：
   暖杏/朱砂渐变横条，口诀白字居中

🔹 区块D — 最底部：
   极浅背景，小提示文字""",
    },
    # v10.9: 理科专属布局变体
    'experiment': {
        'name': '实验流程式',
        'prompt_block': """请设计以下结构化区块（实验流程式布局）：

🔹 区块A — 顶部 Banner：
   深蓝/深绿渐变横幅，🧪图标+实验名称白色大字居中

🔹 区块B — 目的与器材区：
   白色圆角卡片，左侧实验目的(1句话)，右侧主要器材图标化展示
   器材用简化图标+名称标注

🔹 区块C — 步骤流程区：
   白色圆角卡片内，编号色块步骤从上到下：
   ①浅蓝 → ②浅绿 → ③浅橙 → ④浅粉
   每步用圆角色块，步骤之间大号→箭头连接
   对照实验用虚线框标注对照组
   关键操作用⚠️图标标注

🔹 区块D — 现象与结论区：
   左侧：观察到的现象（用色彩描述词："变蓝""冒泡""沉淀"等）
   右侧：结论大字+核心方程式

🔹 区块E — 底部安全条：
   淡红色渐变横条，⚠️安全注意事项1-2条白字""",
    },
    'derivation': {
        'name': '公式推导式',
        'prompt_block': """请设计以下结构化区块（公式推导式布局）：

🔹 区块A — 顶部 Banner：
   深紫/深蓝渐变横幅，公式名称白色大字居中

🔹 区块B — 已知条件区：
   浅蓝色圆角卡片：列出推导的出发点/基本定律/已知关系
   用公式色块展示，变量用主色标注

🔹 区块C — 推导过程区：
   白色卡片内，逐步推导从上到下：
   Step1 → Step2 → Step3 递进色块（浅→深渐变）
   每步右侧标注该步的物理/化学意义（斜体灰色小字）
   步骤之间用 ⇓ 大箭头连接
   关键变换步骤用黄色高亮背景

🔹 区块D — 最终公式区：
   大面积主色圆角色块，公式字号是正文2-3倍
   各符号注释在公式下方（符号=含义 排列）

🔹 区块E — 适用条件条：
   淡橙色渐变横条，⚠️适用前提+常见误用场景白字""",
    },
    'microscopic': {
        'name': '微观图解式',
        'prompt_block': """请设计以下结构化区块（微观图解式布局）：

🔹 区块A — 顶部 Banner：
   深色科技感渐变横幅，标题白色大字居中

🔹 区块B — 宏观现象区：
   白色圆角卡片，展示宏观可观察的现象
   用实物/场景图+现象描述文字
   标注"你看到的👁"

🔹 区块C — 微观图解区：
   浅灰/浅蓝科技感背景圆角卡片
   放大镜视觉效果：从宏观→微观的过渡
   粒子用不同颜色+大小的圆圈表示：
   - 大红圆=A原子，小蓝圆=B原子
   - 箭头=运动/转移方向
   - 电子用更小的紫色点表示
   粒子数量≤15个，保持清晰
   标注"微观本质🔬"

🔹 区块D — 本质总结区：
   暖色渐变条，一句话揭示宏观→微观因果

🔹 区块E — 底部口诀：
   极浅背景，记忆口诀小字""",
    },
    'graph_analysis': {
        'name': '图像解读式',
        'prompt_block': """请设计以下结构化区块（图像解读式布局 — 横屏4:3）：

🔹 区块A — 顶部 Banner：
   深色渐变横幅，图像类型名称白色大字居中

🔹 区块B — 示例图像区：
   白色卡片内，一张典型坐标图/曲线图：
   - 横轴+纵轴标注物理量名称和单位
   - 曲线用主色粗线绘制
   - 关键点(截距/拐点/交点)用红色圆点标注
   - 特殊区域用浅色阴影填充

🔹 区块C — 读图方法区：
   三色步骤条横排：
   ①蓝色"看轴" → ②绿色"看点" → ③橙色"看趋势"
   每步下方2-3行要点注释

🔹 区块D — 考法/易错区：
   左侧：标签色块列出常考题型（2-3种）
   右侧：⚠️易错点红色小字""",
    },
    'model': {
        'name': '科学模型式',
        'prompt_block': """请设计以下结构化区块（科学模型式布局）：

🔹 区块A — 顶部 Banner：
   深灰/深蓝渐变横幅，模型名称白色大字居中

🔹 区块B — 模型示意图区：
   白色圆角卡片内，模型的核心简化示意图：
   - 用圆形/矩形/箭头等几何元素构建模型
   - 关键假设用标注气泡指出
   - 不同部分用不同颜色区分
   - 保持简洁，避免过于复杂的3D效果

🔹 区块C — 适用与局限区：
   白色卡片内分左右两栏：
   ┌─────────────┬─────────────┐
   │  ✅ 能解释    │  ❌ 不能解释  │
   │ 绿色调浅底色  │ 红色调浅底色  │
   └─────────────┴─────────────┘
   每栏列出2-3条

🔹 区块D — 底部核心思想：
   暖色渐变条，模型核心思想一句话白字居中""",
    },
    'precise_wording': {
        'name': '术语精准式',
        'prompt_block': """请设计以下结构化区块（术语精准式布局）：

🔹 区块A — 顶部 Banner：
   深色渐变横幅，"⚠️ 高考踩分用词"白色大字居中

🔹 区块B — 对比区：
   白色圆角卡片内，逐条对比：
   ┌──────────────────────────────┐
   │ ❌ 错误表述（红色底）           │
   │ ✅ 精准表述（绿色底）           │
   │ 💡 差在哪里（灰色小字）         │
   ├──────────────────────────────┤
   │ ❌ ...                        │
   │ ✅ ...                        │
   │ 💡 ...                        │
   └──────────────────────────────┘
   每组❌/✅/💡 三行，最多4组

🔹 区块C — 记忆技巧：
   暖色圆角色块，精准用词的记忆口诀/技巧

🔹 区块D — 底部提示：
   极浅背景，"每个字都是踩分点"提示小字""",
    },
}

# 卡片类型 → 推荐布局
_CARD_TYPE_LAYOUT_MAP = {
    # 对比式
    '辨析卡': 'comparison', '速算卡': 'comparison', '对战卡': 'comparison',
    '语法辨析卡': 'comparison', '易混词卡': 'comparison', '易混词陷阱卡': 'comparison',
    '语法纠错卡': 'comparison', '句式变换卡': 'comparison', '判断火眼卡': 'comparison',
    '暧昧信号卡': 'comparison', '避雷指南卡': 'comparison',
    '陷阱卡': 'comparison',  # v10.11: 陷阱卡核心是❌vs✅对比
    # 流程式
    '方法卡': 'flow', '应用题拆解卡': 'flow', '计算零失误卡': 'flow',
    '操作题规范卡': 'flow', '情感升温卡': 'flow',
    # 思维导图式
    '概念卡': 'concept_map', '思维卡': 'concept_map', '知识总结卡': 'concept_map',
    # 公式突出式
    '公式卡': 'formula_hero',
    # 诗意水墨式 (仅语文)
    '古诗默写卡': 'poetry', '预言解密卡': 'poetry',
    # v10.9: 理科专属布局
    '实验卡': 'experiment', '公式推导卡': 'derivation',
    '过程流卡': 'flow', '微观图解卡': 'microscopic',
    '图像解读卡': 'graph_analysis', '模型卡': 'model',
    '解题策略卡': 'flow', '知识网络卡': 'concept_map',
    '术语精准卡': 'precise_wording',
}


def _get_subject_color_scheme(subject):
    """获取学科专属配色方案（v10.7）"""
    if subject in _SUBJECT_COLOR_SCHEMES:
        return _SUBJECT_COLOR_SCHEMES[subject]
    # 模糊匹配
    for k, v in _SUBJECT_COLOR_SCHEMES.items():
        if k in subject or subject in k:
            return v
    return None


def _build_color_scheme_block(subject):
    """构建配色 prompt 区块（v10.7）"""
    cs = _get_subject_color_scheme(subject)
    if cs:
        return f"""══════ 配色 — {cs['name']}（{subject}专属） ══════

{cs['description']}
 Banner 区块: {cs['banner_gradient']}
 内容卡: {cs['content_bg']}，带轻微阴影
 口诀条: {cs['accent_strip']}
 强调色（标注重点）: {cs['highlight']}
 背景: 内容卡底色的更浅版本，有微妙渐变过渡

⚠️ 以上配色仅供你选色参考，不要把颜色名称或色值渲染到卡片图片上！"""
    return """══════ 配色 ══════

主色选一: 珊瑚粉 / 薄荷蓝 / 蜜桃橙 / 薰衣草紫
 Banner 区块: 该主色的深色渐变版本
 内容卡: 纯白或极浅色，带轻微阴影
 口诀条: 该主色的暖亮渐变版本
 背景: 该主色的极浅淡版本，有微妙渐变过渡

⚠️ 以上配色仅供你选色参考，不要把颜色名称或色值渲染到卡片图片上！"""


def _get_layout_variant(card_type, subject):
    """根据卡片类型和学科选择最合适的布局变体（v10.7）"""
    layout_key = _CARD_TYPE_LAYOUT_MAP.get(card_type, 'standard')
    # 语文古诗/文言文类型使用诗意布局
    if subject == '语文' and card_type in ('古诗默写卡', '预言解密卡'):
        layout_key = 'poetry'
    return _LAYOUT_VARIANTS.get(layout_key, _LAYOUT_VARIANTS['standard'])


def _build_layout_block(card_type, subject):
    """构建布局 prompt 区块（v10.7）"""
    layout = _get_layout_variant(card_type, subject)
    return layout['prompt_block']


def _build_color_scheme_for_v2(subject):
    """为 v2 视觉翻译模板构建英文配色提示（v10.7）"""
    cs = _get_subject_color_scheme(subject)
    if not cs:
        return ''
    return (f"- Subject color scheme: {cs['name']} — {cs['description']}\n"
            f"- Banner: {cs['banner_gradient']}\n"
            f"- Accent strip: {cs['accent_strip']}\n"
            f"- Content background: {cs['content_bg']}\n"
            f"- Highlight color: {cs['highlight']}\n")


def _build_layout_hint_for_v2(card_type, subject):
    """为 v2 视觉翻译模板构建英文布局提示（v10.7）"""
    layout = _get_layout_variant(card_type, subject)
    if layout['name'] == '标准四区':
        return ''  # 标准布局不需要额外提示
    return f"- Layout variant: {layout['name']} — use this layout structure instead of standard 4-zone\n"


def _build_card_info_edu(card, subject, grade, semester):
    """构建教育类卡片信息（v10.6: 支持全学科专属提示 / v10.11: 动态文字量降级）"""
    card_type = card.get('type', '方法卡')

    # ── v10.11: 动态文字量降级 ──
    total_chars, bd = _estimate_card_text_volume(card)
    is_overloaded = total_chars > _MAX_CARD_CHARS
    # 根据超标程度决定降级力度
    if is_overloaded:
        ratio = total_chars / _MAX_CARD_CHARS  # >1.0 表示超标
        # 动态调整各字段上限
        def_limit = 60 if ratio < 1.5 else 40
        pt_limit = _MAX_CORE_POINT_CHARS if ratio < 1.5 else 15
        pt_count = _MAX_CORE_POINTS if ratio < 2.0 else 2
        step_limit = _MAX_EXAMPLE_STEPS if ratio < 1.5 else 2
        tip_limit = _MAX_MEMORY_TIP_CHARS if ratio < 1.5 else 10
        mistake_limit = 80 if ratio < 1.5 else 60  # v10.12: 纠错是教学核心，保留更多
    else:
        def_limit = 120
        pt_limit = 80
        pt_count = 4
        step_limit = 5
        tip_limit = 40
        mistake_limit = 150

    example_info = ''
    example_steps = ''
    if card.get('example'):
        ex = card['example']
        if isinstance(ex, str):
            example_info = ex[:80]
        else:
            example_info = (ex.get('question') or '')[:80]
            if ex.get('steps'):
                steps = ex['steps'][:step_limit]
                import re as _re_step
                def _clean_step(s, idx):
                    s = str(s).strip()
                    # 去掉已有的编号前缀 (1. / ①等)
                    s = _re_step.sub(r'^(?:\d+[.\s、）)]\s*|[①②③④⑤⑥⑦⑧]\s*)', '', s)
                    return f'  {idx+1}. {s[:40]}'
                steps_text = '\n'.join(_clean_step(s, i) for i, s in enumerate(steps))
                example_steps = f"\n【解题步骤】:\n{steps_text}"
            if ex.get('answer'):
                example_steps += f"\n【正确答案】: {ex['answer'][:60]}"

    points = card.get('core_points', [])[:pt_count]
    formulas = [p[:pt_limit] for p in points if any(c in p for c in '=÷×+−≥≤<>°²³∠')]
    clean_pts = [p[:pt_limit] for p in points if not any(c in p for c in '=÷×+−≥≤<>°²³∠')]

    mistakes_info = ''
    if card.get('mistakes'):
        m = card['mistakes'][0]
        reason = m.get('reason', '')
        mistakes_info = f"\n常见错误: ❌{m.get('wrong', '')[:mistake_limit]} → ✅{m.get('correct', '')[:mistake_limit]}"
        if reason:
            mistakes_info += f"\n错因: {reason[:60]}"

    why_exp = ''
    if card.get('why_explanation'):
        why_exp = f"\n本质原因: {card['why_explanation'][:80]}"

    is_vert = _detect_vertical_calc(card)
    
    # v10.6: 学科专属提示注入
    subject_hint = _SUBJECT_EDU_HINTS.get(subject, '')
    
    # v10.11: 文字量警告（提示AI尽量用图不用字）
    text_budget_hint = ''
    if is_overloaded:
        text_budget_hint = f'\n⚠️ 文字量偏多({total_chars}字)！请尽量用图标/示意图/箭头表达，减少文字渲染。核心文字≤{_MAX_CARD_CHARS}字。'

    return f"""学科: {subject} | 年级: {grade}{semester}
标题: {card.get('title', '')} | 类型: {card_type}

【例题】: {example_info or '根据知识点构造一道最典型例题'}
{example_steps}

【定义】: {card.get('definition', '')[:def_limit]}
【要点】: {chr(10).join('• ' + p for p in clean_pts[:_MAX_CORE_POINTS])}
{('【公式】: ' + ' | '.join(formulas)) if formulas else ''}
【口诀】(≤8字): {card.get('memory_tip', '')[:tip_limit]}
{why_exp}
{mistakes_info}
难度: {card.get('difficulty', 3)}/5
{'⚠️ 笔算竖式类：必须画正确竖式' if is_vert else ''}
{subject_hint}{text_budget_hint}"""


def generate_image_prompt_v2(card, subject, grade, semester, api_key, all_keys=None,
                              platform='', ratio_override=''):
    """Step 1 (v2 两阶段): 内容决策 → 视觉翻译 → TEXT_MANIFEST
    
    Phase 1a: Gemini 生成结构化内容 JSON (教学内容决策)
    Phase 1b: Gemini 把内容 JSON 翻译成英文图片 prompt
    
    优势: 每步 prompt 短 → 信号密度高 → 遵循率高
    
    v10.8: platform / ratio_override 控制画布比例。
    """
    card_type = card.get('type', '方法卡')
    eff = _get_effective_params()
    # v10.17: 减少AI渲染中文量, 50字以内准确率最高; 重文字类型允许70字
    _HEAVY_TEXT_TYPES = ('实验卡', '实验', '对比卡', '辨析卡', '比较卡')
    is_heavy = card_type in _HEAVY_TEXT_TYPES
    max_chars = 70 if is_heavy else 50

    # ── Phase 1a: 内容决策 ──
    prompt_1a = build_content_decision_prompt(
        card, card_type, subject, grade, semester, max_chars=max_chars
    )
    print(f'      [v2] Phase 1a: 内容决策 ({len(prompt_1a)}字)')
    
    contents_1a = [{'role': 'user', 'parts': [{'text': prompt_1a}]}]
    gen_config_1a = {
        'maxOutputTokens': 4096,
        'temperature': 0.5,
        'thinkingConfig': {'thinkingBudget': 1024}
    }
    
    resp_1a = gemini_call(TEXT_MODEL, contents_1a, api_key,
                          gen_config=gen_config_1a, all_keys=all_keys)
    if not resp_1a:
        print('      [v2] Phase 1a 失败, 降级到 v1')
        return generate_image_prompt(card, subject, grade, semester, api_key, all_keys, platform=platform, ratio_override=ratio_override)
    
    # 解析 1a 输出
    try:
        parts_1a = resp_1a.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        text_1a = ''
        for part in parts_1a:
            if 'text' in part and not part.get('thought', False):
                t = part['text'].strip()
                if len(t) > len(text_1a):
                    text_1a = t
        
        content_decision = parse_content_decision(text_1a)
        if not content_decision:
            print('      [v2] Phase 1a JSON 解析失败, 降级到 v1')
            return generate_image_prompt(card, subject, grade, semester, api_key, all_keys, platform=platform, ratio_override=ratio_override)
        
        print(f'      [v2] Phase 1a ✓ — blocks={len(content_decision.get("blocks", []))}, '
              f'cn={content_decision.get("total_chinese_chars", "?")}字')
    except Exception as e:
        print(f'      [v2] Phase 1a 解析失败 ({e}), 降级到 v1')
        return generate_image_prompt(card, subject, grade, semester, api_key, all_keys, platform=platform, ratio_override=ratio_override)

    # ── Phase 1b: 视觉翻译 ──
    # v10.7: 注入学科配色 + 布局提示
    color_hint_v2 = _build_color_scheme_for_v2(subject)
    layout_hint_v2 = _build_layout_hint_for_v2(card_type, subject)
    # v10.8: 画布尺寸
    canvas = _resolve_canvas(platform=platform, card_type=card_type,
                             subject=subject, ratio_override=ratio_override)
    canvas_line_v2 = f"{canvas['desc_en']}\n- {canvas['breathing']} whitespace"
    prompt_1b = build_visual_translation_prompt(
        content_decision, card_type, subject,
        extra_color_hint=color_hint_v2,
        extra_layout_hint=layout_hint_v2,
        canvas_line=canvas_line_v2,
        grade=grade,
    )
    
    # 注入反向学习反馈
    if _HAS_SKILL_FEEDBACK:
        try:
            feedback_hint = build_feedback_prompt_hint(card_type)
            if feedback_hint:
                prompt_1b += f'\n{feedback_hint}'
        except Exception:
            pass
    
    print(f'      [v2] Phase 1b: 视觉翻译 ({len(prompt_1b)}字)')
    
    contents_1b = [{'role': 'user', 'parts': [{'text': prompt_1b}]}]
    gen_config_1b = {
        'maxOutputTokens': 4096,
        'temperature': 0.6,
        'thinkingConfig': {'thinkingBudget': 1024}
    }
    
    resp_1b = gemini_call(TEXT_MODEL, contents_1b, api_key,
                          gen_config=gen_config_1b, all_keys=all_keys)
    if not resp_1b:
        print('      [v2] Phase 1b 失败, 降级到 v1')
        return generate_image_prompt(card, subject, grade, semester, api_key, all_keys, platform=platform, ratio_override=ratio_override)
    
    try:
        parts_1b = resp_1b.get('candidates', [{}])[0].get('content', {}).get('parts', [])
        text_1b = ''
        for part in parts_1b:
            if 'text' in part and not part.get('thought', False):
                t = part['text'].strip()
                if len(t) > len(text_1b):
                    text_1b = t
        
        if len(text_1b) < 50:
            print('      [v2] Phase 1b 输出太短, 降级到 v1')
            return generate_image_prompt(card, subject, grade, semester, api_key, all_keys, platform=platform, ratio_override=ratio_override)
        
        # 解析 manifest — 优先从 1b 输出提取，降级到 1a 的 text_manifest
        manifest = _parse_text_manifest(text_1b)
        if not manifest and content_decision.get('text_manifest'):
            manifest = content_decision['text_manifest']
        
        # 英语卡标题优化 + 语法术语保护
        manifest = _fix_english_card_title_manifest(manifest, card, subject)
        manifest = _inject_grammar_terms_to_manifest(manifest, card, subject)
        
        # 清理 prompt
        prompt_clean = re.sub(r'\[TEXT_MANIFEST\].*?\[/TEXT_MANIFEST\]', '', text_1b, flags=re.DOTALL).strip()
        
        # 字数守门员 (v10.16: 传入card_type让实验卡等获得更高字数上限)
        manifest = _enforce_manifest_limits(manifest, card_type=card_type)
        
        # Skill 审计
        if _HAS_SKILL_SCHEMA:
            try:
                prompt_clean, audit_result = audit_and_patch(
                    prompt_clean, card_type, card, manifest, grade
                )
                summary = format_audit_summary(audit_result)
                print(f'      [v2] {summary}')
            except Exception as e:
                print(f'      [v2] [skill audit] error: {e}')
        
        print(f'      [v2] Phase 1b ✓ — prompt={len(prompt_clean)}字, manifest={len(manifest)}项')
        return prompt_clean, manifest
    
    except Exception as e:
        print(f'      [v2] Phase 1b 解析失败 ({e}), 降级到 v1')
        return generate_image_prompt(card, subject, grade, semester, api_key, all_keys, platform=platform, ratio_override=ratio_override)


def generate_image_prompt(card, subject, grade, semester, api_key, all_keys=None,
                          platform='', ratio_override=''):
    """Step 1: 生成英文图片提示词 + TEXT_MANIFEST
    
    v10.8: platform / ratio_override 控制画布比例。
    """
    card_type = card.get('type', '方法卡')
    # 优先使用结构化 Skill Schema 的视觉策略，降级到原始字符串规则
    if _HAS_SKILL_SCHEMA:
        type_rules = get_visual_strategy(card_type, card, grade) or CARD_TYPE_VISUAL_RULES.get(card_type, CARD_TYPE_VISUAL_RULES['方法卡'])
    else:
        type_rules = CARD_TYPE_VISUAL_RULES.get(card_type, CARD_TYPE_VISUAL_RULES['方法卡'])
    is_vert = _detect_vertical_calc(card)

    # ── 获取自适应字数参数 ──
    eff = _get_effective_params()
    max_chars = eff.get('max_chinese_chars', 20)
    max_per_block = eff.get('max_chars_per_block', 5)
    ideal_chars = max(8, max_chars - 5)
    max_slogan = min(max_per_block + 2, 8)
    char_fmt = dict(max_chars=max_chars, max_per_block=max_per_block,
                    ideal_chars=ideal_chars, max_slogan=max_slogan)

    # ── v10.7: 学科配色 + 布局多样化 ──
    color_scheme_block = _build_color_scheme_block(subject)
    layout_variant_block = _build_layout_block(card_type, subject)

    # ── v10.8: 画布尺寸 ──
    canvas = _resolve_canvas(platform=platform, card_type=card_type,
                             subject=subject, ratio_override=ratio_override)
    canvas_block = _build_canvas_block_cn(canvas)

    # 根据学科选择对应模板
    if subject in _WELLNESS_SUBJECTS:
        visual_block = f"   {type_rules}"
        system_prompt = PROMPT_SYSTEM_TEMPLATE_WELLNESS.format(
            subject=subject,
            visual_strategy_block=visual_block,
            color_scheme_block=color_scheme_block,
            layout_variant_block=layout_variant_block,
            canvas_block=canvas_block,
            **char_fmt
        )
    elif is_vert:
        solve_block = """   ⚠️ 笔算竖式类：必须画彩色分层竖式！
   - 竖式用颜色分层(绿/橙/红)，旁边放正误对比
   - 数字必须和例题完全一致"""
        system_prompt = PROMPT_SYSTEM_TEMPLATE.format(
            subject=subject,
            solve_strategy_block=solve_block,
            color_scheme_block=color_scheme_block,
            layout_variant_block=layout_variant_block,
            canvas_block=canvas_block,
            **char_fmt
        )
    else:
        solve_block = f"   {type_rules}"
        # v10.15: 概念类卡片图文融合 — 覆写核心教学思路 (扩大到术语精准卡/模型卡等)
        if card_type in _CONCEPT_LIKE_TYPES:
            # 方向2: 查询精确图形模板
            graph_hint = _lookup_concept_graph_template(card, subject)
            solve_block += f"""
   ⚠️ 概念类卡片图文融合核心原则：
   - 卡片画面60%必须是教学示意图（简笔画/力学图/模型图），不是装饰！
   - 示意图上用箭头+短标注(≤4字)指出概念关键要素
   - 文字只作为图形的标注和补充，禁止出现独立文字段落
   - 读者看图就能理解概念核心，文字只是辅助
   🎯 本卡推荐图形: {graph_hint}"""
        # v10.15: 公式卡/陷阱卡/方法卡 也加图文融合提示
        if card_type == '公式卡':
            solve_block += """
   ⚠️ 公式卡图文融合: 用图形(面积模型/实验场景)推导公式，不要只列公式！
   读者看图就能理解"为什么是这个公式"。"""
        elif card_type == '陷阱卡':
            solve_block += """
   ⚠️ 陷阱卡图文融合: 用对比图(❌vs✅)直观展示错误和正确的区别！
   读者看图就能瞬间理解差异点。"""
        elif card_type == '方法卡' and not is_vert:
            solve_block += """
   ⚠️ 方法卡图文融合: 用步骤流程图(编号色块)展示方法，不要只写文字步骤！"""

        # v10.19: 英语句型卡专用视觉策略 — 场景图+位置图解
        if subject == '英语' and card_type == '句型卡':
            solve_block += """
   ⚠️ 英语句型卡图文融合（最重要！）：
   - 卡片40%面积必须是对话场景简笔画（如两个人物问答 Where is the book?）
   - 用简笔图解展示介词含义（物品 on/in/under 桌子的位置关系图），不要只写文字！
   - 问答用箭头气泡展示：A→"Where is...?" B→"It's on/in/under the..."
   - ❌/✅对比区只需1组：错误（不完整句）vs 正确（完整句），不要纯文字列表
   - 🚫严禁纯文字排版！图解是教学核心，文字是辅助标注
   - 🚫严禁把教材内容原封不动搬上卡片"""

        system_prompt = PROMPT_SYSTEM_TEMPLATE.format(
            subject=subject,
            solve_strategy_block=solve_block,
            color_scheme_block=color_scheme_block,
            layout_variant_block=layout_variant_block,
            canvas_block=canvas_block,
            **char_fmt
        )

    card_info = _build_card_info(card, subject, grade, semester, canvas=canvas)

    # ── 自我优化: 注入 few-shot 高分 prompt 参考 ──
    fewshot_block = ''
    if _HAS_OPTIMIZER:
        try:
            fewshot_block = build_fewshot_hint(subject, card_type)
        except Exception as e:
            print(f'      [optimizer] few-shot hint error: {e}')

    # ── 内容质量: 注入风格指南 + 内容改进提示 ──
    quality_hint = ''
    if _HAS_QUALITY:
        try:
            from content_quality import get_style_guide
            guide_data = get_style_guide(card_type, subject)
            if guide_data.get('guide') and guide_data.get('based_on', 0) >= 3:
                quality_hint += f'\n=== STYLE GUIDE (data-driven) ===\n{guide_data["guide"][:500]}\n=== END ===\n'
        except Exception as e:
            print(f'      [quality] style guide hint error: {e}')

    # ── 内容设计引擎: 教学策略 + 认知负荷 ──
    design_hint = ''
    if _HAS_DESIGN:
        try:
            design = design_card_content(card, card_type, subject, grade)
            design_hint = design.get('design_prompt_injection', '')
            if design.get('warnings'):
                print(f'      [design] 警告: {design["warnings"][0][:60]}')
        except Exception as e:
            print(f'      [design] hint error: {e}')

    # ── 知识呈现蓝图: 视觉布局 + 记忆策略 ──
    blueprint_hint = ''
    if _HAS_BLUEPRINT:
        try:
            bp = generate_visual_blueprint(card, card_type, subject, grade)
            blueprint_hint = bp.get('blueprint_prompt', '')
        except Exception as e:
            print(f'      [blueprint] hint error: {e}')

    # ── 教学效果: 注入教学改进提示 ──
    pedagogy_hint = ''
    if _HAS_PEDAGOGY:
        try:
            ped = full_pedagogical_audit(card, card_type, subject, grade)
            pedagogy_hint = ped.get('prompt_injection', '')
        except Exception as e:
            print(f'      [pedagogy] hint error: {e}')

    full_input = f'{system_prompt}\n\n--- 知识点信息 ---\n{card_info}'

    # ── Skill 结构化注入: 骨架+填充 双阶段 ──
    skill_hint = ''
    if _HAS_SKILL_SCHEMA:
        try:
            skill_hint = build_skill_enhanced_prompt(card_type, card, subject, grade, semester)
            if skill_hint:
                print(f'      [skill] 注入 Skill 骨架+填充 ({len(skill_hint)}字)')
        except Exception as e:
            print(f'      [skill] hint error: {e}')

    if skill_hint:
        full_input += f'\n{skill_hint}'
    if fewshot_block:
        full_input += f'\n\n{fewshot_block}'
    if quality_hint:
        full_input += f'\n{quality_hint}'
    if design_hint:
        full_input += f'\n{design_hint}'
    if blueprint_hint:
        full_input += f'\n{blueprint_hint}'
    if pedagogy_hint:
        full_input += f'\n{pedagogy_hint}'

    # ── Skill 反向学习: 注入历史数据驱动的反馈提示 ──
    if _HAS_SKILL_FEEDBACK:
        try:
            feedback_hint = build_feedback_prompt_hint(card_type)
            if feedback_hint:
                full_input += f'\n{feedback_hint}'
                print(f'      [feedback] 注入反馈提示 ({len(feedback_hint)}字)')
        except Exception as e:
            print(f'      [feedback] hint error: {e}')

    # ── 深层复审沉淀: 注入历史审查发现的内容问题警告 ──
    card_id = card.get('full_id') or card.get('card_id', '')
    review_hint = build_content_review_hint(subject, card_id)
    if review_hint:
        full_input += f'\n{review_hint}'
        print(f'      [content_review] 注入审查警告 ({len(review_hint)}字)')

    contents = [
        {'role': 'user', 'parts': [{'text': full_input}]}
    ]
    gen_config = {
        'maxOutputTokens': 8192,
        'temperature': 0.8,
        'thinkingConfig': {'thinkingBudget': 2048}
    }

    resp = gemini_call(TEXT_MODEL, contents, api_key, gen_config=gen_config, all_keys=all_keys)
    if not resp:
        return None, None

    try:
        candidates = resp.get('candidates', [])
        if not candidates:
            return None, None
        parts = candidates[0].get('content', {}).get('parts', [])
        best_text = ''
        for part in parts:
            if 'text' in part and not part.get('thought', False):
                txt = part['text'].strip()
                if len(txt) > len(best_text):
                    best_text = txt
        if not best_text:
            for part in parts:
                if 'text' in part:
                    txt = part['text'].strip()
                    if len(txt) > len(best_text):
                        best_text = txt

        if len(best_text) < 50:
            return None, None

        # 解析 TEXT_MANIFEST
        manifest = _parse_text_manifest(best_text)
        # 英语卡标题优化: 自动注入英文关键词
        manifest = _fix_english_card_title_manifest(manifest, card, subject)
        # 语法术语保护: 将卡片中的语法术语加入manifest，方便OCR精确审计
        manifest = _inject_grammar_terms_to_manifest(manifest, card, subject)
        # 清理 prompt（移除 manifest 标签）
        prompt_clean = re.sub(r'\[TEXT_MANIFEST\].*?\[/TEXT_MANIFEST\]', '', best_text, flags=re.DOTALL).strip()

        # ── 文字量守门员: 检查manifest总汉字数 (v10.16: card_type感知) ──
        manifest = _enforce_manifest_limits(manifest, card_type=card_type)

        # ── v10.19.1: 防重复守门员: TITLE 和 LINE1 不能重复 ──
        manifest = _dedup_title_line1(manifest, subject=subject)

        # ── Prompt 结构审计: 检查是否覆盖 Skill 规则要求 ──
        if _HAS_SKILL_SCHEMA:
            try:
                prompt_clean, audit_result = audit_and_patch(
                    prompt_clean, card_type, card, manifest, grade
                )
                summary = format_audit_summary(audit_result)
                print(f'      {summary}')
                if audit_result.verdict == 'fail':
                    print(f'      ⚠️ [skill audit] 覆盖率过低，已自动补丁')
            except Exception as e:
                print(f'      [skill audit] error: {e}')

        return prompt_clean, manifest

    except Exception as e:
        print(f'      [Parse error] {e}')
    return None, None


def _parse_text_manifest(text):
    """从 prompt 输出中解析 TEXT_MANIFEST"""
    manifest = {}
    m = re.search(r'\[TEXT_MANIFEST\](.*?)\[/TEXT_MANIFEST\]', text, re.DOTALL)
    if m:
        for line in m.group(1).strip().split('\n'):
            line = line.strip()
            if ':' in line:
                key, val = line.split(':', 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if val:
                    manifest[key] = val
    return manifest


def _fix_english_card_title_manifest(manifest, card, subject):
    """英语卡标题优化: 如果 TITLE 是纯中文泛化标题，自动拼入英文关键短语

    v10.13 优化提取优先级:
      1. card['title'] 中括号内的英文 (Where is...?) → 最佳
      2. card['title'] 中任意英文短语
      3. card['core_points'] 第一条中的英文短语
      4. card['definition'] 中的英文短语
    避免从 definition 中取到无关的 "under the" 等片段。
    """
    if subject != '英语' and subject != 'english':
        return manifest

    title_key = None
    title_val = None
    for k, v in manifest.items():
        if 'TITLE' in k.upper():
            title_key = k
            title_val = v
            break

    if not title_key or not title_val:
        return manifest

    # v10.21: 智能标题优化 — 只在 AI 标题质量差时替换
    # 如果 AI 已经生成了含英文多词的标题，保留它
    eng_phrase = _extract_best_english_phrase(card)

    # 判断当前标题是否已经足够好
    has_english = bool(re.search(r'[a-zA-Z]{2,}', title_val))
    has_multi_word = bool(re.search(r'[a-zA-Z]+\s+[a-zA-Z]+', title_val))
    is_pure_chinese = not has_english

    if eng_phrase:
        if is_pure_chinese:
            # AI 标题纯中文 → 替换为英文短语
            print(f'      [title fix] 纯中文标题 "{title_val}" → "{eng_phrase}"')
            manifest[title_key] = eng_phrase
        elif not has_multi_word and eng_phrase and ' ' in eng_phrase:
            # AI 标题只有单词 → 替换为更好的多词短语
            print(f'      [title fix] 单词标题 "{title_val}" → "{eng_phrase}"')
            manifest[title_key] = eng_phrase
        # else: AI 标题已含多词英文，保留
    elif is_pure_chinese:
        print(f'      [title fix] ⚠️ 无法提取英文短语，保留原标题: "{title_val}"')

    return manifest


def _extract_best_english_phrase(card):
    """从卡片数据中提取最能代表卡片核心内容的英文短语。

    优先级:
      1. title 括号内英文 (Where is...?) → 这是作者显式标注的表达
      2. title 中的英文短语
      3. core_points[0] 中的英文短语 (通常是最核心的句型)
      4. definition 中的英文短语 (补底)
    """
    title_full = card.get('title', '')

    # 策略1: 从 title 括号内提取 (e.g., "(句型卡：... (Where is...?)")
    paren_matches = re.findall(r'[\(\uff08]([^\)\uff09]*?[a-zA-Z][^\)\uff09]*?)[\)\uff09]', title_full)
    for pm in paren_matches:
        eng_in_paren = re.findall(r"[a-zA-Z][a-zA-Z'\s\.\?!]{1,}", pm)
        if eng_in_paren:
            phrase = max(eng_in_paren, key=len).strip().rstrip('.').strip()[:30]
            if len(phrase) >= 3:
                print(f'      [eng phrase] 从title括号提取: "{phrase}"')
                return phrase

    # 策略2: 从 title 中提取任意英文
    eng_words = re.findall(r"[a-zA-Z][a-zA-Z'\s\.\?!]{2,}", title_full)
    if eng_words:
        phrase = max(eng_words, key=len).strip().rstrip('.').strip()[:30]
        if len(phrase) >= 3:
            print(f'      [eng phrase] 从title提取: "{phrase}"')
            return phrase

    # 策略3: 从 core_points 第一条提取英文
    core_points = card.get('core_points', [])
    if core_points:
        cp0 = core_points[0] if isinstance(core_points[0], str) else str(core_points[0])
        eng_words = re.findall(r"[a-zA-Z][a-zA-Z'\s\.\?!]{2,}", cp0)
        if eng_words:
            phrase = max(eng_words, key=len).strip().rstrip('.').strip()[:30]
            if len(phrase) >= 3:
                print(f'      [eng phrase] 从core_points提取: "{phrase}"')
                return phrase

    # 策略4: 从 definition 提取英文
    definition = card.get('definition', '')
    # 优先提取引号内的英文 (如 用 'Where is...?' 询问)
    quoted = re.findall(r"['‘’“”]([^'‘’“”]*?[a-zA-Z][^'‘’“”]*?)['‘’“”]", definition)
    for q in quoted:
        eng_in_q = re.findall(r"[a-zA-Z][a-zA-Z'\s\.\?!]{1,}", q)
        if eng_in_q:
            phrase = max(eng_in_q, key=len).strip().rstrip('.').strip()[:30]
            if len(phrase) >= 3:
                print(f'      [eng phrase] 仍efinition引号提取: "{phrase}"')
                return phrase
    # 补底: definition 中最长英文
    eng_words = re.findall(r"[a-zA-Z][a-zA-Z'\s\.\?!]{2,}", definition)
    if eng_words:
        phrase = max(eng_words, key=len).strip().rstrip('.').strip()[:30]
        if len(phrase) >= 3:
            print(f'      [eng phrase] 仍efinition提取: "{phrase}"')
            return phrase

    return ''


def _inject_grammar_terms_to_manifest(manifest, card, subject):
    """v10.6: 将卡片中涉及的学科专业术语注入 manifest，用于 OCR 精确审计
    
    原理: 如果卡面会渲染"宾语从句""氧化还原""有丝分裂"等中文术语，
    将它们加入 manifest 的期望文字列表，OCR 审计时能精确匹配，
    防止 "同位语从句" 被渲染成 "应语从句" 等错误漏过检测。
    
    v10.6: 从英语专属扩展到全学科支持
    """
    # 英语: 保留原有逻辑 — 只对概念卡(≥2术语)注入
    if subject == '英语' or subject == 'english':
        is_concept, terms = _is_grammar_concept_card(card)
        if not is_concept or not terms:
            return manifest
    else:
        # 其他学科: 查找卡片中出现的受保护术语
        terms = _find_subject_terms_in_card(card, subject)
        if not terms:
            return manifest
    
    # 检查 manifest 中已有的值，避免重复
    existing_values = ' '.join(manifest.values())
    added = 0
    # 按术语长度降序排列，优先保护长术语（更容易出错）
    sorted_terms = sorted(terms, key=len, reverse=True)
    max_inject = 6 if subject != '英语' else 4  # 非英语学科允许更多术语
    for term in sorted_terms[:max_inject]:
        if term not in existing_values and len(term) >= 2:
            key = f'SUBJECT_TERM_{added + 1}'
            manifest[key] = term
            added += 1
            print(f'      [{subject} protect] 注入期望术语: {key}="{term}"')
    
    return manifest


def _count_chinese_chars(text):
    """统计文本中的中文字符数"""
    return sum(1 for c in text if '\u4e00' <= c <= '\u9fff')


def _dedup_title_line1(manifest, subject=''):
    """v10.19.1: 防重复守门员 — 如果 LINE1 以 TITLE 相同的文字开头，自动去除重复部分。
    
    常见问题: TITLE="pay attention to"，LINE1="Pay Attention To (是高考高频固定搭)"  
    → LINE1 以 TITLE 开头，重复了标题内容
    修复: 去掉 LINE1 中与 TITLE 重复的前缀，只保留教学内容部分
    """
    if not manifest:
        return manifest
    
    # 找到 TITLE 和 LINE1
    title_key, title_val = None, ''
    line1_key, line1_val = None, ''
    for k, v in manifest.items():
        ku = k.upper()
        if ku == 'TITLE':
            title_key, title_val = k, v
        elif ku == 'LINE1':
            line1_key, line1_val = k, v
    
    if not title_key or not line1_key or not title_val or not line1_val:
        return manifest
    
    title_norm = title_val.strip().lower().rstrip('?!.。！？')
    line1_norm = line1_val.strip().lower()
    
    # 检查1: LINE1 完全等于 TITLE
    if line1_norm.rstrip('?!.。！？') == title_norm:
        # LINE1 完全重复 TITLE → 替换为通用教学引导
        if subject == '英语' or subject == 'english':
            manifest[line1_key] = f'Usage & Examples:'
        else:
            manifest[line1_key] = '用法详解:'
        print(f'      [dedup] LINE1 完全重复TITLE，已替换: "{line1_val}" → "{manifest[line1_key]}"')
        return manifest
    
    # 检查2: LINE1 以 TITLE 开头（含大小写变体）
    # 如 TITLE="pay attention to" LINE1="Pay Attention To (是高考高频...)"  
    if line1_norm.startswith(title_norm):
        remainder = line1_val[len(title_val):].lstrip(' (（,，:：-—')
        if remainder:
            # 去掉重复前缀，只保留教学部分
            # 如果剩余部分太短（<3字），补充结构标注
            if len(remainder) < 3:
                remainder = f'Structure & Usage'
            manifest[line1_key] = remainder
            print(f'      [dedup] LINE1 去除TITLE重复前缀: "{line1_val}" → "{remainder}"')
        else:
            if subject == '英语' or subject == 'english':
                manifest[line1_key] = 'Structure & Usage'
            else:
                manifest[line1_key] = '用法详解'
            print(f'      [dedup] LINE1 去除TITLE前缀后为空，已替换: "{line1_val}" → "{manifest[line1_key]}"')
        return manifest
    
    # 检查3: TITLE 以 LINE1 开头（反向重复）
    if title_norm.startswith(line1_norm.rstrip('?!.。！？')):
        if subject == '英语' or subject == 'english':
            manifest[line1_key] = 'Structure & Usage'
        else:
            manifest[line1_key] = '用法详解'
        print(f'      [dedup] LINE1 被TITLE包含，已替换: "{line1_val}" → "{manifest[line1_key]}"')
        return manifest
    
    # 检查4: LINE1 和 TITLE 的英文部分高度重合（>80%单词相同）
    title_words = set(re.findall(r'[a-zA-Z]+', title_val.lower()))
    line1_words = set(re.findall(r'[a-zA-Z]+', line1_val.lower()))
    if title_words and line1_words:
        overlap = len(title_words & line1_words)
        max_len = max(len(title_words), len(line1_words))
        if max_len > 0 and overlap / max_len > 0.8:
            # 高度重合 → 去掉 LINE1 中的重复英文，只保留中文教学部分
            cn_parts = re.findall(r'[\u4e00-\u9fff]+', line1_val)
            if cn_parts:
                manifest[line1_key] = ''.join(cn_parts[:2])  # 保留中文释义
                print(f'      [dedup] LINE1 英文与TITLE 80%+重合，保留中文: "{line1_val}" → "{manifest[line1_key]}"')
            else:
                manifest[line1_key] = 'Structure & Usage'
                print(f'      [dedup] LINE1 英文与TITLE 80%+重合，已替换: "{line1_val}" → "{manifest[line1_key]}"')
    
    # 检查5 (英语卡专属): LINE1 如果是纯中文描述性语句（如"高考高频固定搭配"），
    # 对英语卡这不是有效教学内容，应替换为英文结构说明
    if (subject == '英语' or subject == 'english'):
        line1_cn_count = _count_chinese_chars(manifest.get(line1_key, ''))
        line1_cur = manifest.get(line1_key, '')
        has_eng = bool(re.search(r'[a-zA-Z]{2,}', line1_cur))
        # 如果 LINE1 >= 5个中文且没有英文 → 纯中文描述，替换
        if line1_cn_count >= 5 and not has_eng:
            # 从 LINE2+ 中找出含有英文结构的行作为新 LINE1
            for alt_k in sorted(manifest.keys()):
                if alt_k.upper().startswith('LINE') and alt_k != line1_key:
                    alt_v = manifest[alt_k]
                    if re.search(r'[a-zA-Z]{3,}', alt_v):
                        # 把这行提升为 LINE1，原 LINE1 的中文描述丢弃
                        print(f'      [dedup] LINE1 纯中文描述"{line1_cur}" → 提升{alt_k}为LINE1')
                        manifest[line1_key] = alt_v
                        # 后续 LINE 往前移
                        del manifest[alt_k]
                        break
            else:
                # 没找到合适的替代，用通用英文结构标签
                manifest[line1_key] = 'to + Noun / Gerund (prep.)'
                print(f'      [dedup] LINE1 纯中文描述"{line1_cur}" → 替换为结构说明')
    
    return manifest


def _enforce_manifest_limits(manifest, max_total=None, max_per_block=None, card_type=''):
    """
    文字量守门员: 强制裁剪 TEXT_MANIFEST 中超标的中文文字。
    
    v10.2: PIL 全量渲染模式下大幅放宽限制。
    v10.16: 实验卡/对比卡等天然文字多的类型给更高上限(120字)。
    """
    # v10.16: 根据卡片类型动态调整上限
    # 实验卡（实验步骤多）、对比卡（双栏文字）、辨析卡 天然需要更多文字
    _HEAVY_TEXT_TYPES = ('实验卡', '实验', '对比卡', '辨析卡', '比较卡')
    _LIGHT_TEXT_TYPES = ('高频活用卡', '搭配卡', '语法辨析卡', '易混词卡', '句型卡', '词汇卡',
                         '易混词陷阱卡', '语法纠错卡',
                         # v10.21: 初中/高中英语卡也收紧
                         '时态卡', 'PK挑战卡', '知识总结卡', '情景对话卡', '速记卡',
                         '发音挑战卡', '语法卡', '高频活用卡',
                         # v10.27 P1b: 不规则动词卡也收紧到35字
                         '不规则动词卡')
    is_heavy = card_type in _HEAVY_TEXT_TYPES
    is_light = card_type in _LIGHT_TEXT_TYPES
    if max_total is None:
        max_total = 70 if is_heavy else (35 if is_light else 50)   # v10.19.1: 英语卡收紧到35字
    if max_per_block is None:
        max_per_block = 16 if is_heavy else (10 if is_light else 12)  # v10.19.1: 英语卡单块≤10中文字
    if not manifest:
        return manifest
    
    # 统计当前总中文字数
    total_cn = sum(_count_chinese_chars(v) for v in manifest.values())
    max_slogan_check = min(max_per_block + 4, 14)  # v10.21: 口诀允许更宽(原8→14)，避免截断造成废尾
    if total_cn <= max_total:
        # 仍需检查每块≤limit (口诀用独立预算)
        trimmed = {}
        for k, v in manifest.items():
            cn_count = _count_chinese_chars(v)
            is_slogan = any(s in k.upper() for s in ('SLOGAN', '口诀', 'TIP', 'MOTTO'))
            limit = max_slogan_check if is_slogan else max_per_block
            if cn_count > limit:
                new_v = _trim_to_n_chinese(v, limit)
                print(f'      [manifest guard] {k}: "{v}" → "{new_v}" (每块≤{limit}字)')
                trimmed[k] = new_v
            else:
                trimmed[k] = v
        return trimmed
    
    # 总字数超标，需要激进裁剪
    print(f'      ⚠️ [manifest guard] 总中文{total_cn}字超标(上限{max_total})，启动裁剪...')
    
    result = {}
    budget = max_total
    max_slogan = min(max_per_block + 4, 14)  # v10.21: 口诀独立预算(原8→14)，避免截断废尾
    
    # 优先保留 TITLE
    for k, v in manifest.items():
        if 'TITLE' in k.upper():
            trimmed_v = _trim_to_n_chinese(v, min(max_per_block, budget))
            result[k] = trimmed_v
            budget -= _count_chinese_chars(trimmed_v)
            break
    
    # 其余按顺序，口诀给独立预算
    for k, v in manifest.items():
        if k in result:
            continue
        if budget <= 0:
            print(f'      [manifest guard] 丢弃 {k}: "{v}" (预算用完)')
            continue
        # 口诀/SLOGAN 类字段给更大预算
        is_slogan = any(s in k.upper() for s in ('SLOGAN', '口诀', 'TIP', 'MOTTO'))
        alloc = min(max_slogan if is_slogan else max_per_block, budget)
        cn_count = _count_chinese_chars(v)
        if cn_count == 0:
            result[k] = v  # 纯数字/符号，保留
        elif cn_count <= alloc:
            result[k] = v
            budget -= cn_count
        else:
            trimmed_v = _trim_to_n_chinese(v, alloc)
            print(f'      [manifest guard] {k}: "{v}" → "{trimmed_v}"')
            result[k] = trimmed_v
            budget -= _count_chinese_chars(trimmed_v)
    
    new_total = sum(_count_chinese_chars(v) for v in result.values())
    print(f'      [manifest guard] 裁剪完成: {total_cn}字 → {new_total}字, {len(manifest)}块 → {len(result)}块')
    return result


def _trim_to_n_chinese(text, n):
    """智能截断：保留前n个中文字（保留非中文字符），确保不以虚词/助词半截结尾"""
    result = []
    cn_count = 0
    for c in text:
        if '\u4e00' <= c <= '\u9fff':
            cn_count += 1
            if cn_count > n:
                break
        result.append(c)
    trimmed = ''.join(result).rstrip()
    # 如果截断了，检查末尾是否完整
    if len(trimmed) < len(text):
        trimmed = _ensure_complete_chinese(trimmed)
    return trimmed


# 常见的中文"废尾"——如果口诀以这些字结尾，说明被截断了
# v10.5c: 扩展废尾列表 — 加入常见双字词的前半字（被截断后不成词）
_DANGLING_ENDINGS = set('要的了地得在是和与用把被让给往到从向对着过将能运应学知考记复总提升')

def _ensure_complete_chinese(text):
    """确保中文文字块不以虚词/助词结尾（说明被截断）"""
    if not text:
        return text
    last_char = text[-1]
    if last_char in _DANGLING_ENDINGS:
        # 去掉最后的虚词
        return text[:-1].rstrip()
    return text


# ═══════════════════════════════════════════
# v10.13: 逐行字数控制 — manifest LINE 自动拆行
# ═══════════════════════════════════════════
def _split_long_manifest_lines(manifest: dict) -> dict:
    """v10.13: 逐行字数控制 — 超过 _MAX_LINE_CHARS 的 LINE 自动拆成多行。

    法则二核心: 强制"手动拆块"排版，避免单行过长导致文字堆叠/边缘变形。
    - TITLE / SLOGAN / TIP 不拆（它们有自己的区域且通常较短）
    - LINE1 / LINE2 / ... 超过限制时拆成 LINE1a / LINE1b
    - 拆分点优先选：句号/逗号/分号/顿号 > 空格 > 硬切
    """
    if not manifest:
        return manifest
    limit = _MAX_LINE_CHARS
    result = {}
    for key, val in manifest.items():
        # 只拆 LINE 类型的条目
        if not key.upper().startswith('LINE'):
            result[key] = val
            continue
        cn_count = _count_chinese_chars(val)
        if cn_count <= limit:
            result[key] = val
            continue
        # 需要拆分 — 找最佳拆分点
        sub_lines = _smart_split_text(val, limit)
        if len(sub_lines) == 1:
            result[key] = sub_lines[0]
        else:
            for i, sl in enumerate(sub_lines):
                suffix = chr(ord('a') + i)  # a, b, c...
                new_key = f"{key}{suffix}"
                result[new_key] = sl
            split_keys = ', '.join(f"{key}{chr(ord('a') + i)}" for i in range(len(sub_lines)))
            print(f'      [line split] {key}({cn_count}字) → {len(sub_lines)}行: {split_keys}')
    return result


def _smart_split_text(text: str, max_cn: int) -> list:
    """将长文本按中文字数拆分成多段，优先在标点处断开。"""
    _SPLIT_PUNCTS = '。；;！!？?、，,'
    segments = []
    remaining = text
    while _count_chinese_chars(remaining) > max_cn:
        # 在前 max_cn 个中文范围内找最后一个标点
        best_pos = -1
        cn_seen = 0
        for i, ch in enumerate(remaining):
            if '\u4e00' <= ch <= '\u9fff':
                cn_seen += 1
            if cn_seen <= max_cn and ch in _SPLIT_PUNCTS:
                best_pos = i
            if cn_seen > max_cn and best_pos >= 0:
                break
        if best_pos < 0:
            # 没找到标点，在空格处断
            cn_seen = 0
            for i, ch in enumerate(remaining):
                if '\u4e00' <= ch <= '\u9fff':
                    cn_seen += 1
                if cn_seen <= max_cn and ch == ' ':
                    best_pos = i
                if cn_seen > max_cn:
                    break
        if best_pos < 0:
            # 硬切：在第 max_cn 个中文字后切
            cn_seen = 0
            for i, ch in enumerate(remaining):
                if '\u4e00' <= ch <= '\u9fff':
                    cn_seen += 1
                    if cn_seen == max_cn:
                        best_pos = i
                        break
        if best_pos < 0:
            break
        seg = remaining[:best_pos + 1].strip()
        if seg:
            segments.append(seg)
        remaining = remaining[best_pos + 1:].strip()
    if remaining.strip():
        segments.append(remaining.strip())
    return segments if segments else [text]


# ═══════════════════════════════════════════
# Step 2: 生成卡片图片（强模型 + fallback）
# v10.17: 7大AI优化（字数精简/坐标锚定/两步生图/参考图/Best-of-N/定向精修/温度调优）
# ═══════════════════════════════════════════

# v10.17 参考图缓存 — 按卡片类型缓存高分样本供 few-shot 约束
_REFERENCE_IMAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'card_reference_images')
_reference_cache = {}  # {card_type: b64_data}

def _load_reference_image(card_type, subject=''):
    """v10.17: 加载参考图用于 few-shot image 约束。
    从 card_reference_images/ 目录按 card_type 或 subject 查找。
    返回 base64 编码的图片数据，或 None。
    """
    cache_key = f'{card_type}_{subject}'
    if cache_key in _reference_cache:
        return _reference_cache[cache_key]
    
    if not os.path.isdir(_REFERENCE_IMAGE_DIR):
        return None
    
    # 优先: "{card_type}_{subject}.jpg" → "{card_type}.jpg" → "{subject}.jpg"
    candidates = [
        f'{card_type}_{subject}.jpg', f'{card_type}_{subject}.png',
        f'{card_type}.jpg', f'{card_type}.png',
        f'{subject}.jpg', f'{subject}.png',
    ]
    for fname in candidates:
        fpath = os.path.join(_REFERENCE_IMAGE_DIR, fname)
        if os.path.isfile(fpath):
            try:
                with open(fpath, 'rb') as f:
                    data = f.read()
                b64 = base64.b64encode(data).decode('utf-8')
                _reference_cache[cache_key] = b64
                print(f'      [ref] 加载参考图: {fname} ({len(data)//1024}KB)')
                return b64
            except Exception:
                pass
    return None


def _build_coordinate_manifest(manifest, canvas=None):
    """v10.17 优化②: 坐标锚定 — 为每个 manifest 条目分配精确的 y% 坐标和字号。
    比"render in Banner"更精确，AI 遵循率更高。
    """
    if not manifest:
        return ''
    
    # 计算 LINE 条目数量，动态分配内容区 y 坐标
    line_keys = [k for k in manifest if k.upper().startswith('LINE')]
    n_lines = len(line_keys)
    
    parts = []
    parts.append(
        f"\n=== TEXT RENDERING PLAN ===\n"
        f"The card has {len(manifest)} text blocks. Place each in its designated zone:\n"
    )
    
    line_idx = 0
    for key, val in manifest.items():
        cn_count = _count_chinese_chars(val)
        if key.upper() == 'TITLE':
            parts.append(f'  {key}: "{val}" → place in TOP BANNER, large bold white text, centered')
        elif key.upper() == 'SLOGAN':
            parts.append(f'  {key}: "{val}" → place in ACCENT STRIP near bottom, medium bold white text, centered')
        elif key.upper().startswith('LINE'):
            order = f'row {line_idx+1} of {n_lines}' if n_lines > 1 else 'main row'
            font_hint = 'compact' if cn_count > 10 else 'normal'
            parts.append(f'  {key}: "{val}" → place in CONTENT CARD white area, {order}, dark text, {font_hint} size')
            line_idx += 1
        elif key.upper() == 'TIP':
            parts.append(f'  {key}: "{val}" → place at very bottom, tiny gray text')
        else:
            parts.append(f'  {key}: "{val}" → place in CONTENT CARD white area')
    
    parts.append(f"\n⚠️ Render EVERY text item in its zone. NO omissions, NO truncation.")
    parts.append(f"⚠️ Each Chinese character must have perfect strokes — no garbling!")
    parts.append(f"⚠️ If space is tight, use smaller font — NEVER drop characters!")
    parts.append(f"⚠️ NEVER render coordinates, percentages, pixel sizes, hex colors, or layout metadata as visible text!")
    parts.append("=== END TEXT PLAN ===\n")
    
    return '\n'.join(parts)


def generate_card_image(prompt, keys, card_title='', subject='', audit_hint='', manifest=None, canvas=None,
                        reference_image_b64=None, two_step=True):
    """Step 2: 用最强图片模型生成卡片图片。
    
    v10.17 七大优化:
      ① 字数精简 — manifest 已在外部降到 50 字以内
      ② 坐标锚定 — 每个文字块带精确 y%/font/color 定位
      ③ 两步生图 — 先生标题+装饰底图, 再 image-to-image 补内容文字
      ④ 参考图约束 — 高分历史卡片作为 few-shot 风格参考
      ⑤ Best-of-N — 由外部 generate_card_images_best_of_n 调用
      ⑥ 定向精修 — OCR 错误后只修出错区域 (已有 _build_targeted_text_fix_prompt)
      ⑦ 温度调优 — 文字密集型 0.15, 普通 0.3
    
    keys: API key 列表（全部），内部按 模型→全部key 的顺序尝试。
    manifest: TEXT_MANIFEST 字典，告诉 AI 需要渲染哪些文字。
    canvas: v10.8 画布配置 dict，默认 None 等效于 3:4。
    reference_image_b64: v10.17 参考图 base64 (可选)
    two_step: v10.17 是否使用两步生图 (默认 True)
    """
    if not canvas:
        canvas = _CANVAS_PRESETS['小红书']
    canvas_en = _build_canvas_block_en(canvas)
    
    # v10.17 优化⑦: 温度策略 — 文字多则极低温, 少则稍高
    total_cn = sum(_count_chinese_chars(v) for v in (manifest or {}).values())
    temperature = 0.15 if total_cn > 20 else 0.3
    
    # ── 核心策略: 告诉 AI 渲染所有文字到图片中 ──
    chinese_prefix = (
        f"CRITICAL INSTRUCTIONS — COMPLETE CARD WITH TEXT:\n"
        f"1. This is a {subject} educational knowledge card about \"{card_title}\".\n"
        f"2. ✅ You MUST render ALL text directly in the image — text is the core content!\n"
        f"3. Design a STRUCTURED CARD with text integrated into each zone:\n"
        f"   - TOP BANNER at the very top: Dark gradient strip with WHITE TITLE TEXT centered\n"
        f"   - CONTENT CARD in the middle: White rounded rectangle with TEACHING CONTENT text\n"
        f"   - ACCENT STRIP near the bottom: Warm gradient bar with WHITE SLOGAN TEXT centered\n"
        f"   - BOTTOM edge: Small tip text if any\n"
        f"   - Small cute mascot in bottom-right corner (tiny, under 10 percent of image)\n"
        f"4. ⚠️ TEXT QUALITY IS CRITICAL:\n"
        f"   - Every Chinese character must be perfectly formed (correct strokes, no garbled text)\n"
        f"   - Every English word must be spelled correctly\n"
        f"   - Numbers and math symbols must be accurate\n"
        f"   - ⚠️ NEVER truncate text! Every phrase must be COMPLETE\n"
        f"5. Style: Professional Xiaohongshu card template. Use symbols (→/①②③/≈/=) to replace verbose Chinese.\n"
        f"   Main color: choose from coral pink / mint blue / peach orange / lavender.\n"
        f"6. {canvas_en}\n"
        f"7. ⚠️ Do NOT render any coordinates, percentages, pixel sizes, hex color codes, or layout metadata as visible text in the image!\n"
    )

    # v10.17 优化②: 坐标锚定 manifest (替代旧的 zone-only 描述)
    if manifest:
        manifest = _enforce_manifest_limits(manifest)
        manifest = _split_long_manifest_lines(manifest)
        chinese_prefix += _build_coordinate_manifest(manifest, canvas)

    if audit_hint:
        chinese_prefix += f"\n⚠️ CORRECTION FROM PREVIOUS ATTEMPT:\n{audit_hint}\n"

    # ── v10.17 优化③: 两步生图 ──
    # 第一步: 只渲染 TITLE + SLOGAN + 装饰底图（≤10个汉字，准确率极高）
    # 第二步: 把底图 + 剩余 LINE 内容通过 image-to-image 补上
    if two_step and manifest and len(manifest) > 2:
        base_result = _two_step_generate(prompt, chinese_prefix, manifest, keys, 
                                          card_title, subject, canvas, canvas_en, 
                                          temperature, reference_image_b64)
        if base_result[0]:
            return base_result
        # 两步失败则降级到单步
        print('      [v10.17] 两步生图失败, 降级到单步...')

    # ── 单步生成 (降级路径 / 文字少的卡片) ──
    full_prompt = chinese_prefix + "\n" + prompt
    
    # v10.17 优化④: 参考图约束 — 注入 few-shot image
    contents_parts = [{'text': full_prompt}]
    if reference_image_b64:
        contents_parts = [
            {'text': 'Use this card as a style reference (same layout, color style, text placement). Generate a NEW card with different content:\n'},
            {'inlineData': {'mimeType': 'image/jpeg', 'data': reference_image_b64}},
            {'text': full_prompt}
        ]
    
    contents = [{'role': 'user', 'parts': contents_parts}]
    gen_config = {
        'responseModalities': ['TEXT', 'IMAGE'],
        'temperature': temperature,
        'thinkingConfig': {'thinkingBudget': 1024},
    }

    for mi, model in enumerate(IMAGE_MODELS):
        # 优先模型(Nano Banana Pro)用3轮×3key=9次尝试，充分耗尽配额后才降级
        retries = 3 if mi == 0 else 1
        resp = gemini_call(model, contents, keys[0], gen_config=gen_config, retries=retries, all_keys=keys)
        if not resp:
            if mi == 0:
                print(f'\n      ⚠️ 主力模型 {model} 配额耗尽, 降级到备用模型...', flush=True)
            continue
        try:
            candidates = resp.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                for part in parts:
                    if 'inlineData' in part:
                        b64data = part['inlineData'].get('data', '')
                        mime = part['inlineData'].get('mimeType', 'image/png')
                        if b64data:
                            ext = 'png' if 'png' in mime else 'jpg'
                            print(f' ✅ (model={model})', end='')
                            return base64.b64decode(b64data), ext, model
        except Exception as e:
            print(f'      [Parse error with {model}] {e}')
            continue

    return None, None, None


def _two_step_generate(prompt, chinese_prefix, manifest, keys, card_title, subject, 
                        canvas, canvas_en, temperature, reference_image_b64):
    """v10.17 优化③: 两步生图 — 先出标题底图, 再 image-to-image 补内容。
    
    Step 2a: 只渲染 TITLE + SLOGAN + 背景装饰 (≤10个汉字, 准确率~95%)
    Step 2b: 把 2a 的图 + 剩余 LINE/TIP 内容通过 image-to-image 补充
    
    好处: 每步只需渲染 3-5 个汉字，AI 准确率从 ~60% 提升到 ~90%
    """
    # 分离 manifest: 标题层 vs 内容层
    title_manifest = {}
    content_manifest = {}
    for k, v in manifest.items():
        if k.upper() in ('TITLE', 'SLOGAN'):
            title_manifest[k] = v
        else:
            content_manifest[k] = v
    
    if not title_manifest:
        return None, None, None
    
    # ── Step 2a: 标题 + 装饰底图 ──
    title_cn = sum(_count_chinese_chars(v) for v in title_manifest.values())
    step2a_prompt = (
        f"Generate a {subject} educational knowledge card layout about \"{card_title}\".\n"
        f"This is Step 1 of 2 — generate the CARD FRAME with title and decoration ONLY.\n"
        f"⚠️ In this step, ONLY render these {len(title_manifest)} text items:\n"
    )
    for k, v in title_manifest.items():
        if k.upper() == 'TITLE':
            step2a_prompt += f'  {k}: "{v}" → place in TOP BANNER, large bold white text, centered\n'
        elif k.upper() == 'SLOGAN':
            step2a_prompt += f'  {k}: "{v}" → place in ACCENT STRIP near bottom, medium bold white text, centered\n'
    
    step2a_prompt += (
        f"\nFor the CONTENT CARD area in the middle, leave it as a BLANK white rounded rectangle.\n"
        f"Do NOT put any text in the content area — it will be added in Step 2.\n"
        f"Add: dark gradient banner at top, warm accent strip near bottom, soft background, small OWL mascot with graduation cap in bottom-right (always the same owl character, never other animals).\n"
        f"Style: Professional Xiaohongshu card. {canvas_en}\n"
        f"⚠️ Chinese characters must have perfect strokes. Only {title_cn} characters total.\n"
        f"⚠️ Do NOT render any coordinates, percentages, or layout metadata as visible text!\n"
    )
    
    # 参考图
    parts_2a = [{'text': step2a_prompt}]
    if reference_image_b64:
        parts_2a = [
            {'text': 'Style reference (match layout/colors):'},
            {'inlineData': {'mimeType': 'image/jpeg', 'data': reference_image_b64}},
            {'text': step2a_prompt}
        ]
    
    contents_2a = [{'role': 'user', 'parts': parts_2a}]
    gen_config_2a = {
        'responseModalities': ['TEXT', 'IMAGE'],
        'temperature': 0.15,  # 标题层极低温度 — 保证文字准确
        'thinkingConfig': {'thinkingBudget': 512},
    }
    
    base_image = None
    base_ext = None
    base_model = None
    
    for mi, model in enumerate(IMAGE_MODELS):
        retries = 3 if mi == 0 else 1
        resp = gemini_call(model, contents_2a, keys[0], gen_config=gen_config_2a, retries=retries, all_keys=keys)
        if not resp:
            if mi == 0:
                print(f'\n      ⚠️ [2a] 主力模型 {model} 配额耗尽, 降级...', flush=True)
            continue
        try:
            candidates = resp.get('candidates', [])
            if candidates:
                for part in candidates[0].get('content', {}).get('parts', []):
                    if 'inlineData' in part:
                        b64data = part['inlineData'].get('data', '')
                        mime = part['inlineData'].get('mimeType', 'image/png')
                        if b64data:
                            base_image = base64.b64decode(b64data)
                            base_ext = 'png' if 'png' in mime else 'jpg'
                            base_model = model
                            break
            if base_image:
                break
        except Exception as e:
            print(f'      [Step 2a parse error: {model}] {e}')
            continue
    
    if not base_image:
        return None, None, None
    
    print(f' ✅2a({base_model},{len(base_image)//1024}KB)', end='')
    
    if not content_manifest:
        # 没有内容层，直接返回
        return base_image, base_ext, base_model
    
    # ── Step 2b: image-to-image 补充内容区文字 ──
    content_cn = sum(_count_chinese_chars(v) for v in content_manifest.values())
    step2b_prompt = (
        f"This is Step 2 of 2 — ADD the teaching content text to the blank white area.\n"
        f"The card frame (banner, accent strip, background, mascot) is already done.\n"
        f"⚠️ DO NOT change the banner, accent strip, background, or mascot!\n"
        f"⚠️ ONLY add text into the white CONTENT CARD area (the main white rectangle).\n\n"
        f"ADD these {len(content_manifest)} text blocks into the content area:\n"
    )
    
    # 分配 content 区域描述 (不使用坐标数值，防止AI渲染)
    line_keys = list(content_manifest.keys())
    n = len(line_keys)
    for i, (k, v) in enumerate(content_manifest.items()):
        font_hint = 'compact' if _count_chinese_chars(v) > 10 else 'normal'
        if k.upper() == 'TIP':
            step2b_prompt += f'  {k}: "{v}" → place at very bottom, tiny gray text\n'
        else:
            step2b_prompt += f'  {k}: "{v}" → row {i+1} of {n} in content area, dark text, {font_hint} size\n'
    
    step2b_prompt += (
        f"\n⚠️ Only {content_cn} Chinese characters to add. Render with perfect strokes.\n"
        f"⚠️ Use clear font, good spacing, professional typeset on white background.\n"
        f"⚠️ Keep ALL existing elements (banner title, slogan, colors, mascot) IDENTICAL.\n"
    )
    
    b64_base = base64.b64encode(base_image).decode('utf-8')
    contents_2b = [
        {'role': 'user', 'parts': [
            {'text': step2b_prompt},
            {'inlineData': {'mimeType': f'image/{base_ext}', 'data': b64_base}}
        ]}
    ]
    gen_config_2b = {
        'responseModalities': ['TEXT', 'IMAGE'],
        'temperature': 0.15,  # 内容层也用极低温度
        'thinkingConfig': {'thinkingBudget': 1024},
    }
    
    for mi, model in enumerate(IMAGE_MODELS):
        retries = 3 if mi == 0 else 1
        resp = gemini_call(model, contents_2b, keys[0], gen_config=gen_config_2b, retries=retries, all_keys=keys)
        if not resp:
            if mi == 0:
                print(f'\n      ⚠️ [2b] 主力模型 {model} 配额耗尽, 降级...', flush=True)
            continue
        try:
            candidates = resp.get('candidates', [])
            if candidates:
                for part in candidates[0].get('content', {}).get('parts', []):
                    if 'inlineData' in part:
                        b64data = part['inlineData'].get('data', '')
                        mime = part['inlineData'].get('mimeType', 'image/png')
                        if b64data:
                            final_image = base64.b64decode(b64data)
                            final_ext = 'png' if 'png' in mime else 'jpg'
                            print(f'+2b({model},{len(final_image)//1024}KB)', end='')
                            return final_image, final_ext, model
        except Exception as e:
            print(f'      [Step 2b parse error: {model}] {e}')
            continue
    
    # Step 2b 失败 → 返回 Step 2a 的底图（至少标题正确）
    print(' ⚠️2b失败,用2a底图', end='')
    return base_image, base_ext, base_model


def _generate_single_model(model, contents, gen_config, keys, retries=1):
    """单个模型的图片生成（供并行调用）。返回 (image_data, ext, model) 或 (None, None, model)。"""
    try:
        resp = gemini_call(model, contents, keys[0], gen_config=gen_config, retries=retries, all_keys=keys)
        if not resp:
            return None, None, model
        candidates = resp.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            for part in parts:
                if 'inlineData' in part:
                    b64data = part['inlineData'].get('data', '')
                    mime = part['inlineData'].get('mimeType', 'image/png')
                    if b64data:
                        ext = 'png' if 'png' in mime else 'jpg'
                        return base64.b64decode(b64data), ext, model
    except Exception as e:
        print(f'      [Parallel gen error with {model}] {e}')
    return None, None, model


def generate_card_images_parallel(prompt, keys, card_title='', subject='', audit_hint='', manifest=None, canvas=None, reference_image_b64=None):
    """Step 2 v10.17: Best-of-N 并行生成 — 用所有图片模型同时生成，返回全部候选图片。
    
    v10.17: 坐标锚定 + 温度调优 + 参考图约束
    返回: list of (image_data, ext, model)  — 只包含成功生成的候选
    """
    if not canvas:
        canvas = _CANVAS_PRESETS['小红书']
    canvas_en = _build_canvas_block_en(canvas)
    
    # v10.17: 温度策略
    total_cn = sum(_count_chinese_chars(v) for v in (manifest or {}).values())
    temperature = 0.15 if total_cn > 20 else 0.3
    
    chinese_prefix = (
        f"CRITICAL INSTRUCTIONS — COMPLETE CARD WITH TEXT:\n"
        f"1. This is a {subject} educational knowledge card about \"{card_title}\".\n"
        f"2. ✅ You MUST render ALL text directly in the image — text is the core content!\n"
        f"3. Design a STRUCTURED CARD with text integrated into each zone:\n"
        f"   - TOP BANNER at the very top: Dark gradient strip with WHITE TITLE TEXT centered\n"
        f"   - CONTENT CARD in the middle: White rounded rectangle with TEACHING CONTENT text\n"
        f"   - ACCENT STRIP near the bottom: Warm gradient bar with WHITE SLOGAN TEXT centered\n"
        f"   - BOTTOM edge: Small tip text if any\n"
        f"   - Small cute mascot in bottom-right corner (tiny, under 10 percent of image)\n"
        f"4. ⚠️ TEXT QUALITY IS CRITICAL:\n"
        f"   - Every Chinese character must be perfectly formed (correct strokes, no garbled text)\n"
        f"   - Every English word must be spelled correctly\n"
        f"   - ⚠️ NEVER truncate text! Every phrase must be COMPLETE\n"
        f"5. Style: Professional Xiaohongshu card. Use symbols (→/①②③/≈) to replace verbose text.\n"
        f"   Main color: choose from coral pink / mint blue / peach orange / lavender.\n"
        f"6. {canvas_en}\n"
        f"7. ⚠️ Do NOT render any coordinates, percentages, pixel sizes, hex color codes, or layout metadata as visible text in the image!\n"
    )
    # v10.17: 坐标锚定 manifest
    if manifest:
        manifest = _enforce_manifest_limits(manifest)
        manifest = _split_long_manifest_lines(manifest)
        chinese_prefix += _build_coordinate_manifest(manifest, canvas)
    if audit_hint:
        chinese_prefix += f"\n⚠️ CORRECTION FROM PREVIOUS ATTEMPT:\n{audit_hint}\n"

    full_prompt = chinese_prefix + "\n" + prompt
    
    # v10.17: 参考图约束
    content_parts = [{'text': full_prompt}]
    if reference_image_b64:
        content_parts = [
            {'text': 'Use this card as style reference (same layout/colors). Generate a NEW card:'},
            {'inlineData': {'mimeType': 'image/jpeg', 'data': reference_image_b64}},
            {'text': full_prompt}
        ]
    contents = [{'role': 'user', 'parts': content_parts}]
    gen_config = {
        'responseModalities': ['TEXT', 'IMAGE'],
        'temperature': temperature,
        'thinkingConfig': {'thinkingBudget': 1024},
    }

    # 并行调用所有图片模型 — 主力模型(Nano Banana Pro)更多重试
    results = []
    with ThreadPoolExecutor(max_workers=len(IMAGE_MODELS)) as executor:
        futures = {
            executor.submit(_generate_single_model, model, contents, gen_config, keys,
                            retries=3 if mi == 0 else 1): model
            for mi, model in enumerate(IMAGE_MODELS)
        }
        for future in as_completed(futures):
            model_name = futures[future]
            try:
                img_data, ext, model = future.result()
                if img_data:
                    results.append((img_data, ext, model))
                    print(f' ✅{model_name}', end='')
                else:
                    print(f' ❌{model_name}', end='')
            except Exception as e:
                print(f' ❌{model_name}({e})', end='')
    
    return results


# ═══════════════════════════════════════════
# Step 3: Vision OCR 审计 + 质量评分（合并为一次调用）
# ═══════════════════════════════════════════
OCR_AND_QUALITY_PROMPT = """你是一个严格的知识卡片审计员，同时负责文字审计和质量评分。

我给你一张知识卡片图片。请完成两项任务:

═══ 任务A: 中文文字审计 ═══
1. 列出图片中所有可见的中文文字（逐条列出）
2. 检查是否有乱码、错字、缺笔画、变形
3. 将图片中的文字与期望文字对照，标记差异
4. ⚠️ 检查是否有无意义的英文乱码词（如 "onpiere" "chnese" 等不是正常英语单词的文字）

期望的文字清单：
{expected_texts}

═══ 任务B: 质量评分 ═══
从5个维度**独立评分**(每项0-20分，满分100)：
1. **教学清晰度**(20): 例题清晰? 英语卡:有完整例句+易错对比?
2. **文字准确性**(20): 中文无乱码? 英文拼写正确? 截断废字扣15分!
3. **视觉美感**(20): 配色好看? 像小红书爆款? 有吸引力?
4. **布局合理性**(20): 信息层次清晰? 留白充足? 不拥挤?
5. **可收藏感**(20): 看到就想截图保存? 有"干货感"?
⚠️ 每项根据实际观察独立评分，禁止所有维度给相近分数！优秀项18-20，差的项5-10。
{eng_check_block}

请用以下严格 JSON 格式回复（不要加 markdown 代码块标记）：
{{
  "found_texts": ["图中实际读到的每一处中文文字"],
  "errors": [
    {{"expected": "期望文字", "actual": "实际看到的", "type": "garbled|wrong_char|missing|distorted|gibberish_en|eng_error", "severity": "high|medium|low"}}
  ],
  "overall_score": 85,
  "summary": "一句话总结文字审计",
  "quality": {{
    "teaching": <0-20>, "text_accuracy": <0-20>, "visual": <0-20>, "layout": <0-20>, "saveable": <0-20>,
    "total": <五项求和>, "comment": "具体点评，说明扣分理由"
  }}
}}

═══ 文字审计评分标准(overall_score, 0-100) ═══
- 100: 所有中文完美无误
- 80+: 有轻微瑕疵但可读
- 60-79: 有明显错字但整体可理解
- <60: 严重乱码，需要重新生成

⚠️ 特别检查：伪语义中文（非常重要！）
- AI生成的图片中，经常出现「每个字都能认，但组合起来不是人话」的中文短语
- 典型例子："实则考试快速概忆""学会总结要点明""考试重点复习忆""知识牢记心中悟"
- 这些短句不是成语、不是俗语、不是正常句子——读起来别扭、生硬、不通顺
- 判断方法：把图中每段中文读一遍，如果不像正常中国人说的话 → type:"nonsense_cn", severity:"high", 扣15分
- 尤其注意：底部标语/口号区域、装饰性文字区域——这些位置最容易出现
- 注意区分："熟能生巧" "温故知新" 是正常成语 ✅；"实则考试快速概忆" 不是正常中文 ❌

⚠️ 特别检查：截断废字
- 检查每个中文文字块是否是**完整**的词或短句
- 如果某个文字块以虚词/助词结尾(如"搭配固定要""注意到""记住就")明显是被截断了 → type:"truncated", severity:"high", 扣10分

⚠️ 特别检查：英文乱码词
- 不是正常英语单词的英文字符串（如 "onpiere" "teh" "grammer"）→ type:"gibberish_en", severity:"medium", 扣5分

⚠️ 特别检查：教学内容缺失
- 图片中间区域只有卡通人物+"记住哦"气泡没有实际教学文字 → type:"missing_content", severity:"high", 扣30分

⚠️ 特别检查：语法术语错字
- GRAMMAR_TERM_1/2/3 条目必须100%精确，错字=severity:"high"
- 常见渲染错误: "同位语"→"应语", "宾语"→"宝语", "状语"→"壮语"
- 每处扣15分

⚠️ 特别检查：英文关键短语
- 如果期望文字中有 ENG_KEY_PHRASE 条目，图片中必须可见该英文短语
- 如果找不到该英文短语 → type:"eng_missing", severity:"high", 扣20分
- 英文单词拼写错误（如 progres→progress 少字母）→ type:"eng_error", severity:"medium", 扣10分

只输出JSON，不要其他文字。"""

# 向下兼容: 保留旧变量名
OCR_AUDIT_PROMPT = OCR_AND_QUALITY_PROMPT


def _safe_parse_json(raw: str) -> dict | None:
    """鲁棒的 JSON 解析：处理 trailing commas、注释、非法控制字符等 LLM 常见格式问题"""
    # 第一次尝试：直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    cleaned = raw
    # 移除可能的 markdown 代码块标记
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'```\s*$', '', cleaned, flags=re.MULTILINE)
    # 移除单行注释 // ...（但不破坏 URL 中的 //）
    cleaned = re.sub(r'(?<![:\"\'])//[^\n]*', '', cleaned)
    # 移除 trailing commas: ,] 或 ,}
    cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
    # 替换非标准引号
    cleaned = cleaned.replace('\u201c', '"').replace('\u201d', '"')
    cleaned = cleaned.replace('\u2018', "'").replace('\u2019', "'")
    # 移除非法控制字符 (U+0000-U+001F 除了 \t \n \r)
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', cleaned)

    # 第二次尝试
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 第三次尝试：找到最大的平衡 {} 块
    depth = 0
    start_idx = None
    best_start, best_end = 0, 0
    for i, ch in enumerate(cleaned):
        if ch == '{':
            if depth == 0:
                start_idx = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start_idx is not None:
                if (i - start_idx) > (best_end - best_start):
                    best_start, best_end = start_idx, i + 1
    if best_end > best_start:
        try:
            return json.loads(cleaned[best_start:best_end])
        except json.JSONDecodeError:
            pass

    # 第四次尝试：逐行修复（移除无法解析的行）
    try:
        # 尝试用 ast.literal_eval 作为最后手段 — 不行，不支持 true/false/null
        # 替换 JSON literals 为 Python literals
        py_compat = cleaned.replace(':true', ':True').replace(':false', ':False').replace(':null', ':None')
        py_compat = py_compat.replace(', true', ', True').replace(', false', ', False').replace(', null', ', None')
        import ast
        return ast.literal_eval(py_compat[best_start:best_end] if best_end > best_start else py_compat)
    except Exception:
        pass

    # 第五次尝试：截断 JSON 修复 — 补全缺失的括号使之可解析
    # 常见于 Gemini 思维链消耗 output budget 导致 JSON 被截
    try:
        # 找到最后一个完整的 key:value 对
        # 去掉最后的不完整 key 或 value
        truncated = cleaned
        # 去掉最后的不完整值（如 "C_eye_flow" 没有 : 和 value）
        truncated = re.sub(r',?\s*"[^"]*"\s*$', '', truncated)      # 去掉末尾不完整 key
        truncated = re.sub(r',?\s*"[^"]*":\s*$', '', truncated)      # 去掉末尾 key: 没value
        truncated = re.sub(r',?\s*"[^"]*":\s*\[?\s*$', '', truncated) # 去掉末尾 key: [
        truncated = re.sub(r',\s*$', '', truncated)                    # 去掉末尾逗号
        # 计算需要补全的括号
        open_braces = truncated.count('{') - truncated.count('}')
        open_brackets = truncated.count('[') - truncated.count(']')
        truncated += ']' * max(0, open_brackets) + '}' * max(0, open_braces)
        result = json.loads(truncated)
        if isinstance(result, dict):
            print(f'      [JSON truncation repaired] recovered {len(result)} keys')
            return result
    except Exception:
        pass

    print(f'      [JSON repair failed] raw length={len(raw)}, preview: {raw[:200]}')
    return None


def ocr_audit(image_data, expected_manifest, api_key, all_keys=None, eng_key_phrase=''):
    """Step 3: 用 Vision 模型审计图片文字 + 同步质量评分（合并调用，省一次API）
    
    返回: {
        'overall_score': int,  # OCR审计分
        'errors': list,
        'found_texts': list,
        'summary': str,
        'quality': {'total': int, 'teaching': int, ...}  # 质量评分
    }
    """
    if not expected_manifest:
        return {'overall_score': 100, 'errors': [], 'found_texts': [], 'summary': '无期望文字，跳过审计',
                'quality': {'total': 75, 'comment': '无manifest跳过'}}

    expected_lines = '\n'.join(f'- {k}: "{v}"' for k, v in expected_manifest.items())
    
    # 英语卡额外检查块
    eng_check_block = ''
    if eng_key_phrase:
        eng_check_block = f"""
═══ 英文内容特别检查 ═══
本卡的核心英文短语是: "{eng_key_phrase}"
请额外检查:
1. 图片中是否能看到「{eng_key_phrase}」或其部分？
2. 图片中是否有≥2处完整英文例句（≥6词）？
3. 图片中是否有❌/✅对比区域？
4. 英文单词拼写是否正确？（尤其是 {eng_key_phrase} 相关词汇）
如发现英文问题请加入 errors 列表（type:"eng_error" 或 "eng_missing"）。"""
    
    prompt_text = OCR_AND_QUALITY_PROMPT.format(
        expected_texts=expected_lines,
        eng_check_block=eng_check_block
    )

    b64_img = base64.b64encode(image_data).decode('utf-8')
    contents = [
        {'role': 'user', 'parts': [
            {'text': prompt_text},
            {'inlineData': {'mimeType': 'image/png', 'data': b64_img}}
        ]}
    ]
    gen_config = {
        'maxOutputTokens': 16384,  # v10.5b: 4096→16384, 防止思维链截断JSON
        'temperature': 0.1,
    }

    resp = gemini_call(TEXT_MODEL, contents, api_key, gen_config=gen_config, all_keys=all_keys)
    default_quality = {'total': 0, 'comment': '审计调用失败'}
    if not resp:
        return {'overall_score': 0, 'errors': [], 'found_texts': [], 'summary': 'OCR调用失败',
                'quality': default_quality}

    try:
        candidates = resp.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            for part in parts:
                if 'text' in part and not part.get('thought', False):
                    text = part['text'].strip()
                    json_match = re.search(r'\{[\s\S]*\}', text)
                    if json_match:
                        raw_json = json_match.group()
                        result = _safe_parse_json(raw_json)
                        if result is None:
                            continue
                        # 确保 quality 字段存在
                        if 'quality' not in result:
                            result['quality'] = default_quality
                        else:
                            q = result['quality']
                            if 'total' not in q:
                                scores = [q.get(k, 0) for k in ('teaching', 'text_accuracy', 'visual', 'layout', 'saveable')]
                                q['total'] = sum(scores)
                        # v10.5c: 程序化补检 — 对比 found_texts vs manifest 抓漏检
                        result = _programmatic_text_check(result, expected_manifest)
                        return result
    except (json.JSONDecodeError, Exception) as e:
        print(f'      [OCR parse error] {e}')

    return {'overall_score': 50, 'errors': [], 'found_texts': [], 'summary': 'OCR解析失败',
            'quality': default_quality}


def _programmatic_text_check(ocr_result, expected_manifest):
    """v10.5c: 程序化后置检查 —— 用代码逐字对比 found_texts vs manifest。
    
    Gemini Vision 有时会"脑补"缺失的字（把"提升语言运用能"读成"提升语言运用能力"），
    导致截断/缺字漏检。这里用程序做兜底：
    1. 对每个 manifest 值，检查是否有 found_text 与之匹配（允许少量差异）
    2. 如果 found_text 比 manifest 短 1-3 字 → 补报 truncated 错误
    3. 如果 found_text 与 manifest 完全无匹配 → 已由 Gemini 处理
    """
    found_texts = ocr_result.get('found_texts', [])
    if not found_texts or not expected_manifest:
        return ocr_result
    
    errors = ocr_result.get('errors', [])
    existing_errors = {(e.get('expected', ''), e.get('type', '')) for e in errors}
    score = ocr_result.get('overall_score', 100)
    added = 0
    
    # 提取 manifest 中所有中文值（>= 3字的才检查截断）
    manifest_values = []
    for k, v in expected_manifest.items():
        cn_chars = [c for c in v if '\u4e00' <= c <= '\u9fff']
        if len(cn_chars) >= 3:
            manifest_values.append((k, v, ''.join(cn_chars)))
    
    # 对每个 manifest 值，在 found_texts 中找最佳匹配
    for mk, mv, m_cn in manifest_values:
        best_ratio = 0
        best_found = ''
        for ft in found_texts:
            ft_cn = ''.join(c for c in ft if '\u4e00' <= c <= '\u9fff')
            if not ft_cn:
                continue
            # 检查是否是前缀匹配（截断情况）
            if m_cn.startswith(ft_cn) and len(ft_cn) < len(m_cn):
                ratio = len(ft_cn) / len(m_cn)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_found = ft
            # 检查是否完全匹配
            elif ft_cn == m_cn:
                best_ratio = 1.0
                best_found = ft
                break
        
        # 检测截断：found_text 是 manifest 的前缀，但缺 1-3 字
        if 0.5 < best_ratio < 1.0:
            missing_count = len(m_cn) - int(len(m_cn) * best_ratio)
            if missing_count <= 3 and (mv, 'truncated') not in existing_errors:
                errors.append({
                    'expected': mv,
                    'actual': best_found,
                    'type': 'truncated',
                    'severity': 'high'
                })
                score = max(0, score - 10)
                added += 1
                print(f'      [程序化补检] 截断: "{best_found}" → 期望 "{mv}" (缺{missing_count}字)')
    
    if added > 0:
        ocr_result['errors'] = errors
        ocr_result['overall_score'] = score
        ocr_result['summary'] = (ocr_result.get('summary', '') + f' [+{added}处程序化补检]').strip()

    # v10.13: 英文卡核心短语校验
    ocr_result = _programmatic_english_phrase_check(ocr_result, expected_manifest)

    return ocr_result


def _programmatic_english_phrase_check(ocr_result, expected_manifest):
    """v10.13b: 程序化英文核心短语校验（宽松版）。

    v10.13 原版对所有 manifest 行的英文都做 -8 扣分导致英语卡审计分暴跌至 0。
    v10.13b 修正:
      - TITLE 行英文缺失 → -8/处 (核心，必须准确)
      - 其他行英文缺失 → 仅记录警告，不扣分
      - 总扣分上限 -16 (最多影响2处TITLE)
      - 跳过模板占位符 [Noun]/[Item] 等
    """
    found_texts = ocr_result.get('found_texts', [])
    if not found_texts or not expected_manifest:
        return ocr_result

    all_found = ' '.join(found_texts).lower()
    errors = ocr_result.get('errors', [])
    existing_types = {(e.get('expected', ''), e.get('type', '')) for e in errors}
    score = ocr_result.get('overall_score', 100)
    added = 0
    total_deducted = 0
    MAX_DEDUCT = 16  # 最多扣16分

    for mk, mv in expected_manifest.items():
        # 只检查含英文的 manifest 行
        eng_parts = re.findall(r"[a-zA-Z][a-zA-Z'\s]{2,}", mv)
        if not eng_parts:
            continue

        is_title = 'TITLE' in mk.upper()

        for ep in eng_parts:
            ep_clean = ep.strip().lower()
            if len(ep_clean) < 3:
                continue
            # 跳过模板占位符
            if re.search(r'\[.*\]', ep):
                continue
            # 检查核心英文词是否在 found_texts 中出现
            words = [w for w in ep_clean.split() if len(w) >= 2]
            if not words:
                continue
            matched = sum(1 for w in words if w in all_found)
            ratio = matched / len(words) if words else 0

            if ratio < 0.5 and (mv, 'eng_missing') not in existing_types:
                if is_title and total_deducted < MAX_DEDUCT:
                    # TITLE 英文缺失 → 扣分
                    deduct = min(8, MAX_DEDUCT - total_deducted)
                    errors.append({
                        'expected': mv,
                        'actual': f'英文"{ep_clean}"未在图片中找到',
                        'type': 'eng_missing',
                        'severity': 'medium'
                    })
                    score = max(0, score - deduct)
                    total_deducted += deduct
                    added += 1
                    print(f'      [英文补检] TITLE缺失: "{ep_clean}" ← {mk}="{mv}" (-{deduct})')
                elif not is_title:
                    # 非TITLE行 → 仅警告，不扣分
                    print(f'      [英文补检] 内容行缺失(不扣分): "{ep_clean}" ← {mk}')

    if added > 0:
        ocr_result['errors'] = errors
        ocr_result['overall_score'] = score
        ocr_result['summary'] = (ocr_result.get('summary', '') + f' [+{added}处英文补检]').strip()

    return ocr_result


def _teaching_completeness_audit(ocr_result, original_card):
    """v10.12: 教学完整性审计 — 对比原始卡片数据 vs OCR found_texts。
    
    解决的问题：
    - AI 在生成 manifest 时就已丢失内容，OCR 对着残缺 manifest 打 100 分
    - 需要用原始教学数据做交叉校验，确保关键信息确实出现在图片中
    
    检查项：
    1. mistakes.correct（纠错核心）：必须在图片中有实质体现
    2. core_points 关键词覆盖率：核心知识点需在图中可见
    3. memory_tip 覆盖率：口诀应完整出现
    
    返回: 修改后的 ocr_result（可能降分并添加错误）
    """
    found_texts = ocr_result.get('found_texts', [])
    if not found_texts or not original_card:
        return ocr_result
    
    all_found = ''.join(found_texts)
    # 提取所有中文字符用于匹配
    all_found_cn = ''.join(c for c in all_found if '\u4e00' <= c <= '\u9fff')
    
    errors = ocr_result.get('errors', [])
    score = ocr_result.get('overall_score', 100)
    added = 0
    
    # ── 1. mistakes.correct 检查（最关键）──
    mistakes = original_card.get('mistakes', [])
    for m in mistakes[:2]:  # 最多检查前2条 mistake
        if not isinstance(m, dict):
            continue
        correct_text = m.get('correct', '')
        wrong_text = m.get('wrong', '')
        if not correct_text or len(correct_text) < 4:
            continue
        
        # 提取纠错文本中的关键词（≥2字的中文片段）
        import re as _re_tc
        correct_cn = ''.join(c for c in correct_text if '\u4e00' <= c <= '\u9fff')
        wrong_cn = ''.join(c for c in wrong_text if '\u4e00' <= c <= '\u9fff')
        
        # 将纠错文本拆成2-4字的关键词片段
        correct_keywords = []
        for i in range(0, max(len(correct_cn) - 1, 0), 2):
            kw = correct_cn[i:i+3]
            if len(kw) >= 2:
                correct_keywords.append(kw)
        
        if not correct_keywords:
            continue
        
        # 计算覆盖率：有多少关键词能在图片文字中找到
        found_count = sum(1 for kw in correct_keywords if kw in all_found_cn)
        coverage = found_count / len(correct_keywords) if correct_keywords else 0
        
        # 同时检查：❌的描述和✅的纠正是否有实质区分
        # 如果图片中✅区域的文字和❌区域高度相似，说明纠错丢失
        if coverage < 0.3:
            errors.append({
                'expected': f'纠错: {correct_text[:60]}',
                'actual': f'图片中未找到纠错核心内容(覆盖率{coverage:.0%})',
                'type': 'missing_correction',
                'severity': 'high'
            })
            penalty = 20 if coverage < 0.1 else 15
            score = max(0, score - penalty)
            added += 1
            print(f'      [教学完整性] ❌ 纠错核心丢失: "{correct_text[:30]}..." (覆盖率{coverage:.0%}, -{penalty}分)')
        elif coverage < 0.5:
            errors.append({
                'expected': f'纠错: {correct_text[:60]}',
                'actual': f'纠错内容不完整(覆盖率{coverage:.0%})',
                'type': 'incomplete_correction',
                'severity': 'medium'
            })
            score = max(0, score - 10)
            added += 1
            print(f'      [教学完整性] ⚠️ 纠错不完整: "{correct_text[:30]}..." (覆盖率{coverage:.0%}, -10分)')
    
    # ── 2. core_points 关键词覆盖 ──
    points = original_card.get('core_points', [])
    if points:
        total_kw = 0
        found_kw = 0
        for p in points[:3]:  # 只检查前3条
            p_cn = ''.join(c for c in str(p) if '\u4e00' <= c <= '\u9fff')
            if len(p_cn) < 4:
                continue
            # 用3字滑窗检查
            for i in range(0, len(p_cn) - 2, 3):
                kw = p_cn[i:i+3]
                total_kw += 1
                if kw in all_found_cn:
                    found_kw += 1
        
        pt_coverage = found_kw / total_kw if total_kw > 0 else 1.0
        if pt_coverage < 0.2 and total_kw >= 3:
            errors.append({
                'expected': f'核心知识点({len(points)}条)',
                'actual': f'图片中知识点覆盖率仅{pt_coverage:.0%}',
                'type': 'missing_core_content',
                'severity': 'high'
            })
            score = max(0, score - 15)
            added += 1
            print(f'      [教学完整性] ❌ 知识点覆盖率低: {pt_coverage:.0%} ({found_kw}/{total_kw}关键词)')
    
    # ── 3. memory_tip 完整性 ──
    tip = original_card.get('memory_tip', '')
    if tip and len(tip) >= 6:
        tip_cn = ''.join(c for c in tip if '\u4e00' <= c <= '\u9fff')
        if tip_cn and len(tip_cn) >= 4:
            # 检查口诀是否在图片中有体现（允许部分匹配）
            tip_kws = [tip_cn[i:i+3] for i in range(0, len(tip_cn) - 2, 3)]
            tip_found = sum(1 for kw in tip_kws if kw in all_found_cn)
            tip_cov = tip_found / len(tip_kws) if tip_kws else 1.0
            if tip_cov < 0.2 and len(tip_kws) >= 2:
                # 口诀完全缺失（但不像纠错那么严重）
                errors.append({
                    'expected': f'口诀: {tip[:40]}',
                    'actual': f'图片中未找到口诀(覆盖率{tip_cov:.0%})',
                    'type': 'missing_tip',
                    'severity': 'medium'
                })
                score = max(0, score - 5)
                added += 1
                print(f'      [教学完整性] ⚠️ 口诀缺失: "{tip[:25]}..." (覆盖率{tip_cov:.0%})')
    
    if added > 0:
        ocr_result['errors'] = errors
        ocr_result['overall_score'] = score
        ocr_result['summary'] = (ocr_result.get('summary', '') + 
                                  f' [+教学完整性:发现{added}处缺失]').strip()
    
    return ocr_result


def _contrast_pair_check(ocr_result, original_card):
    """v10.12: ❌/✅ 对比度校验 — 陷阱卡/辨析卡专项。
    
    解决的问题：
    - 陷阱卡的核心价值是 ❌错误 和 ✅正确 形成对比
    - 如果两个区域内容高度相似（如都说"摩擦力阻碍"），教学价值=0
    
    检查逻辑：
    1. 在 found_texts 中找到 ❌ 和 ✅ 区域的文字
    2. 计算两者的文字相似度
    3. 相似度 >80% 且原始数据有明确对比 → 判定为"对比失败"
    
    返回: 修改后的 ocr_result
    """
    card_type = original_card.get('type', '')
    if card_type not in ('陷阱卡', '辨析卡', '易错卡'):
        return ocr_result
    
    mistakes = original_card.get('mistakes', [])
    if not mistakes or not isinstance(mistakes[0], dict):
        return ocr_result
    
    wrong_text = mistakes[0].get('wrong', '')
    correct_text = mistakes[0].get('correct', '')
    if not wrong_text or not correct_text:
        return ocr_result
    
    found_texts = ocr_result.get('found_texts', [])
    if not found_texts:
        return ocr_result
    
    # 在 found_texts 中识别 ❌ 区域和 ✅ 区域的文字
    wrong_region_text = ''
    correct_region_text = ''
    
    import re as _re_cp
    
    # 策略1: 逐条 found_text 按标记分类
    wrong_cn_orig = ''.join(c for c in wrong_text if '\u4e00' <= c <= '\u9fff')
    correct_cn_orig = ''.join(c for c in correct_text if '\u4e00' <= c <= '\u9fff')
    
    for ft in found_texts:
        ft_stripped = ft.strip()
        ft_cn = ''.join(c for c in ft if '\u4e00' <= c <= '\u9fff')
        if not ft_cn or len(ft_cn) < 2:
            continue
        
        # 按 emoji/关键词标记分类
        has_wrong_mark = bool(_re_cp.search(r'[❌✗✘]|为什么错|常见错误', ft_stripped))
        has_correct_mark = bool(_re_cp.search(r'[✅✓✔☑]|正确|纠正', ft_stripped))
        
        if has_wrong_mark and not wrong_region_text:
            # 去掉标记本身，保留内容
            content = _re_cp.sub(r'[❌✗✘✅✓✔☑]\s*|为什么错[：:]\s*|常见错误[：:]\s*|→\s*', '', ft_stripped).strip()
            if len(content) >= 3:
                wrong_region_text = content
        elif has_correct_mark and not correct_region_text:
            content = _re_cp.sub(r'[❌✗✘✅✓✔☑]\s*|正确[：:]\s*|纠正[：:]\s*', '', ft_stripped).strip()
            if len(content) >= 3:
                correct_region_text = content
    
    # 策略2: 如果标记匹配失败，用原始 wrong/correct 文本做内容匹配
    if not wrong_region_text or not correct_region_text:
        for ft in found_texts:
            ft_cn = ''.join(c for c in ft if '\u4e00' <= c <= '\u9fff')
            if not ft_cn:
                continue
            # 匹配 wrong
            if not wrong_region_text and wrong_cn_orig:
                prefix_len = 0
                for i in range(min(len(ft_cn), len(wrong_cn_orig))):
                    if ft_cn[i] == wrong_cn_orig[i]:
                        prefix_len += 1
                    else:
                        break
                if prefix_len >= max(3, len(wrong_cn_orig) * 0.5):
                    wrong_region_text = ft
            # 匹配 correct（排除已匹配为 wrong 的）
            if not correct_region_text and correct_cn_orig and ft != wrong_region_text:
                overlap = sum(1 for c in set(ft_cn) if c in correct_cn_orig)
                if overlap >= max(3, len(correct_cn_orig) * 0.3):
                    correct_region_text = ft
    
    if not wrong_region_text or not correct_region_text:
        return ocr_result
    
    # 计算两区域文字的相似度
    wrong_cn = ''.join(c for c in wrong_region_text if '\u4e00' <= c <= '\u9fff')
    correct_cn = ''.join(c for c in correct_region_text if '\u4e00' <= c <= '\u9fff')
    
    if not wrong_cn or not correct_cn:
        return ocr_result
    
    # Jaccard 相似度（2-gram）
    def bigrams(s):
        return set(s[i:i+2] for i in range(len(s) - 1)) if len(s) >= 2 else {s}
    
    w_bg = bigrams(wrong_cn)
    c_bg = bigrams(correct_cn)
    
    if not w_bg or not c_bg:
        return ocr_result
    
    intersection = len(w_bg & c_bg)
    union = len(w_bg | c_bg)
    similarity = intersection / union if union > 0 else 0
    
    # 同时检查：原始数据中 wrong vs correct 是否有实质差异
    orig_wrong_cn = ''.join(c for c in wrong_text if '\u4e00' <= c <= '\u9fff')
    orig_correct_cn = ''.join(c for c in correct_text if '\u4e00' <= c <= '\u9fff')
    orig_w_bg = bigrams(orig_wrong_cn)
    orig_c_bg = bigrams(orig_correct_cn)
    orig_sim = len(orig_w_bg & orig_c_bg) / len(orig_w_bg | orig_c_bg) if (orig_w_bg | orig_c_bg) else 0
    
    # 检测对比失败的多种模式
    errors = ocr_result.get('errors', [])
    score = ocr_result.get('overall_score', 100)
    contrast_lost = False
    contrast_reason = ''
    
    # 模式A: bigram 高相似度 (>0.7)
    if similarity > 0.7 and orig_sim < 0.7:
        contrast_lost = True
        contrast_reason = f'bigram相似度{similarity:.0%}'
    
    # 模式B: ✅区域是❌区域的子串（截断导致纠错 = 错误）
    if not contrast_lost and correct_cn in wrong_cn and orig_sim < 0.7:
        contrast_lost = True
        contrast_reason = f'✅内容是❌的子串'
    
    # 模式C: ❌区域是✅区域的子串（反向包含）
    if not contrast_lost and wrong_cn in correct_cn and orig_sim < 0.7:
        contrast_lost = True
        contrast_reason = f'❌内容是✅的子串'
    
    # 模式D: ✅ 区域太短，无法构成有效纠错（<8字且原始 correct 很长>15字）
    if not contrast_lost and len(correct_cn) < 8 and len(orig_correct_cn) > 15 and orig_sim < 0.7:
        # ✅ 区域被截断到几乎无信息量
        coverage = len(correct_cn) / len(orig_correct_cn) if orig_correct_cn else 0
        if coverage < 0.4:
            contrast_lost = True
            contrast_reason = f'✅区域严重截断({len(correct_cn)}/{len(orig_correct_cn)}字)'
    
    if contrast_lost:
        penalty = 20 if similarity > 0.85 or (correct_cn in wrong_cn) else 10
        errors.append({
            'expected': f'❌"{wrong_text[:30]}" vs ✅"{correct_text[:30]}"',
            'actual': f'图片❌/✅对比失效({contrast_reason})',
            'type': 'contrast_lost',
            'severity': 'high'
        })
        score = max(0, score - penalty)
        ocr_result['errors'] = errors
        ocr_result['overall_score'] = score
        ocr_result['summary'] = (ocr_result.get('summary', '') + 
                                  f' [❌/✅对比丢失:{contrast_reason}]').strip()
        print(f'      [对比校验] ❌ ❌/✅对比失效({contrast_reason}): '
              f'❌"{wrong_region_text[:20]}" vs ✅"{correct_region_text[:20]}" '
              f'(原始差异={1-orig_sim:.0%}, -{penalty}分)')
    
    return ocr_result


def _build_audit_hint(audit_result, expected_manifest):
    """根据审计结果构建纠错提示（仅文字错误，旧版兼容）"""
    if not audit_result.get('errors'):
        return ''

    hints = []
    for err in audit_result['errors'][:5]:  # 最多5个错误
        exp = err.get('expected', '?')
        act = err.get('actual', '?')
        etype = err.get('type', 'unknown')
        if etype == 'garbled':
            hints.append(f'CRITICAL: "{exp}" appeared as garbled "{act}". Render EXACTLY "{exp}" in thick bold strokes.')
        elif etype == 'wrong_char':
            hints.append(f'WRONG CHARACTER: "{act}" must be "{exp}". Replace exactly.')
        elif etype == 'missing':
            hints.append(f'MISSING TEXT: "{exp}" must appear. Add it clearly.')
        elif etype == 'distorted':
            hints.append(f'DISTORTED: "{exp}" is unreadable. Re-render with thick bold strokes.')
        elif etype == 'nonsense_cn':
            hints.append(f'NONSENSE CHINESE: "{act}" is pseudo-semantic gibberish (每个字都对但拼起来不是人话). Remove it entirely or replace with a natural, meaningful Chinese phrase like a real idiom (e.g. 温故知新) or a clear slogan.')
        elif etype == 'truncated':
            hints.append(f'TRUNCATED TEXT: "{act}" is cut off. Complete the full phrase: "{exp}".')
        else:
            hints.append(f'Fix: "{act}" → "{exp}"')

    return '\n'.join(hints)


# ═══════════════════════════════════════════
# v10.5: 视觉反馈闭环 — 5层审核矩阵 + image-to-image 迭代
# ═══════════════════════════════════════════

# 视觉反馈闭环参数
VISUAL_REFINE_THRESHOLD = 78   # 低于此分触发视觉精修
MAX_REFINE_ROUNDS = 2          # 最多精修轮数

VISUAL_FEEDBACK_AUDIT_PROMPT = """你是小红书知识卡片的艺术总监 + 教育产品经理。
请用「5 层审核矩阵」全面审核这张知识卡片，每一层都不能敷衍。

期望出现在图片中的文字清单：
{expected_texts}

学科: {subject}　　目标年级: {grade}

═══════════════════════════════════════════
Layer A — 致命缺陷排查（一票否决）
═══════════════════════════════════════════
任何一条命中 → 直接判定 FAIL，total 不超过 40：
  A1. 文字腐坏: 有中文出现乱码/缺笔画/偏旁错位/不成字的残影吗？
  A2. 内容缺失: 期望文字清单中有哪些完全没出现在图片中？
  A3. 布局坍塌: 文字之间重叠、溢出画布边界、完全不可读？
  A4. 内容偏离: 图片内容与期望教学主题严重不符（如数学卡出现英语内容）？
  A5. 尺寸灾难: 核心教学文字过小（<图片宽度的4%），手机端完全看不清？
  A6. 伪语义文本: 有中文短句虽然每个字都认得，但拼在一起不通顺、不是真正的中文表达吗？
      例如 "实则考试快速概忆" "学会总结要点明" — 每个字没错但读起来不是人话。
      特别关注底部标语/口号/装饰文字区域，这里最常出现AI编造的伪语义文本。

═══════════════════════════════════════════
Layer B — 文字保真度（满分 30）
═══════════════════════════════════════════
这是知识卡片的命脉，权重最高。

B1. 笔画保真 (0-12)
  - 逐字检查中文：偏旁部首是否完整？笔画是否正确？
  - 特别关注高频出错字：语/话/词/算/题/解/等
  - 英文字母拼写完全正确？
  - 数学符号（±×÷=≠≤≥√∑∫）渲染正确？

B2. 文字完备性 (0-10)
  - 期望文字清单里的每一项是否都在图片中出现？
  - 哪些缺失？哪些被截断？（"固定搭配要" → 明显截断）
  - 是否有不该出现的幽灵文字/乱码英文单词？

B3. 排版系统 (0-8)
  - 字号层级清晰？（标题 ≫ 正文 > 口诀 > 注释）
  - 对齐方式统一？（标题居中、正文左对齐、一致性）
  - 行距适中？字间距正常？没有不自然的拉伸/挤压？

═══════════════════════════════════════════
Layer C — 视觉叙事（满分 25）
═══════════════════════════════════════════
好的设计是在「讲故事」，不只是排信息。

C1. 色彩叙事 (0-9)
  - 配色是否匹配学科专属色系？（数学→理性蓝#1a237e系，语文→古韵棕#4e342e系，英语→活力橙#e65100系，物理→科技银蓝#0d47a1系，化学→实验紫绿#4a148c系，生物→生命绿#1b5e20系，历史→复古金棕#3e2723系，地理→地球蓝绿#004d40系，政治→庄重红蓝#b71c1c系）
  - 是否有1个主色+1个辅色+1个点缀色的配色体系？
  - Banner 是否使用学科主色的深色渐变？口诀条是否用暖亮色？
  - 文字与背景对比度是否 ≥ 4.5:1？（WCAG AA 标准）
  - 避免：纯黑背景、荧光色、红配绿等不和谐搭配

C2. 空间节奏 (0-9)
  - 四周安全边距 ≥ 5% 画布宽度？
  - 各区块（Banner/内容卡/口诀条）之间间距是否一致？
  - 整体留白比例 ≥ 20%？还是信息塞得满满当当？
  - 是否遵循某种网格系统？元素是否对齐到隐形网格线？

C3. 视线引导 (0-7)
  - 用户的眼睛会自然按什么路径阅读？
  - 理想路径: 标题 → 核心知识点 → 例题/示范 → 口诀/总结
  - 是否有元素打断了自然阅读流？（如巨大装饰图插在文字中间）
  - 最重要的内容是否在视觉焦点位置？（上方1/3黄金区域）

═══════════════════════════════════════════
Layer D — 教学力（满分 25）
═══════════════════════════════════════════
这不是普通美图，是教学工具。

D1. 认知负荷管理 (0-9)
  - 信息密度是否合理？一张卡讲一个知识点还是塞了太多？
  - 是否有清晰的信息分块（chunking）？相关信息归为一组？
  - 30 秒内能否抓住核心要点？还是需要反复看？
  - 有无冗余/重复信息占据宝贵空间？

D2. 记忆锚点 (0-9)
  - 有没有帮助记忆的视觉技巧？（颜色编码、图标标注、对比框）
  - 口诀/速记法是否用视觉方式强化？（加粗、专色、专区）
  - 错例是否用红色/删除线等视觉标记与正确答案区分？
  - 关键数字/公式是否有视觉锚定？（大号字、框线、背景色块）

D3. 重点凸显 (0-7)
  - 核心考点是否是最醒目的元素？
  - 易错点有没有⚠️或❌的视觉标注？
  - 答案/结论是否有区别于普通文字的展示？（框、底色、✅）
  - 学科专属（v10.6 全学科覆盖）：
    · 数学：公式/运算步骤是否清晰分步？变量和常数是否区分标注？
    · 英语：例句中重点词汇是否标注（加粗/下划线/色块）？语法术语是否精确？
    · 语文：易错字/多音字是否有标注注音？修辞手法名称是否准确？诗词原文是否逐字正确？
    · 物理：公式变量是否用斜体？单位是否正确标注（N/kg/m/s/Pa）？力的方向箭头是否清晰？
    · 化学：化学方程式是否配平？元素符号大小写是否正确（Na不是na）？离子电荷标注是否在右上角？
    · 生物：生物学术语是否精确（有丝分裂≠有死分裂）？过程流程箭头方向是否正确？
    · 历史：年代数字是否准确？人物姓名是否正确？因果关系链是否逻辑清晰？
    · 地理：地图方向标注是否正确？气候类型名称是否完整准确？经纬度数值是否合理？
    · 政治：政治术语是否使用标准表述？哲学原理是否正确区分？逻辑框架是否完整？

═══════════════════════════════════════════
Layer E — 传播力（满分 20）
═══════════════════════════════════════════
小红书上的知识卡片，传播力=价值。

E1. 拇指急停力 (0-7)
  - 在信息流中快速滑动时，这张图能让人停下来吗？
  - 有没有视觉「钩子」？（色块对比、有趣的标题、醒目的图形）
  - 第一眼印象：专业感、可信度、美感三合一？

E2. 截图冲动 (0-7)
  - 看到这张卡片会想长按保存吗？
  - 是否有「干货满满，值得收藏」的感觉？
  - 内容是否足够完整，保存后不看原文也能复习？
  - 是否有品牌/系列标志让人想关注更多？

E3. 工艺打磨 (0-6)
  - 像专业设计师用 Figma/Sketch 做的？还是 Word 截图？
  - 圆角统一？阴影自然？渐变平滑？
  - 装饰元素（卡通角色/图标/分割线）是否精致而不喧宾夺主？
  - 整体是否有「系列感」——像是一套知识卡的其中一张？

═══════════════════════════════════════════
输出格式（严格 JSON，不要任何其他文字）
═══════════════════════════════════════════

{{
  "fatal_flaws": [
    {{"code": "A1", "description": "标题'乘法口诀'中'诀'字缺少右半部分，变成乱码"}}
  ],

  "scores": {{
    "B_stroke_fidelity": 9,
    "B_text_completeness": 8,
    "B_typo_system": 7,
    "C_color_narrative": 8,
    "C_spatial_rhythm": 7,
    "C_eye_flow": 6,
    "D_cognitive_load": 8,
    "D_memory_anchor": 7,
    "D_key_emphasis": 7,
    "E_thumb_stop": 7,
    "E_screenshot_urge": 8,
    "E_craft_polish": 6
  }},

  "total": 78,

  "text_errors": [
    {{"expected": "期望文字", "actual": "图片中看到的", "type": "garbled|wrong_char|missing|truncated|ghost_text|nonsense_cn", "severity": "fatal|high|medium|low", "location": "Banner/Content/Accent/Bottom"}}
  ],

  "eye_flow_path": "标题→步骤1→步骤2→口诀（流畅）",

  "improvements": [
    "【B1·笔画】标题区'诀'字右半偏旁渲染错误→重新渲染,确保'言'+'夬'完整",
    "【C2·空间】内容卡左边距仅约2%画布宽度→增加到至少5%,与右边距对称",
    "【D2·记忆】口诀'归去来兮辞'没有视觉强化→单独置于暖色底条上,加粗36pt",
    "【E3·打磨】Banner渐变生硬(纯黑→纯白)→改为深蓝#1a237e→靛青#283593平滑渐变"
  ],

  "keep": [
    "配色体系（薄荷绿+珊瑚粉）清新舒适，符合学科氛围",
    "内容分块清晰，三大步骤各自独立成框"
  ],

  "subject_specific": {{
    "check": "数学/英语/语文/物理/化学/生物/历史/地理/政治", 
    "issues": ["公式 a²+b²=c² 中指数渲染为普通字符'2'而非上标"]
  }},

  "one_line_verdict": "文字保真度好，但空间太拥挤且口诀区缺少视觉锚定"
}}

⚠️ improvements 规范：
  - 每条必须标注对应维度代码（如【B1·笔画】【C2·空间】）
  - 必须说清楚：[哪里] [什么问题] → [怎么改]
  - 优先排序：fatal_flaws > B层文字 > D层教学 > C层视觉 > E层传播
  - 最多 6 条（抓大放小）
  - 禁止空泛建议（❌"提高美感"  ✅"Banner背景从纯黑#000改为深蓝渐变#1a237e→#0d47a1"）

⚠️ keep 规范：
  - 至少 2 条——这些方面在改进时不要动！
  - 说具体（❌"颜色不错"  ✅"薄荷绿#a8e6cf主色调清新舒适"）

⚠️ fatal_flaws 规范：
  - 如果没有致命缺陷，返回空数组 []
  - 有致命缺陷时 total 不超过 40

只输出 JSON。"""


def visual_feedback_audit(image_data, expected_manifest, api_key, all_keys=None,
                          subject='', grade=''):
    """v10.5 视觉反馈闭环: 5层审核矩阵全维度审核图片。
    
    Layer A: 致命缺陷排查 (gate check)
    Layer B: 文字保真度 (30分)
    Layer C: 视觉叙事   (25分)
    Layer D: 教学力     (25分)
    Layer E: 传播力     (20分)
    
    返回结构化审核结果，可直接喂给 refine_card_image() 做迭代改进。
    """
    empty_result = {
        'total': 0, 'scores': {}, 'fatal_flaws': [],
        'improvements': [], 'keep': [], 'text_errors': [],
        'eye_flow_path': '', 'subject_specific': {},
        'one_line_verdict': ''
    }

    if not expected_manifest:
        empty_result['total'] = 75
        empty_result['one_line_verdict'] = '无manifest，跳过审核'
        return empty_result
    
    expected_lines = '\n'.join(f'- {k}: "{v}"' for k, v in expected_manifest.items())
    prompt_text = VISUAL_FEEDBACK_AUDIT_PROMPT.format(
        expected_texts=expected_lines,
        subject=subject or '通用',
        grade=grade or '小学',
    )

    b64_img = base64.b64encode(image_data).decode('utf-8')
    contents = [
        {'role': 'user', 'parts': [
            {'text': prompt_text},
            {'inlineData': {'mimeType': 'image/jpeg', 'data': b64_img}}
        ]}
    ]
    # v10.5b: maxOutputTokens 4096→16384 — Gemini 2.5 Flash 的思维链消耗输出 budget,
    # 4096 导致 JSON 被截断(raw_length~347)，16384 给足空间
    gen_config = {'maxOutputTokens': 16384, 'temperature': 0.15}

    # 最多尝试2次（首次解析失败时重试1次）
    for attempt in range(2):
        resp = gemini_call(TEXT_MODEL, contents, api_key, gen_config=gen_config, all_keys=all_keys)
        if not resp:
            if attempt == 0:
                continue
            empty_result['one_line_verdict'] = '审核API调用失败'
            return empty_result
        
        try:
            candidates = resp.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                for part in parts:
                    if 'text' in part and not part.get('thought', False):
                        text = part['text'].strip()
                        result = _safe_parse_json(text)
                        if result and 'scores' in result:
                            # 确保 total 计算正确
                            if 'total' not in result or result['total'] == 0:
                                result['total'] = sum(result['scores'].values())
                            # 致命缺陷 → total 限制到 40
                            if result.get('fatal_flaws'):
                                result['total'] = min(result['total'], 40)
                            # 确保所有期望字段都存在
                            for key in ('fatal_flaws', 'improvements', 'keep',
                                        'text_errors', 'eye_flow_path',
                                        'subject_specific', 'one_line_verdict'):
                                if key not in result:
                                    result[key] = empty_result[key]
                            return result
        except Exception as e:
            print(f'      [Visual audit parse error] {e}')
        
        if attempt == 0:
            print(f'      [Visual audit] JSON解析失败, 重试...')
    
    empty_result['total'] = 50
    empty_result['improvements'] = ['审核解析失败，建议重新生成']
    empty_result['one_line_verdict'] = '解析失败'
    return empty_result


def _build_refinement_prompt(visual_audit_result, expected_manifest, subject='', canvas=None):
    """将5层审核矩阵的结果转化为 image-to-image 精修指令。
    
    v10.13 法则三: 精修 prompt 极简化 — 聚焦修复，减少"大改画面"副作用。
    核心原则:
    - 保留做得好的 (keep) → DON'T TOUCH (精简到1句)
    - 修复致命缺陷 (fatal_flaws) → 最高优先级
    - 文字错误 (text_errors) → 第二优先级
    - 不再列出12维评分和视线流分析（减少AI的"重做冲动"）
    - 附上精简版 manifest
    
    canvas: v10.8 画布配置 dict，默认 None 等效于 3:4。
    """
    fatal_flaws = visual_audit_result.get('fatal_flaws', [])
    text_errors = visual_audit_result.get('text_errors', [])
    keep_list = visual_audit_result.get('keep', [])
    total = visual_audit_result.get('total', 0)

    parts = []
    parts.append(
        f"REFINE this {subject or 'educational'} knowledge card (score: {total}/100).\n"
        f"⚠️ IMPORTANT: Only fix the specific issues listed below. Keep everything else IDENTICAL.\n"
        f"Do NOT change layout, colors, background, or illustration style.\n"
    )

    # 0. 保留不动的优点 — v10.13: 精简到1句总结
    if keep_list:
        parts.append(f"✅ KEEP: {'; '.join(keep_list[:3])}")
        parts.append("")

    # 1. 致命缺陷（最高优先）
    if fatal_flaws:
        parts.append("🚨 FATAL — FIX FIRST:")
        for ff in fatal_flaws[:3]:
            desc = ff.get('description', str(ff)) if isinstance(ff, dict) else str(ff)
            parts.append(f"  🚨 {desc}")
        parts.append("")

    # 2. 文字修正 — 核心精修内容
    if text_errors:
        parts.append("🔴 TEXT FIX:")
        for te in text_errors[:6]:
            exp = te.get('expected', '?')
            act = te.get('actual', '?')
            ttype = te.get('type', '')
            loc = te.get('location', '')
            loc_str = f" (in {loc})" if loc else ''
            if ttype == 'missing':
                parts.append(f'  + ADD: "{exp}"{loc_str}')
            elif ttype == 'garbled':
                parts.append(f'  ✏ "{act}" → "{exp}"{loc_str}')
            elif ttype == 'truncated':
                parts.append(f'  ✏ COMPLETE: "{act}" → "{exp}"{loc_str}')
            elif ttype == 'nonsense_cn':
                parts.append(f'  ✏ REMOVE pseudo-Chinese: "{act}"{loc_str}')
            else:
                parts.append(f'  ✏ "{act}" → "{exp}"{loc_str}')
        parts.append("")

    # v10.13: 移除了维度改进、学科专属、最弱维度、视线流等冗余信息
    # 精修只做"点修复"，不做"全面重构"

    # 3. 完整 manifest 重新附上 (v10.13: 拆行后附上)
    if expected_manifest:
        split_manifest = _split_long_manifest_lines(expected_manifest)
        parts.append("📝 TEXT (render exactly, ≤20 chars per line):")
        for key, val in split_manifest.items():
            zone = ('Banner' if key == 'TITLE' else
                    'Accent strip' if key == 'SLOGAN' else
                    'Content card' if key.upper().startswith('LINE') else 'Bottom')
            parts.append(f'  {key}: "{val}" → {zone}')
        parts.append("")

    if not canvas:
        canvas = _CANVAS_PRESETS['小红书']

    parts.append(
        f"OUTPUT: Same card, only fix the issues above. "
        f"{canvas['ratio']} {canvas['orientation']}. Same colors/layout. "
        f"Perfect Chinese strokes."
    )

    return '\n'.join(parts)


def _build_targeted_text_fix_prompt(ocr_audit_result, expected_manifest, subject='', canvas=None):
    """v10.10: 定向文字修复 prompt — 锁定正确区域，只修乱码区域。
    
    与 _build_refinement_prompt 不同，这个 prompt:
    1. 明确标注哪些区域文字正确 → "DO NOT TOUCH"
    2. 只列出有问题的区域 → 要求 AI 仅重绘这些文字
    3. 不做布局/配色/排版调整 → 只改文字
    """
    errors = ocr_audit_result.get('errors', [])
    # 收集有乱码/错字的 manifest key
    broken_keys = set()
    for err in errors:
        sev = err.get('severity', '')
        if sev in ('high', 'medium'):
            exp = err.get('expected', '')
            # 找到这个错误对应的 manifest key
            for mk, mv in (expected_manifest or {}).items():
                if exp and (exp in mv or mv in exp):
                    broken_keys.add(mk)
                    break
            # 也看 location 字段
            loc = err.get('location', '')
            if loc:
                for mk in (expected_manifest or {}):
                    if mk.lower() in loc.lower() or loc.lower() in mk.lower():
                        broken_keys.add(mk)

    if not broken_keys and errors:
        # 如果没匹配到具体 key，标记所有 LINE 为需修复（保守策略）
        broken_keys = {k for k in (expected_manifest or {}) if k.startswith('LINE')}

    correct_keys = set(expected_manifest.keys()) - broken_keys if expected_manifest else set()

    parts = []
    parts.append(
        f"TARGETED TEXT FIX — {subject or 'educational'} knowledge card.\n"
        f"This image has some garbled/incorrect text that needs fixing.\n"
        f"⚠️ CRITICAL: Only fix the text areas marked below. Do NOT change anything else!\n"
        f"Keep the exact same layout, colors, background, illustrations, and mascot.\n"
    )

    # 1. 锁定正确区域 — DO NOT TOUCH
    if correct_keys:
        parts.append("═══ ✅ CORRECT TEXT — DO NOT MODIFY THESE ═══")
        for ck in sorted(correct_keys):
            val = expected_manifest.get(ck, '')
            zone = ('Banner' if ck == 'TITLE' else
                    'Accent strip' if ck == 'SLOGAN' else
                    'Content card' if ck.startswith('LINE') else 'Bottom')
            parts.append(f'  ✅ {ck} ({zone}): "{val}" — ALREADY CORRECT, DO NOT TOUCH!')
        parts.append("")

    # 2. 列出需要修复的区域
    if broken_keys:
        parts.append("═══ 🔴 FIX THESE TEXT AREAS ONLY ═══")
        for bk in sorted(broken_keys):
            val = expected_manifest.get(bk, '')
            zone = ('Banner' if bk == 'TITLE' else
                    'Accent strip' if bk == 'SLOGAN' else
                    'Content card' if bk.startswith('LINE') else 'Bottom')
            # 找到这个 key 对应的错误描述
            err_desc = ''
            for err in errors:
                exp = err.get('expected', '')
                if exp and (exp in val or val in exp):
                    actual = err.get('actual', '?')
                    err_desc = f' (current garbled text: "{actual}")'
                    break
            parts.append(f'  🔴 {bk} ({zone}): MUST be "{val}"{err_desc}')
            parts.append(f'      → Redraw this text with PERFECT Chinese characters, correct strokes')
        parts.append("")

    # 3. 具体错误列表
    high_errors = [e for e in errors if e.get('severity') in ('high', 'medium')]
    if high_errors:
        parts.append("═══ 📋 SPECIFIC ERRORS TO FIX ═══")
        for he in high_errors[:8]:
            exp = he.get('expected', '?')
            act = he.get('actual', '?')
            etype = he.get('type', '')
            if etype == 'garbled':
                parts.append(f'  ✏ GARBLED: "{act}" → must be "{exp}" (fix every character stroke)')
            elif etype == 'truncated':
                parts.append(f'  ✏ TRUNCATED: "{act}" → complete to "{exp}"')
            elif etype == 'missing':
                parts.append(f'  + ADD: "{exp}" is missing, render it in the correct zone')
            else:
                parts.append(f'  ✏ FIX: "{act}" → "{exp}"')
        parts.append("")

    # 4. 画布配置
    if not canvas:
        canvas = _CANVAS_PRESETS['小红书']

    parts.append(
        "OUTPUT: The same card image with ONLY the broken text areas fixed.\n"
        f"{canvas['ratio']} {canvas['orientation']} ratio. "
        "ALL other elements (layout, colors, background, illustrations, correct text) must remain IDENTICAL.\n"
        "Chinese characters must have perfect strokes — no garbling, no truncation.\n"
    )

    return '\n'.join(parts)


def refine_card_image(prev_image_data, refinement_prompt, keys):
    """v10.5: 基于上一轮图片 + 精修指令生成改进版图片 (image-to-image)。
    
    核心: 把上一张图片 + 审核转化的精修指令一起发给图片模型，
    让 AI 在现有基础上改进，而不是从零生成。
    """
    b64_prev = base64.b64encode(prev_image_data).decode('utf-8')
    
    contents = [
        {'role': 'user', 'parts': [
            {'text': refinement_prompt},
            {'inlineData': {'mimeType': 'image/jpeg', 'data': b64_prev}}
        ]}
    ]
    gen_config = {
        'responseModalities': ['TEXT', 'IMAGE'],
        'temperature': 0.15,  # v10.17: 精修用极低温度(0.3→0.15)，只做点修复不做创意改动
        'thinkingConfig': {'thinkingBudget': 1024},
    }

    for mi, model in enumerate(IMAGE_MODELS):
        # 精修也优先用主力模型
        retries = 3 if mi == 0 else 1
        resp = gemini_call(model, contents, keys[0], gen_config=gen_config, retries=retries, all_keys=keys)
        if not resp:
            if mi == 0:
                print(f'\n      ⚠️ [refine] 主力模型 {model} 配额耗尽, 降级...', flush=True)
            continue
        try:
            candidates = resp.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                for part in parts:
                    if 'inlineData' in part:
                        b64data = part['inlineData'].get('data', '')
                        mime = part['inlineData'].get('mimeType', 'image/png')
                        if b64data:
                            ext = 'png' if 'png' in mime else 'jpg'
                            print(f' ✅ (model={model}, refined)', end='')
                            return base64.b64decode(b64data), ext, model
        except Exception as e:
            print(f'      [Refine parse error with {model}] {e}')
            continue

    return None, None, None


# ═══════════════════════════════════════════
# Step 5: PIL 文字修补兜底
# ═══════════════════════════════════════════
def _try_pil_text_repair(image_data, audit_result, expected_manifest):
    """
    审计仍有错误时，用 PIL 在图片底部叠加一条精确文字条。
    这是最终兜底——确保关键文字正确可读。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print('      [PIL not available for text repair]')
        return image_data

    # 修补 high 和 medium severity 的错误（更积极修补）
    repair_errors = [e for e in audit_result.get('errors', []) if e.get('severity') in ('high', 'medium')]
    if not repair_errors:
        return image_data

    # 收集需要修补的文字（标题优先，然后其他错误文字）
    repair_texts = []
    for err in repair_errors[:5]:
        exp = err.get('expected', '')
        if exp and exp in [v for v in expected_manifest.values()]:
            repair_texts.append(exp)

    if not repair_texts:
        return image_data

    # 打开图片
    img = Image.open(io.BytesIO(image_data))
    w, h = img.size
    draw = ImageDraw.Draw(img)

    # 尝试加载中文字体
    font = None
    font_size = max(36, w // 16)  # 更大字号确保可读
    font_paths = [
        'C:/Windows/Fonts/msyh.ttc',       # 微软雅黑
        'C:/Windows/Fonts/simhei.ttf',      # 黑体
        'C:/Windows/Fonts/simsun.ttc',      # 宋体
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc',
        '/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc',
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except Exception:
                continue
    if not font:
        font = ImageFont.load_default()

    # 在底部绘制修补文字条
    repair_line = ' | '.join(repair_texts)
    bbox = draw.textbbox((0, 0), repair_line, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    bar_h = text_h + 20
    bar_y = h - bar_h

    # 半透明白底
    overlay = Image.new('RGBA', (w, bar_h), (255, 255, 255, 220))
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    img.paste(overlay, (0, bar_y), overlay)

    draw = ImageDraw.Draw(img)
    text_x = (w - text_w) // 2
    text_y = bar_y + 10
    draw.text((text_x, text_y), repair_line, fill=(50, 50, 50, 255), font=font)

    # 保存
    buf = io.BytesIO()
    img.convert('RGB').save(buf, format='JPEG', quality=92)
    print(f'      🔧 PIL修补: 叠加了 "{repair_line}"')
    return buf.getvalue()


# ═══════════════════════════════════════════
# 质量评分
# ═══════════════════════════════════════════
QUALITY_PROMPT = """你是知识卡片质量评审员。请从5个维度**独立评分**(每项0-20分，满分100)：

1. **教学清晰度**(20分): 例题清晰? 解题步骤直观? 一眼就懂? (英语卡: 有完整例句+易错对比+本质原因?)
2. **文字准确性**(20分): 中文无乱码无错字? 数字公式正确? ⚠️截断废字(如"搭配固定要""注意到")直接扣15分!
3. **视觉美感**(20分): 配色好看? 像小红书爆款? 有吸引力?
4. **布局合理性**(20分): 信息层次清晰? 留白充足? 不拥挤?
5. **可收藏感**(20分): 看到就想截图保存? 有"干货感"? 口诀是否完整有意义(截断废话扣10分)?

⚠️ 评分铁律:
- 每项依据实际观察独立打分，禁止所有维度给相近分数
- 优秀项给18-20分，普通项12-15分，有问题的项直接降到5-10分
- 先在脑中逐项分析优缺点，再给出最终分数
- comment 必须包含具体扣分理由（如哪处文字截断、哪块布局拥挤）

只输出JSON格式（不要代码块标记）：
{{"teaching": <0-20的整数>, "text_accuracy": <0-20的整数>, "visual": <0-20的整数>, "layout": <0-20的整数>, "saveable": <0-20的整数>, "total": <五项求和>, "comment": "具体点评，说明扣分理由"}}"""


def quality_score(image_data, api_key, card_title='', all_keys=None):
    """对生成的图片进行质量评分（含重试+fallback）"""
    b64_img = base64.b64encode(image_data).decode('utf-8')
    contents = [
        {'role': 'user', 'parts': [
            {'text': f'这张卡片的主题是"{card_title}"。\n\n{QUALITY_PROMPT}'},
            {'inlineData': {'mimeType': 'image/png', 'data': b64_img}}
        ]}
    ]
    # 禁用 thinking mode 避免解析干扰
    gen_config = {
        'maxOutputTokens': 2048,
        'temperature': 0.5,
        'thinkingConfig': {'thinkingBudget': 1024}
    }

    # v10.25: 重试+fallback — 先用TEXT_MODEL, 失败则fallback到TEXT_MODEL_FALLBACK
    for attempt in range(2):
        use_model = TEXT_MODEL if attempt == 0 else (TEXT_MODEL_FALLBACK or TEXT_MODEL)
        if attempt > 0:
            print(f'      [Quality retry] attempt {attempt+1} with {use_model}')
        resp = gemini_call(use_model, contents, api_key, gen_config=gen_config, all_keys=all_keys)
        if not resp:
            if attempt == 0:
                continue  # 重试一次
            return {'total': 0, 'comment': '评分调用失败(含重试)'}

        try:
            candidates = resp.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                # 收集所有文字 parts（跳过 thinking 部分）
                all_text = ''
                for part in parts:
                    if 'text' in part and not part.get('thought'):
                        all_text += part['text']
                if all_text:
                    json_match = re.search(r'\{[\s\S]*?\}', all_text.strip())
                    if json_match:
                        result = json.loads(json_match.group())
                        # 确保有 total 字段
                        if 'total' not in result:
                            scores = [result.get(k, 0) for k in ('teaching', 'text_accuracy', 'visual', 'layout', 'saveable')]
                            result['total'] = sum(scores)
                        if result['total'] > 0:
                            return result
                        # total=0 可能是解析异常, 重试
                        if attempt == 0:
                            print(f'      [Quality] total=0, retrying...')
                            continue
                        return result
        except Exception as e:
            print(f'      [Quality parse error] {e}')
            if attempt == 0:
                continue
    return {'total': 0, 'comment': '评分解析失败(含重试)'}


def _typed_quality_score(image_data, api_key, card_title='', card_type='方法卡',
                          subject='', all_keys=None):
    """
    分类型精准质量评分（Level 3 升级版, v10.25含重试+fallback）。
    用 content_quality.py 中按卡片类型定义的评分维度替代通用评分。
    """
    typed_prompt = build_typed_quality_prompt(card_type, subject, card_title)

    b64_img = base64.b64encode(image_data).decode('utf-8')
    contents = [
        {'role': 'user', 'parts': [
            {'text': f'这张卡片的主题是"{card_title}"。\n\n{typed_prompt}'},
            {'inlineData': {'mimeType': 'image/png', 'data': b64_img}}
        ]}
    ]
    gen_config = {
        'maxOutputTokens': 2048,
        'temperature': 0.5,
        'thinkingConfig': {'thinkingBudget': 1024}
    }

    # v10.25: 重试+fallback
    for attempt in range(2):
        use_model = TEXT_MODEL if attempt == 0 else (TEXT_MODEL_FALLBACK or TEXT_MODEL)
        if attempt > 0:
            print(f'      [Typed quality retry] attempt {attempt+1} with {use_model}')
        resp = gemini_call(use_model, contents, api_key, gen_config=gen_config, all_keys=all_keys)
        if not resp:
            if attempt == 0:
                continue
            # 最终降级到通用评分
            return quality_score(image_data, api_key, card_title=card_title, all_keys=all_keys)

        try:
            candidates = resp.get('candidates', [])
            if candidates:
                parts = candidates[0].get('content', {}).get('parts', [])
                all_text = ''
                for part in parts:
                    if 'text' in part and not part.get('thought'):
                        all_text += part['text']
                if all_text:
                    json_match = re.search(r'\{[\s\S]*?\}', all_text.strip())
                    if json_match:
                        result = json.loads(json_match.group())
                        # 从 dimensions 计算总分
                        if 'total' not in result and 'dimensions' in result:
                            dim_total = 0
                            for d in result['dimensions'].values():
                                dim_total += d.get('score', 0) if isinstance(d, dict) else d
                            result['total'] = dim_total
                        if result.get('total', 0) > 0:
                            return result
                        if attempt == 0:
                            print(f'      [Typed quality] total=0, retrying...')
                            continue
                        return result
        except Exception as e:
            print(f'      [Typed quality parse error] {e}')
            if attempt == 0:
                continue

    # 降级到通用评分
    return quality_score(image_data, api_key, card_title=card_title, all_keys=all_keys)


# ═══════════════════════════════════════════
# 完整流水线: 单卡片处理
# ═══════════════════════════════════════════
def process_single_card(card, subject, grade, semester, keys, output_dir, skip_audit=False,
                        platform='', ratio_override=''):
    """
    处理单张卡片的完整流水线。
    
    v10.8: platform / ratio_override 控制画布比例。
    返回: (success: bool, filepath: str, stats: dict)
    """
    # 使用自适应参数
    _params = _get_effective_params()
    _max_rounds = _params.get('max_audit_rounds', MAX_AUDIT_ROUNDS)
    _pass_score = _params.get('audit_pass_score', AUDIT_PASS_SCORE)

    # v10.8: 解析画布配置
    card_type = card.get('type', '方法卡')
    canvas = _resolve_canvas(platform=platform, card_type=card_type,
                             subject=subject, ratio_override=ratio_override)

    card_id = card['full_id']
    title = card['title']
    stats = {
        'card_id': card_id,
        'title': title,
        'prompt_gen_time': 0,
        'image_gen_time': 0,
        'audit_rounds': 0,
        'audit_score': 0,
        'quality_score': 0,
        'image_model': '',
        'final_action': '',  # 'pass' / 'repaired' / 'best_effort'
    }

    # ── Step -1: 数据源 schema 校验 + 自动修复 ──
    card_ok, card, schema_issues = _validate_and_repair_card(card, subject, grade)
    if schema_issues:
        print(f'  ├─ Schema校验: {len(schema_issues)}项 → {"; ".join(schema_issues[:3])}')
    if not card_ok:
        stats['final_action'] = 'schema_rejected'
        return False, '', stats

    # v10.12: 保存原始卡片数据（压缩前）用于教学完整性审计
    import copy as _copy_mod
    original_card = _copy_mod.deepcopy(card)

    # ── v10.11 Step 0.5: 内容压缩（渲染前文字量降级）──
    pre_total, pre_bd = _estimate_card_text_volume(card)
    card, comp_log = _compress_card_content(card, subject=subject, keys=keys)
    if comp_log:
        post_total, _ = _estimate_card_text_volume(card)
        print(f'  ├─ Step 0.5: 内容压缩 ({pre_total}字→{post_total}字)')
        for cl in comp_log[:3]:
            print(f'  │   {cl}')
        stats['content_compressed'] = True
        stats['pre_compress_chars'] = pre_total
        stats['post_compress_chars'] = post_total

    # ── Step 0: 内容质量预审 ──
    content_audit_result = None
    if _HAS_QUALITY and not skip_audit:
        try:
            print(f'  ├─ Step 0: 内容质量预审...', end='', flush=True)
            key = next_key(keys)
            qc = full_quality_check(card, card.get('type', '方法卡'), subject, grade, key, all_keys=keys)
            content_audit_result = qc
            v = qc.get('verdict', 'error')
            s = qc.get('total_score', 0)
            print(f' {v}({s}分)')
            if not qc.get('should_proceed', True):
                # ── Feature #5: 自动修复 → 重审 (代替直接 reject) ──
                audit_detail = qc.get('audit', {})
                print(f'  ├─ 🔧 Step 0b: 尝试自动修复卡片数据...')
                fix_key = next_key(keys)
                fixed_ok, fixed_card = _auto_fix_card_data(card, audit_detail, fix_key, all_keys=keys)
                if fixed_ok:
                    # 重新 schema 校验
                    fix_ok2, fixed_card, fix_issues = _validate_and_repair_card(fixed_card, subject, grade)
                    if fix_ok2:
                        card = fixed_card  # 替换为修复后的卡片
                        print(f'  ├─ ✅ 自动修复成功，使用修复后的卡片继续')
                        if fix_issues:
                            print(f'  │   修复后仍有: {"; ".join(fix_issues[:2])}')
                        stats['auto_fixed'] = True
                    else:
                        print(f'  ├─ ⛔ 自动修复后仍不合格，reject')
                        stats['content_audit_score'] = s
                        stats['content_verdict'] = v
                        stats['final_action'] = 'content_rejected_after_fix'
                        return False, '', stats
                else:
                    print(f'  ├─ ⛔ 自动修复失败，reject')
                    stats['content_audit_score'] = s
                    stats['content_verdict'] = v
                    stats['final_action'] = 'content_rejected'
                    return False, '', stats
            stats['content_audit_score'] = s
            stats['content_verdict'] = v
        except Exception as e:
            print(f' ⚠️ 预审出错: {e}')

    # ── Step 1: 生成提示词 ──
    # v2 两阶段 (内容决策 + 视觉翻译)  vs  v1 单阶段
    if _HAS_PROMPT_V2:
        print(f'  ├─ Step 1: 生成提示词 [v2 两阶段]...', end='', flush=True)
    else:
        print(f'  ├─ Step 1: 生成提示词...', end='', flush=True)
    t0 = time.time()
    key = next_key(keys)
    if _HAS_PROMPT_V2:
        prompt, manifest = generate_image_prompt_v2(card, subject, grade, semester, key, all_keys=keys,
                                                     platform=platform, ratio_override=ratio_override)
    else:
        prompt, manifest = generate_image_prompt(card, subject, grade, semester, key, all_keys=keys,
                                                  platform=platform, ratio_override=ratio_override)
    stats['prompt_gen_time'] = time.time() - t0

    if not prompt:
        print(' ❌ 失败')
        return False, '', stats
    
    # 如果内容预审有改进建议，注入到 prompt
    if content_audit_result and _HAS_QUALITY:
        hint = content_audit_result.get('refinement_hint', '')
        if hint:
            prompt = hint + '\n' + prompt

    manifest_count = len(manifest) if manifest else 0
    total_chars = sum(len(v) for v in manifest.values()) if manifest else 0
    print(f' ✅ ({len(prompt)}字, {manifest_count}处文字共{total_chars}字)')

    time.sleep(1)

    # v10.17 优化④: 加载参考图 (few-shot image constraint)
    ref_b64 = _load_reference_image(card_type, subject)

    # ── Step 2-4: Best-of-N + OCR审计 + 定向精修循环 ──
    # v10.17: 第1轮用 Best-of-N 并行生成, 后续轮用定向精修
    best_image = None
    best_ext = 'png'
    best_score = 0
    audit_hint = ''
    last_audit = None  # 保存最近一次审计结果（供自我优化系统使用）

    for round_num in range(1, _max_rounds + 1):
        stats['audit_rounds'] = round_num

        round_label = f'(round {round_num}/{_max_rounds})' if round_num > 1 else ''
        
        # v10.17: 第1轮 Best-of-N 并行; 后续轮定向精修已有图片
        if round_num == 1:
            # ── v10.17 优化⑤: Best-of-N 并行生成 + 选最优 ──
            print(f'  ├─ Step 2: Best-of-N 并行生成...', end='', flush=True)
            t1 = time.time()
            candidates = generate_card_images_parallel(
                prompt, keys, card_title=title, subject=subject,
                audit_hint='', manifest=manifest, canvas=canvas,
                reference_image_b64=ref_b64
            )
            stats['image_gen_time'] += time.time() - t1
            
            if not candidates:
                # 并行失败 → 降级到单步生成
                print(f' ❌ 并行失败, 降级单步...', end='', flush=True)
                t1b = time.time()
                img_data, ext, model = generate_card_image(
                    prompt, keys, card_title=title, subject=subject,
                    audit_hint='', manifest=manifest, canvas=canvas,
                    reference_image_b64=ref_b64
                )
                stats['image_gen_time'] += time.time() - t1b
                if not img_data:
                    print(f' ❌ 所有模型生成失败')
                    return False, '', stats
                candidates = [(img_data, ext, model)]
            
            print(f' {len(candidates)}张候选')
            
            if skip_audit:
                # 无审计模式: 取第一张
                best_image, best_ext, model = candidates[0]
                best_score = 100
                stats['audit_score'] = 100
                stats['image_model'] = model or ''
                stats['final_action'] = 'no_audit'
                break
            
            # 对所有候选做快速OCR审计, 选最高分
            _eng_kp = card.get('_eng_key_phrase', '')
            best_candidate_score = -1
            for ci, (cimg, cext, cmodel) in enumerate(candidates):
                print(f'  │  候选{ci+1} OCR审计...', end='', flush=True)
                key = next_key(keys)
                c_audit = ocr_audit(cimg, manifest, key, all_keys=keys, eng_key_phrase=_eng_kp)
                c_audit = _teaching_completeness_audit(c_audit, original_card)
                c_audit = _contrast_pair_check(c_audit, original_card)
                c_score = c_audit.get('overall_score', 0)
                c_q = c_audit.get('quality', {}).get('total', 0)
                c_combined = (c_score + c_q) / 2 if c_q > 0 else c_score
                print(f' 审计={c_score} 质量={c_q} ({c_audit.get("summary", "")})')
                if c_score > best_candidate_score:
                    best_candidate_score = c_score
                    best_image = cimg
                    best_ext = cext
                    best_score = c_score
                    last_audit = c_audit
                    stats['image_model'] = cmodel or ''
            
            img_data = best_image
            ext = best_ext
            model = stats['image_model']
            
        else:
            # ── v10.17 优化⑥: 后续轮用定向精修 (不全图重生) ──
            if best_image and last_audit:
                post_errs = last_audit.get('errors', [])
                high_errs = [e for e in post_errs if e.get('severity') in ('high', 'medium')]
                if high_errs:
                    print(f'  ├─ Step 2: 定向修复{round_label} ({len(high_errs)}处错误)...', end='', flush=True)
                    t1 = time.time()
                    targeted_prompt = _build_targeted_text_fix_prompt(
                        last_audit, manifest, subject=subject, canvas=canvas
                    )
                    img_data, ext, model = refine_card_image(
                        best_image, targeted_prompt, keys
                    )
                    stats['image_gen_time'] += time.time() - t1
                else:
                    # 没有高严重度错误, 用普通重生成
                    print(f'  ├─ Step 2: 生成图片{round_label}...', end='', flush=True)
                    t1 = time.time()
                    img_data, ext, model = generate_card_image(
                        prompt, keys, card_title=title, subject=subject,
                        audit_hint=audit_hint, manifest=manifest, canvas=canvas,
                        reference_image_b64=ref_b64
                    )
                    stats['image_gen_time'] += time.time() - t1
            else:
                print(f'  ├─ Step 2: 生成图片{round_label}...', end='', flush=True)
                t1 = time.time()
                img_data, ext, model = generate_card_image(
                    prompt, keys, card_title=title, subject=subject,
                    audit_hint=audit_hint, manifest=manifest, canvas=canvas,
                    reference_image_b64=ref_b64
                )
                stats['image_gen_time'] += time.time() - t1

            if not img_data:
                print(f' ❌ 生成失败')
                if best_image:
                    break
                return False, '', stats

            print(f' ✅ ({model}, {len(img_data)/1024:.0f}KB)')
            stats['image_model'] = model or ''

            # Step 3: OCR 审计 + 质量评分
            _eng_kp = card.get('_eng_key_phrase', '')
            print(f'  ├─ Step 3: OCR审计+质量评分...', end='', flush=True)
            key = next_key(keys)
            audit = ocr_audit(img_data, manifest, key, all_keys=keys, eng_key_phrase=_eng_kp)
            audit = _teaching_completeness_audit(audit, original_card)
            audit = _contrast_pair_check(audit, original_card)
            score = audit.get('overall_score', 0)
            errors = audit.get('errors', [])
            summary = audit.get('summary', '')
            merged_quality = audit.get('quality', {})
            q_total = merged_quality.get('total', 0)
            combined = (score + q_total) / 2 if q_total > 0 else score
            print(f' 审计={score} 质量={q_total} 综合={combined:.0f} ({summary})')

            if score > best_score:
                best_image = img_data
                best_ext = ext
                best_score = score
                last_audit = audit

        stats['audit_score'] = best_score

        if score >= _pass_score:
            print(f'  ├─ ✅ OCR审计通过! (score={score}, model={model})')
            stats['final_action'] = 'pass'
            break
        else:
            high_errs = [e for e in errors if e.get('severity') in ('high', 'medium')]
            print(f'  ├─ ⚠️  {len(high_errs)}处文字错误, ', end='')
            if round_num < _max_rounds:
                audit_hint = _build_audit_hint(audit, manifest)
                print(f'重新生成...')
                time.sleep(2)
            else:
                print(f'已达最大轮数')

    if not best_image:
        return False, '', stats

    # v10.4: PIL 修补已停用 — AI 直接渲染文字
    # 如果审计未通过，使用最佳得分的图片
    if not stats['final_action']:
        stats['final_action'] = 'best_effort' if best_score < _pass_score else 'pass'

    # ── v10.5: 视觉反馈精修闭环（始终执行） ──
    # OCR循环只管文字对不对；这一步用5层审核矩阵全面评估，
    # 然后 image-to-image 精修，覆盖排版/配色/教学力/传播力等维度。
    # 每张图都过审核+精修，确保视觉质量打磨到位。
    visual_audit_result = None
    if not skip_audit and manifest:
        merged_q_total = 0
        if last_audit:
            merged_q_total = last_audit.get('quality', {}).get('total', 0)
        combined_score = (best_score + merged_q_total) / 2 if merged_q_total > 0 else best_score

        # 始终执行5层视觉审核
        print(f'  ├─ Step 4b: 5层视觉审核 (综合分{combined_score:.0f})...',
              end='', flush=True)
        key = next_key(keys)
        visual_audit_result = visual_feedback_audit(
            best_image, manifest, key, all_keys=keys,
            subject=subject, grade=grade
        )
        va_total = visual_audit_result.get('total', 0)
        va_fatal = visual_audit_result.get('fatal_flaws', [])
        va_verdict = visual_audit_result.get('one_line_verdict', '')
        va_eye = visual_audit_result.get('eye_flow_path', '')
        print(f' {va_total}/100 {"🚨致命!" if va_fatal else ""} ({va_verdict})')
        if va_eye:
            print(f'  │   视线流: {va_eye}')

        # 按最弱维度输出 top-3 scores
        va_scores = visual_audit_result.get('scores', {})
        if va_scores:
            worst3 = sorted(va_scores.items(), key=lambda x: x[1])[:3]
            worst_str = ', '.join(f'{k}={v}' for k, v in worst3)
            print(f'  │   最弱维度: {worst_str}')

        stats['visual_audit_score'] = va_total
        stats['visual_audit_fatal'] = len(va_fatal)

        # 始终至少精修1轮；va_total太低(<30)说明图可能烂到无法精修
        improvements = visual_audit_result.get('improvements', [])
        text_errors = visual_audit_result.get('text_errors', [])
        should_refine = (improvements or text_errors) and va_total >= 30
        if should_refine:
            for refine_round in range(1, MAX_REFINE_ROUNDS + 1):
                print(f'  ├─ Step 4c: image-to-image 精修 (round {refine_round}/{MAX_REFINE_ROUNDS})...',
                      end='', flush=True)
                refinement_prompt = _build_refinement_prompt(
                    visual_audit_result, manifest, subject=subject, canvas=canvas
                )
                t_refine = time.time()
                refined_data, refined_ext, refined_model = refine_card_image(
                    best_image, refinement_prompt, keys
                )
                stats['image_gen_time'] += time.time() - t_refine

                if not refined_data:
                    print(' ❌ 精修失败，保留原图')
                    break

                refined_kb = len(refined_data) / 1024
                print(f' ({refined_kb:.0f}KB)')

                # 对精修后的图片做 OCR 快审 — 确保文字没变差
                # v10.10: 严格乱码防护 — 精修不能引入新的文字错误
                print(f'  ├─ Step 4d: 精修后OCR快审...', end='', flush=True)
                key = next_key(keys)
                refined_audit = ocr_audit(refined_data, manifest, key, all_keys=keys,
                                          eng_key_phrase=card.get('_eng_key_phrase', ''))
                # v10.12: 精修后也做教学完整性 + 对比度校验
                refined_audit = _teaching_completeness_audit(refined_audit, original_card)
                refined_audit = _contrast_pair_check(refined_audit, original_card)
                refined_ocr = refined_audit.get('overall_score', 0)
                refined_q = refined_audit.get('quality', {}).get('total', 0)
                refined_errs = refined_audit.get('errors', [])
                refined_high = len([e for e in refined_errs if e.get('severity') in ('high', 'medium')])
                # 精修前的 high/medium 错误数
                pre_errs = last_audit.get('errors', []) if last_audit else []
                pre_high = len([e for e in pre_errs if e.get('severity') in ('high', 'medium')])
                print(f' OCR={refined_ocr} 质量={refined_q} 严重错误={refined_high}(原{pre_high})')

                # v10.10 严格判定：
                # 1) OCR不能降（零容忍）
                # 2) 不能引入新的高严重度错误
                # 3) 质量要有提升或OCR提升
                ocr_ok = refined_ocr >= best_score  # 零容忍: OCR不能降
                no_new_garble = refined_high <= pre_high  # 不能多出新乱码
                quality_better = refined_q > merged_q_total
                if ocr_ok and no_new_garble and (quality_better or refined_ocr > best_score):
                    old_combined = combined_score
                    best_image = refined_data
                    best_ext = refined_ext
                    best_score = max(best_score, refined_ocr)
                    last_audit = refined_audit
                    merged_q_total = refined_q
                    combined_score = (best_score + merged_q_total) / 2
                    print(f'  ├─ ✅ 精修采纳! 综合分 {old_combined:.0f}→{combined_score:.0f}')
                    stats['refined'] = True
                    stats['refine_rounds'] = refine_round
                    stats['audit_score'] = best_score
                    stats['final_action'] = 'refined'

                    # 精修后综合分达到高标准(90+)，停止精修
                    if combined_score >= 90:
                        print(f'  ├─ ✅ 综合分优秀 ({combined_score:.0f}>=90)，停止精修')
                        break

                    # 多轮精修：对精修结果再做视觉审核 → 供下轮精修用
                    if refine_round < MAX_REFINE_ROUNDS:
                        print(f'  ├─ Step 4b+: 精修后5层审核...', end='', flush=True)
                        key = next_key(keys)
                        visual_audit_result = visual_feedback_audit(
                            best_image, manifest, key, all_keys=keys,
                            subject=subject, grade=grade
                        )
                        va_total = visual_audit_result.get('total', 0)
                        va_verdict = visual_audit_result.get('one_line_verdict', '')
                        print(f' {va_total}/100 ({va_verdict})')
                        stats['visual_audit_score'] = va_total
                        improvements = visual_audit_result.get('improvements', [])
                        if not improvements or va_total >= 90:
                            print(f'  ├─ ✅ 视觉审核已满意(va={va_total})，停止精修')
                            break
                else:
                    reason = []
                    if not ocr_ok:
                        reason.append(f'OCR降了({refined_ocr}<{best_score})')
                    if not no_new_garble:
                        reason.append(f'新增乱码({refined_high}>{pre_high})')
                    if not quality_better and refined_ocr <= best_score:
                        reason.append(f'质量未提升({refined_q}<={merged_q_total})')
                    print(f'  ├─ ❌ 精修未采纳: {", ".join(reason)}，回退原图')
                    break

    # ── v10.10 Step 4e: 定向文字修复（锁定正确区域，只修乱码） ──
    # 条件: 精修后仍有 high/medium 乱码错误（不管是否执行了精修）
    if last_audit and best_image and not skip_audit:
        post_errs = last_audit.get('errors', [])
        post_high = [e for e in post_errs if e.get('severity') in ('high', 'medium')]
        garble_errs = [e for e in post_high if e.get('type') in ('garbled', 'truncated', 'missing')]
        if garble_errs:
            print(f'  ├─ Step 4e: 定向文字修复 ({len(garble_errs)}处乱码)...', flush=True)
            # 保存精修后的版本作为回退基准
            pre_targeted_image = best_image
            pre_targeted_ext = best_ext
            pre_targeted_score = best_score
            pre_targeted_audit = last_audit

            targeted_prompt = _build_targeted_text_fix_prompt(
                last_audit, manifest, subject=subject, canvas=canvas
            )
            t_targeted = time.time()
            targeted_data, targeted_ext, targeted_model = refine_card_image(
                best_image, targeted_prompt, keys
            )
            stats['image_gen_time'] += time.time() - t_targeted

            if targeted_data:
                targeted_kb = len(targeted_data) / 1024
                print(f'  │  定向修复生成 ({targeted_kb:.0f}KB), OCR快审...', end='', flush=True)
                key = next_key(keys)
                targeted_audit = ocr_audit(targeted_data, manifest, key, all_keys=keys,
                                            eng_key_phrase=card.get('_eng_key_phrase', ''))
                # v10.12: 定向修复后也做教学完整性 + 对比度校验
                targeted_audit = _teaching_completeness_audit(targeted_audit, original_card)
                targeted_audit = _contrast_pair_check(targeted_audit, original_card)
                targeted_ocr = targeted_audit.get('overall_score', 0)
                targeted_q = targeted_audit.get('quality', {}).get('total', 0)
                targeted_errs = targeted_audit.get('errors', [])
                targeted_high = len([e for e in targeted_errs if e.get('severity') in ('high', 'medium')])
                orig_high = len(post_high)

                print(f' OCR={targeted_ocr} 严重错误={targeted_high}(原{orig_high})')

                # 采纳条件: OCR不降 + 乱码不增
                if targeted_ocr >= pre_targeted_score and targeted_high <= orig_high:
                    best_image = targeted_data
                    best_ext = targeted_ext
                    best_score = max(best_score, targeted_ocr)
                    last_audit = targeted_audit
                    if targeted_q > 0:
                        merged_q_total = targeted_q
                    combined_score = (best_score + merged_q_total) / 2
                    print(f'  ├─ ✅ 定向修复采纳! OCR={best_score} 乱码{orig_high}→{targeted_high}')
                    stats['targeted_fix'] = True
                    stats['final_action'] = 'targeted_fix'
                else:
                    # 回退到精修版本
                    reason_t = []
                    if targeted_ocr < pre_targeted_score:
                        reason_t.append(f'OCR降了({targeted_ocr}<{pre_targeted_score})')
                    if targeted_high > orig_high:
                        reason_t.append(f'新增乱码({targeted_high}>{orig_high})')
                    print(f'  ├─ ❌ 定向修复未采纳: {", ".join(reason_t)}，回退精修版本')
                    best_image = pre_targeted_image
                    best_ext = pre_targeted_ext
                    best_score = pre_targeted_score
                    last_audit = pre_targeted_audit
            else:
                print(f'  ├─ ❌ 定向修复生成失败，保留当前版本')

    # ── 质量评分（从合并审计结果中提取，省掉单独API调用）──
    q = {}
    if last_audit and last_audit.get('quality', {}).get('total', 0) > 0:
        q = last_audit['quality']
        print(f'  ├─ Step 5b: 质量评分(from merged audit) {q.get("total", 0)}/100')
    else:
        # 降级: 如果合并审计没返回 quality，单独调用
        print(f'  ├─ Step 5b: 质量评分(fallback)...', end='', flush=True)
        key = next_key(keys)
        if _HAS_QUALITY:
            q = _typed_quality_score(best_image, key, card_title=title,
                                      card_type=card.get('type', '方法卡'),
                                      subject=subject, all_keys=keys)
        else:
            q = quality_score(best_image, key, card_title=title, all_keys=keys)
        print(f' {q.get("total", 0)}/100')
    q_total = q.get('total', 0)
    q_comment = q.get('comment', '')
    stats['quality_score'] = q_total
    stats['quality_detail'] = q

    # ── Step 6: 英语卡片专项审核 ──
    eng_audit_result = None
    if _HAS_ENG_AUDIT and is_english_card(card, subject) and not skip_audit:
        print(f'  ├─ Step 6: 英语卡片8维审核...', end='', flush=True)
        try:
            _eng_kp = card.get('_eng_key_phrase', '')
            eng_audit_result = full_english_audit(
                ocr_result=last_audit or {},
                image_data=best_image,
                card_data=card,
                manifest=manifest or {},
                prompt_text=prompt,
                eng_key_phrase=_eng_kp,
                api_key=next_key(keys),
                gemini_call_fn=gemini_call,
                all_keys=keys,
                skip_semantic=(best_score < 60),  # OCR太差就别浪费语义层
            )
            stats['eng_audit'] = {
                'rule_score': eng_audit_result.rule_score,
                'semantic_score': eng_audit_result.semantic_score,
                'final_score': eng_audit_result.final_score,
                'verdict': eng_audit_result.verdict,
                'issue_count': eng_audit_result.issue_count,
            }
            print(f' {eng_audit_result.summary}')
            if eng_audit_result.issues:
                print(f'      {format_english_audit(eng_audit_result)}')
        except Exception as e:
            print(f' ⚠️ 英语审核出错: {e}')

    # ── 保存 ──
    out_name = card_id.replace('-', '_')
    filename = f'{out_name}.{best_ext}'
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(best_image)
    size_kb = len(best_image) / 1024
    eng_info = f' 英语={eng_audit_result.final_score}' if eng_audit_result else ''
    print(f'  └─ 💾 保存 {filename} ({size_kb:.0f}KB) [审计={best_score} 质量={q_total}{eng_info}]')

    # ── 自我优化: 记录完整结果 ──
    if _HAS_OPTIMIZER:
        try:
            # v10.5: 检查 record_full_result 是否接受新参数
            _extra = {}
            try:
                import inspect as _ins
                _sig = _ins.signature(record_full_result)
                if 'visual_audit_score' in _sig.parameters or any(
                    p.kind == _ins.Parameter.VAR_KEYWORD for p in _sig.parameters.values()
                ):
                    _extra = {
                        'visual_audit_score': stats.get('visual_audit_score', 0),
                        'refined': stats.get('refined', False),
                        'refine_rounds': stats.get('refine_rounds', 0),
                    }
            except Exception:
                pass

            record_full_result(
                card_id=card_id,
                subject=subject,
                grade=grade,
                card_type=card.get('type', ''),
                prompt_text=prompt,
                manifest=manifest,
                audit_score=best_score,
                quality_score=q_total,
                audit_result=last_audit,
                image_model=stats.get('image_model', ''),
                audit_rounds=stats.get('audit_rounds', 1),
                final_action=stats.get('final_action', ''),
                prompt_length=len(prompt),
                image_size_kb=size_kb,
                elapsed_seconds=stats.get('prompt_gen_time', 0) + stats.get('image_gen_time', 0),
                success=True,
                **_extra,
            )
        except Exception as e:
            print(f'  ⚠️ [optimizer] record error: {e}')

    return True, filepath, stats


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════
def main():
    test_mode = '--test' in sys.argv
    skip_audit = '--no-audit' in sys.argv
    force = '--force' in sys.argv
    count_limit = 0
    for i, a in enumerate(sys.argv):
        if a == '--count' and i + 1 < len(sys.argv):
            count_limit = int(sys.argv[i + 1])

    # 找输入文件
    args = [a for a in sys.argv[1:] if not a.startswith('--') and not a.isdigit()]
    json_files = []

    if args:
        # 指定了文件
        json_files = [args[0]]
    else:
        # 自动扫描 knowledge_cards/小学/
        cards_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'knowledge_cards', '小学')
        if os.path.isdir(cards_dir):
            for f in sorted(os.listdir(cards_dir)):
                if f.endswith('.json') and '爆款' not in f:
                    json_files.append(os.path.join(cards_dir, f))
        # fallback: 当前目录
        if not json_files:
            for f in sorted(os.listdir('.')):
                if f.startswith('knowledge_cards') and f.endswith('.json'):
                    json_files.append(f)

    if not json_files:
        print('❌ 未找到知识卡片JSON文件')
        print('用法: python generate_card_images_v3.py [cards.json] [--test] [--count N]')
        sys.exit(1)

    output_dir = 'card_images_v3'
    if len(args) > 1:
        output_dir = args[1]
    os.makedirs(output_dir, exist_ok=True)

    keys = load_api_keys()
    if not keys:
        print('❌ 未找到API密钥 (api_key.txt)')
        sys.exit(1)

    print(f'╔══════════════════════════════════════════════════╗')
    print(f'║  🚀 知识卡片图片生成器 v3 — 终极流水线            ║')
    print(f'╠══════════════════════════════════════════════════╣')
    print(f'║  文字模型: {TEXT_MODEL} (降级: {TEXT_MODEL_FALLBACK})')
    print(f'║  图片模型: {" → ".join(IMAGE_MODELS)}')
    print(f'║  审计: {"关闭" if skip_audit else f"开启 (最多{MAX_AUDIT_ROUNDS}轮, 通过≥{AUDIT_PASS_SCORE}分)"}')
    print(f'║  输入: {len(json_files)} 个JSON文件')
    print(f'║  输出: {output_dir}/')
    if test_mode:
        print(f'║  ⚡ 测试模式: 只生成1张')
    elif count_limit:
        print(f'║  🔢 限量模式: 只生成前{count_limit}张')
    print(f'╚══════════════════════════════════════════════════╝\n')

    total = 0
    success = 0
    all_stats = []
    global_start = time.time()

    for json_file in json_files:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        subject = data['subject']
        grade = data['grade']
        semester = data['semester']
        card_count = sum(len(u['cards']) for u in data['units'])
        print(f'📚 {subject} {grade}{semester} ({card_count}张)')
        print(f'   文件: {os.path.basename(json_file)}\n')

        for unit in data['units']:
            print(f'  📖 单元 {unit["unit_id"]}: {unit["unit_name"]}')

            for card in unit['cards']:
                total += 1

                # 检查已存在
                out_name = card['full_id'].replace('-', '_')
                if not force:
                    existing = [f for f in os.listdir(output_dir) if f.startswith(out_name)]
                    if existing:
                        print(f'  ⏭️  [{total}] {card["full_id"]} {card["title"]} → 已存在 {existing[0]}')
                        success += 1
                        continue

                print(f'\n  ┌─ [{total}] {card["full_id"]} {card["title"]} (类型={card.get("type","?")}, 难度={card["difficulty"]})')

                ok, fpath, stats = process_single_card(
                    card, subject, grade, semester, keys, output_dir, skip_audit=skip_audit
                )
                all_stats.append(stats)

                if ok:
                    success += 1

                if test_mode:
                    break
                if count_limit and success >= count_limit:
                    break
                time.sleep(2)

            if test_mode and success > 0:
                break
            if count_limit and success >= count_limit:
                break

        if test_mode and success > 0:
            break
        if count_limit and success >= count_limit:
            break
        print()

    elapsed = time.time() - global_start

    # 保存统计报告
    report_file = os.path.join(output_dir, '_report.json')
    report = {
        'generated_at': datetime.datetime.now().isoformat(),
        'total_cards': total,
        'success': success,
        'elapsed_seconds': round(elapsed, 1),
        'avg_seconds_per_card': round(elapsed / max(success, 1), 1),
        'models': IMAGE_MODELS,
        'audit_enabled': not skip_audit,
        'cards': all_stats,
    }
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 统计摘要
    audit_scores = [s['audit_score'] for s in all_stats if s['audit_score'] > 0]
    quality_scores = [s['quality_score'] for s in all_stats if s['quality_score'] > 0]
    avg_audit = sum(audit_scores) / len(audit_scores) if audit_scores else 0
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

    print(f'\n╔══════════════════════════════════════════════════╗')
    print(f'║  🎉 生成完成!                                     ║')
    print(f'╠══════════════════════════════════════════════════╣')
    print(f'║  成功: {success}/{total} 张')
    print(f'║  耗时: {elapsed:.0f}秒 (平均 {elapsed/max(success,1):.1f}秒/张)')
    print(f'║  OCR审计均分: {avg_audit:.1f}/100')
    print(f'║  质量评分均分: {avg_quality:.1f}/100')
    print(f'║  输出目录: {output_dir}/')
    print(f'║  统计报告: {report_file}')
    print(f'╚══════════════════════════════════════════════════╝')


if __name__ == '__main__':
    main()
