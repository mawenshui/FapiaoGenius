"""自定义异常类"""


class AppError(Exception):
    """应用基础异常"""
    pass


class ParseError(AppError):
    """发票解析错误"""
    pass


class RuleMatchError(AppError):
    """规则匹配失败"""
    pass


class DuplicateInvoiceError(AppError):
    """重复发票错误"""
    pass


class ValidationError(AppError):
    """数据验证错误"""
    pass


class DatabaseError(AppError):
    """数据库操作错误"""
    pass


class AIServiceError(AppError):
    """AI 服务调用错误"""
    pass
