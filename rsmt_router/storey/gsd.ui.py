#! /usr/bin/python
# -*- coding: utf-8 -*-
"""
第三步：根据Steiner树、网表、布局文件 自动生成最终GDS版图
输入4个文件：cp_op2_3文本、leg_cp_op2_3文本、nets.txt、CP_OP2.txt
输出：leg_cp_op2_routing.gds 、 CP_OP2_placement+routing.gds（自动保存到同级目录）
"""
from __future__ import print_function
import sys
import re
import os
import random
import time
import io

# ====================== 第三方依赖 ======================
try:
    from gdsii import tags, types
    from gdsii.record import Record
except ImportError:
    print("请先安装依赖：pip install gdsii", file=sys.stderr)
    sys.exit(1)

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    MATPLOTLIB_AVAIL = True
except ImportError:
    MATPLOTLIB_AVAIL = False

# ====================== PyQt5 界面模块 ======================
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QCheckBox,
                             QTextEdit, QVBoxLayout, QWidget, QLabel, QFileDialog)
from PyQt5.QtCore import Qt

# Matplotlib 内嵌Qt绘图
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

# ====================== 【你的原始业务代码 完全原样保留 无任何修改】 ======================
def parse_file(ifile, ofile):
    rexp = re.compile(r'^(?P<tag>[^:]+)(:\s*(?P<rest>.*))?$')
    lineno = 1
    for line in ifile:
        stripped = line.strip()
        m = rexp.match(stripped)
        if not m:
            print('Parse error at line {0}'.format(lineno), file=sys.stderr)
            sys.exit(1)
        tag_name = m.group('tag')
        rest = m.group('rest')
        tag = tags.DICT[tag_name]
        tag_type = tags.type_of_tag(tag)

        if tag_type == types.NODATA:
            data = None
        elif tag_type == types.ASCII:
            data = rest[1:-1].encode()
        elif tag_type == types.BITARRAY:
            data = int(rest)
        elif tag_type == types.REAL8:
            data = [float(s) for s in rest.split(',')]
        elif tag_type == types.INT2 or tag_type == types.INT4:
            data = [int(s) for s in rest.split(',')]
        else:
            raise Exception('Unsupported type')
        rec = Record(tag, data)
        rec.save(ofile)
        lineno += 1

def via_coordinates(trees):
    intersection_points = []
    for tree in trees:
        horizontal_lines = []
        vertical_lines = []
        for line in tree:
            (x1, y1), (x2, y2) = line
            if y1 == y2:
                horizontal_lines.append(line)
            elif x1 == x2:
                vertical_lines.append(line)
        for h_line in horizontal_lines:
            (hx1, hy), (hx2, _) = h_line
            for v_line in vertical_lines:
                (vx, vy1), (_, vy2) = v_line
                if min(hx1, hx2) <= vx <= max(hx1, hx2) and min(vy1, vy2) <= hy <= max(vy1, vy2):
                    int_vx = int(vx)
                    int_hy = int(hy)
                    intersection_points.append((int_vx, int_hy))
    return intersection_points

def draw_rectangles(lines, width):
    if not MATPLOTLIB_AVAIL:
        return
    fig, ax = plt.subplots()
    for line in lines:
        (x1, y1), (x2, y2) = line
        if y1 == y2:
            bottom_left = (min(x1, x2), y1 - width / 2)
            w = abs(x2 - x1)
            h = width
            rect = patches.Rectangle(bottom_left, w, h, linewidth=2, edgecolor='g', facecolor='g')
            ax.add_patch(rect)
        elif x1 == x2:
            bottom_left = (x1 - width / 2, min(y1, y2))
            w = width
            h = abs(y2 - y1)
            rect = patches.Rectangle(bottom_left, w, h, linewidth=2, edgecolor='r', facecolor='r')
            ax.add_patch(rect)
    ax.autoscale_view()
    plt.show()

def calculate_rectangle_coordinates(center_x, center_y, width, height):
    half_width = width / 2
    half_height = height / 2
    coordinates = int(center_x - half_width), int(center_y - half_height), \
                   int(center_x + half_width), int(center_y - half_height), \
                   int(center_x + half_width), int(center_y + half_height), \
                   int(center_x - half_width), int(center_y + half_height), \
                   int(center_x - half_width), int(center_y - half_height)
    return coordinates

