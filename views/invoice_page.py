"""发票管理页面（核心页面）"""

import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                              QFileDialog, QMessageBox, QLabel)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QDragLeaveEvent

from views.toolbar import InvoiceToolbar
from views.filter_bar import FilterBar
from views.search_bar import SearchBar
from views.invoice_table import InvoiceTable
from views.detail_panel import DetailPanel
from views.import_result_dialog import ImportResultDialog
from views.progress_dialog import ProgressDialog
from views.confirm_dialog import ConfirmDialog

from services.import_service import import_service
from services.invoice_service import invoice_service
from services.export_service import export_service
from database.invoice_dao import FilterCriteria
from models.invoice import Invoice
from utils.file_utils import is_supported_file, get_files_from_folder


class InvoicePage(QWidget):
    """发票管理页面"""
    
    navigate_to_ai_page = pyqtSignal(list)  # 请求跳转到 AI 识别页面，携带文件列表
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_invoices: list[Invoice] = []
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """初始化 UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 启用拖拽导入
        self.setAcceptDrops(True)
        
        # 工具栏
        self._toolbar = InvoiceToolbar()
        main_layout.addWidget(self._toolbar)
        
        # 筛选栏
        self._filter_bar = FilterBar()
        main_layout.addWidget(self._filter_bar)
        
        # 搜索栏
        self._search_bar = SearchBar()
        main_layout.addWidget(self._search_bar)
        
        # 主内容区域（表格 + 详情面板）
        splitter = QSplitter(Qt.Horizontal)
        
        # 表格
        self._table = InvoiceTable()
        self._table.setAcceptDrops(False)  # 防止表格截获拖拽事件
        splitter.addWidget(self._table)
        
        # 详情面板
        self._detail_panel = DetailPanel()
        self._detail_panel.setMinimumWidth(300)
        self._detail_panel.setMaximumWidth(400)
        splitter.addWidget(self._detail_panel)
        
        # 设置分割比例
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter, 1)
        
        # 状态栏
        self._status_bar = QWidget()
        status_layout = QHBoxLayout(self._status_bar)
        status_layout.setContentsMargins(10, 5, 10, 5)
        
        self._status_label = QLabel("共 0 张发票")
        self._status_label.setStyleSheet("color: #666;")
        status_layout.addWidget(self._status_label)
        
        status_layout.addStretch()
        
        self._selected_label = QLabel("")
        self._selected_label.setStyleSheet("color: #666;")
        status_layout.addWidget(self._selected_label)
        
        main_layout.addWidget(self._status_bar)
    
    def _connect_signals(self):
        """连接信号"""
        # 工具栏信号
        self._toolbar.import_file.connect(self._on_import_file)
        self._toolbar.import_folder.connect(self._on_import_folder)
        self._toolbar.export_excel.connect(self._on_export_excel)
        self._toolbar.clear_db.connect(self._on_clear_db)
        
        # 筛选栏信号
        self._filter_bar.filter_changed.connect(self._on_filter_changed)
        
        # 搜索栏信号
        self._search_bar.search_triggered.connect(self._on_search)
        self._search_bar.reset_triggered.connect(self._on_reset)
        
        # 表格信号
        self._table.row_selected.connect(self._on_row_selected)
        
        # 详情面板信号
        self._detail_panel.field_updated.connect(self._on_field_updated)
        
        # 导入服务信号
        import_service.progress_updated.connect(self._on_import_progress)
        import_service.import_finished.connect(self._on_import_finished)
    
    def refresh(self):
        """刷新数据"""
        self._load_data()
    
    def _load_data(self):
        """加载数据"""
        criteria = self._build_filter_criteria()
        self._current_invoices = invoice_service.query(criteria)
        self._table.populate(self._current_invoices)
        self._update_status()
    
    def _build_filter_criteria(self) -> FilterCriteria:
        """构建筛选条件"""
        return FilterCriteria(
            business_type=self._filter_bar.get_business_type() or None,
            invoice_type=self._filter_bar.get_invoice_type() or None,
            reimbursement_status=self._filter_bar.get_reimbursement_status() or None,
            date_from=self._filter_bar.get_date_from(),
            date_to=self._filter_bar.get_date_to(),
            search_text=self._search_bar.get_search_text() or None
        )
    
    def _update_status(self):
        """更新状态栏"""
        total = len(self._current_invoices)
        selected = len(self._table.get_selected_ids())
        
        self._status_label.setText(f"共 {total} 张发票")
        
        if selected > 0:
            self._selected_label.setText(f"已选中 {selected} 张")
        else:
            self._selected_label.setText("")
    
    # === 工具栏事件 ===
    
    def _on_import_file(self):
        """导入文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择发票文件",
            "",
            "发票文件 (*.xml *.pdf *.ofd);;所有文件 (*.*)"
        )
        
        if files:
            self._start_import(files)
    
    def _on_import_folder(self):
        """导入文件夹"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择文件夹"
        )
        
        if folder:
            files = import_service.import_folder(folder)
            if files:
                self._start_import(files)
            else:
                QMessageBox.information(
                    self, "提示",
                    f"文件夹中没有找到支持的发票文件:\n{folder}"
                )
    
    def _start_import(self, files: list[str]):
        """开始导入"""
        import_service.import_files_async(files)
        
        # 显示进度对话框
        self._progress_dialog = ProgressDialog(self)
        self._progress_dialog.cancelled.connect(import_service.cancel_import)
        self._progress_dialog.show()
    
    def _on_import_progress(self, current: int, total: int, filename: str):
        """导入进度更新"""
        if hasattr(self, '_progress_dialog'):
            self._progress_dialog.update_progress(current, total, filename)
    
    def _on_import_finished(self, result):
        """导入完成"""
        if hasattr(self, '_progress_dialog'):
            self._progress_dialog.close_dialog()
        
        # 显示结果对话框
        dialog = ImportResultDialog(result, self)
        dialog.ai_learn_clicked.connect(self._on_ai_learn_requested)
        dialog.ai_batch_clicked.connect(self._on_ai_batch_requested)
        dialog.exec_()
        
        # 刷新数据
        self._load_data()
    
    def _on_ai_learn_requested(self, file_path: str):
        """处理 AI 学习请求（从导入结果弹窗触发）"""
        from views.ai_learn_dialog import AILearnDialog
        learn_dialog = AILearnDialog(file_path, self)
        learn_dialog.invoice_imported.connect(self._load_data)
        learn_dialog.exec_()

    def _on_ai_batch_requested(self, file_paths: list):
        """处理 AI 批量识别请求（从导入结果弹窗触发）"""
        self.navigate_to_ai_page.emit(file_paths)
    
    def _on_export_excel(self):
        """导出 Excel"""
        if not self._current_invoices:
            QMessageBox.information(self, "提示", "没有数据可导出")
            return
        
        filename = export_service.get_default_filename()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 Excel",
            filename,
            "Excel 文件 (*.xlsx)"
        )
        
        if file_path:
            success = export_service.export_to_excel(
                self._current_invoices,
                file_path,
                title="发票数据"
            )
            
            if success:
                QMessageBox.information(self, "导出成功", f"已导出到:\n{file_path}")
            else:
                QMessageBox.warning(self, "导出失败", "导出 Excel 失败，请重试")
    
    def _on_clear_db(self):
        """清空数据库"""
        count = invoice_service.count()
        if count == 0:
            QMessageBox.information(self, "提示", "数据库中没有数据")
            return
        
        confirmed = ConfirmDialog.confirm(
            self,
            "清空数据库",
            f"确定要删除全部 {count} 张发票数据吗？\n\n此操作不可恢复！"
        )
        
        if confirmed:
            if invoice_service.clear_all():
                QMessageBox.information(self, "完成", "数据库已清空")
                self._load_data()
                self._detail_panel.clear()
            else:
                QMessageBox.warning(self, "失败", "清空数据库失败")
    
    # === 筛选搜索事件 ===
    
    def _on_filter_changed(self):
        """筛选条件变化"""
        self._load_data()
    
    def _on_search(self, text: str):
        """搜索"""
        self._load_data()
    
    def _on_reset(self):
        """重置"""
        self._filter_bar.reset()
        self._load_data()
    
    # === 表格事件 ===
    
    def _on_row_selected(self, invoice_id: int):
        """行选中"""
        invoice = invoice_service.get_by_id(invoice_id)
        if invoice:
            self._detail_panel.show_invoice(invoice)
    
    # === 详情面板事件 ===
    
    def _on_field_updated(self, invoice_id: int, field: str, value: str):
        """字段更新"""
        if invoice_service.update_field(invoice_id, field, value):
            self._load_data()
        else:
            QMessageBox.warning(self, "更新失败", f"更新字段 {field} 失败")
    
    # === 拖拽导入事件 ===
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if path and (is_supported_file(path) or os.path.isdir(path)):
                    event.acceptProposedAction()
                    self._show_drop_indicator(True)
                    return
        event.ignore()
    
    def dragLeaveEvent(self, event: QDragLeaveEvent):
        """拖拽离开事件"""
        self._show_drop_indicator(False)
    
    def dropEvent(self, event: QDropEvent):
        """拖拽放置事件"""
        self._show_drop_indicator(False)
        
        urls = event.mimeData().urls()
        file_paths = []
        
        for url in urls:
            path = url.toLocalFile()
            if not path:
                continue
            if os.path.isdir(path):
                # 文件夹：扫描内部支持文件
                file_paths.extend(get_files_from_folder(path))
            elif is_supported_file(path):
                file_paths.append(path)
        
        if file_paths:
            self._start_import(file_paths)
        else:
            QMessageBox.information(
                self, "提示",
                "拖入的文件中没有找到支持的发票文件\n"
                "支持格式: XML, PDF, OFD"
            )
        
        event.acceptProposedAction()
    
    def _show_drop_indicator(self, show: bool):
        """显示/隐藏拖拽指示器"""
        if show:
            self.setStyleSheet("""
                InvoicePage {
                    border: 2px dashed #1890ff;
                    background-color: rgba(24, 144, 255, 0.03);
                }
            """)
        else:
            self.setStyleSheet("")
