"""Flask 应用工厂:注册蓝图、注入配置。"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, render_template

from ..config import get_config
from .routes import api_invoices, api_jobs, api_export, api_projects, debug

# web 包目录,模板/静态资源都挂在它下面
_WEB_DIR = Path(__file__).resolve().parent


def create_app(config=None) -> Flask:
    """创建 Flask 应用。

    Args:
        config: Config 实例,为 None 时从 get_config() 取。

    Returns:
        配置完成的 Flask app。
    """
    if config is None:
        config = get_config()

    app = Flask(
        __name__,
        template_folder=str(_WEB_DIR / "templates"),
        static_folder=str(_WEB_DIR / "static"),
    )

    # 注入配置供蓝图读取
    app.config["DB_PATH"] = config.db_path
    app.config["CONFIG"] = config

    # 注册蓝图
    app.register_blueprint(api_invoices.bp)
    app.register_blueprint(api_jobs.bp)
    app.register_blueprint(api_export.bp)
    app.register_blueprint(api_projects.bp)
    app.register_blueprint(debug.bp)

    # 首页
    @app.route("/")
    def index():  # type: ignore[no-untyped-def]
        return render_template("index.html")

    return app
