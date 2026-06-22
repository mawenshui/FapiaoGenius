"""AI 学习对话框"""

from pathlib import Path
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QPushButton, QFormLayout, QGroupBox,
                              QComboBox, QDoubleSpinBox, QMessageBox,
                              QProgressBar, QInputDialog, QTextEdit,
                              QScrollArea, QWidget, QFrame, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from services.ai_service import ai_service
from services.rule_service import rule_service
from database.invoice_dao import invoice_dao
from models.invoice import Invoice
from models.parse_rule import ParseRule
from core.constants import BusinessType, InvoiceType
from core.logger import logger


class AIWorker(QThread):
    """AI 分析工作线程"""
    finished = pyqtSignal(object)   # dict 或 Exception
    progress = pyqtSignal(str)      # 状态文本

    def __init__(self, file_path: str, mode: str = 'analyze'):
        super().__init__()
        self.file_path = file_path
        self.mode = mode

    def run(self):
        try:
            if self.mode == 'analyze':
                logger.info(f"[AI学习] 开始分析发票: {self.file_path}")
                self.progress.emit("正在提取文件内容...")
                result = ai_service.analyze_invoice(self.file_path)
                logger.info(
                    f"[AI学习] 分析完成: 发票号码={result.get('invoice_number', '')}, "
                    f"购买方={result.get('buyer_name', '')}, "
                    f"金额={result.get('total_amount', 0)}"
                )
                self.finished.emit(result)
            else:
                logger.info(f"[AI学习] 开始学习格式: {self.file_path}")
                self.progress.emit("正在提取文件内容并学习格式...")
                result = ai_service.learn_format(self.file_path)
                rule_name_ai = result.get('rule_name', '')
                match_keywords = result.get('match_keywords', [])
                extraction_config = result.get('extraction_config', {})
                logger.info(
                    f"[AI学习] 学习完成: 规则名={rule_name_ai}, "
                    f"关键词={match_keywords}, "
                    f"提取配置字段={list(extraction_config.keys())}"
                )
                self.finished.emit(result)
        except Exception as e:
            logger.error(f"[AI学习] {self.mode} 失败: {e}", exc_info=True)
            self.finished.emit(e)


