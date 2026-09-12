from datetime import datetime
from sqlalchemy import extract
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Equipamento, Fornecedor, Abastecimento, EntradaInsumo, Transferencia, Obra, FrenteServico
from app.services.excel_generator import ExcelGenerator
from app.services.pdf_generator import PDFGenerator
from app.services.stock_calculator import StockCalculator

relatorios_bp = Blueprint('relatorios', __name__)


def periodo_valido(data_inicio, data_fim):
    try:
        inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        return fim >= inicio
    except (TypeError, ValueError):
        return False


# ==========================================
# RELATÓRIO 1: DOSSIÊ EQUIPAMENTO
# ==========================================
@relatorios_bp.route('/relatorio/equipamento', methods=['GET'])
@login_required
def relatorio_equipamento():
    equipamentos = Equipamento.query.order_by(Equipamento.prefixo_placa).all()
    equip_id, data_inicio, data_fim = request.args.get('equipamento_id'), request.args.get('data_inicio'), request.args.get('data_fim')
    resultados, total_litros, equip_selecionado = [], 0, None

    if equip_id and data_inicio and data_fim and periodo_valido(data_inicio, data_fim):
        resultados = Abastecimento.query.filter(
            Abastecimento.equipamento_id == equip_id,
            Abastecimento.data_abastecimento >= data_inicio,
            Abastecimento.data_abastecimento <= data_fim
        ).order_by(Abastecimento.data_abastecimento.desc()).all()
        total_litros = sum([r.quantidade for r in resultados])
        equip_selecionado = Equipamento.query.get(equip_id)

    return render_template('relatorio_equipamento.html', equipamentos=equipamentos, resultados=resultados,
                           total_litros=total_litros, equip_selecionado=equip_selecionado,
                           data_inicio=data_inicio, data_fim=data_fim, equip_id_str=equip_id)


@relatorios_bp.route('/exportar/equipamento', methods=['GET'])
@login_required
def exportar_equipamento():
    equip_id, data_inicio, data_fim, formato = request.args.get('equipamento_id'), request.args.get('data_inicio'), request.args.get('data_fim'), request.args.get('formato', 'excel')
    insumo_filtro = request.args.get('insumo', None)

    if not (equip_id and data_inicio and data_fim and periodo_valido(data_inicio, data_fim)):
        flash('Filtros incompletos.', 'warning')
        return redirect(url_for('relatorios.relatorio_equipamento'))

    equip = Equipamento.query.get_or_404(equip_id)
    resultados = Abastecimento.query.filter(
        Abastecimento.equipamento_id == equip_id,
        Abastecimento.data_abastecimento >= data_inicio,
        Abastecimento.data_abastecimento <= data_fim
    ).order_by(Abastecimento.data_abastecimento.asc()).all()

    total_litros = sum([r.quantidade for r in resultados])

    if formato == 'excel':
        return ExcelGenerator.exportar_equipamento_excel(equip, resultados, total_litros, data_inicio, data_fim)
    elif formato == 'csv':
        return ExcelGenerator.exportar_equipamento_csv(equip, resultados, total_litros, data_inicio, data_fim)
    elif formato == 'texto':
        return ExcelGenerator.exportar_equipamento_texto(equip, resultados, data_inicio, data_fim, insumo_filtro)
    elif formato == 'pdf':
        return PDFGenerator.exportar_equipamento_pdf(equip, resultados, total_litros, data_inicio, data_fim, current_user.nome)

    flash('Formato inválido.', 'danger')
    return redirect(url_for('relatorios.relatorio_equipamento'))


