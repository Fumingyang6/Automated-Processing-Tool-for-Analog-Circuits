# parms —— 模拟电路自动化设计工具

模拟集成电路的自动化设计流程工具，覆盖「版图生成 → 参数优化 → 自动布局 → 自动布线」四个环节。

- 版本：v0.6
- 团队：CEDA / WHUT
- 界面：PyQt5 桌面程序

---

## 快速开始

```bash
# 1. 建虚拟环境（Python 3.10 ~ 3.12 均可）
python3.10 -m venv venv
source venv/bin/activate

# 2. 装依赖
pip install -r requirements.txt

# 3. 启动（必须在仓库根目录执行）
python main_ui.py
```

> Windows 用户可直接双击 `安装依赖.bat`（用 conda 建 3.10 环境并装 gdspy，
> gdspy 没有 Windows 的 PyPI wheel），之后双击 `启动.bat` 运行。
>
> 需要 GPU 加速时，先按 <https://pytorch.org> 选对应 CUDA 版本装好 torch，
> 再执行 `pip install -r requirements.txt`，否则可能被替换成 CPU 版。

### 系统依赖（不在 pip 里）

| 依赖 | 用途 | 不装会怎样 |
|---|---|---|
| 文泉驿微米黑字体<br>`fonts-wqy-microhei` | 界面和绘图的中文 | 中文显示成方块 |
| `ngspice` | 电路参数优化跑仿真 | 该模块不能跑 |
| sky130A PDK | 电路参数优化的器件模型 | 该模块不能跑 |

Debian/Ubuntu 装字体：

```bash
sudo apt install fonts-wqy-microhei
```

**sky130A PDK 的放置方式**（约 7.7 GB，不随仓库分发）：
通过网盘分享的文件：sky130A-pdk.tar.gz
链接: https://pan.baidu.com/s/1PAhzJP_SGyFMrfWq1CbVIA?pwd=zg7k 提取码: zg7k
解压后放在代码的目录即可

