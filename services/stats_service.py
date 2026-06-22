"""发票统计服务 — 聚合查询与数据计算"""

from typing import Optional
from dataclasses import dataclass
from database.connection import db
from core.logger import logger


@dataclass
class StatItem:
    """统计项"""
    label: str
    count: int
    total_amount: float


class StatsService:
    """发票统计服务"""
    
    def by_business_type(self) -> list[StatItem]:
        """按业务类型统计"""
        sql = """
            SELECT business_type, COUNT(*) as cnt, SUM(total_amount) as total
            FROM invoices GROUP BY business_type ORDER BY total DESC
        """
        return self._execute_stat(sql)
    
    def by_invoice_type(self) -> list[StatItem]:
        """按发票类型统计"""
        sql = """
            SELECT invoice_type, COUNT(*) as cnt, SUM(total_amount) as total
            FROM invoices GROUP BY invoice_type ORDER BY total DESC
        """
        return self._execute_stat(sql)
    
    def by_month(self) -> list[StatItem]:
        """按月份统计"""
        sql = """
            SELECT substr(invoice_date, 1, 7) as month, COUNT(*) as cnt, SUM(total_amount) as total
            FROM invoices WHERE invoice_date != ''
            GROUP BY substr(invoice_date, 1, 7) ORDER BY month ASC
        """
        return self._execute_stat(sql)
    
    def by_reimbursement_status(self) -> list[StatItem]:
        """按报销状态统计"""
        sql = """
            SELECT reimbursement_status, COUNT(*) as cnt, SUM(total_amount) as total
            FROM invoices GROUP BY reimbursement_status ORDER BY total DESC
        """
        return self._execute_stat(sql)
    
    def summary(self) -> dict:
        """总览数据"""
        sql = """
            SELECT 
                COUNT(*) as total_count,
                COALESCE(SUM(total_amount), 0) as total_amount,
                COALESCE(SUM(tax_amount), 0) as total_tax,
                COALESCE(AVG(total_amount), 0) as avg_amount,
                COALESCE(MAX(total_amount), 0) as max_amount,
                COALESCE(MIN(total_amount), 0) as min_amount
            FROM invoices
        """
        with db.transaction() as conn:
            row = conn.execute(sql).fetchone()
            if row:
                return {
                    'total_count': row[0],
                    'total_amount': row[1],
                    'total_tax': row[2],
                    'avg_amount': row[3],
                    'max_amount': row[4],
                    'min_amount': row[5],
                }
        return {
            'total_count': 0, 'total_amount': 0, 'total_tax': 0,
            'avg_amount': 0, 'max_amount': 0, 'min_amount': 0,
        }
    
    def _execute_stat(self, sql: str) -> list[StatItem]:
        """执行统计查询"""
        items = []
        with db.transaction() as conn:
            rows = conn.execute(sql).fetchall()
            for row in rows:
                items.append(StatItem(
                    label=row[0] or '未知',
                    count=row[1] or 0,
                    total_amount=row[2] or 0.0
                ))
        return items


# 全局服务实例
stats_service = StatsService()