# ==========================================
# RELATÓRIO 2: EXTRATO POR FORNECEDOR/POSTO
# ==========================================
@relatorios_bp.route('/relatorio/fornecedor', methods=['GET'])
@login_required
def relatorio_fornecedor():
    fornecedores = Fornecedor.query.order_by(Fornecedor.nome).all()
    forn_id, data_inicio, data_fim = request.args.get('fornecedor_id'), request.args.get('data_inicio'), request.args.get('data_fim')
    forn_selecionado, abastecimentos, entradas_nf, transferencias, transferencias_enviadas = None, [], [], [], []
    total_abastecimentos, total_entradas, total_transf, total_transf_enviadas = 0, 0, 0, 0
    abastecimentos_por_dia = []

    if forn_id and data_inicio and data_fim and periodo_valido(data_inicio, data_fim):
        forn_selecionado = Fornecedor.query.get(forn_id)
        abastecimentos = Abastecimento.query.filter(
            Abastecimento.fornecedor_id == forn_id,
            Abastecimento.data_abastecimento >= data_inicio,
            Abastecimento.data_abastecimento <= data_fim
        ).order_by(Abastecimento.data_abastecimento.desc(), Abastecimento.id.desc()).all()
        total_abastecimentos = sum([a.quantidade for a in abastecimentos])

        grupos_dict = {}
        for ab in abastecimentos:
            d = ab.data_abastecimento
            if d not in grupos_dict:
                grupo = {'data': d, 'itens': [], 'total_dia': 0.0}
                grupos_dict[d] = grupo
                abastecimentos_por_dia.append(grupo)
            grupos_dict[d]['itens'].append(ab)
            grupos_dict[d]['total_dia'] += float(ab.quantidade or 0.0)

        entradas_nf = EntradaInsumo.query.filter(
            EntradaInsumo.fornecedor_id == forn_id, EntradaInsumo.data_entrada >= data_inicio, EntradaInsumo.data_entrada <= data_fim
        ).order_by(EntradaInsumo.data_entrada.desc()).all()
        total_entradas = sum([e.quantidade for e in entradas_nf])

        transferencias = Transferencia.query.filter(
            Transferencia.destino_id == forn_id, db.func.date(Transferencia.data_hora) >= data_inicio, db.func.date(Transferencia.data_hora) <= data_fim
        ).order_by(Transferencia.data_hora.desc()).all()
        total_transf = sum([t.litros for t in transferencias])

        transferencias_enviadas = Transferencia.query.filter(
            Transferencia.origem_id == forn_id, db.func.date(Transferencia.data_hora) >= data_inicio, db.func.date(Transferencia.data_hora) <= data_fim
        ).order_by(Transferencia.data_hora.desc()).all()
        total_transf_enviadas = sum([t.litros for t in transferencias_enviadas])

    return render_template('relatorio_fornecedor.html', fornecedores=fornecedores, forn_selecionado=forn_selecionado,
                           abastecimentos=abastecimentos, abastecimentos_por_dia=abastecimentos_por_dia,
                           entradas_nf=entradas_nf, transferencias=transferencias, transferencias_enviadas=transferencias_enviadas,
                           total_abastecimentos=total_abastecimentos, total_entradas=total_entradas, total_transf=total_transf,
                           total_transf_enviadas=total_transf_enviadas, data_inicio=data_inicio, data_fim=data_fim, forn_id_str=forn_id)


@relatorios_bp.route('/exportar/fornecedor', methods=['GET'])
@login_required
def exportar_fornecedor():
    forn_id, data_inicio, data_fim = request.args.get('fornecedor_id'), request.args.get('data_inicio'), request.args.get('data_fim')
    if not (forn_id and data_inicio and data_fim and periodo_valido(data_inicio, data_fim)):
        flash('Filtros incompletos.', 'warning')
        return redirect(url_for('relatorios.relatorio_fornecedor'))

    forn = Fornecedor.query.get_or_404(forn_id)
    abastecimentos = Abastecimento.query.filter(Abastecimento.fornecedor_id == forn_id, Abastecimento.data_abastecimento >= data_inicio, Abastecimento.data_abastecimento <= data_fim).all()
    entradas_nf = EntradaInsumo.query.filter(EntradaInsumo.fornecedor_id == forn_id, EntradaInsumo.data_entrada >= data_inicio, EntradaInsumo.data_entrada <= data_fim).all()
    transferencias = Transferencia.query.filter(Transferencia.destino_id == forn_id, db.func.date(Transferencia.data_hora) >= data_inicio, db.func.date(Transferencia.data_hora) <= data_fim).all()
    transferencias_enviadas = Transferencia.query.filter(Transferencia.origem_id == forn_id, db.func.date(Transferencia.data_hora) >= data_inicio, db.func.date(Transferencia.data_hora) <= data_fim).all()

    return ExcelGenerator.exportar_fornecedor_excel(forn, abastecimentos, entradas_nf, transferencias, transferencias_enviadas, data_inicio, data_fim)


