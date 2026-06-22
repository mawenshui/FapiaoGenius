"""规则管理页面"""

import json
from pathlib import Path
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QTableWidget, QTableWidgetItem,
                              QHeaderView, QFileDialog, QMessageBox,
                              QDialog, QFormLayout, QLineEdit, QTextEdit,
                              QComboBox, QAbstractItemView, QSizePolicy)
from PyQt5.QtCore import Qt

from services.rule_service import rule_service
from models.parse_rule import ParseRule
from views.confirm_dialog import ConfirmDialog
from core.logger import logger


class RuleDetailDialog(QDialog):
    """规则详情对话框（只读/可编辑）"""

    def __init__(self, rule: ParseRule, editable: bool = False, parent=None):
        super().__init__(parent)
        self._rule = rule
        self._editable = editable
        self._saved = False
        self.setWindowTitle(f"规则详情 — {rule.rule_name}")
        self.setModal(True)
        self.setMinimumSize(520, 480)
        self._init_ui()

    def _init_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 15, 20, 15)

        # 规则 ID (只读)
        id_label = QLabel(self._rule.id)
        id_label.setStyleSheet("color: #999;")
        layout.addRow("规则 ID:", id_label)

        # 规则名称
        if self._editable:
            self._name_edit = QLineEdit(self._rule.rule_name)
            layout.addRow("规则名称:", self._name_edit)
        else:
            layout.addRow("规则名称:", QLabel(self._rule.rule_name))

        # 文件格式
        layout.addRow("文件格式:", QLabel(self._rule.file_format))

        # 来源
        source = "内置" if self._rule.is_builtin else "自定义"
        source_color = "#1890ff" if self._rule.is_builtin else "#52c41a"
        source_label = QLabel(source)
        source_label.setStyleSheet(f"color: {source_color}; font-weight: bold;")
        layout.addRow("来源:", source_label)

        # 匹配关键词
        if self._editable:
            self._keywords_edit = QLineEdit(", ".join(self._rule.match_keywords))
            self._keywords_edit.setPlaceholderText("用逗号分隔")
            layout.addRow("匹配关键词:", self._keywords_edit)
        else:
            layout.addRow("匹配关键词:", QLabel(", ".join(self._rule.match_keywords)))

        # 必填字段
        layout.addRow("必填字段:", QLabel(", ".join(self._rule.required_fields)))

        # 提取配置 (JSON)
        config_text = json.dumps(self._rule.extraction_config, ensure_ascii=False, indent=2)
        if self._editable:
            self._config_edit = QTextEdit()
            self._config_edit.setPlainText(config_text)
            self._config_edit.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 12px;")
            self._config_edit.setMinimumHeight(180)
            layout.addRow("提取配置:", self._config_edit)
        else:
            config_view = QTextEdit()
            config_view.setPlainText(config_text)
            config_view.setReadOnly(True)
            config_view.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 12px; background: #f5f5f5;")
            config_view.setMinimumHeight(180)
            layout.addRow("提取配置:", config_view)

        # 时间
        layout.addRow("创建时间:", QLabel(self._rule.created_at[:19] if self._rule.created_at else "—"))
        layout.addRow("更新时间:", QLabel(self._rule.updated_at[:19] if self._rule.updated_at else "—"))

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        if self._editable:
            save_btn = QPushButton("保存")
            save_btn.setStyleSheet("""
                QPushButton { background-color: #1890ff; color: white; border: none;
                              padding: 8px 25px; border-radius: 4px; font-weight: bold; }
                QPushButton:hover { background-color: #40a9ff; }
            """)
            save_btn.clicked.connect(self._on_save)
            btn_layout.addWidget(save_btn)

        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)

        layout.addRow("", btn_layout)

    def _on_save(self):
        """保存编辑"""
        self._rule.rule_name = self._name_edit.text().strip()
        self._rule.match_keywords = [
            kw.strip() for kw in self._keywords_edit.text().split(',') if kw.strip()
        ]
        # 解析 extraction_config
        try:
            config = json.loads(self._config_edit.toPlainText())
            self._rule.extraction_config = config
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "格式错误", f"提取配置 JSON 格式错误: {e}")
            return

        self._saved = True
        self.accept()

    @property
    def saved(self):
        return self._saved


