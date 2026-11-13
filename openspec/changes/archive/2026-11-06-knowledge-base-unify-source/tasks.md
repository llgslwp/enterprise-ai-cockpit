# Tasks

- [x] 1. 批量导入 docs 下 13 个文件到知识管理（8 工艺类 + QB_T2508 知识类 + 4 制度类），docs 原文件保留作备份
- [x] 2. `config.py`：新增 `KB_DATA_DIR = data/knowledge`，`KB_DIRS` 标记兼容保留
- [x] 3. `loaders.py`：`DOMAIN_NAMES` 改三域；`load_all` 改为读知识管理（排除 index/、跳过停用、只取当前版本）；`load_md/load_docx/load_pdf/load_excel` 增加 `domain` 参数
- [x] 4. `router.py`：`route_domain` 提示词域枚举四域→三域；docstring 同步
- [x] 5. 验证：main import 正常；load_all 读知识管理 11 文档、域分布正确；停用过滤严格验证通过（11→10→11）
- [x] 6. 在 2 号高配机重建索引（`python -m modules.knowledge.build`），并验证问答
- [x] 7. 业务方验收问答，确认后归档本变更
