#!/usr/bin/env python3
"""
小红书虚拟产品 PDF 生成器 (专业学术风格)
=========================================
输出:
  products/打卡清单_小学版.pdf
  products/打卡清单_初中版.pdf
  products/打卡清单_高中版.pdf
  products/AI学习卡片生成指南.pdf
"""

import json, os, sys, tempfile
from pathlib import Path
from fpdf import FPDF
import qrcode

# ────────────────── 配置 ──────────────────

ROOT      = Path(__file__).parent
KC_DIR    = ROOT / "knowledge_cards"
OUT_DIR   = ROOT / "products"
FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"
PLATFORM  = "https://lincsd.github.io/xhs-emotion-platform/"

# 专业学术配色 (R, G, B)
C_NAVY   = (27,  42,  74)
C_SLATE  = (52,  73,  94)
C_GREEN  = (39, 174,  96)
C_LIGHT  = (245, 247, 250)
C_WHITE  = (255, 255, 255)
C_TEXT   = (44,  62,  80)
C_GREY   = (149, 165, 166)
C_BORDER = (200, 206, 211)

# 打卡清单表格列宽  (总 ≈ 180mm, A4 减去左右各 15mm 页边距)
#       序号  知识点  难度  重要  ✓1    ✓2    ✓3
COL_W = [8,   92,    20,   20,   13,   13,   13]
ROW_H = 7        # 数据行高
HDR_H = 8        # 表头行高
MAX_Y = 265      # 手动分页阈值 (保守, 避免自动分页撕裂行)

SUBJECTS = ["数学", "语文", "英语"]

STAGE_CFG = {
    "小学": {
        "name": "小学版",
        "grades": ["一", "二", "三", "四", "五", "六"],
        "gdisp": lambda g: f"{g}年级",
        "eng_start": 2,   # 英语从三年级起
        "suffix": "",
    },
    "初中": {
        "name": "初中版",
        "grades": ["七", "八", "九"],
        "gdisp": lambda g: f"{g}年级",
        "eng_start": 0,
        "suffix": "_总结",
    },
    "高中": {
        "name": "高中版",
        "grades": ["高一", "高二", "高三"],
        "gdisp": lambda g: g,
        "eng_start": 0,
        "suffix": "_总结",
    },
}

SUBJ_COLOR = {
    "数学": (41, 128, 185),
    "语文": (192, 57,  43),
    "英语": (39, 174,  96),
}


# ────────────────── 工具函数 ──────────────────

def stars(n):
    """紧凑星级: ★★★"""
    try:    n = min(max(int(n), 1), 5)
    except: n = 3
    return "\u2605" * n          # ★

def trunc(s, mx=28):
    s = str(s).strip().replace("\n", " ")
    return s[:mx-1] + "\u2026" if len(s) > mx else s

def make_qr(url):
    """生成二维码 PNG 临时文件, 返回路径"""
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(url); qr.make(fit=True)
    img = qr.make_image(fill_color="#1B2A4A", back_color="white")
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(tmp.name); tmp.close()
    return tmp.name

def extract_units(data):
    """
    从 JSON 提取知识点, 返回 [(单元名, [(标题, 难度, 重要度)])]
    兼容 units/cards, knowledge_points, chapters 三种格式
    """
    result = []
    if "units" in data:
        for u in data["units"]:
            name = u.get("unit_name", u.get("name", ""))
            cards = [(c.get("title",""), c.get("difficulty",3), c.get("importance",3))
                     for c in u.get("cards", [])]
            if cards: result.append((name, cards))
    elif "knowledge_points" in data:
        kps = data["knowledge_points"]
        cards = [(k.get("title", k.get("name","")), k.get("difficulty",3), k.get("importance",3))
                 for k in kps]
        if cards: result.append(("知识点", cards))
    elif "chapters" in data:
        for ch in data["chapters"]:
            name = ch.get("name", ch.get("chapter_name",""))
            kps = ch.get("knowledge_points", ch.get("cards", []))
            cards = [(k.get("title", k.get("name","")), k.get("difficulty",3), k.get("importance",3))
                     for k in kps]
            if cards: result.append((name, cards))
    return result

