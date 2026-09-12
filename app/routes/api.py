from flask import Blueprint, request
from flask_login import login_required
from app.models import Fornecedor, Transferencia, Abastecimento, Equipamento

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/fornecedores-por-obra')
@login_required
def fornecedores_por_obra():
    obra_id = request.args.get('obra_id', '').strip()
    try:
        query = Fornecedor.query.filter_by(ativo=True)
        if obra_id:
            query = query.filter_by(obra_id=int(obra_id))
        fornecedores = query.order_by(Fornecedor.nome).all()
        return {
            'fornecedores': [
                {
                    'id': f.id,
                    'nome': f.nome,
                    'tipo': f.tipo_origem,
                    'capacidade': f.capacidade_litros,
                    'categoria_tanque': f.categoria_tanque or 'Tanque',
                    'tipo_combustivel': (f.tipo_combustivel or 'DIESEL S10').strip().upper(),
                    'obra_id': f.obra_id
                } for f in fornecedores
            ]
        }
    except Exception as e:
        return {'erro': str(e)}, 400


@api_bp.route('/transferencia/<int:id>')
@login_required
def transferencia(id):
    t = Transferencia.query.get_or_404(id)
    return {
        'id': t.id,
        'data_hora': t.data_hora.strftime('%Y-%m-%dT%H:%M') if t.data_hora else '',
        'origem_id': t.origem_id,
        'destino_id': t.destino_id,
        'litros': t.litros,
        'tipo_combustivel': t.tipo_combustivel,
        'observacao': t.observacao or ''
    }


@api_bp.route('/combustiveis-disponiveis')
@login_required
def combustiveis_disponiveis():
    equip_id, data_inicio, data_fim, obra_id = request.args.get('equipamento_id'), request.args.get('data_inicio'), request.args.get('data_fim'), request.args.get('obra_id', '').strip()
    if not (equip_id and data_inicio and data_fim):
        return {'combustiveis': []}
    try:
        query = Abastecimento.query.filter(
            Abastecimento.equipamento_id == int(equip_id),
            Abastecimento.data_abastecimento >= data_inicio,
            Abastecimento.data_abastecimento <= data_fim
        )
        if obra_id:
            query = query.filter(Abastecimento.obra_id == int(obra_id))
        combustiveis = query.with_entities(Abastecimento.categoria_insumo).distinct().all()
        return {'combustiveis': [c[0] for c in combustiveis]}
    except Exception as e:
        return {'erro': str(e)}, 400


@api_bp.route('/equipamento/<int:id>')
@login_required
def equipamento(id):
    eq = Equipamento.query.get_or_404(id)
    return {
        'id': eq.id,
        'prefixo_placa': eq.prefixo_placa,
        'descricao': eq.descricao or '',
        'locador': eq.locador or '',
        'tipo_equipamento': eq.tipo_equipamento or ''
    }