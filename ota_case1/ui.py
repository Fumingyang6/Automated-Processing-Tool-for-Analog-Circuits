import sys
import os
import pickle
import torch
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QFileDialog, QTextEdit, QFormLayout, QGroupBox, QHeaderView, QLineEdit,
    QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QStandardItemModel, QStandardItem
from gymnasium import spaces

try:
    from ui_style import cjk_font_family, font_pt, scale_px
except ImportError:
    # 独立调试本文件时根目录不在 sys.path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ui_style import cjk_font_family, font_pt, scale_px


# ---------------- 资源路径辅助函数 ----------------
def resource_path(relative_path):
    """ 获取资源文件的绝对路径，兼容开发环境和 PyInstaller 打包 """
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


# ---------------- 全局配置 ----------------
BASE_DIR = resource_path('.')
OUTPUT_DIR = os.path.join(BASE_DIR, "output_circuit")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------- 性能指标目标值配置 ----------------
PERFORMANCE_TARGETS = {
    "Gain (dB)": 60.0,
    "Bandwidth (Hz)": 1e6,
    "CMRR (dB)": 80.0,
    "PM (°)": 60.0,
    "Reward": 0.0
}


# ---------------- 工具函数：解析模型文件名（兼容新旧格式） ----------------
def parse_model_filename(filename):
    """
    支持两种格式：
    旧：Actor_GraphOTA_ActorCriticRGCN_reward=1.50.pth
    新：DDPGAgent_GraphOTA_2025-04-17_noise=uniform_reward=1.40_ActorCriticRGCN_rew_eng=True.pkl
    """
    result = {
        "valid": False,
        "ckt_name": "",
        "gnn_model": "",
        "reward": -999,
        "display_text": ""
    }

    # 只处理 .pth 或 .pkl
    if not (filename.endswith(".pth") or filename.endswith(".pkl")):
        return result

    # 提取文件名主体（去掉后缀）
    name_body = filename.rsplit(".", 1)[0]

    # 尝试匹配新格式：包含 ActorCritic<GNN> 和 reward=<值>
    import re

    # 查找 ActorCriticXXX
    gnn_match = re.search(r'ActorCritic(\w+)', name_body)
    if not gnn_match:
        return result
    gnn_model = gnn_match.group(1)

    # 查找 reward=<value>
    reward_match = re.search(r'reward=(-?[\d.]+)', name_body)
    if not reward_match:
        return result
    try:
        reward = float(reward_match.group(1))
    except ValueError:
        return result

    # 查找电路名：提取 Graph 开头的部分
    ckt_match = re.search(r'(Graph\w+)', name_body)
    if ckt_match:
        ckt_name = ckt_match.group(1)
    else:
        parts = name_body.split("_")
        if len(parts) >= 3 and parts[0] == "Actor":
            ckt_name = parts[1]
        else:
            return result

    display_text = f"Reward: {reward:.2f} | Circuit: {ckt_name} | Model: {gnn_model} | File: {filename}"
    result["valid"] = True
    result["ckt_name"] = ckt_name
    result["gnn_model"] = gnn_model
    result["reward"] = reward
    result["display_text"] = display_text
    return result


def infer_model_type_from_weights(file_path):
    """
    从 .pth 权重内容推断 Actor 网络类型（RGCN/GCN/GAT/MLP）。
    返回 'SIMULATOR' 表示 ANN 性能仿真器权重（OTAEnv1 内部使用，非 Actor 模型）。
    无法识别时返回 None。
    """
    try:
        if file_path.endswith(".pkl"):
            return None  # 完整 Agent 对象，不做内容推断
        sd = torch.load(file_path, map_location="cpu", weights_only=False)
        if not isinstance(sd, dict):
            return None
        keys = list(sd.keys())

        def _has(prefix):
            return any(k.startswith(prefix) for k in keys)

        def _conv1_extra(*subs):
            return any(k.startswith("conv1.") and s in k for k in keys for s in subs)

        if _has("conv1."):
            if _conv1_extra("comp", "root"):
                return "RGCN"
            if _conv1_extra("att"):
                return "GAT"
            return "GCN"
        if _has("mlp1."):
            return "MLP"
        # initial_ann.ANN 仿真器：fc1(13->64) ... fc4(64->2)
        if _has("fc1.") and _has("fc4."):
            w = sd.get("fc1.weight")
            if w is not None and tuple(w.shape) == (64, 13):
                return "SIMULATOR"
        return None
    except Exception:
        return None