def load_kc(stage, subj, grade, sem, suffix):
    """加载单个 knowledge_card JSON, 返回 (units_list, filepath)"""
    fn = f"{subj}_{grade}{sem}{suffix}.json"
    fp = KC_DIR / stage / fn
    if not fp.exists():
        return None, fp
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return extract_units(json.load(f)), fp
    except Exception as e:
        print(f"  [!] 读取失败 {fp.name}: {e}")
        return None, fp


# ────────────────── 基础 PDF 类 ──────────────────

class PDF(FPDF):
    def __init__(self, title=""):
        super().__init__()
        self._title = title
        self._cover = False
        self.add_font("sh", "", FONT_PATH)
        self.set_auto_page_break(True, margin=22)
        self.set_margins(15, 15, 15)
        self.set_title(title)
        self.set_author("AI学习卡片平台")

    # ── 页眉 ──
    def header(self):
        if self._cover or self.page_no() <= 1:
            return
        self.set_font("sh", "", 8)
        self.set_text_color(*C_GREY)
        self.cell(90, 6, self._title)
        self.cell(90, 6, f"- {self.page_no()} -", align="R")
        self.ln(6)
        self.set_draw_color(*C_BORDER)
        self.line(15, self.get_y(), 195, self.get_y())
        self.ln(4)

    # ── 页脚 ──
    def footer(self):
        if self._cover:
            return
        self.set_y(-16)
        self.set_font("sh", "", 7)
        self.set_text_color(*C_GREY)
        self.cell(0, 6, PLATFORM, align="C")

    # ── 封面 ──
    def cover(self, lines, sub=""):
        self._cover = True
        self.add_page()
        self.set_fill_color(*C_NAVY)
        self.rect(0, 0, 210, 297, "F")
        # 装饰线
        self.set_draw_color(*C_GREEN)
        self.set_line_width(1.5)
        self.line(30, 110, 180, 110)
        # 标题
        self.set_font("sh", "", 36)
        self.set_text_color(*C_WHITE)
        y = 125
        for t in lines:
            self.set_xy(15, y); self.cell(180, 18, t, align="C"); y += 22
        self.set_line_width(1.5)
        self.line(30, y+5, 180, y+5)
        self.set_line_width(0.2)
        if sub:
            self.set_font("sh", "", 14)
            self.set_text_color(200, 210, 220)
            self.set_xy(15, y+15); self.cell(180, 10, sub, align="C")
        # 底部
        self.set_font("sh", "", 10)
        self.set_text_color(150, 160, 180)
        self.set_xy(15, 258); self.cell(180, 8, "配套平台", align="C")
        self.set_font("sh", "", 9)
        self.set_xy(15, 266); self.cell(180, 8, PLATFORM, align="C")
        self._cover = False

    # ── 尾页 (二维码) ──
    def back_cover(self, qr_path):
        self._cover = True
        self.add_page()
        self.set_fill_color(*C_LIGHT)
        self.rect(0, 0, 210, 297, "F")
        self.set_font("sh", "", 22)
        self.set_text_color(*C_NAVY)
        self.set_xy(15, 80); self.cell(180, 12, "扫码打开学习平台", align="C")
        self.image(qr_path, x=70, y=100, w=70)
        self.set_font("sh", "", 12)
        self.set_text_color(*C_SLATE)
        self.set_xy(15, 178); self.cell(180, 8, PLATFORM, align="C")
        self.set_font("sh", "", 10)
        self.set_text_color(*C_GREY)
        self.set_xy(15, 195); self.cell(180, 8, "一键生成 AI 学习卡片  |  覆盖小初高三科", align="C")
        self.set_xy(15, 205); self.cell(180, 8, "多种风格任选  |  手机电脑都能用", align="C")
        self._cover = False

    # ── 章节分隔页 ──
    def section_page(self, title, sub="", color=None):
        self._cover = True
        self.add_page()
        c = color or C_NAVY
        self.set_fill_color(*c)
        self.rect(20, 100, 6, 60, "F")
        self.set_font("sh", "", 32)
        self.set_text_color(*c)
        self.set_xy(35, 112); self.cell(150, 16, title)
        if sub:
            self.set_font("sh", "", 13)
            self.set_text_color(*C_GREY)
            self.set_xy(35, 140); self.cell(150, 10, sub)
        self._cover = False

    # ── 空间检查 ──
    def need_break(self, h):
        return self.get_y() + h > MAX_Y


