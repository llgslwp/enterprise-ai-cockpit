"""知识库配置常量与 .env 加载。

用 __file__ 定位项目根，不依赖盘符 / 当前工作目录，换电脑复制即用。
"""

import contextlib
import os

from app.env import load_env

# 加载 .env（保证 LLM_API_KEY 等敏感配置进入环境变量；已存在的不覆盖）
load_env()

# 国内镜像：未显式配置时默认走 hf-mirror，加速模型下载（BGE-M3 / bge-reranker）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


@contextlib.contextmanager
def no_proxy():
    """临时移除环境代理后执行，模型下载走直连。

    WorkBuddy 环境会注入 http_proxy/https_proxy（127.0.0.1:15335），该代理对
    hf-mirror 返回 502，导致模型下载失败；直连 hf-mirror 可达，故下载时临时绕过代理。
    """
    keys = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY")
    saved = {k: os.environ.pop(k, None) for k in keys}
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v

# 项目根目录 = modules/knowledge/config.py 的上三级
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 知识库数据源目录 = 知识管理文件库（文件按「入库类型」分文件夹、版本化存储）。
# 注：RAG 索引的数据源已从 docs/ 切换到知识管理（单一数据源），docs/ 仅作源备份、不再参与检索。
KB_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "knowledge")

# 兼容保留：旧数据源目录（docs），已被 KB_DATA_DIR 取代，不再参与 RAG 加载。
KB_DIRS = [
    os.path.join(PROJECT_ROOT, "docs", "产品工艺"),
    os.path.join(PROJECT_ROOT, "docs", "公司制度"),
]
KB_DIR = KB_DIRS[0]

# 索引与向量存储目录（numpy/JSON 纯文件落地）
# 索引是「文件库的派生产物」（可从文件随时重建），故放 data/knowledge/index 子目录，
# 与文件库同属一个知识库根目录，避免「文件在 A、索引在 B」两个平级目录的分离坑。
# 注意：将来 RAG 加载文件时须排除 index/ 子目录（它只存索引，不含原始文件）。
INDEX_DIR = os.path.join(PROJECT_ROOT, "data", "knowledge", "index")

# 本地模型名（首次运行自动从 HuggingFace 下载，国内走 hf-mirror 镜像）
EMBED_MODEL = "BAAI/bge-m3"
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"

# 模型精度：fp32 两个模型合计约 4.5GB，7.8GB 内存的机器会 OOM；
# 改用 fp16 半精度，内存减半（约 2.2GB），CPU 上已实测可正常推理。
MODEL_TORCH_DTYPE = "float16"

# 云端大模型（DeepSeek，OpenAI 兼容；由 .env 覆盖）
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")

# 检索参数
# 注：2026-11-03 在 4 核 CPU 上实测 rerank 精排极慢（15条×256 仍 125s），
# 已定位为「模型规模 × CPU 算力」瓶颈，非参数可解。当前保留原始最优参数，
# 待部署高配机（GPU/大内存）后启用；届时若用 GPU，需重装 CUDA 版 torch。
TOP_K_RECALL = 30    # 双路召回各取 top-k（RRF 融合后送入 rerank 的候选数）
TOP_K_RERANK = 6     # Rerank 后保留的切片数，送入生成

# Rerank 精排参数：限制序列长度 + 分批预测，压低 cross-encoder 的 attention 峰值内存
# 2026-11-04 新电脑（RTX 3050）上放宽到 1024 追求更优精度（GPU 显存/算力充足，原 512 为旧机 CPU 防 OOM 而降）
RERANK_MAX_LENGTH = 1024
RERANK_BATCH_SIZE = 8

# Embedding 参数：BGE-M3 默认 8192 上下文，attention 峰值（batch×seq×seq）会撑爆小内存；
# 本库切片最长约 1200 字，限制 1536 + 缩小批次，峰值内存大幅下降且不截断切片。
EMBED_MAX_LENGTH = 1536
EMBED_BATCH_SIZE = 8
