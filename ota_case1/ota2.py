#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 强化学习环境 - GraphOTA2 专用版

import torch
import numpy as np
import os
import json
from tabulate import tabulate
import gymnasium as gym
from gymnasium import spaces

from ckt_graphs import GraphOTA2
from dev_params import DeviceParams
from utils import ActionNormalizer, OutputParser_ota

from datetime import datetime

date = datetime.today().strftime('%Y-%m-%d')

PWD = os.getcwd()
SPICE_NETLIST_DIR = f'{PWD}/simulations'
os.environ['CUDA_LAUNCH_BLOCKING'] = "1"

# 【修改1】使用 GraphOTA2
CktGraph1 = GraphOTA2


class OTAEnv(gym.Env, CktGraph1, DeviceParams):

    def __init__(self):
        gym.Env.__init__(self)
        CktGraph1.__init__(self)
        DeviceParams.__init__(self, self.ckt_hierarchy)

        self.CktGraph = CktGraph1()
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=self.obs_shape, dtype=np.float64)
        self.action_space = spaces.Box(low=-1, high=1, shape=self.action_shape, dtype=np.float64)

    def _initialize_simulation(self):
        # 【修改2】初始化参数扩展为32个 (9组管子 + 2个Vbias)
        # 顺序: M0(W/L/M), M1(W/L/M), M3(W/L/M), M4(W/L/M), M5(W/L/M),
        #       M6(W/L/M), M7(W/L/M), M8(W/L/M), M9(W/L/M), VBIAS2, VBIAS3
        # 注意：这里用 action_space_low 的中间值作为初始值，你也可以自定义
        init_vals = []
        for low, high in zip(self.action_space_low, self.action_space_high):
            init_vals.append((low + high) / 2.0)

        # 解包给成员变量 (为了兼容 _get_obs 里的 self.Vb 等调用，虽然 GraphOTA2 主要用 VBIAS2/3)
        # 我们把前27个按顺序赋值，最后两个单独处理
        if len(init_vals) >= 32:
            self.W_M0, self.L_M0, self.M_M0, \
                self.W_M1, self.L_M1, self.M_M1, \
                self.W_M3, self.L_M3, self.M_M3, \
                self.W_M4, self.L_M4, self.M_M4, \
                self.W_M5, self.L_M5, self.M_M5, \
                self.W_M6, self.L_M6, self.M_M6, \
                self.W_M7, self.L_M7, self.M_M7, \
                self.W_M8, self.L_M8, self.M_M8, \
                self.W_M9, self.L_M9, self.M_M9, \
                self.VBIAS2, self.VBIAS3 = init_vals

            # 兼容旧代码的 self.Vb (如果 _get_obs 里用到的话)
            self.Vb = self.VBIAS2

        """Run the initial simulations."""
        # 传给仿真的是完整的32维数组
        self.do_simulation(np.array(init_vals))

    def _do_simulation(self, action: np.array):
        """
        GraphOTA2 电路参数映射：
        M0-M13, VBIAS2, VBIAS3
        注意：根据 ckt_graphs.py，M1=M2, M3=M10, M7=M11, M8=M12, M9=M13
        """
        # 【修改3】解包32个参数
        if len(action) == 32:
            W_M0, L_M0, M_M0, \
                W_M1, L_M1, M_M1, \
                W_M3, L_M3, M_M3, \
                W_M4, L_M4, M_M4, \
                W_M5, L_M5, M_M5, \
                W_M6, L_M6, M_M6, \
                W_M7, L_M7, M_M7, \
                W_M8, L_M8, M_M8, \
                W_M9, L_M9, M_M9, \
                VBIAS2, VBIAS3 = action
        else:
            # 容错处理
            print(f"[WARNING] Action length {len(action)} != 32")
            return

        # 整数化处理
        M_M0 = int(M_M0)
        M_M1 = int(M_M1)
        M_M3 = int(M_M3)
        M_M4 = int(M_M4)
        M_M5 = int(M_M5)
        M_M6 = int(M_M6)
        M_M7 = int(M_M7)
        M_M8 = int(M_M8)
        M_M9 = int(M_M9)

        # 宽度缩放 (假设和原版一样是 0.21 倍率，如果不对请修改)
        scale_factor = 0.21
        W_M0 = int(W_M0) * scale_factor
        W_M1 = int(W_M1) * scale_factor
        W_M3 = int(W_M3) * scale_factor
        W_M4 = int(W_M4) * scale_factor
        W_M5 = int(W_M5) * scale_factor
        W_M6 = int(W_M6) * scale_factor
        W_M7 = int(W_M7) * scale_factor
        W_M8 = int(W_M8) * scale_factor
        W_M9 = int(W_M9) * scale_factor

        # update netlist
        try:
            # 【修改4】扩展网表行数，从10行增加到20行左右，覆盖所有管子
            lines = ["" for _ in range(20)]

            # 核心管子
            lines[0] = f'.param W_M0={W_M0} L_M0={L_M0} M_M0={M_M0}\n'
            lines[1] = f'.param W_M1={W_M1} L_M1={L_M1} M_M1={M_M1}\n'
            lines[2] = f'.param W_M2={W_M1} L_M2={L_M1} M_M2={M_M1}\n'  # M2匹配M1
            lines[3] = f'.param W_M3={W_M3} L_M3={L_M3} M_M3={M_M3}\n'
            lines[4] = f'.param W_M4={W_M4} L_M4={L_M4} M_M4={M_M4}\n'
            lines[5] = f'.param W_M5={W_M5} L_M5={L_M5} M_M5={M_M5}\n'
            lines[6] = f'.param W_M6={W_M6} L_M6={L_M6} M_M6={M_M6}\n'

            # 新增管子 (M7-M13)
            lines[7] = f'.param W_M7={W_M7} L_M7={L_M7} M_M7={M_M7}\n'
            lines[8] = f'.param W_M8={W_M8} L_M8={L_M8} M_M8={M_M8}\n'
            lines[9] = f'.param W_M9={W_M9} L_M9={L_M9} M_M9={M_M9}\n'

            # 匹配管
            lines[10] = f'.param W_M10={W_M3} L_M10={L_M3} M_M10={M_M3}\n'  # M10匹配M3
            lines[11] = f'.param W_M11={W_M7} L_M11={L_M7} M_M11={M_M7}\n'  # M11匹配M7
            lines[12] = f'.param W_M12={W_M8} L_M12={L_M8} M_M12={M_M8}\n'  # M12匹配M8
            lines[13] = f'.param W_M13={W_M9} L_M13={L_M9} M_M13={M_M9}\n'  # M13匹配M9

            # 偏置电压
            lines[14] = f'.param VBIAS2={VBIAS2}\n'
            lines[15] = f'.param VBIAS3={VBIAS3}\n'

            # 电源
            lines[16] = f'.param VDD=5\n'  # 注意：GraphOTA2里 Vdd=5
            lines[17] = f'.param GND=0\n'

            # 【修改5】使用独立的网表文件 ota2_vars.spice，避免和 GraphOTA 冲突
            ota_vars_path = f'{SPICE_NETLIST_DIR}/ota2_vars.spice'
            with open(ota_vars_path, 'w') as f:
                f.writelines(lines)

            print('*** Simulations for GraphOTA2 ***')
            # 【修改6】调用独立的仿真测试台 ota2.spice (你需要确保有这个sp文件)
            # 如果没有 ota2.spice，你需要复制 ota.spice 并修改里面的 .include 来引用 ota2_vars.spice
            spice_cmd = f'cd {SPICE_NETLIST_DIR}; ngspice -b -o ota2.log ota2.spice'
            os.system(spice_cmd)
            print('*** Simulations Done! ***')
        except Exception as e:
            print(f'ERROR in _do_simulation: {e}')

    def do_simulation(self, action):
        self._do_simulation(action)
        # 注意：这里的 OutputParser_ota 也需要支持 GraphOTA2 的管子命名
        # 如果报错，可能需要检查 utils.py 里的 OutputParser
        self.sim_results = OutputParser_ota(self.CktGraph)
        self.op_results = self.sim_results.dcop(file_name='ota2_op')  # 输出文件也加个2

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
            self.action_space_high).action(action)
        action = action.astype(object)

        print(f"action (GraphOTA2): {action}")

        # 保存到成员变量以便 _get_obs 使用
        if len(action) == 32:
            self.W_M0, self.L_M0, self.M_M0, \
                self.W_M1, self.L_M1, self.M_M1, \
                self.W_M3, self.L_M3, self.M_M3, \
                self.W_M4, self.L_M4, self.M_M4, \
                self.W_M5, self.L_M5, self.M_M5, \
                self.W_M6, self.L_M6, self.M_M6, \
                self.W_M7, self.L_M7, self.M_M7, \
                self.W_M8, self.L_M8, self.M_M8, \
                self.W_M9, self.L_M9, self.M_M9, \
                self.VBIAS2, self.VBIAS3 = action
            self.Vb = self.VBIAS2  # 兼容旧代码

        self.do_simulation(action)
        observation = self._get_obs()
        info = self._get_info()
        reward = self.reward

        if reward >= 0:
            terminated = True
        else:
            terminated = False

        print(tabulate(
            [
                ['Bandwidth', self.bandwidth_result, self.bandwidth_target],
                ['Gain', self.gain_max, self.GAIN_target],
                ['CMRR', self.cmrr_max, self.cmrr_target],
                ['PM', self.pm_max, self.pm_target],
                ['Reward', reward, '']
            ],
            headers=['param', 'num', 'target'], tablefmt='orgtbl', numalign='right', floatfmt=".2f"
        ))

        return observation, reward, terminated, False, info

    def _get_obs(self):
        # 【修改7】读取 ota2 的归一化文件
        try:
            f = open(f'{SPICE_NETLIST_DIR}/ota2_op_mean_std.json')
            self.op_mean_std = json.load(f)
            self.op_mean = self.op_mean_std['OP_M_mean']
            self.op_std = self.op_mean_std['OP_M_std']
            self.op_mean = np.array([self.op_mean['id'], self.op_mean['gm'], self.op_mean['gds'], self.op_mean['vth'],
                                     self.op_mean['vdsat'], self.op_mean['vds'], self.op_mean['vgs']])
            self.op_std = np.array(
                [self.op_std['id'], self.op_std['gm'], self.op_std['gds'], self.op_std['vth'], self.op_std['vdsat'],
                 self.op_std['vds'], self.op_std['vgs']])
        except Exception as e:
            print('You need to run <_init_random_sim> for GraphOTA2 to generate ota2_op_mean_std.json')
            # print(e) # 调试用

        # 【修改8】扩展为处理 M0-M13
        # 辅助函数，避免重复代码
        def get_norm_op(key):
            op_data = self.op_results[key]
            arr = np.array([op_data['id'], op_data['gm'], op_data['gds'],
                            op_data['vth'], op_data['vdsat'], op_data['vds'], op_data['vgs']])
            return (arr - self.op_mean) / self.op_std

        # 初始化所有管子
        OP_norms = {}
        for i in range(14):  # M0 to M13
            key = f'M{i}'
            try:
                # 注意：M3/M4/M7等可能需要 np.abs，参考原版代码对 M3/M4/M5 用了 np.abs
                # 这里为了安全，除了输入对管，其他都先按原版逻辑处理
                if i in [3, 4, 5, 7, 8, 9, 10, 11, 12, 13]:
                    OP_norms[i] = (np.abs(
                        np.array([self.op_results[key]['id'], self.op_results[key]['gm'], self.op_results[key]['gds'],
                                  self.op_results[key]['vth'], self.op_results[key]['vdsat'],
                                  self.op_results[key]['vds'],
                                  self.op_results[key]['vgs']])) - self.op_mean) / self.op_std
                else:
                    OP_norms[i] = get_norm_op(key)
            except:
                OP_norms[i] = np.zeros(7)  # 容错

        # 处理电容和电压
        self.OP_Vb = self.op_results.get('VBIAS2', {}).get('dc', self.VBIAS2)
        self.OP_Vdd = self.Vdd
        self.OP_GND = self.GND

        # 归一化电容 C1
        try:
            self.OP_C1_norm = ActionNormalizer(action_space_low=self.C1_low,
                                               action_space_high=self.C1_high).reverse_action(
                self.op_results['C1']['c'])
        except:
            self.OP_C1_norm = 0.0

        # 【修改9】构建 19行 的观测矩阵 (对应 GraphOTA2 的 node 0-18)
        # node 0-13: M0-M13
        # node 14: VDDA
        # node 15: GND
        # node 16: C1
        # node 17: VBIAS2
        # node 18: VBIAS3

        # 前14行是管子
        obs_list = []
        for i in range(14):
            # 前6个是0，后7个是管子归一化参数
            row = [0, 0, 0, 0, 0, 0] + list(OP_norms[i])
            obs_list.append(row)

        # node 14: VDDA (index 14)
        obs_list.append([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, self.OP_Vdd])
        # node 15: GND (index 15)
        obs_list.append([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, self.OP_GND])
        # node 16: C1 (index 16)
        obs_list.append([0, 0, 0, 0, 0, self.OP_C1_norm, 0, 0, 0, 0, 0, 0, 0])
        # node 17: VBIAS2 (index 17)
        obs_list.append([self.VBIAS2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        # node 18: VBIAS3 (index 18)
        obs_list.append([self.VBIAS3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

        observation = np.array(obs_list)
        observation = np.clip(observation, -5, 5)
        return observation

    def _get_info(self):
        '''Evaluate the performance'''
        # 这部分逻辑通常和具体电路强相关，假设和原版保持一致
        # 如果 GraphOTA2 有不同的仿真输出解析，需要修改这里
        try:
            self.dc_results = self.sim_results.dc(file_name='ota2_dc')
        except:
            pass

        self.Vdrop = 0.0  # 默认值
        self.Vdrop_score = 0.0
        self.load_reg_score = 0.0
        self.Vload_reg_delta = 0.0

        """ bandwidth performance """
        try:
            self.bandwidth_results = self.sim_results.ac_bandwidth(file_name='ota2_bandwidth')
            freq = self.bandwidth_results[0]
            gain = self.bandwidth_results[1]
            max_gain = max(gain) if len(gain) > 0 else 0
            target_gain = max_gain - 3
            closest_index = (np.abs(np.array(gain) - target_gain)).argmin() if len(gain) > 0 else 0
            self.bandwidth_result = freq[closest_index] if len(freq) > closest_index else 0
        except:
            self.bandwidth_result = 0

        if self.rew_eng == True:
            if self.bandwidth_result < self.bandwidth_target:
                self.bandwidth_score = np.min(
                    [(self.bandwidth_result - self.bandwidth_target) / (
                                self.bandwidth_result + self.bandwidth_target + 1e-12), 0])
            else:
                self.bandwidth_score = (self.bandwidth_result - self.bandwidth_target) / (
                            self.bandwidth_result + self.bandwidth_target + 1e-12)
        else:
            self.bandwidth_score = np.min(
                [(self.bandwidth_result - self.bandwidth_target) / (
                            self.bandwidth_result + self.bandwidth_target + 1e-12), 0])

        """ cmrr performance """
        try:
            self.acm_results, self.adm_results = self.sim_results.ac_cmrr(acm_file_name='ota2_acm',
                                                                          adm_file_name='ota2_adm')
            self.acm_max = min(self.acm_results) if len(self.acm_results) > 0 else 1
            self.adm_max = max(self.adm_results) if len(self.adm_results) > 0 else 0
            if self.acm_max != 0 and (self.adm_max / self.acm_max) > 0:
                self.cmrr_max = self.adm_max / self.acm_max
            else:
                self.cmrr_max = float('-inf')
            self.cmrr_max = 20 * np.log10(self.cmrr_max) if self.cmrr_max > 0 else -100
        except:
            self.cmrr_max = -100

        if self.rew_eng == True:
            if self.cmrr_max < self.cmrr_target:
                self.cmrr_score = np.min(
                    [(self.cmrr_max - self.cmrr_target) / (self.cmrr_max + self.cmrr_target + 1e-12), 0])
            else:
                self.cmrr_score = (self.cmrr_max - self.cmrr_target) / (self.cmrr_max + self.cmrr_target + 1e-12)
        else:
            self.cmrr_score = np.min(
                [(self.cmrr_max - self.cmrr_target) / (self.cmrr_max + self.cmrr_target + 1e-12), 0])

        """ Gain performance """
        try:
            self.gain_results = self.sim_results.ac_gain(file_name='ota2_gain')
            self.gain_max = max(self.gain_results[1]) if len(self.gain_results) > 1 and len(
                self.gain_results[1]) > 0 else 0
        except:
            self.gain_max = 0

        if self.rew_eng == True:
            if self.gain_max < self.GAIN_target:
                self.gain_score = np.min(
                    [(self.gain_max - self.GAIN_target) / (self.gain_max + self.GAIN_target + 1e-12), 0])
            else:
                self.gain_score = (self.gain_max - self.GAIN_target) / (self.gain_max + self.GAIN_target + 1e-12)
        else:
            self.gain_score = np.min(
                [(self.gain_max - self.GAIN_target) / (self.gain_max + self.GAIN_target + 1e-12), 0])

        """ PM performance """
        try:
            self.pm_results = self.sim_results.ac_pm(file_name1='ota2_gain', file_name2='ota2_phase_margin')
            self.pm_freq, self.pm_gain, self.pm = self.pm_results
            closest_freq_idx = -1
            min_diff = float('inf')
            for i in range(len(self.pm_gain)):
                diff = abs(self.pm_gain[i])
                if diff < min_diff:
                    min_diff = diff
                    closest_freq_idx = i
            self.pm_max = self.pm[closest_freq_idx] + 180 if closest_freq_idx >= 0 else 0
        except:
            self.pm_max = 0

        if self.rew_eng == True:
            if self.pm_max < self.pm_target:
                self.pm_score = np.min([(self.pm_max - self.pm_target) / (self.pm_max + self.pm_target + 1e-12), 0])
            else:
                self.pm_score = (self.pm_max - self.pm_target) / (self.pm_max + self.pm_target + 1e-12)
        else:
            self.pm_score = np.min([(self.pm_max - self.pm_target) / (self.pm_max + self.pm_target + 1e-12), 0])

        """ Total reward """
        self.reward = 0.25 * self.bandwidth_score + 0.25 * self.gain_score + 0.25 * self.cmrr_score + 0.25 * self.pm_score

        if self.reward >= 0:
            self.reward = self.reward + 1

        if (self.gain_max < 0) or (self.bandwidth_result < 0) or (self.cmrr_max < 0) or (self.pm_max < 0):
            self.reward = self.reward - 1

        if (self.gain_max < self.gain_threshold): self.reward -= 0.1
        if (self.bandwidth_result < self.bandwidth_threshold): self.reward -= 0.1
        if (self.cmrr_max < self.cmrr_threshold): self.reward -= 0.1
        if (self.pm_max < self.pm_threshold): self.reward -= 0.1

        return {
            'Bandwidth': self.bandwidth_result,
            'Gain': self.gain_max,
            'CMRR': self.cmrr_max,
            'PM': self.pm_max
        }

    def _init_random_sim(self, max_sims=100, write=True):
        ''' 生成 GraphOTA2 专用的归一化文件 '''
        random_op_count = 0
        OP_M_lists = []

        # 这里简化处理，只收集 MOS 管的参数
        while random_op_count <= max_sims:
            print(f'* GraphOTA2 simulation #{random_op_count} *')
            action = np.random.uniform(self.action_space_low, self.action_space_high, self.action_dim)
            self._do_simulation(action)

            try:
                sim_results = OutputParser_ota(self.CktGraph)
                op_results = sim_results.dcop(file_name='ota2_op')

                OP_M_list = []
                # 遍历所有管子 M0-M13
                for key in list(op_results):
                    if key[0] == 'M' or key[0] == 'm':
                        try:
                            OP_M = np.array([op_results[key][f'{item}'] for item in
                                             ['id', 'gm', 'gds', 'vth', 'vdsat', 'vds', 'vgs']])
                            OP_M_list.append(OP_M)
                        except:
                            pass

                if len(OP_M_list) > 0:
                    OP_M_lists.append(np.array(OP_M_list))
            except Exception as e:
                print(f"Sim error: {e}")

            random_op_count += 1

        if len(OP_M_lists) > 0:
            OP_M_lists = np.array(OP_M_lists)
            OP_M_mean = np.mean(OP_M_lists.reshape(-1, OP_M_lists.shape[-1]), axis=0)
            OP_M_std = np.std(OP_M_lists.reshape(-1, OP_M_lists.shape[-1]), axis=0)

            OP_M_mean_dict = {}
            OP_M_std_dict = {}
            # 假设 params_mos 在 DeviceParams 里定义了，或者我们手动指定 keys
            keys = ['id', 'gm', 'gds', 'vth', 'vdsat', 'vds', 'vgs']
            for idx, key in enumerate(keys):
                OP_M_mean_dict[key] = OP_M_mean[idx]
                OP_M_std_dict[key] = OP_M_std[idx]

            self.OP_M_mean_std = {
                'OP_M_mean': OP_M_mean_dict,
                'OP_M_std': OP_M_std_dict
            }

            if write == True:
                # 【修改10】保存为 ota2 专用的 json
                with open(f'{SPICE_NETLIST_DIR}/ota2_op_mean_std.json', 'w') as file:
                    json.dump(self.OP_M_mean_std, file)
                print(f"[OK] ota2_op_mean_std.json generated!")

        return OP_M_lists