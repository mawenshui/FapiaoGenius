# AI 智能发票识别管理系统 - 开发指南

## 1. 环境要求

| 项目 | 版本要求 |
|------|----------|
| Python | >= 3.9 |
| 操作系统 | Windows 10 / 11 |
| pip | >= 22.0 |

## 2. 快速开始

### 2.1 克隆项目

```bash
git clone <repo_url>
cd ai_fapiao
```

### 2.2 安装依赖

```bash
# 安装运行时依赖
pip install -r requirements.txt

# 或者使用开发模式安装（含开发依赖）
pip install -e ".[dev]"
```

**依赖清单：**

| 包名 | 版本 | 用途 |
|------|------|------|
| PyQt5 | >= 5.15.0 | UI 框架 |
| pdfplumber | >= 0.9.0 | PDF 文本提取 |
| PyMuPDF | >= 1.23.0 | PDF 备用解析 |
| openpyxl | >= 3.1.0 | Excel 导出 |
| cryptography | >= 41.0.0 | API Key 加密 |

### 2.3 启动应用

```bash
python main.py
```

首次启动会自动完成以下初始化：
1. 创建数据目录 `%APPDATA%\ai_fapiao\`
2. 创建 SQLite 数据库并建表
3. 复制内置解析规则到用户规则目录
4. 创建日志目录

## 3. 项目结构说明

```
ai_fapiao/
├── main.py           # 应用入口，负责 QApplication 初始化和高 DPI 设置
├── core/             # 基础设施层，无业务依赖
├── models/           # 纯数据模型（dataclass），无框架依赖
├── database/         # 数据访问层（DAO），封装 SQL 操作
├── parsers/          # 发票解析引擎，各格式解析器
├── services/         # 业务逻辑层，编排各层调用
├── config/           # 配置管理 + 内置规则文件
├── views/            # PyQt5 UI 层
├── utils/            # 通用工具函数
└── resources/        # 静态资源（样式表等）
```

**层间依赖规则：**
- `views/` → `services/` → `database/` / `parsers/` → `models/` → `core/`
- 上层可以调用下层，**下层不得调用上层**
- `models/` 和 `core/` 是无依赖的基础层

## 4. 开发规范

### 4.1 代码风格

- 遵循 PEP 8 编码规范
- 类名使用 `PascalCase`
- 方法名和变量名使用 `snake_case`
- 常量使用 `UPPER_SNAKE_CASE`
- 所有模块、类、方法必须有 docstring

### 4.2 新增发票格式解析器

1. 在 `parsers/` 下创建新文件，如 `xxx_parser.py`
2. 继承 `BaseParser`，实现 `parse()` 和 `can_parse()` 方法
3. 在 `parsers/parser_registry.py` 的 `create_registry()` 中注册

```python
# parsers/xxx_parser.py
class XXXParser(BaseParser):
    def can_parse(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() == '.xxx'
    
    def parse(self, file_path: str) -> Invoice:
        # 实现解析逻辑
        invoice = Invoice()
        # ...
        return invoice

# parsers/parser_registry.py → create_registry()
registry.register('.xxx', XXXParser())
```

### 4.3 新增业务类型/发票类型

编辑 `core/constants.py` 中的枚举类：

```python
class BusinessType(str, Enum):
    NEW_TYPE = "新类型名称"  # 添加新枚举值
```

若需要在筛选栏中展示，需同时更新 `views/filter_bar.py` 中对应的下拉框初始化。

### 4.4 新增 UI 页面

1. 在 `views/` 下创建页面文件，如 `new_page.py`
2. 继承 `QWidget`，实现 `_init_ui()` 方法
3. 在 `views/main_window.py` 的 `_init_ui()` 中添加到 `_stack`
4. 在 `views/sidebar.py` 中添加导航项

```python
# views/main_window.py
self._new_page = NewPage()
self._stack.addWidget(self._new_page)  # 索引 N
```

### 4.5 数据库表结构变更

1. 修改 `database/schema.py` 中的 `SCHEMA_SQL`
2. 添加迁移逻辑到 `migrate()` 函数
3. 同步更新对应的 `models/` 数据类和 `database/*_dao.py`

## 5. 内置规则开发

### 5.1 规则文件结构

规则文件为 JSON 格式，放置在 `config/builtin_rules/` 目录下：

```json
{
  "id": "唯一标识（UUID）",
  "rule_name": "规则名称",
  "file_format": "pdf",
  "match_keywords": ["关键词1", "关键词2"],
  "extraction_config": {
    "字段名": {
      "type": "regex",
      "pattern": "正则表达式（需捕获组）"
    }
  },
  "required_fields": ["必填字段列表"],
  "created_at": "ISO 8601 时间",
  "updated_at": "ISO 8601 时间",
  "is_builtin": true
}
```

### 5.2 支持的提取字段

| 字段名 | 说明 | 是否必填 |
|--------|------|----------|
| invoice_number | 发票号码 | 是 |
| invoice_date | 开票日期 | 是 |
| buyer_name | 购买方名称 | 否 |
| seller_name | 销售方名称 | 否 |
| amount_without_tax | 不含税金额 | 是 |
| tax_amount | 税额 | 是 |
| total_amount | 价税合计 | 是 |
| business_type | 业务类型 | 否（可自动推断） |
| invoice_type | 发票类型 | 否（可自动推断） |

## 6. 测试

### 6.1 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行指定模块测试
pytest tests/test_xml_parser.py

# 带覆盖率报告
pytest tests/ --cov=. --cov-report=html
```

### 6.2 手动验证清单

| 验证项 | 操作步骤 |
|--------|----------|
| 应用启动 | `python main.py`，窗口正常显示 |
| 导入 XML | 文件 → 导入文件 → 选择 XML → 查看导入结果 |
| 导入 PDF | 文件 → 导入文件夹 → 选择含 PDF 的文件夹 |
| 导入 OFD | 文件 → 导入文件 → 选择 OFD → 查看解析结果 |
| 拖拽导入 | 拖拽文件/文件夹到窗口 → 蓝色虚线反馈 → 自动导入 |
| 表格操作 | 排序、多选、筛选、搜索、重置 |
| 详情编辑 | 点击行 → 修改业务类型/报销状态/备注 → 自动保存 |
| Excel 导出 | 工具栏 → 导出 Excel → 验证内容 |
| 清空数据库 | 工具栏 → 清空数据库 → 二次确认 → 数据清空 |
| AI 连接测试 | 设置页 → 配置 API URL/Key/模型 → 测试连接 |
| AI 学习识别 | 导入失败 → 点击“AI 学习” → 开始识别 → 编辑结果 → 导入 |
| AI 规则生成 | AI 学习对话框 → “保存为新规则” → 确认名称 → 规则保存 |
| 规则管理 | 导航栏 → 规则管理 → 查看/编辑/删除/导入/导出 |
| 快捷键 | Ctrl+O / Ctrl+Shift+O / Ctrl+E / Delete |

## 7. 构建与打包

### 7.1 PyInstaller 打包（规划中）

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=resources/icons/app.ico main.py
```

### 7.2 运行时数据

应用运行后会在用户目录下创建数据：

```
%APPDATA%\ai_fapiao\
├── invoices.db           # SQLite 数据库
├── rules/                # 解析规则文件
│   ├── xml_e_invoice.json
│   └── pdf_vat_normal.json
└── logs/
    └── app.log           # 应用日志
```

## 8. 常见问题

### Q: 导入 PDF 时提示"无法提取文本"
A: PDF 可能是扫描件（纯图片），当前 MVP 仅支持文本型 PDF。后续版本将通过 AI 学习功能支持 OCR 识别。

### Q: 数据库文件在哪里？
A: `%APPDATA%\ai_fapiao\invoices.db`，可直接用 SQLite 客户端查看。

### Q: 如何添加自定义解析规则？
A: 有三种方式：
1. **AI 学习**：导入失败后点击“AI 学习”按钮，AI 自动识别并生成规则
2. **规则管理页面**：导航栏 → 规则管理 → “导入规则”按钮 → 选择 JSON 文件
3. **手动放置**：将 JSON 规则文件放入 `%APPDATA%\ai_fapiao\rules\` 目录，重启应用即可加载

### Q: AI 学习需要什么配置？
A: 在“设置”页面配置 AI API 信息：
- **API 地址**：OpenAI 兼容 API 的端点 URL（如 `https://api.deepseek.com/v1`）
- **API Key**：用户的 API 密钥
- **模型**：如 `deepseek-chat`、`gpt-4-turbo` 等
- 配置完成后可点击“测试连接”验证

### Q: OFD 文件导入失败怎么办？
A: OFD 解析采用双策略：先尝试 XML 委托解析，再降级为正则匹配。如果仍然失败，可以使用 AI 学习功能识别该 OFD 格式并生成解析规则，下次导入同类 OFD 时将自动使用新规则。

### Q: 如何重置应用数据？
A: 删除 `%APPDATA%\ai_fapiao\` 目录，重启应用会自动初始化。
