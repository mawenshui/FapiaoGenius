# 智票通 (FapiaoGenius) - 系统架构文档

## 1. 架构总览

系统采用 **分层架构** 设计，各层职责清晰、低耦合：

```
┌──────────────────────────────────────────────────────────────┐
│                        views/ (UI 层)                        │
│   MainWindow → Sidebar + QStackedWidget                      │
│     ├── InvoicePage (Toolbar + FilterBar + SearchBar          │
│     │               + InvoiceTable + DetailPanel + PDF预览   │
│     │               + 拖拽导入 + 批量操作 + 金额范围搜索)       │
│     ├── ComboPage (智能凑票：参数配置 + 方案表格 + 详情 + 一键报销) │
│     ├── StatsPage (统计报表：matplotlib 图表 + 数据总览)       │
│     ├── RulePage (规则管理 CRUD)                              │
│     ├── AIPage (AI 识别 + 学习过程展示)                       │
│     └── SettingsPage (AI配置 + 主题切换 + 配置迁移)           │
│   对话框:                                                     │
│     ├── AILearnDialog (AI 识别 + 学习 + 规则生成)              │
│     ├── ImportResultDialog (导入结果 + AI 学习入口)            │
│     ├── ProgressDialog | ConfirmDialog                       │
├──────────────────────────────────────────────────────────────┤
│                     services/ (业务逻辑层)                     │
│   ImportService | ExportService (Excel/CSV) | RuleService     │
│   InvoiceService | AIService | ComboService                   │
│   StatsService | BackupService | UpdateService                │
│   ConfigTransferService                                       │
├──────────────────────────────────────────────────────────────┤
│                     parsers/ (解析引擎层)                      │
│   ParserRegistry → XMLParser | PDFParser | OFDParser          │
│   TextExtractor (pdfplumber → PyMuPDF → OCR 三级降级)        │
├──────────────────────────────────────────────────────────────┤
│                     database/ (数据访问层)                     │
│   DatabaseConnection (单例) → InvoiceDAO | RuleDAO | ConfigDAO│
├──────────────────────────────────────────────────────────────┤
│                     models/ (数据模型层)                       │
│   Invoice | ParseRule | AIConfig (dataclass)                 │
├──────────────────────────────────────────────────────────────┤
│                     core/ (基础设施层)                         │
│   AppConfig | Constants | Logger | Exceptions                │
└──────────────────────────────────────────────────────────────┘
```

## 2. 目录结构

