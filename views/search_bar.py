"""搜索栏组件 — 支持关键词搜索 + 金额范围过滤"""

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QLineEdit, QPushButton, 
                              QLabel, QDoubleSpinBox)
from PyQt5.QtCore import pyqtSignal, Qt


class SearchBar(QWidget):
    """搜索栏"""
    
    search_triggered = pyqtSignal(str)  # 搜索信号
    reset_triggered = pyqtSignal()      # 重置信号
    amount_filter_changed = pyqtSignal(float, float)  # 金额范围变化信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # 搜索输入框
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("搜索发票号码、购买方、销售方、备注...")
        self._search_input.setMinimumWidth(300)
        self._search_input.returnPressed.connect(self._on_search)
        self._search_input.setStyleSheet("""
            QLineEdit {
                padding: 6px 10px;
                border: 1px solid #d9d9d9;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border-color: #1890ff;
            }
        """)
        layout.addWidget(self._search_input)
        
        # 搜索按钮
        search_btn = QPushButton("搜索")
        search_btn.clicked.connect(self._on_search)
        search_btn.setStyleSheet("""
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                padding: 6px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
        """)
        layout.addWidget(search_btn)
        
        # 重置按钮
        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self._on_reset)
        layout.addWidget(reset_btn)
        
        # 金额范围过滤
        layout.addWidget(QLabel("金额:"))
        
        self._amount_from = QDoubleSpinBox()
        self._amount_from.setRange(0, 9999999)
        self._amount_from.setDecimals(2)
        self._amount_from.setSpecialValueText("不限")
        self._amount_from.setPrefix("¥ ")
        self._amount_from.setFixedWidth(100)
        self._amount_from.valueChanged.connect(self._on_amount_changed)
        layout.addWidget(self._amount_from)
        
        layout.addWidget(QLabel("-"))
        
        self._amount_to = QDoubleSpinBox()
        self._amount_to.setRange(0, 9999999)
        self._amount_to.setDecimals(2)
        self._amount_to.setSpecialValueText("不限")
        self._amount_to.setPrefix("¥ ")
        self._amount_to.setFixedWidth(100)
        self._amount_to.valueChanged.connect(self._on_amount_changed)
        layout.addWidget(self._amount_to)
        
        layout.addStretch()
    
    def _on_search(self):
        """搜索"""
        text = self._search_input.text().strip()
        self.search_triggered.emit(text)
    
    def _on_reset(self):
        """重置搜索"""
        self._search_input.clear()
        self._amount_from.setValue(0)
        self._amount_to.setValue(0)
        self.reset_triggered.emit()
    
    def get_search_text(self) -> str:
        """获取搜索文本"""
        return self._search_input.text().strip()
    
    def clear(self):
        """清空搜索框"""
        self._search_input.clear()
        self._amount_from.setValue(0)
        self._amount_to.setValue(0)
    
    def get_amount_from(self) -> float:
        """获取金额下限"""
        val = self._amount_from.value()
        return val if val > 0 else None
    
    def get_amount_to(self) -> float:
        """获取金额上限"""
        val = self._amount_to.value()
        return val if val > 0 else None
    
    def _on_amount_changed(self):
        """金额范围变化"""
        self.amount_filter_changed.emit(
            self._amount_from.value(),
            self._amount_to.value()
        )
