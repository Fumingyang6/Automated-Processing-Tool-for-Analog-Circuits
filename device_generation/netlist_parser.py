import re


# spectre 风格数值后缀 → 微米换算系数（u=μm, n=nm, p=pm, m=毫米）
_SPECTRE_SUFFIX_TO_UM = {"u": 1.0, "n": 1e-3, "p": 1e-6, "m": 1e3}


def _spectre_value_to_um(token):
    """把 spectre 数值（如 16.0u / 70n / 5.5）换算成微米。
    不带后缀的数按米处理，与旧格式解析保持一致。"""
    token = str(token).strip()
    m = re.match(r"^([+-]?[\d.]+(?:[eE][+-]?\d+)?)([a-zA-Z]*)$", token)
    if not m:
        raise ValueError(f"无法解析数值: {token}")
    value = float(m.group(1))
    suffix = m.group(2)
    if not suffix:
        return value * 1e6
    factor = _SPECTRE_SUFFIX_TO_UM.get(suffix[0])
    if factor is None:
        raise ValueError(f"不支持的单位后缀: {token}")
    return value * factor


def _kv_pairs(line):
    """把一行里所有的 key=value 提取成字典（spectre 参数都是这种写法）"""
    return dict(re.findall(r"(\w+)=([^\s()]+)", line))


def _mos_attr_from_model(model):
    """从 nch/pch 模型名推断 Mosfet 类认识的属性（lvt/hvt/25/ud/od/na/mac）"""
    known = ("lvt", "hvt", "25", "ud", "od", "na", "mac")
    return [kw for kw in known if kw in model]


