from io import BytesIO
from datetime import datetime
from flask import Response
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus.flowables import HRFlowable


class PDFGenerator:

    @staticmethod
    def exportar_equipamento_pdf(equip, resultados, total_litros, data_inicio, data_fim, usuario_nome):
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(A4),
            leftMargin=1.5*cm, rightMargin=1.5*cm,
            topMargin=1.5*cm, bottomMargin=1.5*cm,
            title=f'Dossiê - {equip.prefixo_placa}',
            author='T.A.N.K - Gestão de Combustíveis'
        )

        styles = getSampleStyleSheet()
        titulo_style = ParagraphStyle('TituloPrincipal', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1F4E79'), spaceAfter=4, alignment=TA_CENTER, fontName='Helvetica-Bold')
        subtitulo_style = ParagraphStyle('Subtitulo', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#666666'), spaceAfter=8, alignment=TA_CENTER)
        value_style = ParagraphStyle('Value', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#1F4E79'), fontName='Helvetica-Bold', leading=13)
        cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#333333'), leading=9)
        header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=7, textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_CENTER, leading=9)
        section_style = ParagraphStyle('SectionTitle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#1F4E79'), fontName='Helvetica-Bold', spaceBefore=10, spaceAfter=6)

        data_ini_format = datetime.strptime(data_inicio, '%Y-%m-%d').strftime('%d/%m/%Y')
        data_fim_format = datetime.strptime(data_fim, '%Y-%m-%d').strftime('%d/%m/%Y')
        data_geracao = datetime.now().strftime('%d/%m/%Y às %H:%M')
        dias_semana = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

        elementos = [
            Paragraph('DOSSIÊ ANALÍTICO DE ABASTECIMENTO', titulo_style),
            Paragraph('Sistema T.A.N.K - Gestão de Combustíveis e Insumos', subtitulo_style),
            HRFlowable(width='100%', thickness=2, color=colors.HexColor('#1F4E79'), spaceAfter=10)
        ]

        info_data = [[
            Paragraph(f'<font color="#666666">Equipamento:</font><br/>{equip.prefixo_placa}', value_style),
            Paragraph(f'<font color="#666666">Tipo:</font><br/>{equip.tipo_equipamento or "N/I"}', value_style),
            Paragraph(f'<font color="#666666">Locador:</font><br/>{equip.locador or "Central"}', value_style),
            Paragraph(f'<font color="#666666">Período:</font><br/>{data_ini_format} a {data_fim_format}', value_style),
            Paragraph(f'<font color="#666666">Total Consumido:</font><br/><font color="#C00000" size="12">{total_litros:,.2f} L</font>', value_style),
        ]]
        info_table = Table(info_data, colWidths=[4.5*cm, 3.5*cm, 5*cm, 5*cm, 4.5*cm])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F0F4F8')),
            ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#2E75B6')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D0D9E4')),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        elementos.append(info_table)
        elementos.append(Spacer(1, 0.4*cm))

        elementos.append(Paragraph('📊 EXTRATO DETALHADO DE ABASTECIMENTOS', section_style))
        cabecalhos = ['Data', 'Dia', 'Fornecedor/Posto', 'Insumo', 'Volume (L)', 'Hodômetro', 'Horímetro', 'Observações']
        dados_tabela = [[Paragraph(h, header_style) for h in cabecalhos]]

        for item in resultados:
            dia_semana = dias_semana[item.data_abastecimento.weekday()]
            forn = item.fornecedor_rel.nome if item.fornecedor_rel else 'N/A'
            dados_tabela.append([
                Paragraph(item.data_abastecimento.strftime('%d/%m/%Y'), cell_style),
                Paragraph(dia_semana, cell_style),
                Paragraph(forn, cell_style),
                Paragraph(item.categoria_insumo, cell_style),
                Paragraph(f'<b>{item.quantidade:,.2f}</b>', cell_style),
                Paragraph(f'{item.hodometro:,.1f} Km' if item.hodometro else '-', cell_style),
                Paragraph(f'{item.horimetro:,.1f} Hr' if item.horimetro else '-', cell_style),
                Paragraph(item.descricao_obs or '-', cell_style),
            ])

        dados_tabela.append([
            Paragraph('', cell_style), Paragraph('', cell_style), Paragraph('', cell_style),
            Paragraph('<b>TOTAL</b>', cell_style),
            Paragraph(f'<font color="#C00000"><b>{total_litros:,.2f}</b></font>', cell_style),
            Paragraph('', cell_style), Paragraph('', cell_style), Paragraph('', cell_style)
        ])

        col_widths = [2*cm, 1.2*cm, 4.5*cm, 2.5*cm, 2*cm, 2.2*cm, 2.2*cm, 6*cm]
        tabela_principal = Table(dados_tabela, colWidths=col_widths, repeatRows=1)
        tabela_principal.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E79')),
            ('PADDING', (0, 0), (-1, 0), 6),
            ('ALIGN', (0, 0), (1, -1), 'CENTER'),
            ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -2), 0.3, colors.HexColor('#D0D9E4')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#D6E4F0')),
            ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor('#1F4E79')),
        ]))
        elementos.append(tabela_principal)

        doc.build(elementos)
        buffer.seek(0)
        nome_arquivo = f'Dossie_{equip.prefixo_placa}_{data_inicio}_{data_fim}.pdf'
        return Response(buffer.getvalue(), mimetype='application/pdf', headers={'Content-Disposition': f'attachment; filename={nome_arquivo}'})

    @staticmethod
    def exportar_locador_pdf(locador_sel, resultados_resumo, lancamentos_detalhados, total_litros, data_inicio, data_fim, usuario_nome):
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=portrait(A4),
            leftMargin=1.2*cm, rightMargin=1.2*cm,
            topMargin=1.2*cm, bottomMargin=1.2*cm,
            title=f'Relatório de Locador - {locador_sel}',
            author='T.A.N.K'
        )

        styles = getSampleStyleSheet()
        titulo_style = ParagraphStyle('TituloLocador', parent=styles['Heading1'], fontSize=14, textColor=colors.HexColor('#1F4E79'), spaceAfter=2, alignment=TA_CENTER, fontName='Helvetica-Bold')
        subtitulo_style = ParagraphStyle('SubtituloLocador', parent=styles['Normal'], fontSize=8.5, textColor=colors.HexColor('#666666'), spaceAfter=5, alignment=TA_CENTER)
        secao_style = ParagraphStyle('SecaoLocador', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#1F4E79'), fontName='Helvetica-Bold', spaceBefore=6, spaceAfter=3)
        card_val_style = ParagraphStyle('CardValue', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#1F4E79'), fontName='Helvetica-Bold', alignment=TA_CENTER, leading=13)
        cell_style = ParagraphStyle('CellLocador', parent=styles['Normal'], fontSize=7.5, textColor=colors.HexColor('#333333'), leading=9)
        cell_center = ParagraphStyle('CellLocadorCenter', parent=styles['Normal'], fontSize=7.5, alignment=TA_CENTER, leading=9)
        cell_right = ParagraphStyle('CellLocadorRight', parent=styles['Normal'], fontSize=7.5, alignment=TA_RIGHT, leading=9)
        header_style = ParagraphStyle('HeaderLocador', parent=styles['Normal'], fontSize=7.5, textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_CENTER, leading=9)
        subtotal_style_left = ParagraphStyle('SubtotalLeft', parent=styles['Normal'], fontSize=7.5, textColor=colors.HexColor('#1F4E79'), fontName='Helvetica-Bold', alignment=TA_LEFT, leading=9)
        subtotal_style_right = ParagraphStyle('SubtotalRight', parent=styles['Normal'], fontSize=7.5, textColor=colors.HexColor('#1F4E79'), fontName='Helvetica-Bold', alignment=TA_RIGHT, leading=9)

        data_ini_format = datetime.strptime(data_inicio, '%Y-%m-%d').strftime('%d/%m/%Y')
        data_fim_format = datetime.strptime(data_fim, '%Y-%m-%d').strftime('%d/%m/%Y')
        data_geracao = datetime.now().strftime('%d/%m/%Y às %H:%M')

        elementos = [
            Paragraph('RELATÓRIO DE CONSUMO POR LOCADOR', titulo_style),
            Paragraph('T.A.N.K - Gestão Estratégica de Combustíveis e Frotas', subtitulo_style),
            HRFlowable(width='100%', thickness=1.5, color=colors.HexColor('#1F4E79'), spaceAfter=6)
        ]

        total_equipamentos = len(resultados_resumo)
        total_abast_geral = sum(r.total_abastecimentos for r in resultados_resumo)

        cards_data = [[
            Paragraph(f'<font color="#666666" size="6.5">Locador</font><br/><b>{locador_sel}</b>', card_val_style),
            Paragraph(f'<font color="#666666" size="6.5">Período</font><br/>{data_ini_format} a {data_fim_format}', card_val_style),
            Paragraph(f'<font color="#666666" size="6.5">Equipamentos</font><br/>{total_equipamentos}', card_val_style),
            Paragraph(f'<font color="#666666" size="6.5">Abastecimentos</font><br/>{total_abast_geral}', card_val_style),
            Paragraph(f'<font color="#666666" size="6.5">Consumo Total</font><br/><font color="#C00000">{total_litros:,.2f} L</font>', card_val_style),
        ]]
        cards_table = Table(cards_data, colWidths=[4.2*cm, 3.8*cm, 3.2*cm, 3.5*cm, 3.9*cm])
        cards_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F0F4F8')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#2E75B6')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D0D9E4')),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        elementos.append(cards_table)
        elementos.append(Spacer(1, 0.3*cm))

        elementos.append(Paragraph('<b>1. Resumo Consolidado por Equipamento</b>', secao_style))
        cabecalhos_res = ['Placa / Prefixo', 'Descrição / Modelo', 'Tipo', 'Abastec.', 'Consumo Total', '% Total']
        dados_tabela_res = [[Paragraph(h, header_style) for h in cabecalhos_res]]

        for r in resultados_resumo:
            perc = (r.total_consumido / total_litros * 100) if total_litros > 0 else 0
            dados_tabela_res.append([
                Paragraph(f'<b>{r.prefixo_placa}</b>', cell_center),
                Paragraph(r.descricao or '-', cell_style),
                Paragraph(r.tipo_equipamento or '-', cell_style),
                Paragraph(str(r.total_abastecimentos), cell_center),
                Paragraph(f'<b>{r.total_consumido:,.2f} L</b>', cell_right),
                Paragraph(f'{perc:.1f}%', cell_center),
            ])

        dados_tabela_res.append([
            Paragraph('<b>TOTAL GERAL</b>', cell_center),
            Paragraph('', cell_style), Paragraph('', cell_style),
            Paragraph(f'<b>{total_abast_geral}</b>', cell_center),
            Paragraph(f'<font color="#C00000"><b>{total_litros:,.2f} L</b></font>', cell_right),
            Paragraph('<b>100.0%</b>', cell_center),
        ])

        tabela_res = Table(dados_tabela_res, colWidths=[3.2*cm, 5.0*cm, 4.0*cm, 2.0*cm, 2.8*cm, 1.6*cm], repeatRows=1)
        tabela_res.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1F4E79')),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -2), 0.3, colors.HexColor('#D0D9E4')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#D6E4F0')),
            ('LINEABOVE', (0, -1), (-1, -1), 1.2, colors.HexColor('#1F4E79')),
        ]))
        elementos.append(tabela_res)

        doc.build(elementos)
        buffer.seek(0)
        nome_arquivo = f'Relatorio_Locador_{locador_sel}_{data_inicio}_{data_fim}.pdf'.replace(' ', '_')
        return Response(buffer.getvalue(), mimetype='application/pdf', headers={'Content-Disposition': f'attachment; filename={nome_arquivo}'})

    @staticmethod
    def exportar_resumo_mensal_pdf(dados, usuario_nome):
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(A4),
            leftMargin=1.2*cm, rightMargin=1.2*cm,
            topMargin=1.2*cm, bottomMargin=1.2*cm,
            title=f"Fechamento Mensal - {dados['nome_mes']} {dados['ano']}",
            author='T.A.N.K - Gestão de Combustíveis'
        )

        styles = getSampleStyleSheet()
        titulo_style = ParagraphStyle('TituloPrincipal', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1E293B'), spaceAfter=2, alignment=TA_CENTER, fontName='Helvetica-Bold')
        subtitulo_style = ParagraphStyle('Subtitulo', parent=styles['Normal'], fontSize=8.5, textColor=colors.HexColor('#64748B'), spaceAfter=6, alignment=TA_CENTER)
        secao_style = ParagraphStyle('Secao', parent=styles['Normal'], fontSize=9.5, textColor=colors.HexColor('#1E3A8A'), fontName='Helvetica-Bold', spaceBefore=6, spaceAfter=3)
        header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=7.5, textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_CENTER, leading=9)
        cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#333333'), leading=9)
        cell_center = ParagraphStyle('CellCenter', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#333333'), alignment=TA_CENTER, leading=9)
        cell_right = ParagraphStyle('CellRight', parent=styles['Normal'], fontSize=7, textColor=colors.HexColor('#333333'), alignment=TA_RIGHT, leading=9)

        obra_nome = dados['obra'].nome if dados['obra'] else 'Todas as Obras'
        obra_cod = dados['obra'].codigo if dados['obra'] else 'GLOBAL'
        nome_mes = dados['nome_mes']
        ano = dados['ano']
        mes = dados['mes']
        nome_mes_ant = dados['nome_mes_anterior']

        elementos = [
            Paragraph(f'FECHAMENTO MENSAL DE COMBUSTÍVEIS — {nome_mes.upper()} / {ano}', titulo_style),
            Paragraph(f'Sistema T.A.N.K • Obra: <b>{obra_cod} - {obra_nome}</b> • Emissão: {datetime.now().strftime("%d/%m/%Y %H:%M")} por {usuario_nome}', subtitulo_style),
            HRFlowable(width='100%', thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=6)
        ]

        # 1. Resumo por Combustível
        elementos.append(Paragraph('<b>1. Balanço Consolidado por Combustível</b>', secao_style))
        cabecalhos_comb = ['Combustível', f'Saldo Inicial ({nome_mes_ant})', '(+) Entradas NF', '(+/-) Transb.', '(-) Saídas (Abast.)', '(=) Saldo Final', 'Capacidade', '% Ocupação']
        tabela_comb_data = [[Paragraph(h, header_style) for h in cabecalhos_comb]]

        for c in dados['resumo_combustiveis']:
            tabela_comb_data.append([
                Paragraph(f"<b>{c['tipo']}</b>", cell_style),
                Paragraph(f"{c['saldo_anterior']:,.2f} L", cell_right),
                Paragraph(f"{c['entradas_nf']:,.2f} L", cell_right),
                Paragraph(f"{c['transf_liquida']:,.2f} L", cell_right),
                Paragraph(f"{c['saidas']:,.2f} L", cell_right),
                Paragraph(f"<b>{c['saldo_final']:,.2f} L</b>", cell_right),
                Paragraph(f"{c['capacidade']:,.2f} L", cell_right),
                Paragraph(f"{c['percentual']:.1f}%", cell_center),
            ])

        # Totais
        tot = dados['totais']
        perc_tot = (tot['saldo_final'] / tot['capacidade_total'] * 100) if tot['capacidade_total'] > 0 else 0
        tabela_comb_data.append([
            Paragraph('<b>TOTAL GERAL</b>', cell_style),
            Paragraph(f"<b>{tot['saldo_anterior']:,.2f} L</b>", cell_right),
            Paragraph(f"<b>{tot['entradas']:,.2f} L</b>", cell_right),
            Paragraph(f"<b>{(tot['transf_rec'] - tot['transf_env']):,.2f} L</b>", cell_right),
            Paragraph(f"<b>{tot['saidas']:,.2f} L</b>", cell_right),
            Paragraph(f"<font color='#1E40AF'><b>{tot['saldo_final']:,.2f} L</b></font>", cell_right),
            Paragraph(f"<b>{tot['capacidade_total']:,.2f} L</b>", cell_right),
            Paragraph(f"<b>{perc_tot:.1f}%</b>", cell_center),
        ])

        t_comb = Table(tabela_comb_data, colWidths=[4.2*cm, 3.5*cm, 3.3*cm, 2.8*cm, 3.5*cm, 3.8*cm, 3.5*cm, 2.7*cm], repeatRows=1)
        t_comb.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
            ('PADDING', (0, 0), (-1, -1), 3.5),
            ('GRID', (0, 0), (-1, -2), 0.3, colors.HexColor('#CBD5E1')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F1F5F9')),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.HexColor('#1E293B')),
        ]))
        elementos.append(t_comb)
        elementos.append(Spacer(1, 0.3*cm))

        # 2. Balanço Físico por Tanque / Comboio
        elementos.append(Paragraph('<b>2. Balanço Físico por Tanque e Comboio Móvel</b>', secao_style))
        cabecalhos_tanq = ['Tanque / Comboio', 'Tipo', 'Combustível', f'Saldo Inicial ({nome_mes_ant})', '(+) NF', '(+) Transb.', '(-) Saídas', '(-) Transb.', '(=) Saldo Final', '%']
        tabela_tanq_data = [[Paragraph(h, header_style) for h in cabecalhos_tanq]]

        for t in dados['balanco_tanques']:
            tabela_tanq_data.append([
                Paragraph(f"<b>{t['nome']}</b>", cell_style),
                Paragraph(t['categoria'], cell_center),
                Paragraph(t['tipo_combustivel'], cell_center),
                Paragraph(f"{t['saldo_anterior']:,.1f}", cell_right),
                Paragraph(f"{t['entradas_nf']:,.1f}", cell_right),
                Paragraph(f"{t['transf_rec']:,.1f}", cell_right),
                Paragraph(f"{t['saidas']:,.1f}", cell_right),
                Paragraph(f"{t['transf_env']:,.1f}", cell_right),
                Paragraph(f"<b>{t['saldo_final']:,.1f}</b>", cell_right),
                Paragraph(f"{t['percentual']:.0f}%", cell_center),
            ])

        t_tanq = Table(tabela_tanq_data, colWidths=[5.0*cm, 2.0*cm, 2.8*cm, 2.8*cm, 2.4*cm, 2.4*cm, 2.6*cm, 2.4*cm, 3.2*cm, 1.7*cm], repeatRows=1)
        t_tanq.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563EB')),
            ('PADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#CBD5E1')),
        ]))
        elementos.append(t_tanq)
        elementos.append(Spacer(1, 0.3*cm))

        # 3. Notas Fiscais Recebidas
        if dados['entradas_nfs']:
            elementos.append(Paragraph(f"<b>3. Notas Fiscais Recebidas no Mês ({len(dados['entradas_nfs'])} NFs)</b>", secao_style))
            cabecalhos_nf = ['Data', 'Nº NF', 'Fornecedor / Destino', 'Combustível / Insumo', 'Volume (L/Kg)', 'Cadastrado Por']
            tabela_nf_data = [[Paragraph(h, header_style) for h in cabecalhos_nf]]

            for nf in dados['entradas_nfs']:
                tabela_nf_data.append([
                    Paragraph(nf.data_entrada.strftime('%d/%m/%Y'), cell_center),
                    Paragraph(nf.numero_nf or 'S/N', cell_center),
                    Paragraph(nf.fornecedor_rel.nome if nf.fornecedor_rel else '-', cell_style),
                    Paragraph(nf.categoria_insumo, cell_style),
                    Paragraph(f"<b>{nf.quantidade:,.2f} L</b>", cell_right),
                    Paragraph(nf.usuario_rel.nome if nf.usuario_rel else '-', cell_style),
                ])

            t_nf = Table(tabela_nf_data, colWidths=[2.5*cm, 3.0*cm, 7.5*cm, 5.0*cm, 4.0*cm, 5.3*cm], repeatRows=1)
            t_nf.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#059669')),
                ('PADDING', (0, 0), (-1, -1), 3),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#CBD5E1')),
            ]))
            elementos.append(t_nf)

        doc.build(elementos)
        buffer.seek(0)
        nome_arq = f"Fechamento_Mensal_{obra_cod}_{ano}_{mes:02d}.pdf".replace(' ', '_')
        return Response(buffer.getvalue(), mimetype='application/pdf', headers={'Content-Disposition': f'attachment; filename={nome_arq}'})

