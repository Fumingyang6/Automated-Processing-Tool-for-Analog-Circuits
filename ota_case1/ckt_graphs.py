#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Here you define the graph for a circuit
构建图结构
"""

import torch
import numpy as np

class GraphOTA:
    """

         My OTA circuit is:

    node 0 will be M0
    node 1 will be M1
    node 2 will be M2
    node 3 will be M3
    node 4 will be M4
    node 5 will be M5
    node 6 will be M6
    node 7 will be vb
    node 8 will be Vdd
    node 9 will be GND
    node 10 will be C1

    """

    def __init__(self, node_type="device"):
        self.device = torch.device(
            "cuda:0" if torch.cuda.is_available() else "cpu"
        )

        self.ckt_hierarchy = (('M0', 'X1.XM0', 'pfet_g5v0d10v5', 'm'),
                              ('M1', 'X1.XM1', 'pfet_g5v0d10v5', 'm'),
                              ('M2', 'X1.XM2', 'pfet_g5v0d10v5', 'm'),
                              ('M3', 'X1.XM3', 'nfet_g5v0d10v5', 'm'),
                              ('M4', 'X1.XM4', 'nfet_g5v0d10v5', 'm'),
                              ('M5', 'X1.XM5', 'pfet_g5v0d10v5', 'm'),
                              ('M6', 'X1.XM6', 'nfet_g5v0d10v5', 'm'),
                              ('Vb', '', 'Vb', 'v'),

                              ('C1', 'X1.XC1', 'cap_mim_m3_1', 'c')
                              )

        self.op = {'M0': {},
                   'M1': {},
                   'M2': {},
                   'M3': {},
                   'M4': {},
                   'M5': {},
                   'M6': {},
                   'Vb': {},
                   'C1': {}
                   }

        if node_type == "device":
            # --------------------------
            # device级节点 (11个节点)
            # --------------------------
            self.edge_index = torch.tensor([
                [0, 1], [1, 0], [0, 2], [2, 0], [0, 5], [5, 0], [0, 7], [7, 0], [0, 8], [8, 0],
                [1, 2], [2, 1], [1, 3], [3, 1], [1, 4], [4, 1], [1, 5], [5, 1], [1, 8], [8, 1],
                [2, 4], [4, 2], [2, 5], [5, 2], [2, 6], [6, 2], [2, 8], [8, 2], [2, 10], [10, 2],
                [3, 4], [4, 3], [3, 6], [6, 3], [3, 9], [9, 3],
                [4, 6], [6, 4], [4, 9], [9, 4], [4, 10], [10, 4],
                [5, 6], [6, 5], [5, 7], [7, 5], [5, 8], [8, 5], [5, 10], [10, 5],
                [6, 9], [9, 6], [6, 10], [10, 6]
            ], dtype=torch.long).t().to(self.device)

            self.edge_type = torch.tensor([
                0, 0, 0, 0, 1, 1, 1, 1, 1, 1,
                0, 0, 0, 0, 0, 0, 1, 1, 1, 1,
                0, 0, 1, 1, 0, 0, 1, 1, 0, 0,
                0, 0, 0, 0, 1, 1,
                0, 0, 1, 1, 0, 0,
                1, 1, 1, 1, 1, 1, 0, 0,
                1, 1, 0, 0,
            ]).to(self.device)

            self.num_nodes = 11

        elif node_type == "pin":
            # --------------------------
            # pin级节点 (32个节点)
            # 原生定义，和训练时完全一致
            # --------------------------
            self.edge_index = torch.tensor([
                [0, 6], [6, 0], [0, 10], [10, 0],  # net1
                [1, 21], [21, 1], [1, 28], [28, 1],  # vb
                [2, 3], [3, 2], [2, 7], [7, 2], [2, 11], [11, 2], [2, 22], [22, 2], [2, 23], [23, 2], [2, 29], [29, 2],
                # vdd
                [4, 12], [12, 4], [4, 13], [13, 4], [4, 17], [17, 4],  # net2
                [8, 16], [16, 8], [8, 25], [25, 8], [8, 31], [31, 8],  # net3
                [14, 15], [15, 14], [14, 18], [18, 14], [14, 19], [19, 14], [14, 26], [26, 14], [14, 27], [27, 14],
                [14, 30], [30, 14],  # gnd
                [20, 24], [24, 20], [20, 31], [31, 20]  # out
            ], dtype=torch.long).t().to(self.device)

            self.edge_type = torch.tensor([
                0, 0, 0, 0,
                1, 1, 1, 1,
                1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                0, 0, 0, 0, 0, 0,
                0, 0, 0, 0, 0, 0,
                1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                1, 1, 0, 0,
            ]).to(self.device)

            self.num_nodes = 32

        else:
            raise ValueError(f"不支持的节点类型: {node_type}，仅支持device和pin")

        self.num_relations = 2
        self.num_node_features = 13
        self.obs_shape = (self.num_nodes, self.num_node_features)


        """Select an action from the input state."""
        self.L_C1 = 30  # each unit cap is 30um by 30um
        self.W_C1 = 30
        M_C1_low = 10
        M_C1_high = 300  # copies of unit cap
        self.C1_low = M_C1_low * (self.L_C1 * self.W_C1 * 2e-15 + (self.L_C1 + self.W_C1) * 0.38e-15)
        self.C1_high = M_C1_high * (self.L_C1 * self.W_C1 * 2e-15 + (self.L_C1 + self.W_C1) * 0.38e-15)

        # 接下来action_space的定义确定了需要调整参数的个数
        self.action_space_low = np.array([1, 0.5, 1,
                                          1, 0.5, 1,
                                          1, 0.5, 1,
                                          1, 0.5, 1,
                                          1.2,  # vb
                                          ])

        self.action_space_high = np.array([100, 1.5, 10,
                                           100, 1.5, 10,
                                           100, 1.5, 10,
                                           100, 1.5, 10,
                                           1.8,
                                           ])

        self.action_dim = len(self.action_space_low)
        self.action_shape = (self.action_dim,)

        """Some target specifications for the final design"""
        self.Vdrop_target = 0.22  # drop-out voltage
        self.Vreg = 1.8  # regulated output
        self.GND = 0
        self.Vdd = 2

        self.Vload_reg_delta_target = self.Vreg * 0.02  # load regulartion variation is at most 2% of Vreg when it is switched from ILmin to ILmax

        self.GAIN_target = 60
        self.cmrr_target = 80
        self.pm_target = 60
        # self.psrr_target = 60
        self.bandwidth_target = 1e6  # 1mhz

        self.gain_threshold = 10
        self.cmrr_threshold = 20
        self.pm_threshold = 40
        self.bandwidth_threshold = 2e5  # 200khz

        """If you want to apply the reward engineering"""
        self.rew_eng = True

class GraphOTA2:
    """

         My OTA2 circuit is:

    node 0 will be M0
    node 1 will be M1
    node 2 will be M2
    node 3 will be M3
    node 4 will be M4
    node 5 will be M5
    node 6 will be M6
    node 7 will be M7
    node 8 will be M8
    node 9 will be M9
    node 10 will be M10
    node 11 will be M11
    node 12 will be M12
    node 13 will be M13
    node 14 will be VDDA
    node 15 will be GND
    node 16 will be C1

    """

    def __init__(self):
        self.device = torch.device(
            "cuda:0" if torch.cuda.is_available() else "cpu"
        )

        # we do not include R here since, it is not straght forward to get the resistance from resistor
        # in SKY130 PDK
        self.ckt_hierarchy = (('M0', 'X1.XM0', 'pfet_g5v0d10v5', 'm'),
                              ('M1', 'X1.XM1', 'pfet_g5v0d10v5', 'm'),
                              ('M2', 'X1.XM2', 'pfet_g5v0d10v5', 'm'),
                              ('M3', 'X1.XM3', 'nfet_g5v0d10v5', 'm'),
                              ('M4', 'X1.XM4', 'pfet_g5v0d10v5', 'm'),
                              ('M5', 'X1.XM5', 'pfet_g5v0d10v5', 'm'),
                              ('M6', 'X1.XM6', 'pfet_g5v0d10v5', 'm'),
                              ('M7', 'X1.XM7', 'nfet_g5v0d10v5', 'm'),
                              ('M8', 'X1.XM8', 'nfet_g5v0d10v5', 'm'),
                              ('M9', 'X1.XM9', 'nfet_g5v0d10v5', 'm'),
                              ('M10', 'X1.XM10', 'nfet_g5v0d10v5', 'm'),
                              ('M11', 'X1.XM11', 'nfet_g5v0d10v5', 'm'),
                              ('M12', 'X1.XM12', 'nfet_g5v0d10v5', 'm'),
                              ('M13', 'X1.XM13', 'nfet_g5v0d10v5', 'm'),
                              ('VBIAS2', '', 'VBIAS2', 'v'),
                              ('VBIAS3', '', 'VBIAS3', 'v'),

                              ('C1', 'X1.XC1', 'cap_mim_m3_1', 'c')
                              )

        self.op = {'M0': {},
                   'M1': {},
                   'M2': {},
                   'M3': {},
                   'M4': {},
                   'M5': {},
                   'M6': {},
                   'M7': {},
                   'M8': {},
                   'M9': {},
                   'M10': {},
                   'M11': {},
                   'M12': {},
                   'M13': {},
                   'VBIAS2': {},
                   'VBIAS3': {},
                   'C1': {}
                   }

        # # 0-M0 1-M1 2-M2 3-M3 4-M4 5-M5 6-M6 7-M7 8-M8 9-M9 10-M10 11-M11 12-M12 13-M13 14-VDDA 15-GND 16-C1 14/15可忽略 17-VBIAS2 18-VBIAS3
        self.edge_index = torch.tensor([
            [0, 16], [16, 0], [0, 5], [5, 0], [0, 8], [8, 0], [0, 6], [6, 0],
            [0, 10], [10, 0], [0, 1], [1, 0], [0, 4], [4, 0], [0, 2], [2, 0], [0, 14], [14, 0],
            [1, 6], [6, 1], [1, 10], [10, 1], [1, 2], [2, 1], [1, 3], [3, 1],
            [1, 4], [4, 1], [1, 5], [5, 1], [1, 14], [14, 1],
            [2, 3], [3, 2], [2, 4], [4, 2], [2, 5], [5, 2], [2, 6], [6, 2], [2, 14], [14, 2],
            [3, 7], [7, 3], [3, 8], [8, 3], [3, 9], [9, 3], [3, 10], [10, 3],
            [3, 11], [11, 3], [3, 12], [12, 3], [3, 13], [13, 3], [3, 15], [15, 3],
            [4, 5], [5, 4], [4, 6], [6, 4], [4, 14], [14, 4],
            [5, 8], [8, 5], [5, 6], [6, 5], [5, 14], [14, 5],
            [6, 10], [10, 6], [6, 14], [14, 6], [6, 16], [16, 6],
            [7, 10], [10, 7], [7, 8], [8, 7], [7, 9], [9, 7], [7, 11], [11, 7],
            [7, 12], [12, 7], [7, 13], [13, 7], [7, 15], [15, 7], [7, 17], [17, 7],
            [8, 9], [9, 8], [8, 12], [12, 8], [8, 10], [10, 8], [8, 11], [11, 8],
            [8, 13], [13, 8], [8, 15], [15, 8], [8, 17], [17, 8],
            [9, 13], [13, 9], [9, 10], [10, 9], [9, 11], [11, 9], [9, 12], [12, 9],
            [9, 15], [15, 9], [9, 16], [16, 9], [9, 17], [17, 9],
            [10, 11], [11, 10], [10, 12], [12, 10], [10, 13], [13, 10], [10, 15], [15, 10],
            [11, 12], [12, 11], [11, 13], [13, 11], [11, 15], [15, 11], [11, 18], [18, 11],
            [12, 13], [13, 12], [12, 15], [15, 12], [12, 18], [18, 12],
            [13, 18], [18, 13]
        ], dtype=torch.long).t().to(self.device) # 匹配第一种图表示 1113已修改

        """

        修改图表示方式，以器件为节点 -> 以pin为节点，这样会极大的增加节点的数量，但对最终性能是否有优化还需试验
        0-M0_d 1-M0_g 2-M0_s 3-M0_b 
        4-M1_d 5-M1_g(vinn) 6-M1_s 7-M1_b 
        8-M2_d 9-M2_g(vinp) 10-M2_s 11-M2_b 
        12-M3_d 13-M3_g 14-M3_s 15-M3_b
        16-M4_d 17-M4_g 18-M4_s 19-M4_b 
        20-M5_d 21-M5_g 22-M5_s 23-M5_b
        24-M6_d 25-M6_g 26-M6_s 27-M6_b
        28-vb 29-vdd 30-gnd 31-c1

        """

        # self.edge_index = torch.tensor([
        #     [0, 6], [6, 0], [0, 10], [10, 0],  # net1
        #     [1, 21], [21, 1], [1, 28], [28, 1],  # vb
        #     [2, 3], [3, 2], [2, 7], [7, 2], [2, 11], [11, 2], [2, 22], [22, 2], [2, 23], [23, 2], [2, 29], [29, 2],
        #     # vdd
        #     [4, 12], [12, 4], [4, 13], [13, 4], [4, 17], [17, 4],  # net2
        #     [8, 16], [16, 8], [8, 25], [25, 8], [8, 31], [31, 8],  # net3
        #     [14, 15], [15, 14], [14, 18], [18, 14], [14, 19], [19, 14], [14, 26], [26, 14], [14, 27], [27, 14],
        #     [14, 30], [30, 14],  # gnd
        #     [20, 24], [24, 20], [20, 31], [31, 20]  # out
        # ], dtype=torch.long).t().to(self.device) # 匹配第二种图表示

        # sorted based on if it is the small signal path
        # small signal path: 0; biasing path: 1 1是直流，0是交流
        self.edge_type = torch.tensor([  # 1114已修改 匹配第一种图表示
            1, 1, 1, 1, 1, 1, 1, 1,
            1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
            1, 1, 1, 1, 0, 0, 0, 0,
            1, 1, 1, 1, 1, 1,
            0, 0, 1, 1, 1, 1, 1, 1, 1, 1,
            1, 1, 1, 1, 1, 1, 1, 1,
            1, 1, 1, 1, 1, 1, 1, 1,
            1, 1, 1, 1, 1, 1,
            1, 1, 1, 1, 1, 1,
            1, 1, 1, 1, 0, 0,
            1, 1, 1, 1, 1, 1, 0, 0,
            1, 1, 1, 1, 1, 1, 1, 1,
            1, 1, 1, 1, 1, 1, 1, 1,
            1, 1, 1, 1, 1, 1,
            0, 0, 1, 1, 1, 1, 1, 1,
            1, 1, 0, 0, 1, 1,
            1, 1, 1, 1, 1, 1, 1, 1,
            1, 1, 1, 1, 1, 1, 1, 1,
            1, 1, 1, 1, 1, 1,
            1, 1,
        ]).to(self.device)

        # self.edge_type = torch.tensor([  # 1010已修改,用以匹配以pin为节点的图结构 匹配第二种图表示
        #     0, 0, 0, 0,
        #     1, 1, 1, 1,
        #     1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        #     0, 0, 0, 0, 0, 0,
        #     0, 0, 0, 0, 0, 0,
        #     1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        #     1, 1, 0, 0,
        # ]).to(self.device)

        self.num_relations = 2
        # self.num_relations = 1
        self.num_nodes = 19 # 匹配第一种图表示
        # self.num_nodes = 32 # 匹配第二种图表示
        self.num_node_features = 13  # 0902未修改，0909无需修改
        self.obs_shape = (self.num_nodes, self.num_node_features)

        """Select an action from the input state."""
        self.L_C1 = 30  # each unit cap is 30um by 30um
        self.W_C1 = 30
        M_C1_low = 10
        M_C1_high = 300  # copies of unit cap
        self.C1_low = M_C1_low * (self.L_C1 * self.W_C1 * 2e-15 + (self.L_C1 + self.W_C1) * 0.38e-15)
        self.C1_high = M_C1_high * (self.L_C1 * self.W_C1 * 2e-15 + (self.L_C1 + self.W_C1) * 0.38e-15)

        # 接下来action_space的定义确定了需要调整参数的个数
        self.action_space_low = np.array([1, 0.5, 1,  # M0
                                          1, 0.5, 1,  # M1=M2
                                          1, 0.5, 1,  # M3=M10
                                          1, 0.5, 1,  # M4
                                          1, 0.5, 1,  # M5
                                          1, 0.5, 1,  # M6
                                          1, 0.5, 1,  # M7=M11
                                          1, 0.5, 1,  # M8=M12
                                          1, 0.5, 1,  # M9=M13
                                          0.5,  # VBIAS2
                                          0.5,  # VBIAS3
                                          ])

        self.action_space_high = np.array([100, 2, 10,
                                           100, 2, 10,
                                           100, 2, 10,
                                           100, 2, 10,
                                           100, 2, 10,
                                           100, 2, 10,
                                           100, 2, 10,
                                           100, 2, 10,
                                           100, 2, 10,
                                           1.4,
                                           1.4
                                           ])

        self.action_dim = len(self.action_space_low)
        self.action_shape = (self.action_dim,)

        """Some target specifications for the final design"""
        self.Vdrop_target = 0.22  # drop-out voltage
        self.Vreg = 1.8  # regulated output
        self.GND = 0
        self.Vdd = 5

        self.Vload_reg_delta_target = self.Vreg * 0.02  # load regulartion variation is at most 2% of Vreg when it is switched from ILmin to ILmax

        self.GAIN_target = 60
        self.cmrr_target = 80
        self.pm_target = 60
        # self.psrr_target = 60
        self.bandwidth_target = 1e6  # 1mhz

        self.gain_threshold = 20
        self.cmrr_threshold = 20
        self.pm_threshold = 40
        self.bandwidth_threshold = 2e5  # 200khz

        """If you want to apply the reward engineering"""
        self.rew_eng = True

class GraphOTA3:
    """

         My OTA circuit is:

    node 0 will be M0
    node 1 will be M1
    node 2 will be M2
    node 3 will be M3
    node 4 will be M4
    node 5 will be M5
    node 6 will be M6
    node 7 will be M7
    node 8 will be M8
    node 9 will be M9
    node 10 will be M10
    node 11 will be M11
    node 12 will be M12
    node 13 will be M13
    node 14 will be M14
    node 15 will be vb
    node 16 will be Vdd
    node 17 will be GND
    node 18 will be C1
    node 19 will be C2

    """

    def __init__(self):
        self.device = torch.device(
            "cuda:0" if torch.cuda.is_available() else "cpu"
        )
        # self.num_node_features = 13
        # we do not include R here since, it is not straght forward to get the resistance from resistor
        # in SKY130 PDK
        self.ckt_hierarchy = (('M0', 'X1.XM0', 'nfet_g5v0d10v5', 'm'),
                              ('M1', 'X1.XM1', 'nfet_g5v0d10v5', 'm'),
                              ('M2', 'X1.XM2', 'nfet_g5v0d10v5', 'm'),
                              ('M3', 'X1.XM3', 'nfet_g5v0d10v5', 'm'),
                              ('M4', 'X1.XM4', 'nfet_g5v0d10v5', 'm'),
                              ('M5', 'X1.XM5', 'nfet_g5v0d10v5', 'm'),
                              ('M6', 'X1.XM6', 'nfet_g5v0d10v5', 'm'),
                              ('M7', 'X1.XM7', 'nfet_g5v0d10v5', 'm'),
                              ('M8', 'X1.XM8', 'pfet_g5v0d10v5', 'm'),
                              ('M9', 'X1.XM9', 'pfet_g5v0d10v5', 'm'),
                              ('M10', 'X1.XM10', 'pfet_g5v0d10v5', 'm'),
                              ('M11', 'X1.XM11', 'pfet_g5v0d10v5', 'm'),
                              ('M12', 'X1.XM12', 'pfet_g5v0d10v5', 'm'),
                              ('M13', 'X1.XM13', 'pfet_g5v0d10v5', 'm'),
                              ('M14', 'X1.XM14', 'pfet_g5v0d10v5', 'm'),
                              ('Vb', '', 'Vb', 'v'),

                              ('C1', 'X1.XC1', 'cap_mim_m3_1', 'c'),
                              ('C2', 'X1.XC2', 'cap_mim_m3_1', 'c')
                              )

        self.op = {'M0': {},
                   'M1': {},
                   'M2': {},
                   'M3': {},
                   'M4': {},
                   'M5': {},
                   'M6': {},
                   'M7': {},
                   'M8': {},
                   'M9': {},
                   'M10': {},
                   'M11': {},
                   'M12': {},
                   'M13': {},
                   'M14': {},
                   'Vb': {},
                   'C1': {},
                   'C2': {},
                   }

        # # 0-M0 1-M1 2-M2 3-M3 4-M4 5-M5 6-M6 7-M7 8-M8 9-M9 10-M10 11-M11 12-M12 13-M13 14-M14 15-vb 16-vdd 17-gnd 18-c1 19-c2

        # self.edge_index = torch.tensor([
        #     [0, 1], [1, 0], [0, 2], [2, 0], [0, 3], [3, 0], [0, 4], [4, 0], [0, 5], [5, 0],
        #     [0, 6], [6, 0], [0, 7], [7, 0], [0, 10], [10, 0], [0, 11], [11, 0], [0, 13], [13, 0],
        #     [0, 14], [14, 0], [0, 17], [17, 0], [0, 18], [18, 0],  # 26
        #     [1, 2], [2, 1], [1, 3], [3, 1], [1, 4], [4, 1], [1, 5], [5, 1], [1, 6], [6, 1],
        #     [1, 7], [7, 1], [1, 9], [9, 1], [1, 11], [11, 1], [1, 12], [12, 1], [1, 14], [14, 1],
        #     [1, 17], [17, 1], [1, 19], [19, 1],   # 24
        #     [2, 3], [3, 2], [2, 4], [4, 2], [2, 5], [5, 2], [2, 6], [6, 2], [2, 7], [7, 2],
        #     [2, 15], [15, 2], [2, 17], [17, 2],   # 14
        #     [3, 4], [4, 3], [3, 5], [5, 3], [3, 6], [6, 3], [3, 7], [7, 3], [3, 9], [9, 3],
        #     [3, 13], [13, 3], [3, 17], [17, 3], [3, 18], [18, 3], [3, 19], [19, 3],  # 18
        #     [4, 5], [5, 4], [4, 6], [6, 4], [4, 7], [7, 4], [4, 8], [8, 4], [4, 15], [15, 4],
        #     [4, 17], [17, 4],  # 12
        #     [5, 6], [6, 5], [5, 7], [7, 5], [5, 15], [15, 5], [5, 17], [17, 5],  # 8
        #     [6, 7], [7, 6], [6, 15], [15, 6], [6, 17], [17, 6],  # 6
        #     [7, 9], [9, 7], [7, 17], [17, 7], [7, 19], [19, 7],  # 6
        #     [8, 9], [9, 8], [8, 10], [10, 8], [8, 11], [11, 8], [8, 12], [12, 8], [8, 13], [13, 8],
        #     [8, 14], [14, 8], [8, 16], [16, 8],  # 14
        #     [9, 10], [10, 9], [9, 11], [11, 9], [9, 12], [12, 9], [9, 13], [13, 9], [9, 14], [14, 9],
        #     [9, 16], [16, 9], [9, 19], [19, 9],  # 14
        #     [10, 11], [11, 10], [10, 12], [12, 10], [10, 13], [13, 10], [10, 14], [14, 10], [10, 16], [16, 10],
        #     [10, 18], [18, 10],  # 12
        #     [11, 12], [12, 11], [11, 13], [13, 11], [11, 14], [14, 11], [11, 16], [16, 11], [11, 18], [18, 11],
        #     [11, 19], [19, 11],  # 12
        #     [12, 13], [13, 12], [12, 14], [14, 12], [12, 16], [16, 12], [12, 19], [19, 12],  # 8
        #     [13, 14], [14, 13], [13, 16], [16, 13], [13, 18], [18, 13],  # 6
        #     [14, 16], [16, 14], [14, 18], [18, 14], [14, 19], [19, 14]  # 6
        # ], dtype=torch.long).t().to(self.device) # 匹配第一种图表示

        self.edge_index = torch.tensor([
            [0, 1], [1, 0], [0, 2], [2, 0], [0, 10], [10, 0], [0, 11], [11, 0], [0, 13], [13, 0],
            [0, 14], [14, 0], [0, 17], [17, 0], [0, 18], [18, 0],  # 16
            [1, 2], [2, 1], [1, 3], [3, 1], [1, 9], [9, 1], [1, 11], [11, 1], [1, 12], [12, 1],
            [1, 14], [14, 1], [1, 17], [17, 1], [1, 19], [19, 1],   # 16
            [2, 5], [5, 2], [2, 6], [6, 2], [2, 15], [15, 2], [2, 17], [17, 2],   # 8
            [3, 6], [6, 3], [3, 7], [7, 3], [3, 9], [9, 3], [3, 13], [13, 3], [3, 17], [17, 3],
            [3, 18], [18, 3], [3, 19], [19, 3],  # 14
            [4, 5], [5, 4], [4, 6], [6, 4], [4, 8], [8, 4], [4, 15], [15, 4], [4, 17], [17, 4],  # 10
            [5, 6], [6, 5], [5, 7], [7, 5], [5, 15], [15, 5], [5, 17], [17, 5],  # 8
            [6, 7], [7, 6], [6, 15], [15, 6], [6, 17], [17, 6],  # 6
            [7, 9], [9, 7], [7, 17], [17, 7], [7, 19], [19, 7],  # 6
            [8, 16], [16, 8],  # 2
            [9, 11], [11, 9], [9, 12], [12, 9], [9, 14], [14, 9], [9, 16], [16, 9], [9, 19], [19, 9],  # 10
            [10, 11], [11, 10], [10, 13], [13, 10], [10, 14], [14, 10], [10, 16], [16, 10], [10, 18], [18, 10],  # 10
            [11, 12], [12, 11], [11, 13], [13, 11], [11, 14], [14, 11], [11, 16], [16, 11], [11, 18], [18, 11],
            [11, 19], [19, 11],  # 12
            [12, 13], [13, 12], [12, 14], [14, 12], [12, 16], [16, 12], [12, 19], [19, 12],  # 8
            [13, 14], [14, 13], [13, 16], [16, 13], [13, 18], [18, 13],  # 6
            [14, 16], [16, 14], [14, 18], [18, 14], [14, 19], [19, 14]  # 6
        ], dtype=torch.long).t().to(self.device)  # 匹配第一种图表示 1121修改 匹配第一种 待验证 1124验证

        self.edge_type = torch.tensor([  # 1118已修改 匹配第一种图表示
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 1, 1, 0, 0,  # 16
            0, 0, 1, 1, 1, 1, 1, 1, 1, 1,
            1, 1, 1, 1, 1, 1,  # 16
            1, 1, 1, 1, 1, 1, 1, 1,  # 8
            0, 0, 0, 0, 0, 0, 1, 1, 1, 1,
            1, 1, 0, 0,  # 14
            1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 10
            1, 1, 1, 1, 1, 1, 1, 1,  # 8
            0, 0, 1, 1, 1, 1,  # 6
            0, 0, 1, 1, 0, 0,  # 6
            1, 1,  # 2
            1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  # 10
            0, 0, 0, 0, 0, 0, 1, 1, 0, 0,  # 10
            1, 1, 0, 0, 0, 0, 1, 1, 0, 0,
            1, 1,  # 12
            1, 1, 1, 1, 1, 1, 1, 1,  # 8
            0, 0, 1, 1, 0, 0,  # 6
            1, 1, 0, 0, 1, 1,  # 6
        ]).to(self.device)  # 匹配第一种图表示 1121修改 匹配第一种 待验证 1124验证


        """

        修改图表示方式，以器件为节点 -> 以pin为节点，这样会极大的增加节点的数量，但对最终性能是否有优化还需试验
        0-M0_d 1-M0_g(vinp) 2-M0_s 3-M0_b 
        4-M1_d 5-M1_g(vinn) 6-M1_s 7-M1_b 
        8-M2_d 9-M2_g 10-M2_s 11-M2_b 
        12-M3_d 13-M3_g 14-M3_s 15-M3_b
        16-M4_d 17-M4_g 18-M4_s 19-M4_b 
        20-M5_d 21-M5_g 22-M5_s 23-M5_b
        24-M6_d 25-M6_g 26-M6_s 27-M6_b
        28-M7_d 29-M7_g 30-M7_s 31-M7_b
        32-M8_d 33-M8_g 34-M8_s 35-M8_b
        36-M9_d 37-M9_g 38-M9_s 39-M9_b
        40-M10_d 41-M10_g 42-M10_s 43-M10_b
        44-M11_d 45-M11_g 46-M11_s 47-M11_b
        48-M12_d 49-M12_g 50-M12_s 51-M12_b
        52-M13_d 53-M13_g 54-M13_s 55-M13_b
        56-M14_d 57-M14_g 58-M14_s 59-M14_b
        60-vb 61-vdd 62-gnd 63-c1 64-c2

        """

        # self.edge_index = torch.tensor([
        #     [0, 40], [40, 0], [0, 41], [41, 0], [0, 44], [44, 0], [0, 53], [53, 0], [0, 57], [57, 0],
        #     [0, 63], [63, 0],  # net2 12
        #     [2, 6], [6, 2], [2, 8], [8, 2],  # net6 4
        #     [3, 7], [7, 3], [3, 10], [10, 3], [3, 11], [11, 3], [3, 15], [15, 3], [3, 18], [18, 3],
        #     [3, 19], [19, 3], [3, 22], [22, 3], [3, 23], [23, 3], [3, 26], [26, 3], [3, 27], [27, 3],
        #     [3, 31], [31, 3], [3, 62], [62, 3],  # gnd 24
        #     [4, 37], [37, 4], [4, 45], [45, 4], [4, 48], [48, 4], [4, 49], [49, 4], [4, 56], [56, 4],
        #     [4, 64], [64, 4],  # net1 12
        #     [9, 17], [17, 9], [9, 20], [20, 9], [9, 21], [21, 9], [9, 25], [25, 9], [9, 60], [60, 9],  # vb 10
        #     [12, 52], [52, 12], [12, 63], [63, 12],  # out 4
        #     [13, 28], [28, 13], [13, 29], [29, 13], [13, 36], [36, 13], [13, 64], [64, 13],  # net3 8
        #     [14, 24], [24, 14], [14, 30], [30, 14],  # net4 4
        #     [16, 32], [32, 16], [16, 33], [33, 16],  # net5 4
        #     [34, 35], [35, 34], [34, 38], [38, 34], [34, 39], [39, 34], [34, 42], [42, 34], [34, 43], [43, 34],
        #     [34, 46], [46, 34], [34, 47], [47, 34], [34, 50], [34, 50], [34, 51], [51, 34], [34, 54], [54, 34],
        #     [34, 55], [55, 34], [34, 58], [58, 34], [34, 59], [59, 34], [34, 61], [61, 34],  # vdd 28
        # ], dtype=torch.long).t().to(self.device)  # 匹配第二种图表示

        # sorted based on if it is the small signal path
        # small signal path: 0; biasing path: 1 1是直流，0是交流

        # self.edge_type = torch.tensor([  # 1121已修改 匹配第二种图表示
        #     0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        #     0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        #     0, 0,  # net2 12
        #     0, 0, 0, 0,  # net 6 4
        #     1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        #     1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        #     1, 1, 1, 1,  # gnd 24
        #     1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        #     1, 1,  # net1 12
        #     0, 0, 0, 0,  # out 4
        #     0, 0, 0, 0, 0, 0, 0, 0,  # net3 8
        #     0, 0, 0, 0,  # net4 4
        #     1, 1, 1, 1,  # net5 4
        #     1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        #     1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        #     1, 1, 1, 1, 1, 1, 1, 1,  # vdd 28
        #
        # ]).to(self.device)

        # self.edge_type = torch.tensor([  # 1118已修改 匹配第一种图表示
        #     0, 0, 0, 0, 1, 1, 1, 1, 1, 1,
        #     1, 1, 1, 1, 0, 0, 0, 0, 0, 0,
        #     0, 0, 1, 1, 0, 0,  # 26
        #     0, 0, 1, 1, 1, 1, 1, 1, 1, 1,
        #     1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        #     1, 1, 1, 1,  # 24
        #     1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        #     1, 1, 1, 1,  # 14
        #     1, 1, 1, 1, 0, 0, 0, 0, 0, 0,
        #     1, 1, 1, 1, 1, 1, 0, 0,  # 18
        #     1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        #     1, 1,  # 12
        #     1, 1, 1, 1, 1, 1, 1, 1,  # 8
        #     0, 0, 1, 1, 1, 1,  # 6
        #     0, 0, 1, 1, 0, 0,  # 6
        #     1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        #     1, 1, 1, 1,  # 14
        #     1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
        #     1, 1, 1, 1,  # 14
        #     0, 0, 1, 1, 0, 0, 0, 0, 1, 1,
        #     0, 0,  # 12
        #     1, 1, 0, 0, 0, 0, 1, 1, 0, 0,
        #     1, 1,  # 12
        #     1, 1, 1, 1, 1, 1, 1, 1,  # 8
        #     0, 0, 1, 1, 0, 0,  # 6
        #     1, 1, 0, 0, 1, 1,  # 6
        # ]).to(self.device)


        self.num_relations = 2
        # self.num_relations = 1
        self.num_nodes = 20 # 匹配第一种图表示
        # self.num_nodes = 65  # 匹配第二种图表示
        self.num_node_features = 13  # 0902未修改，0909无需修改
        self.obs_shape = (self.num_nodes, self.num_node_features)

        """Select an action from the input state."""
        self.L_C1 = 30  # each unit cap is 30um by 30um
        self.W_C1 = 30
        M_C1_low = 10
        M_C1_high = 300  # copies of unit cap
        self.C1_low = M_C1_low * (self.L_C1 * self.W_C1 * 2e-15 + (self.L_C1 + self.W_C1) * 0.38e-15)
        self.C1_high = M_C1_high * (self.L_C1 * self.W_C1 * 2e-15 + (self.L_C1 + self.W_C1) * 0.38e-15)

        # 接下来action_space的定义确定了需要调整参数的个数
        self.action_space_low = np.array([1, 0.5, 1,  # MM0=MM1
                                          1, 0.5, 1,  # MM2=MM6
                                          1, 0.5, 1,  # MM3=MM7
                                          1, 0.5, 1,  # MM4=MM5
                                          1, 0.5, 1,  # MM8
                                          1, 0.5, 1,  # MM9=MM13
                                          1, 0.5, 1,  # MM10=MM14
                                          1, 0.5, 1,  # MM11=MM12
                                          1.2,  # vb
                                          ])

        self.action_space_high = np.array([100, 2, 10,
                                           100, 2, 10,
                                           100, 2, 10,
                                           100, 2, 10,
                                           100, 2, 10,
                                           100, 2, 10,
                                           100, 2, 10,
                                           100, 2, 10,
                                           2.4,
                                           ])

        self.action_dim = len(self.action_space_low)
        self.action_shape = (self.action_dim,)

        """Some target specifications for the final design"""
        self.Vdrop_target = 0.22  # drop-out voltage
        self.Vreg = 1.8  # regulated output
        self.GND = 0
        self.Vdd = 2

        self.Vload_reg_delta_target = self.Vreg * 0.02  # load regulartion variation is at most 2% of Vreg when it is switched from ILmin to ILmax

        self.GAIN_target = 60
        self.cmrr_target = 80
        self.pm_target = 60
        # self.psrr_target = 60
        self.bandwidth_target = 1e6  # 1mhz

        self.gain_threshold = 20
        self.cmrr_threshold = 20
        self.pm_threshold = 40
        self.bandwidth_threshold = 2e5  # 200khz

        """If you want to apply the reward engineering"""
        self.rew_eng = True