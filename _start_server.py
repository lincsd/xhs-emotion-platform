"""Start server with API key loaded from api_key.txt"""
import os, re
os.chdir(os.path.dirname(os.path.abspath(__file__)))
# Load API key
with open('api_key.txt', encoding='utf-8') as f:
    for line in f:
        m = re.match(r'GEMINI_API_KEY\s*=\s*(.+)', line.strip())
        if m:
            os.environ['GEMINI_API_KEY'] = m.group(1).strip()
            break
# Now run server
exec(compile(open('server.py', encoding='utf-8').read(), 'server.py', 'exec'))
