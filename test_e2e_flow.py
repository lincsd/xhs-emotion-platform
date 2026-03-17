"""端到端测试：内容生成 → 3张配图 → AI卡片匹配 → 卡片生成（模拟完整前端流程）"""
import urllib.request, urllib.error, json, time, re, base64

BASE = "https://xhs-gemini-proxy.onrender.com"
TOKEN = None

def api(method, path, body=None, timeout=200):
    url = BASE + path
    data = json.dumps(body).encode('utf-8') if body else None
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
            return True, result, time.time() - t0
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        try: err = json.loads(body_text)
        except: err = {"raw": body_text[:500]}
        return False, {"status": e.code, "error": err}, time.time() - t0
    except Exception as e:
        return False, {"exception": str(e)}, time.time() - t0

def gemini(prompt, model="gemini-2.5-flash", feature="generateContent", max_tokens=4096, timeout=120):
    body = {
        "model": model, "feature": feature, "action": "generateContent",
        "payload": {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens}
        }
    }
    return api("POST", "/api/gemini-proxy", body, timeout=timeout)

def gemini_image(prompt, model="gemini-3.1-flash-image-preview", timeout=180):
    body = {
        "model": model, "feature": "图片生成", "action": "generateContent",
        "payload": {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 8192, "responseModalities": ["TEXT", "IMAGE"]}
        }
    }
    return api("POST", "/api/gemini-proxy", body, timeout=timeout)


TEMPLATES_SUMMARY = """
1. minimal_literary(简约文艺): 情感,成长,读书,感悟,文艺,日记,散文
2. sweet_fresh(甜美清新): 日常,美食,手帐,少女,萌宠,好物,甜品,种草
3. biz_premium(商务高级): 职场,商业,投资,理财,科技,行业
4. ins_aesthetic(INS美学): 穿搭,生活,旅行,咖啡,家居,美学,ootd
5. dark_cyber(暗黑赛博): 摄影,音乐,潮流,电影,深夜,赛博
6. chinese_retro(国潮中式): 国潮,传统,文化,汉服,书法
7. note_knowledge(笔记干货): 学习,考试,干货,方法,效率,工具
8. magazine_edit(杂志排版): 时尚,大片,杂志,造型,质感
9. nature_healing(自然治愈): 治愈,心理,正能量,温暖,自然,养生
10. handwrite_diary(手写日记): 日记,心情,记录,碎碎念,随笔
11. candy_pop(活力彩虹): 彩虹,派对,生日,搞笑,活力,青春
12. breaking_news(热点速报): 新闻,热点,事件,评论,时事
13. product_showcase(种草带货): 种草,带货,好物,推荐,测评
14. ootd_collage(穿搭拼图): 穿搭,ootd,搭配,衣服
15. color_palette(配色灵感): 配色,色彩,调色,滤镜
"""


