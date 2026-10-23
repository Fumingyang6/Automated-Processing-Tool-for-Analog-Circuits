# -*- coding: utf-8 -*-
"""
三合一集成工具：RSMT计算 → 走线合法化 → GDS版图生成
页面切换：顶部三个按钮切换三步功能页面
依赖：
1. 同目录必须存在 UnionFind.py
2. 同目录准备好 nets.txt、CP_OP2.txt
3. 依赖库：pip install pyqt5 matplotlib gdsii
"""
import math
import os
import ast
import sys
import re
import random
import time
import io

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ====================== 第三方库导入 ======================
try:
    from gdsii import tags, types
    from gdsii.record import Record
except ImportError:
    print("请先安装依赖：pip install gdsii", file=sys.stderr)
    sys.exit(1)

# Matplotlib
plt_available = True
MATPLOTLIB_AVAIL = True
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
except ImportError:
    plt_available = False
    MATPLOTLIB_AVAIL = False

# PyQt5
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QPushButton, QCheckBox,
                             QTextEdit, QVBoxLayout, QHBoxLayout, QLabel, QFileDialog,
                             QStackedWidget)
from PyQt5.QtCore import Qt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

# ====================== 公共基础类 & 工具函数（全部原样保留） ======================
# 并查集（同目录必须有 UnionFind.py）
try:
    from UnionFind import UnionFind
except ImportError:
    print("错误：同目录缺少 UnionFind.py 文件！", file=sys.stderr)
    sys.exit(1)

