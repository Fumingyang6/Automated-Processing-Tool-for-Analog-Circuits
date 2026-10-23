"""GDS 版图查看器。

按层着色渲染 GDS 文件，右侧带图层面板可以逐层显隐、双击单独看某一层。
用 gdspy 解析（比项目里那份 2010 年的 gdsii 库完整得多），matplotlib 画图。

画法参照 KLayout：深色画布 + 明亮层次色 + **描边**。
描边而不是实心填充，是因为版图里各层互相叠压，实填充会把下层整个盖掉。

界面上去掉了标题栏和 matplotlib 自带的导航工具条（那些图标没多大用，
却各占一行高度），缩放平移自己做，只保留一个「存图」按钮：

    滚轮缩放（以光标为中心） / 双击复位 / 左键拖动平移 / 右键框选放大
"""

import os

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTreeWidget, QTreeWidgetItem, QFileDialog, QMessageBox,
)
from PyQt5.QtGui import QIcon, QPixmap, QColor
from PyQt5.QtCore import Qt

import matplotlib

matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.collections import PolyCollection

from ui_style import PAGE_STYLE, cjk_font_properties, scale_px

# 画布底色，照着 KLayout 的深色底来
CANVAS_BG = "#1a1a1a"

# KLayout 那类明亮层次色，在深色底上分得开
LAYER_PALETTE = (
    "#4d9de0", "#ff8c42", "#3ddc84", "#ff5c5c", "#4ecdc4",
    "#ffd93d", "#c792ea", "#ffa8c0", "#c9a227", "#b0b0b0",
    "#5fc9f8", "#ff7ab6", "#8ab4f8", "#ffb86c", "#7ee787",
    "#e3b341", "#56d4dd", "#f2cc60", "#d2a8ff", "#9aa0a6",
)

# 每个图形层的描边线宽（点）
OUTLINE_WIDTH = 0.35

# 标签太多会让绘制很慢，超过这个数就只画前面一部分
LABEL_LIMIT = 2000

# 标签字号（点）。matplotlib 的文字是固定磅值、不随缩放变大，
# 所以太小的话放大也读不出来；5 左右是「放大能看清、缩小成一片」的折中
LABEL_SIZE = 5

# 滚轮每格的缩放系数：上滚乘 ZOOM_IN，下滚乘 ZOOM_OUT
ZOOM_IN = 0.8
ZOOM_OUT = 1.25


