import os
import sys
import warnings

if getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.join(sys._MEIPASS, 'site-packages'))


# ====================== Windows 中文路径修复 ======================
# PyQt5 在 Windows 上拿 Qt 安装路径时走了一遍 ANSI 代码页转换。项目路径里只要
# 带中文（比如 …\Desktop\芯片项目\…），QLibraryInfo 返回的插件目录就会变成
# 乱码，Qt 找不到 qwindows.dll，直接 abort()——进程静默退出（0xC0000409），
# 屏幕上没有任何提示，很难查。
#
# 这里把插件目录用环境变量显式指回去。Qt 读环境变量时走的是另一条转换路径，
# 中文能正确还原，于是绕开了上面那个 bug。必须在 QApplication 创建前设置。
if sys.platform == "win32":
    try:
        import PyQt5
        _qt_plugins = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")
        if os.path.isdir(os.path.join(_qt_plugins, "platforms")):
            os.environ.setdefault("QT_PLUGIN_PATH", _qt_plugins)
            os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH",
                                  os.path.join(_qt_plugins, "platforms"))
    except ImportError:
        pass  # 没装 PyQt5，后面那句 import 会给出更清楚的报错

# Windows 控制台默认是 GBK 代码页，子模块里 print 的 ✅ / ❌ 会让整个步骤崩掉
# （UnicodeEncodeError），尽管文件其实已经写好了。降级成 ? 比崩掉强。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass  # pythonw 启动时是 None，或者已经被重定向过
# =================================================================


from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QButtonGroup, QSizePolicy, QDockWidget, QToolButton,
    QInputDialog, QFileDialog, QMessageBox, QAction, QShortcut,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox, QLineEdit
)
from PyQt5.QtGui import (
    QFont, QPalette, QColor, QIcon, QPainter, QPixmap, QPainterPath,
    QDesktopServices, QKeySequence
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QRectF, QUrl, QSettings, QTimer


if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

# 将子目录添加到 sys.path，保证 import 能找到模块
sys.path.append(os.path.join(base_path, "ota_case1"))
sys.path.append(os.path.join(base_path, "analog_placement"))
sys.path.append(os.path.join(base_path, "rsmt_router"))
# 四个功能页。缺依赖时给一句人话提示再退出，
# 否则用户只会看到一段 ImportError 堆栈，不知道要装什么。
try:
    from device_generation.run import CircuitGenerator
    from ota_case1.ui import CircuitOptWindow
    from analog_placement.layout_ui import AutoLayoutWindow
    # 导入布局布线模块
    from rsmt_router.routing_page import RoutingPage
    from ui_style import (
        cjk_font_family, register_style, scaled_qss, apply_ui_scale,
        set_scale, ui_scale, font_pt, reset_scale, scale_up, scale_down,
    )
    from ui_widgets import FileTreePanel
except ImportError as exc:
    sys.stderr.write(
        "\n启动失败：缺少运行依赖\n"
        f"    {exc}\n\n"
        "在项目根目录执行下面这条装依赖：\n"
        "    pip install -r requirements.txt\n\n"
        "如果装过了还报同样的错，重点确认这几个包（旧版 requirements.txt 漏掉了）：\n"
        "    gdspy          —— 电路版图生成、版图查看器\n"
        "    dgl            —— 自动布局的 DGL 步骤\n"
        "    scikit-learn   —— 电路参数优化\n\n"
    )
    raise SystemExit(1) from None


# ====================== 功能页通用容器（带返回按钮） ======================
WRAPPER_TOP_BAR_STYLE = """
    QWidget {
        background-color: #ffffff;
        border-bottom: 1px solid #e4e7ed;
    }
    QPushButton {
        background-color: #f5f7fa;
        border: 1px solid #dcdfe6;
        border-radius: 6px;
        padding: 6px 16px;
        color: #606266;
        font-size: 14px;
    }
    QPushButton:hover {
        background-color: #ecf5ff;
        border-color: #2b6ef7;
        color: #2b6ef7;
    }
"""


class FunctionPageWrapper(QWidget):
    """带顶部返回栏的功能页容器，包裹原有功能模块"""
    go_home_signal = pyqtSignal()  # 返回主页的信号

    def __init__(self, page_title, content_widget, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 顶部导航栏
        top_bar = QWidget()
        top_bar.setFixedHeight(52)
        register_style(top_bar, lambda: scaled_qss(WRAPPER_TOP_BAR_STYLE))
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(20, 0, 20, 0)

        back_btn = QPushButton("← 返回主页")
        back_btn.clicked.connect(self.go_home_signal.emit)

        title_label = QLabel(page_title)
        register_style(
            title_label,
            lambda: scaled_qss(
                "font-size: 17px; font-weight: bold; color: #1a202c;"))
        title_label.setAlignment(Qt.AlignCenter)

        # 占位弹簧，让标题居中
        spacer = QWidget()
        spacer.setFixedWidth(80)

        top_layout.addWidget(back_btn)
        top_layout.addWidget(title_label, 1)
        top_layout.addWidget(spacer)

        main_layout.addWidget(top_bar)
        main_layout.addWidget(content_widget, 1)


# ====================== 主页样式与图片控件 ======================

# 蓝色色阶：主色 #2b6ef7 / 深色 #1e3a8a / 浅色 #dbeafe / 边框 #bfdbfe / 背景 #f5f7fa
HOME_STYLE = """
#homePage {
    background-color: #f5f7fa;
}

/* 顶部通栏横幅：主色到深色横向渐变 */
#header {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                      stop:0 #2b6ef7, stop:1 #1e5bbf);
    border-radius: 12px;
}
#headerTitle {
    color: #ffffff;
    font-size: 36px;
    font-weight: bold;
}
#headerSubtitle {
    color: #ffffff;
    font-size: 19px;
}

/* 左侧导航按钮 */
#navBar QPushButton {
    background-color: #dbeafe;
    color: #1e3a8a;
    border: none;
    border-radius: 10px;
    font-size: 18px;
    font-weight: bold;
    padding: 10px 12px;
}
#navBar QPushButton:hover {
    background-color: #bfdbfe;
}
#navBar QPushButton:checked {
    background-color: #1e3a8a;
    color: #ffffff;
}

/* 右侧内容区外框 */
#contentFrame {
    background-color: #ffffff;
    border: 2px solid #bfdbfe;
    border-radius: 12px;
}

/* 底部页脚 */
#footer {
    background-color: #1e3a8a;
    color: #ffffff;
    font-size: 13px;
    border-radius: 8px;
}
"""


def circular_pixmap(image_path, size, padding=9):
    """白底圆形徽标：logo 等比缩放后完整放进圈内（不裁剪）"""
    target = QPixmap(size, size)
    target.fill(Qt.transparent)

    painter = QPainter(target)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)

    circle = QPainterPath()
    circle.addEllipse(0, 0, size, size)
    painter.fillPath(circle, QColor("#ffffff"))
    painter.setClipPath(circle)

    src = QPixmap(image_path)
    if not src.isNull():
        inner = size - 2 * padding
        fitted = src.scaled(inner, inner, Qt.KeepAspectRatio,
                            Qt.SmoothTransformation)
        painter.drawPixmap((size - fitted.width()) // 2,
                           (size - fitted.height()) // 2, fitted)
    painter.end()
    return target


class RoundedImage(QWidget):
    """等比缩放铺满容器、按圆角矩形裁剪的图片控件（无留白）"""

    def __init__(self, image_path, radius=10, parent=None):
        super().__init__(parent)
        self._radius = radius
        self._pixmap = QPixmap(image_path)
        self._scaled = None
        self._scaled_for = QSize()

    def paintEvent(self, event):
        if self._pixmap.isNull() or self.width() <= 0 or self.height() <= 0:
            return

        # 原图很大，缩放很贵，只在尺寸变化时重算一次
        if self._scaled is None or self._scaled_for != self.size():
            # 等比放大到能铺满整个容器，再居中裁剪掉多余部分
            self._scaled = self._pixmap.scaled(
                self.size(), Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation)
            self._scaled_for = self.size()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), self._radius, self._radius)
        painter.setClipPath(clip)

        offset_x = (self._scaled.width() - self.width()) // 2
        offset_y = (self._scaled.height() - self.height()) // 2
        painter.drawPixmap(0, 0, self._scaled,
                           offset_x, offset_y, self.width(), self.height())


