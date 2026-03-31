"""
local_ocr.py — 本地 RapidOCR 交叉验证模块
=============================================
在 Gemini ocr_audit 之后运行, 用独立 OCR 引擎客观识别图片文字,
与 manifest 期望文字逐条比对, 给出交叉验证分数。

特点:
  - 零 API 费用 (本地 CPU 运行)
  - 速度 <2s/张
  - 与 Gemini 自审互相独立, 避免"自己批改自己"偏差

集成方式:
  在 ocr_audit() 返回后调用 cross_validate():
    cv_result = cross_validate(image_data, manifest)
    # cv_result = {'hit_rate': 0.8, 'matched': [...], 'missed': [...], ...}
  
  结合 Gemini 分数做最终判定:
    - 两者一致: 可信
    - Gemini 高 + OCR 低: Gemini 可能误判 (文字其实有问题)
    - Gemini 低 + OCR 高: Gemini 可能误判 (文字其实没问题, 可跳过重生成)
"""

import os
import io
import re
import time
from difflib import SequenceMatcher

# ── 延迟加载 PaddleOCR (首次调用时初始化, 约 2-3s) ──
_ocr_instance = None
_ocr_init_failed = False


def _get_ocr():
    """延迟初始化 RapidOCR 实例 (单例)"""
    global _ocr_instance, _ocr_init_failed
    if _ocr_init_failed:
        return None
    if _ocr_instance is not None:
        return _ocr_instance
    try:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_instance = RapidOCR()
        print('[local_ocr] RapidOCR 初始化成功', flush=True)
        return _ocr_instance
    except Exception as e:
        print(f'[local_ocr] RapidOCR 初始化失败: {e}', flush=True)
        _ocr_init_failed = True
        return None


def _extract_texts_from_image(image_data: bytes) -> list[str]:
    """用 RapidOCR 从图片字节提取所有文字行"""
    ocr = _get_ocr()
    if ocr is None:
        return []

    try:
        import numpy as np
        from PIL import Image

        img = Image.open(io.BytesIO(image_data)).convert('RGB')
        img_array = np.array(img)

        result, elapse = ocr(img_array)
        texts = []
        if result:
            for line in result:
                # RapidOCR returns: [box, text, confidence]
                text = line[1] if len(line) >= 2 else ''
                confidence = float(line[2]) if len(line) >= 3 else 0
                if text.strip() and confidence > 0.3:
                    texts.append(text.strip())
        return texts
    except Exception as e:
        print(f'[local_ocr] OCR 识别失败: {e}', flush=True)
        return []


def _normalize(text: str) -> str:
    """规范化文字用于比较: 去空格/标点, 统一全半角"""
    # 去空格
    t = re.sub(r'\s+', '', text)
    # 全角→半角 数字和字母
    result = []
    for c in t:
        code = ord(c)
        if 0xFF01 <= code <= 0xFF5E:  # 全角 ! ~ ~
            result.append(chr(code - 0xFEE0))
        elif code == 0x3000:  # 全角空格
            continue
        else:
            result.append(c)
    return ''.join(result).lower()


def _similarity(a: str, b: str) -> float:
    """计算两个字符串的相似度 (0~1)"""
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def _best_match(expected: str, ocr_texts: list[str]) -> tuple[float, str]:
    """在 OCR 结果中找与 expected 最相似的文字, 返回 (相似度, 匹配文字)"""
    best_sim = 0.0
    best_text = ''
    norm_exp = _normalize(expected)

    for t in ocr_texts:
        # 完整匹配
        sim = _similarity(expected, t)
        if sim > best_sim:
            best_sim = sim
            best_text = t

        # 子串匹配: manifest 值可能是 OCR 行的一部分
        norm_t = _normalize(t)
        if len(norm_exp) >= 2 and norm_exp in norm_t:
            best_sim = max(best_sim, 0.95)  # 包含关系视为高匹配
            best_text = t

        # 反向: OCR 行可能是 manifest 的一部分 (截断)
        if len(norm_t) >= 2 and norm_t in norm_exp:
            ratio = len(norm_t) / len(norm_exp)
            if ratio > best_sim:
                best_sim = ratio
                best_text = t

    return best_sim, best_text


