"""配置加载:读取 config.yaml,缺失时从 config.default.yaml 复制并提示用户。"""
from __future__ import annotations

import copy
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import paths

# 默认值,与 config.default.yaml 对齐
_DEFAULTS: dict[str, Any] = {
    "server": {"host": "127.0.0.1", "port": 5000},
    "paths": {
        "inbox": "invoices/inbox",
        "library": "invoices/library",
        "exports": "invoices/exports",
        "db": "data/fapiao.db",
        "logs": "data/logs",
        "models": "data/models",
    },
    "projects": [{"name": "默认项目", "note": "未分类发票归入此项目"}],
    "ocr": {"lang": "ch", "use_angle_cls": True, "det_model_dir": "", "rec_model_dir": ""},
    "llm": {"providers": []},
    "parser": {"classify_threshold": 0.3, "confidence_min": 0.5},
}


@dataclass
class LLMProvider:
    name: str
    base_url: str
    api_key: str
    model: str
    vision: bool = False


@dataclass
class Config:
    raw: dict[str, Any] = field(default_factory=dict)
    _resolved_paths: dict[str, Path] = field(default_factory=dict)

    @property
    def host(self) -> str:
        return str(self.raw.get("server", {}).get("host", "127.0.0.1"))

    @property
    def port(self) -> int:
        return int(self.raw.get("server", {}).get("port", 5000))

    @property
    def inbox(self) -> Path:
        return self._path("inbox")

    @property
    def library(self) -> Path:
        return self._path("library")

    @property
    def exports(self) -> Path:
        return self._path("exports")

    @property
    def db_path(self) -> Path:
        return self._path("db")

    @property
    def logs_dir(self) -> Path:
        return self._path("logs")

    @property
    def models_dir(self) -> Path:
        return self._path("models")

    @property
    def projects(self) -> list[dict[str, Any]]:
        return list(self.raw.get("projects", []))

    @property
    def ocr_settings(self) -> dict[str, Any]:
        return dict(self.raw.get("ocr", {}))

    @property
    def llm_providers(self) -> list[LLMProvider]:
        providers = self.raw.get("llm", {}).get("providers", []) or []
        result: list[LLMProvider] = []
        for p in providers:
            api_key = str(p.get("api_key", "")).strip()
            if not api_key:
                continue
            result.append(
                LLMProvider(
                    name=str(p.get("name", "unknown")),
                    base_url=str(p.get("base_url", "")),
                    api_key=api_key,
                    model=str(p.get("model", "")),
                    vision=bool(p.get("vision", False)),
                )
            )
        return result

    @property
    def classify_threshold(self) -> float:
        return float(self.raw.get("parser", {}).get("classify_threshold", 0.3))

    @property
    def confidence_min(self) -> float:
        return float(self.raw.get("parser", {}).get("confidence_min", 0.5))

    def _path(self, key: str) -> Path:
        if key not in self._resolved_paths:
            raw = str(self.raw.get("paths", {}).get(key, _DEFAULTS["paths"][key]))
            self._resolved_paths[key] = paths.resolve(raw)
        return self._resolved_paths[key]

    def ensure_dirs(self) -> None:
        """确保所有运行所需目录存在。"""
        for key in ("inbox", "library", "exports", "logs", "models"):
            paths.ensure_dir(self._path(key))
        paths.ensure_dir(self.db_path.parent)


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并:override 覆盖 base。"""
    result = copy.deepcopy(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


def load_config(config_path: Path | str | None = None) -> Config:
    """加载配置。优先级: config.yaml > config.default.yaml > 内置默认值。"""
    if config_path is None:
        config_path = paths.PROJECT_ROOT / "config.yaml"
    config_path = Path(config_path)

    default_path = paths.PROJECT_ROOT / "config.default.yaml"

    raw = copy.deepcopy(_DEFAULTS)

    if default_path.exists():
        with open(default_path, "r", encoding="utf-8") as f:
            default_raw = yaml.safe_load(f) or {}
        raw = _deep_merge(raw, default_raw)

    if not config_path.exists():
        # config.yaml 不存在时静默使用 default(便于测试)
        pass
    else:
        with open(config_path, "r", encoding="utf-8") as f:
            user_raw = yaml.safe_load(f) or {}
        raw = _deep_merge(raw, user_raw)

    cfg = Config(raw=raw)
    return cfg


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """重置单例(测试用)。"""
    global _config
    _config = None
