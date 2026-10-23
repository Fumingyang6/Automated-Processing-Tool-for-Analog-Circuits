# -*- coding: utf-8 -*-
import os
import time
import random

# PyQt5 相关导入
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QCheckBox,
                             QTextEdit, QVBoxLayout, QWidget, QLabel, QFileDialog)
from PyQt5.QtCore import Qt

# Matplotlib 嵌入Qt所需模块
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

# ====================== 【原有斯坦纳树算法代码 完全保留无修改】 ======================
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

# 导入并查集（同目录必须存在 UnionFind.py）
from UnionFind import UnionFind

def Kruskal(SetOfPoints):
    """Kruskal 算法求解最小生成树"""
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
    """计算新增点后MST权重变化量"""
    MST = Kruskal(SetOfPoints)
    cost1 = sum(edge.w for edge in MST)

    combo = SetOfPoints + [TestPoint]
    MST = Kruskal(combo)
    cost2 = sum(edge.w for edge in MST)
    return cost1 - cost2

def HananPoints(SetOfPoints):
    """生成Hanan候选点"""
    SomePoints = []
    for i in range(0, len(SetOfPoints)):
        for j in range(i, len(SetOfPoints)):
            if i != j:
                SomePoints.append(Point(SetOfPoints[i].x, SetOfPoints[j].y))
                SomePoints.append(Point(SetOfPoints[j].x, SetOfPoints[i].y))
    return SomePoints

def computeRSMT(OriginalPoints):
    """计算直线斯坦纳最小树 RSMT"""
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
        # 移除度数<=2的无效斯坦纳点
        temp_list = []
        for pt in RectSteinerPoints:
            if pt.deg > 2:
                temp_list.append(pt)
        RectSteinerPoints = temp_list

    RSMT = Kruskal(OriginalPoints + RectSteinerPoints)
    return RSMT, RectSteinerPoints

def read_file(file_path):
    """读取nets.txt 线网点数据"""
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
    """去除同点重复路径"""
    new_list = []
    for tup in original_list:
        if tup[0] != tup[1]:
            new_list.append(tup)
    return new_list

def via_coordinates(trees):
    """计算走线交点（Via 通孔位置）"""
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
        # 求横竖线交点
        for h_line in horizontal_lines:
            (hx1, hy), (hx2, _) = h_line
            for v_line in vertical_lines:
                (vx, vy1), (_, vy2) = v_line
                if (min(hx1, hx2) <= vx <= max(hx1, hx2) and
                    min(vy1, vy2) <= hy <= max(vy1, vy2)):
                    intersection_points.append((int(vx), int(hy)))
    return intersection_points

# ====================== 绘图运行函数 ======================
def run_rsmt_task(fig, is_draw: bool, txt_path: str):
    start_time = time.time()
    if not os.path.exists(txt_path):
        raise FileNotFoundError(f"文件不存在：{txt_path}")

    lists = read_file(txt_path)
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
            decision = 0

            path.append(((p1.x, p1.y), (p1.x, p2.y)))
            path.append(((p1.x, p2.y), (p2.x, p2.y)))

            if is_draw:
                ax.plot([p1.x, p1.x], [p1.y, p2.y], 'b-', linewidth=2)
                ax.plot([p1.x, p2.x], [p2.y, p2.y], 'b-', linewidth=2)

        clean_path = remove_duplicate_elements(path)
        steiner_trees.append(clean_path)
        paths.extend(clean_path)
        all_length += RSMTminDist

        if is_draw:
            for pt in OriginalPoints:
                ax.plot(pt.x, pt.y, 'wo', markersize=10, markeredgecolor='k')
            for st_pt in Steiner_points:
                ax.plot(st_pt.x, st_pt.y, 'ko', markersize=10)
            ax.text(0.02, 0.98, f'Net{idx} Length: {RSMTminDist}',
                    transform=ax.transAxes, verticalalignment='top')

    if is_draw:
        for line in paths:
            (x1, y1), (x2, y2) = line
            if x1 == x2:
                ax.plot([x1, x2], [y1, y2], 'r-')
            elif y1 == y2:
                ax.plot([x1, x2], [y1, y2], 'g-')
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.grid(True)
        ax.set_title("Rectilinear Steiner Minimum Tree - All Nets")

    via_points = via_coordinates(steiner_trees)
    run_time = time.time() - start_time
    fig.canvas.draw()
    return steiner_trees, all_length, via_points, run_time, paths