def cross_validate(image_data: bytes, expected_manifest: dict,
                   threshold: float = 0.7) -> dict:
    """
    核心函数: 用本地 OCR 交叉验证 manifest 文字。
    
    Args:
        image_data: 图片二进制数据
        expected_manifest: {位置key: 期望文字} 字典
        threshold: 相似度阈值, >=threshold 视为匹配成功
    
    Returns:
        {
            'available': bool,       # PaddleOCR 是否可用
            'hit_rate': float,       # 命中率 (0~1)
            'hit_count': int,        # 命中数
            'total_count': int,      # 总检查数
            'matched': [...],        # 匹配成功列表
            'missed': [...],         # 匹配失败列表
            'ocr_texts': [...],      # OCR 提取的原始文字
            'elapsed_ms': int,       # 耗时 (毫秒)
            'cross_score': int,      # 交叉验证分数 (0~100)
        }
    """
    if not expected_manifest:
        return {
            'available': True, 'hit_rate': 1.0, 'hit_count': 0, 'total_count': 0,
            'matched': [], 'missed': [], 'ocr_texts': [],
            'elapsed_ms': 0, 'cross_score': 100,
        }

    t0 = time.time()

    # Step 1: OCR 识别
    ocr_texts = _extract_texts_from_image(image_data)
    if not ocr_texts:
        elapsed = int((time.time() - t0) * 1000)
        return {
            'available': _ocr_instance is not None,
            'hit_rate': 0.0, 'hit_count': 0, 'total_count': len(expected_manifest),
            'matched': [],
            'missed': [{'key': k, 'expected': v, 'ocr_best': '', 'similarity': 0.0}
                       for k, v in expected_manifest.items()],
            'ocr_texts': [],
            'elapsed_ms': elapsed, 'cross_score': 0,
        }

    # Step 2: 逐条比对
    matched = []
    missed = []
    for key, expected_text in expected_manifest.items():
        # 跳过太短的文字 (1-2字符的数字/符号不适合 OCR 验证)
        if len(expected_text.strip()) <= 1:
            matched.append({
                'key': key, 'expected': expected_text,
                'ocr_match': '(skipped)', 'similarity': 1.0,
            })
            continue

        sim, best = _best_match(expected_text, ocr_texts)

        if sim >= threshold:
            matched.append({
                'key': key, 'expected': expected_text,
                'ocr_match': best, 'similarity': round(sim, 3),
            })
        else:
            missed.append({
                'key': key, 'expected': expected_text,
                'ocr_best': best, 'similarity': round(sim, 3),
            })

    elapsed = int((time.time() - t0) * 1000)
    total = len(matched) + len(missed)
    hit_count = len(matched)
    hit_rate = hit_count / total if total > 0 else 1.0

    # 计算交叉验证分数 (0~100)
    cross_score = int(hit_rate * 100)

    return {
        'available': True,
        'hit_rate': round(hit_rate, 3),
        'hit_count': hit_count,
        'total_count': total,
        'matched': matched,
        'missed': missed,
        'ocr_texts': ocr_texts,
        'elapsed_ms': elapsed,
        'cross_score': cross_score,
    }


def calibrate_audit_score(gemini_score: int, cross_result: dict) -> tuple[int, str]:
    """
    结合 Gemini 审核分和交叉验证结果, 输出校准后的分数和原因。
    
    策略:
      1. OCR 不可用 → 直接用 Gemini 分数
      2. 两者一致 → 直接用 Gemini 分数 (可信)
      3. Gemini 高 + OCR 低 → 下调 (Gemini 可能漏检)
      4. Gemini 低 + OCR 高 → 上调 (Gemini 可能误报, 避免不必要的重生成)
    
    Returns:
        (calibrated_score, reason)
    """
    if not cross_result.get('available', False):
        return gemini_score, 'OCR不可用,使用原始分数'

    hit_rate = cross_result.get('hit_rate', 0)
    cross_score = cross_result.get('cross_score', 0)
    total = cross_result.get('total_count', 0)

    if total == 0:
        return gemini_score, '无检查项'

    # ── 情况1: 两者一致 (差距 ≤ 20) ──
    diff = abs(gemini_score - cross_score)
    if diff <= 20:
        return gemini_score, f'一致(OCR={cross_score},差{diff})'

    # ── 情况2: Gemini 高 + OCR 低 → Gemini 可能漏检, 下调 ──
    if gemini_score >= 70 and cross_score < 50:
        missed = cross_result.get('missed', [])
        missed_texts = [m['expected'][:10] for m in missed[:3]]
        adjusted = max(40, int(gemini_score * 0.6))
        return adjusted, f'OCR发现{len(missed)}处未匹配({",".join(missed_texts)}),下调{gemini_score}→{adjusted}'

    # ── 情况3: Gemini 低 + OCR 高 → Gemini 可能误报, 上调 ──
    if gemini_score < 60 and cross_score >= 80:
        adjusted = min(85, int((gemini_score + cross_score) / 2))
        return adjusted, f'OCR验证{cross_score}分文字OK,上调{gemini_score}→{adjusted}'

    # ── 情况4: 中间地带 → 取加权平均 (Gemini 60% + OCR 40%) ──
    adjusted = int(gemini_score * 0.6 + cross_score * 0.4)
    return adjusted, f'加权校准(G={gemini_score}*0.6+OCR={cross_score}*0.4={adjusted})'


# ── 便捷入口 ──

def validate_and_calibrate(image_data: bytes, manifest: dict,
                           gemini_score: int) -> tuple[int, dict, str]:
    """
    一站式调用: OCR交叉验证 + 分数校准。
    
    Returns:
        (calibrated_score, cross_result, reason)
    """
    cross_result = cross_validate(image_data, manifest)
    calibrated, reason = calibrate_audit_score(gemini_score, cross_result)
    return calibrated, cross_result, reason
