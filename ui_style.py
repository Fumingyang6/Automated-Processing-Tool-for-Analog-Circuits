"""各功能页共用的界面样式与绘图字体。

配色跟主页保持一致：
主色 #2b6ef7 / 深色 #1e3a8a / 浅色 #dbeafe / 边框 #dcdfe6 / 页面底 #f5f7fa
"""

import os
import re
import sys

# matplotlib 的字体扫描认不出 .ttc，字体缓存里根本没有文泉驿，
# 图上写中文会变成方块。这里按路径手动注册一份，只在需要中文的地方用，
# 不去改全局 rcParams（项目里好几个模块都在用 matplotlib，改全局会影响它们的图）。
_CJK_FONT_PATHS = (
    # Windows 自带的中文字体
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    # Linux（文泉驿 / Noto）
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)
_cjk_font_prop = None
_cjk_font_loaded = False


def cjk_font_properties():
    """返回中文字体的 FontProperties；系统里没有就返回 None（用默认字体）"""
    global _cjk_font_prop, _cjk_font_loaded
    if not _cjk_font_loaded:
        _cjk_font_loaded = True
        from matplotlib import font_manager
        for path in _CJK_FONT_PATHS:
            if os.path.exists(path):
                font_manager.fontManager.addfont(path)
                _cjk_font_prop = font_manager.FontProperties(fname=path)
                break
    return _cjk_font_prop


# Qt 界面用的中文字体族：按系统给候选列表，逐个查 QFontDatabase 里
# 真实存在的字体，第一个命中的就是界面字体（找不到就返回第一个候选）。
_CJK_QT_CANDIDATES = {
    "win32": ("Microsoft YaHei", "SimHei", "WenQuanYi Micro Hei"),
    "darwin": ("PingFang SC", "Hiragino Sans GB", "WenQuanYi Micro Hei"),
}
_CJK_QT_CANDIDATES_DEFAULT = ("WenQuanYi Micro Hei", "Noto Sans CJK SC")
_cjk_qt_family = None


def cjk_font_family():
    """返回系统里实际可用的中文字体族名（给 QApplication.setFont 用）"""
    global _cjk_qt_family
    if _cjk_qt_family is None:
        from PyQt5.QtGui import QFontDatabase
        candidates = _CJK_QT_CANDIDATES.get(sys.platform, _CJK_QT_CANDIDATES_DEFAULT)
        available = set(QFontDatabase().families())
        _cjk_qt_family = next(
            (name for name in candidates if name in available), candidates[0]
        )
    return _cjk_qt_family


# ====================== 界面缩放 ======================
# DPI 自适应交给 Qt 的 High-DPI 缩放（main_ui.py 启动时设置），
# 这里只管用户手动调的那一档倍率，避免两套缩放叠加。
_SCALE_KEY = "ui/font_scale"
_SCALE_MIN = 0.8
_SCALE_MAX = 2.0
_SCALE_STEP = 0.1


def _settings():
    from PyQt5.QtCore import QSettings
    return QSettings("parms", "parms")


def ui_scale():
    """当前界面倍率（用户设置 × 环境变量 PARMS_UI_SCALE）"""
    try:
        scale = float(_settings().value(_SCALE_KEY, 1.0))
    except (TypeError, ValueError):
        scale = 1.0

    env = os.environ.get("PARMS_UI_SCALE")
    if env:
        try:
            scale *= float(env)
        except ValueError:
            pass
    return max(_SCALE_MIN, min(_SCALE_MAX, scale))


def font_px(base):
    """基准像素字号 → 当前倍率下的像素字号"""
    return max(9, int(round(base * ui_scale())))


def scale_px(base):
    """基准像素尺寸 → 当前倍率下的像素尺寸（控件宽高用）"""
    return max(1, int(round(base * ui_scale())))


def font_pt(base):
    """基准磅值 → 当前倍率下的磅值（给 QFont.setPointSize 用）"""
    return max(7, int(round(base * ui_scale())))