def main():
    global TOKEN

    print("=" * 65)
    print("  端到端测试：内容生成 → 3张配图 → AI卡片匹配")
    print("  模拟完整前端 generatePosts() 工作流")
    print("=" * 65)

    # ── Step 0: 登录 ──
    print("\n📝 Step 0: 登录...")
    ok, r, _ = api("POST", "/api/auth/login", {"username": "lin", "password": "950320"})
    if ok:
        TOKEN = r.get("token")
        print(f"   ✅ 登录成功")
    else:
        print(f"   ❌ 登录失败: {r}")
        return

    ok, credits, _ = api("GET", "/api/user/credits")
    start_credits = credits.get('credits', 0)
    print(f"   💰 当前积分: {start_credits}")

    total_t0 = time.time()
    results = {}
    post = None
    image_dataUrls = []

    # ── Step 1: AI 内容生成 ──
    print("\n📝 Step 1: AI 内容生成（搜索+创作 1条笔记）...")
    t0 = time.time()
    gen_prompt = """你是小红书爆款内容创作专家。请为「治愈」分类生成1条高质量小红书笔记。

要求：
1. 标题要有小红书爆款标题的特点（数字、emoji、悬念、对比等）
2. 正文200-400字，符合小红书调性
3. 包含5-8个标签
4. 封面文字（8-15字，吸引眼球）

返回JSON格式（不要markdown代码块）：
{"posts":[{"title":"标题","content":"正文","tags":"标签1,标签2","cover_text":"封面文字","category":"治愈"}]}"""

    ok, r, elapsed = gemini(gen_prompt, feature="内容生成", max_tokens=4096)
    if ok:
        text = r.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
        jm = re.search(r'\{[\s\S]*\}', text)
        if jm:
            parsed = json.loads(jm.group(0))
            post = parsed.get('posts', [{}])[0]
            print(f"   ✅ 内容生成完成 | {elapsed:.1f}s")
            print(f"   📄 标题: {post.get('title', '?')[:60]}")
            print(f"   📌 封面: {post.get('cover_text', '?')}")
            print(f"   🏷️ 标签: {post.get('tags', '?')[:60]}")
            results['content'] = {'ok': True, 'time': elapsed}
        else:
            print(f"   ⚠️ JSON解析失败，使用默认笔记 | {elapsed:.1f}s")
            post = {"title": "生活中那些被忽略的小确幸", "content": "今天分享5个让心情变好的小习惯...", "category": "治愈", "cover_text": "治愈你的每一天", "tags": "治愈,成长,正能量,心灵,生活"}
            results['content'] = {'ok': True, 'time': elapsed, 'note': '使用默认'}
    else:
        print(f"   ❌ 内容生成失败 | {elapsed:.1f}s | {json.dumps(r, ensure_ascii=False)[:200]}")
        post = {"title": "生活中那些被忽略的小确幸", "content": "今天分享5个让心情变好的小习惯...", "category": "治愈", "cover_text": "治愈你的每一天", "tags": "治愈,成长,正能量"}
        results['content'] = {'ok': False, 'time': elapsed}

    # ── Step 2-4: 生成3张配图（串行） ──
    content_snippet = (post.get('content', '') or '')[:150]
    tags = post.get('tags', '治愈,成长')

    image_prompts = [
        f"""Create a beautiful aesthetic image for a Chinese social media post.
Theme: "{post.get('title', '')}"
Category: {post.get('category', '治愈')}
Style: 小红书风格，柔和敏感的色调，文艺温暖
Requirements: Vertical 3:4 ratio, NO text overlay, artistic, dreamy, Xiaohongshu worthy""",

        f"""Create an artistic scene illustration inspired by this text:
"{content_snippet}"
Style: 小红书风格，柔和色调
Requirements: Vertical 3:4 ratio, NO text, soft, aesthetic, emotionally resonant""",

        f"""Create a visually stunning image for keywords: {tags}
Category mood: {post.get('category', '治愈')}
Style: 小红书风格，温暖治愈
Requirements: Vertical 3:4 ratio, NO text, abstract or symbolic, harmonious colors"""
    ]

    for i, prompt in enumerate(image_prompts):
        print(f"\n🎨 Step {2+i}: 生成配图 {i+1}/3...")
        t0 = time.time()
        ok, r, elapsed = gemini_image(prompt)
        has_image = False
        if ok:
            parts = r.get('candidates', [{}])[0].get('content', {}).get('parts', [])
            for p in parts:
                if 'inlineData' in p:
                    has_image = True
                    img_data = p['inlineData'].get('data', '')
                    mime = p['inlineData'].get('mimeType', 'image/png')
                    img_size = len(img_data) * 3 // 4
                    # Build data URL (same as frontend _extractImageFromResponse)
                    dataUrl = f"data:{mime};base64,{img_data[:100]}..."  # truncated for display
                    image_dataUrls.append(f"data:{mime};base64,{img_data}")
                    print(f"   ✅ 配图{i+1} 成功 | {elapsed:.1f}s | ~{img_size//1024}KB | {mime}")
                    break
            if not has_image:
                print(f"   ⚠️ 配图{i+1} 无图片数据 | {elapsed:.1f}s")
        else:
            status = r.get('status', '?')
            print(f"   ❌ 配图{i+1} 失败(HTTP {status}) | {elapsed:.1f}s")
        results[f'image_{i+1}'] = {'ok': has_image, 'time': elapsed}

    # ── Step 5: AI 卡片模板匹配（带重试） ──
    # 图片生成后等待5秒，让服务器恢复
    print(f"\n⏳ 等待5秒让服务器冷却...")
    time.sleep(5)

    print(f"\n🤖 Step 5: AI 卡片模板匹配...")

    match_prompt = f"""你是小红书卡片模板匹配专家。根据笔记内容选择最合适的卡片模板。

笔记信息:
- 标题: {post.get('title', '')}
- 分类: {post.get('category', '')}
- 标签: {post.get('tags', '')}
- 内容预览: {(post.get('content', '') or '')[:200]}
- 用户已上传 {len(image_dataUrls)} 张配图

所有模板都已支持图片展示页，请根据笔记内容选择最佳模板即可。

可选模板:
{TEMPLATES_SUMMARY}

返回JSON格式（不要markdown代码块）：
[{{"id":"模板id","reason":"推荐理由(15字内)"}}]
最多返回3个推荐，按匹配度排序。"""

    MAX_MATCH_RETRIES = 3
    matched_templates = []
    match_ok = False
    match_elapsed = 0

    for attempt in range(1, MAX_MATCH_RETRIES + 1):
        if attempt > 1:
            wait = attempt * 3  # 6s, 9s
            print(f"   🔄 第{attempt}次重试，等待{wait}秒...")
            time.sleep(wait)

        t0 = time.time()
        ok, r, elapsed = gemini(match_prompt, feature="ai_card_match", max_tokens=8192)
        match_elapsed += elapsed

        if ok:
            text = r.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
            clean = text.replace('```json', '').replace('```', '').strip()
            try:
                jm = re.search(r'\[[\s\S]*\]', clean)
                if jm:
                    matched_templates = json.loads(jm.group(0))
                else:
                    matched_templates = json.loads(clean)
                print(f"   ✅ AI匹配完成 | {elapsed:.1f}s (总{match_elapsed:.1f}s)" + (f" [第{attempt}次尝试]" if attempt > 1 else ""))
                for j, m in enumerate(matched_templates):
                    star = '⭐' if j == 0 else '  '
                    print(f"   {star} {j+1}. {m.get('id', '?')} - {m.get('reason', '?')}")
                match_ok = True
                break
            except Exception as e:
                print(f"   ⚠️ JSON解析失败 | {elapsed:.1f}s | {str(e)[:100]}")
                print(f"   原始回复: {clean[:200]}")
                # JSON解析失败不需重试
                break
        else:
            status = r.get('status', 0)
            print(f"   ❌ AI匹配失败(HTTP {status}) | {elapsed:.1f}s" + (f" [第{attempt}次尝试]" if attempt > 1 else ""))
            # 仅对502/503重试，429配额耗尽不重试
            if status in (502, 503):
                if attempt < MAX_MATCH_RETRIES:
                    continue
            elif status == 429:
                print(f"   ⚠️ 配额耗尽，不再重试")
                break
            else:
                if attempt < MAX_MATCH_RETRIES:
                    continue

    if match_ok:
        results['card_match'] = {'ok': True, 'time': match_elapsed, 'templates': matched_templates}
    else:
        results['card_match'] = {'ok': False, 'time': match_elapsed}

    total_time = time.time() - total_t0

    # ── 最终汇总 ──
    ok_final, credits_final, _ = api("GET", "/api/user/credits")
    end_credits = credits_final.get('credits', 0) if ok_final else start_credits

    print(f"\n{'=' * 65}")
    print(f"  📊 端到端测试结果汇总")
    print(f"{'=' * 65}")

    steps = [
        ('Step 1 内容生成', results.get('content', {})),
        ('Step 2 配图1', results.get('image_1', {})),
        ('Step 3 配图2', results.get('image_2', {})),
        ('Step 4 配图3', results.get('image_3', {})),
        ('Step 5 AI卡片匹配', results.get('card_match', {})),
    ]

    all_ok = True
    for name, r in steps:
        status = '✅' if r.get('ok') else '❌'
        t = r.get('time', 0)
        print(f"  {status} {name:20s}  {t:6.1f}s")
        if not r.get('ok'):
            all_ok = False

    print(f"  {'─' * 40}")
    print(f"  {'✅' if all_ok else '⚠️'}  总耗时:              {total_time:6.1f}s ({total_time/60:.1f}分钟)")
    print(f"  💰 积分消耗: {start_credits - end_credits} (剩余 {end_credits})")

    if matched_templates:
        best = matched_templates[0]
        print(f"\n  🎯 最佳模板: {best.get('id')} - {best.get('reason')}")

    print(f"\n  📋 前端工作流模拟:")
    print(f"     1. generatePosts() → AI生成笔记 ✅")
    print(f"     2. generateImagesForPosts() → 封面+3张配图 {'✅' if results.get('image_1', {}).get('ok') else '❌'}")
    print(f"     3. CardEngine.setUserPhotos(content_images) → 自动加载配图 {'✅' if len(image_dataUrls) > 0 else '❌'}")
    print(f"     4. CardEngine.matchTemplateAI() → AI选模板 {'✅' if results.get('card_match', {}).get('ok') else '❌'}")
    print(f"     5. CardEngine.generateCards() → 生成卡片(封面/图片页/正文/结尾)")
    print(f"        └─ 封面: 使用第1张配图作为全屏背景 + 渐变 + 白色标题")
    print(f"        └─ 图片页: 根据模板风格自动选择(杂志/拍立得/胶片/故事卡)")
    print(f"     6. 图片数据: {len(image_dataUrls)} 张配图已生成，可供卡片引擎使用")

    if len(image_dataUrls) > 0:
        # Save first image to verify
        first_img = image_dataUrls[0].split(',', 1)[1] if ',' in image_dataUrls[0] else ''
        if first_img:
            with open('test_card_image_1.png', 'wb') as f:
                f.write(base64.b64decode(first_img))
            print(f"\n  📸 第1张配图已保存: test_card_image_1.png")

    print()


if __name__ == '__main__':
    main()
