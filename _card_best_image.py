"""
v10.9.9: 卡片最优图+最优Prompt缓存 — Warm-Start 渐进式精修
============================================================
为每张卡片保存历史最优图片 + 产出该图的最优 prompt，
后续生成时可以：
  1. 复用最优 prompt（跳过 Step1 prompt 生成 API 调用）
  2. 在最优图基础上做 image-to-image 精修

存储方式:
  - 图片文件:  card_best_images/{card_id}.{ext}   (文件系统)
  - Prompt:   card_best_images/{card_id}.prompt    (文件系统)
  - 元数据:    optimizer.db → card_best_images 表  (SQLite)

Pipeline 集成点:
  - Step 1.5: 加载历史最优图+Prompt (get_best_cache)
  - Step 7:   保存/更新最优图+Prompt (save_best_cache)

策略:
  ┌────────────────────────┬──────────────────────────────────────────────┐
  │ 缓存状态               │ Pipeline 执行策略                            │
  ├────────────────────────┼──────────────────────────────────────────────┤
  │ 无缓存                 │ Step1生成prompt → Step2-4从头生成             │
  │ 有缓存 score < 60      │ 复用缓存prompt → Step2-4从头生成, 结束取更优   │
  │ 有缓存 60 ≤ s < 85     │ 复用缓存prompt → 缩减轮数=1, 结束取更优       │
  │ 有缓存 score ≥ 85      │ 复用缓存prompt → 跳过从头生成, 直接精修缓存图   │
  │ manifest 变化          │ 重新走Step1生成prompt, 图片缓存失效            │
  └────────────────────────┴──────────────────────────────────────────────┘
"""

import os
import json
import hashlib
import sqlite3
import time

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'optimizer.db')
_IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'card_best_images')

# ── 阈值配置 ──
WARM_START_THRESHOLD = 60       # 缓存分 >= 此值时才启用 warm-start
WARM_START_SKIP_FRESH = 85      # 缓存分 >= 此值时可跳过从头生成, 直接精修


def _ensure_dir():
    os.makedirs(_IMG_DIR, exist_ok=True)


