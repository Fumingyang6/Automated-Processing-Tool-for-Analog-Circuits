import re


def parse_spice_value(value):
    """解析 SPICE 参数值，处理单位转换为浮点数（单位：微米）。"""
    units = {'f': 1e-15, 'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3, 'k': 1e3, 'meg': 1e6}
    match = re.match(r'([0-9\.]+)([a-zA-Z]*)', value)
    if match:
        num = float(match.group(1))
        unit = match.group(2).lower()
        if unit in units:
            return num * units[unit] / 1e-6  # 转换为微米
        return num / 1e-6
    raise ValueError(f"无效的 SPICE 值：{value}")


def longest_common_prefix_ending_with(strs, char='_'):
    """计算字符串列表的最长公共前缀，以指定字符结尾。"""
    if not strs:
        return ""
    P = strs[0]
    candidates = [i for i in range(len(P)) if P[i] == char]
    if not candidates:
        return ""
    max_i = max([i for i in candidates if all(s[:i + 1] == P[:i + 1] for s in strs)], default=-1)
    if max_i != -1:
        return P[:max_i + 1]
    else:
        return ""


def parse_spice_netlist(file_path):
    """
    通用SPICE/CDL网表解析器（双格式自动兼容）
    支持：
    - SP格式：M1/C0/R0 + w/l/multi
    - CDL格式：XM1/XC0/XR0 + W/L/MR
    """
    devices = []
    node_to_devices = {}
    device_name_to_index = {}
    logical_groups = {}  # 存储逻辑组，例如 {'M0': [M0_0_idx, M1_1_idx], 'M1': [M1_0_idx, M1_1_idx]}
    index = 0

    with open(file_path, 'r') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        # ====================== 核心修改1：支持CDL的X前缀器件 ======================
        if line.startswith(('M', 'C', 'R', 'XM', 'XC', 'XR')):
            parts = line.split()
            instance_name = parts[0]

            # 自动去除CDL的X前缀，统一为SP格式命名
            if instance_name.startswith('X'):
                base_name_no_x = instance_name[1:]
            else:
                base_name_no_x = instance_name

            # 提取节点
            if instance_name.startswith(('M', 'XM')):
                nodes = parts[1:5]  # 晶体管：漏极、栅极、源极、衬底
            else:  # 'C'/'R'/'XC'/'XR'
                nodes = parts[1:3]  # 电容/电阻：正、负节点

            # ====================== 核心修改2：支持大小写参数和MR/multi ======================
            params = {}
            param_start = 5 if instance_name.startswith(('M', 'XM')) else 3
            for param in parts[param_start:]:
                if '=' in param:
                    key, value = param.split('=')
                    # 参数名统一转为小写，同时支持大小写
                    params[key.strip().lower()] = value.strip()

            # 处理设备尺寸
            if instance_name.startswith(('M', 'XM')):
                # 同时支持w/W和l/L
                if ('w' in params or 'W' in params) and ('l' in params or 'L' in params):
                    w = parse_spice_value(params.get('w', params.get('W')))
                    l = parse_spice_value(params.get('l', params.get('L')))
                    # 同时支持multi和MR
                    multi = int(params.get('multi', params.get('mr', '1')))

                    base_name = base_name_no_x
                    group_indices = []
                    for m in range(multi):
                        unique_instance_name = f"{base_name}_{m}" if multi > 1 else base_name
                        devices.append({'name': unique_instance_name, 'width': w, 'height': l})
                        device_name_to_index[unique_instance_name] = index
                        group_indices.append(index)
                        for node in nodes:
                            if node not in node_to_devices:
                                node_to_devices[node] = []
                            node_to_devices[node].append(index)
                        index += 1
                    if multi > 1:
                        logical_groups[base_name] = group_indices
                else:
                    print(f"警告：晶体管 {instance_name} 缺少 'w' 或 'l' 参数")
                    continue

            elif instance_name.startswith(('C', 'R', 'XC', 'XR')):
                if ('w' in params or 'W' in params) and ('l' in params or 'L' in params):
                    w = parse_spice_value(params.get('w', params.get('W')))
                    l = parse_spice_value(params.get('l', params.get('L')))
                    # 电阻电容也支持multi
                    multi = int(params.get('multi', params.get('mr', '1')))

                    base_name = base_name_no_x
                    group_indices = []
                    for m in range(multi):
                        unique_instance_name = f"{base_name}_{m}" if multi > 1 else base_name
                        devices.append({'name': unique_instance_name, 'width': w, 'height': l})
                        device_name_to_index[unique_instance_name] = index
                        group_indices.append(index)
                        for node in nodes:
                            if node not in node_to_devices:
                                node_to_devices[node] = []
                            node_to_devices[node].append(index)
                        index += 1
                    if multi > 1:
                        logical_groups[base_name] = group_indices
                else:
                    print(f"警告：元件 {instance_name} 缺少 'w' 或 'l' 参数")
                    continue

    nets = [node_to_devices[node] for node in node_to_devices if len(node_to_devices[node]) > 1]
    return devices, nets, device_name_to_index, logical_groups


def parse_sym_file(file_path, device_name_to_index):
    """
    通用对称文件解析器（双格式自动兼容）
    自动处理：
    - 子电路前缀（如OTA3_my_M1 → M1）
    - CDL的X前缀（如XM1 → M1）
    - multi实例匹配
    """
    sym_pairs = []
    cc_pairs = []  # 存储配对的共质心组，例如 [(group1, group2), ...]

    all_names = set()
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            names = line.split()
            all_names.update(names)
    all_names = list(all_names)

    # 计算以 '_' 结尾的最长公共前缀
    prefix = longest_common_prefix_ending_with(all_names)

    # 处理每行
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            # 移除前缀
            parts = [name[len(prefix):] for name in parts]
            if len(parts) == 2:  # 对称对
                dev1, dev2 = parts
                # ====================== 核心修改3：自动匹配带/不带X前缀的器件 ======================
                indices1 = []
                indices2 = []
                for name, idx in device_name_to_index.items():
                    # 支持：dev1 / Xdev1 / dev1_0 / Xdev1_0
                    if (name == dev1 or
                            name == f"X{dev1}" or
                            name.startswith(f"{dev1}_") or
                            name.startswith(f"X{dev1}_")):
                        indices1.append(idx)
                    if (name == dev2 or
                            name == f"X{dev2}" or
                            name.startswith(f"{dev2}_") or
                            name.startswith(f"X{dev2}_")):
                        indices2.append(idx)

                if indices1 and indices2:
                    if len(indices1) == len(indices2):
                        for idx1, idx2 in zip(sorted(indices1), sorted(indices2)):
                            sym_pairs.append((idx1, idx2))
                        if len(indices1) > 1:
                            cc_pairs.append((indices1, indices2))
                    else:
                        print(f"警告：对称对 {dev1}, {dev2} 的 multi 实例数量不匹配")
                else:
                    print(f"警告：对称对 {dev1}, {dev2} 未在网表中找到")
            elif len(parts) == 1:  # 自对称设备
                dev = parts[0]
                indices = []
                for name, idx in device_name_to_index.items():
                    if (name == dev or
                            name == f"X{dev}" or
                            name.startswith(f"{dev}_") or
                            name.startswith(f"X{dev}_")):
                        indices.append(idx)
                if indices:
                    if len(indices) == 1:
                        sym_pairs.append((indices[0], indices[0]))  # 单设备自对称
                    # 对于 multi > 1，不做处理
                else:
                    print(f"警告：自对称设备 {dev} 未在网表中找到")

    return sym_pairs, cc_pairs