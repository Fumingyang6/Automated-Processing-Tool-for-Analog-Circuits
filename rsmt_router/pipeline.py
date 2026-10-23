"""自动布线流水线：把 RSMT → 间距合法化 → GDS 生成三个阶段串起来。

算法部分全部复用 routing_ui.py 里已有的模块级纯函数，这里只负责编排：
输出目录、阶段衔接、进度回调。整个模块不碰任何 Qt 对象，
所以可以直接丢进后台线程跑。

每个阶段写进自己的子目录，互不覆盖，也不再往 rsmt_router 根目录丢产物：

    <out_dir>/step1_rsmt/steiner_forest_result.txt
    <out_dir>/step2_legalize/leg_cp_op2_3_result.txt
    <out_dir>/step3_gds/leg_cp_op2_routing.txt
                        CP_OP2_placement+routing.txt
                        leg_cp_op2_routing.gds
                        CP_OP2_placement+routing.gds
"""

import ast
import os

try:
    from . import routing_ui as R          # 作为 rsmt_router.pipeline 被导入时
except ImportError:                        # rsmt_router 目录本身在 sys.path 上时
    import routing_ui as R


# 三个阶段各自的输出子目录名
STAGE_DIRS = {
    "step1": "step1_rsmt",
    "step2": "step2_legalize",
    "step3": "step3_gds",
}

# 每个阶段的产物文件名（供界面在文件树里定位）
STAGE_FILES = {
    "step1": ("steiner_forest_result.txt",),
    "step2": ("leg_cp_op2_3_result.txt",),
    "step3": (
        "leg_cp_op2_routing.txt",
        "CP_OP2_placement+routing.txt",
        "leg_cp_op2_routing.gds",
        "CP_OP2_placement+routing.gds",
    ),
}

# 间距合法化的判定阈值，和原实现保持一致
SPACING_THRESHOLD = 560

# 走线宽度（GDS 单位），和原实现保持一致
TRACE_WIDTH = 220

# 写进 GDS 文本的固定文件头
GDS_HEADER = """HEADER: 600
BGNLIB: 110, 8, 17, 14, 22, 22, 110, 8, 17, 14, 36, 21
LIBNAME: "TEST.DB"
UNITS: 0.001, 1e-09
BGNSTR: 70, 1, 1, 1, 0, 0, 110, 8, 17, 14, 35, 55
STRNAME: "test_struc1"
"""

GDS_END = """ENDSTR
ENDLIB"""


def stage_dir(out_dir, stage):
    """返回某个阶段的输出目录，并确保它存在"""
    path = os.path.join(out_dir, STAGE_DIRS[stage])
    os.makedirs(path, exist_ok=True)
    return path


# ==================== 结果文件的读写 ====================

def read_result_file(path):
    """读取形如 `cp_op2_3 = [[...]]` 的结果文件，返回等号右边的列表。

    老的实现是把整个文件 exec 掉——等于对选中的文件执行任意代码，
    而且强依赖变量名恰好叫 cp_op2_3 / leg_cp_op2_3。
    这里按第一个等号切开、右边用 ast.literal_eval 解析，安全且不挑名字。
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if "=" not in content:
        raise ValueError(f"结果文件格式不对（找不到 '='）：{os.path.basename(path)}")
    _, _, literal = content.partition("=")
    try:
        return ast.literal_eval(literal.strip())
    except (SyntaxError, ValueError) as exc:
        raise ValueError(
            f"结果文件内容无法解析：{os.path.basename(path)}（{exc}）"
        ) from exc


def write_result_file(path, var_name, value):
    """按老格式写出 `var_name = 字面量`，保证旧的 storey 脚本仍能读"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{var_name} = {value}")
    return path


# ==================== 阶段1：RSMT 斯坦纳森林 ====================

