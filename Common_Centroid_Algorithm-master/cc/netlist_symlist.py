import re
from main import cc_main_flow

# ===================== 1. 网表解析函数 =====================
def parse_spice_netlist(netlist_path, target_subckt):
    devices = {}
    in_target_subckt = False

    subckt_start_pattern = re.compile(r'^\.*\s*subckt\s+(\w+)', re.IGNORECASE)
    subckt_end_pattern = re.compile(r'^\.*\s*ends\b', re.IGNORECASE)
    mos_pattern = re.compile(r'^\s*(M\w+)\s*\(\s*(.*?)\s*\)\s+(\w+)\s+(.*)$', re.IGNORECASE)
    param_pattern = re.compile(r'(\w+)\s*=\s*([\d.e+-]+)\w*', re.IGNORECASE)

    with open(netlist_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('*'):
                continue

            start_match = subckt_start_pattern.match(line)
            if start_match:
                subckt_name = start_match.group(1)
                if subckt_name.lower() == target_subckt.lower():
                    in_target_subckt = True
                continue

            if subckt_end_pattern.match(line):
                in_target_subckt = False
                continue

            if in_target_subckt and line.upper().startswith('M'):
                match = mos_pattern.match(line)
                if not match:
                    continue
                dev_name = match.group(1)
                model_name = match.group(3)
                param_str = match.group(4)

                params = {'model': model_name}
                for p_match in param_pattern.finditer(param_str):
                    key = p_match.group(1).lower()
                    value = float(p_match.group(2))
                    params[key] = value

                devices[dev_name] = params

    print(f"\n=== 网表解析完成，共找到 {len(devices)} 个器件 ===")
    return devices


# ===================== 2. 约束文件解析函数 =====================
def parse_match_constraint(constraint_path):
    match_groups = []
    with open(constraint_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            dev_full_names = line.split()
            dev_names = [name.split('_')[-1] for name in dev_full_names]
            match_groups.append(dev_names)
    return match_groups


# ===================== 3. 主流程 =====================
def generate_cc_layout(netlist_path, constraint_path, subckt_name, finger_per_segment=3):
    all_devices = parse_spice_netlist(netlist_path, subckt_name)
    match_groups = parse_match_constraint(constraint_path)

    for idx, group in enumerate(match_groups):
        print(f"\n===== 匹配组 {idx + 1}：{group} =====")

        missing = [d for d in group if d not in all_devices]
        if missing:
            print(f"错误：以下器件未在网表中找到：{missing}")
            return

        input_list = []
        for dev_name in group:
            nf = int(all_devices[dev_name].get('nf', 1))
            segment_num = nf // finger_per_segment
            input_list.append(segment_num)

        print(f"自动计算的 input_list：{input_list}")

        # 直接调用函数，原始返回值不做任何处理
        cc_matrix = cc_main_flow(
            input_list=input_list,
            square_array=True,
            orientation="ver",
            num_dummy_rows=0,
            row_numbers=0
        )

        # 直接打印原始输出结果
        print("共质心原始排布结果：")
        print(cc_matrix)
        print("组号映射：", {i + 1: group[i] for i in range(len(group))})


# ===================== 执行入口 =====================
if __name__ == "__main__":
    NETLIST_FILE = "ota3.sp"
    CONSTRAINT_FILE = "ota3.sym"
    TARGET_SUBCKT = "OTA2_my"
    FINGER_PER_SEG = 3

    generate_cc_layout(
        netlist_path=NETLIST_FILE,
        constraint_path=CONSTRAINT_FILE,
        subckt_name=TARGET_SUBCKT,
        finger_per_segment=FINGER_PER_SEG
    )