"""发票查询与管理服务"""

from typing import Optional
from database.invoice_dao import invoice_dao, FilterCriteria
from models.invoice import Invoice
from core.logger import logger


class InvoiceService:
    """发票服务"""
    
    def query(self, filters: Optional[FilterCriteria] = None) -> list[Invoice]:
        """
        查询发票
        
        Args:
            filters: 筛选条件
            
        Returns:
            list[Invoice]: 发票列表
        """
        return invoice_dao.get_all(filters)
    
    def get_by_id(self, invoice_id: int) -> Optional[Invoice]:
        """根据 ID 获取发票"""
        return invoice_dao.get_by_id(invoice_id)
    
    def update_field(self, invoice_id: int, field: str, value) -> bool:
        """
        更新单个字段
        
        Args:
            invoice_id: 发票 ID
            field: 字段名
            value: 字段值
            
        Returns:
            bool: 是否成功
        """
        try:
            invoice_dao.update_field(invoice_id, field, value)
            return True
        except Exception as e:
            logger.error(f"更新字段失败: {e}")
            return False
    
    def update(self, invoice: Invoice) -> bool:
        """
        更新发票
        
        Args:
            invoice: 发票对象
            
        Returns:
            bool: 是否成功
        """
        try:
            invoice_dao.update(invoice)
            return True
        except Exception as e:
            logger.error(f"更新发票失败: {e}")
            return False
    
    def delete(self, invoice_id: int) -> bool:
        """
        删除发票
        
        Args:
            invoice_id: 发票 ID
            
        Returns:
            bool: 是否成功
        """
        try:
            invoice_dao.delete(invoice_id)
            return True
        except Exception as e:
            logger.error(f"删除发票失败: {e}")
            return False
    
    def delete_batch(self, ids: list[int]) -> bool:
        """
        批量删除发票
        
        Args:
            ids: 发票 ID 列表
            
        Returns:
            bool: 是否成功
        """
        try:
            invoice_dao.delete_batch(ids)
            return True
        except Exception as e:
            logger.error(f"批量删除失败: {e}")
            return False
    
    def clear_all(self) -> bool:
        """
        清空所有发票
        
        Returns:
            bool: 是否成功
        """
        try:
            invoice_dao.clear_all()
            logger.warning("已清空所有发票数据")
            return True
        except Exception as e:
            logger.error(f"清空数据库失败: {e}")
            return False
    
    def count(self) -> int:
        """获取发票总数"""
        return invoice_dao.count()
    
    def get_all_business_types(self) -> list[str]:
        """获取所有业务类型"""
        invoices = self.query()
        types = set(inv.business_type for inv in invoices if inv.business_type)
        return sorted(list(types))
    
    def get_all_invoice_types(self) -> list[str]:
        """获取所有发票类型"""
        invoices = self.query()
        types = set(inv.invoice_type for inv in invoices if inv.invoice_type)
        return sorted(list(types))


# 全局发票服务实例
invoice_service = InvoiceService()