def run_rsmt(nets_path, out_dir, log=None):
    """读网表，为每条线网算 RSMT，合成斯坦纳森林并落盘。"""
    log = log or (lambda msg: None)

    if not os.path.exists(nets_path):
        raise FileNotFoundError(f"网表文件不存在：{nets_path}")

    log(f"读取网表：{os.path.basename(nets_path)}")
    nets = R.read_file_point(nets_path)
    log(f"共 {len(nets)} 条线网")

    steiner_trees = []
    all_paths = []
    all_pins = []
    all_steiner_points = []
    total_length = 0

    for idx, original_points in enumerate(nets, 1):
        rsmt, steiner_points = R.computeRSMT(original_points)

        # 每条斜边拆成「先横后竖」两段直角走线
        path = []
        net_length = 0
        for line_obj in rsmt:
            net_length += line_obj.w
            p1 = line_obj.points[0].get()
            p2 = line_obj.points[1].get()
            path.append(((p1.x, p1.y), (p1.x, p2.y)))
            path.append(((p1.x, p2.y), (p2.x, p2.y)))

        clean_path = R.remove_duplicate_elements(path)
        steiner_trees.append(clean_path)
        all_paths.extend(clean_path)
        all_pins.extend((pt.x, pt.y) for pt in original_points)
        all_steiner_points.extend((pt.x, pt.y) for pt in steiner_points)
        total_length += net_length

        log(f"  线网 {idx}/{len(nets)}：{len(clean_path)} 段，长度 {net_length:.1f}")

    via_points = R.via_coordinates(steiner_trees)

    result_path = write_result_file(
        os.path.join(stage_dir(out_dir, "step1"), "steiner_forest_result.txt"),
        "cp_op2_3", steiner_trees,
    )

    log(f"阶段1完成：总线长 {total_length:.1f}，通孔 {len(via_points)} 个")
    return {
        "steiner_trees": steiner_trees,
        "paths": all_paths,
        "pins": all_pins,
        "steiner_points": all_steiner_points,
        "via_points": via_points,
        "total_length": total_length,
        "result_path": result_path,
    }


# ==================== 阶段2：走线间距合法化 ====================

def legalize(step1_file, nets_path, out_dir, log=None, threshold=SPACING_THRESHOLD):
    """对斯坦纳森林做间距检测，用 U 形绕线替换掉过近的平行线段。"""
    log = log or (lambda msg: None)

    if not os.path.exists(step1_file):
        raise FileNotFoundError(f"阶段1结果不存在：{step1_file}")

    steiner_trees = read_result_file(step1_file)
    original_length = R.total_segment_length(steiner_trees)

    rounds = 0
    for rounds in range(1, 1001):
        need_adjust = R.trees_spacing_detect(steiner_trees, threshold)
        if not need_adjust:
            log(f"  第 {rounds} 轮：间距已全部合规，停止")
            break

        adjusted_1, adjusted_2 = R.adjust_segments(need_adjust[0][0:2], threshold)
        backup = steiner_trees.copy()

        # revised_steiner_trees 是「原地修改」传入的列表，两个方案共用这个语义，
        # 所以先试方案1，不满意再从 backup 重来选方案2
        plan_1 = R.revised_steiner_trees(steiner_trees, need_adjust, adjusted_1)
        if len(R.trees_spacing_detect(plan_1)) < len(need_adjust):
            chosen = "方案1"
        else:
            chosen = "方案2"
            steiner_trees = R.revised_steiner_trees(backup, need_adjust, adjusted_2)

        if rounds == 1 or rounds % 50 == 0:
            log(f"  第 {rounds} 轮：待调整 {len(need_adjust)} 组，选择{chosen}")
    else:
        log("  已达到 1000 轮上限，按当前结果继续")

    added_length = R.total_segment_length(steiner_trees) - original_length
    log(f"合法化新增总线长：{added_length:.2f}")

    nets = R.read_file_tuple(nets_path)
    pins, steiner_points = R.distinguishing_point(nets, steiner_trees)
    log(f"引脚 {len(pins)} 个，斯坦纳点 {len(steiner_points)} 个")

    result_path = write_result_file(
        os.path.join(stage_dir(out_dir, "step2"), "leg_cp_op2_3_result.txt"),
        "leg_cp_op2_3", steiner_trees,
    )

    log("阶段2完成")
    return {
        "steiner_trees": steiner_trees,
        "pins": pins,
        "steiner_points": steiner_points,
        "added_length": added_length,
        "rounds": rounds,
        "result_path": result_path,
    }


