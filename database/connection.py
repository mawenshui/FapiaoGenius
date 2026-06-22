"""数据库连接管理"""

import sqlite3
from contextlib import contextmanager
from core.app_config import app_config
from core.logger import logger


class DatabaseConnection:
    """SQLite 数据库连接管理器（单例）"""
    
    _instance = None
    _conn = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @property
    def db_path(self) -> str:
        """数据库文件路径"""
        return str(app_config.db_path)
    
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._conn is None:
            try:
                self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
                self._conn.row_factory = sqlite3.Row
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA foreign_keys=ON")
                logger.debug(f"数据库连接已建立: {self.db_path}")
            except sqlite3.Error as e:
                logger.error(f"数据库连接失败: {e}")
                raise
        return self._conn
    
    @contextmanager
    def transaction(self):
        """事务上下文管理器"""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库事务回滚: {e}")
            raise
    
    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.debug("数据库连接已关闭")


# 全局数据库连接实例
db = DatabaseConnection()
