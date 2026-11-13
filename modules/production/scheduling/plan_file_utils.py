"""排产公共工具库（production-planning 能力，任务 3）。

承载半成品排产链路共用的底层能力：
- WPS 坏样式修复（<fill/> 空节点 → 合法 patternFill）
- 数量列动态定位（按表头关键词，不硬编码列号）
- 规格归一（去 φ/″/"/D/S 前缀，提取数字段，支持斜杠组合规格）
- 文件定位（data/raw 下按文件名日期标签取最新）

规则来源：example/03-全量重跑-开发说明文档.md（权威基准）。
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import zipfile
from datetime import datetime
from typing import List, Optional, Tuple

# 项目根（相对本文件定位，保证任意 cwd 下可运行，换电脑/换启动目录不失效）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 数据区：6 份源文件与 V2.0 基底所在目录
DATA_DIR = os.path.join(_PROJECT_ROOT, "data", "raw")
OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "data", "output")

# 产品表顺序（V2.0 六张 sheet：5 产品表 + 1 配件-颜色）
PRODUCT_SHEETS = ("加力", "美式", "内管钳", "钻杆钳", "套管钳")
COLOR_SHEET_NAME = "配件-颜色"

# 产品线名 → V2.0 sheet 内块头 A 列产品名
PRODUCT_NAMES = {
    "加力": "加力管钳",
    "美式": "美式重型/含钛",
    "内管钳": "内管钳",
    "钻杆钳": "钻杆钳",
    "套管钳": "套管钳",
}


# ---------------------------------------------------------------------------
# WPS 坏样式修复
# ---------------------------------------------------------------------------

def repair_xlsx_styles(src: str, dst: Optional[str] = None) -> Tuple[str, int]:
    """修复 WPS 生成的 xlsx 坏样式（<fill/> 空节点）。

    根因：ERP/WPS 导出的 xlsx 在 xl/styles.xml 有空 <fill/> 节点，
    openpyxl 抛 TypeError: expected <class 'openpyxl.styles.fills.Fill'>。
    修法：正则把空 fill 节点替换为合法的 patternFill（只改样式，不动数据）。

    返回 (输出路径, 替换次数)。
    """
    if dst is None:
        # 默认写到系统临时目录（不污染 data/raw），文件名用源文件名区分、稳定可复用
        base = os.path.basename(src)
        name, ext = os.path.splitext(base)
        dst = os.path.join(tempfile.gettempdir(), f"{name}_wps修复{ext}")
    cnt = 0
    with zipfile.ZipFile(src) as zin:
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.namelist():
                data = zin.read(item)
                if item == "xl/styles.xml":
                    txt = data.decode("utf-8")
                    txt, n = re.subn(
                        r"<fill\s*/>|<fill>\s*</fill>",
                        '<fill><patternFill patternType="none"/></fill>',
                        txt,
                    )
                    cnt += n
                    data = txt.encode("utf-8")
                zout.writestr(item, data)
    return dst, cnt


def ensure_readable(src: str, quiet: bool = False) -> str:
    """确保 xlsx 可被 openpyxl 读取；坏样式自动修复，仍失败则 SystemExit。

    修复件写入系统临时目录（`<temp>/<源文件名>_wps修复.xlsx`），
    不再在 data/raw 下残留 `_修复` 副本。返回可读路径（正常时即 src 本身）。
    """
    import openpyxl
    try:
        openpyxl.load_workbook(src)
        return src
    except TypeError:
        dst, cnt = repair_xlsx_styles(src)
        if not quiet:
            print(f"[repair] {os.path.basename(src)} 修复坏样式 {cnt} 处 -> 临时文件")
        try:
            openpyxl.load_workbook(dst)
            return dst
        except Exception as e:
            print(f"[ERROR] 修复后仍无法读取 {src}: {e}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 无法读取 {src}: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# 数量列 / 表头列动态定位
# ---------------------------------------------------------------------------

def find_qty_col(ws, *keywords: str) -> Tuple[int, str]:
    """在表头行（第 1 行）动态定位数量列。

    优先匹配「现有存量」，其次「数量」；再依次尝试调用方传入的关键词。
    找不到则 SystemExit（禁止硬编码列号）。
    返回 (列号 1-based, 表头文本)。
    """
    import openpyxl
    keys = list(keywords) or ["现有存量", "数量"]
    for kw in keys:
        for c in range(1, ws.max_column + 1):
            v = ws.cell(row=1, column=c).value
            if v is not None and str(v).strip() == kw:
                return c, str(v).strip()
    print(f"[ERROR] 数量列定位失败：表头中无 {keys}", file=sys.stderr)
    sys.exit(1)


def find_col_by_header(ws, *keywords: str, header_row: int = 1) -> Tuple[int, str]:
    """按关键词（任一命中）在表头行找列。返回 (列号 1-based, 表头文本)。"""
    for c in range(1, ws.max_column + 1):
        v = ws.cell(row=header_row, column=c).value
        if v is None:
            continue
        s = str(v).strip()
        for kw in keywords:
            if kw in s:
                return c, s
    return -1, ""


# ---------------------------------------------------------------------------
# 规格归一
# ---------------------------------------------------------------------------

def normalize_spec(spec: str) -> str:
    """归一规格：去 φ/″/"/D/S 前缀与尾随管道，提取数字段。

    支持斜杠组合规格（108/127）与连字符（71-75）。
    例：'重型108D' -> '108'；'钻杆φ54-56' -> '54-56'；'内管钳S43' -> '43'。
    """
    if spec is None:
        return ""
    s = str(spec).strip().rstrip(" |").strip()
    # 去 φ / ″ / " / 英寸 等干扰符
    s = s.replace("φ", "").replace("″", "").replace('"', "").replace("英寸", "")
    # 提取数字段（含连字符/斜杠）
    m = re.search(r"(\d+(?:[-/]\d+)?)", s)
    return m.group(1) if m else ""


def spec_matches_group(row_b_spec: str, group_spec: str) -> bool:
    """判断数据行 B 列规格是否属于某规格块（跨块同名同规格不串块）。"""
    return normalize_spec(str(row_b_spec)) == normalize_spec(str(group_spec))


# ---------------------------------------------------------------------------
# 文件定位
# ---------------------------------------------------------------------------

def _glob_safe(pattern: str) -> List[str]:
    """glob 并排除 Excel 锁文件（~$ 开头）。"""
    import glob
    return [p for p in glob.glob(pattern) if not os.path.basename(p).startswith("~$")]


def _date_key(path: str) -> str:
    """从文件名抽日期键（YYYYMMDD / YYMMDD），抽不到回落 mtime。"""
    name = os.path.basename(path)
    m = re.search(r"(\d{8})", name) or re.search(r"(\d{6})", name)
    if m:
        return m.group(1)
    return datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y%m%d")


def resolve_latest(pattern: str, exclude: Tuple[str, ...] = ()) -> Optional[str]:
    """按文件名日期键取最新文件；排除含排除关键字的派生件。"""
    candidates = []
    for p in _glob_safe(pattern):
        base = os.path.basename(p)
        if any(kw in base for kw in exclude):
            continue
        candidates.append(p)
    if not candidates:
        return None
    return max(candidates, key=_date_key)


def resolve_source(kind: str, exclude: Tuple[str, ...] = ()) -> Optional[str]:
    """按类别定位 data/raw 下最新源文件。

    kind: 文件名关键字（如 '毛坯库'、'车间在产品'、'半成品库'、'外协'、'在产品装配'）。
    """
    return resolve_latest(os.path.join(DATA_DIR, f"*{kind}*.xlsx"), exclude=exclude)


# ---------------------------------------------------------------------------
# 文件占用错误翻译（用户 2026-11-03 需求：把底层 PermissionError 通俗化）
# ---------------------------------------------------------------------------

def is_file_locked_error(exc: BaseException) -> bool:
    """判断异常是否因「目标文件被 Excel/WPS 等程序占用」导致。"""
    # Windows 常见：PermissionError [Errno 13] 或 OSError [WinError 32]（另一个程序正在使用此文件）
    if isinstance(exc, PermissionError):
        return True
    if isinstance(exc, OSError):
        errno = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
        # WinError 32 = 另一个程序正在使用此文件；Errno 13 = 权限拒绝
        if errno in (13, 32):
            return True
        # 兜底：错误信息含「被另一进程使用 / 正由另一进程使用 / being used by another process」
        msg = str(exc).lower()
        if "another process" in msg or "正在使用" in msg or "正由另一" in msg:
            return True
    return False


def friendly_file_error(exc: BaseException, file_path: Optional[str] = None) -> str:
    """把「文件被占用」类异常翻译成通俗中文提示。

    例：「文件 data/raw/半成品生产计划V2.0.xlsx 正被 Excel/WPS 打开或编辑，暂时无法写入。
    请先关闭该文件后再试。」
    """
    name = os.path.basename(file_path) if file_path else ""
    target = name or "相关文件"
    if is_file_locked_error(exc):
        return (
            f"「{target}」正被 Excel/WPS 打开或编辑，暂时无法写入。\n"
            f"请先关闭该文件（及其所在程序），再重新执行操作。"
        )
    # 非占用类异常，原样返回（附文件名的通用提示）
    return f"文件「{target}」操作失败：{exc}"


def ensure_writable(file_path: str) -> None:
    """写入前预检：若文件正被 Excel/WPS 等程序占用，抛 RuntimeError（通俗提示）。

    用 Windows 独占写锁探测：能拿到写锁说明没被独占打开；拿不到则说明被占用。
    提前探测可避免 openpyxl 内部的 ZipFile 析构噪音，并更快失败。
    """
    if not os.path.exists(file_path):
        return  # 文件不存在（新建），无需探测
    import msvcrt
    handle = None
    try:
        handle = os.open(file_path, os.O_RDWR)
        msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)
        msvcrt.locking(handle, msvcrt.LK_UNLCK, 1)
    except (PermissionError, OSError) as e:
        raise RuntimeError(friendly_file_error(e, file_path)) from e
    finally:
        if handle is not None:
            try:
                os.close(handle)
            except OSError:
                pass
