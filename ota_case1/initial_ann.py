#ann预测gm/id
import sys
import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
import os
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import DataLoader, TensorDataset

def resource_path(relative_path):
    """ 获取资源文件的绝对路径，兼容开发环境和 PyInstaller 打包 """
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)

PWD = resource_path('.')   # 指向该脚本所在的目录

# 加载数据
df = pd.read_csv(os.path.join(PWD, "op_data", "circuit_data_case1_op_train.csv"))
# 归一化到 [0, 1] 范围
scaler_X = MinMaxScaler()
scaler_Y = MinMaxScaler()

X = scaler_X.fit_transform(df[["W0", "L0", "M0", "W1", "L1", "M1", "W3", "L3", "M3", "W6", "L6", "M6", "vb"]])
# Y = scaler_Y.fit_transform(df[["Gain", "Bandwidth", "CMRR", "PhaseMargin", "M1_op", "M2_op", "M3_op", "M4_op"]])
# Y = scaler_Y.fit_transform(df[["M3_op"]])
Y = scaler_Y.fit_transform(df[["M1_op", "M3_op"]])
# Y = scaler_Y.fit_transform(df[["M1_op", "M2_op", "M3_op", "M4_op"]])

# 转换为 PyTorch Tensor
X_train = torch.tensor(X, dtype=torch.float32)
Y_train = torch.tensor(Y, dtype=torch.float32)

dataset = TensorDataset(X_train, Y_train)
dataloader = DataLoader(dataset, batch_size=64, shuffle=True)

# 搭建 ANN
class ANN(nn.Module):
    def __init__(self):
        super(ANN, self).__init__()
        self.fc1 = nn.Linear(13, 64)
        self.fc2 = nn.Linear(64, 128)
        self.fc3 = nn.Linear(128, 64)
        self.fc4 = nn.Linear(64, 2)  # 输出4个性能参数

        self.sigmoid = nn.Sigmoid()  # 使用Log-Sigmoid激活函数

    def forward(self, x):
        x = self.sigmoid(self.fc1(x))
        x = self.sigmoid(self.fc2(x))
        x = self.sigmoid(self.fc3(x))
        x = self.fc4(x)  # 最后一层直接输出回归结果
        return x

model = ANN()


