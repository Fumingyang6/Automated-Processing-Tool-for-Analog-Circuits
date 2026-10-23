import dgl
import torch
from netlist.parse_netlist import parse_spice
from ckt.graph import build_graph
from init_feature import initFeature
import os

# 导入动态器件集合
from ckt.ckt import nmos_set, pmos_set, capacitor_set, resistor_set


def extract_devtype_from_raw_netlist(netlist):
    """
    【构图前使用】从 parse_spice 解析后的原始网表，提取所有唯一器件类型
    适配 .SUBCKT 结构，遍历所有子电路内的器件
    :param netlist: parse_spice 输出的原始网表对象
    :return: 去重后的器件类型列表
    """
    all_dev_types = set()
    for subckt in netlist:
        # 遍历子电路内所有器件实例
        for inst in subckt.instances:
            # 解析完成后：器件类型统一存在 reference 字段，不再使用 instnets
            dev_type = inst.reference
            all_dev_types.add(dev_type)
    return list(all_dev_types)


def auto_classify_devices(type_list):
    """
    基于CDL通用命名规则，自动分类 NMOS/PMOS/电容/电阻
    规则：
    1. n 开头 → NMOS
    2. p 开头 → PMOS
    3. 包含 mim/cfmom → 电容
    4. r 开头 → 电阻
    """
    # 先清空原有动态集合
    nmos_set.clear()
    pmos_set.clear()
    capacitor_set.clear()
    resistor_set.clear()

    for dev_type in type_list:
        t = dev_type.lower()
        # NMOS：n开头 或 包含nch
        if t.startswith("n") or "nch" in t:
            nmos_set.append(dev_type)
        # PMOS：p开头 或 包含pch
        elif t.startswith("p") or "pch" in t:
            pmos_set.append(dev_type)
        # 电容：包含mim/cfmom
        elif "mim" in t or "cfmom" in t:
            capacitor_set.append(dev_type)
        # 电阻：r开头
        elif t.startswith("r"):
            resistor_set.append(dev_type)

    # 打印分类结果（调试用）
    print(f"\n【器件自动识别分类结果】")
    print(f"NMOS 类型: {nmos_set}")
    print(f"PMOS 类型: {pmos_set}")
    print(f"电容 类型: {capacitor_set}")
    print(f"电阻 类型: {resistor_set}\n")


def cdl_to_dgl(cdl_file_path, save_path=None):
    """
    将CDL网表文件转换为DGL图并可选保存到文件
    """
    print(f"正在解析网表文件: {cdl_file_path}")

    # 1. 读取CDL文件内容（兼容utf-8/gbk编码）
    try:
        with open(cdl_file_path, 'r', encoding='utf-8') as f:
            netlist_string = f.read()
    except UnicodeDecodeError:
        with open(cdl_file_path, 'r', encoding='gbk') as f:
            netlist_string = f.read()

    # 2. 解析SPICE/CDL原始网表
    netlist = parse_spice(netlist_string)
    print(f"网表解析完成，找到 {len(netlist)} 个子电路")

    # 3. 从【原始网表】提取所有器件类型 + 自动分类（必须在build_graph之前！）
    all_dev_types = extract_devtype_from_raw_netlist(netlist)
    auto_classify_devices(all_dev_types)

    # 4. 构建NetworkX图 + 电路对象（此时器件集合已赋值，正常识别器件/创建引脚）
    G_dict, topCkt = build_graph(netlist)
    G_nx = G_dict[topCkt.name]
    print(f"NetworkX图构建完成: 节点数={G_nx.number_of_nodes()}, 边数={G_nx.number_of_edges()}")

    # 5. 转换为DGL图并初始化特征
    G_dgl = initFeature(G_nx, topCkt)
    print(f"DGL图转换完成: 节点特征维度={G_dgl.ndata['feat'].shape}, 边特征维度={G_dgl.edata['type'].shape}")

    # 6. 保存DGL图到文件
    if save_path:
        dgl.save_graphs(save_path, [G_dgl])
        print(f"DGL图已保存到: {save_path}")

    return G_dgl, topCkt


if __name__ == "__main__":
    # 网表路径 & 保存路径
    CDL_FILE = "ota1.sp"
    SAVE_FILE = "./ota1.dgl"

    # 执行转换
    G_dgl, topCkt = cdl_to_dgl(CDL_FILE, SAVE_FILE)

    # 打印DGL图详情
    print("\n=== DGL图详细信息 ===")
    print(f"图类型: {type(G_dgl)}")
    print(f"节点数: {G_dgl.num_nodes()}")
    print(f"边数: {G_dgl.num_edges()}")
    print(f"节点特征列表: {list(G_dgl.ndata.keys())}")
    print(f"边特征列表: {list(G_dgl.edata.keys())}")