# -*- coding: utf-8 -*-
import math
import os
import ast
import sys

# PyQt5 界面组件
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QCheckBox,
                             QTextEdit, QVBoxLayout, QWidget, QLabel, QFileDialog)
from PyQt5.QtCore import Qt

# Matplotlib 内嵌Qt绘图（替代独立弹窗）
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

# ====================== 【你的原始业务代码 完整原样复制 无任何修改】 ======================
plt_available = True
try:
    import matplotlib.pyplot as plt
except ImportError:
    plt_available = False

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
                    # current_list.append(Point(x, y))
                    current_list.append((x, y))
    if current_list:
        all_lists.append(current_list)
    return all_lists

def distinguishing_point(pins_connect, trees):
    pins = []
    all_points = []

    for j in range(len(pins_connect)):
        # 遍历点列表
        for point in pins_connect[j]:
            pins.append(point)
    # 遍历所有线段
    for sublist in trees:
        for segment in sublist:
            # 提取线段的起点和终点
            start_point = segment[0]
            end_point = segment[1]
            all_points.append(start_point)
            all_points.append(end_point)
            all_points = list(set(all_points))
    steiner_points = [element for element in all_points if element not in pins]

    return pins, steiner_points

# 原始独立绘图函数（保留，不修改）
def display_plot(pins, s_points, trees):
    if not plt_available:
        return
    # 创建图形和坐标轴
    fig, ax = plt.subplots()
    # 遍历每个子列表
    for sub_list in trees:
        for segment in sub_list:
            # 提取线段的两个端点坐标
            (x1, y1), (x2, y2) = segment
            if y1 == y2:  # 水平线
                ax.plot([x1, x2], [y1, y2], 'r-')  # 红色
            elif x1 == x2:  # 垂直线
                ax.plot([x1, x2], [y1, y2], 'g-')  # 绿色

    # 绘制所有原pin点和steiner点
    x_coords = [point[0] for point in pins]
    y_coords = [point[1] for point in pins]
    x_coords1 = [point[0] for point in s_points]
    y_coords1 = [point[1] for point in s_points]
    plt.scatter(x_coords, y_coords, color='black', s=20)
    plt.scatter(x_coords1, y_coords1, color='orange', s=20)
    # 设置坐标轴标签
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    # 显示网格
    ax.grid(True)
    # 显示图形
    plt.show()
    # plt.savefig('ota5_2_flute_new.png', dpi=300)

# 计算树间的间距（水平或垂直间距）
def trees_spacing_detect(data, threshold=560):
    horizontal_spacings = []
    vertical_spacings = []
    num_sublists = len(data)
    results = []

    # 遍历每一对子列表
    for i in range(num_sublists):
        for j in range(i + 1, num_sublists):
            sublist1 = data[i]
            sublist2 = data[j]

            # 提取两个子列表中的水平和垂直线段
            horizontal_lines1 = [line for line in sublist1 if line[0][1] == line[1][1] and abs(line[1][0] - line[0][0]) > 0]  # 树1中的水平线，确保线段的长度大于0
            vertical_lines1 = [line for line in sublist1 if line[0][0] == line[1][0] and abs(line[1][1] - line[0][1]) > 0]  # 树1中的垂直线
            horizontal_lines2 = [line for line in sublist2 if line[0][1] == line[1][1] and abs(line[1][0] - line[0][0]) > 0]  # 树2中的水平线
            vertical_lines2 = [line for line in sublist2 if line[0][0] == line[1][0] and abs(line[1][1] - line[0][1]) > 0]  # 树2中的垂直线

            # 计算水平线段间的垂直间距
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
                        # overlap_x = (x1_min <= x2_max and x1_max >= x2_min)
                        if not (x1_max < x2_min or x2_max < x1_min):  # 如果水平投影存在重合
                            results.append([sublist1, sublist2, spacing])

            # y_coords1 = set([line[0][1] for line in horizontal_lines1])
            # y_coords2 = set([line[0][1] for line in horizontal_lines2])
            # all_y_coords = sorted(y_coords1.union(y_coords2))
            # for k in range(len(all_y_coords) - 1):
            #     if (all_y_coords[k] in y_coords1 and all_y_coords[k + 1] in y_coords2) or \
            #             (all_y_coords[k] in y_coords2 and all_y_coords[k + 1] in y_coords1):
            #         spacing = all_y_coords[k + 1] - all_y_coords[k]
            #         horizontal_spacings.append(spacing)
            #         if spacing < threshold:
            #             results.append([sublist1, sublist2, spacing])

            # 计算垂直线段间的水平间距
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
                        # overlap_x = (x1_min <= x2_max and x1_max >= x2_min)
                        if not (y1_max < y2_min or y2_max < y1_min):  # 如果水平投影存在重合
                            results.append([sublist1, sublist2, spacing])

            # x_coords1 = set([line[0][0] for line in vertical_lines1])
            # x_coords2 = set([line[0][0] for line in vertical_lines2])
            # all_x_coords = sorted(x_coords1.union(x_coords2))
            # for k in range(len(all_x_coords) - 1):
            #     if (all_x_coords[k] in x_coords1 and all_x_coords[k + 1] in x_coords2) or \
            #             (all_x_coords[k] in x_coords2 and all_x_coords[k + 1] in x_coords1):
            #         spacing = all_x_coords[k + 1] - all_x_coords[k]
            #         vertical_spacings.append(spacing)
            #         if spacing < threshold:
            #             results.append([sublist1, sublist2, spacing])

    return results

