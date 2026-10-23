# -*- coding: utf-8 -*-
"""生成新的《Parms 使用手册》。

只包含四个功能模块的操作步骤与截图，不再包含总览和问题汇总。
用法：..\\.venv\\python.exe build_manual.py
"""
import os
import re
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Frame, NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer,
)
from reportlab.platypus.tableofcontents import TableOfContents

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_docs as B

SRC = os.path.join(HERE, "Parms_使用手册.md")
OUT_PDF = os.path.join(HERE, "_Parms_使用手册_new.pdf")


def img_flowable(path, max_w=170 * mm, max_h=218 * mm):
    """截图尽量按页宽显示，保证界面文字可读。"""
    if not os.path.exists(path):
        return Spacer(1, 1)
    from PIL import Image as PILImage
    iw, ih = PILImage.open(path).size
    scale = min(max_w / iw, max_h / ih)
    return B.Image(path, width=iw * scale, height=ih * scale)


def on_cover(canv, doc):
    canv.saveState()
    w, h = A4
    canv.setFillColor(B.C_PRIMARY)
    canv.rect(0, h - 92 * mm, w, 92 * mm, stroke=0, fill=1)
    canv.setFillColor(B.C_ACCENT)
    canv.rect(0, h - 95 * mm, w, 3 * mm, stroke=0, fill=1)
    canv.setFillColor(colors.white)
    canv.setFont(B.BOLD, 36)
    canv.drawCentredString(w / 2, h - 44 * mm, "Parms")
    canv.setFont(B.BODY, 13)
    canv.drawCentredString(w / 2, h - 56 * mm, "模拟电路自动化设计工具")
    canv.setFont(B.BODY, 11)
    canv.setFillColor(colors.HexColor("#c7dbff"))
    canv.drawCentredString(w / 2, h - 68 * mm,
                          "功能操作手册 · 四个模块的操作步骤与截图演示")
    canv.restoreState()


def on_page(canv, doc):
    canv.saveState()
    w, h = A4
    canv.setStrokeColor(B.C_BORDER)
    canv.setLineWidth(0.6)
    canv.line(20 * mm, h - 17 * mm, w - 20 * mm, h - 17 * mm)
    canv.setFont(B.BODY, 8.5)
    canv.setFillColor(B.C_MUTED)
    canv.drawString(20 * mm, h - 14 * mm, "Parms · 功能操作手册")
    canv.drawRightString(w - 20 * mm, h - 14 * mm, "CEDA · WHUT")
    canv.line(20 * mm, 15 * mm, w - 20 * mm, 15 * mm)
    canv.drawCentredString(w / 2, 10.5 * mm, "第 %d 页" % doc.page)
    canv.restoreState()


def build():
    B.reg_fonts()
    # FragParser 内部调用模块级 img_flowable，替换成适合整页截图的尺寸
    B.img_flowable = img_flowable

    doc = B.Doc(
        OUT_PDF, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=22 * mm, bottomMargin=20 * mm,
        title="Parms 使用手册", author="CEDA · WHUT")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                  id="main")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame], onPage=on_cover),
        PageTemplate(id="main", frames=[frame], onPage=on_page),
    ])

    F = [Spacer(1, 116 * mm)]
    F.append(Paragraph("基于当前界面（v0.6）实测编写", B.S["cover_meta"]))
    F.append(Paragraph(
        "覆盖电路版图生成 / 自动布局 / 电路参数优化 / 自动布线",
        B.S["cover_meta"]))
    F.append(Spacer(1, 32 * mm))
    F.append(Paragraph("2026 年 10 月 · 内部资料", B.S["cover_meta"]))
    F.append(NextPageTemplate("main"))
    F.append(PageBreak())

    F.append(Paragraph("目录", B.S["h1"]))
    toc = TableOfContents()
    # 大标题（章）用整条浅蓝底 + 大号粗体，小标题只用灰色小字并缩进，
    # 两者一眼能分开。
    toc.levelStyles = [
        ParagraphStyle("t0", fontName=B.BOLD, fontSize=13.5, leading=21,
                       textColor=colors.HexColor("#1e3a8a"),
                       backColor=colors.HexColor("#e8f0fe"),
                       borderPadding=(4, 8, 4, 8),
                       leftIndent=0, spaceBefore=11, wordWrap="CJK"),
        ParagraphStyle("t1", fontName=B.BODY, fontSize=9.2, leading=13,
                       textColor=colors.HexColor("#606266"),
                       leftIndent=26, spaceBefore=1, wordWrap="CJK"),
    ]
    F.append(toc)
    F.append(PageBreak())

    with open(SRC, encoding="utf-8") as f:
        md = f.read()
    html = B.md_to_html(md)
    parser = B.FragParser()
    parser.feed(html)
    parser._flush()
    # md_to_html 把 # 和 ## 都映射成 h2，目录里会全挤在同一级。
    # 按「2.1 …」这种编号把二级小节标成 h3，只改目录层级。
    for fl in parser.out:
        toc = getattr(fl, "_toc", None)
        if toc and toc[0] == "h2" and re.match(r"^\d+\.\d+", toc[1]):
            fl._toc = ("h3", toc[1])
    print("  %-38s -> %3d flowables" % (os.path.basename(SRC), len(parser.out)))
    # 章标题从新页开始，避免章节标题单独落在页脚
    chapter_starts = ("二、自动布局", "三、电路参数优化", "四、自动布线")
    body = []
    for fl in parser.out:
        toc = getattr(fl, "_toc", None)
        if toc and any(toc[1].startswith(t) for t in chapter_starts):
            body.append(PageBreak())
        body.append(fl)
    F.extend(body)

    doc.multiBuild(F)
    print("\nOK ->", OUT_PDF)
    print("size: %d bytes" % os.path.getsize(OUT_PDF))


if __name__ == "__main__":
    build()
