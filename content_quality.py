#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内容质量三级升级系统 (Content Quality System)
==============================================
Level 1: 内容审核引擎 (Content Audit Engine)
  - 知识准确性审核
  - 课标匹配度审核
  - 例题完整性审核
  - 逻辑连贯性审核
  - 助记有效性审核

Level 2: 内容沉淀系统 (Content Distiller)
  - 高分卡片模式提炼
  - 低分卡片失败归因
  - 最佳实践指南自动生成
  - 跨类型策略迁移

Level 3: 自适应质量标准 (Adaptive Quality Rubrics)
  - 分卡片类型评分标准
  - 分学科重点权重
  - 可执行反馈建议
  - 质量趋势追踪

存储: SQLite (content_quality.db)
集成: 被 generate_card_images_v3.py 和 server.py 调用
"""

import json, os, sqlite3, time, re, statistics
from datetime import datetime, timedelta

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH = os.path.join(_BASE_DIR, 'content_quality.db')

# ═══════════════════════════════════════════
# Level 3: 自适应质量标准 (Rubrics)
# ═══════════════════════════════════════════

# 每种卡片类型的评分维度及权重（满分100）
QUALITY_RUBRICS = {
    # ── 数学类 ──
    '方法卡': {
        'dimensions': {
            '知识准确性': {'weight': 25, 'desc': '公式/定理/定义是否正确无误'},
            '例题完整性': {'weight': 25, 'desc': '题目+步骤+答案是否完整'},
            '教学清晰度': {'weight': 20, 'desc': '解题逻辑是否一步一步清晰可懂'},
            '视觉美感':   {'weight': 15, 'desc': '配色/排版/图表是否美观有吸引力'},
            '助记有效性': {'weight': 15, 'desc': '口诀/记忆技巧是否朗朗上口、真有用'},
        },
        'must_have': ['例题', '解题步骤', '公式或规则'],
        'red_flags': ['公式错误', '步骤缺失', '答案错误', '难度不匹配'],
    },
    '易错题卡': {
        'dimensions': {
            '知识准确性': {'weight': 25, 'desc': '正确答案和错误原因是否准确'},
            '对比清晰度': {'weight': 25, 'desc': '正误对比是否一目了然(❌ vs ✅)'},
            '例题完整性': {'weight': 20, 'desc': '易错题+正确解法是否完整'},
            '视觉美感':   {'weight': 15, 'desc': '红绿对比/标注是否醒目美观'},
            '实用价值':   {'weight': 15, 'desc': '这个易错点是否真的常考/高频'},
        },
        'must_have': ['错误示范', '正确解法', '易错原因'],
        'red_flags': ['正确答案反而是错的', '错误原因解释不清'],
    },
    '计算零失误卡': {
        'dimensions': {
            '知识准确性': {'weight': 30, 'desc': '竖式/运算/验算过程100%正确'},
            '步骤规范性': {'weight': 25, 'desc': '竖式对位/进退位/验算步骤规范'},
            '教学清晰度': {'weight': 20, 'desc': '计算过程彩色分层、逐步演示'},
            '视觉美感':   {'weight': 15, 'desc': '竖式排版/配色/标注是否清晰'},
            '防错提示':   {'weight': 10, 'desc': '是否有检查清单/验算步骤'},
        },
        'must_have': ['竖式过程', '计算答案', '验算方法'],
        'red_flags': ['计算结果错误', '竖式对位错误', '进位遗漏'],
    },
    # ── 语文类 ──
    '生字卡': {
        'dimensions': {
            '知识准确性': {'weight': 30, 'desc': '笔顺/拼音/释义是否正确'},
            '例句质量':   {'weight': 20, 'desc': '例句是否通顺、贴近生活'},
            '记忆技巧':   {'weight': 20, 'desc': '字源/联想/口诀是否有效'},
            '视觉美感':   {'weight': 15, 'desc': '字体展示/配色是否美观'},
            '信息密度':   {'weight': 15, 'desc': '一张卡上信息量是否恰到好处'},
        },
        'must_have': ['汉字', '拼音', '释义'],
        'red_flags': ['拼音声调错误', '释义有误', '笔顺顺序错'],
    },
    '阅读理解卡': {
        'dimensions': {
            '知识准确性': {'weight': 25, 'desc': '答题方法/公式是否准确可靠'},
            '方法实用性': {'weight': 25, 'desc': '方法步骤是否可操作、可套用'},
            '例题质量':   {'weight': 20, 'desc': '示例选段+答案是否典型为准'},
            '视觉美感':   {'weight': 15, 'desc': '排版层次/配色是否美观'},
            '覆盖度':     {'weight': 15, 'desc': '是否覆盖常考题型'},
        },
        'must_have': ['答题方法', '示例', '答题模板'],
        'red_flags': ['方法步骤模糊', '示例答案有误'],
    },
    # ── 英语类 ──
    '语法辨析卡': {
        'dimensions': {
            '语法准确性': {'weight': 30, 'desc': '语法规则/引导词用法100%正确'},
            '中英对照':   {'weight': 25, 'desc': '中英双语对照是否清晰准确'},
            '例句质量':   {'weight': 20, 'desc': '例句是否地道、典型、无语法错'},
            '对比清晰度': {'weight': 15, 'desc': '不同用法的对比是否一目了然'},
            '视觉美感':   {'weight': 10, 'desc': '配色/排版/图标是否美观'},
        },
        'must_have': ['语法规则', '中英双语例句', '用法对比'],
        'red_flags': ['英语语法错误', '翻译不准确', '引导词混淆'],
    },
    '单词卡': {
        'dimensions': {
            '知识准确性': {'weight': 30, 'desc': '单词拼写/音标/释义是否正确'},
            '例句质量':   {'weight': 20, 'desc': '例句是否地道、难度匹配'},
            '记忆技巧':   {'weight': 20, 'desc': '联想/词根/对比是否有效'},
            '发音标注':   {'weight': 15, 'desc': '音标/自然拼读是否标注'},
            '视觉美感':   {'weight': 15, 'desc': '配色/排版是否美观'},
        },
        'must_have': ['单词', '释义', '例句'],
        'red_flags': ['单词拼写错误', '释义不准确', '音标错误'],
    },
    # ── 考卷类 ──
    '考卷真题卡': {
        'dimensions': {
            '题目准确性': {'weight': 30, 'desc': '题目内容/数据是否准确无误'},
            '解题步骤':   {'weight': 30, 'desc': '解答过程是否完整、逻辑清晰'},
            '答案正确性': {'weight': 20, 'desc': '最终答案是否100%正确'},
            '评分标准':   {'weight': 10, 'desc': '是否标注得分点/扣分点'},
            '视觉美感':   {'weight': 10, 'desc': '排版是否清晰可读'},
        },
        'must_have': ['真题题目', '完整解答', '标准答案'],
        'red_flags': ['答案计算错误', '解题步骤跳跃', '题目抄写有误'],
    },
    # ── 知识总结类 ──
    '知识总结卡': {
        'dimensions': {
            '知识覆盖度': {'weight': 25, 'desc': '该单元核心知识点是否全面覆盖'},
            '结构层次':   {'weight': 25, 'desc': '知识点是否有清晰的层级结构'},
            '信息密度':   {'weight': 20, 'desc': '内容是否精炼、无冗余、有干货感'},
            '可收藏感':   {'weight': 15, 'desc': '看到就想截图保存的吸引力'},
            '视觉美感':   {'weight': 15, 'desc': '配色/图标/排版是否美观'},
        },
        'must_have': ['核心知识点', '知识结构图', '关键公式或规则'],
        'red_flags': ['知识点遗漏', '分类混乱', '重复冗余'],
    },
    # ── 养生类 ──
    '养生卡': {
        'dimensions': {
            '知识准确性': {'weight': 30, 'desc': '健康/营养/运动建议是否科学准确'},
            '实用价值':   {'weight': 25, 'desc': '方法/食谱/动作是否可操作'},
            '安全性':     {'weight': 20, 'desc': '建议是否安全、无副作用风险'},
            '可收藏感':   {'weight': 15, 'desc': '干货感、想截图保存'},
            '视觉美感':   {'weight': 10, 'desc': '配色/排版是否美观'},
        },
        'must_have': ['核心建议', '操作方法', '注意事项'],
        'red_flags': ['医学知识错误', '危险建议', '过度承诺效果'],
    },
    # ── 国学类 ──
    '国学卡': {
        'dimensions': {
            '知识准确性': {'weight': 30, 'desc': '原文/出处/释义是否准确'},
            '文化深度':   {'weight': 25, 'desc': '解读是否有深度和见解'},
            '现代连接':   {'weight': 20, 'desc': '古典知识是否与现代生活关联'},
            '可收藏感':   {'weight': 15, 'desc': '文化底蕴感、想保存分享'},
            '视觉美感':   {'weight': 10, 'desc': '配色/排版/中国风元素'},
        },
        'must_have': ['原文出处', '释义', '现代启示'],
        'red_flags': ['原文引用错误', '释义偏离原意', '张冠李戴'],
    },
    # ── 情感类 ──
    '情感卡': {
        'dimensions': {
            '内容共鸣度': {'weight': 30, 'desc': '是否击中目标人群的情感痛点'},
            '实用价值':   {'weight': 25, 'desc': '建议/方法是否可操作'},
            '表达质量':   {'weight': 20, 'desc': '文字是否打动人、有文采'},
            '可收藏感':   {'weight': 15, 'desc': '精辟/走心程度，想转发分享'},
            '视觉美感':   {'weight': 10, 'desc': '配色/排版/氛围感'},
        },
        'must_have': ['核心观点', '实用建议'],
        'red_flags': ['价值观不当', '过于说教', '内容空洞'],
    },
}

# 默认 Rubric (未注册类型的兜底)
_DEFAULT_RUBRIC = {
    'dimensions': {
        '知识准确性': {'weight': 25, 'desc': '内容是否准确无误'},
        '教学清晰度': {'weight': 25, 'desc': '信息是否清晰易懂'},
        '视觉美感':   {'weight': 20, 'desc': '配色/排版是否美观'},
        '可收藏感':   {'weight': 15, 'desc': '干货感/想截图保存'},
        '实用价值':   {'weight': 15, 'desc': '内容是否实用有价值'},
    },
    'must_have': [],
    'red_flags': [],
}

# 学科特有的审核重点
SUBJECT_FOCUS = {
    '数学': {
        'critical_checks': ['公式正确性', '计算结果验算', '步骤逻辑', '竖式对位'],
        'common_errors': ['分数运算符号', '小数点位置', '单位换算', '进位退位'],
        'grade_alignment': {
            '一上': '10以内加减法', '一下': '20以内加减法',
            '二上': '100以内加减法、认识乘法', '二下': '表内除法、万以内数',
            '三上': '万以内加减法、倍的认识', '三下': '两位数乘除法、面积',
            '四上': '大数认识、角的度量', '四下': '四则运算、小数',
            '五上': '小数乘除法、方程', '五下': '分数加减法、长方体',
            '六上': '分数乘除法、圆', '六下': '比例、数学广角',
        },
    },
    '语文': {
        'critical_checks': ['汉字笔顺', '拼音声调', '成语释义', '文言文翻译'],
        'common_errors': ['多音字声调', '形近字混淆', '成语误用', '标点符号'],
        'grade_alignment': {
            '一上': '拼音、基础汉字', '一下': '识字写字、简单课文',
            '二上': '看图写话、查字典', '二下': '阅读理解入门',
            '三上': '阅读概括、作文起步', '三下': '详写略写、修辞',
            '四上': '阅读感悟、缩写', '四下': '把事写清楚',
            '五上': '说明文、概括中心', '五下': '人物描写、表达方式',
            '六上': '文言文入门、小升初', '六下': '综合复习、小升初',
        },
    },
    '英语': {
        'critical_checks': ['语法正确性', '拼写准确', '时态一致', '中英翻译'],
        'common_errors': ['主谓一致', '时态混用', '介词搭配', 'there be句型'],
        'grade_alignment': {
            '三上': '字母、基础问候', '三下': '数字、颜色、动物',
            '四上': '教室/家庭词汇', '四下': '天气、时间',
            '五上': '日常活动、能力', '五下': '季节、生日',
            '六上': '方位、交通', '六下': '综合语法、小升初',
            '状语从句': '地点/方式/结果/让步状语从句语法',
        },
    },
    '养生': {
        'critical_checks': ['健康知识准确性', '安全性', '禁忌人群'],
        'common_errors': ['夸大效果', '忽略禁忌', '剂量不明'],
    },
    '国学': {
        'critical_checks': ['原文准确性', '出处核实', '释义准据性'],
        'common_errors': ['原文错字', '出处张冠李戴', '释义曲解'],
    },
    '情感': {
        'critical_checks': ['价值观导向', '建议可行性', '表达得体'],
        'common_errors': ['价值观偏差', '过度物化', '建议极端'],
    },
}


# ═══════════════════════════════════════════
# 数据库
# ═══════════════════════════════════════════
def _get_conn():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_quality_db():
    """创建内容质量系统所需的表"""
    conn = _get_conn()
    conn.executescript("""
        -- Level 1: 内容审核记录
        CREATE TABLE IF NOT EXISTS content_audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT NOT NULL,
            subject TEXT DEFAULT '',
            grade TEXT DEFAULT '',
            card_type TEXT DEFAULT '',
            -- 各维度评分
            dimension_scores TEXT DEFAULT '{}',
            -- 综合信息
            total_score REAL DEFAULT 0,
            must_have_pass INTEGER DEFAULT 1,
            red_flags_found TEXT DEFAULT '[]',
            improvement_suggestions TEXT DEFAULT '[]',
            verdict TEXT DEFAULT 'pass',
            audit_detail TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_ca_card ON content_audits(card_id);
        CREATE INDEX IF NOT EXISTS idx_ca_type ON content_audits(card_type);
        CREATE INDEX IF NOT EXISTS idx_ca_score ON content_audits(total_score DESC);

        -- Level 2: 内容模式库
        CREATE TABLE IF NOT EXISTS content_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,
            card_type TEXT DEFAULT '',
            subject TEXT DEFAULT '',
            pattern_description TEXT NOT NULL,
            evidence TEXT DEFAULT '{}',
            confidence REAL DEFAULT 0.5,
            usage_count INTEGER DEFAULT 0,
            effectiveness REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_cp_type ON content_patterns(pattern_type, card_type);

        -- Level 2: 失败归因记录
        CREATE TABLE IF NOT EXISTS failure_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT NOT NULL,
            card_type TEXT DEFAULT '',
            subject TEXT DEFAULT '',
            failure_category TEXT DEFAULT '',
            root_cause TEXT DEFAULT '',
            dimension_weakest TEXT DEFAULT '',
            score_before REAL DEFAULT 0,
            suggestion TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_fa_category ON failure_analysis(failure_category);

        -- Level 3: 质量趋势追踪
        CREATE TABLE IF NOT EXISTS quality_trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_type TEXT DEFAULT '',
            subject TEXT DEFAULT '',
            period TEXT DEFAULT '',
            avg_score REAL DEFAULT 0,
            sample_count INTEGER DEFAULT 0,
            top_dimension TEXT DEFAULT '',
            weakest_dimension TEXT DEFAULT '',
            improvement_rate REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_qt_period ON quality_trends(period);

        -- Level 2: 最佳实践指南
        CREATE TABLE IF NOT EXISTS style_guides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_type TEXT NOT NULL,
            subject TEXT DEFAULT '',
            guide_text TEXT NOT NULL,
            based_on_samples INTEGER DEFAULT 0,
            avg_score_of_samples REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_sg_type ON style_guides(card_type, subject);
    """)
    conn.commit()
    conn.close()
    print(f"[content_quality] DB initialized: {_DB_PATH}")


# 启动时自动初始化
init_quality_db()


# ═══════════════════════════════════════════
# Level 1: 内容审核引擎 (Content Audit Engine)
# ═══════════════════════════════════════════

def build_content_audit_prompt(card, card_type, subject, grade=''):
    """
    根据卡片类型和学科，构建分类型的内容审核 Prompt。
    返回让 Gemini 进行深度内容审核的 prompt 文本。
    """
    rubric = QUALITY_RUBRICS.get(card_type, _DEFAULT_RUBRIC)
    subject_info = SUBJECT_FOCUS.get(subject, {})

    # 构建维度评分说明
    dim_lines = []
    for name, detail in rubric['dimensions'].items():
        dim_lines.append(f"  - **{name}** (权重{detail['weight']}分): {detail['desc']}")
    dimensions_text = '\n'.join(dim_lines)

    # 必要元素
    must_have_text = ''
    if rubric.get('must_have'):
        must_have_text = '\n必要元素（缺失任一项严重扣分）：\n' + '\n'.join(f'  ✓ {m}' for m in rubric['must_have'])

    # 红线警告
    red_flags_text = ''
    if rubric.get('red_flags'):
        red_flags_text = '\n红线错误（触犯任一项直接不及格）：\n' + '\n'.join(f'  ⛔ {r}' for r in rubric['red_flags'])

    # 学科特有检查
    subject_checks = ''
    if subject_info:
        checks = subject_info.get('critical_checks', [])
        errors = subject_info.get('common_errors', [])
        grade_desc = subject_info.get('grade_alignment', {}).get(grade, '')
        if checks:
            subject_checks += f'\n{subject}学科重点检查项：\n' + '\n'.join(f'  🔍 {c}' for c in checks)
        if errors:
            subject_checks += f'\n{subject}常见错误类型：\n' + '\n'.join(f'  ⚠️ {e}' for e in errors)
        if grade_desc:
            subject_checks += f'\n年级课标范围: {grade} — {grade_desc}'
            subject_checks += f'\n⚠️ 超出此范围的内容应扣"课标匹配度"分'

    # 组装完整卡片信息
    card_info = json.dumps(card, ensure_ascii=False, indent=2)

    prompt = f"""你是一位资深的{subject}教育内容质量审核专家。

