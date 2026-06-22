"""导入进度弹窗"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal


class ProgressDialog(QDialog):
    """导入进度对话框"""
    
    cancelled = pyqtSignal()  # 取消信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("正在导入...")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 状态标签
        self._status_label = QLabel("准备导入...")
        self._status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status_label)
        
        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFixedHeight(25)
        layout.addWidget(self._progress_bar)
        
        # 当前文件标签
        self._file_label = QLabel("")
        self._file_label.setAlignment(Qt.AlignCenter)
        self._file_label.setStyleSheet("color: #666; font-size: 12px;")
        self._file_label.setWordWrap(True)
        layout.addWidget(self._file_label)
        
        # 取消按钮
        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self._cancel_btn)
    
    def update_progress(self, current: int, total: int, filename: str = ""):
        """
        更新进度
        
        Args:
            current: 当前进度
            total: 总数
            filename: 当前处理文件名
        """
        if total > 0:
            percent = int(current / total * 100)
            self._progress_bar.setValue(percent)
            self._status_label.setText(f"正在导入... ({current}/{total})")
        
        if filename:
            self._file_label.setText(filename)
    
    def _on_cancel(self):
        """取消导入"""
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setText("正在取消...")
        self.cancelled.emit()
    
    def close_dialog(self):
        """关闭对话框"""
        self.accept()
    
    def set_cancel_enabled(self, enabled: bool):
        """设置取消按钮是否可用"""
        self._cancel_btn.setEnabled(enabled)
        self._cancel_btn.setText("取消" if enabled else "正在取消...")
