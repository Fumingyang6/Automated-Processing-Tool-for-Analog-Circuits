# 在仓库根目录运行本脚本（jiao.sh 位于仓库根目录）
cd "$(dirname "$0")"
# 虚拟环境的 site-packages 路径：可用环境变量 SITE_PACKAGES 覆盖，
# 默认取当前用户 home 下的 CEDA 虚拟环境
SITE_PACKAGES="${SITE_PACKAGES:-$HOME/.virtualenvs/CEDA/lib/python3.10/site-packages}"
rm -rf build
pyinstaller --onefile --windowed \
    --add-binary="$SITE_PACKAGES:site-packages" \
    --add-data="device_generation:device_generation" \
    --add-data="analog_placement:analog_placement" \
    --add-data="ota_case1:ota_case1" \
    --add-data="rsmt_router:rsmt_router" \
    --add-data="assets:assets" \
    --hidden-import PyQt5.QtCore \
    --hidden-import PyQt5.QtGui \
    --hidden-import PyQt5.QtWidgets \
    --hidden-import PyQt5.sip \
    --name="parms" \
    main_ui.py

#pyinstaller --onefile --windowed \
#    --add-binary="$HOME/.virtualenvs/CEDA/lib/python3.10/site-packages/gdspy:gdspy" \
#    --add-binary="$HOME/.virtualenvs/CEDA/lib/python3.10/site-packages/gymnasium:gymnasium" \
#    --add-binary="$HOME/.virtualenvs/CEDA/lib/python3.10/site-packages/PyQt5:PyQt5" \
#    --add-binary="$HOME/.virtualenvs/CEDA/lib/python3.10/site-packages/PyQt5/Qt5:PyQt5/Qt5" \
#    --add-binary="$HOME/.virtualenvs/CEDA/lib/python3.10/site-packages/matplotlib:matplotlib" \
#    --add-binary="$HOME/.virtualenvs/CEDA/lib/python3.10/site-packages/mpl_toolkits:mpl_toolkits" \
#    --add-binary="$HOME/.virtualenvs/CEDA/lib/python3.10/site-packages/tabulate:tabulate" \
#    --add-binary="$HOME/.virtualenvs/CEDA/lib/python3.10/site-packages/torch_geometric:torch_geometric" \
#    --add-binary="$HOME/.virtualenvs/CEDA/lib/python3.10/site-packages/dgl:dgl" \
#    --add-binary="$HOME/.virtualenvs/CEDA/lib/python3.10/site-packages/IPython:IPython" \
#    --add-binary="$HOME/.virtualenvs/CEDA/lib/python3.10/site-packages/stack_data:stack_data" \
#    --add-binary="$HOME/.virtualenvs/CEDA/lib/python3.10/site-packages/pickleshare.py:."
#    --add-binary="./rsmt_router/gdsii:rsmt_router/gdsii" \
#    --add-data="./rsmt_router/UnionFind.py:." \
#    --add-data="./device_generation:device_generation" \
#    --add-data="./analog_placement:analog_placement" \
#    --add-data="./ota_case1:ota_case1" \
#    --add-data="./rsmt_router:rsm_router" \
#    --collect-all asttokens \
#    --collect-all backcall \
#    --collect-all certifi \
#    --collect-all click \
#    --collect-all cloudpickle \
#    --collect-all contourpy \
#    --collect-all cycler \
#    --collect-all executing \
#    --collect-all filelock \
#    --collect-all idna \
#    --collect-all jedi \
#    --collect-all joblib \
#    --collect-all kiwisolver \
#    --collect-all mpmath \
#    --collect-all networkx \
#    --collect-all numpy \
#    --collect-all packaging \
#    --collect-all pandas \
#    --collect-all parso \
#    --collect-all pexpect \
#    --collect-all prompt_toolkit \
#    --collect-all psutil \
#    --collect-all ptyprocess \
#    --collect-all pure_eval \
#    --collect-all pytz \
#    --collect-all requests \
#    --collect-all scipy \
#    --collect-all sympy \
#    --collect-all torch \
#    --collect-all tqdm \
#    --collect-all traitlets \
#    --collect-all tzdata \
#    --collect-all urllib3 \
#    --collect-all wcwidth \
#    --hidden-import PyQt5.QtCore \
#    --hidden-import PyQt5.QtGui \
#    --hidden-import PyQt5.QtWidgets \
#    --hidden-import PyQt5.sip \
#    --name="parms" \
#    main_ui.py