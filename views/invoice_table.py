"""发票数据表格组件"""

from PyQt5.QtWidgets import (QTableWidget, QTableWidgetItem, QHeaderView, 
                              QAbstractItemView, QCheckBox, QWidget, QHBoxLayout)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor, QBrush
from core.constants import TABLE_COLUMNS
from models.invoice import Invoice


class InvoiceTable(QTableWidget):
    """发票数据表格"""
    
    row_selected = pyqtSignal(int)       # 行选中信号，传递发票 ID
    batch_delete = pyqtSignal(list)      # 批量删除信号，传递 ID 列表
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._invoices: list[Invoice] = []
        self._checkboxes: dict[int, QCheckBox] = {}
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        # 设置列数（包含 checkbox 列）
        self.setColumnCount(len(TABLE_COLUMNS) + 1)
        
        # 设置表头
        headers = [""] + [col[1] for col in TABLE_COLUMNS]
        self.setHorizontalHeaderLabels(headers)
        
        # 设置列宽
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # checkbox 列
        self.setColumnWidth(0, 40)
        
        for i, col in enumerate(TABLE_COLUMNS, 1):
            self.setColumnWidth(i, col[2])
        
        # 表格属性
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.verticalHeader().setVisible(False)
        
        # 样式
        self.setStyleSheet("""
            QTableWidget {
                gridline-color: #e8e8e8;
                border: 1px solid #e8e8e8;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #e6f7ff;
                color: #333;
            }
            QHeaderView::section {
                background-color: #fafafa;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #e8e8e8;
                border-right: 1px solid #e8e8e8;
                font-weight: bold;
            }
        """)
        
        # 信号连接
        self.cellClicked.connect(self._on_cell_clicked)
    
    def populate(self, invoices: list[Invoice]):
        """填充表格数据"""
        self._invoices = invoices
        self._checkboxes.clear()
        
        self.setSortingEnabled(False)
        self.setRowCount(len(invoices))
        
        for row, invoice in enumerate(invoices):
            # Checkbox 列
            checkbox = QCheckBox()
            checkbox.stateChanged.connect(lambda state, inv_id=invoice.id: 
                                          self._on_checkbox_changed(state, inv_id))
            self._checkboxes[invoice.id] = checkbox
            
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.setCellWidget(row, 0, checkbox_widget)
            
            # 数据列
            self._set_row_data(row, invoice)
        
        self.setSortingEnabled(True)
    
    def _set_row_data(self, row: int, invoice: Invoice):
        """设置行数据"""
        data = [
            str(invoice.id),
            invoice.business_type,
            invoice.invoice_type,
            invoice.invoice_number,
            invoice.invoice_date,
            invoice.buyer_name,
            invoice.seller_name,
            f"{invoice.amount_without_tax:.2f}",
            f"{invoice.tax_amount:.2f}",
            f"{invoice.total_amount:.2f}",
            invoice.reimbursement_status,
            invoice.status,
            invoice.remark,
        ]
        
        for col, value in enumerate(data, 1):
            item = QTableWidgetItem(value)
            
            # 金额列右对齐
            if col in [8, 9, 10]:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            # 报销状态列颜色区分
            if col == 11:
                status_colors = {
                    "报销中": QColor("#FFF8DC"),   # 浅黄色
                    "已报销": QColor("#FFE4E1"),   # 浅红色
                    "未报销": QColor("#E8F5E9"),   # 浅绿色
                }
                bg_color = status_colors.get(value)
                if bg_color:
                    item.setBackground(QBrush(bg_color))
            
            # 存储发票 ID 到第一列
            if col == 1:
                item.setData(Qt.UserRole, invoice.id)
            
            self.setItem(row, col, item)
    
    def _on_cell_clicked(self, row: int, col: int):
        """单元格点击事件"""
        if col == 0:  # checkbox 列不处理
            return
        
        # 获取发票 ID
        item = self.item(row, 1)
        if item:
            invoice_id = item.data(Qt.UserRole)
            if invoice_id:
                self.row_selected.emit(invoice_id)
    
    def _on_checkbox_changed(self, state, invoice_id):
        """Checkbox 状态变化"""
        pass  # 可以添加选中计数等功能
    
    def get_selected_ids(self) -> list[int]:
        """获取所有选中的发票 ID"""
        selected = []
        for inv_id, checkbox in self._checkboxes.items():
            if checkbox.isChecked():
                selected.append(inv_id)
        return selected
    
    def clear_selection(self):
        """清除所有选择"""
        for checkbox in self._checkboxes.values():
            checkbox.setChecked(False)
    
    def select_all(self):
        """全选"""
        for checkbox in self._checkboxes.values():
            checkbox.setChecked(True)
    
    def get_invoice_by_row(self, row: int) -> Invoice:
        """根据行号获取发票对象"""
        if 0 <= row < len(self._invoices):
            return self._invoices[row]
        return None
    
    def get_current_invoice(self) -> Invoice:
        """获取当前选中行的发票"""
        row = self.currentRow()
        return self.get_invoice_by_row(row)
