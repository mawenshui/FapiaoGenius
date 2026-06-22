"""可点击复制路径控件"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QApplication
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QCursor


class ClickablePath(QWidget):
    """可点击复制的路径显示控件"""
    
    copied = pyqtSignal(str)  # 复制信号
    
    def __init__(self, path: str = "", parent=None):
        super().__init__(parent)
        self._path = path
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 路径标签
        self._label = QLabel(self._path)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._label.setStyleSheet("color: #666;")
        layout.addWidget(self._label, 1)
        
        # 复制按钮
        self._copy_btn = QPushButton("复制")
        self._copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._copy_btn.setFixedWidth(60)
        self._copy_btn.clicked.connect(self._copy_path)
        layout.addWidget(self._copy_btn)
    
    def set_path(self, path: str):
        """设置路径"""
        self._path = path
        self._label.setText(path)
    
    def path(self) -> str:
        """获取路径"""
        return self._path
    
    def _copy_path(self):
        """复制路径到剪贴板"""
        if self._path:
            clipboard = QApplication.clipboard()
            clipboard.setText(self._path)
            self.copied.emit(self._path)
            
            # 简单提示
            self._copy_btn.setText("已复制")
            # 延迟恢复文本
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self._copy_btn.setText("复制"))
