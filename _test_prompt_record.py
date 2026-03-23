"""Test the generate-prompt-record endpoint"""
import urllib.request, json, ssl

url = "http://localhost:3000/api/generate-prompt-record"
body = json.dumps({
    "subject": "语文",
    "card": {
        "full_id": "语文-三下-01-04",
        "title": "修辞手法-比喻和拟人",
        "type": "修辞手法卡",
        "definition": "比喻和拟人是两种常见的修辞手法",
        "core_points": ["比喻用'像''好像'连接", "拟人赋予事物人的动作"],
        "example": {"question": "判断：小鸟在枝头唱歌", "answer": "拟人", "steps": ["分析句子", "找修辞特征"]},
        "memory_tip": "比喻看像字，拟人看动作",
        "mistakes": [{"desc": "把拟人误认为比喻"}],
        "difficulty": 3
    }
}).encode('utf-8')

req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")

try:
    resp = urllib.request.urlopen(req, timeout=120)
    data = json.loads(resp.read().decode('utf-8'))
    print("SUCCESS!")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1000])
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.reason}")
    body = e.read().decode('utf-8')
    print(f"Body: {body[:500]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
