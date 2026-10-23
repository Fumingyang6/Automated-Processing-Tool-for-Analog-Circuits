import matplotlib
import re
import sys

# 自动检测当前运行的后端，避免冲突
if 'PyQt5' in sys.modules or 'PyQt6' in sys.modules:
    matplotlib.use('Qt5Agg')
else:
    matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from matplotlib.colors import to_rgba

# 只影响绘图：按器件类型区分颜色，坐标和布局结果完全不参与。
# MOS 再按网表里的模型名（nch / pch …）细分 NMOS / PMOS，
# 这样纯 MOS 电路也能看出两类管子。
_DEVICE_STYLES = {
    'M': ('#2563eb', 'MOS'),
    'R': ('#dc2626', '电阻'),
    'C': ('#16a34a', '电容'),
}
_NMOS_STYLE = ('#2563eb', 'NMOS')
_PMOS_STYLE = ('#f59e0b', 'PMOS')
_OTHER_DEVICE_STYLE = ('#6b7280', '其他器件')


def _device_style(name, models=None):
    """根据器件名首字母和模型名返回 (颜色, 图例文字)"""
    name = str(name or '').strip()
    prefix = name[:1].upper()
    if prefix == 'M' and models:
        # multi 拆分后的名字是 M9_0、M9_1 …，去掉数字后缀再查模型
        base = re.sub(r'_\d+$', '', name)
        model = models.get(base) or models.get(name) or ''
        if model.startswith('n'):
            return _NMOS_STYLE
        if model.startswith('p'):
            return _PMOS_STYLE
    return _DEVICE_STYLES.get(prefix, _OTHER_DEVICE_STYLE)


def draw_layout_on(ax, x, y, devices, sym_pairs, x_sym, title="Layout of Devices",
                   show_legend=True, models=None):
    """把设备布局画到给定的 Axes 上，显示设备、对称轴和重叠区域。

    与 plot_layout 的区别是这里不创建 figure、也不弹窗，
    方便嵌入到 Qt 界面里的内嵌画布上。

    show_legend=False 时不画图例，交给调用方统一放一个（左右并排两幅图时用）。
    """
    labeled_types = set()
    for i, dev in enumerate(devices):
        xi, yi = x[i], y[i]
        wi, hi = dev['width'], dev['height']
        color, type_label = _device_style(dev.get('name', ''), models)
        # 每个类型只挂一次图例，图例项不会重复
        label = type_label if type_label not in labeled_types else None
        labeled_types.add(type_label)
        rect = patches.Rectangle(
            (xi - wi / 2, yi - hi / 2), wi, hi, linewidth=1.2,
            edgecolor=color, facecolor=to_rgba(color, 0.30), label=label,
        )
        ax.add_patch(rect)
        # ax.text(xi + 0.1, yi, dev['name'], fontsize=8, color='black')
    for i in range(len(devices)):
        for j in range(i + 1, len(devices)):
            xi, yi = x[i], y[i]
            xj, yj = x[j], y[j]
            wi, hi = devices[i]['width'], devices[i]['height']
            wj, hj = devices[j]['width'], devices[j]['height']
            left_i, right_i = xi - wi / 2, xi + wi / 2
            bottom_i, top_i = yi - hi / 2, yi + hi / 2
            left_j, right_j = xj - wj / 2, xj + wj / 2
            bottom_j, top_j = yj - hj / 2, yj + hj / 2
            overlap_width = min(right_i, right_j) - max(left_i, left_j)
            overlap_height = min(top_i, top_j) - max(bottom_i, bottom_j)
            if overlap_width > 0 and overlap_height > 0:
                overlap_left = max(left_i, left_j)
                overlap_bottom = max(bottom_i, bottom_j)
                rect = patches.Rectangle(
                    (overlap_left, overlap_bottom), overlap_width, overlap_height,
                    linewidth=0, facecolor='yellow', alpha=0.5, label='Overlap' if i == 0 and j == 1 else None
                )
                ax.add_patch(rect)
    y_min = min(y) - max(dev['height'] / 2 for dev in devices) - 1
    y_max = max(y) + max(dev['height'] / 2 for dev in devices) + 1
    x_min = min(x) - max(dev['width'] / 2 for dev in devices) - 1
    x_max = max(x) + max(dev['width'] / 2 for dev in devices) + 1
    ax.axvline(x=x_sym, color='green', linestyle='--', label='Symmetry Axis')
    ax.set_xlabel('X Coordinate')
    ax.set_ylabel('Y Coordinate')
    ax.set_title(title)
    if show_legend:
        ax.legend()
    ax.set_aspect('equal')
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    # 原实现在结尾是 ax.grid(True) 之后又 plt.grid(False)，净效果为不显示网格，
    # 这里直接不画网格，保持和原来完全一样的观感


def plot_layout(x, y, devices, sym_pairs, x_sym, title="Layout of Devices"):
    """在独立的 matplotlib 窗口中显示布局（保持原有行为，供 test.py 等沿用）"""
    fig, ax = plt.subplots(figsize=(10, 10))
    draw_layout_on(ax, x, y, devices, sym_pairs, x_sym, title)
    plt.show()