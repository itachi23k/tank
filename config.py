import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'chave-secreta-padrao-lcm-2026')
    # Se não houver URL de PostgreSQL no .env, usa SQLite local para testes rápidos
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///frota_local.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False


     # WhatsApp API Oficial (Meta)
    WHATSAPP_TOKEN = os.environ.get('WHATSAPP_TOKEN', '')
    WHATSAPP_PHONE_ID = os.environ.get('WHATSAPP_PHONE_ID', '')
