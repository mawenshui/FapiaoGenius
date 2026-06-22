"""筛选栏组件"""

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QLabel, QComboBox, 
                              QDateEdit, QPushButton)
from PyQt5.QtCore import pyqtSignal, Qt, QDate
from core.constants import BusinessType, InvoiceType, ReimbursementStatus, InvoiceStatus


class FilterBar(QWidget):
    """筛选栏"""
    
    filter_changed = pyqtSignal()  # 筛选条件变化信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # 业务类型
        layout.addWidget(QLabel("业务类型:"))
        self._business_combo = QComboBox()
        self._business_combo.addItem("全部", "")
        for biz in BusinessType.all_values():
            self._business_combo.addItem(biz, biz)
        self._business_combo.setMinimumWidth(100)
        self._business_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._business_combo)
        
        # 发票类型
        layout.addWidget(QLabel("发票类型:"))
        self._invoice_type_combo = QComboBox()
        self._invoice_type_combo.addItem("全部", "")
        for inv_type in InvoiceType.all_values():
            self._invoice_type_combo.addItem(inv_type, inv_type)
        self._invoice_type_combo.setMinimumWidth(100)
        self._invoice_type_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._invoice_type_combo)
        
        # 报销状态
        layout.addWidget(QLabel("报销状态:"))
        self._reimbursement_combo = QComboBox()
        self._reimbursement_combo.addItem("全部", "")
        for status in ReimbursementStatus.all_values():
            self._reimbursement_combo.addItem(status, status)
        self._reimbursement_combo.setMinimumWidth(80)
        self._reimbursement_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._reimbursement_combo)
        
        # 日期范围
        layout.addWidget(QLabel("开票日期:"))
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDisplayFormat("yyyy-MM-dd")
        self._date_from.setDate(QDate.currentDate().addMonths(-12))
        self._date_from.setFixedWidth(120)
        self._date_from.dateChanged.connect(self._on_filter_changed)
        layout.addWidget(self._date_from)
        
        layout.addWidget(QLabel("至"))
        
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDisplayFormat("yyyy-MM-dd")
        self._date_to.setDate(QDate.currentDate())
        self._date_to.setFixedWidth(120)
        self._date_to.dateChanged.connect(self._on_filter_changed)
        layout.addWidget(self._date_to)
        
        # 重置按钮
        reset_btn = QPushButton("重置筛选")
        reset_btn.clicked.connect(self.reset)
        layout.addWidget(reset_btn)
        
        layout.addStretch()
    
    def _on_filter_changed(self):
        """筛选条件变化"""
        self.filter_changed.emit()
    
    def reset(self):
        """重置所有筛选条件"""
        self._business_combo.setCurrentIndex(0)
        self._invoice_type_combo.setCurrentIndex(0)
        self._reimbursement_combo.setCurrentIndex(0)
        self._date_from.setDate(QDate.currentDate().addMonths(-12))
        self._date_to.setDate(QDate.currentDate())
    
    def get_business_type(self) -> str:
        """获取业务类型筛选值"""
        return self._business_combo.currentData() or ""
    
    def get_invoice_type(self) -> str:
        """获取发票类型筛选值"""
        return self._invoice_type_combo.currentData() or ""
    
    def get_reimbursement_status(self) -> str:
        """获取报销状态筛选值"""
        return self._reimbursement_combo.currentData() or ""
    
    def get_date_from(self) -> str:
        """获取起始日期"""
        return self._date_from.date().toString("yyyy-MM-dd")
    
    def get_date_to(self) -> str:
        """获取结束日期"""
        return self._date_to.date().toString("yyyy-MM-dd")
