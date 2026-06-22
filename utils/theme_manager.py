"""主题管理器 — QSS 样式加载与切换"""

from pathlib import Path
from core.logger import logger


class ThemeManager:
    """主题管理器"""
    
    # 内置主题列表
    THEMES = {
        "default": "默认主题（浅色）",
        "dark": "深色主题",
    }
    
    _current_theme = "default"
    _styles_dir = Path(__file__).parent.parent / "resources" / "styles"
    
    @classmethod
    def get_available_themes(cls) -> dict[str, str]:
        """获取可用主题列表"""
        return dict(cls.THEMES)
    
    @classmethod
    def get_current_theme(cls) -> str:
        """获取当前主题"""
        return cls._current_theme
    
    @classmethod
    def apply_theme(cls, app, theme_name: str) -> bool:
        """应用主题到应用"""
        if theme_name not in cls.THEMES:
            logger.warning(f"未知主题: {theme_name}")
            return False
        
        qss_file = cls._styles_dir / f"{theme_name}.qss"
        if not qss_file.exists():
            logger.warning(f"主题文件不存在: {qss_file}")
            return False
        
        try:
            with open(qss_file, 'r', encoding='utf-8') as f:
                stylesheet = f.read()
            app.setStyleSheet(stylesheet)
            cls._current_theme = theme_name
            logger.info(f"已切换主题: {cls.THEMES[theme_name]}")
            return True
        except Exception as e:
            logger.error(f"加载主题失败: {e}")
            return False
    
    @classmethod
    def load_saved_theme(cls, app):
        """加载保存的主题"""
        theme = cls._read_preference()
        if theme and theme != "default":
            cls.apply_theme(app, theme)
    
    @classmethod
    def save_theme(cls, theme_name: str):
        """保存主题选择"""
        cls._write_preference(theme_name)
    
    @classmethod
    def _pref_file(cls) -> Path:
        from core.app_config import app_config
        return Path(app_config.data_dir) / "theme.json"
    
    @classmethod
    def _read_preference(cls) -> str:
        import json
        try:
            if cls._pref_file().exists():
                with open(cls._pref_file(), 'r') as f:
                    data = json.load(f)
                return data.get('theme', 'default')
        except Exception:
            pass
        return 'default'
    
    @classmethod
    def _write_preference(cls, theme_name: str):
        import json
        try:
            with open(cls._pref_file(), 'w') as f:
                json.dump({'theme': theme_name}, f)
        except Exception as e:
            logger.error(f"保存主题偏好失败: {e}")


# 全局实例
theme_manager = ThemeManager()
