"""Excel 读取层（inventory-data-model 能力）。

将六类库存 Excel 文件读入统一结构（InventoryTable）。

实现说明：
- 直接解析 xlsx 的 zip 结构（xl/worksheets/sheetN.xml + xl/sharedStrings.xml），
  绕过 openpyxl 对 WPS 生成文件的样式解析兼容性问题。
- 字段无关：不硬编码任何字段名，按文件实际表头原样读取。
- 原样承接：字段名与单元格值原样保留，不做重命名、合并、类型转换。
"""

import datetime as _dt
import os
import re
import zipfile
from typing import Optional

try:
    from lxml import etree as ET  # lxml 大幅加速 XML 解析（ElementTree 遍历是读文件瓶颈，276ms→~30ms）
except ImportError:
    from xml.etree import ElementTree as ET

from app.data_model.structures import InventoryTable

# xlsx 命名空间
_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
# sheet 元素的 r:id 属性所在命名空间（officeDocument）
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
# workbook.xml.rels 中 Relationship 元素所在命名空间（package）
_PKG_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _q(tag: str) -> str:
    return f"{{{_NS}}}{tag}"


# Excel 内置日期格式 numFmtId（与 openpyxl BUILTIN_FORMATS 精确对齐：
# 仅 14-22 / 45-47。注意 openpyxl 未收录 27-36/50-58/67 等东亚中文日期 id，
# 这些 id 会被 openpyxl 回退为 General、不转日期，这里保持一致）。
_BUILTIN_DATE_FORMATS = {
    14, 15, 16, 17, 18, 19, 20, 21, 22, 45, 46, 47,
}


def _is_date_format_code(code: str) -> bool:
    """判断自定义数字格式码是否为日期格式（含 y/m/d/h/s 指示符）。"""
    if not code:
        return False
    fmt = code.split(";")[0].lower()
    fmt = re.sub(r'"[^"]*"', "", fmt)      # 去引号字面量
    fmt = re.sub(r"\[[^\]]*\]", "", fmt)   # 去方括号段（颜色/条件）
    fmt = re.sub(r"\\.", "", fmt)          # 去转义字符
    fmt = re.sub(r"_[^;]*", "", fmt)       # 去下划线填充
    fmt = re.sub(r"\*[^;]*", "", fmt)      # 去星号填充
    return any(ch in fmt for ch in "ymdhs")


def _load_date_xf_indexes(zf: zipfile.ZipFile) -> set:
    """返回「日期格式」的 cellXfs 索引集合（单元格 s 属性即 cellXfs 索引）。

    识别两类：内置日期 numFmtId（14-22/27-36/45-47/50-58/67 等），
    以及自定义 numFmt 中 formatCode 含日期指示符的。
    """
    try:
        root = ET.fromstring(zf.read("xl/styles.xml"))
    except KeyError:
        return set()
    custom = {}
    for nf in root.iter(_q("numFmt")):
        nid = nf.get("numFmtId")
        code = nf.get("formatCode")
        if nid and code:
            custom[int(nid)] = code
    cellxfs = root.find(_q("cellXfs"))
    if cellxfs is None:
        return set()
    date_xf = set()
    for idx, xf in enumerate(cellxfs.iter(_q("xf"))):
        nid = xf.get("numFmtId")
        if nid is None:
            continue
        nid_i = int(nid)
        if nid_i in _BUILTIN_DATE_FORMATS:
            date_xf.add(idx)
        elif nid_i in custom and _is_date_format_code(custom[nid_i]):
            date_xf.add(idx)
    return date_xf


def _excel_serial_to_datetime(serial):
    """Excel 日期序列号 → datetime（1900 日期系统，含 1900-02-29 假闰日）。"""
    base = _dt.datetime(1899, 12, 30) if serial >= 60 else _dt.datetime(1899, 12, 31)
    return base + _dt.timedelta(days=serial)


