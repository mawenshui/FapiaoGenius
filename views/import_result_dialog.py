"""导入结果弹窗"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QScrollArea, QWidget, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal
from services.import_service import ImportResult
from views.widgets.file_link_label import FileLinkLabel


class ImportResultDialog(QDialog):
    """导入结果对话框"""
    
    ai_learn_clicked = pyqtSignal(str)  # AI 学习按钮点击，传递文件路径
    ai_batch_clicked = pyqtSignal(list)  # AI 批量识别按钮点击，传递所有失败文件路径
    
    def __init__(self, result: ImportResult, parent=None):
        super().__init__(parent)
        self._result = result
        self.setWindowTitle("导入结果")
        self.setModal(True)
        self.setMinimumSize(500, 400)
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 统计摘要
        self._add_summary_section(layout)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #e8e8e8;")
        line.setFixedHeight(1)
        layout.addWidget(line)
        
        # 失败文件列表
        if self._result.failed_details:
            self._add_failed_files_section(layout)
        
        # 按钮区域
        self._add_button_section(layout)
    
    def _add_summary_section(self, parent_layout):
        """添加统计摘要区域"""
        summary_widget = QWidget()
        summary_layout = QVBoxLayout(summary_widget)
        summary_layout.setSpacing(8)
        
        # 标题
        title = QLabel("导入统计")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        summary_layout.addWidget(title)
        
        # 统计数据
        stats = [
            ("总文件数", self._result.total, "#333"),
            ("成功导入", self._result.success, "#52c41a"),
            ("导入失败", self._result.failed, "#ff4d4f" if self._result.failed > 0 else "#333"),
            ("重复跳过", self._result.skipped, "#faad14" if self._result.skipped > 0 else "#333"),
        ]
        
        for label, value, color in stats:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setFixedWidth(100)
            val = QLabel(str(value))
            val.setStyleSheet(f"color: {color}; font-weight: bold;")
            row.addWidget(lbl)
            row.addWidget(val)
            row.addStretch()
            summary_layout.addLayout(row)
        
        parent_layout.addWidget(summary_widget)
    
    def _add_failed_files_section(self, parent_layout):
        """添加失败文件列表"""
        # 标题
        title = QLabel("失败文件列表")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ff4d4f;")
        parent_layout.addWidget(title)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(8)
        
        for failed in self._result.failed_details:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            
            # 文件图标和名称（超链接）
            icon_label = QLabel("📄")
            row_layout.addWidget(icon_label)
            
            link = FileLinkLabel(failed.file_name, failed.file_path)
            link.setToolTip(f"点击打开文件: {failed.file_path}")
            row_layout.addWidget(link)
            
            # 失败原因
            reason_label = QLabel(f"({failed.reason})")
            reason_label.setStyleSheet("color: #999; font-size: 11px;")
            reason_label.setWordWrap(True)
            row_layout.addWidget(reason_label, 1)
            
            content_layout.addWidget(row)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        parent_layout.addWidget(scroll)
        
        # AI 学习按钮（如果有规则不匹配的文件）
        rule_mismatch_files = [f for f in self._result.failed_details if f.is_rule_mismatch]
        if rule_mismatch_files:
            ai_layout = QHBoxLayout()
            ai_layout.addStretch()
            
            ai_btn = QPushButton("AI 学习")
            ai_btn.setToolTip("使用 AI 学习新的发票格式")
            ai_btn.setStyleSheet("""
                QPushButton {
                    background-color: #722ed1;
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #9254de;
                }
            """)
            ai_btn.clicked.connect(lambda: self._on_ai_learn(rule_mismatch_files[0].file_path))
            ai_layout.addWidget(ai_btn)
            
            parent_layout.addLayout(ai_layout)
        
        # AI 批量识别按钮（所有失败文件）
        if self._result.failed_details:
            batch_layout = QHBoxLayout()
            batch_layout.addStretch()
            
            batch_btn = QPushButton("🤖 AI 批量识别")
            batch_btn.setToolTip("将所有失败文件发送到 AI 识别页面进行批量识别")
            batch_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1890ff;
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #40a9ff;
                }
            """)
            batch_btn.clicked.connect(self._on_ai_batch)
            batch_layout.addWidget(batch_btn)
            
            parent_layout.addLayout(batch_layout)
    
    def _add_button_section(self, parent_layout):
        """添加按钮区域"""
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        parent_layout.addLayout(btn_layout)
    
    def _on_ai_learn(self, file_path: str):
        """AI 学习按钮点击"""
        self.ai_learn_clicked.emit(file_path)
        self.accept()

    def _on_ai_batch(self):
        """AI 批量识别按钮点击"""
        failed_paths = [f.file_path for f in self._result.failed_details]
        self.ai_batch_clicked.emit(failed_paths)
        self.accept()