_FONT_SIZE_RE = re.compile(r"font-size\s*:\s*(\d+)px")
# 只缩放固定宽高（树行高、数字框箭头），不动 min-height：
# 各页的 min-height 是按原布局留的余量，跟着字号翻倍反而会把行撑破。
_SIZE_RE = re.compile(r"(?<![\w-])(width|height)\s*:\s*(\d+)px")


def scaled_qss(qss):
    """把 QSS 里的字号和固定宽高按当前倍率放大。

    QSS 里全是花括号，不能用 str.format；逐条正则替换最省事。
    固定高宽也要一起放大：比如树行高写死 24px，字号调大后行高不够，
    文字就会被上下裁掉。
    """
    qss = _FONT_SIZE_RE.sub(
        lambda m: "font-size: %dpx" % font_px(int(m.group(1))), qss)
    return _SIZE_RE.sub(
        lambda m: "%s: %dpx" % (m.group(1), scale_px(int(m.group(2)))), qss)


# 按控件 setStyleSheet 的样式没法从全局改，登记工厂函数，
# 调倍率时统一重新应用。
_styled_widgets = []


def register_style(widget, factory):
    """登记一个控件的样式工厂，立即应用；factory 每次返回最新 QSS"""
    entry = (widget, factory)
    _styled_widgets.append(entry)
    _apply_entry(entry)
    return widget


def _apply_entry(entry):
    widget, factory = entry
    try:
        widget.setStyleSheet(factory())
        return True
    except RuntimeError:
        # 页面已被 deleteLater 销毁，底层 C++ 对象不在了
        return False


def refresh_all_styles():
    """重新应用所有登记过的样式（切换字号倍率后调用）"""
    alive = []
    for entry in _styled_widgets:
        if _apply_entry(entry):
            alive.append(entry)
    _styled_widgets[:] = alive


def set_scale(scale):
    scale = max(_SCALE_MIN, min(_SCALE_MAX, round(float(scale), 2)))
    _settings().setValue(_SCALE_KEY, scale)


def scale_up():
    set_scale(ui_scale() + _SCALE_STEP)


def scale_down():
    set_scale(ui_scale() - _SCALE_STEP)


def reset_scale():
    set_scale(1.0)


def apply_ui_scale(app=None):
    """按当前倍率重设应用字体并刷新全部已登记样式"""
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import QApplication

    app = app or QApplication.instance()
    if app is not None:
        font = QFont(cjk_font_family())
        font.setPointSize(font_pt(11))
        app.setFont(font)
    refresh_all_styles()


