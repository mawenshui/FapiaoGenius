"""导航侧边栏"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QButtonGroup
from PyQt5.QtCore import pyqtSignal, Qt


class Sidebar(QWidget):
    """导航侧边栏"""
    
    page_changed = pyqtSignal(int)  # 页面切换信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(120)
        
        self._buttons: list[QPushButton] = []
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 20, 5, 20)
        layout.setSpacing(5)
        
        # 按钮组
        self._button_group = QButtonGroup()
        self._button_group.setExclusive(True)
        
        # 导航项
        items = [
            ("发票管理", 0),
            ("智能凑票", 1),
            ("规则管理", 2),
            ("AI 识别", 3),
            ("设置", 4),
        ]
        
        for text, index in items:
            btn = self._create_nav_button(text, index)
            layout.addWidget(btn)
            self._buttons.append(btn)
        
        layout.addStretch()
        
        # 默认选中第一个
        if self._buttons:
            self._buttons[0].setChecked(True)
        
        # 样式
        self.setStyleSheet("""
            QWidget {
                background-color: #f0f2f5;
            }
        """)
    
    def _create_nav_button(self, text: str, index: int) -> QPushButton:
        """创建导航按钮"""
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setFixedHeight(45)
        btn.setCursor(Qt.PointingHandCursor)
        
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                text-align: left;
                padding-left: 15px;
                font-size: 14px;
                color: #333;
            }
            QPushButton:hover {
                background-color: #e6f7ff;
            }
            QPushButton:checked {
                background-color: #1890ff;
                color: white;
                font-weight: bold;
            }
        """)
        
        btn.clicked.connect(lambda checked, idx=index: self._on_button_clicked(idx))
        self._button_group.addButton(btn, index)
        
        return btn
    
    def _on_button_clicked(self, index: int):
        """按钮点击"""
        self.page_changed.emit(index)
    
    def set_current_index(self, index: int):
        """设置当前选中索引"""
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)
