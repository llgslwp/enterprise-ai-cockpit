# 企业 AI 驾驶舱

> 一个「制造业 × Agent」的智能运营平台：用 LangChain 多工具 Agent、RAG 知识库、OpenSpec 规格驱动，把一家管钳制造厂的生产、库存、质量数据，变成可对话、可追溯、可验证的智能决策中枢。

本仓库是一个**个人工程能力展示项目**，完整覆盖 AI 落地应用工程师的核心技能栈：Agent 工具编排、RAG 全链路、语义理解、GPU 性能优化、规格驱动开发、工程化防线的落地。

---

## 一、项目解决了什么

| 维度 | 说明 |
|:---|:---|
| **场景** | 传统制造厂（管钳/自由钳，年产 50 万把）的生产运营 |
| **痛点** | 库存靠微信传文件、数据散落多个 Excel、ERP 无 BOM 无计划管理 |
| **方案** | 多角色驾驶舱 + 全局智能助手（Agent），自然语言查询库存/缺口/产量 |
| **技术难点** | 语义路由、多轮改写、Rerank 精排、副作用确认、工具调用可追溯 |

---

## 二、核心能力矩阵

| 能力 | 说明 | 状态 |
|:---|:---|:---|
| **智能辅助决策（Agent）** | LangChain `create_agent` + 只读工具（库存/缺口/产量），自然语言对话 + 工具调用轨迹可展开对账 | ✅ |
| **企业知识库（RAG）** | 解析→清洗→语义分块→BGE-M3 向量化→向量+BM25 双索引→混合检索+RRF→Rerank→语义路由→Query 改写→生成+引用溯源 | ✅ |
| **知识管理** | 文件上传/版本管理/停用启用/回滚，上传后自动重建索引 | ✅ |
| **生产/库存/质量模块** | 半成品排产、库存汇总、质量看板（控制图/四预警/8D） | ✅ |
| **多角色体系** | 保管员/生产副总/总经理/质检员（架构就位，本期单账号过渡） | 预留 |
| **汇总看板** | 总经理决策视图 | 待数据指标定稿 |

---

## 三、技术栈

| 层 | 选型 |
|:---|:---|
| 前端 | Vue 3 + Vite + Vue Router + Axios + ECharts |
| 后端 | FastAPI + Uvicorn（REST JSON + Session Cookie） |
| Agent | LangChain 1.x `create_agent`（CompiledStateGraph）+ OpenAI 兼容 LLM（DeepSeek） |
| RAG | BGE-M3（Embedding）+ bge-reranker-v2-m3（Rerank）+ numpy/JSON 向量存储 + BM25 双路 + RRF |
| 数据 | 无数据库，纯文件（Excel 读写，zipfile + lxml 解析） |
| 规范 | OpenSpec（规格驱动开发） |

---

## 四、架构

```
┌─────────────────────────────────────────────────┐
│              前端 (Vue 3 + Vite SPA)              │
│  登录 / 上传 / 计划 / 看板 / 质量 / 知识库 / 智能决策 │
└───────────────────────┬─────────────────────────┘
                        │ REST JSON (/api/*)
                        │ Session + Cookie
┌───────────────────────▼─────────────────────────┐
│                 后端 (FastAPI)                     │
│  auth ── files ── agent ── production/inventory/quality ── knowledge │
│  ┌──────────────────────────────────────────┐   │
│  │ LangChain Agent（create_agent）            │   │
│  │ 知识库问答 + 只读工具调用（tool use）       │   │
│  │ 检索 → Rerank → 生成 → 引用溯源 → 流式输出  │   │
│  └──────────────┬───────────────────────────┘   │
│                 │ LLM 抽象接入层 (OpenAI 兼容)     │
│                 ▼ DeepSeek / 通义 / 智谱          │
└───────────────────────────────────────────────────┘
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
      数据文件（Excel）        模型索引（numpy/JSON）
```

**关键设计**：
- **只读边界 + 写操作拦截**：Agent 工具全部只读，任何会改数据的操作走人工确认通道。
- **四道防线**：数据层复用确定性实现（0 差异验收）→ 动作层仅只读 → 留痕层返回 tool_calls 轨迹 → 验收层 golden set。
- **检索兜底**：离题判定改为「先检索、有证据就放行」，杜绝关键词白名单滞后导致的内容误杀。

---

## 五、RAG 全链路（核心展示点）

