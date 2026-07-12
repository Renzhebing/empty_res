"""OCR 引擎:懒加载 PaddleOCR。"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class OCREngine:
    """PaddleOCR 封装,懒加载。"""

    def __init__(
        self,
        lang: str = "ch",
        use_angle_cls: bool = True,
        det_model_dir: str = "",
        rec_model_dir: str = "",
    ):
        self.lang = lang
        self.use_angle_cls = use_angle_cls
        self.det_model_dir = det_model_dir
        self.rec_model_dir = rec_model_dir
        self._engine: Any = None
        self.available = False
        self._initialized = False

    def _init_engine(self) -> None:
        """懒加载初始化 PaddleOCR。"""
        if self._initialized:
            return
        self._initialized = True
        try:
            from paddleocr import PaddleOCR  # 懒加载

            kwargs: dict[str, Any] = {
                "use_angle_cls": self.use_angle_cls,
                "lang": self.lang,
            }
            if self.det_model_dir:
                kwargs["det_model_dir"] = self.det_model_dir
            if self.rec_model_dir:
                kwargs["rec_model_dir"] = self.rec_model_dir
            self._engine = PaddleOCR(**kwargs)
            self.available = True
            logger.info("PaddleOCR 初始化成功")
        except Exception as e:
            logger.error("PaddleOCR 初始化失败: %s", e)
            self.available = False

    def recognize(self, image_path: Path | str) -> tuple[list[tuple], float]:
        """识别图片,返回 (结果列表, 平均置信度)。

        结果列表每项为 (box, text, conf)。
        """
        if not self._initialized:
            self._init_engine()
        if not self.available:
            return [], 0.0
        try:
            results = self._engine.ocr(str(image_path), cls=self.use_angle_cls)
            all_items: list[tuple] = []
            confs: list[float] = []
            # PaddleOCR 返回 [[box, (text, conf)], ...]
            for page in results or []:
                if page is None:
                    continue
                for line in page:
                    if line is None:
                        continue
                    box = line[0]
                    text, conf = line[1]
                    all_items.append((box, text, conf))
                    confs.append(float(conf))
            avg_conf = sum(confs) / len(confs) if confs else 0.0
            return all_items, avg_conf
        except Exception as e:
            logger.error("OCR 识别失败: %s", e)
            return [], 0.0


# 模块级单例
_engine_singleton: OCREngine | None = None
_engine_lock = threading.Lock()


def get_engine(config=None) -> OCREngine:
    """获取 OCR 引擎单例(线程安全)。"""
    global _engine_singleton
    if _engine_singleton is not None:
        return _engine_singleton
    with _engine_lock:
        if _engine_singleton is not None:
            return _engine_singleton
        if config is None:
            from ..config import get_config
            config = get_config()
        settings = config.ocr_settings
        _engine_singleton = OCREngine(
            lang=str(settings.get("lang", "ch")),
            use_angle_cls=bool(settings.get("use_angle_cls", True)),
            det_model_dir=str(settings.get("det_model_dir", "")),
            rec_model_dir=str(settings.get("rec_model_dir", "")),
        )
        return _engine_singleton
