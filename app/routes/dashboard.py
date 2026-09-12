import os
import calendar
from datetime import date
from flask import Blueprint, render_template, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Equipamento, Fornecedor, Abastecimento, EntradaInsumo, Obra
from app.services.stock_calculator import StockCalculator

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    hoje = date.today()
    primeiro_dia = date(hoje.year, hoje.month, 1)
    ultimo_dia = date(hoje.year, hoje.month, calendar.monthrange(hoje.year, hoje.month)[1])

    if current_user.is_global:
        obras_visiveis = Obra.query.filter_by(ativa=True).all()
    elif current_user.obra_padrao_id:
        obras_visiveis = [Obra.query.get(current_user.obra_padrao_id)]
    else:
        obras_visiveis = []

    obra_ids = [o.id for o in obras_visiveis] if obras_visiveis else [-1]

    # Consumos consolidados
    consumo_por_tipo = db.session.query(
        Abastecimento.categoria_insumo,
        db.func.sum(Abastecimento.quantidade).label('total')
    ).filter(
        Abastecimento.data_abastecimento >= primeiro_dia,
        Abastecimento.data_abastecimento <= ultimo_dia,
        Abastecimento.obra_id.in_(obra_ids) if obras_visiveis else True
    ).group_by(Abastecimento.categoria_insumo).order_by(db.desc('total')).all()
    consumo_mes = sum([c.total for c in consumo_por_tipo]) if consumo_por_tipo else 0

    # Entradas consolidadas
    entradas_por_tipo = db.session.query(
        EntradaInsumo.categoria_insumo,
        db.func.sum(EntradaInsumo.quantidade).label('total')
    ).filter(
        EntradaInsumo.data_entrada >= primeiro_dia,
        EntradaInsumo.data_entrada <= ultimo_dia,
        EntradaInsumo.obra_id.in_(obra_ids) if obras_visiveis else True
    ).group_by(EntradaInsumo.categoria_insumo).order_by(db.desc('total')).all()
    entradas_mes = sum([e.total for e in entradas_por_tipo]) if entradas_por_tipo else 0

    # Estoque em lote
    saldos_map, tanques_internos = StockCalculator.obter_saldos_tanques_lote(obra_ids=obra_ids)
    tanques_por_obra = {}
    for t in tanques_internos:
        tanques_por_obra.setdefault(t.obra_id, []).append(t)

    obras_dados = []
    for obra in obras_visiveis:
        consumo_obra_por_tipo = db.session.query(
            Abastecimento.categoria_insumo,
            db.func.sum(Abastecimento.quantidade).label('total')
        ).filter(
            Abastecimento.data_abastecimento >= primeiro_dia,
            Abastecimento.data_abastecimento <= ultimo_dia,
            Abastecimento.obra_id == obra.id
        ).group_by(Abastecimento.categoria_insumo).order_by(db.desc('total')).all()
        consumo_obra = sum([c.total for c in consumo_obra_por_tipo]) if consumo_obra_por_tipo else 0

        entradas_obra_por_tipo = db.session.query(
            EntradaInsumo.categoria_insumo,
            db.func.sum(EntradaInsumo.quantidade).label('total')
        ).filter(
            EntradaInsumo.data_entrada >= primeiro_dia,
            EntradaInsumo.data_entrada <= ultimo_dia,
            EntradaInsumo.obra_id == obra.id
        ).group_by(EntradaInsumo.categoria_insumo).order_by(db.desc('total')).all()
        entradas_obra = sum([e.total for e in entradas_obra_por_tipo]) if entradas_obra_por_tipo else 0

        tanques_obra = tanques_por_obra.get(obra.id, [])
        niveis_estoque = []
        for c in tanques_obra:
            saldo = saldos_map.get(c.id, 0.0)
            capacidade = c.capacidade_litros or 0.0
            perc_visual = max(0.0, min((saldo / capacidade * 100) if capacidade > 0 else 0.0, 100.0))
            niveis_estoque.append({
                'nome': c.nome,
                'saldo': saldo,
                'capacidade': capacidade,
                'percentual': perc_visual,
                'estoque_inicial': c.estoque_inicial or 0.0,
                'categoria': c.categoria_tanque or 'Tanque'
            })

        maquinas_obra_mes = db.session.query(Abastecimento.equipamento_id).filter(
            Abastecimento.obra_id == obra.id,
            Abastecimento.data_abastecimento >= primeiro_dia,
            Abastecimento.data_abastecimento <= ultimo_dia
        ).distinct().count()

        obras_dados.append({
            'obra': obra,
            'consumo_mes': consumo_obra,
            'consumo_por_tipo': consumo_obra_por_tipo,
            'entradas_mes': entradas_obra,
            'entradas_por_tipo': entradas_obra_por_tipo,
            'maquinas_ativas': maquinas_obra_mes,
            'niveis_estoque': niveis_estoque
        })

    meses = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
             'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    
    db_candidates = [
        os.path.join(current_app.instance_path, 'frota_local.db'),
        os.path.join(current_app.root_path, '..', 'instance', 'frota_local.db'),
        os.path.join(current_app.instance_path, 'frota.db')
    ]
    db_size = 0.0
    for cand in db_candidates:
        if os.path.exists(cand):
            db_size = round(os.path.getsize(cand) / 1024, 2)
            break       

    return render_template('dashboard.html',
                           consumo_mes=consumo_mes,
                           consumo_por_tipo=consumo_por_tipo,
                           entradas_mes=entradas_mes,
                           entradas_por_tipo=entradas_por_tipo,
                           equipamentos_ativos=Equipamento.query.filter_by(ativo=True).count(),
                           fornecedores_ativos=Fornecedor.query.filter_by(ativo=True).count(),
                           nome_mes=meses[hoje.month],
                           ano=hoje.year,
                           obras_dados=obras_dados,
                           db_size=db_size,
                           total_obras=Obra.query.count(),
                           total_equipamentos=Equipamento.query.count(),
                           total_abastecimentos=Abastecimento.query.count())