# AI 智能发票识别管理系统 - 模块详细设计

## 1. 模块总览

| 模块 | 路径 | 职责 | 状态 |
|------|------|------|------|
| 基础设施 | `core/` | 全局配置、常量、日志、异常 | ✅ 完成 |
| 数据模型 | `models/` | Invoice、ParseRule、AIConfig | ✅ 完成 |
| 数据访问 | `database/` | SQLite 连接、DAO 层 | ✅ 完成 |
| 解析引擎 | `parsers/` | 多格式发票解析 | ✅ 完成 |
| 配置管理 | `config/` | 规则文件管理 | ✅ 完成 |
| 业务逻辑 | `services/` | 导入/导出/查询/AI | ✅ 完成 |
| UI 视图 | `views/` | PyQt5 界面 | ✅ 完成 |
| 工具函数 | `utils/` | 文件/加密/验证 | ✅ 完成 |

---

## 2. core/ 基础设施层

### 2.1 app_config.py — 全局配置

```python
class AppConfig:
    APP_NAME = "ai_fapiao"
    
    @property data_dir   → %APPDATA%/ai_fapiao/
    @property db_path    → data_dir/invoices.db
    @property rules_dir  → data_dir/rules/
    @property log_dir    → data_dir/logs/
    @property builtin_rules_dir → 项目内 config/builtin_rules/
    
    def ensure_dirs()    → 创建目录 + 复制内置规则
```

- **单例模式**，全局实例 `app_config`
- 首次启动自动复制 `builtin_rules/` 到用户 `rules/` 目录

### 2.2 constants.py — 枚举常量

| 枚举类 | 值 |
|--------|------|
| `BusinessType` | 铁路12306、机票、打车、餐饮、住宿、办公用品、通讯、加油、停车、过路费、购物、其他 |
| `InvoiceType` | 电子发票、增值税专票、增值税普票、机打发票、定额发票、收据、其他 |
| `ReimbursementStatus` | 未报销、报销中、已报销 |
| `InvoiceStatus` | 正常、异常 |
| `FileFormat` | xml、pdf、ofd |

另定义：`SUPPORTED_EXTENSIONS`、`REQUIRED_FIELDS`、`TABLE_COLUMNS`

### 2.3 logger.py — 日志

- 控制台输出 INFO 级别
- 文件输出 DEBUG 级别
- 日志文件：`%APPDATA%/ai_fapiao/logs/app.log`

### 2.4 exceptions.py — 异常类

```
AppError (基类)
├── ParseError          # 解析失败
├── RuleMatchError      # 规则不匹配（触发 AI 学习）
├── DuplicateInvoiceError # 重复发票
├── ValidationError     # 数据验证失败
├── DatabaseError       # 数据库错误
└── AIServiceError      # AI 服务错误
```

---

## 3. models/ 数据模型层

### 3.1 Invoice — 发票模型

```python
@dataclass
class Invoice:
    id: int | None
    business_type: str       # 业务类型
    invoice_type: str        # 发票类型
    invoice_number: str      # 发票号码（唯一）
    invoice_date: str        # 开票日期 (YYYY-MM-DD)
    buyer_name: str          # 购买方
    seller_name: str         # 销售方
    amount_without_tax: float # 不含税金额
    tax_amount: float        # 税额
    total_amount: float      # 价税合计
    reimbursement_status: str # 报销状态
    status: str              # 状态
    remark: str              # 备注
    source_file_path: str    # 源文件路径
    file_format: str         # 文件格式
    rule_id: str             # 使用的规则 ID
    import_time: str         # 导入时间
    ai_learned: bool         # 是否 AI 学习

    def to_dict() -> dict
    @classmethod from_row(row) -> Invoice
    def set_import_time()
```

### 3.2 ParseRule — 解析规则模型

```python
@dataclass
class ParseRule:
    id: str                  # UUID
    rule_name: str           # 规则名称
    file_format: str         # 适用格式
    match_keywords: list[str] # 匹配关键词
    extraction_config: dict  # 提取配置 {field: {type, pattern}}
    required_fields: list[str]
    created_at: str
    updated_at: str
    is_builtin: bool

    def to_dict() -> dict     # 数据库用（JSON 序列化 list/dict）
    def to_json() -> str      # 文件用（格式化 JSON）
    @classmethod from_row(row) -> ParseRule
    @classmethod from_json(str) -> ParseRule
```

