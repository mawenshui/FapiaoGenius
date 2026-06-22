"""解析规则数据访问对象"""

from typing import Optional
from database.connection import db
from models.parse_rule import ParseRule
from core.logger import logger


class RuleDAO:
    """解析规则数据访问对象"""
    
    def insert(self, rule: ParseRule):
        """插入规则"""
        data = rule.to_dict()
        
        sql = """
            INSERT OR REPLACE INTO parse_rules (
                id, rule_name, file_format, match_keywords,
                extraction_config, required_fields, created_at,
                updated_at, is_builtin
            ) VALUES (
                :id, :rule_name, :file_format, :match_keywords,
                :extraction_config, :required_fields, :created_at,
                :updated_at, :is_builtin
            )
        """
        
        with db.transaction() as conn:
            conn.execute(sql, data)
            logger.debug(f"规则已保存: {rule.rule_name}")
    
    def get_all(self) -> list[ParseRule]:
        """获取所有规则"""
        sql = "SELECT * FROM parse_rules ORDER BY created_at DESC"
        with db.transaction() as conn:
            rows = conn.execute(sql).fetchall()
            return [ParseRule.from_row(row) for row in rows]
    
    def get_by_id(self, rule_id: str) -> Optional[ParseRule]:
        """根据 ID 获取规则"""
        sql = "SELECT * FROM parse_rules WHERE id = ?"
        with db.transaction() as conn:
            row = conn.execute(sql, (rule_id,)).fetchone()
            return ParseRule.from_row(row) if row else None
    
    def get_by_format(self, file_format: str) -> list[ParseRule]:
        """根据文件格式获取规则"""
        sql = "SELECT * FROM parse_rules WHERE file_format = ? ORDER BY created_at DESC"
        with db.transaction() as conn:
            rows = conn.execute(sql, (file_format,)).fetchall()
            return [ParseRule.from_row(row) for row in rows]
    
    def update(self, rule: ParseRule):
        """更新规则"""
        data = rule.to_dict()
        
        sql = """
            UPDATE parse_rules SET
                rule_name = :rule_name,
                file_format = :file_format,
                match_keywords = :match_keywords,
                extraction_config = :extraction_config,
                required_fields = :required_fields,
                updated_at = :updated_at,
                is_builtin = :is_builtin
            WHERE id = :id
        """
        
        with db.transaction() as conn:
            conn.execute(sql, data)
            logger.debug(f"规则已更新: {rule.rule_name}")
    
    def delete(self, rule_id: str):
        """删除规则"""
        sql = "DELETE FROM parse_rules WHERE id = ?"
        with db.transaction() as conn:
            conn.execute(sql, (rule_id,))
            logger.debug(f"规则已删除: {rule_id}")


# 全局 DAO 实例
rule_dao = RuleDAO()

