"""工具栏组件"""

from PyQt5.QtWidgets import QToolBar, QAction, QMenu, QToolButton
from PyQt5.QtCore import pyqtSignal, Qt, QSize
from PyQt5.QtGui import QIcon


class InvoiceToolbar(QToolBar):
    """发票管理工具栏"""
    
    import_file = pyqtSignal()       # 导入文件
    import_folder = pyqtSignal()     # 导入文件夹
    export_excel = pyqtSignal()      # 导出 Excel
    combo_clicked = pyqtSignal()     # 智能凑票
    clear_db = pyqtSignal()          # 清空数据库
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        self.setMovable(False)
        self.setIconSize(QSize(20, 20))
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        
        # 导入文件
        import_file_action = QAction("📄 导入文件", self)
        import_file_action.setToolTip("导入单个发票文件 (Ctrl+O)")
        import_file_action.setShortcut("Ctrl+O")
        import_file_action.triggered.connect(self.import_file.emit)
        self.addAction(import_file_action)
        
        # 导入文件夹
        import_folder_action = QAction("📁 导入文件夹", self)
        import_folder_action.setToolTip("批量导入文件夹中的发票 (Ctrl+Shift+O)")
        import_folder_action.setShortcut("Ctrl+Shift+O")
        import_folder_action.triggered.connect(self.import_folder.emit)
        self.addAction(import_folder_action)
        
        self.addSeparator()
        
        # 导出 Excel
        export_action = QAction("📊 导出 Excel", self)
        export_action.setToolTip("将当前数据导出为 Excel 文件")
        export_action.triggered.connect(self.export_excel.emit)
        self.addAction(export_action)
        
        self.addSeparator()
        
        # 智能凑票
        combo_action = QAction("💰 智能凑票", self)
        combo_action.setToolTip("智能组合发票达到目标金额")
        combo_action.triggered.connect(self.combo_clicked.emit)
        self.addAction(combo_action)
        
        self.addSeparator()
        
        # 清空数据库
        clear_action = QAction("🗑️ 清空数据库", self)
        clear_action.setToolTip("删除所有发票数据（不可恢复）")
        clear_action.triggered.connect(self.clear_db.emit)
        self.addAction(clear_action)
        
        # 工具栏样式
        self.setStyleSheet("""
            QToolBar {
                background-color: #fff;
                border-bottom: 1px solid #e8e8e8;
                padding: 5px;
                spacing: 5px;
            }
            QToolButton {
                padding: 5px 10px;
                border-radius: 4px;
            }
            QToolButton:hover {
                background-color: #e6f7ff;
            }
        """)
