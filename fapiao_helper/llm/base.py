"""LLM 基类。"""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """LLM 抽象基类。"""

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """文本补全。"""
        ...

    @abstractmethod
    def complete_with_image(self, prompt: str, image_base64: str, mime: str = "image/png") -> str:
        """带图片的多模态补全。"""
        ...

    def has_provider(self) -> bool:
        """是否有可用 provider。"""
        return True
