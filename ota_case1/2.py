#得到gm/id的阈值，用于筛选潜在性能好的解

import pandas as pd
import os

PWD = os.getcwd()

def analyze_op_by_performance(csv_path):
    """
    分析性能好与性能差样本中 M1_op 和 M3_op 的数值分布情况。

    参数:
        csv_path (str): 数据集 CSV 文件路径
    """

    # 读取数据
    df = pd.read_csv(csv_path)

    # 性能指标
    good_condition = (df["Gain"] > 20) & \
                     (df["Bandwidth"] > 1e6) & \
                     (df["CMRR"] > 40) & \
                     (df["PhaseMargin"] > 40)

    # 分离出性能好的和性能差的数据
    good_df = df[good_condition]
    bad_df = df[~good_condition]

    print(f"性能良好样本数量: {len(good_df)}")
    print(f"性能较差样本数量: {len(bad_df)}\n")

    # 提取最小值
    m1_op_min = good_df["M1_op"].min()
    m3_op_min = good_df["M3_op"].min()

    print(f"性能好部分 M1_op 最小值: {m1_op_min}")
    print(f"性能好部分 M3_op 最小值: {m3_op_min}")

    # 提取最大值
    m1_op_max = good_df["M1_op"].max()
    m3_op_max = good_df["M3_op"].max()

    print(f"性能好部分 M1_op 最大值: {m1_op_max}")
    print(f"性能好部分 M3_op 最大值: {m3_op_max}")

    # 提取感兴趣的参数
    m1_op_good = good_df["M1_op"]
    m3_op_good = good_df["M3_op"]
    m1_op_bad = bad_df["M1_op"]
    m3_op_bad = bad_df["M3_op"]

    # 打印统计信息
    print("【性能良好】M1_op 和 M3_op 统计：")
    print(m1_op_good.describe())
    print(m3_op_good.describe())

    print("\n【性能较差】M1_op 和 M3_op 统计：")
    print(m1_op_bad.describe())
    print(m3_op_bad.describe())

analyze_op_by_performance(f'{PWD}/op_data/circuit_data_case1_op_retrain.csv')
