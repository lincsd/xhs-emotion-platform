"""
Seed optimizer prompt_memory with high-quality reference prompts for 语法辨析卡.
Based on 4 reference card images: 地点/方式/结果/让步状语从句.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from self_optimizer import record_prompt

SEED_PROMPTS = [
    {
        "card_id": "英语-状语从句-G1-01",
        "subject": "英语",
        "grade": "状语从句",
        "card_type": "语法辨析卡",
        "prompt_text": """IMPORTANT: All visible text MUST be Simplified Chinese (简体中文). LARGE BOLD thick-stroke rounded sans-serif. Max 15 Chinese chars total, each block ≤4 chars. No English text in the image. Clean spacious layout, ≥25% whitespace. Every Chinese character must be pixel-perfect with clear strokes.

A vertical 3:4 XiaoHongShu knowledge card about English grammar - Adverbial Clause of Place (where).

LAYOUT: Coral-pink to peach gradient background. Top banner in saturated deep coral with HUGE bold title "地点从句" (4 chars, 72pt). 

CORE SECTION (≥45%): Two-column comparison on white rounded card:
- LEFT column (blue #54A0FF background block): Header icon 📍 with label "where". Below: visual diagram showing "where = at the place" with arrow pointing to location icon. Simple sentence structure diagram with colored blocks.
- RIGHT column (orange #FF9F43 background block): Header "wherever" block. Below: visual showing "wherever = no matter where" with scattered location pins icon.

BOTTOM BAR: Golden strip with memory tip "无名→状语" (4 chars, bold). 

Cute mini teacher character in corner with speech bubble "看前面!" (3 chars).

Style: Vibrant saturated colors, thick rounded outlines, generous whitespace between sections, modern flat design with subtle shadows. NO paragraphs, NO long text. Use arrows, icons, color blocks to convey grammar rules visually.""",
        "manifest": {"TITLE": "地点从句", "LINE1": "无名→状语", "LINE2": "看前面!"},
        "audit_score": 95,
        "quality_score": 95
    },
    {
        "card_id": "英语-状语从句-G2-02",
        "subject": "英语",
        "grade": "状语从句",
        "card_type": "语法辨析卡",
        "prompt_text": """IMPORTANT: All visible text MUST be Simplified Chinese (简体中文). LARGE BOLD thick-stroke rounded sans-serif. Max 15 Chinese chars total, each block ≤4 chars. No English text in the image. Clean spacious layout, ≥25% whitespace. Every Chinese character must be pixel-perfect with clear strokes.

A vertical 3:4 XiaoHongShu knowledge card about English grammar - Adverbial Clause of Manner (as if / the way).

LAYOUT: Mint-blue to lavender gradient background. Top banner saturated teal with HUGE bold title "方式从句" (4 chars, 72pt).

CORE SECTION (≥45%): White rounded card with visual comparison:
- TOP half: Three comparison blocks side by side:
  Block 1 (blue): "as" with equals arrow pointing to "像…一样" visual icon (mask/mirror icon)
  Block 2 (orange): "as if" with cloud/thought bubble icon suggesting hypothesis
  Block 3 (green): "the way" with path/road icon suggesting method
- BOTTOM half: Visual decision tree - "真→陈述" vs "假→虚拟" with ✓/✗ color-coded branches

BOTTOM GOLDEN BAR: Memory phrase "真陈假虚" (4 chars, bold gold).

Cute student character with confused-then-enlightened expression, bubble "原来!" (2 chars).

Style: Color-coded sections with thick borders, comparison arrows, clean spacious layout. Icons and visual metaphors over text. Modern XiaoHongShu aesthetic.""",
        "manifest": {"TITLE": "方式从句", "LINE1": "真陈假虚", "LINE2": "原来!"},
        "audit_score": 95,
        "quality_score": 95
    },
    {
        "card_id": "英语-状语从句-G3-01",
        "subject": "英语",
        "grade": "状语从句",
        "card_type": "语法辨析卡",
        "prompt_text": """IMPORTANT: All visible text MUST be Simplified Chinese (简体中文). LARGE BOLD thick-stroke rounded sans-serif. Max 15 Chinese chars total, each block ≤4 chars. No English text in the image. Clean spacious layout, ≥25% whitespace. Every Chinese character must be pixel-perfect with clear strokes.

A vertical 3:4 XiaoHongShu knowledge card about English grammar - Adverbial Clause of Result (so...that / such...that).

LAYOUT: Peach-orange to warm pink gradient background. Top banner deep orange with HUGE bold title "结果从句" (4 chars, 72pt).

CORE SECTION (≥45%): White rounded card with side-by-side comparison:
- LEFT (blue block): "so" label large, below shows "so + 形/副" with adjective/adverb icons (speed meter, size comparison). Arrow pointing down to "that..." result cloud.
- RIGHT (orange block): "such" label large, below shows "such + 名词" with noun icons (book, flower, day). Arrow pointing down to "that..." result cloud.
- CENTER dividing line with VS badge.

KEY RULE STRIP: Red warning block showing "so ≠ a+形+名" with ❌, green block "such + a+形+名" with ✅

BOTTOM GOLDEN BAR: "形副so名such" (6 chars, bold).

Cute teacher with pointing gesture, bubble "别混!" (2 chars).

Style: High contrast comparison layout, color-coded grammar blocks, visual flow arrows, XiaoHongShu vibrant aesthetic.""",
        "manifest": {"TITLE": "结果从句", "LINE1": "形副so名such", "LINE2": "别混!"},
        "audit_score": 95,
        "quality_score": 95
    },
    {
        "card_id": "英语-状语从句-G4-01",
        "subject": "英语",
        "grade": "状语从句",
        "card_type": "语法辨析卡",
        "prompt_text": """IMPORTANT: All visible text MUST be Simplified Chinese (简体中文). LARGE BOLD thick-stroke rounded sans-serif. Max 15 Chinese chars total, each block ≤4 chars. No English text in the image. Clean spacious layout, ≥25% whitespace. Every Chinese character must be pixel-perfect with clear strokes.

A vertical 3:4 XiaoHongShu knowledge card about English grammar - Adverbial Clause of Concession (although / even if / while).

LAYOUT: Lavender to soft purple gradient background. Top banner deep purple with HUGE bold title "让步从句" (4 chars, 72pt).

CORE SECTION (≥45%): White rounded card with tiered comparison:
- ROW 1 (blue block): "although" = "though" with equals sign, strength meter showing "虽然" level
- ROW 2 (orange block): "even if" vs "even though" with split: left shows hypothesis cloud (?), right shows fact checkmark (✓)
- ROW 3 (green block): "while" with triple meaning icons: clock (时间), vs-badge (对比), handshake (让步)

WARNING STRIP (red): Big ❌ showing "although + but" crossed out, with red circle and line through it

BOTTOM GOLDEN BAR: "虽but不同框" (6 chars, bold gold).

Cute student character with alert expression, bubble "记住!" (2 chars).

Style: Layered comparison rows with distinct color coding, warning symbols, clean modern XiaoHongShu layout with generous whitespace.""",
        "manifest": {"TITLE": "让步从句", "LINE1": "虽but不同框", "LINE2": "记住!"},
        "audit_score": 95,
        "quality_score": 95
    }
]

def seed():
    count = 0
    for s in SEED_PROMPTS:
        try:
            record_prompt(
                card_id=s["card_id"],
                subject=s["subject"],
                grade=s["grade"],
                card_type=s["card_type"],
                prompt_text=s["prompt_text"],
                manifest=s["manifest"],
                audit_score=s["audit_score"],
                quality_score=s["quality_score"],
                image_model="seed-reference",
                audit_rounds=0,
                final_action="seed"
            )
            count += 1
            print(f"  ✓ Seeded: {s['card_id']}")
        except Exception as e:
            print(f"  ✗ Failed {s['card_id']}: {e}")
    print(f"\nSeeded {count}/{len(SEED_PROMPTS)} grammar prompts into optimizer.")

if __name__ == "__main__":
    seed()
