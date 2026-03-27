#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识卡片内容审校模块 (Card Review Gate)
========================================
在出图前拦截低质量 / 有硬伤的卡片内容。

三层审校:
  Layer 1 — 硬规则校验 (validate_hard_rules)      纯代码，零延迟
  Layer 2 — AI 教学审稿 (review_teaching_quality)  调 Gemini，~3s
  Layer 3 — Prompt 压缩 (build_structured_payload)  结构化输出

接入方式:
  from card_review import run_review_gate
  result = run_review_gate(card, subject, api_key)
  if not result['pass']:
      skip ...
"""

import re, json, os

# ═══════════════════════════════════════════
# 常量 & 阈值
# ═══════════════════════════════════════════
LANGUAGE_SCORE_THRESHOLD = 90   # 语言分 < 此值 → 不出图
TEACHING_SCORE_THRESHOLD = 85   # 教学分 < 此值 → 不出图
MAX_KNOWLEDGE_POINTS_GRAMMAR = 5  # 语法/句型/情景卡最大主知识点数
MAX_KNOWLEDGE_POINTS_VOCAB = 6    # 词汇卡最大主知识点数 (词汇卡通常 3-5 个词)
MAX_TITLE_LEN = 30                # 中文标题最大字符数
MAX_REWRITE_ATTEMPTS = 2          # 最多自动重写次数

# 英语语法卡检测关键词
ENGLISH_GRAMMAR_KEYWORDS = [
    '语法', '时态', '词性', '搭配', '句型', '从句', '虚拟语气',
    '被动语态', '主谓一致', '冠词', '介词', '连词', '代词',
    'grammar', 'tense', 'collocation', 'phrase',
    # 英语卡片类型
    '语法辨析', '高频活用', '易混辨析', '词性辨析',
]

# ─── 英文拼写检查: 基础高频词表 ───
# 不在此表中的 5+ 字母英文单词视为可疑 (需进一步检查)
_BASIC_ENGLISH_WORDS = set()

def _load_basic_words():
    """懒加载基础英语词表 (外部词表 ~10000 + 内置教学补充)"""
    global _BASIC_ENGLISH_WORDS
    if _BASIC_ENGLISH_WORDS:
        return _BASIC_ENGLISH_WORDS

    core = set()

    # 1) 从外部文件加载 (google-10000-english)
    words_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_english_words.txt')
    if os.path.exists(words_file):
        with open(words_file, 'r', encoding='utf-8') as f:
            for line in f:
                w = line.strip().lower()
                if w:
                    core.add(w)

    # 2) 教学/考试补充词 (外部词表可能遗漏的教育常见词)
    edu_supplement = {
        # 文具/学校
        'eraser','sharpener','crayon','marker','textbook','notebook','backpack',
        'blackboard','whiteboard','chalk','scissors','stapler','ruler','compass',
        'protractor','calculator','dictionary','encyclopedia','syllabus',
        # 身体部位
        'forehead','eyebrow','eyelash','cheek','tongue','throat','shoulder',
        'elbow','wrist','thumb','fingernail','ankle','heel',
        # 动物扩展
        'giraffe','hippopotamus','rhinoceros','crocodile','chimpanzee','squirrel',
        'hedgehog','tortoise','parrot','sparrow','woodpecker','grasshopper',
        'dragonfly','caterpillar','centipede','octopus','jellyfish','seahorse',
        'insect','beetle','cricket','mosquito','butterfly','firefly','ladybug',
        # 食物
        'hamburger','sandwich','sausage','chocolate','strawberry','blueberry',
        'watermelon','pineapple','grapefruit','tangerine','avocado','broccoli',
        'cauliflower','asparagus','mushroom','cucumber','eggplant','zucchini',
        # 天气/自然
        'temperature','thermometer','hurricane','earthquake','lightning','thunder',
        'rainbow','atmosphere','hemisphere','continent','peninsula','archipelago',
        # 家庭称谓
        'grandpa','grandma','grandfather','grandmother','granddaughter','grandson',
        'uncle','auntie','nephew','niece','cousin',
        # 语法术语
        'noun','verb','adjective','adverb','pronoun','preposition',
        'conjunction','interjection','article','phrase','clause','sentence',
        'subject','predicate','modifier','tense','aspect','mood',
        'voice','singular','plural','masculine','feminine','neuter',
        'infinitive','participle','gerund','modal','auxiliary',
        'collocation','synonym','antonym','homophone','prefix','suffix',
        'syllable','vowel','consonant','stress','intonation',
        # 教学指令
        'underline','highlight','rewrite','translate','paraphrase',
        'summarize','brainstorm','categorize','prioritize','alphabetize',
        # 考试/学科
        'examination','assessment','curriculum','semester','prerequisite',
        'scholarship','certificate','diploma','graduation','commencement',
        # 复合词/常见学校用词
        'schoolbag','classmate','classroom','homework','birthday','football',
        'basketball','baseball','volleyball','playground','bookstore','airport',
        'supermarket','postcard','weekend','somewhere','everywhere','anywhere',
        'nothing','something','everything','anything','everyone','someone',
        'anyone','nobody','whoever','whatever','whenever','wherever','however',
        'although','because','therefore','otherwise','meanwhile','furthermore',
        'nowadays','themselves','ourselves','yourselves','itself',
        'cannot','didn','doesn','isn','wasn','weren','hadn','hasn','shouldn',
        'wouldn','couldn','mustn','aren',
        # 复合人称/常见复合名词
        'snowman','snowmen','postman','postmen','policeman','policemen',
        'fireman','firemen','fisherman','businessman','gentleman',
        'doorbell','raincoat','rainforest','sunlight','moonlight','starfish',
        'seashell','outside','inside','upstairs','downstairs','afternoon',
        'tonight','tomorrow','yesterday','together','sometimes','everyone',
        # 日常用品/衣物
        'sweater','jacket','trousers','umbrella','glasses','toothbrush',
        'toothpaste','bathroom','bedroom','kitchen','living','dining',
        # 高考高频词(词表遗漏补充)
        'pronounce','pronunciation','fluency','fluent','comprehension','comprehend',
        'emphasize','emphasis','distinguish','circumstance','embarrass','embarrassed',
        'enthusiasm','enthusiastic','exaggerate','inevitable','interrupt','negotiate',
        'reluctant','persuade','perceive','privilege','prejudice','conscience',
        'controversy','correspond','curiosity','desperate','dilemma','discipline',
        'elaborate','equivalent','excellence','sacrifice','conscience','suspicion',
        'sympathy','thorough','tremendous','aggressive','Anniversary','apparatus',
        'bureau','catalogue','cemetery','colleague','controversy','correspondence',
        'desperate','dilemma','discipline','embarrassment','extravagant','fascinate',
        'gorgeous','harassment','hygiene','ignorance','indigenous','innocent',
        'jealous','leisure','maintenance','miscellaneous','nuisance','obstacle',
        'parliament','peculiar','phenomenon','privilege','questionnaire','receipt',
        'recommend','restaurant','rhythm','schedule','simultaneous','technique',
        'thorough','trivial','tyranny','unanimous','vehicle','weird','yield',
        # 高中常见动词/形容词
        'accomplish','acknowledge','adequate','anticipate','beneficial','compensate',
        'competent','conform','conscientious','consecutive','contemplate','contradict',
        'controversy','deceive','deliberate','deprive','deteriorate','diagnose',
        'diminish','discard','discriminate','dissolve','dominate','eligible',
        'encounter','endeavor','enormous','evacuate','exploit','feasible',
        'fluctuate','formulate','fragile','fundamental','genuine','grateful',
        'hazard','hesitate','humble','illustrate','implement','implicit',
        'impose','indifferent','inferior','inhabit','manipulate','moderate',
        'monument','negotiate','nourish','oblige','overlook','penetrate',
        'persistent','plausible','portable','postpone','precaution','precede',
        'preliminary','presume','prevail','primitive','proclaim','profound',
        'prohibit','prominent','propagate','prospect','provoke','punctual',
        'refrain','regardless','regulate','reinforce','relevant','remedy',
        'resemble','resign','restrain','retrieve','rigorous','ruthless',
        'setback','shatter','skeptical','solemn','specify','spontaneous',
        'stagger','stimulate','subordinate','subsidy','supplement','suppress',
        'surveillance','sustainable','tentative','terminate','tolerate',
        'transform','transparent','undergo','undermine','undertake','utilize',
        'vanish','elaborate','vulnerable','whatsoever','widespread','withdraw',
    }
    core.update(edu_supplement)

    _BASIC_ENGLISH_WORDS = core
    return _BASIC_ENGLISH_WORDS


def detect_fabricated_words(text):
    """
    检测可能是 AI 编造的英文假词 (如 guestioneful, bindingly)。
    策略: 提取所有 6+ 字母的英文单词，不在基础词表中的标记为可疑。
    使用 ~10000 词外部词表 + 教学补充词 + 多层词形还原。
    返回可疑词列表。
    """
    words = _load_basic_words()
    # 提取所有英文单词 (最小 6 字母，减少误报)
    tokens = re.findall(r"\b[a-zA-Z]{6,}\b", text)
    suspicious = []
    for tok in tokens:
        low = tok.lower()
        # 跳过全大写缩写
        if tok.isupper():
            continue
        # 直接匹配
        if low in words:
            continue
        # 多层词形还原
        stems = set()
        # 常见屈折后缀
        inflections = [
            ('ies', 'y'), ('ied', 'y'), ('ying', 'y'),  # carry → carries
            ('ves', 'f'), ('ves', 'fe'),                 # knife → knives
            ('ses', 's'), ('xes', 'x'), ('zes', 'z'),   # bus → buses
            ('ches', 'ch'), ('shes', 'sh'),              # watch → watches
            ('ness', ''), ('ment', ''), ('tion', ''), ('sion', ''),
            ('able', ''), ('ible', ''), ('ful', ''), ('less', ''),
            ('ous', ''), ('ive', ''), ('ical', ''), ('ence', ''),
            ('ance', ''), ('ment', ''), ('ness', ''),
        ]
        simple_suffixes = ['s', 'es', 'ed', 'ing', 'ly', 'er', 'est',
                           'tion', 'sion', 'ment', 'ness', 'ful', 'less',
                           'able', 'ible', 'ous', 'ive', 'al', 'ical',
                           'ity', 'ize', 'ise', 'ify', 'ate', 'ent', 'ant']
        for suffix in simple_suffixes:
            if low.endswith(suffix) and len(low) - len(suffix) >= 3:
                root = low[:-len(suffix)]
                stems.add(root)
                stems.add(root + 'e')     # e.g. make → making
                stems.add(root + root[-1]) # e.g. run → running (doubled consonant)
        for old_end, new_end in inflections:
            if low.endswith(old_end) and len(low) - len(old_end) >= 2:
                stems.add(low[:-len(old_end)] + new_end)

        # 检查任一词根是否在词表中
        if any(s in words for s in stems):
            continue
        suspicious.append(tok)
    # 去重
    return list(dict.fromkeys(suspicious))


# 过于泛化的标题关键词 (这些单独作为标题不够具体)
VAGUE_TITLE_PATTERNS = [
    '高频词汇', '重点语法', '常见搭配', '易错考点', '必背知识',
    '核心知识', '重要知识', '关键考点', '必考考点', '常考题型',
    '高频考点', '重点知识', '基础语法', '基础词汇',
]
# 泛化标题子串 — 英语卡标题如果纯中文≤4字且包含这些词，就是泛化
VAGUE_TITLE_SUBSTRINGS = [
    '活用', '辨析', '高频', '重点', '考点', '必背',
    '常见', '基础', '核心', '关键', '常考',
]

# 常见重复词模式 (英文)
REPEATED_WORD_PATTERN = re.compile(
    r'\b(\w{2,})\s+\1\b', re.IGNORECASE
)

# 常见残缺表达模式 (英文短语末尾不完整)
INCOMPLETE_PHRASE_PATTERNS = [
    # "success in" 后面没有名词/动名词
    re.compile(r'\b(success|successful|succeed)\s+in\s*[.,;!?\s]*$', re.IGNORECASE),
    # "pay attention to" 后面没有宾语
    re.compile(r'\bpay\s+(?:close\s+)?attention\s+to\s*[.,;!?\s]*$', re.IGNORECASE),
    # "is important to" 后面没有动词
    re.compile(r'\bis\s+important\s+to\s*[.,;!?\s]*$', re.IGNORECASE),
    # "depend on" 后面没有宾语
    re.compile(r'\bdepend(?:s)?\s+on\s*[.,;!?\s]*$', re.IGNORECASE),
]

# 笼统错因关键词 —— 这些单独出现时说明错因不够具体
VAGUE_REASON_PATTERNS = [
    '词性错', '搭配错', '语法错', '用法错',
    '词性不对', '搭配不对', '用错了',
]


# ═══════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════

def _first_mistake(card, field='wrong'):
    """从 card['mistakes'] 里取第一条的指定字段"""
    mistakes = card.get('mistakes', [])
    if not mistakes:
        return ''
    m = mistakes[0]
    if isinstance(m, dict):
        return str(m.get(field, ''))
    return str(m)


def _all_text(card):
    """把卡片里所有文本拼成一个大字符串，用于全局检测"""
    parts = [
        card.get('title', ''),
        card.get('definition', ''),
        ' '.join(str(p) for p in card.get('core_points', [])),
        card.get('memory_tip', ''),
        _first_mistake(card, 'wrong'),
        _first_mistake(card, 'correct'),
    ]
    ex = card.get('example', {})
    if ex:
        parts.append(str(ex.get('question', '')))
        parts.append(str(ex.get('answer', '')))
        parts.extend(str(s) for s in ex.get('steps', []))
    return '\n'.join(parts)


def _has_english(text):
    """检测文本中是否包含英文单词"""
    return bool(re.search(r'[a-zA-Z]{2,}', text))


def is_english_grammar_card(card, subject=''):
    """判断是否为英语语法类卡片"""
    if subject == '英语':
        return True
    text = _all_text(card).lower()
    return any(kw in text for kw in ENGLISH_GRAMMAR_KEYWORDS)


def detect_knowledge_candidates(card):
    """
    检测卡片中包含多少个独立知识点。
    策略: 检查 core_points 里是否有明显不同主题的条目。
    返回去重后的知识点列表。
    """
    points = card.get('core_points', [])
    if len(points) <= 1:
        return points[:1]

    # 简单策略: 如果 core_points 里有明显不同的英文短语/语法结构，算多个知识点
    unique_topics = []
    seen_roots = set()
    for p in points:
        # 提取英文关键短语
        eng_phrases = re.findall(r'[a-zA-Z][a-zA-Z\s]{2,}[a-zA-Z]', str(p))
        root = ' '.join(eng_phrases).lower().strip() if eng_phrases else str(p)[:10].lower()
        if root and root not in seen_roots:
            seen_roots.add(root)
            unique_topics.append(str(p))

    # 如果没有英文，按中文主题去重
    if not unique_topics:
        for p in points:
            stub = str(p)[:8]
            if stub not in seen_roots:
                seen_roots.add(stub)
                unique_topics.append(str(p))

    return unique_topics


def has_repeated_word(text):
    """检测是否有连续重复的英文单词，如 'can can'。
    排除自然拼读/语音教学中的合法重复 (如 'ball: ball', 'B-b-ball')
    """
    match = REPEATED_WORD_PATTERN.search(text)
    if not match:
        return False
    word = match.group(1).lower()
    # 自然拼读卡里, 单个名词在发音演示中重复是正常的
    # 如 "Aa apple apple" 或 "ball: ball"
    # 只标记语法/功能词重复 (如 can can, the the, is is)
    grammar_words = {
        'can','could','will','would','shall','should','may','might','must',
        'is','am','are','was','were','be','been','being',
        'have','has','had','do','does','did',
        'the','a','an','this','that','these','those',
        'not','no','and','or','but','if','so','for','to',
        'he','she','it','they','we','you','i',
    }
    return word in grammar_words


def has_incomplete_phrase(text):
    """检测是否有残缺的英文表达"""
    # 按句子和换行拆分后逐段检查
    sentences = re.split(r'[.!?。！？\n]', text)
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        for pat in INCOMPLETE_PHRASE_PATTERNS:
            if pat.search(sent):
                return True
    return False


def looks_like_complete_sentence(text):
    """
    判断一段英文文本是否看起来像完整句子。
    至少要有: 主语 + 谓语动词 + 一定长度
    """
    text = text.strip()
    if not text:
        return False
    # 太短不可能是完整句
    if len(text) < 10:
        return False
    # 至少包含一个动词的痕迹(简化判断)
    words = text.split()
    if len(words) < 3:
        return False
    # 如果全是中文，跳过英文句子检查
    if not re.search(r'[a-zA-Z]', text):
        return True
    # 英文句子: 至少3个单词，首字母大写或全小写都算
    return True


def vague_error_reason(card):
    """检测 mistakes 里的错因是否过于笼统"""
    mistakes = card.get('mistakes', [])
    if not mistakes:
        return False  # 没有 mistakes 不算笼统（可能不需要）
    for m in mistakes:
        if not isinstance(m, dict):
            continue
        wrong = str(m.get('wrong', ''))
        correct = str(m.get('correct', ''))
        # 如果 wrong 和 correct 都很短且笼统
        combined = wrong + correct
        for vague in VAGUE_REASON_PATTERNS:
            if vague in combined and len(combined) < 20:
                return True
    return False


# ═══════════════════════════════════════════
# Layer 1: 硬规则校验
# ═══════════════════════════════════════════

def validate_hard_rules(card, subject=''):
    """
    纯代码校验，零延迟。
    返回: { 'pass': bool, 'issues': list[str], 'stage': 'hard_rule' }
    """
    issues = []
    is_eng = is_english_grammar_card(card, subject)
    text = _all_text(card)

    # ── 规则 1: 重复词 ──
    if has_repeated_word(text):
        match = REPEATED_WORD_PATTERN.search(text)
        word = match.group(1) if match else '?'
        issues.append(f'存在重复词: "{word} {word}"')

    # ── 规则 2: 残缺表达 (只检查 mistakes 的 wrong/correct 字段，不检查标题/定义) ──
    mistake_texts = []
    for m in card.get('mistakes', []):
        if isinstance(m, dict):
            mistake_texts.append(str(m.get('wrong', '')))
            mistake_texts.append(str(m.get('correct', '')))
    mistake_text = '\n'.join(mistake_texts)
    if _has_english(mistake_text) and has_incomplete_phrase(mistake_text):
        issues.append('存在残缺英文表达 (短语末尾缺宾语/补语)')

    # ── 规则 3: 正误对比完整性 ──
    wrong = _first_mistake(card, 'wrong')
    correct = _first_mistake(card, 'correct')
    if card.get('mistakes'):
        if not wrong:
            issues.append('mistakes 缺少 wrong 字段')
        if not correct:
            issues.append('mistakes 缺少 correct 字段')

    # ── 规则 4: 英语卡正确例句必须像完整句 ──
    # 仅对语法/句型卡的纯英文 correct 字段检查, 跳过词汇卡(单词即正确答案)和中文解释
    if is_eng and correct and _has_english(correct):
        card_type_4 = card.get('type', '') + card.get('title', '')
        is_vocab_4 = any(kw in card_type_4 for kw in ('词汇', '单词', '拼读', '发音'))
        if not is_vocab_4:
            eng_chars = len(re.findall(r'[a-zA-Z]', correct))
            total_chars = len(correct.replace(' ',''))
            if total_chars > 0 and eng_chars / total_chars > 0.8:
                # 排除: 只有1-2个英文单词的答案 (如 "pencil", "swim")
                eng_words = re.findall(r'[a-zA-Z]+', correct)
                if len(eng_words) >= 3 and not looks_like_complete_sentence(correct):
                    issues.append('正确例句不是完整句')

    # ── 规则 5: 单卡知识点过多 ──
    if is_eng:
        candidates = detect_knowledge_candidates(card)
        card_type = card.get('type', '')
        is_vocab = '词汇' in card_type or '词汇' in card.get('title', '')
        max_kp = MAX_KNOWLEDGE_POINTS_VOCAB if is_vocab else MAX_KNOWLEDGE_POINTS_GRAMMAR
        if len(candidates) > max_kp:
            issues.append(f'单卡知识点过多 ({len(candidates)}个, 限{max_kp}), 建议拆分')

    # ── 规则 6: 错因过于笼统 ──
    if is_eng and vague_error_reason(card):
        issues.append('错因解释过于笼统 (如"词性错"), 需要具体说明')

    # ── 规则 7: 标题过长 ──
    title = card.get('title', '')
    if len(title) > MAX_TITLE_LEN:
        issues.append(f'标题过长 ({len(title)}字), 建议≤{MAX_TITLE_LEN}字')

    # ── 规则 8: 定义缺失 ──
    if not card.get('definition', '').strip():
        issues.append('缺少 definition 字段')

    # ── 规则 9: AI 造词检测 ──
    if is_eng and _has_english(text):
        fabricated = detect_fabricated_words(text)
        if fabricated:
            issues.append(f'疑似 AI 造词: {", ".join(fabricated[:3])}')

    # ── 规则 10: 标题过于泛化 ──
    title = card.get('title', '')
    title_flagged = False
    for vague in VAGUE_TITLE_PATTERNS:
        if title.strip() == vague:
            issues.append(f'标题 "{title}" 过于泛化，需要精确到具体知识点 (如 "succeed词族辨析")')
            title_flagged = True
            break
    # 英语卡额外检测: 纯中文≤4字 + 含泛化子串 → 大概率不够具体
    if not title_flagged and is_eng:
        has_eng_in_title = bool(re.search(r'[a-zA-Z]', title))
        cn_chars_in_title = len(re.findall(r'[\u4e00-\u9fff]', title))
        if not has_eng_in_title and cn_chars_in_title <= 4:
            for sub in VAGUE_TITLE_SUBSTRINGS:
                if sub in title:
                    issues.append(f'标题 "{title}" 过于泛化 (英语卡标题应包含具体词/短语，如 "pay attention to搭配")')
                    break

    # ── 规则 11: Steps 连贯性 + 离题检测 (英语卡) ──
    if is_eng:
        steps = card.get('example', {}).get('steps', [])
        if len(steps) >= 2:
            # 标题+定义的英文关键词 = 本卡核心主题
            topic_text = (card.get('title', '') + ' ' + card.get('definition', '')).lower()
            topic_kw = set(re.findall(r'[a-zA-Z]{3,}', topic_text))
            # 提取每个 step 的英文关键词
            step_keywords = []
            for s in steps:
                kw = set(re.findall(r'[a-zA-Z]{3,}', str(s).lower()))
                step_keywords.append(kw)
            # 检测: 某个 step 既与相邻 step 断连，又与标题/定义无关 → 离题
            off_topic_steps = []
            for i, kw in enumerate(step_keywords):
                if not kw:
                    continue
                # 与标题主题有没有交集
                has_topic_overlap = bool(kw & topic_kw)
                # 与相邻步骤有没有交集
                has_neighbor_overlap = False
                if i > 0 and step_keywords[i-1]:
                    has_neighbor_overlap = has_neighbor_overlap or bool(kw & step_keywords[i-1])
                if i < len(step_keywords) - 1 and step_keywords[i+1]:
                    has_neighbor_overlap = has_neighbor_overlap or bool(kw & step_keywords[i+1])
                if not has_topic_overlap and not has_neighbor_overlap:
                    off_topic_steps.append(i + 1)
            if off_topic_steps:
                issues.append(f'Step {off_topic_steps} 与本卡主题无关，可能混杂了不相关知识点')

    # ── 规则 12: 步骤教学深度检测 (英语卡，防止拆词式浅层内容) ──
    if is_eng:
        steps = card.get('example', {}).get('steps', [])
        if len(steps) >= 2:
            short_step_count = 0
            for s in steps:
                s_str = str(s).strip()
                eng_words = re.findall(r'[a-zA-Z]+', s_str)
                cn_chars = len(re.findall(r'[\u4e00-\u9fff]', s_str))
                # 步骤只有1-3个英文单词且中文极少 → 浅层
                if len(eng_words) <= 3 and cn_chars <= 8:
                    short_step_count += 1
            if short_step_count >= len(steps) * 0.6:
                issues.append(
                    f'步骤内容过浅: {short_step_count}/{len(steps)}步只有孤立单词/短语，'
                    f'缺少完整例句和解释 (禁止把短语拆成单词当步骤)'
                )

    # ── 规则 13: 口诀完整性检测 ──
    memory_tip = card.get('memory_tip', '').strip()
    if memory_tip:
        # 检查是否以虚词/助词结尾(表被截断)
        _DANGLING_TAILS = set('要的了地得在是和与用把被让给往到从向对着过将')
        if memory_tip[-1] in _DANGLING_TAILS and len(memory_tip) <= 8:
            issues.append(
                f'口诀疑似截断: "{memory_tip}" 以虚词"{memory_tip[-1]}"结尾，'
                f'不是完整短句 (如"搭配固定要" → 应改为"搭配用to")'
            )
        # 检查是否太笼统无意义
        _USELESS_SLOGANS = [
            '多练就会', '记住就好', '背了就行', '牢记即可', '熟能生巧',
            '搭配固定要多记', '重点词汇要掌握', '语法规则记清楚',
            '多背多练多记', '词汇积累靠坚持', '知识要点记牢',
            '搭配要多记', '固定搭配记住', '语法要牢记',
            '记住哦', '来看看', '一起学', '加油哦', '注意哦',
            '要记住', '记住了', '来看看吧', '一起学吧',
        ]
        if memory_tip in _USELESS_SLOGANS:
            issues.append(f'口诀"{memory_tip}"过于笼统无意义，需要包含具体知识点(如"to后接名词")')
        # 进一步检查：英语卡口诀不含任何英文关键词也是问题
        if subject in ('英语', 'english') and memory_tip:
            has_eng_word = bool(re.search(r'[a-zA-Z]{2,}', memory_tip))
            has_specific_cn = bool(re.search(r'(介词|名词|动词|原形|ing|ed|不可数|可数|单数|复数|被动|主动|从句|定语|状语)', memory_tip))
            if not has_eng_word and not has_specific_cn and len(memory_tip) >= 4:
                issues.append(
                    f'英语卡口诀"{memory_tip}"缺少英文关键词或具体语法术语，'
                    f'应含具体知识点(如"to后加名词""注意pay的搭配")'
                )

    return {
        'pass': len(issues) == 0,
        'issues': issues,
        'stage': 'hard_rule',
    }


# ═══════════════════════════════════════════
# Layer 2: AI 教学审稿
# ═══════════════════════════════════════════

# 审稿 system prompt —— 只负责挑错，不负责创作
_REVIEW_SYSTEM_PROMPT = """你是一位严格的英语教学内容审稿员。
你只负责审稿，绝不负责创作。