```

代码优先读 `SKY130_PDK_DIR` 环境变量，未设置时默认用 `~/pdk/sky130A`
（见 `ota_case1/utils.py` 的 `get_sky130_pdk_dir`）。压缩包解压后顶层目录
就是 `sky130A/`，**`SKY130_PDK_DIR` 要指向这个目录本身**——该目录下应当能
直接看到 `libs.tech/` 和 `libs.ref/`，不要再往里多套一层，否则网表里的
`__SKY130_PDK_DIR__/libs.tech/ngspice/...` 会找不到文件。

**Windows 上 ngspice 的两个坑**：

- 要用 `ngspice_con.exe`（控制台构建），不要用 `ngspice.exe`（GUI/Tcl 构建），
  后者在批处理模式下会静默返回 1、不产生任何输出，表现为“仿真失败但没有报错”；
  代码里 `find_ngspice_exe()` 已优先查找 `ngspice_con.exe`，把它放进 PATH 即可。
- 部分发行包（如 MSYS2 版）的 `spinit` 脚本把 codemodel 路径写死成
  `/mingw64/lib/ngspice/*.cm`，启动时打印
  `Library /mingw64/lib/ngspice/*.cm couldn't be loaded`。把该行改成
  ngspice 安装目录下的实际路径（如 `C:/your/ngspice/lib/ngspice/*.cm`）即可。


### 起不来怎么办

程序启动时会检查依赖，缺了会直接告诉你装什么。如果只看到一句
`ModuleNotFoundError`，多半是 `requirements.txt` 装漏了，重点确认这三个：

- `gdspy` —— 电路版图生成和版图查看器依赖它，**缺了程序根本起不来**
- `dgl` —— 自动布局的 DGL 环节用
- `scikit-learn` —— 电路参数优化用

---

## 四个功能模块

| 模块 | 代码目录 | 做什么 | 输入 | 输出 |
|---|---|---|---|---|
| **电路版图生成** | `device_generation/` | 由网表生成器件版图 | 网表 `.sp` / `.cdl` | `.gds` 版图 |
| **电路参数优化** | `ota_case1/` | 强化学习 + 神经网络优化 OTA 参数 | 工艺库、仿真配置 | 优化后的参数、仿真结果 |
| **自动布局** | `analog_placement/` | RSMT + 共质心约束的模拟电路布局优化 | `.sp` 网表 + `.sym` 约束 | 器件坐标、布局图 |
| **自动布线** | `rsmt_router/` | 斯坦纳树布线 → 间距合法化 → GDS | `nets.txt` + `CP_OP2.txt` | `.gds` 版图 |

### 已知限制

**电路参数优化模块受工艺库限制。** 它需要 `ngspice`（含 `ngspice_con.exe`）和
sky130 PDK，这些不在仓库里，需要自行准备（步骤见上）。其余三个模块开箱可用。

**仓库里没有训练好的 Actor 权重。** `ota_case1/saved_agents*/` 只有占位说明，
`ota_case1/op_pth/` 里是 OTAEnv1（加速版）用的 ANN 性能仿真器，不是策略网络。
想跑出真实的优化结果，需要先用 `ota_case1/main.py` 训练（默认 5000 步，
耗时较长，产出到 `saved_weights/`），或向维护者索取权重文件。没有权重时
界面仍可完成推理流程，但结果等价于随机初始化，性能指标没有参考意义。

**仿真用的 `.OP` 归一化统计已随仓库提供**
（`ota_case1/simulations/ota_op_mean_std.json`）。它必须与训练 Actor 时的统计
一致，请勿随意重新生成；只有在重新训练时才需要调用
`env._init_random_sim(100)` 覆盖它。

---

## 各模块的样例数据

| 模块 | 样例输入位置 |
|---|---|
| 自动布局 | `analog_placement/mycase/*.sp` + 同名 `.sym` |
| 自动布线 | `rsmt_router/nets.txt`（网表）+ `rsmt_router/CP_OP2.txt`（布局） |
| 参考设计 | `examples/`（见下） |

**`examples/` 是参考材料，不能直接运行。** 里面是上游流程的示例设计
（`ota1`~`ota3`、`adc1`~`adc2`、`comp`、`mockPDK`），每个目录的 `run.sh`
调用的是上游的 `flow/python/Magical.py`，那个脚本**不在本仓库里**，
本仓库也没有代码读它们的 `.json` 配置。当作设计参考和网表示例看即可。

---

## 自动布线的产物落在哪

点「一键生成」后，三个阶段各写进自己的子目录（在 `rsmt_router/` 下）：

```
rsmt_router/
├── nets.txt                              输入：网表
├── CP_OP2.txt                            输入：布局（GDS 文本格式）
├── step1_rsmt/steiner_forest_result.txt  阶段1：斯坦纳森林
├── step2_legalize/leg_cp_op2_3_result.txt 阶段2：间距合法化后
└── step3_gds/                            阶段3：GDS 产物
    ├── leg_cp_op2_routing.txt / .gds             只有走线
    └── CP_OP2_placement+routing.txt / .gds       走线 + 原版图合并
```

界面右侧的标签页可以直接查看这些 `.txt`；`.gds` 会用内置的版图查看器
按层着色渲染（滚轮缩放、双击复位、左键拖动平移、右键框选放大、可逐层显隐）。

---

## 目录结构

```
CEDA/
├── main_ui.py              主界面入口
├── ui_style.py             各页面共用的 UI 样式
├── gds_viewer.py           GDS 版图查看器
├── resource_utils.py       打包/资源路径工具
├── device_generation/      功能一：电路版图生成
├── ota_case1/              功能二：电路参数优化
├── analog_placement/       功能三：自动布局（LAYOUT/ 是算法，DGL_build/ 是图构建）
├── rsmt_router/            功能四：自动布线（pipeline.py 是流水线，routing_page.py 是界面）
├── examples/               参考设计（不可直接运行）
├── assets/                 界面图片资源
└── requirements.txt
```

---

## 开发注意事项

**必须从仓库根目录运行。** `ota_case1/`、`analog_placement/`、`rsmt_router/`
都没有 `__init__.py`（作为命名空间包解析），且 `main_ui.py` 靠
`sys.path.append` 把子目录加进搜索路径。换目录启动会 `ModuleNotFoundError`。

**不要提交大文件。** `.gitignore` 已经挡掉了模型权重（`*.pth`、`*.pt`、
`saved_weights/`）和生成的 `.gds`、仿真输出。网表（`.sp` / `.spice`）
和 `ota_case1/op_data/` 属于**输入**，是要入库的，别误删这几条例外规则。
