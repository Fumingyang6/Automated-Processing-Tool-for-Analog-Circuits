import dgl
import torch
import networkx as nx
from ckt.ckt import *
import matplotlib.pyplot as plt


import re  # 新增：导入正则表达式模块


# 工业级健壮的参数提取函数，处理所有可能的格式
def get_param(dev, key, default=0.0):
    # 参数名别名映射：同时支持CDL和SP格式
    alias_map = {
        'MR': ['MR', 'multi', 'm'],  # 并联数
        'L': ['L', 'l'],             # 沟道长度
        'W': ['W', 'w'],             # 沟道宽度
        'NF': ['NF', 'nf', 'nfingers'] ,# 指数量
        'LR': ['LR', 'L', 'l'],
        'WR': ['WR', 'W', 'w']
    }

    # 获取该key对应的所有别名
    aliases = alias_map.get(key, [key])

    # 遍历所有别名，找到第一个存在的参数
    for alias in aliases:
        if alias in dev.param:
            value_str = dev.param[alias].strip()
            if not value_str:
                continue
            match = re.search(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', value_str)
            if match:
                try:
                    return float(match.group())
                except ValueError:
                    continue

    # 所有别名都不存在，返回默认值
    return default


# tensor要求张量维度保持一致，因此需要对不一致的名称长度进行补齐，使用‘/’进行补齐，对应ord值为47
def fill(lst):
    same_dim = True
    target_dim = max(len(item) for item in lst)
    for item in lst:
        if len(item) != target_dim:
            same_dim = False
            break
    # 补齐列表元素
    if not same_dim:
        lst = [item + [47] * (target_dim - len(item)) for item in lst]
    return lst


# 特征初始化
def initFeature(G_nx, topCkt):  # 输入的参数 G_nx是MultiDiGraph， topCkt是Ckt类
    dev_list = []  # 所有器件类型的列表
    dev_list.extend(list(nmos_set))  # 扩展器件类型到dev_list
    dev_list.extend(list(pmos_set))
    dev_list.extend(list(capacitor_set))
    dev_list.extend(list(resistor_set))
    print(f"支持的器件类型: {dev_list}")
    feat = []  # 节点特征矩阵
    name = []  # 节点名称表示
    labels = []  # 节点标签0，1，2，3
    type = []  # 器件类型

    G_dgl = dgl.DGLGraph(G_nx)  # 创建一个没有节点和边的空图（此处接收一个Networks图数据G_nx）
    for i in range(G_nx.number_of_nodes()):  # 遍历G_nx的节点
        dev = topCkt.allDevices[i]  # 从Ckt中取出第i个device
        feat_len = len(dev_list) + 6  # 特征值组成 7（器件类型长度） + 3
        f = [0.] * feat_len  # 特征值全部置0
        onehot = dev_list.index(dev.type)  # 按照device的type找到 对应dev_list的索引
        f[onehot] = 1  # 对应索引的数据设置为1表示是这个type
        print(dev.name)

        # 修改：NMOS参数（M→MR）
        if dev.isNmos():
            W = get_param(dev, 'W')
            L = get_param(dev, 'L')
            MR = get_param(dev, 'MR')
            f[-3] = W / 1e-3  # 设置倒数第三个值为 器件参数W的对应值
            f[-2] = L  # 设置倒数第二个值为 器件参数L的对应值
            f[-1] = MR  # 设置倒数第一个值为 器件并联数MR
            labels.append(0)

        # 修改：PMOS参数（M→MR）
        elif dev.isPmos():
            W = get_param(dev, 'W')
            L = get_param(dev, 'L')
            MR = get_param(dev, 'MR')
            f[-3] = W / 1e-3
            f[-2] = L
            f[-1] = MR
            labels.append(1)

        # 修改：电容参数（l→LR, w→WR, m→MR）
        elif dev.isCap():
            if dev.type == 'mim1_ckt':
                LR = get_param(dev, 'LR')
                WR = get_param(dev, 'WR')
                MR = get_param(dev, 'MR')
                f[-3] = MR
                f[-2] = LR / 1e-3
                f[-1] = WR / 1e-3
                labels.append(2)
            elif dev.type == 'mim2_ckt':
                LR = get_param(dev, 'LR')
                WR = get_param(dev, 'WR')
                MR = get_param(dev, 'MR')
                f[-3] = MR
                f[-2] = LR / 1e-3
                f[-1] = WR / 1e-3
                labels.append(2)
            elif dev.type == 'cfmom_2t':
                LR = get_param(dev, 'LR')
                WR = get_param(dev, 'WR')
                MR = get_param(dev, 'MR')
                f[-3] = MR
                f[-2] = LR / 1e-3
                f[-1] = WR / 1e-3
                labels.append(2)

            elif dev.type == 'cfmom':
                L = get_param(dev, 'L')
                W = get_param(dev, 'W')
                MR = get_param(dev, 'MR')
                f[-3] = MR
                f[-2] = L / 1e-3
                f[-1] = W / 1e-3
                labels.append(2)

        # 修改：电阻参数（M→MR，支持rpposab_ckt_p）
        elif dev.isRes():
            if dev.type in ['rpposab_ckt', 'rpposab_ckt_p','rppolywo']:
                W = get_param(dev, 'W')
                L = get_param(dev, 'L')
                MR = get_param(dev, 'MR')
                f[-3] = MR
                f[-2] = W
                f[-1] = L / 1e-3
                labels.append(3)

        type.append(f[:4])  # 7种器件类型的one-hot编码
        feat.append(f[4:])  # 剩下3个是器件参数特征
        name.append([ord(char) for char in dev.name])

    name = fill(name)  # 器件名称长度补齐

    G_dgl.ndata['feat'] = torch.tensor(feat)  # 设置与节点特征
    G_dgl.ndata['name'] = torch.tensor(name)  # 设置节点名称
    G_dgl.ndata['label'] = torch.LongTensor(labels)  # 设置节点类型标签
    G_dgl.ndata['type'] = torch.LongTensor(type)  # 设置节点类型编码

    etype = []  # 边类型列表
    for e, e_data in G_nx.edges.items():  # 此处需借助networkx构图G_nx
        # NMOS
        if e_data['in_type'] == 'ng':
            etype.append(0)
        elif e_data['in_type'] == 'nd':
            etype.append(1)
        elif e_data['in_type'] == 'ns':
            etype.append(2)
        # PMOS
        elif e_data['in_type'] == 'pg':
            etype.append(3)
        elif e_data['in_type'] == 'pd':
            etype.append(4)
        elif e_data['in_type'] == 'ps':
            etype.append(5)
        # 电容
        elif e_data['in_type'] == 'c':
            etype.append(6)
        # 电阻
        elif e_data['in_type'] == 'r':
            etype.append(7)
        else:
            etype.append(8)

    G_dgl.edata['type'] = torch.tensor(etype)  # 设置边特征

    return G_dgl