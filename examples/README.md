# Examples #

> **注意：这里的例子在本仓库中无法直接运行。**
>
> 这批示例连同 `mockPDK/` 是从上游流程整块搬过来的参考材料。各目录下的
> `run.sh` 调用的是上游的 `flow/python/Magical.py`，**该脚本从未包含在本仓库里**，
> 本仓库也没有任何代码读取这些示例的 `.json` 配置。
>
> 请把这里当作设计参考和网表示例（`.sp`）来用。本仓库真正能跑通的
> 自动布线流程，用的是 `rsmt_router/nets.txt` + `rsmt_router/CP_OP2.txt`。

Here we provide a mock PDK technology files and a few examples.

# Mock PDK
The mock PDK is made up referencing public domain PDKs. It is not targeting any real pratical industrial process.

# OTA3

A telescopic three-stage OTA.
It is designed towards TSMC40 technology. But the netlist we present here has procssed and does not contain information voiding NDA.
```
cd ota3
source run.sh
```
# ADC2

A CTDSM design
It is designed towards TSMC40 technology. But the netlist we present here has procssed and does not contain information voiding NDA.
```
cd ADC2
source run.sh
```
