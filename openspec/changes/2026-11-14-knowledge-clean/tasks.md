# 文本清洗环节补建 — 任务清单

## 1. 实现 cleaner.py
- [ ] 1.1 `clean_text(text, doc_type)`：通用清洗（控制字符清理 / 换行统一 / 空格与制表符统一 / 空行折叠 / 首尾空白 / 重复段落去重）
- [ ] 1.2 `clean_documents(docs)`：分块前批量清洗，返回新 Document 列表
- [ ] 1.3 `filter_chunks(chunks, min_len=30)`：分块后过滤过短切片 + title_path/内容指纹去重

## 2. 集成 build 链路
- [ ] 2.1 `build.py` 在 `load_all()` 后、`chunk_all()` 前调用 `clean_documents()`
- [ ] 2.2 `build.py` 在 `chunk_all()` 后、`build_index()` 前调用 `filter_chunks()`

## 3. 验收
- [ ] 3.1 清洗前后各跑一次 `python -m modules.knowledge.build`，对比切片数 / 平均字数 / 最小字数——碎屑（8 字级）应消失
- [ ] 3.2 跑 `run_eval()` 的 7 个 QA，Recall@k / MRR 不得下降
- [ ] 3.3 确认未回写原文件、未违反数据源三铁律