### 3.3 AIConfig — AI 配置模型

```python
@dataclass
class AIConfig:
    id: int = 1              # 固定为 1（单行配置）
    api_url: str
    api_key: str             # 解密后的明文
    model_name: str
    custom_fields: list[str]
    updated_at: str
```

---

## 4. database/ 数据访问层

### 4.1 connection.py — 连接管理

- **单例** `DatabaseConnection`，全局实例 `db`
- SQLite WAL 模式 + 外键约束
- `get_connection()` 返回带 `Row` 工厂的连接
- `transaction()` 上下文管理器自动 commit/rollback

### 4.2 invoice_dao.py — 发票 CRUD

| 方法 | 说明 |
|------|------|
| `insert(invoice)` | 插入发票，返回 ID |
| `insert_batch(invoices)` | 批量插入 |
| `get_by_id(id)` | 按 ID 查询 |
| `get_all(filters)` | 动态筛选查询 |
| `update(invoice)` | 全量更新 |
| `update_field(id, field, value)` | 单字段更新（白名单校验） |
| `delete(id)` | 删除 |
| `delete_batch(ids)` | 批量删除 |
| `clear_all()` | 清空 |
| `exists_by_number(number)` | 去重检查 |
| `count()` | 总数 |

**筛选查询构建：**
```python
FilterCriteria(
    business_type, invoice_type, reimbursement_status,
    status, date_from, date_to, search_text
)
→ 动态 WHERE 条件拼接
→ 搜索字段：invoice_number, buyer_name, seller_name, remark
```

### 4.3 rule_dao.py — 规则 CRUD

- `insert(rule)` — INSERT OR REPLACE
- `get_all()` / `get_by_id(id)` / `get_by_format(format)`
- `update(rule)` / `delete(id)`

### 4.4 config_dao.py — AI 配置

- `get()` — 获取配置（不存在返回默认值）
- `save(config)` — UPSERT（id 固定为 1）

---

## 5. parsers/ 解析引擎层

### 5.1 BaseParser — 抽象基类

```python
class BaseParser(ABC):
    @abstractmethod parse(file_path) -> Invoice
    @abstractmethod can_parse(file_path) -> bool
    def _validate_required(invoice, required_fields)  # 验证必填字段
    def _get_file_format(file_path) -> str
```

### 5.2 XMLParser — XML 发票解析

- 支持多种命名空间（`fp:` 前缀和无前缀）
- 多路径探测：每种字段定义多个 XPath，依次尝试
- 双重解析策略：`_parse_standard_xml()` → `_parse_simple_xml()`
- 自动推断业务类型（根据销售方名称关键词）

### 5.3 PDFParser — PDF 规则解析

- 依赖 `TextExtractor` 提取文本
- 优先使用 `RuleService` 匹配规则
- 降级到通用正则解析 (`_parse_generic`)
- 自动推断业务类型和发票类型
- 金额计算补全：缺失字段通过 `total = amount + tax` 推算

### 5.4 OFDParser — OFD 完整解析

OFD 是 ZIP 包，内含多层 XML 文件。采用双策略解析：

**策略1：XML 委托解析**
- 按优先级查找候选 XML（`Doc_0/Content.xml` → `Pages/Page_0/Content.xml` → 含“发票”的 XML）
- 委托给 `XMLParser._parse_standard_xml()` + `_parse_simple_xml()` 解析
- 合并结果，补全缺失字段

**策略2：全文正则降级**
- 从所有 XML 中提取纯文本
- 调用 `PDFParser._parse_generic()` 正则匹配

