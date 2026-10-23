# ota_case1 · 电路参数优化

用强化学习（DDPG / SAC）训练图神经网络（GNN）策略，在 sky130 PDK + ngspice 下自动搜索
OTA 电路（M0~M6 + 补偿电容）的 13 个器件参数，使增益、带宽、CMRR、相位裕度逼近设计指标。

主界面入口：`python main_ui.py` → 左侧「电路参数优化」。

---

## 前置条件

| 依赖 | 说明 |
|---|---|
| ngspice | 仿真引擎。Windows 必须用 `ngspice_con.exe`（控制台构建），详见根目录 README |
| sky130A PDK | 用环境变量 `SKY130_PDK_DIR` 指定，未设置时默认 `~/pdk/sky130A` |
| `simulations/ota_op_mean_std.json` | `.OP` 参数归一化统计，已随仓库提供，**不要随意重新生成** |

前三项缺一不可。仓库里**没有训练好的 Actor 权重**（`saved_agents/` 只有占位说明），
`op_pth/` 里的 `.pth` 是加速环境用的 ANN 性能仿真器，不是策略网络。

---

## 界面使用步骤

1. 选「模型文件」：`.pth`（纯 state_dict）或 `.pkl`（完整 Agent 对象）。
   文件名需包含 `ActorCritic<GNN>`（如 `ActorCriticRGCN`）和 `reward=`，
   否则会被判定为无法识别；ANN 仿真器权重会被拒绝并提示。
2. 选「电路拓扑 / 节点类型 / Agent 类型 / GNN 模型 / 环境类型」。
3. 点「开始优化」，等待结果表；结束后可查看 13 个参数与性能指标。

**配置项对应关系**

| 界面项 | 可选值 | 说明 |
|---|---|---|
| 电路拓扑 | GraphOTA / GraphOTA2 / GraphOTA3 | 只有 GraphOTA 有参数名映射，另外两个显示为「电路参数_N」 |
| 节点类型 | device 级（11 节点）/ pin 级（32 节点） | 必须与训练权重时一致，否则观测形状校验会失败 |
| Agent 类型 | DDPG / SAC | 仅用于识别权重来源 |
| GNN 模型 | RGCN / GCN / GAT / MLP | 读取模型文件时会从权重结构推断 |
| 环境类型 | OTAEnv（原版）/ OTAEnv1（加速版） | 原版每次调用 ngspice；加速版用 ANN 代理模型估算 `.OP` |

---

## 优化参数

动作空间 13 维，`GraphOTA` 的取值来自 `ckt_graphs.py` 的 `action_space_low/high`：

| 索引 | 参数 | 范围 | 实际含义 |
|---|---|---|---|
| 0~2 | W_M0 / L_M0 / M_M0 | W:1~100，L:0.5~1.5，M:1~10 | M0 管（与 M5 共用） |
| 3~5 | W_M1 / L_M1 / M_M1 | 同上 | M1 管（与 M2 共用） |
| 6~8 | W_M3 / L_M3 / M_M3 | 同上 | M3 管（与 M4 共用） |
| 9~11 | W_M6 / L_M6 / M_M6 | 同上 | M6 管 |
| 12 | Vb | 1.2~1.8 V | 偏置电压 |

**宽度换算**：写进网表的宽度是 `W_real = int(W) * 0.21`（单位 µm）。
所以动作值 1 对应 0.21 µm、2 对应 0.42 µm。sky130 的 `g5v0d10v5` 是 binning 模型，
最小 bin 是 0.42 µm，**动作值 1 会找不到模型而仿真失败**，有效下限实际是 2。
路径定义见 `ckt_graphs.py`、`ota.py` 的 `_do_simulation`。

---

## 观测、指标与奖励

- 观测：`obs_shape = (节点数, 13)`，13 个特征来自每个管子的
  `id / gm / gds / vth / vdsat / vds / vgs`，用 `ota_op_mean_std.json` 做标准化。
