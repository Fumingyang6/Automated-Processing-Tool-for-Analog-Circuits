# -*- coding: utf-8 -*-
"""
把 docs/ 下的四份 Markdown 合成一本 PDF。

Markdown 只用到这些语法（本目录的文档就是照这个子集写的）：
    # / ## / ### 标题        **粗体**        `行内代码`
    - 无序列表               1. 有序列表
    | 表格 | 表头 |          （紧跟一行 |---|---| 分隔）
    > 引用（渲染成提示框，含“注意/建议/示例”等词的用橙色）
    ![说明](images/xx.png)  图片 + 图注
    ```           围栏代码块
    ---                     分隔线

依赖 reportlab + Pillow。用法：

    ..\\.venv\\python.exe build_docs.py
"""
import os
import re
import sys
from html.parser import HTMLParser

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Preformatted, Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

HERE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(HERE, "images")
OUT_PDF = os.path.join(HERE, "Parms_模块一模块二_使用文档与案例说明.pdf")

DOCS = [
    "模块一_电路版图生成_使用文档.md",
    "模块一_电路版图生成_案例说明.md",
    "模块二_自动布局_使用文档.md",
    "模块二_自动布局_案例说明.md",
]

# ---------------------------------------------------------------- 字体
FONT_DIR = r"C:\Windows\Fonts"
BODY, BOLD, MONO, MONO_NAME = "MSYH", "MSYH-Bold", "Mono", "MSYH"


def reg_fonts():
    global MONO_NAME
    pdfmetrics.registerFont(TTFont(BODY, os.path.join(FONT_DIR, "msyh.ttc")))
    pdfmetrics.registerFont(TTFont(BOLD, os.path.join(FONT_DIR, "msyhbd.ttc")))
    pdfmetrics.registerFontFamily(BODY, normal=BODY, bold=BOLD,
                                  italic=BODY, boldItalic=BOLD)
    # 行内代码用等宽体。Consolas 之类没有中文字形，而 reportlab 遇到缺字会
    # 直接渲染成空白且不报错——会静默吞掉正文，所以必须挑带中文的等宽体。
    # 新宋体（NSimSun）是 simsun.ttc 的 1 号子字体，中文全角、拉丁半角都是等宽。
    try:
        pdfmetrics.registerFont(
            TTFont(MONO, os.path.join(FONT_DIR, "simsun.ttc"), subfontIndex=1))
        MONO_NAME = MONO
    except Exception:
        MONO_NAME = BODY
    # 顺带把 NSimSun 取名 "CJK"，代码块和 ASCII 图用它
    try:
        pdfmetrics.registerFont(
            TTFont("CJK", os.path.join(FONT_DIR, "simsun.ttc"), subfontIndex=1))
    except Exception:
        pdfmetrics.registerFont(TTFont("CJK", os.path.join(FONT_DIR, "msyh.ttc")))


# ---------------------------------------------------------------- 配色
C_PRIMARY = colors.HexColor("#1e3a8a")
C_ACCENT = colors.HexColor("#2b6ef7")
C_TEXT = colors.HexColor("#303133")
C_MUTED = colors.HexColor("#606266")
C_BORDER = colors.HexColor("#dcdfe6")
C_BG = colors.HexColor("#f5f7fa")
C_NOTE_BG = colors.HexColor("#eef6ff")
C_NOTE_BAR = colors.HexColor("#2b6ef7")
C_WARN_BG = colors.HexColor("#fff6e6")
C_WARN_BAR = colors.HexColor("#e6a23c")
C_CODEBG = colors.HexColor("#f6f8fa")

# ---------------------------------------------------------------- 样式
S = {}
S["body"] = ParagraphStyle(
    "body", fontName=BODY, fontSize=10, leading=17, textColor=C_TEXT,
    alignment=TA_JUSTIFY, spaceAfter=5, wordWrap="CJK")
S["h2"] = ParagraphStyle(
    "h2", fontName=BOLD, fontSize=16, leading=22, textColor=C_PRIMARY,
    spaceBefore=16, spaceAfter=9, wordWrap="CJK")