```python
class OFDParser(BaseParser):
    _CANDIDATE_PATHS = ['Doc_0/Content.xml', 'Doc_0/Pages/Page_0/Content.xml', ...]
    
    def parse(file_path) -> Invoice:
        # 策略1: 候选 XML → XMLParser 委托
        # 策略2: 全文提取 → PDFParser 正则降级
        # 均失败: ParseError 引导 AI 学习
    
    def _find_invoice_xml(zf, names) -> list[str]  # 优先级排序
    def _parse_ofd_xml(root) -> Invoice             # 委托 XMLParser
    def _extract_all_text_from_ofd(zf, names) -> str # 全文提取
    def _parse_with_regex_fallback(text, path) -> Invoice  # 正则降级
```

### 5.5 ParserRegistry — 工厂调度

```python
registry.register('.xml', XMLParser())
registry.register('.pdf', PDFParser(rule_service))
registry.register('.ofd', OFDParser())

registry.parse(file_path)  # 按扩展名分发
```

### 5.6 TextExtractor — PDF 文本提取

- 主选 pdfplumber：`extract_text()` 全文 + `extract_words()` 带坐标
- 降级 PyMuPDF：`fitz.open()` + `get_text()`

---

## 6. services/ 业务逻辑层

### 6.1 ImportService — 导入编排

**核心数据结构：**
```python
@dataclass ImportResult:
    total: int
    success: int
    failed: int
    skipped: int
    failed_details: list[FailedFile]

@dataclass FailedFile:
    file_path: str
    file_name: str
    reason: str
    is_rule_mismatch: bool  # 决定是否显示 AI 学习按钮
```

**异步导入：**
```python
ImportWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished_signal = pyqtSignal(object)
    
ImportService.import_files_async(paths)  # 创建线程并启动
ImportService.cancel_import()            # 设置取消标志
```

### 6.2 ExportService — Excel 导出

- 使用 openpyxl 生成 `.xlsx`
- 带表头样式（蓝底白字）
- 金额列格式化 `#,##0.00`
- 全表边框
- 自动列宽

### 6.3 RuleService — 规则管理

- `load_rules()` — 从文件 + 数据库加载所有规则
- `match_rule(text, format)` — 关键词命中率评分，返回最佳匹配
- `save_rule(rule)` — 同时保存到文件和数据库
- `delete_rule(id)` — 同时从文件和数据库删除

### 6.4 InvoiceService — 发票管理

- `query(filters)` — 委托 InvoiceDAO
- `update_field(id, field, value)` — 单字段更新
- `delete_batch(ids)` — 批量删除
- `clear_all()` — 清空数据库

### 6.5 AIService — AI 服务（OpenAI 兼容 API）

使用 `urllib.request` 调用 OpenAI 兼容的 Chat Completion API，无新依赖。

| 方法 | 说明 |
|------|------|
| `get_config()` / `save_config()` | 配置管理（含 Fernet 加密解密） |
| `_call_api(messages, temperature, use_json_format)` | 统一 API 入口，POST 到 `{api_url}/chat/completions` |
| `_handle_http_error(code, body)` | HTTP 错误分类处理（401/429/5xx） |
| `_extract_json_from_text(text)` | 从 markdown 代码块 / 裸 JSON 中提取 |
| `_extract_text_for_ai(file_path)` | 按格式提取文本（PDF→pdfplumber, XML→ET, OFD→ZIP+XML） |
| `_postprocess_invoice_data(data)` | 金额转换 + 日期标准化 + 金额校验 |
| `test_connection()` | 发送简单 prompt 验证连接 |
| `analyze_invoice(file_path)` | 构造 prompt 提取 10 个字段 + JSON 返回 |
| `learn_format(file_path)` | AI 分析 + 建议 extraction_config 和 match_keywords |

**API 调用流程：**
```
_call_api(messages)
  → urllib.request.Request(url, data, headers)
  → urllib.request.urlopen(req, timeout=60, ssl_ctx)
  → json.loads(response) → choices[0].message.content → json.loads()
  → 异常: HTTPError → _handle_http_error() / URLError / JSONDecodeError
  → 降级: response_format 不支持时去掉该参数重试
```

**Prompt 设计：**
- `analyze_invoice`: 提取 10 个字段（invoice_number/date/buyer/seller/3个金额/2个类型/confidence）
- `learn_format`: 同上 + 额外要求 AI 建议正则 extraction_config 和 match_keywords
- 金额校验: `abs(total - (amount + tax)) < 0.02`

