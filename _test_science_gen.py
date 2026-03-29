"""
生成理科卡片示例图片 - 用于展示 v10.9 新增卡片类型
完整两阶段: Phase 1 (prompt生成) → Phase 2 (AI图片生成)
"""
import sys, os, json, base64, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_test_science_output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 测试用卡片数据 — 从 JSON 中挑选代表性卡片
TEST_CARDS = [
    {
        "file": "public/knowledge_cards/初中/物理_八上_总结.json",
        "unit_idx": 0, "card_idx": 2,  # 测量平均速度实验 → 实验卡
        "subject": "物理", "stage": "初中", "grade_short": "八上",
    },
    {
        "file": "public/knowledge_cards/初中/化学_九上_总结.json",
        "unit_idx": 2, "card_idx": 0,  # 分子原子微观图解 → 微观图解卡
        "subject": "化学", "stage": "初中", "grade_short": "九上",
    },
    {
        "file": "public/knowledge_cards/高中/物理_高一上_总结.json",
        "unit_idx": 1, "card_idx": 0,  # 匀变速公式推导体系 → 公式推导卡
        "subject": "物理", "stage": "高中", "grade_short": "高一上",
    },
    {
        "file": "public/knowledge_cards/高中/生物_高一上_总结.json",
        "unit_idx": 2, "card_idx": 1,  # 分泌蛋白合成运输流程 → 过程流卡
        "subject": "生物", "stage": "高中", "grade_short": "高一上",
    },
]

# 加载 API keys
api_key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api_key.txt')
api_keys = []
if os.path.exists(api_key_file):
    content = open(api_key_file, encoding='utf-8').read()
    for line in content.strip().split('\n'):
        line = line.strip()
        if line.startswith('GEMINI_API_KEY='):
            key = line.split('=', 1)[1].strip()
            if ',' in key:
                api_keys.extend([k.strip() for k in key.split(',') if k.strip()])
            else:
                api_keys.append(key)

if not api_keys:
    print("❌ 未找到 GEMINI_API_KEY")
    sys.exit(1)

print(f"✅ 加载 {len(api_keys)} 个 API key")
os.environ['GEMINI_API_KEY'] = api_keys[0]

# 导入图片生成模块
from generate_card_images_v3 import generate_image_prompt_v2, generate_card_image, _resolve_canvas

results = []
for i, tc in enumerate(TEST_CARDS):
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), tc['file'])
    data = json.loads(open(fp, encoding='utf-8').read())
    card = data['units'][tc['unit_idx']]['cards'][tc['card_idx']]
    
    # 解析 grade 和 semester
    gs = tc['grade_short']
    if '上' in gs:
        semester = '上'
        grade = gs.replace('上', '').replace('_', '')
    elif '下' in gs:
        semester = '下'
        grade = gs.replace('下', '').replace('_', '')
    else:
        grade = gs
        semester = '上'
    
    print(f"\n{'='*60}")
    print(f"[{i+1}/{len(TEST_CARDS)}] 生成: {card['title']} ({card['type']})")
    print(f"  科目: {tc['subject']} | 阶段: {tc['stage']} | 年级: {grade} 学期: {semester}")
    print(f"{'='*60}")
    
    try:
        # Phase 1: 生成 prompt + manifest
        t0 = time.time()
        result = generate_image_prompt_v2(
            card=card,
            subject=tc['subject'],
            grade=grade,
            semester=semester,
            api_key=api_keys[0],
            all_keys=api_keys,
        )
        t1 = time.time()
        
        if not result or not isinstance(result, tuple) or len(result) < 2:
            print(f"  ❌ Phase 1 失败: {result}")
            results.append((card['title'], 0, t1 - t0, False))
            continue
        
        prompt_text, manifest = result
        print(f"  ✅ Phase 1 完成 ({t1-t0:.1f}s) — prompt={len(prompt_text)}字, manifest={len(manifest) if manifest else 0}项")
        
        # Phase 2: 生成图片
        canvas = _resolve_canvas(card_type=card.get('type', '方法卡'), subject=tc['subject'])
        img_data, ext, model = generate_card_image(
            prompt=prompt_text,
            keys=api_keys,
            card_title=card['title'],
            subject=tc['subject'],
            manifest=manifest,
            canvas=canvas,
        )
        t2 = time.time()
        
        if img_data:
            fname = f"{tc['subject']}_{tc['grade_short']}_{card['type']}_{card.get('card_id', i)}.{ext}"
            out_path = os.path.join(OUTPUT_DIR, fname)
            with open(out_path, 'wb') as f:
                f.write(img_data)
            size_kb = len(img_data) / 1024
            print(f"  ✅ Phase 2 完成! {fname} ({size_kb:.0f} KB, {t2-t1:.1f}s, model={model})")
            print(f"  总耗时: {t2-t0:.1f}s")
            results.append((fname, size_kb, t2 - t0, True))
        else:
            print(f"  ❌ Phase 2 图片生成失败")
            results.append((card['title'], 0, t2 - t0, False))
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        import traceback; traceback.print_exc()
        results.append((card['title'], 0, 0, False))

# 汇总
print(f"\n{'='*60}")
print("生成结果汇总:")
print(f"{'='*60}")
success = sum(1 for r in results if r[3])
for fname, size, elapsed, ok in results:
    status = '✅' if ok else '❌'
    print(f"  {status} {fname}  {size:.0f}KB  {elapsed:.1f}s")
print(f"\n成功: {success}/{len(results)}")
print(f"输出目录: {OUTPUT_DIR}")
