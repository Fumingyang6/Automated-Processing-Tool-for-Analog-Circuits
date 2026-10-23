import gdspy
import os
import numpy as np
import sys

# 导入工艺层定义
from device_generation.glovar import tsmc40_glovar as glovar
layer = glovar.layer

# 导入业务模块
from device_generation.Mosfet import Mosfet
from netlist_symlist import parse_spice_netlist, parse_match_constraint
from main import cc_main_flow


def generate_cc_array_gds(
    match_group_params,
    cc_matrix,
    seg_nf,
    space_x=0.3,
    space_y=0.3,
    output_dir="./cc_output",
    array_name="cc_array"
):
    # 强制格式标准化
    if isinstance(cc_matrix, list):
        arr = np.array(cc_matrix)
    else:
        arr = np.array(cc_matrix)
    if arr.ndim == 1:
        total = len(arr)
        row_cnt = int(np.sqrt(total))
        arr = arr.reshape(row_cnt, -1)
    cc_matrix = arr.astype(int).tolist()
    rows = len(cc_matrix)
    cols = len(cc_matrix[0])
    print(f" 矩阵规模：{rows}行 × {cols}列")

    os.makedirs(output_dir, exist_ok=True)
    unit_dir = os.path.join(output_dir, "unit_cells")
    os.makedirs(unit_dir, exist_ok=True)

    # 生成有源标准单元
    unit_info = {}
    top_lib = gdspy.GdsLibrary()

    for group_idx, dev_info in enumerate(match_group_params, 1):
        print(f"生成第{group_idx}组器件单元：{dev_info['name']}")
        unit_name = f"{dev_info['name']}_seg{seg_nf}"
        is_nch = 'nch' in dev_info['model'].lower()

        mos_unit = Mosfet(
            nch=is_nch,
            name=unit_name,
            w=dev_info['w'],
            l=dev_info['l'],
            nf=seg_nf,
            attr=dev_info.get('attr', []),
            spectre=dev_info.get('spectre', True),
            pinConType=dev_info.get('pinConType', None),
            bulkCon=dev_info.get('bulkCon', [0])
        )

        unit_gds_path = os.path.join(unit_dir, f"{unit_name}.gds")
        mos_unit.to_gds(unit_gds_path)

        temp_lib = gdspy.GdsLibrary()
        temp_lib.read_gds(unit_gds_path)
        unit_cell = temp_lib.top_level()[0]
        top_lib.add(unit_cell)

        bb = unit_cell.get_bounding_box()
        bb_ll = bb[0]
        bb_ur = bb[1]
        cell_w = bb_ur[0] - bb_ll[0]
        cell_h = bb_ur[1] - bb_ll[1]

        offset_x = bb_ll[0]
        offset_y = bb_ll[1]

        unit_info[group_idx] = {
            "cell": unit_cell,
            "width": cell_w,
            "height": cell_h,
            "offset_x": offset_x,
            "offset_y": offset_y
        }
        print(f"单元尺寸：{cell_w:.3f} × {cell_h:.3f} um")

    # ========== 真实MOS dummy生成 ==========
    ref_w = unit_info[1]["width"]
    ref_h = unit_info[1]["height"]

    has_dummy = any(0 in row for row in cc_matrix)
    if has_dummy:
        ref_dev = match_group_params[0]
        ref_is_nch = 'nch' in ref_dev['model'].lower()

        # 生成同规格MOS dummy
        dummy_mos = Mosfet(
            nch=ref_is_nch,
            name="dummy_unit",
            w=ref_dev['w'],
            l=ref_dev['l'],
            nf=seg_nf,
            attr=ref_dev.get('attr', []),
            spectre=ref_dev.get('spectre', True),
            pinConType=None,
            bulkCon=[0]
        )
        dummy_cell = dummy_mos.cell

        # 适配list结构的Pin shape提取
        def _get_m1_bbox(pin):
            x_list = []
            y_list = []
            for shape_item in pin.shape:
                layer_name = shape_item[0]
                if layer_name == 'M1':
                    ll = shape_item[1]
                    ur = shape_item[2]
                    x_list.append(ll[0])
                    x_list.append(ur[0])
                    y_list.append(ll[1])
                    y_list.append(ur[1])
            if not x_list:
                return [0, 0, 0, 0]
            return [min(x_list), min(y_list), max(x_list), max(y_list)]

        g_bbox = _get_m1_bbox(dummy_mos.gate)
        s_bbox = _get_m1_bbox(dummy_mos.source)
        d_bbox = _get_m1_bbox(dummy_mos.drain)

        # M1短接栅源漏防天线
        x1 = min(g_bbox[0], s_bbox[0], d_bbox[0])
        y1 = min(g_bbox[1], s_bbox[1], d_bbox[1])
        x2 = max(g_bbox[2], s_bbox[2], d_bbox[2])
        y2 = max(g_bbox[3], s_bbox[3], d_bbox[3])
        short_m1 = gdspy.Rectangle((x1, y1), (x2, y2), layer['M1'])
        dummy_cell.add(short_m1)

        top_lib.add(dummy_cell)

        dummy_bb = dummy_cell.get_bounding_box()
        dummy_w = dummy_bb[1][0] - dummy_bb[0][0]
        dummy_h = dummy_bb[1][1] - dummy_bb[0][1]
        unit_info[0] = {
            "cell": dummy_cell,
            "width": dummy_w,
            "height": dummy_h,
            "offset_x": dummy_bb[0][0],
            "offset_y": dummy_bb[0][1]
        }
        print(f"Dummy单元尺寸：{dummy_w:.3f} × {dummy_h:.3f} um")

    # 网格摆放：行序翻转，矩阵行与版图上下视觉一致
    step_x = ref_w + space_x
    step_y = ref_h + space_y
    total_w = cols * step_x - space_x
    total_h = rows * step_y - space_y
    start_x = -total_w / 2
    start_y = -total_h / 2

    array_cell = gdspy.Cell(array_name)
    top_lib.add(array_cell)

    for i in range(rows):
        for j in range(cols):
            group_id = cc_matrix[i][j]
            if group_id not in unit_info:
                continue
            info = unit_info[group_id]
            target_x = start_x + j * step_x
            target_y = start_y + (rows - 1 - i) * step_y
            place_x = target_x - info["offset_x"]
            place_y = target_y - info["offset_y"]
            inst = gdspy.CellReference(info["cell"], origin=(place_x, place_y))
            array_cell.add(inst)

    output_path = os.path.join(output_dir, f"{array_name}.gds")
    top_lib.write_gds(output_path)
    print(f"✅ 本组共质心阵列生成完成：{os.path.abspath(output_path)}")
    print(f"   阵列规模：{rows}行 × {cols}列")
    print(f"   单元外框尺寸：{ref_w:.3f}um × {ref_h:.3f}um")
    return output_path