# ====================== 新版UI界面（新增保存功能） ======================
class RSMTUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.steiner_forests = []
        self.file_path = "nets.txt"
        # 默认保存文件名（适配下一步 cp_op2_3 赋值）
        self.save_default_name = "steiner_forest_result.txt"
        self.save_file_path = ""
        self.initUI()

    def initUI(self):
        self.setWindowTitle("直线斯坦纳最小树(RSMT) 计算工具")
        self.setGeometry(100, 80, 1000, 750)

        # Matplotlib绘图组件
        self.fig = Figure(figsize=(9, 6), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)

        # 主布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 上方控制区
        ctrl_widget = QWidget()
        ctrl_layout = QVBoxLayout(ctrl_widget)
        ctrl_layout.setSpacing(6)

        # 1. 文件选择
        file_layout = QVBoxLayout()
        self.select_file_btn = QPushButton("选择网表文件(.txt)")
        self.select_file_btn.clicked.connect(self.on_select_file)
        self.file_label = QLabel(f"当前文件：{self.file_path}")
        file_layout.addWidget(self.select_file_btn)
        file_layout.addWidget(self.file_label)
        ctrl_layout.addLayout(file_layout)

        # 2. 绘图开关 + 日志清空按钮
        btn_row_layout = QVBoxLayout()
        self.draw_checkbox = QCheckBox("开启界面内绘图显示")
        self.draw_checkbox.setChecked(True)
        self.draw_checkbox.toggled.connect(self.toggle_plot_area)

        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self.clear_log_text)

        row_h = QVBoxLayout()
        row_h.addWidget(self.draw_checkbox)
        row_h.addWidget(self.clear_log_btn)
        ctrl_layout.addLayout(row_h)

        # 3. 运行计算按钮
        self.run_btn = QPushButton("开始计算 RSMT")
        self.run_btn.clicked.connect(self.on_run_task)
        self.run_btn.setFixedHeight(38)
        ctrl_layout.addWidget(self.run_btn)

        # ========== 【新增：保存结果按钮 + 保存路径标签】 ==========
        self.save_result_btn = QPushButton("保存斯坦纳森林结果")
        self.save_result_btn.clicked.connect(self.save_forest_result)
        self.save_result_btn.setFixedHeight(38)
        ctrl_layout.addWidget(self.save_result_btn)

        self.save_path_label = QLabel("保存路径：暂未保存")
        ctrl_layout.addWidget(self.save_path_label)
        # =======================================================

        # 4. 状态文字
        self.status_label = QLabel("状态：就绪")
        ctrl_layout.addWidget(self.status_label)

        main_layout.addWidget(ctrl_widget)

        # 绘图区容器
        self.toolbar.setVisible(True)
        self.canvas.setVisible(True)
        main_layout.addWidget(self.toolbar)
        main_layout.addWidget(self.canvas)

        # 日志文本框
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("运行结果、斯坦纳森林、Via坐标将展示在这里...")
        main_layout.addWidget(self.result_text, stretch=1)

    # 切换绘图区域显示/隐藏
    def toggle_plot_area(self, is_checked):
        self.toolbar.setVisible(is_checked)
        self.canvas.setVisible(is_checked)

    # 清空日志文本
    def clear_log_text(self):
        self.result_text.clear()

    # 选择网表文件
    def on_select_file(self):
        file_dialog = QFileDialog()
        path, _ = file_dialog.getOpenFileName(
            self,
            "选择网表文件",
            "./",
            "Text Files (*.txt);;All Files (*)"
        )
        if path:
            self.file_path = path
            self.file_label.setText(f"当前文件：{self.file_path}")

    # ========== 【新增：保存斯坦纳森林结果函数】 ==========
    def save_forest_result(self):
        """将 steiner_forests 保存为 cp_op2_3 = 列表 格式的文本文件"""
        if not self.steiner_forests:
            self.result_text.append("\n>>> 提示：暂无计算结果，无法保存！请先执行计算")
            self.status_label.setText("状态：无结果可保存")
            return

        try:
            # 弹出保存文件选择框，默认文件名 steiner_forest_result.txt
            path, _ = QFileDialog.getSaveFileName(
                self,
                "保存斯坦纳森林结果",
                self.save_default_name,
                "Text Files (*.txt);;All Files (*)"
            )
            if not path:
                # 用户取消选择
                return

            # 核心：生成  cp_op2_3 = 列表数据 格式（直接适配你下一步代码）
            save_content = f"cp_op2_3 = {self.steiner_forests}"

            # 写入文件
            with open(path, "w", encoding="utf-8") as f:
                f.write(save_content)

            # 更新路径与状态
            self.save_file_path = path
            self.save_path_label.setText(f"保存路径：{path}")
            self.result_text.append(f"\n>>> 斯坦纳森林结果已成功保存至：{path}")
            self.status_label.setText("状态：结果保存成功")

        except Exception as e:
            err = f"\n>>> 保存失败：{str(e)}"
            self.result_text.append(err)
            self.status_label.setText("状态：保存失败")
    # =======================================================

    # 运行计算
    def on_run_task(self):
        self.run_btn.setEnabled(False)
        self.status_label.setText("状态：计算中，请稍候...")
        # 每次计算清空上一次保存路径提示
        self.save_path_label.setText("保存路径：暂未保存")

        try:
            is_draw = self.draw_checkbox.isChecked()
            target_file = self.file_path

            forests, total_len, via_pts, cost_time, all_paths = run_rsmt_task(
                fig=self.fig,
                is_draw=is_draw,
                txt_path=target_file
            )

            self.steiner_forests = forests

            res = "======= 计算完成 =======\n"
            res += f"运行耗时：{cost_time:.4f} 秒\n"
            res += f"总线网布线长度：{total_len}\n"
            res += f"Via(通孔)坐标列表：\n{via_pts}\n\n"
            res += f"【斯坦纳森林列表(steiner_forests)】\n"
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

# 程序入口
if __name__ == "__main__":
    app = QApplication([])
    window = RSMTUI()
    window.show()
    app.exec_()