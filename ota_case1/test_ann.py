import torch
import torch.nn as nn
from initial_ann import ANN
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import MinMaxScaler
from sklearn.preprocessing import StandardScaler

PWD = os.getcwd()
SPICE_NETLIST_DIR = f'{PWD}'

# def ac_gain(file_name):
#     ota_ac = open(f'{SPICE_NETLIST_DIR}/{file_name}', 'r')
#     lines_ac = ota_ac.readlines()
#     freq = []
#     gain = []
#     for line in lines_ac:
#         Vac = line.split(' ')
#         Vac = [i for i in Vac if i != '']
#         freq.append(float(Vac[0]))
#         gain.append(float(Vac[1]))
#     return freq, gain
#
# def ac_bandwidth(file_name):
#     ota_bandwidth = open(f'{SPICE_NETLIST_DIR}/{file_name}', 'r')
#     lines_bandwidth = ota_bandwidth.readlines()
#     freq = []
#     bandwidth = []
#     for line_bandwidth in lines_bandwidth:
#         Vac = line_bandwidth.split(' ')
#         Vac = [i for i in Vac if i != '']
#         freq.append(float(Vac[0]))
#         bandwidth.append(float(Vac[1]))
#
#     return freq, bandwidth
#
# def ac_pm(file_name1, file_name2):
#     # AC analysis result parser
#     ota_gain = open(f'{SPICE_NETLIST_DIR}/{file_name1}', 'r')
#     lines_ac = ota_gain.readlines()
#     freq = []
#     gain = []
#     for line in lines_ac:
#         Vac = line.split(' ')
#         Vac = [i for i in Vac if i != '']
#         freq.append(float(Vac[0]))
#         gain.append(float(Vac[1]))
#
#     ota_pm = open(f'{SPICE_NETLIST_DIR}/{file_name2}', 'r')
#     lines_pm = ota_pm.readlines()
#     pm = []
#     for line in lines_pm:
#         Vac = line.split(' ')
#         Vac = [i for i in Vac if i != '']
#         pm.append(float(Vac[1]))
#
#     return freq, gain, pm
#
# def ac_cmrr(acm_file_name, adm_file_name):
#     ota_acm = open(f'{SPICE_NETLIST_DIR}/{acm_file_name}', 'r')
#     lines_acm = ota_acm.readlines()
#     acm = []
#     for line_acm in lines_acm:
#         Vac = line_acm.split(' ')
#         Vac = [i for i in Vac if i != '']
#         acm.append(float(Vac[1]))
#
#     ota_adm = open(f'{SPICE_NETLIST_DIR}/{adm_file_name}', 'r')
#     lines_adm = ota_adm.readlines()
#     adm = []
#     for line_adm in lines_adm:
#         Vac = line_adm.split(' ')
#         Vac = [i for i in Vac if i != '']
#         adm.append(float(Vac[1]))
#
#     return acm, adm

# 加载数据
# df = pd.read_csv("test_data_combined2.csv")
df = pd.read_csv(f"{PWD}/op_data/circuit_data_case1_op_test.csv")


scaler = StandardScaler()

# 归一化到 [0, 1] 范围
scaler_X = MinMaxScaler()
scaler_Y = MinMaxScaler()

X = scaler_X.fit_transform(df[["W0", "L0", "M0", "W1", "L1", "M1", "W3", "L3", "M3", "W6", "L6", "M6", "vb"]])
# Y = scaler_Y.fit_transform(df[["M3_op"]])
Y = scaler_Y.fit_transform(df[["M1_op", "M3_op"]])
# Y = scaler_Y.fit_transform(df[["M1_op", "M2_op", "M3_op", "M4_op"]])

# 转换为 PyTorch Tensor
X_train = torch.tensor(X, dtype=torch.float32)
Y_train = torch.tensor(Y, dtype=torch.float32)

Y_actual = scaler_Y.inverse_transform(Y)  # 反归一化后的实际值
# print("实际：", Y_actual)
Y_actual_scaled = scaler.fit_transform(Y_actual)


simulator = ANN()
simulator.load_state_dict(torch.load(f"{PWD}/op_pth/case1_model_ea_op.pth", weights_only=True))
simulator.eval()

# 进行推理和反归一化
with torch.no_grad():
    predictions = simulator(X_train).numpy()
    predictions = scaler_Y.inverse_transform(predictions)
    predictions_scaled = scaler.transform(predictions)
    print("示例预测结果：", predictions)

# # 计算均方误差（MSE）
#     mse = mean_squared_error(Y_actual_scaled, predictions_scaled)
# print(f"测试集的均方误差 (MSE): {mse:.4f}")
#
# mse_bandwidth = mean_squared_error(Y_actual_scaled[:, 1], predictions_scaled[:, 1])
# print(f"带宽的 MSE: {mse_bandwidth:.4f}")
#
# mse_gain = mean_squared_error(Y_actual_scaled[:, 0], predictions_scaled[:, 0])
# print(f"增益的 MSE: {mse_gain:.4f}")
#
# mse_cmrr = mean_squared_error(Y_actual_scaled[:, 2], predictions_scaled[:, 2])
# print(f"CMRR的 MSE: {mse_cmrr:.4f}")
#
# mse_pm = mean_squared_error(Y_actual_scaled[:, 3], predictions_scaled[:, 3])
# print(f"PM的 MSE: {mse_pm:.4f}")

