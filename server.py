#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书情感账号自动化运营管理平台
纯Python实现，无需第三方依赖
"""

import http.server
import json
import sqlite3
import os
import sys
import random
import shutil
import hashlib
import secrets
import urllib.parse
import urllib.request
import ssl
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
BUILD_VERSION = '20260314y'  # 更新此版本号以追踪部署

# Gemini API Proxy 配置
GEMINI_API_BASE = 'https://generativelanguage.googleapis.com'

def _load_server_gemini_key():
    """只从环境变量读取 API Key，绝不从文件读取（防止 Key 泄露到 Git）"""
    return (os.environ.get('GEMINI_API_KEY') or '').strip()

SERVER_GEMINI_API_KEY = _load_server_gemini_key()
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
    """)
    conn.commit()
    conn.close()


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

    def _set_json_headers(self, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

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

    def _get_current_user(self):
        """从 Authorization header 获取当前登录用户，返回 user dict 或 None"""
        auth = self.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return None
        token = auth[7:].strip()
        if not token:
            return None
        conn = self._get_db()
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
    FREE_DAILY_AI_LIMIT = 3   # 免费用户每天3次免费调用（按次数，不区分积分）

    # 各功能积分消耗映射（基于真实 Gemini API 成本 + 合理毛利）
    FEATURE_COSTS = {
        # 内容生成链路（搜索+分析+生成，最贵）
        '内容搜索分析':  2,   # Google grounding $0.035 + tokens ~¥0.33
        '内容分析':      1,   # 无 grounding，纯文本分析
        '内容生成':      2,   # 大量输出 tokens + thinking
        # 图片生成（Imagen模型）
        '图片生成':      3,   # Imagen 单独计价 ~¥0.2
        '图片测试':      0,   # 测试不扣费
        # 品牌定位（文本生成，中等）
        '品牌定位':      2,
        # 轻量功能（纯文本，便宜）
        'AI评分优化':    1,
        '热门话题搜索':  1,   # grounding 但输出少
        '标签生成':      1,
        '生成评论话术':  1,
        '竞品分析':      2,   # grounding + 较多输出
        '笔记改写':      1,
        'AB测试':        2,   # 多版本输出，tokens 较多
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
        conn.execute('UPDATE redeem_codes SET used_by=?, used_at=datetime("now","localtime") WHERE id=?',
                     (user['id'], row['id']))
        conn.execute('UPDATE users SET ai_credits = ai_credits + ? WHERE id=?',
                     (credits, user['id']))
        conn.commit()
        new_credits = conn.execute('SELECT ai_credits FROM users WHERE id=?', (user['id'],)).fetchone()['ai_credits']
        conn.close()
        return self._send_json({'success': True, 'added': credits, 'credits': new_credits})

    def _admin_gen_codes(self, body):
        """API: 管理员生成兑换码（简单密码验证）"""
        admin_key = body.get('adminKey', '')
        if admin_key != os.environ.get('ADMIN_KEY', 'xhs-admin-2026'):
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

    def _send_json(self, data, code=200):
        self._set_json_headers(code)
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length:
            return json.loads(self.rfile.read(length).decode('utf-8'))
        return {}

    def _get_db(self):
        conn = sqlite3.connect(DB_PATH)
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
            return self._send_json({'version': BUILD_VERSION})
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
        elif path.startswith('/api/export/'):
            post_id = path.split('/')[-1]
            return self._export_post(post_id)
        else:
            # 静态文件
            return super().do_GET()

    def do_POST(self):
        path, query = self._parse_path()
        body = self._read_body()

        # --- 公开路由 ---
        if path == '/api/auth/register':
            return self._auth_register(body)
        elif path == '/api/auth/login':
            return self._auth_login(body)
        elif path == '/api/auth/logout':
            return self._auth_logout()
        elif path == '/api/gemini-proxy':
            return self._gemini_proxy(body)
        elif path == '/api/ai-proxy':
            return self._gemini_proxy(body)
        elif path == '/api/baidu-search':
            return self._baidu_search(body)
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
        else:
            self._send_json({'error': 'Not found'}, 404)

    def do_PUT(self):
        path, query = self._parse_path()
        body = self._read_body()

        if path.startswith('/api/posts/'):
            post_id = path.split('/')[-1]
            return self._update_post(post_id, body)
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
        else:
            self._send_json({'error': 'Not found'}, 404)

    # ---- 用户认证 ----
    def _auth_register(self, body):
        username = (body.get('username') or '').strip()
        password = body.get('password') or ''
        nickname = (body.get('nickname') or '').strip()
        if len(username) < 2 or len(username) > 20:
            return self._send_json({'error': '用户名长度需2-20个字符'}, 400)
        if len(password) < 6:
            return self._send_json({'error': '密码至少6位'}, 400)
        conn = self._get_db()
        exists = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if exists:
            conn.close()
            return self._send_json({'error': '用户名已存在'}, 409)
        pw_hash = self._hash_password(password)
        conn.execute('INSERT INTO users (username, password_hash, nickname) VALUES (?,?,?)',
                     (username, pw_hash, nickname or username))
        conn.commit()
        uid = conn.execute('SELECT last_insert_rowid() as id').fetchone()['id']
        # 自动登录：创建 session
        token = secrets.token_urlsafe(48)
        expires = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('INSERT INTO sessions (user_id, token, expires_at) VALUES (?,?,?)',
                     (uid, token, expires))
        conn.commit()
        conn.close()
        self._send_json({'token': token, 'user': {'id': uid, 'username': username, 'nickname': nickname or username, 'avatar': ''}})

    def _auth_login(self, body):
        username = (body.get('username') or '').strip()
        password = body.get('password') or ''
        if not username or not password:
            return self._send_json({'error': '请输入用户名和密码'}, 400)
        conn = self._get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if not user or not self._verify_password(password, user['password_hash']):
            conn.close()
            return self._send_json({'error': '用户名或密码错误'}, 401)
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
        conn = self._get_db()
        row = conn.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
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
        conn = self._get_db()
        fields = []
        params = []
        
        for key in ['title', 'content', 'category', 'tags', 'cover_text', 'status', 'scheduled_date', 'publish_date', 'likes', 'collects', 'comments', 'views']:
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
        conn = self._get_db()
        conn.execute('DELETE FROM posts WHERE id = ?', (post_id,))
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
        conn = self._get_db()
        conn.execute('DELETE FROM income WHERE id = ?', (inc_id,))
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


    # ---- Gemini API 代理 ----
    def _gemini_proxy(self, body):
        """代理转发 Gemini API 请求，解决浏览器无法直接访问 Google API 的问题"""
        api_key = SERVER_GEMINI_API_KEY or body.get('apiKey', '')
        model = body.get('model', 'gemini-2.5-flash')
        payload = body.get('payload', {})
        action = body.get('action', 'generateContent')  # generateContent or listModels
        feature = body.get('feature', action)  # 用于追踪功能类型

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

        # 图片生成模型需要更长的超时时间
        is_image_model = 'image' in model or 'banana' in model or 'imagen' in model
        timeout = 180 if is_image_model else 120

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

            self._send_json(result)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='replace')
            try:
                err_json = json.loads(err_body)
            except:
                err_json = {'error': {'code': e.code, 'message': err_body[:500]}}
            self._send_json(err_json, e.code)
        except Exception as e:
            self._send_json({'error': {'code': 500, 'message': str(e)}}, 500)


# ============ 启动服务器 ============
def main():
    bootstrap_db_if_needed()
    init_db()
    
    server = http.server.HTTPServer(('0.0.0.0', PORT), APIHandler)
    
    print(f"\n[*] XHS Emotion Platform started")
    print(f"[*] URL: http://localhost:{PORT}")
    print(f"[*] API: http://localhost:{PORT}/api")
    print(f"[*] DB Path: {DB_PATH}")
    if _PROXY_URL:
        print(f"[*] Gemini Proxy: enabled (via {_PROXY_URL})")
    else:
        print(f"[*] Gemini Proxy: enabled (direct)")
    print(f"[*] Press Ctrl+C to stop\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped")
        server.server_close()

if __name__ == '__main__':
    main()
