"""云端大模型抽象接入层（决策 13）。

定义统一的 LLM 接口，隔离厂商差异；首个实现用 OpenAI 兼容格式，
换 base_url + api_key 即可切换厂商（DeepSeek / 通义千问 / 智谱 GLM 等）。
"""

import os
from typing import Optional

import httpx


class LLMError(Exception):
    """大模型调用异常。"""


class BaseLLM:
    """统一 LLM 抽象接口。"""

    def chat(self, messages: list[dict], temperature: float = 0.2) -> str:
        raise NotImplementedError


class OpenAICompatLLM(BaseLLM):
    """OpenAI 兼容接口实现（覆盖 DeepSeek、通义、智谱等国内厂商）。"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")).rstrip("/")
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", "deepseek-chat")

    def chat(self, messages: list[dict], temperature: float = 0.2) -> str:
        if not self.api_key:
            raise LLMError("未配置 LLM_API_KEY，无法调用云端大模型")
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as e:
            raise LLMError(f"大模型调用失败 HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"大模型调用异常: {e}")


def get_llm() -> BaseLLM:
    """返回默认 LLM 实例（OpenAI 兼容，首选 DeepSeek）。"""
    return OpenAICompatLLM()
