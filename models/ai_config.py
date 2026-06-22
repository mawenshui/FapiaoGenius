"""AI 配置数据模型"""

import json
from dataclasses import dataclass, field
from datetime import datetime
import sqlite3


@dataclass
class AIConfig:
    """AI 服务配置"""
    id: int = 1
    api_url: str = ""
    api_key: str = ""
    model_name: str = "deepseek-v4-flash"
    custom_fields: list[str] = field(default_factory=list)
    updated_at: str = ""
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'api_url': self.api_url,
            'api_key': self.api_key,
            'model_name': self.model_name,
            'custom_fields': json.dumps(self.custom_fields, ensure_ascii=False),
            'updated_at': self.updated_at,
        }
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'AIConfig':
        """从数据库行创建实例"""
        return cls(
            id=row['id'],
            api_url=row['api_url'] or '',
            api_key=row['api_key'] or '',
            model_name=row['model_name'] or 'deepseek-v4-flash',
            custom_fields=json.loads(row['custom_fields'] or '[]'),
            updated_at=row['updated_at'] or ''
        )
    
    def update_timestamp(self):
        """更新时间戳"""
        self.updated_at = datetime.now().isoformat()
