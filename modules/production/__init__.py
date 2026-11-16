"""生产管理模块。

本包用 __getattr__ 懒加载 router，避免「导入任一子模块」（如 formula_eval / mapping /
gap_stat）时连带加载 router → fastapi 等重依赖。这样 CI 单测环境只装 pytest + openpyxl
也能 import 纯函数子模块，无需 fastapi；运行时 main.py 的 `production.router` 仍可用。
"""


def __getattr__(name: str):
    if name == "router":
        from modules.production.router import router
        return router
    raise AttributeError(f"module 'modules.production' has no attribute '{name}'")

