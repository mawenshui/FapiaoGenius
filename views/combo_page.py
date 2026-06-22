"""智能凑票页面"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QRadioButton, QButtonGroup, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QGroupBox, QFormLayout, QAbstractItemView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor

from services.combo_service import combo_service, ComboParams, ComboSolution
from core.logger import logger


class ComboWorker(QThread):
    """凑票计算工作线程"""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, params: ComboParams):
        super().__init__()
        self.params = params
    
    def run(self):
        try:
            solutions = combo_service.find_combinations(self.params)
            self.finished.emit(solutions)
        except Exception as e:
            logger.error(f"凑票计算失败: {e}")
            self.error.emit(str(e))


class ComboPage(QWidget):
    """智能凑票页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._solutions = []
        self._worker = None
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # 标题
        title = QLabel("💰 智能凑票")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #333;")
        layout.addWidget(title)
        
        # 参数配置区
        params_group = QGroupBox("凑票参数")
        params_layout = QFormLayout(params_group)
        
        # 目标金额
        amount_layout = QHBoxLayout()
        self._target_amount = QLineEdit()
        self._target_amount.setPlaceholderText("请输入目标金额")
        amount_layout.addWidget(self._target_amount)
        amount_layout.addWidget(QLabel("元"))
        params_layout.addRow("目标金额:", amount_layout)
        
        # 金额模式
        mode_widget = QWidget()
        mode_layout = QHBoxLayout(mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        self._mode_group = QButtonGroup()
        
        self._mode_less = QRadioButton("可少于规定金额")
        self._mode_greater = QRadioButton("可大于规定金额")
        self._mode_less.setChecked(True)
        
        self._mode_group.addButton(self._mode_less, 0)
        self._mode_group.addButton(self._mode_greater, 1)
        
        mode_layout.addWidget(self._mode_less)
        mode_layout.addWidget(self._mode_greater)
        mode_layout.addStretch()
        params_layout.addRow("金额模式:", mode_widget)
        
        # 挑选策略
        strategy_widget = QWidget()
        strategy_layout = QHBoxLayout(strategy_widget)
        strategy_layout.setContentsMargins(0, 0, 0, 0)
        self._strategy_group = QButtonGroup()
        
        self._strategy_fewest = QRadioButton("张数最少")
        self._strategy_most = QRadioButton("张数最多")
        self._strategy_large = QRadioButton("大额优先")
        self._strategy_small = QRadioButton("小额优先")
        self._strategy_fewest.setChecked(True)
        
        self._strategy_group.addButton(self._strategy_fewest, 0)
        self._strategy_group.addButton(self._strategy_most, 1)
        self._strategy_group.addButton(self._strategy_large, 2)
        self._strategy_group.addButton(self._strategy_small, 3)
        
        strategy_layout.addWidget(self._strategy_fewest)
        strategy_layout.addWidget(self._strategy_most)
        strategy_layout.addWidget(self._strategy_large)
        strategy_layout.addWidget(self._strategy_small)
        strategy_layout.addStretch()
        params_layout.addRow("挑选策略:", strategy_widget)
        
        # 发票范围过滤
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        
        filter_layout.addWidget(QLabel("业务类型:"))
        self._business_type_filter = QComboBox()
        self._business_type_filter.addItem("全部", None)
        self._business_type_filter.addItem("餐饮", "餐饮")
        self._business_type_filter.addItem("交通", "交通")
        self._business_type_filter.addItem("住宿", "住宿")
        self._business_type_filter.addItem("办公", "办公")
        self._business_type_filter.addItem("其他", "其他")
        filter_layout.addWidget(self._business_type_filter)
        
        filter_layout.addWidget(QLabel("发票类型:"))
        self._invoice_type_filter = QComboBox()
        self._invoice_type_filter.addItem("全部", None)
        self._invoice_type_filter.addItem("增值税普通发票", "增值税普通发票")
        self._invoice_type_filter.addItem("增值税专用发票", "增值税专用发票")
        self._invoice_type_filter.addItem("电子发票", "电子发票")
        filter_layout.addWidget(self._invoice_type_filter)
        
        filter_layout.addStretch()
        params_layout.addRow("发票范围:", filter_widget)
        
        layout.addWidget(params_group)
        
        # 计算按钮
        btn_layout = QHBoxLayout()
        self._calc_btn = QPushButton("🚀 开始计算")
        self._calc_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self._calc_btn.clicked.connect(self._on_calculate)
        btn_layout.addWidget(self._calc_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 结果展示区
        result_group = QGroupBox("计算结果")
        result_layout = QVBoxLayout(result_group)
        
        # 方案表格
        self._result_table = QTableWidget()
        self._result_table.setColumnCount(5)
        self._result_table.setHorizontalHeaderLabels([
            "方案编号", "发票张数", "合计金额", "差额", "操作"
        ])
        self._result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._result_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._result_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        result_layout.addWidget(self._result_table)
        
        # 详情展开区
        self._detail_table = QTableWidget()
        self._detail_table.setColumnCount(5)
        self._detail_table.setHorizontalHeaderLabels([
            "发票号码", "开票日期", "销售方", "金额", "业务类型"
        ])
        self._detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._detail_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._detail_table.setMaximumHeight(200)
        result_layout.addWidget(self._detail_table)
        
        # 一键设置状态按钮
        status_layout = QHBoxLayout()
        
        self._btn_processing = QPushButton("一键设为报销中")
        self._btn_processed = QPushButton("一键设为已报销")
        
        for btn in [self._btn_processed, self._btn_processing]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #0b7dda;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                }
            """)
        
        self._btn_processing.clicked.connect(lambda: self._set_status("报销中"))
        self._btn_processed.clicked.connect(lambda: self._set_status("已报销"))
        
        status_layout.addWidget(self._btn_processing)
        status_layout.addWidget(self._btn_processed)
        status_layout.addStretch()
        result_layout.addLayout(status_layout)
        
        layout.addWidget(result_group)
        
        # 连接表格选择信号
        self._result_table.itemSelectionChanged.connect(self._on_solution_selected)
    
    def _on_calculate(self):
        """开始计算"""
        # 验证输入
        try:
            target = float(self._target_amount.text())
            if target <= 0:
                raise ValueError("金额必须大于 0")
        except ValueError as e:
            QMessageBox.warning(self, "输入错误", f"目标金额无效: {e}")
            return
        
        # 构建参数
        mode_map = {0: "less", 1: "greater"}
        strategy_map = {0: "fewest", 1: "most", 2: "large_first", 3: "small_first"}
        
        params = ComboParams(
            target_amount=target,
            amount_mode=mode_map.get(self._mode_group.checkedId(), "less"),
            strategy=strategy_map.get(self._strategy_group.checkedId(), "fewest"),
            business_type=self._business_type_filter.currentData(),
            invoice_type=self._invoice_type_filter.currentData(),
        )
        
        # 禁用按钮，启动工作线程
        self._calc_btn.setEnabled(False)
        self._calc_btn.setText("计算中...")
        self._result_table.setRowCount(0)
        self._detail_table.setRowCount(0)
        
        self._worker = ComboWorker(params)
        self._worker.finished.connect(self._on_calc_finished)
        self._worker.error.connect(self._on_calc_error)
        self._worker.start()
    
    def _on_calc_finished(self, solutions: list):
        """计算完成"""
        self._calc_btn.setEnabled(True)
        self._calc_btn.setText("🚀 开始计算")
        self._solutions = solutions
        
        if not solutions:
            QMessageBox.information(self, "计算结果", "未找到符合条件的凑票方案")
            return
        
        # 填充结果表格
        self._result_table.setRowCount(len(solutions))
        
        for i, sol in enumerate(solutions):
            # 方案编号
            item = QTableWidgetItem(f"方案 {i + 1}")
            item.setData(Qt.UserRole, i)
            self._result_table.setItem(i, 0, item)
            
            # 发票张数
            self._result_table.setItem(i, 1, QTableWidgetItem(str(sol.count)))
            
            # 合计金额
            self._result_table.setItem(i, 2, QTableWidgetItem(f"¥{sol.total_amount:,.2f}"))
            
            # 差额
            diff_item = QTableWidgetItem(f"¥{sol.difference:+,.2f}")
            if sol.difference > 0:
                diff_item.setForeground(QColor("#f44336"))  # 红色表示超出
            elif sol.difference < 0:
                diff_item.setForeground(QColor("#ff9800"))  # 橙色表示不足
            else:
                diff_item.setForeground(QColor("#4CAF50"))  # 绿色表示正好
            self._result_table.setItem(i, 3, diff_item)
            
            # 操作按钮
            detail_btn = QPushButton("查看详情")
            detail_btn.clicked.connect(lambda checked, idx=i: self._show_detail(idx))
            self._result_table.setCellWidget(i, 4, detail_btn)
        
        logger.info(f"凑票计算完成: {len(solutions)} 个方案")
    
    def _on_calc_error(self, error_msg: str):
        """计算错误"""
        self._calc_btn.setEnabled(True)
        self._calc_btn.setText("🚀 开始计算")
        QMessageBox.critical(self, "计算失败", f"凑票计算出错: {error_msg}")
    
    def _on_solution_selected(self):
        """方案被选中"""
        rows = self._result_table.selectionModel().selectedRows()
        if rows:
            idx = rows[0].row()
            self._show_detail(idx)
    
    def _show_detail(self, solution_idx: int):
        """显示方案详情"""
        if solution_idx < 0 or solution_idx >= len(self._solutions):
            return
        
        sol = self._solutions[solution_idx]
        self._detail_table.setRowCount(len(sol.invoices))
        
        for i, inv in enumerate(sol.invoices):
            self._detail_table.setItem(i, 0, QTableWidgetItem(inv.invoice_number))
            self._detail_table.setItem(i, 1, QTableWidgetItem(inv.invoice_date))
            self._detail_table.setItem(i, 2, QTableWidgetItem(inv.seller_name))
            self._detail_table.setItem(i, 3, QTableWidgetItem(f"¥{inv.total_amount:,.2f}"))
            self._detail_table.setItem(i, 4, QTableWidgetItem(inv.business_type))
    
    def _set_status(self, status: str):
        """一键设置报销状态"""
        rows = self._result_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "提示", "请先选择一个凑票方案")
            return
        
        idx = rows[0].row()
        if idx < 0 or idx >= len(self._solutions):
            return
        
        sol = self._solutions[idx]
        invoice_ids = [inv.id for inv in sol.invoices if inv.id]
        
        if not invoice_ids:
            QMessageBox.warning(self, "提示", "该方案没有可更新的发票")
            return
        
        reply = QMessageBox.question(
            self,
            "确认操作",
            f"确定将方案 {idx + 1} 中的 {len(invoice_ids)} 张发票设为「{status}」吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            updated = combo_service.set_reimbursement_status(invoice_ids, status)
            QMessageBox.information(
                self,
                "操作完成",
                f"成功更新 {updated} 张发票的报销状态为「{status}」"
            )
            logger.info(f"一键设置报销状态: {updated} 张发票 -> {status}")
