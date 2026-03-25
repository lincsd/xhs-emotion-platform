#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书情感账号自动化运营管理平台
纯Python实现，无需第三方依赖
"""

import http.server
import socketserver
import json
import sqlite3
import os
import sys
import random
import shutil
import hashlib
import hmac
import base64
import secrets
import urllib.parse
import urllib.request
import ssl
import re
import threading
import time
import gzip
from datetime import datetime, timedelta
from pathlib import Path

# Fix Windows GBK console encoding for emoji
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ============ 配置 ============
PORT = int(os.environ.get('PORT', '3000'))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEGACY_DB_PATH = os.path.join(BASE_DIR, 'data.db')


def _resolve_db_path():
    """优先使用环境变量指定数据库路径，便于云端挂载持久化磁盘。"""
    explicit_db_path = (os.environ.get('DB_PATH') or '').strip()
    data_dir = (os.environ.get('DATA_DIR') or '').strip()

    if explicit_db_path:
        db_path = os.path.abspath(os.path.expanduser(explicit_db_path))
    elif data_dir:
        db_path = os.path.join(os.path.abspath(os.path.expanduser(data_dir)), 'data.db')
    else:
        db_path = LEGACY_DB_PATH

    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    return db_path


DB_PATH = _resolve_db_path()
PUBLIC_DIR = os.path.join(BASE_DIR, 'public')
BUILD_VERSION = '20260324h'  # v3异步+全局超时240s+减少重试

# 积分套餐配置
CREDIT_PACKAGES = [
    {'id': 'pkg_50',   'name': '体验包',  'credits': 50,   'price': 9.9,   'badge': ''},
    {'id': 'pkg_200',  'name': '标准包',  'credits': 200,  'price': 29.9,  'badge': '热门'},
    {'id': 'pkg_500',  'name': '专业包',  'credits': 500,  'price': 59.9,  'badge': '超值'},
    {'id': 'pkg_2000', 'name': '团队包',  'credits': 2000, 'price': 199,   'badge': '最划算'},
]

# 邀请奖励配置
INVITE_REWARD_INVITER = 20    # 邀请人获得积分
INVITE_REWARD_INVITEE = 10    # 被邀请人获得积分
INVITE_MAX_REWARDS = 50       # 每人最多获得邀请奖励次数
COMMISSION_RATE = 0.15        # 分销返现比例 15%

# 支付配置
WECHAT_PAY_QR = os.environ.get('WECHAT_PAY_QR', '/wechat_pay.jpg')   # 微信收款二维码图片 URL
ALIPAY_PAY_QR = os.environ.get('ALIPAY_PAY_QR', '/alipay_pay.jpg')   # 支付宝收款二维码图片 URL
PAYMENT_ACCOUNT = os.environ.get('PAYMENT_ACCOUNT', '')    # 收款账号说明(可选)
ORDER_EXPIRE_HOURS = 24  # 订单超时小时数

# 短信验证码配置
SMS_CODE_TTL_MINUTES = 10
SMS_SEND_COOLDOWN_SECONDS = 60
SMS_DAILY_LIMIT_PER_PHONE = 20

# 图形验证码配置
CAPTCHA_TTL_SECONDS = 300  # 5分钟有效
REGISTER_IP_DAILY_LIMIT = 3  # 同一 IP 每天最多注册几个账号
_captcha_store = {}  # {token: {'answer': int, 'expires': float}}

# 管理员密钥 — 必须通过环境变量ADMIN_KEY设置
ADMIN_KEY = os.environ.get('ADMIN_KEY', '')
if not ADMIN_KEY:
    ADMIN_KEY = secrets.token_hex(16)
    print(f'[WARNING] ADMIN_KEY not set in environment, generated temporary key: {ADMIN_KEY}')

# 登录失败频率限制
_login_fail_tracker = {}  # {ip_or_username: {'count': int, 'first_fail': float}}
LOGIN_MAX_FAILS = 5       # 5次失败后锁定
LOGIN_LOCKOUT_SECONDS = 300  # 锁定5分钟

# Gemini API Proxy 配置
GEMINI_API_BASE = 'https://generativelanguage.googleapis.com'

def _sanitize_api_key(key):
    """清洗 API Key：去除 GEMINI_API_KEY= 前缀、ADMIN_KEY=xxx 后缀等杂质"""
    key = key.strip()
    # 去除 KEY=value 前缀 (如 GEMINI_API_KEY=AIza...)
    if '=' in key and not key.startswith('AIza'):
        key = key.split('=', 1)[-1].strip()
    # 去除末尾可能的 ADMIN_KEY=xxx 等杂质
    if ' ' in key:
        key = key.split()[0].strip()
    return key

def _load_server_gemini_key():
    """只从环境变量读取 API Key，绝不从文件读取（防止 Key 泄露到 Git）
    如果 GEMINI_API_KEY 包含逗号（多 Key 模式），只返回第一个 Key"""
    raw = (os.environ.get('GEMINI_API_KEY') or '').strip()
    if ',' in raw:
        return _sanitize_api_key(raw.split(',')[0])
    return _sanitize_api_key(raw)

SERVER_GEMINI_API_KEY = _load_server_gemini_key()

# 多 API Key 轮询（支持 GEMINI_API_KEYS 或 GEMINI_API_KEY 用逗号分隔多个 Key）
def _load_server_gemini_keys():
    """加载多个 Gemini API Key，支持所有 Gemini 调用的轮询
    优先读 GEMINI_API_KEYS，若为空则从 GEMINI_API_KEY 按逗号拆分"""
    raw = (os.environ.get('GEMINI_API_KEYS') or '').strip()
    if not raw:
        # 从 GEMINI_API_KEY 按逗号拆分（支持单 Key 或多 Key）
        raw = (os.environ.get('GEMINI_API_KEY') or '').strip()
    if not raw:
        return []
    keys = [_sanitize_api_key(k) for k in raw.split(',') if k.strip()]
    return [k for k in keys if k]  # 过滤空值

SERVER_GEMINI_API_KEYS = _load_server_gemini_keys()
_server_key_index = 0
_server_key_lock = threading.Lock()

# 图片生成请求节流：防止连续图片请求压垮 Render 实例
_last_image_gen_time = 0
_image_gen_lock = threading.Lock()
IMAGE_GEN_MIN_GAP = 2.0  # 图片请求最小间隔(秒)

# ── 异步任务队列（解决 Cloudflare 100s 代理超时） ──
_async_tasks = {}          # {task_id: {status, result, created, updated}}
_async_tasks_lock = threading.Lock()
_ASYNC_TASK_TTL = 600      # 任务结果保留10分钟
_ASYNC_TASK_TIMEOUT = 240  # 后台任务最大运行时间(秒) — 超时返回最佳结果或错误

def _get_next_server_key():
    """轮询获取下一个服务器端 API Key（线程安全）"""
    global _server_key_index
    if not SERVER_GEMINI_API_KEYS:
        return ''
    if len(SERVER_GEMINI_API_KEYS) == 1:
        return SERVER_GEMINI_API_KEYS[0]
    with _server_key_lock:
        idx = _server_key_index
        _server_key_index = (_server_key_index + 1) % len(SERVER_GEMINI_API_KEYS)
    return SERVER_GEMINI_API_KEYS[idx]
# 自动检测系统代理
_PROXY_URL = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy') or os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy') or ''
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

def _build_opener():
    handlers = [urllib.request.HTTPSHandler(context=_SSL_CTX)]
    if _PROXY_URL:
        handlers.insert(0, urllib.request.ProxyHandler({'https': _PROXY_URL, 'http': _PROXY_URL}))
    return urllib.request.build_opener(*handlers)

_OPENER = _build_opener()

# ============ 数据库初始化 ============
def init_db():
    print(f"[init_db] Starting... DB_PATH={DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT NOT NULL,
            tags TEXT,
            cover_text TEXT,
            status TEXT DEFAULT 'draft',
            scheduled_date TEXT,
            publish_date TEXT,
            likes INTEGER DEFAULT 0,
            collects INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            views INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            post_id INTEGER,
            date TEXT DEFAULT (date('now','localtime')),
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS account_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE,
            followers INTEGER DEFAULT 0,
            total_likes INTEGER DEFAULT 0,
            total_collects INTEGER DEFAULT 0,
            total_views INTEGER DEFAULT 0,
            notes_count INTEGER DEFAULT 0,
            user_id INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nickname TEXT DEFAULT '',
            avatar TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS sms_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            purpose TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            ip TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            expires_at TEXT NOT NULL,
            used_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_sms_codes_phone_purpose ON sms_codes(phone, purpose);
        CREATE INDEX IF NOT EXISTS idx_sms_codes_created_at ON sms_codes(created_at);
    """)
    # 迁移：给已有表添加 user_id 列（忽略已存在错误）
    for tbl in ('posts', 'income', 'account_stats'):
        try:
            conn.execute(f'ALTER TABLE {tbl} ADD COLUMN user_id INTEGER DEFAULT 0')
        except:
            pass
    # 迁移：给 posts 表添加图片列
    for col in ('cover_image TEXT', 'content_images TEXT'):
        try:
            conn.execute(f'ALTER TABLE posts ADD COLUMN {col}')
        except:
            pass
    # 迁移：给 users 表添加 ai_credits 列
    try:
        conn.execute('ALTER TABLE users ADD COLUMN ai_credits INTEGER DEFAULT 0')
    except:
        pass
    try:
        conn.execute('ALTER TABLE users ADD COLUMN tier TEXT DEFAULT "free"')
    except:
        pass
    # 迁移：给 users 表添加 phone 列（手机号注册）
    try:
        conn.execute('ALTER TABLE users ADD COLUMN phone TEXT')
    except:
        pass
    try:
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone ON users(phone)')
    except:
        pass
    # 迁移：给 users 表添加邀请码 & 邀请人字段
    for col in ('invite_code TEXT', 'invited_by INTEGER DEFAULT 0', 'commission_balance REAL DEFAULT 0'):
        try:
            conn.execute(f'ALTER TABLE users ADD COLUMN {col}')
        except:
            pass
    # 提交 ALTER 确保列生效
    conn.commit()
    # 为 invite_code 列创建唯一索引（ALTER TABLE 不支持 UNIQUE 约束）
    try:
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_invite_code ON users(invite_code)')
    except:
        pass
    # 迁移：给 posts 表添加 starred（收藏）列
    try:
        conn.execute('ALTER TABLE posts ADD COLUMN starred INTEGER DEFAULT 0')
        conn.commit()
    except:
        pass
    # 迁移：给 orders 表添加 pay_method 字段
    try:
        conn.execute("ALTER TABLE orders ADD COLUMN pay_method TEXT DEFAULT ''")
        conn.commit()
    except:
        pass
    # AI 使用量追踪表
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ai_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            feature TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_ai_usage_user_date ON ai_usage(user_id, date);

        CREATE TABLE IF NOT EXISTS redeem_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            credits INTEGER NOT NULL DEFAULT 100,
            used_by INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            used_at TEXT
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            package_id TEXT NOT NULL,
            credits INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            pay_method TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            paid_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

        CREATE TABLE IF NOT EXISTS invite_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_id INTEGER NOT NULL,
            invitee_id INTEGER NOT NULL,
            reward_inviter INTEGER DEFAULT 0,
            reward_invitee INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (inviter_id) REFERENCES users(id),
            FOREIGN KEY (invitee_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS commissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            from_user_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            method TEXT DEFAULT '',
            account_info TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            processed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS content_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            topic TEXT DEFAULT '',
            plan_date TEXT NOT NULL,
            plan_time TEXT DEFAULT '10:00',
            status TEXT DEFAULT 'planned',
            notes TEXT DEFAULT '',
            category TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_content_plans_user ON content_plans(user_id);
        CREATE INDEX IF NOT EXISTS idx_content_plans_date ON content_plans(plan_date);
    """)
    # 为所有老用户生成邀请码（如果没有）
    try:
        rows = conn.execute('SELECT id FROM users WHERE invite_code IS NULL').fetchall()
        for r in rows:
            code = 'INV' + secrets.token_hex(4).upper()
            try:
                conn.execute('UPDATE users SET invite_code=? WHERE id=?', (code, r['id']))
            except:
                pass
    except Exception as e:
        print(f"[init_db] 跳过邀请码回填: {e}")
    conn.commit()
    conn.close()
    print(f"[init_db] Done. Version={BUILD_VERSION}")


def bootstrap_db_if_needed():
    """首次切换到持久化目录时，尽量从旧位置复制数据库。"""
    if DB_PATH == LEGACY_DB_PATH:
        return
    if os.path.exists(DB_PATH):
        return
    if not os.path.exists(LEGACY_DB_PATH):
        return

    shutil.copy2(LEGACY_DB_PATH, DB_PATH)
    print(f"[*] Bootstrapped database to persistent path: {DB_PATH}")

# ============ 内容生成引擎 ============
class ContentEngine:
    categories = {
        '治愈': {'emoji': '🌸', 'color': '#FFB6C1'},
        '成长': {'emoji': '🌱', 'color': '#90EE90'},
        '爱情': {'emoji': '💕', 'color': '#FF69B4'},
        '友情': {'emoji': '🤝', 'color': '#87CEEB'},
        '自我': {'emoji': '✨', 'color': '#FFD700'},
        '离别': {'emoji': '🍂', 'color': '#DEB887'},
        '温暖': {'emoji': '☀️', 'color': '#FFA500'},
        '释怀': {'emoji': '🕊️', 'color': '#E6E6FA'},
    }

    hooks = {
        '治愈': [
            '有些伤口，时间会慢慢缝合。',
            '你不必假装坚强，也不必向任何人证明什么。',
            '生活从来不会亏待认真生活的人。',
            '别急，好事都在路上。',
            '那些看似无法跨越的坎，回头看都是风景。',
            '每一个你觉得难熬的日子，都在让你变得更好。',
            '你值得被这个世界温柔以待。',
            '没关系的，一切都会好起来的。',
            '那些暗淡的日子里，你也在发光。',
            '慢慢来，比较快。',
        ],
        '成长': [
            '长大这件事，是在某个瞬间突然发生的。',
            '没有人天生就会坚强，都是后天被生活教会的。',
            '成熟不是变得冷漠，是学会了不动声色地处理事情。',
            '你终究会明白，独立是最大的底气。',
            '人生没有白走的路，每一步都算数。',
            '那些让你难过的事，终有一天你都会笑着说出来。',
            '当你开始不在意别人的目光，才是真正的成长。',
            '别人的评价不重要，你自己的感受才重要。',
            '能够一个人扛住所有，是成年人最基本的能力。',
            '你所经历的一切，都在塑造更好的你。',
        ],
        '爱情': [
            '爱一个人，是藏不住的，就像风藏不住云。',
            '最好的感情，是势均力敌的爱。',
            '真正爱你的人，不会让你等到心灰意冷。',
            '喜欢是乍见之欢，爱是久处不厌。',
            '错过的人，就别再回头了。',
            '两个人在一起，最重要的是舒服。',
            '有些人注定只能陪你走一段路。',
            '爱情里最怕的不是争吵，是沉默。',
            '对的人不需要你变成别的样子。',
            '最深的爱，是成全你成为自己。',
        ],
        '友情': [
            '真正的朋友，是在你最难的时候还在的人。',
            '友情不需要天天联系，但需要时一定在。',
            '有些朋友，见面少了，但默契还在。',
            '长大后发现，朋友不在多，在真。',
            '好朋友就是，就算很久没联系，再见面也不会生疏。',
            '能陪你笑的人很多，能陪你哭的人很少。',
            '最好的友情是互相麻烦，互相需要。',
            '成年人的友情，是各自忙碌又互相牵挂。',
        ],
        '自我': [
            '你不必活成任何人期待的样子。',
            '取悦自己，才是人生最大的功课。',
            '学会和自己相处，是一生的修行。',
            '你值得拥有更好的生活。',
            '不要为了合群，丢掉了自己。',
            '做自己喜欢的事，成为自己喜欢的人。',
            '你的价值不需要别人来定义。',
            '独处不是孤独，是自由。',
            '别怕与众不同，那是你最珍贵的地方。',
            '学会爱自己，才有能力爱别人。',
        ],
        '离别': [
            '有些再见，说出口就是永远。',
            '不是所有的故事都有结局，不是所有的相遇都有意义。',
            '离开的人不必挽留，留下的人也不必讨好。',
            '后来我们都学会了，适时地转身。',
            '分开也是一种成全。',
            '那些没说出口的再见，成了心里最深的遗憾。',
            '人生就是一场一场的离别。',
            '有些路，注定要一个人走。',
        ],
        '温暖': [
            '这个世界上，总有人在偷偷爱你。',
            '你看，生活虽然很难，但也有很多温暖的瞬间。',
            '今天也要做一个温暖的人。',
            '被人惦记是一件很幸福的事。',
            '生活不止眼前的苟且，还有很多小确幸。',
            '谢谢那些在我没有放弃自己的每一天。',
            '你比自己想象的要坚强得多。',
            '总有一束光，会照亮你前行的路。',
        ],
        '释怀': [
            '放下不是遗忘，是不再执着。',
            '有些事情，想通了就释然了。',
            '学会接受不完美，才能活得轻松。',
            '不再期待别人给你答案，自己就是答案。',
            '原谅不是为了别人，是为了放过自己。',
            '过去的就让它过去吧。',
            '不必强求，该来的总会来。',
            '人生本就是一场修行，学会放下才能前行。',
        ],
    }

    body_templates = {
        '治愈': [
            '我知道你现在可能很难过，觉得全世界都在和你作对。但我想告诉你，那些让你流泪的事情，终究会让你变得更强大。\n\n不要害怕受伤，也不要害怕失去。你所经历的一切苦难，都是在为未来的幸福铺路。\n\n你看，春天总会来的，花总会开的，好事总会发生的。你只需要再坚持一下下，再等一等。',
            '有时候我们会突然感到很疲惫，不是身体的疲惫，而是心累了。\n\n这个时候，允许自己停下来，给自己一个拥抱。你不是矫情，你只是太累了。\n\n记住，休息不是后退，是为了更好地出发。你已经做得很好了。',
            '生活从来不会一帆风顺，总有那么些时刻让你觉得撑不下去。\n\n但你回头看看，那些你以为熬不过去的夜晚，不都熬过来了吗？\n\n你远比自己想象的要勇敢得多。所以，别怕，继续走下去。',
            '每个人都有脆弱的时候，不必觉得丢人。\n\n哭过之后擦干眼泪，继续前行。那些让你痛苦的经历，终将成为你最宝贵的财富。\n\n你不需要变得刀枪不入，你只需要在每一次跌倒后，选择站起来。',
            '也许你正经历着一段很难的时光，觉得看不到尽头。\n\n但请你相信，黑夜之后一定会有黎明，冬天过后一定会有春天。\n\n你现在所承受的一切，都是在为更好的明天积蓄力量。坚持住，好吗？',
        ],
        '成长': [
            '曾经以为长大是一件很酷的事情，后来才发现，长大就意味着要承受更多。\n\n但也正是这些承受，让我们变成了更好的人。那些曾经觉得过不去的坎，现在回头看都是成长的标记。\n\n感谢每一次跌倒，让我学会了更好地站起来。',
            '成长大概就是：越来越能接受现实的样子，而不是期待别人的改变。\n\n我学会了在失望的时候不再抱怨，在委屈的时候不再解释，在难过的时候自己消化。\n\n这不是变得冷漠，而是懂得了：自己的情绪，自己负责。',
            '从什么时候开始，我们不再轻易说出自己的感受了？\n\n大概是从明白了"没有人真正在意你的委屈"开始吧。\n\n但这不是坏事，这意味着你已经足够强大，可以独立面对这个世界了。',
            '慢慢发现，成长就是一个不断失去的过程。\n\n失去天真、失去依赖、失去一些朋友。但与此同时，你也在获得——获得独立、获得智慧、获得真正属于你的东西。\n\n别害怕失去，那只是为了给更好的腾出位置。',
            '以前总觉得成年人都是超人，什么都能搞定。\n\n等自己成了成年人才发现，原来谁都是一边崩溃一边自愈的。\n\n没有谁天生坚强，只是在一次次的跌倒中学会了默默站起来。这就是成长的代价，也是成长的意义。',
        ],
        '爱情': [
            '真正好的爱情，是两个人在一起的时候很开心，分开的时候也不会患得患失。\n\n不需要时刻证明，不需要反复确认。只是知道对方在那里，就足够安心。\n\n如果一段感情让你变得越来越不像自己，那它一定不是对的。',
            '后来才明白，爱情不是找一个完美的人，而是找一个愿意和你一起变好的人。\n\n他不需要给你很多承诺，但会在每一个小细节里让你感到被在乎。\n\n最好的爱情，是我因为你变成了更好的我。',
            '别再等一个人来拯救你了。\n\n好的感情从来不是一个人拯救另一个人，而是两个独立的灵魂互相温暖。\n\n先把自己活好，对的人自然会来。',
            '爱情最让人心碎的不是争吵，不是分手，而是那种慢慢变淡的过程。\n\n你发现他不再秒回消息了，不再在意你的情绪了，不再主动找你了。\n\n但你要记住，不够爱你的人，就不值得你继续付出。你值得更好的。',
            '我渐渐明白了，感情不能将就。将就的感情，最终会让两个人都不幸福。\n\n宁可一个人好好地活着，也不要在一段不对的关系里反复受伤。\n\n等一个真正让你心动的人出现，比在凑合中消磨自己要好得多。',
        ],
        '友情': [
            '年纪越大越觉得，身边能有两三个真心朋友就已经很幸运了。\n\n不需要太多人来来去去，只需要那几个知道你不开心时会发消息问你的人。\n\n感谢那些在我沉默时也愿意陪着的人。',
            '以前觉得朋友越多越好，后来才明白，真正的朋友是那些你不用维持关系也不会走散的人。\n\n可能很久没联系，但一条消息就能回到从前。\n\n这种友情，不怕时间，不怕距离。',
            '最舒服的友情，大概就是：我不用刻意讨好你，你也不用委屈迁就我。\n\n我们各自忙碌，偶尔联系，但彼此都知道对方一直都在。\n\n这样的朋友，一个就够了。',
        ],
        '自我': [
            '我终于不再为了迎合别人而委屈自己了。\n\n那些不喜欢真实的我的人，大概本来就不是我该交往的人。\n\n做自己可能会失去一些人，但留下来的都是值得的。',
            '别再为了一些不值得的人和事内耗了。\n\n你的时间和精力很宝贵，应该用在让自己变好的事情上。\n\n从今天开始，把注意力放在自己身上。你会发现，原来自己可以过得这么好。',
            '我开始学着不再讨好任何人了。\n\n不是变得冷漠，而是明白了：真正在乎你的人，不需要你讨好。不在乎你的人，讨好了也没用。\n\n做好自己就够了。',
            '有一天你会发现，独处真的是一件很美好的事。\n\n不用迎合别人，不用在意他人的眼光，完全按照自己的节奏生活。\n\n独处的时光，是和自己对话的最好机会。学会享受它。',
        ],
        '离别': [
            '有些人走了就是走了，不需要理由，也不需要解释。\n\n成年人的世界里，渐行渐远是常态，念念不忘才是例外。\n\n学会好好告别，也是一种能力。',
            '那个曾经说要陪你到最后的人，最后也没能留下来。\n\n但你看，没有他你也走到了现在，而且过得也不差。\n\n人生就是这样，有人来有人走，重要的是那些愿意留下来的。',
            '后来我不再难过了，不是因为不在乎了，而是接受了这个结果。\n\n有些人的离开，其实是一种解脱。虽然过程很痛，但结果是好的。\n\n感谢你曾经来过我的世界，也祝你在没有我的日子里，一切都好。',
        ],
        '温暖': [
            '昨天在路上，一个陌生人对我笑了一下。\n\n就那么一个小小的微笑，就让我觉得这个世界还是很美好的。\n\n你看，温暖其实无处不在，只是我们有时候忽略了。',
            '下雨的时候，有人递给你一把伞。加班到很晚，有人给你发一条"注意休息"。\n\n这些看似微不足道的小事，其实就是生活里最大的温暖。\n\n不要忘了，有人在远方默默地关心着你。',
            '今天看到一对老夫妻手牵手过马路，老奶奶走得慢，老爷爷就放慢脚步等她。\n\n这大概就是最好的爱情和最温暖的风景吧。\n\n原来幸福可以很简单——有人愿意等你，有人愿意陪你慢慢走。',
        ],
        '释怀': [
            '曾经让你痛哭的事情，现在是不是已经能笑着提起了？\n\n这就对了。时间不会帮你忘记，但会帮你释怀。\n\n那些过不去的，终究都会过去的。',
            '我不再执着于一个结果了。\n\n该来的会来，该走的会走。与其紧握不放，不如张开双手，接受命运的安排。\n\n放下了，反而轻松了。',
            '从前我总是把别人的看法放在心上，活得累又不开心。\n\n后来想通了：别人爱怎么看就怎么看吧，我没有义务让所有人满意。\n\n放过别人，也放过自己。这才是真正的释怀。',
        ],
    }

    endings = [
        '\n\n💗 如果这段文字触动了你，记得点赞收藏，让更多人看到温暖。',
        '\n\n🌟 关注我，每天给你一剂心灵鸡汤，陪你度过每一个不容易的日子。',
        '\n\n✨ 你有什么想说的吗？欢迎在评论区写下你的故事，我会认真看每一条。',
        '\n\n🌸 转发给你在乎的人吧，让他/她知道你在想他/她。',
        '\n\n💫 每天更新情感语录，关注不迷路～',
        '\n\n🤗 发给你最近在想的那个人吧。',
        '\n\n📌 收藏起来，在难过的时候看一看。',
        '\n\n💝 关注我，做你的情感树洞。',
        '\n\n🌈 在评论区告诉我，你现在是什么心情？',
        '\n\n🍀 把这段话送给正在努力的你。',
    ]

    title_templates = {
        '治愈': [
            '致那个正在难过的你｜看完真的会好很多',
            '这段话送给正在低谷的你💗',
            '别哭了｜这些话说到我心坎里了',
            '突然被治愈了｜适合深夜一个人看',
            '看完这段话 我哭了很久💧',
            '一个人的时候看看这个｜真的会好起来的',
            '熬不下去的时候就打开看看🌸',
            '你已经做得很好了｜别再为难自己了',
            '深夜看到这段话 突然红了眼眶',
            '不开心的时候请打开这条笔记🥺',
        ],
        '成长': [
            '成年人最扎心的真相｜越早知道越好',
            '长大后才明白的道理💡',
            '这就是成长吧｜句句戳心',
            '20+岁最该明白的事情',
            '从什么时候开始我们变了',
            '成年人的世界 没有容易二字',
            '别再天真了｜这些话你要记住',
            '每一次崩溃都是在成长💪',
            '你变了 是因为你长大了',
            '比起矫情 我更希望你清醒',
        ],
        '爱情': [
            '关于爱情 我想明白了💓',
            '爱情里最扎心的一段话',
            '如果你正在爱一个人｜一定要看看这个',
            '分手后才明白的事情💔',
            '这才是真正好的爱情的样子',
            '别再爱错人了｜看看这些特征',
            '感情里最怕的是什么？',
            '给正在暗恋/单恋的你🥺',
            '那个你爱的人 值得吗？',
            '最后一次为你流泪 再见了',
        ],
        '友情': [
            '真正的朋友长什么样子🤝',
            '你身边有这样的朋友吗？',
            '长大后友情最真实的样子',
            '那些慢慢走散的朋友啊',
            '好朋友之间不需要多说什么',
            '成年人的友情｜贵精不贵多',
            '友谊不会因为距离而消失',
            '知己一两个 足够温暖一辈子',
        ],
        '自我': [
            '从今天开始 做自己✨',
            '别再活在别人的期待里了',
            '自爱是终身浪漫的开始💕',
            '你不需要向任何人解释自己',
            '学会这一点 你会过得更开心',
            '别再讨好任何人了｜做自己就好',
            '你的人生不需要观众',
            '独处是最好的增值期🌟',
            '你比你想象的要好得多',
            '不合群没关系 你很特别',
        ],
        '离别': [
            '那些没能好好说再见的人🍂',
            '有些人走着走着就散了',
            '最后一次回头看你｜再见',
            '离开也是一种成全',
            '后来才明白 错过就是错过',
            '那个再也不见的人啊',
            '有些故事 注定没有结局',
            '转身之后 别再回头',
        ],
        '温暖': [
            '这个世界还是很温暖的☀️',
            '生活中那些被治愈的瞬间',
            '突然觉得被世界温柔对待了',
            '记录那些让我觉得幸福的小事',
            '谢谢你们 在我身边',
            '人间值得｜今天也是有温度的一天',
            '被一个细节温暖了整个冬天',
            '原来有人在偷偷爱你💝',
        ],
        '释怀': [
            '放下了 就真的释然了🕊️',
            '那些曾经过不去的坎｜如今',
            '终于不再执着了',
            '学会放下 是一种能力',
            '今天起 别再为不值得的人难过',
            '想通了就轻松了✨',
            '翻篇了 不回头了',
            '放过自己 比什么都重要',
        ],
    }

    tag_sets = {
        '治愈': ['治愈文字', '情感语录', '正能量', '鸡汤', '暖心', '深夜emo', '扎心文案', '心灵鸡汤', '生活感悟', '心情日记'],
        '成长': ['成长日记', '生活感悟', '人生哲理', '扎心语录', '醒悟', '成年人的世界', '人间清醒', '自我成长'],
        '爱情': ['爱情语录', '恋爱', '情感', '甜蜜', '暗恋', '失恋', '分手', '疗伤', '两性关系', '感情观'],
        '友情': ['友情', '朋友', '闺蜜', '友谊地久天长', '真朋友', '好朋友'],
        '自我': ['做自己', '自信', '独立', '女性力量', '自爱', '个性签名', '人间清醒', '情商'],
        '离别': ['离别', '遗憾', '错过', '思念', '怀念', '告别'],
        '温暖': ['温暖', '暖心', '小确幸', '生活美好', '被治愈', '正能量'],
        '释怀': ['释怀', '放下', '看开', '释然', '人间清醒', '不执着'],
    }

    cover_texts = {
        '治愈': ['你值得被温柔以待', '别怕 一切都会好的', '你已经很棒了', '没关系 慢慢来', '抱抱你', '总会好起来的'],
        '成长': ['这就是成长', '长大是一瞬间的事', '你变了', '成熟的代价', '不再天真'],
        '爱情': ['爱是什么', '对的人', '错过的人', '再见 也是再也不见', '你值得被爱', '心动的感觉'],
        '友情': ['真朋友', '谢谢你还在', '最好的我们', '一起走过的日子'],
        '自我': ['做自己', '你的价值', '别在意别人', '为自己而活', '自信的样子最好看'],
        '离别': ['再见了', '路过你的世界', '那些没说出口的话', '转身 是最好的告别'],
        '温暖': ['世界很美好', '小确幸', '今天也要开心', '被温暖了'],
        '释怀': ['放下了', '不再执着', '想通了', '轻装前行'],
    }

    @classmethod
    def generate(cls, category=None):
        if not category:
            category = random.choice(list(cls.categories.keys()))
        
        title = random.choice(cls.title_templates.get(category, cls.title_templates['治愈']))
        hook = random.choice(cls.hooks.get(category, cls.hooks['治愈']))
        body = random.choice(cls.body_templates.get(category, cls.body_templates['治愈']))
        ending = random.choice(cls.endings)
        cover_text = random.choice(cls.cover_texts.get(category, cls.cover_texts['治愈']))
        
        all_tags = cls.tag_sets.get(category, cls.tag_sets['治愈'])[:]
        random.shuffle(all_tags)
        tags = ','.join(all_tags[:5])
        
        content = f"{hook}\n\n{body}{ending}"
        
        return {
            'title': title,
            'content': content,
            'category': category,
            'tags': tags,
            'cover_text': cover_text
        }

    @classmethod
    def generate_batch(cls, count, category=None):
        return [cls.generate(category) for _ in range(count)]


# ============ 变现方案数据 ============
MONETIZATION_GUIDE = {
    'strategies': [
        {
            'name': '广告合作',
            'icon': '📢',
            'threshold': '1000粉丝起',
            'income': '200-2000元/条',
            'description': '品牌方找你投放情感类软文，融入产品推荐',
            'tips': ['保持内容调性一致', '选择与情感相关的品牌', '报价参考: 粉丝数×0.1-0.3']
        },
        {
            'name': '蒲公英平台',
            'icon': '🌻',
            'threshold': '1000粉丝+',
            'income': '100-5000元/单',
            'description': '小红书官方创作者平台，接品牌推广单',
            'tips': ['完善创作者资料', '保持稳定更新频率', '专注情感垂类提高报价']
        },
        {
            'name': '付费咨询',
            'icon': '💬',
            'threshold': '5000粉丝+',
            'income': '50-200元/次',
            'description': '提供情感咨询、恋爱建议等付费服务',
            'tips': ['需要一定的专业背景', '可以从免费问答开始积累口碑', '逐步转化为付费']
        },
        {
            'name': '课程/电子书',
            'icon': '📚',
            'threshold': '10000粉丝+',
            'income': '被动收入',
            'description': '出品情感类课程、恋爱指南等知识付费产品',
            'tips': ['整理热门内容成体系', '定价29-199元', '通过笔记引流至付费内容']
        },
        {
            'name': '表情包/壁纸',
            'icon': '🎨',
            'threshold': '3000粉丝+',
            'income': '1-10元/份',
            'description': '设计情感主题壁纸、文字表情包等数字产品',
            'tips': ['利用封面文字风格延展', '在笔记中自然引流', '薄利多销策略']
        },
        {
            'name': '直播打赏',
            'icon': '🎙️',
            'threshold': '1000粉丝+',
            'income': '不定',
            'description': '开设情感电台、深夜谈心等直播',
            'tips': ['固定时间直播培养用户习惯', '可读粉丝投稿故事', '搭配文字背景增强氛围']
        },
        {
            'name': '账号矩阵',
            'icon': '📱',
            'threshold': '积累经验后',
            'income': '倍增收益',
            'description': '用相同模式批量运营多个情感子账号',
            'tips': ['每个号定位稍有差异', '共享内容库提高效率', '本系统支持多账号管理']
        }
    ],
    'roadmap': [
        {'phase': '冷启动期', 'duration': '1-2个月', 'followers': '0-1000', 'tasks': ['每天发2-3条优质笔记', '选好4-5个核心标签', '研究爆款笔记套路', '积极互动回复评论']},
        {'phase': '成长期', 'duration': '2-4个月', 'followers': '1000-5000', 'tasks': ['入驻蒲公英平台', '开始接广告合作', '优化内容形式', '建立粉丝社群']},
        {'phase': '变现期', 'duration': '4-6个月', 'followers': '5000-20000', 'tasks': ['稳定广告收入', '开发付费产品', '尝试直播', '考虑账号矩阵']},
        {'phase': '规模化', 'duration': '6个月+', 'followers': '20000+', 'tasks': ['团队化运营', '多渠道变现', '品牌化发展', 'IP打造']},
    ]
}


# ============ HTTP 请求处理器 ============
class APIHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def log_message(self, format, *args):
        # 简化日志
        pass

    def end_headers(self):
        path = getattr(self, 'path', '').split('?')[0] or ''
        if path == '/' or path.endswith('.html'):
            # HTML 不缓存，确保用户总是加载最新版
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        elif path.endswith('.json'):
            # JSON 数据文件短缓存（5分钟），确保内容更新及时
            self.send_header('Cache-Control', 'public, max-age=300')
        elif any(path.endswith(ext) for ext in ('.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.woff2')):
            # 静态资源缓存 7 天
            self.send_header('Cache-Control', 'public, max-age=604800')
        super().end_headers()

    def _set_json_headers(self, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        # CORS
        origin = self.headers.get('Origin', '*')
        self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        # 安全响应头
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')

    # ---- 用户认证工具方法 ----
    @staticmethod
    def _hash_password(password, salt=None):
        if salt is None:
            salt = secrets.token_hex(16)
        h = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
        return f'{salt}:{h}'

    @staticmethod
    def _verify_password(password, stored):
        if ':' not in stored:
            return False
        salt, _ = stored.split(':', 1)
        return APIHandler._hash_password(password, salt) == stored

    @staticmethod
    def _is_valid_phone(phone):
        return bool(re.match(r'^1[3-9]\d{9}$', phone or ''))

    @staticmethod
    def _is_valid_sms_code(code):
        return bool(re.match(r'^\d{6}$', code or ''))

    @staticmethod
    def _hash_sms_code(phone, purpose, code):
        raw = f'{phone}|{purpose}|{code}|xhs_sms_v1'
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    @staticmethod
    def _client_ip(headers):
        xff = (headers.get('X-Forwarded-For') or '').strip()
        if xff:
            return xff.split(',')[0].strip()
        return (headers.get('X-Real-IP') or '').strip()

    @staticmethod
    def _generate_sms_code():
        return f'{random.randint(0, 999999):06d}'

    # ---- 图形验证码 ----
    @staticmethod
    def _generate_captcha():
        """生成数学验证码，返回 (token, question_text, answer)"""
        import time as _time
        # 清理过期验证码
        now = _time.time()
        expired = [k for k, v in _captcha_store.items() if v['expires'] < now]
        for k in expired:
            del _captcha_store[k]
        # 生成随机数学题
        ops = [('+', lambda a, b: a + b), ('-', lambda a, b: a - b), ('×', lambda a, b: a * b)]
        op_sym, op_fn = random.choice(ops)
        if op_sym == '-':
            a, b = random.randint(10, 99), random.randint(1, 50)
            if a < b: a, b = b, a
        elif op_sym == '×':
            a, b = random.randint(2, 12), random.randint(2, 9)
        else:
            a, b = random.randint(10, 80), random.randint(1, 50)
        answer = op_fn(a, b)
        question = f'{a} {op_sym} {b} = ?'
        token = secrets.token_urlsafe(16)
        _captcha_store[token] = {'answer': answer, 'expires': now + CAPTCHA_TTL_SECONDS}
        return token, question, answer

    @staticmethod
    def _verify_captcha(token, user_answer):
        """验证图形验证码，验证后立即失效"""
        import time as _time
        if not token or user_answer is None:
            return False
        entry = _captcha_store.pop(token, None)
        if not entry:
            return False
        if entry['expires'] < _time.time():
            return False
        try:
            return int(user_answer) == entry['answer']
        except (ValueError, TypeError):
            return False

    def _get_captcha(self):
        """GET /api/captcha - 返回一个新的图形验证码"""
        token, question, _ = self._generate_captcha()
        return self._send_json({'token': token, 'question': question})

    @staticmethod
    def _aliyun_percent_encode(value):
        return urllib.parse.quote(str(value), safe='~')

    def _send_sms_via_aliyun(self, phone, code, purpose):
        access_key_id = (os.environ.get('ALIYUN_SMS_ACCESS_KEY_ID') or '').strip()
        access_key_secret = (os.environ.get('ALIYUN_SMS_ACCESS_KEY_SECRET') or '').strip()
        sign_name = (os.environ.get('ALIYUN_SMS_SIGN_NAME') or '').strip()
        template_code_common = (os.environ.get('ALIYUN_SMS_TEMPLATE_CODE') or '').strip()
        template_code_register = (os.environ.get('ALIYUN_SMS_TEMPLATE_CODE_REGISTER') or '').strip()
        template_code_login = (os.environ.get('ALIYUN_SMS_TEMPLATE_CODE_LOGIN') or '').strip()
        region_id = (os.environ.get('ALIYUN_SMS_REGION_ID') or 'cn-hangzhou').strip()
        endpoint = (os.environ.get('ALIYUN_SMS_ENDPOINT') or 'dysmsapi.aliyuncs.com').strip()

        template_code = template_code_register if purpose == 'register' else template_code_login
        if not template_code:
            template_code = template_code_common

        if not (access_key_id and access_key_secret and sign_name and template_code):
            print('[sms][aliyun] missing required env: ALIYUN_SMS_ACCESS_KEY_ID/SECRET/SIGN_NAME/TEMPLATE_CODE')
            return False

        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        nonce = secrets.token_hex(16)
        params = {
            'AccessKeyId': access_key_id,
            'Action': 'SendSms',
            'Format': 'JSON',
            'PhoneNumbers': phone,
            'RegionId': region_id,
            'SignName': sign_name,
            'SignatureMethod': 'HMAC-SHA1',
            'SignatureNonce': nonce,
            'SignatureVersion': '1.0',
            'TemplateCode': template_code,
            'TemplateParam': json.dumps({'code': code}, ensure_ascii=False, separators=(',', ':')),
            'Timestamp': timestamp,
            'Version': '2017-05-25',
        }

        sorted_items = sorted(params.items(), key=lambda item: item[0])
        canonicalized_query = '&'.join(
            f'{self._aliyun_percent_encode(key)}={self._aliyun_percent_encode(value)}'
            for key, value in sorted_items
        )
        string_to_sign = 'POST&%2F&' + self._aliyun_percent_encode(canonicalized_query)
        sign_key = (access_key_secret + '&').encode('utf-8')
        signature = base64.b64encode(
            hmac.new(sign_key, string_to_sign.encode('utf-8'), hashlib.sha1).digest()
        ).decode('utf-8')
        params['Signature'] = signature

        body = urllib.parse.urlencode(params).encode('utf-8')
        req = urllib.request.Request(
            f'https://{endpoint}/',
            data=body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            method='POST'
        )
        try:
            with _OPENER.open(req, timeout=10) as resp:
                text = resp.read().decode('utf-8', errors='ignore')
                try:
                    result = json.loads(text)
                except Exception:
                    print(f'[sms][aliyun] invalid json response: {text[:200]}')
                    return False
                if result.get('Code') == 'OK':
                    return True
                print(f"[sms][aliyun] send failed code={result.get('Code')} message={result.get('Message')}")
                return False
        except Exception as e:
            print(f'[sms][aliyun] request failed: {e}')
            return False

    def _send_sms_message(self, phone, code, purpose):
        sms_provider = (os.environ.get('SMS_PROVIDER') or '').strip().lower()
        sms_api_url = (os.environ.get('SMS_API_URL') or '').strip()
        sms_api_token = (os.environ.get('SMS_API_TOKEN') or '').strip()

        if sms_provider == 'aliyun':
            return self._send_sms_via_aliyun(phone, code, purpose)

        if not sms_api_url:
            print(f'[sms] mock send phone={phone} purpose={purpose} code={code}')
            return True

        payload = {
            'phone': phone,
            'code': code,
            'purpose': purpose,
            'sign': (os.environ.get('SMS_SIGN') or '小红书智能运营台').strip()
        }
        data = json.dumps(payload).encode('utf-8')
        headers = {'Content-Type': 'application/json'}
        if sms_api_token:
            headers['Authorization'] = f'Bearer {sms_api_token}'
        req = urllib.request.Request(
            sms_api_url,
            data=data,
            headers=headers,
            method='POST'
        )
        try:
            with _OPENER.open(req, timeout=10) as resp:
                return 200 <= resp.getcode() < 300
        except Exception as e:
            print(f'[sms] send failed: {e}')
            return False

    def _consume_sms_code(self, conn, phone, purpose, code):
        code_hash = self._hash_sms_code(phone, purpose, code)
        row = conn.execute(
            '''SELECT id FROM sms_codes
               WHERE phone=? AND purpose=? AND code_hash=?
                 AND used_at IS NULL
                 AND expires_at > datetime("now","localtime")
               ORDER BY id DESC LIMIT 1''',
            (phone, purpose, code_hash)
        ).fetchone()
        if not row:
            return False
        conn.execute('UPDATE sms_codes SET used_at=datetime("now","localtime") WHERE id=?', (row['id'],))
        return True

    def _auth_send_code(self, body):
        phone = (body.get('phone') or '').strip()
        purpose = (body.get('purpose') or '').strip().lower()
        if purpose not in ('register', 'login'):
            return self._send_json({'error': '验证码用途不正确'}, 400)
        if not self._is_valid_phone(phone):
            return self._send_json({'error': '请输入正确的11位手机号'}, 400)

        conn = self._get_db()
        try:
            user = conn.execute('SELECT id FROM users WHERE phone=?', (phone,)).fetchone()
        except Exception:
            user = None

        if purpose == 'register' and user:
            conn.close()
            return self._send_json({'error': '该手机号已注册'}, 409)
        if purpose == 'login' and not user:
            conn.close()
            return self._send_json({'error': '该手机号未注册'}, 404)

        cooldown = conn.execute(
            '''SELECT created_at FROM sms_codes
               WHERE phone=? AND purpose=?
               ORDER BY id DESC LIMIT 1''',
            (phone, purpose)
        ).fetchone()
        if cooldown:
            delta = conn.execute(
                'SELECT CAST((julianday("now","localtime") - julianday(?)) * 86400 AS INTEGER) as s',
                (cooldown['created_at'],)
            ).fetchone()['s']
            if delta is not None and delta < SMS_SEND_COOLDOWN_SECONDS:
                conn.close()
                return self._send_json({'error': f'发送太频繁，请{SMS_SEND_COOLDOWN_SECONDS - max(delta, 0)}秒后再试'}, 429)

        today_cnt = conn.execute(
            '''SELECT COUNT(*) as cnt FROM sms_codes
               WHERE phone=? AND date(created_at)=date("now","localtime")''',
            (phone,)
        ).fetchone()['cnt']
        if today_cnt >= SMS_DAILY_LIMIT_PER_PHONE:
            conn.close()
            return self._send_json({'error': '该手机号今日验证码发送次数已达上限'}, 429)

        code = self._generate_sms_code()
        if not self._send_sms_message(phone, code, purpose):
            conn.close()
            return self._send_json({'error': '验证码发送失败，请稍后重试'}, 502)

        expires = (datetime.now() + timedelta(minutes=SMS_CODE_TTL_MINUTES)).strftime('%Y-%m-%d %H:%M:%S')
        ip = self._client_ip(self.headers)
        code_hash = self._hash_sms_code(phone, purpose, code)
        conn.execute(
            'INSERT INTO sms_codes (phone, purpose, code_hash, ip, expires_at) VALUES (?,?,?,?,?)',
            (phone, purpose, code_hash, ip, expires)
        )
        conn.commit()
        conn.close()
        return self._send_json({'success': True, 'message': '验证码已发送', 'ttl': SMS_CODE_TTL_MINUTES * 60})

    def _get_current_user(self):
        """从 Authorization header 获取当前登录用户，返回 user dict 或 None"""
        auth = self.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return None
        token = auth[7:].strip()
        if not token:
            return None
        conn = self._get_db()
        try:
            row = conn.execute(
                'SELECT u.id, u.username, u.nickname, u.avatar, u.created_at, '
                'u.ai_credits, u.tier, u.invite_code, u.invited_by, u.commission_balance, u.phone '
                'FROM sessions s JOIN users u ON s.user_id = u.id '
                'WHERE s.token = ? AND s.expires_at > datetime("now","localtime")',
                (token,)
            ).fetchone()
        except Exception:
            # 如果新列还不存在，退回到旧查询
            row = conn.execute(
                'SELECT u.id, u.username, u.nickname, u.avatar, u.created_at, u.ai_credits, u.tier '
                'FROM sessions s JOIN users u ON s.user_id = u.id '
                'WHERE s.token = ? AND s.expires_at > datetime("now","localtime")',
                (token,)
            ).fetchone()
        conn.close()
        return dict(row) if row else None

    def _require_auth(self):
        """要求登录，返回 user dict 或发送 401 并返回 None"""
        user = self._get_current_user()
        if not user:
            self._send_json({'error': '请先登录', 'code': 'AUTH_REQUIRED'}, 401)
        return user

    # ---- AI 配额系统 ----
    FREE_DAILY_AI_LIMIT = 10  # 免费用户每天10次免费调用（够2轮完整 内容+配图 流程）

    # 各功能积分消耗映射（基于真实 Gemini API 成本 + 合理毛利）
    FEATURE_COSTS = {
        # 内容生成链路（搜索+分析+生成，最贵）
        '内容搜索分析':  2,   # Google grounding $0.035 + tokens ~¥0.33
        '内容分析':      1,   # 无 grounding，纯文本分析
        '内容生成':      2,   # 大量输出 tokens + thinking
        # 图片生成（图片模型，成本较高）
        '图片生成':      2,   # 图片模型成本 ~¥0.15-0.30/张
        '图片测试':      0,   # 测试不扣费
        'AI修图':        2,   # 图片模型编辑，成本同上
        # 品牌定位（文本生成，中等）
        '品牌定位':      2,
        # 轻量功能（纯文本，便宜）
        'AI评分优化':    1,
        '热门话题搜索':  2,   # grounding 搜索，成本 ~¥0.25/次
        '标签生成':      1,
        '生成评论话术':  1,
        '竞品分析':      2,   # grounding + 较多输出
        '笔记改写':      1,
        'AB测试':        2,   # 多版本输出，tokens 较多
        # 新增智能工具
        '一键润色':      1,   # 纯文本优化
        '爆款标题':      1,   # 批量标题生成
        '热词分析':      2,   # grounding 搜索当前热词
        '图片配文':      1,   # Vision 分析 + 文案生成
        '模板匹配':      1,   # AI模板智能匹配
        'template_match': 1,  # 单篇模板匹配
        'template_match_batch': 1,  # 批量模板匹配
        # 默认（未标记的功能）
        'generateContent': 1,
    }

    def _get_feature_cost(self, feature):
        """获取某功能的积分消耗"""
        return self.FEATURE_COSTS.get(feature, 1)

    def _get_today_ai_usage(self, user_id):
        """获取用户今日AI使用次数"""
        conn = self._get_db()
        today = datetime.now().strftime('%Y-%m-%d')
        row = conn.execute(
            'SELECT COUNT(*) as cnt FROM ai_usage WHERE user_id=? AND date=?',
            (user_id, today)
        ).fetchone()
        conn.close()
        return row['cnt'] if row else 0

    def _record_ai_usage(self, user_id, feature='ai'):
        """记录一次AI使用，并扣减积分（如果超出免费额度）"""
        cost = self._get_feature_cost(feature)
        conn = self._get_db()
        today = datetime.now().strftime('%Y-%m-%d')
        conn.execute('INSERT INTO ai_usage(user_id, date, feature) VALUES(?,?,?)',
                     (user_id, today, feature))
        # 检查是否超出免费额度，超出则按功能扣积分
        usage_today = conn.execute(
            'SELECT COUNT(*) as cnt FROM ai_usage WHERE user_id=? AND date=?',
            (user_id, today)
        ).fetchone()['cnt']
        if usage_today > self.FREE_DAILY_AI_LIMIT and cost > 0:
            conn.execute('UPDATE users SET ai_credits = MAX(0, ai_credits - ?) WHERE id=?', (cost, user_id))
        conn.commit()
        conn.close()

    def _check_ai_quota(self, user, feature='generateContent'):
        """检查用户是否还有AI调用额度。返回 (allowed, info_dict)"""
        user_id = user['id']
        today_usage = self._get_today_ai_usage(user_id)
        credits = user.get('ai_credits', 0) or 0
        cost = self._get_feature_cost(feature)

        if today_usage < self.FREE_DAILY_AI_LIMIT:
            return True, {
                'freeRemaining': self.FREE_DAILY_AI_LIMIT - today_usage,
                'credits': credits,
                'todayUsed': today_usage,
                'cost': cost
            }
        elif cost == 0:
            # 免费功能（如图片测试）无条件允许
            return True, {
                'freeRemaining': 0,
                'credits': credits,
                'todayUsed': today_usage,
                'cost': 0
            }
        elif credits >= cost:
            return True, {
                'freeRemaining': 0,
                'credits': credits,
                'todayUsed': today_usage,
                'cost': cost
            }
        else:
            return False, {
                'freeRemaining': 0,
                'credits': credits,
                'todayUsed': today_usage,
                'cost': cost,
                'needed': cost - credits
            }

    def _get_user_credits_info(self):
        """API: 获取当前用户AI积分与使用情况"""
        user = self._get_current_user()
        if not user:
            return self._send_json({'error': '未登录', 'code': 'AUTH_REQUIRED'}, 401)
        user_id = user['id']
        today_usage = self._get_today_ai_usage(user_id)
        credits = user.get('ai_credits', 0) or 0
        return self._send_json({
            'credits': credits,
            'todayUsed': today_usage,
            'freeLimit': self.FREE_DAILY_AI_LIMIT,
            'freeRemaining': max(0, self.FREE_DAILY_AI_LIMIT - today_usage),
            'tier': user.get('tier', 'free'),
            'featureCosts': self.FEATURE_COSTS
        })

    def _redeem_code(self, body):
        """API: 兑换卡密充值AI积分"""
        user = self._require_auth()
        if not user:
            return
        code = (body.get('code') or '').strip().upper()
        if not code:
            return self._send_json({'error': '请输入兑换码'}, 400)
        conn = self._get_db()
        row = conn.execute('SELECT * FROM redeem_codes WHERE code=? AND used_by IS NULL', (code,)).fetchone()
        if not row:
            conn.close()
            return self._send_json({'error': '兑换码无效或已使用'}, 400)
        credits = row['credits']
        # 原子操作：仅在 used_by 仍为 NULL 时才更新，防止双重兑换
        cur = conn.execute('UPDATE redeem_codes SET used_by=?, used_at=datetime("now","localtime") WHERE id=? AND used_by IS NULL',
                     (user['id'], row['id']))
        if cur.rowcount == 0:
            conn.close()
            return self._send_json({'error': '兑换码已被使用'}, 400)
        conn.execute('UPDATE users SET ai_credits = ai_credits + ? WHERE id=?',
                     (credits, user['id']))
        conn.commit()
        new_credits = conn.execute('SELECT ai_credits FROM users WHERE id=?', (user['id'],)).fetchone()['ai_credits']
        conn.close()
        return self._send_json({'success': True, 'added': credits, 'credits': new_credits})

    def _admin_gen_codes(self, body):
        """API: 管理员生成兑换码（简单密码验证）"""
        admin_key = body.get('adminKey', '')
        if admin_key != ADMIN_KEY:
            return self._send_json({'error': '无权限'}, 403)
        count = min(int(body.get('count', 1)), 100)
        credits = int(body.get('credits', 100))
        conn = self._get_db()
        codes = []
        for _ in range(count):
            code = secrets.token_hex(6).upper()
            conn.execute('INSERT INTO redeem_codes(code, credits) VALUES(?,?)', (code, credits))
            codes.append(code)
        conn.commit()
        conn.close()
        return self._send_json({'codes': codes, 'credits': credits})

    # ---- 支付配置 ----
    def _get_payment_config(self):
        """API: 获取支付配置（QR码地址等）"""
        return self._send_json({
            'wechatQr': WECHAT_PAY_QR,
            'alipayQr': ALIPAY_PAY_QR,
            'account': PAYMENT_ACCOUNT,
            'expireHours': ORDER_EXPIRE_HOURS,
        })

    # ---- 积分套餐 & 订单 ----
    def _get_packages(self):
        """API: 获取积分套餐列表"""
        return self._send_json({'packages': CREDIT_PACKAGES})

    def _create_order(self, body):
        """API: 创建购买订单"""
        user = self._require_auth()
        if not user:
            return
        pkg_id = body.get('packageId', '')
        pkg = next((p for p in CREDIT_PACKAGES if p['id'] == pkg_id), None)
        if not pkg:
            return self._send_json({'error': '无效的套餐'}, 400)
        order_no = 'ORD' + datetime.now().strftime('%Y%m%d%H%M%S') + secrets.token_hex(3).upper()
        conn = self._get_db()
        conn.execute(
            'INSERT INTO orders (order_no, user_id, package_id, credits, amount) VALUES (?,?,?,?,?)',
            (order_no, user['id'], pkg_id, pkg['credits'], pkg['price'])
        )
        conn.commit()
        conn.close()
        return self._send_json({
            'orderNo': order_no,
            'amount': pkg['price'],
            'credits': pkg['credits'],
            'packageName': pkg['name']
        })

    def _get_my_orders(self):
        """API: 获取当前用户订单列表"""
        user = self._get_current_user()
        if not user:
            return self._send_json({'error': '未登录'}, 401)
        conn = self._get_db()
        rows = conn.execute(
            'SELECT order_no, package_id, credits, amount, status, pay_method, created_at, paid_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 50',
            (user['id'],)
        ).fetchall()
        conn.close()
        return self._send_json({'orders': [dict(r) for r in rows]})

    def _notify_paid(self, body):
        """API: 用户标记订单为'已转账'"""
        user = self._require_auth()
        if not user:
            return
        order_no = (body.get('orderNo') or '').strip()
        pay_method = (body.get('payMethod') or '').strip()  # wechat / alipay / other
        if not order_no:
            return self._send_json({'error': '缺少订单号'}, 400)
        conn = self._get_db()
        order = conn.execute('SELECT * FROM orders WHERE order_no=? AND user_id=?', (order_no, user['id'])).fetchone()
        if not order:
            conn.close()
            return self._send_json({'error': '订单不存在'}, 404)
        if order['status'] != 'pending':
            conn.close()
            return self._send_json({'error': '该订单状态无法操作'}, 400)
        conn.execute(
            "UPDATE orders SET status='notified', pay_method=? WHERE id=?",
            (pay_method, order['id'])
        )
        conn.commit()
        conn.close()
        return self._send_json({'success': True, 'orderNo': order_no, 'status': 'notified'})

    def _cancel_order(self, body):
        """API: 用户取消自己的待支付订单"""
        user = self._require_auth()
        if not user:
            return
        order_no = (body.get('orderNo') or '').strip()
        if not order_no:
            return self._send_json({'error': '缺少订单号'}, 400)
        conn = self._get_db()
        order = conn.execute('SELECT * FROM orders WHERE order_no=? AND user_id=?', (order_no, user['id'])).fetchone()
        if not order:
            conn.close()
            return self._send_json({'error': '订单不存在'}, 404)
        if order['status'] not in ('pending', 'notified'):
            conn.close()
            return self._send_json({'error': '该订单状态无法取消'}, 400)
        conn.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order['id'],))
        conn.commit()
        conn.close()
        return self._send_json({'success': True, 'orderNo': order_no})

    def _admin_confirm_order(self, body):
        """API: 管理员确认订单已支付"""
        admin_key = body.get('adminKey', '')
        if admin_key != ADMIN_KEY:
            return self._send_json({'error': '无权限'}, 403)
        order_no = (body.get('orderNo') or '').strip()
        if not order_no:
            return self._send_json({'error': '缺少订单号'}, 400)
        conn = self._get_db()
        order = conn.execute('SELECT * FROM orders WHERE order_no=?', (order_no,)).fetchone()
        if not order:
            conn.close()
            return self._send_json({'error': '订单不存在'}, 404)
        if order['status'] == 'paid':
            conn.close()
            return self._send_json({'error': '该订单已确认'}, 400)
        # 原子操作：仅在状态仍为pending时更新，防止双重确认
        cur = conn.execute("UPDATE orders SET status='paid', paid_at=datetime('now','localtime') WHERE id=? AND status != 'paid'", (order['id'],))
        if cur.rowcount == 0:
            conn.close()
            return self._send_json({'error': '该订单状态已变更'}, 400)
        # 增加积分
        conn.execute('UPDATE users SET ai_credits = ai_credits + ? WHERE id=?',
                     (order['credits'], order['user_id']))
        conn.commit()
        # 处理分销佣金：查看该用户是否有邀请人
        inviter_id = conn.execute('SELECT invited_by FROM users WHERE id=?', (order['user_id'],)).fetchone()
        if inviter_id and inviter_id['invited_by'] and inviter_id['invited_by'] > 0:
            commission_amount = round(order['amount'] * COMMISSION_RATE, 2)
            if commission_amount > 0:
                conn.execute(
                    'INSERT INTO commissions (user_id, from_user_id, order_id, amount, status) VALUES (?,?,?,?,?)',
                    (inviter_id['invited_by'], order['user_id'], order['id'], commission_amount, 'confirmed')
                )
                conn.execute(
                    'UPDATE users SET commission_balance = commission_balance + ? WHERE id=?',
                    (commission_amount, inviter_id['invited_by'])
                )
                conn.commit()
        conn.close()
        return self._send_json({'success': True, 'orderNo': order_no, 'credits': order['credits']})

    # ---- 邀请系统 ----
    def _get_invite_info(self):
        """API: 获取当前用户的邀请信息"""
        user = self._get_current_user()
        if not user:
            return self._send_json({'error': '未登录'}, 401)
        conn = self._get_db()
        invite_code = user.get('invite_code') or ''
        # 如果用户还没有邀请码（旧用户迁移场景），自动生成
        if not invite_code:
            invite_code = 'INV' + secrets.token_hex(4).upper()
            try:
                conn.execute('UPDATE users SET invite_code=? WHERE id=?', (invite_code, user['id']))
                conn.commit()
            except Exception:
                invite_code = ''
        # 邀请统计
        stats = conn.execute(
            'SELECT COUNT(*) as total FROM invite_records WHERE inviter_id=?', (user['id'],)
        ).fetchone()
        total_invited = stats['total'] if stats else 0
        # 邀请获得的积分
        reward_sum = conn.execute(
            'SELECT COALESCE(SUM(reward_inviter), 0) as total FROM invite_records WHERE inviter_id=?', (user['id'],)
        ).fetchone()['total']
        # 佣金信息
        commission_balance = user.get('commission_balance', 0) or 0
        total_commission = conn.execute(
            'SELECT COALESCE(SUM(amount), 0) as total FROM commissions WHERE user_id=? AND status IN ("confirmed","withdrawn")',
            (user['id'],)
        ).fetchone()['total']
        withdrawn = conn.execute(
            'SELECT COALESCE(SUM(amount), 0) as total FROM withdrawals WHERE user_id=? AND status IN ("approved","completed")',
            (user['id'],)
        ).fetchone()['total']
        # 邀请记录
        records = conn.execute(
            '''SELECT ir.created_at, u.username, u.nickname, ir.reward_inviter
               FROM invite_records ir JOIN users u ON ir.invitee_id = u.id
               WHERE ir.inviter_id=? ORDER BY ir.id DESC LIMIT 50''',
            (user['id'],)
        ).fetchall()
        conn.close()
        return self._send_json({
            'inviteCode': invite_code,
            'totalInvited': total_invited,
            'rewardCredits': reward_sum,
            'maxRewards': INVITE_MAX_REWARDS,
            'rewardPerInvite': INVITE_REWARD_INVITER,
            'rewardForInvitee': INVITE_REWARD_INVITEE,
            'commissionRate': COMMISSION_RATE,
            'commissionBalance': round(commission_balance, 2),
            'totalCommission': round(total_commission, 2),
            'totalWithdrawn': round(withdrawn, 2),
            'records': [dict(r) for r in records]
        })

    def _get_invite_leaderboard(self):
        """API: 获取邀请排行榜"""
        conn = self._get_db()
        rows = conn.execute(
            '''SELECT u.nickname, u.username, COUNT(ir.id) as invite_count,
                      COALESCE(SUM(ir.reward_inviter), 0) as total_reward
               FROM invite_records ir JOIN users u ON ir.inviter_id = u.id
               GROUP BY ir.inviter_id
               ORDER BY invite_count DESC LIMIT 20'''
        ).fetchall()
        conn.close()
        leaderboard = []
        for r in rows:
            name = r['nickname'] or r['username']
            # 脱敏处理
            if len(name) > 2:
                masked = name[0] + '*' * (len(name) - 2) + name[-1]
            else:
                masked = name[0] + '*'
            leaderboard.append({
                'name': masked,
                'inviteCount': r['invite_count'],
                'totalReward': r['total_reward']
            })
        return self._send_json({'leaderboard': leaderboard})

    def _get_commissions(self):
        """API: 获取佣金明细"""
        user = self._get_current_user()
        if not user:
            return self._send_json({'error': '未登录'}, 401)
        conn = self._get_db()
        rows = conn.execute(
            '''SELECT c.amount, c.status, c.created_at, u.nickname, u.username, o.order_no, o.amount as order_amount
               FROM commissions c
               JOIN users u ON c.from_user_id = u.id
               JOIN orders o ON c.order_id = o.id
               WHERE c.user_id=? ORDER BY c.id DESC LIMIT 50''',
            (user['id'],)
        ).fetchall()
        conn.close()
        return self._send_json({'commissions': [dict(r) for r in rows]})

    def _request_withdrawal(self, body):
        """API: 申请提现"""
        user = self._require_auth()
        if not user:
            return
        amount = float(body.get('amount', 0))
        method = (body.get('method') or '').strip()  # wechat / alipay
        account_info = (body.get('accountInfo') or '').strip()
        if amount < 1:
            return self._send_json({'error': '最低提现金额为1元'}, 400)
        if not method or not account_info:
            return self._send_json({'error': '请填写提现方式和账号'}, 400)
        balance = user.get('commission_balance', 0) or 0
        if amount > balance:
            return self._send_json({'error': f'可提现余额不足，当前余额 ¥{balance:.2f}'}, 400)
        conn = self._get_db()
        # 原子操作：直接用 WHERE 条件检查余额，防止并发超额提现
        cur = conn.execute(
            'UPDATE users SET commission_balance = commission_balance - ? WHERE id=? AND commission_balance >= ?',
            (amount, user['id'], amount)
        )
        if cur.rowcount == 0:
            conn.close()
            return self._send_json({'error': '可提现余额不足'}, 400)
        conn.execute(
            'INSERT INTO withdrawals (user_id, amount, method, account_info) VALUES (?,?,?,?)',
            (user['id'], amount, method, account_info)
        )
        conn.commit()
        new_balance = conn.execute('SELECT commission_balance FROM users WHERE id=?', (user['id'],)).fetchone()['commission_balance']
        conn.close()
        return self._send_json({'success': True, 'newBalance': round(new_balance, 2)})

    def _get_withdrawals(self):
        """API: 获取提现记录"""
        user = self._get_current_user()
        if not user:
            return self._send_json({'error': '未登录'}, 401)
        conn = self._get_db()
        rows = conn.execute(
            'SELECT amount, method, account_info, status, created_at, processed_at FROM withdrawals WHERE user_id=? ORDER BY id DESC LIMIT 50',
            (user['id'],)
        ).fetchall()
        conn.close()
        return self._send_json({'withdrawals': [dict(r) for r in rows]})

    def _admin_process_withdrawal(self, body):
        """API: 管理员处理提现"""
        admin_key = body.get('adminKey', '')
        if admin_key != ADMIN_KEY:
            return self._send_json({'error': '无权限'}, 403)
        wid = int(body.get('id', 0))
        action = body.get('action', '')  # approve / reject
        if not wid or action not in ('approve', 'reject'):
            return self._send_json({'error': '参数错误'}, 400)
        conn = self._get_db()
        w = conn.execute('SELECT * FROM withdrawals WHERE id=?', (wid,)).fetchone()
        if not w or w['status'] != 'pending':
            conn.close()
            return self._send_json({'error': '提现记录不存在或已处理'}, 400)
        if action == 'approve':
            conn.execute("UPDATE withdrawals SET status='completed', processed_at=datetime('now','localtime') WHERE id=?", (wid,))
        else:
            conn.execute("UPDATE withdrawals SET status='rejected', processed_at=datetime('now','localtime') WHERE id=?", (wid,))
            # 退回余额
            conn.execute('UPDATE users SET commission_balance = commission_balance + ? WHERE id=?',
                         (w['amount'], w['user_id']))
        conn.commit()
        conn.close()
        return self._send_json({'success': True})

    def _admin_list_orders(self, query):
        """API: 管理员查看所有订单"""
        admin_key = query.get('adminKey', '')
        if admin_key != ADMIN_KEY:
            return self._send_json({'error': '无权限'}, 403)
        status = query.get('status', '')
        conn = self._get_db()
        if status:
            rows = conn.execute(
                '''SELECT o.*, u.username, u.nickname, u.phone FROM orders o
                   JOIN users u ON o.user_id = u.id WHERE o.status=? ORDER BY o.id DESC LIMIT 100''',
                (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                '''SELECT o.*, u.username, u.nickname, u.phone FROM orders o
                   JOIN users u ON o.user_id = u.id ORDER BY o.id DESC LIMIT 100'''
            ).fetchall()
        conn.close()
        return self._send_json({'orders': [dict(r) for r in rows]})

    def _send_json(self, data, code=200):
        raw = json.dumps(data, ensure_ascii=False).encode('utf-8')
        # Gzip 压缩（仅当客户端支持且数据 > 512 字节时）
        accept_enc = self.headers.get('Accept-Encoding', '') if hasattr(self, 'headers') else ''
        if len(raw) > 512 and 'gzip' in accept_enc:
            compressed = gzip.compress(raw)
            self._set_json_headers(code)
            self.send_header('Content-Encoding', 'gzip')
            self.send_header('Content-Length', str(len(compressed)))
            self.end_headers()
            self.wfile.write(compressed)
        else:
            self._set_json_headers(code)
            self.end_headers()
            self.wfile.write(raw)

    MAX_BODY_SIZE = 10 * 1024 * 1024  # 10MB 请求体上限

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length > self.MAX_BODY_SIZE:
            self._send_json({'error': '请求体过大'}, 413)
            return None
        if length:
            return json.loads(self.rfile.read(length).decode('utf-8'))
        return {}

    def _get_db(self):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _parse_path(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = dict(urllib.parse.parse_qsl(parsed.query))
        return path, query

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '86400')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        path, query = self._parse_path()

        # --- 健康检查（零数据库操作，确保 < 1s 响应）---
        if path == '/healthz':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return

        # --- 公开路由 ---
        if path == '/api/auth/me':
            return self._auth_me()
        elif path == '/api/stats':
            return self._get_stats()
        elif path == '/api/monetization-guide':
            return self._send_json(MONETIZATION_GUIDE)
        elif path == '/api/categories':
            return self._send_json(ContentEngine.categories)
        elif path == '/api/version':
            return self._send_json({
                'version': BUILD_VERSION,
                'keyCount': len(SERVER_GEMINI_API_KEYS),
                'hasServerKey': bool(SERVER_GEMINI_API_KEY),
            })
        elif path == '/api/captcha':
            return self._get_captcha()
        # --- 需要登录的路由 ---
        elif path == '/api/posts':
            return self._get_posts(query)
        elif path.startswith('/api/posts/') and path.count('/') == 3:
            post_id = path.split('/')[-1]
            return self._get_post(post_id)
        elif path == '/api/calendar':
            return self._get_calendar(query)
        elif path == '/api/income':
            return self._get_income(query)
        elif path == '/api/account-stats':
            return self._get_account_stats()
        elif path == '/api/user/credits':
            return self._get_user_credits_info()
        elif path == '/api/packages':
            return self._get_packages()
        elif path == '/api/payment-config':
            return self._get_payment_config()
        elif path == '/api/orders/my':
            return self._get_my_orders()
        elif path == '/api/invite/info':
            return self._get_invite_info()
        elif path == '/api/invite/leaderboard':
            return self._get_invite_leaderboard()
        elif path == '/api/invite/commissions':
            return self._get_commissions()
        elif path == '/api/invite/withdrawals':
            return self._get_withdrawals()
        elif path == '/api/admin/orders':
            return self._admin_list_orders(query)
        elif path == '/api/content-plans':
            return self._get_content_plans(query)
        elif path.startswith('/api/export/'):
            post_id = path.split('/')[-1]
            return self._export_post(post_id)
        elif path.startswith('/api/note-images/'):
            return self._serve_note_image(path)
        elif path == '/api/generated-notes':
            return self._list_generated_notes()
        elif path.startswith('/api/task-status/'):
            task_id = path.split('/')[-1]
            return self._get_task_status(task_id)
        else:
            # 静态文件
            return super().do_GET()

    def do_POST(self):
        path, query = self._parse_path()
        body = self._read_body()

        # --- 公开路由 ---
        if path == '/api/auth/register':
            return self._auth_register(body)
        elif path == '/api/auth/send-code':
            return self._auth_send_code(body)
        elif path == '/api/auth/login':
            return self._auth_login(body)
        elif path == '/api/auth/login-sms':
            return self._auth_login_sms(body)
        elif path == '/api/auth/logout':
            return self._auth_logout()
        elif path == '/api/gemini-proxy':
            return self._gemini_proxy(body)
        elif path == '/api/ai-proxy':
            return self._gemini_proxy(body)
        elif path == '/api/baidu-search':
            return self._baidu_search(body)
        elif path == '/api/fetch-url':
            return self._fetch_url(body)
        # --- 需要登录的路由 ---
        elif path == '/api/posts':
            return self._create_post(body)
        elif path == '/api/generate':
            return self._generate_posts(body)
        elif path == '/api/schedule':
            return self._schedule_posts(body)
        elif path == '/api/income':
            return self._create_income(body)
        elif path == '/api/account-stats':
            return self._save_account_stats(body)
        elif path == '/api/export-batch':
            return self._export_batch(body)
        elif path == '/api/redeem':
            return self._redeem_code(body)
        elif path == '/api/admin/gen-codes':
            return self._admin_gen_codes(body)
        elif path == '/api/orders/create':
            return self._create_order(body)
        elif path == '/api/orders/notify-paid':
            return self._notify_paid(body)
        elif path == '/api/orders/cancel':
            return self._cancel_order(body)
        elif path == '/api/admin/orders/confirm':
            return self._admin_confirm_order(body)
        elif path == '/api/invite/withdraw':
            return self._request_withdrawal(body)
        elif path == '/api/admin/withdrawal':
            return self._admin_process_withdrawal(body)
        elif path == '/api/content-plans':
            return self._create_content_plan(body)
        elif path == '/api/generate-note':
            return self._generate_xhs_note(body)
        elif path == '/api/ai-match-cards':
            return self._ai_match_cards(body)
        elif path == '/api/generate-prompt-record':
            return self._generate_prompt_record(body)
        elif path == '/api/render-card-image':
            return self._render_card_image_html(body)
        elif path == '/api/generate-card-image-v3':
            return self._generate_card_image_v3(body)
        elif path == '/api/generate-card-image-v3-async':
            return self._generate_card_image_v3_async(body)
        else:
            self._send_json({'error': 'Not found'}, 404)

    def do_PUT(self):
        path, query = self._parse_path()
        body = self._read_body()

        if path.startswith('/api/posts/'):
            post_id = path.split('/')[-1]
            return self._update_post(post_id, body)
        elif path.startswith('/api/content-plans/'):
            plan_id = path.split('/')[-1]
            return self._update_content_plan(plan_id, body)
        else:
            self._send_json({'error': 'Not found'}, 404)

    def do_DELETE(self):
        path, query = self._parse_path()

        if path.startswith('/api/posts/'):
            post_id = path.split('/')[-1]
            return self._delete_post(post_id)
        elif path.startswith('/api/income/'):
            inc_id = path.split('/')[-1]
            return self._delete_income(inc_id)
        elif path.startswith('/api/content-plans/'):
            plan_id = path.split('/')[-1]
            return self._delete_content_plan(plan_id)
        else:
            self._send_json({'error': 'Not found'}, 404)

    # ---- 用户认证 ----
    def _auth_register(self, body):
        phone = (body.get('phone') or '').strip()
        sms_code = (body.get('smsCode') or '').strip()
        username = (body.get('username') or '').strip()
        password = body.get('password') or ''
        nickname = (body.get('nickname') or '').strip()
        invite_code_input = (body.get('inviteCode') or '').strip().upper()
        captcha_token = (body.get('captchaToken') or '').strip()
        captcha_answer = body.get('captchaAnswer')
        # 手机号必填且格式校验
        if not self._is_valid_phone(phone):
            return self._send_json({'error': '请输入正确的11位手机号'}, 400)
        # 图形验证码校验（必填）
        if not self._verify_captcha(captcha_token, captcha_answer):
            return self._send_json({'error': '验证码错误或已过期，请重新获取'}, 400)
        # IP 注册频率限制
        ip = self._client_ip(self.headers)
        if ip:
            conn_ip = self._get_db()
            try:
                today_reg = conn_ip.execute(
                    "SELECT COUNT(*) as cnt FROM users WHERE created_at >= date('now','localtime') "
                    "AND id IN (SELECT user_id FROM sessions WHERE "
                    "SUBSTR(token,1,0)='' AND created_at >= date('now','localtime'))",
                    ()
                ).fetchone()['cnt']
            except Exception:
                today_reg = 0
            conn_ip.close()
            # 简单 IP 限制：检查 sms_codes 表中的注册记录
            conn_ip2 = self._get_db()
            try:
                ip_reg_count = conn_ip2.execute(
                    "SELECT COUNT(*) as cnt FROM sms_codes WHERE ip=? AND purpose='register_ok' AND date(created_at)=date('now','localtime')",
                    (ip,)
                ).fetchone()['cnt']
            except Exception:
                ip_reg_count = 0
            conn_ip2.close()
            if ip_reg_count >= REGISTER_IP_DAILY_LIMIT:
                return self._send_json({'error': f'该网络今日注册账号已达上限（{REGISTER_IP_DAILY_LIMIT}个），请明天再试'}, 429)
        # 注册不再需要短信验证码，仅图形验证码即可
        if len(username) < 2 or len(username) > 20:
            return self._send_json({'error': '用户名长度需2-20个字符'}, 400)
        if len(password) < 6:
            return self._send_json({'error': '密码至少6位'}, 400)
        conn = self._get_db()
        # 检查手机号唯一性
        try:
            phone_exists = conn.execute('SELECT id FROM users WHERE phone = ?', (phone,)).fetchone()
        except Exception:
            phone_exists = None
        if phone_exists:
            conn.close()
            return self._send_json({'error': '该手机号已注册'}, 409)
        exists = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if exists:
            conn.close()
            return self._send_json({'error': '用户名已存在'}, 409)
        # 检查邀请码是否有效
        inviter_id = 0
        if invite_code_input:
            inviter = conn.execute('SELECT id FROM users WHERE invite_code = ?', (invite_code_input,)).fetchone()
            if inviter:
                inviter_id = inviter['id']
        pw_hash = self._hash_password(password)
        my_invite_code = 'INV' + secrets.token_hex(4).upper()
        conn.execute('INSERT INTO users (username, password_hash, nickname, phone, invite_code, invited_by) VALUES (?,?,?,?,?,?)',
                     (username, pw_hash, nickname or username, phone, my_invite_code, inviter_id))
        conn.commit()
        uid = conn.execute('SELECT last_insert_rowid() as id').fetchone()['id']
        # 处理邀请奖励
        if inviter_id > 0:
            # 检查邀请人是否还有奖励额度
            invite_count = conn.execute(
                'SELECT COUNT(*) as cnt FROM invite_records WHERE inviter_id=?', (inviter_id,)
            ).fetchone()['cnt']
            if invite_count < INVITE_MAX_REWARDS:
                # 发放奖励
                conn.execute(
                    'INSERT INTO invite_records (inviter_id, invitee_id, reward_inviter, reward_invitee) VALUES (?,?,?,?)',
                    (inviter_id, uid, INVITE_REWARD_INVITER, INVITE_REWARD_INVITEE)
                )
                conn.execute('UPDATE users SET ai_credits = ai_credits + ? WHERE id=?',
                             (INVITE_REWARD_INVITER, inviter_id))
                conn.execute('UPDATE users SET ai_credits = ai_credits + ? WHERE id=?',
                             (INVITE_REWARD_INVITEE, uid))
                conn.commit()
        # 自动登录：创建 session
        token = secrets.token_urlsafe(48)
        expires = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('INSERT INTO sessions (user_id, token, expires_at) VALUES (?,?,?)',
                     (uid, token, expires))
        conn.commit()
        conn.close()
        self._send_json({'token': token, 'user': {'id': uid, 'username': username, 'nickname': nickname or username, 'avatar': ''}})
        # 记录注册 IP（用于限流）
        try:
            ip = self._client_ip(self.headers)
            conn2 = self._get_db()
            conn2.execute("INSERT INTO sms_codes (phone, purpose, code_hash, ip, expires_at) VALUES (?,?,?,?,datetime('now','localtime'))",
                         (phone, 'register_ok', 'n/a', ip))
            conn2.commit()
            conn2.close()
        except Exception:
            pass

    def _auth_login(self, body):
        username = (body.get('username') or '').strip()
        password = body.get('password') or ''
        if not username or not password:
            return self._send_json({'error': '请输入用户名/手机号和密码'}, 400)
        # 登录频率限制
        client_ip = self._client_ip(self.headers)
        rate_key = f'{client_ip}:{username}'
        now = time.time()
        fail_info = _login_fail_tracker.get(rate_key)
        if fail_info:
            elapsed = now - fail_info['first_fail']
            if elapsed > LOGIN_LOCKOUT_SECONDS:
                del _login_fail_tracker[rate_key]
            elif fail_info['count'] >= LOGIN_MAX_FAILS:
                remaining = int(LOGIN_LOCKOUT_SECONDS - elapsed)
                return self._send_json({'error': f'登录尝试过多，请{remaining}秒后重试'}, 429)
        conn = self._get_db()
        # 支持用户名或手机号登录
        try:
            user = conn.execute('SELECT * FROM users WHERE username = ? OR phone = ?', (username, username)).fetchone()
        except Exception:
            # phone 列可能不存在，回退到仅用户名
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if not user or not self._verify_password(password, user['password_hash']):
            conn.close()
            # 记录登录失败
            if rate_key in _login_fail_tracker:
                _login_fail_tracker[rate_key]['count'] += 1
            else:
                _login_fail_tracker[rate_key] = {'count': 1, 'first_fail': now}
            return self._send_json({'error': '用户名或密码错误'}, 401)
        # 登录成功，清除失败记录
        _login_fail_tracker.pop(rate_key, None)
        # 清理该用户的过期 session
        conn.execute('DELETE FROM sessions WHERE user_id = ? AND expires_at <= datetime("now","localtime")', (user['id'],))
        # 创建新 session
        token = secrets.token_urlsafe(48)
        expires = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('INSERT INTO sessions (user_id, token, expires_at) VALUES (?,?,?)',
                     (user['id'], token, expires))
        conn.commit()
        conn.close()
        self._send_json({'token': token, 'user': {'id': user['id'], 'username': user['username'], 'nickname': user['nickname'], 'avatar': user['avatar']}})

    def _auth_login_sms(self, body):
        phone = (body.get('phone') or '').strip()
        sms_code = (body.get('smsCode') or '').strip()
        if not self._is_valid_phone(phone):
            return self._send_json({'error': '请输入正确的11位手机号'}, 400)
        if not self._is_valid_sms_code(sms_code):
            return self._send_json({'error': '请输入6位短信验证码'}, 400)

        conn = self._get_db()
        user = conn.execute('SELECT * FROM users WHERE phone = ?', (phone,)).fetchone()
        if not user:
            conn.close()
            return self._send_json({'error': '该手机号未注册'}, 404)
        if not self._consume_sms_code(conn, phone, 'login', sms_code):
            conn.close()
            return self._send_json({'error': '验证码错误或已过期'}, 400)

        conn.execute('DELETE FROM sessions WHERE user_id = ? AND expires_at <= datetime("now","localtime")', (user['id'],))
        token = secrets.token_urlsafe(48)
        expires = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('INSERT INTO sessions (user_id, token, expires_at) VALUES (?,?,?)',
                     (user['id'], token, expires))
        conn.commit()
        conn.close()
        self._send_json({'token': token, 'user': {'id': user['id'], 'username': user['username'], 'nickname': user['nickname'], 'avatar': user['avatar']}})

    def _auth_logout(self):
        auth = self.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth[7:].strip()
            conn = self._get_db()
            conn.execute('DELETE FROM sessions WHERE token = ?', (token,))
            conn.commit()
            conn.close()
        self._send_json({'message': '已退出登录'})

    def _auth_me(self):
        user = self._get_current_user()
        if not user:
            return self._send_json({'error': '未登录', 'code': 'AUTH_REQUIRED'}, 401)
        self._send_json({'user': user})

    # ---- 笔记管理 ----
    def _get_posts(self, query):
        user = self._get_current_user()
        conn = self._get_db()
        sql = 'SELECT * FROM posts WHERE 1=1'
        params = []
        if user:
            sql += ' AND user_id = ?'
            params.append(user['id'])
        
        if query.get('status'):
            sql += ' AND status = ?'
            params.append(query['status'])
        if query.get('category'):
            sql += ' AND category = ?'
            params.append(query['category'])
        if query.get('starred'):
            sql += ' AND starred = 1'
        
        sql += ' ORDER BY created_at DESC'
        
        count_sql = sql.replace('SELECT *', 'SELECT COUNT(*) as total')
        total = conn.execute(count_sql, params).fetchone()['total']
        
        page = int(query.get('page', 1))
        limit = int(query.get('limit', 20))
        sql += ' LIMIT ? OFFSET ?'
        params.extend([limit, (page - 1) * limit])
        
        posts = [dict(r) for r in conn.execute(sql, params).fetchall()]
        conn.close()
        # 列表接口不返回完整图片数据（太大），只返回标记
        for p in posts:
            p['has_cover_image'] = bool(p.get('cover_image'))
            ci = p.get('content_images')
            try:
                import json as _json
                ci_list = _json.loads(ci) if ci else []
            except:
                ci_list = []
            p['content_images_count'] = len(ci_list)
            p.pop('cover_image', None)
            p.pop('content_images', None)
        
        self._send_json({'posts': posts, 'total': total, 'page': page, 'limit': limit})

    def _get_post(self, post_id):
        user = self._get_current_user()
        uid = user['id'] if user else 0
        conn = self._get_db()
        row = conn.execute('SELECT * FROM posts WHERE id = ? AND (user_id = ? OR user_id = 0)', (post_id, uid)).fetchone()
        conn.close()
        if row:
            d = dict(row)
            # 解析 content_images JSON
            ci = d.get('content_images')
            try:
                d['content_images'] = json.loads(ci) if ci else []
            except:
                d['content_images'] = []
            self._send_json(d)
        else:
            self._send_json({'error': '笔记不存在'}, 404)

    def _create_post(self, body):
        user = self._get_current_user()
        uid = user['id'] if user else 0
        cover_img = body.get('cover_image') or None
        content_imgs = body.get('content_images')
        content_imgs_json = json.dumps(content_imgs) if content_imgs else None
        conn = self._get_db()
        conn.execute(
            'INSERT INTO posts (title, content, category, tags, cover_text, status, scheduled_date, user_id, cover_image, content_images) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (body.get('title', ''), body.get('content', ''), body.get('category', '治愈'),
             body.get('tags', ''), body.get('cover_text', ''), body.get('status', 'draft'),
             body.get('scheduled_date'), uid, cover_img, content_imgs_json)
        )
        conn.commit()
        last_id = conn.execute('SELECT last_insert_rowid() as id').fetchone()['id']
        conn.close()
        self._send_json({'id': last_id, 'message': '创建成功'})

    def _update_post(self, post_id, body):
        user = self._get_current_user()
        uid = user['id'] if user else 0
        conn = self._get_db()
        # 所有权检查
        row = conn.execute('SELECT user_id FROM posts WHERE id = ?', (post_id,)).fetchone()
        if row and row['user_id'] != 0 and row['user_id'] != uid:
            conn.close()
            self._send_json({'error': '无权操作此笔记'}, 403)
            return
        fields = []
        params = []
        
        for key in ['title', 'content', 'category', 'tags', 'cover_text', 'status', 'scheduled_date', 'publish_date', 'likes', 'collects', 'comments', 'views', 'starred']:
            if key in body and body[key] is not None:
                fields.append(f'{key} = ?')
                params.append(body[key])
        # 图片字段
        if 'cover_image' in body:
            fields.append('cover_image = ?')
            params.append(body['cover_image'])
        if 'content_images' in body:
            fields.append('content_images = ?')
            params.append(json.dumps(body['content_images']) if body['content_images'] else None)
        
        if fields:
            fields.append("updated_at = datetime('now','localtime')")
            params.append(post_id)
            conn.execute(f"UPDATE posts SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()
        
        conn.close()
        self._send_json({'message': '更新成功'})

    def _delete_post(self, post_id):
        user = self._get_current_user()
        uid = user['id'] if user else 0
        conn = self._get_db()
        # 所有权检查
        row = conn.execute('SELECT user_id FROM posts WHERE id = ?', (post_id,)).fetchone()
        if row and row['user_id'] != 0 and row['user_id'] != uid:
            conn.close()
            self._send_json({'error': '无权删除此笔记'}, 403)
            return
        conn.execute('DELETE FROM posts WHERE id = ? AND (user_id = ? OR user_id = 0)', (post_id, uid))
        conn.commit()
        conn.close()
        self._send_json({'message': '删除成功'})

    # ---- 自动生成 ----
    def _generate_posts(self, body):
        count = int(body.get('count', 1))
        category = body.get('category') or None
        auto_save = body.get('autoSave', True)
        
        posts = ContentEngine.generate_batch(count, category)
        
        if auto_save:
            conn = self._get_db()
            for p in posts:
                conn.execute(
                    "INSERT INTO posts (title, content, category, tags, cover_text, status) VALUES (?,?,?,?,?,'draft')",
                    (p['title'], p['content'], p['category'], p['tags'], p['cover_text'])
                )
                p['id'] = conn.execute('SELECT last_insert_rowid() as id').fetchone()['id']
            conn.commit()
            conn.close()
        
        self._send_json({'posts': posts, 'message': f'成功生成 {len(posts)} 条笔记'})

    # ---- 排期管理 ----
    def _schedule_posts(self, body):
        post_ids = body.get('post_ids', [])
        start_date = body.get('start_date', datetime.now().isoformat())
        interval_hours = int(body.get('interval_hours', 24))
        
        if not post_ids:
            return self._send_json({'error': '请选择笔记'}, 400)
        
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00')) if 'T' in start_date else datetime.strptime(start_date, '%Y-%m-%d')
        
        conn = self._get_db()
        for i, pid in enumerate(post_ids):
            dt = start + timedelta(hours=i * interval_hours)
            conn.execute(
                "UPDATE posts SET status='scheduled', scheduled_date=? WHERE id=?",
                (dt.strftime('%Y-%m-%d %H:%M:%S'), pid)
            )
        conn.commit()
        conn.close()
        
        self._send_json({'message': f'已排期 {len(post_ids)} 条笔记'})

    def _get_calendar(self, query):
        conn = self._get_db()
        month = query.get('month', '')
        sql = "SELECT id, title, category, status, scheduled_date, publish_date FROM posts WHERE status IN ('scheduled','published')"
        params = []
        if month:
            sql += ' AND (scheduled_date LIKE ? OR publish_date LIKE ?)'
            params.extend([f'{month}%', f'{month}%'])
        sql += ' ORDER BY COALESCE(scheduled_date, publish_date)'
        
        events = [dict(r) for r in conn.execute(sql, params).fetchall()]
        conn.close()
        self._send_json(events)

    # ---- 收入管理 ----
    def _get_income(self, query):
        user = self._get_current_user()
        conn = self._get_db()
        month = query.get('month', '')
        
        sql = 'SELECT * FROM income WHERE 1=1'
        params = []
        if user:
            sql += ' AND user_id = ?'
            params.append(user['id'])
        if month:
            sql += ' AND date LIKE ?'
            params.append(f'{month}%')
        sql += ' ORDER BY date DESC'
        
        records = [dict(r) for r in conn.execute(sql, params).fetchall()]
        
        # 构造总收入和分来源查询 (共享 WHERE)
        where_parts = ['1=1']
        t_params = []
        if user:
            where_parts.append('user_id = ?')
            t_params.append(user['id'])
        if month:
            where_parts.append('date LIKE ?')
            t_params.append(f'{month}%')
        where_clause = ' AND '.join(where_parts)
        
        total = conn.execute(f'SELECT COALESCE(SUM(amount),0) as total FROM income WHERE {where_clause}', t_params).fetchone()['total']
        by_source = [dict(r) for r in conn.execute(f'SELECT source, SUM(amount) as total FROM income WHERE {where_clause} GROUP BY source', t_params).fetchall()]
        
        conn.close()
        self._send_json({'records': records, 'total': total, 'bySource': by_source})

    def _create_income(self, body):
        user = self._get_current_user()
        uid = user['id'] if user else 0
        conn = self._get_db()
        conn.execute(
            'INSERT INTO income (source, amount, description, post_id, date, user_id) VALUES (?,?,?,?,?,?)',
            (body['source'], body['amount'], body.get('description', ''),
             body.get('post_id'), body.get('date', datetime.now().strftime('%Y-%m-%d')), uid)
        )
        conn.commit()
        last_id = conn.execute('SELECT last_insert_rowid() as id').fetchone()['id']
        conn.close()
        self._send_json({'id': last_id, 'message': '添加成功'})

    def _delete_income(self, inc_id):
        user = self._get_current_user()
        uid = user['id'] if user else 0
        conn = self._get_db()
        # 所有权检查
        row = conn.execute('SELECT user_id FROM income WHERE id = ?', (inc_id,)).fetchone()
        if row and row['user_id'] != 0 and row['user_id'] != uid:
            conn.close()
            self._send_json({'error': '无权删除此记录'}, 403)
            return
        conn.execute('DELETE FROM income WHERE id = ? AND (user_id = ? OR user_id = 0)', (inc_id, uid))
        conn.commit()
        conn.close()
        self._send_json({'message': '删除成功'})

    # ---- 数据统计 ----
    def _get_stats(self):
        user = self._get_current_user()
        conn = self._get_db()
        uid_clause = 'WHERE user_id = ?' if user else 'WHERE 1=1'
        uid_params = [user['id']] if user else []
        
        total = conn.execute(f'SELECT COUNT(*) as c FROM posts {uid_clause}', uid_params).fetchone()['c']
        draft = conn.execute(f"SELECT COUNT(*) as c FROM posts {uid_clause} AND status='draft'", uid_params).fetchone()['c']
        scheduled = conn.execute(f"SELECT COUNT(*) as c FROM posts {uid_clause} AND status='scheduled'", uid_params).fetchone()['c']
        published = conn.execute(f"SELECT COUNT(*) as c FROM posts {uid_clause} AND status='published'", uid_params).fetchone()['c']
        total_income = conn.execute(f'SELECT COALESCE(SUM(amount),0) as t FROM income {uid_clause}', uid_params).fetchone()['t']
        
        current_month = datetime.now().strftime('%Y-%m')
        month_params = uid_params + [f'{current_month}%']
        month_income = conn.execute(f'SELECT COALESCE(SUM(amount),0) as t FROM income {uid_clause} AND date LIKE ?', month_params).fetchone()['t']
        
        cat_dist = [dict(r) for r in conn.execute(f'SELECT category, COUNT(*) as count FROM posts {uid_clause} GROUP BY category', uid_params).fetchall()]
        recent = [dict(r) for r in conn.execute(f'SELECT id, title, category, status, created_at FROM posts {uid_clause} ORDER BY created_at DESC LIMIT 5', uid_params).fetchall()]
        
        total_likes = conn.execute(f'SELECT COALESCE(SUM(likes),0) as t FROM posts {uid_clause}', uid_params).fetchone()['t']
        total_collects = conn.execute(f'SELECT COALESCE(SUM(collects),0) as t FROM posts {uid_clause}', uid_params).fetchone()['t']
        total_views = conn.execute(f'SELECT COALESCE(SUM(views),0) as t FROM posts {uid_clause}', uid_params).fetchone()['t']
        
        conn.close()
        
        self._send_json({
            'totalPosts': total, 'draftPosts': draft, 'scheduledPosts': scheduled, 'publishedPosts': published,
            'totalIncome': total_income, 'monthIncome': month_income,
            'categoryDist': cat_dist, 'recentPosts': recent,
            'totalLikes': total_likes, 'totalCollects': total_collects, 'totalViews': total_views
        })

    # ---- 账号数据 ----
    def _get_account_stats(self):
        user = self._get_current_user()
        conn = self._get_db()
        sql = 'SELECT * FROM account_stats'
        params = []
        if user:
            sql += ' WHERE user_id = ?'
            params.append(user['id'])
        sql += ' ORDER BY date DESC LIMIT 30'
        stats = [dict(r) for r in conn.execute(sql, params).fetchall()]
        conn.close()
        self._send_json(stats)

    def _save_account_stats(self, body):
        user = self._get_current_user()
        uid = user['id'] if user else 0
        conn = self._get_db()
        d = body.get('date', datetime.now().strftime('%Y-%m-%d'))
        conn.execute(
            'INSERT OR REPLACE INTO account_stats (date, followers, total_likes, total_collects, total_views, notes_count, user_id) VALUES (?,?,?,?,?,?,?)',
            (d, body.get('followers', 0), body.get('total_likes', 0), body.get('total_collects', 0),
             body.get('total_views', 0), body.get('notes_count', 0), uid)
        )
        conn.commit()
        conn.close()
        self._send_json({'message': '记录成功'})

    # ---- 导出 ----
    def _serve_note_image(self, path):
        """Serve images from xhs_notes/ directory safely."""
        import posixpath
        # Strip prefix: /api/note-images/数学_三下_.../slide_2.jpg -> 数学_三下_.../slide_2.jpg
        rel = path[len('/api/note-images/'):]
        rel = urllib.parse.unquote(rel)
        # Security: prevent path traversal
        rel = posixpath.normpath(rel)
        if rel.startswith('..') or rel.startswith('/') or ':' in rel:
            return self._send_json({'error': 'Invalid path'}, 403)
        full_path = os.path.join(BASE_DIR, 'xhs_notes', rel)
        if not os.path.isfile(full_path):
            return self._send_json({'error': 'Image not found'}, 404)
        ext = os.path.splitext(full_path)[1].lower()
        mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp'}
        content_type = mime_map.get(ext, 'application/octet-stream')
        with open(full_path, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'public, max-age=604800')
        self.end_headers()
        self.wfile.write(data)

    def _export_post(self, post_id):
        conn = self._get_db()
        row = conn.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
        conn.close()
        
        if not row:
            return self._send_json({'error': '笔记不存在'}, 404)
        
        post = dict(row)
        text = f"【标题】{post['title']}\n\n【正文】\n{post['content']}\n\n【标签】{post['tags']}\n\n【封面文字】{post['cover_text']}\n\n【分类】{post['category']}"
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Disposition', f'attachment; filename="note_{post_id}.txt"')
        self.end_headers()
        self.wfile.write(text.encode('utf-8'))

    def _export_batch(self, body):
        ids = body.get('ids', [])
        if not ids:
            return self._send_json({'error': '请选择笔记'}, 400)
        
        conn = self._get_db()
        placeholders = ','.join('?' * len(ids))
        posts = [dict(r) for r in conn.execute(f'SELECT * FROM posts WHERE id IN ({placeholders})', ids).fetchall()]
        conn.close()
        
        texts = []
        for p in posts:
            texts.append(f"===== 笔记 #{p['id']} =====\n【标题】{p['title']}\n\n【正文】\n{p['content']}\n\n【标签】{p['tags']}\n【封面文字】{p['cover_text']}\n【分类】{p['category']}\n【状态】{p['status']}")
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Disposition', 'attachment; filename="notes_export.txt"')
        self.end_headers()
        self.wfile.write('\n\n'.join(texts).encode('utf-8'))


    # ---- URL 内容抓取代理 ----
    def _fetch_url(self, body):
        """代理抓取指定 URL 的网页内容，针对小红书特殊优化"""
        import re as _re
        import html as _html

        url = (body.get('url', '') or '').strip()
        if not url:
            return self._send_json({'error': 'Missing url'}, 400)
        if not url.startswith(('http://', 'https://')):
            return self._send_json({'error': 'Invalid url'}, 400)

        is_xhs = 'xiaohongshu.com' in url or 'xhslink.com' in url

        # 小红书用 Mobile UA 获取 SSR 数据
        if is_xhs:
            ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        else:
            ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

        headers = {
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        if is_xhs:
            headers['Referer'] = 'https://www.xiaohongshu.com/'

        try:
            req = urllib.request.Request(url, headers=headers)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            resp = urllib.request.urlopen(req, timeout=20, context=ctx)
            raw = resp.read()

            # 解码
            encoding = 'utf-8'
            content_type = resp.headers.get('Content-Type', '')
            if 'charset=' in content_type:
                encoding = content_type.split('charset=')[-1].strip()
            try:
                html_text = raw.decode(encoding, errors='replace')
            except Exception:
                html_text = raw.decode('utf-8', errors='replace')

            # ===== 小红书特殊处理：从 __INITIAL_STATE__ 中提取笔记内容 =====
            if is_xhs:
                xhs_text = self._extract_xhs_note(html_text, _re, _html)
                if xhs_text and len(xhs_text) > 50:
                    return self._send_json({
                        'ok': True,
                        'text': xhs_text,
                        'length': len(xhs_text),
                        'url': url,
                        'method': 'xhs_ssr'
                    })

            # ===== 通用处理：提取页面纯文本 =====
            text = html_text
            text = _re.sub(r'<script[^>]*>[\s\S]*?</script>', '', text, flags=_re.IGNORECASE)
            text = _re.sub(r'<style[^>]*>[\s\S]*?</style>', '', text, flags=_re.IGNORECASE)
            text = _re.sub(r'<!--[\s\S]*?-->', '', text)
            text = _re.sub(r'<br\s*/?>', '\n', text, flags=_re.IGNORECASE)
            text = _re.sub(r'</(p|div|h[1-6]|li|tr)>', '\n', text, flags=_re.IGNORECASE)
            text = _re.sub(r'<[^>]+>', ' ', text)
            text = _html.unescape(text)
            text = _re.sub(r'[ \t]+', ' ', text)
            text = _re.sub(r'\n\s*\n+', '\n\n', text)
            text = text.strip()

            if len(text) > 30000:
                text = text[:30000] + '\n\n[内容已截断]'

            self._send_json({
                'ok': True,
                'text': text,
                'length': len(text),
                'url': url,
                'method': 'generic'
            })
        except Exception as e:
            self._send_json({
                'ok': False,
                'error': f'抓取失败: {str(e)}',
                'url': url
            }, 500)

    def _extract_xhs_note(self, html_text, _re, _html):
        """从小红书页面 __INITIAL_STATE__ 中提取笔记的标题和正文"""
        # 提取 __INITIAL_STATE__ JSON
        m = _re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{[\s\S]*?\})\s*</script>', html_text)
        if not m:
            return None

        state_str = m.group(1)
        # XHS 使用 \u002F 替代 /，先还原
        state_str = state_str.replace('\\u002F', '/')

        try:
            state = json.loads(state_str)
        except Exception:
            # JSON 解析失败，用正则提取关键字段
            return self._extract_xhs_note_regex(state_str, _re)

        # 从 state 中查找笔记数据
        note_data = None
        # 尝试多种路径
        for path in [
            lambda s: s.get('noteData', {}).get('data', {}).get('noteData', {}),
            lambda s: s.get('noteDetailMap', {}).get(list(s.get('noteDetailMap', {}).keys())[0] if s.get('noteDetailMap') else '', {}),
            lambda s: s.get('note', {}).get('noteDetailMap', {}).get(list(s.get('note', {}).get('noteDetailMap', {}).keys())[0] if s.get('note', {}).get('noteDetailMap') else '', {}),
        ]:
            try:
                nd = path(state)
                if nd and (nd.get('title') or nd.get('desc')):
                    note_data = nd
                    break
            except Exception:
                continue

        if not note_data:
            # 降级：在整个 state 字符串中用正则搜索
            return self._extract_xhs_note_regex(state_str, _re)

        # 组装文本
        parts = []
        title = note_data.get('title', '')
        if title:
            parts.append(f'标题：{title}')

        desc = note_data.get('desc', '')
        if desc:
            # 清理 XHS 话题标签格式
            desc = _re.sub(r'\[话题\]', '', desc)
            desc = desc.replace('\\n', '\n').replace('\\t', '\t')
            parts.append(f'\n正文：\n{desc}')

        # 用户信息
        user = note_data.get('user', {})
        if user:
            nick = user.get('nickName', '') or user.get('nickname', '')
            if nick:
                parts.append(f'\n发布者：{nick}')

        # 标签
        tags = note_data.get('tagList', [])
        if tags:
            tag_names = [t.get('name', '') for t in tags if t.get('name')]
            if tag_names:
                parts.append(f'标签：{", ".join(tag_names)}')

        # 互动数据
        interact = note_data.get('interactInfo', {})
        if interact:
            stats = []
            if interact.get('likedCount'): stats.append(f'点赞 {interact["likedCount"]}')
            if interact.get('collectedCount'): stats.append(f'收藏 {interact["collectedCount"]}')
            if interact.get('commentCount'): stats.append(f'评论 {interact["commentCount"]}')
            if interact.get('shareCount'): stats.append(f'转发 {interact["shareCount"]}')
            if stats:
                parts.append(f'互动数据：{" | ".join(stats)}')

        return '\n'.join(parts) if parts else None

    def _extract_xhs_note_regex(self, state_str, _re):
        """当 JSON 解析失败时，用正则从 state 字符串中提取笔记内容"""
        parts = []

        # 提取标题
        title_m = _re.search(r'"title"\s*:\s*"([^"]{2,200})"', state_str)
        # 找最后一个 title（通常是笔记标题而非热搜标题）
        titles = _re.findall(r'"title"\s*:\s*"([^"]{2,200})"', state_str)
        if titles:
            # 笔记标题通常在 noteData 附近，取最长的一个作为候选
            note_title = max(titles, key=len)
            parts.append(f'标题：{note_title}')

        # 提取正文 desc
        desc_m = _re.search(r'"desc"\s*:\s*"((?:[^"\\]|\\.){10,})"', state_str)
        if desc_m:
            desc = desc_m.group(1)
            desc = desc.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
            desc = _re.sub(r'\[话题\]', '', desc)
            parts.append(f'\n正文：\n{desc}')

        # 提取用户昵称
        nick_m = _re.search(r'"nickName"\s*:\s*"([^"]{1,50})"', state_str)
        if nick_m:
            parts.append(f'\n发布者：{nick_m.group(1)}')

        # 提取标签
        tag_names = _re.findall(r'"name"\s*:\s*"([^"]{1,30})"[^}]*"type"\s*:\s*"topic"', state_str)
        if not tag_names:
            tag_names = _re.findall(r'"type"\s*:\s*"topic"[^}]*"name"\s*:\s*"([^"]{1,30})"', state_str)
        if tag_names:
            parts.append(f'标签：{", ".join(tag_names)}')

        # 提取互动数据
        liked_m = _re.search(r'"likedCount"\s*:\s*"(\d+)"', state_str)
        collected_m = _re.search(r'"collectedCount"\s*:\s*"(\d+)"', state_str)
        comment_m = _re.search(r'"commentCount"\s*:\s*"(\d+)"', state_str)
        stats = []
        if liked_m: stats.append(f'点赞 {liked_m.group(1)}')
        if collected_m: stats.append(f'收藏 {collected_m.group(1)}')
        if comment_m: stats.append(f'评论 {comment_m.group(1)}')
        if stats:
            parts.append(f'互动数据：{" | ".join(stats)}')

        return '\n'.join(parts) if parts else None

    # ---- 百度搜索小红书笔记 ----
    def _baidu_search(self, body):
        """搜索百度 site:xiaohongshu.com 获取真实小红书笔记标题和摘要"""
        import re as _re
        import html as _html

        keyword = (body.get('keyword', '') or '').strip()
        if not keyword:
            return self._send_json({'error': 'Missing keyword'}, 400)

        count = min(int(body.get('count', 10)), 20)
        query = f'site:xiaohongshu.com {keyword}'
        encoded_query = urllib.parse.quote(query)
        url = f'https://www.baidu.com/s?wd={encoded_query}&rn={count}'

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            # 百度不走代理（国内网站无需翻墙）
            no_proxy_opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=_SSL_CTX)
            )
            resp = no_proxy_opener.open(req, timeout=15)
            html_text = resp.read().decode('utf-8', errors='replace')

            results = []
            # 提取百度搜索结果：标题和摘要
            # 百度搜索结果在 class="result" 的 div 中
            blocks = _re.findall(
                r'<div[^>]*class="result[^"]*"[^>]*>[\s\S]*?(?=<div[^>]*class="result|$)',
                html_text
            )
            if not blocks:
                # 备用：尝试提取 <h3> 标签
                blocks = _re.findall(r'<h3[^>]*>[\s\S]*?</h3>[\s\S]*?(?=<h3|$)', html_text)

            for block in blocks[:count]:
                # 提取标题
                title_match = _re.search(r'<h3[^>]*>([\s\S]*?)</h3>', block)
                title = ''
                link = ''
                if title_match:
                    title_html = title_match.group(1)
                    # 提取链接
                    link_match = _re.search(r'href="([^"]*)"', title_html)
                    if link_match:
                        link = link_match.group(1)
                    # 去掉 HTML 标签
                    title = _re.sub(r'<[^>]+>', '', title_html).strip()
                    title = _html.unescape(title)

                # 提取摘要
                abstract = ''
                abs_match = _re.search(
                    r'<span[^>]*class="content-right_[^"]*"[^>]*>([\s\S]*?)</span>',
                    block
                )
                if not abs_match:
                    abs_match = _re.search(r'<div[^>]*class="c-abstract[^"]*"[^>]*>([\s\S]*?)</div>', block)
                if not abs_match:
                    abs_match = _re.search(r'<span[^>]*class=".*?abstract.*?"[^>]*>([\s\S]*?)</span>', block)
                if abs_match:
                    abstract = _re.sub(r'<[^>]+>', '', abs_match.group(1)).strip()
                    abstract = _html.unescape(abstract)

                if title:
                    results.append({
                        'title': title,
                        'abstract': abstract,
                        'link': link,
                    })

            self._send_json({'results': results, 'query': query, 'count': len(results)})
        except Exception as e:
            self._send_json({'error': f'百度搜索失败: {str(e)}', 'results': []}, 200)


    # ---- 内容规划 CRUD ----
    def _get_content_plans(self, query):
        user = self._require_auth()
        if not user: return
        month = query.get('month', '')  # 格式 2026-03
        conn = self._get_db()
        if month:
            rows = conn.execute(
                "SELECT * FROM content_plans WHERE user_id=? AND plan_date LIKE ? ORDER BY plan_date, plan_time",
                (user['id'], month + '%')
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM content_plans WHERE user_id=? ORDER BY plan_date DESC, plan_time LIMIT 100",
                (user['id'],)
            ).fetchall()
        conn.close()
        self._send_json([dict(r) for r in rows])

    def _create_content_plan(self, body):
        user = self._require_auth()
        if not user: return
        title = (body.get('title') or '').strip()
        plan_date = (body.get('plan_date') or '').strip()
        if not title or not plan_date:
            return self._send_json({'error': '标题和日期不能为空'}, 400)
        conn = self._get_db()
        conn.execute(
            'INSERT INTO content_plans(user_id, title, topic, plan_date, plan_time, notes, category) VALUES(?,?,?,?,?,?,?)',
            (user['id'], title, body.get('topic', ''), plan_date,
             body.get('plan_time', '10:00'), body.get('notes', ''), body.get('category', ''))
        )
        conn.commit()
        plan_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.close()
        self._send_json({'id': plan_id, 'ok': True})

    def _update_content_plan(self, plan_id, body):
        user = self._require_auth()
        if not user: return
        conn = self._get_db()
        plan = conn.execute('SELECT * FROM content_plans WHERE id=? AND user_id=?', (plan_id, user['id'])).fetchone()
        if not plan:
            conn.close()
            return self._send_json({'error': '计划不存在'}, 404)
        fields, vals = [], []
        for key in ['title', 'topic', 'plan_date', 'plan_time', 'status', 'notes', 'category']:
            if key in body:
                fields.append(f'{key}=?')
                vals.append(body[key])
        if fields:
            vals.append(plan_id)
            conn.execute(f"UPDATE content_plans SET {','.join(fields)} WHERE id=?", vals)
            conn.commit()
        conn.close()
        self._send_json({'ok': True})

    def _delete_content_plan(self, plan_id):
        user = self._require_auth()
        if not user: return
        conn = self._get_db()
        conn.execute('DELETE FROM content_plans WHERE id=? AND user_id=?', (plan_id, user['id']))
        conn.commit()
        conn.close()
        self._send_json({'ok': True})

    # ---- Gemini API 代理 ----
    def _gemini_proxy(self, body):
        """代理转发 Gemini API 请求，解决浏览器无法直接访问 Google API 的问题"""
        # 所有模型统一使用多 Key 轮询
        model = body.get('model', 'gemini-2.5-flash')
        is_image_model = 'image' in model or 'banana' in model or 'imagen' in model
        api_key = _get_next_server_key() or body.get('apiKey', '')
        payload = body.get('payload', {})
        action = body.get('action', 'generateContent')  # generateContent or listModels
        feature = body.get('feature', action)  # 用于追踪功能类型

        # 智能模型路由：对高质量需求的功能，自动将 flash-lite 升级为 flash
        # flash-lite 适合简单任务（标签、评分），但内容生成/分析等需要更强能力
        UPGRADE_FEATURES = {
            '内容生成', '内容分析', '内容搜索分析', '品牌定位', '竞品分析',
            '笔记改写', '一键润色', '爆款标题', '内容规划', 'AB测试',
            '热词分析', '图片配文', '评论话术', '生成评论话术',
            'ai_card_match', 'template_match', 'template_match_batch',
            'tmpl_ai_gen', 'tmpl_palette', 'tmpl_transfer',
        }
        original_model = model
        if model == 'gemini-2.5-flash-lite' and feature in UPGRADE_FEATURES:
            model = 'gemini-2.5-flash'
            print(f'[ModelRoute] {feature}: {original_model} → {model} (auto-upgrade)')


        # AI 配额检查（传入 feature 以判断所需积分）
        user = self._get_current_user()
        if user:
            allowed, info = self._check_ai_quota(user, feature)
            if not allowed:
                cost = self._get_feature_cost(feature)
                return self._send_json({
                    'error': {'code': 429, 'message': f'积分不足（需要{cost}积分），请充值AI积分继续使用'},
                    'quotaExceeded': True,
                    'usage': info
                }, 429)

        # action 只允许合法的 Gemini API 动作，中文标签归入 feature
        VALID_ACTIONS = ('generateContent', 'streamGenerateContent', 'listModels', 'countTokens')
        if action not in VALID_ACTIONS:
            feature = action  # 保留中文标签用于追踪
            action = 'generateContent'

        if not api_key:
            return self._send_json({'error': 'Missing apiKey and server GEMINI_API_KEY'}, 400)

        # Render Standard 方案网关超时约 300 秒
        is_image_model = 'image' in model or 'banana' in model or 'imagen' in model
        timeout = 180 if is_image_model else 120

        # 图片模型请求节流：强制最小间隔，防止连续请求导致502
        if is_image_model:
            global _last_image_gen_time
            with _image_gen_lock:
                now = time.time()
                elapsed_since_last = now - _last_image_gen_time
                if elapsed_since_last < IMAGE_GEN_MIN_GAP:
                    wait_time = IMAGE_GEN_MIN_GAP - elapsed_since_last
                    print(f'[ImageThrottle] 距上次图片请求仅{elapsed_since_last:.1f}s, 等待{wait_time:.1f}s')
                    time.sleep(wait_time)
                _last_image_gen_time = time.time()

        # 多 Key 自动重试：429/500/503 时切换 Key + 渐进退避
        # Phase 1: 每个 Key 尝试一轮（快速切换，2s间隔）
        # Phase 2: keys 耗尽后，额外重试最后一个 key（递增退避 5s/10s/15s）
        n_keys = len(SERVER_GEMINI_API_KEYS)
        PHASE1_DELAY = 2.0             # Key 切换间隔
        PHASE2_DELAYS = [5, 10, 15]    # 额外退避轮次
        max_retries = n_keys + len(PHASE2_DELAYS) if n_keys > 1 else 1 + len(PHASE2_DELAYS)
        last_err_json, last_err_code = None, 500

        for attempt in range(max_retries):
            if attempt > 0:
                # Phase1: 切换下一个 Key; Phase2: 保持上一个 Key 但加长等待
                if attempt < n_keys:
                    api_key = _get_next_server_key()
                    delay = PHASE1_DELAY
                else:
                    delay = PHASE2_DELAYS[min(attempt - n_keys, len(PHASE2_DELAYS) - 1)]
                if not api_key:
                    break
                phase = 'keyRotate' if attempt < n_keys else 'backoff'
                print(f'[GeminiProxy] 重试 {attempt}/{max_retries-1} ({phase}), key=...{api_key[-6:]}, 等待{delay}s')
                time.sleep(delay)

            try:
                if action == 'listModels':
                    url = f'{GEMINI_API_BASE}/v1beta/models?key={api_key}'
                    req = urllib.request.Request(url)
                else:
                    url = f'{GEMINI_API_BASE}/v1beta/models/{model}:{action}?key={api_key}'
                    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
                    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json; charset=utf-8'})

                resp = _OPENER.open(req, timeout=timeout)
                result = json.loads(resp.read().decode('utf-8'))

                # 成功后记录AI用量
                if user and action != 'listModels':
                    self._record_ai_usage(user['id'], feature)

                if attempt > 0:
                    print(f'[GeminiProxy] ✅ 重试{attempt}次后成功 ({model})')
                return self._send_json(result)
            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8', errors='replace')
                try:
                    err_json = json.loads(err_body)
                except:
                    err_json = {'error': {'code': e.code, 'message': err_body[:500]}}
                last_err_json, last_err_code = err_json, e.code
                # 可重试的错误码：429 限频 / 500 服务器错误 / 503 过载
                if e.code in (429, 500, 503) and attempt < max_retries - 1:
                    continue  # delay 在循环顶部处理
                print(f'[GeminiProxy] ❌ {model} 最终失败: HTTP {e.code} (尝试{attempt+1}次)')
                return self._send_json(err_json, e.code)
            except Exception as e:
                last_err_json = {'error': {'code': 500, 'message': str(e)}}
                last_err_code = 500
                if attempt < max_retries - 1:
                    continue  # delay 在循环顶部处理
                print(f'[GeminiProxy] ❌ {model} 网络错误: {e} (尝试{attempt+1}次)')
                return self._send_json(last_err_json, 500)

        # 所有重试都失败
        print(f'[GeminiProxy] ❌ {model} 所有 {max_retries} 次重试失败')
        self._send_json(last_err_json or {'error': {'code': 503, 'message': f'所有API Key均返回503，模型 {model} 当前繁忙，请稍后重试'}}, last_err_code)

    # ============ 笔记工坊 - AI 笔记生成 ============
    def _generate_xhs_note(self, body):
        """从知识卡片数据生成小红书笔记"""
        subject = body.get('subject', '数学')
        grade_short = body.get('grade_short', '三下')
        template = body.get('template', '反差型')
        card_ids = body.get('card_ids', [])  # 可选指定卡片

        # 根据 subject 判断文件夹和文件名
        _WELLNESS_SUBJECTS = {'养生', '减脂', '养生减脂', '融合'}
        _CULTURE_SUBJECTS = {'国学'}
        if subject in _CULTURE_SUBJECTS:
            folder = '国学文化'
            card_file = os.path.join(PUBLIC_DIR, 'knowledge_cards', folder, f'{subject}_{grade_short}.json')
            boom_file = None
            exam_file = None
            all_wellness_files = []
            culture_dir = os.path.join(PUBLIC_DIR, 'knowledge_cards', folder)
            if os.path.isdir(culture_dir):
                for fn in os.listdir(culture_dir):
                    if fn.endswith('.json'):
                        all_wellness_files.append(os.path.join(culture_dir, fn))
        elif subject in _WELLNESS_SUBJECTS:
            folder = '养生减脂'
            # 养生减脂的文件名: {subject}_{grade_short}.json
            card_file = os.path.join(PUBLIC_DIR, 'knowledge_cards', folder, f'{subject}_{grade_short}.json')
            boom_file = os.path.join(PUBLIC_DIR, 'knowledge_cards', folder, '养生减脂_爆款.json')
            exam_file = None
            # 也搜索整个目录下所有文件
            all_wellness_files = []
            wellness_dir = os.path.join(PUBLIC_DIR, 'knowledge_cards', folder)
            if os.path.isdir(wellness_dir):
                for fn in os.listdir(wellness_dir):
                    if fn.endswith('.json'):
                        all_wellness_files.append(os.path.join(wellness_dir, fn))
        else:
            folder = '小学'
            card_file = os.path.join(PUBLIC_DIR, 'knowledge_cards', folder, f'{subject}_{grade_short}.json')
            boom_file = os.path.join(PUBLIC_DIR, 'knowledge_cards', folder, f'{subject}_{grade_short}_爆款.json')
            exam_file = os.path.join(PUBLIC_DIR, 'knowledge_cards', folder, f'{subject}_{grade_short}_考卷.json')
            all_wellness_files = []

        # 读取卡片数据
        files_to_search = [f for f in [card_file, boom_file] if f]
        if exam_file:
            files_to_search.append(exam_file)
        if all_wellness_files:
            files_to_search = list(set(files_to_search + all_wellness_files))

        cards_data = []
        for fp in files_to_search:
            if os.path.exists(fp):
                try:
                    d = json.loads(open(fp, encoding='utf-8').read())
                    for u in d.get('units', []):
                        for c in u.get('cards', []):
                            if not card_ids or c.get('card_id') in card_ids or c.get('full_id') in card_ids:
                                cards_data.append(c)
                except:
                    pass

        if not cards_data:
            return self._send_json({'error': '未找到卡片数据'}, 404)

        # 选取适合模板的卡片（最多6张）
        import random
        template_card_map = {
            '反差型': ['陷阱卡','辨析卡','易错字陷阱卡','易混词陷阱卡','语法纠错卡','易错卡','易错字卡','反差卡','翻车卡','误区卡'],
            '挑战型': ['挑战卡','速算卡','发音挑战卡','古诗默写挑战卡','拼音闯关卡','笔顺挑战卡','挑战卡_养生'],
            '干货型': ['方法卡','公式卡','概念卡','阅读技巧卡','写作方法卡','词汇卡','语法卡','句型卡','修辞手法卡','阅读理解技巧卡',
                     '干货卡','科普卡','清单卡','食疗卡','食谱卡','体质卡','体质调理卡','日常习惯卡','穴位卡'],
            '故事型': ['生活卡','思维卡','对战卡','情景对话卡','亲子古诗PK卡','亲子英语PK卡','看图写话卡',
                     '对比卡','体态卡','跟练卡','运动卡','减脂卡'],
            '考前冲刺型': ['填空满分卡','选择秒杀卡','计算零失误卡','判断火眼卡','应用题拆解卡','操作题规范卡',
                       '拼写零错卡','默写满分卡','作文得分卡','听力得分卡','填空必会卡','写作模板卡'],
            '满分攻略型': ['填空满分卡','选择秒杀卡','选择审题卡','选择攻略卡','计算零失误卡','判断火眼卡',
                       '应用题拆解卡','操作题规范卡','拼写零错卡','默写满分卡','阅读答题卡','句子变换卡',
                       '作文得分卡','听力得分卡','填空必会卡','匹配速解卡','阅读通关卡','写作模板卡'],
        }
        preferred = template_card_map.get(template, [])
        matched = [c for c in cards_data if c.get('type') in preferred]
        if len(matched) < 3:
            matched = cards_data  # fallback to all
        selected = random.sample(matched, min(5, len(matched)))

        cards_text = ""
        for i, c in enumerate(selected, 1):
            cards_text += f"\n卡片{i}: [{c.get('type','')}] {c.get('title','')}\n"
            if c.get('definition'):
                cards_text += f"  定义: {c.get('definition','')}\n"
            if c.get('description'):
                cards_text += f"  描述: {c.get('description','')}\n"
            points = c.get('core_points') or c.get('key_steps') or c.get('tips') or []
            if points:
                cards_text += f"  要点: {'; '.join(points[:5])}\n"
            ex = c.get('example', {})
            if isinstance(ex, dict) and ex:
                cards_text += f"  例题: {ex.get('question','')} → {ex.get('answer','')}\n"
            if c.get('memory_tip'):
                cards_text += f"  口诀: {c.get('memory_tip','')}\n"
            hook = c.get('emotion_hook', '')
            if hook:
                cards_text += f"  钩子: {hook}\n"
            trap = c.get('trap_point', '')
            if trap:
                cards_text += f"  陷阱点: {trap}\n"
            # 养生专属字段
            if c.get('myth'):
                cards_text += f"  误区: {c.get('myth','')}\n"
            if c.get('truth'):
                cards_text += f"  真相: {c.get('truth','')}\n"
            if c.get('contrast_before'):
                cards_text += f"  反差前: {c.get('contrast_before','')}\n"
            if c.get('contrast_after'):
                cards_text += f"  反差后: {c.get('contrast_after','')}\n"
            # 考卷专题专属字段
            if c.get('exam_frequency'):
                cards_text += f"  考试频率: {c.get('exam_frequency','')}\n"
            if c.get('score_weight'):
                cards_text += f"  分值占比: {c.get('score_weight','')}\n"
            for ef in ['fill_strategy','choice_tricks','calc_checklist','judge_traps',
                       'problem_model','operation_steps','high_freq_words','audit_points',
                       'must_dictate','answer_templates','transform_rules','writing_formulas',
                       'listening_strategy','choice_focus','must_know_words','match_method',
                       'reading_skills','writing_frames']:
                val = c.get(ef)
                if val:
                    if isinstance(val, list):
                        cards_text += f"  {ef}: {'; '.join(str(v) for v in val[:5])}\n"
                    else:
                        cards_text += f"  {ef}: {val}\n"

        # ── Prompt工程智慧注入 ──
        prompt_wisdom = ""
        card_context = body.get('card_context')
        prompt_context = body.get('prompt_context')
        if card_context or prompt_context:
            prompt_wisdom += "\n\n🔗 【Prompt工程智慧 - 来自五角色流水线分析】\n"
            if prompt_context:
                pc = prompt_context
                if isinstance(pc, dict):
                    r1 = pc.get('R1', {})
                    r2 = pc.get('R2', {})
                    r3 = pc.get('R3', {})
                    if r1:
                        prompt_wisdom += f"\n📚 R1 教研专家分析:\n"
                        prompt_wisdom += f"  选题: {r1.get('selected_problem', '')}\n"
                        prompt_wisdom += f"  陷阱点: {r1.get('trap_point', '')}\n"
                        prompt_wisdom += f"  Top3易错: {'; '.join(r1.get('top3_mistakes', []))}\n"
                        prompt_wisdom += f"  为何重要: {r1.get('why_important', '')}\n"
                    if r2:
                        prompt_wisdom += f"\n🎓 R2 教学设计师智慧:\n"
                        prompt_wisdom += f"  顿悟时刻: {r2.get('eureka_moment', '')}\n"
                        prompt_wisdom += f"  生活类比: {r2.get('analogy', '')}\n"
                        prompt_wisdom += f"  创新策略: {r2.get('novel_strategy', '')}\n"
                        prompt_wisdom += f"  灵魂口诀: {r2.get('soul_mnemonic', '')}\n"
                    if r3:
                        prompt_wisdom += f"\n📱 R3 小红书策划:\n"
                        prompt_wisdom += f"  爆款标题: {r3.get('best_title', '')}\n"
                        prompt_wisdom += f"  情绪基调: {r3.get('emotion_tone', '')}\n"
                        prompt_wisdom += f"  钩子类型: {r3.get('hook_type', '')}\n"
                        prompt_wisdom += f"  系列标签: {r3.get('series_tag', '')}\n"
                        prompt_wisdom += f"  IP状态: {r3.get('ip_character_state', '')}\n"
            if card_context and isinstance(card_context, dict):
                cc = card_context
                if cc.get('emotion_hook'):
                    prompt_wisdom += f"\n💥 情绪钩子: {cc['emotion_hook']}\n"
                if cc.get('trap_point'):
                    prompt_wisdom += f"🪤 卡片陷阱点: {cc['trap_point']}\n"
                mistakes = cc.get('mistakes', [])
                if mistakes:
                    prompt_wisdom += f"⚠️ 易错点: {'; '.join(m.get('wrong','') + '→' + m.get('correct','') for m in mistakes[:3] if isinstance(m, dict))}\n"

            prompt_wisdom += "\n请充分利用以上Prompt工程智慧来丰富笔记内容：\n"
            prompt_wisdom += "- 使用R1的陷阱分析来设置认知冲突\n"
            prompt_wisdom += "- 使用R2的顿悟时刻和类比来打造'啊哈'体验\n"
            prompt_wisdom += "- 使用R2的灵魂口诀作为记忆锚点\n"
            prompt_wisdom += "- 参考R3的爆款标题风格和情绪基调\n"
            prompt_wisdom += "- 使用钩子类型来设计封面和开头\n"

        note_prompt = f"""你是一位小红书教育内容创作高手，擅长将知识卡片转化为高传播力的小红书笔记。

以下是{subject} {grade_short}的知识卡片数据：
{cards_text}
{prompt_wisdom}
请基于以上卡片内容，用「{template}」模板风格，生成一篇完整的小红书笔记。

模板风格说明：
- 反差型：设置认知冲突→暴露错误→揭示正确→引发讨论
- 挑战型：发起挑战→限时→公布答案→评级
- 干货型：痛点引入→系统知识点→口诀总结→收藏引导
- 故事型：生活场景→遇到问题→解决方案→触动共鸣
- 考前冲刺型：倒计时紧迫感→必考清单→快速提分技巧→检查提醒→加油打气
- 满分攻略型：题型拆解→得分策略→答题模板→避坑清单→满分示范

⚠️ 严格字数限制（必须遵守）：
- 标题 ≤ 20字（含emoji，超过20字视为不合格）
- 正文 ≤ 1000字（含emoji和标点，超过1000字视为不合格）
- 候选标题每条 ≤ 20字

请输出JSON格式（不要markdown代码块），包含以下字段：
{{
  "note_id": "{subject}_{grade_short}_{template}_自动生成",
  "title": "标题（含emoji，≤20字，有情绪钩子）",
  "template": "{template}",
  "card_ids": [使用到的卡片card_id列表],
  "hashtags": "#标签1 #标签2 ... （8-12个相关标签）",
  "narrative_arc": "叙事弧线描述（一句话）",
  "emotion_curve": ["好奇", "尝试", "受挫/惊讶", "顿悟", "分享"],
  "carousel": [
    {{"slide": 1, "type": "封面", "desc": "封面设计描述"}},
    {{"slide": 2, "type": "内容页", "desc": "第2页内容描述"}},
    {{"slide": 3, "type": "内容页", "desc": "第3页内容描述"}},
    {{"slide": 4, "type": "总结页", "desc": "总结/口诀"}},
    {{"slide": 5, "type": "互动页", "desc": "评论引导"}}
  ],
  "title_candidates": [
    {{"title": "候选标题1", "score": 8}},
    {{"title": "候选标题2", "score": 7}},
    {{"title": "候选标题3", "score": 9}}
  ],
  "body": "正文内容（≤1000字，包含emoji、分段、金句、互动引导）",
  "pinned_comment": "置顶评论内容",
  "interaction_hooks": {{
    "comment_guide": "评论引导语",
    "save_guide": "收藏引导语",
    "share_guide": "转发引导语"
  }},
  "best_post_time": "最佳发布时间建议",
  "scores": {{
    "title_appeal": 8,
    "content_quality": 9,
    "knowledge_accuracy": 9,
    "readability": 8,
    "viral_potential": 8,
    "compliance": 9
  }},
  "total": 51,
  "verdict": "PASS",
  "predicted": {{"likes": "2k-5k", "saves": "1k-3k", "comments": "200-500"}},
  "strengths": ["优势1", "优势2"],
  "issues": ["问题1（如有）"],
  "suggestions": ["改进建议1"]
}}
"""
        api_key = _get_next_server_key()
        if not api_key:
            return self._send_json({'error': 'No Gemini API key configured'}, 500)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        req_body = json.dumps({
            "contents": [{"parts": [{"text": note_prompt}]}],
            "generationConfig": {"temperature": 0.8, "maxOutputTokens": 65536}
        }).encode('utf-8')

        try:
            opener = _build_opener()
            req = urllib.request.Request(url, data=req_body, headers={"Content-Type": "application/json"}, method="POST")
            resp = opener.open(req, timeout=120)
            data = json.loads(resp.read().decode('utf-8'))
            candidates = data.get('candidates', [])
            if not candidates:
                return self._send_json({'error': 'AI返回空结果(可能触发安全过滤)'}, 500)
            text = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
            if not text:
                return self._send_json({'error': 'AI返回无文本内容'}, 500)

            # 提取JSON
            text = re.sub(r'^```json\s*', '', text.strip())
            text = re.sub(r'^```\s*', '', text.strip())
            text = re.sub(r'\s*```$', '', text.strip())
            start = text.find('{')
            end = text.rfind('}')
            if start >= 0 and end > start:
                text = text[start:end+1]

            note = json.loads(text)
            note['generated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
            note['note_id'] = f"{subject}_{grade_short}_{template}_{time.strftime('%Y%m%d_%H%M%S')}"

            # 保存到文件
            notes_dir = os.path.join(PUBLIC_DIR, 'generated_notes')
            os.makedirs(notes_dir, exist_ok=True)
            note_path = os.path.join(notes_dir, f"{note['note_id']}.json")
            with open(note_path, 'w', encoding='utf-8') as f:
                json.dump(note, f, ensure_ascii=False, indent=2)

            return self._send_json({'ok': True, 'note': note})
        except json.JSONDecodeError as e:
            return self._send_json({'error': f'AI响应JSON解析失败: {str(e)}'}, 500)
        except Exception as e:
            return self._send_json({'error': f'生成失败: {str(e)}'}, 500)

    def _list_generated_notes(self):
        """列出所有已生成的笔记"""
        notes_dir = os.path.join(PUBLIC_DIR, 'generated_notes')
        notes = []
        if os.path.exists(notes_dir):
            for f in sorted(os.listdir(notes_dir), reverse=True):
                if f.endswith('.json'):
                    try:
                        data = json.loads(open(os.path.join(notes_dir, f), encoding='utf-8').read())
                        notes.append(data)
                    except:
                        pass
        return self._send_json({'notes': notes})

    def _ai_match_cards(self, body):
        """AI智能匹配: 根据用户问题推荐最相关的知识卡片"""
        query = body.get('query', '').strip()
        subject = body.get('subject', '')
        grade_short = body.get('grade_short', '')

        if not query:
            return self._send_json({'error': '请输入搜索问题'}, 400)

        # 收集所有(或指定学科/年级)的卡片
        cards_dir = os.path.join(PUBLIC_DIR, 'knowledge_cards', '小学')
        all_cards = []
        if os.path.exists(cards_dir):
            for f in sorted(os.listdir(cards_dir)):
                if not f.endswith('.json') or f == 'manifest.json':
                    continue
                if subject and not f.startswith(subject):
                    continue
                if grade_short and grade_short not in f:
                    continue
                try:
                    data = json.loads(open(os.path.join(cards_dir, f), encoding='utf-8').read())
                    for u in data.get('units', []):
                        for c in u.get('cards', []):
                            c['_source'] = f.replace('.json', '')
                            all_cards.append(c)
                except:
                    pass

        if not all_cards:
            return self._send_json({'error': '未找到卡片数据'}, 404)

        # 本地关键词匹配（快速，非AI方式）
        query_lower = query.lower()
        scored = []
        for c in all_cards:
            score = 0
            title = (c.get('title', '') or '').lower()
            definition = (c.get('definition', '') or '').lower()
            core_points = ' '.join(c.get('core_points', []) or []).lower()
            card_type = (c.get('type', '') or '').lower()
            memory_tip = (c.get('memory_tip', '') or '').lower()
            hook = (c.get('emotion_hook', '') or '').lower()
            
            # 精确匹配title得分高
            if query_lower in title:
                score += 10
            # 关键词在各字段中匹配
            for kw in query_lower.split():
                if kw in title: score += 5
                if kw in definition: score += 3
                if kw in core_points: score += 2
                if kw in card_type: score += 2
                if kw in memory_tip: score += 1
                if kw in hook: score += 1
            if score > 0:
                scored.append((score, c))
        
        scored.sort(key=lambda x: -x[0])
        results = [c for _, c in scored[:10]]

        # 如果本地匹配不足3个结果，尝试AI匹配
        if len(results) < 3:
            api_key = _get_next_server_key()
            if api_key:
                # 构造精简卡片列表给AI
                card_summaries = []
                for i, c in enumerate(all_cards[:200]):  # 限制200张避免超长
                    card_summaries.append(f"{i}|{c.get('type','')}|{c.get('title','')}|{c.get('definition','')[:50]}")
                
                prompt = f"""用户问题: "{query}"

以下是知识卡片列表(格式: 序号|类型|标题|定义):
{chr(10).join(card_summaries)}

请从中选出最相关的5-8张卡片，返回它们的序号，用逗号分隔。只返回数字，不要其他解释。
例如: 3,15,42,78,99"""

                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
                    req_body = json.dumps({
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 200}
                    }).encode('utf-8')
                    opener = _build_opener()
                    req = urllib.request.Request(url, data=req_body, headers={"Content-Type": "application/json"}, method="POST")
                    resp = opener.open(req, timeout=30)
                    data = json.loads(resp.read().decode('utf-8'))
                    candidates = data.get('candidates', [])
                    if not candidates:
                        raise ValueError('AI返回空结果')
                    text = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '').strip()
                    indices = [int(x.strip()) for x in re.findall(r'\d+', text)]
                    ai_results = [all_cards[i] for i in indices if 0 <= i < len(all_cards)]
                    if ai_results:
                        # 合并去重
                        seen = set(id(c) for c in results)
                        for c in ai_results:
                            if id(c) not in seen:
                                results.append(c)
                                seen.add(id(c))
                except Exception as e:
                    pass  # AI匹配失败不影响本地结果

        return self._send_json({'ok': True, 'results': results[:10], 'total': len(all_cards)})

    # ═══════════════════════════════════════════
    # v3 AI 卡片生成器 (全自动流水线)
    # ═══════════════════════════════════════════
    def _generate_card_image_v3(self, body):
        """
        全自动 AI 卡片图片生成 v3 流水线：
        Step 1: Flash 生成优化英文 Prompt + TEXT_MANIFEST
        Step 2: Nano Banana 生成卡片图片
        Step 3: Vision OCR 审计
        Step 4: 不通过则带纠错提示重试 (最多3轮)
        Step 5: PIL 文字修补兜底 + 质量评分
        
        返回: {ok, image(base64), score, audit_score, quality, model, rounds, manifest}
        """
        card = body.get('card')
        if not card or not card.get('full_id'):
            return self._send_json({'error': '缺少卡片数据(card.full_id)'}, 400)

        subject = body.get('subject', '数学')
        grade = body.get('grade', '三年级')
        semester = body.get('semester', '下册')
        skip_audit = body.get('skipAudit', False)

        if not SERVER_GEMINI_API_KEYS:
            return self._send_json({'error': '服务端未配置 Gemini API Key'}, 500)

        try:
            from generate_card_images_v3 import (
                generate_image_prompt, generate_card_image,
                ocr_audit, _build_audit_hint, _try_pil_text_repair,
                quality_score, AUDIT_PASS_SCORE, MAX_AUDIT_ROUNDS
            )
        except ImportError as e:
            return self._send_json({'error': f'v3模块导入失败: {e}'}, 500)

        keys = list(SERVER_GEMINI_API_KEYS)
        title = card.get('title', '')
        card_type = card.get('type', '方法卡')

        import traceback
        pipeline_log = []

        try:
            # ── Step 1: 生成提示词 ──
            pipeline_log.append('Step1: 生成Prompt...')
            print(f'[v3] {card["full_id"]} Step1: 生成Prompt...', flush=True)
            prompt, manifest = generate_image_prompt(card, subject, grade, semester, keys[0], all_keys=keys)
            if not prompt:
                return self._send_json({'error': 'Step1失败: 无法生成图片提示词', 'pipeline': pipeline_log}, 500)
            
            manifest_count = len(manifest) if manifest else 0
            total_chars = sum(len(v) for v in manifest.values()) if manifest else 0
            pipeline_log.append(f'Step1完成: {len(prompt)}字prompt, {manifest_count}处文字共{total_chars}字')
            print(f'[v3] Step1完成: {len(prompt)}字prompt, {manifest_count}处文字', flush=True)

            time.sleep(1)

            # ── Step 2-4: 生成图片 + OCR审计循环 ──
            best_image = None
            best_ext = 'png'
            best_score = 0
            audit_hint = ''
            used_model = ''
            rounds_used = 0

            max_rounds = 1 if skip_audit else MAX_AUDIT_ROUNDS
            for round_num in range(1, max_rounds + 1):
                rounds_used = round_num

                # Step 2: 生成图片
                round_label = f'(round {round_num}/{max_rounds})' if round_num > 1 else ''
                pipeline_log.append(f'Step2: 生成图片{round_label}...')
                print(f'[v3] Step2: 生成图片{round_label}...', flush=True)

                img_data, ext, model = generate_card_image(
                    prompt, keys, card_title=title, subject=subject, audit_hint=audit_hint
                )
                if model:
                    used_model = model
                if not img_data:
                    pipeline_log.append('Step2失败: 图片生成失败')
                    if best_image:
                        break
                    return self._send_json({'error': 'Step2失败: 图片生成失败', 'pipeline': pipeline_log}, 500)

                size_kb = len(img_data) / 1024
                pipeline_log.append(f'Step2完成: {size_kb:.0f}KB (model={model})')

                if skip_audit:
                    best_image = img_data
                    best_ext = ext
                    best_score = 100
                    break

                # Step 3: OCR 审计
                pipeline_log.append('Step3: OCR审计...')
                print(f'[v3] Step3: OCR审计...', flush=True)
                audit = ocr_audit(img_data, manifest, keys[0], all_keys=keys)
                score = audit.get('overall_score', 0)
                errors = audit.get('errors', [])
                summary = audit.get('summary', '')
                pipeline_log.append(f'Step3完成: 得分={score}/100 ({summary})')
                print(f'[v3] Step3: 得分={score}/100 ({summary})', flush=True)

                if score > best_score:
                    best_image = img_data
                    best_ext = ext
                    best_score = score

                if score >= AUDIT_PASS_SCORE:
                    pipeline_log.append(f'✅ OCR审计通过 (score={score})')
                    break
                else:
                    high_errs = [e for e in errors if e.get('severity') in ('high', 'medium')]
                    if round_num < max_rounds:
                        audit_hint = _build_audit_hint(audit, manifest)
                        pipeline_log.append(f'⚠️ {len(high_errs)}处错误, 重新生成...')
                        time.sleep(2)
                    else:
                        pipeline_log.append(f'⚠️ {len(high_errs)}处错误, 已达最大轮数')

            if not best_image:
                return self._send_json({'error': '图片生成全部失败', 'pipeline': pipeline_log}, 500)

            # ── Step 5: PIL 修补兜底 ──
            final_action = 'pass'
            if best_score < AUDIT_PASS_SCORE and manifest and not skip_audit:
                pipeline_log.append('Step5: PIL文字修补...')
                print(f'[v3] Step5: PIL文字修补...', flush=True)
                final_audit = ocr_audit(best_image, manifest, keys[0], all_keys=keys)
                repaired = _try_pil_text_repair(best_image, final_audit, manifest)
                if repaired != best_image:
                    best_image = repaired
                    best_ext = 'jpg'
                    final_action = 'repaired'
                    pipeline_log.append('PIL修补完成')
                else:
                    final_action = 'best_effort'
                    pipeline_log.append('无需PIL修补')

            # ── 质量评分 ──
            quality = {'total': 0, 'comment': ''}
            try:
                pipeline_log.append('Step5b: 质量评分...')
                print(f'[v3] Step5b: 质量评分...', flush=True)
                quality = quality_score(best_image, keys[0], card_title=title, all_keys=keys)
                pipeline_log.append(f'质量评分: {quality.get("total", 0)}/100 ({quality.get("comment", "")})')
            except Exception:
                pipeline_log.append('质量评分跳过')

            # 返回结果
            img_b64 = base64.b64encode(best_image).decode('utf-8')
            mime = 'image/jpeg' if best_ext == 'jpg' else 'image/png'

            print(f'[v3] ✅ {card["full_id"]} 完成: 审计={best_score} 质量={quality.get("total",0)} model={used_model} rounds={rounds_used}', flush=True)

            return self._send_json({
                'ok': True,
                'image': img_b64,
                'mimeType': mime,
                'size': len(best_image),
                'auditScore': best_score,
                'qualityScore': quality.get('total', 0),
                'qualityDetail': quality,
                'model': used_model,
                'rounds': rounds_used,
                'finalAction': final_action,
                'manifest': manifest,
                'pipeline': pipeline_log,
                'card_id': card['full_id']
            })

        except Exception as e:
            traceback.print_exc()
            pipeline_log.append(f'异常: {str(e)[:200]}')
            return self._send_json({'error': f'v3流水线异常: {str(e)[:200]}', 'pipeline': pipeline_log}, 500)

    # ── 异步 v3 图片生成（解决 Cloudflare tunnel 100s 超时） ──
    def _generate_card_image_v3_async(self, body):
        """接收 v3 请求 → 立即返回 task_id → 后台线程执行流水线"""
        card = body.get('card')
        if not card or not card.get('full_id'):
            return self._send_json({'error': '缺少卡片数据(card.full_id)'}, 400)

        if not SERVER_GEMINI_API_KEYS:
            return self._send_json({'error': '服务端未配置 Gemini API Key'}, 500)

        task_id = secrets.token_hex(12)
        with _async_tasks_lock:
            # 清理过期任务
            now = time.time()
            expired = [k for k, v in _async_tasks.items() if now - v['created'] > _ASYNC_TASK_TTL]
            for k in expired:
                del _async_tasks[k]
            _async_tasks[task_id] = {
                'status': 'running',
                'result': None,
                'created': now,
                'updated': now,
                'card_id': card['full_id'],
                'progress': 'v3流水线启动中...',
            }

        def _run_v3(task_id, body):
            """在后台线程执行 v3 流水线（带全局超时保护）"""
            _start_time = time.time()

            def _elapsed():
                return time.time() - _start_time

            def _timed_out():
                return _elapsed() > _ASYNC_TASK_TIMEOUT

            try:
                from generate_card_images_v3 import (
                    generate_image_prompt, generate_card_image,
                    ocr_audit, _build_audit_hint, _try_pil_text_repair,
                    quality_score, AUDIT_PASS_SCORE, MAX_AUDIT_ROUNDS
                )
            except ImportError as e:
                with _async_tasks_lock:
                    _async_tasks[task_id] = {**_async_tasks[task_id],
                        'status': 'error', 'result': {'error': f'v3模块导入失败: {e}'}, 'updated': time.time()}
                return

            card = body.get('card', {})
            subject = body.get('subject', '数学')
            grade = body.get('grade', '三年级')
            semester = body.get('semester', '下册')
            skip_audit = body.get('skipAudit', False)
            keys = list(SERVER_GEMINI_API_KEYS)
            title = card.get('title', '')
            pipeline_log = []

            def _update_progress(msg):
                with _async_tasks_lock:
                    if task_id in _async_tasks:
                        _async_tasks[task_id]['progress'] = msg
                        _async_tasks[task_id]['updated'] = time.time()

            def _finish_with_best(best_image, best_ext, best_score, used_model, rounds_used, final_action='timeout_best'):
                """超时时用目前最好的结果返回"""
                if not best_image:
                    pipeline_log.append(f'⏰ 超时({_elapsed():.0f}s)且无可用图片')
                    with _async_tasks_lock:
                        _async_tasks[task_id] = {**_async_tasks[task_id],
                            'status': 'error', 'result': {'error': f'v3流水线超时({_elapsed():.0f}s): Gemini API响应缓慢', 'pipeline': pipeline_log}, 'updated': time.time()}
                    return
                pipeline_log.append(f'⏰ 超时({_elapsed():.0f}s), 使用当前最佳结果(score={best_score})')
                img_b64 = base64.b64encode(best_image).decode('utf-8')
                mime = 'image/jpeg' if best_ext == 'jpg' else 'image/png'
                result = {
                    'ok': True, 'image': img_b64, 'mimeType': mime,
                    'size': len(best_image), 'auditScore': best_score,
                    'qualityScore': 0, 'qualityDetail': {'total': 0, 'comment': '超时跳过评分'},
                    'model': used_model, 'rounds': rounds_used,
                    'finalAction': final_action, 'manifest': {},
                    'pipeline': pipeline_log, 'card_id': card.get('full_id', ''),
                }
                with _async_tasks_lock:
                    _async_tasks[task_id] = {**_async_tasks[task_id],
                        'status': 'done', 'result': result, 'updated': time.time(), 'progress': '完成(超时最佳)'}

            try:
                # Step 1
                _update_progress('Step1: 生成Prompt...')
                print(f'[v3-async] {card.get("full_id","")} Step1: 生成Prompt...', flush=True)
                prompt, manifest = generate_image_prompt(card, subject, grade, semester, keys[0], all_keys=keys)
                if not prompt:
                    pipeline_log.append('Step1失败')
                    with _async_tasks_lock:
                        _async_tasks[task_id] = {**_async_tasks[task_id],
                            'status': 'error', 'result': {'error': 'Step1失败: 无法生成图片提示词', 'pipeline': pipeline_log}, 'updated': time.time()}
                    return

                manifest_count = len(manifest) if manifest else 0
                pipeline_log.append(f'Step1完成: {len(prompt)}字prompt, {manifest_count}处文字 ({_elapsed():.0f}s)')
                time.sleep(1)

                if _timed_out():
                    _finish_with_best(None, 'png', 0, '', 0)
                    return

                # Step 2-4: 生成+审计循环
                best_image = None
                best_ext = 'png'
                best_score = 0
                audit_hint = ''
                used_model = ''
                rounds_used = 0
                # 异步模式下限制审计轮数为1（减少总时间）
                max_rounds = 1 if skip_audit else min(MAX_AUDIT_ROUNDS, 2)

                for round_num in range(1, max_rounds + 1):
                    if _timed_out():
                        pipeline_log.append(f'⏰ 超时, 跳出循环')
                        break

                    rounds_used = round_num
                    _update_progress(f'Step2: AI生图 (round {round_num}/{max_rounds})... [{_elapsed():.0f}s]')
                    pipeline_log.append(f'Step2: 生成图片 (round {round_num})...')
                    print(f'[v3-async] Step2: 生成图片 (round {round_num})... [{_elapsed():.0f}s]', flush=True)

                    img_data, ext, model = generate_card_image(
                        prompt, keys, card_title=title, subject=subject, audit_hint=audit_hint
                    )
                    if model:
                        used_model = model
                    if not img_data:
                        pipeline_log.append(f'Step2失败: 图片生成失败 ({_elapsed():.0f}s)')
                        if best_image:
                            break
                        if _timed_out():
                            _finish_with_best(None, 'png', 0, '', rounds_used)
                            return
                        with _async_tasks_lock:
                            _async_tasks[task_id] = {**_async_tasks[task_id],
                                'status': 'error', 'result': {'error': 'Step2失败: 图片生成失败(所有模型/Key均失败)', 'pipeline': pipeline_log}, 'updated': time.time()}
                        return

                    size_kb = len(img_data) / 1024
                    pipeline_log.append(f'Step2完成: {size_kb:.0f}KB (model={model}) [{_elapsed():.0f}s]')

                    if skip_audit:
                        best_image = img_data
                        best_ext = ext
                        best_score = 100
                        break

                    if _timed_out():
                        # 已有图片但来不及审计 → 直接用
                        best_image = img_data
                        best_ext = ext
                        best_score = 50  # 未审计
                        pipeline_log.append(f'⏰ 超时, 跳过审计')
                        break

                    # Step 3: OCR
                    _update_progress(f'Step3: OCR审计 (round {round_num})... [{_elapsed():.0f}s]')
                    pipeline_log.append('Step3: OCR审计...')
                    audit = ocr_audit(img_data, manifest, keys[0], all_keys=keys)
                    score = audit.get('overall_score', 0)
                    errors = audit.get('errors', [])
                    summary = audit.get('summary', '')
                    pipeline_log.append(f'Step3完成: 得分={score}/100 ({summary}) [{_elapsed():.0f}s]')

                    if score > best_score:
                        best_image = img_data
                        best_ext = ext
                        best_score = score

                    if score >= AUDIT_PASS_SCORE:
                        pipeline_log.append(f'✅ OCR审计通过 (score={score})')
                        break
                    else:
                        if round_num < max_rounds and not _timed_out():
                            audit_hint = _build_audit_hint(audit, manifest)
                            pipeline_log.append(f'⚠️ 重新生成...')
                            time.sleep(2)

                if not best_image:
                    with _async_tasks_lock:
                        _async_tasks[task_id] = {**_async_tasks[task_id],
                            'status': 'error', 'result': {'error': '图片生成全部失败', 'pipeline': pipeline_log}, 'updated': time.time()}
                    return

                if _timed_out():
                    _finish_with_best(best_image, best_ext, best_score, used_model, rounds_used)
                    return

                # Step 5: PIL
                final_action = 'pass'
                if best_score < AUDIT_PASS_SCORE and manifest and not skip_audit and not _timed_out():
                    _update_progress(f'Step5: PIL文字修补... [{_elapsed():.0f}s]')
                    pipeline_log.append('Step5: PIL文字修补...')
                    final_audit = ocr_audit(best_image, manifest, keys[0], all_keys=keys)
                    repaired = _try_pil_text_repair(best_image, final_audit, manifest)
                    if repaired != best_image:
                        best_image = repaired
                        best_ext = 'jpg'
                        final_action = 'repaired'
                        pipeline_log.append('PIL修补完成')
                    else:
                        final_action = 'best_effort'

                # Quality score
                quality = {'total': 0, 'comment': ''}
                if not _timed_out():
                    try:
                        _update_progress(f'Step5b: 质量评分... [{_elapsed():.0f}s]')
                        pipeline_log.append('Step5b: 质量评分...')
                        quality = quality_score(best_image, keys[0], card_title=title, all_keys=keys)
                        pipeline_log.append(f'质量评分: {quality.get("total", 0)}/100')
                    except Exception:
                        pipeline_log.append('质量评分跳过')
                else:
                    pipeline_log.append('⏰ 超时, 跳过质量评分')

                img_b64 = base64.b64encode(best_image).decode('utf-8')
                mime = 'image/jpeg' if best_ext == 'jpg' else 'image/png'
                total_time = _elapsed()
                print(f'[v3-async] ✅ {card.get("full_id","")} 完成: 审计={best_score} 质量={quality.get("total",0)} 耗时={total_time:.0f}s', flush=True)

                result = {
                    'ok': True,
                    'image': img_b64,
                    'mimeType': mime,
                    'size': len(best_image),
                    'auditScore': best_score,
                    'qualityScore': quality.get('total', 0),
                    'qualityDetail': quality,
                    'model': used_model,
                    'rounds': rounds_used,
                    'finalAction': final_action,
                    'manifest': manifest,
                    'pipeline': pipeline_log,
                    'card_id': card.get('full_id', ''),
                    'elapsed': round(total_time, 1),
                }
                with _async_tasks_lock:
                    _async_tasks[task_id] = {**_async_tasks[task_id],
                        'status': 'done', 'result': result, 'updated': time.time(), 'progress': '完成'}

            except Exception as e:
                import traceback
                traceback.print_exc()
                pipeline_log.append(f'异常: {str(e)[:200]}')
                with _async_tasks_lock:
                    _async_tasks[task_id] = {**_async_tasks[task_id],
                        'status': 'error', 'result': {'error': f'v3流水线异常: {str(e)[:200]}', 'pipeline': pipeline_log}, 'updated': time.time()}

        t = threading.Thread(target=_run_v3, args=(task_id, body), daemon=True)
        t.start()

        print(f'[v3-async] 任务已创建: {task_id} for {card.get("full_id","")}', flush=True)
        return self._send_json({'task_id': task_id, 'status': 'running'})

    def _get_task_status(self, task_id):
        """查询异步任务状态"""
        with _async_tasks_lock:
            task = _async_tasks.get(task_id)
        if not task:
            return self._send_json({'error': '任务不存在或已过期'}, 404)

        resp = {'task_id': task_id, 'status': task['status'], 'progress': task.get('progress', '')}
        if task['status'] == 'done':
            resp['result'] = task['result']
            # 取走结果后清理（节省内存）
            with _async_tasks_lock:
                if task_id in _async_tasks:
                    del _async_tasks[task_id]
        elif task['status'] == 'error':
            resp['result'] = task['result']
            with _async_tasks_lock:
                if task_id in _async_tasks:
                    del _async_tasks[task_id]
        return self._send_json(resp)

    # ═══════════════════════════════════════════
    # HTML 卡片渲染器 API
    # ═══════════════════════════════════════════
    def _render_card_image_html(self, body):
        """用 HTML 模板渲染知识卡片→截图→返回图片 base64"""
        card = body.get('card')
        if not card or not card.get('full_id'):
            return self._send_json({'error': '缺少卡片数据(card.full_id)'}, 400)

        try:
            from generate_card_images_html import generate_card_html, render_card_to_image, _find_chrome
        except ImportError as e:
            return self._send_json({'error': f'渲染模块导入失败: {e}'}, 500)

        if not _find_chrome():
            return self._send_json({'error': '未找到 Chrome 浏览器，无法渲染卡片图片'}, 500)

        subject = body.get('subject', '数学')
        grade = body.get('grade', '三年级')
        semester = body.get('semester', '下册')

        import tempfile, base64
        try:
            html = generate_card_html(card, subject, grade, semester)

            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp_path = tmp.name

            size = render_card_to_image(html, tmp_path, width=1080)

            with open(tmp_path, 'rb') as f:
                img_b64 = base64.b64encode(f.read()).decode('utf-8')

            os.unlink(tmp_path)

            return self._send_json({
                'ok': True,
                'image': img_b64,
                'mimeType': 'image/jpeg',
                'size': size,
                'card_id': card['full_id']
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._send_json({'error': f'渲染失败: {e}'}, 500)

    # ═══════════════════════════════════════════
    # 五角色流水线：按需生成 R1→R2→R3 Prompt 记录
    # ═══════════════════════════════════════════
    def _generate_prompt_record(self, body):
        """为指定知识卡片生成 R1(教研专家)→R2(教学设计师)→R3(小红书策划) prompt record"""
        card = body.get('card')
        subject = body.get('subject', '数学')
        if not card or not card.get('full_id'):
            return self._send_json({'error': '缺少卡片数据'}, 400)

        api_key = _get_next_server_key()
        if not api_key:
            return self._send_json({'error': '服务端未配置 Gemini API Key'}, 500)

        card_type = card.get('type', '方法卡')
        CARD_TYPE_SKILLS = {
            '概念卡': {'strategy': '生活场景→抽象概念', 'visual': '生活实物大图, 概念提炼金句, 口诀', 'emotion': '熟悉感→恍然大悟'},
            '方法卡': {'strategy': '具体例题→色块分步→答案', 'visual': '例题大字展示, 色块解题, 答案超大', 'emotion': '好奇→清晰→成就'},
            '辨析卡': {'strategy': '✓/✗ 并排对比→红圈标差异', 'visual': '左✗右✓并排, 红圈差异, 金句', 'emotion': '困惑→明白→警觉'},
            '公式卡': {'strategy': '图形实例→直观推导→公式', 'visual': '格子推导图, 公式超大醒目', 'emotion': '好奇→理解→记住'},
            '陷阱卡': {'strategy': '设置陷阱→暴露错误→揭示真相', 'emotion': '好奇挑战→惊讶→恍然大悟', 'hook': '反直觉, 90%做错'},
            '速算卡': {'strategy': '常规慢方法→速算技巧→结果一致', 'emotion': '好奇→震撼→成就感', 'hook': '比老师教的快10倍'},
            '挑战卡': {'strategy': '限时+闯关+悬念答案', 'emotion': '跃跃欲试→紧张→不服气/成就', 'hook': '30秒内答对算你赢'},
            '生活卡': {'strategy': '生活场景→数学问题→实用解法', 'emotion': '熟悉亲切→恍然大悟→实用满足', 'hook': '原来买菜也要数学'},
            '对战卡': {'strategy': '左右分栏→家长vs孩子→同题PK', 'emotion': '跃跃欲试→紧张→欢乐亲子', 'hook': '家长vs孩子谁先答对'},
            '思维卡': {'strategy': '有趣问题→可视化思维过程→优雅解法', 'emotion': '好奇挑战→专注→啊哈恍然', 'hook': '聪明的孩子都会'},
            # 语文/英语通用
            '基础卡': {'strategy': '核心知识→易错归纳→记忆口诀', 'emotion': '专注→理解→巩固'},
            '阅读卡': {'strategy': '文段赏析→方法提炼→实战运用', 'emotion': '好奇→领悟→自信'},
            '写作卡': {'strategy': '范文引导→技巧拆解→仿写训练', 'emotion': '畏难→开窍→跃跃欲试'},
            '词汇卡': {'strategy': '词义→语境→记忆技巧', 'emotion': '陌生→关联→牢记'},
            '语法卡': {'strategy': '规则展示→例句对比→易错提醒', 'emotion': '困惑→清晰→操练'},
            '口语卡': {'strategy': '场景对话→核心句型→开口练习', 'emotion': '害羞→模仿→自信'},
            # 考卷真题专题
            '填空满分卡': {'strategy': '审题三步法→陷阱识别→验证', 'visual': '色块审题流程, 陷阱红圈, 单位对比', 'emotion': '警觉→细心→满分'},
            '选择秒杀卡': {'strategy': '排除法→单位筛查→估算验证', 'visual': '四选项排列, 划掉错项, 绿色正确', 'emotion': '快速→精准→秒杀'},
            '计算零失误卡': {'strategy': '竖式分层→进位检查→验算', 'visual': '彩色竖式, 对位检查, 验算步骤', 'emotion': '专注→仔细→零错'},
            '判断火眼卡': {'strategy': '识别绝对词→举反例→判断', 'visual': '✓✗对比, 反例图, 陷阱词高亮', 'emotion': '怀疑→验证→火眼金睛'},
            '应用题拆解卡': {'strategy': '读→画→列→验四步法', 'visual': '线段图, 流程色块, 答语模板', 'emotion': '畏难→拆解→满分'},
            '操作题规范卡': {'strategy': '审题→作图→标注→检查', 'visual': '方格纸, 尺子画线, 检查清单', 'emotion': '随意→规范→满分'},
            # 英语考卷真题专题
            '听力得分卡': {'strategy': '听前预判→关键词捕捉→排除干扰', 'visual': '耳机图标, 关键词高亮, 选项排除色块', 'emotion': '紧张→专注→精准'},
            '拼写零错卡': {'strategy': '词根拆分→易错字母标红→手写强化', 'visual': '字母色块拆分, 红圈易错点, 手写示范', 'emotion': '粗心→警觉→零错'},
            '填空必会卡': {'strategy': '语境推断→语法匹配→验证通顺', 'visual': '句子填空色块, 语法提示, 选词高亮', 'emotion': '犹豫→推断→必会'},
            '匹配速解卡': {'strategy': '关键词定位→逐一排除→连线验证', 'visual': '左右连线图, 关键词高亮, 匹配箭头', 'emotion': '眼花→定位→秒解'},
            '阅读通关卡': {'strategy': '略读大意→精读细节→定位答案', 'visual': '文段分层色块, 关键句高亮, 答案定位箭头', 'emotion': '畏难→层层通关→自信'},
            '写作模板卡': {'strategy': '开头模板→中间展开→结尾句型', 'visual': '三段式色块模板, 句型高亮, 连接词列表', 'emotion': '不会写→套模板→轻松写'},
            # 语文考卷真题专题
            '拼写默写卡': {'strategy': '形近字辨析→词根偏旁→记忆口诀', 'visual': '字形对比色块, 偏旁高亮, 口诀金句', 'emotion': '混淆→辨析→牢记'},
            '句式变换卡': {'strategy': '辨句型→找关键词→套公式改写', 'visual': '句型对比左右栏, 箭头指引, 关键词红色', 'emotion': '迷糊→清晰→套公式'},
            '阅读理解卡': {'strategy': '先看题→再读文→定位关键句→组织答案', 'visual': '文段分层色块, 关键句下划线, 答题模板', 'emotion': '畏难→拆解→能答'},
            '古诗默写卡': {'strategy': '理解诗意→抽查默写→易错字标红', 'visual': '古诗原文大字, 易错字红圈, 诗意图解', 'emotion': '模糊→理解→背熟'},
            '作文模板卡': {'strategy': '开头套路→中间展开→结尾升华', 'visual': '三段式框架, 好词好句高亮, 修辞示例', 'emotion': '动笔难→套模板→满分'},
            # 国学文化专题
            '预言解密卡': {'strategy': '原文引用→逐句拆解→历史验证', 'visual': '古文竖排大字, 拆字色块, 历史对照图', 'emotion': '好奇→解密→震撼'},
            '人物传奇卡': {'strategy': '人物档案→传奇事迹→后世影响', 'visual': '人物画像, 故事场景还原, 名言金句', 'emotion': '好奇→敬佩→传承'},
            '历史印证卡': {'strategy': '预言原文→历史事实→精准对比', 'visual': '左预言右历史对比栏, 时间线, 命中标记', 'emotion': '怀疑→震惊→折服'},
            '反转揭秘卡': {'strategy': '常见认知→反转真相→深层启示', 'visual': '先展示误区, 大反转箭头, 真相揭晓', 'emotion': '以为→震惊→恍然大悟'},
            '智慧启示卡': {'strategy': '故事总结→思维提炼→现代应用', 'visual': '古今对比, 思维导图, 金句收尾', 'emotion': '思考→领悟→启发'},
        }
        skill = CARD_TYPE_SKILLS.get(card_type, CARD_TYPE_SKILLS.get('方法卡', {}))

        NOVEL_STRATEGIES = {
            '反转法': '先展示常见错误答案及原因, 再揭示正确解法, 制造"原来坑在这里"的惊喜',
            '类比法': '把抽象知识映射到生活场景, 降低理解门槛',
            '对抗法': '设计"正确先生vs粗心怪"两个角色对抗, 孩子代入角色增强记忆',
            '动画帧法': '设计成动画的关键帧, 有动感和故事感',
            '一笔改错法': '展示一个错误, 只改一个地方让它变正确, 游戏化思维训练',
        }
        novel_list = '\n'.join(f'  - {k}: {v}' for k, v in NOVEL_STRATEGIES.items())

        def _call_gemini(prompt_text, temperature=0.8):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            req_body = json.dumps({
                "contents": [{"parts": [{"text": prompt_text}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": 4096}
            }).encode('utf-8')
            req = urllib.request.Request(url, data=req_body, headers={"Content-Type": "application/json"}, method="POST")
            try:
                resp = _OPENER.open(req, timeout=60)
            except urllib.error.HTTPError as he:
                err_body = he.read().decode('utf-8', errors='replace')[:500]
                print(f'[Gemini API Error] {he.code}: {err_body}')
                raise Exception(f'Gemini API {he.code}: {err_body[:200]}')
            data = json.loads(resp.read().decode('utf-8'))
            # 提取文本（跳过 thought 部分）
            text = ''
            for part in data.get('candidates', [{}])[0].get('content', {}).get('parts', []):
                if 'text' in part and 'thought' not in part:
                    text = part['text'].strip()
            return text

        def _parse_json(text):
            clean = re.sub(r'```json\s*', '', text)
            clean = re.sub(r'```\s*$', '', clean).strip()
            return json.loads(clean)

        try:
            # ── R1: 教研专家 ──
            r1_prompt = f"""你是一位有20年教研经验的小学{subject}教研员，研究过10万份试卷。

请分析以下知识点,输出内容选题brief(JSON格式):

知识点: {card.get('title','')}
题型: {card_type}
定义: {card.get('definition','')}
核心要点: {'; '.join(card.get('core_points',[])[:4])}
例题: {card.get('example',{}).get('question','无')}
答案: {card.get('example',{}).get('answer','无')}
口诀: {card.get('memory_tip','')}
易错点: {json.dumps(card.get('mistakes',[]), ensure_ascii=False)[:200]}
难度: {card.get('difficulty',3)}/5

请输出JSON(不要markdown代码块):
{{
  "selected_problem": "选出的最核心例题(一道)",
  "why_important": "为什么这道题重要(一句话)",
  "top3_mistakes": ["学生最常犯的错误1","错误2","错误3"],
  "trap_point": "最容易踩的坑(一句话)",
  "exam_frequency": "考试频率(高/中/低)",
  "parent_appeal": "家长为什么会关注这个(一句话)",
  "age_range": "适合年龄段"
}}"""

            r1_text = _call_gemini(r1_prompt, 0.6)
            try:
                brief1 = _parse_json(r1_text)
            except:
                brief1 = {'selected_problem': card.get('example',{}).get('question',''), 'raw': r1_text[:300]}

            # ── R2: 教学设计师 ──
            r2_prompt = f"""你是一位认知科学博士+一线{subject}教师，擅长把复杂变简单。

已有教研专家的分析:
{json.dumps(brief1, ensure_ascii=False, indent=2)}

知识点: {card.get('title','')} (题型: {card_type})
题型设计策略: {skill.get('strategy','')}
例题: {card.get('example',{}).get('question','无')}
解题步骤: {json.dumps(card.get('example',{}).get('steps',[]), ensure_ascii=False)}

可选的新奇解题展示策略:
{novel_list}

请输出JSON(不要markdown代码块):
{{
  "eureka_moment": "顿悟点——哪个瞬间孩子会恍然大悟?(一句话)",
  "analogy": "类比——这道题像生活中的什么?(一句话)",
  "novel_strategy": "推荐使用的新奇策略名称(从上面选一个)",
  "novel_application": "这个策略具体怎么用在这道题上(2-3句话)",
  "visual_solution": "解题可视化方案: 用什么图示/色块/对比来展示(详细描述,3-5句话)",
  "soul_mnemonic": "灵魂口诀(≤10字,朗朗上口)"
}}"""

            r2_text = _call_gemini(r2_prompt, 0.85)
            try:
                brief2 = _parse_json(r2_text)
            except:
                brief2 = {'visual_solution': card.get('memory_tip',''), 'raw': r2_text[:300]}

            # ── R3: 小红书策划 ──
            r3_prompt = f"""你是小红书教育赛道TOP操盘手，打造过100个10w+爆款笔记。

知识点: {card.get('title','')} (题型: {card_type})
教研分析: {json.dumps(brief1, ensure_ascii=False)[:300]}
教学设计: {json.dumps(brief2, ensure_ascii=False)[:300]}
题型情绪路线: {skill.get('emotion', '')}
题型传播钩子: {skill.get('hook', '')}

请输出JSON(不要markdown代码块):
{{
  "title_options": [
    "爆款标题1(必须有情绪钩子,15-25字)",
    "爆款标题2",
    "爆款标题3"
  ],
  "best_title": "推荐使用的标题(从上面选)",
  "emotion_tone": "卡片整体情绪基调(1个词)",
  "hook_type": "钩子类型(惊讶/实用/挑战/焦虑/好奇等)",
  "interaction_design": "互动设计(引导评论/转发的具体方法,2句话)",
  "comment_guide": "评论区引导语(1句话)",
  "series_tag": "系列标签(如#小学{subject}陷阱题#)",
  "target_audience": "目标人群(家长/学生/老师)",
  "ip_character_state": "小老师角色此刻的表情和状态(如: 惊讶张嘴/得意眨眼/思考摸下巴)"
}}"""

            r3_text = _call_gemini(r3_prompt, 0.9)
            try:
                brief3 = _parse_json(r3_text)
            except:
                brief3 = {'best_title': card.get('title',''), 'raw': r3_text[:300]}

            # 构造返回结果
            import datetime
            now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
            total_len = len(r1_prompt) + len(r2_prompt) + len(r3_prompt)

            result = {
                'title': card.get('title',''),
                'type': card_type,
                'pipeline': 'v2_R1R2R3',
                'score': 38,  # R1-R3 无质检,给默认分
                'verdict': 'PASS',
                'generated_at': now_str,
                'prompt_length': total_len,
                'briefs': {
                    'R1': brief1,
                    'R2': brief2,
                    'R3': brief3,
                }
            }

            return self._send_json({'ok': True, 'record': result})

        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._send_json({'error': f'生成失败: {str(e)}'}, 500)


# ============ 多线程 HTTP 服务器 ============
class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """ThreadingMixIn 使每个请求在独立线程中处理，
    防止长耗时的 Gemini 代理请求阻塞其他 API 调用。"""
    daemon_threads = True


# ============ 启动服务器 ============
def main():
    bootstrap_db_if_needed()
    init_db()
    
    server = ThreadedHTTPServer(('0.0.0.0', PORT), APIHandler)
    
    print(f"\n[*] XHS Emotion Platform started (threaded)")
    print(f"[*] URL: http://localhost:{PORT}")
    print(f"[*] API: http://localhost:{PORT}/api")
    print(f"[*] DB Path: {DB_PATH}")
    if _PROXY_URL:
        print(f"[*] Gemini Proxy: enabled (via {_PROXY_URL})")
    else:
        print(f"[*] Gemini Proxy: enabled (direct)")
    print(f"[*] Gemini API Keys: {len(SERVER_GEMINI_API_KEYS)} key(s) loaded" + (" (multi-key rotation enabled)" if len(SERVER_GEMINI_API_KEYS) > 1 else ""))
    print(f"[*] Press Ctrl+C to stop\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped")
        server.server_close()

if __name__ == '__main__':
    main()
