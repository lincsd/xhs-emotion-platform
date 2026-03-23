"""Create 'lin' user account with proper password hash"""
import sqlite3, hashlib, secrets, os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'xhs_data.db')
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# Ensure phone column exists (migration)
try:
    conn.execute('ALTER TABLE users ADD COLUMN phone TEXT')
    print("Added 'phone' column")
except:
    print("'phone' column already exists")

try:
    conn.execute('ALTER TABLE users ADD COLUMN invite_code TEXT')
except:
    pass
try:
    conn.execute('ALTER TABLE users ADD COLUMN invited_by INTEGER DEFAULT 0')
except:
    pass
try:
    conn.execute('ALTER TABLE users ADD COLUMN commission_balance REAL DEFAULT 0')
except:
    pass
try:
    conn.execute('ALTER TABLE users ADD COLUMN ai_credits INTEGER DEFAULT 0')
except:
    pass
try:
    conn.execute('ALTER TABLE users ADD COLUMN tier TEXT DEFAULT "free"')
except:
    pass
conn.commit()

# Hash password
password = '950320'
salt = secrets.token_hex(16)
h = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
password_hash = f'{salt}:{h}'

# Check if lin already exists
existing = conn.execute("SELECT id FROM users WHERE username=?", ('lin',)).fetchone()
if existing:
    print(f"User 'lin' already exists (id={existing['id']}), updating password...")
    conn.execute("UPDATE users SET password_hash=? WHERE username=?", (password_hash, 'lin'))
else:
    # Generate invite code
    invite_code = secrets.token_hex(4).upper()
    conn.execute("""
        INSERT INTO users (username, password_hash, nickname, avatar, ai_credits, tier, invite_code)
        VALUES (?, ?, ?, '', 1000, 'pro', ?)
    """, ('lin', password_hash, 'Lin', invite_code))
    print(f"Created user 'lin' with 1000 credits, tier=pro, invite_code={invite_code}")

conn.commit()

# Verify
user = conn.execute("SELECT * FROM users WHERE username=?", ('lin',)).fetchone()
d = dict(user)
d['password_hash'] = d['password_hash'][:30] + '...'
print(f"\nVerified: {d}")

# Test password verify
stored = dict(conn.execute("SELECT password_hash FROM users WHERE username=?", ('lin',)).fetchone())['password_hash']
salt_part, hash_part = stored.split(':')
test_hash = hashlib.sha256((salt_part + password).encode('utf-8')).hexdigest()
print(f"Password verify: {'OK' if test_hash == hash_part else 'FAILED'}")

conn.close()
