"""主窗口"""

from PyQt5.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QStackedWidget,
                              QMenuBar, QMenu, QAction, QStatusBar, QLabel)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon

from views.sidebar import Sidebar
from views.invoice_page import InvoicePage
from views.combo_page import ComboPage
from views.stats_page import StatsPage
from views.rule_page import RulePage
from views.ai_page import AIPage
from views.settings_page import SettingsPage
from services.invoice_service import invoice_service


class MainWindow(QMainWindow):
    """应用主窗口"""
    
    def __init__(self):
        super().__init__()
        self._init_ui()
        self._load_initial_data()
    
    def _init_ui(self):
        """初始化 UI"""
        self.setWindowTitle("智票通 - AI 智能发票识别管理系统")
        self.setMinimumSize(1200, 700)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 侧边栏
        self._sidebar = Sidebar()
        main_layout.addWidget(self._sidebar)
        
        # 页面堆栈
        self._stack = QStackedWidget()
        
        # 添加页面
        self._invoice_page = InvoicePage()
        self._combo_page = ComboPage()
        self._stats_page = StatsPage()
        self._rule_page = RulePage()
        self._ai_page = AIPage()
        self._settings_page = SettingsPage()
        
        self._stack.addWidget(self._invoice_page)   # 0
        self._stack.addWidget(self._combo_page)     # 1
        self._stack.addWidget(self._stats_page)     # 2
        self._stack.addWidget(self._rule_page)      # 3
        self._stack.addWidget(self._ai_page)        # 4
        self._stack.addWidget(self._settings_page)  # 5
        
        main_layout.addWidget(self._stack, 1)
        
        # 创建菜单栏（需要在页面创建之后）
        self._create_menu_bar()
        
        # 状态栏
        self._create_status_bar()
        
        # 连接信号
        self._sidebar.page_changed.connect(self._on_page_changed)
        
        # AI 页面导入成功后刷新发票列表
        self._ai_page.invoice_imported.connect(self._invoice_page.refresh)
        
        # 发票页面请求跳转到 AI 识别
        self._invoice_page.navigate_to_ai_page.connect(self._on_navigate_to_ai)        
        # 默认显示发票管理页面
        self._stack.setCurrentIndex(0)
    
    def _create_menu_bar(self):
        """创建菜单栏"""
        menu_bar = self.menuBar()
        
        # 文件菜单
        file_menu = menu_bar.addMenu("文件(&F)")
        
        import_action = QAction("导入文件...", self)
        import_action.setShortcut("Ctrl+O")
        import_action.triggered.connect(lambda: self._invoice_page._on_import_file())
        file_menu.addAction(import_action)
        
        import_folder_action = QAction("导入文件夹...", self)
        import_folder_action.setShortcut("Ctrl+Shift+O")
        import_folder_action.triggered.connect(lambda: self._invoice_page._on_import_folder())
        file_menu.addAction(import_folder_action)
        
        file_menu.addSeparator()
        
        export_action = QAction("导出 Excel...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(lambda: self._invoice_page._on_export_excel())
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出(&Q)", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 编辑菜单
        edit_menu = menu_bar.addMenu("编辑(&E)")
        
        select_all_action = QAction("全选", self)
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(self._invoice_page._table.select_all)
        edit_menu.addAction(select_all_action)
        
        delete_action = QAction("删除选中", self)
        delete_action.setShortcut("Delete")
        delete_action.triggered.connect(self._on_delete_selected)
        edit_menu.addAction(delete_action)
        
        # 工具菜单
        tools_menu = menu_bar.addMenu("工具(&T)")
        
        clear_action = QAction("清空数据库...", self)
        clear_action.triggered.connect(lambda: self._invoice_page._on_clear_db())
        tools_menu.addAction(clear_action)
        
        # 帮助菜单
        help_menu = menu_bar.addMenu("帮助(&H)")
        
        update_action = QAction("检查更新...", self)
        update_action.triggered.connect(self._check_update)
        help_menu.addAction(update_action)
        
        help_menu.addSeparator()
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
        # 菜单栏样式
        menu_bar.setStyleSheet("""
            QMenuBar {
                background-color: #fff;
                border-bottom: 1px solid #e8e8e8;
            }
            QMenuBar::item {
                padding: 8px 12px;
            }
            QMenuBar::item:selected {
                background-color: #e6f7ff;
            }
            QMenu {
                background-color: #fff;
                border: 1px solid #e8e8e8;
            }
            QMenu::item {
                padding: 8px 30px;
            }
            QMenu::item:selected {
                background-color: #e6f7ff;
            }
        """)
    
    def _create_status_bar(self):
        """创建状态栏"""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        
        # 左侧信息
        self._status_left = QLabel("就绪")
        status_bar.addWidget(self._status_left)
        
        # 右侧信息
        self._status_right = QLabel("v1.3.0")
        status_bar.addPermanentWidget(self._status_right)
        
        status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #fafafa;
                border-top: 1px solid #e8e8e8;
            }
            QLabel {
                color: #666;
                padding: 2px 10px;
            }
        """)
    
    def _on_page_changed(self, index: int):
        """页面切换"""
        self._stack.setCurrentIndex(index)
        
        # 切换到发票管理页面时刷新数据
        if index == 0:
            self._invoice_page.refresh()
        
        # 切换到统计报表时刷新数据
        if index == 2:
            self._stats_page.refresh()
        
        # 更新状态栏
        page_names = ["发票管理", "智能凑票", "统计报表", "规则管理", "AI 识别", "设置"]
        if 0 <= index < len(page_names):
            self._status_left.setText(f"当前页面: {page_names[index]}")
    
    def _on_delete_selected(self):
        """删除选中项"""
        if self._stack.currentIndex() == 0:  # 只在发票管理页面有效
            selected_ids = self._invoice_page._table.get_selected_ids()
            if selected_ids:
                from views.confirm_dialog import ConfirmDialog
                confirmed = ConfirmDialog.confirm(
                    self,
                    "确认删除",
                    f"确定要删除选中的 {len(selected_ids)} 张发票吗？"
                )
                if confirmed:
                    invoice_service.delete_batch(selected_ids)
                    self._invoice_page.refresh()

    def _on_navigate_to_ai(self, file_paths: list):
        """跳转到 AI 识别页面并加载文件"""
        self._sidebar.set_current_index(4)  # AI 识别页面索引
        self._stack.setCurrentIndex(4)
        if file_paths:
            self._ai_page.add_files_and_start(file_paths)
    
    def _load_initial_data(self):
        """加载初始数据"""
        from services.rule_service import rule_service
        rule_service.load_rules()
        self._invoice_page.refresh()
    
    def _show_about(self):
        """显示关于对话框"""
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "关于",
            "<h3>智票通</h3>"
            "<p>版本: 1.3.0</p>"
            "<p>一款基于 AI 的智能发票识别与管理工具</p>"
            "<p>支持 XML、PDF、OFD 格式发票自动识别</p>"
            "<hr>"
            "<p>功能特点:</p>"
            "<ul>"
            "<li>多格式发票自动识别</li>"
            "<li>AI 学习新发票格式</li>"
            "<li>智能凑票功能</li>"
            "<li>Excel 导出</li>"
            "</ul>"
        )
    
    def closeEvent(self, event):
        """关闭事件"""
        from database.connection import db
        db.close()
        event.accept()
    
    def _check_update(self):
        """检查更新"""
        from PyQt5.QtWidgets import QMessageBox
        from services.update_service import update_service
        
        self._status_left.setText("正在检查更新...")
        
        result = update_service.check_update("1.3.0")
        
        if result['error']:
            QMessageBox.warning(self, "检查失败", f"无法检查更新:\n{result['error']}")
        elif result['has_update']:
            msg = f"发现新版本 v{result['version']}！\n\n"
            if result['changelog']:
                msg += f"更新内容:\n{result['changelog'][:300]}\n\n"
            if result['download_url']:
                msg += "是否打开下载页面？"
                reply = QMessageBox.question(self, "发现新版本", msg)
                if reply == QMessageBox.Yes:
                    import webbrowser
                    webbrowser.open(result['download_url'])
            else:
                msg += "暂无下载链接，请访问 GitHub Release 页面。"
                QMessageBox.information(self, "发现新版本", msg)
        else:
            QMessageBox.information(self, "检查更新", "当前已是最新版本 ✓")
        
        self._status_left.setText("就绪")