def _parse_cell_ref(ref: str):
    """解析单元格引用如 'B3' 返回 (行号, 列号)，行号列号均为1起。"""
    m = re.match(r"([A-Z]+)(\d+)", ref)
    if not m:
        return None, None
    letters, digits = m.groups()
    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch) - 64)
    return int(digits), col


def _load_shared_strings(zf: zipfile.ZipFile) -> list:
    """读取共享字符串表，返回字符串列表（按索引）。"""
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    strings = []
    for si in root.findall(f"{{{_NS}}}si"):
        text = "".join(t.text or "" for t in si.iter(f"{{{_NS}}}t"))
        strings.append(text)
    return strings


def _cell_value(c, shared_strings: list, date_xf: set = frozenset()):
    """解析单元格 c 的值为 Python 对象（日期格式单元格转 datetime）。"""
    t = c.get("t")
    if t == "inlineStr":
        # 内联字符串（openpyxl 生成的文件用此形式）：值在 <is><t> 内，无 <v>
        is_el = c.find(f"{{{_NS}}}is")
        if is_el is not None:
            return "".join(node.text or "" for node in is_el.iter(f"{{{_NS}}}t"))
        return None
    v = c.find(f"{{{_NS}}}v")
    if v is None or v.text is None:
        return None
    raw = v.text
    if t == "s":
        idx = int(raw)
        return shared_strings[idx] if idx < len(shared_strings) else raw
    if t == "b":
        return raw == "1"
    if t == "str":
        return raw
    try:
        if "." in raw or "e" in raw.lower():
            val = float(raw)
        else:
            val = int(raw)
    except ValueError:
        return raw
    # 日期格式单元格 → datetime（与 openpyxl 行为一致）
    s = c.get("s")
    if s is not None and int(s) in date_xf:
        return _excel_serial_to_datetime(val)
    return val


def _iter_sheet_rows(zf: zipfile.ZipFile, sheet_xml_path: str, shared_strings=None, date_xf=None):
    """迭代一个工作表的所有行，每行 yield (行号, {列号(1起): 值})。

    shared_strings / date_xf 可预加载传入（多 sheet 时只解析一次，避免重复解压），
    缺省时才自行加载。
    """
    root = ET.fromstring(zf.read(sheet_xml_path))
    if shared_strings is None:
        shared_strings = _load_shared_strings(zf)
    if date_xf is None:
        date_xf = _load_date_xf_indexes(zf)
    for row in root.iter(f"{{{_NS}}}row"):
        row_num = int(row.get("r", 0))
        row_data = {}
        for c in row.findall(f"{{{_NS}}}c"):
            ref = c.get("r")
            if not ref:
                continue
            _, col = _parse_cell_ref(ref)
            if col is None:
                continue
            row_data[col] = _cell_value(c, shared_strings, date_xf)
        yield row_num, row_data


def _list_sheets(zf: zipfile.ZipFile) -> list:
    """返回 [(sheet名, sheet_xml路径)] 列表，按 workbook 中声明顺序。"""
    wb_root = ET.fromstring(zf.read("xl/workbook.xml"))
    rels_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_by_id = {}
    for rel in rels_root.findall(f"{{{_PKG_NS}}}Relationship"):
        rid = rel.get("Id")
        target = rel.get("Target")
        if rid and target:
            rel_by_id[rid] = target
    result = []
    for s in wb_root.iter(f"{{{_NS}}}sheet"):
        name = s.get("name")
        rid = s.get(f"{{{_REL_NS}}}id")
        target = rel_by_id.get(rid)
        if target:
            # 兼容两种 Target 写法：
            #  - WPS/腾讯文档导出：target 形如 "worksheets/sheet1.xml"（相对 xl/）
            #  - openpyxl 生成：target 形如 "/xl/worksheets/sheet1.xml"（已含 xl/ 前缀）
            t = target.lstrip("/")
            path = t if t.startswith("xl/") else "xl/" + t
        else:
            path = ""
        result.append((name, path))
    return result


