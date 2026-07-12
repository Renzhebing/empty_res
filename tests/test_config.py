"""测试配置加载。"""
from __future__ import annotations

from pathlib import Path

import yaml

from fapiao_helper import config as config_mod


def _write_config(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")


def test_load_default_values(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config_mod.paths, "PROJECT_ROOT", tmp_path)
    config_mod.reset_config()
    cfg = config_mod.load_config()
    assert cfg.port == 5000
    assert cfg.classify_threshold == 0.3


def test_load_user_config(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config_mod.paths, "PROJECT_ROOT", tmp_path)
    _write_config(tmp_path / "config.yaml", {"server": {"port": 8080}, "parser": {"classify_threshold": 0.5}})
    config_mod.reset_config()
    cfg = config_mod.load_config()
    assert cfg.port == 8080
    assert cfg.classify_threshold == 0.5


def test_llm_providers_filter(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config_mod.paths, "PROJECT_ROOT", tmp_path)
    _write_config(tmp_path / "config.yaml", {"llm": {"providers": [
        {"name": "p1", "base_url": "http://x", "api_key": "sk-real", "model": "m1"},
        {"name": "p2", "base_url": "http://y", "api_key": "", "model": "m2"},
    ]}})
    config_mod.reset_config()
    cfg = config_mod.load_config()
    assert len(cfg.llm_providers) == 1
    assert cfg.llm_providers[0].name == "p1"


def test_paths_resolved(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config_mod.paths, "PROJECT_ROOT", tmp_path)
    _write_config(tmp_path / "config.yaml", {"paths": {"db": "data/my.db"}})
    config_mod.reset_config()
    cfg = config_mod.load_config()
    assert cfg.db_path.is_absolute()
    assert cfg.db_path.name == "my.db"


def test_ensure_dirs(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config_mod.paths, "PROJECT_ROOT", tmp_path)
    config_mod.reset_config()
    cfg = config_mod.load_config()
    cfg.ensure_dirs()
    assert cfg.inbox.exists()
    assert cfg.library.exists()