S["h3"] = ParagraphStyle(
    "h3", fontName=BOLD, fontSize=12, leading=18, textColor=C_ACCENT,
    spaceBefore=11, spaceAfter=5, wordWrap="CJK")
S["li"] = ParagraphStyle(
    "li", parent=S["body"], leftIndent=13, bulletIndent=3, spaceAfter=3)
S["note"] = ParagraphStyle(
    "note", parent=S["body"], fontSize=9.5, leading=15.5, alignment=TA_LEFT,
    textColor=colors.HexColor("#1a4d8f"), spaceAfter=0)
S["warn"] = ParagraphStyle(
    "warn", parent=S["note"], textColor=colors.HexColor("#8a5a00"))
S["cell"] = ParagraphStyle(
    "cell", fontName=BODY, fontSize=9, leading=14, textColor=C_TEXT,
    wordWrap="CJK")
S["cellh"] = ParagraphStyle(
    "cellh", parent=S["cell"], fontName=BOLD, textColor=colors.white)
S["code"] = ParagraphStyle(
    "code", fontName="CJK", fontSize=8.2, leading=12.6,
    textColor=colors.HexColor("#24292f"), wordWrap="CJK")
S["cover_title"] = ParagraphStyle(
    "cover_title", fontName=BOLD, fontSize=30, leading=42,
    textColor=C_PRIMARY, alignment=TA_CENTER, wordWrap="CJK")
S["cover_sub"] = ParagraphStyle(
    "cover_sub", fontName=BODY, fontSize=15, leading=24,
    textColor=C_ACCENT, alignment=TA_CENTER, wordWrap="CJK")
S["cover_meta"] = ParagraphStyle(
    "cover_meta", fontName=BODY, fontSize=10.5, leading=19,
    textColor=C_MUTED, alignment=TA_CENTER, wordWrap="CJK")
S["h1"] = ParagraphStyle(
    "h1", fontName=BOLD, fontSize=21, leading=30,
    textColor=C_PRIMARY, spaceAfter=12, wordWrap="CJK")
S["caption"] = ParagraphStyle(
    "caption", fontName=BODY, fontSize=8.8, leading=14,
    textColor=C_MUTED, alignment=TA_CENTER, spaceBefore=4, spaceAfter=12,
    wordWrap="CJK")


# ================================================================ Markdown -> HTML
# 微软雅黑和新宋体都没有 emoji 字形，reportlab 遇到缺字不会报错，直接画成空白方块。
# 文档里保留界面原始的 emoji（Markdown 是给人读的，应该和界面一致），
# 只在出 PDF 这一步换成有字形的等价符号。
GLYPH_FIX = {
    "✅": "√",        # ✅ -> √
    "❌": "×",        # ❌ -> ×
    "✔": "√",
    "✘": "×",
    "⚠️": "!",
    "⚠": "!",
    "⏳": "",          # ⏳ 沙漏，字体里没有；原文后面本来就跟着 "..."，去掉即可
    "\U0001f465": "",          # 👥
    "\U0001f4c1": "",
    "\U0001f4c4": "",
    "⭐": "*",
}


