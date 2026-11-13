"""云端大模型接入层（agent-core 能力保留部分）。

仅保留 LLM 抽象层（OpenAICompatLLM，OpenAI 兼容、首选 DeepSeek）。
操作型编排引擎（engine.py 的意图识别 / 副作用确认 / 写回 / 排产触发）已于
2026-11-03 清除，人机对话改由 LangChain 承载的纯知识库问答（见 modules/knowledge/）。
"""

from .llm import BaseLLM, LLMError, OpenAICompatLLM, get_llm

__all__ = ["BaseLLM", "LLMError", "OpenAICompatLLM", "get_llm"]