if __name__ == "__main__":
    NETLIST_FILE = "ota3.sp"
    CONSTRAINT_FILE = "ota3.sym"
    TARGET_SUBCKT = "OTA2_my"
    space_x = 0.3
    space_y = 0.3
    output_root = "./cc_output"

    # 检查文件存在
    if not os.path.exists(NETLIST_FILE):
        print("[错误] 找不到网表文件，请检查路径和文件名")
        sys.exit(1)
    if not os.path.exists(CONSTRAINT_FILE):
        print("[错误] 找不到约束文件，请检查路径和文件名")
        sys.exit(1)

    # 解析网表、约束
    print("\n开始解析网表...")
    all_devices = parse_spice_netlist(NETLIST_FILE, TARGET_SUBCKT)
    print(f"[调试] 解析到器件列表：{list(all_devices.keys())}")
    if not all_devices:
        print("[错误] 网表中未找到任何器件，请检查子电路名和器件格式")
        sys.exit(1)

    print("\n开始解析约束文件...")
    match_groups = parse_match_constraint(CONSTRAINT_FILE)
    print(f"解析到全部匹配组：{match_groups}")
    if not match_groups:
        print("[错误] 约束文件中未找到匹配组，请检查文件内容")
        sys.exit(1)

    # ========== 循环遍历所有匹配组，批量生成多组共质心 ==========
    for group_idx, current_group in enumerate(match_groups):
        print(f"\n==================== 开始处理第{group_idx+1}组匹配器件：{current_group} ====================")
        # 校验器件是否存在
        missing = [d for d in current_group if d not in all_devices]
        if missing:
            print(f"警告：以下器件未在网表中找到，跳过本组：{missing}")
            continue

        group_params = []
        input_list = []
        seg_nf_list = []
        # 自适应分割逻辑
        for dev_name in current_group:
            dev_info = all_devices[dev_name].copy()
            dev_info['name'] = dev_name
            group_params.append(dev_info)
            total_nf = int(dev_info['nf'])
            # 自适应seg_nf规则
            if total_nf == 1:
                seg_nf = 1
                seg_cnt = 1
            else:
                seg_nf = 2  # nf≥2统一用偶数2分段，无单元空位
                seg_cnt = total_nf // seg_nf
            input_list.append(seg_cnt)
            seg_nf_list.append(seg_nf)
            print(f"器件{dev_name} 总nf={total_nf} → 单段seg_nf={seg_nf}，分段数量={seg_cnt}")

        # 同组器件统一seg_nf校验（匹配组必须分段规格一致）
        seg_nf_unique = list(set(seg_nf_list))
        if len(seg_nf_unique) != 1:
            print(f"错误：本组匹配器件分段规格不统一{seg_nf_list}，无法共质心排布，跳过本组")
            continue
        used_seg_nf = seg_nf_unique[0]
        print(f"本组统一使用seg_nf={used_seg_nf}，输入分段列表input_list={input_list}")

        # 生成阵列名称（器件名拼接，区分多组文件）
        array_name = "_".join(current_group) + "_cc_array"

        # 调用共质心算法
        print("\n调用共质心算法...")
        cc_result = cc_main_flow(
            input_list=input_list,
            square_array=True,
            orientation="ver",
            num_dummy_rows=0,
            row_numbers=0
        )
        print(f" 算法一维排布结果：{cc_result}")

        # 生成当前组GDS
        generate_cc_array_gds(
            match_group_params=group_params,
            cc_matrix=cc_result,
            seg_nf=used_seg_nf,
            space_x=space_x,
            space_y=space_y,
            output_dir=output_root,
            array_name=array_name
        )

    print("\n===== 全部匹配组处理完成 =====")