---

## 7. views/ UI 层

### 7.1 MainWindow — 主窗口

```
MainWindow (QMainWindow)
├── MenuBar (文件/编辑/工具/帮助)
├── CentralWidget
│   ├── Sidebar (120px 固定宽)
│   └── QStackedWidget
│       ├── [0] InvoicePage
│       ├── [1] ComboPage
│       ├── [2] RulePage
│       └── [3] SettingsPage
└── StatusBar
```

### 7.2 InvoicePage — 发票管理页面

```
InvoicePage (QWidget, acceptDrops=True)
├── InvoiceToolbar
├── FilterBar
├── SearchBar
├── QSplitter
│   ├── InvoiceTable (3/4 宽度, acceptDrops=False)
│   └── DetailPanel (1/4 宽度, 300~400px)
└── StatusBarWidget (总数 + 选中数)
```

**信号编排：**
- Toolbar → 导入/导出/清空
- FilterBar → filter_changed → _load_data()
- SearchBar → search/reset → _load_data()
- Table → row_selected → DetailPanel.show_invoice()
- DetailPanel → field_updated → InvoiceService.update_field()
- ImportResultDialog → ai_learn_clicked → AILearnDialog

**拖拽导入（v1.1）：**
- `dragEnterEvent`: 检查 MIME URL，验证支持格式或文件夹
- `dragLeaveEvent`: 清除视觉指示器
- `dropEvent`: 提取路径（文件夹自动扫描），调用 `_start_import()`
- `_show_drop_indicator`: 蓝色虚线边框 `#1890ff`
- `InvoiceTable.setAcceptDrops(False)`: 防止子组件截获事件

### 7.3 InvoiceTable — 发票表格

- QTableWidget + 自定义 checkbox 列
- 排序支持 (`setSortingEnabled`)
- 行选中模式 (`SelectRows`)
- 交替行色
- 金额列右对齐
- 发票 ID 存储在 `Qt.UserRole`

### 7.4 DetailPanel — 详情面板

- **只读区**：发票号码、日期、类型、购买方、销售方、金额
- **可编辑区**：业务类型(ComboBox)、报销状态(ComboBox)、状态(ComboBox)、备注(LineEdit)
- **源文件区**：路径显示+复制、打开文件按钮、导入时间
- 空状态提示："请选择一张发票查看详情"

### 7.5 ImportResultDialog — 导入结果

- 统计摘要：总数/成功/失败/跳过
- 失败文件列表（可滚动）：文件名超链接 + 失败原因
- AI 学习按钮（仅规则不匹配时显示，`ai_learn_clicked` 信号 → AILearnDialog）

### 7.6 对话框组件

- **ProgressDialog**：进度条 + 当前文件 + 取消按钮
- **ConfirmDialog**：通用二次确认
- **SettingsPage**：AI API 配置表单（API URL/Key/模型 + 真实连接测试）

### 7.7 AILearnDialog — AI 学习对话框 (v1.1)

```
AILearnDialog (QDialog)
├── AIWorker(QThread)       # 异步 AI 调用
│   ├── finished(object)     # dict 或 Exception
│   └── progress(str)        # 状态文本
├── 文件信息区: 文件名 + 打开文件链接
├── API 连接区: 状态标签 + 测试连接按钮
├── 操作区: 开始 AI 识别按钮
├── 进度区: 状态文本 + 不确定进度条
├── 结果区 (QScrollArea + QFormLayout):
│   ├── invoice_number (QLineEdit)
│   ├── invoice_date (QLineEdit)
│   ├── buyer_name / seller_name (QLineEdit)
│   ├── amount / tax / total (QDoubleSpinBox)
│   ├── invoice_type / business_type (QComboBox)
│   └── validation_label (金额实时校验)
└── 按钮区: 保存为新规则 + 导入此发票 + 关闭
```

**核心方法：**
- `_on_test_connection()` → `ai_service.test_connection()`
- `_on_start_analysis()` → `AIWorker(file_path, 'analyze')`
- `_on_analysis_finished(result)` → 填充表单 + 金额校验
- `_on_save_as_rule()` → `AIWorker(file_path, 'learn')` → 构造 ParseRule → `rule_service.save_rule()`
- `_on_import_invoice()` → 构造 Invoice(ai_learned=True) → `invoice_dao.insert()`