class NetlistParser:
    """网表文件解析器"""

    @staticmethod
    def parse_netlist(netlist_path):
        """解析网表文件，提取电阻、电容、MOS管参数

        支持两种格式：
        - Cadence ADE 导出格式（x 开头的实例、rppolywo_m / nch_*_mac / cfmom_2t）
        - spectre 直出格式（M*/C*/R* 实例、pch / nch_lvt / cfmom_2t / rppolywo），
          即 examples/ 和 mycase/ 里样例网表的格式
        """
        devices = {
            "resistors": [],  # 电阻列表
            "capacitors": [],  # 电容列表
            "mosfets": []  # MOS管列表
        }

        current_subckt = ""

        # 正则表达式匹配各器件
        subckt_pattern = re.compile(r"^\.?(?:subckt|topckt)\s+(\w+)\s+.*")
        res_pattern = re.compile(
            r"^(x\w+)\s+.*\s+rppolywo_m\s+lr=([\d.e-]+)\s+wr=([\d.e-]+)\s+.*series=(\d+)\s+segspace=([\d.e-]+)"
        )
        mos_pattern = re.compile(
            r"^(x\w+)\s+.*\s+(nch|pch)_(\w+)_mac\s+l=([\d.e-]+)\s+w=([\d.e-]+)\s+.*nf=(\d+)"
        )
        cap_pattern = re.compile(
            r"^(xc\w+)\s+.*\s+cfmom_2t\s+nr=(\d+)\s+lr=([\d.e-]+)\s+w=([\d.e-]+)\s+s=([\d.e-]+)\s+stm=(\d+)\s+spm=(\d+)\s+.*ftip=([\d.e-]+)"
        )

        try:
            with open(netlist_path, 'r', encoding='utf-8', errors='ignore') as f:
                raw_lines = f.readlines()
        except FileNotFoundError:
            raise Exception(f"网表文件不存在: {netlist_path}")
        except Exception as e:
            raise Exception(f"解析网表文件出错: {str(e)}")

        try:
            # spectre 里参数过长会用反斜杠折行，先把续行拼回一行
            lines = NetlistParser._join_continuations(raw_lines)

            for line in lines:
                line = line.strip()
                if not line or line.startswith(("**", "*", "//")):
                    continue

                # 1. 更新当前子电路名
                subckt_match = subckt_pattern.match(line)
                if subckt_match:
                    current_subckt = subckt_match.group(1)
                    continue

                # 2. 解析电阻
                res_match = res_pattern.match(line)
                if res_match:
                    devices = NetlistParser._parse_resistor(res_match, current_subckt, devices)
                    continue

                # 3. 解析MOS管
                mos_match = mos_pattern.match(line)
                if mos_match:
                    devices = NetlistParser._parse_mosfet(mos_match, current_subckt, devices)
                    continue

                # 4. 解析电容
                cap_match = cap_pattern.match(line)
                if cap_match:
                    devices = NetlistParser._parse_capacitor(cap_match, current_subckt, devices)
                    continue

                # 5. 旧格式都没匹配上，再试 spectre 直出格式
                devices = NetlistParser._parse_spectre_line(line, current_subckt, devices)

        except Exception as e:
            raise Exception(f"解析网表文件出错: {str(e)}")

        return devices

    @staticmethod
    def _join_continuations(raw_lines):
        """把以反斜杠结尾的行和它的续行拼成一行"""
        joined = []
        buf = ""
        for line in raw_lines:
            stripped = line.rstrip("\n")
            if stripped.endswith("\\"):
                buf += stripped[:-1] + " "
            else:
                buf += stripped
                joined.append(buf)
                buf = ""
        if buf:
            joined.append(buf)
        return joined

    @staticmethod
    def _parse_spectre_line(line, current_subckt, devices):
        """解析 spectre 直出格式的器件行（样例网表的写法）"""
        tokens = line.split()
        if len(tokens) < 3 or "=" not in line:
            return devices

        inst_name = tokens[0]
        # nch/pch 开头的模型名（nch、pch、nch_lvt、nch_25ud18_mac 等）
        model = next((t for t in tokens[1:] if t.startswith(("nch", "pch"))), None)
        kv = _kv_pairs(line)

        # MOS 管：模型名以 nch/pch 开头，且有 l、w 参数
        if model and "l" in kv and "w" in kv:
            devices["mosfets"].append({
                "subckt": current_subckt,
                "inst_name": inst_name,
                "nch": model.startswith("nch"),
                "l": _spectre_value_to_um(kv["l"]),
                "w": _spectre_value_to_um(kv["w"]),
                "nf": int(float(kv.get("nf", 1))),
                "attr": _mos_attr_from_model(model),
                "spectre": True,
                "pinConType": None,
                "bulkCon": [0]
            })
            return devices

        # 电容：cfmom_2t（MOM 电容）
        if any(t.startswith("cfmom") for t in tokens) and all(k in kv for k in ("nr", "lr", "w", "s", "stm", "spm")):
            devices["capacitors"].append({
                "subckt": current_subckt,
                "inst_name": inst_name,
                "l": _spectre_value_to_um(kv["lr"]),
                "w": _spectre_value_to_um(kv["w"]),
                "sp": _spectre_value_to_um(kv["s"]),
                "nf": int(kv["nr"]),
                "m_bot": int(kv["stm"]),
                "m_top": int(kv["spm"]),
                "f_tip": _spectre_value_to_um(kv.get("ftip", "0.14")),
                "attr": ["2t"],
                "flatten": True
            })
            return devices

        # 电阻：rppolywo / rppolywo_m
        if any(t.startswith("rppolywo") for t in tokens) and all(k in kv for k in ("series",)) \
                and ("l" in kv or "lr" in kv) and ("w" in kv or "wr" in kv):
            devices["resistors"].append({
                "subckt": current_subckt,
                "inst_name": inst_name,
                "l": _spectre_value_to_um(kv.get("l", kv.get("lr"))),
                "w": _spectre_value_to_um(kv.get("w", kv.get("wr"))),
                "series": True,
                "seg_num": int(kv["series"]),
                "seg_space": _spectre_value_to_um(kv.get("segspace", "0.18")),
                "attr": ["wo", "m"]
            })
            return devices

        return devices

    @staticmethod
    def _parse_resistor(res_match, current_subckt, devices):
        """解析电阻行"""
        inst_name = res_match.group(1)
        lr_m = float(res_match.group(2))  # 长度（米）
        wr_m = float(res_match.group(3))  # 宽度（米）
        series = int(res_match.group(4))  # 段数
        segspace_m = float(res_match.group(5))  # 段间距（米）

        # 单位转换：米 → 微米（×1e6）
        lr_um = lr_m * 1e6
        wr_um = wr_m * 1e6
        segspace_um = segspace_m * 1e6

        devices["resistors"].append({
            "subckt": current_subckt,
            "inst_name": inst_name,
            "l": lr_um,
            "w": wr_um,
            "series": True,
            "seg_num": series,
            "seg_space": segspace_um,
            "attr": ["wo", "m"]
        })

        return devices

    @staticmethod
    def _parse_mosfet(mos_match, current_subckt, devices):
        """解析MOS管行"""
        inst_name = mos_match.group(1)
        mos_type = mos_match.group(2)  # nch/pch
        vt_type = mos_match.group(3)  # lvt/hvt
        l_m = float(mos_match.group(4))
        w_m = float(mos_match.group(5))
        nf = int(mos_match.group(6))

        # 单位转换
        l_um = l_m * 1e6
        w_um = w_m * 1e6

        # 构建属性列表
        attr = [vt_type, "mac"]
        nch = True if mos_type == "nch" else False
        bulk_con = [0]

        devices["mosfets"].append({
            "subckt": current_subckt,
            "inst_name": inst_name,
            "nch": nch,
            "l": l_um,
            "w": w_um,
            "nf": nf,
            "attr": attr,
            "spectre": True,
            "pinConType": None,
            "bulkCon": bulk_con
        })

        return devices

    @staticmethod
    def _parse_capacitor(cap_match, current_subckt, devices):
        """解析电容行"""
        inst_name = cap_match.group(1)
        nr = int(cap_match.group(2))  # 指数量
        lr_m = float(cap_match.group(3))  # 长度（米）
        w_m = float(cap_match.group(4))  # 宽度（米）
        s_m = float(cap_match.group(5))  # 间距（米）
        stm = int(cap_match.group(6))  # 底层金属
        spm = int(cap_match.group(7))  # 顶层金属
        ftip_m = float(cap_match.group(8))  # 指端长度（米）

        # 单位转换
        lr_um = lr_m * 1e6
        w_um = w_m * 1e6
        s_um = s_m * 1e6
        ftip_um = ftip_m * 1e6

        devices["capacitors"].append({
            "subckt": current_subckt,
            "inst_name": inst_name,
            "l": lr_um,
            "w": w_um,
            "sp": s_um,
            "nf": nr,
            "m_bot": stm,
            "m_top": spm,
            "f_tip": ftip_um,
            "attr": ["2t"],
            "flatten": True
        })

        return devices