# ====================== 主页（HomePage） ======================
class HomePage(QWidget):
    """软件主页：顶部横幅 + 左侧导航 + 右侧图片区 + 底部页脚"""
    # 四个跳转信号，分别对应四个功能
    jump_to_gen = pyqtSignal()
    jump_to_opt = pyqtSignal()
    jump_to_place = pyqtSignal()
    jump_to_route = pyqtSignal()

    # (按钮文字, 对应信号)，顺序即界面上的排列顺序
    NAV_ITEMS = (
        ("电路版图生成", "jump_to_gen"),
        ("自动布局", "jump_to_place"),
        ("电路参数优化", "jump_to_opt"),
        ("自动布线", "jump_to_route"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homePage")
        register_style(self, lambda: scaled_qss(HOME_STYLE))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(16)

        root_layout.addWidget(self._build_header())
        root_layout.addWidget(self._build_body(), 1)
        root_layout.addWidget(self._build_footer())

    def _build_header(self):
        """顶部横幅：圆形logo与文字作为一个整体水平居中"""
        header = QWidget()
        header.setObjectName("header")
        header.setFixedHeight(170)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(28, 0, 28, 0)
        header_layout.setSpacing(0)

        logo_label = QLabel()
        logo_label.setFixedSize(104, 104)
        logo_path = os.path.join(base_path, "assets", "homepage.png")
        if os.path.exists(logo_path):
            logo_label.setPixmap(circular_pixmap(logo_path, 104))

        title_label = QLabel("模拟电路自动化设计工具")
        title_label.setObjectName("headerTitle")

        version_label = QLabel("Parms")
        version_label.setObjectName("headerSubtitle")

        # 副标题放在主标题正下方，两行文字居中
        text_group = QWidget()
        text_layout = QVBoxLayout(text_group)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)
        text_layout.addWidget(title_label, 0, Qt.AlignHCenter)
        text_layout.addWidget(version_label, 0, Qt.AlignHCenter)

        header_layout.addStretch()
        header_layout.addWidget(logo_label, 0, Qt.AlignVCenter)
        header_layout.addSpacing(26)
        header_layout.addWidget(text_group, 0, Qt.AlignVCenter)
        header_layout.addStretch()
        return header

    def _build_body(self):
        """主体区域：左侧固定导航栏 + 右侧自适应图片区"""
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(16)

        # 导航区与图片区按 2:3 分配宽度：按钮不再挤成窄条，
        # 图片区也不会独占大半个窗口；窗口变宽时两边同步放大。
        body_layout.addWidget(self._build_nav(), 2)

        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(2, 2, 2, 2)
        content_layout.setSpacing(0)
        content_layout.addWidget(
            RoundedImage(os.path.join(base_path, "xpian.png"), radius=10)
        )

        body_layout.addWidget(content_frame, 3)
        return body

    def _build_nav(self):
        """左侧导航栏：四个功能按钮，在整列内均匀分布"""
        nav_bar = QWidget()
        nav_bar.setObjectName("navBar")
        # 宽度完全按 2:3 与图片区分配，不再设上限：上限会让按钮区在
        # 宽屏上缩成窄条、图片重新占满大半个窗口。参考首页设计稿，
        # 左侧导航约占总宽 40%，只保留一个最小宽度防止小窗口挤坏。
        nav_bar.setMinimumWidth(300)
        nav_bar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        nav_layout = QVBoxLayout(nav_bar)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(18)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        # 按钮之间只留固定间距，整列由按钮平分撑满，
        # 这样四个按钮的上下边正好和右侧图片区对齐（不用弹簧，否则间隔会大到 70px 以上）
        for text, signal_name in self.NAV_ITEMS:
            button = QPushButton(text)
            button.setCheckable(True)
            button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(getattr(self, signal_name).emit)
            self.nav_group.addButton(button)
            nav_layout.addWidget(button)
        return nav_bar

    def clear_nav_selection(self):
        """取消导航栏的选中态：避免看起来像默认选中了某一项"""
        # 互斥的 QButtonGroup 不允许直接取消选中，得先临时关掉互斥
        self.nav_group.setExclusive(False)
        for button in self.nav_group.buttons():
            button.setChecked(False)
        self.nav_group.setExclusive(True)

    def _build_footer(self):
        """底部页脚"""
        footer = QLabel("版本 v0.6 | 团队：CEDA | WHUT")
        footer.setObjectName("footer")
        footer.setFixedHeight(36)
        footer.setAlignment(Qt.AlignCenter)
        return footer


# ====================== 顶部菜单栏 ======================
# (菜单名, [条目, ...])，条目为 None 表示分隔线。
# 条目是 (动作 ID, 显示文字, 快捷键或 None)。
# 「构建」菜单的动作会实际执行对应流程（见 on_menu_action）。
MENU_ITEMS = (
    ("文件（F）", (
        ("open_netlist", "打开网表…", "Ctrl+O"),
        ("open_result_dir", "打开结果目录", None),
        None,
        ("quit", "退出", "Ctrl+Q"),
    )),
    ("编辑（E）", (
        ("undo", "撤销", "Ctrl+Z"),
        ("redo", "重做", "Ctrl+Y"),
        None,
        ("clear_log", "清除执行日志", None),
    )),
    ("构建（B）", (
        ("build_all", "一键运行全部流程", None),
        None,
        ("build_dgl", "网表转 DGL 图", None),
        ("build_sym", "提取匹配约束", None),
        ("build_layout", "运行自动布局优化", None),
        ("build_route", "运行自动布线", None),
    )),
    ("工具（T）", (
        ("workdir", "打开工作目录", "Ctrl+D"),
        None,
        ("preferences", "首选项…", None),
    )),
    ("窗口（W）", (
        ("win_home", "主页", None),
        None,
        ("win_gen", "电路版图生成", None),
        ("win_opt", "电路参数优化", None),
        ("win_place", "自动布局", None),
        ("win_route", "自动布线", None),
    )),
    ("帮助（H）", (
        ("help_manual", "使用说明", "F1"),
        None,
        ("help_about", "关于 parms", None),
    )),
)

# 主窗口 / 菜单栏 / 下拉菜单样式（字号由 scaled_qss 统一缩放）
MAIN_WINDOW_STYLE = """
    QMainWindow {
        background-color: #f5f7fa;
    }
    QMenuBar {
        background-color: #e9edf2;
        border-bottom: 1px solid #dcdfe6;
        padding: 2px 6px;
        font-size: 14px;
        color: #303133;
    }
    QMenuBar::item {
        background: transparent;
        color: #303133;
        padding: 5px 5px;
        border-radius: 6px;
    }
    QMenuBar::item:selected, QMenuBar::item:pressed {
        background-color: #dbeafe;
        color: #1e3a8a;
    }
    QMenu {
        background-color: #ffffff;
        border: 1px solid #e4e7ed;
        border-radius: 8px;
        padding: 4px;
        font-size: 14px;
    }
    QMenu::item {
        padding: 6px 26px 6px 16px;
        border-radius: 6px;
        color: #303133;
    }
    QMenu::item:selected {
        background-color: #dbeafe;
        color: #1e3a8a;
    }
    QMenu::item:disabled {
        color: #a8abb2;
    }
    QMenu::separator {
        height: 1px;
        background-color: #e4e7ed;
        margin: 4px 8px;
    }
"""


# ====================== 一键全流程配置窗口 ======================
class BuildAllDialog(QDialog):
    """一键运行全部流程的输入配置窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("一键运行全部流程")
        self.setMinimumWidth(760)
        self.settings = QSettings("parms", "parms")

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        intro = QLabel(
            "将按以下顺序执行四个步骤：\n"
            "  1. 电路版图生成（网表 → GDS）\n"
            "  2. 自动布局（网表 → DGL → 匹配约束 → 布局优化）\n"
            "  3. 电路参数优化（加载 Actor 模型生成最优参数）\n"
            "  4. 自动布线（布线网表 + 布局文件 → 走线 GDS）\n\n"
            "步骤 1、2 共用同一个网表；步骤 3、4 使用各自的输入。\n"
            "执行过程中界面会自动切到对应功能页，请不要手动切页。")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        form.setSpacing(8)

        default_nets = os.path.join(base_path, "rsmt_router", "nets.txt")
        default_layout = os.path.join(base_path, "rsmt_router", "CP_OP2.txt")

        self.netlist_edit = self._add_path_row(
            form, "网表文件（步骤 1、2）：",
            self._saved("build/netlist"),
            "选择网表文件",
            "网表文件 (*.sp *.cdl *.spice *.txt);;所有文件 (*)")
        self.model_edit = self._add_path_row(
            form, "Actor 模型（步骤 3）：",
            self._saved("build/model"),
            "选择参数优化模型文件",
            "模型文件 (*.pth *.pkl);;所有文件 (*)")
        self.nets_edit = self._add_path_row(
            form, "布线网表（步骤 4）：",
            self._saved("build/nets") or default_nets,
            "选择布线网表文件", "文本文件 (*.txt);;所有文件 (*)")
        self.layout_edit = self._add_path_row(
            form, "布线布局文件（步骤 4）：",
            self._saved("build/layout") or default_layout,
            "选择布线布局文件", "文本文件 (*.txt);;所有文件 (*)")

        self.node_type_combo = QComboBox()
        self.node_type_combo.addItems(["device级节点（器件级）", "pin级节点"])
        saved_index = self.settings.value("build/node_type", 1, type=int)
        self.node_type_combo.setCurrentIndex(0 if saved_index == 0 else 1)
        form.addRow("参数优化节点类型：", self.node_type_combo)

        layout.addLayout(form)

        note = QLabel(
            "提示：参数优化的模型必须是训练好的 Actor 智能体（.pth/.pkl）；"
            "op_pth 目录下的权重是性能仿真器，不能用于这一步。")
        note.setWordWrap(True)
        note.setStyleSheet("color: #64748b;")
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("开始运行")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _saved(self, key):
        path = self.settings.value(key, "", type=str)
        if path and os.path.exists(path):
            return path
        return ""

    def _add_path_row(self, form, label, path, title, file_filter):
        edit = QLineEdit(path)
        edit.setPlaceholderText("请选择文件")
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(edit, 1)
        browse = QPushButton("浏览…")
        browse.setCursor(Qt.PointingHandCursor)
        browse.clicked.connect(
            lambda: self._browse(edit, title, file_filter))
        row.addWidget(browse)
        form.addRow(label, row)
        return edit

    def _browse(self, edit, title, file_filter):
        current = edit.text().strip()
        start = os.path.dirname(current) if os.path.exists(current) else ""
        path, _ = QFileDialog.getOpenFileName(self, title, start, file_filter)
        if path:
            edit.setText(path)

    def accept(self):
        checks = (
            (self.netlist_edit, "网表文件"),
            (self.model_edit, "Actor 模型"),
            (self.nets_edit, "布线网表"),
            (self.layout_edit, "布线布局文件"),
        )
        for edit, label in checks:
            path = edit.text().strip()
            if not path or not os.path.exists(path):
                QMessageBox.warning(
                    self, "输入不完整",
                    f"请选择有效的{label}。")
                return

        self.settings.setValue("build/netlist",
                               self.netlist_edit.text().strip())
        self.settings.setValue("build/model",
                               self.model_edit.text().strip())
        self.settings.setValue("build/nets",
                               self.nets_edit.text().strip())
        self.settings.setValue("build/layout",
                               self.layout_edit.text().strip())
        self.settings.setValue("build/node_type",
                               self.node_type_combo.currentIndex())
        super().accept()

    def paths(self):
        return {
            "netlist": self.netlist_edit.text().strip(),
            "model": self.model_edit.text().strip(),
            "nets": self.nets_edit.text().strip(),
            "layout": self.layout_edit.text().strip(),
            "node_type_index": self.node_type_combo.currentIndex(),
        }


# ====================== 主窗口 ======================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("parms")
        self.resize(1120, 760)

        self.setObjectName("parms")

        # 当前页面内容控件（菜单动作按能力分发到它们）
        self.page_contents = {}
        self.menu_actions = {}
        self.menu_menus = {}
        self._scale_shortcuts = []
        # 一键全流程的运行状态；非 None 表示正在执行
        self._flow = None

        # 整体浅色背景 + 菜单栏/下拉菜单样式
        register_style(self, lambda: scaled_qss(MAIN_WINDOW_STYLE))

        self.build_menu_bar()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 用堆叠窗口管理器替代标签页，实现页面切换
        # 忽略各功能页自身的尺寸要求，否则隐藏页会把主窗口顶大，1200x800 压不下去
        self.stack = QStackedWidget()
        self.stack.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        main_layout.addWidget(self.stack)

        # 0号页面：主页
        self.home_page = HomePage()
        self.stack.addWidget(self.home_page)

        # 绑定主页跳转信号
        self.home_page.jump_to_gen.connect(lambda: self.switch_to_page(1))
        self.home_page.jump_to_opt.connect(lambda: self.switch_to_page(2))
        self.home_page.jump_to_place.connect(lambda: self.switch_to_page(3))
        self.home_page.jump_to_route.connect(lambda: self.switch_to_page(4))

        # 工作目录侧栏（默认隐藏）+ 字号快捷键
        self.build_work_dir_dock()
        self._install_scale_shortcuts()

        # 初始化四个功能页（首次进入时会重新创建，保证刷新）
        self._init_function_pages()

    def build_menu_bar(self):
        """顶部菜单栏：所有菜单都接上实际动作"""
        menu_bar = self.menuBar()
        # 强制用窗口内菜单栏，免得某些桌面环境把它挪到系统全局顶栏去
        menu_bar.setNativeMenuBar(False)

        for title, items in MENU_ITEMS:
            menu = menu_bar.addMenu(title)
            self.menu_menus[title] = menu

            for item in items:
                if item is None:
                    menu.addSeparator()
                    continue

                action_id, text, shortcut = item
                action = QAction(text, self)
                if shortcut:
                    action.setShortcut(QKeySequence(shortcut))
                action.triggered.connect(
                    lambda _checked=False, aid=action_id:
                    self.on_menu_action(aid))

                menu.addAction(action)
                self.menu_actions[action_id] = action

        self.menu_actions["workdir"].setCheckable(True)
        self.menu_actions["workdir"].setChecked(False)

    # ==================== 工作目录侧栏 ====================
    def build_work_dir_dock(self):
        """左侧工作目录树（默认隐藏），菜单和菜单栏角上的按钮都能开关"""
        self.work_dock = QDockWidget("工作目录", self)
        self.work_dock.setObjectName("workDirDock")
        self.work_dock.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.work_tree = FileTreePanel(
            base_path, title="工作目录", hide_callback=self.work_dock.hide)
        self.work_tree.file_activated.connect(self.open_work_file)
        self.work_dock.setWidget(self.work_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.work_dock)
        self.work_dock.hide()
        self.work_dock.visibilityChanged.connect(self.on_work_dock_visibility)

        # 菜单栏右上角的常驻按钮：dock 藏起来之后也能把它叫出来
        self.dock_toggle_btn = QToolButton()
        self.dock_toggle_btn.setCheckable(True)
        self.dock_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.dock_toggle_btn.setToolTip("显示 / 隐藏左侧工作目录")
        self.dock_toggle_btn.setText("📁 显示目录")
        self.dock_toggle_btn.clicked.connect(
            lambda checked: self.set_work_dock_visible(checked))
        self.menuBar().setCornerWidget(
            self.dock_toggle_btn, Qt.TopRightCorner)

        self.menu_actions["workdir"].toggled.connect(
            self.set_work_dock_visible)

    def set_work_dock_visible(self, visible):
        self.work_dock.setVisible(bool(visible))

    def on_work_dock_visibility(self, visible):
        action = self.menu_actions.get("workdir")
        if action is not None and action.isChecked() != visible:
            action.setChecked(visible)
        self.dock_toggle_btn.setChecked(visible)
        self.dock_toggle_btn.setText("📁 隐藏目录" if visible else "📁 显示目录")

    def open_work_file(self, path):
        """双击工作目录树里的文件：交给系统默认程序打开"""
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    # ==================== 字号快捷键 ====================
    def _install_scale_shortcuts(self):
        bindings = (
            ("Ctrl+=", self.scale_ui_up),
            ("Ctrl++", self.scale_ui_up),
            ("Ctrl+-", self.scale_ui_down),
            ("Ctrl+0", self.scale_ui_reset),
        )
        for keys, slot in bindings:
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.activated.connect(slot)
            self._scale_shortcuts.append(shortcut)

    def scale_ui_up(self):
        scale_up()
        apply_ui_scale()
        self.refresh_actions()

    def scale_ui_down(self):
        scale_down()
        apply_ui_scale()
        self.refresh_actions()

    def scale_ui_reset(self):
        reset_scale()
        apply_ui_scale()
        self.refresh_actions()

    # ==================== 菜单动作分发 ====================
    def current_content(self):
        """当前功能页的内容控件（0 号主页返回 None）"""
        return self.page_contents.get(self.stack.currentIndex())

    def refresh_actions(self):
        """按当前页面的能力启停菜单项"""
        if not self.menu_actions:
            return

        # 全流程运行期间锁住会打断流程的菜单动作
        if self._flow is not None:
            for action_id in (
                    "open_netlist", "open_result_dir", "undo", "redo",
                    "clear_log", "build_all", "build_dgl", "build_sym",
                    "build_layout", "build_route",
                    "win_home", "win_gen", "win_opt", "win_place",
                    "win_route"):
                action = self.menu_actions.get(action_id)
                if action is not None:
                    action.setEnabled(False)
            return

        page = self.current_content()
        self.menu_actions["open_netlist"].setEnabled(
            page is not None and hasattr(page, "open_netlist"))
        self.menu_actions["open_result_dir"].setEnabled(
            page is not None and hasattr(page, "open_result_dir"))
        self.menu_actions["undo"].setEnabled(
            page is not None
            and callable(getattr(page, "can_undo", None))
            and page.can_undo())
        self.menu_actions["redo"].setEnabled(
            page is not None
            and callable(getattr(page, "can_redo", None))
            and page.can_redo())
        self.menu_actions["clear_log"].setEnabled(
            page is not None and hasattr(page, "clear_log"))

        # 构建菜单：对应模块后台有任务时置灰，避免重复启动
        auto_page = self.page_contents.get(3)
        auto_busy = (auto_page is not None
                     and self._page_busy(auto_page))
        for action_id in ("build_all", "build_dgl", "build_sym",
                          "build_layout"):
            self.menu_actions[action_id].setEnabled(not auto_busy)

        route_page = self.page_contents.get(4)
        self.menu_actions["build_route"].setEnabled(
            not (route_page is not None and self._page_busy(route_page)))

    def on_menu_action(self, action_id):
        if action_id == "quit":
            self.close()
        elif action_id == "open_netlist":
            self.menu_open_netlist()
        elif action_id == "open_result_dir":
            page = self.current_content()
            if page is not None and hasattr(page, "open_result_dir"):
                page.open_result_dir()
        elif action_id in ("undo", "redo"):
            page = self.current_content()
            method = getattr(page, action_id, None)
            if callable(method):
                method()
            self.refresh_actions()
        elif action_id == "clear_log":
            page = self.current_content()
            if page is not None and hasattr(page, "clear_log"):
                page.clear_log()
        elif action_id == "workdir":
            self.set_work_dock_visible(
                self.menu_actions["workdir"].isChecked())
        elif action_id == "preferences":
            self.show_preferences()
        elif action_id == "win_home":
            self.go_back_home()
        elif action_id == "win_gen":
            self.switch_to_page(1)
        elif action_id == "win_opt":
            self.switch_to_page(2)
        elif action_id == "win_place":
            self.switch_to_page(3)
        elif action_id == "win_route":
            self.switch_to_page(4)
        elif action_id == "help_manual":
            self.open_manual()
        elif action_id == "help_about":
            QMessageBox.about(
                self, "关于 parms",
                "模拟电路自动化设计工具\n\n"
                "版本 v0.6\n团队：CEDA | WHUT")
        elif action_id == "build_all":
            self.build_all()
        elif action_id == "build_dgl":
            self.build_dgl()
        elif action_id == "build_sym":
            self.build_sym()
        elif action_id == "build_layout":
            self.build_layout()
        elif action_id == "build_route":
            self.build_route()

    # ==================== 构建菜单 ====================
    @staticmethod
    def _page_busy(page):
        checker = getattr(page, "_worker_running", None)
        return bool(callable(checker) and checker())

    def _warn_build_busy(self):
        QMessageBox.information(
            self, "任务进行中",
            "当前模块还有任务在运行，请等它结束后再执行构建操作。")

    def _auto_layout_page(self):
        """返回自动布局页；不在该页时先切过去（切页会按既有逻辑重建页面）"""
        page = self.current_content()
        if isinstance(page, AutoLayoutWindow):
            return page
        self.switch_to_page(3)
        return self.current_content()

    def _routing_page(self):
        """返回自动布线页；不在该页时先切过去"""
        page = self.current_content()
        if isinstance(page, RoutingPage):
            return page
        self.switch_to_page(4)
        return self.current_content()

    def _netlist_start_dir(self):
        start = getattr(self, "_last_netlist_dir", None)
        if start and os.path.isdir(start):
            return start
        return os.path.join(base_path, "analog_placement", "mycase")

    def _ask_open_file(self, title, start_dir, file_filter):
        path, _ = QFileDialog.getOpenFileName(
            self, title, start_dir, file_filter)
        return path

    def _need_auto_page(self):
        """取自动布局页并检查是否忙；不可用时返回 None"""
        page = self._auto_layout_page()
        if page is None:
            return None
        if self._page_busy(page):
            self._warn_build_busy()
            return None
        return page

    def build_dgl(self):
        """构建 → 网表转 DGL 图"""
        page = self._need_auto_page()
        if page is None:
            return

        netlist = page.cdl_input_edit.text().strip()
        if not netlist or not os.path.exists(netlist):
            netlist = self._ask_open_file(
                "选择要转换的网表", self._netlist_start_dir(),
                "网表文件 (*.sp *.cdl *.spice *.txt);;所有文件 (*)")
            if not netlist:
                return
            self._last_netlist_dir = os.path.dirname(netlist)
            page.cdl_input_edit.setText(netlist)
            page.dgl_output_edit.setText(
                os.path.splitext(netlist)[0] + ".dgl")

        # 只填了网表、没填输出路径时按同名 .dgl 自动补齐
        if not page.dgl_output_edit.text().strip():
            page.dgl_output_edit.setText(
                os.path.splitext(netlist)[0] + ".dgl")

        page.tabs.setCurrentIndex(0)
        page.convert_to_dgl()

    def build_sym(self):
        """构建 → 提取匹配约束"""
        page = self._need_auto_page()
        if page is None:
            return

        dgl_path = page.dgl_input_edit.text().strip()
        if not dgl_path or not os.path.exists(dgl_path):
            dgl_path = self._ask_open_file(
                "选择 DGL 图文件",
                os.path.join(base_path, "analog_placement"),
                "DGL 文件 (*.dgl);;所有文件 (*)")
            if not dgl_path:
                return
            page.dgl_input_edit.setText(dgl_path)

        netlist = page.netlist_input_edit.text().strip()
        if not netlist or not os.path.exists(netlist):
            netlist = self._ask_open_file(
                "选择与 DGL 对应的原始网表", self._netlist_start_dir(),
                "网表文件 (*.sp *.cdl *.spice *.txt);;所有文件 (*)")
            if not netlist:
                return
            self._last_netlist_dir = os.path.dirname(netlist)
            page.netlist_input_edit.setText(netlist)

        page.tabs.setCurrentIndex(0)
        page.extract_constraint()

    def build_layout(self):
        """构建 → 运行自动布局优化"""
        page = self._need_auto_page()
        if page is None:
            return

        netlist = page.layout_netlist_edit.text().strip()
        if not netlist or not os.path.exists(netlist):
            netlist = self._ask_open_file(
                "选择带约束的网表",
                os.path.join(base_path, "analog_placement"),
                "网表文件 (*.sp *.cdl *.spice *.txt);;所有文件 (*)")
            if not netlist:
                return
            page.layout_netlist_edit.setText(netlist)

        sym_path = page.sym_input_edit.text().strip()
        if not sym_path or not os.path.exists(sym_path):
            sym_path = self._ask_open_file(
                "选择约束文件(.sym)",
                os.path.join(base_path, "analog_placement"),
                "约束文件 (*.sym);;所有文件 (*)")
            if not sym_path:
                return
            page.sym_input_edit.setText(sym_path)

        page.tabs.setCurrentIndex(1)
        page.run_layout()

    def build_route(self):
        """构建 → 运行自动布线（每次选择网表和布局文件）"""
        page = self._routing_page()
        if page is None:
            return
        if self._page_busy(page):
            self._warn_build_busy()
            return

        router_dir = os.path.join(base_path, "rsmt_router")
        current_nets = page.nets_edit.text().strip()
        start_dir = (os.path.dirname(current_nets)
                     if os.path.exists(current_nets) else router_dir)
        nets = self._ask_open_file(
            "选择布线网表文件", start_dir,
            "文本文件 (*.txt);;所有文件 (*)")
        if not nets:
            return

        current_layout = page.layout_edit.text().strip()
        layout_start = (os.path.dirname(current_layout)
                        if os.path.exists(current_layout)
                        else os.path.dirname(nets))
        layout = self._ask_open_file(
            "选择布局文件", layout_start,
            "文本文件 (*.txt);;所有文件 (*)")
        if not layout:
            return

        page.nets_edit.setText(nets)
        page.layout_edit.setText(layout)
        page.nets_path = nets
        page.layout_path = layout
        page.refresh_tree()
        page.run_pipeline()

    # ---------- 一键运行全部流程 ----------
    def build_all(self):
        """构建 → 一键运行全部流程

        顺序：电路版图生成 → 自动布局 → 电路参数优化 → 自动布线。
        四个模块的输入输出并不互通，所以先在一个配置窗口里把各自的
        输入选好，再按顺序自动执行；任一步失败就停在那一页。
        """
        if self._flow is not None:
            QMessageBox.information(
                self, "流程运行中", "一键运行全部流程正在执行，请等待完成。")
            return

        # 有后台任务在跑时不允许启动，避免两个流程抢同一批文件
        for index in (1, 2, 3, 4):
            page = self.page_contents.get(index)
            if page is not None and self._page_busy(page):
                self._warn_build_busy()
                return

        dialog = BuildAllDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return

        # 页面不再重建：保留各模块已有的输入和撤销记录，
        # 全流程要用的路径会在各步骤里显式覆盖。
        self._flow = {
            "paths": dialog.paths(),
            "completed": [],
            "failed": None,
            "timer": None,
        }
        self.refresh_actions()
        self._build_flow_step1()

    @staticmethod
    def _flow_error_line(text, limit=120):
        """取错误信息的第一行，避免汇总窗口被 traceback 撑爆"""
        text = (text or "").strip()
        if text.startswith("[ERROR]"):
            text = text[len("[ERROR]"):].strip()
        line = text.splitlines()[0].strip() if text else ""
        return line[:limit]

    def _build_flow_fail(self, step_name, message):
        if self._flow is None:
            return
        self._flow["failed"] = (step_name, message)
        self._finish_build_flow()

    def _finish_build_flow(self):
        """结束流程：恢复菜单，弹出一次汇总"""
        flow = self._flow
        if flow is None:
            return
        self._flow = None
        # 中途失败/超时也要恢复参数优化页的静默开关
        opt_page = self.page_contents.get(2)
        if opt_page is not None:
            opt_page.silent_mode = False
        timer = flow.get("timer")
        if timer is not None:
            try:
                timer.stop()
                timer.deleteLater()
            except RuntimeError:
                # 定时器可能已经被 Qt 回收，忽略即可
                pass
        self.refresh_actions()

        completed = dict(flow.get("completed", []))
        failed = flow.get("failed")
        lines = ["一键运行全部流程已中止。" if failed
                 else "一键运行全部流程已完成。", ""]

        for name in ("电路版图生成", "自动布局", "电路参数优化", "自动布线"):
            if name in completed:
                lines.append(f"✅ {name}")
                detail = completed[name]
                if detail:
                    lines.append("   " + detail.replace("\n", "\n   "))
            elif failed is not None and failed[0] == name:
                lines.append(f"❌ {name}：{failed[1]}")
            else:
                lines.append(f"⏭ {name}：未执行")
            lines.append("")

        text = "\n".join(lines).rstrip()
        if failed is not None:
            QMessageBox.warning(self, "全流程已中止", text)
        else:
            QMessageBox.information(self, "全流程完成", text)

    def _build_flow_step1(self):
        """步骤1：电路版图生成"""
        netlist = self._flow["paths"]["netlist"]
        try:
            self.stack.setCurrentIndex(1)
            QApplication.processEvents()
            page = self.page_contents[1]
            page.open_netlist(netlist)
            result = page.run_netlist_generation(interactive=False)
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}

        if not result.get("ok"):
            self._build_flow_fail(
                "电路版图生成", result.get("error") or "生成失败")
            return

        self._flow["completed"].append((
            "电路版图生成",
            f"成功 {result.get('success', 0)} 个，失败 {result.get('failed', 0)} 个\n"
            f"输出：{result.get('output_dir', '')}"))
        self._build_flow_step2()

    def _build_flow_step2(self):
        """步骤2：自动布局（转 DGL → 提取约束 → 布局优化）"""
        netlist = self._flow["paths"]["netlist"]
        dgl_path = os.path.splitext(netlist)[0] + ".dgl"
        sym_path = ""
        out_netlist = ""
        try:
            self.stack.setCurrentIndex(3)
            QApplication.processEvents()
            page = self.page_contents[3]
            page.cdl_input_edit.setText(netlist)
            page.dgl_output_edit.setText(dgl_path)
            page.tabs.setCurrentIndex(0)

            if not page.convert_to_dgl(interactive=False):
                self._build_flow_fail("自动布局", "网表转 DGL 图失败")
                return
            if not page.extract_constraint(interactive=False):
                self._build_flow_fail("自动布局", "匹配约束提取失败")
                return

            sym_path = page.sym_input_edit.text().strip()
            out_netlist = page.layout_netlist_edit.text().strip()
            page.tabs.setCurrentIndex(1)
            QApplication.processEvents()
            page.run_layout()
            worker = page.worker
            if worker is None or not worker.isRunning():
                self._build_flow_fail("自动布局", "布局优化未能启动")
                return
        except Exception as exc:
            self._build_flow_fail("自动布局", str(exc))
            return

        self._flow["layout_paths"] = (dgl_path, sym_path, out_netlist)
        self._wait_for_page_worker(
            page, "worker", self._build_flow_after_layout, "自动布局")

    def _build_flow_after_layout(self):
        if self._flow is None:
            return
        page = self.page_contents[3]
        if not getattr(page, "last_layout_ok", False):
            detail = self._flow_error_line(
                getattr(page, "last_layout_error", ""))
            message = "布局优化失败，详见页面执行日志"
            if detail:
                message = f"布局优化失败：{detail}"
            self._build_flow_fail("自动布局", message)
            return

        dgl_path, sym_path, out_netlist = self._flow["layout_paths"]
        self._flow["completed"].append((
            "自动布局",
            f"DGL：{dgl_path}\n"
            f"约束：{sym_path}\n"
            f"带约束网表：{out_netlist}\n"
            "布局优化已完成"))
        self._build_flow_step3()

    def _build_flow_step3(self):
        """步骤3：电路参数优化"""
        paths = self._flow["paths"]
        try:
            self.stack.setCurrentIndex(2)
            QApplication.processEvents()
            page = self.page_contents[2]
            index = paths.get("node_type_index", 1)
            index = max(0, min(index, page.node_type_combo.count() - 1))
            page.node_type_combo.setCurrentIndex(index)

            page.silent_mode = True
            if not page.set_model_file(paths["model"], interactive=False):
                message = getattr(page, "last_model_error", "模型文件无效")
                page.silent_mode = False
                self._build_flow_fail("电路参数优化", message)
                return
            if not page.start_optimize():
                page.silent_mode = False
                self._build_flow_fail("电路参数优化", "无法启动参数优化")
                return

            thread = page.optimize_thread
            if thread is None or not thread.isRunning():
                page.silent_mode = False
                self._build_flow_fail("电路参数优化", "参数优化未能启动")
                return
        except Exception as exc:
            page = self.page_contents.get(2)
            if page is not None:
                page.silent_mode = False
            self._build_flow_fail("电路参数优化", str(exc))
            return

        self._wait_for_page_worker(
            page, "optimize_thread", self._build_flow_after_optimize,
            "电路参数优化")

    def _build_flow_after_optimize(self):
        if self._flow is None:
            return
        page = self.page_contents[2]
        page.silent_mode = False
        if not page.has_valid_result:
            detail = self._flow_error_line(
                getattr(page, "last_run_error", ""))
            message = "参数优化失败，详见页面日志"
            if detail:
                message = f"参数优化失败：{detail}"
            self._build_flow_fail("电路参数优化", message)
            return

        result = getattr(page, "last_result", None) or {}
        perf = result.get("performance", {})

        def number(key):
            try:
                return float(perf.get(key, 0) or 0)
            except (TypeError, ValueError):
                return 0.0

        self._flow["completed"].append((
            "电路参数优化",
            f"Reward：{number('Reward'):.2f}\n"
            f"Gain：{number('Gain'):.2f} dB | "
            f"带宽：{number('Bandwidth'):.3e} Hz\n"
            f"CMRR：{number('CMRR'):.2f} dB | "
            f"PM：{number('PM'):.2f}°"))
        self._build_flow_step4()

    def _build_flow_step4(self):
        """步骤4：自动布线"""
        paths = self._flow["paths"]
        try:
            self.stack.setCurrentIndex(4)
            QApplication.processEvents()
            page = self.page_contents[4]
            page.nets_edit.setText(paths["nets"])
            page.layout_edit.setText(paths["layout"])
            page.nets_path = paths["nets"]
            page.layout_path = paths["layout"]
            page.refresh_tree()
            page.run_pipeline()
            worker = page.worker
            if worker is None or not worker.isRunning():
                self._build_flow_fail("自动布线", "自动布线未能启动")
                return
        except Exception as exc:
            self._build_flow_fail("自动布线", str(exc))
            return

        self._flow["route_page"] = page
        self._wait_for_page_worker(
            page, "worker", self._build_flow_after_route, "自动布线")

    def _build_flow_after_route(self):
        if self._flow is None:
            return
        page = self.page_contents[4]
        if not getattr(page, "last_run_ok", False):
            detail = self._flow_error_line(
                getattr(page, "last_run_error", ""))
            message = "自动布线失败，详见页面日志"
            if detail:
                message = f"自动布线失败：{detail}"
            self._build_flow_fail("自动布线", message)
            return

        self._flow["completed"].append((
            "自动布线",
            f"输出：{os.path.join(page.out_dir, 'step3_gds')}"))
        self._finish_build_flow()

    def _wait_for_page_worker(self, page, attr, on_done, step_name,
                              timeout_s=1800):
        """轮询页面上的后台线程，结束后调用 on_done

        比直接等 QThread.finished 稳一些：页面自己的 finished 槽
        （恢复按钮、记录状态）先执行完，我们再继续下一步。
        """
        timer = QTimer(self)
        timer.setInterval(200)
        elapsed = [0.0]
        self._flow["timer"] = timer

        def tick():
            if self._flow is None:
                timer.stop()
                return
            elapsed[0] += 0.2
            worker = getattr(page, attr, None)
            if worker is None or not worker.isRunning():
                timer.stop()
                # 交给 _finish_build_flow 统一停表并销毁
                QTimer.singleShot(150, on_done)
            elif elapsed[0] > timeout_s:
                timer.stop()
                self._build_flow_fail(step_name, "后台任务运行超时")

        timer.timeout.connect(tick)
        timer.start()

    def menu_open_netlist(self):
        page = self.current_content()
        if page is None or not hasattr(page, "open_netlist"):
            QMessageBox.information(
                self, "打开网表", "当前页面不支持打开网表。")
            return

        start_dir = getattr(self, "_last_netlist_dir", base_path)
        path, _ = QFileDialog.getOpenFileName(
            self, "打开网表", start_dir,
            "网表文件 (*.sp *.cdl *.spice *.txt);;所有文件 (*)")
        if path:
            self._last_netlist_dir = os.path.dirname(path)
            page.open_netlist(path)
            self.refresh_actions()

    def show_preferences(self):
        choices = ["80%", "90%", "100%", "110%", "125%", "150%"]
        current = int(round(ui_scale() * 100))
        index = min(range(len(choices)),
                    key=lambda i: abs(int(choices[i][:-1]) - current))

        choice, accepted = QInputDialog.getItem(
            self, "首选项", "界面字号（Ctrl+= / Ctrl+- 也可调）：",
            choices, index, False)
        if accepted:
            set_scale(int(choice[:-1]) / 100.0)
            apply_ui_scale()
            self.refresh_actions()

    def open_manual(self):
        candidates = (
            os.path.join(base_path, "Parms_使用手册.pdf"),
            os.path.join(base_path, "docs",
                         "Parms_模块一模块二_使用文档与案例说明.pdf"),
        )
        for path in candidates:
            if os.path.exists(path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(path))
                return
        QMessageBox.information(self, "使用说明", "没有找到使用手册文件。")

    def _init_function_pages(self):
        """初始化/刷新四个功能页面，每次调用都会重新创建实例，清空所有参数"""
        # 先移除旧页面（如果存在）
        for i in range(self.stack.count()-1, 0, -1):
            widget = self.stack.widget(i)
            if widget:
                self.stack.removeWidget(widget)
                widget.deleteLater()

        self.page_contents = {}
        pages = (
            (1, CircuitGenerator, "电路版图生成"),
            (2, CircuitOptWindow, "电路参数优化"),
            (3, AutoLayoutWindow, "自动布局"),
            (4, RoutingPage, "自动布线"),
        )
        for index, content_class, title in pages:
            content = content_class()
            page = FunctionPageWrapper(title, content)
            page.go_home_signal.connect(self.go_back_home)
            self.stack.addWidget(page)
            self.page_contents[index] = content

            # 页面完成操作后刷新菜单的撤销 / 重做状态
            signal = getattr(content, "state_changed", None)
            if signal is not None:
                signal.connect(self.refresh_actions)

        self.refresh_actions()

    def switch_to_page(self, index):
        """切换到指定功能页

        功能页只在启动时创建一次，切换不再重建：各模块的输入、日志
        和撤销记录都会保留，直到关闭软件。
        """
        if self._flow is not None:
            QMessageBox.information(
                self, "流程运行中",
                "一键运行全部流程正在执行，请等待完成后再切换页面。")
            return
        self.stack.setCurrentIndex(index)
        self.refresh_actions()

    def go_back_home(self):
        """返回主页"""
        if self._flow is not None:
            QMessageBox.information(
                self, "流程运行中",
                "一键运行全部流程正在执行，请等待完成后再切换页面。")
            return
        # 回到主页时清掉导航栏的加深状态，只有刚点下去那一下才高亮
        self.home_page.clear_nav_selection()
        self.stack.setCurrentIndex(0)
        self.refresh_actions()

    def create_empty_page(self, title, message):
        """创建一个带科技感图标和文字的占位页面（保留备用）"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        icon_label = QLabel("⚡")
        icon_label.setFont(QFont(cjk_font_family(), font_pt(48)))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("color: #cbd5e0; margin-bottom: 20px;")

        text_label = QLabel(message)
        text_label.setFont(QFont(cjk_font_family(), font_pt(16)))
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setStyleSheet("color: #718096; background: transparent;")

        layout.addWidget(icon_label)
        layout.addWidget(text_label)
        return page


if __name__ == "__main__":
    icon_path = os.path.join(base_path, "assets", "image.png")
    #print(icon_path)

    # High-DPI 缩放必须在 QApplication 创建之前设置才生效。
    # 让 Qt 按系统缩放比统一放大控件与字体；ui_scale() 只负责用户手动倍率，
    # 两套缩放各管一头，不会叠加。
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("parms")
    app.setApplicationDisplayName("parms")
    app.setOrganizationName("parms")
    app.setDesktopFileName("parms")

    if os.path.exists(icon_path):
        app_icon = QIcon()
        app_icon.addFile(icon_path, QSize(64, 64))
        app_icon.addFile(icon_path, QSize(128, 128))
        app_icon.addFile(icon_path, QSize(256, 256))
        app.setWindowIcon(app_icon)

    # 全局字体与调色板（中文字体按系统自动挑选，Linux 用文泉驿、Windows 用微软雅黑）
    font = QFont()
    font.setFamily(cjk_font_family())
    font.setPointSize(font_pt(11))
    app.setFont(font)

    # 设置全局默认调色板，确保所有控件继承浅色风格
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#f5f7fa"))
    palette.setColor(QPalette.WindowText, QColor("#1a202c"))
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#f0f2f5"))
    palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
    palette.setColor(QPalette.ToolTipText, QColor("#1a202c"))
    palette.setColor(QPalette.Text, QColor("#1a202c"))
    palette.setColor(QPalette.Button, QColor("#e9edf2"))
    palette.setColor(QPalette.ButtonText, QColor("#1a202c"))
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Highlight, QColor("#2b6ef7"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())