```
原始文件（docx/md/pdf/xlsx）
   │ 解析（python-docx / pypdf / lxml）
   ▼
清洗 + 语义分块（按标题层级）
   │ BGE-M3 向量化（GPU, fp16）
   ▼
向量索引 + BM25 索引（双索引）
   │ 混合检索（稠密 + BM25 + RRF 融合）
   ▼
Rerank（bge-reranker-v2-m3, cross-encoder）
   │ 语义路由（工艺类/制度类/知识类）+ Query 改写
   ▼
生成（DeepSeek，流式 SSE）+ 引用溯源 [1][2]
```

---

## 六、快速开始

> ⚠️ **数据说明**：本仓库仅开源代码与文档，**不含企业业务数据**（生产台账、工艺文件、制度文档均已从仓库隔离，见 `.gitignore`）。运行前需自备数据或使用脱敏示例。

### 环境要求

- Python 3.13+
- Node.js 20+
- （可选）NVIDIA GPU + CUDA 版 PyTorch，用于加速 BGE-M3 向量化与 Rerank

### 后端

```bash
# 1. 安装依赖（torch 需单独装，见 requirements.txt 顶部说明）
pip install -r requirements.txt

# 2. 配置大模型（写入 .env，参考 .env 结构）
#    LLM_API_KEY=your_deepseek_key
#    LLM_BASE_URL=https://api.deepseek.com

# 3. 启动
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

- 接口文档（Swagger UI）：http://127.0.0.1:8000/docs
- 默认账号：`admin` / `admin123`（生产环境务必通过环境变量 `COCKPIT_ADMIN_USER` / `COCKPIT_ADMIN_PASS` 覆盖）

### 前端

```bash
cd web
npm install
npm run dev   # http://127.0.0.1:5173（已配置代理到后端 8000）
```

### 知识库建索引

```bash
python -m modules.knowledge.build   # 读 data/knowledge/ 文件，落 data/knowledge/index/
```

---

## 七、演示路径（自然语言操作）

1. 登录 → 进入驾驶舱
2. 「智能辅助决策」页输入：`这个月加力 95 有多少库存？`
3. Agent 识别意图 → 调用 `query_stock` 工具 → 返回结构化数据 + 工具调用轨迹（可展开对账）
4. 「知识库」页输入工艺问题 → 检索 → Rerank → 流式生成 + 引用溯源

---

## 八、目录结构

```
企业AI驾驶舱/
├── main.py                    # FastAPI 入口
├── app/                       # 底座：auth / deps / data_model（Excel 读取层）
├── modules/                   # 业务模块
│   ├── agent/                 #   Agent（tools / agent / router / spec_aliases）
│   ├── knowledge/             #   知识库 RAG 全链路（14 个模块）
│   ├── production/            #   生产管理（排产 / 回填 / 公式求值）
│   ├── inventory/             #   库存管理
│   ├── quality/               #   质量管理（控制图 / 四预警 / 8D）
│   └── files/                 #   文件上传
├── web/                       # Vue 3 前端（src/views 各页面）
├── openspec/                  # OpenSpec 规格驱动工件（specs + changes/archive）
├── docs/                      # 开发过程记录 / 交互设计 / 方法论
└── data/                      # 数据目录（业务数据已隔离，仅保留占位）
```

---

## 九、工程亮点（面试可展开）

1. **Agent 工具编排**：LangChain 1.x `create_agent`（CompiledStateGraph 循环），规避已废弃的 AgentExecutor/initialize_agent。
2. **四道防线**：数据 0 差异复用、只读工具边界、tool_calls 留痕、golden set 验收。
3. **RAG 全链路自建**：不依赖托管向量库，BGE-M3 + BM25 双路 + RRF + Rerank 全本地实现。
4. **GPU 性能优化**：fp16 半精度 + 分批预测 + RERANK_MAX_LENGTH 调优，rerank 从 CPU 125 秒降到 GPU 秒级（约 50 倍）。
5. **规格驱动开发**：全程 OpenSpec（proposal → spec delta → tasks → archive），21 个变更可追溯。
6. **检索兜底设计**：用「检索证据」替代「关键词白名单」判离题，根治内容误杀。

---

## 十、开发方法与过程

本项目采用 **OpenSpec 规格驱动开发**（Spec-Driven Development），完整过程见：
- `docs/开发过程记录/开发过程记录-技术版.md`
- `docs/开发过程记录/开发过程记录-非技术版.md`
- `openspec/changes/archive/`（21 个变更的完整规格演化史）

---

## 十一、License

MIT（待定）