def _get_conn():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_best_image_table():
    """创建 card_best_images 表 (含 prompt 字段)"""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS card_best_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT UNIQUE NOT NULL,
            subject TEXT DEFAULT '',
            grade TEXT DEFAULT '',
            image_ext TEXT DEFAULT 'png',
            image_path TEXT DEFAULT '',
            prompt_path TEXT DEFAULT '',
            audit_score INTEGER DEFAULT 0,
            quality_score INTEGER DEFAULT 0,
            combined_score REAL DEFAULT 0,
            image_model TEXT DEFAULT '',
            manifest_hash TEXT DEFAULT '',
            manifest_json TEXT DEFAULT '{}',
            generation_count INTEGER DEFAULT 1,
            image_size_kb REAL DEFAULT 0,
            prompt_length INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_cbi_card ON card_best_images(card_id);
        CREATE INDEX IF NOT EXISTS idx_cbi_combined ON card_best_images(combined_score DESC);
    """)
    # 兼容旧表：添加新列（如果不存在）
    for col, coldef in [
        ('prompt_path', "TEXT DEFAULT ''"),
        ('manifest_json', "TEXT DEFAULT '{}'"),
        ('prompt_length', "INTEGER DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE card_best_images ADD COLUMN {col} {coldef}")
        except Exception:
            pass  # 列已存在
    conn.commit()
    conn.close()


def _safe_filename(card_id):
    """card_id → 安全文件名 (处理 Windows 不允许的字符)"""
    safe = card_id
    for ch in r'\/:"*?<>|':
        safe = safe.replace(ch, '_')
    return safe


def manifest_hash(manifest):
    """manifest → 12字符 MD5 短哈希 (用于变更检测)"""
    if not manifest:
        return ''
    m_str = json.dumps(manifest, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(m_str.encode('utf-8')).hexdigest()[:12]


def get_best_cache(card_id):
    """
    加载某卡片的历史最优图 + 最优 prompt。

    Returns:
        dict: {image_data, ext, prompt_text, manifest_json,
               audit_score, quality_score, combined_score,
               manifest_hash, model, generation_count, updated_at}
        None: 无缓存
    """
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM card_best_images WHERE card_id = ?", (card_id,)
        ).fetchone()
        if not row:
            return None

        img_path = row['image_path']
        if not img_path or not os.path.exists(img_path):
            # 文件丢失 → 清除记录
            conn.execute("DELETE FROM card_best_images WHERE card_id = ?", (card_id,))
            conn.commit()
            return None

        with open(img_path, 'rb') as f:
            image_data = f.read()

        # 读取 prompt 文件
        prompt_text = ''
        prompt_path = row['prompt_path'] if 'prompt_path' in row.keys() else ''
        if prompt_path and os.path.exists(prompt_path):
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    prompt_text = f.read()
            except Exception:
                pass

        # 读取缓存的 manifest
        cached_manifest = {}
        manifest_json_str = row['manifest_json'] if 'manifest_json' in row.keys() else '{}'
        if manifest_json_str:
            try:
                cached_manifest = json.loads(manifest_json_str)
            except Exception:
                pass

        return {
            'image_data': image_data,
            'ext': row['image_ext'],
            'prompt_text': prompt_text,
            'manifest': cached_manifest,
            'audit_score': row['audit_score'],
            'quality_score': row['quality_score'],
            'combined_score': row['combined_score'],
            'manifest_hash': row['manifest_hash'],
            'model': row['image_model'],
            'generation_count': row['generation_count'],
            'prompt_length': row['prompt_length'] if 'prompt_length' in row.keys() else 0,
            'updated_at': row['updated_at'],
        }
    except Exception as e:
        print(f'[warm-start] get_best_cache error: {e}')
        return None
    finally:
        conn.close()


# 兼容旧调用
get_best_image = get_best_cache


def save_best_cache(card_id, image_data, ext, audit_score, quality_score,
                    prompt_text='', model='', manifest=None, subject='', grade=''):
    """
    保存/更新某卡片的最优图 + 最优 prompt。
    仅在新图更优 或 manifest 变化时才更新。

    Returns:
        (saved: bool, reason: str)
    """
    _ensure_dir()
    combined = (audit_score + quality_score) / 2 if quality_score > 0 else float(audit_score)
    m_hash = manifest_hash(manifest)
    m_json = json.dumps(manifest or {}, ensure_ascii=False)

    conn = _get_conn()
    try:
        existing = conn.execute(
            "SELECT combined_score, generation_count, manifest_hash FROM card_best_images WHERE card_id = ?",
            (card_id,)
        ).fetchone()

        gen_count = 1
        if existing:
            old_combined = existing['combined_score']
            gen_count = existing['generation_count'] + 1
            old_m_hash = existing['manifest_hash']

            # 仅在 新分更高 或 manifest变化 时才更新图片+prompt
            if combined <= old_combined and m_hash == old_m_hash:
                # 只更新计数
                conn.execute(
                    "UPDATE card_best_images SET generation_count = ?, updated_at = datetime('now','localtime') WHERE card_id = ?",
                    (gen_count, card_id)
                )
                conn.commit()
                return False, f'缓存更优({old_combined:.0f}>={combined:.0f}), gen#{gen_count}'

        # 写入图片文件
        safe_name = _safe_filename(card_id)
        img_path = os.path.join(_IMG_DIR, f'{safe_name}.{ext}')
        with open(img_path, 'wb') as f:
            f.write(image_data)

        # 写入 prompt 文件
        prompt_path = os.path.join(_IMG_DIR, f'{safe_name}.prompt')
        if prompt_text:
            with open(prompt_path, 'w', encoding='utf-8') as f:
                f.write(prompt_text)
        else:
            prompt_path = ''

        size_kb = len(image_data) / 1024
        prompt_len = len(prompt_text) if prompt_text else 0

        if existing:
            conn.execute("""
                UPDATE card_best_images SET
                    subject=?, grade=?, image_ext=?, image_path=?, prompt_path=?,
                    audit_score=?, quality_score=?, combined_score=?,
                    image_model=?, manifest_hash=?, manifest_json=?,
                    generation_count=?, image_size_kb=?, prompt_length=?,
                    updated_at=datetime('now','localtime')
                WHERE card_id = ?
            """, (subject, grade, ext, img_path, prompt_path,
                  audit_score, quality_score, combined, model, m_hash, m_json,
                  gen_count, size_kb, prompt_len, card_id))
        else:
            conn.execute("""
                INSERT INTO card_best_images
                    (card_id, subject, grade, image_ext, image_path, prompt_path,
                     audit_score, quality_score, combined_score,
                     image_model, manifest_hash, manifest_json,
                     generation_count, image_size_kb, prompt_length)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (card_id, subject, grade, ext, img_path, prompt_path,
                  audit_score, quality_score, combined, model, m_hash, m_json,
                  gen_count, size_kb, prompt_len))

        conn.commit()
        action = '更新' if existing else '首次保存'
        return True, f'{action}(combined={combined:.0f}, prompt={prompt_len}字, gen#{gen_count})'
    except Exception as e:
        print(f'[warm-start] save_best_cache error: {e}')
        return False, f'保存异常: {str(e)[:50]}'
    finally:
        conn.close()


# 兼容旧调用
save_best_image = save_best_cache


def get_cache_stats():
    """获取缓存整体统计"""
    conn = _get_conn()
    try:
        row = conn.execute("""
            SELECT
                COUNT(*) as total_cards,
                COALESCE(AVG(combined_score), 0) as avg_score,
                COALESCE(SUM(image_size_kb), 0) as total_size_kb,
                COALESCE(AVG(generation_count), 0) as avg_gen_count,
                COALESCE(MAX(generation_count), 0) as max_gen_count
            FROM card_best_images
        """).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def list_cached_cards(limit=50, min_score=0):
    """列出缓存中的卡片"""
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT card_id, subject, grade, audit_score, quality_score,
                   combined_score, generation_count, image_size_kb, prompt_length, updated_at
            FROM card_best_images
            WHERE combined_score >= ?
            ORDER BY combined_score DESC
            LIMIT ?
        """, (min_score, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ═══ 启动时自动初始化 ═══
try:
    init_best_image_table()
except Exception as _init_e:
    print(f'[warm-start] 表初始化跳过: {_init_e}')
