import sys
import os
import time
import traceback

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QGroupBox, QFormLayout, QLineEdit, QLabel, QFileDialog,
    QTextEdit, QSpinBox, QDoubleSpinBox, QTabWidget,
    QScrollArea, QFrame, QMessageBox
)
from PyQt5.QtGui import QFont, QTextCursor, QDesktopServices
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl

import matplotlib

matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

# 获取当前文件所在目录，用于临时切换工作目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 添加DGL_build目录到Python搜索路径
import sys

sys.path.append(os.path.join(BASE_DIR, "DGL_build"))

# 项目根目录，为了 import ui_style
sys.path.append(os.path.dirname(BASE_DIR))

# 页面样式、缩放和绘图字体助手都放在项目根的 ui_style.py，各功能页共用
from ui_style import (
    PAGE_STYLE, cjk_font_properties, register_style, scaled_qss,
)
from ui_history import PageHistory

# 预处理页单独放大一档：这一页只有下拉条和按钮，字号小、行距松时
# 窗口越大越显得空。这里把输入框和按钮都撑起来，窗口缩放时按比例伸展。
PREPROCESS_STYLE = """
QLabel, QGroupBox {
    font-size: 16px;
}
QLineEdit {
    /* 和旁边 52px 高的「浏览」按钮对齐 */
    min-height: 42px;
    padding: 4px 10px;
    font-size: 16px;
}
QPushButton {
    min-height: 38px;
    min-width: 84px;
    padding: 6px 20px;
    font-size: 16px;
}
QPushButton#primaryButton {
    min-height: 46px;
    font-size: 17px;
    padding: 8px 24px;
}
"""