# ==================== 阶段3：GDS 版图生成 ====================

def generate_gds(source_file, nets_path, layout_txt, out_dir, log=None):
    """把走线树写进 GDS 文本，和原始版图合并后再转成二进制 GDS。

    source_file 传阶段2的合法化结果——这正是修正后的行为。原实现读入了
    阶段2的结果却从没用它，实际走的是阶段1的原始树（见老版 routing_ui.py）。
    想复现旧行为的话传阶段1的结果文件进来即可。
    """
    log = log or (lambda msg: None)

    for path, name in ((source_file, "走线结果"), (nets_path, "网表"), (layout_txt, "布局")):
        if not os.path.exists(path):
            raise FileNotFoundError(f"{name}文件不存在：{path}")

    input_steiners = read_result_file(source_file)

    net_lists = R.read_file_tuple(nets_path)
    _, via_points = R.distinguishing_point(net_lists, input_steiners)

    segments = []
    for group in input_steiners:
        segments.extend(group)
    log(f"待写入 GDS 的走线段：{len(segments)} 段，通孔 {len(via_points)} 个")

    out = stage_dir(out_dir, "step3")

    # ---- 1) 生成只有走线的 GDS 文本 ----
    routing_txt = os.path.join(out, "leg_cp_op2_routing.txt")
    with open(routing_txt, "w", encoding="utf-8") as f:
        f.write(GDS_HEADER)
        for (x1, y1), (x2, y2) in segments:
            # 竖线走 62 层、横线走 63 层，和原实现一致
            layer = 62 if x1 == x2 else 63
            f.write(f"PATH\nLAYER: {layer}\nDATATYPE: 0\nPATHTYPE: 0\n"
                    f"WIDTH: {TRACE_WIDTH}\nXY: {x1}, {y1}, {x2}, {y2}\nENDEL\n")
        for point in via_points:
            f.write(_via_boundaries(point))
        f.write(GDS_END)
    log(f"生成走线 GDS 文本：{os.path.basename(routing_txt)}")

    # ---- 2) 把走线结构合并进原始版图 ----
    merged_txt = os.path.join(out, "CP_OP2_placement+routing.txt")
    merged_lines = _merge_into_layout(routing_txt, layout_txt)
    with open(merged_txt, "w", encoding="utf-8") as f:
        f.writelines(merged_lines)
    log(f"生成合并版图文本：{os.path.basename(merged_txt)}")

    # ---- 3) 两份文本各转一份二进制 GDS ----
    for src, dst in ((routing_txt, "leg_cp_op2_routing.gds"),
                     (merged_txt, "CP_OP2_placement+routing.gds")):
        dst_path = os.path.join(out, dst)
        with open(dst_path, "wb") as ofile, open(src, "r", encoding="utf-8") as ifile:
            try:
                R.parse_file(ifile, ofile)
            except SystemExit:
                # parse_file 遇到格式不对会直接 sys.exit(1)，那会连线程一起带走，
                # 转成普通异常交给上层记日志
                raise RuntimeError(
                    f"GDS 文本解析失败：{os.path.basename(src)}，"
                    "通常是原始版图文件格式不符合预期"
                ) from None
        log(f"生成二进制 GDS：{dst}")

    log("阶段3完成")
    return {
        "segments": len(segments),
        "via_points": via_points,
        "files": [os.path.join(out, n) for n in STAGE_FILES["step3"]],
        "result_path": os.path.join(out, "CP_OP2_placement+routing.gds"),
    }


def _via_boundaries(point):
    """通孔位置要盖 4 个方框（62/63 层各一个大框，70 层两个小框）"""
    x, y = point[0], point[1]
    big = R.calculate_rectangle_coordinates(x, y, 760, 240)
    left = R.calculate_rectangle_coordinates(x - 220, y, 220, 220)
    right = R.calculate_rectangle_coordinates(x + 220, y, 220, 220)

    def boundary(layer, coords):
        xy = ", ".join(str(v) for v in coords)
        return f"BOUNDARY\nLAYER: {layer}\nDATATYPE: 0\nXY: {xy}\nENDEL\n"

    return boundary(62, big) + boundary(63, big) + boundary(70, left) + boundary(70, right)


