import sys
import os

def resource_path(relative_path):
    """ 获取资源文件的绝对路径，兼容开发环境和 PyInstaller 打包 """
    if getattr(sys, 'frozen', False):
        # 打包后的临时目录
        base_path = sys._MEIPASS
    else:
        # 正常运行的脚本目录
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)