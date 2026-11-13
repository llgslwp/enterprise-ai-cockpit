"""极简 .env 加载（不依赖 python-dotenv）。

把项目根目录 .env 的 KEY=VALUE 注入 os.environ（已存在的环境变量不覆盖）。
供 agent / knowledge 等模块读取 LLM_API_KEY 等敏感配置，避免硬编码进代码。
"""

import os


def load_env(path: str | None = None) -> None:
    """解析 .env 文件，逐行注入环境变量。"""
    if path is None:
        # app/env.py 的上级目录 = 项目根
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, ".env")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
