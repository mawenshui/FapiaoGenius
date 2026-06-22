"""解析器注册与调度"""

from pathlib import Path
from typing import Optional
from parsers.base_parser import BaseParser
from models.invoice import Invoice
from core.exceptions import ParseError
from core.logger import logger


class ParserRegistry:
    """解析器注册表"""
    
    def __init__(self):
        self._parsers: dict[str, BaseParser] = {}
    
    def register(self, ext: str, parser: BaseParser):
        """
        注册解析器
        
        Args:
            ext: 文件扩展名（如 '.xml', '.pdf'）
            parser: 解析器实例
        """
        self._parsers[ext.lower()] = parser
        logger.debug(f"已注册解析器: {ext} -> {parser.__class__.__name__}")
    
    def parse(self, file_path: str) -> Invoice:
        """
        根据文件扩展名调度解析器
        
        Args:
            file_path: 文件路径
            
        Returns:
            Invoice: 解析后的发票对象
            
        Raises:
            ParseError: 无对应解析器或解析失败
        """
        ext = Path(file_path).suffix.lower()
        
        parser = self._parsers.get(ext)
        if not parser:
            raise ParseError(f"不支持的文件格式: {ext}")
        
        if not parser.can_parse(file_path):
            raise ParseError(f"解析器无法处理该文件: {file_path}")
        
        return parser.parse(file_path)
    
    def get_supported_extensions(self) -> list[str]:
        """获取支持的文件扩展名列表"""
        return list(self._parsers.keys())
    
    def can_parse(self, file_path: str) -> bool:
        """判断是否有解析器能处理该文件"""
        ext = Path(file_path).suffix.lower()
        parser = self._parsers.get(ext)
        return parser is not None and parser.can_parse(file_path)


def create_registry(rule_service=None) -> ParserRegistry:
    """
    创建并初始化解析器注册表
    
    Args:
        rule_service: 规则服务实例（用于 PDF 解析器）
        
    Returns:
        ParserRegistry: 初始化后的注册表
    """
    from parsers.xml_parser import XMLParser
    from parsers.pdf_parser import PDFParser
    from parsers.ofd_parser import OFDParser
    
    registry = ParserRegistry()
    registry.register('.xml', XMLParser())
    registry.register('.pdf', PDFParser(rule_service))
    registry.register('.ofd', OFDParser())
    
    logger.info(f"解析器注册表已初始化，支持格式: {registry.get_supported_extensions()}")
    return registry