# ==========================================
# RELATÓRIO 3: CONSOLIDADO POSTO X EQUIPAMENTO
# ==========================================
@relatorios_bp.route('/relatorio/consolidado', methods=['GET'])
@login_required
def relatorio_consolidado():
    fornecedores = Fornecedor.query.order_by(Fornecedor.nome).all()
    forn_id, data_inicio, data_fim = request.args.get('fornecedor_id'), request.args.get('data_inicio'), request.args.get('data_fim')
    resultados, total_litros, forn_selecionado = [], 0, None

    if forn_id and data_inicio and data_fim and periodo_valido(data_inicio, data_fim):
        resultados = db.session.query(
            Equipamento.prefixo_placa, Equipamento.tipo_equipamento,
            db.func.sum(Abastecimento.quantidade).label('total_consumido')
        ).join(Abastecimento, Equipamento.id == Abastecimento.equipamento_id)\
        .filter(Abastecimento.fornecedor_id == forn_id, Abastecimento.data_abastecimento >= data_inicio, Abastecimento.data_abastecimento <= data_fim)\
        .group_by(Equipamento.id).order_by(db.desc('total_consumido')).all()
        total_litros = sum([r.total_consumido for r in resultados])
        forn_selecionado = Fornecedor.query.get(forn_id)

    return render_template('relatorio_consolidado.html', fornecedores=fornecedores, resultados=resultados,
                           total_litros=total_litros, forn_selecionado=forn_selecionado,
                           data_inicio=data_inicio, data_fim=data_fim, forn_id_str=forn_id)


@relatorios_bp.route('/exportar/consolidado', methods=['GET'])
@login_required
def exportar_consolidado():
    forn_id, data_inicio, data_fim = request.args.get('fornecedor_id'), request.args.get('data_inicio'), request.args.get('data_fim')
    if not (forn_id and data_inicio and data_fim and periodo_valido(data_inicio, data_fim)):
        flash('Filtros incompletos.', 'warning')
        return redirect(url_for('relatorios.relatorio_consolidado'))

    forn = Fornecedor.query.get_or_404(forn_id)
    resultados = db.session.query(
        Equipamento.prefixo_placa, Equipamento.tipo_equipamento,
        db.func.sum(Abastecimento.quantidade).label('total_consumido')
    ).join(Abastecimento, Equipamento.id == Abastecimento.equipamento_id)\
    .filter(Abastecimento.fornecedor_id == forn_id, Abastecimento.data_abastecimento >= data_inicio, Abastecimento.data_abastecimento <= data_fim)\
    .group_by(Equipamento.id).order_by(db.desc('total_consumido')).all()

    return ExcelGenerator.exportar_consolidado_csv(forn, resultados, data_inicio, data_fim)


# ==========================================
# RELATÓRIO 4: BALANÇO DE ESTOQUE
# ==========================================
@relatorios_bp.route('/relatorio/estoque', methods=['GET'])
@login_required
def relatorio_estoque():
    comboios = Fornecedor.query.filter_by(tipo_origem='Interno').order_by(Fornecedor.nome).all()
    forn_id, data_inicio, data_fim = request.args.get('fornecedor_id'), request.args.get('data_inicio'), request.args.get('data_fim')
    entradas_nf, saidas_abast, transf_recebidas, transf_enviadas, estoque_inicial, saldo, forn_selecionado = 0, 0, 0, 0, 0, 0, None

    if forn_id and data_inicio and data_fim and periodo_valido(data_inicio, data_fim):
        forn_selecionado = Fornecedor.query.get(forn_id)
        if forn_selecionado:
            d_ini = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            d_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()

            # Movimentações anteriores à data de início para obter o saldo inicial real da data
            ent_ant = db.session.query(db.func.sum(EntradaInsumo.quantidade)).filter(
                EntradaInsumo.fornecedor_id == forn_id, EntradaInsumo.data_entrada < d_ini
            ).scalar() or 0.0
            saida_ant = db.session.query(db.func.sum(Abastecimento.quantidade)).filter(
                Abastecimento.fornecedor_id == forn_id, Abastecimento.data_abastecimento < d_ini
            ).scalar() or 0.0
            transf_rec_ant = db.session.query(db.func.sum(Transferencia.litros)).filter(
                Transferencia.destino_id == forn_id, db.func.date(Transferencia.data_hora) < d_ini
            ).scalar() or 0.0
            transf_env_ant = db.session.query(db.func.sum(Transferencia.litros)).filter(
                Transferencia.origem_id == forn_id, db.func.date(Transferencia.data_hora) < d_ini
            ).scalar() or 0.0

            cadastro_inicial = forn_selecionado.estoque_inicial or 0.0
            estoque_inicial = cadastro_inicial + ent_ant + transf_rec_ant - saida_ant - transf_env_ant

            # Movimentações do período selecionado
            entradas_nf = db.session.query(db.func.sum(EntradaInsumo.quantidade)).filter(
                EntradaInsumo.fornecedor_id == forn_id, EntradaInsumo.data_entrada >= d_ini, EntradaInsumo.data_entrada <= d_fim
            ).scalar() or 0.0
            saidas_abast = db.session.query(db.func.sum(Abastecimento.quantidade)).filter(
                Abastecimento.fornecedor_id == forn_id, Abastecimento.data_abastecimento >= d_ini, Abastecimento.data_abastecimento <= d_fim
            ).scalar() or 0.0
            transf_recebidas = db.session.query(db.func.sum(Transferencia.litros)).filter(
                Transferencia.destino_id == forn_id, db.func.date(Transferencia.data_hora) >= d_ini, db.func.date(Transferencia.data_hora) <= d_fim
            ).scalar() or 0.0
            transf_enviadas = db.session.query(db.func.sum(Transferencia.litros)).filter(
                Transferencia.origem_id == forn_id, db.func.date(Transferencia.data_hora) >= d_ini, db.func.date(Transferencia.data_hora) <= d_fim
            ).scalar() or 0.0

            saldo = estoque_inicial + entradas_nf + transf_recebidas - saidas_abast - transf_enviadas

    return render_template('relatorio_estoque.html', comboios=comboios, forn_selecionado=forn_selecionado,
                           entradas_nf=entradas_nf, saidas_abast=saidas_abast, transf_recebidas=transf_recebidas,
                           transf_enviadas=transf_enviadas, estoque_inicial=estoque_inicial, saldo=saldo,
                           data_inicio=data_inicio, data_fim=data_fim, forn_id_str=forn_id)


