import os
from datetime import datetime
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # --- INICIALIZAÇÃO DE EXTENSÕES ---
    db.init_app(app)
    login_manager.init_app(app)
    
    # ⚠️ IMPORTANTE: Atualizado para o blueprint 'auth'
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, faça login para acessar o sistema.'
    login_manager.login_message_category = 'warning'

    # --- REGISTRO DOS BLUEPRINTS MODULARES ---
    from app.routes import ALL_BLUEPRINTS
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    @app.context_processor
    def inject_globals():
        from app.models import Obra, Equipamento, Fornecedor, Abastecimento
        
        db_candidates = [
            os.path.join(app.instance_path, 'frota_local.db'),
            os.path.join(app.root_path, '..', 'instance', 'frota_local.db'),
            os.path.join(app.instance_path, 'frota.db')
        ]
        db_size = 0.0
        for cand in db_candidates:
            if os.path.exists(cand):
                db_size = round(os.path.getsize(cand) / 1024, 2)
                break

        try:
            todas_obras_nav = Obra.query.filter_by(ativa=True).order_by(Obra.nome).all()
        except Exception:
            todas_obras_nav = []

        try:
            total_obras = Obra.query.count()
            total_equipamentos = Equipamento.query.count()
            total_abastecimentos = Abastecimento.query.count()
        except Exception:
            total_obras = 0
            total_equipamentos = 0
            total_abastecimentos = 0

        return {
            'now': datetime.utcnow(),
            'todas_obras_nav': todas_obras_nav,
            'db_size': db_size,
            'total_obras': total_obras,
            'total_equipamentos': total_equipamentos,
            'total_abastecimentos': total_abastecimentos
        }

    # --- IMPORTAÇÃO DOS MODELOS E CRIAÇÃO DAS TABELAS ---
    with app.app_context():
        from app.models import (
            Usuario, Equipamento, Fornecedor, Abastecimento,
            EntradaInsumo, Transferencia, Obra, WhatsAppContato, WhatsAppLog
        )
        
        # Cria todas as tabelas
        db.create_all()
        
        # --- CRIAÇÃO DA OBRA PADRÃO ---
        if not Obra.query.first():
            obra_padrao = Obra(
                codigo='OB-001',
                nome='OBRA PADRÃO',
                local='A DEFINIR',
                responsavel='ADMINISTRADOR',
                ativa=True,
                data_inicio=datetime.utcnow().date()
            )
            db.session.add(obra_padrao)
            db.session.commit()
            print(">>> Obra padrão criada com sucesso!")
        
        # --- CRIAÇÃO AUTOMÁTICA DO ADMIN PADRÃO ---
        admin_email = os.environ.get('ADMIN_EMAIL', 'cassiojr1658@gmail.com')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'itachi23k')
        
        if not Usuario.query.filter_by(email=admin_email).first():
            admin = Usuario(
                nome='Administrador',
                email=admin_email,
                nivel_acesso='administrador',
                ativo=True,
                acesso_global=True,
                obra_padrao_id=1
            )
            admin.set_senha(admin_password)
            db.session.add(admin)
            db.session.commit()
            print(">>> Usuário Admin padrão criado com sucesso!")
        
        # --- ATUALIZAR DADOS EXISTENTES (MIGRAÇÕES SQL DE COMPATIBILIDADE) ---
        from sqlalchemy import text
        try:
            db.session.execute(text("ALTER TABLE fornecedores ADD COLUMN categoria_tanque VARCHAR(30) DEFAULT 'Tanque'"))
        except Exception:
            pass
        try:
            db.session.execute(text("ALTER TABLE fornecedores ADD COLUMN tipo_combustivel VARCHAR(50) DEFAULT 'DIESEL S10'"))
        except Exception:
            pass
        try:
            db.session.execute(text("ALTER TABLE abastecimentos ADD COLUMN frente_servico VARCHAR(100)"))
        except Exception:
            pass

        db.session.execute(text("UPDATE fornecedores SET obra_id = 1 WHERE obra_id IS NULL"))
        db.session.execute(text("UPDATE fornecedores SET categoria_tanque = 'Tanque' WHERE categoria_tanque IS NULL OR categoria_tanque = ''"))
        db.session.execute(text("UPDATE fornecedores SET tipo_combustivel = 'DIESEL S10' WHERE tipo_combustivel IS NULL OR tipo_combustivel = ''"))
        db.session.execute(text("UPDATE abastecimentos SET obra_id = 1 WHERE obra_id IS NULL"))
        db.session.execute(text("UPDATE entradas_insumos SET obra_id = 1 WHERE obra_id IS NULL"))
        db.session.execute(text("UPDATE transferencias SET obra_id = 1 WHERE obra_id IS NULL"))
        db.session.execute(text("UPDATE usuarios SET acesso_global = 1 WHERE nivel_acesso = 'administrador'"))
        db.session.commit()
        print(">>> Dados existentes vinculados à obra padrão e novos campos de fornecedor inicializados!")

    # --- INICIAR AGENDADOR WHATSAPP ---
    # Evita iniciar duas vezes quando o Flask está em modo debug
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        try:
            from app.services.agendador import AgendadorWhatsApp
            agendador = AgendadorWhatsApp(app)
            agendador.iniciar()
            print(">>> Agendador WhatsApp iniciado com sucesso!")
        except Exception as e:
            print(f">>> ERRO ao iniciar agendador: {str(e)}")

    return app