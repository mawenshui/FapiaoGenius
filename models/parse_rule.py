"""解析规则数据模型

extraction_config 格式：字段名 → 正则表达式字符串的直接映射
示例：{"invoice_number": "发票号码[：:]\\s*(\\d+)", "invoice_date": "..."}
每个正则必须包含一个捕获组 () 用于提取目标值。
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import sqlite3


@dataclass
class ParseRule:
    """发票解析规则

    extraction_config: dict[str, str] — 字段名到正则表达式的直接映射。
    示例: {"invoice_number": "发票号码[：:]\\s*(\\d+)", ...}
    """
    id: str = ""
    rule_name: str = ""
    file_format: str = ""
    match_keywords: list[str] = field(default_factory=list)
    extraction_config: dict = field(default_factory=dict)
    required_fields: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    is_builtin: bool = False
    
    def to_dict(self) -> dict:
        """转换为字典（用于数据库存储）"""
        return {
            'id': self.id,
            'rule_name': self.rule_name,
            'file_format': self.file_format,
            'match_keywords': json.dumps(self.match_keywords, ensure_ascii=False),
            'extraction_config': json.dumps(self.extraction_config, ensure_ascii=False),
            'required_fields': json.dumps(self.required_fields, ensure_ascii=False),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'is_builtin': 1 if self.is_builtin else 0,
        }
    
    def to_json(self) -> str:
        """转换为 JSON 字符串（用于文件存储）"""
        return json.dumps({
            'id': self.id,
            'rule_name': self.rule_name,
            'file_format': self.file_format,
            'match_keywords': self.match_keywords,
            'extraction_config': self.extraction_config,
            'required_fields': self.required_fields,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'is_builtin': self.is_builtin,
        }, ensure_ascii=False, indent=2)
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'ParseRule':
        """从数据库行创建实例"""
        return cls(
            id=row['id'],
            rule_name=row['rule_name'],
            file_format=row['file_format'],
            match_keywords=json.loads(row['match_keywords'] or '[]'),
            extraction_config=json.loads(row['extraction_config'] or '{}'),
            required_fields=json.loads(row['required_fields'] or '[]'),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            is_builtin=bool(row['is_builtin'])
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ParseRule':
        """从 JSON 字符串创建实例"""
        data = json.loads(json_str)
        return cls(
            id=data.get('id', ''),
            rule_name=data.get('rule_name', ''),
            file_format=data.get('file_format', ''),
            match_keywords=data.get('match_keywords', []),
            extraction_config=data.get('extraction_config', {}),
            required_fields=data.get('required_fields', []),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            is_builtin=data.get('is_builtin', False)
        )
    
    def set_timestamps(self):
        """设置时间戳"""
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        self.updated_at = now
