#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

This one is for SKY130 process.

You can just run it once to generate the script for the DCOP analysis.
    # 这部分实现的功能是：
    # 1、将自定义的图结构写入到ckt_hierarchy中备用
    # 2、通过gen_dev_params匹配ckt_hierarchy中M/C/V的器件参数（匹配到所使用的模型），写入到ldo_tb_dev_params.spice中
    # 3、输入是ckt_graphs.py中的自定义图结构，输出是将匹配到的节点相关信息写入ldo_tb_dev_params.spice
    # 4、函数gen_dev_params中的另一个参数file_name写入到ldo_tb_dev_params.spice的最后一行，作用是？
"""

from ckt_graphs import GraphOTA, GraphOTA2, GraphOTA3


class DeviceParams(object):
    def __init__(self, ckt_hierarchy, warning_msg=False):
        self.ckt_hierarchy = ckt_hierarchy
        self.dev_names_mos = (
            'nfet3_01v8',
            'nfet3_01v8_lvt',
            'nfet3_03v3_nvt',
            'nfet3_05v0_nvt',
            'nfet3_20v0',
            'nfet3_g5v0d10v5',
            'nfet3_g5v0d16v0',
            'nfet_01v8',
            'nfet_01v8_esd',
            'nfet_01v8_lvt',
            'nfet_01v8lvt_nf'
            'nfet_01v8_nf',
            'nfet_03v3_nvt',
            'nfet_03v3_nvt_nf',
            'nfet_05v0_nvt',
            'nfet_05v0_nvt_nf',
            'nfet_20v0_iso',
            'nfet_20v0_nvt',
            'nfet_20v0_zvt',
            'nfet_g5v0d10v5',
            'nfet_g5v0d10v5_esd',
            'nfet_g5v0d10v5_nf',
            'nfet_g5v0d10v5_nvt_esd',
            'nfet_g5v0d16v0',
            'nfet_g5v0d16v0_nf',
            'pfet3_01v8',
            'pfet3_01v8',
            'pfet3_01v8',
            'pfet3_20v0',
            'pfet3_g5v0d10v5',
            'pfet3_g5v0d16v0',
            'pfet_01v8',
            'pfet_01v8_hvt',
            'pfet_01v8_hvt_nf',
            'pfet_01v8_lvt',
            'pfet_01v8_lvt_nf',
            'pfet_01v8_nf',
            'pfet_20v0',
            'pfet_g5v0d10v5',
            'pfet_g5v0d10v5_nf',
            'pfet_g5v0d16v0',
            'pfet_g5v0d16v0_nf'
        )
        self.dev_names_r = (
            'res_generic_l1',
            'res_generic_m1',
            'res_generic_m2',
            'res_generic_m3',
            'res_generic_m4',
            'res_generic_m5',
            'res_generic_nd',
            'res_generic_pd',
            'res_generic_po',
            'res_high_po',
            'res_high_po_0p35',
            'res_high_po_0p69',
            'res_high_po_1p41',
            'res_high_po_2p85',
            'res_high_po_5p73',
            'res_iso_pw',
            'res_xhigh_po',
            'res_xhigh_po_0p35',
            'res_xhigh_po_0p69',
            'res_xhigh_po_1p41',
            'res_xhigh_po_2p85',
            'res_xhigh_po_5p73'
        )
        self.dev_names_c = (
            'cap_mim_m3_1',
            'cap_mim_m3_2',
            'cap_var_hvt',
            'cap_var_lvt',
            'vpp_cap'
        )

        if warning_msg == True:
            for i in self.ckt_hierarchy:
                dev_name = i[2]
                dev_type = i[3]
                if dev_type == 'm' or dev_type == 'M':
                    if dev_name not in self.dev_names_mos:
                        print(f'This MOS is not in sky130 PDK. A valid device name can be {self.dev_names_mos}.')
                elif dev_type == 'r' or dev_type == 'R':
                    if dev_name not in self.dev_names_r:
                        print(f'This resistor is not in sky130 PDK. A valid device name can be {self.dev_names_r}.')
                elif dev_type == 'c' or dev_type == 'C':
                    if dev_name not in self.dev_names_c:
                        print(f'This capacitor is not in sky130 PDK. A valid device name can be {self.dev_names_c}.')
                elif dev_type == 'i' or dev_type == 'I':
                    None
                elif dev_type == 'v' or dev_type == 'V':
                    None
                else:
                    print('You have a device type that cannot be found here...')

        # 45 attributes for mos
        self.params_mos = (
            'gmbs',
            'gm',
            'gds',
            'vdsat',
            'vth',
            'id',
            'ibd',
            'ibs',
            'gbd',
            'gbs',
            'isub',
            'igidl',
            'igisl',
            'igs',
            'igd',
            'igb',
            'igcs',
            'vbs',
            'vgs',
            'vds',
            'cgg',
            'cgs',
            'cgd',
            'cbg',
            'cbd',
            'cbs',
            'cdg',
            'cdd',
            'cds',
            'csg',
            'csd',
            'css',
            'cgb',
            'cdb',
            'csb',
            'cbb',
            'capbd',
            'capbs',
            'qg',
            'qb',
            'qs',
            'qinv',
            'qdef',
            'gcrg',
            'gtau'
        )
        # 20 attributes for r
        self.params_r = (
            'r',
            'ac',
            'temp',
            'dtemp',
            'l',
            'w',
            'm',
            'tc',
            'tc1',
            'tc2',
            'scale',
            'noise',
            'i',
            'p',
            'sens_dc',
            'sens_real',
            'sens_imag',
            'sens_mag',
            'sens_ph',
            'sens_cplx'
        )
        # 18 attributes for c
        self.params_c = (
            'capacitance',
            'cap',
            'c',
            'ic',
            'temp',
            'dtemp',
            'w',
            'l',
            'm',
            'scale',
            'i',
            'p',
            'sens_dc',
            'sens_real',
            'sens_imag',
            'sens_mag',
            'sens_ph',
            'sens_cplx'
        )
        # 8 attributes for i source
        self.params_i = (
            'dc',
            'acmag',
            'acphase',
            'acreal',
            'acimag',
            'v',
            'p',
            'current'
        )
        # 7 attributes for v source
        self.params_v = (
            'dc',
            'acmag',
            'acphase',
            'acreal',
            'acimag',
            'i',
            'p',
        )

    def gen_dev_params(self, file_name):
        lines = []
        write_file = ''
        for i in self.ckt_hierarchy:
            symbol_name = i[0]
            subckt = i[1]
            dev_name = i[2]
            dev_type = i[3]

            if dev_type == 'm' or dev_type == 'M':
                for param in self.params_mos:
                    if subckt == '':
                        raise ValueError('In this PDK, transistor is instantiated as a subckt! Subckt is missing here.')
                    else:
                        if dev_name in self.dev_names_mos:
                            # line = f'let {param}_{symbol_name}=@m.{subckt}.msky130_fd_pr__{dev_name}[{param}]'
                            line = f'let {param}_{symbol_name}=@m.{subckt}.msky130_fd_pr__{dev_name}[{param}]'
                        else:
                            raise ValueError('This device is not defined in this PDK.')
                    lines.append(line)
                    write_file = write_file + f'{param}_{symbol_name} '
                lines.append('')
            elif dev_type == 'r' or dev_type == 'R':
                for param in self.params_r:
                    if subckt == '':
                        raise ValueError('In this PDK, resistor is instantiated as a subckt! Subckt is missing here.')
                    else:
                        if dev_name in self.dev_names_r:
                            raise ValueError('it is not straightforward to extract resistance info from this PDK, \
                                             so for resistance just use Rsheet * L / W / M for approximation. Remove the resistors from the ckt_hierarchy.')
                        else:
                            raise ValueError('This device is not defined in this PDK.')
                    lines.append(line)
                    write_file = write_file + f'{param}_{symbol_name} '
                lines.append('')
            elif dev_type == 'c' or dev_type == 'C':
                for param in self.params_c:
                    if subckt == '':
                        raise ValueError('In this PDK, capacitor is instantiated as a subckt! Subckt is missing here.')
                    else:
                        if dev_name in self.dev_names_c:
                            # line = f'let {param}_{symbol_name}=@c.{subckt}.c1[{param}]'
                            line = f'let {param}_{symbol_name}=@c.{subckt}.c1[{param}]'
                        else:
                            raise ValueError('This device is not defined in this PDK.')
                    lines.append(line)
                    write_file = write_file + f'{param}_{symbol_name} '
                lines.append('')
            elif dev_type == 'i' or dev_type == 'I':
                for param in self.params_i:
                    if subckt == '':
                        line = f'let {param}_{symbol_name}=@{dev_name}[{param}]'
                    else:
                        line = f'let {param}_{symbol_name}=@i.{subckt}.{dev_name}[{param}]'
                    lines.append(line)
                    write_file = write_file + f'{param}_{symbol_name} '
                lines.append('')
            elif dev_type == 'v' or dev_type == 'V':
                for param in self.params_v:
                    if subckt == '':
                        line = f'let {param}_{symbol_name}=@{dev_name}[{param}]'
                    else:
                        line = f'let {param}_{symbol_name}=@v.{subckt}.{dev_name}[{param}]'
                    lines.append(line)
                    write_file = write_file + f'{param}_{symbol_name} '
                lines.append('')
            else:
                None

        lines.append(f'write {file_name} ' + write_file)

        return lines


if __name__ == '__main__':
    # ckt_hierarchy = GraphLDO().ckt_hierarchy
    # dev_params_script = DeviceParams(ckt_hierarchy).gen_dev_params(file_name='ldo_tb_op')
    #
    # print(ckt_hierarchy)
    # print(dev_params_script)
    #
    # with open('simulations/ldo_tb_dev_params.spice', 'w') as f:
    #     for line in dev_params_script:
    #         f.write(f'{line}\n')

    # ckt_hierarchy = GraphOTA().ckt_hierarchy
    # dev_params_script = DeviceParams(ckt_hierarchy).gen_dev_params(file_name='ota_op')
    #
    # print(ckt_hierarchy)
    # print(dev_params_script)
    #
    # with open('simulations/ota_dev_params.spice', 'w') as f:
    #     for line in dev_params_script:
    #         f.write(f'{line}\n')

    # ckt_hierarchy = GraphOTA2().ckt_hierarchy
    # dev_params_script = DeviceParams(ckt_hierarchy).gen_dev_params(file_name='ota2_op')
    #
    # print(ckt_hierarchy)
    # print(dev_params_script)
    #
    # with open('simulations/ota2_dev_params.spice', 'w') as f:
    #     for line in dev_params_script:
    #         f.write(f'{line}\n')

    ckt_hierarchy = GraphOTA3().ckt_hierarchy
    dev_params_script = DeviceParams(ckt_hierarchy).gen_dev_params(file_name='ota3_op')

    print(ckt_hierarchy)
    print(dev_params_script)

    with open('simulations/ota3_dev_params.spice', 'w') as f:
        for line in dev_params_script:
            f.write(f'{line}\n')

    # ckt_hierarchy = GraphLDOFoldedCascode().ckt_hierarchy
    # dev_params_script = DeviceParams(ckt_hierarchy).gen_dev_params(file_name='ldo_folded_cascode_tb_op')
    #
    # with open('simulations/ldo_folded_cascode_tb_dev_params.spice', 'w') as f:
    #     for line in dev_params_script:
    #         f.write(f'{line}\n')

