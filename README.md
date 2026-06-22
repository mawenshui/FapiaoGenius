# 智票通 (FapiaoGenius)

> AI 智能发票识别管理系统 — 支持 PDF / XML / OFD 格式发票自动识别、智能凑票、规则学习

## 功能特性

- **多格式解析**：支持 PDF、XML、OFD 三种电子发票格式
- **AI 智能学习**：通过 AI 自动生成解析规则，适应不同发票版式
- **智能凑票**：回溯搜索 + 贪心降级算法，支持多种金额模式和挑选策略
- **规则管理**：内置规则 + AI 学习规则，支持导入导出
- **报销管理**：发票状态跟踪、批量设置报销状态
- **Excel 导出**：一键导出筛选结果

## 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.9+ |
| UI | PyQt5 |
| 数据库 | SQLite (WAL) |
| PDF 解析 | pdfplumber + PyMuPDF |
| AI | OpenAI 兼容 API (DeepSeek) |
| 打包 | PyInstaller + WiX |

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动应用
python main.py
```

## 项目结构

```
ai_fapiao/
├── main.py              # 应用入口
├── core/                # 基础设施（配置/常量/日志）
├── models/              # 数据模型（Invoice/ParseRule/AIConfig）
├── database/            # 数据访问层（DAO）
├── parsers/             # 发票解析引擎（PDF/XML/OFD）
├── services/            # 业务逻辑层（导入/导出/AI/凑票）
├── views/               # PyQt5 UI 层
├── config/              # 内置解析规则
├── tests/               # 自动化测试
└── docs/                # 技术文档
```

## 文档

- [系统架构](docs/architecture.md)
- [模块设计](docs/module_design.md)
- [数据模型](docs/data_model.md)
- [开发计划](docs/development_plan.md)
- [变更日志](docs/ChangeLogs.md)
- [后续优化方案](docs/optimization_plan.md)

## 系统要求

- Windows 10 / 11
- Python 3.9+

## License

MIT
