"""发票详情面板"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                              QComboBox, QLineEdit, QPushButton, QScrollArea,
                              QFormLayout, QGroupBox)
from PyQt5.QtCore import pyqtSignal, Qt
from models.invoice import Invoice
from core.constants import BusinessType, InvoiceType, ReimbursementStatus, InvoiceStatus
from views.widgets.clickable_path import ClickablePath
from utils.file_utils import open_file


class DetailPanel(QWidget):
    """发票详情面板"""
    
    field_updated = pyqtSignal(int, str, str)  # 字段更新信号: (invoice_id, field_name, value)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._invoice: Invoice = None
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 标题
        title = QLabel("发票详情")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        main_layout.addWidget(title)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setSpacing(15)
        
        # 基本信息组
        self._basic_group = self._create_basic_info_group()
        self._content_layout.addWidget(self._basic_group)
        
        # 可编辑信息组
        self._edit_group = self._create_editable_group()
        self._content_layout.addWidget(self._edit_group)
        
        # 源文件信息组
        self._file_group = self._create_file_info_group()
        self._content_layout.addWidget(self._file_group)
        
        self._content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        # 空状态提示
        self._empty_label = QLabel("请选择一张发票查看详情")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #999; font-size: 14px;")
        main_layout.addWidget(self._empty_label)
        
        # 初始隐藏内容
        scroll.hide()
        self._scroll = scroll
    
    def _create_basic_info_group(self) -> QGroupBox:
        """创建基本信息组"""
        group = QGroupBox("基本信息")
        layout = QFormLayout(group)
        layout.setSpacing(10)
        
        self._invoice_number_label = QLabel()
        layout.addRow("发票号码:", self._invoice_number_label)
        
        self._invoice_date_label = QLabel()
        layout.addRow("开票日期:", self._invoice_date_label)
        
        self._invoice_type_label = QLabel()
        layout.addRow("发票类型:", self._invoice_type_label)
        
        self._business_type_label = QLabel()
        layout.addRow("业务类型:", self._business_type_label)
        
        self._buyer_label = QLabel()
        layout.addRow("购买方:", self._buyer_label)
        
        self._seller_label = QLabel()
        layout.addRow("销售方:", self._seller_label)
        
        self._amount_label = QLabel()
        layout.addRow("不含税金额:", self._amount_label)
        
        self._tax_label = QLabel()
        layout.addRow("税额:", self._tax_label)
        
        self._total_label = QLabel()
        self._total_label.setStyleSheet("font-weight: bold; color: #f5222d;")
        layout.addRow("价税合计:", self._total_label)
        
        return group
    
    def _create_editable_group(self) -> QGroupBox:
        """创建可编辑信息组"""
        group = QGroupBox("可编辑信息")
        layout = QFormLayout(group)
        layout.setSpacing(10)
        
        # 业务类型下拉
        self._business_combo = QComboBox()
        for biz in BusinessType.all_values():
            self._business_combo.addItem(biz)
        self._business_combo.currentTextChanged.connect(
            lambda v: self._on_field_changed('business_type', v))
        layout.addRow("业务类型:", self._business_combo)
        
        # 报销状态下拉
        self._reimbursement_combo = QComboBox()
        for status in ReimbursementStatus.all_values():
            self._reimbursement_combo.addItem(status)
        self._reimbursement_combo.currentTextChanged.connect(
            lambda v: self._on_field_changed('reimbursement_status', v))
        layout.addRow("报销状态:", self._reimbursement_combo)
        
        # 状态下拉
        self._status_combo = QComboBox()
        for status in InvoiceStatus.all_values():
            self._status_combo.addItem(status)
        self._status_combo.currentTextChanged.connect(
            lambda v: self._on_field_changed('status', v))
        layout.addRow("状态:", self._status_combo)
        
        # 备注
        self._remark_edit = QLineEdit()
        self._remark_edit.editingFinished.connect(
            lambda: self._on_field_changed('remark', self._remark_edit.text()))
        layout.addRow("备注:", self._remark_edit)
        
        return group
    
    def _create_file_info_group(self) -> QGroupBox:
        """创建源文件信息组"""
        group = QGroupBox("源文件信息")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        
        # 文件路径
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("路径:"))
        self._path_widget = ClickablePath()
        path_layout.addWidget(self._path_widget, 1)
        layout.addLayout(path_layout)
        
        # 打开文件按钮
        open_btn = QPushButton("打开文件")
        open_btn.clicked.connect(self._open_source_file)
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: #52c41a;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #73d13d;
            }
        """)
        layout.addWidget(open_btn)
        
        # 导入时间
        self._import_time_label = QLabel()
        layout.addWidget(self._import_time_label)
        
        return group
    
    def show_invoice(self, invoice: Invoice):
        """显示发票详情"""
        self._invoice = invoice
        
        # 更新基本信息
        self._invoice_number_label.setText(invoice.invoice_number)
        self._invoice_date_label.setText(invoice.invoice_date)
        self._invoice_type_label.setText(invoice.invoice_type)
        self._business_type_label.setText(invoice.business_type)
        self._buyer_label.setText(invoice.buyer_name or "-")
        self._seller_label.setText(invoice.seller_name or "-")
        self._amount_label.setText(f"¥ {invoice.amount_without_tax:,.2f}")
        self._tax_label.setText(f"¥ {invoice.tax_amount:,.2f}")
        self._total_label.setText(f"¥ {invoice.total_amount:,.2f}")
        
        # 更新可编辑字段（阻止信号触发）
        self._business_combo.blockSignals(True)
        self._reimbursement_combo.blockSignals(True)
        self._status_combo.blockSignals(True)
        
        idx = self._business_combo.findText(invoice.business_type)
        if idx >= 0:
            self._business_combo.setCurrentIndex(idx)
        
        idx = self._reimbursement_combo.findText(invoice.reimbursement_status)
        if idx >= 0:
            self._reimbursement_combo.setCurrentIndex(idx)
        
        idx = self._status_combo.findText(invoice.status)
        if idx >= 0:
            self._status_combo.setCurrentIndex(idx)
        
        self._remark_edit.setText(invoice.remark or "")
        
        self._business_combo.blockSignals(False)
        self._reimbursement_combo.blockSignals(False)
        self._status_combo.blockSignals(False)
        
        # 更新文件信息
        self._path_widget.set_path(invoice.source_file_path)
        self._import_time_label.setText(f"导入时间: {invoice.import_time[:19] if invoice.import_time else '-'}")
        
        # 显示内容，隐藏空状态
        self._scroll.show()
        self._empty_label.hide()
    
    def clear(self):
        """清空详情"""
        self._invoice = None
        self._scroll.hide()
        self._empty_label.show()
    
    def _on_field_changed(self, field: str, value: str):
        """字段更新"""
        if self._invoice:
            self.field_updated.emit(self._invoice.id, field, value)
    
    def _open_source_file(self):
        """打开源文件"""
        if self._invoice and self._invoice.source_file_path:
            open_file(self._invoice.source_file_path)
