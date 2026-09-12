from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Adicionar coluna receber_emergenciais
    try:
        db.session.execute(text("ALTER TABLE whatsapp_contatos ADD COLUMN receber_emergenciais BOOLEAN DEFAULT 1"))
        print("✅ Coluna receber_emergenciais adicionada")
    except Exception as e:
        print(f"Coluna receber_emergenciais já existe: {e}")

    # Adicionar coluna horario_envio
    try:
        db.session.execute(text("ALTER TABLE whatsapp_contatos ADD COLUMN horario_envio VARCHAR(5) DEFAULT '07:00'"))
        print("✅ Coluna horario_envio adicionada")
    except Exception as e:
        print(f"Coluna horario_envio já existe: {e}")

    db.session.commit()
    print("✅ Migração concluída!")