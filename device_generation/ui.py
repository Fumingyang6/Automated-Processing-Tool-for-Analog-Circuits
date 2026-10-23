from PyQt5 import uic
from PyQt5.QtWidgets import (
    QMainWindow, QMessageBox, QFileDialog, QButtonGroup, QProgressBar,
    QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QPushButton, QGroupBox, QLabel, QSpacerItem, QAbstractSpinBox,
)
from PyQt5.QtCore import Qt
from resource_utils import resource_path
import sys, os

try:
    from ui_style import PAGE_STYLE, register_style, scaled_qss, scale_px
except ImportError:
    # 独立调试本文件时项目根目录不在 sys.path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ui_style import PAGE_STYLE, register_style, scaled_qss, scale_px

# 元件生成页在 PAGE_STYLE 基础上再放大一档，输入框和按钮才不会又小又空
DEVICE_UI_STYLE = """
QLineEdit, QComboBox {
    /* 38 + 上下 padding + 边框 = 48px，和按钮同高，同一行看起来齐平 */
    min-height: 38px;
    padding: 4px 8px;
    font-size: 15px;
}
QPushButton {
    min-height: 34px;
    padding: 6px 18px;
    font-size: 15px;
}
QRadioButton, QCheckBox {
    font-size: 14px;
    spacing: 6px;
}
"""


"""内置ui
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)
    
class CircuitUI(QMainWindow):

    def __init__(self):
        super().__init__()
        self.ui = uic.loadUi(resource_path("devise.ui"))"""

"""外置ui"""
class CircuitUI(QWidget):
    """用户界面管理类"""
    def __init__(self):
        super().__init__()
        self.ui = uic.loadUi(resource_path("device_generation/devise.ui"), self)
