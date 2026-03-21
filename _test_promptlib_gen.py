import json, urllib.request, urllib.error, base64, time, sys

SERVER = "http://localhost:3000"

SAMPLE_CARD = {
    "full_id": "math3b_u01_t04",
    "title": "\u63cf\u8ff0\u7269\u4f53\u6240\u5728\u7684\u65b9\u5411",
    "type": "\u65b9\u6cd5\u5361",
    "definition": "\u7528\u65b9\u5411\u8bcd\u51c6\u786e\u63cf\u8ff0\u7269\u4f53\u76f8\u5bf9\u4f4d\u7f6e",
    "core_points": ["\u786e\u5b9a\u89c2\u6d4b\u70b9", "\u7528\u4e1c\u5357\u897f\u5317\u63cf\u8ff0\u65b9\u5411"],
    "example": {
        "question": "\u5728\u5730\u56fe\u4e0a\uff0c\u5b66\u6821\u5728\u5c0f\u660e\u5bb6\u6b63\u5317\u65b9300\u7c73\u5904\uff0c\u516c\u56ed\u5728\u5c0f\u660e\u5bb6\u6b63\u4e1c\u65b9200\u7c73\u5904\u3002\u8bf7\u95ee\uff0c\u516c\u56ed\u5728\u5b66\u6821\u7684\u4ec0\u4e48\u65b9\u5411\uff1f",
        "answer": "\u4e1c\u5357\u65b9\u5411",
        "steps": ["\u786e\u5b9a\u89c2\u6d4b\u70b9", "\u753b\u51fa\u65b9\u4f4d\u56fe", "\u516c\u56ed\u5728\u5b66\u6821\u7684\u4e1c\u5357\u65b9"]
    },
    "memory_tip": "\u7684\u5b57\u524d\u9762\u662f\u76ee\u6807\uff0c\u7684\u5b57\u540e\u9762\u662f\u4e2d\u5fc3",
    "mistakes": [{"wrong": "\u8bf4\u5b66\u6821\u5728\u516c\u56ed\u7684\u5317\u65b9", "correct": "\u5e94\u5148\u786e\u5b9a\u89c2\u6d4b\u70b9"}]
}

SYS_PROMPT = (
    "\u4f60\u662f\u4e00\u4f4d\u62e5\u670925\u5e74\u6570\u5b66\u6559\u5b66\u7ecf\u9a8c\u7684\u7279\u7ea7\u6559\u5e08+\u5c0f\u7ea2\u4e66\u7206\u6b3e\u5361\u7247\u8bbe\u8ba1\u5e08\u3002\n"
    "\u4f60\u7684\u4efb\u52a1\uff1a\u5c06\u77e5\u8bc6\u70b9\u8f6c\u5316\u4e3a\u4e00\u6bb5\u82f1\u6587AI\u56fe\u7247\u751f\u6210\u63d0\u793a\u8bcd\u3002\n"
    "\u6bcf\u5f20\u5361\u7247=\u4e00\u9053\u5177\u4f53\u4f8b\u9898\u7684\u4e00\u56fe\u79d2\u61c2\u8bb2\u89e3\u3002\n"
    "\u89c6\u89c9: \u7ad6\u5c4f3:4, \u6e10\u53d8\u80cc\u666f, \u5168\u5361\u4e2d\u6587\u226435\u5b57\u3002\n"
    "\u53ea\u8f93\u51fa\u82f1\u6587\u63d0\u793a\u8bcd\u3002"
)

def call_proxy(model, payload, feature="test"):
    url = f"{SERVER}/api/gemini-proxy"
    body = json.dumps({"model": model, "payload": payload, "action": "generateContent", "feature": feature}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=200)
        return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(err), e.code
        except:
            return {"error": err[:500]}, e.code
    except Exception as e:
        return {"error": str(e)}, 0