def _merge_into_layout(routing_txt, layout_txt):
    """把走线 GDS 文本里 test_struc1 的内容，插进原始版图最后一个空结构里"""
    extracted = []
    inside = False
    with open(routing_txt, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith('STRNAME: "test_struc1"'):
                inside = True
                continue
            if line.strip() == "ENDSTR":
                break
            if inside:
                extracted.append(line)

    with open(layout_txt, "r", encoding="utf-8") as f:
        lines = f.readlines()

    def starts(line, tag):
        return line.strip().startswith(tag)

    # 找出所有「BGNSTR 之后只跟了一个 STRNAME 就 ENDSTR」的空结构，取最后一个
    valid_blocks = []
    block_start = None
    strname_idx = None
    for idx, line in enumerate(lines):
        if starts(line, "BGNSTR"):
            block_start = idx
            strname_idx = None
        elif block_start is not None and starts(line, "STRNAME"):
            strname_idx = idx
        elif block_start is not None and starts(line, "ENDSTR"):
            is_empty = all(
                lines[i].strip() == "" or starts(lines[i], "STRNAME")
                for i in range(block_start + 1, idx)
            )
            if is_empty and strname_idx is not None:
                valid_blocks.append((block_start, strname_idx, idx))
            block_start = None

    if not valid_blocks:
        raise RuntimeError(
            f"原始版图里找不到可写入的空结构：{os.path.basename(layout_txt)}"
        )

    insert_at = valid_blocks[-1][1] + 1
    lines[insert_at:insert_at] = extracted
    return lines


# ==================== 一键跑完整条链 ====================

def run_all(nets_path, layout_txt, out_dir, on_stage=None, log=None,
            use_legalized=True, reuse_step1=None, reuse_step2=None):
    """串行跑完三个阶段，阶段之间自动衔接。

    每完成一个阶段就回调 on_stage(阶段名, 结果字典)。绘图数据通过这个回调
    交给界面——matplotlib 画布只能在 GUI 线程动，所以这里只负责把数据递出去。

    use_legalized 只留给回归对比用（False 时阶段3改回用阶段1的原始树，
    复现修正前的输出）。界面上不暴露这个开关——正确行为就是走阶段2的合法化结果。

    reuse_step1 / reuse_step2 传入现成的结果文件路径就跳过对应阶段。
    跳过的阶段没有绘图数据，回调里会带 reused=True。
    """
    log = log or (lambda msg: None)
    on_stage = on_stage or (lambda stage, payload: None)

    if reuse_step1:
        log(f"======= 阶段1/3：复用已有结果 {os.path.basename(reuse_step1)} =======")
        step1 = {"result_path": reuse_step1, "reused": True}
    else:
        log("======= 阶段1/3：RSMT 斯坦纳树计算 =======")
        step1 = run_rsmt(nets_path, out_dir, log)
    on_stage("step1", step1)

    if reuse_step2:
        log(f"======= 阶段2/3：复用已有结果 {os.path.basename(reuse_step2)} =======")
        step2 = {"result_path": reuse_step2, "reused": True}
    else:
        log("======= 阶段2/3：走线间距合法化 =======")
        step2 = legalize(step1["result_path"], nets_path, out_dir, log)
    on_stage("step2", step2)

    log("======= 阶段3/3：GDS 版图生成 =======")
    if use_legalized:
        source = step2["result_path"]
    else:
        log("（走线几何取自阶段1原始树，复现修正前的行为）")
        source = step1["result_path"]
    step3 = generate_gds(source, nets_path, layout_txt, out_dir, log)
    on_stage("step3", step3)

    log("======= 三个阶段全部完成 =======")
    return {"step1": step1, "step2": step2, "step3": step3}