你需要检查以下 5 个维度:
1. 语言自然度 — 英文例句是否地道自然
2. 语法准确性 — 语法、搭配、词性是否正确
3. 知识点聚焦 — 是否只聚焦一个主知识点，有无混杂
4. 正误对比清晰度 — 错句是否真错，正句是否真对，错因是否具体
5. 秒懂适配度 — 内容是否适合压缩成一张图片教学卡

严格按 JSON 格式输出，不要输出其他内容:
{
  "pass": true或false,
  "language_score": 0到100的整数,
  "teaching_score": 0到100的整数,
  "issues": ["问题1", "问题2"],
  "rewrite_suggestion": "如果不通过，给出具体修改建议；通过则留空"
}

评分标准:
- language_score ≥ 90: 英文地道自然，无语法错误
- language_score 70-89: 有小瑕疵但不影响理解
- language_score < 70: 有硬伤，不能出图

- teaching_score ≥ 85: 知识点聚焦，正误清晰，适合做卡
- teaching_score 70-84: 有改进空间但基本可用
- teaching_score < 70: 不适合出图

pass = true 的条件: language_score ≥ 90 且 teaching_score ≥ 85 且 issues 为空"""


def _build_review_user_prompt(card, subject=''):
    """构建审稿用户 prompt"""
    wrong = _first_mistake(card, 'wrong')
    correct = _first_mistake(card, 'correct')
    ex = card.get('example', {})

    lines = [
        f'学科: {subject}',
        f'标题: {card.get("title", "")}',
        f'定义: {card.get("definition", "")}',
        f'核心点: {json.dumps(card.get("core_points", []), ensure_ascii=False)}',
        f'例题: {ex.get("question", "")}',
        f'答案: {ex.get("answer", "")}',
        f'错句: {wrong}',
        f'正句: {correct}',
        f'口诀: {card.get("memory_tip", "")}',
    ]
    return '\n'.join(lines)


def review_teaching_quality(card, subject, gemini_call_fn, api_key, text_model='gemini-2.5-flash'):
    """
    调用 AI 进行教学质量审稿。

    参数:
      card          — 卡片 dict
      subject       — 学科名
      gemini_call_fn — generate_card_images.gemini_call 函数引用
      api_key       — Gemini API Key
      text_model    — 文字模型名

    返回:
      {
        'pass': bool,
        'language_score': int,
        'teaching_score': int,
        'issues': list[str],
        'rewrite_suggestion': str,
        'stage': 'ai_review',
        'raw': str  # 原始返回，便于调试
      }
    """
    user_prompt = _build_review_user_prompt(card, subject)
    contents = [
        {'role': 'user', 'parts': [{'text': f'{_REVIEW_SYSTEM_PROMPT}\n\n--- 待审稿卡片 ---\n{user_prompt}'}]}
    ]
    gen_config = {
        'maxOutputTokens': 2048,
        'temperature': 0.1,  # 审稿要稳定
    }

    resp = gemini_call_fn(text_model, contents, api_key, gen_config=gen_config)

    # 默认结果 (调用失败时放行，避免阻塞管线)
    default = {
        'pass': True,
        'language_score': 95,
        'teaching_score': 90,
        'issues': [],
        'rewrite_suggestion': '',
        'stage': 'ai_review',
        'raw': '',
    }

    if not resp:
        print('    [review] AI 审稿调用失败, 默认放行')
        return default

    # 解析返回
    try:
        candidates = resp.get('candidates', [])
        if not candidates:
            return default

        text = ''
        for part in candidates[0].get('content', {}).get('parts', []):
            if 'text' in part and not part.get('thought', False):
                text += part['text']

        # 尝试提取 JSON
        text = text.strip()
        # 去掉 markdown 代码块
        if text.startswith('```'):
            text = re.sub(r'^```\w*\n?', '', text)
            text = re.sub(r'\n?```$', '', text)
            text = text.strip()

        parsed = json.loads(text)
        result = {
            'pass': bool(parsed.get('pass', True)),
            'language_score': int(parsed.get('language_score', 95)),
            'teaching_score': int(parsed.get('teaching_score', 90)),
            'issues': list(parsed.get('issues', [])),
            'rewrite_suggestion': str(parsed.get('rewrite_suggestion', '')),
            'stage': 'ai_review',
            'raw': text,
        }

        # 强制执行阈值 (不信任模型自己的 pass 判断)
        if result['language_score'] < LANGUAGE_SCORE_THRESHOLD:
            result['pass'] = False
            if f'语言分 {result["language_score"]} < {LANGUAGE_SCORE_THRESHOLD}' not in result['issues']:
                result['issues'].append(f'语言分 {result["language_score"]} < {LANGUAGE_SCORE_THRESHOLD}')
        if result['teaching_score'] < TEACHING_SCORE_THRESHOLD:
            result['pass'] = False
            if f'教学分 {result["teaching_score"]} < {TEACHING_SCORE_THRESHOLD}' not in result['issues']:
                result['issues'].append(f'教学分 {result["teaching_score"]} < {TEACHING_SCORE_THRESHOLD}')

        return result

    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        print(f'    [review] 解析审稿结果失败: {e}')
        default['raw'] = text if 'text' in dir() else ''
        return default


# ═══════════════════════════════════════════
# Layer 3: 结构化 Payload 构建
# ═══════════════════════════════════════════

def build_structured_payload(card, subject='', review_result=None):
    """
    把卡片信息压缩成结构化的 prompt 输入。
    后续 prompt 生成只从这些字段里取值，不再自由抓原始 card。
    """
    review_result = review_result or {}
    wrong = _first_mistake(card, 'wrong')
    correct = _first_mistake(card, 'correct')
    ex = card.get('example', {})

    return {
        'title': card.get('title', ''),
        'card_type': card.get('type', ''),
        'subject': subject,
        'definition': card.get('definition', ''),
        'core_points': card.get('core_points', [])[:3],
        'example_question': ex.get('question', ''),
        'example_answer': ex.get('answer', ''),
        'example_steps': ex.get('steps', []),
        'wrong_example': wrong,
        'correct_example': correct,
        'memory_tip': card.get('memory_tip', ''),
        'difficulty': card.get('difficulty', 3),
        'is_english_grammar': is_english_grammar_card(card, subject),
        'review_hint': review_result.get('rewrite_suggestion', ''),
    }


# ═══════════════════════════════════════════
# 英语语法卡专用 Prompt 模板
# ═══════════════════════════════════════════

ENGLISH_GRAMMAR_PROMPT_TEMPLATE = """你是英语语法教学卡图片设计师。

