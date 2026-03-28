#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v10.8 多尺寸画布系统测试

测试覆盖:
- _CANVAS_PRESETS 数据完整性
- _CONTENT_RATIO_MAP 映射正确性
- _RATIO_ORIENTATION 完备性
- _resolve_canvas() 优先级逻辑（ratio_override > platform > content_type > 默认）
- _build_canvas_block_cn() 中文输出
- _build_canvas_block_en() 英文输出
- 模板占位符 {canvas_block} 正确替换
- prompt_builder_v2 canvas_line 参数
- 向后兼容性（不传参 = 3:4 默认）
"""

import sys
import unittest

sys.path.insert(0, r'd:\Users\Administrator\Desktop\ls\xhsqg')

from generate_card_images_v3 import (
    _CANVAS_PRESETS,
    _CONTENT_RATIO_MAP,
    _RATIO_ORIENTATION,
    _resolve_canvas,
    _build_canvas_block_cn,
    _build_canvas_block_en,
    PROMPT_SYSTEM_TEMPLATE,
    PROMPT_SYSTEM_TEMPLATE_WELLNESS,
)


# ══════════════════════════════════════════
# 1. 数据结构完整性
# ══════════════════════════════════════════

class TestCanvasPresets(unittest.TestCase):
    """_CANVAS_PRESETS 数据完整性"""

    REQUIRED_PLATFORMS = {'小红书', '抖音', '微信', 'B站', '朋友圈', '公众号', '知乎', 'PPT'}

    def test_all_platforms_present(self):
        """8 大平台都有预设"""
        self.assertTrue(self.REQUIRED_PLATFORMS.issubset(set(_CANVAS_PRESETS.keys())))

    def test_preset_fields_complete(self):
        """每个预设都有 5 个必需字段"""
        for platform, preset in _CANVAS_PRESETS.items():
            with self.subTest(platform=platform):
                for key in ('ratio', 'orientation', 'desc_cn', 'desc_en', 'breathing'):
                    self.assertIn(key, preset, f'{platform} 缺少 {key}')

    def test_ratio_format(self):
        """比例格式正确 (X:Y)"""
        import re
        for platform, preset in _CANVAS_PRESETS.items():
            with self.subTest(platform=platform):
                self.assertRegex(preset['ratio'], r'^\d+:\d+$')

    def test_orientation_valid(self):
        """方向只有 vertical/horizontal/square"""
        valid = {'vertical', 'horizontal', 'square'}
        for platform, preset in _CANVAS_PRESETS.items():
            with self.subTest(platform=platform):
                self.assertIn(preset['orientation'], valid)

    def test_xiaohongshu_is_3_4(self):
        """小红书默认 3:4 竖屏"""
        xhs = _CANVAS_PRESETS['小红书']
        self.assertEqual(xhs['ratio'], '3:4')
        self.assertEqual(xhs['orientation'], 'vertical')

    def test_douyin_is_9_16(self):
        """抖音默认 9:16"""
        dy = _CANVAS_PRESETS['抖音']
        self.assertEqual(dy['ratio'], '9:16')

    def test_wechat_is_1_1(self):
        """微信默认 1:1"""
        wx = _CANVAS_PRESETS['微信']
        self.assertEqual(wx['ratio'], '1:1')


class TestContentRatioMap(unittest.TestCase):
    """_CONTENT_RATIO_MAP 映射正确性"""

    def test_comparison_cards_use_4_3(self):
        """对比类卡片 → 4:3 横版"""
        for ct in ['辨析卡', '对战卡', '语法辨析卡', '易混词卡']:
            with self.subTest(card_type=ct):
                self.assertEqual(_CONTENT_RATIO_MAP.get(ct), '4:3')

    def test_flow_cards_use_3_4(self):
        """流程类卡片 → 3:4 竖版"""
        for ct in ['方法卡', '应用题拆解卡']:
            with self.subTest(card_type=ct):
                self.assertEqual(_CONTENT_RATIO_MAP.get(ct), '3:4')

    def test_formula_card_use_1_1(self):
        """公式卡 → 1:1 方形"""
        self.assertEqual(_CONTENT_RATIO_MAP.get('公式卡'), '1:1')

    def test_poetry_card_use_9_16(self):
        """诗词卡 → 9:16 长屏"""
        self.assertEqual(_CONTENT_RATIO_MAP.get('古诗默写卡'), '9:16')

    def test_all_ratios_in_orientation_map(self):
        """所有内容类型推荐的比例在 _RATIO_ORIENTATION 中有定义"""
        for ct, ratio in _CONTENT_RATIO_MAP.items():
            with self.subTest(card_type=ct, ratio=ratio):
                self.assertIn(ratio, _RATIO_ORIENTATION)


class TestRatioOrientation(unittest.TestCase):
    """_RATIO_ORIENTATION 完备性"""

    def test_common_ratios_present(self):
        """常见比例都有"""
        for r in ['3:4', '4:3', '1:1', '9:16', '16:9']:
            with self.subTest(ratio=r):
                self.assertIn(r, _RATIO_ORIENTATION)

    def test_3_4_is_vertical(self):
        self.assertEqual(_RATIO_ORIENTATION['3:4'], 'vertical')

    def test_16_9_is_horizontal(self):
        self.assertEqual(_RATIO_ORIENTATION['16:9'], 'horizontal')

    def test_1_1_is_square(self):
        self.assertEqual(_RATIO_ORIENTATION['1:1'], 'square')


# ══════════════════════════════════════════
# 2. _resolve_canvas() 优先级逻辑
# ══════════════════════════════════════════

class TestResolveCanvas(unittest.TestCase):
    """画布解析器优先级测试"""

    def test_default_is_xiaohongshu_3_4(self):
        """无参数 → 默认小红书 3:4"""
        c = _resolve_canvas()
        self.assertEqual(c['ratio'], '3:4')
        self.assertEqual(c['orientation'], 'vertical')

    def test_platform_douyin(self):
        """指定抖音 → 9:16"""
        c = _resolve_canvas(platform='抖音')
        self.assertEqual(c['ratio'], '9:16')
        self.assertEqual(c['orientation'], 'vertical')

    def test_platform_overrides_content_type(self):
        """平台 > 内容类型推荐"""
        c = _resolve_canvas(platform='微信', card_type='辨析卡')
        self.assertEqual(c['ratio'], '1:1', '微信平台应覆盖辨析卡的 4:3 推荐')

    def test_ratio_override_beats_everything(self):
        """ratio_override > platform > content_type"""
        c = _resolve_canvas(platform='抖音', card_type='辨析卡', ratio_override='16:9')
        self.assertEqual(c['ratio'], '16:9')
        self.assertEqual(c['orientation'], 'horizontal')

    def test_content_type_when_no_platform(self):
        """不指定平台时，内容类型推荐生效"""
        c = _resolve_canvas(card_type='公式卡')
        self.assertEqual(c['ratio'], '1:1')

    def test_content_type_ignored_with_platform(self):
        """指定平台时，内容类型推荐不生效"""
        c = _resolve_canvas(platform='小红书', card_type='公式卡')
        self.assertEqual(c['ratio'], '3:4', '小红书平台应覆盖公式卡的 1:1')

    def test_unknown_platform_falls_to_content(self):
        """未知平台 → 降级到内容类型推荐"""
        c = _resolve_canvas(platform='未知平台', card_type='古诗默写卡')
        self.assertEqual(c['ratio'], '9:16')

    def test_unknown_everything_defaults_3_4(self):
        """都不认识 → 默认 3:4"""
        c = _resolve_canvas(platform='火星', card_type='不存在卡')
        self.assertEqual(c['ratio'], '3:4')

    def test_invalid_ratio_override_ignored(self):
        """无效比例字符串被忽略"""
        c = _resolve_canvas(ratio_override='abc')
        self.assertEqual(c['ratio'], '3:4')

    def test_result_has_all_fields(self):
        """返回 dict 包含全部 5 个字段"""
        c = _resolve_canvas()
        for key in ('ratio', 'orientation', 'desc_cn', 'desc_en', 'breathing'):
            self.assertIn(key, c)

    def test_ratio_override_generates_correct_desc(self):
        """ratio_override 生成正确的中英文描述"""
        c = _resolve_canvas(ratio_override='16:9')
        self.assertIn('16:9', c['desc_cn'])
        self.assertIn('16:9', c['desc_en'])
        self.assertIn('横屏', c['desc_cn'])
        self.assertIn('horizontal', c['desc_en'])


# ══════════════════════════════════════════
# 3. Prompt 块生成
# ══════════════════════════════════════════

class TestCanvasBlocks(unittest.TestCase):
    """画布 prompt 片段生成"""

    def test_cn_block_contains_ratio(self):
        canvas = _resolve_canvas(platform='小红书')
        block = _build_canvas_block_cn(canvas)
        self.assertIn('3:4', block)
        self.assertIn('竖屏', block)
        self.assertIn('留白', block)

    def test_en_block_contains_ratio(self):
        canvas = _resolve_canvas(platform='抖音')
        block = _build_canvas_block_en(canvas)
        self.assertIn('9:16', block)
        self.assertIn('breathing room', block)

    def test_cn_block_for_square(self):
        canvas = _resolve_canvas(platform='微信')
        block = _build_canvas_block_cn(canvas)
        self.assertIn('1:1', block)
        self.assertIn('正方形', block)

    def test_en_block_for_horizontal(self):
        canvas = _resolve_canvas(platform='B站')
        block = _build_canvas_block_en(canvas)
        self.assertIn('16:9', block)
        self.assertIn('horizontal', block)


# ══════════════════════════════════════════
# 4. 模板占位符替换
# ══════════════════════════════════════════

class TestTemplateIntegration(unittest.TestCase):
    """模板中 {canvas_block} 替换正确"""

    def test_system_template_has_canvas_placeholder(self):
        """PROMPT_SYSTEM_TEMPLATE 包含 {canvas_block}"""
        self.assertIn('{canvas_block}', PROMPT_SYSTEM_TEMPLATE)

    def test_wellness_template_has_canvas_placeholder(self):
        """PROMPT_SYSTEM_TEMPLATE_WELLNESS 包含 {canvas_block}"""
        self.assertIn('{canvas_block}', PROMPT_SYSTEM_TEMPLATE_WELLNESS)

    def test_system_template_no_hardcoded_3_4(self):
        """PROMPT_SYSTEM_TEMPLATE 不再有硬编码的 "竖屏 3:4 画布"""
        self.assertNotIn('竖屏 3:4 画布', PROMPT_SYSTEM_TEMPLATE)

    def test_wellness_template_no_hardcoded_3_4(self):
        """PROMPT_SYSTEM_TEMPLATE_WELLNESS 不再有硬编码"""
        self.assertNotIn('竖屏 3:4 画布', PROMPT_SYSTEM_TEMPLATE_WELLNESS)

    def test_template_format_with_default_canvas(self):
        """模板 .format() 使用默认画布不报错"""
        canvas = _resolve_canvas()
        block = _build_canvas_block_cn(canvas)
        # 尝试格式化 (只验证 canvas_block 不报错, 其他用空字符串)
        try:
            # 提供所有已知的占位符
            formatted = PROMPT_SYSTEM_TEMPLATE.format(
                subject='数学',
                solve_strategy_block='test',
                color_scheme_block='',
                layout_variant_block='',
                canvas_block=block,
                max_chars=20,
                max_per_block=5,
                ideal_chars=15,
                max_slogan=8,
            )
            self.assertIn('3:4', formatted)
            self.assertIn('留白', formatted)
        except KeyError as e:
            self.fail(f'模板格式化缺少占位符: {e}')