# ---------------- 动态导入模块 ----------------
def get_ckt_graph_class(name, node_type="device"):
    from ckt_graphs import GraphOTA, GraphOTA2, GraphOTA3
    graph_map = {
        "GraphOTA": GraphOTA,
        "GraphOTA2": GraphOTA2,
        "GraphOTA3": GraphOTA3
    }
    return lambda: graph_map[name](node_type=node_type)


def get_env_class(name):
    """ 按需导入环境类，避免提前加载 ota1 及其依赖的 CSV """
    if name == "OTAEnv1 (加速版)":
        # ota1.py 用 os.getcwd() 定位 op_data/op_pth 资源，而 UI 可能从
        # 项目根目录启动；导入前先切换到 ota_case1 目录（路径在导入时固化）。
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        from ota1 import OTAEnv1
        return OTAEnv1
    elif name == "OTAEnv (原版)":
        from ota import OTAEnv
        return OTAEnv
    else:
        from ota import OTAEnv
        return OTAEnv


def get_actor_model_class(name):
    from models import ActorCriticRGCN, ActorCriticGCN, ActorCriticGAT, ActorCriticMLP
    model_map = {
        "RGCN": ActorCriticRGCN,
        "GCN": ActorCriticGCN,
        "GAT": ActorCriticGAT,
        "MLP": ActorCriticMLP
    }
    return model_map.get(name, ActorCriticRGCN)


