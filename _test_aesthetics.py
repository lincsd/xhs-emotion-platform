#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v10.7 审美升级测试 — 学科配色系统 + 布局多样化

测试覆盖:
- _SUBJECT_COLOR_SCHEMES 数据完整性
- _LAYOUT_VARIANTS 数据完整性
- _CARD_TYPE_LAYOUT_MAP 映射正确性
- _get_subject_color_scheme() 精确+模糊匹配
- _build_color_scheme_block() 输出格式
- _get_layout_variant() 路由逻辑
- _build_layout_block() 输出格式
- _build_color_scheme_for_v2() 英文输出
- _build_layout_hint_for_v2() 英文输出
- PROMPT_SYSTEM_TEMPLATE 占位符替换
- prompt_builder_v2 签名兼容
"""

import sys
import unittest

sys.path.insert(0, r'd:\Users\Administrator\Desktop\ls\xhsqg')

from generate_card_images_v3 import (
    _SUBJECT_COLOR_SCHEMES,
    _LAYOUT_VARIANTS,
    _CARD_TYPE_LAYOUT_MAP,
    _get_subject_color_scheme,
    _build_color_scheme_block,
    _get_layout_variant,
    _build_layout_block,
    _build_color_scheme_for_v2,
    _build_layout_hint_for_v2,
    PROMPT_SYSTEM_TEMPLATE,
    PROMPT_SYSTEM_TEMPLATE_WELLNESS,
)


class TestSubjectColorSchemes(unittest.TestCase):
    """学科配色系统数据完整性"""

    def test_all_core_subjects_have_color_scheme(self):
        """9 大学科 + 养生/减脂 都有配色方案"""
        expected = {'数学', '英语', '语文', '物理', '化学', '生物', '历史', '地理', '政治', '养生', '减脂'}
        self.assertTrue(expected.issubset(set(_SUBJECT_COLOR_SCHEMES.keys())))

    def test_color_scheme_fields_complete(self):
        """每个配色方案都有 5 个必需字段"""
        required_keys = {'name', 'banner_gradient', 'accent_strip', 'content_bg', 'highlight', 'description'}
        for subject, scheme in _SUBJECT_COLOR_SCHEMES.items():
            for key in required_keys:
                self.assertIn(key, scheme, f'{subject} 缺少字段 {key}')
                self.assertTrue(len(scheme[key]) > 0, f'{subject}.{key} 不能为空')

    def test_color_schemes_have_hex_codes(self):
        """配色方案应包含 hex 色值"""
        for subject, scheme in _SUBJECT_COLOR_SCHEMES.items():
            self.assertIn('#', scheme['banner_gradient'], f'{subject} banner_gradient 无 hex')
            self.assertIn('#', scheme['content_bg'], f'{subject} content_bg 无 hex')

    def test_each_subject_unique_name(self):
        """每个学科的配色名称不重复"""
        names = [s['name'] for s in _SUBJECT_COLOR_SCHEMES.values()]
        self.assertEqual(len(names), len(set(names)), '配色名称有重复')


class TestGetSubjectColorScheme(unittest.TestCase):
    """_get_subject_color_scheme 精确+模糊匹配"""

    def test_exact_match(self):
        """精确匹配"""
        cs = _get_subject_color_scheme('数学')
        self.assertIsNotNone(cs)
        self.assertEqual(cs['name'], '理性蓝')

    def test_exact_match_all_subjects(self):
        """所有核心学科精确匹配"""
        for subj in ['数学', '英语', '语文', '物理', '化学', '生物', '历史', '地理', '政治']:
            cs = _get_subject_color_scheme(subj)
            self.assertIsNotNone(cs, f'{subj} 无配色')

    def test_fuzzy_match(self):
        """模糊匹配: '养生减脂' 匹配到 '养生'"""
        cs = _get_subject_color_scheme('养生减脂')
        self.assertIsNotNone(cs)

    def test_unknown_subject_returns_none(self):
        """未知学科返回 None"""
        cs = _get_subject_color_scheme('烹饪')
        self.assertIsNone(cs)


class TestBuildColorSchemeBlock(unittest.TestCase):
    """_build_color_scheme_block 输出格式"""

    def test_known_subject_generates_branded_block(self):
        """已知学科生成品牌配色区块"""
        block = _build_color_scheme_block('物理')
        self.assertIn('科技银蓝', block)
        self.assertIn('物理', block)
        self.assertIn('Banner', block)
        self.assertIn('#0d47a1', block)

    def test_unknown_subject_generates_generic_block(self):
        """未知学科生成通用配色区块"""
        block = _build_color_scheme_block('烹饪')
        self.assertIn('珊瑚粉', block)  # 通用配色选择
        self.assertIn('Banner', block)

    def test_block_has_all_sections(self):
        """配色区块包含所有必需部分"""
        for subj in ['数学', '英语', '语文']:
            block = _build_color_scheme_block(subj)
            self.assertIn('Banner', block)
            self.assertIn('内容卡', block)
            self.assertIn('口诀条', block)


class TestLayoutVariants(unittest.TestCase):
    """布局变体数据完整性"""

    def test_all_layout_types_exist(self):
        """6 种布局变体都存在"""
        expected = {'standard', 'comparison', 'flow', 'concept_map', 'formula_hero', 'poetry'}
        self.assertEqual(expected, set(_LAYOUT_VARIANTS.keys()))

    def test_layout_has_required_fields(self):
        """每个布局变体有 name 和 prompt_block"""
        for key, layout in _LAYOUT_VARIANTS.items():
            self.assertIn('name', layout, f'{key} 缺少 name')
            self.assertIn('prompt_block', layout, f'{key} 缺少 prompt_block')
            self.assertTrue(len(layout['prompt_block']) > 50, f'{key} prompt_block 太短')

    def test_all_layouts_have_4_zones(self):
        """每个布局都有 A/B/C/D 四个区块"""
        for key, layout in _LAYOUT_VARIANTS.items():
            block = layout['prompt_block']
            self.assertIn('区块A', block, f'{key} 缺少区块A')
            self.assertIn('区块B', block, f'{key} 缺少区块B (或变体)')
            self.assertIn('区块C', block, f'{key} 缺少区块C')
            self.assertIn('区块D', block, f'{key} 缺少区块D')

    def test_comparison_layout_has_left_right(self):
        """对比式布局有左右栏"""
        block = _LAYOUT_VARIANTS['comparison']['prompt_block']
        self.assertIn('左栏', block)
        self.assertIn('右栏', block)
        self.assertIn('❌', block)
        self.assertIn('✅', block)

    def test_flow_layout_has_steps(self):
        """流程式布局有步骤和箭头"""
        block = _LAYOUT_VARIANTS['flow']['prompt_block']
        self.assertIn('箭头', block)
        self.assertIn('步骤', block)

    def test_concept_map_layout_has_branches(self):
        """思维导图式有分支"""
        block = _LAYOUT_VARIANTS['concept_map']['prompt_block']
        self.assertIn('分支', block)
        self.assertIn('中心', block)

    def test_formula_hero_layout_has_formula(self):
        """公式突出式有公式展示"""
        block = _LAYOUT_VARIANTS['formula_hero']['prompt_block']
        self.assertIn('公式', block)
        self.assertIn('超大', block)

    def test_poetry_layout_has_ink_style(self):
        """诗意水墨式有中国风元素"""
        block = _LAYOUT_VARIANTS['poetry']['prompt_block']
        self.assertIn('宣纸', block)
        self.assertIn('书法', block)


class TestCardTypeLayoutMap(unittest.TestCase):
    """卡片类型 → 布局映射"""

    def test_comparison_types_map_correctly(self):
        """对比类卡片映射到 comparison"""
        comparison_types = ['辨析卡', '速算卡', '语法辨析卡', '易混词卡', '判断火眼卡']
        for ct in comparison_types:
            self.assertEqual(_CARD_TYPE_LAYOUT_MAP.get(ct), 'comparison', f'{ct} 应映射到 comparison')

    def test_flow_types_map_correctly(self):
        """流程类卡片映射到 flow"""
        flow_types = ['方法卡', '应用题拆解卡', '计算零失误卡']
        for ct in flow_types:
            self.assertEqual(_CARD_TYPE_LAYOUT_MAP.get(ct), 'flow', f'{ct} 应映射到 flow')

    def test_concept_types_map_correctly(self):
        """概念类卡片映射到 concept_map"""
        concept_types = ['概念卡', '思维卡', '知识总结卡']
        for ct in concept_types:
            self.assertEqual(_CARD_TYPE_LAYOUT_MAP.get(ct), 'concept_map', f'{ct} 应映射到 concept_map')

    def test_formula_type_maps_correctly(self):
        self.assertEqual(_CARD_TYPE_LAYOUT_MAP.get('公式卡'), 'formula_hero')

    def test_poetry_type_maps_correctly(self):
        self.assertEqual(_CARD_TYPE_LAYOUT_MAP.get('古诗默写卡'), 'poetry')

    def test_unmapped_types_get_standard(self):
        """未映射的卡片类型默认 standard"""
        for ct in ['生活卡', '挑战卡', '恋爱心理卡']:
            layout = _get_layout_variant(ct, '数学')
            self.assertEqual(layout['name'], '标准四区', f'{ct} 应默认标准四区')


class TestGetLayoutVariant(unittest.TestCase):
    """_get_layout_variant 路由逻辑"""

    def test_comparison_card_gets_comparison_layout(self):
        layout = _get_layout_variant('辨析卡', '数学')
        self.assertEqual(layout['name'], '左右对比式')

    def test_method_card_gets_flow_layout(self):
        layout = _get_layout_variant('方法卡', '数学')
        self.assertEqual(layout['name'], '步骤流程式')

    def test_concept_card_gets_concept_map(self):
        layout = _get_layout_variant('概念卡', '物理')
        self.assertEqual(layout['name'], '思维导图式')

    def test_formula_card_gets_formula_hero(self):
        layout = _get_layout_variant('公式卡', '数学')
        self.assertEqual(layout['name'], '公式突出式')

    def test_yuwen_poetry_gets_poetry_layout(self):
        layout = _get_layout_variant('古诗默写卡', '语文')
        self.assertEqual(layout['name'], '诗意水墨式')

    def test_unknown_card_type_gets_standard(self):
        layout = _get_layout_variant('随便什么卡', '数学')
        self.assertEqual(layout['name'], '标准四区')


class TestBuildLayoutBlock(unittest.TestCase):
    """_build_layout_block 输出"""

    def test_returns_string_for_all_types(self):
        for ct in ['方法卡', '辨析卡', '概念卡', '公式卡', '古诗默写卡', '生活卡']:
            block = _build_layout_block(ct, '数学')
            self.assertIsInstance(block, str)
            self.assertIn('区块A', block)


class TestV2ColorLayoutHints(unittest.TestCase):
    """v2 路径的英文配色/布局提示"""

    def test_color_hint_for_known_subject(self):
        hint = _build_color_scheme_for_v2('化学')
        self.assertIn('Subject color scheme', hint)
        self.assertIn('Banner', hint)
        self.assertIn('#4a148c', hint)

    def test_color_hint_for_unknown_subject_empty(self):
        hint = _build_color_scheme_for_v2('烹饪')
        self.assertEqual(hint, '')

    def test_layout_hint_for_non_standard(self):
        hint = _build_layout_hint_for_v2('辨析卡', '数学')
        self.assertIn('Layout variant', hint)
        self.assertIn('左右对比', hint)

    def test_layout_hint_for_standard_empty(self):
        hint = _build_layout_hint_for_v2('生活卡', '数学')
        self.assertEqual(hint, '')


class TestTemplateFormatting(unittest.TestCase):
    """模板能正确格式化"""

    def test_main_template_accepts_new_placeholders(self):
        """PROMPT_SYSTEM_TEMPLATE 能接受 color_scheme_block 和 layout_variant_block"""
        result = PROMPT_SYSTEM_TEMPLATE.format(
            subject='数学',
            solve_strategy_block='test strategy',
            color_scheme_block='COLOR BLOCK HERE',
            layout_variant_block='LAYOUT BLOCK HERE',
            canvas_block='CANVAS BLOCK HERE',
        )
        self.assertIn('COLOR BLOCK HERE', result)
        self.assertIn('LAYOUT BLOCK HERE', result)
        self.assertIn('数学', result)

    def test_wellness_template_accepts_new_placeholders(self):
        """PROMPT_SYSTEM_TEMPLATE_WELLNESS 也接受新占位符"""
        result = PROMPT_SYSTEM_TEMPLATE_WELLNESS.format(
            subject='养生',
            visual_strategy_block='test strategy',
            color_scheme_block='COLOR BLOCK HERE',
            layout_variant_block='LAYOUT BLOCK HERE',
            canvas_block='CANVAS BLOCK HERE',
        )
        self.assertIn('COLOR BLOCK HERE', result)
        self.assertIn('LAYOUT BLOCK HERE', result)

    def test_end_to_end_format_math(self):
        """端到端: 数学卡片完整格式化"""
        color_block = _build_color_scheme_block('数学')
        layout_block = _build_layout_block('方法卡', '数学')
        result = PROMPT_SYSTEM_TEMPLATE.format(
            subject='数学',
            solve_strategy_block='步骤分解',
            color_scheme_block=color_block,
            layout_variant_block=layout_block,
            canvas_block='- 竖屏 3:4 画布\n- ≥ 25% 留白',
        )
        self.assertIn('理性蓝', result)
        self.assertIn('步骤流程', result)
        self.assertNotIn('{color_scheme_block}', result)
        self.assertNotIn('{layout_variant_block}', result)

    def test_end_to_end_format_yuwen_poetry(self):
        """端到端: 语文古诗卡片完整格式化"""
        color_block = _build_color_scheme_block('语文')
        layout_block = _build_layout_block('古诗默写卡', '语文')
        result = PROMPT_SYSTEM_TEMPLATE.format(
            subject='语文',
            solve_strategy_block='诗词鉴赏',
            color_scheme_block=color_block,
            layout_variant_block=layout_block,
            canvas_block='- 竖屏 3:4 画布\n- ≥ 25% 留白',
        )
        self.assertIn('古韵棕', result)
        self.assertIn('宣纸', result)
        self.assertIn('书法', result)

    def test_end_to_end_format_english(self):
        """端到端: 英语辨析卡完整格式化"""
        color_block = _build_color_scheme_block('英语')
        layout_block = _build_layout_block('语法辨析卡', '英语')
        result = PROMPT_SYSTEM_TEMPLATE.format(
            subject='英语',
            solve_strategy_block='语法对比',
            color_scheme_block=color_block,
            layout_variant_block=layout_block,
            canvas_block='- 竖屏 3:4 画布\n- ≥ 25% 留白',
        )
        self.assertIn('活力橙', result)
        self.assertIn('左栏', result)
        self.assertIn('右栏', result)


class TestPromptBuilderV2Compat(unittest.TestCase):
    """prompt_builder_v2 签名兼容性"""

    def test_build_visual_translation_prompt_accepts_new_params(self):
        """build_visual_translation_prompt 接受 extra_color_hint 和 extra_layout_hint"""
        from prompt_builder_v2 import build_visual_translation_prompt
        import inspect
        sig = inspect.signature(build_visual_translation_prompt)
        params = list(sig.parameters.keys())
        self.assertIn('extra_color_hint', params)
        self.assertIn('extra_layout_hint', params)

    def test_build_visual_translation_prompt_default_compat(self):
        """不传新参数也能正常工作（向后兼容）"""
        from prompt_builder_v2 import build_visual_translation_prompt
        mock_decision = {
            'blocks': [{'id': 'TITLE', 'text': '测试'}],
            'text_manifest': {'TITLE': '测试', 'SLOGAN': '口诀'},
        }
        # 不传 extra_color_hint 和 extra_layout_hint
        result = build_visual_translation_prompt(mock_decision, '方法卡', '数学')
        self.assertIn('TITLE', result)

    def test_build_visual_translation_prompt_with_hints(self):
        """传入新参数后内容包含提示"""
        from prompt_builder_v2 import build_visual_translation_prompt
        mock_decision = {
            'blocks': [{'id': 'TITLE', 'text': '测试'}],
            'text_manifest': {'TITLE': '测试', 'SLOGAN': '口诀'},
        }
        color_hint = _build_color_scheme_for_v2('数学')
        layout_hint = _build_layout_hint_for_v2('方法卡', '数学')
        result = build_visual_translation_prompt(
            mock_decision, '方法卡', '数学',
            extra_color_hint=color_hint,
            extra_layout_hint=layout_hint,
        )
        self.assertIn('#1a237e', result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