请对以下知识卡片进行**深度内容审核**。

== 卡片信息 ==
类型: {card_type}
学科: {subject}
年级: {grade}
完整数据:
{card_info}

== 评分维度（满分100分） ==
{dimensions_text}
{must_have_text}
{red_flags_text}
{subject_checks}

== 审核要求 ==
1. 逐维度打分，每维度满分为其权重分值
2. 检查所有「必要元素」是否齐全
3. 检查是否触犯任何「红线错误」
4. 给出具体的改进建议（至少2条）
5. 作出最终裁决: pass(≥75分) / needs_improvement(60-74) / reject(<60)

== 输出格式（纯JSON，不要代码块标记）==
{{
  "dimensions": {{
    "维度名": {{"score": 分数, "max": 满分, "comment": "简评"}},
    ...
  }},
  "total_score": 总分,
  "must_have_check": {{
    "all_present": true或false,
    "missing": ["缺失的元素"]
  }},
  "red_flags": ["触犯的红线，没有则空数组"],
  "knowledge_errors": ["发现的知识性错误，没有则空数组"],
  "improvements": ["改进建议1", "改进建议2", ...],
  "verdict": "pass|needs_improvement|reject",
  "summary": "一句话总评"
}}

只输出JSON。"""
    return prompt


def content_audit(card, card_type, subject, grade, api_key, all_keys=None):
    """
    Level 1: 对卡片数据进行内容质量审核（在生成图片之前）。
    返回审核结果字典。
    """
    import urllib.request, urllib.error

    prompt = build_content_audit_prompt(card, card_type, subject, grade)

    # 调用 Gemini API
    api_base = 'https://generativelanguage.googleapis.com/v1beta'
    model = 'gemini-2.5-flash'
    url = f'{api_base}/models/{model}:generateContent?key={api_key}'

    body = {
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {
            'maxOutputTokens': 4096,
            'temperature': 0.1,
            'thinkingConfig': {'thinkingBudget': 2048}
        }
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read())

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
                    result = json.loads(json_match.group())
                    # 持久化
                    _save_content_audit(card.get('full_id', card.get('id', '')),
                                       subject, grade, card_type, result)
                    return result
    except Exception as e:
        print(f'[content_audit] Error: {e}')

    return {
        'dimensions': {},
        'total_score': 0,
        'must_have_check': {'all_present': True, 'missing': []},
        'red_flags': [],
        'knowledge_errors': [],
        'improvements': [],
        'verdict': 'error',
        'summary': '审核调用失败',
    }


def _save_content_audit(card_id, subject, grade, card_type, result):
    """持久化内容审核结果"""
    try:
        conn = _get_conn()
        conn.execute("""
            INSERT INTO content_audits
            (card_id, subject, grade, card_type, dimension_scores, total_score,
             must_have_pass, red_flags_found, improvement_suggestions, verdict, audit_detail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            card_id, subject, grade, card_type,
            json.dumps(result.get('dimensions', {}), ensure_ascii=False),
            result.get('total_score', 0),
            1 if result.get('must_have_check', {}).get('all_present', True) else 0,
            json.dumps(result.get('red_flags', []), ensure_ascii=False),
            json.dumps(result.get('improvements', []), ensure_ascii=False),
            result.get('verdict', 'unknown'),
            json.dumps(result, ensure_ascii=False),
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'[content_audit] DB save error: {e}')