def read_file(file_path):
    all_lists = []
    current_list = None
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if line.startswith('num net'):
                continue
            if line.startswith('A'):
                if current_list is not None:
                    all_lists.append(current_list)
                current_list = []
            else:
                if line:
                    x, y = map(int, line.split())
                    current_list.append((x, y))
    if current_list:
        all_lists.append(current_list)
    return all_lists

def distinguishing_point(pins_connect, trees):
    pins = []
    all_points = []
    for j in range(len(pins_connect)):
        for point in pins_connect[j]:
            pins.append(point)
    for sublist in trees:
        for segment in sublist:
            start_point = segment[0]
            end_point = segment[1]
            all_points.append(start_point)
            all_points.append(end_point)
            all_points = list(set(all_points))
    steiner_points = [element for element in all_points if element not in pins]
    return pins, steiner_points

def display_plot(pins, s_points, trees):
    if not MATPLOTLIB_AVAIL:
        return
    fig, ax = plt.subplots()
    for sub_list in trees:
        for segment in sub_list:
            (x1, y1), (x2, y2) = segment
            if y1 == y2:
                ax.plot([x1, x2], [y1, y2], 'r-')
            elif x1 == x2:
                ax.plot([x1, x2], [y1, y2], 'g-')
    x_coords = [point[0] for point in pins]
    y_coords = [point[1] for point in pins]
    x_coords1 = [point[0] for point in s_points]
    y_coords1 = [point[1] for point in s_points]
    plt.scatter(x_coords, y_coords, color='black', s=20)
    plt.scatter(x_coords1, y_coords1, color='orange', s=20)
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.grid(True)
    plt.show()

# ====================== 【UI内嵌绘图函数（适配Qt画布）】 ======================
def display_plot_inside(ax, pins, s_points, trees):
    ax.clear()
    for sub_list in trees:
        for segment in sub_list:
            (x1, y1), (x2, y2) = segment
            if y1 == y2:
                ax.plot([x1, x2], [y1, y2], 'r-')
            elif x1 == x2:
                ax.plot([x1, x2], [y1, y2], 'g-')
    if pins:
        x_coords = [p[0] for p in pins]
        y_coords = [p[1] for p in pins]
        ax.scatter(x_coords, y_coords, color='black', s=20)
    if s_points:
        x_coords1 = [p[0] for p in s_points]
        y_coords1 = [p[1] for p in s_points]
        ax.scatter(x_coords1, y_coords1, color='orange', s=20)
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.grid(True)
    ax.set_aspect("equal")
    ax.set_title("布线版图可视化")