class RulePage(QWidget):
    """规则管理页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # === 标题栏 ===
        header = QHBoxLayout()
        title = QLabel("规则管理")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton("刷新")
        refresh_btn.setStyleSheet("""
            QPushButton { background-color: #f0f0f0; border: 1px solid #d9d9d9;
                          padding: 6px 15px; border-radius: 3px; }
            QPushButton:hover { background-color: #e8e8e8; }
        """)
        refresh_btn.clicked.connect(self._load_rules)
        header.addWidget(refresh_btn)

        import_btn = QPushButton("导入规则")
        import_btn.setStyleSheet("""
            QPushButton { background-color: #52c41a; color: white; border: none;
                          padding: 6px 15px; border-radius: 3px; }
            QPushButton:hover { background-color: #73d13d; }
        """)
        import_btn.clicked.connect(self._on_import_rule)
        header.addWidget(import_btn)

        self._delete_all_btn = QPushButton("一键删除自定义")
        self._delete_all_btn.setStyleSheet("""
            QPushButton { background-color: #ff4d4f; color: white; border: none;
                          padding: 6px 15px; border-radius: 3px; }
            QPushButton:hover { background-color: #ff7875; }
            QPushButton:disabled { background-color: #d9d9d9; }
        """)
        self._delete_all_btn.clicked.connect(self._on_delete_all_custom)
        header.addWidget(self._delete_all_btn)

        layout.addLayout(header)

        # === 表格 ===
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            "规则名称", "文件格式", "匹配关键词", "来源", "更新时间", "操作"
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self._table.setColumnWidth(5, 200)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet("""
            QTableWidget { gridline-color: #f0f0f0; }
            QTableWidget::item { padding: 6px; }
            QHeaderView::section {
                background-color: #fafafa; border: 1px solid #e8e8e8;
                padding: 8px; font-weight: bold;
            }
        """)
        layout.addWidget(self._table, 1)

        # === 状态栏 ===
        self._status_label = QLabel("共 0 条规则")
        self._status_label.setStyleSheet("color: #999;")
        layout.addWidget(self._status_label)

    # ------------------------------------------------------------------
    # 数据加载
    # ------------------------------------------------------------------

    def _load_rules(self):
        """加载并显示所有规则"""
        rule_service.load_rules()
        rules = rule_service.get_all_rules()

        self._table.setRowCount(len(rules))
        for row, rule in enumerate(rules):
            self._populate_row(row, rule)

        self._status_label.setText(f"共 {len(rules)} 条规则")

    def _populate_row(self, row: int, rule: ParseRule):
        """填充一行数据"""
        # 规则名称
        name_item = QTableWidgetItem(rule.rule_name)
        name_item.setData(Qt.UserRole, rule.id)  # 存储 rule_id
        self._table.setItem(row, 0, name_item)

        # 文件格式
        self._table.setItem(row, 1, QTableWidgetItem(rule.file_format.upper()))

        # 匹配关键词
        kw_text = ", ".join(rule.match_keywords) if rule.match_keywords else "—"
        self._table.setItem(row, 2, QTableWidgetItem(kw_text))

        # 来源
        source = "内置" if rule.is_builtin else "自定义"
        source_item = QTableWidgetItem(source)
        if rule.is_builtin:
            source_item.setForeground(Qt.blue)
        else:
            source_item.setForeground(Qt.darkGreen)
        self._table.setItem(row, 3, source_item)

        # 更新时间
        time_text = rule.updated_at[:19] if rule.updated_at else "—"
        self._table.setItem(row, 4, QTableWidgetItem(time_text))

        # 操作按钮
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(5, 3, 5, 3)
        btn_layout.setSpacing(5)

        view_btn = QPushButton("查看")
        view_btn.setStyleSheet(self._btn_style("#1890ff"))
        view_btn.clicked.connect(lambda _, rid=rule.id: self._on_view_rule(rid))
        btn_layout.addWidget(view_btn)

        if not rule.is_builtin:
            edit_btn = QPushButton("编辑")
            edit_btn.setStyleSheet(self._btn_style("#fa8c16"))
            edit_btn.clicked.connect(lambda _, rid=rule.id: self._on_edit_rule(rid))
            btn_layout.addWidget(edit_btn)

            del_btn = QPushButton("删除")
            del_btn.setStyleSheet(self._btn_style("#ff4d4f"))
            del_btn.clicked.connect(lambda _, rid=rule.id: self._on_delete_rule(rid))
            btn_layout.addWidget(del_btn)

        btn_layout.addStretch()
        self._table.setCellWidget(row, 5, btn_widget)

    @staticmethod
    def _btn_style(color: str) -> str:
        return f"""
            QPushButton {{ background-color: {color}; color: white; border: none;
                          padding: 4px 12px; border-radius: 3px; font-size: 12px; }}
            QPushButton:hover {{ opacity: 0.85; }}
        """

    # ------------------------------------------------------------------
    # 操作
    # ------------------------------------------------------------------

    def _on_view_rule(self, rule_id: str):
        """查看规则详情"""
        rule = rule_service.get_by_id(rule_id)
        if not rule:
            QMessageBox.warning(self, "错误", "规则不存在")
            return
        dialog = RuleDetailDialog(rule, editable=False, parent=self)
        dialog.exec_()

    def _on_edit_rule(self, rule_id: str):
        """编辑规则"""
        rule = rule_service.get_by_id(rule_id)
        if not rule:
            QMessageBox.warning(self, "错误", "规则不存在")
            return
        if rule.is_builtin:
            QMessageBox.warning(self, "提示", "内置规则不可编辑")
            return

        dialog = RuleDetailDialog(rule, editable=True, parent=self)
        if dialog.exec_() == QDialog.Accepted and dialog.saved:
            try:
                from config.rule_manager import rule_manager
                rule_manager.save(rule)
                from database.rule_dao import rule_dao
                rule_dao.update(rule)
                rule_service.load_rules()
                QMessageBox.information(self, "成功", f"规则 '{rule.rule_name}' 已更新")
                self._load_rules()
            except Exception as e:
                QMessageBox.warning(self, "保存失败", f"保存失败: {e}")

    def _on_delete_rule(self, rule_id: str):
        """删除单个规则"""
        rule = rule_service.get_by_id(rule_id)
        if not rule:
            return
        if rule.is_builtin:
            QMessageBox.warning(self, "提示", "内置规则不可删除")
            return

        confirmed = ConfirmDialog.confirm(
            self, "确认删除",
            f"确定要删除规则 '{rule.rule_name}' 吗？"
        )
        if confirmed:
            rule_service.delete_rule(rule_id)
            self._load_rules()
            QMessageBox.information(self, "成功", f"规则 '{rule.rule_name}' 已删除")

    def _on_delete_all_custom(self):
        """一键删除所有自定义规则"""
        rules = rule_service.get_all_rules()
        custom_rules = [r for r in rules if not r.is_builtin]

        if not custom_rules:
            QMessageBox.information(self, "提示", "没有自定义规则可删除")
            return

        confirmed = ConfirmDialog.confirm(
            self, "确认批量删除",
            f"确定要删除全部 {len(custom_rules)} 条自定义规则吗？\n\n"
            f"此操作不可恢复！"
        )
        if not confirmed:
            return

        deleted = 0
        failed = 0
        for rule in custom_rules:
            try:
                rule_service.delete_rule(rule.id)
                deleted += 1
                logger.info(f"[规则删除] 已删除: {rule.rule_name} (ID={rule.id})")
            except Exception as e:
                failed += 1
                logger.error(f"[规则删除] 删除失败: {rule.rule_name}, 错误: {e}")

        self._load_rules()

        msg = f"已删除 {deleted} 条自定义规则"
        if failed:
            msg += f"，{failed} 条删除失败"
        QMessageBox.information(self, "完成", msg)
        logger.info(f"[规则删除] 批量删除完成: 成功={deleted}, 失败={failed}")

    def _on_import_rule(self):
        """导入规则 JSON 文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入规则", "", "JSON 文件 (*.json)"
        )
        if not file_path:
            return

        try:
            content = Path(file_path).read_text(encoding='utf-8')
            rule = ParseRule.from_json(content)

            if not rule.id:
                import uuid
                rule.id = f"imported_{uuid.uuid4().hex[:8]}"

            rule_service.save_rule(rule)
            self._load_rules()
            QMessageBox.information(
                self, "导入成功",
                f"规则 '{rule.rule_name}' 导入成功"
            )
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "导入失败", f"JSON 格式错误: {e}")
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"导入失败: {e}")

    def _on_export_rule(self, rule_id: str):
        """导出规则为 JSON 文件"""
        rule = rule_service.get_by_id(rule_id)
        if not rule:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出规则",
            f"{rule.rule_name}.json",
            "JSON 文件 (*.json)"
        )
        if file_path:
            try:
                Path(file_path).write_text(rule.to_json(), encoding='utf-8')
                QMessageBox.information(self, "成功", f"规则已导出到:\n{file_path}")
            except Exception as e:
                QMessageBox.warning(self, "导出失败", f"导出失败: {e}")

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def showEvent(self, event):
        """页面显示时刷新数据"""
        self._load_rules()
        super().showEvent(event)
