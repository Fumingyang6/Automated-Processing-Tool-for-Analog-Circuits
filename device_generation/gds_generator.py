from device_generation.Mosfet import Mosfet
from device_generation.Capacitor import Capacitor
from device_generation.Resistor import Resistor
import os


class GDSGenerator:

    def __init__(self, output_dir=None):

        if output_dir is None:
            self.output_dir = os.path.join(os.getcwd(), "gds")
        else:
            self.output_dir = output_dir

        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)

    def set_output_dir(self, output_dir):
        """设置输出目录"""
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_resistor(self, params):
        try:
            resistor = Resistor(
                series=params.get('series', False),
                name=params['name'],
                w=params['w'],
                l=params['l'],
                seg_num=params.get('seg_num', 1),
                seg_space=params.get('seg_space', 0.18),
                attr=params.get('attr', ['m'])
            )

            gds_path = os.path.join(self.output_dir, f"{params['name']}.gds")
            resistor.to_gds(gds_path)

            return True, gds_path
        except Exception as e:
            return False, str(e)

    def generate_capacitor(self, params):
        try:
            capacitor = Capacitor(
                name=params['name'],
                w=params['w'],
                sp=params['sp'],
                nf=params['nf'],
                l=params['l'],
                m_bot=params.get('m_bot', 4),
                m_top=params.get('m_top', 7),
                attr=params.get('attr', ["2t"]),
                f_tip=params.get('f_tip', 0.14),
                flatten=params.get('flatten', True)
            )

            gds_path = os.path.join(self.output_dir, f"{params['name']}.gds")
            capacitor.to_gds(gds_path)

            return True, gds_path
        except Exception as e:
            return False, str(e)

    def generate_mosfet(self, params):
        try:
            mosfet = Mosfet(
                nch=params['nch'],
                name=params['name'],
                w=params['w'],
                l=params['l'],
                nf=params['nf'],
                attr=params.get('attr', []),
                spectre=params.get('spectre', True),
                pinConType=params.get('pinConType', None),
                bulkCon=params.get('bulkCon', [0])
            )

            gds_path = os.path.join(self.output_dir, f"{params['name']}.gds")
            mosfet.to_gds(gds_path)

            return True, gds_path
        except Exception as e:
            return False, str(e)

    def generate_from_netlist_data(self, devices, base_name="netlist", progress_callback=None):
        results = {
            'success': 0,
            'failed': 0,
            'details': [],
            'output_dir': self.output_dir
        }

        netlist_dir = os.path.join(self.output_dir, base_name)
        os.makedirs(netlist_dir, exist_ok=True)
        original_dir = self.output_dir
        self.output_dir = netlist_dir

        total_devices = len(devices["resistors"]) + len(devices["capacitors"]) + len(devices["mosfets"])
        current_progress = 0

        if progress_callback:
            progress_callback(current_progress, total_devices)

        for res in devices["resistors"]:
            try:
                device_name = f"{res['subckt']}_{res['inst_name']}"
                success, result = self.generate_resistor({
                    'name': device_name,
                    'series': res['series'],
                    'w': res['w'],
                    'l': res['l'],
                    'seg_num': res['seg_num'],
                    'seg_space': res['seg_space'],
                    'attr': res['attr']
                })

                if success:
                    results['success'] += 1
                    results['details'].append(f"✓ 电阻 {device_name}: {result}")
                else:
                    results['failed'] += 1
                    results['details'].append(f"✗ 电阻 {device_name}: {result}")
            except Exception as e:
                results['failed'] += 1
                results['details'].append(f"✗ 电阻 {device_name}: 生成异常 - {str(e)}")

            current_progress += 1
            if progress_callback:
                progress_callback(current_progress, total_devices)

        # 生成电容
        for cap in devices["capacitors"]:
            try:
                device_name = f"{cap['subckt']}_{cap['inst_name']}"
                success, result = self.generate_capacitor({
                    'name': device_name,
                    'w': cap['w'],
                    'l': cap['l'],
                    'sp': cap['sp'],
                    'nf': cap['nf'],
                    'm_bot': cap['m_bot'],
                    'm_top': cap['m_top'],
                    'attr': cap['attr'],
                    'f_tip': cap.get('f_tip', 0.14),
                    'flatten': cap.get('flatten', True)
                })

                if success:
                    results['success'] += 1
                    results['details'].append(f"✓ 电容 {device_name}: {result}")
                else:
                    results['failed'] += 1
                    results['details'].append(f"✗ 电容 {device_name}: {result}")
            except Exception as e:
                results['failed'] += 1
                results['details'].append(f"✗ 电容 {device_name}: 生成异常 - {str(e)}")

            current_progress += 1
            if progress_callback:
                progress_callback(current_progress, total_devices)

        # 生成MOS管
        for mos in devices["mosfets"]:
            try:
                device_name = f"{mos['subckt']}_{mos['inst_name']}"
                success, result = self.generate_mosfet({
                    'name': device_name,
                    'nch': mos['nch'],
                    'w': mos['w'],
                    'l': mos['l'],
                    'nf': mos['nf'],
                    'attr': mos['attr'],
                    'spectre': mos['spectre'],
                    'pinConType': mos['pinConType'],
                    'bulkCon': mos['bulkCon']
                })

                if success:
                    results['success'] += 1
                    results['details'].append(f"✓ MOS管 {device_name}: {result}")
                else:
                    results['failed'] += 1
                    results['details'].append(f"✗ MOS管 {device_name}: {result}")
            except Exception as e:
                results['failed'] += 1
                results['details'].append(f"✗ MOS管 {device_name}: 生成异常 - {str(e)}")

            current_progress += 1
            if progress_callback:
                progress_callback(current_progress, total_devices)

        self.output_dir = original_dir

        return results