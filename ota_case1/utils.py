#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import torch
import math
import warnings
from torch import Tensor
import numpy as np

import os

from dev_params import DeviceParams

# 用 __file__ 定位 ota_case1 目录，而不是 import 时的 os.getcwd()：
# UI 场景下本模块可能在 chdir 之前就被 import，getcwd() 会固化成错误目录
# （ota.py 中的 resource_path 也是同样的处理思路）
PWD = os.path.dirname(os.path.abspath(__file__))
SPICE_NETLIST_DIR = f'{PWD}/simulations'
os.environ['CUDA_LAUNCH_BLOCKING'] = "1"


def get_sky130_pdk_dir():
    """sky130A PDK 根目录。

    优先取环境变量 SKY130_PDK_DIR；否则默认 ~/pdk/sky130A
    （volare 预编译包解压位置）。返回正斜杠路径，避免 ngspice
    在 Windows 下把反斜杠当转义符。
    """
    pdk_dir = os.environ.get("SKY130_PDK_DIR") or os.path.join(
        os.path.expanduser("~"), "pdk", "sky130A")
    return pdk_dir.replace("\\", "/")


def prepare_ota_netlist(template_name="ota.spice", out_name="ota_gen.spice"):
    """把 ota.spice 模板里的 __SKY130_PDK_DIR__ 占位符替换为本机实际 PDK
    路径，在 simulations/ 下生成可直接给 ngspice 使用的网表，返回文件名。

    这样仓库里的 ota.spice 不含任何个人绝对路径；换机器时只需设置
    SKY130_PDK_DIR 环境变量，或把 PDK 解压到默认位置 ~/pdk/sky130A。
    """
    with open(os.path.join(SPICE_NETLIST_DIR, template_name), "r", encoding="utf-8") as f:
        content = f.read()
    content = content.replace("__SKY130_PDK_DIR__", get_sky130_pdk_dir())
    with open(os.path.join(SPICE_NETLIST_DIR, out_name), "w", encoding="utf-8") as f:
        f.write(content)
    return out_name


def find_ngspice_exe():
    """定位可用的 ngspice 可执行文件。

    Windows 部分发行包（如 MSYS2）里的 ngspice.exe 是 GUI/Tcl 构建，
    在批处理模式下会静默失败（退出码 1 且无输出）；ngspice_con.exe
    才是控制台构建。因此 Windows 下优先查找 ngspice_con.exe，
    找不到再退回 ngspice。
    """
    if os.name == 'nt':
        for entry in os.environ.get("PATH", "").split(os.pathsep):
            entry = entry.strip()
            if not entry:
                continue
            candidate = os.path.join(entry, "ngspice_con.exe")
            if os.path.isfile(candidate):
                return candidate
    return "ngspice"


class ActionNormalizer():
    """Rescale and relocate the actions."""

    def __init__(self, action_space_low, action_space_high):
        self.action_space_low = action_space_low
        self.action_space_high = action_space_high

    def action(self, action: np.ndarray) -> np.ndarray:
        """Change the range (-1, 1) to (low, high)."""
        low = self.action_space_low
        high = self.action_space_high

        scale_factor = (high - low) / 2
        reloc_factor = high - scale_factor

        # 假设 action 是一个 PyTorch 张量
        if isinstance(action, torch.Tensor):  # 检查 action 是否是 PyTorch 张量
            action = action.cpu().detach().numpy()  # 将其移动到 CPU 并转换为 NumPy 数组
        else:
            # 如果 action 已经是 ndarray 类型，你可以直接使用
            pass
        action = action * scale_factor + reloc_factor
        action = np.clip(action, low, high)

        return action

    def reverse_action(self, action: np.ndarray) -> np.ndarray:
        """Change the range (low, high) to (-1, 1)."""
        low = self.action_space_low
        high = self.action_space_high

        scale_factor = (high - low) / 2
        reloc_factor = high - scale_factor

        action = (action - reloc_factor) / scale_factor
        action = np.clip(action, -1.0, 1.0)

        return action