PAGE_STYLE = """
#page {
    background-color: #f5f7fa;
}

QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e4e7ed;
    border-radius: 10px;
    margin-top: 13px;
    padding: 10px 8px 8px 8px;
    font-size: 15px;
    font-weight: bold;
    color: #1e3a8a;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
}

QLabel {
    color: #606266;
    font-size: 14px;
    font-weight: normal;
}

QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #dcdfe6;
    border-radius: 6px;
    min-height: 20px;
    color: #1a202c;
    font-size: 14px;
    selection-background-color: #2b6ef7;
    selection-color: #ffffff;
}
QLineEdit {
    padding: 4px 8px;
}
/* 数字框右侧得给上下箭头留出固定宽度，否则箭头会被 padding 挤变形 */
QSpinBox, QDoubleSpinBox {
    padding: 4px 2px 4px 8px;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    margin: 1px 1px 0 0;
    border-left: 1px solid #e4e7ed;
    border-top-right-radius: 5px;
    background-color: #f5f7fa;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    margin: 0 1px 1px 0;
    border-left: 1px solid #e4e7ed;
    border-bottom-right-radius: 5px;
    background-color: #f5f7fa;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #dbeafe;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    width: 7px;
    height: 7px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #2b6ef7;
}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    background-color: #f5f7fa;
    color: #a8abb2;
}

QPushButton {
    background-color: #f5f7fa;
    border: 1px solid #dcdfe6;
    border-radius: 6px;
    padding: 5px 14px;
    color: #606266;
    font-size: 14px;
}
QPushButton:hover {
    background-color: #ecf5ff;
    border-color: #2b6ef7;
    color: #2b6ef7;
}
QPushButton:pressed {
    background-color: #dbeafe;
}
QPushButton:disabled {
    background-color: #f5f7fa;
    border-color: #e4e7ed;
    color: #a8abb2;
}

/* 主操作按钮：浅蓝，不抢眼 */
QPushButton#primaryButton {
    background-color: #dbeafe;
    border: 1px solid #bfdbfe;
    border-radius: 8px;
    color: #1e3a8a;
    font-size: 15px;
    font-weight: bold;
    padding: 6px 22px;
}
QPushButton#primaryButton:hover {
    background-color: #bfdbfe;
    border-color: #93c5fd;
}
QPushButton#primaryButton:pressed {
    background-color: #a9cefd;
}
QPushButton#primaryButton:disabled {
    background-color: #eef4ff;
    border-color: #dbeafe;
    color: #a8abb2;
}

/* 顶部入口 / 返回按钮：和主页导航按钮同色系 */
QPushButton#entryButton {
    background-color: #dbeafe;
    border: none;
    border-radius: 8px;
    color: #1e3a8a;
    font-size: 14px;
    font-weight: bold;
    padding: 6px 14px;
}
QPushButton#entryButton:hover {
    background-color: #bfdbfe;
}
QPushButton#entryButton:pressed {
    background-color: #bfdbfe;
}

/* 紧凑按钮：用在空间紧张的地方（比如版图查看器的图层面板），
   和 entryButton 同色系，但内边距小很多，两个汉字也放得下 */
QPushButton#compactButton {
    background-color: #dbeafe;
    border: none;
    border-radius: 6px;
    color: #1e3a8a;
    font-size: 13px;
    font-weight: bold;
    padding: 5px 5px;
}
QPushButton#compactButton:hover {
    background-color: #bfdbfe;
}
QPushButton#compactButton:pressed {
    background-color: #a9cefd;
}

QTextEdit, QPlainTextEdit {
    background-color: #fbfcfe;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    padding: 4px 6px;
    font-family: "Microsoft YaHei", "WenQuanYi Micro Hei", monospace;
    font-size: 13px;
    color: #475569;
}

/* 左侧文件树 */
QTreeWidget {
    background-color: #ffffff;
    border: 1px solid #e4e7ed;
    border-radius: 10px;
    padding: 4px;
    font-size: 14px;
    color: #303133;
    outline: none;
}
QTreeWidget::item {
    height: 24px;
    border-radius: 6px;
}
QTreeWidget::item:hover {
    background-color: #f0f6ff;
}
QTreeWidget::item:selected {
    background-color: #dbeafe;
    color: #1e3a8a;
}
/* 焦点移到别处（点了右边图区/标签/按钮）但选中项没变时，
   用浅灰表示「还选着，但不是当前焦点」，避免蓝块一直杵在那儿 */
QTreeWidget::item:selected:!active {
    background-color: #e9edf2;
    color: #606266;
}
/* 缩进/展开箭头那一列 Qt 会用调色板里的高亮色单独刷一遍，
   不覆盖的话选中行左边会多出一块深蓝 */
QTreeWidget::branch:selected {
    background-color: #dbeafe;
}
QTreeWidget::branch:selected:!active {
    background-color: #e9edf2;
}

/* 右侧标签区 */
QTabWidget::pane {
    background-color: #ffffff;
    border: 1px solid #e4e7ed;
    border-radius: 10px;
    top: -1px;
}
QTabBar::tab {
    background-color: #eef1f5;
    border: 1px solid #e4e7ed;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 6px 14px;
    margin-right: 3px;
    font-size: 14px;
    color: #606266;
}
QTabBar::tab:hover {
    background-color: #e3ecfa;
    color: #1e3a8a;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #1e3a8a;
    font-weight: bold;
}
QTabBar::close-button {
    subcontrol-position: right;
}
"""
