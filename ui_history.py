"""每个功能页各自独立的撤销 / 重做栈。

只记录"在当前页面上已经完成"的操作。四个功能页在软件启动时创建一次，
之后切换模块不再重建，所以撤销记录会保留到关闭软件为止。

撤销只操作本模块自己记录过的文件：每一步在执行前都会拍快照，
撤销时把文件还原成操作前的状态（原来没有的才删除），
不会去扫描目录或删除启动软件之前就存在的文件。
"""

from PyQt5.QtWidgets import QMessageBox


class PageHistory:
    """线性撤销栈。

    push(label, do, undo, step=None)：
      - do   —— 重做时重新执行该操作（通常是重新生成文件）
      - undo —— 撤销时回退该操作（恢复它覆盖前的文件内容，
                或删除它新建的文件）
      - step —— 模块内的步骤序号（1、2、3…）。连续递增的步骤算同一条链：
                重做时会先清掉这条链在当前步骤及之前的所有产物，
                再从第一步按顺序重新执行到当前步骤。
                step=None 表示独立操作，重做只重跑它自己。
    """

    def __init__(self, owner=None):
        self.owner = owner
        self._undo = []
        self._redo = []
        # 当前这条步骤链的标识与最后一步的序号
        self._chain = None
        self._last_step = None

    # ==================== 记录 ====================
    def push(self, label, do, undo, step=None):
        """记录一个已经执行成功的操作"""
        if step is None:
            # 独立操作（例如单个器件生成）：重做只重跑自己
            chain = None
            self._chain = None
            self._last_step = None
        else:
            # 步骤往回走说明用户重新开始了这条流程，另起一条链
            if (self._chain is None or self._last_step is None
                    or step <= self._last_step):
                self._chain = object()
            chain = self._chain
            self._last_step = step

        self._undo.append((label, do, undo, chain, step))
        self._redo.clear()

    def clear(self):
        self._undo.clear()
        self._redo.clear()
        self._chain = None
        self._last_step = None

    def can_undo(self):
        return bool(self._undo)

    def can_redo(self):
        return bool(self._redo)

    def undo_label(self):
        return self._undo[-1][0] if self._undo else ""

    def redo_label(self):
        return self._redo[-1][0] if self._redo else ""

    # ==================== 执行 ====================
    def undo(self):
        if not self._undo:
            return False
        entry = self._undo.pop()
        try:
            entry[2]()
        except Exception as exc:               # 回退失败：这步留在撤销栈里
            self._undo.append(entry)
            self._report("撤销失败", entry[0], exc)
            return False
        self._redo.append(entry)
        self._sync_position()
        return True

    def redo(self):
        """重做：先清链，再从第一步重跑到当前步骤

        目标步骤本身在撤销时已经回退过，不需要再清一次；
        它前面的同链步骤虽然还标着"已完成"，但产物要先删掉，
        这样重跑时拿到的是干净的状态。
        """
        if not self._redo:
            return False

        target = self._redo[-1]
        clean, chain = self._redo_plan(target)
        try:
            # 倒序清理：同一文件被多次覆盖时，才能还原到链开始前的状态
            for entry in reversed(clean):
                entry[2]()
            # 正序重跑：后面的步骤依赖前面步骤的产物
            for entry in chain:
                entry[1]()
        except Exception as exc:               # 重做失败：这步仍可重做
            self._report("重做失败", target[0], exc)
            return False

        self._redo.pop()
        self._undo.append(target)
        self._sync_position()
        return True

    def _redo_plan(self, target):
        """返回 (需要清理的已完成步骤, 需要按顺序重跑的步骤)"""
        chain_id = target[3]
        if chain_id is None:
            # 独立操作：目标已经在撤销时回退过，直接重跑即可
            return [], [target]

        # 找到撤销栈末尾与目标同链的连续一段
        start = len(self._undo)
        while start > 0 and self._undo[start - 1][3] is chain_id:
            start -= 1
        previous = self._undo[start:]
        return previous, previous + [target]

    def _sync_position(self):
        """让链标识跟着撤销栈的末端走，便于判断下一次操作是否另起一链"""
        if self._undo:
            self._chain = self._undo[-1][3]
            self._last_step = self._undo[-1][4]
        else:
            self._chain = None
            self._last_step = None

    def _report(self, title, label, exc):
        if self.owner is not None:
            QMessageBox.critical(self.owner, title, f"{label}：\n{exc}")
