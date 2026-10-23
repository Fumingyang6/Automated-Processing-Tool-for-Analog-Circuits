import pyparsing as _p
import re
from . import netlist as nl


# ====================== 原始稳定CDL解析器（完全不动）======================
def parse_spice_cdl(netlist_string):
    lines = netlist_string.split('\n')
    clean_lines = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if not line:
            i += 1
            continue

        if line.startswith('*'):
            i += 1
            continue

        if line.startswith('.') and not line.startswith('.SUBCKT') and not line.startswith('.ENDS'):
            i += 1
            continue

        while i + 1 < len(lines) and lines[i + 1].strip().startswith('+'):
            line += ' ' + lines[i + 1].strip()[1:].strip()
            i += 1

        line = line.split('$')[0].strip()
        clean_lines.append(line)
        i += 1

    clean_netlist = '\n'.join(clean_lines) + '\n'

    ws = ' \t'
    _p.ParserElement.setDefaultWhitespaceChars(ws)

    EOL = _p.LineEnd().suppress()
    linebreak = _p.Suppress(_p.LineEnd() + "+")
    identifier = _p.Word(_p.alphanums + '._!<>#-+')
    net = identifier
    nets = _p.Group(_p.OneOrMore(net('net') + ~_p.FollowedBy("=") | linebreak))
    cktname = identifier
    ckttype = _p.CaselessLiteral("type:").suppress() + identifier
    cktname_end = _p.CaselessLiteral(".ends").suppress()

    comment = _p.Suppress(".PARAM" + _p.SkipTo(_p.LineEnd())) | _p.Suppress("*" + _p.SkipTo(_p.LineEnd()))
    expression = _p.Word(_p.alphanums + '._*+-/()')
    inst_param_key = identifier + _p.Suppress("=")
    inst_param_value = expression('expression')
    inst_parameter = _p.Group(inst_param_key('name') + inst_param_value('value')).setResultsName('key')
    parameters = _p.Group(_p.ZeroOrMore(inst_parameter | linebreak)).setResultsName('parameters')
    instname = identifier
    instnets = _p.Group(_p.OneOrMore(net('net') + ~_p.FollowedBy("=") | linebreak))
    instance = _p.Group(instname('name') + instnets('instnets') + parameters + EOL).setResultsName('instance')
    subcircuit_content = _p.Group(_p.ZeroOrMore(instance | EOL | comment)).setResultsName('subnetlist')

    topcircuit = _p.Group(
        _p.CaselessLiteral(".subckt").suppress() + _p.Optional(ckttype('type')) + cktname('name') + _p.Optional(
            nets('nets')) + EOL
        + subcircuit_content
        + cktname_end + EOL).setResultsName('topcircuit')

    netlist_element = topcircuit | EOL | comment('comment')
    netlist = _p.ZeroOrMore(netlist_element) + _p.StringEnd()

    parameters.setParseAction(handle_parameters)
    instance.setParseAction(handle_instance)
    topcircuit.setParseAction(handle_topcircuit)

    nl1 = netlist.parseString(clean_netlist)
    return nl1


