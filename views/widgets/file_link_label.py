"""可点击文件名超链接控件"""

from PyQt5.QtWidgets import QLabel, QMessageBox
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QCursor
from utils.file_utils import open_file


class FileLinkLabel(QLabel):
    """可点击文件名超链接标签"""
    
    clicked = pyqtSignal(str)  # 点击信号，传递文件路径
    
    def __init__(self, text: str = "", file_path: str = "", parent=None):
        super().__init__(text, parent)
        self._file_path = file_path
        
        # 设置超链接样式
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setStyleSheet("""
            QLabel {
                color: #1890ff;
                text-decoration: underline;
            }
            QLabel:hover {
                color: #40a9ff;
            }
        """)
        
        # 启用鼠标追踪
        self.setMouseTracking(True)
    
    def set_file_path(self, file_path: str):
        """设置文件路径"""
        self._file_path = file_path
    
    def file_path(self) -> str:
        """获取文件路径"""
        return self._file_path
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.LeftButton and self._file_path:
            self._open_file()
            self.clicked.emit(self._file_path)
        super().mousePressEvent(event)
    
    def _open_file(self):
        """打开文件"""
        if not self._file_path:
            return
        
        success = open_file(self._file_path)
        if not success:
            QMessageBox.warning(
                self,
                "打开失败",
                f"无法打开文件:\n{self._file_path}\n\n请检查文件是否存在或是否有对应的程序打开。"
            )