# ---------------- 后台线程：确定性推理 ----------------
class OptimizeThread(QThread):
    update_log = pyqtSignal(str)
    update_result = pyqtSignal(dict)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._is_running = True

    def stop(self):
        self._is_running = False
        self.update_log.emit("[INFO] 正在停止...")

    def run(self):
        try:
            self.update_log.emit("=" * 60)
            self.update_log.emit("[OK] 开始加载配置...")
            self.update_log.emit(f"   电路拓扑: {self.config['ckt_graph']}")
            self.update_log.emit(f"   节点类型: {self.config['node_type']}")
            self.update_log.emit(f"   Agent类型: {self.config['agent_type']}")
            self.update_log.emit(f"   GNN模型: {self.config['gnn_model']}")
            self.update_log.emit(f"   环境类型: {self.config['env_type']}")
            self.update_log.emit(f"   模型文件: {os.path.basename(self.config['model_path'])}")
            self.update_log.emit("=" * 60)

            # 1. 导入并初始化电路图类
            CktGraphClass = get_ckt_graph_class(self.config['ckt_graph'], self.config['node_type'])
            ckt_graph = CktGraphClass()

            # 2. 导入并初始化环境（按需导入）
            EnvClass = get_env_class(self.config['env_type'])
            env = EnvClass()

            env.CktGraph = ckt_graph
            env.num_nodes = ckt_graph.num_nodes
            env.obs_shape = ckt_graph.obs_shape
            env.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=env.obs_shape, dtype=np.float64)

            # 3. 导入并加载Actor模型
            ActorModelClass = get_actor_model_class(self.config['gnn_model'])
            actor = ActorModelClass.Actor(ckt_graph)
            # Actor 内部模块不会自行搬到 GPU，这里统一迁移（CPU 机器上无副作用）
            actor.to(ckt_graph.device)

            model_path = self.config['model_path']
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"模型文件不存在: {model_path}")

            # ---------- 根据文件后缀加载模型权重 ----------
            self.update_log.emit("[INFO] 正在加载模型权重...")
            if model_path.endswith('.pkl'):
                # pickle 保存的完整 Agent 对象
                with open(model_path, 'rb') as f:
                    agent_obj = pickle.load(f)
                if hasattr(agent_obj, 'actor'):
                    actor.load_state_dict(agent_obj.actor.state_dict())
                    self.update_log.emit("[INFO] 成功从 Agent 对象加载 Actor 权重")
                elif hasattr(agent_obj, 'state_dict'):
                    actor.load_state_dict(agent_obj.state_dict())
                    self.update_log.emit("[INFO] 成功从 pickle state_dict 加载权重")
                else:
                    raise AttributeError("pickle 对象中未找到 Actor 或 state_dict")
            elif model_path.endswith('.pth'):
                # torch.save 的 state_dict
                state_dict = torch.load(model_path, map_location=ckt_graph.device, weights_only=False)
                actor.load_state_dict(state_dict)
                self.update_log.emit("[INFO] 成功加载 torch state_dict")
            else:
                # 未知后缀，尝试两种方式
                try:
                    state_dict = torch.load(model_path, map_location=ckt_graph.device, weights_only=False)
                    actor.load_state_dict(state_dict)
                except Exception:
                    with open(model_path, 'rb') as f:
                        obj = pickle.load(f)
                    if hasattr(obj, 'actor'):
                        actor.load_state_dict(obj.actor.state_dict())
                    else:
                        raise ValueError("无法从文件中提取模型权重")
            # ---------- 加载完成 ----------

            actor.eval()

            # 4. 获取环境初始状态
            self.update_log.emit("[INFO] 正在初始化环境...")
            # 确保环境已进行初始仿真，避免 op_results 为 None
            if not hasattr(env, 'op_results') or env.op_results is None:
                dummy_action = np.zeros(env.action_space.shape)
                env.step(dummy_action)
            state, _ = env.reset()
            # 校验：环境实际观测形状必须与所选节点类型的图表示一致，
            # 否则会在 Actor 推理时出现难解的维度错误（OTA 系列环境的
            # 观测是 pin 级 32 节点表示，需在下拉中选择 pin 级节点）
            if tuple(state.shape) != tuple(ckt_graph.obs_shape):
                raise ValueError(
                    f"环境观测形状 {state.shape} 与所选节点类型的图形状 "
                    f"{ckt_graph.obs_shape} 不一致，请在“节点类型”下拉中改选 "
                    f"与训练权重一致的表示（OTA 训练权重为 pin 级节点）")

            from utils import ActionNormalizer
            normalizer = ActionNormalizer(
                action_space_low=ckt_graph.action_space_low,
                action_space_high=ckt_graph.action_space_high
            )

            with torch.no_grad():
                if not self._is_running:
                    self.update_log.emit("[STOP] 优化已中断。")
                    return

                state_tensor = torch.FloatTensor(state).unsqueeze(0).to(ckt_graph.device)
                action_tensor = actor(state_tensor)
                action_tensor = action_tensor.clamp(-1, 1)

                # 反归一化回实际电路参数空间
                real_action = normalizer.action(action_tensor).flatten()
                for i in [2, 5, 8, 11]:
                    real_action[i] = int(np.clip(real_action[i], 1, 100))
                real_action = real_action.astype(float)

                self.update_log.emit("[INFO] 正在进行电路仿真...")
                _, reward, _, _, info = env.step(action_tensor.flatten().cpu().numpy())

            self.update_log.emit("")
            self.update_log.emit(f"[SUCCESS] 推理完成！")
            self.update_log.emit(f"          Reward: {reward:.4f}")

            # 6. 整理结果参数名
            ckt_name = self.config['ckt_graph']
            LOCAL_PARAM_MAPPING = {
                "GraphOTA": [
                    "W_M0 (M0管宽度)", "L_M0 (M0管长度)", "M_M0 (M0管倍数)",
                    "W_M1 (M1/M2管宽度)", "L_M1 (M1/M2管长度)", "M_M1 (M1/M2管倍数)",
                    "W_M3 (M3/M4管宽度)", "L_M3 (M3/M4管长度)", "M_M3 (M3/M4管倍数)",
                    "W_M6 (M6管宽度)", "L_M6 (M6管长度)", "M_M6 (M6管倍数)",
                    "Vb (偏置电压)"
                ]
            }

            if ckt_name in LOCAL_PARAM_MAPPING and len(LOCAL_PARAM_MAPPING[ckt_name]) == len(real_action):
                param_names = LOCAL_PARAM_MAPPING[ckt_name]
            else:
                param_names = [f"电路参数_{i + 1}" for i in range(len(real_action))]

            params_dict = {name: float(val) for name, val in zip(param_names, real_action)}

            result = {
                "params": params_dict,
                "performance": {
                    "Gain": info.get("Gain", 0),
                    "Bandwidth": info.get("Bandwidth", 0),
                    "CMRR": info.get("CMRR", 0),
                    "PM": info.get("PM", 0),
                    "Reward": reward
                },
                "action": real_action,
                "config": self.config,
                "param_names": param_names,
                "info": info
            }

            self.update_result.emit(result)
            self.finished_signal.emit()

        except Exception as e:
            import traceback
            self.error_signal.emit(f"[ERROR] {str(e)}\n{traceback.format_exc()}")


