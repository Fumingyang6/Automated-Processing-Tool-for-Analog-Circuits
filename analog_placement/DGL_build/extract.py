import dgl
import os
import numpy as np
import time


def find_nodes(node_1, node_2, types, src_nodes, dst_nodes):
    num_edges1 = 0  # 例如节点1->节点2的边条数
    edges_index1 = []  # 例如节点1->节点2的索引
    edges_types1 = []  # 例如节点1->节点2的边类型列表
    for k1 in range(len(types)):
        if src_nodes[k1] == node_1 and dst_nodes[k1] == node_2:
            num_edges1 += 1
            edges_index1.append(k1)
            edges_types1.append(types[k1])
    num_edges2 = 0  # 例如节点2->节点1的边条数
    edges_index2 = []  # 例如节点2->节点1的索引
    edges_types2 = []  # 例如节点2->节点1的边类型列表
    for k2 in range(len(types)):
        if src_nodes[k2] == node_2 and dst_nodes[k2] == node_1:
            num_edges2 += 1
            edges_index2.append(k2)
            edges_types2.append(types[k2])
    return num_edges1, num_edges2, edges_index1, edges_index2, edges_types1, edges_types2


def rmv_last(string):
    if string[-1] == '/':
        return string[:-1]
    else:
        return string


def add_match_comment_unified_group(sym_file, sp_file, output_file, netlist_name, four_tube_groups=[]):
    """
    生成带多级group的约束注释：
    - 顶层group1：包含所有匹配器件
    - 子group2/group3：包含四管共源共栅等需要整体放置的组
    """
    all_devices = []
    pair_map = {}

    with open(sym_file, 'r', encoding='utf-8') as f:
        for line in f:
            names = line.strip().split()
            if len(names) == 2:
                dev1_full, dev2_full = names
                dev1_short = dev1_full.split('_')[-1]
                dev2_short = dev2_full.split('_')[-1]
                all_devices.append(dev1_short)
                all_devices.append(dev2_short)
                pair_str = f"{dev1_full} match with {dev2_full}"
                pair_map[dev1_short] = pair_str
                pair_map[dev2_short] = pair_str

    seen = set()
    unique_devices = []
    for d in all_devices:
        if d not in seen:
            unique_devices.append(d)
            seen.add(d)

    # 构建顶层group
    full_unique_devices = [f"{netlist_name}_{d}" for d in unique_devices]
    group_content = "\\".join(full_unique_devices)
    group_str = f"group1({group_content})"

    # 构建四管子group
    subgroup_strs = []
    for idx, group in enumerate(four_tube_groups):
        full_group = [f"{netlist_name}_{d}" for d in group]
        subgroup_content = "\\".join(full_group)
        subgroup_str = f"group{idx+2}({subgroup_content})"
        subgroup_strs.append(subgroup_str)
        print(f"生成四管共源共栅子组: {subgroup_str}")

    # 合并所有group
    all_groups = [group_str] + subgroup_strs
    full_group_str = ", ".join(all_groups)

    with open(sp_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    output_lines = []
    for line in lines:
        stripped = line.rstrip('\n')

        if not line.strip() or line.strip().startswith('*'):
            output_lines.append(line)
            continue

        first_word = line.strip().split()[0] if line.strip() else ""

        if first_word in pair_map:
            comment = f"****{pair_map[first_word]}, {full_group_str}"
            new_line = stripped + "     " + comment + "\n"
            output_lines.append(new_line)
        else:
            output_lines.append(line)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)

    print(f"✅ 统一组模式处理完成！结果已保存至：{output_file}")
    print(f"👥 顶层组内器件：{', '.join(full_unique_devices)}")