- 设计目标（`ckt_graphs.py`）：Gain 60 dB、CMRR 80 dB、PM 60°、带宽 1 MHz。
- 奖励：各指标相对目标算 score（低于目标给负分、高于目标给正分），
  再结合压降、负载调整率等项合成；`reward >= 0` 视为达标并终止。

---

## 文件结构

| 文件 | 作用 |
|---|---|
| `ui.py` | 界面与 `OptimizeThread`：加载模型 → 建图 → 建环境 → 推理 → 输出 |
| `ota.py` | `OTAEnv`：原版环境，每次动作都真实调用 ngspice |
| `ota1.py` | `OTAEnv1`：加速环境，用 `op_pth` 里的 ANN 模型代替 `.OP` 仿真 |
| `ota2.py` | 已废弃的 LDO 环境，界面不引用（内部仍是 Linux 风格 `os.system`） |
| `ckt_graphs.py` | `GraphOTA/2/3`：节点数、动作范围、性能目标 |
| `dev_params.py` | 按器件名匹配 PDK 模型，生成 `.OP` 参数列表 |
| `utils.py` | ngspice 调用、网表生成、观测归一化、输出解析 |
| `models.py` | GNN 与 Actor/Critic 网络定义 |
| `ddpg.py` / `sac.py` | 两种强化学习 Agent |
| `main.py` / `main2.py` / `main3.py` | 训练入口：DDPG / SAC / SAC+ANN |
| `simulations/` | 网表模板 `ota.spice`、参数 `ota_vars.spice`、仿真输出（输出不入库） |
| `op_data/` | ANN 仿真器训练数据 |
| `op_pth/` | ANN 仿真器权重（随仓库提供） |

---

## 训练

```bash
# 必须在 ota_case1 目录下执行（脚本用相对路径 ./saved_agents 等）
cd ota_case1
python main.py      # DDPG
python main2.py     # SAC
python main3.py     # SAC + ANN
```

- 默认 5000 步，每步一次 ngspice 仿真，耗时较长；训练前先建好输出目录：
  `mkdir saved_weights`
- 产出：`saved_weights/Actor_*.pth`、`Critic_*.pth`，`saved_agents/*.pkl`，
  `saved_memories/*.pkl` 与 `rews_buf_*.npy`（后两类是训练中间产物，已被 `.gitignore` 忽略）
- 训练结束后把 `Actor_*.pth` 或 `*Agent_*.pkl` 交给界面的「模型文件」即可

---

## 常见问题

| 现象 | 原因与处理 |
|---|---|
| `could not find a valid modelname` | 动作里 W 太小，`int(W)*0.21 < 0.42`；检查初始值或加大 W |
| ngspice 返回码 1 且无任何输出 | 用了 GUI 版 `ngspice.exe`，换成 `ngspice_con.exe` 并加入 PATH |
| `Library /mingw64/lib/ngspice/*.cm couldn't be loaded` | MSYS2 版 `spinit` 里 codemodel 路径写死，改为本机实际路径 |
| `AttributeError: 'OTAEnv' object has no attribute 'op_mean'` | 缺 `simulations/ota_op_mean_std.json`，或被误删 |
| 观测形状与权重不匹配 | 节点类型选错（device 11 节点 / pin 32 节点），需与训练时一致 |
| 界面上选模型后提示「ANN 性能仿真器权重」 | `op_pth/*.pth` 是代理模型，不是 Actor，请选训练产出的 `Actor_*.pth` |

---

## 已知限制

- 仓库不提供预训练的 Actor，未训练权重下的优化结果等于随机采样，指标没有参考意义。
- `GraphOTA2` / `GraphOTA3` 没有中文参数名映射，结果表显示为通用编号。
- 动作下限 1 对应 0.21 µm，在 binning 模型下无有效 bin；初始化已避开该值，但策略搜索到 1 时仍会仿真失败。
