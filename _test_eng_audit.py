"""英语卡片审核器 端到端测试"""
import sys
sys.path.insert(0, '.')

from english_card_auditor import (
    is_english_card, rule_audit_english, full_english_audit,
    format_english_audit, EnglishAuditResult,
    build_semantic_audit_prompt, parse_semantic_audit_response,
)

def test_is_english_card():
    assert is_english_card({'type': '词汇卡'}, '英语') == True
    assert is_english_card({'type': '方法卡'}, '数学') == False
    assert is_english_card({'type': '语法辨析卡'}, '') == True
    assert is_english_card({'type': '易混词陷阱卡'}, '数学') == True
    assert is_english_card({'type': '概念卡'}, '') == False
    print('[PASS] is_english_card')

def test_good_card():
    """测试一张合格的英语搭配卡"""
    card = {
        'card_id': '01-01',
        'full_id': '英语-三下-01-01',
        'title': 'make progress',
        'type': '搭配卡',
        'definition': 'make progress 意为取得进步',
        'core_points': [
            'make progress = 取得进步',
            'make a decision = 做决定',
        ],
        'mistakes': [
            {'wrong': 'I do progress every day.', 'correct': 'I make progress every day.',
             'reason': 'progress collocates with make, not do'}
        ],
        'memory_tip': 'progress用make',
        '_eng_key_phrase': 'make progress',
    }
    ocr_texts = [
        'make progress', '取得进步',
        'make a decision', '做决定',
        'I do progress every day.',
        'I make progress every day.',
        '❌', '✅',
        'progress用make',
    ]
    manifest = {'TITLE': 'make progress', 'SLOGAN': 'progress用make'}
    
    result = rule_audit_english(ocr_texts, card, manifest, eng_key_phrase='make progress')
    print(f'\n[Good Card] Score: {result.rule_score}/100, Verdict: {result.verdict}')
    print(f'  Dims: {result.dimension_scores}')
    for i in result.issues:
        print(f'  [{i.dimension}] {i.severity}: {i.description} (-{i.deduction})')
    assert result.verdict == 'pass', f'Expected pass, got {result.verdict}'
    assert result.rule_score >= 80
    print('[PASS] good card')

def test_bad_card():
    """测试一张有多种问题的卡"""
    card = {
        'card_id': '02-03',
        'full_id': '英语-六上-02-03',
        'title': '高频词汇',  # 纯中文标题=问题
        'type': '词汇卡',
        'definition': '学习重点词汇',
        'core_points': ['重点词汇要掌握'],  # 无英文
        'mistakes': [],
        'memory_tip': '搭配固定要多记',  # 万能废话
        '_eng_key_phrase': 'make progress',
    }
    ocr_texts = [
        '记住哦', '来看看', '加油哦',
        'grammer rules',  # 拼写错误
        '高频词汇',
    ]
    manifest = {'TITLE': '高频词汇', 'SLOGAN': '搭配固定要多记'}
    
    result = rule_audit_english(ocr_texts, card, manifest, eng_key_phrase='make progress')
    print(f'\n[Bad Card] Score: {result.rule_score}/100, Verdict: {result.verdict}')
    for i in result.issues:
        print(f'  [{i.dimension}] {i.severity}: {i.description} (-{i.deduction})')
    assert result.verdict in ('warn', 'fail'), f'Expected warn/fail, got {result.verdict}'
    assert result.rule_score < 70
    print('[PASS] bad card')

