"""程序入口。"""
from __future__ import annotations

from .config import get_config
from .db import init_db, sync_projects
from .app import create_app


def main() -> None:
    cfg = get_config()
    cfg.ensure_dirs()
    init_db(cfg.db_path)
    sync_projects(cfg.db_path, cfg.projects)
    app = create_app(cfg)
    app.run(host=cfg.host, port=cfg.port, debug=False)


if __name__ == "__main__":
    main()
