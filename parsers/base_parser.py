"""解析器抽象基类"""

from abc import ABC, abstractmethod
from models.invoice import Invoice
from core.exceptions import ParseError, ValidationError
from core.constants import REQUIRED_FIELDS


class BaseParser(ABC):
    """发票解析器抽象基类"""
    
    @abstractmethod
    def parse(self, file_path: str) -> Invoice:
        """
        解析发票文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            Invoice: 解析后的发票对象
            
        Raises:
            ParseError: 解析失败时抛出
        """
        pass
    
    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """
        判断是否能解析该文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否能解析
        """
        pass
    
    def _validate_required(self, invoice: Invoice, required_fields: list[str] = None) -> None:
        """
        验证必填字段完整性
        
        Args:
            invoice: 发票对象
            required_fields: 需要验证的字段列表，默认使用全局必填字段
            
        Raises:
            ValidationError: 缺少必填字段时抛出
        """
        if required_fields is None:
            required_fields = REQUIRED_FIELDS
        
        missing = []
        for field in required_fields:
            value = getattr(invoice, field, None)
            if value is None or value == '' or value == 0.0:
                missing.append(field)
        
        if missing:
            raise ValidationError(f"缺少必填字段: {', '.join(missing)}")
    
    def _get_file_format(self, file_path: str) -> str:
        """获取文件格式"""
        from utils.file_utils import get_file_extension
        return get_file_extension(file_path).lstrip('.')
