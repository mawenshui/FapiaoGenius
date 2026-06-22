"""全局应用配置"""

import os
import shutil
from pathlib import Path


class AppConfig:
    """应用配置单例"""
    
    APP_NAME = "ai_fapiao"
    APP_VERSION = "1.0.0"
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @property
    def data_dir(self) -> Path:
        """数据目录路径"""
        appdata = os.environ.get('APPDATA')
        if appdata:
            return Path(appdata) / self.APP_NAME
        return Path.home() / '.config' / self.APP_NAME
    
    @property
    def db_path(self) -> Path:
        """数据库文件路径"""
        return self.data_dir / "invoices.db"
    
    @property
    def rules_dir(self) -> Path:
        """规则文件目录"""
        return self.data_dir / "rules"
    
    @property
    def log_dir(self) -> Path:
        """日志目录"""
        return self.data_dir / "logs"
    
    @property
    def builtin_rules_dir(self) -> Path:
        """内置规则目录（项目内）"""
        return Path(__file__).parent.parent / "config" / "builtin_rules"
    
    def ensure_dirs(self):
        """确保所有必要目录存在"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.rules_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._copy_builtin_rules_if_needed()
    
    def _copy_builtin_rules_if_needed(self):
        """
        确保用户目录中的内置规则与源码保持最新
        
        - 内置规则（builtin_ 前缀）：始终覆盖更新
        - 自定义规则：不影响
        - 新规则：复制过去
        """
        if not self.builtin_rules_dir.exists():
            return
        
        for rule_file in self.builtin_rules_dir.glob("*.json"):
            target = self.rules_dir / rule_file.name
            # 内置规则始终覆盖；新规则复制过去
            if not target.exists() or rule_file.name.startswith('builtin_'):
                shutil.copy2(rule_file, target)


# 全局配置实例
app_config = AppConfig()