def _resolve_sheet_path(zf: zipfile.ZipFile, sheet_name: Optional[str]) -> str:
    """根据工作表名定位 sheet xml 路径；未指定或未找到则取第一个 sheet。"""
    sheets = _list_sheets(zf)
    if not sheet_name:
        for name, path in sheets:
            if path:
                return path
        return "xl/worksheets/sheet1.xml"
    for name, path in sheets:
        if name == sheet_name:
            return path
    # 未找到指定名，回退到第一个可用 sheet
    for name, path in sheets:
        if path:
            return path
    return "xl/worksheets/sheet1.xml"


def read_excel_table(
    file_path: str,
    category: str,
    sheet_name: Optional[str] = None,
    header_row: int = 1,
) -> InventoryTable:
    """读取一个 xlsx 文件为 InventoryTable（不依赖 openpyxl）。

    file_path:  xlsx 文件路径
    category:   数据类别（如「毛坯库」）
    sheet_name: 工作表名；None 时取第一个工作表
    header_row: 表头所在行（1 起），默认为第 1 行

    返回 InventoryTable，columns 为原始表头，rows 为逐行原始值。
    """
    zf = zipfile.ZipFile(file_path)
    sheet_path = _resolve_sheet_path(zf, sheet_name)
    shared_strings = _load_shared_strings(zf)
    date_xf = _load_date_xf_indexes(zf)

    columns = []
    data_rows = []
    for row_num, row_data in _iter_sheet_rows(zf, sheet_path, shared_strings, date_xf):
        if row_num == header_row:
            max_col = max(row_data.keys()) if row_data else 0
            columns = [
                "" if row_data.get(i) is None else str(row_data.get(i))
                for i in range(1, max_col + 1)
            ]
            continue
        if row_num < header_row:
            continue
        if not row_data:
            continue
        record = {}
        for idx, col_name in enumerate(columns, start=1):
            if col_name == "":
                continue
            record[col_name] = row_data.get(idx)
        if any(v is not None for v in record.values()):
            data_rows.append(record)

    zf.close()
    return InventoryTable(
        category=category,
        columns=columns,
        rows=data_rows,
        source=file_path,
    )


def read_all_sheets(file_path: str) -> list:
    """一次性读取 xlsx 全部工作表，返回 [(sheet原始名, [(行号, {列号:值})...])...]，按 workbook 声明顺序。

    与 read_excel_table 同源（zip 直读、不依赖 openpyxl），但保留「按列号」的原始网格，
    供需要多 sheet、多表头行、新旧版本分列的复杂读取场景复用（如质量抽检表）。
    每行是一个 dict，key 为 1 起的列号，value 为解析后的原始值（空单元格不出现）。
    """
    zf = zipfile.ZipFile(file_path)
    try:
        shared_strings = _load_shared_strings(zf)
        date_xf = _load_date_xf_indexes(zf)
        result = []
        for name, path in _list_sheets(zf):
            if not path:
                continue
            rows = [(rn, row_data) for rn, row_data in _iter_sheet_rows(zf, path, shared_strings, date_xf)]
            result.append((name, rows))
        return result
    finally:
        zf.close()


# 进程级缓存：按 (路径, mtime, size) 缓存 read_all_sheets 结果。
# 多个接口（如质量看板 inspection/spc/8d）共享同一源文件时，只解压解析一次；
# 文件 mtime/size 变化（用户重新上传/排产覆盖）自动失效。后端单进程常驻下有效。
_sheets_cache: dict = {}


def read_all_sheets_cached(file_path: str) -> list:
    """带进程级缓存的 read_all_sheets（文件未变则复用上次解析结果）。"""
    try:
        mtime = os.path.getmtime(file_path)
        size = os.path.getsize(file_path)
    except OSError:
        return read_all_sheets(file_path)
    key = (file_path, mtime, size)
    cached = _sheets_cache.get(key)
    if cached is not None:
        return cached
    result = read_all_sheets(file_path)
    _sheets_cache[key] = result
    return result
