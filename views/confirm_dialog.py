"""通用确认弹窗"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PyQt5.QtCore import Qt


class ConfirmDialog(QDialog):
    """通用确认对话框"""
    
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)
        
        self._init_ui(message)
    
    def _init_ui(self, message: str):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 消息标签
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setAlignment(Qt.AlignCenter)
        msg_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(msg_label)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        # 确认按钮
        confirm_btn = QPushButton("确认")
        confirm_btn.setFixedWidth(100)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4d4f;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ff7875;
            }
        """)
        confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(confirm_btn)
        
        layout.addLayout(btn_layout)
    
    @classmethod
    def confirm(cls, parent, title: str, message: str) -> bool:
        """
        显示确认对话框
        
        Args:
            parent: 父组件
            title: 标题
            message: 消息
            
        Returns:
            bool: 用户是否点击确认
        """
        dialog = cls(title, message, parent)
        return dialog.exec_() == QDialog.Accepted
