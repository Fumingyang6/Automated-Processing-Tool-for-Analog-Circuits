"""功能页共用的小部件：磁盘目录树、目录树文本。"""

import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem,
)


# 这些目录要么巨大、要么和项目无关，列出来会让树变得没法用
SKIP_DIRS = {
    ".venv", "__pycache__", ".git", ".svn", ".idea", ".vscode",
    "node_modules", ".mypy_cache", ".pytest_cache", ".ipynb_checkpoints",
    "build", "dist",
}

# 单个目录一次最多列多少项，防止某个大目录把界面卡住
_MAX_CHILDREN = 300


def human_size(size):
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


class FileTreePanel(QWidget):
    """懒加载的磁盘目录树。

    目录节点展开时才去读子项，根目录设成整个工程也不会拖慢启动。
    文件项双击发 file_activated，由使用方决定怎么打开。
    """

    file_activated = pyqtSignal(str)

    def __init__(self, root, title="文件目录", hide_callback=None, parent=None):
        super().__init__(parent)
        self.root = os.path.abspath(root)
        self._hide_callback = hide_callback
        self._build_ui(title)
        self.refresh()

    def _build_ui(self, title):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(2, 0, 2, 0)
        header.addWidget(QLabel(title))
        header.addStretch()

        refresh = QPushButton("↻ 刷新")
        refresh.setObjectName("entryButton")
        refresh.setCursor(Qt.PointingHandCursor)
        refresh.setToolTip("重新读取磁盘上的实际目录")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)

        if self._hide_callback is not None:
            hide = QPushButton("隐藏")
            hide.setObjectName("entryButton")
            hide.setCursor(Qt.PointingHandCursor)
            hide.setToolTip("隐藏这个目录栏")
            hide.clicked.connect(self._hide_callback)
            header.addWidget(hide)

        layout.addLayout(header)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(1)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.tree, 1)

    # ==================== 构建 ====================
    def refresh(self):
        """重新读取根目录（会丢掉展开状态）"""
        self.tree.clear()
        name = os.path.basename(self.root.rstrip("\\/")) or self.root
        root_item = QTreeWidgetItem([name])
        root_item.setData(0, Qt.UserRole, self.root)
        root_item.setToolTip(0, self.root)
        self.tree.addTopLevelItem(root_item)
        self._fill_dir(root_item, self.root)
        root_item.setExpanded(True)

    def _fill_dir(self, item, path):
        """把一个目录的直接子项挂到 item 下（目录带一个懒加载占位）"""
        item.takeChildren()
        try:
            entries = list(os.scandir(path))
        except OSError:
            return

        dirs = sorted(
            (e for e in entries
             if e.is_dir(follow_symlinks=False) and e.name not in SKIP_DIRS),
            key=lambda e: e.name.lower())
        files = sorted(
            (e for e in entries if e.is_file(follow_symlinks=False)),
            key=lambda e: e.name.lower())

        for entry in (dirs + files)[:_MAX_CHILDREN]:
            child = QTreeWidgetItem([entry.name])
            child.setData(0, Qt.UserRole, entry.path)
            child.setToolTip(0, entry.path)
            if entry.is_dir(follow_symlinks=False):
                child.addChild(QTreeWidgetItem(["…"]))   # 展开箭头占位
            item.addChild(child)

        total = len(dirs) + len(files)
        if total > _MAX_CHILDREN:
            more = QTreeWidgetItem([f"… 还有 {total - _MAX_CHILDREN} 项"])
            more.setForeground(0, QBrush(QColor("#a8abb2")))
            more.setFlags(Qt.ItemIsEnabled)
            item.addChild(more)

    # ==================== 交互 ====================
    def _on_item_expanded(self, item):
        path = item.data(0, Qt.UserRole)
        if not path or not os.path.isdir(path):
            return
        # QTreeWidgetItem 没有 children()，只能按索引取
        if item.childCount() == 1 and item.child(0).text(0) == "…":
            self._fill_dir(item, path)

    def _on_double_click(self, item, _column):
        path = item.data(0, Qt.UserRole)
        if path and os.path.isfile(path):
            self.file_activated.emit(path)

    @staticmethod
    def _find_child(parent, name):
        for index in range(parent.childCount()):
            child = parent.child(index)
            if child.text(0) == name:
                return child
        return None

    def reveal(self, target):
        """展开并选中 target；目标在根目录之外时什么也不做"""
        target = os.path.abspath(target)
        try:
            rel = os.path.relpath(target, self.root)
        except ValueError:
            return
        if rel.startswith(".."):
            return

        item = self.tree.topLevelItem(0)
        if item is None:
            return
        if rel == ".":
            self.tree.setCurrentItem(item)
            return

        parent = item
        for part in rel.split(os.sep):
            self._on_item_expanded(parent)
            child = self._find_child(parent, part)
            if child is None:
                return
            parent = child
            path = parent.data(0, Qt.UserRole)
            if path and os.path.isdir(path):
                parent.setExpanded(True)

        self.tree.setCurrentItem(parent)
        self.tree.scrollToItem(parent)


def format_dir_tree(path, max_entries=30):
    """把目录渲染成适合放进结果弹窗的文本树"""
    if not path:
        return ""

    path = os.path.abspath(path)
    if os.path.isfile(path):
        try:
            size = human_size(os.path.getsize(path))
        except OSError:
            size = "?"
        return f"{os.path.basename(path)}    {size}"

    if not os.path.isdir(path):
        return str(path)

    try:
        names = os.listdir(path)
    except OSError as exc:
        return f"{path}\n（无法读取：{exc}）"

    def sort_key(name):
        full = os.path.join(path, name)
        return (not os.path.isdir(full), name.lower())

    names.sort(key=sort_key)
    shown = names[:max_entries]

    lines = [os.path.basename(path.rstrip("\\/")) + "/"]
    for index, name in enumerate(shown):
        is_last = index == len(shown) - 1 and len(names) <= max_entries
        branch = "└── " if is_last else "├── "
        full = os.path.join(path, name)
        if os.path.isdir(full):
            lines.append(f"{branch}{name}/")
        else:
            try:
                size = human_size(os.path.getsize(full))
            except OSError:
                size = "?"
            lines.append(f"{branch}{name}    {size}")

    if len(names) > max_entries:
        lines.append(f"└── … 共 {len(names)} 项")
    return "\n".join(lines)