def fix_glyphs(s):
    for k, v in GLYPH_FIX.items():
        s = s.replace(k, v)
    return s


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(s):
    """行内语法。先抽出行内代码，避免代码里的 * 被当成粗体。"""
    s = esc(s)
    codes = []

    def stash(m):
        codes.append(m.group(1))
        return "\x00%d\x00" % (len(codes) - 1)

    s = re.sub(r"`([^`]+)`", stash, s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    for i, c in enumerate(codes):
        s = s.replace("\x00%d\x00" % i,
                      '<font name="%s" size="9" color="#b3306b">%s</font>'
                      % (MONO_NAME, c))
    return s


WARN_WORDS = ("注意", "警告", "⚠", "务必", "千万", "必然")


def md_to_html(md):
    md = fix_glyphs(md)
    out = []
    lines = md.split("\n")
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        st = ln.strip()

        # 围栏代码块
        if st.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre>%s</pre>" % esc("\n".join(buf)))
            continue

        # 表格
        if st.startswith("|") and i + 1 < n and re.match(
                r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            head = [c.strip() for c in st.strip("|").split("|")]
            out.append("<table><tr>" + "".join("<th>%s</th>" % inline(c)
                                               for c in head) + "</tr>")
            i += 2
            while i < n and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join("<td>%s</td>" % inline(c)
                                            for c in cells) + "</tr>")
                i += 1
            out.append("</table>")
            continue

        # 引用块 -> 提示框
        if st.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            text = " ".join(x for x in buf if x)
            cls = "warn" if any(w in text for w in WARN_WORDS) else "note"
            out.append('<div class="%s">%s</div>' % (cls, inline(text)))
            continue

        # 图片
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", st)
        if m:
            out.append('<img src="%s" alt="%s"/>' % (m.group(2), esc(m.group(1))))
            i += 1
            continue

        # 标题
        if st.startswith("### "):
            out.append("<h3>%s</h3>" % inline(st[4:]))
            i += 1
            continue
        if st.startswith("## "):
            out.append("<h2>%s</h2>" % inline(st[3:]))
            i += 1
            continue
        if st.startswith("# "):
            out.append("<h2>%s</h2>" % inline(st[2:]))   # 每份文档的一级标题当章
            i += 1
            continue

        # 分隔线
        if re.match(r"^-{3,}$", st):
            i += 1
            continue

        # 列表
        if re.match(r"^[-*] ", st) or re.match(r"^\d+\. ", st):
            out.append("<ul>")
            while i < n:
                s2 = lines[i].strip()
                m2 = re.match(r"^[-*] (.*)$", s2) or re.match(r"^\d+\. (.*)$", s2)
                if not m2:
                    break
                out.append("<li>%s</li>" % inline(m2.group(1)))
                i += 1
            out.append("</ul>")
            continue

        # 空行
        if not st:
            i += 1
            continue

        # 段落（连续的普通行合并）
        buf = []
        while i < n:
            s2 = lines[i].strip()
            if (not s2 or s2.startswith(("#", ">", "|", "```", "!["))
                    or re.match(r"^[-*] ", s2) or re.match(r"^\d+\. ", s2)
                    or re.match(r"^-{3,}$", s2)):
                break
            buf.append(s2)
            i += 1
        if buf:
            out.append("<p>%s</p>" % inline(" ".join(buf)))
    return "\n".join(out)


# ================================================================ HTML -> flowables
class FragParser(HTMLParser):
    BLOCK = {"h2", "h3", "p", "li", "pre"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.buf = []
        self.mode = None
        self.in_table = False
        self.rows = None
        self.row = None
        self.cell = None
        self.cellhdr = False
        self.in_pre = False

    # ---- 文本 ----
    def _flush(self):
        txt = "".join(self.buf).strip()
        self.buf = []
        if not txt:
            return
        if self.mode == "li":
            self.out.append(Paragraph(txt, S["li"], bulletText="•"))
        elif self.mode == "h2":
            p = Paragraph(txt, S["h2"])
            p._toc = ("h2", txt)
            self.out.append(p)
        elif self.mode == "h3":
            p = Paragraph(txt, S["h3"])
            p._toc = ("h3", txt)
            self.out.append(p)
        elif self.mode == "pre":
            self.out.append(self._codeblock(txt))
        elif self.mode in ("div:note", "div:warn"):
            is_note = self.mode.endswith("note")
            self.out.append(self._callout(
                Paragraph(txt, S["note"] if is_note else S["warn"]),
                C_NOTE_BAR if is_note else C_WARN_BAR,
                C_NOTE_BG if is_note else C_WARN_BG))
        elif self.mode == "p":
            self.out.append(Paragraph(txt, S["body"]))

    @staticmethod
    def _callout(para, bar, bg):
        t = Table([["", para]], colWidths=[2.2 * mm, None])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), bar),
            ("BACKGROUND", (1, 0), (1, 0), bg),
            ("LEFTPADDING", (1, 0), (1, 0), 7),
            ("RIGHTPADDING", (1, 0), (1, 0), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (0, 0), 0),
            ("RIGHTPADDING", (0, 0), (0, 0), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        return KeepTogether([Spacer(1, 3), t, Spacer(1, 7)])

    @staticmethod
    def _codeblock(txt):
        t = Table([[Preformatted(txt, S["code"])]], colWidths=[170 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), C_CODEBG),
            ("BOX", (0, 0), (-1, -1), 0.5, C_BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return KeepTogether([Spacer(1, 3), t, Spacer(1, 8)])

    def _inline(self, s):
        if self.in_table and self.cell is not None:
            self.cell.append(s)
        else:
            self.buf.append(s)

    # ---- 标签 ----
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self.in_table, self.rows = True, []
            return
        if tag == "tr":
            self.row = []
            return
        if tag in ("td", "th"):
            self.cell, self.cellhdr = [], (tag == "th")
            return
        if tag == "img":
            src = a.get("src", "")
            path = os.path.join(HERE, src.replace("/", os.sep))
            self.out.append(KeepTogether([
                Spacer(1, 4), img_flowable(path),
                Paragraph(esc(a.get("alt", "")), S["caption"])]))
            return
        if tag == "div":
            self._flush()
            cls = a.get("class", "")
            self.mode = ("div:note" if "note" in cls
                         else "div:warn" if "warn" in cls else "p")
            return
        if tag in self.BLOCK:
            self._flush()
            self.mode = tag
            return
        if tag == "code":
            self._inline('<font name="%s" size="9" color="#b3306b">' % MONO_NAME)
            return
        if tag in ("b", "strong"):
            self._inline("<b>")
            return
        if tag == "br":
            self._inline("<br/>")
            return

    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table = False
            self._emit_table()
            return
        if tag == "tr":
            if self.row:
                self.rows.append(self.row)
            self.row = None
            return
        if tag in ("td", "th"):
            if self.row is not None and self.cell is not None:
                self.row.append((self.cellhdr, "".join(self.cell).strip()))
            self.cell = None
            return
        if tag == "code":
            self._inline("</font>")
            return
        if tag in ("b", "strong"):
            self._inline("</b>")
            return
        if tag == "div" or tag in self.BLOCK:
            self._flush()
            self.mode = None
            return

    def handle_data(self, data):
        if self.in_table and self.cell is not None:
            self.cell.append(data)
            return
        if self.mode is None:
            return
        if self.mode == "pre":
            self.buf.append(data)          # 已经转义过了
            return
        self.buf.append(data)

    def _emit_table(self):
        rows = [r for r in (self.rows or []) if r]
        if not rows:
            return
        ncol = max(len(r) for r in rows)
        data = []
        for r in rows:
            cells = [Paragraph(t, S["cellh"] if hdr else S["cell"])
                     for hdr, t in r]
            while len(cells) < ncol:
                cells.append(Paragraph("", S["cell"]))
            data.append(cells)

        avail = 170 * mm
        widths = col_widths(rows, ncol, avail)
        has_head = bool(rows[0] and rows[0][0][0])
        t = Table(data, colWidths=widths, repeatRows=1 if has_head else 0)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_BG]),
            ("GRID", (0, 0), (-1, -1), 0.4, C_BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        self.out.append(Spacer(1, 3))
        self.out.append(t)
        self.out.append(Spacer(1, 8))
        self.rows = None


def disp_width(s):
    """估算显示宽度：中日韩全角字符按 2 算，其余按 1。"""
    return sum(2 if ord(ch) > 0x2E7F else 1 for ch in s)


def col_widths(rows, ncol, avail):
    """按各列最宽文字估算列宽。用真实的显示宽度而不是字符个数，
    否则 "gds/R_demo.gds" 这种拉丁串会被判得太窄，在单元格里断成两行。"""
    weights = []
    for c in range(ncol):
        widest = 0
        for r in rows:
            if c >= len(r):
                continue
            txt = re.sub(r"<[^>]+>", "", r[c][1])   # 去掉行内标签再量
            widest = max(widest, max(
                (disp_width(x) for x in txt.split()), default=0))
        weights.append(max(6.0, min(48.0, widest + 2)))
    total = sum(weights)
    return [avail * w / total for w in weights]


def img_flowable(path, max_w=168 * mm, max_h=104 * mm):
    if not os.path.exists(path):
        return Spacer(1, 1)
    from PIL import Image as PILImage
    iw, ih = PILImage.open(path).size
    scale = min(max_w / iw, max_h / ih)
    return Image(path, width=iw * scale, height=ih * scale)


# ================================================================ 文档模板
class Doc(BaseDocTemplate):
    def __init__(self, fn, **kw):
        super().__init__(fn, **kw)
        self.page_kind = "cover"

    def afterFlowable(self, fl):
        toc = getattr(fl, "_toc", None)
        if toc:
            lvl, txt = toc
            self.notify("TOCEntry", (0 if lvl == "h2" else 1, txt, self.page))


def on_cover(canv, doc):
    canv.saveState()
    w, h = A4
    canv.setFillColor(C_PRIMARY)
    canv.rect(0, h - 92 * mm, w, 92 * mm, stroke=0, fill=1)
    canv.setFillColor(C_ACCENT)
    canv.rect(0, h - 95 * mm, w, 3 * mm, stroke=0, fill=1)
    canv.setFillColor(colors.white)
    canv.setFont(BOLD, 36)
    canv.drawCentredString(w / 2, h - 44 * mm, "Parms")
    canv.setFont(BODY, 13)
    canv.drawCentredString(w / 2, h - 56 * mm, "模拟电路自动化设计工具")
    canv.setFont(BODY, 11)
    canv.setFillColor(colors.HexColor("#c7dbff"))
    canv.drawCentredString(w / 2, h - 68 * mm, "模块一 / 模块二  使用文档与案例说明")
    canv.restoreState()


def on_page(canv, doc):
    canv.saveState()
    w, h = A4
    canv.setStrokeColor(C_BORDER)
    canv.setLineWidth(0.6)
    canv.line(20 * mm, h - 17 * mm, w - 20 * mm, h - 17 * mm)
    canv.setFont(BODY, 8.5)
    canv.setFillColor(C_MUTED)
    canv.drawString(20 * mm, h - 14 * mm, "Parms · 模块一 电路版图生成 / 模块二 自动布局")
    canv.drawRightString(w - 20 * mm, h - 14 * mm, "CEDA · WHUT")
    canv.line(20 * mm, 15 * mm, w - 20 * mm, 15 * mm)
    canv.drawCentredString(w / 2, 10.5 * mm, "第 %d 页" % doc.page)
    canv.restoreState()


def build():
    reg_fonts()
    doc = Doc(
        OUT_PDF, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=22 * mm, bottomMargin=20 * mm,
        title="Parms 模块一/模块二 使用文档与案例说明", author="CEDA · WHUT")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame], onPage=on_cover),
        PageTemplate(id="main", frames=[frame], onPage=on_page),
    ])

    F = [Spacer(1, 116 * mm)]
    F.append(Paragraph("基于项目 v0.6 实机测试编写", S["cover_meta"]))
    F.append(Paragraph("覆盖模块一「电路版图生成」与模块二「自动布局」", S["cover_meta"]))
    F.append(Spacer(1, 32 * mm))
    F.append(Paragraph("2026 年 10 月 · 内部资料", S["cover_meta"]))
    F.append(NextPageTemplate("main"))
    F.append(PageBreak())

    F.append(Paragraph("目录", S["h1"]))
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("t0", fontName=BOLD, fontSize=11, leading=23,
                       textColor=C_PRIMARY, leftIndent=0, spaceBefore=6,
                       wordWrap="CJK"),
        ParagraphStyle("t1", fontName=BODY, fontSize=9.5, leading=17,
                       textColor=C_TEXT, leftIndent=15, wordWrap="CJK"),
    ]
    F.append(toc)
    F.append(PageBreak())

    for name in DOCS:
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            print("!! 缺少 %s" % name)
            continue
        with open(path, encoding="utf-8") as f:
            html = md_to_html(f.read())
        p = FragParser()
        p.feed(html)
        p._flush()
        print("  %-42s -> %3d flowables" % (name, len(p.out)))
        F.append(CondPageBreak(60 * mm))
        F.extend(p.out)
        F.append(PageBreak())

    doc.multiBuild(F)
    print("\nOK ->", OUT_PDF)
    print("size: %d bytes" % os.path.getsize(OUT_PDF))


if __name__ == "__main__":
    build()
