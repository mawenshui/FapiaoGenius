"""设置页面"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                              QLineEdit, QComboBox, QPushButton, QGroupBox,
                              QFormLayout, QMessageBox)
from PyQt5.QtCore import Qt
from services.ai_service import ai_service
from models.ai_config import AIConfig


class SettingsPage(QWidget):
    """设置页面"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._load_config()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 标题
        title = QLabel("设置")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)
        
        # AI 配置组
        ai_group = QGroupBox("AI 服务配置")
        ai_layout = QFormLayout(ai_group)
        ai_layout.setSpacing(15)
        ai_layout.setContentsMargins(15, 20, 15, 15)
        
        # API 地址
        self._api_url_edit = QLineEdit()
        self._api_url_edit.setPlaceholderText("https://api.deepseek.com")
        ai_layout.addRow("API 地址:", self._api_url_edit)
        
        # API Key
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setPlaceholderText("请输入 API Key")
        self._api_key_edit.setEchoMode(QLineEdit.Password)
        ai_layout.addRow("API Key:", self._api_key_edit)
        
        # 模型选择
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        models = [
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        ]
        self._model_combo.addItems(models)
        ai_layout.addRow("模型:", self._model_combo)
        
        # 测试连接按钮
        test_btn = QPushButton("测试连接")
        test_btn.clicked.connect(self._on_test_connection)
        test_btn.setStyleSheet("""
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
        ai_layout.addRow("", test_btn)
        
        layout.addWidget(ai_group)
        
        # 主题设置组
        theme_group = QGroupBox("外观设置")
        theme_layout = QFormLayout(theme_group)
        theme_layout.setSpacing(15)
        theme_layout.setContentsMargins(15, 20, 15, 15)
        
        self._theme_combo = QComboBox()
        from utils.theme_manager import ThemeManager
        for key, name in ThemeManager.get_available_themes().items():
            self._theme_combo.addItem(name, key)
        # 选中当前主题
        current = ThemeManager.get_current_theme()
        idx = self._theme_combo.findData(current)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_layout.addRow("主题:", self._theme_combo)
        
        layout.addWidget(theme_group)
        
        # 配置迁移组
        transfer_group = QGroupBox("配置迁移")
        transfer_layout = QHBoxLayout(transfer_group)
        transfer_layout.setSpacing(15)
        transfer_layout.setContentsMargins(15, 20, 15, 15)
        
        export_btn = QPushButton("📦 导出配置")
        export_btn.clicked.connect(self._on_export_config)
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #52c41a; color: white;
                padding: 8px 16px; border-radius: 4px; border: none;
            }
            QPushButton:hover { background-color: #73d13d; }
        """)
        transfer_layout.addWidget(export_btn)
        
        import_btn = QPushButton("📂 导入配置")
        import_btn.clicked.connect(self._on_import_config)
        import_btn.setStyleSheet("""
            QPushButton {
                background-color: #1890ff; color: white;
                padding: 8px 16px; border-radius: 4px; border: none;
            }
            QPushButton:hover { background-color: #40a9ff; }
        """)
        transfer_layout.addWidget(import_btn)
        
        transfer_layout.addStretch()
        transfer_desc = QLabel("导出/导入 AI 配置、主题偏好和自定义规则")
        transfer_desc.setStyleSheet("color: #999; font-size: 11px;")
        transfer_layout.addWidget(transfer_desc)
        
        layout.addWidget(transfer_group)
        
        # 保存按钮
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        
        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self._on_save_config)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                padding: 10px 30px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
        """)
        save_layout.addWidget(save_btn)
        
        layout.addLayout(save_layout)
        layout.addStretch()
    
    def _load_config(self):
        """加载配置"""
        config = ai_service.get_config()
        self._api_url_edit.setText(config.api_url)
        self._api_key_edit.setText(config.api_key)
        
        idx = self._model_combo.findText(config.model_name)
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)
        else:
            self._model_combo.setEditText(config.model_name)
    
    def _on_test_connection(self):
        """测试连接"""
        # 先保存配置
        self._save_current_config()
        
        success, message = ai_service.test_connection()
        
        if success:
            QMessageBox.information(self, "连接成功", message)
        else:
            QMessageBox.warning(self, "连接失败", message)
    
    def _on_save_config(self):
        """保存配置"""
        self._save_current_config()
        QMessageBox.information(self, "保存成功", "AI 配置已保存")
    
    def _save_current_config(self):
        """保存当前配置到服务"""
        api_url = self._api_url_edit.text().strip()
        # API 地址为空时使用 DeepSeek 默认地址
        if not api_url:
            api_url = "https://api.deepseek.com"
        config = AIConfig(
            api_url=api_url,
            api_key=self._api_key_edit.text().strip(),
            model_name=self._model_combo.currentText().strip()
        )
        ai_service.save_config(config)
    
    def _on_theme_changed(self, index: int):
        """主题切换"""
        theme_key = self._theme_combo.itemData(index)
        if theme_key:
            from PyQt5.QtWidgets import QApplication
            from utils.theme_manager import ThemeManager
            app = QApplication.instance()
            if app:
                ThemeManager.apply_theme(app, theme_key)
                ThemeManager.save_theme(theme_key)
    
    def _on_export_config(self):
        """导出配置"""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        from services.config_transfer_service import config_transfer_service
        
        path, _ = QFileDialog.getSaveFileName(
            self, "导出配置", "fapiao_genius_config.zip", "ZIP 文件 (*.zip)"
        )
        if path:
            result = config_transfer_service.export_config(path)
            if result['success']:
                QMessageBox.information(self, "导出成功", result['message'])
            else:
                QMessageBox.warning(self, "导出失败", result['message'])
    
    def _on_import_config(self):
        """导入配置"""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        from services.config_transfer_service import config_transfer_service
        
        path, _ = QFileDialog.getOpenFileName(
            self, "导入配置", "", "ZIP 文件 (*.zip)"
        )
        if path:
            reply = QMessageBox.question(
                self, "确认导入",
                "导入将覆盖当前的 AI 配置、主题和自定义规则。\n\n确定继续？"
            )
            if reply == QMessageBox.Yes:
                result = config_transfer_service.import_config(path)
                if result['success']:
                    QMessageBox.information(self, "导入成功", result['message'])
                    self._load_config()  # 刷新配置显示
                else:
                    QMessageBox.warning(self, "导入失败", result['message'])
