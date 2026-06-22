"""发票数据访问对象"""

from typing import Optional
from dataclasses import dataclass
from database.connection import db
from models.invoice import Invoice
from core.logger import logger


@dataclass
class FilterCriteria:
    """筛选条件"""
    business_type: Optional[str] = None
    invoice_type: Optional[str] = None
    reimbursement_status: Optional[str] = None
    status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    search_text: Optional[str] = None


class InvoiceDAO:
    """发票数据访问对象"""
    
    def insert(self, invoice: Invoice) -> int:
        """插入发票记录，返回 ID"""
        data = invoice.to_dict()
        data.pop('id', None)
        
        sql = """
            INSERT INTO invoices (
                business_type, invoice_type, invoice_number, invoice_date,
                buyer_name, seller_name, amount_without_tax, tax_amount,
                total_amount, reimbursement_status, status, remark,
                source_file_path, file_format, rule_id, import_time, ai_learned
            ) VALUES (
                :business_type, :invoice_type, :invoice_number, :invoice_date,
                :buyer_name, :seller_name, :amount_without_tax, :tax_amount,
                :total_amount, :reimbursement_status, :status, :remark,
                :source_file_path, :file_format, :rule_id, :import_time, :ai_learned
            )
        """
        
        with db.transaction() as conn:
            cursor = conn.execute(sql, data)
            invoice.id = cursor.lastrowid
            logger.debug(f"发票已插入: {invoice.invoice_number}")
            return invoice.id
    
    def insert_batch(self, invoices: list[Invoice]) -> list[int]:
        """批量插入发票"""
        ids = []
        with db.transaction() as conn:
            for invoice in invoices:
                data = invoice.to_dict()
                data.pop('id', None)
                cursor = conn.execute(
                    """INSERT INTO invoices (
                        business_type, invoice_type, invoice_number, invoice_date,
                        buyer_name, seller_name, amount_without_tax, tax_amount,
                        total_amount, reimbursement_status, status, remark,
                        source_file_path, file_format, rule_id, import_time, ai_learned
                    ) VALUES (
                        :business_type, :invoice_type, :invoice_number, :invoice_date,
                        :buyer_name, :seller_name, :amount_without_tax, :tax_amount,
                        :total_amount, :reimbursement_status, :status, :remark,
                        :source_file_path, :file_format, :rule_id, :import_time, :ai_learned
                    )""",
                    data
                )
                ids.append(cursor.lastrowid)
        logger.info(f"批量插入 {len(ids)} 条发票")
        return ids
    
    def get_by_id(self, invoice_id: int) -> Optional[Invoice]:
        """根据 ID 获取发票"""
        sql = "SELECT * FROM invoices WHERE id = ?"
        with db.transaction() as conn:
            row = conn.execute(sql, (invoice_id,)).fetchone()
            return Invoice.from_row(row) if row else None
    
    def get_all(self, filters: Optional[FilterCriteria] = None) -> list[Invoice]:
        """获取所有发票（支持筛选）"""
        conditions = []
        params = []
        
        if filters:
            if filters.business_type:
                conditions.append("business_type = ?")
                params.append(filters.business_type)
            if filters.invoice_type:
                conditions.append("invoice_type = ?")
                params.append(filters.invoice_type)
            if filters.reimbursement_status:
                conditions.append("reimbursement_status = ?")
                params.append(filters.reimbursement_status)
            if filters.status:
                conditions.append("status = ?")
                params.append(filters.status)
            if filters.date_from:
                conditions.append("invoice_date >= ?")
                params.append(filters.date_from)
            if filters.date_to:
                conditions.append("invoice_date <= ?")
                params.append(filters.date_to)
            if filters.search_text:
                conditions.append(
                    "(invoice_number LIKE ? OR buyer_name LIKE ? OR seller_name LIKE ? OR remark LIKE ?)"
                )
                pattern = f"%{filters.search_text}%"
                params.extend([pattern] * 4)
        
        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM invoices WHERE {where} ORDER BY import_time DESC"
        
        with db.transaction() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [Invoice.from_row(row) for row in rows]
    
    def update(self, invoice: Invoice):
        """更新发票"""
        data = invoice.to_dict()
        invoice_id = data.pop('id')
        
        sql = """
            UPDATE invoices SET
                business_type = :business_type,
                invoice_type = :invoice_type,
                invoice_number = :invoice_number,
                invoice_date = :invoice_date,
                buyer_name = :buyer_name,
                seller_name = :seller_name,
                amount_without_tax = :amount_without_tax,
                tax_amount = :tax_amount,
                total_amount = :total_amount,
                reimbursement_status = :reimbursement_status,
                status = :status,
                remark = :remark,
                source_file_path = :source_file_path,
                file_format = :file_format,
                rule_id = :rule_id,
                import_time = :import_time,
                ai_learned = :ai_learned
            WHERE id = :id
        """
        data['id'] = invoice_id
        
        with db.transaction() as conn:
            conn.execute(sql, data)
            logger.debug(f"发票已更新: {invoice.invoice_number}")
    
    def update_field(self, invoice_id: int, field: str, value):
        """更新单个字段"""
        allowed_fields = {
            'business_type', 'invoice_type', 'reimbursement_status',
            'status', 'remark'
        }
        if field not in allowed_fields:
            raise ValueError(f"不允许修改字段: {field}")
        
        sql = f"UPDATE invoices SET {field} = ? WHERE id = ?"
        with db.transaction() as conn:
            conn.execute(sql, (value, invoice_id))
            logger.debug(f"发票字段已更新: id={invoice_id}, {field}={value}")
    
    def delete(self, invoice_id: int):
        """删除发票"""
        sql = "DELETE FROM invoices WHERE id = ?"
        with db.transaction() as conn:
            conn.execute(sql, (invoice_id,))
            logger.debug(f"发票已删除: id={invoice_id}")
    
    def delete_batch(self, ids: list[int]):
        """批量删除发票"""
        if not ids:
            return
        placeholders = ','.join(['?'] * len(ids))
        sql = f"DELETE FROM invoices WHERE id IN ({placeholders})"
        with db.transaction() as conn:
            conn.execute(sql, ids)
            logger.info(f"批量删除 {len(ids)} 条发票")
    
    def clear_all(self):
        """清空所有发票"""
        sql = "DELETE FROM invoices"
        with db.transaction() as conn:
            conn.execute(sql)
            logger.info("已清空所有发票数据")
    
    def exists_by_number(self, invoice_number: str) -> bool:
        """检查发票号码是否已存在"""
        sql = "SELECT 1 FROM invoices WHERE invoice_number = ?"
        with db.transaction() as conn:
            row = conn.execute(sql, (invoice_number,)).fetchone()
            return row is not None
    
    def count(self) -> int:
        """获取发票总数"""
        sql = "SELECT COUNT(*) FROM invoices"
        with db.transaction() as conn:
            row = conn.execute(sql).fetchone()
            return row[0] if row else 0


# 全局 DAO 实例
invoice_dao = InvoiceDAO()