# ==========================================
# RELATÓRIO 5: CONSUMO POR LOCADOR
# ==========================================
@relatorios_bp.route('/relatorio/locador', methods=['GET'])
@login_required
def relatorio_locador():
    locadores_db = db.session.query(Equipamento.locador).distinct().all()
    lista_locadores = [l[0] for l in locadores_db if l[0]]
    locador_sel, data_inicio, data_fim = request.args.get('locador'), request.args.get('data_inicio'), request.args.get('data_fim')
    resultados, total_litros = [], 0

    if locador_sel and data_inicio and data_fim and periodo_valido(data_inicio, data_fim):
        resultados = db.session.query(
            Equipamento.prefixo_placa, Equipamento.descricao, Equipamento.tipo_equipamento,
            db.func.sum(Abastecimento.quantidade).label('total_consumido'),
            db.func.count(Abastecimento.id).label('total_abastecimentos')
        ).join(Abastecimento, Equipamento.id == Abastecimento.equipamento_id)\
        .filter(Equipamento.locador == locador_sel, Abastecimento.data_abastecimento >= data_inicio, Abastecimento.data_abastecimento <= data_fim)\
        .group_by(Equipamento.id).order_by(db.desc('total_consumido')).all()
        total_litros = sum([r.total_consumido for r in resultados])

    return render_template('relatorio_locador.html', lista_locadores=lista_locadores, resultados=resultados,
                           total_litros=total_litros, locador_sel=locador_sel, data_inicio=data_inicio, data_fim=data_fim)


@relatorios_bp.route('/exportar/locador', methods=['GET'])
@login_required
def exportar_locador():
    locador_sel, data_inicio, data_fim, formato = request.args.get('locador'), request.args.get('data_inicio'), request.args.get('data_fim'), request.args.get('formato', 'pdf')
    if not (locador_sel and data_inicio and data_fim and periodo_valido(data_inicio, data_fim)):
        flash('Filtros incompletos.', 'warning')
        return redirect(url_for('relatorios.relatorio_locador'))

    resultados_resumo = db.session.query(
        Equipamento.id.label('equipamento_id'), Equipamento.prefixo_placa, Equipamento.descricao, Equipamento.tipo_equipamento,
        db.func.sum(Abastecimento.quantidade).label('total_consumido'), db.func.count(Abastecimento.id).label('total_abastecimentos')
    ).join(Abastecimento, Equipamento.id == Abastecimento.equipamento_id)\
    .filter(Equipamento.locador == locador_sel, Abastecimento.data_abastecimento >= data_inicio, Abastecimento.data_abastecimento <= data_fim)\
    .group_by(Equipamento.id).order_by(Equipamento.prefixo_placa).all()

    lancamentos_detalhados = Abastecimento.query.join(
        Equipamento, Abastecimento.equipamento_id == Equipamento.id
    ).filter(Equipamento.locador == locador_sel, Abastecimento.data_abastecimento >= data_inicio, Abastecimento.data_abastecimento <= data_fim)\
    .order_by(Equipamento.prefixo_placa, Abastecimento.data_abastecimento.asc(), Abastecimento.id.asc()).all()

    total_litros = sum([r.total_consumido for r in resultados_resumo])

    if formato == 'excel':
        return ExcelGenerator.exportar_locador_excel(locador_sel, resultados_resumo, lancamentos_detalhados, total_litros, data_inicio, data_fim)
    return PDFGenerator.exportar_locador_pdf(locador_sel, resultados_resumo, lancamentos_detalhados, total_litros, data_inicio, data_fim, current_user.nome)


