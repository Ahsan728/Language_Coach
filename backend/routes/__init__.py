from backend.routes.api import register_api_routes
from backend.routes.mobile_api import register_mobile_api_routes
from backend.routes.web import register_web_routes


__all__ = ['register_api_routes', 'register_mobile_api_routes', 'register_web_routes']
