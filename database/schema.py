"""数据库 Schema 定义"""

from database.connection import db
from core.logger import logger


SCHEMA_SQL = """
-- 发票信息表
CREATE TABLE IF NOT EXISTS invoices (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    business_type          TEXT    NOT NULL,
    invoice_type           TEXT    NOT NULL,
    invoice_number         TEXT    UNIQUE NOT NULL,
    invoice_date           TEXT    NOT NULL,
    buyer_name             TEXT    DEFAULT '',
    seller_name            TEXT    DEFAULT '',
    amount_without_tax     REAL    NOT NULL DEFAULT 0.0,
    tax_amount             REAL    NOT NULL DEFAULT 0.0,
    total_amount           REAL    NOT NULL DEFAULT 0.0,
    reimbursement_status   TEXT    DEFAULT '未报销',
    status                 TEXT    DEFAULT '正常',
    remark                 TEXT    DEFAULT '',
    source_file_path       TEXT    NOT NULL,
    file_format            TEXT    NOT NULL,
    rule_id                TEXT    DEFAULT '',
    import_time            TEXT    NOT NULL,
    ai_learned             INTEGER DEFAULT 0
);

-- 发票表索引
CREATE INDEX IF NOT EXISTS idx_invoice_number ON invoices(invoice_number);
CREATE INDEX IF NOT EXISTS idx_invoice_date ON invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_business_type ON invoices(business_type);
CREATE INDEX IF NOT EXISTS idx_reimbursement ON invoices(reimbursement_status);

-- 解析规则表
CREATE TABLE IF NOT EXISTS parse_rules (
    id                TEXT PRIMARY KEY,
    rule_name         TEXT NOT NULL,
    file_format       TEXT NOT NULL,
    match_keywords    TEXT NOT NULL DEFAULT '[]',
    extraction_config TEXT NOT NULL DEFAULT '{}',
    required_fields   TEXT NOT NULL DEFAULT '[]',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    is_builtin        INTEGER DEFAULT 0
);

-- AI 配置表（单行）
CREATE TABLE IF NOT EXISTS ai_config (
    id              INTEGER PRIMARY KEY DEFAULT 1,
    api_url         TEXT NOT NULL DEFAULT '',
    api_key         TEXT NOT NULL DEFAULT '',
    model_name      TEXT NOT NULL DEFAULT 'deepseek-chat',
    custom_fields   TEXT DEFAULT '[]',
    updated_at      TEXT NOT NULL DEFAULT ''
);
"""


def init_schema():
    """初始化数据库表结构"""
    try:
        with db.transaction() as conn:
            conn.executescript(SCHEMA_SQL)
        logger.info("数据库 Schema 初始化完成")
    except Exception as e:
        logger.error(f"数据库 Schema 初始化失败: {e}")
        raise
