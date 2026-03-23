import sqlite3, os
db = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'xhs_data.db')
print(f"DB: {db}, exists: {os.path.exists(db)}")
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

# List tables
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"Tables: {[t['name'] for t in tables]}")

if any(t['name'] == 'users' for t in tables):
    # Get column names
    cols = conn.execute('PRAGMA table_info(users)').fetchall()
    col_names = [c['name'] for c in cols]
    print(f"Users columns: {col_names}")
    
    rows = conn.execute('SELECT * FROM users').fetchall()
    print(f"\nTotal users: {len(rows)}")
    for r in rows:
        d = dict(r)
        pw = d.get('password_hash', '')
        d['password_hash'] = pw[:30] + '...' if pw else 'NONE'
        print(f"  {d}")

    lin = conn.execute("SELECT id, username, password_hash FROM users WHERE username=?", ('lin',)).fetchone()
    if lin:
        print(f"\nUser 'lin' found: id={lin['id']}, hash_prefix={lin['password_hash'][:40]}...")
    else:
        print("\nUser 'lin' NOT FOUND!")

    print("\nActive sessions (last 5):")
    try:
        sessions = conn.execute('SELECT user_id, token, expires_at FROM sessions ORDER BY expires_at DESC LIMIT 5').fetchall()
        for s in sessions:
            print(f"  user_id={s['user_id']}  expires={s['expires_at']}  token={s['token'][:20]}...")
    except Exception as e:
        print(f"  Error: {e}")
else:
    print("No 'users' table found!")

conn.close()
