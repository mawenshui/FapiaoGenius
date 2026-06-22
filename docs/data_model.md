# AI 智能发票识别管理系统 - 数据模型设计

## 1. 数据库设计

### 1.1 数据库配置

| 配置项 | 值 |
|--------|------|
| 引擎 | SQLite 3 |
| 日志模式 | WAL (Write-Ahead Logging) |
| 外键约束 | 启用 |
| 文件路径 | `%APPDATA%\ai_fapiao\invoices.db` |
| 连接方式 | 单例 + 上下文管理器 |

### 1.2 ER 关系图

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│    invoices      │    │   parse_rules     │    │    ai_config     │
├──────────────────┤    ├──────────────────┤    ├──────────────────┤
│ PK id            │    │ PK id            │    │ PK id (=1)       │
│    business_type │    │    rule_name     │    │    api_url       │
│    invoice_type  │    │    file_format   │    │    api_key       │
│ UK invoice_number│    │    match_keywords│    │    model_name    │
│    invoice_date  │    │    extraction_   │    │    custom_fields │
│    buyer_name    │    │    config        │    │    updated_at    │
│    seller_name   │    │    required_     │    └──────────────────┘
│    amount_       │    │    fields        │
│    without_tax   │    │    created_at    │
│    tax_amount    │    │    updated_at    │
│    total_amount  │    │    is_builtin    │
│    reimbursement │    └──────────────────┘
│    _status       │           ▲
│    status        │           │ rule_id
│    remark        │           │
│    source_file_  │───────────┘
│    path          │
│    file_format   │
│    rule_id       │
│    import_time   │
│    ai_learned    │
└──────────────────┘
```

- `invoices.rule_id` → `parse_rules.id`（逻辑关联，非外键约束）

---

## 2. 表结构定义

### 2.1 invoices — 发票信息表

```sql
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
```

**索引：**

```sql
CREATE INDEX idx_invoice_number ON invoices(invoice_number);
CREATE INDEX idx_invoice_date ON invoices(invoice_date);
CREATE INDEX idx_business_type ON invoices(business_type);
CREATE INDEX idx_reimbursement ON invoices(reimbursement_status);
```

**字段说明：**

| 字段 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| id | INTEGER | 自增主键 | 1 |
| business_type | TEXT | 业务类型（枚举值） | "餐饮" |
| invoice_type | TEXT | 发票类型（枚举值） | "电子发票" |
| invoice_number | TEXT | 发票号码（唯一约束，去重依据） | "01234567" |
| invoice_date | TEXT | 开票日期，YYYY-MM-DD 格式 | "2026-06-17" |
| buyer_name | TEXT | 购买方名称 | "XX科技有限公司" |
| seller_name | TEXT | 销售方名称 | "XX餐厅" |
| amount_without_tax | REAL | 不含税金额 | 100.00 |
| tax_amount | REAL | 税额 | 6.00 |
| total_amount | REAL | 价税合计（= 不含税 + 税额） | 106.00 |
| reimbursement_status | TEXT | 报销状态 | "未报销" / "报销中" / "已报销" |
| status | TEXT | 发票状态 | "正常" / "异常" |
| remark | TEXT | 用户备注 | "出差报销" |
| source_file_path | TEXT | 源文件绝对路径 | "C:\invoices\inv_001.pdf" |
| file_format | TEXT | 文件格式 | "xml" / "pdf" / "ofd" |
| rule_id | TEXT | 使用的解析规则 ID | "builtin_pdf_vat_normal" |
| import_time | TEXT | 导入时间，ISO 8601 格式 | "2026-06-17T10:30:00.123456" |
| ai_learned | INTEGER | 是否通过 AI 学习识别 | 0 / 1 |

### 2.2 parse_rules — 解析规则表

```sql
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
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT | 规则 UUID（主键） |
| rule_name | TEXT | 规则显示名称 |
| file_format | TEXT | 适用文件格式 ("pdf" / "ofd") |
| match_keywords | TEXT | 匹配关键词 JSON 数组 |
| extraction_config | TEXT | 提取规则 JSON 对象 |
| required_fields | TEXT | 必填字段 JSON 数组 |
| is_builtin | INTEGER | 是否内置规则 (0/1) |

**extraction_config JSON 结构：**

```json
{
  "invoice_number": {
    "type": "regex",
    "pattern": "发票号码[：:]\\s*(\\d+)"
  },
  "invoice_date": {
    "type": "regex",
    "pattern": "开票日期[：:]\\s*([\\d]{4}年[\\d]{1,2}月[\\d]{1,2}日)"
  },
  "total_amount": {
    "type": "regex",
    "pattern": "价税合计.*?￥?([\\d,]+\\.?\\d*)"
  }
}
```

**规则存储双重机制：**
- **文件系统**：`%APPDATA%\ai_fapiao\rules\{id}_{name}.json`
- **数据库**：`parse_rules` 表（AI 学习的规则）
- `RuleService.load_rules()` 从两者合并加载

### 2.3 ai_config — AI 配置表

