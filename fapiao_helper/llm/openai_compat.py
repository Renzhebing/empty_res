"""OpenAI 兼容实现。"""
from __future__ import annotations

import logging

from .base import BaseLLM

logger = logging.getLogger(__name__)


class OpenAICompatLLM(BaseLLM):
    """OpenAI 兼容 LLM 实现。"""

    def __init__(self, provider):
        self.provider = provider
        try:
            from openai import OpenAI  # 懒加载
        except ImportError as e:
            logger.error("openai 库未安装: %s", e)
            raise
        self._client = OpenAI(base_url=provider.base_url, api_key=provider.api_key)

    def complete(self, prompt: str) -> str:
        """文本补全。"""
        resp = self._client.chat.completions.create(
            model=self.provider.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""

    def complete_with_image(self, prompt: str, image_base64: str, mime: str = "image/png") -> str:
        """带图片的多模态补全。"""
        if not self.provider.vision:
            raise NotImplementedError("此 provider 不支持 vision")
        data_uri = f"data:{mime};base64,{image_base64}"
        resp = self._client.chat.completions.create(
            model=self.provider.model,
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ]}
            ],
        )
        return resp.choices[0].message.content or ""
