#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自我优化系统 (Self-Optimization System)
========================================
三大子系统:
  1. Prompt Memory Bank — 记忆历史 Prompt + 评分，高分 Prompt 作为 few-shot 参考
  2. Error Dictionary   — 积累易出错汉字/组合，自动强化提示
  3. Adaptive Params    — 根据历史成功率自适应调节参数(温度、字数上限、重试次数)

存储: SQLite (与主系统同 DB 或独立 optimizer.db)
接口: 纯函数式，可被 generate_card_images_v3.py 和 server.py 调用
"""

import json, os, sqlite3, time, statistics
from datetime import datetime

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH = os.path.join(_BASE_DIR, 'optimizer.db')

# Prompt Memory Bank 配置
TOP_K_PROMPTS = 3              # few-shot 参考数量
MIN_SCORE_FOR_MEMORY = 75      # 仅记住≥此分的 prompt

# Error Dictionary 配置
ERROR_BOOST_THRESHOLD = 2      # 某字出错≥此次数 → 自动强化
MAX_ERROR_HINTS = 10           # 注入提示最多几条

# Adaptive Params 配置
ADAPT_WINDOW = 50              # 计算自适应参数的样本窗口
DEFAULT_PARAMS = {
    'max_chinese_chars': 15,
    'max_chars_per_block': 4,
    'audit_pass_score': 80,
    'max_audit_rounds': 3,
    'temperature': 0.4,
}

# ═══════════════════════════════════════════
# 数据库初始化
# ═══════════════════════════════════════════
def _get_conn():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_optimizer_db():
    """创建优化系统所需的表"""
    conn = _get_conn()
    conn.executescript("""
        -- 1. Prompt Memory Bank: 记录每次生成的 prompt + 分数
        CREATE TABLE IF NOT EXISTS prompt_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            grade TEXT DEFAULT '',
            card_type TEXT DEFAULT '',
            prompt_text TEXT NOT NULL,
            manifest_json TEXT DEFAULT '{}',
            audit_score INTEGER DEFAULT 0,
            quality_score INTEGER DEFAULT 0,
            combined_score REAL DEFAULT 0,
            image_model TEXT DEFAULT '',
            audit_rounds INTEGER DEFAULT 1,
            final_action TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_pm_subject ON prompt_memory(subject);
        CREATE INDEX IF NOT EXISTS idx_pm_combined ON prompt_memory(combined_score DESC);
        CREATE INDEX IF NOT EXISTS idx_pm_card_type ON prompt_memory(card_type);

        -- 2. Error Dictionary: 记录每次 OCR 审计中出错的字符
        CREATE TABLE IF NOT EXISTS error_dictionary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            char_text TEXT NOT NULL,
            expected TEXT NOT NULL,
            actual TEXT DEFAULT '',
            error_type TEXT DEFAULT 'garbled',
            severity TEXT DEFAULT 'high',
            subject TEXT DEFAULT '',
            image_model TEXT DEFAULT '',
            occurrence_count INTEGER DEFAULT 1,
            last_seen TEXT DEFAULT (datetime('now','localtime')),
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_ed_char ON error_dictionary(char_text);
        CREATE INDEX IF NOT EXISTS idx_ed_count ON error_dictionary(occurrence_count DESC);

        -- 3. Generation Stats: 每次生成的完整统计
        CREATE TABLE IF NOT EXISTS generation_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT NOT NULL,
            subject TEXT DEFAULT '',
            grade TEXT DEFAULT '',
            audit_score INTEGER DEFAULT 0,
            quality_score INTEGER DEFAULT 0,
            audit_rounds INTEGER DEFAULT 1,
            image_model TEXT DEFAULT '',
            final_action TEXT DEFAULT '',
            prompt_length INTEGER DEFAULT 0,
            image_size_kb REAL DEFAULT 0,
            elapsed_seconds REAL DEFAULT 0,
            success INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_gs_created ON generation_stats(created_at);
        CREATE INDEX IF NOT EXISTS idx_gs_subject ON generation_stats(subject);

        -- 4. Adaptive Params: 当前自适应参数快照
        CREATE TABLE IF NOT EXISTS adaptive_params (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            param_key TEXT UNIQUE NOT NULL,
            param_value REAL NOT NULL,
            reason TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    conn.commit()
    conn.close()
    print(f"[self_optimizer] DB initialized: {_DB_PATH}")

# 启动时自动初始化
init_optimizer_db()


# ═══════════════════════════════════════════
# 1. Prompt Memory Bank
# ═══════════════════════════════════════════
def record_prompt(card_id, subject, grade, card_type, prompt_text, manifest,
                  audit_score, quality_score, image_model='', audit_rounds=1, final_action=''):
    """记录一次 prompt 生成结果到记忆库"""
    combined = audit_score * 0.5 + quality_score * 0.5
    if combined < MIN_SCORE_FOR_MEMORY:
        return  # 分数太低不值得记忆

    conn = _get_conn()
    conn.execute("""
        INSERT INTO prompt_memory 
        (card_id, subject, grade, card_type, prompt_text, manifest_json,
         audit_score, quality_score, combined_score, image_model, audit_rounds, final_action)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        card_id, subject, grade, card_type, prompt_text,
        json.dumps(manifest or {}, ensure_ascii=False),
        audit_score, quality_score, combined,
        image_model, audit_rounds, final_action
    ))
    conn.commit()
    conn.close()


def get_top_prompts(subject, card_type='', limit=None):
    """获取某学科/卡片类型的高分 prompt 作为 few-shot 参考"""
    limit = limit or TOP_K_PROMPTS
    conn = _get_conn()
    if card_type:
        rows = conn.execute("""
            SELECT prompt_text, audit_score, quality_score, combined_score, card_id
            FROM prompt_memory
            WHERE subject = ? AND card_type = ?
            ORDER BY combined_score DESC
            LIMIT ?
        """, (subject, card_type, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT prompt_text, audit_score, quality_score, combined_score, card_id
            FROM prompt_memory
            WHERE subject = ?
            ORDER BY combined_score DESC
            LIMIT ?
        """, (subject, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_fewshot_hint(subject, card_type=''):
    """构建 few-shot 参考提示（注入到 prompt 生成环节）"""
    top = get_top_prompts(subject, card_type)
    if not top:
        return ''

    lines = ["=== HIGH-SCORING PROMPT EXAMPLES (for reference, DO NOT copy directly) ==="]
    for i, p in enumerate(top, 1):
        # 只取前500字，避免太长
        snippet = p['prompt_text'][:500]
        lines.append(f"Example {i} (score={p['combined_score']:.0f}):\n{snippet}\n---")
    lines.append("=== END EXAMPLES === Use similar style and structure.\n")
    return '\n'.join(lines)


# ═══════════════════════════════════════════
# 2. Error Dictionary
# ═══════════════════════════════════════════
def record_errors(audit_result, subject='', image_model=''):
    """从 OCR 审计结果中提取出错字符并记录"""
    errors = audit_result.get('errors', [])
    if not errors:
        return

    conn = _get_conn()
    for err in errors:
        expected = err.get('expected', '')
        actual = err.get('actual', '')
        severity = err.get('severity', 'low')
        error_type = err.get('type', 'unknown')

        if not expected:
            continue

        # 逐字记录出错的汉字
        for ch in expected:
            if '\u4e00' <= ch <= '\u9fff':
                existing = conn.execute(
                    "SELECT id, occurrence_count FROM error_dictionary WHERE char_text = ? AND subject = ?",
                    (ch, subject)
                ).fetchone()
                if existing:
                    conn.execute("""
                        UPDATE error_dictionary 
                        SET occurrence_count = occurrence_count + 1,
                            last_seen = datetime('now','localtime'),
                            actual = ?,
                            error_type = ?,
                            severity = ?,
                            image_model = ?
                        WHERE id = ?
                    """, (actual, error_type, severity, image_model, existing['id']))
                else:
                    conn.execute("""
                        INSERT INTO error_dictionary 
                        (char_text, expected, actual, error_type, severity, subject, image_model)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (ch, expected, actual, error_type, severity, subject, image_model))
    conn.commit()
    conn.close()


def get_frequent_errors(subject='', min_count=None):
    """获取高频出错字符"""
    min_count = min_count or ERROR_BOOST_THRESHOLD
    conn = _get_conn()
    if subject:
        rows = conn.execute("""
            SELECT char_text, occurrence_count, error_type, expected, actual
            FROM error_dictionary
            WHERE subject = ? AND occurrence_count >= ?
            ORDER BY occurrence_count DESC
            LIMIT ?
        """, (subject, min_count, MAX_ERROR_HINTS)).fetchall()
    else:
        rows = conn.execute("""
            SELECT char_text, occurrence_count, error_type, expected, actual
            FROM error_dictionary
            WHERE occurrence_count >= ?
            ORDER BY occurrence_count DESC
            LIMIT ?
        """, (min_count, MAX_ERROR_HINTS)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_error_boost_hint(subject='', manifest=None):
    """
    构建易错字符强化提示。
    如果当前 manifest 包含高频出错字符，生成针对性警告。
    """
    frequent = get_frequent_errors(subject)
    if not frequent or not manifest:
        return ''

    # 找出 manifest 中包含的高频易错字符
    all_text = ''.join(manifest.values())
    risky_chars = []
    for err in frequent:
        ch = err['char_text']
        if ch in all_text:
            risky_chars.append(err)

    if not risky_chars:
        return ''

    lines = ["\n⚠️ HISTORICALLY PROBLEMATIC CHARACTERS (pay extra attention):"]
    for rc in risky_chars[:8]:
        ch = rc['char_text']
        count = rc['occurrence_count']
        lines.append(
            f'  - Character "{ch}" (U+{ord(ch):04X}) has been rendered incorrectly {count} times before. '
            f'Use EXTRA thick strokes and verify it is EXACTLY "{ch}".'
        )
    lines.append("Render these characters with maximum care and precision.\n")
    return '\n'.join(lines)


# ═══════════════════════════════════════════
# 3. Generation Stats & Adaptive Params
# ═══════════════════════════════════════════
def record_generation(card_id, subject='', grade='', audit_score=0, quality_score=0,
                      audit_rounds=1, image_model='', final_action='',
                      prompt_length=0, image_size_kb=0, elapsed_seconds=0, success=True):
    """记录一次完整的生成统计"""
    conn = _get_conn()
    conn.execute("""
        INSERT INTO generation_stats
        (card_id, subject, grade, audit_score, quality_score, audit_rounds,
         image_model, final_action, prompt_length, image_size_kb, elapsed_seconds, success)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        card_id, subject, grade, audit_score, quality_score, audit_rounds,
        image_model, final_action, prompt_length, image_size_kb, elapsed_seconds,
        1 if success else 0
    ))
    conn.commit()
    conn.close()


def get_stats_summary(window=None):
    """获取最近 N 次生成的统计摘要"""
    window = window or ADAPT_WINDOW
    conn = _get_conn()
    rows = conn.execute("""
        SELECT audit_score, quality_score, audit_rounds, success,
               final_action, image_model, elapsed_seconds, subject
        FROM generation_stats
        ORDER BY id DESC
        LIMIT ?
    """, (window,)).fetchall()
    conn.close()

    if not rows:
        return {
            'total_records': 0,
            'success_rate': 0,
            'avg_audit': 0,
            'avg_quality': 0,
            'avg_rounds': 0,
            'avg_elapsed': 0,
            'pass_rate': 0,
            'repair_rate': 0,
            'model_stats': {},
        }

    data = [dict(r) for r in rows]
    success_count = sum(1 for d in data if d['success'])
    audit_scores = [d['audit_score'] for d in data if d['audit_score'] > 0]
    quality_scores = [d['quality_score'] for d in data if d['quality_score'] > 0]
    rounds = [d['audit_rounds'] for d in data]
    elapsed = [d['elapsed_seconds'] for d in data if d['elapsed_seconds'] > 0]

    pass_count = sum(1 for d in data if d['final_action'] == 'pass')
    repair_count = sum(1 for d in data if d['final_action'] == 'repaired')

    # 按模型分组统计
    model_stats = {}
    for d in data:
        m = d['image_model'] or 'unknown'
        if m not in model_stats:
            model_stats[m] = {'count': 0, 'avg_audit': 0, 'scores': []}
        model_stats[m]['count'] += 1
        if d['audit_score'] > 0:
            model_stats[m]['scores'].append(d['audit_score'])
    for m in model_stats:
        scores = model_stats[m]['scores']
        model_stats[m]['avg_audit'] = sum(scores) / len(scores) if scores else 0
        del model_stats[m]['scores']

    return {
        'total_records': len(data),
        'success_rate': round(success_count / len(data) * 100, 1),
        'avg_audit': round(sum(audit_scores) / len(audit_scores), 1) if audit_scores else 0,
        'avg_quality': round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else 0,
        'avg_rounds': round(sum(rounds) / len(rounds), 2) if rounds else 0,
        'avg_elapsed': round(sum(elapsed) / len(elapsed), 1) if elapsed else 0,
        'pass_rate': round(pass_count / len(data) * 100, 1),
        'repair_rate': round(repair_count / len(data) * 100, 1),
        'model_stats': model_stats,
    }


def compute_adaptive_params():
    """
    根据历史数据自适应计算最优参数。
    
    策略:
    - 如果 avg_audit ≥ 90: 可以放宽字数限制 (+2)，减少重试 (-1)
    - 如果 avg_audit < 70: 收紧字数限制 (-2)，增加重试 (+1)
    - 如果 repair_rate > 30%: 提高审计阈值 (+5)
    - 如果 pass_rate > 90%: 可以适当降低审计阈值 (-3)
    """
    stats = get_stats_summary()
    if stats['total_records'] < 10:
        return DEFAULT_PARAMS.copy()  # 数据不够，用默认值

    params = DEFAULT_PARAMS.copy()
    avg_audit = stats['avg_audit']
    pass_rate = stats['pass_rate']
    repair_rate = stats['repair_rate']

    # 自适应字数限制
    if avg_audit >= 90:
        params['max_chinese_chars'] = min(20, params['max_chinese_chars'] + 2)
        params['max_chars_per_block'] = min(6, params['max_chars_per_block'] + 1)
    elif avg_audit < 70:
        params['max_chinese_chars'] = max(10, params['max_chinese_chars'] - 2)
        params['max_chars_per_block'] = max(3, params['max_chars_per_block'] - 1)

    # 自适应审计阈值
    if repair_rate > 30:
        params['audit_pass_score'] = min(90, params['audit_pass_score'] + 5)
    elif pass_rate > 90:
        params['audit_pass_score'] = max(70, params['audit_pass_score'] - 3)

    # 自适应重试次数
    if avg_audit >= 85 and pass_rate > 80:
        params['max_audit_rounds'] = max(2, params['max_audit_rounds'] - 1)
    elif avg_audit < 65:
        params['max_audit_rounds'] = min(5, params['max_audit_rounds'] + 1)

    # 保存参数快照
    _save_adaptive_params(params)
    return params


def _save_adaptive_params(params):
    """持久化自适应参数"""
    conn = _get_conn()
    for k, v in params.items():
        conn.execute("""
            INSERT INTO adaptive_params (param_key, param_value, updated_at)
            VALUES (?, ?, datetime('now','localtime'))
            ON CONFLICT(param_key) DO UPDATE SET
                param_value = excluded.param_value,
                updated_at = excluded.updated_at
        """, (k, float(v)))
    conn.commit()
    conn.close()


def get_adaptive_params():
    """读取最新的自适应参数（如无则返回默认值）"""
    conn = _get_conn()
    rows = conn.execute("SELECT param_key, param_value FROM adaptive_params").fetchall()
    conn.close()
    if not rows:
        return DEFAULT_PARAMS.copy()
    params = DEFAULT_PARAMS.copy()
    for r in rows:
        if r['param_key'] in params:
            params[r['param_key']] = r['param_value']
    # 确保整数类型
    for k in ('max_chinese_chars', 'max_chars_per_block', 'audit_pass_score', 'max_audit_rounds'):
        if k in params:
            params[k] = int(params[k])
    return params


# ═══════════════════════════════════════════
# 综合 Dashboard / 统计 API
# ═══════════════════════════════════════════
def get_optimizer_dashboard():
    """返回完整的优化系统仪表盘数据"""
    conn = _get_conn()

    # 总记录数
    total_prompts = conn.execute("SELECT COUNT(*) FROM prompt_memory").fetchone()[0]
    total_errors = conn.execute("SELECT COUNT(*) FROM error_dictionary").fetchone()[0]
    total_generations = conn.execute("SELECT COUNT(*) FROM generation_stats").fetchone()[0]

    # Top 10 易错字符
    top_errors = conn.execute("""
        SELECT char_text, occurrence_count, error_type, last_seen
        FROM error_dictionary
        ORDER BY occurrence_count DESC
        LIMIT 10
    """).fetchall()

    # 最近10次生成
    recent = conn.execute("""
        SELECT card_id, subject, audit_score, quality_score, 
               audit_rounds, final_action, image_model, created_at
        FROM generation_stats
        ORDER BY id DESC
        LIMIT 10
    """).fetchall()

    # 按学科统计
    subject_stats = conn.execute("""
        SELECT subject, 
               COUNT(*) as count,
               ROUND(AVG(audit_score), 1) as avg_audit,
               ROUND(AVG(quality_score), 1) as avg_quality
        FROM generation_stats
        WHERE audit_score > 0
        GROUP BY subject
        ORDER BY count DESC
    """).fetchall()

    conn.close()

    return {
        'summary': {
            'total_prompts_memorized': total_prompts,
            'total_error_chars_tracked': total_errors,
            'total_generations_recorded': total_generations,
        },
        'stats': get_stats_summary(),
        'adaptive_params': get_adaptive_params(),
        'top_error_chars': [dict(r) for r in top_errors],
        'recent_generations': [dict(r) for r in recent],
        'subject_stats': [dict(r) for r in subject_stats],
    }


def reset_optimizer():
    """重置优化系统（清空所有学习数据）"""
    conn = _get_conn()
    conn.executescript("""
        DELETE FROM prompt_memory;
        DELETE FROM error_dictionary;
        DELETE FROM generation_stats;
        DELETE FROM adaptive_params;
    """)
    conn.commit()
    conn.close()
    print("[self_optimizer] All learning data reset.")


# ═══════════════════════════════════════════
# 便捷: 一次性记录完整结果
# ═══════════════════════════════════════════
def record_full_result(card_id, subject, grade, card_type, prompt_text, manifest,
                       audit_score, quality_score, audit_result=None,
                       image_model='', audit_rounds=1, final_action='',
                       prompt_length=0, image_size_kb=0, elapsed_seconds=0, success=True):
    """
    一次性记录到所有子系统:
    - Prompt Memory Bank
    - Error Dictionary  
    - Generation Stats
    并触发自适应参数重算（每10次）
    """
    # 1. 记录 prompt
    record_prompt(card_id, subject, grade, card_type, prompt_text, manifest,
                  audit_score, quality_score, image_model, audit_rounds, final_action)

    # 2. 记录出错字符
    if audit_result:
        record_errors(audit_result, subject=subject, image_model=image_model)

    # 3. 记录生成统计
    record_generation(card_id, subject, grade, audit_score, quality_score,
                      audit_rounds, image_model, final_action,
                      prompt_length, image_size_kb, elapsed_seconds, success)

    # 4. 每10次自动重算自适应参数
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM generation_stats").fetchone()[0]
    conn.close()
    if total % 10 == 0:
        compute_adaptive_params()
        print(f"[self_optimizer] 自适应参数已更新 (第{total}次生成)")