# 以下为合法化调整部分
def is_horizontal(segment):
    """判断线段是否为水平线段"""
    return segment[0][1] == segment[1][1]

def is_vertical(segment):
    """判断线段是否为垂直线段"""
    return segment[0][0] == segment[1][0]

def distance_between_parallel_segments(seg1, seg2):
    """计算两条平行线段之间的间距（水平线段算垂直间距，垂直线段算水平间距）"""
    if is_horizontal(seg1) and is_horizontal(seg2):
        return abs(seg1[0][1] - seg2[0][1])
    elif is_vertical(seg1) and is_vertical(seg2):
        return abs(seg1[0][0] - seg2[0][0])
    return None

def segment_length(segment):
    """计算线段的长度"""
    p1, p2 = segment
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)

def total_segment_length(groups):
    """统计列表中所有线段的总线长"""
    total_length = 0
    for group in groups:
        for segment in group:
            total_length += segment_length(segment)
    return total_length

def replace_with_u_shape(segment1, segment2, shift):
    """用 U 形的 3 条线段替换原来的线段"""
    new_segments = []
    p1, p2 = segment1
    p3, p4 = segment2
    # 水平线的替换
    if is_horizontal(segment1):
        if p3[1] >= p1[1]: # 若seg1在seg2上面
            middle_y = p1[1] - shift
            new_segments = [
                (p1, (p1[0], middle_y)),
                ((p1[0], middle_y), (p2[0], middle_y)),
                ((p2[0], middle_y), p2)
            ]
        else:
            middle_y = p1[1] + shift
            new_segments = [
                (p1, (p1[0], middle_y)),
                ((p1[0], middle_y), (p2[0], middle_y)),
                ((p2[0], middle_y), p2)
            ]
    # 垂直线的替换
    elif is_vertical(segment1):
        if p3[0] >= p1[0]: # 若seg1在seg2左边
            middle_x = p1[0] - shift
            new_segments = [
                (p1, (middle_x, p1[1])),
                ((middle_x, p1[1]), (middle_x, p2[1])),
                ((middle_x, p2[1]), p2)
            ]
        else:
            middle_x = p1[0] + shift
            new_segments = [
                (p1, (middle_x, p1[1])),
                ((middle_x, p1[1]), (middle_x, p2[1])),
                ((middle_x, p2[1]), p2)
            ]
    return new_segments