def parse_spice_sp(netlist_string):
    """
    SPICE格式专用解析器（纯正则实现，无pyparsing依赖）
    输出格式与原pyparsing解析器完全一致，上层代码零修改
    支持：不带点的subckt/ends、括号引脚、续行符+、所有参数格式
    """
    import re
    from . import netlist as nl

    # 第一步：通用预处理（和之前一致）
    lines = netlist_string.split('\n')
    clean_lines = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if not line or line.startswith('*'):
            i += 1
            continue

        if line.startswith('.') and not line.lower().startswith(('.subckt', '.ends')):
            i += 1
            continue

        # 合并续行符+
        while i + 1 < len(lines) and lines[i + 1].strip().startswith('+'):
            line += ' ' + lines[i + 1].strip()[1:].strip()
            i += 1

        # 去除$后缀和多余空格
        line = line.split('$')[0].strip()
        # 处理括号引脚
        line = line.replace('(', ' ').replace(')', ' ')
        line = re.sub(r'\s+', ' ', line).strip()

        clean_lines.append(line)
        i += 1

    clean_netlist = '\n'.join(clean_lines) + '\n'

    # 第二步：正则提取所有子电路
    subckts = []
    # 匹配任意格式的子电路：.subckt / subckt / .SUBCKT / SUBCKT
    subckt_pattern = re.compile(
        r'^\s*\.?subckt\s+(\w+)\s+(.*?)\s*^\s*\.?ends\b',
        re.IGNORECASE | re.DOTALL | re.MULTILINE
    )

    for match in subckt_pattern.finditer(clean_netlist):
        subckt_name = match.group(1)
        subckt_body = match.group(2).strip()
        body_lines = subckt_body.split('\n')

        # ====================== 核心修复：分离端口行和器件行 ======================
        # 第一行是子电路端口，提取后从器件内容中移除
        first_line = body_lines[0].strip()
        ports = first_line.split() if first_line else []

        # 剩下的行才是真正的器件行
        device_body = '\n'.join(body_lines[1:]) if len(body_lines) > 1 else ''
        # ======================================================================

        # 提取所有器件实例（只匹配器件行）
        instances = []
        # 器件行必须满足：名字 + 至少1个引脚 + 器件类型（总元素数≥3）
        inst_pattern = re.compile(
            r'^\s*(\w+)\s+(.+?)\s+(\w+)\s*((?:\w+=\S+\s*)*)$',
            re.MULTILINE
        )

        for inst_match in inst_pattern.finditer(device_body):
            inst_name = inst_match.group(1)
            pins_str = inst_match.group(2).strip()
            dev_type = inst_match.group(3)
            params_str = inst_match.group(4).strip()

            # 解析引脚
            pins = [p.strip() for p in pins_str.split() if p.strip()]

            # 额外校验：有效器件至少有1个引脚
            if len(pins) < 1:
                continue

            # 解析参数
            params = {}
            if params_str:
                for param in params_str.split():
                    if '=' in param:
                        key, value = param.split('=', 1)
                        params[key.strip()] = value.strip()

            # 构造和原pyparsing完全一致的instance对象
            inst = nl.instance(inst_name, pins, dev_type, params)
            instances.append(inst)

        # 构造和原pyparsing完全一致的subcircuit对象
        sc = nl.subcircuit(subckt_name, ports, instances)
        sc.typeof = 'topcircuit'
        subckts.append(sc)

    return subckts


# ====================== 自动判断网表类型并调用对应解析器 ======================
def parse_spice(netlist_string):
    """
    自动识别网表格式（CDL/SP）并调用对应解析器
    输出格式完全一致，上层代码无需任何修改
    """
    # 快速判断网表类型：检查前100行是否有不带点的subckt
    lines = netlist_string.split('\n')[:100]
    is_sp_format = False

    for line in lines:
        line_stripped = line.strip().lower()
        if not line_stripped or line_stripped.startswith('*'):
            continue
        # 如果有以subckt开头且不带点的行，判定为SP格式
        if line_stripped.startswith('subckt') and not line_stripped.startswith('.subckt'):
            is_sp_format = True
            break

    if is_sp_format:
        print("检测到SPICE格式网表，使用SP专用解析器")
        return parse_spice_sp(netlist_string)
    else:
        print("检测到CDL格式网表，使用原始CDL解析器")
        return parse_spice_cdl(netlist_string)


# ====================== 公共解析动作（完全不变）======================
def handle_parameters(token):
    d = {}
    for p in token.parameters:
        d[p[0]] = p[1]
    return d


def handle_topcircuit(token):
    sc = token.topcircuit
    nets = sc.nets
    name = sc.name
    instances = sc.subnetlist
    s = nl.subcircuit(name, nets, instances)
    s.typeof = 'topcircuit'
    return [s]


def handle_instance(token):
    inst = token.instance
    name = str(inst.name)
    pins = [str(p) for p in inst.instnets[0:-1]]
    reference = str(inst.instnets[-1])
    parameters = inst.parameters
    i = nl.instance(name, pins, reference, parameters)
    return [i]