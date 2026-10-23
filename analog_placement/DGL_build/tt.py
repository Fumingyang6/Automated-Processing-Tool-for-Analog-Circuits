import dgl
import torch

# 加载保存的DGL图
graphs, _ = dgl.load_graphs("./compare.dgl")
G = graphs[0]

print("=== 基本结构验证 ===")
print(f"节点总数: {G.num_nodes()}")
print(f"边总数: {G.num_edges()}")
print(f"节点特征列表: {list(G.ndata.keys())}")
print(f"边特征列表: {list(G.edata.keys())}")

# 验证特征维度
print(f"\n特征维度验证:")
print(f"feat维度: {G.ndata['feat'].shape} (应该是[36, 3])")
print(f"name维度: {G.ndata['name'].shape}")
print(f"label维度: {G.ndata['label'].shape} (应该是[36])")
print(f"type维度: {G.ndata['type'].shape} (应该是[36, 7])")
print(f"边type维度: {G.edata['type'].shape} (应该是[692])")

# 统计各类型器件数量
labels = G.ndata['label'].numpy()
print(f"\n器件类型统计:")
print(f"NMOS数量: {sum(labels == 0)} (应该是18个)")
print(f"PMOS数量: {sum(labels == 1)} (应该是12个)")
print(f"电容数量: {sum(labels == 2)} (应该是1个)")
print(f"电阻数量: {sum(labels == 3)} (应该是5个)")

print("\n=== 节点特征细节验证 ===")
print("随机抽取5个器件验证:")

# 抽取索引0、5、10、15、20的器件
for idx in [0, 5, 10, 15, 20]:
    label = G.ndata['label'][idx].item()
    feat = G.ndata['feat'][idx].numpy()
    type_onehot = G.ndata['type'][idx].numpy()

    type_name = ["NMOS", "PMOS", "电容", "电阻"][label]
    print(f"\n器件 {idx}:")
    print(f"  类型: {type_name}")
    print(f"  参数特征: W={feat[0]:.2f}, L={feat[1]:.2f}, MR={feat[2]:.2f}")
    print(f"  类型one-hot: {type_onehot}")

    print("\n=== 边特征验证 ===")
    edge_types = G.edata['type'].numpy()

    # 统计各类型边的数量
    print(f"边类型统计:")
    print(f"NMOS栅极(ng): {sum(edge_types == 0)}")
    print(f"NMOS漏极(nd): {sum(edge_types == 1)}")
    print(f"NMOS源极(ns): {sum(edge_types == 2)}")
    print(f"PMOS栅极(pg): {sum(edge_types == 3)}")
    print(f"PMOS漏极(pd): {sum(edge_types == 4)}")
    print(f"PMOS源极(ps): {sum(edge_types == 5)}")
    print(f"电容(c): {sum(edge_types == 6)}")
    print(f"电阻(r): {sum(edge_types == 7)}")
    print(f"其他: {sum(edge_types == 8)}")