class Point:
    """Point Class for Steiner"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.deg = 0
        self.edges = []
        self.MSTedges = []

    def update(self, edge):
        self.edges.append(edge)

    def reset(self):
        self.edges = []
        self.deg = 0
        self.MSTedges = []

    def MSTupdate(self, edge):
        self.deg += 1
        self.MSTedges.append(edge)

class ref:
    """指针代理类"""
    def __init__(self, obj):
        self.obj = obj

    def get(self):
        return self.obj

    def set(self, obj):
        self.obj = obj

class Line:
    """线段类"""
    def __init__(self, p1, p2, w):
        self.points = []
        self.points.append(ref(p1))
        self.points.append(ref(p2))
        self.w = w

    def getOther(self, pt):
        if pt == self.points[0].get():
            return self.points[1]
        elif pt == self.points[1].get():
            return self.points[0]
        else:
            print("Error: Line does not contain this point")

    def getFirst(self):
        return self.points[0]

    def getLast(self):
        return self.points[1]

def Kruskal(SetOfPoints):
    for i in range(0, len(SetOfPoints)):
        SetOfPoints[i].reset()
    for i in range(0, len(SetOfPoints)):
        for j in range(i, len(SetOfPoints)):
            if i != j:
                dist = (abs(SetOfPoints[i].x - SetOfPoints[j].x) + abs(SetOfPoints[i].y - SetOfPoints[j].y))
                line = Line(SetOfPoints[i], SetOfPoints[j], dist)
                SetOfPoints[i].update(line)
                SetOfPoints[j].update(line)
            else:
                dist = 100000
                line = Line(SetOfPoints[i], SetOfPoints[j], dist)
                SetOfPoints[i].update(line)
    G = {}
    for i in range(0, len(SetOfPoints)):
        subset = {}
        for j in range(0, len(SetOfPoints[i].edges)):
            subset[j] = SetOfPoints[i].edges[j].w
        G[i] = subset
    subtrees = UnionFind()
    tree = []
    for W, u, v in sorted((G[u][v], u, v) for u in G for v in G[u]):
        if subtrees[u] != subtrees[v]:
            tree.append([u, v])
            subtrees.union(u, v)
    MST = []
    for i in range(0, len(tree)):
        point1 = SetOfPoints[tree[i][0]]
        point2 = SetOfPoints[tree[i][1]]
        for j in range(0, len(point1.edges)):
            if point2 == point1.edges[j].getOther(point1).get():
                point1.MSTupdate(point1.edges[j])
                point2.MSTupdate(point1.edges[j])
                MST.append(point1.edges[j])
    return MST

def DeltaMST(SetOfPoints, TestPoint):
    MST = Kruskal(SetOfPoints)
    cost1 = sum(edge.w for edge in MST)
    combo = SetOfPoints + [TestPoint]
    MST = Kruskal(combo)
    cost2 = sum(edge.w for edge in MST)
    return cost1 - cost2

def HananPoints(SetOfPoints):
    SomePoints = []
    for i in range(0, len(SetOfPoints)):
        for j in range(i, len(SetOfPoints)):
            if i != j:
                SomePoints.append(Point(SetOfPoints[i].x, SetOfPoints[j].y))
                SomePoints.append(Point(SetOfPoints[j].x, SetOfPoints[i].y))
    return SomePoints

def computeRSMT(OriginalPoints):
    RectSteinerPoints = []
    Candidate_Set = [0]
    while Candidate_Set != []:
        maxPoint = Point(0, 0)
        current_total = OriginalPoints + RectSteinerPoints
        Candidate_Set = [x for x in HananPoints(current_total) if DeltaMST(current_total, x) > 0]
        cost = 0
        for pt in Candidate_Set:
            DeltaCost = DeltaMST(current_total, pt)
            if DeltaCost > cost:
                maxPoint = pt
                cost = DeltaCost
        if maxPoint.x != 0 and maxPoint.y != 0:
            RectSteinerPoints.append(maxPoint)
        temp_list = []
        for pt in RectSteinerPoints:
            if pt.deg > 2:
                temp_list.append(pt)
        RectSteinerPoints = temp_list
    RSMT = Kruskal(OriginalPoints + RectSteinerPoints)
    return RSMT, RectSteinerPoints

def read_file_point(file_path):
    all_lists = []
    current_list = None
    with open(file_path, 'r', encoding='utf-8') as file:
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
                    current_list.append(Point(x, y))
    if current_list:
        all_lists.append(current_list)
    return all_lists

def remove_duplicate_elements(original_list):
    new_list = []
    for tup in original_list:
        if tup[0] != tup[1]:
            new_list.append(tup)
    return new_list

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

def read_file_tuple(file_path):
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

# 走线合法化相关函数
def trees_spacing_detect(data, threshold=560):
    horizontal_spacings = []
    vertical_spacings = []
    num_sublists = len(data)
    results = []
    for i in range(num_sublists):
        for j in range(i + 1, num_sublists):
            sublist1 = data[i]
            sublist2 = data[j]
            horizontal_lines1 = [line for line in sublist1 if line[0][1] == line[1][1] and abs(line[1][0] - line[0][0]) > 0]
            vertical_lines1 = [line for line in sublist1 if line[0][0] == line[1][0] and abs(line[1][1] - line[0][1]) > 0]
            horizontal_lines2 = [line for line in sublist2 if line[0][1] == line[1][1] and abs(line[1][0] - line[0][0]) > 0]
            vertical_lines2 = [line for line in sublist2 if line[0][0] == line[1][0] and abs(line[1][1] - line[0][1]) > 0]
            y_coord1 = []
            x_range1 = []
            y_coord2 = []
            x_range2 = []
            for line1 in horizontal_lines1:
                y_coord1.append(line1[0][1])
                x_range1.append((line1[0][0], line1[1][0]))
            for line2 in horizontal_lines2:
                y_coord2.append(line2[0][1])
                x_range2.append((line2[0][0], line2[1][0]))
            for i1 in range(len(y_coord1)):
                for j1 in range(len(y_coord2)):
                    spacing = abs(y_coord1[i1] - y_coord2[j1])
                    if spacing < threshold:
                        x1_min, x1_max = min(x_range1[i1][0], x_range1[i1][1]), max(x_range1[i1][0], x_range1[i1][1])
                        x2_min, x2_max = min(x_range2[j1][0], x_range2[j1][1]), max(x_range2[j1][0], x_range2[j1][1])
                        if not (x1_max < x2_min or x2_max < x1_min):
                            results.append([sublist1, sublist2, spacing])
            x_coord1 = []
            y_range1 = []
            x_coord2 = []
            y_range2 = []
            for line11 in vertical_lines1:
                x_coord1.append(line11[0][0])
                y_range1.append((line11[0][1], line11[1][1]))
            for line21 in vertical_lines2:
                x_coord2.append(line21[0][0])
                y_range2.append((line21[0][1], line21[1][1]))
            for i2 in range(len(x_coord1)):
                for j2 in range(len(x_coord2)):
                    spacing = abs(x_coord1[i2] - x_coord2[j2])
                    if spacing < threshold:
                        y1_min, y1_max = min(y_range1[i2][0], y_range1[i2][1]), max(y_range1[i2][0], y_range1[i2][1])
                        y2_min, y2_max = min(y_range2[j2][0], y_range2[j2][1]), max(y_range2[j2][0], y_range2[j2][1])
                        if not (y1_max < y2_min or y2_max < y1_min):
                            results.append([sublist1, sublist2, spacing])
    return results

def is_horizontal(segment):
    return segment[0][1] == segment[1][1]

def is_vertical(segment):
    return segment[0][0] == segment[1][0]

def distance_between_parallel_segments(seg1, seg2):
    if is_horizontal(seg1) and is_horizontal(seg2):
        return abs(seg1[0][1] - seg2[0][1])
    elif is_vertical(seg1) and is_vertical(seg2):
        return abs(seg1[0][0] - seg2[0][0])
    return None

def segment_length(segment):
    p1, p2 = segment
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)

def total_segment_length(groups):
    total_length = 0
    for group in groups:
        for segment in group:
            total_length += segment_length(segment)
    return total_length

def replace_with_u_shape(segment1, segment2, shift):
    new_segments = []
    p1, p2 = segment1
    p3, p4 = segment2
    if is_horizontal(segment1):
        if p3[1] >= p1[1]:
            middle_y = p1[1] - shift
            new_segments = [(p1, (p1[0], middle_y)), ((p1[0], middle_y), (p2[0], middle_y)), ((p2[0], middle_y), p2)]
        else:
            middle_y = p1[1] + shift
            new_segments = [(p1, (p1[0], middle_y)), ((p1[0], middle_y), (p2[0], middle_y)), ((p2[0], middle_y), p2)]
    elif is_vertical(segment1):
        if p3[0] >= p1[0]:
            middle_x = p1[0] - shift
            new_segments = [(p1, (middle_x, p1[1])), ((middle_x, p1[1]), (middle_x, p2[1])), ((middle_x, p2[1]), p2)]
        else:
            middle_x = p1[0] + shift
            new_segments = [(p1, (middle_x, p1[1])), ((middle_x, p1[1]), (middle_x, p2[1])), ((middle_x, p2[1]), p2)]
    return new_segments

def adjust_segments(groups, threshold=450):
    group1, group2 = groups
    orig_group1 = group1.copy()
    orig_group2 = group2.copy()
    adjust_group1 = []
    adjust_group2 = []
    for i, seg1 in enumerate(group1):
        for j, seg2 in enumerate(group2):
            if (is_horizontal(seg1) and is_horizontal(seg2)) or (is_vertical(seg1) and is_vertical(seg2)):
                dist = distance_between_parallel_segments(seg1, seg2)
                if dist < threshold:
                    shift = threshold - dist
                    best_new_segments = replace_with_u_shape(seg1, seg2, shift)
                    adjust_group1 = group1[:i] + best_new_segments + group1[i + 1:]
    for k, seg1_1 in enumerate(orig_group1):
        for h, seg2_1 in enumerate(group2):
            if (is_horizontal(seg1_1) and is_horizontal(seg2_1)) or (is_vertical(seg1_1) and is_vertical(seg2_1)):
                dist1 = distance_between_parallel_segments(seg1_1, seg2_1)
                if dist1 < threshold:
                    shift1 = threshold - dist1
                    best_new_segments2 = replace_with_u_shape(seg2_1, seg1_1, shift1)
                    adjust_group2 = group2[:h] + best_new_segments2 + group2[h + 1:]
    adjust_group1 = list(set(adjust_group1))
    adjust_group2 = list(set(adjust_group2))
    return [orig_group1, adjust_group2], [adjust_group1, orig_group2]

def revised_steiner_trees(input_steiner_trees1, requir_adjust_trees1, adjusted_segments11):
    indices = []
    for t, sublist in enumerate(input_steiner_trees1):
        if sublist in requir_adjust_trees1[0][0:2]:
            indices.append(t)
    for l, index in enumerate(indices):
        input_steiner_trees1[index] = adjusted_segments11[l]
    # 注意：这里是原地修改 input_steiner_trees1，调用方需要自己备份原列表
    return input_steiner_trees1

# GDS解析相关
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

def calculate_rectangle_coordinates(center_x, center_y, width, height):
    half_width = width / 2
    half_height = height / 2
    coordinates = int(center_x - half_width), int(center_y - half_height), \
                   int(center_x + half_width), int(center_y - half_height), \
                   int(center_x + half_width), int(center_y + half_height), \
                   int(center_x - half_width), int(center_y + half_height), \
                   int(center_x - half_width), int(center_y - half_height)
    return coordinates

# 内嵌绘图通用函数
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

# ====================== 页面1：第一步 RSMT 计算页面 ======================
class PageRSMT(QWidget):
    def __init__(self):
        super().__init__()
        self.steiner_forests = []
        # 所有路径都基于BASE_DIR，固定在模块目录
        self.file_path = os.path.join(BASE_DIR, "nets.txt")
        self.save_default_name = os.path.join(BASE_DIR, "steiner_forest_result.txt")
        self.save_file_path = ""
        self.fig = Figure(figsize=(9, 6), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(15, 15, 15, 15)

        ctrl_widget = QWidget()
        ctrl_layout = QVBoxLayout(ctrl_widget)
        ctrl_layout.setSpacing(6)

        self.select_file_btn = QPushButton("选择网表文件(.txt)")
        self.select_file_btn.clicked.connect(self.on_select_file)
        self.file_label = QLabel(f"当前文件：{self.file_path}")
        ctrl_layout.addWidget(self.select_file_btn)
        ctrl_layout.addWidget(self.file_label)

        self.draw_checkbox = QCheckBox("开启界面内绘图显示")
        self.draw_checkbox.setChecked(True)
        self.draw_checkbox.toggled.connect(self.toggle_plot_area)
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self.clear_log_text)
        ctrl_layout.addWidget(self.draw_checkbox)
        ctrl_layout.addWidget(self.clear_log_btn)

        self.run_btn = QPushButton("开始计算 RSMT")
        self.run_btn.clicked.connect(self.on_run_task)
        self.run_btn.setFixedHeight(38)
        ctrl_layout.addWidget(self.run_btn)

        self.save_result_btn = QPushButton("保存斯坦纳森林结果")
        self.save_result_btn.clicked.connect(self.save_forest_result)
        self.save_result_btn.setFixedHeight(38)
        ctrl_layout.addWidget(self.save_result_btn)
        self.save_path_label = QLabel("保存路径：暂未保存")
        ctrl_layout.addWidget(self.save_path_label)

        self.status_label = QLabel("状态：就绪")
        ctrl_layout.addWidget(self.status_label)
        main_layout.addWidget(ctrl_widget)

        self.toolbar.setVisible(True)
        self.canvas.setVisible(True)
        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(self.canvas)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("运行结果、斯坦纳森林、Via坐标将展示在这里...")
        main_layout.addWidget(self.result_text, stretch=1)

    def toggle_plot_area(self, is_checked):
        self.toolbar.setVisible(is_checked)
        self.canvas.setVisible(is_checked)

    def clear_log_text(self):
        self.result_text.clear()

    def on_select_file(self):
        # 文件对话框默认打开到模块目录
        path, _ = QFileDialog.getOpenFileName(self, "选择网表文件", BASE_DIR, "Text Files (*.txt);;All Files (*)")
        if path:
            self.file_path = path
            self.file_label.setText(f"当前文件：{self.file_path}")

    def save_forest_result(self):
        if not self.steiner_forests:
            self.result_text.append("\n>>> 提示：暂无计算结果，无法保存！请先执行计算")
            self.status_label.setText("状态：无结果可保存")
            return
        try:
            # 保存对话框默认定位到模块目录
            path, _ = QFileDialog.getSaveFileName(self, "保存斯坦纳森林结果", self.save_default_name, "Text Files (*.txt);;All Files (*)")
            if not path:
                return
            save_content = f"cp_op2_3 = {self.steiner_forests}"
            with open(path, "w", encoding="utf-8") as f:
                f.write(save_content)
            self.save_file_path = path
            self.save_path_label.setText(f"保存路径：{path}")
            self.result_text.append(f"\n>>> 斯坦纳森林结果已成功保存至：{path}")
            self.status_label.setText("状态：结果保存成功")
        except Exception as e:
            err = f"\n>>> 保存失败：{str(e)}"
            self.result_text.append(err)
            self.status_label.setText("状态：保存失败")

    def run_rsmt_task(self, fig, is_draw: bool, txt_path: str):
        start_time = time.time()
        if not os.path.exists(txt_path):
            raise FileNotFoundError(f"文件不存在：{txt_path}")
        lists = read_file_point(txt_path)
        paths = []
        steiner_trees = []
        all_length = 0
        fig.clear()
        ax = fig.add_subplot(111)
        ax.set_aspect("equal")
        for idx, sublist in enumerate(lists, 1):
            OriginalPoints = sublist
            RSMT1, Steiner_points = computeRSMT(OriginalPoints)
            path = []
            RSMTminDist = 0
            for line_obj in RSMT1:
                RSMTminDist += line_obj.w
                p1 = line_obj.points[0].get()
                p2 = line_obj.points[1].get()
                path.append(((p1.x, p1.y), (p1.x, p2.y)))
                path.append(((p1.x, p2.y), (p2.x, p2.y)))
            clean_path = remove_duplicate_elements(path)
            steiner_trees.append(clean_path)
            paths.extend(clean_path)
            all_length += RSMTminDist
            if is_draw:
                for (x1,y1),(x2,y2) in clean_path:
                    if x1 == x2:
                        ax.plot([x1, x2], [y1, y2], 'r-', linewidth=2)
                    else:
                        ax.plot([x1, x2], [y1, y2], 'g-', linewidth=2)
                for pt in OriginalPoints:
                    ax.plot(pt.x, pt.y, 'wo', markersize=10, markeredgecolor='k')
                for st_pt in Steiner_points:
                    ax.plot(st_pt.x, st_pt.y, 'ko', markersize=10)
                ax.text(0.02, 0.98, f'Net{idx} Length: {RSMTminDist}', transform=ax.transAxes, verticalalignment='top')
        if is_draw:
            ax.set_xlabel("X")
            ax.set_ylabel("Y")
            ax.grid(True)
            ax.set_title("Rectilinear Steiner Minimum Tree - All Nets")
        via_points = via_coordinates(steiner_trees)
        run_time = time.time() - start_time
        fig.canvas.draw()
        return steiner_trees, all_length, via_points, run_time, paths

    def on_run_task(self):
        self.run_btn.setEnabled(False)
        self.status_label.setText("状态：计算中，请稍候...")
        self.save_path_label.setText("保存路径：暂未保存")
        try:
            is_draw = self.draw_checkbox.isChecked()
            target_file = self.file_path
            forests, total_len, via_pts, cost_time, all_paths = self.run_rsmt_task(self.fig, is_draw, target_file)
            self.steiner_forests = forests
            res = "======= 计算完成 =======\n"
            res += f"运行耗时：{cost_time:.4f} 秒\n"
            res += f"总线网布线长度：{total_len}\n"
            res += f"Via(通孔)坐标列表：\n{via_pts}\n\n"
            res += f"【斯坦纳森林列表】\n"
            for idx, tree in enumerate(forests, 1):
                res += f"线网{idx} 斯坦纳树：{tree}\n"
            res += f"\n【全部走线路径】\n{all_paths}"
            self.result_text.setText(res)
            self.status_label.setText("状态：计算完成，可点击保存结果")
        except Exception as e:
            err_msg = f"运行出错：{str(e)}"
            self.result_text.setText(err_msg)
            self.status_label.setText("状态：运行失败")
        finally:
            self.run_btn.setEnabled(True)

# ====================== 页面2：第二步 走线合法化调整页面（已修改） ======================
class PageAdjust(QWidget):
    def __init__(self):
        super().__init__()
        self.cp_op2_3 = None
        self.final_steiner_trees = None
        self.result_file_path = ""
        self.save_default_name = os.path.join(BASE_DIR, "leg_cp_op2_3_result.txt")
        # 新增：nets.txt 文件路径，默认同目录
        self.nets_file_path = os.path.join(BASE_DIR, 'nets.txt')
        self.fig = Figure(figsize=(9, 6), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(15, 15, 15, 15)
        ctrl_widget = QWidget()
        ctrl_layout = QVBoxLayout(ctrl_widget)
        ctrl_layout.setSpacing(6)

        # 选择第一步结果文件
        self.select_result_btn = QPushButton("选择第一步斯坦纳森林结果文件(.txt)")
        self.select_result_btn.clicked.connect(self.load_result_file)
        self.file_tip_label = QLabel("当前加载文件：未选择")
        ctrl_layout.addWidget(self.select_result_btn)
        ctrl_layout.addWidget(self.file_tip_label)

        # 新增：选择 nets.txt 文件
        self.select_nets_btn = QPushButton("选择 nets.txt 文件")
        self.select_nets_btn.clicked.connect(self.select_nets_file)
        self.nets_label = QLabel(f"当前 nets 文件：{self.nets_file_path}")
        ctrl_layout.addWidget(self.select_nets_btn)
        ctrl_layout.addWidget(self.nets_label)

        self.draw_checkbox = QCheckBox("开启界面内绘图显示")
        self.draw_checkbox.setChecked(True)
        self.draw_checkbox.toggled.connect(self.toggle_plot_area)
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self.clear_log)
        ctrl_layout.addWidget(self.draw_checkbox)
        ctrl_layout.addWidget(self.clear_log_btn)

        self.run_btn = QPushButton("开始执行间距检测 & 合法化调整")
        self.run_btn.clicked.connect(self.run_all_task)
        self.run_btn.setFixedHeight(38)
        ctrl_layout.addWidget(self.run_btn)

        self.save_final_btn = QPushButton("保存调整后斯坦纳树列表")
        self.save_final_btn.clicked.connect(self.save_final_steiner)
        self.save_final_btn.setFixedHeight(38)
        ctrl_layout.addWidget(self.save_final_btn)
        self.save_path_label = QLabel("结果保存路径：暂未保存")
        ctrl_layout.addWidget(self.save_path_label)

        self.status_label = QLabel("状态：就绪，请先选择结果文件")
        ctrl_layout.addWidget(self.status_label)
        main_layout.addWidget(ctrl_widget)

        self.toolbar.setVisible(True)
        self.canvas.setVisible(True)
        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(self.canvas)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("运行日志、检测结果、线长变化、点位信息将在此展示...")
        main_layout.addWidget(self.log_text, stretch=1)

    def toggle_plot_area(self, is_checked):
        self.toolbar.setVisible(is_checked)
        self.canvas.setVisible(is_checked)

    def clear_log(self):
        self.log_text.clear()

    def load_result_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择斯坦纳森林结果文件", BASE_DIR, "Text Files (*.txt);;All Files (*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            temp_dict = {}
            exec(content, {}, temp_dict)
            self.cp_op2_3 = temp_dict["cp_op2_3"]
            self.result_file_path = path
            self.file_tip_label.setText(f"当前加载文件：{path}")
            self.log_text.append(">>> 结果文件加载成功，已自动赋值给 cp_op2_3")
            self.status_label.setText("状态：文件加载完成，可开始运行")
            self.final_steiner_trees = None
            self.save_path_label.setText("结果保存路径：暂未保存")
        except Exception as e:
            err = f">>> 文件解析失败：{str(e)}"
            self.log_text.append(err)
            self.status_label.setText("状态：文件加载失败")
            self.cp_op2_3 = None

    # 新增：选择 nets.txt 文件
    def select_nets_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 nets.txt", BASE_DIR, "Text Files (*.txt);;All Files (*)")
        if path:
            self.nets_file_path = path
            self.nets_label.setText(f"当前 nets 文件：{path}")

    def save_final_steiner(self):
        if self.final_steiner_trees is None:
            self.log_text.append("\n>>> 提示：暂无调整后的结果，请先执行【间距检测 & 合法化调整】！")
            self.status_label.setText("状态：无结果可保存")
            return
        try:
            path, _ = QFileDialog.getSaveFileName(self, "保存调整后斯坦纳树列表", self.save_default_name, "Text Files (*.txt);;All Files (*)")
            if not path:
                return
            save_content = f"leg_cp_op2_3 = {self.final_steiner_trees}"
            with open(path, "w", encoding="utf-8") as f:
                f.write(save_content)
            self.save_path_label.setText(f"结果保存路径：{path}")
            self.log_text.append(f"\n>>> 调整后斯坦纳树列表已成功保存至：{path}")
            self.status_label.setText("状态：结果保存成功")
        except Exception as e:
            err = f"\n>>> 保存失败：{str(e)}"
            self.log_text.append(err)
            self.status_label.setText("状态：保存失败")

    def run_all_task(self):
        if self.cp_op2_3 is None:
            self.log_text.append(">>> 错误：请先选择并加载上一步的结果文件！")
            self.status_label.setText("状态：缺少输入数据")
            return
        # 检查 nets 文件是否存在
        if not os.path.exists(self.nets_file_path):
            self.log_text.append(f">>> 错误：nets.txt 文件不存在：{self.nets_file_path}，请重新选择！")
            self.status_label.setText("状态：nets 文件缺失")
            return

        self.run_btn.setEnabled(False)
        self.status_label.setText("状态：正在执行检测与调整，请稍候...")
        self.log_text.append("\n======= 开始执行间距检测 & 走线合法化 =======")
        try:
            input_steiner_trees = self.cp_op2_3
            orig_wl = total_segment_length(input_steiner_trees)
            threshold = 560
            log_buffer = []
            for _ in range(1000):
                requir_adjust_trees = trees_spacing_detect(input_steiner_trees, threshold)
                log_buffer.append(f"本轮需要调整的树对数量：{len(requir_adjust_trees)}")
                if len(requir_adjust_trees) == 0:
                    break
                elif len(requir_adjust_trees) > 0:
                    adjusted_segments1, adjusted_segments2 = adjust_segments(requir_adjust_trees[0][0:2], threshold)
                    input_steiner_trees2 = input_steiner_trees.copy()
                    if len(trees_spacing_detect(revised_steiner_trees(input_steiner_trees, requir_adjust_trees, adjusted_segments1))) < len(requir_adjust_trees):
                        log_buffer.append("本轮选择：方案1")
                    else:
                        log_buffer.append("本轮选择：方案2")
                        input_steiner_trees = revised_steiner_trees(input_steiner_trees2, requir_adjust_trees, adjusted_segments2)
            add_length = total_segment_length(input_steiner_trees) - orig_wl
            log_buffer.append(f"\n合法化新增总线长：{add_length:.2f}")
            # 使用用户选择的 nets 文件路径
            file_path = self.nets_file_path
            lists = read_file_tuple(file_path)
            OriginalPoints, steiner_points = distinguishing_point(lists, input_steiner_trees)
            log_buffer.append(f"原始引脚数量：{len(OriginalPoints)}")
            log_buffer.append(f"斯坦纳点数量：{len(steiner_points)}")
            log_buffer.append(f"斯坦纳点坐标：{steiner_points}")
            self.final_steiner_trees = input_steiner_trees
            self.log_text.append("\n".join(log_buffer))
            self.log_text.append("\n>>> 全部流程执行完成，可点击【保存调整后斯坦纳树列表】导出结果！")
            if self.draw_checkbox.isChecked():
                ax = self.fig.add_subplot(111)
                display_plot_inside(ax, OriginalPoints, steiner_points, input_steiner_trees)
                self.canvas.draw()
            self.status_label.setText("状态：执行完成")
        except Exception as e:
            err_msg = f"\n>>> 运行出错：{str(e)}"
            self.log_text.append(err_msg)
            self.status_label.setText("状态：运行失败")
            self.final_steiner_trees = None
        finally:
            self.run_btn.setEnabled(True)

# ====================== 页面3：第三步 GDS版图生成页面 ======================
class PageGDS(QWidget):
    def __init__(self):
        super().__init__()
        self.file_cp_op2_3 = ""
        self.file_leg_cp_op2_3 = ""
        self.file_nets = ""
        self.file_cp_op2_txt = ""
        self.cp_op2_3 = None
        self.leg_cp_op2_3 = None
        self.fig = Figure(figsize=(9, 6), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(15, 15, 15, 15)
        ctrl_widget = QWidget()
        ctrl_layout = QVBoxLayout(ctrl_widget)
        ctrl_layout.setSpacing(6)

        self.btn_cp_op2_3 = QPushButton("1.  选择第一步结果文件(.txt)")
        self.btn_cp_op2_3.clicked.connect(self.select_cp_op2_3)
        self.label_cp_op2_3 = QLabel("路径：未选择")
        ctrl_layout.addWidget(self.btn_cp_op2_3)
        ctrl_layout.addWidget(self.label_cp_op2_3)

        self.btn_leg_cp_op2_3 = QPushButton("2. 选择第二步结果文件(.txt)")
        self.btn_leg_cp_op2_3.clicked.connect(self.select_leg_cp_op2_3)
        self.label_leg_cp_op2_3 = QLabel("路径：未选择")
        ctrl_layout.addWidget(self.btn_leg_cp_op2_3)
        ctrl_layout.addWidget(self.label_leg_cp_op2_3)

        self.btn_nets = QPushButton("3. 选择 网表文件txt")
        self.btn_nets.clicked.connect(self.select_nets)
        self.label_nets = QLabel("路径：未选择")
        ctrl_layout.addWidget(self.btn_nets)
        ctrl_layout.addWidget(self.label_nets)

        self.btn_cp_op2_txt = QPushButton("4. 选择 布局文件txt")
        self.btn_cp_op2_txt.clicked.connect(self.select_cp_op2_txt)
        self.label_cp_op2_txt = QLabel("路径：未选择")
        ctrl_layout.addWidget(self.btn_cp_op2_txt)
        ctrl_layout.addWidget(self.label_cp_op2_txt)

        self.check_draw = QCheckBox("开启界面内绘图显示")
        self.check_draw.setChecked(True)
        self.check_draw.toggled.connect(self.toggle_draw_area)
        self.btn_clear_log = QPushButton("清空日志")
        self.btn_clear_log.clicked.connect(self.clear_log)
        ctrl_layout.addWidget(self.check_draw)
        ctrl_layout.addWidget(self.btn_clear_log)

        self.btn_run = QPushButton("开始生成 GDS 版图")
        self.btn_run.clicked.connect(self.run_full_task)
        self.btn_run.setFixedHeight(38)
        ctrl_layout.addWidget(self.btn_run)

        self.label_status = QLabel("状态：就绪，请依次选择4个输入文件")
        ctrl_layout.addWidget(self.label_status)
        main_layout.addWidget(ctrl_widget)

        self.toolbar.setVisible(True)
        self.canvas.setVisible(True)
        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(self.canvas)

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlaceholderText("运行日志、点位信息、文件生成状态将在此展示...")
        main_layout.addWidget(self.log_edit, stretch=1)

    def toggle_draw_area(self, is_checked):
        self.toolbar.setVisible(is_checked)
        self.canvas.setVisible(is_checked)

    def clear_log(self):
        self.log_edit.clear()

    def select_cp_op2_3(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 cp_op2_3 文件", BASE_DIR, "Text Files (*.txt)")
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
        path, _ = QFileDialog.getOpenFileName(self, "选择 leg_cp_op2_3 文件", BASE_DIR, "Text Files (*.txt)")
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
        path, _ = QFileDialog.getOpenFileName(self, "选择 nets.txt", BASE_DIR, "Text Files (*.txt)")
        if not path:
            return
        self.file_nets = path
        self.label_nets.setText(f"路径：{path}")
        self.log_edit.append(">>> nets.txt 文件加载成功")

    def select_cp_op2_txt(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 CP_OP2.txt", BASE_DIR, "Text Files (*.txt)")
        if not path:
            return
        self.file_cp_op2_txt = path
        self.label_cp_op2_txt.setText(f"路径：{path}")
        self.log_edit.append(">>> CP_OP2.txt 文件加载成功")

    class LogRedirect(io.StringIO):
        def __init__(self, log_widget):
            super().__init__()
            self.log_widget = log_widget
        def write(self, s):
            if s.strip():
                self.log_widget.append(s.strip())

    def run_full_task(self):
        if not all([self.cp_op2_3, self.leg_cp_op2_3, self.file_nets, self.file_cp_op2_txt]):
            self.log_edit.append("\n>>> 错误：请先完整选择4个输入文件！")
            self.label_status.setText("状态：缺少输入文件")
            return
        self.btn_run.setEnabled(False)
        self.label_status.setText("状态：正在生成GDS版图，请稍候...")
        self.log_edit.append("\n======= 开始执行GDS版图生成全流程 =======")
        old_stdout = sys.stdout
        sys.stdout = self.LogRedirect(self.log_edit)
        try:
            input_steiners = self.cp_op2_3
            net_path = self.file_nets
            original_file_path = self.file_cp_op2_txt
            paths = []
            net_lists = read_file_tuple(net_path)
            OriginalPoints, intersec_points = distinguishing_point(net_lists, input_steiners)
            print('斯坦纳点（通孔）', intersec_points)
            print('原有点', OriginalPoints)
            if self.check_draw.isChecked() and MATPLOTLIB_AVAIL:
                ax = self.fig.add_subplot(111)
                display_plot_inside(ax, OriginalPoints, intersec_points, input_steiners)
                self.canvas.draw()
            for group in input_steiners:
                paths.extend(group)
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
            routing_txt = os.path.join(BASE_DIR, 'leg_cp_op2_routing.txt')
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
            new_file_path = os.path.join(BASE_DIR, 'CP_OP2_placement+routing.txt')
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
            gds_routing_path = os.path.join(BASE_DIR, 'leg_cp_op2_routing.gds')
            with open(gds_routing_path, 'wb') as ofile:
                with open(routing_txt, 'r') as ifile:
                    parse_file(ifile, ofile)
            print(">>> 布线GDS文件生成完成：leg_cp_op2_routing.gds")
            gds_full_path = os.path.join(BASE_DIR, 'CP_OP2_placement+routing.gds')
            with open(gds_full_path, 'wb') as ofile:
                with open(new_file_path, 'r') as ifile:
                    parse_file(ifile, ofile)
            print(">>> 合并版图GDS文件生成完成：CP_OP2_placement+routing.gds")
            print("\n>>> 全流程执行完毕！所有GDS文件已自动保存到模块目录")
            self.label_status.setText("状态：全部任务执行完成")
        except Exception as e:
            err = f"\n>>> 运行异常：{str(e)}"
            self.log_edit.append(err)
            self.label_status.setText("状态：运行失败")
        finally:
            sys.stdout = old_stdout
            self.btn_run.setEnabled(True)

class RSMTRoutingWidget(QWidget):
    """布局布线模块主界面，封装为QWidget，可直接嵌入主UI标签页"""
    def __init__(self):
        super().__init__()

        # 顶部切换按钮栏
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setSpacing(10)
        top_layout.setContentsMargins(10,10,10,10)

        self.btn_page1 = QPushButton("第一步：RSMT斯坦纳树计算")
        self.btn_page2 = QPushButton("第二步：走线间距合法化调整")
        self.btn_page3 = QPushButton("第三步：GDS版图自动生成")
        self.btn_page1.setFixedHeight(35)
        self.btn_page2.setFixedHeight(35)
        self.btn_page3.setFixedHeight(35)

        top_layout.addWidget(self.btn_page1)
        top_layout.addWidget(self.btn_page2)
        top_layout.addWidget(self.btn_page3)

        # 堆叠页面容器
        self.stack = QStackedWidget()
        self.page1 = PageRSMT()
        self.page2 = PageAdjust()
        self.page3 = PageGDS()
        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)
        self.stack.addWidget(self.page3)

        # 主布局：直接挂载到当前QWidget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)
        main_layout.addWidget(top_widget)
        main_layout.addWidget(self.stack)

        # 初始化按钮样式
        self.update_active_button(0)

        # 绑定页面切换事件
        self.btn_page1.clicked.connect(lambda: self.switch_to_page(0))
        self.btn_page2.clicked.connect(lambda: self.switch_to_page(1))
        self.btn_page3.clicked.connect(lambda: self.switch_to_page(2))

    def switch_to_page(self, index):
        """切换到指定页面"""
        self.stack.setCurrentIndex(index)
        self.update_active_button(index)

    def update_active_button(self, active_index):
        """更新顶部按钮高亮状态，风格可按需和主UI统一"""
        normal_style = """
        QPushButton {
            background-color: #f5f5f5;
            border: 1px solid #d9d9d9;
            border-radius: 5px;
            padding: 6px 14px;
            color: #555555;
            font-size: 13px;
        }
        QPushButton:hover {
            background-color: #e8e8e8;
            border-color: #bfbfbf;
        }
        """
        active_style = """
        QPushButton {
            background-color: #1890ff;
            border: 1px solid #1890ff;
            border-radius: 5px;
            padding: 6px 14px;
            color: white;
            font-size: 13px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #40a9ff;
            border-color: #40a9ff;
        }
        """
        self.btn_page1.setStyleSheet(active_style if active_index == 0 else normal_style)
        self.btn_page2.setStyleSheet(active_style if active_index == 1 else normal_style)
        self.btn_page3.setStyleSheet(active_style if active_index == 2 else normal_style)

# ========== 模块独立运行调试 ==========
if __name__ == "__main__":
    from PyQt5.QtWidgets import QMainWindow

    app = QApplication(sys.argv)

    # 独立运行时套一层主窗口
    main_win = QMainWindow()
    main_win.setWindowTitle("RSMT布局布线工具")
    main_win.resize(1050, 800)

    widget = RSMTRoutingWidget()
    main_win.setCentralWidget(widget)
    main_win.show()

    sys.exit(app.exec_())