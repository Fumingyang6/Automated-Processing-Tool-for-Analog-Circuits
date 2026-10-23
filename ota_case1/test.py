# 版图相关流程

import os
import subprocess

run_magic_extraction_tcl = f'/home/zk/zhangke/test/run_magic_extraction.tcl'
def generate_layout():
    # 1. 调用 shell 脚本
    try:
        subprocess.run(["/home/zk/zhangke/test/run_schematic2layout.sh"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error during schematic to layout generation: {e}")
        return

    # 2. 检查生成的版图文件
    work_dir = "/home/zk/zhangke/test/work"
    gds_file = os.path.join(work_dir, "CASE1_0.gds")
    if not os.path.exists(gds_file):
        raise AssertionError(f"Failure: {gds_file} not found in {work_dir}")
    else:
        print(f"Success: {gds_file} found.")


def magic_extraction():
    # 1. 进入到启动路径
    os.chdir('/home/zk/zhangke/test')
    print("Changed directory to /home/zk/zhangke/test")

    # 2. 执行 Magic，并运行 TCL 脚本
    magic_command = f'magic -T /usr/local/share/pdk/sky130A/libs.tech/magic/sky130A.tech -dnull -noconsole {run_magic_extraction_tcl}'

    try:
        # 执行 Magic 命令
        subprocess.run(magic_command, shell=True, check=True)
        print("Magic TCL script executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error executing Magic command: {e}")
        return

    # 3. 检查文件，检查是否生成 CASE1_0.spice
    spice_file = '/home/zk/zhangke/test/CASE1_0.spice'  # 请根据实际生成路径检查
    if os.path.exists(spice_file):
        print(f"SPICE file {spice_file} generated successfully.")
    else:
        print(f"Error: SPICE file {spice_file} not found.")


if __name__ == "__main__":
    # generate_layout()
    magic_extraction()

