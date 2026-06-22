"""数据验证工具函数"""

from typing import Optional
from core.exceptions import ValidationError
from core.constants import REQUIRED_FIELDS
from models.invoice import Invoice


def validate_invoice(invoice: Invoice) -> None:
    """验证发票数据完整性"""
    errors = []
    
    # 验证必填字段
    if not invoice.invoice_number:
        errors.append("发票号码不能为空")
    if not invoice.invoice_date:
        errors.append("开票日期不能为空")
    
    # 验证金额
    if invoice.amount_without_tax < 0:
        errors.append("不含税金额不能为负数")
    if invoice.tax_amount < 0:
        errors.append("税额不能为负数")
    if invoice.total_amount < 0:
        errors.append("价税合计不能为负数")
    
    if errors:
        raise ValidationError("; ".join(errors))


def validate_amounts(invoice: Invoice, tolerance: float = 0.02) -> bool:
    """验证金额逻辑（不含税金额 + 税额 ≈ 价税合计）"""
    expected = invoice.amount_without_tax + invoice.tax_amount
    diff = abs(invoice.total_amount - expected)
    
    if diff > tolerance:
        return False
    return True


def validate_date_format(date_str: str) -> bool:
    """验证日期格式（YYYY-MM-DD）"""
    if not date_str:
        return False
    
    import re
    pattern = r'^\d{4}-\d{2}-\d{2}$'
    if not re.match(pattern, date_str):
        return False
    
    # 尝试解析
    from datetime import datetime
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def normalize_date(date_str: str) -> Optional[str]:
    """标准化日期格式为 YYYY-MM-DD"""
    if not date_str:
        return None
    
    import re
    from datetime import datetime
    
    # 尝试多种格式
    formats = [
        '%Y-%m-%d',
        '%Y年%m月%d日',
        '%Y/%m/%d',
        '%Y.%m.%d',
        '%Y%m%d',
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # 尝试正则提取
    match = re.search(r'(\d{4})\D+(\d{1,2})\D+(\d{1,2})', date_str)
    if match:
        y, m, d = match.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"
    
    return None


def parse_amount(text: str) -> float:
    """解析金额字符串为浮点数"""
    if not text:
        return 0.0
    
    import re
    # 移除货币符号和空格
    cleaned = re.sub(r'[¥￥$€\s,，]', '', str(text))
    
    try:
        return float(cleaned)
    except ValueError:
        return 0.0