# ---------------- 主窗口（其余部分保持不变） ----------------
class CircuitOptWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.optimize_thread = None
        self.has_valid_result = False
        self.selected_model_path = ""
        self.parsed_model_info = None
        # 一键全流程用：静默模式下不弹中间提示，结果/错误记在属性里
        self.silent_mode = False
        self.last_model_error = ""
        self.last_run_error = ""
        self.last_result = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        title = QLabel("模拟电路自动优化平台")
        title.setFont(QFont(cjk_font_family(), font_pt(18), QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        self.init_config_tab()
        self.init_result_tab()

    def init_config_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        config_group = QGroupBox("核心配置")
        config_layout = QFormLayout(config_group)

        self.ckt_combo = QComboBox()
        self.ckt_combo.addItems(["GraphOTA", "GraphOTA2", "GraphOTA3"])
        config_layout.addRow("电路拓扑：", self.ckt_combo)

        self.node_type_combo = QComboBox()
        model = QStandardItemModel()
        device_item = QStandardItem("device级节点（器件级）")
        device_item.setData("device", Qt.UserRole)
        model.appendRow(device_item)
        pin_item = QStandardItem("pin级节点")
        pin_item.setData("pin", Qt.UserRole)
        model.appendRow(pin_item)
        self.node_type_combo.setModel(model)
        self.node_type_combo.setCurrentIndex(0)
        config_layout.addRow("节点类型：", self.node_type_combo)

        self.agent_combo = QComboBox()
        self.agent_combo.addItems(["DDPG", "SAC"])
        config_layout.addRow("Agent类型：", self.agent_combo)

        self.gnn_combo = QComboBox()
        self.gnn_combo.addItems(["RGCN", "GCN", "GAT", "MLP"])
        config_layout.addRow("GNN模型：", self.gnn_combo)

        self.env_combo = QComboBox()
        self.env_combo.addItems(["OTAEnv (原版)", "OTAEnv1 (加速版)"])
        config_layout.addRow("环境类型：", self.env_combo)

        layout.addWidget(config_group)

        # ---------- 手动选择模型文件 ----------
        model_group = QGroupBox("模型文件选择")
        model_layout = QVBoxLayout(model_group)

        file_sel_layout = QHBoxLayout()
        self.model_path_edit = QLineEdit()
        self.model_path_edit.setReadOnly(True)
        self.model_path_edit.setPlaceholderText("请选择训练好的 Actor 模型文件 (.pth / .pkl)")
        self.browse_model_btn = QPushButton("浏览...")
        self.browse_model_btn.clicked.connect(self.browse_model_file)
        file_sel_layout.addWidget(self.model_path_edit)
        file_sel_layout.addWidget(self.browse_model_btn)
        model_layout.addLayout(file_sel_layout)

        self.model_info_label = QLabel("模型信息：未选择")
        self.model_info_label.setStyleSheet("color: #555;")
        model_layout.addWidget(self.model_info_label)

        layout.addWidget(model_group)

        self.optimize_btn = QPushButton("开始生成最优电路")
        self.optimize_btn.setFont(QFont(cjk_font_family(), font_pt(14), QFont.Bold))
        self.optimize_btn.setMinimumHeight(scale_px(50))
        self.optimize_btn.clicked.connect(self.start_optimize)
        layout.addWidget(self.optimize_btn)

        log_group = QGroupBox("优化日志")
        log_layout = QVBoxLayout(log_group)
        log_btn_layout = QHBoxLayout()
        log_label = QLabel("日志：")
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.clicked.connect(self.clear_log)
        log_btn_layout.addWidget(log_label)
        log_btn_layout.addStretch()
        log_btn_layout.addWidget(clear_log_btn)
        log_layout.addLayout(log_btn_layout)

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setPlaceholderText("优化日志会显示在这里...")
        log_layout.addWidget(self.log_edit)
        layout.addWidget(log_group)

        # 配置项较多：窗口较矮或字号放大时，内容会超出可用高度，
        # 按钮会被压缩到文字显示不全。放进滚动区后按钮始终保持自身高度。
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }")
        scroll.viewport().setAutoFillBackground(False)
        scroll.setWidget(tab)
        self.tab_widget.addTab(scroll, "配置")

    def browse_model_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择Actor模型文件", "",
            "模型文件 (*.pth *.pkl);;所有文件 (*.*)"
        )
        if not file_path:
            return
        self.set_model_file(file_path, interactive=True)

    def set_model_file(self, file_path, interactive=True):
        """设置 Actor 模型文件，返回是否可用。

        interactive=False 时不弹窗，失败原因写进 last_model_error，
        供「一键运行全部流程」判断。
        """
        self.last_model_error = ""
        if not file_path or not os.path.exists(file_path):
            self.last_model_error = "模型文件不存在"
            if interactive:
                QMessageBox.warning(self, "模型无效", "模型文件不存在。")
            return False

        filename = os.path.basename(file_path)
        parsed = parse_model_filename(filename)
        if not parsed["valid"]:
            # 文件名不含标准信息时，尝试从权重结构推断模型类型
            inferred = infer_model_type_from_weights(file_path)
            if inferred == "SIMULATOR":
                self.last_model_error = (
                    f"文件 {filename} 是 ANN 性能仿真器权重，"
                    "不是 Actor 智能体模型")
                if interactive:
                    QMessageBox.warning(
                        self, "文件类型不符",
                        f"文件 {filename} 是 ANN 性能仿真器权重（OTAEnv1 加速版内部自动加载，"
                        f"无需手动选择），不是 Actor 智能体模型。\n"
                        f"请在保存的 Agent 目录中选择 Actor 模型文件。")
                return False
            if inferred is None:
                self.last_model_error = f"文件 {filename} 无法解析为 Actor 模型"
                if interactive:
                    QMessageBox.warning(
                        self, "模型无效",
                        f"文件 {filename} 无法解析，请确认文件名包含 'ActorCritic<GNN>' 和 'reward=<值>'，"
                        f"或是有效的 Actor 权重文件。")
                return False
            parsed["valid"] = True
            parsed["gnn_model"] = inferred
            self.log_edit.append(
                f"[INFO] 文件名未含模型信息，已从权重结构自动推断 GNN 模型: {inferred}")

        self.selected_model_path = file_path
        self.parsed_model_info = parsed
        self.model_path_edit.setText(file_path)

        info_text = (f"电路: {parsed['ckt_name']} | GNN: {parsed['gnn_model']} | "
                     f"Reward: {parsed['reward']:.2f}")
        self.model_info_label.setText(info_text)
        self.model_info_label.setStyleSheet("color: #1a73e8; font-weight: bold;")

        ckt_index = self.ckt_combo.findText(parsed['ckt_name'])
        if ckt_index >= 0:
            self.ckt_combo.setCurrentIndex(ckt_index)
        gnn_index = self.gnn_combo.findText(parsed['gnn_model'])
        if gnn_index >= 0:
            self.gnn_combo.setCurrentIndex(gnn_index)

        self.log_edit.append(f"[OK] 已选择模型: {filename}")
        return True

    def _worker_running(self):
        thread = self.optimize_thread
        return thread is not None and thread.isRunning()

    def init_result_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        label = QLabel("最优电路设计结果")
        label.setFont(QFont(cjk_font_family(), font_pt(16)))
        layout.addWidget(label)

        split_layout = QHBoxLayout()

        param_group = QGroupBox("电路参数")
        param_layout = QVBoxLayout(param_group)
        self.param_table = QTableWidget(13, 2)
        self.param_table.setHorizontalHeaderLabels(["参数名", "值"])
        header = self.param_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        default_params = ["W0", "L0", "M0", "W1", "L1", "M1", "W3", "L3", "M3", "W6", "L6", "M6", "vb"]
        for i, p in enumerate(default_params):
            self.param_table.setItem(i, 0, QTableWidgetItem(p))
        param_layout.addWidget(self.param_table)
        split_layout.addWidget(param_group)

        perf_group = QGroupBox("电路性能指标")
        perf_layout = QVBoxLayout(perf_group)
        self.perf_table = QTableWidget(5, 3)
        self.perf_table.setHorizontalHeaderLabels(["指标名", "当前值", "目标值"])
        perf_header = self.perf_table.horizontalHeader()
        perf_header.setSectionResizeMode(QHeaderView.Stretch)
        perfs = ["Gain (dB)", "Bandwidth (Hz)", "CMRR (dB)", "PM (°)", "Reward"]
        for i, p in enumerate(perfs):
            self.perf_table.setItem(i, 0, QTableWidgetItem(p))
            target_val = PERFORMANCE_TARGETS.get(p, "-")
            if isinstance(target_val, float) and p == "Bandwidth (Hz)":
                target_str = f"{target_val:.0e}"
            elif isinstance(target_val, float):
                target_str = f"{target_val:.2f}"
            else:
                target_str = str(target_val)
            self.perf_table.setItem(i, 2, QTableWidgetItem(target_str))
        perf_layout.addWidget(self.perf_table)
        split_layout.addWidget(perf_group)

        layout.addLayout(split_layout)

        self.export_btn = QPushButton("SPICE NETLIST")
        self.export_btn.setMinimumHeight(scale_px(40))
        self.export_btn.clicked.connect(self.export_spice)
        self.export_btn.setEnabled(False)
        layout.addWidget(self.export_btn)

        self.tab_widget.addTab(tab, "结果")

    def start_optimize(self):
        """启动参数优化，返回是否成功启动（供一键全流程判断）"""
        if self._worker_running():
            if not self.silent_mode:
                QMessageBox.warning(self, "警告", "参数优化正在运行中，请等待完成。")
            return False

        if not self.selected_model_path:
            if not self.silent_mode:
                QMessageBox.warning(self, "警告", "请先选择模型文件！")
            return False

        index = self.node_type_combo.currentIndex()
        selected_node_type = self.node_type_combo.itemData(index, Qt.UserRole)

        config = {
            "ckt_graph": self.ckt_combo.currentText(),
            "node_type": selected_node_type,
            "agent_type": self.agent_combo.currentText(),
            "gnn_model": self.gnn_combo.currentText(),
            "env_type": self.env_combo.currentText(),
            "model_path": self.selected_model_path
        }

        # 新一轮开始：先清掉上一轮的成功标记，避免全流程误判
        self.has_valid_result = False
        self.last_result = None
        self.last_run_error = ""
        self.export_btn.setEnabled(False)
        self.log_edit.clear()

        self.optimize_thread = OptimizeThread(config)
        self.optimize_thread.update_log.connect(self.append_log)
        self.optimize_thread.update_result.connect(self.show_result)
        self.optimize_thread.error_signal.connect(self.show_error)
        self.optimize_thread.start()

        self.optimize_btn.setEnabled(False)
        self.optimize_btn.setText("正在优化中...")
        return True

    def append_log(self, text):
        self.log_edit.append(text)

    def clear_log(self):
        self.log_edit.clear()

    def show_result(self, result):
        params = result["params"]
        param_names = result["param_names"]
        self.param_table.setRowCount(len(param_names))
        for i, name in enumerate(param_names):
            self.param_table.setItem(i, 0, QTableWidgetItem(name))
            self.param_table.setItem(i, 1, QTableWidgetItem(f"{params[name]:.4f}"))
        self.param_table.resizeColumnsToContents()

        perf = result["performance"]
        perf_names = ["Gain (dB)", "Bandwidth (Hz)", "CMRR (dB)", "PM (°)", "Reward"]
        thresholds = [
            PERFORMANCE_TARGETS["Gain (dB)"],
            PERFORMANCE_TARGETS["Bandwidth (Hz)"],
            PERFORMANCE_TARGETS["CMRR (dB)"],
            PERFORMANCE_TARGETS["PM (°)"],
            PERFORMANCE_TARGETS["Reward"]
        ]
        perf_values = [
            f"{perf['Gain']:.2f}",
            f"{perf['Bandwidth']:.2e}",
            f"{perf['CMRR']:.2f}",
            f"{perf['PM']:.2f}",
            f"{perf['Reward']:.2f}"
        ]

        for i, v in enumerate(perf_values):
            item_val = QTableWidgetItem(v)
            try:
                val = float(perf[perf_names[i].split(' ')[0]]) if i < 4 else float(perf['Reward'])
                if (i < 4 and val >= thresholds[i]) or (i == 4 and val >= 0):
                    item_val.setBackground(QColor(0, 255, 0, 50))
                else:
                    item_val.setBackground(QColor(255, 0, 0, 50))
            except:
                pass
            self.perf_table.setItem(i, 1, item_val)

        self.optimize_btn.setEnabled(True)
        self.optimize_btn.setText("开始生成最优电路")
        self.tab_widget.setCurrentIndex(1)
        self.has_valid_result = True
        self.last_result = result
        self.export_btn.setEnabled(True)

    def show_error(self, error):
        self.last_run_error = error
        self.has_valid_result = False
        if not self.silent_mode:
            QMessageBox.critical(self, "运行错误", error)
        self.optimize_btn.setEnabled(True)
        self.optimize_btn.setText("开始生成最优电路")

    def export_spice(self):
        if not self.has_valid_result:
            QMessageBox.warning(self, "无法导出", "请先点击「开始生成最优电路」，获得优化结果后再导出！")
            return
        if self.param_table.rowCount() == 0 or self.param_table.item(0, 1) is None:
            QMessageBox.warning(self, "警告", "参数表格为空，请先运行优化！")
            return

        params = {}
        raw_value_list = []
        for i in range(self.param_table.rowCount()):
            name_item = self.param_table.item(i, 0)
            value_item = self.param_table.item(i, 1)
            if name_item and value_item:
                full_name = name_item.text()
                val = value_item.text()
                clean_key = full_name.split(' ')[0].split('(')[0]
                params[clean_key] = val
                raw_value_list.append(val)

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出SPICE网表",
            os.path.join(OUTPUT_DIR, "optimal_circuit.sp"),
            "SPICE Files (*.sp *.spice);;All Files (*.*)"
        )
        if not file_path:
            return

        config = self.ckt_combo.currentText()
        spice_header = f"""
* 最优电路设计 - 自动生成
* 配置：{config} | {self.agent_combo.currentText()} | {self.gnn_combo.currentText()}
* 参数列表：
"""
        for name, val in params.items():
            spice_header += f"* {name} = {val}\n"

        vb_val = "0.0"
        for possible_key in ['Vb', 'vb', 'Vb (偏置电压)', 'VBIAS2', 'VBIAS3']:
            if possible_key in params:
                vb_val = params[possible_key]
                break
        if len(raw_value_list) > 0:
            vb_val = raw_value_list[-1]

        spice_template = spice_header + f"""
* 电源定义
VDD VDD 0 1.8V
VSS VSS 0 0V
VB VB 0 {vb_val}V

* 仿真设置
.ac dec 10 1Hz 1GHz
.print ac vdb(OUT) vp(OUT)
.end
        """
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(spice_template)

        QMessageBox.information(self, "导出成功", f"SPICE网表已保存到：\n{file_path}")


# ========== 独立调试入口 ==========
if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont(cjk_font_family(), 10)
    app.setFont(font)
    window = CircuitOptWindow()
    window.setWindowTitle("模拟电路自动优化平台")
    window.resize(1000, 800)
    window.show()
    sys.exit(app.exec_())