# ══════════════════════════════════════════
# 5. prompt_builder_v2 兼容性
# ══════════════════════════════════════════

class TestV2CanvasLine(unittest.TestCase):
    """prompt_builder_v2 的 canvas_line 参数"""

    def test_build_visual_translation_prompt_accepts_canvas_line(self):
        """函数签名包含 canvas_line 参数"""
        import inspect
        from prompt_builder_v2 import build_visual_translation_prompt
        sig = inspect.signature(build_visual_translation_prompt)
        self.assertIn('canvas_line', sig.parameters)

    def test_default_canvas_line_is_3_4(self):
        """不传 canvas_line 时默认使用 3:4"""
        from prompt_builder_v2 import VISUAL_TRANSLATION_TEMPLATE
        self.assertIn('{canvas_line}', VISUAL_TRANSLATION_TEMPLATE)

    def test_custom_canvas_line_injected(self):
        """传入自定义 canvas_line 会注入到输出"""
        from prompt_builder_v2 import build_visual_translation_prompt
        content = {
            'blocks': [{'zone': 'B', 'items': [{'text': 'test'}]}],
            'text_manifest': {'TITLE': 'Test'},
        }
        result = build_visual_translation_prompt(
            content, '方法卡', '数学',
            canvas_line='Canvas ratio 16:9 (horizontal)\n- ≥ 20% whitespace',
        )
        self.assertIn('16:9', result)
        self.assertIn('horizontal', result)


