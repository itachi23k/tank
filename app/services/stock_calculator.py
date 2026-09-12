"""
Serviço de cálculo e consolidação de estoque e movimentações em lote.
Elimina o problema de N+1 queries.
"""
from collections import defaultdict
from sqlalchemy import func
from app import db
from app.models import Fornecedor, EntradaInsumo, Abastecimento, Transferencia


class StockCalculator:

    @staticmethod
    def parse_data_brasileira(data_str):
        """
        Converte string de data no formato brasileiro (DD/MM/AAAA) ou ISO (AAAA-MM-DD) para date.
        """
        from datetime import date, datetime
        if not data_str:
            return date.today()
        if isinstance(data_str, date) and not isinstance(data_str, datetime):
            return data_str
        if isinstance(data_str, datetime):
            return data_str.date()
        data_str = str(data_str).strip()
        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d.%m.%Y'):
            try:
                return datetime.strptime(data_str, fmt).date()
            except ValueError:
                continue
        return date.today()

    @classmethod
    def obter_saldos_tanques_lote(cls, fornecedor_ids=None, obra_ids=None, data_referencia=None):
        """
        Calcula o saldo de múltiplos fornecedores/tanques até a data_referencia (inclusive)
        em apenas 4 queries agregadas.
        Retorna:
            saldos (dict): {fornecedor_id: saldo_atual}
            tanques (list): lista de objetos Fornecedor
        """
        from datetime import date, datetime
        query_forn = Fornecedor.query.filter_by(ativo=True, tipo_origem='Interno')
        if fornecedor_ids:
            query_forn = query_forn.filter(Fornecedor.id.in_(fornecedor_ids))
        if obra_ids:
            query_forn = query_forn.filter(Fornecedor.obra_id.in_(obra_ids))
            
        tanques = query_forn.all()
        if not tanques:
            return {}, []

        ids = [t.id for t in tanques]

        data_ref = None
        if data_referencia:
            data_ref = cls.parse_data_brasileira(data_referencia)

        # 1. Total de Entradas por NF em lote (até a data de referência)
        query_ent = db.session.query(
            EntradaInsumo.fornecedor_id,
            func.coalesce(func.sum(EntradaInsumo.quantidade), 0.0)
        ).filter(EntradaInsumo.fornecedor_id.in_(ids))
        if data_ref:
            query_ent = query_ent.filter(EntradaInsumo.data_entrada <= data_ref)
        entradas = dict(query_ent.group_by(EntradaInsumo.fornecedor_id).all())

        # 2. Total de Saídas (Abastecimentos) em lote (até a data de referência)
        query_sai = db.session.query(
            Abastecimento.fornecedor_id,
            func.coalesce(func.sum(Abastecimento.quantidade), 0.0)
        ).filter(Abastecimento.fornecedor_id.in_(ids))
        if data_ref:
            query_sai = query_sai.filter(Abastecimento.data_abastecimento <= data_ref)
        saidas = dict(query_sai.group_by(Abastecimento.fornecedor_id).all())

        # 3. Total de Transbordos Recebidos em lote (até a data de referência)
        query_transf_rec = db.session.query(
            Transferencia.destino_id,
            func.coalesce(func.sum(Transferencia.litros), 0.0)
        ).filter(Transferencia.destino_id.in_(ids))
        if data_ref:
            query_transf_rec = query_transf_rec.filter(func.date(Transferencia.data_hora) <= data_ref)
        transf_rec = dict(query_transf_rec.group_by(Transferencia.destino_id).all())

        # 4. Total de Transbordos Enviados em lote (até a data de referência)
        query_transf_env = db.session.query(
            Transferencia.origem_id,
            func.coalesce(func.sum(Transferencia.litros), 0.0)
        ).filter(Transferencia.origem_id.in_(ids))
        if data_ref:
            query_transf_env = query_transf_env.filter(func.date(Transferencia.data_hora) <= data_ref)
        transf_env = dict(query_transf_env.group_by(Transferencia.origem_id).all())

        # Cálculo do saldo final consolidado em memória
        saldos = {}
        for t in tanques:
            est_ini = t.estoque_inicial or 0.0
            ent = entradas.get(t.id, 0.0)
            sai = saidas.get(t.id, 0.0)
            rec = transf_rec.get(t.id, 0.0)
            env = transf_env.get(t.id, 0.0)
            saldos[t.id] = est_ini + ent + rec - sai - env

        return saldos, tanques

    @classmethod
    def calcular_dados_obras_whatsapp(cls, obras_visiveis, data_referencia=None):
        """
        Calcula e estrutura os dados de tanques fixos, comboios móveis e resumos para o WhatsApp
        com suporte a filtro por data de referência.
        """
        from app.services.whatsapp_oficial import WhatsAppOficial

        wpp = WhatsAppOficial()
        data_ref = cls.parse_data_brasileira(data_referencia)
        data_atual = data_ref.strftime('%d/%m/%Y')

        if not obras_visiveis:
            return [], data_atual, ""

        obra_ids = [o.id for o in obras_visiveis]
        saldos_map, tanques = cls.obter_saldos_tanques_lote(obra_ids=obra_ids, data_referencia=data_ref)

        tanques_por_obra = defaultdict(list)
        for t in tanques:
            tanques_por_obra[t.obra_id].append(t)

        obras_dados = []
        textos_obras = []

        for obra in obras_visiveis:
            tanques_obra = tanques_por_obra.get(obra.id, [])
            tanques_fixos = []
            comboios_moveis = []
            tanques_dados = []
            resumo_por_tipo = defaultdict(lambda: {'disponivel': 0.0, 'capacidade': 0.0})

            for t in tanques_obra:
                saldo = saldos_map.get(t.id, 0.0)
                capacidade = t.capacidade_litros or 0.0
                percentual = (saldo / capacidade * 100) if capacidade > 0 else 0.0
                tipo = (t.tipo_combustivel or 'DIESEL S10').strip().upper()
                categoria = (t.categoria_tanque or 'Tanque').strip()

                item = {
                    'id': t.id,
                    'nome': t.nome,
                    'tipo': tipo,
                    'tipo_combustivel': tipo,
                    'categoria': categoria,
                    'saldo': saldo,
                    'capacidade': capacidade,
                    'percentual': min(max(percentual, 0.0), 100.0),
                    'estoque_inicial': t.estoque_inicial or 0.0
                }

                tanques_dados.append(item)
                if categoria.lower() == 'comboio':
                    comboios_moveis.append(item)
                else:
                    tanques_fixos.append(item)

                resumo_por_tipo[tipo]['disponivel'] += saldo
                resumo_por_tipo[tipo]['capacidade'] += capacidade

            canteiro_tipos_map = defaultdict(float)
            for tf in tanques_fixos:
                canteiro_tipos_map[tf['tipo']] += tf['saldo']

            resumo_canteiro = [{'tipo': k, 'saldo': v} for k, v in sorted(canteiro_tipos_map.items())]
            resumo_comboios = [{'nome': c['nome'], 'tipo': c['tipo'], 'saldo': c['saldo']} for c in comboios_moveis]
            
            resumo_tipos = []
            for k, v in sorted(resumo_por_tipo.items()):
                perc = (v['disponivel'] / v['capacidade'] * 100) if v['capacidade'] > 0 else 0.0
                resumo_tipos.append({
                    'nome': k,
                    'disponivel': v['disponivel'],
                    'percentual': min(max(perc, 0.0), 100.0)
                })

            msg_obra = wpp.montar_relatorio_diario(obra, tanques_fixos, comboios_moveis, resumo_por_tipo, data_formatada=data_atual)
            params_template = wpp.montar_parametros_template_obra(obra, tanques_fixos, comboios_moveis, resumo_por_tipo, data_formatada=data_atual)

            obras_dados.append({
                'obra': obra,
                'tanques': tanques_dados,
                'tanques_fixos': tanques_fixos,
                'comboios': comboios_moveis,
                'comboios_moveis': comboios_moveis,
                'resumo_canteiro': resumo_canteiro,
                'resumo_comboios': resumo_comboios,
                'resumo_tipos': resumo_tipos,
                'total_tanques': len(tanques_obra),
                'total_tanques_fixos': len(tanques_fixos),
                'total_comboios': len(comboios_moveis),
                'mensagem_texto': msg_obra,
                'params_template': params_template
            })
            textos_obras.append(msg_obra)

        texto_geral = "\n\n".join(textos_obras)
        return obras_dados, data_atual, texto_geral

    @classmethod
    def obter_meses_disponiveis(cls, obra_id=None):
        """
        Retorna lista de tuplas (ano, mes, rotulo_formatado) ordenadas do mais recente ao mais antigo.
        """
        import calendar
        from datetime import date
        from app.models import Obra

        min_e = db.session.query(func.min(EntradaInsumo.data_entrada))
        max_e = db.session.query(func.max(EntradaInsumo.data_entrada))
        min_s = db.session.query(func.min(Abastecimento.data_abastecimento))
        max_s = db.session.query(func.max(Abastecimento.data_abastecimento))

        if obra_id:
            min_e = min_e.filter(EntradaInsumo.obra_id == obra_id)
            max_e = max_e.filter(EntradaInsumo.obra_id == obra_id)
            min_s = min_s.filter(Abastecimento.obra_id == obra_id)
            max_s = max_s.filter(Abastecimento.obra_id == obra_id)

        datas = [d for d in [min_e.scalar(), max_e.scalar(), min_s.scalar(), max_s.scalar()] if d]
        
        hoje = date.today()
        if not datas:
            datas = [hoje]

        data_min = min(datas)
        data_max = max(datas)
        if data_max < hoje:
            data_max = hoje

        nomes_meses = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                       'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']

        meses = []
        ano, mes = data_max.year, data_max.month
        while (ano, mes) >= (data_min.year, data_min.month):
            meses.append((ano, mes, f"{nomes_meses[mes]} / {ano}"))
            mes -= 1
            if mes == 0:
                mes = 12
                ano -= 1

        return meses

    @classmethod
    def calcular_fechamento_mensal(cls, obra_id, ano, mes):
        """
        Calcula o fechamento mensal exato de uma obra para o mês/ano especificado:
        - Saldo anterior (disponível no final do mês anterior / início do mês selecionado)
        - Entradas por Nota Fiscal no mês
        - Saídas por Abastecimento no mês
        - Transbordos (recebidos e enviados) no mês
        - Saldo final (disponível no final do mês selecionado)
        - Detalhes de NFs, consumo por equipamento e por locador
        """
        import calendar
        from datetime import date
        from app.models import Obra, Equipamento

        nomes_meses = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
                       'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']

        data_inicio = date(ano, mes, 1)
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        data_fim = date(ano, mes, ultimo_dia)

        # Mês anterior
        mes_ant = 12 if mes == 1 else mes - 1
        ano_ant = ano - 1 if mes == 1 else ano
        nome_mes_anterior = f"{nomes_meses[mes_ant]}/{ano_ant}"

        # Mês seguinte
        mes_prox = 1 if mes == 12 else mes + 1
        ano_prox = ano + 1 if mes == 12 else ano

        obra = Obra.query.get(obra_id) if obra_id else None

        # 1. Tanques e comboios da obra
        query_tanques = Fornecedor.query.filter_by(ativo=True, tipo_origem='Interno')
        if obra:
            query_tanques = query_tanques.filter(Fornecedor.obra_id == obra.id)
        
        tanques = query_tanques.order_by(Fornecedor.categoria_tanque.desc(), Fornecedor.nome).all()
        tanque_ids = [t.id for t in tanques]

        if not tanque_ids:
            return {
                'obra': obra,
                'ano': ano,
                'mes': mes,
                'nome_mes': nomes_meses[mes],
                'nome_mes_anterior': nome_mes_anterior,
                'data_inicio': data_inicio,
                'data_fim': data_fim,
                'mes_ant': mes_ant,
                'ano_ant': ano_ant,
                'mes_prox': mes_prox,
                'ano_prox': ano_prox,
                'resumo_combustiveis': [],
                'balanco_tanques': [],
                'entradas_nfs': [],
                'consumo_equipamentos': [],
                'consumo_locadores': [],
                'totais': {
                    'saldo_anterior': 0.0,
                    'entradas': 0.0,
                    'transf_rec': 0.0,
                    'saidas': 0.0,
                    'transf_env': 0.0,
                    'saldo_final': 0.0,
                    'variacao_mes': 0.0,
                    'capacidade_total': 0.0
                }
            }

        # 2. Histórico ACUMULADO anterior ao mês (< data_inicio)
        entradas_ant = dict(
            db.session.query(
                EntradaInsumo.fornecedor_id,
                func.coalesce(func.sum(EntradaInsumo.quantidade), 0.0)
            ).filter(EntradaInsumo.fornecedor_id.in_(tanque_ids), EntradaInsumo.data_entrada < data_inicio)
            .group_by(EntradaInsumo.fornecedor_id).all()
        )

        saidas_ant = dict(
            db.session.query(
                Abastecimento.fornecedor_id,
                func.coalesce(func.sum(Abastecimento.quantidade), 0.0)
            ).filter(Abastecimento.fornecedor_id.in_(tanque_ids), Abastecimento.data_abastecimento < data_inicio)
            .group_by(Abastecimento.fornecedor_id).all()
        )

        transf_rec_ant = dict(
            db.session.query(
                Transferencia.destino_id,
                func.coalesce(func.sum(Transferencia.litros), 0.0)
            ).filter(Transferencia.destino_id.in_(tanque_ids), func.date(Transferencia.data_hora) < data_inicio)
            .group_by(Transferencia.destino_id).all()
        )

        transf_env_ant = dict(
            db.session.query(
                Transferencia.origem_id,
                func.coalesce(func.sum(Transferencia.litros), 0.0)
            ).filter(Transferencia.origem_id.in_(tanque_ids), func.date(Transferencia.data_hora) < data_inicio)
            .group_by(Transferencia.origem_id).all()
        )

        # 3. Movimentações NO MÊS [data_inicio, data_fim]
        entradas_mes = dict(
            db.session.query(
                EntradaInsumo.fornecedor_id,
                func.coalesce(func.sum(EntradaInsumo.quantidade), 0.0)
            ).filter(EntradaInsumo.fornecedor_id.in_(tanque_ids), EntradaInsumo.data_entrada >= data_inicio, EntradaInsumo.data_entrada <= data_fim)
            .group_by(EntradaInsumo.fornecedor_id).all()
        )

        saidas_mes = dict(
            db.session.query(
                Abastecimento.fornecedor_id,
                func.coalesce(func.sum(Abastecimento.quantidade), 0.0)
            ).filter(Abastecimento.fornecedor_id.in_(tanque_ids), Abastecimento.data_abastecimento >= data_inicio, Abastecimento.data_abastecimento <= data_fim)
            .group_by(Abastecimento.fornecedor_id).all()
        )

        transf_rec_mes = dict(
            db.session.query(
                Transferencia.destino_id,
                func.coalesce(func.sum(Transferencia.litros), 0.0)
            ).filter(Transferencia.destino_id.in_(tanque_ids), func.date(Transferencia.data_hora) >= data_inicio, func.date(Transferencia.data_hora) <= data_fim)
            .group_by(Transferencia.destino_id).all()
        )

        transf_env_mes = dict(
            db.session.query(
                Transferencia.origem_id,
                func.coalesce(func.sum(Transferencia.litros), 0.0)
            ).filter(Transferencia.origem_id.in_(tanque_ids), func.date(Transferencia.data_hora) >= data_inicio, func.date(Transferencia.data_hora) <= data_fim)
            .group_by(Transferencia.origem_id).all()
        )

        # 4. Construção do Balanço por Tanque
        balanco_tanques = []
        combustiveis_map = defaultdict(lambda: {
            'saldo_anterior': 0.0,
            'entradas_nf': 0.0,
            'transf_rec': 0.0,
            'saidas': 0.0,
            'transf_env': 0.0,
            'saldo_final': 0.0,
            'capacidade': 0.0,
            'tanques': []
        })

        tot_saldo_ant = 0.0
        tot_entradas = 0.0
        tot_transf_rec = 0.0
        tot_saidas = 0.0
        tot_transf_env = 0.0
        tot_saldo_fim = 0.0
        tot_capacidade = 0.0

        for t in tanques:
            tipo_comb = (t.tipo_combustivel or 'DIESEL S10').strip().upper()
            capacidade = t.capacidade_litros or 0.0

            # Saldo disponível no início do mês (final do mês anterior)
            saldo_ant = (t.estoque_inicial or 0.0) + entradas_ant.get(t.id, 0.0) + transf_rec_ant.get(t.id, 0.0) - saidas_ant.get(t.id, 0.0) - transf_env_ant.get(t.id, 0.0)

            ent = entradas_mes.get(t.id, 0.0)
            sai = saidas_mes.get(t.id, 0.0)
            rec = transf_rec_mes.get(t.id, 0.0)
            env = transf_env_mes.get(t.id, 0.0)

            saldo_fim = saldo_ant + ent + rec - sai - env
            perc_ocup = (saldo_fim / capacidade * 100) if capacidade > 0 else 0.0

            item_t = {
                'id': t.id,
                'nome': t.nome,
                'categoria': t.categoria_tanque or 'Tanque',
                'tipo_combustivel': tipo_comb,
                'capacidade': capacidade,
                'saldo_anterior': saldo_ant,
                'entradas_nf': ent,
                'transf_rec': rec,
                'saidas': sai,
                'transf_env': env,
                'variacao_mes': ent + rec - sai - env,
                'saldo_final': saldo_fim,
                'percentual': min(max(perc_ocup, 0.0), 100.0)
            }
            balanco_tanques.append(item_t)

            # Acumular no combustível
            comb = combustiveis_map[tipo_comb]
            comb['saldo_anterior'] += saldo_ant
            comb['entradas_nf'] += ent
            comb['transf_rec'] += rec
            comb['saidas'] += sai
            comb['transf_env'] += env
            comb['saldo_final'] += saldo_fim
            comb['capacidade'] += capacidade
            comb['tanques'].append(item_t)

            # Totais gerais
            tot_saldo_ant += saldo_ant
            tot_entradas += ent
            tot_transf_rec += rec
            tot_saidas += sai
            tot_transf_env += env
            tot_saldo_fim += saldo_fim
            tot_capacidade += capacidade

        # 5. Lista de Resumo por Combustível
        resumo_combustiveis = []
        for tipo, c in sorted(combustiveis_map.items()):
            perc = (c['saldo_final'] / c['capacidade'] * 100) if c['capacidade'] > 0 else 0.0
            var = c['entradas_nf'] + c['transf_rec'] - c['saidas'] - c['transf_env']
            resumo_combustiveis.append({
                'tipo': tipo,
                'saldo_anterior': c['saldo_anterior'],
                'entradas_nf': c['entradas_nf'],
                'transf_rec': c['transf_rec'],
                'saidas': c['saidas'],
                'transf_env': c['transf_env'],
                'transf_liquida': c['transf_rec'] - c['transf_env'],
                'variacao_mes': var,
                'saldo_final': c['saldo_final'],
                'capacidade': c['capacidade'],
                'percentual': min(max(perc, 0.0), 100.0),
                'tanques': c['tanques']
            })

        # 6. Entradas detalhadas de NFs no mês
        query_nfs = EntradaInsumo.query.filter(
            EntradaInsumo.data_entrada >= data_inicio,
            EntradaInsumo.data_entrada <= data_fim
        )
        if obra:
            query_nfs = query_nfs.filter(
                db.or_(
                    EntradaInsumo.obra_id == obra.id,
                    EntradaInsumo.fornecedor_id.in_(tanque_ids)
                )
            )
        else:
            query_nfs = query_nfs.filter(EntradaInsumo.fornecedor_id.in_(tanque_ids))
            
        entradas_nfs = query_nfs.order_by(EntradaInsumo.data_entrada.asc(), EntradaInsumo.id.asc()).all()

        # 7. Consumo detalhado por Equipamento no mês
        query_equip = db.session.query(
            Equipamento.prefixo_placa,
            Equipamento.descricao,
            Equipamento.tipo_equipamento,
            Equipamento.locador,
            Abastecimento.categoria_insumo,
            func.sum(Abastecimento.quantidade).label('total_litros'),
            func.count(Abastecimento.id).label('total_abastecimentos')
        ).join(Equipamento, Abastecimento.equipamento_id == Equipamento.id)\
         .filter(
             Abastecimento.data_abastecimento >= data_inicio,
             Abastecimento.data_abastecimento <= data_fim
         )
        
        if obra:
            query_equip = query_equip.filter(Abastecimento.obra_id == obra.id)
        else:
            query_equip = query_equip.filter(Abastecimento.fornecedor_id.in_(tanque_ids))

        consumo_equipamentos = query_equip.group_by(
            Equipamento.id, Abastecimento.categoria_insumo
        ).order_by(func.sum(Abastecimento.quantidade).desc()).all()

        # 8. Consumo agrupado por Locador no mês
        query_loc = db.session.query(
            func.coalesce(Equipamento.locador, 'NÃO INFORMADO').label('locador'),
            func.sum(Abastecimento.quantidade).label('total_litros'),
            func.count(Abastecimento.id).label('total_abastecimentos')
        ).join(Equipamento, Abastecimento.equipamento_id == Equipamento.id)\
         .filter(
             Abastecimento.data_abastecimento >= data_inicio,
             Abastecimento.data_abastecimento <= data_fim
         )
        if obra:
            query_loc = query_loc.filter(Abastecimento.obra_id == obra.id)
        else:
            query_loc = query_loc.filter(Abastecimento.fornecedor_id.in_(tanque_ids))

        consumo_locadores = query_loc.group_by(Equipamento.locador).order_by(func.sum(Abastecimento.quantidade).desc()).all()

        return {
            'obra': obra,
            'ano': ano,
            'mes': mes,
            'nome_mes': nomes_meses[mes],
            'nome_mes_anterior': nome_mes_anterior,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'mes_ant': mes_ant,
            'ano_ant': ano_ant,
            'mes_prox': mes_prox,
            'ano_prox': ano_prox,
            'resumo_combustiveis': resumo_combustiveis,
            'balanco_tanques': balanco_tanques,
            'entradas_nfs': entradas_nfs,
            'consumo_equipamentos': consumo_equipamentos,
            'consumo_locadores': consumo_locadores,
            'totais': {
                'saldo_anterior': tot_saldo_ant,
                'entradas': tot_entradas,
                'transf_rec': tot_transf_rec,
                'saidas': tot_saidas,
                'transf_env': tot_transf_env,
                'saldo_final': tot_saldo_fim,
                'variacao_mes': tot_entradas + tot_transf_rec - tot_saidas - tot_transf_env,
                'capacidade_total': tot_capacidade
            }
        }

