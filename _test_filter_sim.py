"""测试 v6 通用版 prompt — 多种卡片类型"""
import sys, os, copy, re
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')
from generate_card_images_v3 import _build_card_info_grammar

test_cases = [
    {
        'name': '搭配卡: pay attention to',
        'card': {
            'title': '高频词汇活用与固定搭配',
            'definition': 'pay attention to 是高考高频固定搭配，意为注意关注。to是介词，后接名词/动名词。',
            'type': '搭配卡',
            'memory_tip': '搭配固定要多记',
            'core_points': ['pay attention to 注意/关注', 'to后接名词或doing'],
            'mistakes': [{'wrong': 'He made a great successful.', 'correct': 'He made great success.', 'reason': '词性错误'}],
            'difficulty': 3,
        },
    },
    {
        'name': '易混词卡: affect vs effect',
        'card': {
            'title': '易混词辨析',
            'definition': 'affect 是动词，意为影响；effect 是名词，意为效果/影响。两者词性不同。',
            'type': '易混词卡',
            'memory_tip': 'A动E名',
            'core_points': ['affect(v.)影响', 'effect(n.)效果', 'have an effect on'],
            'mistakes': [{'wrong': 'The weather will effect our plans.', 'correct': 'The weather will affect our plans.', 'reason': 'effect是名词不能当动词'}],
            'difficulty': 3,
        },
    },
    {
        'name': '语法卡: be used to vs used to',
        'card': {
            'title': '语法辨析',
            'definition': 'be used to doing 表示习惯于做某事；used to do 表示过去常常做某事。两者结构和含义完全不同。',
            'type': '语法辨析卡',
            'memory_tip': 'be习惯used过去',
            'core_points': ['be used to + doing 习惯于', 'used to + do 过去常常', 'get used to + doing 逐渐习惯'],
            'mistakes': [{'wrong': 'I am used to get up early.', 'correct': 'I am used to getting up early.', 'reason': 'be used to后接doing'}],
            'difficulty': 4,
        },
    },
    {
        'name': '句型卡: too...to / enough to',
        'card': {
            'title': '句型对比',
            'definition': 'too...to 意为太...以至于不能；enough to 意为足够...可以。两者语义相反。',
            'type': '句型卡',
            'memory_tip': 'too否定enough肯定',
            'core_points': ['too + adj + to do 太...不能', 'adj + enough + to do 足够...能', 'enough放形容词后面'],
            'mistakes': [{'wrong': 'He is enough old to drive.', 'correct': 'He is old enough to drive.', 'reason': 'enough必须放在形容词后面'}],
            'difficulty': 3,
        },
    },
    # ★ 综合类知识点: title+definition 全中文，英文只在 core_points 里
    {
        'name': '综合卡: 高频词汇活用与固定搭配 (title/def纯中文)',
        'card': {
            'title': '高频词汇活用与固定搭配',
            'definition': '熟练掌握高考高频词汇的多种用法、固定搭配和短语动词，是提升语言运用能力和高考成绩的关键。',
            'type': '搭配卡',
            'memory_tip': '搭配固定要多记，熟能生巧是真理',
            'core_points': [
                '**动词固定搭配**：如`make progress` (取得进步), `take part in` (参加), `pay attention to` (注意)',
                '**形容词固定搭配**：如`be proud of` (为……自豪), `be interested in` (对……感兴趣)',
                '**名词固定搭配**：如`a sense of humor` (幽默感), `a lack of` (缺乏)',
                '**短语动词（phrasal verbs）**：如`put up with` (忍受), `turn down` (拒绝)',
                '**词性转换**：如`success` (名词), `succeed` (动词), `successful` (形容词)',
            ],
            'mistakes': [{'wrong': 'He made a great successful in his career.', 'correct': 'He made great success in his career.', 'reason': '形容词错，应用名词'}],
            'difficulty': 3,
        },
    },
]

for tc in test_cases:
    card = copy.deepcopy(tc['card'])
    prompt = _build_card_info_grammar(card, '英语', '高一', '上册')
    print(f'\n{"="*60}')
    print(f'📘 {tc["name"]}')
    print(f'{"="*60}')
    # 只打印关键部分
    lines = prompt.split('\n')
    for line in lines:
        if any(k in line for k in ['本卡主角', '语法规则', '知识要点', '对错参考', '区块B', '用法拓展', '标题', '铁律', '💡', '数据缺失']):
            print(f'  {line.strip()}')
    print(f'  → title修正: "{card["title"]}"')
    # 验证
    has_eng_title = bool(card['title'] and re.search(r'[a-zA-Z]{3,}', card['title']))
    print(f'  ✅ 英文标题' if has_eng_title else '  ❌ 标题仍是中文')
    has_usage = '用法拓展' in prompt or '用法结构' in prompt
    print(f'  ✅ 要求用法拓展' if has_usage else '  ❌ 缺少用法拓展要求')
    no_hardcode = 'pay attention to + noun' not in prompt
    print(f'  ✅ 无硬编码用法' if no_hardcode else '  ❌ 有硬编码用法(应由AI生成)')
    # 综合类特殊检查: successful/success 离题错误不应出现在 prompt 中
    if '综合卡' in tc['name']:
        has_successful = 'successful' in prompt.lower()
        print(f'  ❌ 离题错误 successful/success 仍在prompt中!' if has_successful else '  ✅ 离题错误 successful/success 已过滤')

print(f'\n✅ 所有 {len(test_cases)} 种卡片类型测试完成')