def adjust_segments(groups, threshold=450):
    """调整线段组以满足间距要求并最小化增加长度"""
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
                    # 用 U 形线段替换原来的线段，并删除原线段
                    best_new_segments = replace_with_u_shape(seg1,seg2, shift) # 调整线段组1
                    adjust_group1 = group1[:i] + best_new_segments + group1[i + 1:]
                    # group1[i:i+1] = best_new_segments

    for k, seg1_1 in enumerate(orig_group1):
        for h, seg2_1 in enumerate(group2):
            if (is_horizontal(seg1_1) and is_horizontal(seg2_1)) or (is_vertical(seg1_1) and is_vertical(seg2_1)):
                dist1 = distance_between_parallel_segments(seg1_1, seg2_1)
                if dist1 < threshold:
                    shift1 = threshold - dist1
                    # 用 U 形线段替换原来的线段，并删除原线段
                    best_new_segments2 = replace_with_u_shape(seg2_1, seg1_1, shift1)  # 调整线段组2
                    adjust_group2 = group2[:h] + best_new_segments2 + group2[h + 1:]
                    # group2[h:h + 1] = best_new_segments2

    adjust_group1 = list(set(adjust_group1)) # 去除重复的路径
    adjust_group2 = list(set(adjust_group2)) # 去除重复的路径

    return [orig_group1, adjust_group2], [adjust_group1, orig_group2]
    # # 比较两种合法化方案和输出
    # if total_segment_length([adjust_group1, orig_group2]) >= total_segment_length([orig_group1, adjust_group2]):
    #     print('修改后路径1', [orig_group1, adjust_group2])
    #     return [orig_group1, adjust_group2]
    # else:
    #     print('修改后路径2', [adjust_group1, orig_group2])
    #     return [adjust_group1, orig_group2]

# 修改斯坦纳树组
def revised_steiner_trees(input_steiner_trees1, requir_adjust_trees1, adjusted_segments11):
    # 修改原steiner树组
    indices = []
    for t, sublist in enumerate(input_steiner_trees1):
        if sublist in requir_adjust_trees1[0][0:2]:  # 每次调整第一个树组
            indices.append(t)
    # 进行替换操作
    for l, index in enumerate(indices):
        input_steiner_trees1[index] = adjusted_segments11[l]
    print("替换后的 steiner_trees 列表:", input_steiner_trees1)

    return input_steiner_trees1

# ====================== 【新增：Qt内嵌绘图函数（复用原绘图逻辑）】 ======================
def display_plot_inside(ax, pins, s_points, trees):
    ax.clear()
    for sub_list in trees:
        for segment in sub_list:
            (x1, y1), (x2, y2) = segment
            if y1 == y2:
                ax.plot([x1, x2], [y1, y2], 'r-')
            elif x1 == x2:
                ax.plot([x1, x2], [y1, y2], 'g-')
    # 绘制引脚与斯坦纳点
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
    ax.set_title("走线合法化结果图")