def build_content_refinement_hint(audit_result):
    """
    根据内容审核结果，生成注入到 Prompt 中的改进提示。
    这让图片生成时自动修正审核发现的问题。
    """
    if not audit_result or audit_result.get('verdict') == 'error':
        return ''

    lines = []

    # 知识性错误
    errors = audit_result.get('knowledge_errors', [])
    if errors:
        lines.append("⚠️ KNOWLEDGE CORRECTIONS (from content audit):")
        for err in errors[:5]:
            lines.append(f"  - FIX: {err}")

    # 缺失元素
    missing = audit_result.get('must_have_check', {}).get('missing', [])
    if missing:
        lines.append("📋 MISSING ELEMENTS (must include):")
        for m in missing:
            lines.append(f"  - ADD: {m}")

    # 改进建议
    improvements = audit_result.get('improvements', [])
    if improvements:
        lines.append("💡 QUALITY IMPROVEMENTS:")
        for imp in improvements[:3]:
            lines.append(f"  - {imp}")

    # 红线警告
    red_flags = audit_result.get('red_flags', [])
    if red_flags:
        lines.append("🚫 CRITICAL ISSUES TO FIX:")
        for rf in red_flags:
            lines.append(f"  - MUST FIX: {rf}")

    if lines:
        return '\n'.join(['', '=== CONTENT AUDIT FEEDBACK ==='] + lines + ['=== END FEEDBACK ===', ''])
    return ''