class OutputParser_ota(DeviceParams):

    def __init__(self, CktGraph):
        self.ckt_hierarchy = CktGraph.ckt_hierarchy
        self.op = CktGraph.op
        super().__init__(self.ckt_hierarchy)

    def ac(self, file_name):
        # AC analysis result parser
        try:
            ota_ac = open(f'{SPICE_NETLIST_DIR}/{file_name}', 'r')
            lines_ac = ota_ac.readlines()
            freq = []
            Vout_mag = []
            Vout_ph = []
            for line in lines_ac:
                Vac = line.split(' ')
                Vac = [i for i in Vac if i != '']
                freq.append(float(Vac[0]))
                Vout_mag.append(float(Vac[1]))
                Vout_ph.append(float(Vac[3]))
            return freq, Vout_mag, Vout_ph
        except:
            print("Simulation errors, no .AC simulation results.")

    def ac_gain(self, file_name):
        # AC analysis result parser
        try:
            ota_ac = open(f'{SPICE_NETLIST_DIR}/{file_name}', 'r')
            lines_ac = ota_ac.readlines()
            freq = []
            gain = []
            for line in lines_ac:
                Vac = line.split(' ')
                Vac = [i for i in Vac if i != '']
                freq.append(float(Vac[0]))
                gain.append(float(Vac[1]))
            return freq, gain
        except:
            print("Simulation errors, no gain simulation results.")

    def ac_pm(self, file_name1, file_name2):
        # AC analysis result parser
        try:
            ota_gain = open(f'{SPICE_NETLIST_DIR}/{file_name1}', 'r')
            lines_ac = ota_gain.readlines()
            freq = []
            gain = []
            for line in lines_ac:
                Vac = line.split(' ')
                Vac = [i for i in Vac if i != '']
                freq.append(float(Vac[0]))
                gain.append(float(Vac[1]))

            ota_pm = open(f'{SPICE_NETLIST_DIR}/{file_name2}', 'r')
            lines_pm = ota_pm.readlines()
            pm = []
            for line in lines_pm:
                Vac = line.split(' ')
                Vac = [i for i in Vac if i != '']
                pm.append(float(Vac[1]))

            return freq, gain, pm

        except:
            print("Simulation errors, no pm simulation results.")

    def ac_cmrr(self, acm_file_name, adm_file_name):
        # AC analysis result parser
        try:
            ota_acm = open(f'{SPICE_NETLIST_DIR}/{acm_file_name}', 'r')
            lines_acm = ota_acm.readlines()
            acm = []
            for line_acm in lines_acm:
                Vac = line_acm.split(' ')
                Vac = [i for i in Vac if i != '']
                acm.append(float(Vac[1]))

            ota_adm = open(f'{SPICE_NETLIST_DIR}/{adm_file_name}', 'r')
            lines_adm = ota_adm.readlines()
            adm = []
            for line_adm in lines_adm:
                Vac = line_adm.split(' ')
                Vac = [i for i in Vac if i != '']
                adm.append(float(Vac[1]))

            return acm, adm
        except:
            print("Simulation errors, no cmrr simulation results.")

    def ac_bandwidth(self, file_name):
        try:
            ota_bandwidth = open(f'{SPICE_NETLIST_DIR}/{file_name}', 'r')
            lines_bandwidth = ota_bandwidth.readlines()
            freq = []
            bandwidth = []
            for line_bandwidth in lines_bandwidth:
                Vac = line_bandwidth.split(' ')
                Vac = [i for i in Vac if i != '']
                freq.append(float(Vac[0]))
                bandwidth.append(float(Vac[1]))

            return freq, bandwidth
        except:
            print("Simulation errors, no bandwidth simulation results.")

    def op_results(self, op_file_name, target_names):
        ota_op = open(f'{SPICE_NETLIST_DIR}/{op_file_name}', 'r')
        lines = ota_op.readlines()

        var_index_map = {}
        values = []
        parsing_vars = False
        parsing_values = False

        for line in lines:
            line = line.strip()

            if line.startswith("Variables:"):
                parsing_vars = True
                continue
            elif line.startswith("Values:"):
                parsing_vars = False
                parsing_values = True
                continue

            if parsing_vars:
                parts = line.split()
                if len(parts) >= 2:
                    idx = int(parts[0])
                    name = parts[1]
                    var_index_map[name] = idx

            elif parsing_values:
                # 去掉编号“0”，只收集 float 数
                parts = line.split()
                for p in parts:
                    try:
                        values.append(float(p))
                    except ValueError:
                        pass

        # 跳过第一个编号项（就是 index `0`）
        # 比如：0    1.116...  → 跳过这两个，留下后面的
        values = values[1:]

        # 映射目标变量名到值
        op_result = {}
        for name in target_names:
            if name not in var_index_map:
                raise KeyError(f"变量名 {name} 不存在")
            idx = var_index_map[name]
            if idx >= len(values):
                raise IndexError(f"{name} 索引 {idx} 超出 values 长度")
            op_result[name] = values[idx]

        return op_result

    def dc(self, file_name):
        # DC analysis result parser
        try:
            ota_dc = open(f'{SPICE_NETLIST_DIR}/{file_name}', 'r')
            lines_dc = ota_dc.readlines()
            Vin_dc = []
            Vout_dc = []
            for line in lines_dc:
                Vdc = line.split(' ')
                Vdc = [i for i in Vdc if i != '']
                Vin_dc.append(float(Vdc[0]))
                Vout_dc.append(float(Vdc[1]))

            dx = Vin_dc[1] - Vin_dc[0]
            dydx = np.gradient(Vout_dc, dx)

            return Vin_dc, Vout_dc
        except:
            print("Simulation errors, no .OP simulation results.")

    def tran(self, file_name):
        # Transient analysis result parser
        try:
            ota_tran = open(f'{SPICE_NETLIST_DIR}/{file_name}', 'r')
            lines_tran = ota_tran.readlines()
            time = []
            Vout_tran = []
            for line in lines_tran:
                line = line.split(' ')
                line = [i for i in line if i != '']
                time.append(float(line[0]))
                Vout_tran.append(float(line[1]))

            return time, Vout_tran
        except:
            print("Simulation errors, no .TRAN simulation results.")

    def dcop(self, file_name):
        # DCOP analysis result parser
        try:
            ota_op = open(f'{SPICE_NETLIST_DIR}/{file_name}', 'r')
            # ldo_tb_op = open(f'{file_dir}', 'r')
            lines_op = ota_op.readlines()
            for index, line in enumerate(lines_op):
                if line == "Values:\n":
                    # print(f"{index}") # catch the index where the dcop values start
                    start_idx = index
            _lines_op = lines_op[start_idx + 2:-1]
            lines_op = []
            for _line in _lines_op:
                lines_op.append(float(_line.split('\n')[0].split('\t')[1]))

            num_dev = len(self.ckt_hierarchy)
            num_dev_params_mos = len(self.params_mos)
            num_dev_params_r = len(self.params_r)
            num_dev_params_c = len(self.params_c)
            num_dev_params_i = len(self.params_i)
            num_dev_params_v = len(self.params_v)

            idx = 0
            for i in range(num_dev):
                dev_type = self.ckt_hierarchy[i][3]
                if dev_type == 'm' or dev_type == 'M':
                    for j in range(num_dev_params_mos):
                        param = self.params_mos[j]
                        self.op[list(self.op)[i]][param] = lines_op[idx + j]
                    idx = idx + num_dev_params_mos
                elif dev_type == 'r' or dev_type == 'R':
                    for j in range(num_dev_params_r):
                        param = self.params_r[j]
                        self.op[list(self.op)[i]][param] = lines_op[idx + j]
                    idx = idx + num_dev_params_r
                elif dev_type == 'c' or dev_type == 'C':
                    for j in range(num_dev_params_c):
                        param = self.params_c[j]
                        self.op[list(self.op)[i]][param] = lines_op[idx + j]
                    idx = idx + num_dev_params_c
                elif dev_type == 'i' or dev_type == 'I':
                    for j in range(num_dev_params_i):
                        param = self.params_i[j]
                        self.op[list(self.op)[i]][param] = lines_op[idx + j]
                    idx = idx + num_dev_params_i
                elif dev_type == 'v' or dev_type == 'V':
                    for j in range(num_dev_params_v):
                        param = self.params_v[j]
                        self.op[list(self.op)[i]][param] = lines_op[idx + j]
                    idx = idx + num_dev_params_v
                else:
                    None

            return self.op
        except:
            print("Simulation errors, no .OP simulation results.")


