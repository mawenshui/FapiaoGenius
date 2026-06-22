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
