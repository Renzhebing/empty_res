"""LLM 路由器:多供应商选择。"""
from __future__ import annotations

import logging

from .base import BaseLLM

logger = logging.getLogger(__name__)


class LLMRouter(BaseLLM):
    """多供应商路由:维护 text/vision 两个 provider。"""

    def __init__(self, providers: list):
        self._text_provider = None
        self._vision_provider = None

        for p in providers:
            api_key = getattr(p, "api_key", "") if not isinstance(p, dict) else p.get("api_key", "")
            if not api_key:
                continue
            try:
                from .openai_compat import OpenAICompatLLM
                from ..config import LLMProvider

                # 兼容 LLMProvider dataclass 和 dict
                if isinstance(p, LLMProvider):
                    provider = p
                else:
                    provider = LLMProvider(
                        name=p.get("name", "unknown"),
                        base_url=p.get("base_url", ""),
                        api_key=p.get("api_key", ""),
                        model=p.get("model", ""),
                        vision=p.get("vision", False),
                    )
                llm = OpenAICompatLLM(provider)
                if provider.vision and self._vision_provider is None:
                    self._vision_provider = llm
                elif not provider.vision and self._text_provider is None:
                    self._text_provider = llm
            except Exception as e:
                logger.warning("LLM provider %s 初始化失败: %s", getattr(p, "name", "?"), e)

    def has_provider(self) -> bool:
        return self._text_provider is not None or self._vision_provider is not None

    def complete(self, prompt: str) -> str:
        """文本补全:优先 text provider,回退 vision。"""
        if self._text_provider is not None:
            return self._text_provider.complete(prompt)
        if self._vision_provider is not None:
            return self._vision_provider.complete(prompt)
        raise RuntimeError("无可用 LLM provider")

    def complete_with_image(self, prompt: str, image_base64: str, mime: str = "image/png") -> str:
        """带图片补全:用 vision provider。"""
        if self._vision_provider is None:
            raise RuntimeError("无可用 vision provider")
        return self._vision_provider.complete_with_image(prompt, image_base64, mime)


def get_router(config=None) -> LLMRouter:
    """从 config 构建 LLMRouter。"""
    if config is None:
        from ..config import get_config
        config = get_config()
    return LLMRouter(config.llm_providers)
