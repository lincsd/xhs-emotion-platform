import sqlite3
conn = sqlite3.connect('D:/Users/Administrator/Desktop/ls/xhsqg/data.db')
c = conn.cursor()
try:
    c.execute('SELECT id, username, credits FROM users')
    for row in c.fetchall():
        print(row)
except Exception as e:
    print(f"Error: {e}")
    # Maybe wrong table name - list tables
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print("Tables:", c.fetchall())
conn.close()