══════ 铁 律 (违反任何一条 = 废卡) ══════

1. 一张卡只讲 **一个** 知识点 (如 "succeed词族" 或 "pay attention to搭配"，不能两个都讲)
2. 卡面上所有英文必须是 **真实存在的单词和短语**，禁止编造词汇
3. 正确例句必须是 **完整、地道、语法正确** 的英文句子
4. 错误例句必须是 **真实常见的典型错误**，不能人为编造不自然的错句
5. 错因必须 **具体标注词性/搭配/句法** (如 "succeed是动词, 这里需要名词success")
6. 标题必须精确到知识点 (如 "succeed词族辨析")，不能写 "高频词汇" "重点语法" 等空泛标题
7. 如有 Steps，每步必须聚焦同一知识点，逻辑递进
8. 不出现任何与主知识点无关的单词/短语/例句

══════ 信息块固定结构 (只有这 6 块，多一块都不行) ══════

[标题] 格式: "知识点名: 关键短语", 如 "词族辨析: succeed"，≤10中文字
[主规则] 一句话核心规则, ≤15字, 如 "great后接名词success, 不接形容词successful"
[正确例句] 一个完整自然英文句 + 关键词绿色高亮 + ✓
[错误例句] 一个典型错误英文句 + 错误词红色删除线 + ✗
[错因解释] ≤20字中文, 必须标注词性/搭配, 如 "successful是形容词→应改为名词success"
[记忆口诀] ≤10字, 如 "great配名词, 别用形容词"

