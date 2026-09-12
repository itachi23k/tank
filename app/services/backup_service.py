"""
Serviço de backup, restauração e manutenção de integridade do banco.
"""
import json
import csv
from io import StringIO
from datetime import datetime, date
from flask import Response
from app import db
from app.models import (
    Usuario, Equipamento, Fornecedor, Abastecimento,
    EntradaInsumo, Transferencia, Obra
)


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


class BackupService:

    @staticmethod
    def serialize_model(obj):
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

    @classmethod
    def gerar_backup_json(cls):
        """Exporta todas as entidades de dados (omitindo senhas de usuários)."""
        data = {
            'obras': [cls.serialize_model(o) for o in Obra.query.all()],
            'equipamentos': [cls.serialize_model(e) for e in Equipamento.query.all()],
            'fornecedores': [cls.serialize_model(f) for f in Fornecedor.query.all()],
            'abastecimentos': [cls.serialize_model(a) for a in Abastecimento.query.all()],
            'entradas': [cls.serialize_model(e) for e in EntradaInsumo.query.all()],
            'transferencias': [cls.serialize_model(t) for t in Transferencia.query.all()],
        }
        return json.dumps(data, indent=2, ensure_ascii=False, cls=CustomJSONEncoder)

    @classmethod
    def restaurar_backup(cls, file_stream, mode, user_id):
        """Restaura registros mantendo a integridade referencial das chaves estrangeiras."""
        data = json.load(file_stream)

        if mode == 'overwrite':
            db.session.query(Transferencia).delete()
            db.session.query(Abastecimento).delete()
            db.session.query(EntradaInsumo).delete()
            db.session.query(Fornecedor).delete()
            db.session.query(Equipamento).delete()
            db.session.query(Obra).delete()
            db.session.commit()

        def fix_types(record):
            if not isinstance(record, dict):
                return record
            cleaned = {}
            for key, value in record.items():
                if isinstance(value, str):
                    try:
                        if 'T' in value:
                            cleaned[key] = datetime.fromisoformat(value)
                        elif len(value) == 10 and value[4] == '-' and value[7] == '-':
                            cleaned[key] = date.fromisoformat(value)
                        elif value.lower() in ('true', 'false'):
                            cleaned[key] = (value.lower() == 'true')
                        elif value == 'None':
                            cleaned[key] = None
                        else:
                            cleaned[key] = value
                    except ValueError:
                        cleaned[key] = value
                else:
                    cleaned[key] = value
            return cleaned

        obra_id_map = {}
        for obra_data in data.get('obras', []):
            rec = fix_types(obra_data)
            old_id = rec.get('id')
            if mode == 'overwrite' and old_id:
                obj = Obra(**rec)
                db.session.add(obj)
                db.session.flush()
                obra_id_map[old_id] = obj.id
            else:
                rec.pop('id', None)
                existente = Obra.query.filter_by(codigo=rec.get('codigo')).first()
                if existente:
                    obra_id_map[old_id] = existente.id
                else:
                    obj = Obra(**rec)
                    db.session.add(obj)
                    db.session.flush()
                    obra_id_map[old_id] = obj.id

        equip_id_map = {}
        for eq_data in data.get('equipamentos', []):
            rec = fix_types(eq_data)
            old_id = rec.get('id')
            if mode == 'overwrite' and old_id:
                obj = Equipamento(**rec)
                db.session.add(obj)
                db.session.flush()
                equip_id_map[old_id] = obj.id
            else:
                rec.pop('id', None)
                existente = Equipamento.query.filter_by(prefixo_placa=rec.get('prefixo_placa')).first()
                if existente:
                    equip_id_map[old_id] = existente.id
                else:
                    obj = Equipamento(**rec)
                    db.session.add(obj)
                    db.session.flush()
                    equip_id_map[old_id] = obj.id

        forn_id_map = {}
        for forn_data in data.get('fornecedores', []):
            rec = fix_types(forn_data)
            old_id = rec.get('id')
            if 'obra_id' in rec and rec['obra_id'] in obra_id_map:
                rec['obra_id'] = obra_id_map[rec['obra_id']]

            if mode == 'overwrite' and old_id:
                obj = Fornecedor(**rec)
                db.session.add(obj)
                db.session.flush()
                forn_id_map[old_id] = obj.id
            else:
                rec.pop('id', None)
                existente = Fornecedor.query.filter_by(nome=rec.get('nome')).first()
                if existente:
                    forn_id_map[old_id] = existente.id
                else:
                    obj = Fornecedor(**rec)
                    db.session.add(obj)
                    db.session.flush()
                    forn_id_map[old_id] = obj.id

        for abast_data in data.get('abastecimentos', []):
            rec = fix_types(abast_data)
            rec.pop('id', None)
            if 'usuario_id' in rec:
                rec['usuario_id'] = user_id
            if rec.get('equipamento_id') in equip_id_map:
                rec['equipamento_id'] = equip_id_map[rec['equipamento_id']]
            if rec.get('fornecedor_id') in forn_id_map:
                rec['fornecedor_id'] = forn_id_map[rec['fornecedor_id']]
            if rec.get('obra_id') in obra_id_map:
                rec['obra_id'] = obra_id_map[rec['obra_id']]
            db.session.add(Abastecimento(**rec))

        for ent_data in data.get('entradas', []):
            rec = fix_types(ent_data)
            rec.pop('id', None)
            if 'usuario_id' in rec:
                rec['usuario_id'] = user_id
            if rec.get('fornecedor_id') in forn_id_map:
                rec['fornecedor_id'] = forn_id_map[rec['fornecedor_id']]
            if rec.get('obra_id') in obra_id_map:
                rec['obra_id'] = obra_id_map[rec['obra_id']]
            db.session.add(EntradaInsumo(**rec))

        for transf_data in data.get('transferencias', []):
            rec = fix_types(transf_data)
            rec.pop('id', None)
            if 'usuario_id' in rec:
                rec['usuario_id'] = user_id
            if rec.get('origem_id') in forn_id_map:
                rec['origem_id'] = forn_id_map[rec['origem_id']]
            if rec.get('destino_id') in forn_id_map:
                rec['destino_id'] = forn_id_map[rec['destino_id']]
            if rec.get('obra_id') in obra_id_map:
                rec['obra_id'] = obra_id_map[rec['obra_id']]
            db.session.add(Transferencia(**rec))

        db.session.commit()

    @staticmethod
    def exportar_obras_csv():
        si = StringIO()
        cw = csv.writer(si, delimiter=';')
        cw.writerow(['Codigo', 'Nome', 'Local', 'Tanques Fixos', 'Comboios'])
        for o in Obra.query.all():
            tanques = Fornecedor.query.filter(
                Fornecedor.obra_id == o.id,
                Fornecedor.tipo_origem == 'Interno',
                Fornecedor.categoria_tanque != 'Comboio'
            ).count()
            comboios = Fornecedor.query.filter(
                Fornecedor.obra_id == o.id,
                Fornecedor.tipo_origem == 'Interno',
                Fornecedor.categoria_tanque == 'Comboio'
            ).count()
            cw.writerow([o.codigo, o.nome, o.local or '', tanques, comboios])
        return '\ufeff' + si.getvalue()

    @staticmethod
    def exportar_movimentacoes_csv():
        si = StringIO()
        cw = csv.writer(si, delimiter=';')
        cw.writerow(['Data', 'Tipo', 'Equipamento/Origem', 'Destino', 'Volume (L)', 'Combustível'])
        for a in Abastecimento.query.order_by(Abastecimento.data_abastecimento.desc()).limit(1000).all():
            cw.writerow([
                a.data_abastecimento.strftime('%d/%m/%Y'), 'Abastecimento',
                a.equipamento_rel.prefixo_placa if a.equipamento_rel else '',
                a.fornecedor_rel.nome if a.fornecedor_rel else '',
                a.quantidade, a.categoria_insumo
            ])
        for t in Transferencia.query.order_by(Transferencia.data_hora.desc()).limit(1000).all():
            cw.writerow([
                t.data_hora.strftime('%d/%m/%Y %H:%M'), 'Transbordo',
                t.origem.nome, t.destino.nome, t.litros, t.tipo_combustivel
            ])
        return '\ufeff' + si.getvalue()

    @staticmethod
    def reset_database():
        db.drop_all()
        db.create_all()
        obra = Obra(codigo='OB-001', nome='OBRA PADRÃO', local='A DEFINIR', ativa=True)
        db.session.add(obra)
        db.session.flush()

        admin = Usuario(
            nome='Administrador',
            email='cassiojr1658@gmail.com',
            nivel_acesso='administrador',
            ativo=True,
            acesso_global=True,
            obra_padrao_id=obra.id
        )
        admin.set_senha('itachi23k')
        db.session.add(admin)
        db.session.commit()