# ====================== 【第二步主UI界面（变量名改为 leg_cp_op2_3）】 ======================
class AdjustTreeUI(QMainWindow):
    def __init__(self):
        super().__init__()
        # 存储上一步加载的斯坦纳森林数据（对应 cp_op2_3）
        self.cp_op2_3 = None
        # 存储【调整完成后的最终斯坦纳树列表】
        self.final_steiner_trees = None
        # 上一步结果文件路径
        self.result_file_path = ""
        # ========== 修改默认保存文件名 ==========
        self.save_default_name = "leg_cp_op2_3_result.txt"

        # 初始化Matplotlib绘图组件
        self.fig = Figure(figsize=(9, 6), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("走线间距检测 & 合法化调整工具")
        self.setGeometry(100, 80, 1000, 750)

        # 全局主布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 顶部控制区域
        ctrl_widget = QWidget()
        ctrl_layout = QVBoxLayout(ctrl_widget)
        ctrl_layout.setSpacing(6)

        # 1. 选择上一步导出的结果文件
        self.select_result_btn = QPushButton("选择上一步斯坦纳森林结果文件(.txt)")
        self.select_result_btn.clicked.connect(self.load_result_file)
        self.file_tip_label = QLabel("当前加载文件：未选择")
        ctrl_layout.addWidget(self.select_result_btn)
        ctrl_layout.addWidget(self.file_tip_label)

        # 2. 绘图开关 + 清空日志
        self.draw_checkbox = QCheckBox("开启界面内绘图显示")
        self.draw_checkbox.setChecked(True)
        self.draw_checkbox.toggled.connect(self.toggle_plot_area)

        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self.clear_log)
        ctrl_layout.addWidget(self.draw_checkbox)
        ctrl_layout.addWidget(self.clear_log_btn)

        # 3. 运行计算按钮
        self.run_btn = QPushButton("开始执行间距检测 & 合法化调整")
        self.run_btn.clicked.connect(self.run_all_task)
        self.run_btn.setFixedHeight(38)
        ctrl_layout.addWidget(self.run_btn)

        # 保存调整后斯坦纳树列表 按钮 + 路径标签
        self.save_final_btn = QPushButton("保存调整后斯坦纳树列表")
        self.save_final_btn.clicked.connect(self.save_final_steiner)
        self.save_final_btn.setFixedHeight(38)
        ctrl_layout.addWidget(self.save_final_btn)

        self.save_path_label = QLabel("结果保存路径：暂未保存")
        ctrl_layout.addWidget(self.save_path_label)

        # 4. 状态提示
        self.status_label = QLabel("状态：就绪，请先选择结果文件")
        ctrl_layout.addWidget(self.status_label)

        main_layout.addWidget(ctrl_widget)

        # 绘图区域（工具栏 + 画布）
        self.toolbar.setVisible(True)
        self.canvas.setVisible(True)
        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(self.canvas)

        # 日志输出区域（自动拉伸占满剩余空间）
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("运行日志、检测结果、线长变化、点位信息将在此展示...")
        main_layout.addWidget(self.log_text, stretch=1)

    # 切换绘图区显示/隐藏
    def toggle_plot_area(self, is_checked):
        self.toolbar.setVisible(is_checked)
        self.canvas.setVisible(is_checked)

    # 清空日志
    def clear_log(self):
        self.log_text.clear()

    # 加载上一步的结果文件，解析得到 cp_op2_3
    def load_result_file(self):
        file_dialog = QFileDialog()
        path, _ = file_dialog.getOpenFileName(
            self,
            "选择斯坦纳森林结果文件",
            "./",
            "Text Files (*.txt);;All Files (*)"
        )
        if not path:
            return

        try:
            # 读取文件内容（格式：cp_op2_3 = [[...]]）
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()

            # 解析字符串为列表数据
            temp_dict = {}
            exec(content, {}, temp_dict)
            self.cp_op2_3 = temp_dict["cp_op2_3"]

            self.result_file_path = path
            self.file_tip_label.setText(f"当前加载文件：{path}")
            self.log_text.append(">>> 结果文件加载成功，已自动赋值给 cp_op2_3")
            self.status_label.setText("状态：文件加载完成，可开始运行")
            # 重置上一次的最终结果
            self.final_steiner_trees = None
            self.save_path_label.setText("结果保存路径：暂未保存")

        except Exception as e:
            err = f">>> 文件解析失败：{str(e)}"
            self.log_text.append(err)
            self.status_label.setText("状态：文件加载失败")
            self.cp_op2_3 = None

    # 保存调整后的最终斯坦纳树列表（变量名改为 leg_cp_op2_3）
    def save_final_steiner(self):
        # 前置判断：必须先完成调整流程，才有数据可保存
        if self.final_steiner_trees is None:
            self.log_text.append("\n>>> 提示：暂无调整后的结果，请先执行【间距检测 & 合法化调整】！")
            self.status_label.setText("状态：无结果可保存")
            return

        try:
            # 弹出保存对话框
            path, _ = QFileDialog.getSaveFileName(
                self,
                "保存调整后斯坦纳树列表",
                self.save_default_name,
                "Text Files (*.txt);;All Files (*)"
            )
            if not path:
                return

            # ========== 核心修改：变量名改为 leg_cp_op2_3 ==========
            save_content = f"leg_cp_op2_3 = {self.final_steiner_trees}"

            # 写入文件
            with open(path, "w", encoding="utf-8") as f:
                f.write(save_content)

            # 更新界面信息
            self.save_path_label.setText(f"结果保存路径：{path}")
            self.log_text.append(f"\n>>> 调整后斯坦纳树列表已成功保存至：{path}")
            self.status_label.setText("状态：结果保存成功")

        except Exception as e:
            err = f"\n>>> 保存失败：{str(e)}"
            self.log_text.append(err)
            self.status_label.setText("状态：保存失败")

    # 执行完整业务逻辑（完全沿用你原始代码）
    def run_all_task(self):
        # 前置校验：必须先加载结果文件
        if self.cp_op2_3 is None:
            self.log_text.append(">>> 错误：请先选择并加载上一步的结果文件！")
            self.status_label.setText("状态：缺少输入数据")
            return

        self.run_btn.setEnabled(False)
        self.status_label.setText("状态：正在执行检测与调整，请稍候...")
        self.log_text.append("\n======= 开始执行间距检测 & 走线合法化 =======")

        try:
            # ========== 以下代码 100% 沿用你原始逻辑，无修改 ==========
            input_steiner_trees = self.cp_op2_3
            orig_wl = total_segment_length(input_steiner_trees)
            threshold = 560

            log_buffer = []
            # 循环调整（最大1000轮）
            for _ in range(1000):
                requir_adjust_trees = trees_spacing_detect(input_steiner_trees, threshold)
                log_buffer.append(f"本轮需要调整的树对数量：{len(requir_adjust_trees)}")

                # 捕获原代码print输出
                print('需要调整的树对', requir_adjust_trees)
                print('需要调整的树对数量',len(requir_adjust_trees))

                if len(requir_adjust_trees) == 0:
                    break
                elif len(requir_adjust_trees) > 0:
                    adjusted_segments1, adjusted_segments2 = adjust_segments(requir_adjust_trees[0][0:2], threshold)
                    input_steiner_trees2 = input_steiner_trees.copy()

                    if len(trees_spacing_detect(revised_steiner_trees(input_steiner_trees, requir_adjust_trees, adjusted_segments1))) < len(requir_adjust_trees):
                        print('方案1')
                        log_buffer.append("本轮选择：方案1")
                    else:
                        print('方案2')
                        log_buffer.append("本轮选择：方案2")
                        input_steiner_trees = revised_steiner_trees(input_steiner_trees2, requir_adjust_trees, adjusted_segments2)

            # 计算新增线长
            add_length = total_segment_length(input_steiner_trees) - orig_wl
            print('合法化增加的线长', add_length)
            log_buffer.append(f"\n合法化新增总线长：{add_length:.2f}")

            # 读取nets.txt 区分引脚和斯坦纳点（沿用原逻辑）
            file_path = 'nets.txt'
            lists = read_file(file_path)
            OriginalPoints, steiner_points = distinguishing_point(lists, input_steiner_trees)
            print('斯坦纳点', steiner_points)
            print('原有点', OriginalPoints)
            log_buffer.append(f"原始引脚数量：{len(OriginalPoints)}")
            log_buffer.append(f"斯坦纳点数量：{len(steiner_points)}")
            log_buffer.append(f"斯坦纳点坐标：{steiner_points}")

            # 保存【调整完成后的最终树列表】到实例变量，供给保存按钮使用
            self.final_steiner_trees = input_steiner_trees

            # 输出所有日志
            self.log_text.append("\n".join(log_buffer))
            self.log_text.append("\n>>> 全部流程执行完成，可点击【保存调整后斯坦纳树列表】导出结果！")

            # 内嵌绘图（开启绘图时执行）
            if self.draw_checkbox.isChecked():
                ax = self.fig.add_subplot(111)
                display_plot_inside(ax, OriginalPoints, steiner_points, input_steiner_trees)
                self.fig.canvas.draw()

            self.status_label.setText("状态：执行完成")

        except Exception as e:
            err_msg = f"\n>>> 运行出错：{str(e)}"
            self.log_text.append(err_msg)
            self.status_label.setText("状态：运行失败")
            self.final_steiner_trees = None
        finally:
            self.run_btn.setEnabled(True)

# 程序入口
if __name__ == "__main__":
    app = QApplication([])
    window = AdjustTreeUI()
    window.show()
    app.exec_()