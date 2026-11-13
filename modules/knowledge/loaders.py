"""文档解析加载器（knowledge-base 能力之一）。

统一产出 LangChain Document 对象，每个文档带元数据：
- source:   文件绝对路径
- domain:   知识域（工艺类 / 制度类 / 知识类，与知识管理入库类型一致）——语义路由子库划分依据
- doc_type: 文件类型（md / word / pdf / excel）
- title:    文档标题（文件名去扩展名）

数据源 = 知识管理文件库（data/knowledge/），只加载「启用」文件的「当前版本」；
一期解析 MD + Word 文字版；PDF / Excel 预留接口（扫描 PDF 的 OCR 留二期）。
"""

from __future__ import annotations

import json
import os

from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document

from .config import KB_DATA_DIR

# 知识域全集（三域，与知识管理的「入库类型」一一对应，作为语义路由的子库划分依据）
DOMAIN_NAMES = ["工艺类", "制度类", "知识类"]


def _base_meta(path: str, doc_type: str, domain: str = "工艺类") -> dict:
    return {
        "source": os.path.abspath(path),
        "domain": domain,
        "doc_type": doc_type,
        "title": os.path.splitext(os.path.basename(path))[0],
    }


def load_md(path: str, domain: str = "工艺类") -> list[Document]:
    """读取 Markdown，保留原始标题结构（供语义分块）。"""
    loader = TextLoader(path, encoding="utf-8")
    docs = loader.load()
    meta = _base_meta(path, "md", domain)
    for d in docs:
        d.metadata.update(meta)
    return docs


def load_docx(path: str, domain: str = "工艺类") -> list[Document]:
    """读取 Word 文字版，识别标题层级，转成 markdown 结构（供 MarkdownHeaderTextSplitter 语义分块）。

    说明：不用 langchain 的 Docx2txtLoader——它丢标题层级，无法做语义分块；
    用 python-docx 按段落样式识别标题，同时抽取表格内容。
    """
    import docx

    doc = docx.Document(path)
    lines: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        # 容错：部分 docx（WPS/某些导出工具生成）段落 style 可能为 None，视为正文
        style = (para.style.name if para.style is not None else "") or ""
        style = style.lower()
        if style == "title" or "heading 1" in style:
            lines.append(f"# {text}")
        elif "heading 2" in style:
            lines.append(f"## {text}")
        elif "heading 3" in style:
            lines.append(f"### {text}")
        elif "heading" in style:
            lines.append(f"#### {text}")
        else:
            lines.append(text)
    # 抽取表格（按行列拼接，保留结构语义）
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            lines.append(" | ".join(cells))

    content = "\n\n".join(lines).strip()
    if not content:
        return []
    return [Document(page_content=content, metadata=_base_meta(path, "word", domain))]


def load_pdf(path: str, domain: str = "工艺类") -> list[Document]:
    """读取 PDF 文字层；扫描版（无文字层）抛 ValueError，提示 OCR 留二期。"""
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    content = "\n\n".join(pages).strip()
    if not content:
        raise ValueError(f"扫描版 PDF（无文字层），需 OCR 转文字（留二期）：{os.path.basename(path)}")
    return [Document(page_content=content, metadata=_base_meta(path, "pdf", domain))]


def load_excel(path: str, domain: str = "工艺类") -> list[Document]:
    """读取 Excel，按工作表逐行提取，保留行列语义（预留接口，一期暂无素材）。"""
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    docs: list[Document] = []
    for ws in wb.worksheets:
        lines = [f"# 工作表：{ws.title}"]
        for row in ws.iter_rows(values_only=True):
            cells = ["" if c is None else str(c).strip() for c in row]
            if any(cells):
                lines.append(" | ".join(cells))
        content = "\n".join(lines).strip()
        if content:
            meta = _base_meta(path, "excel", domain)
            meta["sheet"] = ws.title
            docs.append(Document(page_content=content, metadata=meta))
    return docs


def _iter_current_files():
    """遍历知识管理里所有「启用」文件的「当前版本」磁盘路径，yield (path, 入库类型)。

    - 排除 index/ 子目录（它只存 RAG 索引，不含原始文件）
    - 跳过 status=disabled 的停用文件
    - 只取 current_version 对应版本文件（历史版本不进索引）
    """
    meta_path = os.path.join(KB_DATA_DIR, "meta.json")
    if not os.path.isfile(meta_path):
        return
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except (json.JSONDecodeError, OSError):
        return
    for rec in meta.values():
        if rec.get("status") == "disabled":
            continue
        ftype = rec.get("type", "工艺类")
        fid = rec.get("id", "")
        cur_ver = rec.get("current_version")
        target = None
        for v in rec.get("versions", []):
            if v.get("version") == cur_ver:
                target = v.get("file_path")
                break
        if not target:
            continue
        full = os.path.join(KB_DATA_DIR, ftype, fid, target)
        if os.path.isfile(full):
            yield full, ftype


def load_all(directories: list[str] | None = None, verbose: bool = True) -> list[Document]:
    """加载知识管理里全部启用文件的「当前版本」文档；扫描版 PDF 打印提示并跳过。

    数据源 = 知识管理文件库（data/knowledge/），按「入库类型」设知识域（三域）；
    directories 参数保留仅为兼容旧调用，不再生效（数据源统一由知识管理 meta.json 决定）。
    """
    docs: list[Document] = []
    for path, ftype in _iter_current_files():
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".md":
                docs.extend(load_md(path, ftype))
            elif ext == ".docx":
                docs.extend(load_docx(path, ftype))
            elif ext == ".pdf":
                try:
                    docs.extend(load_pdf(path, ftype))
                except ValueError as e:
                    if verbose:
                        print(f"[跳过] {e}")
            elif ext in (".xlsx", ".xls"):
                docs.extend(load_excel(path, ftype))
        except Exception as e:  # noqa: BLE001
            if verbose:
                print(f"[加载失败] {os.path.basename(path)}: {e}")
    return docs
