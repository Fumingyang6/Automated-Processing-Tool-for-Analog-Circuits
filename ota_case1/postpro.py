#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 强化学习环境

import torch
import numpy as np
import os
import json
from tabulate import tabulate
import gymnasium as gym
from gymnasium import spaces

from ckt_graphs import GraphOTA
from dev_params import DeviceParams
from utils import ActionNormalizer, OutputParser_ota

from datetime import datetime

date = datetime.today().strftime('%Y-%m-%d')

PWD = os.getcwd()
SPICE_NETLIST_DIR = f'{PWD}/simulations'
os.environ['CUDA_LAUNCH_BLOCKING'] = "1"

CktGraph1 = GraphOTA


class OTAEnv(gym.Env, CktGraph1, DeviceParams):

    def __init__(self):
        gym.Env.__init__(self)
        CktGraph1.__init__(self)
        DeviceParams.__init__(self, self.ckt_hierarchy)

        self.CktGraph = CktGraph1()
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=self.obs_shape, dtype=np.float64)
        self.action_space = spaces.Box(low=-1, high=1, shape=self.action_shape, dtype=np.float64)  # 动作空间和观测空间都是连续空间

    def _initialize_simulation(self):  # 初始化电路参数，即可调整的参数个数
        self.W_M0, self.L_M0, self.M_M0, \
            self.W_M1, self.L_M1, self.M_M1, \
            self.W_M2, self.L_M2, self.M_M2, \
            self.W_M3, self.L_M3, self.M_M3, \
            self.W_M4, self.L_M4, self.M_M4, \
            self.W_M5, self.L_M5, self.M_M5, \
            self.W_M6, self.L_M6, self.M_M6, \
            self.Vb, = \
            np.array([0.42, 0.5, 1,
                      0.42, 0.5, 1,
                      0.42, 0.5, 1,
                      0.42, 0.5, 1,
                      0.42, 0.5, 1,
                      0.42, 0.5, 1,
                      0.42, 0.5, 1,
                      1.1166186541318894  # vb
                      ])

        """Run the initial simulations."""
        action = np.array([self.W_M0, self.L_M0, self.M_M0, \
                           self.W_M1, self.L_M1, self.M_M1, \
                           self.W_M3, self.L_M3, self.M_M3, \
                           self.W_M6, self.L_M6, self.M_M6, \
                           self.Vb])

        self.do_simulation(action)  # 初始化仿真，函数do_simulation的参数是目前的电路参数设置

    def _do_simulation(self, action: np.array):  # 对./simulation路径下的ldo_tb_vars.spice做写入，对ldo_tb.spice做仿真，后者调用前者
        """
         MM0 MM5 need to match
         MM3 MM4 need to match
         MM1 MM2 need to highly match

        """
        W_M0, L_M0, M_M0, \
            W_M1, L_M1, M_M1, \
            W_M3, L_M3, M_M3, \
            W_M6, L_M6, M_M6, \
            Vb = action

        M_M0 = int(M_M0)
        M_M1 = int(M_M1)
        M_M3 = int(M_M3)
        M_M6 = int(M_M6)

        W_M0 = int(W_M0) * 0.21
        W_M1 = int(W_M1) * 0.21
        W_M3 = int(W_M3) * 0.21
        W_M6 = int(W_M6) * 0.21


        # update netlist
        try:
            # open the netlist of the testbench
            ota_vars = open(f'{SPICE_NETLIST_DIR}/ota_vars.spice', 'r')
            # lines = ota_vars.readlines()

            # if lines == []:
            lines = ["" for _ in range(10)]
            lines[0] = f'.param W_M0={W_M0} L_M0={L_M0} M_M0={M_M0}\n'
            lines[1] = f'.param W_M1={W_M1} L_M1={L_M1} M_M1={M_M1}\n'
            lines[2] = f'.param W_M2={W_M1} L_M2={L_M1} M_M2={M_M1}\n'
            lines[3] = f'.param W_M3={W_M3} L_M3={L_M3} M_M3={M_M3}\n'
            lines[4] = f'.param W_M4={W_M3} L_M4={L_M3} M_M4={M_M3}\n'
            lines[5] = f'.param W_M5={W_M0} L_M5={L_M0} M_M5={M_M0}\n'
            lines[6] = f'.param W_M6={W_M6} L_M6={L_M6} M_M6={M_M6}\n'
            lines[7] = f'.param Vb={Vb}\n'
            lines[8] = f'.param VDD=5\n'
            lines[9] = f'.param GND=0\n'

            ota_vars = open(f'{SPICE_NETLIST_DIR}/ota_vars.spice', 'w')
            ota_vars.writelines(lines)
            ota_vars.close()

            print('*** Simulations for bandwidth, gain, cmrr and phase  ***')
            os.system(f'cd {SPICE_NETLIST_DIR}; ngspice -b -o ota.log ota.spice')
            print('*** Simulations Done! ***')
        except:
            print('ERROR')

    def do_simulation(self, action):
        self._do_simulation(action)
        self.sim_results = OutputParser_ota(self.CktGraph)
        self.op_results = self.sim_results.dcop(file_name='ota_op')

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._initialize_simulation()
        observation = self._get_obs()
        info = self._get_info()
        return observation, info

    def close(self):
        return None

    def step(self, action):
        action = ActionNormalizer(action_space_low=self.action_space_low, action_space_high= \
            self.action_space_high).action(action)  # convert [-1.1] range back to normal range
        action = action.astype(object)  # action中的astype函数将原action中的数据类型转换为object类型

        print(f"action: {action}")

        self.W_M0, self.L_M0, self.M_M0, \
            self.W_M1, self.L_M1, self.M_M1, \
            self.W_M3, self.L_M3, self.M_M3, \
            self.W_M6, self.L_M6, self.M_M6, \
            self.Vb = action

        ''' run simulations '''
        self.do_simulation(action)

        ''' get observation '''
        observation = self._get_obs()
        info = self._get_info()

        reward = self.reward  # 关于reward的定义方法在函数_get_info()里

        if reward >= 0:
            terminated = True
        else:
            terminated = False

        print(tabulate(  # 这里用到的dc_result是从函数 _get_info()里面来的
            [

                ['Bandwidth', self.bandwidth_result, self.bandwidth_target],
                ['Gain', self.gain_max, self.GAIN_target],
                ['CMRR', self.cmrr_max, self.cmrr_target],
                ['PM', self.pm_max, self.pm_target],

                ['bandwidth score', self.bandwidth_score, ''],
                ['gain score', self.gain_score, ''],
                ['cmrr score', self.cmrr_score, ''],
                ['pm score', self.pm_score, ''],

                ['Reward', reward, '']
            ],
            headers=['param', 'num', 'target'], tablefmt='orgtbl', numalign='right', floatfmt=".2f"
        ))

        return observation, reward, terminated, False, info

    def _get_obs(self):
        # pick some .OP params from the dict:
        try:
            f = open(f'{SPICE_NETLIST_DIR}/ota_op_mean_std.json')
            self.op_mean_std = json.load(f)
            self.op_mean = self.op_mean_std['OP_M_mean']
            self.op_std = self.op_mean_std['OP_M_std']
            self.op_mean = np.array([self.op_mean['id'], self.op_mean['gm'], self.op_mean['gds'], self.op_mean['vth'],
                                     self.op_mean['vdsat'], self.op_mean['vds'], self.op_mean['vgs']])
            self.op_std = np.array(
                [self.op_std['id'], self.op_std['gm'], self.op_std['gds'], self.op_std['vth'], self.op_std['vdsat'],
                 self.op_std['vds'], self.op_std['vgs']])
        except:
            print('You need to run <_random_op_sims> to generate mean and std for transistor .OP parameters')

        self.OP_M0 = self.op_results['M0']  # op_results是在前面的do_simulation函數中更新的
        self.OP_M0_norm = (np.array([self.OP_M0['id'],
                                     self.OP_M0['gm'],
                                     self.OP_M0['gds'],
                                     self.OP_M0['vth'],
                                     self.OP_M0['vdsat'],
                                     self.OP_M0['vds'],
                                     self.OP_M0['vgs']
                                     ]) - self.op_mean) / self.op_std
        self.OP_M1 = self.op_results['M1']
        self.OP_M1_norm = (np.array([self.OP_M1['id'],
                                     self.OP_M1['gm'],
                                     self.OP_M1['gds'],
                                     self.OP_M1['vth'],
                                     self.OP_M1['vdsat'],
                                     self.OP_M1['vds'],
                                     self.OP_M1['vgs']
                                     ]) - self.op_mean) / self.op_std
        self.OP_M2 = self.op_results['M2']
        self.OP_M2_norm = (np.array([self.OP_M2['id'],
                                     self.OP_M2['gm'],
                                     self.OP_M2['gds'],
                                     self.OP_M2['vth'],
                                     self.OP_M2['vdsat'],
                                     self.OP_M2['vds'],
                                     self.OP_M2['vgs']
                                     ]) - self.op_mean) / self.op_std
        self.OP_M3 = self.op_results['M3']
        self.OP_M3_norm = (np.abs([self.OP_M3['id'],
                                   self.OP_M3['gm'],
                                   self.OP_M3['gds'],
                                   self.OP_M3['vth'],
                                   self.OP_M3['vdsat'],
                                   self.OP_M3['vds'],
                                   self.OP_M3['vgs']
                                   ]) - self.op_mean) / self.op_std
        self.OP_M4 = self.op_results['M4']
        self.OP_M4_norm = (np.abs([self.OP_M4['id'],
                                   self.OP_M4['gm'],
                                   self.OP_M4['gds'],
                                   self.OP_M4['vth'],
                                   self.OP_M4['vdsat'],
                                   self.OP_M4['vds'],
                                   self.OP_M4['vgs']
                                   ]) - self.op_mean) / self.op_std
        self.OP_M5 = self.op_results['M5']
        self.OP_M5_norm = (np.abs([self.OP_M5['id'],
                                   self.OP_M5['gm'],
                                   self.OP_M5['gds'],
                                   self.OP_M5['vth'],
                                   self.OP_M5['vdsat'],
                                   self.OP_M5['vds'],
                                   self.OP_M5['vgs']
                                   ]) - self.op_mean) / self.op_std
        self.OP_M6 = self.op_results['M6']
        self.OP_M6_norm = (np.array([self.OP_M6['id'],
                                     self.OP_M6['gm'],
                                     self.OP_M6['gds'],
                                     self.OP_M6['vth'],
                                     self.OP_M6['vdsat'],
                                     self.OP_M6['vds'],
                                     self.OP_M6['vgs']
                                     ]) - self.op_mean) / self.op_std

        self.OP_Vb = self.op_results['Vb']['dc']

        # normalize all passive components
        self.OP_C1_norm = ActionNormalizer(action_space_low=self.C1_low, action_space_high=self.C1_high).reverse_action(
            self.op_results['C1']['c'])  # convert to (-1, 1)

        # [OP_Vb,OP_Vdd,OP_GND,     OP_Rfb_norm, OP_Cfb_norm, OP_CL_norm,      OP_M_norm]
        # state shall be in the order of node (node0, node1, ...) 12个节点，每个节点有13个观测值
        observation = np.array([
            [0, 0, 0, 0, 0, 0, self.OP_M0_norm[0], self.OP_M0_norm[1], self.OP_M0_norm[2], self.OP_M0_norm[3],
             self.OP_M0_norm[4], self.OP_M0_norm[5], self.OP_M0_norm[6]],
            [0, 0, 0, 0, 0, 0, self.OP_M1_norm[0], self.OP_M1_norm[1], self.OP_M1_norm[2], self.OP_M1_norm[3],
             self.OP_M1_norm[4], self.OP_M1_norm[5], self.OP_M1_norm[6]],
            [0, 0, 0, 0, 0, 0, self.OP_M2_norm[0], self.OP_M2_norm[1], self.OP_M2_norm[2], self.OP_M2_norm[3],
             self.OP_M2_norm[4], self.OP_M2_norm[5], self.OP_M2_norm[6]],
            [0, 0, 0, 0, 0, 0, self.OP_M3_norm[0], self.OP_M3_norm[1], self.OP_M3_norm[2], self.OP_M3_norm[3],
             self.OP_M3_norm[4], self.OP_M3_norm[5], self.OP_M3_norm[6]],
            [0, 0, 0, 0, 0, 0, self.OP_M4_norm[0], self.OP_M4_norm[1], self.OP_M4_norm[2], self.OP_M4_norm[3],
             self.OP_M4_norm[4], self.OP_M4_norm[5], self.OP_M4_norm[6]],
            [0, 0, 0, 0, 0, 0, self.OP_M5_norm[0], self.OP_M5_norm[1], self.OP_M5_norm[2], self.OP_M5_norm[3],
             self.OP_M5_norm[4], self.OP_M5_norm[5], self.OP_M5_norm[6]],
            [0, 0, 0, 0, 0, 0, self.OP_M6_norm[0], self.OP_M6_norm[1], self.OP_M6_norm[2], self.OP_M6_norm[3],
             self.OP_M6_norm[4], self.OP_M6_norm[5], self.OP_M6_norm[6]],
            [self.Vb, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, self.Vdd, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, self.GND, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, self.OP_C1_norm, 0, 0, 0, 0, 0, 0, 0],
        ]) # 匹配第一种图表示
        # observation = np.array([
        #     [0, 0, 0, 0, 0, 0, self.OP_M0_norm[0], self.OP_M0_norm[1], self.OP_M0_norm[2], self.OP_M0_norm[3],
        #      self.OP_M0_norm[4], self.OP_M0_norm[5], self.OP_M0_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M0_norm[0], self.OP_M0_norm[1], self.OP_M0_norm[2], self.OP_M0_norm[3],
        #      self.OP_M0_norm[4], self.OP_M0_norm[5], self.OP_M0_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M0_norm[0], self.OP_M0_norm[1], self.OP_M0_norm[2], self.OP_M0_norm[3],
        #      self.OP_M0_norm[4], self.OP_M0_norm[5], self.OP_M0_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M0_norm[0], self.OP_M0_norm[1], self.OP_M0_norm[2], self.OP_M0_norm[3],
        #      self.OP_M0_norm[4], self.OP_M0_norm[5], self.OP_M0_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M1_norm[0], self.OP_M1_norm[1], self.OP_M1_norm[2], self.OP_M1_norm[3],
        #      self.OP_M1_norm[4], self.OP_M1_norm[5], self.OP_M1_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M1_norm[0], self.OP_M1_norm[1], self.OP_M1_norm[2], self.OP_M1_norm[3],
        #      self.OP_M1_norm[4], self.OP_M1_norm[5], self.OP_M1_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M1_norm[0], self.OP_M1_norm[1], self.OP_M1_norm[2], self.OP_M1_norm[3],
        #      self.OP_M1_norm[4], self.OP_M1_norm[5], self.OP_M1_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M1_norm[0], self.OP_M1_norm[1], self.OP_M1_norm[2], self.OP_M1_norm[3],
        #      self.OP_M1_norm[4], self.OP_M1_norm[5], self.OP_M1_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M2_norm[0], self.OP_M2_norm[1], self.OP_M2_norm[2], self.OP_M2_norm[3],
        #      self.OP_M2_norm[4], self.OP_M2_norm[5], self.OP_M2_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M2_norm[0], self.OP_M2_norm[1], self.OP_M2_norm[2], self.OP_M2_norm[3],
        #      self.OP_M2_norm[4], self.OP_M2_norm[5], self.OP_M2_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M2_norm[0], self.OP_M2_norm[1], self.OP_M2_norm[2], self.OP_M2_norm[3],
        #      self.OP_M2_norm[4], self.OP_M2_norm[5], self.OP_M2_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M2_norm[0], self.OP_M2_norm[1], self.OP_M2_norm[2], self.OP_M2_norm[3],
        #      self.OP_M2_norm[4], self.OP_M2_norm[5], self.OP_M2_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M3_norm[0], self.OP_M3_norm[1], self.OP_M3_norm[2], self.OP_M3_norm[3],
        #      self.OP_M3_norm[4], self.OP_M3_norm[5], self.OP_M3_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M3_norm[0], self.OP_M3_norm[1], self.OP_M3_norm[2], self.OP_M3_norm[3],
        #      self.OP_M3_norm[4], self.OP_M3_norm[5], self.OP_M3_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M3_norm[0], self.OP_M3_norm[1], self.OP_M3_norm[2], self.OP_M3_norm[3],
        #      self.OP_M3_norm[4], self.OP_M3_norm[5], self.OP_M3_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M3_norm[0], self.OP_M3_norm[1], self.OP_M3_norm[2], self.OP_M3_norm[3],
        #      self.OP_M3_norm[4], self.OP_M3_norm[5], self.OP_M3_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M4_norm[0], self.OP_M4_norm[1], self.OP_M4_norm[2], self.OP_M4_norm[3],
        #      self.OP_M4_norm[4], self.OP_M4_norm[5], self.OP_M4_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M4_norm[0], self.OP_M4_norm[1], self.OP_M4_norm[2], self.OP_M4_norm[3],
        #      self.OP_M4_norm[4], self.OP_M4_norm[5], self.OP_M4_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M4_norm[0], self.OP_M4_norm[1], self.OP_M4_norm[2], self.OP_M4_norm[3],
        #      self.OP_M4_norm[4], self.OP_M4_norm[5], self.OP_M4_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M4_norm[0], self.OP_M4_norm[1], self.OP_M4_norm[2], self.OP_M4_norm[3],
        #      self.OP_M4_norm[4], self.OP_M4_norm[5], self.OP_M4_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M5_norm[0], self.OP_M5_norm[1], self.OP_M5_norm[2], self.OP_M5_norm[3],
        #      self.OP_M5_norm[4], self.OP_M5_norm[5], self.OP_M5_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M5_norm[0], self.OP_M5_norm[1], self.OP_M5_norm[2], self.OP_M5_norm[3],
        #      self.OP_M5_norm[4], self.OP_M5_norm[5], self.OP_M5_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M5_norm[0], self.OP_M5_norm[1], self.OP_M5_norm[2], self.OP_M5_norm[3],
        #      self.OP_M5_norm[4], self.OP_M5_norm[5], self.OP_M5_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M5_norm[0], self.OP_M5_norm[1], self.OP_M5_norm[2], self.OP_M5_norm[3],
        #      self.OP_M5_norm[4], self.OP_M5_norm[5], self.OP_M5_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M6_norm[0], self.OP_M6_norm[1], self.OP_M6_norm[2], self.OP_M6_norm[3],
        #      self.OP_M6_norm[4], self.OP_M6_norm[5], self.OP_M6_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M6_norm[0], self.OP_M6_norm[1], self.OP_M6_norm[2], self.OP_M6_norm[3],
        #      self.OP_M6_norm[4], self.OP_M6_norm[5], self.OP_M6_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M6_norm[0], self.OP_M6_norm[1], self.OP_M6_norm[2], self.OP_M6_norm[3],
        #      self.OP_M6_norm[4], self.OP_M6_norm[5], self.OP_M6_norm[6]],
        #     [0, 0, 0, 0, 0, 0, self.OP_M6_norm[0], self.OP_M6_norm[1], self.OP_M6_norm[2], self.OP_M6_norm[3],
        #      self.OP_M6_norm[4], self.OP_M6_norm[5], self.OP_M6_norm[6]],
        #     [self.Vb, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        #     [0, self.Vdd, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        #     [0, 0, self.GND, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        #     [0, 0, 0, 0, 0, self.OP_C1_norm, 0, 0, 0, 0, 0, 0, 0],
        # ]) # 匹配第二种图表示
        # clip the obs for better regularization
        observation = np.clip(observation, -5, 5)

        return observation

    def _get_info(self):
        '''Evaluate the performance'''
        ''' DC performance '''
        self.dc_results = self.sim_results.dc(file_name='ota_dc')  # sim_results get update form 'def do_simulation'
        idx = int(self.Vdd / 0.01 - 1 / 0.01)  # since I sweep Vdc from 1V - 3V to avoid some bad DC points
        self.Vdrop = abs(self.Vdd - self.dc_results[1][idx])

        self.Vdrop_score = np.min([(self.Vdrop_target - self.Vdrop) / (self.Vdrop_target + self.Vdrop), 0])

        """ Load regulation """
        _, self.load_reg = self.sim_results.tran(file_name='ota_load_reg')
        idx_1 = int(len(self.load_reg) / 4)
        idx_2 = len(self.load_reg) - 1
        self.Vload_reg_delta = abs(self.load_reg[idx_2] - self.load_reg[idx_1])

        self.load_reg_score = np.min([(self.Vload_reg_delta_target - self.Vload_reg_delta) / (
                self.Vload_reg_delta_target + self.Vload_reg_delta), 0])


        """ bandwidth performance """
        self.bandwidth_results = self.sim_results.ac_bandwidth(file_name='ota_bandwidth')
        # 获取频率和增益列表
        freq = self.bandwidth_results[0]  # 频率列表
        gain = self.bandwidth_results[1]  # 增益列表
        # 1. 找到增益中的最大值
        max_gain = max(gain)
        # 2. 计算最大值减 3（单位假设为dB）
        target_gain = max_gain - 3
        # 3. 找到最接近 target_gain 的增益，并获取其对应的频率
        # 使用绝对值差值来找到最接近的增益值
        closest_index = (np.abs(np.array(gain) - target_gain)).argmin()
        # 4. 对应的频率即为带宽
        self.bandwidth_result = freq[closest_index]

        if self.rew_eng == True:
            # 如果增益最大值小于某个目标值，减分
            if self.bandwidth_result < self.bandwidth_target:
                self.bandwidth_score = np.min(
                    [(self.bandwidth_result - self.bandwidth_target) / (self.bandwidth_result + self.bandwidth_target),
                     0])
            else:
                # 增益达到目标值或更高时，得高分
                self.bandwidth_score = (self.bandwidth_result - self.bandwidth_target) / (
                            self.bandwidth_result + self.bandwidth_target)
                # self.gain_score = self.gain_score * 0.5  # 给权重

        else:
            # 仅基于增益值计算分数，不考虑是否启用奖励引擎
            self.bandwidth_score = np.min(
                [(self.bandwidth_result - self.bandwidth_target) / (self.bandwidth_result + self.bandwidth_target), 0])


        """ cmrr performance """
        self.acm_results, self.adm_results = self.sim_results.ac_cmrr(acm_file_name='ota_acm', adm_file_name='ota_adm')
        # 找到最大值
        self.acm_max = min(self.acm_results)
        self.adm_max = max(self.adm_results)
        if self.acm_max != 0 and (self.adm_max / self.acm_max) > 0:
            self.cmrr_max = self.adm_max / self.acm_max
        else:
            self.cmrr_max = float('-inf')
        self.cmrr_max = 20 * np.log10(self.cmrr_max)

        if self.rew_eng == True:
            # cmrr小于target，减分
            if self.cmrr_max < self.cmrr_target:
                self.cmrr_score = np.min([(self.cmrr_max - self.cmrr_target) / (self.cmrr_max + self.cmrr_target), 0])
            else:
                # cmrr小于等于target，得高分
                self.cmrr_score = (self.cmrr_max - self.cmrr_target) / (self.cmrr_max + self.cmrr_target)
                # self.cmrr_score = self.cmrr_score * 0.5  # 给权重

        else:
            # 仅基于增益值计算分数，不考虑是否启用奖励引擎
            self.cmrr_score = np.min([(self.cmrr_max - self.cmrr_target) / (self.cmrr_max + self.cmrr_target), 0])

        """ Gain performance """
        self.gain_results = self.sim_results.ac_gain(
            file_name='ota_gain')  # sim_results get update form 'def do_simulation'
        # 找到增益最大值
        self.gain_max = max(self.gain_results[1])

        if self.rew_eng == True:
            # 如果增益最大值小于某个目标值，减分
            if self.gain_max < self.GAIN_target:
                self.gain_score = np.min([(self.gain_max - self.GAIN_target) / (self.gain_max + self.GAIN_target), 0])
            else:
                # 增益达到目标值或更高时，得高分
                self.gain_score = (self.gain_max - self.GAIN_target) / (self.gain_max + self.GAIN_target)
                # self.gain_score = self.gain_score * 0.5  # 给权重

        else:
            # 仅基于增益值计算分数，不考虑是否启用奖励引擎
            self.gain_score = np.min([(self.gain_max - self.GAIN_target) / (self.gain_max + self.GAIN_target), 0])

        """ PM performance """
        self.pm_results = self.sim_results.ac_pm(
            file_name1='ota_gain', file_name2='ota_phase_margin')  # sim_results get update form 'def do_simulation'
        # 找到相位裕度
        self.pm_freq, self.pm_gain, self.pm = self.pm_results
        # 找到增益为0 dB时的频率
        closest_freq_idx = -1
        min_diff = float('inf')  # 初始差值设置为无穷大

        for i in range(len(self.pm_gain)):
            diff = abs(self.pm_gain[i])  # 计算与0 dB的差距
            if diff < min_diff:
                min_diff = diff
                closest_freq_idx = i

        # 获取该频率对应的相位
        self.pm_max = self.pm[closest_freq_idx]
        self.pm_max += 180


        if self.rew_eng == True:
            # 如果增益最大值小于某个目标值，减分
            if self.pm_max < self.pm_target:
                self.pm_score = np.min([(self.pm_max - self.pm_target) / (self.pm_max + self.pm_target), 0])
            else:
                # 增益达到目标值或更高时，得高分
                self.pm_score = (self.pm_max - self.pm_target) / (self.pm_max + self.pm_target)
                # self.gain_score = self.gain_score * 0.5  # 给权重

        else:
            # 仅基于增益值计算分数，不考虑是否启用奖励引擎
            self.pm_score = np.min([(self.pm_max - self.pm_target) / (self.pm_max + self.pm_target), 0])

        """ Decap score """
        self.C1_area_score = (self.C1_low - self.op_results['C1']['c']) / (self.C1_low + self.op_results['C1']['c'])

        """ Total reward """  # 更新reward
        self.reward = 0.25 * self.bandwidth_score + 0.25 * self.gain_score + 0.25 * self.cmrr_score + \
                      0.25 * self.pm_score

        if self.reward >= 0:  # 额外奖励
            self.reward = self.reward + 1

        # 额外惩罚1
        if (self.gain_max < 0) or (self.bandwidth_result < 0) or (self.cmrr_max < 0) or (self.pm_max < 0):
            self.reward = self.reward - 1

        # 额外惩罚2
        if (self.gain_max < self.gain_threshold):
            self.reward = self.reward - 0.1
        if (self.bandwidth_result < self.bandwidth_threshold):
            self.reward = self.reward - 0.1
        if (self.cmrr_max < self.cmrr_threshold):
            self.reward = self.reward - 0.1
        if (self.pm_max < self.pm_threshold):
            self.reward = self.reward - 0.1

        return {
            'Drop-out voltage (mV)': self.Vdrop * 1e3,
            'Load regulation (mV)': self.Vload_reg_delta * 1e3,


            'Bandwidth': self.bandwidth_result,
            'Gain': self.gain_max,
            'CMRR': self.cmrr_max,
            'PM': self.pm_max

        }

    def _init_random_sim(self, max_sims=100, write=True):
        '''

        This is NOT the same as the random step in the agent, here is basically
        doing some completely random design variables selection for generating
        some device parameters for calculating the mean and variance for each
        .OP device parameters (getting a statistical idea of, how each ckt parameter's range is like),
        so that you can do the normalization for the state representations later.

        '''

        random_op_count = 0
        OP_M_lists = []
        OP_R_lists = []
        OP_C_lists = []
        OP_V_lists = []

        while random_op_count <= max_sims:
            print(f'* simulation #{random_op_count} *')
            action = np.random.uniform(self.action_space_low, self.action_space_high, self.action_dim)
            print(f'action: {action}')
            self._do_simulation(action)

            sim_results = OutputParser_ota(self.CktGraph)
            op_results = sim_results.dcop(file_name='ota_op')

            OP_M_list = []
            OP_R_list = []
            OP_C_list = []
            OP_V_list = []

            for key in list(op_results):
                if key[0] == 'M' or key[0] == 'm':
                    OP_M = np.array([op_results[key][f'{item}'] for item in list(op_results[key])])
                    OP_M_list.append(OP_M)
                elif key[0] == 'R' or key[0] == 'r':
                    OP_R = np.array([op_results[key][f'{item}'] for item in list(op_results[key])])
                    OP_R_list.append(OP_R)
                elif key[0] == 'C' or key[0] == 'c':
                    OP_C = np.array([op_results[key][f'{item}'] for item in list(op_results[key])])
                    OP_C_list.append(OP_C)
                elif key[0] == 'V' or key[0] == 'v':
                    OP_V = np.array([op_results[key][f'{item}'] for item in list(op_results[key])])
                    OP_V_list.append(OP_V)
                else:
                    None

            OP_M_list = np.array(OP_M_list)
            OP_R_list = np.array(OP_R_list)
            OP_C_list = np.array(OP_C_list)
            OP_V_list = np.array(OP_V_list)

            OP_M_lists.append(OP_M_list)
            OP_R_lists.append(OP_R_list)
            OP_C_lists.append(OP_C_list)
            OP_V_lists.append(OP_V_list)

            random_op_count = random_op_count + 1

        OP_M_lists = np.array(OP_M_lists)
        OP_R_lists = np.array(OP_R_lists)
        OP_C_lists = np.array(OP_C_lists)
        OP_V_lists = np.array(OP_V_lists)

        if OP_M_lists.size != 0:
            OP_M_mean = np.mean(OP_M_lists.reshape(-1, OP_M_lists.shape[-1]), axis=0)
            OP_M_std = np.std(OP_M_lists.reshape(-1, OP_M_lists.shape[-1]), axis=0)
            OP_M_mean_dict = {}
            OP_M_std_dict = {}
            for idx, key in enumerate(self.params_mos):
                OP_M_mean_dict[key] = OP_M_mean[idx]
                OP_M_std_dict[key] = OP_M_std[idx]

        if OP_R_lists.size != 0:
            OP_R_mean = np.mean(OP_R_lists.reshape(-1, OP_R_lists.shape[-1]), axis=0)
            OP_R_std = np.std(OP_R_lists.reshape(-1, OP_R_lists.shape[-1]), axis=0)
            OP_R_mean_dict = {}
            OP_R_std_dict = {}
            for idx, key in enumerate(self.params_r):
                OP_R_mean_dict[key] = OP_R_mean[idx]
                OP_R_std_dict[key] = OP_R_std[idx]

        if OP_C_lists.size != 0:
            OP_C_mean = np.mean(OP_C_lists.reshape(-1, OP_C_lists.shape[-1]), axis=0)
            OP_C_std = np.std(OP_C_lists.reshape(-1, OP_C_lists.shape[-1]), axis=0)
            OP_C_mean_dict = {}
            OP_C_std_dict = {}
            for idx, key in enumerate(self.params_c):
                OP_C_mean_dict[key] = OP_C_mean[idx]
                OP_C_std_dict[key] = OP_C_std[idx]

        if OP_V_lists.size != 0:
            OP_V_mean = np.mean(OP_V_lists.reshape(-1, OP_V_lists.shape[-1]), axis=0)
            OP_V_std = np.std(OP_V_lists.reshape(-1, OP_V_lists.shape[-1]), axis=0)
            OP_V_mean_dict = {}
            OP_V_std_dict = {}
            for idx, key in enumerate(self.params_v):
                OP_V_mean_dict[key] = OP_V_mean[idx]
                OP_V_std_dict[key] = OP_V_std[idx]

        self.OP_M_mean_std = {
            'OP_M_mean': OP_M_mean_dict,
            'OP_M_std': OP_M_std_dict
        }

        if write == True:
            with open(f'{SPICE_NETLIST_DIR}/ldo_tb_op_mean_std.json', 'w') as file:
                json.dump(self.OP_M_mean_std, file)

        return OP_M_lists

# if __name__ == '__main__':