class AILearnDialog(QDialog):
    """AI 学习对话框"""
    invoice_imported = pyqtSignal()  # 通知外部刷新数据

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self._file_path = file_path
        self._worker = None
        self._learn_result = None  # 存储 learn_format 的结果
        self.setWindowTitle("AI 智能识别")
        self.setModal(True)
        self.setMinimumSize(580, 650)
        self._init_ui()

    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 15, 20, 15)

        # === 文件信息 ===
        file_widget = QWidget()
        file_layout = QHBoxLayout(file_widget)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.addWidget(QLabel("📄"))
        name = Path(self._file_path).name
        file_label = QLabel(f"当前文件: <b>{name}</b>")
        file_layout.addWidget(file_label, 1)
        open_btn = QPushButton("打开文件")
        open_btn.setFixedWidth(80)
        open_btn.setStyleSheet("color: #1890ff; border: none; text-decoration: underline;")
        open_btn.clicked.connect(self._open_file)
        file_layout.addWidget(open_btn)
        layout.addWidget(file_widget)

        # === AI 连接状态 ===
        conn_widget = QWidget()
        conn_layout = QHBoxLayout(conn_widget)
        conn_layout.setContentsMargins(0, 0, 0, 0)
        conn_layout.addWidget(QLabel("API 状态:"))
        self._conn_status = QLabel("未测试")
        self._conn_status.setStyleSheet("color: #999;")
        conn_layout.addWidget(self._conn_status, 1)
        test_btn = QPushButton("测试连接")
        test_btn.setStyleSheet("""
            QPushButton { background-color: #52c41a; color: white; border: none;
                          padding: 5px 15px; border-radius: 3px; }
            QPushButton:hover { background-color: #73d13d; }
        """)
        test_btn.clicked.connect(self._on_test_connection)
        conn_layout.addWidget(test_btn)
        layout.addWidget(conn_widget)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #e8e8e8;")
        line.setFixedHeight(1)
        layout.addWidget(line)

        # === 操作按钮 ===
        action_layout = QHBoxLayout()
        self._analyze_btn = QPushButton("🔍 开始 AI 识别")
        self._analyze_btn.setStyleSheet("""
            QPushButton { background-color: #722ed1; color: white; border: none;
                          padding: 10px 25px; border-radius: 4px; font-weight: bold; font-size: 14px; }
            QPushButton:hover { background-color: #9254de; }
            QPushButton:disabled { background-color: #d9d9d9; }
        """)
        self._analyze_btn.clicked.connect(self._on_start_analysis)
        action_layout.addWidget(self._analyze_btn)
        action_layout.addStretch()
        layout.addLayout(action_layout)

        # === 进度区 ===
        self._progress_widget = QWidget()
        prog_layout = QVBoxLayout(self._progress_widget)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet("color: #1890ff;")
        prog_layout.addWidget(self._progress_label)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # 不确定进度
        self._progress_bar.setMaximumHeight(6)
        prog_layout.addWidget(self._progress_bar)
        self._progress_widget.hide()
        layout.addWidget(self._progress_widget)

        # === 结果区（可滚动） ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        result_widget = QWidget()
        self._result_layout = QFormLayout(result_widget)
        self._result_layout.setSpacing(10)
        self._result_layout.setContentsMargins(0, 5, 0, 5)

        title_label = QLabel("识别结果")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        self._result_layout.addRow(title_label, None)

        # 发票号码
        self._inv_number_edit = QLineEdit()
        self._inv_number_edit.setPlaceholderText("发票号码")
        self._result_layout.addRow("发票号码:", self._inv_number_edit)

        # 开票日期
        self._inv_date_edit = QLineEdit()
        self._inv_date_edit.setPlaceholderText("YYYY-MM-DD")
        self._result_layout.addRow("开票日期:", self._inv_date_edit)

        # 购买方
        self._buyer_edit = QLineEdit()
        self._buyer_edit.setPlaceholderText("购买方名称")
        self._result_layout.addRow("购买方:", self._buyer_edit)

        # 销售方
        self._seller_edit = QLineEdit()
        self._seller_edit.setPlaceholderText("销售方名称")
        self._result_layout.addRow("销售方:", self._seller_edit)

        # 不含税金额
        self._amount_spin = self._make_amount_spin()
        self._result_layout.addRow("不含税金额:", self._amount_spin)

        # 税额
        self._tax_spin = self._make_amount_spin()
        self._result_layout.addRow("税额:", self._tax_spin)

        # 价税合计
        self._total_spin = self._make_amount_spin()
        self._result_layout.addRow("价税合计:", self._total_spin)

        # 发票类型
        self._inv_type_combo = QComboBox()
        self._inv_type_combo.addItems(InvoiceType.all_values())
        self._result_layout.addRow("发票类型:", self._inv_type_combo)

        # 业务类型
        self._biz_type_combo = QComboBox()
        self._biz_type_combo.addItems(BusinessType.all_values())
        self._result_layout.addRow("业务类型:", self._biz_type_combo)

        # 验证状态
        self._validation_label = QLabel("")
        self._validation_label.setWordWrap(True)
        self._result_layout.addRow("", self._validation_label)

        # 金额实时校验信号
        self._amount_spin.valueChanged.connect(self._validate_amounts)
        self._tax_spin.valueChanged.connect(self._validate_amounts)
        self._total_spin.valueChanged.connect(self._validate_amounts)

        scroll.setWidget(result_widget)
        layout.addWidget(scroll, 1)

        # === 底部按钮 ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._save_rule_btn = QPushButton("保存为新规则")
        self._save_rule_btn.setEnabled(False)
        self._save_rule_btn.setStyleSheet("""
            QPushButton { background-color: #fa8c16; color: white; border: none;
                          padding: 8px 18px; border-radius: 4px; }
            QPushButton:hover { background-color: #ffa940; }
            QPushButton:disabled { background-color: #d9d9d9; }
        """)
        self._save_rule_btn.clicked.connect(self._on_save_as_rule)
        btn_layout.addWidget(self._save_rule_btn)

        self._import_btn = QPushButton("导入此发票")
        self._import_btn.setEnabled(False)
        self._import_btn.setStyleSheet("""
            QPushButton { background-color: #1890ff; color: white; border: none;
                          padding: 8px 18px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #40a9ff; }
            QPushButton:disabled { background-color: #d9d9d9; }
        """)
        self._import_btn.clicked.connect(self._on_import_invoice)
        btn_layout.addWidget(self._import_btn)

        cancel_btn = QPushButton("关闭")
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _make_amount_spin(self) -> QDoubleSpinBox:
        """创建金额输入控件"""
        spin = QDoubleSpinBox()
        spin.setRange(0, 99999999)
        spin.setDecimals(2)
        spin.setPrefix("¥ ")
        spin.setStyleSheet("QDoubleSpinBox { padding: 4px; }")
        return spin

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def _open_file(self):
        """打开源文件"""
        import os
        try:
            if os.path.exists(self._file_path):
                os.startfile(self._file_path)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法打开文件: {e}")

    def _on_test_connection(self):
        """测试连接"""
        self._conn_status.setText("测试中...")
        self._conn_status.setStyleSheet("color: #faad14;")
        QApplication = __import__('PyQt5.QtWidgets', fromlist=['QApplication']).QApplication
        QApplication.processEvents()

        success, message = ai_service.test_connection()
        if success:
            self._conn_status.setText(f"✅ {message}")
            self._conn_status.setStyleSheet("color: #52c41a;")
        else:
            self._conn_status.setText(f"❌ {message}")
            self._conn_status.setStyleSheet("color: #ff4d4f;")

    def _on_start_analysis(self):
        """开始 AI 分析"""
        # 先保存配置（如果用户修改了）
        self._analyze_btn.setEnabled(False)
        self._progress_widget.show()
        self._progress_label.setText("正在调用 AI 分析...")
        self._validation_label.setText("")

        self._worker = AIWorker(self._file_path, mode='analyze')
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_analysis_finished)
        self._worker.start()

    def _on_worker_progress(self, text: str):
        """工作线程进度更新"""
        self._progress_label.setText(text)

    def _cleanup_worker(self):
        """安全清理工作线程，避免 QThread 在线程运行时被销毁"""
        if self._worker is not None:
            self._worker.wait(5000)  # 等待线程完全结束（最多 5 秒）
            self._worker.deleteLater()  # 延迟到事件循环中销毁
            self._worker = None

    def _on_analysis_finished(self, result):
        """分析完成回调"""
        self._progress_widget.hide()
        self._analyze_btn.setEnabled(True)
        self._cleanup_worker()

        if isinstance(result, Exception):
            QMessageBox.warning(self, "AI 识别失败", str(result))
            return

        # 填充结果
        self._fill_results(result)
        self._save_rule_btn.setEnabled(True)
        self._import_btn.setEnabled(True)

        # 显示 confidence
        confidence = result.get('confidence', '')
        if confidence == 'high':
            conf_text = "识别置信度: 🟢 高"
            conf_color = "color: #52c41a;"
        elif confidence == 'medium':
            conf_text = "识别置信度: 🟡 中"
            conf_color = "color: #faad14;"
        else:
            conf_text = "识别置信度: 🔴 低"
            conf_color = "color: #ff4d4f;"

        # 显示 validation warning
        warning = result.get('validation_warning', '')
        if warning:
            self._validation_label.setText(f"⚠️ {warning}")
            self._validation_label.setStyleSheet("color: #faad14;")
        else:
            self._validation_label.setText(f"✅ {conf_text}  |  金额校验通过")
            self._validation_label.setStyleSheet("color: #52c41a;")

    def _fill_results(self, data: dict):
        """将 AI 返回的数据填充到表单"""
        self._inv_number_edit.setText(str(data.get('invoice_number', '')))
        self._inv_date_edit.setText(str(data.get('invoice_date', '')))
        self._buyer_edit.setText(str(data.get('buyer_name', '')))
        self._seller_edit.setText(str(data.get('seller_name', '')))

        self._amount_spin.setValue(float(data.get('amount_without_tax', 0)))
        self._tax_spin.setValue(float(data.get('tax_amount', 0)))
        self._total_spin.setValue(float(data.get('total_amount', 0)))

        # 发票类型
        inv_type = data.get('invoice_type', '')
        idx = self._inv_type_combo.findText(inv_type)
        if idx >= 0:
            self._inv_type_combo.setCurrentIndex(idx)

        # 业务类型
        biz_type = data.get('business_type', '')
        idx = self._biz_type_combo.findText(biz_type)
        if idx >= 0:
            self._biz_type_combo.setCurrentIndex(idx)

    def _validate_amounts(self):
        """实时校验金额"""
        amount = self._amount_spin.value()
        tax = self._tax_spin.value()
        total = self._total_spin.value()

        if amount > 0 and total > 0:
            expected = amount + tax
            diff = abs(total - expected)
            if diff > 0.02:
                self._validation_label.setText(
                    f"⚠️ 金额校验: {amount:.2f} + {tax:.2f} = {expected:.2f}，"
                    f"但价税合计为 {total:.2f}，差额 {diff:.2f}"
                )
                self._validation_label.setStyleSheet("color: #faad14;")
            else:
                self._validation_label.setText("✅ 金额校验通过")
                self._validation_label.setStyleSheet("color: #52c41a;")

    def _on_save_as_rule(self):
        """保存为新规则"""
        # 先调用 learn_format 获取规则建议
        self._analyze_btn.setEnabled(False)
        self._save_rule_btn.setEnabled(False)
        self._progress_widget.show()
        self._progress_label.setText("正在学习发票格式...")

        self._worker = AIWorker(self._file_path, mode='learn')
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_learn_finished)
        self._worker.start()

    def _on_learn_finished(self, result):
        """学习格式完成回调"""
        self._progress_widget.hide()
        self._analyze_btn.setEnabled(True)
        self._save_rule_btn.setEnabled(True)
        self._cleanup_worker()

        if isinstance(result, Exception):
            QMessageBox.warning(self, "AI 学习失败", str(result))
            return

        self._learn_result = result
        default_name = result.get('rule_name', '自定义规则')
        extraction_config = result.get('extraction_config', {})

        # === 验证规则正则是否能正确提取 ===
        validation_report = self._validate_extraction_config(extraction_config)

        # 让用户确认/修改规则名称
        prompt_text = "请输入规则名称:"
        if validation_report:
            prompt_text = (
                f"规则提取测试结果：\n\n{validation_report}\n"
                f"────────────────────\n"
                f"注：未能提取的字段将在导入时自动降级补全。\n\n"
                f"请输入规则名称:"
            )

        name, ok = QInputDialog.getText(
            self, "保存规则",
            prompt_text,
            text=default_name
        )
        if not ok or not name.strip():
            return

        # 构造 ParseRule
        import uuid
        from datetime import datetime

        rule = ParseRule(
            id=f"ai_learned_{uuid.uuid4().hex[:8]}",
            rule_name=name.strip(),
            file_format=Path(self._file_path).suffix.lower().lstrip('.'),
            match_keywords=result.get('match_keywords', []),
            extraction_config=extraction_config,
            required_fields=["invoice_number", "invoice_date", "total_amount"],
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            is_builtin=False,
        )

        try:
            logger.info(
                f"[规则保存] 开始保存规则: {rule.rule_name}, "
                f"ID={rule.id}, 格式={rule.file_format}, "
                f"关键词={rule.match_keywords}, "
                f"提取配置字段={list(rule.extraction_config.keys())}"
            )
            rule_service.save_rule(rule)
            logger.info(f"[规则保存] 规则保存成功: {rule.rule_name}")
            QMessageBox.information(
                self, "保存成功",
                f"规则 '{rule.rule_name}' 已保存。\n"
                f"下次导入同类发票时将自动使用此规则解析。"
            )
        except Exception as e:
            logger.error(f"[规则保存] 保存失败: {e}", exc_info=True)
            QMessageBox.warning(self, "保存失败", f"规则保存失败: {e}")

    def _validate_extraction_config(self, config: dict) -> str:
        """
        验证 AI 建议的 extraction_config 正则能否从原文件中提取到内容
        
        Returns:
            str: 验证报告文本（空字符串表示全部通过）
        """
        import re
        from services.ai_service import ai_service
        
        if not config:
            return ""
        
        # 提取原文
        try:
            text = ai_service._extract_text_for_ai(self._file_path)
        except Exception:
            return ""
        
        if not text.strip():
            return ""
        
        # 测试每个字段的正则
        ok_fields = []
        fail_fields = []
        
        for field, field_config in config.items():
            # 兼容新旧格式
            if isinstance(field_config, dict):
                pattern = field_config.get('pattern', '')
            else:
                pattern = field_config

            if not pattern:
                fail_fields.append(f"  {field}: 无正则")
                continue

            try:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    value = match.group(1) if match.groups() else match.group(0)
                    value = value.strip()[:50]  # 截取前 50 字符展示
                    ok_fields.append(f"  ✓ {field}: {value}")
                else:
                    fail_fields.append(f"  ✗ {field}: 未匹配")
            except re.error as e:
                fail_fields.append(f"  ✗ {field}: 正则语法错误 ({e})")
        
        if not fail_fields:
            return ""  # 全部通过
        
        lines = []
        if ok_fields:
            lines.append("提取成功:")
            lines.extend(ok_fields)
        if fail_fields:
            lines.append("提取失败:")
            lines.extend(fail_fields)
        
        return "\n".join(lines)

    def _on_import_invoice(self):
        """导入此发票"""
        invoice = Invoice(
            business_type=self._biz_type_combo.currentText(),
            invoice_type=self._inv_type_combo.currentText(),
            invoice_number=self._inv_number_edit.text().strip(),
            invoice_date=self._inv_date_edit.text().strip(),
            buyer_name=self._buyer_edit.text().strip(),
            seller_name=self._seller_edit.text().strip(),
            amount_without_tax=self._amount_spin.value(),
            tax_amount=self._tax_spin.value(),
            total_amount=self._total_spin.value(),
            source_file_path=self._file_path,
            file_format=Path(self._file_path).suffix.lower().lstrip('.'),
            ai_learned=True,
        )

        # 验证必填字段
        if not invoice.invoice_number:
            QMessageBox.warning(self, "提示", "发票号码不能为空")
            return
        if not invoice.invoice_date:
            QMessageBox.warning(self, "提示", "开票日期不能为空")
            return

        # 检查重复
        if invoice_dao.exists_by_number(invoice.invoice_number):
            QMessageBox.warning(
                self, "重复",
                f"发票号码 {invoice.invoice_number} 已存在于数据库中"
            )
            return

        invoice.set_import_time()

        try:
            invoice_dao.insert(invoice)
            self.invoice_imported.emit()
            QMessageBox.information(self, "成功", "发票已导入数据库")
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"导入失败: {e}")

    def closeEvent(self, event):
        """关闭对话框时确保线程已清理"""
        self._cleanup_worker()
        super().closeEvent(event)
