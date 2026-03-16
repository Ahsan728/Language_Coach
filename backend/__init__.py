from flask import Flask

from backend.routes import register_api_routes, register_mobile_api_routes, register_web_routes
from backend.services import build_path_config, configure_app, init_db


def create_app(config_overrides=None):
    path_config = build_path_config(config_overrides)
    app = Flask(
        __name__,
        template_folder=path_config['TEMPLATE_DIR'],
        static_folder=path_config['STATIC_DIR'],
    )

    if config_overrides:
        app.config.update(config_overrides)

    configure_app(app)

    with app.app_context():
        init_db()

    register_web_routes(app)
    register_api_routes(app)
    register_mobile_api_routes(app)
    return app
