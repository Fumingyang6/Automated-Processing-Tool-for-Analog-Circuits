import os

clk_set = ["clk", "clksb", "clks_boost", "clkb", "clkbo"]
vss_set = ["gnd", "vss", "GNDA", "GND", "vrefnd", "avss", "dvss", "vss_d"]
vdd_set = ["vdd", "vdd_and", "vdd_c", "vdd_comp", "vdd_gm", "VDD", "VDDA", "veld", "avdd", "vrefp", "vrefnp", "avdd_sar", "vdd_ac", "dvdd", "vdd_int", "vddac", "vdd_d"]

# 根据工艺和网表确定网表中的器件类型（包括两种工艺的器件类型）
# nmos_set = ["n33e2r", "n50e2r", "n18", "n50", "n15ll"]
# pmos_set = ["p33e2r", "p50e2r", "p18", "p50", "p15ll"]
# nmos_set = ["n33e2r", "n50e2r", "n18", "n15ll", "nch_lvt_mac"]
# pmos_set = ["p33e2r", "p50e2r", "p18", "p15ll", "pch_lvt_mac"]
# capacitor_set = ["mim1_ckt", "mim2_ckt", "cfmom_2t"]
# # 180nm数据的主要器件类型
nmos_set = []
pmos_set = []
capacitor_set = []
resistor_set = []
#nmos_set = ["n18_ckt", "n50_ckt"]
#pmos_set = ["p18_ckt", "p50_ckt"]
#capacitor_set = ["mim2_ckt"]
#resistor_set = ["rpposab_ckt", "rpposab_ckt_p"]
# 130nm工艺主要器件类型
#nmos_set = ["n33e2r", "n50e2r"]
#pmos_set = ["p33e2r", "p50e2r"]
#capacitor_set = ["mim1_ckt"]
# # TSMC 40nm工艺主要器件类型
# nmos_set = ["nch_lvt_mac"]
# pmos_set = ["pch_lvt_mac"]
# capacitor_set = ["cfmom_2t"]

#resistor_set = ["rpposab_ckt"]

three_term_set = ['mim1_ckt', 'mim2_ckt']

class CktObj:
    def __init__(self, name):
        self.name = name # str

class Net(CktObj):
    def __init__(self, name, isPower):
        CktObj.__init__(self, name)
        self.type = 'signal'
        if name in vss_set:
            self.type = 'vss'
        elif name in vdd_set:
            self.type= 'vdd'
        elif name in clk_set:
            self.type = 'clk'
        self.pins = {}
        self.isPower = isPower
    def add_pin(self, pin):
        self.pins[pin.name] = pin

class Pin(CktObj):
    def __init__(self, name, device, type):
        CktObj.__init__(self, name)
        self.device = device
        self.net = None
        self.type = type
        self.connected = False
        self.connectedPins = {}

class Device(CktObj):
    def __init__(self, name, type, param, level):
        CktObj.__init__(self, name)
        self.type = type
        self.isDev = True
        self.param = param
        self.level = level
        self.pins = []
        self.idx = -1 # idx in Ckt.devices
        self.in_deg = 0
        self.feat = None # trained feature
        self.parentCkt = None
        self.name_suffix = name.split('/')[-1]
    def __str__(self):
        return self.name + ' ' + self.type
    def add_pin(self, pin):
        self.pins.append(pin)
    def isNmos(self):
        return self.type in nmos_set
    def isPmos(self):
        return self.type in pmos_set
    def isMos(self):
        return self.isNmos() or self.isPmos()
    def isCap(self):
        return self.type in capacitor_set
    def isRes(self):
        return self.type in resistor_set
    def isPassive(self):
        return self.type in capacitor_set or self.type in resistor_set

class Ckt(object):
    def __init__(self, name, level):
        self.name = name
        self.name_suffix = name
        self.type = 'TOP'
        self.level = level
        self.nets = {}
        self.devices = []
        self.allDevices = [] # all lowest level transistors
        self.allDeviceName2Id = {}
        self.max_level = 0
        self.devices_level = []
        self.avg_indeg = 0
        self.avg_size = 0
        self.max_size = 0

    def add_net(self, net):
        self.nets[net.name] = net
    def add_device(self, device):
        if device.name not in self.allDeviceName2Id.keys():
            device.idx = len(self.allDevices)
            self.allDeviceName2Id[device.name] = len(self.allDevices)
            self.allDevices.append(device)
            if device.level >= self.max_level:
                self.max_level = device.level
                while len(self.devices_level) <= self.max_level + 1:
                    self.devices_level.append([])
            self.devices_level[device.level].append(device)

    def get_device_by_name(self, name):
        return self.allDevices[self.allDeviceName2Id[name]]
    def hasPowerNet(self):
        for net in self.nets:
            if net.type in ['vss', 'vdd']:
                return True
        return False
    def hasSignalNet(self):
        for net in self.nets:
            if net.type in ['signal', 'clk']:
                return True
        return False
