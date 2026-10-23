import networkx as nx
from .ckt import *
import dgl
import matplotlib.pyplot as plt

def isDevice(inst):
    if str(inst.reference) in nmos_set or \
       str(inst.reference) in pmos_set or \
       str(inst.reference) in capacitor_set or \
       str(inst.reference) in resistor_set:
        return True
    return False

def isNmos(inst):
    if inst.reference in nmos_set:
        return True
    return False

def isPmos(inst):
    if inst.reference in pmos_set:
        return True
    return False

def isCap(inst):
    if inst.reference in capacitor_set:
        return True
    return False

def isRes(inst):
    if inst.reference in resistor_set:
        return True
    return False

def isThreeTerm(inst):
    if inst.reference in three_term_set:
        return True
    return False

# 构建节点
def build_ckt_dev(netlist, topCkt, subCkt, thisInst, name_prefix, level):
    ckt_nl = None
    for ckt in netlist:
        if ckt.name == thisInst.reference:
            ckt_nl = ckt

    # thisInst is device
    if ckt_nl == None:
        dev = Device(name_prefix, thisInst.reference, thisInst.parameters, level + 1)

        # 直接使用从ckt.py导入的正确集合进行判断
        if thisInst.reference in nmos_set:
            drain = Pin(dev.name + '.d', dev, 'nd')
            gate = Pin(dev.name + '.g', dev, 'ng')
            source = Pin(dev.name + '.s', dev, 'ns')
            bulk = Pin(dev.name + '.b', dev, 'nb')
            dev.add_pin(drain)
            dev.add_pin(gate)
            dev.add_pin(source)
            dev.add_pin(bulk)
        elif thisInst.reference in pmos_set:
            drain = Pin(dev.name + '.d', dev, 'pd')
            gate = Pin(dev.name + '.g', dev, 'pg')
            source = Pin(dev.name + '.s', dev, 'ps')
            bulk = Pin(dev.name + '.b', dev, 'pb')
            dev.add_pin(drain)
            dev.add_pin(gate)
            dev.add_pin(source)
            dev.add_pin(bulk)
        elif thisInst.reference in capacitor_set:
            t1 = Pin(dev.name + '.t1', dev, 'c')
            t2 = Pin(dev.name + '.t2', dev, 'c')
            dev.add_pin(t1)
            dev.add_pin(t2)
        elif thisInst.reference in resistor_set:
            t1 = Pin(dev.name + '.t1', dev, 'r')
            t2 = Pin(dev.name + '.t2', dev, 'r')
            dev.add_pin(t1)
            dev.add_pin(t2)
        else:
            print(f"警告: 未识别的器件类型 {dev.type}，已跳过")

        dev.parentCkt = subCkt
        topCkt.add_device(dev)
        subCkt.add_device(dev)
        return


# 构建网络连接边
def build_net(netlist, subCkt, subNet, thisNet, thisInst, name_prefix):
    ckt_nl = None
    for ckt in netlist:
        if ckt.name == thisInst.reference:
            ckt_nl = ckt

    # thisInst is device
    if ckt_nl == None:
        ids = []
        for i in range(len(thisInst.pins)):
            if thisNet.name == thisInst.pins[i]:
                ids.append(i)

        dev = subCkt.get_device_by_name(name_prefix)

        # 添加终极安全检查，永远不会再出现索引越界
        for id in ids:
            if id >= len(dev.pins):
                print(f"警告: 器件 {dev.name} 引脚索引 {id} 超出范围，已跳过")
                continue
            pin = dev.pins[id]
            if not pin.connected:
                pin.connected = True
                pin.net = subNet
                subNet.add_pin(pin)
        return


# 构建图
def build_graph(netlist):
    topCkt = None
    G_dict = {}
    G = nx.MultiDiGraph()

    # build nodes (devices) 构建节点
    for ckt in netlist:
        if ckt.typeof == 'topcircuit':
            topCkt = Ckt(ckt.name, 0)
            for inst in ckt.instances:
                build_ckt_dev(netlist, topCkt, topCkt, inst, topCkt.name + '/' + inst.name, 0)

    for dev in topCkt.allDevices:
        G.add_node(dev.idx, device=str(dev).split()[1], label=dev.name.split("/")[1])

    # build edges (nets) 构建边
    for ckt in netlist:
        if ckt.typeof == 'topcircuit':
            for net in ckt.nets.values():
                isPower = False
                topNet = Net(topCkt.name + '/' + net.name, isPower)
                for inst in ckt.instances:
                    build_net(netlist, topCkt, topNet, net, inst, topCkt.name + '/' + inst.name)
                if len(topNet.pins) > 0:
                    topCkt.add_net(topNet)

    for net in topCkt.nets.values():
        if not net.isPower:
            pins = list(net.pins.values())
            for i in range(len(pins)):
                for j in range(len(pins)):
                    if i != j:
                        dev1, dev2 = pins[i].device, pins[j].device
                        if dev1.idx != dev2.idx:
                            in_type = pins[j].type
                            G.add_edge(dev1.idx, dev2.idx, in_type=in_type)

    G_dict[topCkt.name] = G

    return G_dict, topCkt

    # # Networks 多重有向图 MultiDiGraph
    # # 打印节点特征
    # for node in G.nodes():
    #     print(f"Node {node} features: {G.nodes[node]}")
    #
    # # 打印边特征
    # for edge in G.edges(keys=True):
    #     print(f"Edge from {edge[0]} to {edge[1]}, key {edge[2]} features: {G.edges[edge]}") # key为哈希标识符，用于区分一对节点之间的多边
    # # print(G)
    #
    # # 可视化图
    # # pos = nx.spring_layout(G)
    # pos = nx.kamada_kawai_layout(G)
    #
    # # nx.draw(G, pos, with_labels=True, node_color='lightblue', node_size=500,
    # #         edge_color='gray', width=1, arrowsize=20, arrowstyle='->')
    #
    # # 给不同类型的边设置不同的颜色
    # node_colors = {'n33e2r': 'purple', 'p33e2r': 'red', 'n50e2r': 'blue', 'p50e2r': 'gray', 'mim1_ckt': 'yellow', 'rpposab_ckt': 'lightblue'}
    # # 绘制节点
    # # nx.draw_networkx_nodes(G, pos, node_size=300, node_color='lightblue')
    # # 绘制不同颜色的节点（不同类型）
    # nx.draw_networkx_nodes(G, pos, node_size=300, node_color=[node_colors[G.nodes[node]['device']] for node in G.nodes()])
    # # 绘制节点标签
    # nx.draw_networkx_labels(G, pos, labels={node: G.nodes[node]['label'] for node in G.nodes()})
    # # 给不同类型的边设置不同的颜色
    # edge_colors = {'nd': 'black', 'ns': 'red', 'ng': 'blue', 'pd': 'gray', 'pg': 'yellow', 'ps': 'purple', 'c': 'orange', 'r': 'green'}
    # # 绘制不同颜色的边（不同类型）
    # for edge in G.edges():
    #     edge_type = G.edges[edge[0], edge[1], 0]['in_type']
    #     nx.draw_networkx_edges(G, pos, edgelist=[edge], edge_color=edge_colors[edge_type], width=2, arrowsize=15)
    #
    # plt.show()
    # # plt.savefig('./MultiDigraph.png', dpi=1280)

    