def constraint_extraction(dgl_file_path, original_netlist_path):
    start_time = time.time()
    graphs, _ = dgl.load_graphs(dgl_file_path)
    graph = graphs[0]
    netlist_name = (''.join(chr(num) for num in graph.ndata['name'][0].tolist()).split('/')[0])

    netlist_basename = os.path.basename(original_netlist_path)
    netlist_prefix = os.path.splitext(netlist_basename)[0]

    nodes_name = []
    for k in range(graph.number_of_nodes()):
        nodes_name.append(rmv_last(''.join(chr(num) for num in graph.ndata['name'][k].tolist())).split('/')[1])

    possible_match = []
    match_pairs = []
    mismatch_pairs = []
    matchs = dict()
    mismatchs = dict()
    types = graph.edata['type'].tolist()
    src_nodes = graph.edges()[0].tolist()
    dst_nodes = graph.edges()[1].tolist()

    for i in range(graph.number_of_nodes()):
        for j in range(i + 1, graph.number_of_nodes()):
            if (graph.ndata['label'][i].tolist() == graph.ndata['label'][j].tolist() and graph.ndata['feat'][
                i].tolist() == graph.ndata['feat'][j].tolist()):
                possible_match.append((
                    rmv_last(''.join(chr(num) for num in graph.ndata['name'][i].tolist())).split('/')[
                        1],
                    rmv_last(''.join(chr(num) for num in graph.ndata['name'][j].tolist())).split('/')[
                        1]))

                num_edges1_1, num_edges2_1, edges_index1_1, edges_index2_1, edges_types1_1, edges_types2_1 = find_nodes(
                    i, j, types, src_nodes, dst_nodes)
                count = sum(x == y for x, y in zip(edges_types1_1, edges_types2_1))
                if num_edges1_1 > 1 and count > 1:
                    match_pairs.append((rmv_last(''.join(chr(num) for num in graph.ndata['name'][i].tolist())).split(
                        '/')[1], rmv_last(''.join(chr(num) for num in graph.ndata['name'][j].tolist())).split('/')[1]))
                else:
                    mismatch_pairs.append((rmv_last(''.join(chr(num) for num in graph.ndata['name'][i].tolist())).split(
                        '/')[1], rmv_last(''.join(chr(num) for num in graph.ndata['name'][j].tolist())).split('/')[1]))

            else:
                mismatch_pairs.append((
                    rmv_last(''.join(chr(num) for num in graph.ndata['name'][i].tolist())).split('/')[
                        1],
                    rmv_last(''.join(chr(num) for num in graph.ndata['name'][j].tolist())).split('/')[
                        1]))

    matchs[netlist_name] = match_pairs
    mismatchs[netlist_name] = mismatch_pairs

    print('匹配约束提取时间', time.time() - start_time, 's')

    filtered_list = [
        item for item in match_pairs
        if not any('R' in elem or 'C' in elem for elem in item)
    ]

    # ====================== 新增：自动分组两两配对 + 识别四管共源共栅组 ======================
    all_devs = set()
    for pair in filtered_list:
        all_devs.add(pair[0])
        all_devs.add(pair[1])

    dev_groups = {}
    for dev_name in all_devs:
        for i in range(graph.number_of_nodes()):
            node_name = rmv_last(''.join(chr(num) for num in graph.ndata['name'][i].tolist())).split('/')[1]
            if node_name == dev_name:
                key = (graph.ndata['label'][i].item(), tuple(graph.ndata['feat'][i].tolist()))
                if key not in dev_groups:
                    dev_groups[key] = []
                dev_groups[key].append(dev_name)
                break

    final_pairs = []
    # 新增：收集需要整体放置的四管组
    four_tube_groups = []
    for group in dev_groups.values():
        group_sorted = sorted(group)
        # 识别四管共源共栅组（4个相同器件）
        if len(group_sorted) == 4:
            four_tube_groups.append(group_sorted)
            print(f"识别到四管共源共栅组: {group_sorted}")
        # 两两配对
        for i in range(0, len(group_sorted), 2):
            if i + 1 < len(group_sorted):
                final_pairs.append((group_sorted[i], group_sorted[i + 1]))
    # ======================================================================================

    print('原始匹配对：', filtered_list)
    print('优化后匹配对：', final_pairs)

    sym_file_path = f'./{netlist_prefix}.sym'
    with open(sym_file_path, 'w') as file:
        for item in final_pairs:
            full_dev1 = f"{netlist_name}_{item[0]}"
            full_dev2 = f"{netlist_name}_{item[1]}"
            line = f"{full_dev1} {full_dev2}\n"
            file.write(line)

    original_ext = os.path.splitext(original_netlist_path)[1]
    output_file_path = f'./new_{netlist_prefix}{original_ext}'

    # 传入四管组信息生成带子组的注释
    add_match_comment_unified_group(sym_file_path, original_netlist_path, output_file_path, netlist_name,
                                    four_tube_groups)

    outpath = os.path.abspath(output_file_path)

    return outpath


if __name__ == "__main__":
    # ====================== 在这里修改你的网表路径 ======================
    # 示例1：处理CDL格式网表
    # DGL_FILE = "./netlists/CD2101_250710/rec_nmos100_dgl.bin"
    # ORIGINAL_NETLIST = "./netlists/CD2101_250710/rec_nmos100.cdl"

    # 示例2：处理SP格式网表（输入ota4.sp，生成ota4.sym和new_ota4.sp）
    DGL_FILE = "./ota1.dgl"
    ORIGINAL_NETLIST = "./ota1.sp"
    # ====================================================================

    output_path = constraint_extraction(DGL_FILE, ORIGINAL_NETLIST)
    print(f"\n.sym约束文件：{os.path.abspath(f'./{os.path.splitext(os.path.basename(ORIGINAL_NETLIST))[0]}.sym')}")
    print(f"带约束注释的网表：{output_path}")