"""AI 配置数据访问对象"""

from typing import Optional
from database.connection import db
from models.ai_config import AIConfig
from core.logger import logger


class ConfigDAO:
    """AI 配置数据访问对象"""
    
    def get(self) -> AIConfig:
        """获取 AI 配置（单行）"""
        sql = "SELECT * FROM ai_config WHERE id = 1"
        with db.transaction() as conn:
            row = conn.execute(sql).fetchone()
            if row:
                return AIConfig.from_row(row)
            # 返回默认配置
            return AIConfig()
    
    def save(self, config: AIConfig):
        """保存 AI 配置（upsert）"""
        config.id = 1
        config.update_timestamp()
        data = config.to_dict()
        
        sql = """
            INSERT OR REPLACE INTO ai_config (
                id, api_url, api_key, model_name, custom_fields, updated_at
            ) VALUES (
                :id, :api_url, :api_key, :model_name, :custom_fields, :updated_at
            )
        """
        
        with db.transaction() as conn:
            conn.execute(sql, data)
            logger.debug("AI 配置已保存")


# 全局 DAO 实例
config_dao = ConfigDAO()
