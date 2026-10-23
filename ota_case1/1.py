#单文件仿真结果处理（看仿真结果）

import os
import numpy as np
import math

PWD = os.getcwd()
SPICE_NETLIST_DIR = f'{PWD}/simulations'

def ac_gain(file_name):
    ota_ac = open(f'{SPICE_NETLIST_DIR}/{file_name}', 'r')
    lines_ac = ota_ac.readlines()
    freq = []
    gain = []
    for line in lines_ac:
        Vac = line.split(' ')
        Vac = [i for i in Vac if i != '']
        freq.append(float(Vac[0]))
        gain.append(float(Vac[1]))
    return freq, gain

def ac_bandwidth(file_name):
    ota_bandwidth = open(f'{SPICE_NETLIST_DIR}/{file_name}', 'r')
    lines_bandwidth = ota_bandwidth.readlines()
    freq = []
    bandwidth = []
    for line_bandwidth in lines_bandwidth:
        Vac = line_bandwidth.split(' ')
        Vac = [i for i in Vac if i != '']
        freq.append(float(Vac[0]))
        bandwidth.append(float(Vac[1]))

    return freq, bandwidth

def ac_pm(file_name1, file_name2):
    # AC analysis result parser
    ota_gain = open(f'{SPICE_NETLIST_DIR}/{file_name1}', 'r')
    lines_ac = ota_gain.readlines()
    freq = []
    gain = []
    for line in lines_ac:
        Vac = line.split(' ')
        Vac = [i for i in Vac if i != '']
        freq.append(float(Vac[0]))
        gain.append(float(Vac[1]))

    ota_pm = open(f'{SPICE_NETLIST_DIR}/{file_name2}', 'r')
    lines_pm = ota_pm.readlines()      
    pm = []
    for line in lines_pm:
        Vac = line.split(' ')
        Vac = [i for i in Vac if i != '']
        pm.append(float(Vac[1]))

    return freq, gain, pm

def ac_cmrr(acm_file_name, adm_file_name):
    ota_acm = open(f'{SPICE_NETLIST_DIR}/{acm_file_name}', 'r')
    lines_acm = ota_acm.readlines()
    acm = []
    for line_acm in lines_acm:
        Vac = line_acm.split(' ')
        Vac = [i for i in Vac if i != '']
        acm.append(float(Vac[1]))

    ota_adm = open(f'{SPICE_NETLIST_DIR}/{adm_file_name}', 'r')
    lines_adm = ota_adm.readlines()
    adm = []
    for line_adm in lines_adm:
        Vac = line_adm.split(' ')
        Vac = [i for i in Vac if i != '']
        adm.append(float(Vac[1]))

    return acm, adm

def op_results(op_file_name, target_names):
    ota_op = open(f'{SPICE_NETLIST_DIR}/{op_file_name}', 'r')
    lines = ota_op.readlines()

    var_index_map = {}
    values = []
    parsing_vars = False
    parsing_values = False

    for line in lines:
        line = line.strip()

        if line.startswith("Variables:"):
            parsing_vars = True
            continue
        elif line.startswith("Values:"):
            parsing_vars = False
            parsing_values = True
            continue

        if parsing_vars:
            parts = line.split()
            if len(parts) >= 2:
                idx = int(parts[0])
                name = parts[1]
                var_index_map[name] = idx

        elif parsing_values:
            # 去掉编号“0”，只收集 float 数
            parts = line.split()
            for p in parts:
                try:
                    values.append(float(p))
                except ValueError:
                    pass

    # 跳过第一个编号项（就是 index `0`）
    # 比如：0    1.116...  → 跳过这两个，留下后面的
    values = values[1:]

    # 映射目标变量名到值
    result = {}
    for name in target_names:
        if name not in var_index_map:
            raise KeyError(f"变量名 {name} 不存在")
        idx = var_index_map[name]
        if idx >= len(values):
            raise IndexError(f"{name} 索引 {idx} 超出 values 长度")
        result[name] = values[idx]

    return result

gain_results = ac_gain(file_name='ota_gain')
gain_result = max(gain_results[1])

bandwidth_results = ac_bandwidth(file_name='ota_bandwidth')
# 获取频率和增益列表
freq = bandwidth_results[0]  # 频率列表
gain = bandwidth_results[1]  # 增益列表
# 1. 找到增益中的最大值
max_gain = max(gain)
# 2. 计算最大值减 3（单位假设为dB）
target_gain = max_gain - 3
# 3. 找到最接近 target_gain 的增益，并获取其对应的频率
# 使用绝对值差值来找到最接近的增益值
closest_index = (np.abs(np.array(gain) - target_gain)).argmin()
# 4. 对应的频率即为带宽
bandwidth_result = freq[closest_index]

pm_results = ac_pm(file_name1='ota_gain',file_name2='ota_phase_margin')
# 找到相位裕度
pm_freq, pm_gain, pm = pm_results
    # 找到增益为0 dB时的频率
closest_freq_idx = -1
min_diff = float('inf')  # 初始差值设置为无穷大

for i in range(len(pm_gain)):
    diff = abs(pm_gain[i])  # 计算与0 dB的差距
    if diff < min_diff:
        min_diff = diff
        closest_freq_idx = i

    # 获取该频率对应的相位
pm_result = pm[closest_freq_idx]
pm_result += 180

acm_results, adm_results = ac_cmrr(acm_file_name='ota_acm', adm_file_name='ota_adm')
# 找到最大值
acm_max = min(acm_results)
adm_max = max(adm_results)
if acm_max != 0 and (adm_max / acm_max) > 0:
    cmrr_max = adm_max / acm_max
else:
    cmrr_max = float('-inf')
cmrr_max = 20 * np.log10(cmrr_max)

target_names = ['gm_m1', 'i(id_m1)', 'gm_m2', 'i(id_m2)', 'gm_m3', 'i(id_m3)', 'gm_m4', 'i(id_m4)', ]
op_result = op_results(op_file_name='ota_op', target_names=target_names)

m1_op = op_result['gm_m1'] / op_result['i(id_m1)']
m2_op = op_result['gm_m2'] / op_result['i(id_m2)']
m3_op = op_result['gm_m3'] / op_result['i(id_m3)']
m4_op = op_result['gm_m4'] / op_result['i(id_m4)']

print('pm_target = ', pm_result)
print('gain_result = ', gain_result)
print('bandwidth_result = ', bandwidth_result)
print('cmrr_result = ', cmrr_max)
print("m1_gm/id = ", op_result['gm_m1'] / op_result['i(id_m1)'])
print("m2_gm/id = ", op_result['gm_m2'] / op_result['i(id_m2)'])
print("m3_gm/id = ", op_result['gm_m3'] / op_result['i(id_m3)'])
print("m4_gm/id = ", op_result['gm_m4'] / op_result['i(id_m4)'])
print(SPICE_NETLIST_DIR)

result = {'bandwidth':bandwidth_result, 'gain':abs(gain_result), 'cmrr':cmrr_max, 'pm': pm_result}
# result = {'bandwidth':43651583.2, 'gain':39.02, 'cmrr':61.86, 'pm': 59.6}
target = {'bandwidth':1e6, 'gain':60, 'cmrr':80, 'pm': 60}
score = {}

for key,value in result.items():
    if value < target[key] :
         socre_ = 0.5 * (value / target[key])
         score[key] = socre_
    score[key] = (value / target[key])

for key,value in score.items():
    print(f'key:{key}, value:{value}')

FOM = math.pow(score['bandwidth'] * score['gain'] * score['cmrr'] * score['pm'], 1/4)
print(f'FOM = {FOM}')