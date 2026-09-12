from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.cadastros import cadastros_bp
from app.routes.operacoes import operacoes_bp
from app.routes.relatorios import relatorios_bp
from app.routes.whatsapp import whatsapp_bp
from app.routes.api import api_bp
from app.routes.admin import admin_bp

ALL_BLUEPRINTS = [
    auth_bp,
    dashboard_bp,
    cadastros_bp,
    operacoes_bp,
    relatorios_bp,
    whatsapp_bp,
    api_bp,
    admin_bp
]