def read_device_models(netlist_path):
    """从网表里读 MOS 的模型名（pch / nch_lvt …），只用于绘图配色。

    布局算法本身不读这个返回值：器件坐标、尺寸和对称关系都不受影响，
    这里只是让布局图能把 NMOS / PMOS 用不同颜色区分开。
    返回 {实例名: 小写模型名}，实例名按解析器的规则去掉 CDL 的 X 前缀。
    """
    models = {}
    try:
        with open(netlist_path, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line or line[0] in "*.#":
                    continue
                parts = line.split()
                if not parts:
                    continue
                name = parts[0]
                if not (name.startswith("M") or name.startswith("XM")):
                    continue
                # M<name> n1 n2 n3 n4 model ...
                if len(parts) < 6:
                    continue
                model = parts[5]
                if "=" in model or model.startswith("$"):
                    continue
                if name.startswith("X"):
                    name = name[1:]
                models[name] = model.lower()
    except OSError:
        pass
    return models


# 后台线程的存活引用。页面切换时 AutoLayoutWindow 会被销毁，
# 若 QThread 还挂在它下面会直接崩，所以放模块级集合里托管，线程跑完再移除。
_ACTIVE_WORKERS = set()



class LayoutWorker(QThread):
    """后台执行自动布局优化，避免十几秒的计算把界面卡死"""

    # 布局图数据：{kind, x, y, devices, sym_pairs, x_sym, title}
    figure_ready = pyqtSignal(object)
    succeeded = pyqtSignal(object, object)
    failed = pyqtSignal(str)

    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.params = params

    def _on_plot(self, kind, x, y, devices, sym_pairs, x_sym, title):
        # 本方法运行在工作线程里，只允许发信号，
        # 不能碰任何 Qt 控件或 matplotlib canvas
        self.figure_ready.emit({
            "kind": kind,
            "x": x,
            "y": y,
            "devices": devices,
            "sym_pairs": sym_pairs,
            "x_sym": x_sym,
            "title": title,
        })

    def run(self):
        original_cwd = os.getcwd()
        try:
            os.chdir(BASE_DIR)

            # 导入布局函数
            from LAYOUT import optimize_layout

            x, y = optimize_layout(plot_callback=self._on_plot,
                                   plot_intermediate=False,
                                   **self.params)
            self.succeeded.emit(x, y)
        except Exception:
            self.failed.emit(traceback.format_exc())
        finally:
            os.chdir(original_cwd)


class AutoLayoutWindow(QWidget):
    # 页面完成一次操作后通知主窗口刷新菜单状态
    state_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.worker = None
        self.start_time = 0.0
        self.history = PageHistory(self)
        self._last_layout_params = None
        self._replaying = False
        # 最近一次布局优化是否成功；一键全流程用它判断能否继续
        self.last_layout_ok = None
        self.last_layout_error = ""
        # MOS 模型名映射，只给布局图配色用，参与计算的仍是原始器件数据
        self._device_models = {}
        self.init_ui()

    def init_ui(self):
        register_style(self, lambda: scaled_qss(PAGE_STYLE))

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # 两个标签页按实际操作顺序排列：先预处理（步骤1/2），
        # 再做布局优化（步骤3）。页面内容比主窗口高，套一层滚动区，
        # 窗口小了也不会把控件裁掉。
        self.tabs = QTabWidget()
        outer_layout.addWidget(self.tabs)
        self.tabs.addTab(self.make_scrollable(self.build_preprocess_page()), "预处理")
        self.tabs.addTab(self.make_scrollable(self.build_main_page()), "布局优化")
        self.tabs.setCurrentIndex(0)

    @staticmethod
    def make_scrollable(inner):
        """把页面包进滚动区：空间够就撑满，不够就出滚动条"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(inner)
        return scroll

    # ==================== 主页面（步骤3 + 布局图 + 日志） ====================
    def build_main_page(self):
        page = QWidget()
        page.setObjectName("page")
        page_layout = QVBoxLayout(page)
        # 上下留白压紧，把高度让给布局图
        page_layout.setContentsMargins(14, 10, 14, 10)
        page_layout.setSpacing(9)

        page_layout.addWidget(self.build_step3_group())
        page_layout.addWidget(self.build_figure_group(), 1)
        page_layout.addWidget(self.build_log_group())
        return page

    def build_step3_group(self):
        """步骤3：运行自动布局优化"""
        step3_group = QGroupBox("运行自动布局优化")
        step3_layout = QFormLayout(step3_group)
        step3_layout.setSpacing(6)
        step3_layout.setContentsMargins(9, 6, 9, 8)

        # 输入带约束的网表
        self.layout_netlist_edit = QLineEdit()
        self.layout_netlist_edit.setPlaceholderText("选择带约束注释的网表文件")
        layout_netlist_browse_btn = QPushButton("浏览")
        layout_netlist_browse_btn.clicked.connect(self.select_layout_netlist)

        layout_netlist_layout = QHBoxLayout()
        layout_netlist_layout.addWidget(self.layout_netlist_edit)
        layout_netlist_layout.addWidget(layout_netlist_browse_btn)
        step3_layout.addRow("带约束网表：", layout_netlist_layout)

        # 输入约束文件
        self.sym_input_edit = QLineEdit()
        self.sym_input_edit.setPlaceholderText("选择.sym约束文件")
        sym_browse_btn = QPushButton("浏览")
        sym_browse_btn.clicked.connect(self.select_sym_file)

        sym_input_layout = QHBoxLayout()
        sym_input_layout.addWidget(self.sym_input_edit)
        sym_input_layout.addWidget(sym_browse_btn)
        step3_layout.addRow("约束文件(.sym)：", sym_input_layout)

        # ==================== 完整布局参数设置 ====================
        # 第一行参数
        param_row1 = QHBoxLayout()

        self.target_area_spin = QDoubleSpinBox()
        self.target_area_spin.setRange(1.0, 100.0)
        self.target_area_spin.setValue(10.0)
        self.target_area_spin.setSingleStep(1.0)
        param_row1.addWidget(QLabel("目标面积："))
        param_row1.addWidget(self.target_area_spin)

        self.max_steps_spin = QSpinBox()
        self.max_steps_spin.setRange(100, 10000)
        self.max_steps_spin.setValue(1000)
        self.max_steps_spin.setSingleStep(100)
        param_row1.addWidget(QLabel("优化步数："))
        param_row1.addWidget(self.max_steps_spin)

        step3_layout.addRow("基础参数：", param_row1)

        # 第二行参数
        param_row2 = QHBoxLayout()

        self.tmoc_weight_spin = QDoubleSpinBox()
        self.tmoc_weight_spin.setRange(0.0, 100.0)
        self.tmoc_weight_spin.setValue(20.0)
        self.tmoc_weight_spin.setSingleStep(5.0)
        param_row2.addWidget(QLabel("共质心权重："))
        param_row2.addWidget(self.tmoc_weight_spin)

        self.symmetry_weight_spin = QDoubleSpinBox()
        self.symmetry_weight_spin.setRange(0.0, 500.0)
        self.symmetry_weight_spin.setValue(100.0)
        self.symmetry_weight_spin.setSingleStep(10.0)
        param_row2.addWidget(QLabel("对称性权重："))
        param_row2.addWidget(self.symmetry_weight_spin)

        self.hpwl_weight_spin = QDoubleSpinBox()
        self.hpwl_weight_spin.setRange(0.0, 1.0)
        self.hpwl_weight_spin.setValue(0.01)
        self.hpwl_weight_spin.setSingleStep(0.01)
        param_row2.addWidget(QLabel("线长权重："))
        param_row2.addWidget(self.hpwl_weight_spin)

        step3_layout.addRow("优化权重：", param_row2)

        # 第三行参数
        param_row3 = QHBoxLayout()

        self.max_overlap_spin = QDoubleSpinBox()
        self.max_overlap_spin.setRange(0.0, 5.0)
        self.max_overlap_spin.setValue(2.0)
        self.max_overlap_spin.setSingleStep(0.1)
        param_row3.addWidget(QLabel("最大重叠率："))
        param_row3.addWidget(self.max_overlap_spin)

        self.max_symmetry_error_spin = QDoubleSpinBox()
        self.max_symmetry_error_spin.setRange(0.0, 1.0)
        self.max_symmetry_error_spin.setValue(0.1)
        self.max_symmetry_error_spin.setSingleStep(0.05)
        param_row3.addWidget(QLabel("最大对称误差："))
        param_row3.addWidget(self.max_symmetry_error_spin)

        self.max_oob_penalty_spin = QDoubleSpinBox()
        self.max_oob_penalty_spin.setRange(0.0, 1.0)
        self.max_oob_penalty_spin.setValue(0.1)
        self.max_oob_penalty_spin.setSingleStep(0.05)
        param_row3.addWidget(QLabel("越界惩罚系数："))
        param_row3.addWidget(self.max_oob_penalty_spin)

        step3_layout.addRow("约束参数：", param_row3)

        # 运行布局按钮：左右留弹簧，按内容宽度居中，不拉满整行
        self.layout_btn = QPushButton("开始自动布局优化")
        self.layout_btn.setObjectName("primaryButton")
        self.layout_btn.setMinimumHeight(34)
        self.layout_btn.setMinimumWidth(180)
        self.layout_btn.setCursor(Qt.PointingHandCursor)
        self.layout_btn.clicked.connect(self.run_layout)

        run_row = QHBoxLayout()
        run_row.addStretch()
        run_row.addWidget(self.layout_btn)
        run_row.addStretch()
        step3_layout.addRow(run_row)

        # QFormLayout 空间不足时会把按钮压到 minimumSizeHint。按实际
        # sizeHint 兜底，放大字号后「开始自动布局优化」不会被压扁。
        self.layout_btn.setMinimumHeight(
            max(34, self.layout_btn.sizeHint().height()))

        return step3_group

    def build_figure_group(self):
        """布局图：左右两幅内嵌画布，左边初始布局、右边最终布局"""
        figure_group = QGroupBox("布局图")
        figure_layout = QVBoxLayout(figure_group)
        figure_layout.setContentsMargins(6, 6, 6, 6)
        figure_layout.setSpacing(0)

        self.figure = Figure(figsize=(8, 3.6))
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(300)
        figure_layout.addWidget(self.canvas)

        self.ax_initial = self.figure.add_subplot(1, 2, 1)
        self.ax_final = self.figure.add_subplot(1, 2, 2)
        self.reset_figure()
        return figure_group

    def build_log_group(self):
        """执行日志：高度压小，把空间让给布局图"""
        log_group = QGroupBox("执行日志")
        log_layout = QVBoxLayout(log_group)

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        # 日志要看完整的报错堆栈，太矮只能来回滚，给到 160~230 像素
        self.log_edit.setMinimumHeight(160)
        self.log_edit.setMaximumHeight(230)
        # 样式统一放在 PAGE_STYLE 里（控件自带的样式表会盖掉父级的，所以这里不单独设）
        log_layout.addWidget(self.log_edit)

        return log_group

    # ==================== 子页面（步骤1 + 步骤2） ====================
    def build_preprocess_page(self):
        page = QWidget()
        page.setObjectName("page")
        # 整页套一档更大的样式，窗口宽高变化时输入框跟着伸展
        register_style(page, lambda: scaled_qss(PAGE_STYLE + PREPROCESS_STYLE))

        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(16, 12, 16, 12)
        page_layout.setSpacing(14)

        hint = QLabel(
            "先做步骤 1、2；结果会自动填到「布局优化」标签页。"
            "失败时会弹窗提示，详细堆栈见「布局优化」页的执行日志。")
        hint.setWordWrap(True)
        page_layout.addWidget(hint)

        page_layout.addWidget(self.build_step1_group())
        page_layout.addWidget(self.build_step2_group())
        page_layout.addStretch()
        return page

    def build_step1_group(self):
        """步骤1：CDL/SP网表转DGL图"""
        step1_group = QGroupBox("CDL/SP网表 → DGL图文件")
        step1_layout = QFormLayout(step1_group)
        step1_layout.setSpacing(12)
        step1_layout.setContentsMargins(12, 12, 12, 12)

        # 输入网表文件
        self.cdl_input_edit = QLineEdit()
        self.cdl_input_edit.setPlaceholderText("选择CDL或SP格式的网表文件")
        cdl_browse_btn = QPushButton("浏览")
        cdl_browse_btn.setCursor(Qt.PointingHandCursor)
        cdl_browse_btn.clicked.connect(self.select_cdl_file)

        cdl_input_layout = QHBoxLayout()
        cdl_input_layout.addWidget(self.cdl_input_edit)
        cdl_input_layout.addWidget(cdl_browse_btn)
        step1_layout.addRow("输入网表：", cdl_input_layout)

        # 输出DGL文件
        self.dgl_output_edit = QLineEdit()
        self.dgl_output_edit.setPlaceholderText("选择DGL文件保存路径")
        dgl_browse_btn = QPushButton("浏览")
        dgl_browse_btn.setCursor(Qt.PointingHandCursor)
        dgl_browse_btn.clicked.connect(self.select_dgl_save_file)

        dgl_output_layout = QHBoxLayout()
        dgl_output_layout.addWidget(self.dgl_output_edit)
        dgl_output_layout.addWidget(dgl_browse_btn)
        step1_layout.addRow("输出DGL：", dgl_output_layout)

        # 转换按钮：主操作，做成主按钮样式并占满整行
        self.convert_btn = QPushButton("开始转换为DGL图")
        self.convert_btn.setObjectName("primaryButton")
        self.convert_btn.setCursor(Qt.PointingHandCursor)
        self.convert_btn.setMinimumHeight(46)
        # 用 lambda 转接：clicked 会传一个 checked 参数，
        # 不能让它落到 convert_to_dgl 的 interactive 形参上
        self.convert_btn.clicked.connect(lambda: self.convert_to_dgl())
        step1_layout.addRow(self.convert_btn)

        return step1_group

    def build_step2_group(self):
        """步骤2：DGL图提取匹配约束"""
        step2_group = QGroupBox("DGL图 → 匹配约束文件(.sym)")
        step2_layout = QFormLayout(step2_group)
        step2_layout.setSpacing(12)
        step2_layout.setContentsMargins(12, 12, 12, 12)

        # 输入DGL文件
        self.dgl_input_edit = QLineEdit()
        self.dgl_input_edit.setPlaceholderText("选择DGL图文件")
        dgl_input_browse_btn = QPushButton("浏览")
        dgl_input_browse_btn.setCursor(Qt.PointingHandCursor)
        dgl_input_browse_btn.clicked.connect(self.select_dgl_file)

        dgl_input_layout = QHBoxLayout()
        dgl_input_layout.addWidget(self.dgl_input_edit)
        dgl_input_layout.addWidget(dgl_input_browse_btn)
        step2_layout.addRow("输入DGL：", dgl_input_layout)

        # 输入原网表文件
        self.netlist_input_edit = QLineEdit()
        self.netlist_input_edit.setPlaceholderText("选择对应的原始网表文件")
        netlist_browse_btn = QPushButton("浏览")
        netlist_browse_btn.setCursor(Qt.PointingHandCursor)
        netlist_browse_btn.clicked.connect(self.select_netlist_file)

        netlist_input_layout = QHBoxLayout()
        netlist_input_layout.addWidget(self.netlist_input_edit)
        netlist_input_layout.addWidget(netlist_browse_btn)
        step2_layout.addRow("原始网表：", netlist_input_layout)

        # 提取约束按钮：主操作，做成主按钮样式并占满整行
        self.extract_btn = QPushButton("提取匹配约束并生成.sym文件")
        self.extract_btn.setObjectName("primaryButton")
        self.extract_btn.setCursor(Qt.PointingHandCursor)
        self.extract_btn.setMinimumHeight(46)
        self.extract_btn.clicked.connect(lambda: self.extract_constraint())
        step2_layout.addRow(self.extract_btn)

        return step2_group

    # ==================== 文件选择槽函数 ====================
    def select_cdl_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择网表文件", "", "网表文件 (*.cdl *.sp *.spice);;所有文件 (*.*)"
        )
        if file_path:
            self.cdl_input_edit.setText(file_path)
            # 自动填充输出DGL路径
            default_dgl = os.path.splitext(file_path)[0] + ".dgl"
            self.dgl_output_edit.setText(default_dgl)

    def select_dgl_save_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存DGL文件", "", "DGL文件 (*.dgl);;所有文件 (*.*)"
        )
        if file_path:
            self.dgl_output_edit.setText(file_path)

    def select_dgl_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择DGL文件", "", "DGL文件 (*.dgl);;所有文件 (*.*)"
        )
        if file_path:
            self.dgl_input_edit.setText(file_path)

    def select_netlist_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择原始网表文件", "", "网表文件 (*.cdl *.sp *.spice);;所有文件 (*.*)"
        )
        if file_path:
            self.netlist_input_edit.setText(file_path)

    def select_layout_netlist(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择带约束的网表文件", "", "网表文件 (*.cdl *.sp *.spice);;所有文件 (*.*)"
        )
        if file_path:
            self.layout_netlist_edit.setText(file_path)

    def select_sym_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择约束文件", "", "约束文件 (*.sym);;所有文件 (*.*)"
        )
        if file_path:
            self.sym_input_edit.setText(file_path)

    # ==================== 日志与状态管理 ====================
    def append_log(self, text, level="info"):
        """
        带级别和时间戳的日志输出
        level: info/success/warning/error
        """
        timestamp = time.strftime("%H:%M:%S", time.localtime())

        # 不同级别使用不同颜色
        color_map = {
            "info": "#1e293b",
            "success": "#16a34a",
            "warning": "#ca8a04",
            "error": "#dc2626"
        }

        color = color_map.get(level, "#1e293b")
        formatted_text = f'<span style="color: #64748b;">[{timestamp}]</span> <span style="color: {color};">{text}</span>'

        self.log_edit.append(formatted_text)
        # 自动滚动到底部
        self.log_edit.verticalScrollBar().setValue(
            self.log_edit.verticalScrollBar().maximum()
        )

    # ==================== 菜单能力 / 撤销重做 ====================
    def open_netlist(self, path):
        """文件 → 打开网表：填入步骤1输入并切到预处理标签页"""
        self.cdl_input_edit.setText(path)
        self.dgl_output_edit.setText(os.path.splitext(path)[0] + ".dgl")
        self.tabs.setCurrentIndex(0)

    def open_result_dir(self):
        """文件 → 打开结果目录：.sym 和带约束网表都落在 analog_placement/"""
        QDesktopServices.openUrl(QUrl.fromLocalFile(BASE_DIR))

    def clear_log(self):
        self.log_edit.clear()

    def _worker_running(self):
        return self.worker is not None and self.worker.isRunning()

    def can_undo(self):
        return self.history.can_undo() and not self._worker_running()

    def can_redo(self):
        return self.history.can_redo() and not self._worker_running()

    def undo(self):
        changed = self.history.undo()
        self.state_changed.emit()
        return changed

    def redo(self):
        changed = self.history.redo()
        self.state_changed.emit()
        return changed

    @staticmethod
    def _read_bytes(path):
        try:
            with open(path, "rb") as handle:
                return handle.read()
        except OSError:
            return None

    @staticmethod
    def _restore_file(path, previous):
        if previous is None:
            if os.path.exists(path):
                os.remove(path)
        else:
            with open(path, "wb") as handle:
                handle.write(previous)

    def _push_convert_command(self, cdl_path, dgl_path, previous):
        def redo():
            original_cwd = os.getcwd()
            try:
                os.chdir(BASE_DIR)
                from DGL_build.dgl_generator import cdl_to_dgl
                cdl_to_dgl(cdl_path, dgl_path)
            finally:
                os.chdir(original_cwd)
            self.dgl_input_edit.setText(dgl_path)
            self.netlist_input_edit.setText(cdl_path)
            self.append_log(
                f"↻ 已重做：网表转 DGL 图（{os.path.basename(dgl_path)}）")

        def undo():
            self._restore_file(dgl_path, previous)
            self.append_log(
                f"↩ 已撤销：网表转 DGL 图（{os.path.basename(dgl_path)}）",
                "warning")

        self.history.push(
            f"网表转 DGL 图（{os.path.basename(cdl_path)}）", redo, undo,
            step=1)

    def _push_extract_command(self, dgl_path, netlist_path, sym_path,
                              output_netlist_path, prev_sym, prev_out):
        def redo():
            original_cwd = os.getcwd()
            try:
                os.chdir(BASE_DIR)
                from DGL_build.extract import constraint_extraction
                constraint_extraction(dgl_path, netlist_path)
            finally:
                os.chdir(original_cwd)
            self.layout_netlist_edit.setText(output_netlist_path)
            self.sym_input_edit.setText(sym_path)
            self.append_log(
                f"↻ 已重做：约束提取（{os.path.basename(sym_path)}）")

        def undo():
            self._restore_file(sym_path, prev_sym)
            self._restore_file(output_netlist_path, prev_out)
            self.append_log(
                f"↩ 已撤销：约束提取（{os.path.basename(sym_path)}）",
                "warning")

        self.history.push(
            f"提取匹配约束（{os.path.basename(netlist_path)}）", redo, undo,
            step=2)

    def set_button_running(self, button, running_text):
        """设置按钮为运行中状态"""
        button.setEnabled(False)
        button.setText(f"⏳ {running_text}")
        # 强制刷新UI
        button.repaint()

    def restore_button(self, button, original_text):
        """恢复按钮为正常状态"""
        button.setEnabled(True)
        button.setText(original_text)

    # ==================== 布局图绘制（只在GUI线程执行） ====================
    def reset_figure(self):
        """清空左右两幅图，各放一句提示"""
        self.draw_panel_placeholder(self.ax_initial, "初始布局")
        self.draw_panel_placeholder(self.ax_final, "最终布局")
        self.layout_figure()
        self.canvas.draw_idle()

    def draw_panel_placeholder(self, ax, title):
        ax.clear()
        ax.set_title(title, fontsize=11, color="#94a3b8",
                     fontproperties=cjk_font_properties())
        ax.text(0.5, 0.5, "等待运行…", ha="center", va="center", fontsize=10,
                color="#cbd5e0", fontproperties=cjk_font_properties())
        ax.set_axis_off()

    def draw_panel(self, ax, payload):
        """把一帧布局图画到指定的那一幅里"""
        # 懒导入：LAYOUT.visualization 会连带拉起 torch（约2秒），
        # 不放在模块顶层以免拖慢整个程序的启动
        from LAYOUT.visualization import draw_layout_on

        ax.clear()
        ax.set_axis_on()
        draw_layout_on(ax, payload["x"], payload["y"], payload["devices"],
                       payload["sym_pairs"], payload["x_sym"], payload["title"],
                       show_legend=False, models=self._device_models)
        self.layout_figure()
        self.canvas.draw_idle()

    def layout_figure(self):
        """两幅图共用一个图例，放到整张图下方，免得压住器件"""
        handles, labels = self.ax_initial.get_legend_handles_labels()
        if not handles:
            handles, labels = self.ax_final.get_legend_handles_labels()

        for legend in list(self.figure.legends):
            legend.remove()
        if handles:
            # 颜色对应的器件类型都放在整张图下方，按实际图例项排成一行。
            # 图例里有「电阻 / 电容」这类中文，必须用注册过的中文字体，
            # 否则 matplotlib 会画成方块。
            legend_font = cjk_font_properties()
            if legend_font is not None:
                legend_font = legend_font.copy()
                legend_font.set_size(10)
            self.figure.legend(handles, labels, loc="lower center",
                               ncol=min(len(handles), 6),
                               frameon=False, fontsize=10,
                               prop=legend_font)

        self.figure.subplots_adjust(left=0.06, right=0.99, top=0.90,
                                    bottom=0.16 if handles else 0.06,
                                    wspace=0.16)

    def on_figure_ready(self, payload):
        """工作线程每画一张图就会发一次信号"""
        # 中间那张“第一阶段结束”的图不显示
        if payload["kind"] == "initial":
            self.draw_panel(self.ax_initial, payload)
        elif payload["kind"] == "final":
            self.draw_panel(self.ax_final, payload)

    # ==================== 执行槽函数 ====================
    def convert_to_dgl(self, interactive=True):
        """步骤1：转换CDL/SP为DGL，返回是否成功（供构建菜单串联流程用）

        interactive=False 时不弹窗，只写日志，供「一键运行全部流程」调用。
        """
        cdl_path = self.cdl_input_edit.text().strip()
        dgl_path = self.dgl_output_edit.text().strip()

        if not cdl_path or not os.path.exists(cdl_path):
            self.append_log("请选择有效的网表文件", "error")
            if interactive:
                QMessageBox.warning(
                    self, "网表处理失败",
                    "请选择有效的网表文件。\n\n"
                    "详细信息见「布局优化」页的执行日志。")
            return False

        # 设置按钮为运行中状态
        self.set_button_running(self.convert_btn, "正在转换DGL图...")

        self.append_log("=" * 70)
        self.append_log("开始转换网表为DGL图", "info")
        self.append_log(f"输入网表：{os.path.basename(cdl_path)}")
        self.append_log(f"输出路径：{os.path.basename(dgl_path)}")
        self.append_log("-" * 70)

        start_time = time.time()
        previous_dgl = self._read_bytes(dgl_path) if dgl_path else None
        original_cwd = os.getcwd()

        try:
            # 临时切换工作目录到analog-placement
            os.chdir(BASE_DIR)

            # 导入转换函数
            from DGL_build.dgl_generator import cdl_to_dgl

            # 执行转换
            G_dgl, topCkt = cdl_to_dgl(cdl_path, dgl_path)

            elapsed = time.time() - start_time

            self.append_log(f"✅ DGL图转换完成，耗时 {elapsed:.2f} 秒", "success")
            self.append_log(f"节点数：{G_dgl.num_nodes()}")
            self.append_log(f"边数：{G_dgl.num_edges()}")
            self.append_log(f"节点特征维度：{G_dgl.ndata['feat'].shape}")

            # 自动填充步骤2的输入
            self.dgl_input_edit.setText(dgl_path)
            self.netlist_input_edit.setText(cdl_path)

            self._push_convert_command(cdl_path, dgl_path, previous_dgl)
            self.state_changed.emit()
            return True

        except Exception as e:
            elapsed = time.time() - start_time
            self.append_log(f"❌ 转换失败，耗时 {elapsed:.2f} 秒", "error")
            self.append_log(f"错误信息：{str(e)}", "error")
            self.append_log(traceback.format_exc(), "error")
            if interactive:
                QMessageBox.warning(
                    self, "网表处理失败",
                    f"网表转 DGL 图失败：{e}\n\n"
                    "详细信息见「布局优化」页的执行日志。")
            return False
        finally:
            os.chdir(original_cwd)
            # 恢复按钮状态
            self.restore_button(self.convert_btn, "开始转换为DGL图")
            self.append_log("=" * 70 + "\n")

    def extract_constraint(self, interactive=True):
        """步骤2：提取匹配约束，返回是否成功（供构建菜单串联流程用）

        interactive=False 时不弹窗，只写日志，供「一键运行全部流程」调用。
        """
        dgl_path = self.dgl_input_edit.text().strip()
        netlist_path = self.netlist_input_edit.text().strip()

        if not dgl_path or not os.path.exists(dgl_path):
            self.append_log("请选择有效的DGL文件", "error")
            if interactive:
                QMessageBox.warning(
                    self, "网表处理失败",
                    "请选择有效的 DGL 文件。\n\n"
                    "详细信息见「布局优化」页的执行日志。")
            return False

        if not netlist_path or not os.path.exists(netlist_path):
            self.append_log("请选择有效的原始网表文件", "error")
            if interactive:
                QMessageBox.warning(
                    self, "网表处理失败",
                    "请选择有效的原始网表文件。\n\n"
                    "详细信息见「布局优化」页的执行日志。")
            return False

        # 设置按钮为运行中状态
        self.set_button_running(self.extract_btn, "正在提取匹配约束...")

        self.append_log("=" * 70)
        self.append_log("开始提取匹配约束", "info")
        self.append_log(f"输入DGL：{os.path.basename(dgl_path)}")
        self.append_log(f"原始网表：{os.path.basename(netlist_path)}")
        self.append_log("-" * 70)

        start_time = time.time()
        # .sym 由 extract.constraint_extraction 写入其工作目录（BASE_DIR）
        sym_path = os.path.join(
            BASE_DIR,
            os.path.splitext(os.path.basename(netlist_path))[0] + '.sym')
        output_netlist_path = os.path.join(
            BASE_DIR,
            'new_' + os.path.basename(netlist_path))
        prev_sym = self._read_bytes(sym_path)
        prev_out = self._read_bytes(output_netlist_path)
        original_cwd = os.getcwd()

        try:
            # 临时切换工作目录到analog-placement
            os.chdir(BASE_DIR)

            # 导入约束提取函数
            from DGL_build.extract import constraint_extraction

            # 执行提取
            output_netlist_path = constraint_extraction(dgl_path, netlist_path)

            elapsed = time.time() - start_time

            self.append_log(f"✅ 约束提取完成，耗时 {elapsed:.2f} 秒", "success")
            self.append_log(f"生成约束文件：{os.path.basename(sym_path)}")
            self.append_log(f"生成带约束网表：{os.path.basename(output_netlist_path)}")

            # 自动填充步骤3的输入
            self.layout_netlist_edit.setText(output_netlist_path)
            self.sym_input_edit.setText(sym_path)

            self._push_extract_command(
                dgl_path, netlist_path, sym_path, output_netlist_path,
                prev_sym, prev_out)
            self.state_changed.emit()

            # 提取成功后直接切到布局优化页，再弹窗告知结果
            self.tabs.setCurrentIndex(1)
            if interactive:
                QMessageBox.information(
                    self, "提取完成",
                    "匹配约束提取完成。\n\n"
                    f"约束文件：{os.path.basename(sym_path)}\n"
                    f"带约束网表：{os.path.basename(output_netlist_path)}\n\n"
                    "已自动切换到「布局优化」页，结果已填入，请继续设置参数。")
            return True

        except Exception as e:
            elapsed = time.time() - start_time
            self.append_log(f"❌ 约束提取失败，耗时 {elapsed:.2f} 秒", "error")
            self.append_log(f"错误信息：{str(e)}", "error")
            self.append_log(traceback.format_exc(), "error")
            if interactive:
                QMessageBox.warning(
                    self, "网表处理失败",
                    f"约束提取失败：{e}\n\n"
                    "详细信息见「布局优化」页的执行日志。")
            return False
        finally:
            os.chdir(original_cwd)
            # 恢复按钮状态
            self.restore_button(self.extract_btn, "提取匹配约束并生成.sym文件")
            self.append_log("=" * 70 + "\n")

    def run_layout(self):
        """步骤3：运行自动布局（放到后台线程，界面不卡）"""
        self.last_layout_ok = None
        self.last_layout_error = ""
        netlist_path = self.layout_netlist_edit.text().strip()
        sym_path = self.sym_input_edit.text().strip()

        if not netlist_path or not os.path.exists(netlist_path):
            self.append_log("请选择有效的带约束网表文件", "error")
            return

        if not sym_path or not os.path.exists(sym_path):
            self.append_log("请选择有效的约束文件", "error")
            return

        if self.worker is not None and self.worker.isRunning():
            self.append_log("布局优化正在运行中，请等待完成", "warning")
            return

        # 获取所有UI参数
        params = dict(
            netlist_file=netlist_path,
            sym_file=sym_path,
            target_area=self.target_area_spin.value(),
            max_steps=self.max_steps_spin.value(),
            tmoc_weight=self.tmoc_weight_spin.value(),
            symmetry_weight=self.symmetry_weight_spin.value(),
            hpwl_weight=self.hpwl_weight_spin.value(),
            max_overlap_percent=self.max_overlap_spin.value(),
            max_symmetry_error=self.max_symmetry_error_spin.value(),
            max_oob_penalty=self.max_oob_penalty_spin.value(),
        )

        self._start_layout(params)

    def _start_layout(self, params, replay=False):
        """真正启动后台布局线程；重做时 replay=True，避免再压一条历史"""
        if self.worker is not None and self.worker.isRunning():
            self.append_log("布局优化正在运行中，请等待完成", "warning")
            return

        self._last_layout_params = dict(params)
        self._replaying = replay
        netlist_path = params["netlist_file"]
        sym_path = params["sym_file"]

        # 只读一遍网表拿模型名，用来给 NMOS / PMOS 分色
        self._device_models = read_device_models(netlist_path)

        self.append_log("=" * 70)
        self.append_log(
            "重新执行自动布局优化" if replay else "开始自动布局优化", "info")
        self.append_log(f"网表文件：{os.path.basename(netlist_path)}")
        self.append_log(f"约束文件：{os.path.basename(sym_path)}")
        self.append_log(f"目标面积：{params['target_area']} | 优化步数：{params['max_steps']}")
        self.append_log(f"共质心权重：{params['tmoc_weight']} | 对称性权重：{params['symmetry_weight']}")
        self.append_log("-" * 70)

        # 先把上一轮的图清掉，让初始图能立刻显示出来
        self.reset_figure()

        worker = LayoutWorker(dict(params))
        self.worker = worker
        # 托管引用：页面被销毁时线程不会跟着被销毁
        _ACTIVE_WORKERS.add(worker)
        worker.finished.connect(lambda: _ACTIVE_WORKERS.discard(worker))

        worker.figure_ready.connect(self.on_figure_ready)
        worker.succeeded.connect(self.on_layout_succeeded)
        worker.failed.connect(self.on_layout_failed)
        worker.finished.connect(self.on_worker_finished)

        self.start_time = time.time()
        self.set_button_running(self.layout_btn, "正在进行自动布局优化...")
        worker.start()
        self.state_changed.emit()

    def on_layout_succeeded(self, x, y):
        self.last_layout_ok = True
        self.last_layout_error = ""
        elapsed = time.time() - self.start_time
        self.append_log(f"✅ 布局优化完成，总耗时 {elapsed:.2f} 秒", "success")
        self.append_log(f"器件X坐标：{x}")
        self.append_log(f"器件Y坐标：{y}")

        # 步骤3 不落盘，历史里只记录“重跑一次 / 清空图”
        if not self._replaying and self._last_layout_params is not None:
            params = dict(self._last_layout_params)

            def redo():
                self._start_layout(dict(params), replay=True)

            def undo():
                self.draw_panel_placeholder(self.ax_final, "最终布局（已撤销）")
                self.layout_figure()
                self.canvas.draw_idle()
                self.append_log("↩ 已撤销：自动布局优化结果", "warning")

            self.history.push(
                f"自动布局优化（{os.path.basename(params['netlist_file'])}）",
                redo, undo, step=3)
        self.state_changed.emit()

    def on_layout_failed(self, error_text):
        self.last_layout_ok = False
        self.last_layout_error = error_text
        elapsed = time.time() - self.start_time
        self.append_log(f"❌ 布局失败，耗时 {elapsed:.2f} 秒", "error")
        self.append_log(error_text, "error")

    def on_worker_finished(self):
        self._replaying = False
        self.restore_button(self.layout_btn, "开始自动布局优化")
        self.append_log("=" * 70 + "\n")
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
        self.state_changed.emit()


# 模块可以独立运行测试
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 设置全局字体
    from ui_style import cjk_font_family
    font = QFont(cjk_font_family())
    font.setPointSize(12)
    app.setFont(font)

    window = AutoLayoutWindow()
    window.setWindowTitle("自动布局模块")
    window.resize(880, 1000)
    window.show()
    sys.exit(app.exec_())