# ────────────────── 打卡清单表格绘制 ──────────────────

def draw_table_header(pdf):
    """绘制表头行"""
    pdf.set_fill_color(*C_SLATE)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("sh", "", 8)
    for w, txt in zip(COL_W, ["序号","知识点","难度","重要","第1轮","第2轮","第3轮"]):
        pdf.cell(w, HDR_H, txt, border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_text_color(*C_TEXT)


def draw_checklist(pdf, subj, grade_d, sem_d, units, n_pts, color):
    """绘制一个学期的打卡清单页"""
    tag = f"{subj} \u00b7 {grade_d}{sem_d}"

    pdf.add_page()
    # 页面标题
    pdf.set_font("sh", "", 16)
    pdf.set_text_color(*color)
    pdf.cell(0, 10, tag); pdf.ln(10)

    # 学生信息栏
    pdf.set_fill_color(*C_LIGHT)
    iy = pdf.get_y()
    pdf.rect(15, iy, 180, 9, "F")
    pdf.set_font("sh", "", 9)
    pdf.set_text_color(*C_TEXT)
    pdf.set_xy(17, iy+1)
    pdf.cell(55, 7, "姓名:_______________")
    pdf.cell(55, 7, "班级:_______________")
    pdf.cell(68, 7, f"知识点总数: {n_pts} 个", align="R")
    pdf.ln(12)

    draw_table_header(pdf)

    idx = 0
    for unit_name, cards in units:
        # 单元标题行 — 检查空间
        if pdf.need_break(HDR_H + ROW_H * 2):
            pdf.add_page()
            pdf.set_font("sh", "", 12)
            pdf.set_text_color(*color)
            pdf.cell(0, 8, f"{tag} (续)"); pdf.ln(10)
            draw_table_header(pdf)

        pdf.set_fill_color(230, 235, 240)
        pdf.set_font("sh", "", 9)
        pdf.set_text_color(*C_NAVY)
        tw = sum(COL_W)
        pdf.cell(tw, ROW_H, f"  {trunc(unit_name, 40)}", border="LRT", fill=True)
        pdf.ln()

        for title, diff, imp in cards:
            if pdf.need_break(ROW_H):
                pdf.add_page()
                pdf.set_font("sh", "", 12)
                pdf.set_text_color(*color)
                pdf.cell(0, 8, f"{tag} (续)"); pdf.ln(10)
                draw_table_header(pdf)

            idx += 1
            bg = (250, 251, 252) if idx % 2 == 0 else C_WHITE
            pdf.set_fill_color(*bg)
            pdf.set_font("sh", "", 8)
            pdf.set_text_color(*C_TEXT)
            pdf.cell(COL_W[0], ROW_H, str(idx), border=1, align="C", fill=True)
            pdf.cell(COL_W[1], ROW_H, trunc(title, 28), border=1, fill=True)
            pdf.set_font("sh", "", 7)
            pdf.cell(COL_W[2], ROW_H, stars(diff), border=1, align="C", fill=True)
            pdf.cell(COL_W[3], ROW_H, stars(imp), border=1, align="C", fill=True)
            pdf.set_font("sh", "", 8)
            for j in range(3):
                pdf.cell(COL_W[4+j], ROW_H, "", border=1, fill=True)
            pdf.ln()

    # 底部进度
    pdf.ln(4)
    pdf.set_font("sh", "", 9)
    pdf.set_text_color(*C_GREY)
    pdf.cell(0, 7, f"完成进度: ______ / {n_pts} 个知识点已掌握")
    pdf.ln()


# ────────────────── 生成: 打卡清单 PDF ──────────────────

def gen_checklist(stage):
    cfg  = STAGE_CFG[stage]
    name = cfg["name"]
    pdf  = PDF(f"知识点打卡清单 \u00b7 {name}")

    print(f"\n{'='*50}\n  生成: 打卡清单 {name}\n{'='*50}")

    pdf.cover(["知识点打卡清单", name],
              "数学 \u00b7 语文 \u00b7 英语  |  3轮打卡 \u00b7 打印即用")

    total_pts = 0
    total_files = 0

    for subj in SUBJECTS:
        sc = SUBJ_COLOR.get(subj, C_NAVY)
        items = []  # (grade_display, sem_display, units, n_points)

        for gi, gk in enumerate(cfg["grades"]):
            if subj == "英语" and gi < cfg["eng_start"]:
                continue
            for sem in ["上", "下"]:
                units, fp = load_kc(stage, subj, gk, sem, cfg["suffix"])
                if units is None:
                    print(f"  [跳过] {fp.name}")
                    continue
                gd  = cfg["gdisp"](gk)
                sd  = f"{sem}册"
                npt = sum(len(c) for _, c in units)
                items.append((gd, sd, units, npt))
                total_files += 1

        if not items:
            continue

        s_total = sum(n for *_, n in items)
        pdf.section_page(subj, f"共 {len(items)} 个学期 \u00b7 {s_total} 个知识点", sc)

        for gd, sd, units, npt in items:
            draw_checklist(pdf, subj, gd, sd, units, npt, sc)
            total_pts += npt

    qr = make_qr(PLATFORM)
    pdf.back_cover(qr)
    os.unlink(qr)

    out = OUT_DIR / f"打卡清单_{name}.pdf"
    pdf.output(str(out))
    sz = out.stat().st_size / 1024
    print(f"  -> {out.name}  ({total_files} 学期, {total_pts} 知识点, "
          f"{pdf.page_no()} 页, {sz:.0f}KB)")
    return out


# ────────────────── 指南 PDF 辅助 ──────────────────

def _step_hdr(pdf, n, title):
    """步骤标题: 第N步 · 标题"""
    y = pdf.get_y()
    pdf.set_font("sh", "", 28)
    pdf.set_text_color(*C_GREEN)
    pdf.set_xy(15, y); pdf.cell(55, 16, f"第{n}步")
    pdf.set_font("sh", "", 22)
    pdf.set_text_color(*C_NAVY)
    pdf.cell(130, 16, title); pdf.ln(16)
    pdf.set_draw_color(*C_GREEN)
    pdf.set_line_width(0.8)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.set_line_width(0.2)
    pdf.ln(4)

def _numbered(pdf, items):
    """带编号的步骤列表"""
    for i, txt in enumerate(items):
        y = pdf.get_y()
        # 编号方块
        pdf.set_fill_color(*C_GREEN)
        pdf.rect(20, y+1, 7, 7, "F")
        pdf.set_font("sh", "", 10)
        pdf.set_text_color(*C_WHITE)
        pdf.set_xy(20, y+0.5); pdf.cell(7, 8, str(i+1), align="C")
        # 文字
        pdf.set_font("sh", "", 11)
        pdf.set_text_color(*C_TEXT)
        pdf.set_xy(31, y); pdf.multi_cell(154, 8, txt)
        pdf.ln(1)

def _tip(pdf, txt):
    """提示框"""
    y = pdf.get_y()
    pdf.set_fill_color(255, 248, 230)
    pdf.set_draw_color(243, 156, 18)
    pdf.rect(20, y, 170, 12, "DF")
    pdf.set_font("sh", "", 9)
    pdf.set_text_color(200, 120, 0)
    pdf.set_xy(25, y+2); pdf.cell(160, 8, f"[提示] {txt}")
    pdf.ln(16)

def _benefit(pdf, num, title, desc):
    """益处条目"""
    y = pdf.get_y()
    pdf.set_fill_color(*C_LIGHT)
    pdf.rect(15, y, 180, 18, "F")
    pdf.set_fill_color(*C_GREEN)
    pdf.rect(15, y, 4, 18, "F")
    pdf.set_font("sh", "", 14)
    pdf.set_text_color(*C_GREEN)
    pdf.set_xy(22, y+1); pdf.cell(10, 8, f"0{num}")
    pdf.set_font("sh", "", 13)
    pdf.set_text_color(*C_NAVY)
    pdf.set_xy(36, y+1); pdf.cell(100, 8, title)
    pdf.set_font("sh", "", 9)
    pdf.set_text_color(*C_GREY)
    pdf.set_xy(22, y+9); pdf.cell(165, 7, desc)
    pdf.set_xy(15, y+22)

def _faq(pdf, q, a):
    """FAQ 条目"""
    if pdf.need_break(22):
        pdf.add_page()
    pdf.set_font("sh", "", 12)
    pdf.set_text_color(*C_NAVY)
    pdf.cell(0, 8, f"Q: {q}"); pdf.ln(8)
    pdf.set_font("sh", "", 10)
    pdf.set_text_color(*C_TEXT)
    pdf.multi_cell(170, 7, f"A: {a}")
    pdf.ln(4)


# ────────────────── 生成: 指南 PDF ──────────────────

def gen_guide():
    print(f"\n{'='*50}\n  生成: AI学习卡片生成指南\n{'='*50}")

    pdf = PDF("AI学习卡片 \u00b7 一键生成指南")
    qr  = make_qr(PLATFORM)

    # ── 封面 ──
    pdf.cover(["AI学习卡片", "一键生成指南"],
              "打开平台 \u2192 选内容 \u2192 一键生成 \u2192 下载使用")

    # ── P2: 你将获得 ──
    pdf.add_page()
    pdf.set_font("sh", "", 22)
    pdf.set_text_color(*C_NAVY)
    pdf.cell(0, 14, "这份指南能帮你什么?"); pdf.ln(20)
    _benefit(pdf, 1, "一键生成精美学习卡片", "AI 自动排版设计, 不需要任何设计经验")
    _benefit(pdf, 2, "覆盖小学 / 初中 / 高中", "数学、语文、英语三大主科全覆盖")
    _benefit(pdf, 3, "多种卡片风格任选",     "极简文艺、手绘笔记、清新可爱、学术干货")
    _benefit(pdf, 4, "手机电脑都能用",       "打开浏览器就能用, 不用下载任何软件")
    pdf.ln(6)
    _tip(pdf, "只需 4 步, 3 分钟就能生成第一张卡片!")

    # ── P3: 第1步 ──
    pdf.add_page()
    _step_hdr(pdf, 1, "打开学习平台")
    pdf.set_font("sh", "", 11)
    pdf.set_text_color(*C_TEXT)
    pdf.ln(4)
    pdf.cell(0, 8, "在手机或电脑的浏览器地址栏, 输入以下网址:"); pdf.ln(12)
    # URL 框
    uy = pdf.get_y()
    pdf.set_fill_color(*C_LIGHT)
    pdf.set_draw_color(*C_NAVY)
    pdf.rect(25, uy, 160, 16, "DF")
    pdf.set_font("sh", "", 14)
    pdf.set_text_color(*C_NAVY)
    pdf.set_xy(25, uy+3); pdf.cell(160, 10, PLATFORM, align="C")
    pdf.set_xy(15, uy+22); pdf.ln(4)
    pdf.set_font("sh", "", 11)
    pdf.set_text_color(*C_TEXT)
    pdf.cell(0, 8, "或用手机扫描下方二维码直接打开:"); pdf.ln(10)
    pdf.image(qr, x=75, y=pdf.get_y(), w=60)
    pdf.ln(65)
    _tip(pdf, "推荐使用 Chrome 或 Edge 浏览器, 效果最佳")

    # ── P4: 第2步 ──
    pdf.add_page()
    _step_hdr(pdf, 2, "注册登录账号")
    pdf.ln(4)
    _numbered(pdf, [
        "打开平台后, 点击页面上的 [注册] 按钮",
        "输入你的手机号码",
        "点击 [获取验证码], 手机会收到一条短信",
        "输入收到的 6 位验证码",
        "点击 [注册] 按钮, 完成注册",
        "下次登录直接用手机号 + 验证码即可",
    ])
    pdf.ln(4)
    _tip(pdf, "注册完全免费, 新用户还会获得体验额度!")

    # ── P5: 第3步 ──
    pdf.add_page()
    _step_hdr(pdf, 3, "选择生成内容")
    pdf.ln(4)
    _numbered(pdf, [
        "在左侧菜单中, 点击 [内容生成]",
        "选择你需要的 [内容类别]",
        "选择 [生成数量] (建议新手先选 1 张试试)",
        "如需 AI 自动生成封面图, 打开 [AI Cover Image] 开关",
        "勾选 [自动保存到草稿] 方便后续管理",
    ])
    pdf.ln(4)
    _tip(pdf, "不知道选什么? 类别选 [随机], 系统会帮你挑最热门的")

    # ── P6: 第4步 ──
    pdf.add_page()
    _step_hdr(pdf, 4, "一键生成 & 下载")
    pdf.ln(4)
    _numbered(pdf, [
        "确认选好参数后, 点击 [一键生成] 大按钮",
        "等待 AI 生成 (通常 30 秒左右, 耐心等待)",
        "生成完成后, 卡片会显示在预览区域",
        "点击 [导出] 可以下载图片到手机或电脑",
        "可以批量导出, 一次下载多张卡片",
        "直接分享到小红书、朋友圈、家长群",
    ])
    pdf.ln(4)
    # 模式说明框
    by = pdf.get_y()
    pdf.set_fill_color(240, 248, 255)
    pdf.set_draw_color(41, 128, 185)
    pdf.rect(20, by, 170, 28, "DF")
    pdf.set_font("sh", "", 10)
    pdf.set_text_color(41, 128, 185)
    pdf.set_xy(25, by+3); pdf.cell(160, 7, "两种生成模式:"); pdf.ln()
    pdf.set_font("sh", "", 9)
    pdf.set_text_color(*C_TEXT)
    pdf.set_xy(25, pdf.get_y())
    pdf.cell(160, 7, "AI 智能模式 -- 联网分析热门趋势, 生成高质量内容 (推荐)"); pdf.ln()
    pdf.set_xy(25, pdf.get_y())
    pdf.cell(160, 7, "本地模板模式 -- 离线生成, 不需要网络"); pdf.ln(10)

    # ── P7: FAQ ──
    pdf.add_page()
    pdf.set_font("sh", "", 22)
    pdf.set_text_color(*C_NAVY)
    pdf.cell(0, 14, "常见问题"); pdf.ln(10)
    _faq(pdf, "需要花钱吗?",
         "注册免费, 新用户有体验额度。用完后可以购买积分包, 最低 9.9 元起。")
    _faq(pdf, "手机可以用吗?",
         "可以! 手机浏览器打开网址就能用, 和电脑操作一样。")
    _faq(pdf, "生成的内容质量好吗?",
         "使用 Google Gemini AI 生成, 内容质量很高。系统还会分析小红书热门趋势来优化内容。")
    _faq(pdf, "能生成哪些学科的卡片?",
         "目前支持数学、语文、英语三科, 覆盖小学到高中。")
    _faq(pdf, "生成的图片可以商用吗?",
         "可以自用或在小红书发布。AI 生成的内容无版权问题。")
    _faq(pdf, "遇到问题怎么办?",
         "平台右下角有帮助按钮, 也可以在小红书私信联系我们。")

    # ── 尾页 ──
    pdf.back_cover(qr)
    os.unlink(qr)

    out = OUT_DIR / "AI学习卡片生成指南.pdf"
    pdf.output(str(out))
    sz = out.stat().st_size / 1024
    print(f"  -> {out.name}  ({pdf.page_no()} 页, {sz:.0f}KB)")
    return out


# ────────────────── 主入口 ──────────────────

if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  小红书虚拟产品 PDF 生成器")
    print("  风格: 专业学术  |  格式: PDF")
    print("=" * 60)

    paths = []
    for stage in ["小学", "初中", "高中"]:
        paths.append(gen_checklist(stage))
    paths.append(gen_guide())

    print("\n" + "=" * 60)
    print("  全部完成!")
    print(f"  输出目录: {OUT_DIR}")
    print("=" * 60)
    for p in paths:
        sz = p.stat().st_size / 1024
        print(f"  {p.name:<30s} {sz:>6.0f} KB")