```sql
CREATE TABLE IF NOT EXISTS ai_config (
    id              INTEGER PRIMARY KEY DEFAULT 1,
    api_url         TEXT NOT NULL DEFAULT '',
    api_key         TEXT NOT NULL DEFAULT '',
    model_name      TEXT NOT NULL DEFAULT 'deepseek-chat',
    custom_fields   TEXT DEFAULT '[]',
    updated_at      TEXT NOT NULL DEFAULT ''
);
```

- 单行配置表，`id` 固定为 1
- `api_key` 使用 Fernet 加密存储
- `custom_fields` 为用户自定义字段的 JSON 数组

---

## 3. 枚举值定义

### 3.1 业务类型 (BusinessType)

| 枚举值 | 中文显示 | 关键词自动推断 |
|--------|----------|---------------|
| railway | 铁路12306 | 铁路、12306、火车票 |
| flight | 机票 | 航空、机票、飞机 |
| taxi | 打车 | 出租车、打车、滴滴 |
| catering | 餐饮 | 餐饮、餐厅、饭店 |
| hotel | 住宿 | 酒店、宾馆、住宿 |
| office | 办公用品 | 办公、文具 |
| telecom | 通讯 | 电信、移动、联通 |
| gas | 加油 | 加油、石油、石化 |
| parking | 停车 | 停车 |
| toll | 过路费 | 过路费、通行费 |
| shopping | 购物 | - |
| other | 其他 | 默认值 |

### 3.2 发票类型 (InvoiceType)

| 枚举值 | 中文显示 | PDF 文本匹配 |
|--------|----------|-------------|
| e_invoice | 电子发票 | "增值税电子普通发票"、"电子发票" |
| vat_special | 增值税专票 | "增值税专用发票" |
| vat_normal | 增值税普票 | "增值税普通发票" |
| machine_print | 机打发票 | "机打发票" |
| fixed_amount | 定额发票 | "定额发票" |
| receipt | 收据 | - |
| other | 其他 | 默认值 |

### 3.3 报销状态 (ReimbursementStatus)

| 枚举值 | 中文显示 |
|--------|----------|
| not_reimbursed | 未报销 |
| reimbursing | 报销中 |
| reimbursed | 已报销 |

### 3.4 发票状态 (InvoiceStatus)

| 枚举值 | 中文显示 |
|--------|----------|
| normal | 正常 |
| abnormal | 异常 |

---

## 4. 数据模型类映射

### 4.1 Python dataclass ↔ 数据库表

```
Invoice (models/invoice.py)       ←→ invoices 表
  to_dict()                         → INSERT 参数
  from_row(sqlite3.Row)             ← SELECT 结果

ParseRule (models/parse_rule.py)  ←→ parse_rules 表
  to_dict() (JSON 序列化列表字段)   → INSERT 参数
  to_json() (格式化 JSON)           → 规则文件
  from_row(sqlite3.Row)             ← SELECT 结果
  from_json(str)                    ← 规则文件读取

AIConfig (models/ai_config.py)    ←→ ai_config 表
  to_dict()                         → INSERT 参数
  from_row(sqlite3.Row)             ← SELECT 结果
```

### 4.2 JSON 序列化约定

| 模型 | 字段 | 存储方式 |
|------|------|----------|
| ParseRule | match_keywords | `json.dumps(list)` → TEXT |
| ParseRule | extraction_config | `json.dumps(dict)` → TEXT |
| ParseRule | required_fields | `json.dumps(list)` → TEXT |
| AIConfig | custom_fields | `json.dumps(list)` → TEXT |
| Invoice | ai_learned | `bool → int (0/1)` |

---

## 5. 数据安全

### 5.1 API Key 加密

```
明文 api_key
  → Fernet.encrypt()
  → 加密字符串存储到数据库
  
密钥派生:
  username + 固定盐值 → SHA256 → base64 → Fernet key
```

### 5.2 去重机制

- 导入时通过 `invoice_number` (UNIQUE 约束) 去重
- 重复发票计入 `skipped` 统计，不报错

### 5.3 数据完整性

- 必填字段验证：`invoice_number`、`invoice_date`、`total_amount`
- 金额逻辑验证：`amount_without_tax + tax_amount ≈ total_amount`
- 事务保证：批量操作在事务中执行，失败自动回滚

---

## 6. 数据迁移策略

当前版本 (v1.1) 未对数据库 Schema 做结构性变更（与 v1.0 保持一致）。后续如需变更：

1. 在 `database/schema.py` 中添加 `migrate()` 函数
2. 检查现有表结构（`PRAGMA table_info`）
3. 执行 ALTER TABLE 添加新列
4. 更新对应的 Model 和 DAO

```python
def migrate():
    conn = db.get_connection()
    columns = [row[1] for row in conn.execute("PRAGMA table_info(invoices)").fetchall()]
    if 'new_column' not in columns:
        conn.execute("ALTER TABLE invoices ADD COLUMN new_column TEXT DEFAULT ''")
```
