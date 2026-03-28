import json

# Read the 10-card file
with open('_card_samples_output.json', 'r', encoding='utf-8') as f:
    cards = json.load(f)

# Add card 11: 语法辨析卡 from 英语_状语从句
cards.append({
    "index": 11,
    "source_file": "小学/英语_状语从句.json",
    "unit_id": "G1",
    "unit_name": "地点状语从句",
    "card": {
        "card_id": "G1-01",
        "full_id": "英语-状语从句-G1-01",
        "title": "where引导的地点状语从句",
        "type": "语法辨析卡",
        "difficulty": 3,
        "importance": 5,
        "definition": "where引导地点状语从句，表示「在……的地方」，修饰主句谓语动词，说明动作发生的地点。",
        "core_points": [
            "where = in/at the place where，表「在……地方」",
            "从句可置于主句前或后，前置时常加逗号",
            "区分where引导的地点状语从句和定语从句：状语从句中where前无先行词",
            "常见搭配：Stay where you are. / Put it where you found it."
        ],
        "example": {
            "question": "Where there is a will, there is a way. 此句中where引导什么从句？",
            "steps": [
                "1. 观察where前面有没有先行词（名词）",
                "2. 没有先行词→地点状语从句",
                "3. 翻译：在有意志的地方，就有出路"
            ],
            "answer": "where引导地点状语从句，表「在……的地方」，整句意为「有志者事竟成」。"
        },
        "mistakes": [
            {
                "wrong": "混淆where引导的定语从句：This is the place where I was born.（有先行词place→定语从句）",
                "correct": "Where I was born is a small village.（无先行词→地点状语从句）"
            }
        ],
        "memory_tip": "where前无名词→状语从句；where前有名词→定语从句！",
        "emotion_hook": "99%的同学分不清where到底引导什么从句，一招秒判！",
        "trap_point": "where既能引导定语从句也能引导状语从句，关键看前面有没有先行词。",
        "related": {
            "prerequisite": "定语从句基础",
            "next": "G1-02 wherever引导的地点状语从句"
        }
    }
})

# Add card 12: 不规则动词卡 from 英语_六下
cards.append({
    "index": 12,
    "source_file": "小学/英语_六下.json",
    "unit_id": "05",
    "unit_name": "Where did you go?",
    "card": {
        "card_id": "05-03",
        "full_id": "英语-六下-05-03",
        "title": "不规则动词卡：常见不规则动词过去式 (Group 1)",
        "type": "不规则动词卡",
        "difficulty": 4,
        "importance": 5,
        "definition": "学习一些常用不规则动词的过去式变化。",
        "core_points": [
            "go - went (去)",
            "see - saw (看)",
            "eat - ate (吃)",
            "drink - drank (喝)",
            "buy - bought (买)",
            "read - read (读，发音不同)",
            "have - had (有)",
            "do - did (做)"
        ],
        "example": {
            "question": "写出下列动词的过去式：",
            "steps": ["1. go", "2. see", "3. eat", "4. have"],
            "answer": "1. went\n2. saw\n3. ate\n4. had"
        },
        "mistakes": [
            {"wrong": "goed", "correct": "went"},
            {"wrong": "eated", "correct": "ate"}
        ],
        "memory_tip": "不规则动词很顽皮，变化多端不讲理。死记硬背是王道，多读多练才记牢！Go-went, see-saw, eat-ate, drink-drank, buy-bought, read-read, have-had, do-did！"
    }
})

# Fix source paths
for c in cards:
    c["source_file"] = c["source_file"].replace("\\", "/")

with open("_card_samples_output.json", "w", encoding="utf-8") as f:
    json.dump(cards, f, ensure_ascii=False, indent=2)

print(f"Total cards: {len(cards)}")
for c in cards:
    card = c["card"]
    ctype = card["type"]
    ctitle = card["title"]
    src = c["source_file"]
    uid = c["unit_id"]
    print(f"  #{c['index']} [{ctype}] {ctitle}  -- from {src} unit={uid}")
