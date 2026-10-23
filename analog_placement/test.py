from LAYOUT import optimize_layout

if __name__ == "__main__":
    x, y = optimize_layout(
        netlist_file="mycase/ota1.sp",
        sym_file="mycase/ota1.sym"
    )
    # x, y = optimize_layout(
    #     netlist_file="mycase/ota4.sp",
    #     sym_file="mycase/ota4.sym",
    #     target_area=20.0,        # 增大布局面积，减少拥挤
    #     max_steps=2000,          # 增加优化步数，提高收敛性
    #     tmoc_weight=50.0,        # 加强共质心约束（对高精度OTA很重要）
    #     symmetry_weight=200.0,   # 加强对称性约束
    #     hpwl_weight=0.05,        # 适当增加线长权重
    #     max_overlap_percent=1.0, # 更严格的重叠要求
    #     plot_intermediate=True   # 显示初始和第一阶段结束的布局图
    # )