# 计算均方误差（MSE）
    mse = mean_squared_error(Y_actual_scaled, predictions_scaled)
print(f"测试集的均方误差 (MSE): {mse:.4f}")

mse_m1 = mean_squared_error(Y_actual_scaled[:, 0], predictions_scaled[:, 0])
print(f"M1的 MSE: {mse_m1:.4f}")

mse_m3 = mean_squared_error(Y_actual_scaled[:, 1], predictions_scaled[:, 1])
print(f"M3的 MSE: {mse_m3:.4f}")

# mse_m2 = mean_squared_error(Y_actual_scaled[:, 1], predictions_scaled[:, 1])
# print(f"M2的 MSE: {mse_m2:.4f}")
#
# mse_m3 = mean_squared_error(Y_actual_scaled[:, 2], predictions_scaled[:, 2])
# print(f"M3的 MSE: {mse_m3:.4f}")
#
# mse_m4 = mean_squared_error(Y_actual_scaled[:, 3], predictions_scaled[:, 3])
# print(f"M4的 MSE: {mse_m4:.4f}")


# 计算残差（实际值 - 预测值）
residuals = Y_actual - predictions

# 画残差图
plt.figure(figsize=(14, 6))
plt.scatter(range(len(residuals)), residuals[:, 0], color="b", alpha=0.6, label="M1")
plt.scatter(range(len(residuals)), residuals[:, 1], color="g", alpha=0.6, label="M3")
# plt.scatter(range(len(residuals)), residuals[:, 2], color="r", alpha=0.6, label="CMRR")
# plt.scatter(range(len(residuals)), residuals[:, 3], color="purple", alpha=0.6, label="PhaseMargin")
plt.axhline(0, color='black', linestyle='--', linewidth=1)
plt.xlabel("test sample index")
plt.ylabel("res")
plt.title("res_picture")
plt.legend()
plt.grid(True)
plt.savefig(f"{PWD}/op_pth/case1_M1+M3_res")
plt.show()

# simulator = ANN()
# simulator.load_state_dict(torch.load("ann_model_ea.pth", weights_only=True))
# simulator.eval()
#
# # # 测试：预测和反归一化
# # with torch.no_grad():
# #     model.eval()
# #     predictions = model(X_train)
# #     predictions = scaler_Y.inverse_transform(predictions.numpy())  # 反归一化得到真实预测值
# #     print("示例预测结果：", predictions[:5])
#
# test_input = torch.tensor([
#     [10, 1.2, 2, 20, 0.8, 5, 30, 0.72, 4, 15, 0.5, 8, 1.27],  # "W0", "L0", "M0", "W1", "L1", "M1", "W3", "L3", "M3", "W6", "L6", "M6", "vb"
# ], dtype=torch.float32)
#
# # 进行推理
# with torch.no_grad():
#     predictions = simulator(test_input)
#     predictions = scaler_Y.inverse_transform(predictions.numpy())  # 反归一化得到真实预测值
#
# print("模型预测输出:", predictions[:5])
#
# gain_results = ac_gain(file_name='test_gain')
# gain_result = max(gain_results[1])
#
# bandwidth_results = ac_bandwidth(file_name='test_bandwidth')
# # 获取频率和增益列表
# freq = bandwidth_results[0]  # 频率列表
# gain = bandwidth_results[1]  # 增益列表
# # 1. 找到增益中的最大值
# max_gain = max(gain)
# # 2. 计算最大值减 3（单位假设为dB）
# target_gain = max_gain - 3
# # 3. 找到最接近 target_gain 的增益，并获取其对应的频率
# # 使用绝对值差值来找到最接近的增益值
# closest_index = (np.abs(np.array(gain) - target_gain)).argmin()
# # 4. 对应的频率即为带宽
# bandwidth_result = freq[closest_index]
#
# pm_results = ac_pm(file_name1='test_gain',file_name2='test_phase_margin')
# # 找到相位裕度
# pm_freq, pm_gain, pm = pm_results
#     # 找到增益为0 dB时的频率
# closest_freq_idx = -1
# min_diff = float('inf')  # 初始差值设置为无穷大
#
# for i in range(len(pm_gain)):
#     diff = abs(pm_gain[i])  # 计算与0 dB的差距
#     if diff < min_diff:
#         min_diff = diff
#         closest_freq_idx = i
#
#     # 获取该频率对应的相位
# pm_result = pm[closest_freq_idx]
# pm_result += 180
#
# acm_results, adm_results = ac_cmrr(acm_file_name='test_acm', adm_file_name='test_adm')
# # 找到最大值
# acm_max = min(acm_results)
# adm_max = max(adm_results)
# if acm_max != 0 and (adm_max / acm_max) > 0:
#     cmrr_max = adm_max / acm_max
# else:
#     cmrr_max = float('-inf')
# cmrr_max = 20 * np.log10(cmrr_max)
#
# print('gain_result = ', gain_result)
# print('bandwidth_result = ', bandwidth_result)
# print('cmrr_result = ', cmrr_max)
# print('pm_target = ', pm_result)