###

        self.current_subckt = ""
        # 这个下拉框只用来切换生成页面，.ui 里是 editable 的，
        # 用户能点进去改文字/框选，这里关掉编辑，只保留下拉选择。
        self.ui.comboBox.setEditable(False)
        self.ui.stackedWidget.setCurrentIndex(self.ui.comboBox.currentIndex())
        self.setup_progress_bar()
        self.setup_radio_groups()
        self.ui.comboBoxTech.clear()

        # attr 默认留空：电阻的 m / wo 在 .ui 里两个都是 checked（分属不同
        # GroupBox，本来不互斥），这里先都清掉，再放进同一个互斥组。
        self.ui.radioButton_6.setChecked(False)
        self.ui.radioButton_7.setChecked(False)
        self.attr_radio_group = QButtonGroup()
        self.attr_radio_group.addButton(self.ui.radioButton_6)   # m
        self.attr_radio_group.addButton(self.ui.radioButton_7)   # wo
        self.attr_radio_group.setExclusive(True)

        # 电容的 attr 下拉框同样默认不选
        self.ui.comboBox_9.setCurrentIndex(-1)

        # 统一沿用各功能页的样式，并整理 .ui 里遗留的弹簧和边距。
        # 先整理布局（会重建「网表+工艺」页并设置主按钮名），再套样式。
        self.tidy_layouts()
        register_style(self, lambda: scaled_qss(PAGE_STYLE + DEVICE_UI_STYLE))
        ##self.ui.show()

    # ==================== 布局整理 ====================
    def tidy_layouts(self):
        """让元件生成页随窗口大小自适应。

        devise.ui 是设计器画的，里面大量水平弹簧的 stretch 有 3~4，
        输入框只占一小块，窗口越大空白越多。这里去掉弹簧，
        把额外宽度分给输入框，窗口缩放时各行比例保持不变。
        """
        pages = (self.ui.Result, self.ui.Capacitor, self.ui.MOS)
        for page in pages:
            # 纯收音机按钮的 GroupBox 自带边距，会把一行撑得很高
            for box in page.findChildren(QGroupBox):
                if not box.title():
                    box.setStyleSheet(
                        "QGroupBox { border: none; margin: 0; padding: 0; }")
            self._tidy_layout(page.layout(), root=True)
            # 标签统一宽度，同一页的输入框左边缘才能对齐
            self._align_labels(page)
            # 内容顶部对齐，避免窗口变高时各行被拉散
            self._append_bottom_stretch(page)

        # attr 原先排在 series 行末尾，窗口一宽就被长下拉框顶到最右边，
        # 用户很容易漏选。挪成单独一行，紧跟 series 下面。
        # 放在布局整理之后，行尾的弹簧才不会被 tidy 清掉。
        self._move_attr_row()

        # 「网表+工艺」页在设计器里用的是绝对坐标，窗口一大控件全挤在
        # 左上角、右边留一大片空白，这里重新排成随窗口伸缩的表单。
        self._rebuild_table_page()

        # 顶部「选择生成元件」一行同样去掉弹簧
        self._tidy_layout(self.ui.layout(), root=True)
        # 元件选择框给一个合适的宽度，剩下的空间留在行尾，
        # 否则「选择生成元件」标签会被拉长、把下拉框挤到最右边
        self.ui.comboBox.setMinimumWidth(160)
        self.ui.comboBox.setMaximumWidth(360)
        self.ui.horizontalLayout_7.addStretch(1)

    def _move_attr_row(self):
        """把电阻页的 attr 单选钮从 series 行末尾挪到单独一行"""
        series_row = self.ui.horizontalLayout
        attr_label = self.ui.label_24
        wo_box = self.ui.groupBox_3
        m_box = self.ui.groupBox_4

        for widget in (attr_label, wo_box, m_box):
            series_row.removeWidget(widget)

        attr_row = QHBoxLayout()
        attr_row.setContentsMargins(0, 0, 0, 0)
        attr_row.setSpacing(16)
        attr_row.addWidget(attr_label)
        attr_row.addWidget(wo_box)
        attr_row.addWidget(m_box)
        attr_row.addStretch(1)

        parent = self.ui.verticalLayout
        index = parent.indexOf(series_row)
        parent.insertLayout(index + 1, attr_row)

    def _rebuild_table_page(self):
        """重建「网表+工艺」页：绝对坐标 → 自适应表单布局"""
        page = self.ui.Table
        netlist_edit = self.ui.lineEditNetlist
        netlist_btn = self.ui.pushButtonSelectNetlist
        tech_edit = self.ui.lineEditTechDir
        tech_btn = self.ui.pushButtonSelectTechDir
        tech_combo = self.ui.comboBoxTech
        old_label = self.ui.linex
        generate_btn = self.ui.pushButtonGenerate
        progress = self.ui.progressBar

        # 先脱离设计器的绝对定位容器
        for widget in (netlist_edit, netlist_btn, tech_edit, tech_btn,
                       tech_combo, old_label, generate_btn, progress):
            widget.setParent(page)

        # 原来的三个 layoutWidget 已经空了，隐藏即可（删掉会留下悬空引用）
        for child in page.children():
            if isinstance(child, QWidget) and child.objectName() == "layoutWidget":
                child.hide()

        # 设计器里是拿 QLineEdit 当标签用的，换成真正的 QLabel
        old_label.hide()
        netlist_btn.setText("浏览…")
        tech_btn.setText("浏览…")
        generate_btn.setObjectName("primaryButton")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(10)

        netlist_row = QHBoxLayout()
        netlist_row.addWidget(netlist_edit, 1)
        netlist_row.addWidget(netlist_btn)
        form.addRow("网表文件：", netlist_row)

        tech_row = QHBoxLayout()
        tech_row.addWidget(tech_edit, 1)
        tech_row.addWidget(tech_btn)
        form.addRow("工艺文件目录：", tech_row)

        form.addRow("工艺文件：", tech_combo)
        layout.addLayout(form)

        # 生成按钮居中，不拉成整行长条
        generate_btn.setMinimumHeight(38)
        generate_btn.setMinimumWidth(160)
        generate_btn.setMaximumWidth(260)
        generate_btn.setCursor(Qt.PointingHandCursor)
        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(generate_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        progress.setMinimumHeight(18)
        layout.addWidget(progress)
        layout.addStretch()

    def _tidy_layout(self, layout, root=False):
        if layout is None:
            return

        # 先递归处理子布局，再处理自己
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is not None and item.layout() is not None:
                self._tidy_layout(item.layout())

        # 去掉水平弹簧：输入框自己会随窗口伸展
        for index in reversed(range(layout.count())):
            item = layout.itemAt(index)
            if isinstance(item, QSpacerItem):
                layout.removeItem(item)

        if root:
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(10)
        else:
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)

        if not isinstance(layout, QHBoxLayout):
            return

        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                if isinstance(widget, (QLineEdit, QComboBox, QAbstractSpinBox)):
                    layout.setStretch(index, 1)
                else:
                    # 标签、单选钮保留原尺寸；.ui 里给标签留的 stretch
                    # 必须清掉，否则多出来的宽度会被标签吃掉
                    layout.setStretch(index, 0)
                if isinstance(widget, QPushButton):
                    widget.setMinimumHeight(38)
                    widget.setMinimumWidth(120)
                    widget.setMaximumWidth(260)
                    layout.setAlignment(widget, Qt.AlignHCenter)
            elif item.layout() is not None:
                # MOS 页左右两列按 1:1 分配宽度
                layout.setStretch(index, 1)

    @staticmethod
    def _align_labels(page):
        """把一页里的标签设成同一最小宽度，输入框就能排成一列"""
        labels = page.findChildren(QLabel)
        if not labels:
            return
        # 超长标签不再继续加宽，避免把输入框挤没；上限跟着字号倍率走，
        # 否则放大后「MOS类型选择」这类标签会被截断
        target = min(max(label.sizeHint().width() for label in labels),
                     scale_px(150))
        for label in labels:
            label.setMinimumWidth(target)

    @staticmethod
    def _append_bottom_stretch(page):
        """在内容最下方加一个弹簧，窗口拉高时控件不会被竖向拉散"""
        layout = page.layout()
        if layout is None:
            return
        # MOS 根布局是横向的，取它里面的竖向内容列
        if isinstance(layout, QHBoxLayout) and layout.count():
            item = layout.itemAt(0)
            if item is not None and item.layout() is not None:
                layout = item.layout()
        # Result / Capacitor 外面多包了一层独占的 VBox，能往下走就往下走
        while isinstance(layout, QVBoxLayout) and layout.count() == 1:
            item = layout.itemAt(0)
            if item is None or item.layout() is None:
                break
            layout = item.layout()
        layout.addStretch(1)

    def setup_progress_bar(self):
        """设置进度条"""
        self.progress_bar = self.ui.progressBar
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setFormat("%v/%m")
        self.progress_bar.hide()

    def setup_radio_groups(self):
        # OD25相关单选按钮组
        self.od25_radio_group = QButtonGroup()
        self.od25_radio_group.addButton(self.ui.radioButton)
        self.od25_radio_group.addButton(self.ui.radioButton_2)
        self.od25_radio_group.addButton(self.ui.radioButton_5)
        self.od25_radio_group.setExclusive(True)

        # MOS类型单选按钮组
        self.mos_type_group = QButtonGroup()
        self.mos_type_group.addButton(self.ui.radioButton_3)  # NMOS
        self.mos_type_group.addButton(self.ui.radioButton_4)  # PMOS
        self.mos_type_group.setExclusive(True)

    def connect_signals(self, handlers):
        """连接UI信号到外部处理函数

        Args:
            handlers: 包含处理函数的字典，应有以下键：
                - generate_component: 生成组件按钮处理函数
                - generate_capacitor: 生成电容按钮处理函数
                - generate_mosfet: 生成MOSFET按钮处理函数
                - generate_from_netlist: 从网表生成按钮处理函数
        """
        # 组件生成按钮
        self.ui.pushButton.clicked.connect(handlers.get('generate_component'))
        self.ui.pushButton_2.clicked.connect(handlers.get('generate_capacitor'))
        self.ui.pushButton_3.clicked.connect(handlers.get('generate_mosfet'))

        # 网表文件选择
        self.ui.pushButtonSelectNetlist.clicked.connect(self.on_select_netlist)
        self.ui.pushButtonSelectTechDir.clicked.connect(self.on_select_tech_dir)
        self.ui.pushButtonGenerate.clicked.connect(handlers.get('generate_from_netlist'))

        # 下拉框变化
        self.ui.comboBox.currentIndexChanged.connect(
            lambda: self.ui.stackedWidget.setCurrentIndex(self.ui.comboBox.currentIndex())
        )

        # 复选框状态变化
        self.ui.checkBox.stateChanged.connect(self.on_od25_state_changed)
        self.ui.radioButton_3.toggled.connect(self.on_mos_type_changed)

    def on_select_netlist(self):
        """选择网表文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.ui,
            "选择网表文件",
            "",
            "Spice网表 (*.sp);;所有文件 (*)"
        )
        if file_path:
            self.ui.lineEditNetlist.setText(file_path)
            return file_path
        return None

    def on_select_tech_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self.ui,
            "选择工艺文件目录",
            ""
        )
        if dir_path:
            self.ui.lineEditTechDir.setText(dir_path)
            self.refresh_tech_combo(dir_path)
            return dir_path
        return None

    def refresh_tech_combo(self, tech_dir):
        """刷新工艺文件下拉框"""
        self.ui.comboBoxTech.clear()
        if not os.path.exists(tech_dir):
            return

        # 过滤工艺相关文件
        tech_files = [
            f for f in os.listdir(tech_dir)
            if os.path.isfile(os.path.join(tech_dir, f))
               and f.endswith(('.techfile', '.lef', '.gds'))
        ]
        self.ui.comboBoxTech.addItems(tech_files)

    def on_od25_state_changed(self, is_checked):
        """OD25复选框状态变化处理"""
        if not is_checked:
            self.od25_radio_group.setExclusive(False)
            for btn in self.od25_radio_group.buttons():
                btn.setChecked(False)
            self.od25_radio_group.setExclusive(True)

    def on_mos_type_changed(self, is_checked):
        """MOS类型变化处理"""
        if not is_checked:
            self.ui.checkBox_2.setChecked(False)

    def get_resistor_params(self):
        """获取电阻参数"""
        return {
            'series': self.ui.comboBox_2.currentText() == "True",
            'name': self.ui.lineEdit_4.text().strip(),
            'width': self.ui.lineEdit_6.text().strip(),
            'length': self.ui.lineEdit_3.text().strip(),
            'segments': self.ui.lineEdit_7.text().strip(),
            'seg_space': self.ui.lineEdit_5.text().strip() or "0.18",
            'attr': (['wo'] if self.ui.radioButton_7.isChecked()
                     else (['m'] if self.ui.radioButton_6.isChecked() else []))
        }

    def get_capacitor_params(self):
        """获取电容参数"""
        return {
            'name': self.ui.lineEdit.text().strip(),
            'width': self.ui.lineEdit_2.text().strip(),
            'length': self.ui.lineEdit_8.text().strip(),
            'spacing': self.ui.lineEdit_9.text().strip(),
            'nf': self.ui.lineEdit_10.text().strip(),
            'm_bot': int(self.ui.comboBox_10.currentText().strip('(默认）')),
            'm_top': int(self.ui.comboBox_11.currentText().strip('（默认）')),
            'f_tip': self.ui.lineEdit_23.text().strip() or "0.14",
            'flatten': self.ui.comboBox_8.currentText() == "True",
            'attr': self.ui.comboBox_9.currentText()
        }

    def get_mosfet_params(self):
        """获取MOSFET参数"""
        # 构建属性列表
        attr = []
        if self.ui.checkBox.isChecked():
            attr.append('25')
            if self.ui.radioButton.isChecked():
                attr.append('ud')
            elif self.ui.radioButton_2.isChecked():
                attr.append('od')

        if self.ui.checkBox_2.isChecked() and self.ui.radioButton_3.isChecked():
            attr.append('na')

        if self.ui.checkBox_3.isChecked():
            attr.append('mac')

        vt_type = self.ui.comboBox_7.currentText()
        if vt_type in ['lvt', 'hvt']:
            attr.append(vt_type)

        # 解析体连接方式
        bulk_con = []
        bulk_con_text = self.ui.comboBox_6.currentText()
        if bulk_con_text == '0(S)':
            bulk_con = [0]
        elif bulk_con_text == '1(G)':
            bulk_con = [1]
        elif bulk_con_text == '2(D)':
            bulk_con = [2]

        return {
            'is_nmos': self.ui.radioButton_3.isChecked(),
            'is_pmos': self.ui.radioButton_4.isChecked(),
            'name': self.ui.lineEdit_11.text().strip(),
            'width': self.ui.lineEdit_12.text().strip(),
            'length': self.ui.lineEdit_13.text().strip(),
            'nf': self.ui.lineEdit_14.text().strip(),
            'spectre': self.ui.checkBox_4.isChecked(),
            'attr': attr,
            'pin_con_type': self.ui.comboBox_5.currentText(),
            'bulk_con': bulk_con
        }

    def get_netlist_path(self):
        """获取网表文件路径"""
        return self.ui.lineEditNetlist.text().strip()

    def get_tech_dir(self):
        """获取工艺文件目录"""
        return self.ui.lineEditTechDir.text().strip()

    def validate_number(self, value_str, field_name, value_type=float):
        """验证数字输入"""
        if not value_str:
            return None
        try:
            return value_type(value_str)
        except ValueError:
            return None

    def show_warning(self, title, message):
        """显示警告消息框"""
        QMessageBox.warning(self.ui, title, message)

    def show_error(self, title, message):
        """显示错误消息框"""
        QMessageBox.critical(self.ui, title, message)

    def show_info(self, title, message):
        """显示信息消息框"""
        QMessageBox.information(self.ui, title, message)

    def show_progress(self, show=True):
        """显示或隐藏进度条"""
        if show:
            self.progress_bar.show()
        else:
            self.progress_bar.hide()

    def update_progress(self, current, total):
        """更新进度条"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

    def reset_progress(self):
        """重置进度条"""
        self.progress_bar.setValue(0)
        self.progress_bar.hide()