def test_grammar_typo():
    """测试语法术语渲染错误检测"""
    card = {
        'card_id': '03-01',
        'full_id': '英语-高一上-03-01',
        'title': 'that clause',
        'type': '语法辨析卡',
        'definition': 'that引导的从句',
        'core_points': ['appositive clause 同位语从句'],
        'mistakes': [],
        'memory_tip': 'that从句',
        '_eng_key_phrase': 'that clause',
    }
    ocr_texts = [
        'that clause',
        '应语从句',  # 错: 应为"同位语从句"
        'The news that he won is exciting.',
        '❌ The news he won is exciting.',
        '✅ The news that he won is exciting.',
    ]
    manifest = {'TITLE': 'that clause'}
    
    result = rule_audit_english(ocr_texts, card, manifest, eng_key_phrase='that clause')
    print(f'\n[Grammar Typo] Score: {result.rule_score}/100, Verdict: {result.verdict}')
    for i in result.issues:
        print(f'  [{i.dimension}] {i.severity}: {i.description} (-{i.deduction})')
    # 应检测到 "应语" → "同位语" 错误
    d2_issues = [i for i in result.issues if i.dimension == 'D2' and i.category == 'grammar_term_typo']
    assert len(d2_issues) >= 1, 'Expected grammar term typo detection'
    print('[PASS] grammar typo')

def test_empty_card():
    """测试完全空白的废卡"""
    card = {
        'card_id': '04-01',
        'full_id': '英语-三下-04-01',
        'title': 'hello',
        'type': '词汇卡',
        'definition': 'hello 你好',
        'core_points': [],
        'mistakes': [],
        'memory_tip': '',
        '_eng_key_phrase': 'hello',
    }
    ocr_texts = ['hi']  # 几乎空白
    manifest = {'TITLE': 'hello'}
    
    result = rule_audit_english(ocr_texts, card, manifest, eng_key_phrase='hello')
    print(f'\n[Empty Card] Score: {result.rule_score}/100, Verdict: {result.verdict}')
    for i in result.issues:
        print(f'  [{i.dimension}] {i.severity}: {i.description} (-{i.deduction})')
    print('[PASS] empty card')

def test_semantic_prompt():
    """测试语义层 prompt 构建"""
    card = {
        'type': '搭配卡',
        'grade': '六年级',
        '_eng_key_phrase': 'make progress',
    }
    prompt = build_semantic_audit_prompt(card, 'make progress')
    assert 'make progress' in prompt
    assert 'D3' in prompt
    assert 'D4' in prompt
    print('\n[PASS] semantic prompt build')

def test_semantic_parse():
    """测试语义层响应解析"""
    fake_resp = '''{
      "D3_teaching_correctness": {"score": 20, "issues": [], "comment": "good"},
      "D4_teaching_completeness": {"score": 18, "issues": ["缺少口诀"], "comment": "ok"},
      "D5_layout_hierarchy": {"score": 22, "issues": [], "comment": "clear"},
      "D6_visual_quality": {"score": 19, "issues": ["配色偏暗"], "comment": "decent"},
      "total": 79,
      "overall_comment": "overall decent"
    }'''
    dim_scores, issues = parse_semantic_audit_response(fake_resp)
    assert dim_scores.get('D3') == 20
    assert dim_scores.get('D4') == 18
    assert len(issues) == 2  # 缺少口诀 + 配色偏暗
    print('[PASS] semantic parse')

def test_format_report():
    """测试报告格式化"""
    result = EnglishAuditResult(
        card_id='英语-三下-01-01',
        rule_score=72,
        semantic_score=80,
        final_score=76,
        verdict='warn',
        dimension_scores={'D1': 20, 'D2': 18, 'D7': 22, 'D8': 12},
    )
    report = format_english_audit(result)
    assert '英语-三下-01-01' in report
    assert '72' in report
    print(f'\n{report}')
    print('[PASS] format report')

def test_pipeline_import():
    """测试 v3 pipeline 导入兼容性"""
    # 模拟 v3 中的导入
    from english_card_auditor import (
        is_english_card, rule_audit_english, full_english_audit,
        format_english_audit, EnglishAuditResult,
    )
    print('\n[PASS] pipeline import compatible')

if __name__ == '__main__':
    test_is_english_card()
    test_good_card()
    test_bad_card()
    test_grammar_typo()
    test_empty_card()
    test_semantic_prompt()
    test_semantic_parse()
    test_format_report()
    test_pipeline_import()
    print('\n✅ All tests passed!')