def _no_grad_trunc_normal_(tensor, mean, std, a, b):
    # Method based on https://people.sc.fsu.edu/~jburkardt/presentations/truncated_normal.pdf
    def norm_cdf(x):
        # Computes standard normal cumulative distribution function
        return (1. + math.erf(x / np.sqrt(2.))) / 2.

    if (mean < a - 2 * std) or (mean > b + 2 * std):
        warnings.warn("mean is more than 2 std from [a, b] in nn.init.trunc_normal_. "
                      "The distribution of values may be incorrect.",
                      stacklevel=2)

    with torch.no_grad():
        # Values are generated by using a truncated uniform distribution and
        # then using the inverse CDF for the normal distribution.
        # Get upper and lower cdf values
        l = norm_cdf((a - mean) / std)
        u = norm_cdf((b - mean) / std)

        # Uniformly fill tensor with values from [l, u], then translate to
        # [2l-1, 2u-1].
        tensor.uniform_(2 * l - 1, 2 * u - 1)

        # Use inverse cdf transform for normal distribution to get truncated
        # standard normal
        tensor.erfinv_()

        # Transform to proper mean, std
        tensor.mul_(std * math.sqrt(2.))
        tensor.add_(mean)

        # Clamp to ensure it's in the proper range
        tensor.clamp_(min=a, max=b)
        return tensor


def trunc_normal_(tensor: Tensor, mean: float = 0., std: float = 1., a: float = -2., b: float = 2.) -> Tensor:
    r"""Fills the input Tensor with values drawn from a truncated
    normal distribution. The values are effectively drawn from the
    normal distribution :math:`\mathcal{N}(\text{mean}, \text{std}^2)`
    with values outside :math:`[a, b]` redrawn until they are within
    the bounds. The method used for generating the random values works
    best when :math:`a \leq \text{mean} \leq b`.

    Args:
        tensor: an n-dimensional `torch.Tensor`
        mean: the mean of the normal distribution
        std: the standard deviation of the normal distribution
        a: the minimum cutoff value
        b: the maximum cutoff value

    Examples:
        >>> w = torch.empty(3, 5)
        >>> nn.init.trunc_normal_(w)
    """
    return _no_grad_trunc_normal_(tensor, mean, std, a, b)


def trunc_normal(mean, std, a=-1, b=1):
    """
    wrapper of <trunc_normal_> to work with np.array

    """

    output = np.zeros(len(mean))

    for i in range(len(mean)):
        output[i] = trunc_normal_(torch.empty(1), mean[i], std, a, b)[0]

    return output