### 7.8 RulePage — 规则管理页面 (v1.1)

```
RulePage (QWidget)
├── 标题栏: "规则管理" + [刷新] + [导入规则]
├── QTableWidget (6 列)
│   ├── 规则名称 | 文件格式 | 匹配关键词 | 来源 | 更新时间 | 操作
│   └── 操作列: [查看] [编辑](仅自定义) [删除](仅自定义) [导出]
└── 状态栏: "共 X 条规则"
```

**核心方法：**
- `_load_rules()` → `rule_service.get_all_rules()` → 填充表格
- `_on_view_rule(id)` → `RuleDetailDialog(editable=False)`
- `_on_edit_rule(id)` → `RuleDetailDialog(editable=True)` → 保存
- `_on_delete_rule(id)` → ConfirmDialog → `rule_service.delete_rule()`
- `_on_import_rule()` → 文件选择 → `ParseRule.from_json()` → `rule_service.save_rule()`
- `showEvent()` → 自动刷新

**RuleDetailDialog — 规则详情对话框：**
- 查看模式：只读展示所有字段 + JSON 配置
- 编辑模式：可编辑 rule_name / match_keywords / extraction_config（JSON 编辑器）
- 内置规则只读保护，不可编辑/删除

---

## 8. utils/ 工具层

| 模块 | 函数 | 说明 |
|------|------|------|
| file_utils | `open_file(path)` | os.startfile 打开文件 |
| | `get_file_extension(path)` | 获取小写扩展名 |
| | `is_supported_file(path)` | 检查是否支持格式 |
| | `get_files_from_folder(path)` | 递归扫描文件夹 |
| crypto | `encrypt_key(text)` | Fernet 加密 |
| | `decrypt_key(text)` | Fernet 解密（降级 base64） |
| validators | `validate_invoice(invoice)` | 必填字段校验 |
| | `validate_amounts(invoice)` | 金额逻辑校验 |
| | `normalize_date(text)` | 日期格式标准化 |
| | `parse_amount(text)` | 金额字符串解析 |

---

## 8. services/combo_service.py — 智能凑票服务

### 8.1 架构设计

```
统一搜索引擎
  _backtrack_search (≤50张)
    ├── 回溯 + 剪枝（less/greater 模式感知）
    ├── 堆管理保留最优方案（差额最小）
    └── 最大节点数限制 500000
  _greedy_search (>50张，降级)
    ├── 贪心策略1: 大额优先
    └── 贪心策略2: 小额优先

策略排序层
  _sort_by_strategy
    ├── fewest: 张数升序 → 差额绝对值升序
    ├── most: 张数降序 → 差额绝对值升序
    ├── large_first: 平均金额降序 → 差额绝对值升序
    └── small_first: 平均金额升序 → 差额绝对值升序
```

### 8.2 核心参数

| 参数 | 类型 | 说明 |
|------|------|------|
| target_amount | float | 目标金额 |
| amount_mode | str | `less`（可少于）或 `greater`（可大于） |
| strategy | str | `fewest` / `most` / `large_first` / `small_first` |
| max_solutions | int | 最多返回方案数（默认 10） |

### 8.3 关键算法

| 方法 | 职责 |
|------|------|
| `find_combinations(params)` | 编排搜索 → 排序 → 截取 |
| `_backtrack_search(invoices, params)` | 回溯搜索，内置差额最小逻辑 |
| `_greedy_search(invoices, params)` | 贪心降级（>50张发票） |
| `_sort_by_strategy(solutions, params)` | 按策略偏好排序 |
| `set_reimbursement_status(ids, status)` | 批量更新报销状态 |

### 8.4 设计原则

- **搜索与排序职责分离**：搜索引擎负责找到差额最小的方案集合，策略仅影响排序
- **差额最小内化**：所有模式都内置差额最小逻辑，无需单独选项
- **模式感知剪枝**：`less` 模式超过目标即剪枝，`greater` 模式超过目标+阈值即剪枝