def main():
    print("=" * 60)
    print("Test: PromptLib Generate Image (2-step pipeline)")
    print("=" * 60)
    card = SAMPLE_CARD
    ex = card["example"]

    card_info = (
        f"\u77e5\u8bc6\u70b9: {card['title']}\n"
        f"\u9898\u578b: {card['type']}\n"
        f"\u5b9a\u4e49: {card['definition']}\n"
        f"\u6838\u5fc3\u8981\u70b9: {'; '.join(card['core_points'])}\n"
        f"\u4f8b\u9898: {ex['question']}\n"
        f"\u7b54\u6848: {ex['answer']}\n"
        f"\u6b65\u9aa4: {' -> '.join(ex['steps'])}\n"
        f"\u53e3\u8bc0: {card['memory_tip']}\n"
        f"\u6613\u9519\u70b9: {'; '.join(m['wrong']+'->'+m['correct'] for m in card['mistakes'])}"
    )

    print(f"\nCard: {card['title']} ({card['full_id']})")

    # Step 1: Flash generates English image prompt
    print("\nStep 1/2: gemini-2.5-flash generating image prompt...")
    step1_payload = {
        "contents": [{"parts": [{"text": "SYSTEM:\n" + SYS_PROMPT + "\n\nUSER:\n\u8bf7\u4e3a\u4ee5\u4e0b\u77e5\u8bc6\u70b9\u8bbe\u8ba1\u4e00\u5f20\u77e5\u8bc6\u5361\u7247\u7684\u56fe\u7247\u63d0\u793a\u8bcd\uff1a\n\n" + card_info}]}],
        "generationConfig": {"thinkingConfig": {"thinkingBudget": 2048}, "maxOutputTokens": 8192}
    }

    t0 = time.time()
    data1, code1 = call_proxy("gemini-2.5-flash", step1_payload, "\u77e5\u8bc6\u5361\u7247Prompt\u751f\u6210")
    t1 = time.time()
    print(f"  Status: {code1}, Time: {t1-t0:.1f}s")

    if code1 != 200:
        print(f"  FAIL Step 1! Error: {json.dumps(data1, ensure_ascii=False)[:300]}")
        sys.exit(1)

    image_prompt = ""
    for cand in data1.get("candidates", []):
        for part in (cand.get("content") or {}).get("parts", []):
            if part.get("text"):
                image_prompt += part["text"]
    image_prompt = image_prompt.strip()

    if not image_prompt:
        print(f"  FAIL: empty prompt! Response: {json.dumps(data1, ensure_ascii=False)[:500]}")
        sys.exit(1)

    print(f"  OK! Prompt length: {len(image_prompt)} chars")
    print(f"  Preview: {image_prompt[:200]}...")

    # Step 2: Image model generates image
    IMAGE_MODELS = ["gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview", "gemini-2.5-flash-image"]
    print(f"\nStep 2/2: Image model generating image...")

    step2_payload = {
        "contents": [{"parts": [{"text": image_prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}
    }

    success = False
    for model_name in IMAGE_MODELS:
        print(f"\n  Trying: {model_name}")
        t2 = time.time()
        data2, code2 = call_proxy(model_name, step2_payload, "\u56fe\u7247\u751f\u6210")
        t3 = time.time()
        print(f"  Status: {code2}, Time: {t3-t2:.1f}s")

        if code2 != 200:
            print(f"  {model_name} error {code2}: {json.dumps(data2, ensure_ascii=False)[:200]}")
            continue

        has_image = False
        img_data = None
        for cand in data2.get("candidates", []):
            for part in (cand.get("content") or {}).get("parts", []):
                if part.get("inlineData") and part["inlineData"].get("data"):
                    has_image = True
                    img_data = part["inlineData"]
                    break
            if has_image:
                break

        if has_image:
            img_bytes = base64.b64decode(img_data["data"])
            size_kb = len(img_bytes) / 1024
            fname = f"_test_promptlib_{card['full_id']}.png"
            with open(fname, "wb") as f:
                f.write(img_bytes)
            print(f"  OK! Model: {model_name}")
            print(f"  Image: {size_kb:.1f} KB")
            print(f"  Saved: {fname}")
            success = True
            break
        else:
            print(f"  {model_name}: no image in response")
            for cand in data2.get("candidates", []):
                for part in (cand.get("content") or {}).get("parts", []):
                    if part.get("text"):
                        print(f"  Text: {part['text'][:100]}")

    total = time.time() - t0
    print(f"\n{'=' * 60}")
    if success:
        print(f"PASS! Total: {total:.1f}s")
        print(f"Frontend generate image button works correctly!")
    else:
        print(f"FAIL! All image models failed. Total: {total:.1f}s")
    print("=" * 60)

if __name__ == "__main__":
    main()
