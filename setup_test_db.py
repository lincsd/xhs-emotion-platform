"""Create a mock database simulating Render's old 20260314r schema."""
import sqlite3
import os

db = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'xhs_data.db')
if os.path.exists(db):
    os.remove(db)

conn = sqlite3.connect(db)
conn.executescript("""
    CREATE TABLE posts (id INTEGER PRIMARY KEY, title TEXT, content TEXT, category TEXT, tags TEXT, status TEXT DEFAULT 'draft', cover_image TEXT, content_images TEXT, user_id INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now','localtime')));
    CREATE TABLE income (id INTEGER PRIMARY KEY, amount REAL, description TEXT, user_id INTEGER DEFAULT 0);
    CREATE TABLE account_stats (id INTEGER PRIMARY KEY, date TEXT UNIQUE, user_id INTEGER DEFAULT 0);
    CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, nickname TEXT DEFAULT '', avatar TEXT DEFAULT '', created_at TEXT DEFAULT (datetime('now','localtime')), ai_credits INTEGER DEFAULT 0, tier TEXT DEFAULT 'free');
    CREATE TABLE sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, token TEXT UNIQUE NOT NULL, created_at TEXT DEFAULT (datetime('now','localtime')), expires_at TEXT NOT NULL);
    CREATE TABLE ai_usage (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, date TEXT NOT NULL, feature TEXT NOT NULL, created_at TEXT DEFAULT (datetime('now','localtime')));
    CREATE TABLE redeem_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, credits INTEGER NOT NULL DEFAULT 100, used_by INTEGER, created_at TEXT DEFAULT (datetime('now','localtime')), used_at TEXT);
""")
conn.execute("INSERT INTO users (username, password_hash, nickname) VALUES ('testuser', 'hash123', 'Test')")
conn.commit()
conn.close()
print(f'Old DB created at: {db}')
