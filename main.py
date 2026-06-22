"""智票通 - 应用入口"""

import sys
import os
from pathlib import Path

# 将项目根目录加入路径
sys.path.insert(0, str(Path(__file__).parent))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt


def main():
    """应用主入口"""
    # 高 DPI 支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setApplicationName("智票通")
    app.setApplicationVersion("1.4.0")
    app.setStyle('Fusion')
    
    # 初始化应用配置
    from core.app_config import app_config
    app_config.ensure_dirs()
    
    # 初始化数据库
    from database.schema import init_schema
    init_schema()
    
    # 加载样式表
    style_path = Path(__file__).parent / "resources" / "styles" / "default.qss"
    if style_path.exists():
        with open(style_path, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())
    
    # 加载保存的主题
    from utils.theme_manager import ThemeManager
    ThemeManager.load_saved_theme(app)
    
    # 创建并显示主窗口
    from views.main_window import MainWindow
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        from core.logger import logger
        logger.exception(f"应用异常退出: {e}")
        sys.exit(1)