@relatorios_bp.route('/relatorio/obras')
@login_required
def relatorio_obras():
    return redirect(url_for('whatsapp.painel', aba='manual'))


# ==========================================
# RELATÓRIO: HISTÓRICO MENSAL POR OBRA
# ==========================================
@relatorios_bp.route('/relatorio/historico-obra')
@login_required
def historico_obra():
    import calendar
    from datetime import date
    from app.models import Obra

    # Obras visíveis para o usuário
    if current_user.is_global:
        obras_lista = Obra.query.filter_by(ativa=True).order_by(Obra.nome).all()
    elif current_user.obra_padrao_id:
        obras_lista = Obra.query.filter(
            Obra.id == current_user.obra_padrao_id, Obra.ativa == True
        ).all()
    else:
        obras_lista = []

    obra_id_sel = request.args.get('obra_id', '', type=str)
    pagina = request.args.get('pagina', 1, type=int)
    por_pagina = 12  # meses por página

    obra_sel = None
    meses_dados = []
    total_paginas = 1
    total_entradas_geral = {}
    total_saidas_geral = {}

    if obra_id_sel:
        obra_sel = Obra.query.get(int(obra_id_sel))

    if obra_sel and (current_user.is_global or obra_sel.id == current_user.obra_padrao_id):
        # Descobrir o intervalo de meses com dados (entradas ou saídas)
        min_entrada = db.session.query(db.func.min(EntradaInsumo.data_entrada)).filter(
            EntradaInsumo.obra_id == obra_sel.id
        ).scalar()
        min_saida = db.session.query(db.func.min(Abastecimento.data_abastecimento)).filter(
            Abastecimento.obra_id == obra_sel.id
        ).scalar()
        max_entrada = db.session.query(db.func.max(EntradaInsumo.data_entrada)).filter(
            EntradaInsumo.obra_id == obra_sel.id
        ).scalar()
        max_saida = db.session.query(db.func.max(Abastecimento.data_abastecimento)).filter(
            Abastecimento.obra_id == obra_sel.id
        ).scalar()

        datas_validas = [d for d in [min_entrada, min_saida, max_entrada, max_saida] if d]
        if datas_validas:
            data_min = min(datas_validas)
            data_max = max(datas_validas)

            # Gerar lista de todos os meses do intervalo (do mais recente ao mais antigo)
            todos_meses = []
            ano, mes = data_max.year, data_max.month
            while (ano, mes) >= (data_min.year, data_min.month):
                todos_meses.append((ano, mes))
                mes -= 1
                if mes == 0:
                    mes = 12
                    ano -= 1

            total_paginas = max(1, (len(todos_meses) + por_pagina - 1) // por_pagina)
            pagina = max(1, min(pagina, total_paginas))
            meses_pagina = todos_meses[(pagina - 1) * por_pagina: pagina * por_pagina]

            # Buscar entradas e saídas em lote para os meses da página
            if meses_pagina:
                primeiro_mes = meses_pagina[-1]  # mais antigo da página
                ultimo_mes  = meses_pagina[0]    # mais recente da página
                data_inicio_pag = date(primeiro_mes[0], primeiro_mes[1], 1)
                data_fim_pag    = date(ultimo_mes[0], ultimo_mes[1],
                                       calendar.monthrange(ultimo_mes[0], ultimo_mes[1])[1])

                # Entradas agrupadas por (ano, mês, categoria)
                rows_entrada = db.session.query(
                    extract('year', EntradaInsumo.data_entrada).label('ano'),
                    extract('month', EntradaInsumo.data_entrada).label('mes'),
                    EntradaInsumo.categoria_insumo,
                    db.func.sum(EntradaInsumo.quantidade).label('total')
                ).filter(
                    EntradaInsumo.obra_id == obra_sel.id,
                    EntradaInsumo.data_entrada >= data_inicio_pag,
                    EntradaInsumo.data_entrada <= data_fim_pag
                ).group_by(
                    extract('year', EntradaInsumo.data_entrada),
                    extract('month', EntradaInsumo.data_entrada),
                    EntradaInsumo.categoria_insumo
                ).all()

                # Saídas agrupadas por (ano, mês, categoria)
                rows_saida = db.session.query(
                    extract('year', Abastecimento.data_abastecimento).label('ano'),
                    extract('month', Abastecimento.data_abastecimento).label('mes'),
                    Abastecimento.categoria_insumo,
                    db.func.sum(Abastecimento.quantidade).label('total')
                ).filter(
                    Abastecimento.obra_id == obra_sel.id,
                    Abastecimento.data_abastecimento >= data_inicio_pag,
                    Abastecimento.data_abastecimento <= data_fim_pag
                ).group_by(
                    extract('year', Abastecimento.data_abastecimento),
                    extract('month', Abastecimento.data_abastecimento),
                    Abastecimento.categoria_insumo
                ).all()

                # Indexar por (ano, mês, categoria)
                map_entrada = {}
                for r in rows_entrada:
                    map_entrada[(int(r.ano), int(r.mes), r.categoria_insumo)] = r.total

                map_saida = {}
                for r in rows_saida:
                    map_saida[(int(r.ano), int(r.mes), r.categoria_insumo)] = r.total

                # Coletar todos os tipos presentes
                tipos_entrada = sorted(set(k[2] for k in map_entrada))
                tipos_saida   = sorted(set(k[2] for k in map_saida))

                nomes_meses = ['', 'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                               'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

                for ano_m, mes_m in meses_pagina:
                    entradas_mes = {t: map_entrada.get((ano_m, mes_m, t), 0) for t in tipos_entrada}
                    saidas_mes   = {t: map_saida.get((ano_m, mes_m, t), 0) for t in tipos_saida}

                    total_e = sum(entradas_mes.values())
                    total_s = sum(saidas_mes.values())

                    meses_dados.append({
                        'ano': ano_m,
                        'mes': mes_m,
                        'mes_nome': nomes_meses[mes_m],
                        'entradas': entradas_mes,
                        'saidas': saidas_mes,
                        'total_entrada': total_e,
                        'total_saida': total_s,
                    })

                    # Acumular totais gerais
                    for t, v in entradas_mes.items():
                        total_entradas_geral[t] = total_entradas_geral.get(t, 0) + v
                    for t, v in saidas_mes.items():
                        total_saidas_geral[t] = total_saidas_geral.get(t, 0) + v

    return render_template(
        'relatorio_historico_obra.html',
        obras_lista=obras_lista,
        obra_sel=obra_sel,
        obra_id_sel=obra_id_sel,
        meses_dados=meses_dados,
        total_entradas_geral=total_entradas_geral,
        total_saidas_geral=total_saidas_geral,
        pagina=pagina,
        total_paginas=total_paginas,
    )


# ==========================================
# RELATÓRIO: RESUMO / FECHAMENTO MENSAL
# ==========================================
@relatorios_bp.route('/relatorio/resumo-mensal')
@relatorios_bp.route('/relatorio/fechamento-mensal')
@login_required
def resumo_mensal():
    from datetime import date
    hoje = date.today()

    # Obras visíveis para o usuário
    if current_user.is_global:
        obras_lista = Obra.query.filter_by(ativa=True).order_by(Obra.nome).all()
    elif current_user.obra_padrao_id:
        obras_lista = Obra.query.filter(
            Obra.id == current_user.obra_padrao_id, Obra.ativa == True
        ).all()
    else:
        obras_lista = []

    obra_id_param = request.args.get('obra_id', type=str)
    
    # Se não passou obra_id e usuário tem obra padrão, seleciona a dele
    if not obra_id_param and not current_user.is_global and current_user.obra_padrao_id:
        obra_id_param = str(current_user.obra_padrao_id)
    elif not obra_id_param and obras_lista:
        obra_id_param = str(obras_lista[0].id)

    obra_id_int = int(obra_id_param) if (obra_id_param and obra_id_param.isdigit()) else (obras_lista[0].id if obras_lista else None)
    
    # Obter lista de meses disponíveis com dados
    meses_disponiveis = StockCalculator.obter_meses_disponiveis(obra_id_int)
    
    # Padrão: mês/ano atual ou o mais recente disponível
    ano_default = meses_disponiveis[0][0] if meses_disponiveis else hoje.year
    mes_default = meses_disponiveis[0][1] if meses_disponiveis else hoje.month

    ano = request.args.get('ano', ano_default, type=int)
    mes = request.args.get('mes', mes_default, type=int)

    dados_fechamento = StockCalculator.calcular_fechamento_mensal(obra_id_int, ano, mes)

    return render_template(
        'relatorio_resumo_mensal.html',
        obras_lista=obras_lista,
        obra_sel=dados_fechamento['obra'],
        obra_id_sel=str(obra_id_int) if obra_id_int else '',
        ano_sel=ano,
        mes_sel=mes,
        meses_disponiveis=meses_disponiveis,
        dados=dados_fechamento
    )


@relatorios_bp.route('/exportar/resumo-mensal/excel')
@login_required
def exportar_resumo_mensal_excel():
    obra_id = request.args.get('obra_id', type=int)
    ano = request.args.get('ano', type=int)
    mes = request.args.get('mes', type=int)

    if not (ano and mes):
        flash('Parâmetros de ano e mês inválidos.', 'warning')
        return redirect(url_for('relatorios.resumo_mensal'))

    dados = StockCalculator.calcular_fechamento_mensal(obra_id, ano, mes)
    return ExcelGenerator.exportar_resumo_mensal_excel(dados)


@relatorios_bp.route('/exportar/resumo-mensal/pdf')
@login_required
def exportar_resumo_mensal_pdf():
    obra_id = request.args.get('obra_id', type=int)
    ano = request.args.get('ano', type=int)
    mes = request.args.get('mes', type=int)

    if not (ano and mes):
        flash('Parâmetros de ano e mês inválidos.', 'warning')
        return redirect(url_for('relatorios.resumo_mensal'))

    dados = StockCalculator.calcular_fechamento_mensal(obra_id, ano, mes)
    return PDFGenerator.exportar_resumo_mensal_pdf(dados, current_user.nome)


# ==========================================
# RELATÓRIO: MÉDIA DE CONSUMO POR FRENTE DE SERVIÇO
# ==========================================
@relatorios_bp.route('/relatorio/media-consumo', methods=['GET'])
@login_required
def media_consumo():
    from datetime import date, datetime
    from app.models import Obra, Abastecimento

    # Obras permitidas para o usuário
    if current_user.is_global:
        obras_lista = Obra.query.filter_by(ativa=True).order_by(Obra.nome).all()
    elif current_user.obra_padrao_id:
        obras_lista = Obra.query.filter(Obra.id == current_user.obra_padrao_id, Obra.ativa == True).all()
    else:
        obras_lista = []

    obra_id_param = request.args.get('obra_id', '')
    data_inicio_param = request.args.get('data_inicio', '')
    data_fim_param = request.args.get('data_fim', '')
    frente_filtro = request.args.get('frente_servico', '').strip().upper()

    hoje = date.today()
    if not data_inicio_param or not data_fim_param:
        inicio_dt = date(hoje.year, hoje.month, 1)
        fim_dt = hoje
        data_inicio_param = inicio_dt.strftime('%Y-%m-%d')
        data_fim_param = fim_dt.strftime('%Y-%m-%d')
    else:
        try:
            inicio_dt = datetime.strptime(data_inicio_param, '%Y-%m-%d').date()
            fim_dt = datetime.strptime(data_fim_param, '%Y-%m-%d').date()
        except ValueError:
            inicio_dt = date(hoje.year, hoje.month, 1)
            fim_dt = hoje
            data_inicio_param = inicio_dt.strftime('%Y-%m-%d')
            data_fim_param = fim_dt.strftime('%Y-%m-%d')

    obra_id_int = int(obra_id_param) if (obra_id_param and obra_id_param.isdigit()) else None
    if not obra_id_int and not current_user.is_global and current_user.obra_padrao_id:
        obra_id_int = current_user.obra_padrao_id

    # Query base
    query = Abastecimento.query.filter(
        Abastecimento.data_abastecimento >= inicio_dt,
        Abastecimento.data_abastecimento <= fim_dt
    )
    if obra_id_int:
        query = query.filter(Abastecimento.obra_id == obra_id_int)
    if frente_filtro:
        query = query.filter(Abastecimento.frente_servico == frente_filtro)

    abastecimentos = query.all()

    total_volume = sum(a.quantidade for a in abastecimentos)
    total_registros = len(abastecimentos)
    dias_periodo = max((fim_dt - inicio_dt).days + 1, 1)
    media_diaria = total_volume / dias_periodo if dias_periodo > 0 else 0.0

    # Frentes disponíveis para filtro
    frentes_query = db.session.query(Abastecimento.frente_servico)\
        .filter(Abastecimento.frente_servico.isnot(None), Abastecimento.frente_servico != '')
    if obra_id_int:
        frentes_query = frentes_query.filter(Abastecimento.obra_id == obra_id_int)
    
    frentes_cadastradas_query = db.session.query(FrenteServico.nome).filter(FrenteServico.ativa == True)
    if obra_id_int:
        frentes_cadastradas_query = frentes_cadastradas_query.filter((FrenteServico.obra_id == obra_id_int) | (FrenteServico.obra_id.is_(None)))

    set_frentes = set(f[0].strip().upper() for f in frentes_query.distinct().all() if f[0] and f[0].strip())
    set_frentes.update(f[0].strip().upper() for f in frentes_cadastradas_query.all() if f[0] and f[0].strip())
    frentes_disponiveis = sorted(list(set_frentes))

    # Agrupamento por Frente de Serviço
    frentes_stats = {}
    for a in abastecimentos:
        nome_f = (a.frente_servico.strip().upper() if a.frente_servico and a.frente_servico.strip() else "GERAL / NÃO INFORMADA")
        if nome_f not in frentes_stats:
            frentes_stats[nome_f] = {
                'nome': nome_f,
                'total_litros': 0.0,
                'qtd_abastecimentos': 0,
                'equipamentos': set(),
                'combustiveis': {}
            }
        frentes_stats[nome_f]['total_litros'] += a.quantidade
        frentes_stats[nome_f]['qtd_abastecimentos'] += 1
        if a.equipamento_id:
            eq_nome = a.equipamento_rel.prefixo_placa if a.equipamento_rel else f"Eq #{a.equipamento_id}"
            frentes_stats[nome_f]['equipamentos'].add(eq_nome)

        c_insumo = a.categoria_insumo or 'DIESEL'
        frentes_stats[nome_f]['combustiveis'][c_insumo] = frentes_stats[nome_f]['combustiveis'].get(c_insumo, 0.0) + a.quantidade

    frentes_lista = sorted(frentes_stats.values(), key=lambda x: x['total_litros'], reverse=True)

    for f in frentes_lista:
        f['percentual'] = (f['total_litros'] / total_volume * 100.0) if total_volume > 0 else 0.0
        f['media_por_abastecimento'] = f['total_litros'] / f['qtd_abastecimentos'] if f['qtd_abastecimentos'] > 0 else 0.0
        f['media_diaria'] = f['total_litros'] / dias_periodo if dias_periodo > 0 else 0.0
        f['qtd_equipamentos'] = len(f['equipamentos'])
        f['lista_equipamentos'] = sorted(list(f['equipamentos']))

    # Série temporal para gráfico
    agrupar_por_mes = dias_periodo > 60
    timeline_dict = {}
    top_frentes_nomes = [f['nome'] for f in frentes_lista[:6]]

    for a in abastecimentos:
        chave_data = a.data_abastecimento.strftime('%Y-%m') if agrupar_por_mes else a.data_abastecimento.strftime('%d/%m')
        nome_f = (a.frente_servico.strip().upper() if a.frente_servico and a.frente_servico.strip() else "GERAL / NÃO INFORMADA")
        if nome_f not in top_frentes_nomes:
            nome_f = "OUTRAS FRENTES"

        if chave_data not in timeline_dict:
            timeline_dict[chave_data] = {}
        timeline_dict[chave_data][nome_f] = timeline_dict[chave_data].get(nome_f, 0.0) + a.quantidade

    labels_grafico = sorted(timeline_dict.keys())
    series_frentes = []
    
    # Ordem de frentes nas séries
    frentes_para_serie = list(top_frentes_nomes)
    if any("OUTRAS FRENTES" in d for d in timeline_dict.values()):
        frentes_para_serie.append("OUTRAS FRENTES")

    for f_nome in frentes_para_serie:
        dados_serie = [round(timeline_dict[lbl].get(f_nome, 0.0), 2) for lbl in labels_grafico]
        if sum(dados_serie) > 0:
            series_frentes.append({
                'name': f_nome,
                'data': dados_serie
            })

    maior_frente = frentes_lista[0] if frentes_lista else None
    total_equipamentos_unicos = len(set(a.equipamento_id for a in abastecimentos if a.equipamento_id))
    obra_sel = Obra.query.get(obra_id_int) if obra_id_int else None

    return render_template(
        'relatorio_media_consumo.html',
        obras_lista=obras_lista,
        obra_sel=obra_sel,
        obra_id_sel=str(obra_id_int) if obra_id_int else '',
        data_inicio=data_inicio_param,
        data_fim=data_fim_param,
        frente_filtro=frente_filtro,
        frentes_disponiveis=frentes_disponiveis,
        total_volume=total_volume,
        total_registros=total_registros,
        dias_periodo=dias_periodo,
        media_diaria=media_diaria,
        total_equipamentos_unicos=total_equipamentos_unicos,
        maior_frente=maior_frente,
        frentes_lista=frentes_lista,
        labels_grafico=labels_grafico,
        series_frentes=series_frentes,
        agrupar_por_mes=agrupar_por_mes
    )