```
ai_fapiao/
├── main.py                     # 应用入口
├── pyproject.toml              # 构建配置
├── requirements.txt            # 依赖清单
├── setup.py                    # 安装脚本
├── .gitignore
├── core/                       # 基础设施层
│   ├── __init__.py
│   ├── app_config.py           # 全局配置（路径、目录管理）
│   ├── constants.py            # 枚举常量（业务类型、发票类型等）
│   ├── logger.py               # 日志配置
│   └── exceptions.py           # 自定义异常
├── models/                     # 数据模型（@dataclass）
│   ├── __init__.py
│   ├── invoice.py              # Invoice 发票模型
│   ├── parse_rule.py           # ParseRule 解析规则模型
│   └── ai_config.py            # AIConfig AI 配置模型
├── database/                   # 数据访问层
│   ├── __init__.py
│   ├── connection.py           # SQLite 连接管理（单例+事务）
│   ├── schema.py               # 建表 DDL
│   ├── invoice_dao.py          # 发票 CRUD + 动态筛选
│   ├── rule_dao.py             # 规则 CRUD
│   └── config_dao.py           # AI 配置 CRUD
├── parsers/                    # 发票解析引擎
│   ├── __init__.py
│   ├── base_parser.py          # 解析器抽象基类 (ABC)
│   ├── xml_parser.py           # XML 电子发票解析
│   ├── pdf_parser.py           # PDF 规则解析 + 段落分隔法 + 通用降级
│   ├── ofd_parser.py           # OFD 完整解析 (XML委托 + 正则降级)
│   ├── parser_registry.py      # 工厂模式调度注册表
│   └── text_extractor.py       # PDF 文本提取
├── services/                   # 业务逻辑层
│   ├── __init__.py
│   ├── import_service.py       # 导入编排 + QThread 异步
│   ├── export_service.py       # Excel / CSV 导出
│   ├── rule_service.py         # 规则匹配与管理
│   ├── invoice_service.py      # 发票查询/编辑/删除
│   ├── ai_service.py           # AI 服务 (OpenAI 兼容 API + urllib)
│   ├── combo_service.py        # 智能凑票 (回溯搜索 + 策略排序)
│   ├── stats_service.py        # 统计报表 (聚合查询)
│   ├── backup_service.py       # 数据备份与恢复 (ZIP)
│   ├── update_service.py       # 自动更新 (GitHub Release API)
│   └── config_transfer_service.py  # 配置导入导出
├── config/                     # 配置管理
│   ├── __init__.py
│   ├── rule_manager.py         # 规则 JSON 文件读写
│   └── builtin_rules/          # 内置解析规则
│       ├── xml_e_invoice.json
│       └── pdf_vat_normal.json
├── views/                      # UI 层 (PyQt5)
│   ├── __init__.py
│   ├── main_window.py          # 主窗口（菜单栏+侧边栏+页面栈+状态栏）
│   ├── sidebar.py              # 导航侧边栏
│   ├── toolbar.py              # 工具栏
│   ├── invoice_page.py         # 发票管理页面（核心）
│   ├── filter_bar.py           # 筛选栏
│   ├── search_bar.py           # 搜索栏
│   ├── invoice_table.py        # 发票表格（QTableWidget + checkbox + 报销状态颜色）
│   ├── detail_panel.py         # 详情面板（展示+编辑）
│   ├── import_result_dialog.py # 导入结果弹窗
│   ├── progress_dialog.py      # 导入进度弹窗
│   ├── settings_page.py        # 设置页面 (AI配置 + 主题 + 配置迁移)
│   ├── combo_page.py           # 智能凑票页面（参数配置 + 方案表格 + 详情 + 一键报销）
│   ├── stats_page.py           # 统计报表页面 (matplotlib 图表)
│   ├── rule_page.py            # 规则管理页面 (CRUD + 导入导出)
│   ├── ai_learn_dialog.py      # AI 学习对话框 (异步识别 + 规则生成)
│   ├── ai_page.py              # AI 识别页面（学习过程展示）
│   ├── confirm_dialog.py       # 通用确认弹窗
│   └── widgets/
│       ├── __init__.py
│       ├── file_link_label.py  # 可点击超链接控件
│       └── clickable_path.py   # 可点击复制路径控件
├── utils/                      # 工具函数
│   ├── __init__.py
│   ├── file_utils.py           # 文件操作
│   ├── crypto.py               # API Key 加密
│   ├── validators.py           # 数据验证
│   └── theme_manager.py        # 主题管理器 (QSS 加载 + 切换)
├── tests/                      # 自动化测试 (pytest)
│   ├── test_combo_service.py
│   ├── test_combo_comprehensive.py
│   ├── test_combo_closest_strategy.py
│   ├── test_combo_full_validation.py
│   ├── test_combo_real_world.py
│   ├── test_strategy_differences.py
│   └── test_v14_features.py    # v1.4 功能测试 (OCR/备份/CSV/搜索)
├── resources/
│   └── styles/
│       ├── default.qss         # 浅色主题
│       └── dark.qss            # 深色主题
└── docs/
    ├── PRD.md                  # 产品需求文档
    ├── architecture.md         # 系统架构文档（本文件）
    ├── development_guide.md    # 开发指南
    ├── module_design.md        # 模块详细设计
    ├── data_model.md           # 数据模型设计
    ├── ChangeLogs.md           # 变更日志
    └── optimization_plan.md    # 后续优化方案
```

## 3. 核心设计模式

### 3.1 数据库连接 — 单例 + 上下文管理器

```python
class DatabaseConnection:
    _instance = None  # 单例

    @contextmanager
    def transaction(self):
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
```

- SQLite WAL 模式保证并发读取性能
- 事务上下文自动 commit/rollback
- 全局 `db` 实例供所有 DAO 使用

### 3.2 解析器调度 — 工厂模式 + 策略模式

```python
registry = ParserRegistry()
registry.register('.xml', XMLParser())
registry.register('.pdf', PDFParser(rule_service))
registry.register('.ofd', OFDParser())

# 使用时根据文件扩展名自动调度
invoice = registry.parse(file_path)
```

- `ParserRegistry` 维护扩展名到解析器的映射
- 每个解析器实现 `BaseParser` 抽象接口
- `PDFParser` 依赖 `RuleService` 进行规则匹配

### 3.3 异步导入 — QThread + Signal

```python
class ImportWorker(QThread):
    progress = pyqtSignal(int, int, str)    # current, total, filename
    finished_signal = pyqtSignal(object)    # ImportResult

ImportService.import_files_async(paths)  # 启动异步线程
```

- 导入操作在子线程执行，避免 UI 阻塞
- 通过 Signal 实时推送进度到 UI
- 支持取消操作

### 3.4 筛选查询 — 动态 SQL 构建

```python
@dataclass
class FilterCriteria:
    business_type: str | None = None
    invoice_type: str | None = None
    # ...

InvoiceDAO.get_all(filters) → 动态拼接 WHERE 条件
```

### 3.5 UI 编排 — 页面级协调器

```
InvoicePage（协调器）
├── Toolbar → import_file / import_folder / export_excel / clear_db 信号
├── FilterBar → filter_changed 信号
├── SearchBar → search_triggered / reset_triggered 信号
├── InvoiceTable → row_selected 信号
└── DetailPanel → field_updated 信号
```

