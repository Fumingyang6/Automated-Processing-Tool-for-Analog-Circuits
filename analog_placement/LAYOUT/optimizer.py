import torch
import torch.nn as nn
import numpy as np
import time
from .parsers import parse_spice_netlist, parse_sym_file
from .core import compute_tmoc, compute_hpwl, compute_overlap, compute_symmetry, compute_oob_penalty
from .visualization import plot_layout


device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"使用设备: {device}")


def optimize_layout(
        netlist_file,
        sym_file,
        target_area=10.0,
        max_steps=1000,
        tmoc_weight=20.0,
        symmetry_weight=100.0,
        hpwl_weight=0.01,
        max_overlap_percent=2.0,
        max_symmetry_error=0.1,
        max_oob_penalty=0.1,
        plot_intermediate=True,
        plot_callback=None
):
    """
    模拟电路共质心布局优化函数（100%复刻原始代码行为）

    仅允许修改以下参数：
    - target_area: 目标布局面积(μm²)，默认10.0
    - max_steps: 最大优化步数，默认1000
    - tmoc_weight: 共质心失配惩罚权重，默认20.0
    - symmetry_weight: 对称性惩罚权重，默认100.0
    - hpwl_weight: 线长优化权重，默认0.01
    - max_overlap_percent: 最大允许重叠百分比，默认2.0%
    - max_symmetry_error: 最大允许对称性误差，默认0.1
    - max_oob_penalty: 最大允许边界越界惩罚，默认0.1
    - plot_callback: 可选的布局图回调，签名
      (kind, x, y, devices, sym_pairs, x_sym, title)；kind 为
      "initial" / "intermediate" / "final"。传了它就不再弹 matplotlib 窗口。

    注意：plot_callback 会在调用方的线程里被调用（界面是用后台线程跑的），
    所以回调本身必须是线程安全的——不要在里面碰 Qt 控件。
    """

    def emit_plot(kind, x, y, devices, sym_pairs, x_sym, title, announce=None):
        """出图：有回调就交给外部渲染，否则退回原来的 matplotlib 弹窗"""
        if plot_callback is None and not plot_intermediate:
            return
        if announce:
            print(announce)
        if plot_callback is not None:
            plot_callback(kind, x, y, devices, sym_pairs, x_sym, title)
        else:
            plot_layout(x, y, devices, sym_pairs, x_sym, title=title)
    # 解析网表和对称文件（与原始代码完全一致）
    devices, nets, device_name_to_index, logical_groups = parse_spice_netlist(netlist_file)
    sym_pairs, cc_pairs = parse_sym_file(sym_file, device_name_to_index)

    # 设置参数（仅修改用户指定的8个参数，其他完全使用原始默认值）
    params = {
        'n_devices': len(devices),
        'nets': nets,
        'sym_pairs': sym_pairs,
        'cc_pairs': cc_pairs,
        'logical_groups': logical_groups,
        'beta_hpwl_initial': hpwl_weight,  # 可配置
        'beta_hpwl_final': hpwl_weight,  # 可配置
        'lambda_overlap_base': 1000.0,
        'lambda_overlap_max': 10000.0,
        'lambda_overlap_min': 1000.0,
        'lambda_oob': 5.0,
        'lambda_tmoc': tmoc_weight,  # 可配置
        'tau_sym_initial': symmetry_weight,  # 可配置
        'tau_sym_max': symmetry_weight,  # 可配置
        'eta': 0.03,
        'eta_sym_factor': 10.0,
        'alpha_lse': 0.1,
        'gamma_oob': 0.1,
        'lr': 0.03,
        'max_steps': max_steps,  # 可配置
        'min_steps': 100,
        'density_factor': 3,
        'x_sym': 0.0,
        'spacing': 1.0,
        'first_stage_max_steps': 500,
        'tmoc_threshold_factor': 0.01,
        'tmoc_multiplier_first_stage': 100.0,
        'initial_spread_factor': 1.5,
    }

    # 面积归一化（与原始代码完全一致）
    actual_total_area = sum(dev['width'] * dev['height'] for dev in devices)
    scale = (target_area / actual_total_area) ** 0.5  # 可配置target_area
    for dev in devices:
        dev['width'] *= scale
        dev['height'] *= scale
    total_device_area = sum(dev['width'] * dev['height'] for dev in devices)

    # 定义边界（与原始代码完全一致）
    side = np.sqrt(target_area * params['density_factor'])
    X_L = torch.tensor(-side / 2, device=device, dtype=torch.float32)
    X_H = torch.tensor(side / 2, device=device, dtype=torch.float32)
    Y_L = torch.tensor(-side / 2, device=device, dtype=torch.float32)
    Y_H = torch.tensor(side / 2, device=device, dtype=torch.float32)

    # 初始化坐标（与原始代码完全一致）
    initial_side = side * params['initial_spread_factor']
    initial_X_L = -initial_side / 2
    initial_X_H = initial_side / 2
    initial_Y_L = -initial_side / 2
    initial_Y_H = initial_side / 2
    x_init = torch.rand(params['n_devices'], device=device, dtype=torch.float32) * (
                initial_X_H - initial_X_L) + initial_X_L
    y_init = torch.rand(params['n_devices'], device=device, dtype=torch.float32) * (
                initial_Y_H - initial_Y_L) + initial_Y_L
    v_init = torch.empty(2 * params['n_devices'], device=device, dtype=torch.float32)
    v_init[0::2] = x_init
    v_init[1::2] = y_init
    v = nn.Parameter(v_init)

    optimizer = torch.optim.RMSprop([v], lr=params['lr'], alpha=0.9, momentum=0.9)

    # 初始化权重（与原始代码完全一致）
    lambda_overlap_current = params['lambda_overlap_base']
    tau_sym_current = params['tau_sym_initial']
    lambda_oob_current = params['lambda_oob']
    lambda_tmoc_current = params['lambda_tmoc']

    # 计算初始TMOC值以设置阈值（与原始代码完全一致）
    x = v[::2]
    y = v[1::2]
    initial_tmoc = compute_tmoc(x, y, params['cc_pairs'], devices)
    params['tmoc_threshold'] = params['tmoc_threshold_factor'] * initial_tmoc.item()

    # 优化循环（与原始代码完全一致，仅修改停止条件）
    start_time = time.time()
    in_first_stage = True

    emit_plot("initial", x.detach().cpu().numpy(), y.detach().cpu().numpy(),
              devices, sym_pairs, params['x_sym'],
              "Initial Device Layout", "初始布局:")

    for step in range(params['max_steps']):
        optimizer.zero_grad()
        x = v[::2]
        y = v[1::2]
        beta_hpwl_current = params['beta_hpwl_initial'] + (
                params['beta_hpwl_final'] - params['beta_hpwl_initial']) * min(1.0, step / params['min_steps'])

        # 计算所有惩罚项（与原始代码完全一致）
        hpwl = compute_hpwl(x, y, params['nets'], devices, params['alpha_lse'])
        overlap_penalty, total_overlap_area = compute_overlap(x, y, devices)
        sym = compute_symmetry(x, y, params['sym_pairs'], params['cc_pairs'], params['x_sym'],
                               params['logical_groups'], params['spacing'])
        oob_penalty = compute_oob_penalty(x, y, devices, X_L, X_H, Y_L, Y_H, params['gamma_oob'])
        tmoc = compute_tmoc(x, y, params['cc_pairs'], devices)

        # 两阶段损失函数（与原始代码完全一致）
        if step < params['first_stage_max_steps'] and (
                tmoc.item() >= 0.01 or total_overlap_area.item() >= 0.02 * total_device_area):
            # 第一阶段：仅优化TMOC和重叠
            loss = (lambda_tmoc_current * params['tmoc_multiplier_first_stage'] * tmoc +
                    lambda_overlap_current * overlap_penalty)
        else:
            # 第二阶段：优化所有目标
            if in_first_stage:
                emit_plot("intermediate", x.detach().cpu().numpy(), y.detach().cpu().numpy(),
                          devices, sym_pairs, params['x_sym'],
                          "Layout at the End of First Stage", "第一阶段结束时的布局:")
                in_first_stage = False
            loss = (beta_hpwl_current * hpwl +
                    lambda_overlap_current * overlap_penalty +
                    tau_sym_current * sym +
                    lambda_oob_current * oob_penalty +
                    lambda_tmoc_current * tmoc)

        # 反向传播和优化（与原始代码完全一致）
        loss.backward()
        optimizer.step()

        # 计算对称性指标（与原始代码完全一致）
        average_width = np.mean([dev['width'] for dev in devices])
        average_height = np.mean([dev['height'] for dev in devices])
        rms_x = torch.tensor(0.0, device=device)
        rms_y = torch.tensor(0.0)

        if params['sym_pairs']:
            # 过滤掉属于共质心组的对称对
            cc_devices = set()
            for group1, group2 in params['cc_pairs']:
                cc_devices.update(group1)
                cc_devices.update(group2)

            non_cc_sym_pairs = []
            for i, j in params['sym_pairs']:
                if i not in cc_devices and j not in cc_devices:
                    non_cc_sym_pairs.append((i, j))

            # 计算 RMS_x
            if non_cc_sym_pairs:
                sym_dev_x = [x[i] + x[j] - 2 * params['x_sym'] for i, j in non_cc_sym_pairs]
                rms_x = torch.sqrt(torch.mean(torch.tensor([d ** 2 for d in sym_dev_x], device=device)))

            # 计算 RMS_y
            if non_cc_sym_pairs:
                sym_dev_y = [y[i] - y[j] for i, j in non_cc_sym_pairs]
                rms_y = torch.sqrt(torch.mean(torch.tensor([d ** 2 for d in sym_dev_y], device=device)))

        # 动态调整权重（与原始代码完全一致）
        overlap_percentage = (total_overlap_area.item() / total_device_area) * 100 if total_device_area > 0 else 0
        if overlap_percentage < 5:
            eta_sym = params['eta'] * params['eta_sym_factor']
            if step < params['first_stage_max_steps'] and tmoc.item() >= params['tmoc_threshold']:
                lambda_overlap_current += params['eta'] * overlap_penalty.item()
            else:
                lambda_overlap_current = params['lambda_overlap_min']
        else:
            eta_sym = params['eta']
            lambda_overlap_current += params['eta'] * overlap_penalty.item()
            lambda_overlap_current = min(lambda_overlap_current, params['lambda_overlap_max'])
        tau_sym_current += eta_sym * sym.item()
        tau_sym_current = min(tau_sym_current, params['tau_sym_max'])
        lambda_oob_current += params['eta'] * oob_penalty.item()
        lambda_oob_current = min(lambda_oob_current, 1.0)
        lambda_tmoc_current += params['eta'] * tmoc.item()
        lambda_tmoc_current = min(lambda_tmoc_current, 100.0)

        # 计算边界条件（与原始代码完全一致）
        widths = torch.tensor([d['width'] for d in devices], device=device)
        heights = torch.tensor([d['height'] for d in devices], device=device)
        left = x - widths / 2
        right = x + widths / 2
        bottom = y - heights / 2
        top = y + heights / 2

        # 打印进度（与原始代码完全一致）
        if step % 10 == 0:
            print(
                f"步骤 {step}, 损失: {loss.item():.4f}, HPWL: {hpwl.item():.4f}, 重叠: {total_overlap_area.item():.4f} ({overlap_percentage:.2f}%), "
                f"对称惩罚: {sym.item():.4f}, OOB 惩罚: {oob_penalty.item():.4f}, TMOC: {tmoc.item():.4f}, "
                f"RMS_x: {rms_x.item():.4f}, RMS_y: {rms_y.item():.4f}, "
                f"权重: beta_hpwl={beta_hpwl_current:.2f}, lambda_overlap={lambda_overlap_current:.2f}, "
                f"tau_sym={tau_sym_current:.2f}, lambda_oob={lambda_oob_current:.2f}, lambda_tmoc={lambda_tmoc_current:.2f}")

        # 停止条件（使用可配置参数）
        max_overlap_ratio = max_overlap_percent / 100.0
        if step >= params['min_steps'] and \
                total_overlap_area.item() <= max_overlap_ratio * total_device_area and \
                oob_penalty.item() <= max_oob_penalty and \
                (not params['sym_pairs'] or (
                        rms_x.item() <= max_symmetry_error * average_width and
                        rms_y.item() <= max_symmetry_error * average_height)):
            print(f"在步骤 {step} 停止: 重叠、对称性和 OOB 条件满足。")
            break

    end_time = time.time()
    print(f"总优化时间: {end_time - start_time:.2f} 秒")
    print("达到最大步骤但未满足条件。" if step == params['max_steps'] - 1 else "")
    print("最终布局:")
    print("Final coordinates:", v.cpu().data.numpy())
    x = v[::2].detach().cpu().numpy()
    y = v[1::2].detach().cpu().numpy()

    emit_plot("final", x, y, devices, sym_pairs, params['x_sym'], "Final Device Layout")

    return x, y