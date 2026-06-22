"""发票数据模型"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import sqlite3


@dataclass
class Invoice:
    """发票信息"""
    id: Optional[int] = None
    business_type: str = ""
    invoice_type: str = ""
    invoice_number: str = ""
    invoice_date: str = ""
    buyer_name: str = ""
    seller_name: str = ""
    amount_without_tax: float = 0.0
    tax_amount: float = 0.0
    total_amount: float = 0.0
    reimbursement_status: str = "未报销"
    status: str = "正常"
    remark: str = ""
    source_file_path: str = ""
    file_format: str = ""
    rule_id: str = ""
    import_time: str = ""
    ai_learned: bool = False
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'business_type': self.business_type,
            'invoice_type': self.invoice_type,
            'invoice_number': self.invoice_number,
            'invoice_date': self.invoice_date,
            'buyer_name': self.buyer_name,
            'seller_name': self.seller_name,
            'amount_without_tax': self.amount_without_tax,
            'tax_amount': self.tax_amount,
            'total_amount': self.total_amount,
            'reimbursement_status': self.reimbursement_status,
            'status': self.status,
            'remark': self.remark,
            'source_file_path': self.source_file_path,
            'file_format': self.file_format,
            'rule_id': self.rule_id,
            'import_time': self.import_time,
            'ai_learned': 1 if self.ai_learned else 0,
        }
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'Invoice':
        """从数据库行创建实例"""
        return cls(
            id=row['id'],
            business_type=row['business_type'],
            invoice_type=row['invoice_type'],
            invoice_number=row['invoice_number'],
            invoice_date=row['invoice_date'],
            buyer_name=row['buyer_name'] or '',
            seller_name=row['seller_name'] or '',
            amount_without_tax=row['amount_without_tax'] or 0.0,
            tax_amount=row['tax_amount'] or 0.0,
            total_amount=row['total_amount'] or 0.0,
            reimbursement_status=row['reimbursement_status'] or '未报销',
            status=row['status'] or '正常',
            remark=row['remark'] or '',
            source_file_path=row['source_file_path'],
            file_format=row['file_format'],
            rule_id=row['rule_id'] or '',
            import_time=row['import_time'],
            ai_learned=bool(row['ai_learned'])
        )
    
    def set_import_time(self):
        """设置导入时间为当前时间"""
        self.import_time = datetime.now().isoformat()
