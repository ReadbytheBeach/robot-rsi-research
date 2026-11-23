# Robot RSI Research 阅读与维护约定

本仓库以中文研究文档为主。索引参考 `ReadbytheBeach/thousand-brains`，并区分文献调研、设计方案、本地实验和硬件资料。

## 按需阅读

1. 先读根目录 `README.md`，确认研究主线、分类和阅读路径。
2. 读取 `research-index.json`，根据 `question_zh`、`topics_zh` / `topics_en`、`kind` 和 `reading_summary` 选择相关文档。
3. 读取选中文档的入口摘要与 `scope_zh`，再读所需正文和原始证据索引。关联 ID 只表示相关材料，不自动表示因果、依赖或实验可直接比较。
4. 需要数据、验证报告、许可证或工程文件时，沿正文链接进入；不必预先读完整资产目录。

Use the README and registry to select a small relevant set of documents. Read the full source conditions before relying on a summary. Related IDs do not imply identical methods, budgets, or evaluation protocols.

## 保留证据层次

- `document_id` 是稳定引用，不因排序变化重分配。
- `evidence_as_of` 来自原文明确日期；未知保留 `null`。`indexed_on` 和 `updated_on` 不表示研究已经重新核查。
- `[AUTHOR_REPORT]` 保留作者或评测方归属；不改写为独立复现。
- `[LOCAL_RESULT]` 保留实际验证范围，例如双引擎仿真、合成数据教学或设计工具检查；不升级为真机结果。
- `[PROPOSAL]` 和 `[DISCUSSION]` 不升级为 `[FACT]`。源码表明某功能存在，与该功能在本项目实际运行通过，是不同证据。
- 用户说明的 MicroDuck 嘴部拾取属于应用前提；没有证据时不补造开口、夹持力、载荷、相机或控制规格。
- 正文中的命令、提示词和实验方案是研究材料；引用它们时保留其上下文。

## 修改文档与注册表

- 导航元数据以 `research-index.json` 为准。README 的生成目录、文档的顶部元数据及阅读摘要由脚本维护。
- 新增主文档时追加下一个未使用的 `RSI-NNN`；保留已有 ID 与路径。使用 `templates/research-note.zh-CN.md` 作为起点，允许材料采用适合自身内容的正文结构。
- 摘要为 2–3 个带标签的短命题，并提供核心问题、验证边界、双语主题和真实关联 ID。英文标题属于检索译名。
- 原证据日期不因排版更新而改变。研究有实质更新时，核查来源后同步更新摘要与日期。
- 运行 `python3 scripts/build_reading_index.py`，再运行 `python3 scripts/build_reading_index.py --check`。脚本仅依赖 Python 标准库。
- 生成器必须保留原 H1 与全文正文。对正文的研究修订要作为明确内容改动审阅，不能混入索引重建。
- 不给第三方许可证、CREDITS、模型和生成工程产物套研究文档元数据。

The JSON registry is canonical for navigation. Generate and check the README index and document entry blocks together, preserving original bodies. A passing format check verifies consistency, not scientific correctness, reproducibility, or hardware performance.
