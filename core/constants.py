"""枚举常量定义"""

from enum import Enum


class BusinessType(str, Enum):
    """业务类型"""
    RAILWAY = "铁路12306"
    FLIGHT = "机票"
    TAXI = "打车"
    CATERING = "餐饮"
    HOTEL = "住宿"
    OFFICE = "办公用品"
    TELECOM = "通讯"
    GAS = "加油"
    PARKING = "停车"
    TOLL = "过路费"
    SHOPPING = "购物"
    OTHER = "其他"

    @classmethod
    def all_values(cls) -> list[str]:
        return [item.value for item in cls]


class InvoiceType(str, Enum):
    """发票类型"""
    E_INVOICE = "电子发票"
    VAT_SPECIAL = "增值税专票"
    VAT_NORMAL = "增值税普票"
    MACHINE_PRINT = "机打发票"
    FIXED_AMOUNT = "定额发票"
    RECEIPT = "收据"
    OTHER = "其他"

    @classmethod
    def all_values(cls) -> list[str]:
        return [item.value for item in cls]


class ReimbursementStatus(str, Enum):
    """报销状态"""
    NOT_REIMBURSED = "未报销"
    REIMBURSING = "报销中"
    REIMBURSED = "已报销"

    @classmethod
    def all_values(cls) -> list[str]:
        return [item.value for item in cls]


class InvoiceStatus(str, Enum):
    """发票状态"""
    NORMAL = "正常"
    ABNORMAL = "异常"

    @classmethod
    def all_values(cls) -> list[str]:
        return [item.value for item in cls]


class FileFormat(str, Enum):
    """文件格式"""
    XML = "xml"
    PDF = "pdf"
    OFD = "ofd"


# 支持的文件扩展名
SUPPORTED_EXTENSIONS = ['.xml', '.pdf', '.ofd']

# 必填字段（不可取消）
REQUIRED_FIELDS = [
    'invoice_number',
    'invoice_date',
    'amount_without_tax',
    'tax_amount',
    'total_amount'
]

# 表格列定义 (字段名, 显示名, 宽度)
TABLE_COLUMNS = [
    ('id', 'ID', 50),
    ('business_type', '业务类型', 100),
    ('invoice_type', '发票类型', 100),
    ('invoice_number', '发票号码', 150),
    ('invoice_date', '开票日期', 100),
    ('buyer_name', '购买方', 150),
    ('seller_name', '销售方', 150),
    ('amount_without_tax', '不含税金额', 100),
    ('tax_amount', '税额', 80),
    ('total_amount', '价税合计', 100),
    ('reimbursement_status', '报销状态', 80),
    ('status', '状态', 60),
    ('remark', '备注', 150),
]