# ═══════════════════════════════════════════
# Level 1: 分类型质量评分 Prompt（替代原有笼统评分）
# ═══════════════════════════════════════════

def build_typed_quality_prompt(card_type, subject, card_title=''):
    """
    根据卡片类型生成精确的质量评分 Prompt。
    替代 v3.py 中的通用 QUALITY_PROMPT。
    """
    rubric = QUALITY_RUBRICS.get(card_type, _DEFAULT_RUBRIC)

    dim_lines = []
    dim_json_template = {}
    for name, detail in rubric['dimensions'].items():
        dim_lines.append(f"- **{name}**({detail['weight']}分): {detail['desc']}")
        dim_json_template[name] = {"score": 0, "max": detail['weight']}

    dimensions_text = '\n'.join(dim_lines)

    prompt = f"""你是{subject}知识卡片质量评审专家。请对这张「{card_type}」类型的卡片"{card_title}"进行精准评分。

评分维度（满分100分）：
{dimensions_text}

评分要求：
1. 严格按各维度权重打分，不要超过该维度的满分
2. 每个维度必须给出具体的扣分原因
3. 给出2-3条可执行的改进建议
4. 总分 = 各维度分数之和

输出纯JSON格式（不要代码块标记）：
{{
  "dimensions": {{
    "维度名": {{"score": 实际得分, "max": 满分, "reason": "评分理由"}},
    ...
  }},
  "total": 总分,
  "strengths": ["优点1", "优点2"],
  "improvements": ["可执行改进建议1", "可执行改进建议2"],
  "comment": "一句话总评"
}}

只输出JSON。"""
    return prompt