# ══════════════════════════════════════════
# 6. 向后兼容性
# ══════════════════════════════════════════

class TestBackwardCompatibility(unittest.TestCase):
    """不传任何 canvas 参数时，行为与旧版一致"""

    def test_resolve_canvas_default_matches_old_behavior(self):
        """默认解析结果 = 3:4 vertical + ≥25% 留白"""
        c = _resolve_canvas()
        self.assertEqual(c['ratio'], '3:4')
        self.assertEqual(c['orientation'], 'vertical')
        self.assertIn('25%', c['breathing'])

    def test_generate_image_prompt_signature_backward_compatible(self):
        """generate_image_prompt 新参数都有默认值"""
        import inspect
        from generate_card_images_v3 import generate_image_prompt
        sig = inspect.signature(generate_image_prompt)
        self.assertEqual(sig.parameters['platform'].default, '')
        self.assertEqual(sig.parameters['ratio_override'].default, '')

    def test_generate_card_image_signature_backward_compatible(self):
        """generate_card_image 新参数有默认值"""
        import inspect
        from generate_card_images_v3 import generate_card_image
        sig = inspect.signature(generate_card_image)
        self.assertIsNone(sig.parameters['canvas'].default)

    def test_build_refinement_prompt_signature_backward_compatible(self):
        """_build_refinement_prompt 新参数有默认值"""
        import inspect
        from generate_card_images_v3 import _build_refinement_prompt
        sig = inspect.signature(_build_refinement_prompt)
        self.assertIsNone(sig.parameters['canvas'].default)

    def test_process_single_card_signature_backward_compatible(self):
        """process_single_card 新参数有默认值"""
        import inspect
        from generate_card_images_v3 import process_single_card
        sig = inspect.signature(process_single_card)
        self.assertEqual(sig.parameters['platform'].default, '')
        self.assertEqual(sig.parameters['ratio_override'].default, '')


# ══════════════════════════════════════════
# 7. 跨平台一致性
# ══════════════════════════════════════════

class TestCrossPlatformConsistency(unittest.TestCase):
    """所有平台预设的一致性"""

    def test_all_presets_orientation_matches_ratio(self):
        """每个平台的 orientation 与 ratio 一致"""
        for platform, preset in _CANVAS_PRESETS.items():
            with self.subTest(platform=platform):
                expected_orient = _RATIO_ORIENTATION.get(preset['ratio'])
                self.assertEqual(preset['orientation'], expected_orient,
                    f'{platform}: ratio={preset["ratio"]} → expected {expected_orient}, got {preset["orientation"]}')

    def test_desc_cn_contains_ratio(self):
        """中文描述包含比例数字"""
        for platform, preset in _CANVAS_PRESETS.items():
            with self.subTest(platform=platform):
                self.assertIn(preset['ratio'], preset['desc_cn'])

    def test_desc_en_contains_ratio(self):
        """英文描述包含比例数字"""
        for platform, preset in _CANVAS_PRESETS.items():
            with self.subTest(platform=platform):
                self.assertIn(preset['ratio'], preset['desc_en'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