# ====================== 【第三步主UI界面】 ======================
class GdsGenerateUI(QMainWindow):
    def __init__(self):
        super().__init__()
        # 全局变量：4个文件路径
        self.file_cp_op2_3 = ""       # 输入1：cp_op2_3 文本
        self.file_leg_cp_op2_3 = ""   # 输入2：leg_cp_op2_3 文本
        self.file_nets = ""           # 输入3：nets.txt
        self.file_cp_op2_txt = ""     # 输入4：CP_OP2.txt

        # 解析后的Steiner树数据
        self.cp_op2_3 = None
        self.leg_cp_op2_3 = None

        # 绘图组件初始化
        self.fig = Figure(figsize=(9, 6), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("GDS版图自动生成工具（第三步）")
        self.setGeometry(100, 80, 1000, 750)

        # 主布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 顶部控制区域
        ctrl_widget = QWidget()
        ctrl_layout = QVBoxLayout(ctrl_widget)
        ctrl_layout.setSpacing(6)

        # ========== 1. 四个文件选择项 ==========
        # 1-1 选择 cp_op2_3 文件
        self.btn_cp_op2_3 = QPushButton("1. 选择 cp_op2_3 结果文件(.txt)")
        self.btn_cp_op2_3.clicked.connect(self.select_cp_op2_3)
        self.label_cp_op2_3 = QLabel("路径：未选择")
        ctrl_layout.addWidget(self.btn_cp_op2_3)
        ctrl_layout.addWidget(self.label_cp_op2_3)

        # 1-2 选择 leg_cp_op2_3 文件
        self.btn_leg_cp_op2_3 = QPushButton("2. 选择 leg_cp_op2_3 结果文件(.txt)")
        self.btn_leg_cp_op2_3.clicked.connect(self.select_leg_cp_op2_3)
        self.label_leg_cp_op2_3 = QLabel("路径：未选择")
        ctrl_layout.addWidget(self.btn_leg_cp_op2_3)
        ctrl_layout.addWidget(self.label_leg_cp_op2_3)

        # 1-3 选择 nets.txt
        self.btn_nets = QPushButton("3. 选择 网表文件 nets.txt")
        self.btn_nets.clicked.connect(self.select_nets)
        self.label_nets = QLabel("路径：未选择")
        ctrl_layout.addWidget(self.btn_nets)
        ctrl_layout.addWidget(self.label_nets)

        # 1-4 选择 CP_OP2.txt
        self.btn_cp_op2_txt = QPushButton("4. 选择 布局文件 CP_OP2.txt")
        self.btn_cp_op2_txt.clicked.connect(self.select_cp_op2_txt)
        self.label_cp_op2_txt = QLabel("路径：未选择")
        ctrl_layout.addWidget(self.btn_cp_op2_txt)
        ctrl_layout.addWidget(self.label_cp_op2_txt)

        # ========== 2. 绘图开关 + 清空日志 ==========
        self.check_draw = QCheckBox("开启界面内绘图显示")
        self.check_draw.setChecked(True)
        self.check_draw.toggled.connect(self.toggle_draw_area)

        self.btn_clear_log = QPushButton("清空日志")
        self.btn_clear_log.clicked.connect(self.clear_log)
        ctrl_layout.addWidget(self.check_draw)
        ctrl_layout.addWidget(self.btn_clear_log)

        # ========== 3. 运行主按钮 ==========
        self.btn_run = QPushButton("开始生成 GDS 版图")
        self.btn_run.clicked.connect(self.run_full_task)
        self.btn_run.setFixedHeight(38)
        ctrl_layout.addWidget(self.btn_run)

        # ========== 4. 状态提示 ==========
        self.label_status = QLabel("状态：就绪，请依次选择4个输入文件")
        ctrl_layout.addWidget(self.label_status)

        main_layout.addWidget(ctrl_widget)

        # 绘图区域
        self.toolbar.setVisible(True)
        self.canvas.setVisible(True)
        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(self.canvas)

        # 日志输出区域
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlaceholderText("运行日志、点位信息、文件生成状态将在此展示...")
        main_layout.addWidget(self.log_edit, stretch=1)

    # ========== 绘图区显隐 ==========
    def toggle_draw_area(self, is_checked):
        self.toolbar.setVisible(is_checked)
        self.canvas.setVisible(is_checked)

    # ========== 清空日志 ==========
    def clear_log(self):
        self.log_edit.clear()

    # ========== 四个文件选择函数 ==========
    def select_cp_op2_3(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 cp_op2_3 文件", "./", "Text Files (*.txt)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            temp_dict = {}
            exec(content, {}, temp_dict)
            self.cp_op2_3 = temp_dict["cp_op2_3"]
            self.file_cp_op2_3 = path
            self.label_cp_op2_3.setText(f"路径：{path}")
            self.log_edit.append(">>> cp_op2_3 文件加载成功")
        except Exception as e:
            self.log_edit.append(f">>> cp_op2_3 解析失败：{str(e)}")
            self.cp_op2_3 = None

    def select_leg_cp_op2_3(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 leg_cp_op2_3 文件", "./", "Text Files (*.txt)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            temp_dict = {}
            exec(content, {}, temp_dict)
            self.leg_cp_op2_3 = temp_dict["leg_cp_op2_3"]
            self.file_leg_cp_op2_3 = path
            self.label_leg_cp_op2_3.setText(f"路径：{path}")
            self.log_edit.append(">>> leg_cp_op2_3 文件加载成功")
        except Exception as e:
            self.log_edit.append(f">>> leg_cp_op2_3 解析失败：{str(e)}")
            self.leg_cp_op2_3 = None

    def select_nets(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 nets.txt", "./", "Text Files (*.txt)")
        if not path:
            return
        self.file_nets = path
        self.label_nets.setText(f"路径：{path}")
        self.log_edit.append(">>> nets.txt 文件加载成功")

    def select_cp_op2_txt(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 CP_OP2.txt", "./", "Text Files (*.txt)")
        if not path:
            return
        self.file_cp_op2_txt = path
        self.label_cp_op2_txt.setText(f"路径：{path}")
        self.log_edit.append(">>> CP_OP2.txt 文件加载成功")

    # ========== 重定向print输出到日志框 ==========
    class LogRedirect(io.StringIO):
        def __init__(self, log_widget):
            super().__init__()
            self.log_widget = log_widget
        def write(self, s):
            if s.strip():
                self.log_widget.append(s.strip())

    # ========== 主运行函数（执行全流程） ==========
    def run_full_task(self):
        # 前置校验：4个文件必须全部加载完成
        if not all([self.cp_op2_3, self.leg_cp_op2_3, self.file_nets, self.file_cp_op2_txt]):
            self.log_edit.append("\n>>> 错误：请先完整选择4个输入文件！")
            self.label_status.setText("状态：缺少输入文件")
            return

        self.btn_run.setEnabled(False)
        self.label_status.setText("状态：正在生成GDS版图，请稍候...")
        self.log_edit.append("\n======= 开始执行GDS版图生成全流程 =======")

        # 重定向print到日志框
        old_stdout = sys.stdout
        sys.stdout = self.LogRedirect(self.log_edit)

        try:
            # --------------- 替换原代码硬编码变量 ---------------
            input_steiners = self.cp_op2_3
            net_path = self.file_nets
            original_file_path = self.file_cp_op2_txt
            paths = []

            # 读取网表
            net_lists = read_file(net_path)
            # 区分引脚和Steiner点
            OriginalPoints, intersec_points = distinguishing_point(net_lists, input_steiners)
            print('斯坦纳点（通孔）', intersec_points)
            print('原有点', OriginalPoints)

            # 内嵌绘图
            if self.check_draw.isChecked() and MATPLOTLIB_AVAIL:
                ax = self.fig.add_subplot(111)
                display_plot_inside(ax, OriginalPoints, intersec_points, input_steiners)
                self.canvas.draw()

            # 拼接所有走线
            for group in input_steiners:
                paths.extend(group)

            # 生成布线GDS中间文本
            width = 220
            lines = paths
            header_info = """HEADER: 600
BGNLIB: 110, 8, 17, 14, 22, 22, 110, 8, 17, 14, 36, 21
LIBNAME: "TEST.DB"
UNITS: 0.001, 1e-09
BGNSTR: 70, 1, 1, 1, 0, 0, 110, 8, 17, 14, 35, 55
STRNAME: "test_struc1"
"""
            end_info = """ENDSTR
ENDLIB"""
            routing_txt = 'leg_cp_op2_routing.txt'
            with open(routing_txt, 'w') as file:
                file.write(header_info)
                for line in lines:
                    (x1, y1), (x2, y2) = line
                    if x1 == x2:
                        layer = 62
                    else:
                        layer = 63
                    path_info = f"""PATH
LAYER: {layer}
DATATYPE: 0
PATHTYPE: 0
WIDTH: {width}
XY: {x1}, {y1}, {x2}, {y2}
ENDEL
"""
                    file.write(path_info)
                for point in intersec_points:
                    x3, y3, x4, y4, x5, y5, x6, y6, x7, y7 = calculate_rectangle_coordinates(point[0], point[1], 760, 240)
                    x3_1, y3_1, x4_1, y4_1, x5_1, y5_1, x6_1, y6_1, x7_1, y7_1 = calculate_rectangle_coordinates(point[0]-220, point[1], 220, 220)
                    x3_2, y3_2, x4_2, y4_2, x5_2, y5_2, x6_2, y6_2, x7_2, y7_2 = calculate_rectangle_coordinates(point[0] + 220, point[1], 220,220)
                    boundary_info = f"""BOUNDARY
LAYER: 62
DATATYPE: 0
XY: {x3}, {y3}, {x4}, {y4}, {x5}, {y5}, {x6}, {y6}, {x7}, {y7}
ENDEL
BOUNDARY
LAYER: 63
DATATYPE: 0
XY: {x3}, {y3}, {x4}, {y4}, {x5}, {y5}, {x6}, {y6}, {x7}, {y7}
ENDEL
BOUNDARY
LAYER: 70
DATATYPE: 0
XY: {x3_1}, {y3_1}, {x4_1}, {y4_1}, {x5_1}, {y5_1}, {x6_1}, {y6_1}, {x7_1}, {y7_1}
ENDEL
BOUNDARY
LAYER: 70
DATATYPE: 0
XY: {x3_2}, {y3_2}, {x4_2}, {y4_2}, {x5_2}, {y5_2}, {x6_2}, {y6_2}, {x7_2}, {y7_2}
ENDEL
"""
                    file.write(boundary_info)
                file.write(end_info)

            # 合并布局+布线文本
            new_file_path = './CP_OP2_placement+routing.txt'
            extracted_content = []
            start_extracting = False
            with open(routing_txt, 'r', encoding='utf-8') as source_file:
                for line in source_file:
                    if line.strip().startswith('STRNAME: "test_struc1"'):
                        start_extracting = True
                        continue
                    if line.strip() == 'ENDSTR':
                        start_extracting = False
                        break
                    if start_extracting:
                        extracted_content.append(line)

            with open(original_file_path, 'r', encoding='utf-8') as original_file:
                lines = original_file.readlines()

            def is_bgnstr(line): return line.strip().startswith("BGNSTR")
            def is_endstr(line): return line.strip().startswith("ENDSTR")
            def is_strname(line): return line.strip().startswith("STRNAME")

            valid_blocks = []
            block_start = None
            strname_idx = None
            for idx, line in enumerate(lines):
                if is_bgnstr(line):
                    block_start = idx
                    strname_idx = None
                elif block_start is not None and is_strname(line):
                    strname_idx = idx
                elif block_start is not None and is_endstr(line):
                    block_valid = True
                    for inner_idx in range(block_start + 1, idx):
                        inner_line = lines[inner_idx]
                        if inner_line.strip() != "" and not is_strname(inner_line):
                            block_valid = False
                            break
                    if block_valid and strname_idx is not None:
                        valid_blocks.append((block_start, strname_idx, idx))
                    block_start = None

            if valid_blocks:
                last_block = valid_blocks[-1]
                last_strname_idx = last_block[1]
                lines[last_strname_idx + 1:last_strname_idx + 1] = extracted_content

            with open(new_file_path, 'w', encoding='utf-8') as new_file:
                new_file.writelines(lines)

            # 自动生成 布线GDS
            with open('./leg_cp_op2_routing.gds', 'wb') as ofile:
                with open(routing_txt, 'r') as ifile:
                    parse_file(ifile, ofile)
            print(">>> 布线GDS文件生成完成：leg_cp_op2_routing.gds")

            # 自动生成 布局+布线GDS
            with open('./CP_OP2_placement+routing.gds', 'wb') as ofile:
                with open(new_file_path, 'r') as ifile:
                    parse_file(ifile, ofile)
            print(">>> 合并版图GDS文件生成完成：CP_OP2_placement+routing.gds")

            print("\n>>> 全流程执行完毕！所有GDS文件已自动保存到程序同级目录")
            self.label_status.setText("状态：全部任务执行完成")

        except Exception as e:
            err = f"\n>>> 运行异常：{str(e)}"
            self.log_edit.append(err)
            self.label_status.setText("状态：运行失败")
        finally:
            # 恢复标准输出
            sys.stdout = old_stdout
            self.btn_run.setEnabled(True)

# ====================== 程序入口 ======================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GdsGenerateUI()
    window.show()
    app.exec_()