class GdsViewer(QWidget):
    """一个 GDS 文件的版图视图（画布 + 图层面板）"""

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self.setStyleSheet(PAGE_STYLE)

        self.path = path
        self.polygons = {}      # {(层, 类型): [多边形数组]}
        self.labels = {}        # {(层, 类型): [(x, y, 文字), ...]}
        self.layer_colors = {}
        self.collections = {}   # {(层, 类型): PolyCollection}
        self.label_artists = {} # {(层, 类型): [Text, ...]}，用到才建
        self.layer_kind = {}    # {(层, 类型): "graphic" | "label"}
        self.full_bbox = None   # 整张版图的包围盒，用来复位
        self._pan_origin = None # 拖动平移的起点
        self._loading = False

        self.build_ui()
        self.load(path)

    # ==================== 界面 ====================
    def build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(2, 2, 2, 2)
        root.setSpacing(6)

        self.figure = Figure(figsize=(6, 5), facecolor=CANVAS_BG)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setFocusPolicy(Qt.ClickFocus)
        self.ax = self.figure.add_subplot(111)

        # matplotlib 的 Qt 画布会把鼠标事件转成这些回调，
        # 而且直接带上光标处的数据坐标，缩放和平移不用自己做像素换算
        self.canvas.mpl_connect("scroll_event", self.on_scroll)
        self.canvas.mpl_connect("button_press_event", self.on_press)
        self.canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.canvas.mpl_connect("button_release_event", self.on_release)

        root.addWidget(self.canvas, 1)
        root.addWidget(self.build_layer_panel())

    def build_layer_panel(self):
        panel = QWidget()
        # 三个紧凑按钮横排，宽度随字体倍率放大，避免放大后文字被挤掉
        panel.setFixedWidth(scale_px(196))
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(4)
        head.addWidget(QLabel("图层"))
        head.addStretch()
        for text, slot, tip in (
            ("全显", lambda: self.set_all_layers(True), "勾选全部图层"),
            ("全隐", lambda: self.set_all_layers(False), "取消全部图层"),
            ("存图", self.save_image, "把当前视图存成图片"),
        ):
            button = QPushButton(text)
            # 用紧凑样式：按内容自适应宽度，别写死宽度，否则两个字会被裁掉
            button.setObjectName("compactButton")
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip(tip)
            button.setMinimumWidth(40)      # 留点余量，免得字体差异把字挤掉
            button.clicked.connect(slot)
            head.addWidget(button)
        layout.addLayout(head)

        self.layer_tree = QTreeWidget()
        self.layer_tree.setHeaderLabels(["层", "数量"])
        self.layer_tree.setColumnWidth(0, 110)
        self.layer_tree.setRootIsDecorated(False)
        self.layer_tree.itemChanged.connect(self.on_layer_item_changed)
        self.layer_tree.itemDoubleClicked.connect(self.on_layer_double_clicked)
        self.layer_tree.setToolTip(
            "勾选控制显隐；双击某一层＝只看这一层。\n带 T 的是文字标签层，默认不勾选。")
        layout.addWidget(self.layer_tree, 1)
        return panel

    # ==================== 读取 ====================
    @staticmethod
    def spec_of(element):
        """gdspy 里 Polygon/Path 用 layers/datatypes（复数列表），Label 用 layer/datatype，
        这里统一成 (层, 类型) 元组"""
        layers = getattr(element, "layers", None)
        if layers is None:
            layers = [getattr(element, "layer", 0)]
        datatypes = getattr(element, "datatypes", None)
        if datatypes is None:
            datatypes = [getattr(element, "datatype", 0)]
        return (layers[0], datatypes[0] if datatypes[0] is not None else 0)

    def load(self, path):
        if not os.path.exists(path):
            self.show_message(f"文件不存在：{path}")
            return
        try:
            import gdspy
        except ImportError:
            self.show_message("没有安装 gdspy，无法渲染 GDS 版图。\n\n安装：pip install gdspy")
            return

        try:
            library = gdspy.GdsLibrary(infile=path)
        except Exception as exc:
            self.show_message(f"这个 GDS 读不出来：\n\n{exc}")
            return

        top_cells = library.top_level()
        if not top_cells:
            self.show_message("这个 GDS 里没有顶层结构。")
            return
        self.top_cell = top_cells[0]

        try:
            # by_spec=True 按 (层, 类型) 分组，并顺带把引用层级展开
            self.polygons = {k: v for k, v in
                             self.top_cell.get_polygons(by_spec=True).items() if len(v)}
            self.labels = self.collect_labels(self.top_cell)
        except Exception as exc:
            self.show_message(f"提取图形失败：\n\n{exc}")
            return

        if not self.polygons and not self.labels:
            self.show_message("这个 GDS 里没有可画的图形。")
            return

        for spec in self.polygons:
            self.layer_kind[spec] = "graphic"
        for spec in self.labels:
            self.layer_kind.setdefault(spec, "label")

        self.assign_colors()
        self.build_layer_tree()
        self.draw_all()

    def collect_labels(self, cell):
        """按层收集文字标签；顶层展开后数量可能上千，这里先截断"""
        grouped = {}
        for label in cell.get_labels():
            spec = self.spec_of(label)
            bucket = grouped.setdefault(spec, [])
            if len(bucket) < LABEL_LIMIT:
                position = label.position
                bucket.append((float(position[0]), float(position[1]), label.text))
        return {k: v for k, v in grouped.items() if v}

    def show_message(self, text):
        self.ax.clear()
        self.ax.set_axis_off()
        self.ax.set_facecolor(CANVAS_BG)
        self.figure.set_facecolor(CANVAS_BG)
        self.ax.text(0.5, 0.5, text.splitlines()[0], ha="center", va="center",
                     fontsize=11, color="#a8abb2",
                     fontproperties=cjk_font_properties())
        self.ax.set_position([0, 0, 1, 1])
        self.canvas.draw_idle()

    def assign_colors(self):
        specs = sorted(self.polygons) + sorted(s for s in self.labels if s not in self.polygons)
        for index, spec in enumerate(specs):
            self.layer_colors[spec] = LAYER_PALETTE[index % len(LAYER_PALETTE)]

    @staticmethod
    def color_icon(color):
        pixmap = QPixmap(14, 14)
        pixmap.fill(QColor(color))
        return QIcon(pixmap)

    def build_layer_tree(self):
        self._loading = True
        self.layer_tree.clear()
        for spec in sorted(set(self.polygons) | set(self.labels)):
            is_label = self.layer_kind.get(spec) == "label"
            count = len(self.polygons.get(spec)) if not is_label else len(self.labels[spec])
            name = f"{spec[0]}/{spec[1]}" + ("  T" if is_label else "")
            item = QTreeWidgetItem([name, str(count)])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            # 标签层默认不勾选：上千个文字全画出来既慢又糊成一团
            item.setCheckState(0, Qt.Unchecked if is_label else Qt.Checked)
            item.setIcon(0, self.color_icon(self.layer_colors[spec]))
            item.setData(0, Qt.UserRole, spec)
            self.layer_tree.addTopLevelItem(item)
        self._loading = False

    # ==================== 绘制 ====================
    def draw_all(self):
        self.ax.clear()
        self.collections.clear()
        self.label_artists.clear()

        for spec in sorted(self.polygons):
            color = self.layer_colors[spec]
            # 描边画法：实填充会把下层整个盖掉，版图看不出层次
            collection = PolyCollection(self.polygons[spec], facecolors="none",
                                        edgecolors=color, linewidths=OUTLINE_WIDTH)
            self.ax.add_collection(collection)
            self.collections[spec] = collection

        self.full_bbox = self.top_cell.get_bounding_box()
        self.apply_full_view()
        self.ax.set_aspect("equal")
        self.ax.set_facecolor(CANVAS_BG)
        # 只看版图，不需要坐标系：刻度、边框、网格全部关掉
        self.ax.set_axis_off()
        # 坐标轴铺满整块画布，边距全去掉，图能画到最大
        self.ax.set_position([0, 0, 1, 1])
        self.canvas.draw_idle()
        self.apply_visibility()

    def apply_visibility(self):
        items = self.layer_items()
        for spec, collection in self.collections.items():
            item = items.get(spec)
            collection.set_visible(item is not None and item.checkState(0) == Qt.Checked)
        for spec in self.labels:
            self.apply_label_visibility(spec)
        self.canvas.draw_idle()

    def apply_label_visibility(self, spec):
        item = self.layer_items().get(spec)
        visible = item is not None and item.checkState(0) == Qt.Checked

        if not visible:
            for artist in self.label_artists.get(spec, []):
                artist.set_visible(False)
            return

        # 标签第一次显示时才创建 Text 对象，避免开图就卡
        if spec not in self.label_artists:
            color = self.layer_colors[spec]
            props = cjk_font_properties()
            self.label_artists[spec] = [
                self.ax.text(x, y, text, fontsize=LABEL_SIZE, color=color,
                             ha="left", va="center", clip_on=True,
                             fontproperties=props)
                for x, y, text in self.labels[spec]
            ]
        else:
            for artist in self.label_artists[spec]:
                artist.set_visible(True)

    def layer_items(self):
        return {self.layer_tree.topLevelItem(i).data(0, Qt.UserRole):
                self.layer_tree.topLevelItem(i)
                for i in range(self.layer_tree.topLevelItemCount())}

    # ==================== 缩放平移 ====================
    def on_scroll(self, event):
        """滚轮缩放：以光标所在的位置为中心"""
        if event.xdata is None or event.ydata is None:
            return                      # 光标在坐标区外面
        factor = ZOOM_IN if event.step > 0 else ZOOM_OUT
        self.zoom_at(event.xdata, event.ydata, factor)

    def zoom_at(self, center_x, center_y, factor):
        """把显示范围以 (center_x, center_y) 为中心缩放 factor 倍（<1 放大）"""
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        self.ax.set_xlim(center_x + (x0 - center_x) * factor,
                         center_x + (x1 - center_x) * factor)
        self.ax.set_ylim(center_y + (y0 - center_y) * factor,
                         center_y + (y1 - center_y) * factor)
        self.canvas.draw_idle()

    def on_press(self, event):
        """左键按下：双击复位，单击准备拖动平移"""
        if event.inaxes is not self.ax:
            return
        if event.dblclick and event.button == 1:
            self.fit_view()
            self._pan_origin = None
            return
        if event.button == 1:
            self._pan_origin = (event.x, event.y, self.ax.get_xlim(),
                                self.ax.get_ylim(), self.ax.get_window_extent())

    def on_motion(self, event):
        """左键按住拖动 = 平移"""
        if self._pan_origin is None or event.x is None:
            return
        x0, y0, xlim, ylim, extent = self._pan_origin
        # 像素位移换算成数据位移
        dx = (event.x - x0) / extent.width * (xlim[1] - xlim[0])
        dy = (event.y - y0) / extent.height * (ylim[1] - ylim[0])
        self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
        self.ax.set_ylim(ylim[0] - dy, ylim[1] - dy)
        self.canvas.draw_idle()

    def on_release(self, _event):
        self._pan_origin = None

    def apply_full_view(self):
        """按整张版图设置显示范围，留 1% 边距"""
        if self.full_bbox is None:
            return
        (x0, y0), (x1, y1) = self.full_bbox
        pad_x = (x1 - x0) * 0.01
        pad_y = (y1 - y0) * 0.01
        self.ax.set_xlim(x0 - pad_x, x1 + pad_x)
        self.ax.set_ylim(y0 - pad_y, y1 + pad_y)

    def fit_view(self):
        self.apply_full_view()
        self.canvas.draw_idle()

    # ==================== 存图 ====================
    def save_image(self):
        name = os.path.splitext(os.path.basename(self.path))[0] + ".png"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存版图图片", os.path.join(os.path.dirname(self.path), name),
            "PNG 图片 (*.png);;SVG 矢量图 (*.svg);;PDF (*.pdf)")
        if not path:
            return
        try:
            # facecolor 传上，否则存出来的图会丢掉深色底
            self.figure.savefig(path, dpi=200, facecolor=self.figure.get_facecolor())
        except Exception as exc:
            QMessageBox.warning(self, "保存失败", f"存图出错：\n\n{exc}")

    # ==================== 图层交互 ====================
    def on_layer_item_changed(self, _item, _column):
        if not self._loading:
            self.apply_visibility()

    def on_layer_double_clicked(self, item, _column):
        """双击某一层：只看它；如果本来就只有它显示，则恢复全显"""
        target = item.data(0, Qt.UserRole)
        items = self.layer_items()
        checked = [spec for spec, entry in items.items()
                   if entry.checkState(0) == Qt.Checked]
        solo = len(checked) == 1 and checked[0] == target

        self._loading = True
        for spec, entry in items.items():
            want = True if solo else (spec == target)
            entry.setCheckState(0, Qt.Checked if want else Qt.Unchecked)
        self._loading = False
        self.apply_visibility()

    def set_all_layers(self, checked):
        self._loading = True
        for index in range(self.layer_tree.topLevelItemCount()):
            self.layer_tree.topLevelItem(index).setCheckState(
                0, Qt.Checked if checked else Qt.Unchecked)
        self._loading = False
        self.apply_visibility()


# 模块可以独立运行测试
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QFont

    app = QApplication(sys.argv)
    from ui_style import cjk_font_family
    font = QFont(cjk_font_family())
    font.setPointSize(10)
    app.setFont(font)

    target = sys.argv[1] if len(sys.argv) > 1 else None
    if not target:
        print("用法: python gds_viewer.py <文件.gds>")
        sys.exit(1)

    window = GdsViewer(target)
    window.setWindowTitle(f"版图 - {os.path.basename(target)}")
    window.resize(1100, 750)
    window.show()
    sys.exit(app.exec_())
