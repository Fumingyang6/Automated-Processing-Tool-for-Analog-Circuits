import sys
import subprocess
import os
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QMessageBox, QSplitter,
)
from PyQt5.QtCore import Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from device_generation.ui import CircuitUI
from device_generation.netlist_parser import NetlistParser
from device_generation.gds_generator import GDSGenerator
from ui_widgets import FileTreePanel, format_dir_tree
from ui_history import PageHistory
from ui_style import scale_px

if hasattr(sys, '_MEIPASS'):
    sys.path.append(sys._MEIPASS)
else:
    sys.path.append(os.path.dirname(__file__))

class CircuitGenerator(QWidget):
    """电路生成器主类，整合所有模块"""

    # 页面完成一次操作后通知主窗口刷新菜单状态
    state_changed = pyqtSignal()

    def __init__(self):
        # 初始化各个模块
        super().__init__()
        self.ui = CircuitUI()
        self.history = PageHistory(self)
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # ===================== 【修改】只保留 GDS 目录变量，移除文件/批量标记 =====================
        self.last_gds_dir = ""   # 记录最后一次 GDS 保存目录
        # 按钮文字改为更直观的描述
        self.open_klayout_btn = QPushButton("打开 GDS 保存文件夹")
        self.open_klayout_btn.setMinimumHeight(35)
        self.open_klayout_btn.setEnabled(False)  # 初始禁用，生成GDS后才可用
        self.open_klayout_btn.clicked.connect(self.open_gds_folder)
        # =================================================================

        self._build_layout()

        self.parser = NetlistParser()
        self.generator = GDSGenerator()
        self.connect_ui_events()

    def _build_layout(self):
        """左侧工作目录树 + 右侧原有功能区（可拖动分隔）"""
        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(10)

        splitter = QSplitter(Qt.Horizontal)

        self.file_tree = FileTreePanel(self.base_dir, title="文件目录")
        # 标题和刷新按钮横排，最小宽度跟着倍率走，避免放大后标题被挤掉
        self.file_tree.setMinimumWidth(scale_px(200))
        self.file_tree.file_activated.connect(self.open_tree_file)
        splitter.addWidget(self.file_tree)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        # 让按钮和主体区分开
        right_layout.setSpacing(10)
        right_layout.addWidget(self.ui, 1)
        right_layout.addWidget(self.open_klayout_btn)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 900])
        outer.addWidget(splitter)

    def open_tree_file(self, path):
        """双击左侧文件树：用系统默认程序打开"""
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def connect_ui_events(self):
        # 定义处理函数字典
        handlers = {
            'generate_component': self.handle_generate_component,
            'generate_capacitor': self.handle_generate_capacitor,
            'generate_mosfet': self.handle_generate_mosfet,
            'generate_from_netlist': self.handle_generate_from_netlist
        }
        self.ui.connect_signals(handlers)

    # ===================== 【重写】核心函数：打开GDS文件夹 =====================
    def open_gds_folder(self):
        """用系统文件管理器打开 GDS 保存目录（跨平台）"""
        if not self.last_gds_dir or not os.path.isdir(self.last_gds_dir):
            QMessageBox.warning(self, "提示", "暂无GDS目录，请先生成 GDS 文件！")
            return

        try:
            if sys.platform == "win32":
                os.startfile(self.last_gds_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.last_gds_dir])
            else:
                subprocess.Popen(["xdg-open", self.last_gds_dir])
        except Exception as e:
            QMessageBox.critical(self, "打开失败", f"错误详情：{str(e)}")
    # =================================================================

    # ===================== 菜单能力：打开网表 / 结果目录 =====================
    def open_result_dir(self):
        """文件 → 打开结果目录"""
        self.open_gds_folder()

    def open_netlist(self, path):
        """文件 → 打开网表：切到「网表+工艺」页并填入路径"""
        index = self.ui.ui.comboBox.findText("网表+工艺")
        if index >= 0:
            self.ui.ui.comboBox.setCurrentIndex(index)
        self.ui.ui.lineEditNetlist.setText(path)

    # ===================== 撤销 / 重做 =====================
    def can_undo(self):
        return self.history.can_undo()

    def can_redo(self):
        return self.history.can_redo()

    def undo(self):
        changed = self.history.undo()
        self.state_changed.emit()
        return changed

    def redo(self):
        changed = self.history.redo()
        self.state_changed.emit()
        return changed

    @staticmethod
    def _read_bytes(path):
        try:
            with open(path, "rb") as handle:
                return handle.read()
        except OSError:
            return None

    @staticmethod
    def _restore_file(path, previous):
        """撤销单文件操作：原来有就写回原字节，原来没有就删掉"""
        if previous is None:
            if os.path.exists(path):
                os.remove(path)
        else:
            with open(path, "wb") as handle:
                handle.write(previous)

    @staticmethod
    def _snapshot_dir(path):
        """记录目录里现有文件的内容，撤销批量生成时用来还原"""
        existed = os.path.isdir(path)
        snapshot = {}
        if existed:
            for name in os.listdir(path):
                full = os.path.join(path, name)
                if os.path.isfile(full):
                    with open(full, "rb") as handle:
                        snapshot[name] = handle.read()
        return existed, snapshot

    @staticmethod
    def _restore_dir(path, existed, snapshot):
        if os.path.isdir(path):
            for name in os.listdir(path):
                full = os.path.join(path, name)
                if os.path.isfile(full) and name not in snapshot:
                    os.remove(full)
            for name, data in snapshot.items():
                with open(os.path.join(path, name), "wb") as handle:
                    handle.write(data)
            if not existed and not os.listdir(path):
                os.rmdir(path)

    def _after_generation(self, path):
        """生成成功后：记住目录、更新按钮、刷新左侧文件树"""
        self.last_gds_dir = path if os.path.isdir(path) else os.path.dirname(path)
        self.open_klayout_btn.setEnabled(bool(self.last_gds_dir))
        self.file_tree.refresh()
        self.file_tree.reveal(path)
        self.state_changed.emit()

    def _after_undo(self, path):
        """撤销后：刷新目录状态与文件树（不删除别的文件）"""
        parent = path if os.path.isdir(path) else os.path.dirname(path)
        self.last_gds_dir = parent if os.path.isdir(parent) else ""
        self.open_klayout_btn.setEnabled(bool(self.last_gds_dir))
        self.file_tree.refresh()
        if self.last_gds_dir:
            self.file_tree.reveal(parent)
        self.state_changed.emit()

    def _record_single(self, label, method_name, params, target, previous):
        """记录一次已成功的单器件生成，供撤销 / 重做使用"""
        def redo():
            self.generator.set_output_dir(os.path.dirname(target))
            success, result = getattr(self.generator, method_name)(dict(params))
            if not success:
                raise RuntimeError(result)
            self._after_generation(result)

        def undo():
            self._restore_file(target, previous)
            self._after_undo(target)

        self.history.push(label, redo, undo)

    def _record_batch(self, label, devices, base_name, output_dir, batch_dir,
                      existed, snapshot):
        """记录一次已成功的网表批量生成（快照需在生成前拍好）"""
        def redo():
            # 批量生成会临时改 output_dir，重做前按当时的目录重新设一遍
            self.generator.set_output_dir(output_dir)
            self.generator.generate_from_netlist_data(devices, base_name)
            self._after_generation(batch_dir)

        def undo():
            self._restore_dir(batch_dir, existed, snapshot)
            self._after_undo(batch_dir)

        self.history.push(label, redo, undo)

    @staticmethod
    def _result_text(headline, path):
        """结果弹窗统一带上目录树"""
        parent = path if os.path.isdir(path) else os.path.dirname(path)
        return f"{headline}\n\n{format_dir_tree(parent, max_entries=25)}"
    # =================================================================

    def handle_generate_component(self):
        """处理生成组件按钮点击"""
        component_type = self.ui.ui.comboBox.currentText()
        if component_type == "电阻":
            self.handle_generate_resistor()
        elif component_type == "电容":
            self.handle_generate_capacitor()
        elif component_type == "MOS":
            self.handle_generate_mosfet()

    def handle_generate_resistor(self):
        """处理生成电阻"""
        params = self.ui.get_resistor_params()

        if not params['name']:
            self.ui.show_warning("输入错误", "请填写元件名称（name）")
            return

        if not params['attr']:
            self.ui.show_warning("参数错误", "请先选择 attr（wo 或 m）")
            return

        try:
            width = self.ui.validate_number(params['width'], "宽度")
            length = self.ui.validate_number(params['length'], "长度")
            segments = self.ui.validate_number(params['segments'], "段数", int)

            def is_grid_aligned(value):
                value = round(value * 1000)
                return value % 5 == 0

            if width < 0.05:
                self.ui.show_warning("参数错误", "宽度（width）必须大于等于0.05um，请重新输入！")
                return
            if not is_grid_aligned(width):
                self.ui.show_warning("参数错误", "宽度（width）必须为最小网格单位0.005um整数倍，请重新输入！")
                return
            if length < 0.05:
                self.ui.show_warning("参数错误", "长度（length）必须大于等于0.05um，请重新输入！")
                return
            if not is_grid_aligned(length):
                self.ui.show_warning("参数错误", "长度（length）必须为最小网格单位0.005um整数倍，请重新输入！")
                return

            if width is None or length is None or segments is None:
                self.ui.show_warning("输入错误", "请填写有效的数值参数！")
                return

            seg_space = float(params['seg_space'])
            if seg_space  < 0.1:
                self.ui.show_warning("参数错误", "seg_space 必须大于等于0.1um，请重新输入！")
                return
            if not is_grid_aligned(seg_space):
                self.ui.show_warning("参数错误", "段间距(seg_space)必须为最小网格单位0.005um整数倍，请重新输入！")
                return

            # 生成电阻
            generate_params = {
                'name': params['name'],
                'series': params['series'],
                'w': width,
                'l': length,
                'seg_num': segments,
                'seg_space': seg_space,
                'attr': params['attr']
            }
            target = os.path.join(
                self.generator.output_dir, f"{params['name']}.gds")
            previous = self._read_bytes(target)

            success, result = self.generator.generate_resistor(generate_params)

            if success:
                self._record_single(
                    f"生成电阻 {params['name']}", "generate_resistor",
                    generate_params, target, previous)
                self._after_generation(result)
                self.ui.show_info(
                    "成功",
                    self._result_text(f"电阻GDS文件已生成：{result}", result))
            else:
                self.ui.show_error("生成失败", f"生成过程出错：{result}")

        except ValueError as e:
            self.ui.show_warning("输入格式错误", f"参数格式错误：{str(e)}")
        except Exception as e:
            self.ui.show_error("生成失败", f"生成过程出错：{str(e)}")

    def handle_generate_capacitor(self):
        """处理生成电容"""
        params = self.ui.get_capacitor_params()

        # 验证输入
        if not params['name']:
            self.ui.show_warning("输入错误", "请填写电容名称（name）")
            return

        if not params['attr']:
            self.ui.show_warning("参数错误", "请先选择 attr（3t 或 2t）")
            return

        try:
            width = self.ui.validate_number(params['width'], "宽度")
            length = self.ui.validate_number(params['length'], "长度")
            spacing = self.ui.validate_number(params['spacing'], "间距")
            nf = self.ui.validate_number(params['nf'], "指数量", int)
            f_tip = self.ui.validate_number(params['f_tip'], "指端长度")

            if None in [width, length, spacing, nf]:
                self.ui.show_warning("输入错误", "请填写有效的数值参数！")
                return

            # ===================== 1. 定义TSMC40完整金属层规则 =====================
            METAL_RULES = {
                1: {'min_w': 0.1, 'min_sp': 0.15},
                2: {'min_w': 0.1, 'min_sp': 0.15},
                3: {'min_w': 0.1, 'min_sp': 0.15},
                4: {'min_w': 0.1, 'min_sp': 0.15},
                5: {'min_w': 0.44, 'min_sp': 0.46},
                6: {'min_w': 0.44, 'min_sp': 0.46}
            }
            GRID = 0.005
            EPS = 1e-6

            # ===================== 2. 基础参数校验 =====================
            # 指数量最小值校验
            if nf < 2:
                self.ui.show_warning("参数错误", "指数量(nf)最小为2！")
                return

            # 金属层范围校验
            m_bot = params['m_bot']
            m_top = params['m_top']
            if m_top <= m_bot:
                self.ui.show_warning("参数错误", "m_top必须大于m_bot，请重新选择！")
                return

            if m_top - m_bot + 1 != int(params['attr'][0]):
                self.ui.show_warning("参数错误", "金属层数不匹配，请重新选择！")
                return


            # ===================== 3. 自动计算最严格的规则 =====================
            # 找出选择的金属层中最大的最小宽度和最小间距
            max_min_w = 0.0
            max_min_sp = 0.0
            for layer in range(m_bot, m_top + 1):
                if METAL_RULES[layer]['min_w'] > max_min_w:
                    max_min_w = METAL_RULES[layer]['min_w']
                if METAL_RULES[layer]['min_sp'] > max_min_sp:
                    max_min_sp = METAL_RULES[layer]['min_sp']

            # 自动设置f_tip默认值（根据最严格的间距）
            if f_tip is None:
                f_tip = 0.14

            # ===================== 4. 统一参数校验（消除重复代码） =====================
            # 网格对齐校验函数
            # ✅ 100%准确，无任何精度问题
            def Ris_grid_aligned(value):
                # 1μm = 1000nm，TSMC40网格=5nm
                value= round(value * 1000)
                return value % 5 == 0

            # 宽度校验
            if width < max_min_w:
                self.ui.show_warning("参数错误",
                                     f"选择的金属层范围M{m_bot}-M{m_top}，最小宽度为{max_min_w}um！")
                return
            if not Ris_grid_aligned(width):
                self.ui.show_warning("参数错误", "宽度必须为0.005um的整数倍！")
                return

            # 长度校验
            if length < 0.1:
                self.ui.show_warning("参数错误", "长度必须大于0.1um！")
                return
            if not Ris_grid_aligned(length):
                self.ui.show_warning("参数错误", "长度必须为0.005um的整数倍！")
                return

            # 间距校验
            if spacing < max_min_sp:
                self.ui.show_warning("参数错误",
                                     f"选择的金属层范围M{m_bot}-M{m_top}，最小间距为{max_min_sp}um！")
                return
            if not Ris_grid_aligned(spacing):
                self.ui.show_warning("参数错误", "间距必须为0.005um的整数倍！")
                return

            # 指端长度校验
            if f_tip < max_min_sp:
                self.ui.show_warning("参数错误",
                                     f"指端长度最小为{max_min_sp}um！")
                return
            if not Ris_grid_aligned(f_tip):
                self.ui.show_warning("参数错误", "指端长度必须为0.005um的整数倍！")
                return

            # ===================== 5. 生成电容 =====================
            generate_params = {
                'name': params['name'],
                'w': width,
                'l': length,
                'sp': spacing,
                'nf': nf,
                'm_bot': m_bot,
                'm_top': m_top,
                'attr': params['attr'],
                'f_tip': f_tip,
                'flatten': params['flatten']
            }
            target = os.path.join(
                self.generator.output_dir, f"{params['name']}.gds")
            previous = self._read_bytes(target)

            success, result = self.generator.generate_capacitor(
                generate_params)

            if success:
                self._record_single(
                    f"生成电容 {params['name']}", "generate_capacitor",
                    generate_params, target, previous)
                self._after_generation(result)
                self.ui.show_info(
                    "成功",
                    self._result_text(f"电容GDS文件已生成：{result}", result))
            else:
                self.ui.show_error("生成失败", f"生成过程出错：{result}")

        except ValueError as e:
            self.ui.show_warning("输入格式错误", f"参数格式错误：{str(e)}")
        except Exception as e:
            self.ui.show_error("生成失败", f"生成过程出错：{str(e)}")

    def handle_generate_mosfet(self):
        """处理生成MOSFET"""
        params = self.ui.get_mosfet_params()

        # 验证MOS类型
        if not (params['is_nmos'] or params['is_pmos']):
            self.ui.show_warning("输入错误", "请选择MOS类型（NMOS/PMOS）")
            return

        # 验证名称
        if not params['name']:
            self.ui.show_warning("输入错误", "请填写MOS名称（name）")
            return

        try:
            width = self.ui.validate_number(params['width'], "宽度")
            length = self.ui.validate_number(params['length'], "长度")
            nf = self.ui.validate_number(params['nf'], "指数量", int)
            def Nis_grid_aligned(value):
                # 1μm = 1000nm，TSMC40网格=5nm
                value= round(value * 1000)
                return value % 5 == 0

            if None in [width, length, nf]:
                self.ui.show_warning("输入错误", "请填写有效的数值参数！")
                return

            if not Nis_grid_aligned(width):
                self.ui.show_warning("参数错误", "宽度必须为0.005um的整数倍！")
                return


            if not Nis_grid_aligned(length):
                self.ui.show_warning("参数错误", "长度必须为0.005um的整数倍！")
                return
            if length < 0.04:
                self.ui.show_warning("输入错误", f"栅长不能小于0.04μm！")
                return


            if params['spectre']:
                single_finger_w = width / nf
            else:
                single_finger_w = width

            if single_finger_w < 0.05:
                self.ui.show_warning("输入错误", f"单指宽度不能小于0.05μm！当前单指宽度为{single_finger_w:.3f}μm")
                return

            # 解析引脚连接类型
            pin_con_type = params['pin_con_type']
            if pin_con_type == "None":
                pin_con_type = None

            # 生成MOSFET
            generate_params = {
                'name': params['name'],
                'nch': params['is_nmos'],
                'w': width,
                'l': length,
                'nf': nf,
                'attr': params['attr'],
                'spectre': params['spectre'],
                'pinConType': pin_con_type,
                'bulk_con': params['bulk_con']
            }
            target = os.path.join(
                self.generator.output_dir, f"{params['name']}.gds")
            previous = self._read_bytes(target)

            success, result = self.generator.generate_mosfet(generate_params)

            if success:
                self._record_single(
                    f"生成 MOS 管 {params['name']}", "generate_mosfet",
                    generate_params, target, previous)
                self._after_generation(result)
                self.ui.show_info(
                    "成功",
                    self._result_text(f"MOS管GDS文件已生成：{result}", result))
            else:
                self.ui.show_error("生成失败", f"生成过程出错：{result}")

        except ValueError as e:
            self.ui.show_warning("输入格式错误", f"参数格式错误：{str(e)}")
        except Exception as e:
            self.ui.show_error("生成失败", f"生成过程出错：{str(e)}")

    def handle_generate_from_netlist(self):
        """处理从网表生成（批量GDS）"""
        self.run_netlist_generation(interactive=True)

    def run_netlist_generation(self, interactive=True):
        """从网表批量生成 GDS，返回执行结果。

        interactive=False 时不弹窗，供「一键运行全部流程」静默调用。
        返回：{"ok": bool, "success": int, "failed": int,
               "output_dir": str, "error": str}
        """
        netlist_path = self.ui.get_netlist_path()

        if not netlist_path:
            if interactive:
                self.ui.show_warning("输入错误", "请选择网表文件！")
            return {"ok": False, "success": 0, "failed": 0,
                    "output_dir": "", "error": "请选择网表文件"}

        # 设置输出目录
        output_dir = os.path.join(os.path.dirname(netlist_path), "gds")
        self.generator.set_output_dir(output_dir)

        try:
            # 解析网表
            devices = self.parser.parse_netlist(netlist_path)

            # 计算总器件数
            total_devices = len(devices["resistors"]) + len(devices["capacitors"]) + len(devices["mosfets"])

            if total_devices == 0:
                if interactive:
                    self.ui.show_info("提示", "网表中未解析到电阻、电容或MOS管！")
                return {"ok": False, "success": 0, "failed": 0,
                        "output_dir": output_dir,
                        "error": "网表中未解析到电阻、电容或MOS管"}

            # 显示并初始化进度条
            self.ui.show_progress(True)
            self.ui.update_progress(0, total_devices)

            # 使用进度回调生成器件
            base_name = os.path.splitext(os.path.basename(netlist_path))[0]

            # 生成前先记下输出子目录里已有的文件，撤销时用于还原
            batch_dir = os.path.join(output_dir, base_name)
            existed, snapshot = self._snapshot_dir(batch_dir)

            # 传递进度回调函数给生成器
            def progress_callback(current, total):
                self.ui.update_progress(current, total)

            results = self.generator.generate_from_netlist_data(
                devices,
                base_name,
                progress_callback=progress_callback
            )

            # 显示结果：数量统计 + 输出目录树
            result_message = (
                f"网表：{os.path.basename(netlist_path)}\n"
                f"电阻：{len(devices['resistors'])} 个\n"
                f"电容：{len(devices['capacitors'])} 个\n"
                f"MOS 管：{len(devices['mosfets'])} 个\n"
                f"成功 {results['success']} 个，失败 {results['failed']} 个\n\n"
                + format_dir_tree(batch_dir, max_entries=25)
            )

            self._record_batch(
                f"批量生成 {base_name}", devices, base_name,
                output_dir, batch_dir, existed, snapshot)
            self._after_generation(batch_dir)
            if interactive:
                self.ui.show_info("生成完成", result_message)

            # 如果有失败项，显示详细信息
            if results['failed'] > 0 and interactive:
                details = "\n".join([d for d in results['details'] if d.startswith("✗")])
                self.ui.show_warning("部分失败", f"以下器件生成失败：\n{details}")

            ok = results["success"] > 0
            return {
                "ok": ok,
                "success": results["success"],
                "failed": results["failed"],
                "output_dir": batch_dir,
                "error": "" if ok else "所有器件均生成失败",
            }

        except Exception as e:
            if interactive:
                self.ui.show_error("生成失败", f"生成过程出错：{str(e)}")
            return {"ok": False, "success": 0, "failed": 0,
                    "output_dir": output_dir, "error": str(e)}
        finally:
            # 重置进度条
            self.ui.reset_progress()