⚠️ 禁止添加:
- 第二组正误对比
- 不相关的 Step 拆解
- 与主知识点无关的词汇或短语
- "高频词汇" "重点必背" 等无意义装饰文字

══════ 视觉设计 ══════

- 竖版 3:4 比例
- 渐变背景, 小红书风格 (鲜明温暖有活力)
- 标题用鲜色 banner, 超大加粗字体 (72pt)
- 正误对比: 上下或左右并排, 差异词用颜色强调
  - ✓ 正确: 翠绿 #2ED573 高亮关键词
  - ✗ 错误: 亮红 #FF4757 删除线关键词
- 错因: 橙色/蓝色色块, 箭头指向错误位置
- 记忆口诀: 便签纸风格, 手写感
- 最多 3 处高亮重点
- 只有 3-4 个视觉区块 (标题 / 规则 / 正误对比 / 口诀)
- ≥ 25% 留白
- 可爱小老师卡通角色 + ≤6字气泡 (如 "秒懂!")

══════ 配色 ══════

- 背景: 渐变 (如薰衣草紫 #E8D5F5→#D9AAF5 或 薄荷蓝 #A1C4FD→#C2E9FB)
- 标题: 饱和色 banner (亮粉 #FF6B81 / 活力橙 #FF9F43)
- 内容区: 白色/浅奶油圆角卡片

══════ 文字原则 ══════

- 全卡中文 ≤ 30 字
- 英文例句保持原样, 关键词高亮
- 标题 ≤ 10 字
- 规则 ≤ 15 字
- 错因 ≤ 20 字
- 口诀 ≤ 10 字
- 不写段落, 不写解释性长文

══════ 输出 ══════

只输出一段英文图片生成提示词, 不输出其他内容。
提示词开头必须写: "IMPORTANT: All visible text must be Simplified Chinese (简体中文) except for English example sentences. LARGE BOLD font. Clean layout. Only ONE grammar point per card."
长度: 300-450 英文单词

⚠️ 最终检查: 生成前确认卡面上只出现与主知识点直接相关的英文词汇，没有拼凑无关内容。"""


def generate_english_grammar_prompt(payload, gemini_call_fn, api_key, text_model='gemini-2.5-flash'):
    """
    英语语法卡专用: 用结构化 payload 生成图片提示词。
    """
    card_info = f"""标题: {payload['title']}
主规则: {payload['definition'][:80]}
核心点: {', '.join(str(p) for p in payload['core_points'][:3])}
错误例句: {payload['wrong_example']}
正确例句: {payload['correct_example']}
例题: {payload['example_question'][:100]}
答案: {payload['example_answer'][:60]}
记忆点: {payload['memory_tip'][:30]}
{('审稿建议: ' + payload['review_hint'][:200]) if payload.get('review_hint') else ''}"""

    contents = [
        {'role': 'user', 'parts': [{'text': f'{ENGLISH_GRAMMAR_PROMPT_TEMPLATE}\n\n--- 卡片信息 ---\n{card_info}'}]}
    ]
    gen_config = {
        'maxOutputTokens': 8192,
        'temperature': 0.7,
        'thinkingConfig': {'thinkingBudget': 1024}
    }

    resp = gemini_call_fn(text_model, contents, api_key, gen_config=gen_config)
    if not resp:
        return None

    try:
        candidates = resp.get('candidates', [])
        if candidates:
            parts = candidates[0].get('content', {}).get('parts', [])
            best_text = ''
            for part in parts:
                if 'text' in part and not part.get('thought', False):
                    txt = part['text'].strip()
                    if len(txt) > len(best_text):
                        best_text = txt
            if len(best_text) > 50:
                return best_text
            # fallback
            for part in parts:
                if 'text' in part:
                    txt = part['text'].strip()
                    if len(txt) > len(best_text):
                        best_text = txt
            if len(best_text) > 50:
                return best_text
    except Exception as e:
        print(f'    [eng-prompt parse error] {e}')
    return None


# ═══════════════════════════════════════════
# 统一入口: 审校闸门
# ═══════════════════════════════════════════

def run_review_gate(card, subject, gemini_call_fn=None, api_key=None, text_model='gemini-2.5-flash'):
    """
    完整审校流程: 硬规则 → AI审稿 → 结构化输出。

    返回:
    {
        'pass': bool,
        'stage': 'hard_rule' | 'ai_review' | 'passed',
        'issues': list[str],
        'hard_result': dict,
        'review_result': dict | None,
        'payload': dict | None,
    }
    """
    is_eng = is_english_grammar_card(card, subject)

    # ── Layer 1: 硬规则 ──
    hard_result = validate_hard_rules(card, subject)
    if not hard_result['pass']:
        return {
            'pass': False,
            'stage': 'hard_rule',
            'issues': hard_result['issues'],
            'hard_result': hard_result,
            'review_result': None,
            'payload': None,
        }

    # ── Layer 2: AI 审稿 (只对英语语法卡启用, 其他学科跳过) ──
    review_result = None
    if is_eng and gemini_call_fn and api_key:
        review_result = review_teaching_quality(card, subject, gemini_call_fn, api_key, text_model)
        if not review_result['pass']:
            return {
                'pass': False,
                'stage': 'ai_review',
                'issues': review_result['issues'],
                'hard_result': hard_result,
                'review_result': review_result,
                'payload': None,
            }

    # ── Layer 3: 结构化 payload ──
    payload = build_structured_payload(card, subject, review_result)

    return {
        'pass': True,
        'stage': 'passed',
        'issues': [],
        'hard_result': hard_result,
        'review_result': review_result,
        'payload': payload,
    }