# ═══════════════════════════════════════════
# Level 2: 内容沉淀系统 (Content Distiller)
# ═══════════════════════════════════════════

def analyze_top_cards(card_type='', subject='', min_score=80, limit=20):
    """
    分析高分卡片的共同模式，提炼成功因素。
    """
    conn = _get_conn()
    query = """
        SELECT card_id, card_type, subject, dimension_scores, total_score,
               improvement_suggestions, verdict, audit_detail
        FROM content_audits
        WHERE total_score >= ?
    """
    params = [min_score]
    if card_type:
        query += " AND card_type = ?"
        params.append(card_type)
    if subject:
        query += " AND subject = ?"
        params.append(subject)
    query += " ORDER BY total_score DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        return {'patterns': [], 'sample_count': 0, 'avg_score': 0}

    # 分析维度得分分布
    dimension_totals = {}
    dimension_counts = {}

    for row in rows:
        dims = json.loads(row['dimension_scores'] or '{}')
        for dim_name, dim_data in dims.items():
            if dim_name not in dimension_totals:
                dimension_totals[dim_name] = 0
                dimension_counts[dim_name] = 0
            score = dim_data.get('score', dim_data) if isinstance(dim_data, dict) else dim_data
            dimension_totals[dim_name] += float(score)
            dimension_counts[dim_name] += 1

    # 找出强项维度（得分率最高）
    dim_rates = {}
    for dim in dimension_totals:
        if dimension_counts[dim] > 0:
            dim_rates[dim] = dimension_totals[dim] / dimension_counts[dim]

    sorted_dims = sorted(dim_rates.items(), key=lambda x: -x[1])
    strengths = [d[0] for d in sorted_dims[:3]]
    weaknesses = [d[0] for d in sorted_dims[-2:]]

    patterns = []
    if strengths:
        patterns.append({
            'type': 'strength_pattern',
            'description': f'高分卡片在「{"、".join(strengths)}」维度表现突出',
            'evidence': {d: round(dim_rates[d], 1) for d in strengths},
        })
    if weaknesses:
        patterns.append({
            'type': 'improvement_area',
            'description': f'即使高分卡片，「{"、".join(weaknesses)}」仍有提升空间',
            'evidence': {d: round(dim_rates[d], 1) for d in weaknesses},
        })

    avg_score = sum(r['total_score'] for r in rows) / len(rows)

    return {
        'patterns': patterns,
        'dimension_avg': {k: round(v, 1) for k, v in dim_rates.items()},
        'sample_count': len(rows),
        'avg_score': round(avg_score, 1),
        'strengths': strengths,
        'weaknesses': weaknesses,
    }


def analyze_failures(card_type='', subject='', max_score=60, limit=20):
    """
    分析低分卡片的失败原因，归纳典型问题。
    """
    conn = _get_conn()
    query = """
        SELECT card_id, card_type, subject, dimension_scores, total_score,
               red_flags_found, improvement_suggestions, verdict, audit_detail
        FROM content_audits
        WHERE total_score > 0 AND total_score <= ?
    """
    params = [max_score]
    if card_type:
        query += " AND card_type = ?"
        params.append(card_type)
    if subject:
        query += " AND subject = ?"
        params.append(subject)
    query += " ORDER BY total_score ASC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        return {'failure_patterns': [], 'sample_count': 0}

    # 统计最弱维度
    weak_dims = {}
    all_red_flags = []
    all_suggestions = []

    for row in rows:
        dims = json.loads(row['dimension_scores'] or '{}')
        # 找出每张卡最弱的维度
        if dims:
            weakest = min(dims.items(),
                         key=lambda x: (x[1].get('score', x[1]) / max(x[1].get('max', 1), 1))
                         if isinstance(x[1], dict) else x[1])
            dim_name = weakest[0]
            weak_dims[dim_name] = weak_dims.get(dim_name, 0) + 1

        flags = json.loads(row['red_flags_found'] or '[]')
        all_red_flags.extend(flags)

        sugs = json.loads(row['improvement_suggestions'] or '[]')
        all_suggestions.extend(sugs)

    # 归纳失败模式
    failure_patterns = []

    # 最常见的弱项维度
    if weak_dims:
        sorted_weak = sorted(weak_dims.items(), key=lambda x: -x[1])
        for dim, count in sorted_weak[:3]:
            failure_patterns.append({
                'category': 'weak_dimension',
                'dimension': dim,
                'frequency': count,
                'description': f'"{dim}"是低分卡片最常见的弱项（{count}/{len(rows)}张卡）',
            })

    # 最常见的红线错误
    if all_red_flags:
        from collections import Counter
        flag_counts = Counter(all_red_flags)
        for flag, count in flag_counts.most_common(3):
            failure_patterns.append({
                'category': 'red_flag',
                'issue': flag,
                'frequency': count,
                'description': f'红线错误"{flag}"出现{count}次',
            })

    # 保存分析结果
    for fp in failure_patterns:
        _save_failure_analysis(fp, card_type, subject)

    return {
        'failure_patterns': failure_patterns,
        'sample_count': len(rows),
        'top_suggestions': list(set(all_suggestions))[:5],
    }


