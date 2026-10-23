import torch
import numpy as np

def compute_tmoc(x, y, cc_pairs, devices, spacing=0.0):
    """计算配对共质心组的总失配偏移系数（TMOC），强制 2xN 网格布局。"""
    device = x.device
    tmoc = torch.tensor(0.0, device=device, dtype=torch.float32)

    for group1, group2 in cc_pairs:
        N = len(group1)  # 每组模块数
        indices = torch.tensor(group1 + group2, device=device)

        # 计算当前质心
        centroid_x = torch.mean(x[indices])
        centroid_y = torch.mean(y[indices])

        # 获取模块尺寸（假设组内模块尺寸相同）
        w = devices[group1[0]]['width']
        h = devices[group1[0]]['height']
        dx = w + spacing
        dy = h + spacing

        # 计算网格基点
        x0 = centroid_x - (N - 1) / 2 * dx
        y0 = centroid_y - 0.5 * dy

        # 分配网格位置
        positions_group1 = [(r, c) for r in range(2) for c in range(N) if (r + c) % 2 == 0]
        positions_group2 = [(r, c) for r in range(2) for c in range(N) if (r + c) % 2 == 1]
        positions_group1.sort(key=lambda p: (p[0], p[1]))
        positions_group2.sort(key=lambda p: (p[0], p[1]))

        # 为 group1 模块分配预定位置
        for k, idx in enumerate(group1):
            r, c = positions_group1[k]
            pred_x = x0 + c * dx
            pred_y = y0 + r * dy
            tmoc += (x[idx] - pred_x) ** 2 + (y[idx] - pred_y) ** 2

        # 为 group2 模块分配预定位置
        for k, idx in enumerate(group2):
            r, c = positions_group2[k]
            pred_x = x0 + c * dx
            pred_y = y0 + r * dy
            tmoc += (x[idx] - pred_x) ** 2 + (y[idx] - pred_y) ** 2

    return tmoc

def compute_hpwl(x, y, nets, devices, alpha=0.1):
    """计算半周长线长（HPWL），向量化实现，适配字典格式的 devices。"""
    device = x.device
    hpwl = torch.tensor(0.0, device=device, dtype=torch.float32)

    for net in nets:
        indices = torch.tensor(net, device=device)
        x_net = x[indices]
        y_net = y[indices]
        max_x = alpha * torch.logsumexp(x_net / alpha, dim=0)
        min_x = -alpha * torch.logsumexp(-x_net / alpha, dim=0)
        max_y = alpha * torch.logsumexp(y_net / alpha, dim=0)
        min_y = -alpha * torch.logsumexp(-y_net / alpha, dim=0)
        hpwl += (max_x - min_x) + (max_y - min_y)

    return hpwl

def smooth_max_zero(x, gamma=0.1):
    return gamma * torch.log1p(torch.exp(x / gamma))

def compute_overlap(x, y, devices):
    """计算设备间的重叠惩罚和总重叠面积，适配字典格式的 devices。"""
    device = x.device
    n_devices = len(devices)
    widths = torch.tensor([dev['width'] for dev in devices], device=device, dtype=torch.float32)
    heights = torch.tensor([dev['height'] for dev in devices], device=device, dtype=torch.float32)
    i, j = torch.triu_indices(n_devices, n_devices, offset=1, device=device)
    xi = x[i]
    xj = x[j]
    yi = y[i]
    yj = y[j]
    wi = widths[i]
    wj = widths[j]
    hi = heights[i]
    hj = heights[j]
    left_i = xi - wi / 2
    right_i = xi + wi / 2
    bottom_i = yi - hi / 2
    top_i = yi + hi / 2
    left_j = xj - wj / 2
    right_j = xj + wj / 2
    bottom_j = yj - hj / 2
    top_j = yj + hj / 2
    overlap_width = torch.minimum(right_i, right_j) - torch.maximum(left_i, left_j)
    overlap_height = torch.minimum(top_i, top_j) - torch.maximum(bottom_i, bottom_j)
    overlap_area = torch.maximum(torch.tensor(0.0, device=device), overlap_width) * torch.maximum(
        torch.tensor(0.0, device=device), overlap_height)
    overlap_penalty = torch.sum(overlap_area ** 2)
    total_overlap_area = torch.sum(overlap_area)
    return overlap_penalty, total_overlap_area

def compute_symmetry(x, y, sym_pairs, cc_groups, x_sym, logical_groups, spacing=1.0):
    """计算对称性损失，仅包括对称对约束。"""
    device = x.device
    sym_loss = torch.tensor(0.0, device=device, dtype=torch.float32)
    num_constraints = 0

    # 对称对约束：确保对称设备关于 x_sym 对称
    if sym_pairs:
        i = torch.tensor([pair[0] for pair in sym_pairs], device=device)
        j = torch.tensor([pair[1] for pair in sym_pairs], device=device)
        xi = x[i]
        xj = x[j]
        yi = y[i]
        yj = y[j]
        x_sym_tensor = torch.tensor(x_sym, device=device, dtype=torch.float32)
        sym_loss += torch.sum((xi + xj - 2 * x_sym_tensor) ** 2)  # x 坐标对称
        sym_loss += torch.sum((yi - yj) ** 2)  # y 坐标相等
        num_constraints += len(sym_pairs)

    if num_constraints > 0:
        sym_loss /= num_constraints
    return sym_loss

def compute_oob_penalty(x, y, devices, X_L, X_H, Y_L, Y_H, gamma_oob):
    """计算超出边界的惩罚，适配字典格式的 devices。"""
    device = x.device
    widths = torch.tensor([dev['width'] for dev in devices], device=device, dtype=torch.float32)
    heights = torch.tensor([dev['height'] for dev in devices], device=device, dtype=torch.float32)
    left = x - widths / 2
    right = x + widths / 2
    bottom = y - heights / 2
    top = y + heights / 2
    oob_penalty = torch.sum(torch.log1p(torch.exp((X_L - left) / gamma_oob)) * gamma_oob)
    oob_penalty += torch.sum(torch.log1p(torch.exp((right - X_H) / gamma_oob)) * gamma_oob)
    oob_penalty += torch.sum(torch.log1p(torch.exp((Y_L - bottom) / gamma_oob)) * gamma_oob)
    oob_penalty += torch.sum(torch.log1p(torch.exp((top - Y_H) / gamma_oob)) * gamma_oob)
    return oob_penalty