页面负责创建子组件并连接信号，实现数据流闭环。

## 4. 数据流

### 4.1 发票导入流程

```
用户点击"导入文件"
  → QFileDialog 选择文件
  → ImportService.import_files_async(paths)
  → ImportWorker (QThread)
    → ParserRegistry.parse(path)
      → XMLParser / PDFParser / OFDParser
    → InvoiceDAO.exists_by_number() 去重
    → InvoiceDAO.insert() 入库
    → progress Signal 推送进度
  → import_finished Signal
  → ImportResultDialog 展示结果
  → InvoicePage.refresh() 刷新表格
```

### 4.2 筛选/搜索流程

```
用户操作筛选栏/搜索栏
  → FilterBar.filter_changed / SearchBar.search_triggered
  → InvoicePage._build_filter_criteria()
  → InvoiceService.query(criteria)
  → InvoiceDAO.get_all(filters)  [动态 SQL]
  → InvoiceTable.populate(invoices)
  → 状态栏更新计数
```

### 4.3 详情编辑流程

```
用户点击表格行
  → InvoiceTable.row_selected(id)
  → InvoiceService.get_by_id(id)
  → DetailPanel.show_invoice(invoice)

用户修改可编辑字段
  → DetailPanel.field_updated(id, field, value)
  → InvoiceService.update_field(id, field, value)
  → InvoiceDAO.update_field()
  → InvoicePage.refresh() 刷新表格
```

### 4.4 AI 学习流程

```
导入结果有规则不匹配文件
  → ImportResultDialog 显示 AI 学习按钮
  → 用户点击 → ai_learn_clicked(file_path)
  → InvoicePage._on_ai_learn_requested()
  → AILearnDialog(file_path)
    → [测试连接] → AIService.test_connection()
    → [开始 AI 识别]
      → AIWorker(QThread) → AIService.analyze_invoice()
        → _extract_text_for_ai() (PDF/XML/OFD 文本提取)
        → _call_api() (urllib.request → OpenAI Chat API)
        → _postprocess_invoice_data() (金额校验 + 日期标准化)
      → 填充可编辑表单 → 金额实时校验
    → [导入此发票] → InvoiceDAO.insert(ai_learned=True)
    → [保存为新规则]
      → AIService.learn_format() (AI 建议 extraction_config + match_keywords)
      → QInputDialog 确认规则名称
      → RuleService.save_rule() → RuleManager + RuleDAO
```

## 5. 运行时数据路径

| 数据 | 路径 |
|------|------|
| SQLite 数据库 | `%APPDATA%\ai_fapiao\invoices.db` |
| 解析规则文件 | `%APPDATA%\ai_fapiao\rules\*.json` |
| 应用日志 | `%APPDATA%\ai_fapiao\logs\app.log` |
| 内置规则 | 项目内 `config/builtin_rules/` |

## 6. 依赖关系图

```
main.py
  ├── core.app_config → 初始化目录
  ├── database.schema → 初始化表结构
  └── views.main_window.MainWindow
        ├── views.sidebar
        ├── views.invoice_page
        │     ├── views.toolbar
        │     ├── views.filter_bar
        │     ├── views.search_bar
        │     ├── views.invoice_table
        │     ├── views.detail_panel
        │     ├── views.import_result_dialog
        │     │     └── [ai_learn_clicked] → views.ai_learn_dialog
        │     │                                  ├── services.ai_service
        │     │                                  ├── services.rule_service
        │     │                                  └── database.invoice_dao
        │     ├── views.progress_dialog
        │     ├── services.import_service
        │     │     ├── parsers.parser_registry
        │     │     │     ├── parsers.xml_parser
        │     │     │     ├── parsers.pdf_parser → parsers.text_extractor
        │     │     │     └── parsers.ofd_parser → parsers.xml_parser (委托)
        │     │     ├── services.rule_service
        │     │     │     ├── config.rule_manager
        │     │     │     └── database.rule_dao
        │     │     └── database.invoice_dao
        │     ├── services.invoice_service
        │     └── services.export_service
        ├── views.combo_page → services.combo_service
        ├── views.rule_page → services.rule_service + views.RuleDetailDialog
        └── views.settings_page → services.ai_service
```

## 7. 安全设计

| 安全点 | 实现方案 |
|--------|----------|
| API Key 存储 | Fernet 对称加密，密钥派生自用户名+固定盐值 |
| 数据库完整性 | WAL 模式 + 外键约束 + 事务回滚 |
| 二次确认 | 清空数据库等危险操作弹出 ConfirmDialog |
| 文件安全 | 发票数据仅本地存储，不上传任何服务器 |
| SQL 注入 | 所有查询使用参数化 SQL（`?` 占位符） |