def _save_failure_analysis(pattern, card_type, subject):
    """持久化失败归因"""
    try:
        conn = _get_conn()
        conn.execute("""
            INSERT INTO failure_analysis
            (card_id, card_type, subject, failure_category, root_cause, suggestion)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            'batch_analysis',
            card_type, subject,
            pattern.get('category', ''),
            pattern.get('description', ''),
            pattern.get('issue', pattern.get('dimension', '')),
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'[failure_analysis] DB error: {e}')


def generate_style_guide(card_type, subject='', api_key=None):
    """
    Level 2: 基于历史高分数据，自动生成该类型卡片的最佳实践指南。
    调用 AI 综合分析高分模式 + 低分教训 → 输出风格指南。
    """
    top_analysis = analyze_top_cards(card_type, subject)
    fail_analysis = analyze_failures(card_type, subject)
    rubric = QUALITY_RUBRICS.get(card_type, _DEFAULT_RUBRIC)

    if top_analysis['sample_count'] < 3:
        # 数据不够，使用预设 rubric 生成基础指南
        guide = _build_default_guide(card_type, rubric)
        _save_style_guide(card_type, subject, guide, 0, 0)
        return guide

    if not api_key:
        guide = _build_default_guide(card_type, rubric)
        _save_style_guide(card_type, subject, guide,
                         top_analysis['sample_count'], top_analysis['avg_score'])
        return guide

    import urllib.request
    # 用 AI 综合分析
    analysis_prompt = f"""基于以下数据分析，为「{card_type}」类型的{subject}知识卡片生成最佳实践指南。

高分卡片分析（{top_analysis['sample_count']}样本，均分{top_analysis['avg_score']}）：
- 强项维度: {top_analysis.get('strengths', [])}
- 各维度均分: {json.dumps(top_analysis.get('dimension_avg', {}), ensure_ascii=False)}
- 成功模式: {json.dumps(top_analysis.get('patterns', []), ensure_ascii=False)}

低分卡片分析（{fail_analysis['sample_count']}样本）：
- 失败模式: {json.dumps(fail_analysis.get('failure_patterns', []), ensure_ascii=False)}
- 改进建议: {fail_analysis.get('top_suggestions', [])}

评分标准: {json.dumps(rubric, ensure_ascii=False)}

请生成一份简洁有力的「{card_type}」制作指南（200-400字），包括：
1. 核心原则（3条）
2. 必做清单（5条）
3. 避坑指南（3条）
4. 评分重点

只输出指南文本，不要JSON。"""

    try:
        api_base = 'https://generativelanguage.googleapis.com/v1beta'
        model = 'gemini-2.5-flash'
        url = f'{api_base}/models/{model}:generateContent?key={api_key}'
        body = {
            'contents': [{'role': 'user', 'parts': [{'text': analysis_prompt}]}],
            'generationConfig': {
                'maxOutputTokens': 2048,
                'temperature': 0.3,
                'thinkingConfig': {'thinkingBudget': 1024}
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read())
        candidates = data.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            for part in parts:
                if 'text' in part and not part.get('thought', False):
                    guide = part['text'].strip()
                    _save_style_guide(card_type, subject, guide,
                                     top_analysis['sample_count'], top_analysis['avg_score'])
                    return guide
    except Exception as e:
        print(f'[style_guide] AI generation error: {e}')

    guide = _build_default_guide(card_type, rubric)
    _save_style_guide(card_type, subject, guide,
                     top_analysis['sample_count'], top_analysis['avg_score'])
    return guide


def _build_default_guide(card_type, rubric):
    """当数据不足时，基于 rubric 构建默认指南"""
    lines = [f"=== {card_type} 最佳实践指南 ===\n"]

    lines.append("【核心原则】")
    dims = list(rubric['dimensions'].items())
    sorted_dims = sorted(dims, key=lambda x: -x[1]['weight'])
    for i, (name, detail) in enumerate(sorted_dims[:3], 1):
        lines.append(f"  {i}. {name}优先（权重{detail['weight']}%）: {detail['desc']}")

    if rubric.get('must_have'):
        lines.append("\n【必做清单】")
        for m in rubric['must_have']:
            lines.append(f"  ✓ 必须包含: {m}")

    if rubric.get('red_flags'):
        lines.append("\n【避坑指南】")
        for r in rubric['red_flags']:
            lines.append(f"  ⛔ 避免: {r}")

    lines.append(f"\n【评分标准】满分100分")
    for name, detail in rubric['dimensions'].items():
        lines.append(f"  {name}: {detail['weight']}分")

    return '\n'.join(lines)


def _save_style_guide(card_type, subject, guide_text, sample_count, avg_score):
    """持久化最佳实践指南"""
    try:
        conn = _get_conn()
        # Upsert
        existing = conn.execute(
            "SELECT id FROM style_guides WHERE card_type = ? AND subject = ?",
            (card_type, subject)
        ).fetchone()
        if existing:
            conn.execute("""
                UPDATE style_guides
                SET guide_text = ?, based_on_samples = ?, avg_score_of_samples = ?,
                    updated_at = datetime('now','localtime')
                WHERE id = ?
            """, (guide_text, sample_count, avg_score, existing['id']))
        else:
            conn.execute("""
                INSERT INTO style_guides
                (card_type, subject, guide_text, based_on_samples, avg_score_of_samples)
                VALUES (?, ?, ?, ?, ?)
            """, (card_type, subject, guide_text, sample_count, avg_score))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'[style_guide] DB error: {e}')


def get_style_guide(card_type, subject=''):
    """获取某类型的最佳实践指南"""
    conn = _get_conn()
    row = conn.execute(
        "SELECT guide_text, based_on_samples, avg_score_of_samples, updated_at "
        "FROM style_guides WHERE card_type = ? AND subject = ? ORDER BY id DESC LIMIT 1",
        (card_type, subject)
    ).fetchone()
    conn.close()
    if row:
        return {
            'guide': row['guide_text'],
            'based_on': row['based_on_samples'],
            'avg_score': row['avg_score_of_samples'],
            'updated': row['updated_at'],
        }
    # 没有存储的，生成默认
    rubric = QUALITY_RUBRICS.get(card_type, _DEFAULT_RUBRIC)
    return {
        'guide': _build_default_guide(card_type, rubric),
        'based_on': 0,
        'avg_score': 0,
        'updated': None,
    }


def cross_pollinate(from_type, to_type, subject=''):
    """
    Level 2: 跨类型策略迁移。
    分析 from_type 的成功模式，迁移可复用策略到 to_type。
    """
    source = analyze_top_cards(from_type, subject)
    target_rubric = QUALITY_RUBRICS.get(to_type, _DEFAULT_RUBRIC)

    if source['sample_count'] < 3:
        return {'transferable': [], 'message': f'{from_type}数据不足，无法迁移'}

    # 找出 from_type 的强项维度
    source_strengths = source.get('strengths', [])
    target_dims = set(target_rubric['dimensions'].keys())

    # 迁移可复用的维度策略
    transferable = []
    for s in source_strengths:
        if s in target_dims:
            transferable.append({
                'dimension': s,
                'source_score': source.get('dimension_avg', {}).get(s, 0),
                'message': f'"{from_type}"在"{s}"维度得分{source["dimension_avg"].get(s, 0):.0f},'
                          f'可参考其策略提升"{to_type}"的同维度表现',
            })

    # 保存迁移建议
    if transferable:
        try:
            conn = _get_conn()
            conn.execute("""
                INSERT INTO content_patterns
                (pattern_type, card_type, subject, pattern_description, evidence, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                'cross_pollinate',
                to_type, subject,
                f'从{from_type}迁移策略: {", ".join(t["dimension"] for t in transferable)}',
                json.dumps(transferable, ensure_ascii=False),
                0.6,
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f'[cross_pollinate] DB error: {e}')

    return {
        'transferable': transferable,
        'source_type': from_type,
        'target_type': to_type,
        'source_sample_count': source['sample_count'],
    }


# ═══════════════════════════════════════════
# Level 3: 质量趋势追踪
# ═══════════════════════════════════════════

def compute_quality_trends(card_type='', subject='', days=7):
    """
    计算最近N天的质量趋势，并保存快照。
    """
    conn = _get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    query = """
        SELECT card_type, subject, dimension_scores, total_score, created_at
        FROM content_audits
        WHERE total_score > 0 AND created_at >= ?
    """
    params = [cutoff]
    if card_type:
        query += " AND card_type = ?"
        params.append(card_type)
    if subject:
        query += " AND subject = ?"
        params.append(subject)
    query += " ORDER BY created_at"

    rows = conn.execute(query, params).fetchall()

    # 也获取更早的数据用于计算改进率
    prev_cutoff = (datetime.now() - timedelta(days=days*2)).strftime('%Y-%m-%d')
    prev_query = """
        SELECT AVG(total_score) as prev_avg
        FROM content_audits
        WHERE total_score > 0 AND created_at >= ? AND created_at < ?
    """
    prev_params = [prev_cutoff, cutoff]
    if card_type:
        prev_query += " AND card_type = ?"
        prev_params.append(card_type)
    if subject:
        prev_query += " AND subject = ?"
        prev_params.append(subject)

    prev_row = conn.execute(prev_query, prev_params).fetchone()
    prev_avg = prev_row['prev_avg'] if prev_row and prev_row['prev_avg'] else 0
    conn.close()

    if not rows:
        return {'period': f'last_{days}_days', 'sample_count': 0, 'avg_score': 0}

    scores = [r['total_score'] for r in rows]
    avg_score = sum(scores) / len(scores)

    # 分析各维度的强弱
    dim_totals = {}
    dim_counts = {}
    for row in rows:
        dims = json.loads(row['dimension_scores'] or '{}')
        for dim_name, dim_data in dims.items():
            if dim_name not in dim_totals:
                dim_totals[dim_name] = 0
                dim_counts[dim_name] = 0
            score = dim_data.get('score', dim_data) if isinstance(dim_data, dict) else dim_data
            dim_totals[dim_name] += float(score)
            dim_counts[dim_name] += 1

    dim_avgs = {}
    for d in dim_totals:
        if dim_counts[d] > 0:
            dim_avgs[d] = dim_totals[d] / dim_counts[d]

    top_dim = max(dim_avgs.items(), key=lambda x: x[1])[0] if dim_avgs else ''
    weak_dim = min(dim_avgs.items(), key=lambda x: x[1])[0] if dim_avgs else ''
    improvement_rate = ((avg_score - prev_avg) / max(prev_avg, 1)) * 100 if prev_avg > 0 else 0

    period = f'last_{days}_days'
    trend = {
        'period': period,
        'sample_count': len(rows),
        'avg_score': round(avg_score, 1),
        'prev_avg_score': round(prev_avg, 1),
        'improvement_rate': round(improvement_rate, 1),
        'top_dimension': top_dim,
        'weakest_dimension': weak_dim,
        'dimension_avgs': {k: round(v, 1) for k, v in dim_avgs.items()},
        'score_range': [min(scores), max(scores)],
    }

    # 保存趋势快照
    try:
        conn = _get_conn()
        conn.execute("""
            INSERT INTO quality_trends
            (card_type, subject, period, avg_score, sample_count,
             top_dimension, weakest_dimension, improvement_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            card_type or 'all', subject or 'all', period,
            avg_score, len(rows), top_dim, weak_dim, improvement_rate,
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'[quality_trends] DB error: {e}')

    return trend


# ═══════════════════════════════════════════
# 综合 Dashboard
# ═══════════════════════════════════════════

def get_quality_dashboard():
    """返回完整的内容质量系统仪表盘数据"""
    conn = _get_conn()

    total_audits = conn.execute("SELECT COUNT(*) FROM content_audits").fetchone()[0]
    total_patterns = conn.execute("SELECT COUNT(*) FROM content_patterns").fetchone()[0]
    total_failures = conn.execute("SELECT COUNT(*) FROM failure_analysis").fetchone()[0]
    total_guides = conn.execute("SELECT COUNT(*) FROM style_guides").fetchone()[0]

    # 各裁决分布
    verdict_dist = conn.execute("""
        SELECT verdict, COUNT(*) as count
        FROM content_audits
        GROUP BY verdict
    """).fetchall()

    # 按卡片类型的均分
    type_scores = conn.execute("""
        SELECT card_type, COUNT(*) as count,
               ROUND(AVG(total_score), 1) as avg_score,
               MIN(total_score) as min_score,
               MAX(total_score) as max_score
        FROM content_audits
        WHERE total_score > 0
        GROUP BY card_type
        ORDER BY avg_score DESC
    """).fetchall()

    # 最近10次审核
    recent = conn.execute("""
        SELECT card_id, card_type, subject, total_score, verdict,
               improvement_suggestions, created_at
        FROM content_audits
        ORDER BY id DESC
        LIMIT 10
    """).fetchall()

    conn.close()

    return {
        'summary': {
            'total_audits': total_audits,
            'total_patterns': total_patterns,
            'total_failure_analyses': total_failures,
            'total_style_guides': total_guides,
        },
        'verdict_distribution': {r['verdict']: r['count'] for r in verdict_dist},
        'type_scores': [dict(r) for r in type_scores],
        'recent_audits': [dict(r) for r in recent],
        'rubric_types_registered': list(QUALITY_RUBRICS.keys()),
    }


def get_rubric_for_type(card_type):
    """获取某卡片类型的评分标准"""
    return QUALITY_RUBRICS.get(card_type, _DEFAULT_RUBRIC)


# ═══════════════════════════════════════════
# 便捷: 完整审核+评分流程
# ═══════════════════════════════════════════

def full_quality_check(card, card_type, subject, grade, api_key, all_keys=None):
    """
    一次性执行完整的质量检查流程:
    1. 内容审核（知识准确性、必要元素、红线检查）
    2. 生成改进提示（注入到 prompt 生成环节）
    3. 返回审核结果 + 改进提示

    适合在 generate_image_prompt() 之前调用。
    """
    # Step 1: 内容审核
    audit = content_audit(card, card_type, subject, grade, api_key, all_keys)

    # Step 2: 生成改进提示
    refinement_hint = build_content_refinement_hint(audit)

    # Step 3: 获取该类型的最佳实践指南
    guide_data = get_style_guide(card_type, subject)
    style_hint = ''
    if guide_data.get('guide') and guide_data.get('based_on', 0) >= 3:
        # 只在有足够样本支撑时注入指南
        style_hint = f"\n=== STYLE GUIDE (from {guide_data['based_on']} high-scoring samples) ===\n"
        style_hint += guide_data['guide'][:500]
        style_hint += "\n=== END STYLE GUIDE ===\n"

    return {
        'audit': audit,
        'verdict': audit.get('verdict', 'error'),
        'total_score': audit.get('total_score', 0),
        'refinement_hint': refinement_hint,
        'style_hint': style_hint,
        'should_proceed': audit.get('verdict') != 'reject',
    }


# ═══════════════════════════════════════════
# 初始化默认风格指南
# ═══════════════════════════════════════════

def bootstrap_default_guides():
    """为所有已注册的卡片类型生成默认指南（首次运行时）"""
    conn = _get_conn()
    existing = conn.execute("SELECT COUNT(*) FROM style_guides").fetchone()[0]
    conn.close()

    if existing > 0:
        return  # 已有数据，跳过

    print('[content_quality] Bootstrapping default style guides...')
    for card_type, rubric in QUALITY_RUBRICS.items():
        guide = _build_default_guide(card_type, rubric)
        _save_style_guide(card_type, '', guide, 0, 0)
    print(f'[content_quality] Created {len(QUALITY_RUBRICS)} default guides.')


# 启动时自动创建默认指南
bootstrap_default_guides()
