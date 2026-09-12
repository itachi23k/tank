from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Equipamento, Fornecedor, Abastecimento, EntradaInsumo, Transferencia, Obra, AlocacaoFrenteEquipamento
from app.routes.auth import lancador_required, admin_required
from app.services.csv_importer import CsvImporterService
from app.utils import parse_float_ptbr, normalizar_combustivel, validar_compatibilidade_posto, obter_ultimas_leituras_equipamentos

operacoes_bp = Blueprint('operacoes', __name__)


# ==========================================
# LANÇAMENTOS EM LOTE (ABASTECIMENTOS)
# ==========================================
@operacoes_bp.route('/lancamento', methods=['GET', 'POST'])
@lancador_required
def lancamento():
    if request.method == 'POST':
        try:
            data_str = request.form.get('data_abastecimento')
            obra_id = request.form.get('obra_id')
            if not data_str:
                flash('Data do abastecimento é obrigatória.', 'danger')
                return redirect(url_for('operacoes.lancamento'))

            try:
                data_abast = datetime.strptime(data_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Formato de data inválido. Utilize o formato correto.', 'danger')
                return redirect(url_for('operacoes.lancamento'))

            obra = Obra.query.filter_by(id=int(obra_id) if obra_id else None, ativa=True).first()

            if not obra or (not current_user.is_global and obra.id != current_user.obra_padrao_id):
                flash('Selecione uma obra ativa permitida para o seu usuário.', 'danger')
                return redirect(url_for('operacoes.lancamento'))

            equip_ids = request.form.getlist('equipamento_id[]')
            forn_ids = request.form.getlist('fornecedor_id[]')
            categorias = request.form.getlist('categoria_insumo[]')
            quantidades_str = request.form.getlist('quantidade[]')
            hodometros_str = request.form.getlist('hodometro[]')
            horimetros_str = request.form.getlist('horimetro[]')
            observacoes = request.form.getlist('descricao_obs[]')
            frentes_servico = request.form.getlist('frente_servico[]')

            if not equip_ids:
                flash('Adicione pelo menos uma linha de lançamento.', 'warning')
                return redirect(url_for('operacoes.lancamento'))

            total_processados = 0
            erros = []
            alertas = []

            equip_map = {e.id: e for e in Equipamento.query.filter(Equipamento.id.in_([int(x) for x in equip_ids if x]), Equipamento.ativo == True).all()}
            forn_map = {f.id: f for f in Fornecedor.query.filter(Fornecedor.id.in_([int(x) for x in forn_ids if x]), Fornecedor.ativo == True).all()}
            leituras_atuais = obter_ultimas_leituras_equipamentos()

            for i in range(len(equip_ids)):
                try:
                    # Ignora linhas totalmente vazias (ex: usuário adicionou uma linha a mais por engano)
                    tem_algo = any([
                        equip_ids[i] if i < len(equip_ids) else None,
                        forn_ids[i] if i < len(forn_ids) else None,
                        quantidades_str[i] if i < len(quantidades_str) else None,
                        hodometros_str[i] if i < len(hodometros_str) else None,
                        horimetros_str[i] if i < len(horimetros_str) else None
                    ])
                    if not tem_algo:
                        continue

                    with db.session.begin_nested():
                        if not equip_ids[i] or not forn_ids[i] or not categorias[i] or not quantidades_str[i]:
                            erros.append(f'Linha {i+1}: Equipamento, Insumo, Posto e Quantidade são obrigatórios.')
                            continue

                        equip_id = int(equip_ids[i])
                        forn_id = int(forn_ids[i])
                        categoria = normalizar_combustivel(categorias[i])
                        equipamento = equip_map.get(equip_id)
                        fornecedor = forn_map.get(forn_id)

                        if not equipamento:
                            erros.append(f'Linha {i+1}: equipamento inativo ou inválido.')
                            continue
                        if not fornecedor:
                            erros.append(f'Linha {i+1}: posto inativo ou inválido.')
                            continue
                        if fornecedor.obra_id is not None and fornecedor.obra_id != obra.id:
                            erros.append(f'Linha {i+1}: o posto "{fornecedor.nome}" não pertence à obra selecionada.')
                            continue

                        compativel, motivo = validar_compatibilidade_posto(fornecedor, categoria)
                        if not compativel:
                            erros.append(f'Linha {i+1}: {motivo}')
                            continue

                        quantidade = parse_float_ptbr(quantidades_str[i], campo_nome=f"Linha {i+1} (Quantidade)", positivo=True, permitir_nulo=False)

                        hodo_raw = hodometros_str[i] if i < len(hodometros_str) else None
                        hori_raw = horimetros_str[i] if i < len(horimetros_str) else None
                        hodo_val = parse_float_ptbr(hodo_raw, campo_nome=f"Linha {i+1} (Hodômetro)", permitir_nulo=True)
                        hori_val = parse_float_ptbr(hori_raw, campo_nome=f"Linha {i+1} (Horímetro)", permitir_nulo=True)

                        if hodo_val is not None and hodo_val < 0:
                            erros.append(f'Linha {i+1}: hodômetro não pode ser negativo.')
                            continue
                        if hori_val is not None and hori_val < 0:
                            erros.append(f'Linha {i+1}: horímetro não pode ser negativo.')
                            continue

                        # Checagem de conferência de leitura anterior
                        ultima_leit = leituras_atuais.get(equip_id, {})
                        if hodo_val is not None and ultima_leit.get('hodometro') is not None:
                            if hodo_val < ultima_leit['hodometro']:
                                alertas.append(f"Aviso Linha {i+1} ({equipamento.prefixo_placa}): Hodômetro ({hodo_val:.1f}) inferior ao anterior ({ultima_leit['hodometro']:.1f}).")
                        if hori_val is not None and ultima_leit.get('horimetro') is not None:
                            if hori_val < ultima_leit['horimetro']:
                                alertas.append(f"Aviso Linha {i+1} ({equipamento.prefixo_placa}): Horímetro ({hori_val:.1f}) inferior ao anterior ({ultima_leit['horimetro']:.1f}).")

                        obs = observacoes[i].strip().upper() if i < len(observacoes) else ''
                        frente = frentes_servico[i].strip().upper() if i < len(frentes_servico) and frentes_servico[i] else None

                        if not frente:
                            aloc = AlocacaoFrenteEquipamento.query.filter(
                                AlocacaoFrenteEquipamento.equipamento_id == equip_id,
                                AlocacaoFrenteEquipamento.data_inicio <= data_abast,
                                AlocacaoFrenteEquipamento.data_fim >= data_abast
                            ).first()
                            if aloc and aloc.frente_rel:
                                frente = aloc.frente_rel.nome

                        db.session.add(Abastecimento(
                            data_abastecimento=data_abast, categoria_insumo=categoria, quantidade=quantidade,
                            hodometro=hodo_val, horimetro=hori_val, descricao_obs=obs, frente_servico=frente,
                            equipamento_id=equip_id, fornecedor_id=forn_id, obra_id=obra.id, usuario_id=current_user.id
                        ))
                        total_processados += 1
                except ValueError as ve:
                    erros.append(f"Linha {i+1}: {str(ve)}")
                except Exception as row_err:
                    erros.append(f"Linha {i+1}: {str(row_err)}")

            if total_processados > 0:
                db.session.commit()
                flash(f'✅ {total_processados} lançamento(s) registrado(s) com sucesso!', 'success')
            else:
                db.session.rollback()
                flash('Nenhum lançamento foi salvo.', 'warning')

            if alertas:
                for al in alertas[:3]:
                    flash(al, 'info')

            if erros:
                for erro in erros[:5]:
                    flash(erro, 'danger')

        except Exception as e:
            db.session.rollback()
            flash(f'Erro crítico: {str(e)}', 'danger')
        return redirect(url_for('operacoes.lancamento'))

    return render_template(
        'lancamento.html',
        equipamentos=Equipamento.query.filter_by(ativo=True).order_by(Equipamento.prefixo_placa).all(),
        fornecedores=Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.nome).all(),
        obras_lista=Obra.query.filter_by(ativa=True).order_by(Obra.nome).all() if current_user.is_global else (
            Obra.query.filter_by(id=current_user.obra_padrao_id, ativa=True).all() if current_user.obra_padrao_id else []
        ),
        leituras=obter_ultimas_leituras_equipamentos(),
        ultimos=Abastecimento.query.order_by(Abastecimento.data_abastecimento.desc(), Abastecimento.id.desc()).limit(5).all()
    )


@operacoes_bp.route('/lancamento/excluir/<int:id>', methods=['POST'])
@lancador_required
def excluir_lancamento(id):
    abast = Abastecimento.query.get_or_404(id)
    try:
        db.session.delete(abast)
        db.session.commit()
        flash('Lançamento estornado com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'danger')
    return redirect(url_for('operacoes.lancamento'))


@operacoes_bp.route('/abastecimento/editar/<int:id>', methods=['GET', 'POST'])
@lancador_required
def editar_abastecimento(id):
    abast = Abastecimento.query.get_or_404(id)
    if request.method == 'POST':
        try:
            data_str = request.form.get('data_abastecimento')
            abast.data_abastecimento = datetime.strptime(data_str, '%Y-%m-%d').date()
            equip_id = int(request.form.get('equipamento_id'))
            forn_id = int(request.form.get('fornecedor_id')) if request.form.get('fornecedor_id') else None
            categoria = normalizar_combustivel(request.form.get('categoria_insumo'))

            quantidade = parse_float_ptbr(request.form.get('quantidade'), "Volume", positivo=True, permitir_nulo=False)
            hodo_val = parse_float_ptbr(request.form.get('hodometro'), "Hodômetro", permitir_nulo=True)
            hori_val = parse_float_ptbr(request.form.get('horimetro'), "Horímetro", permitir_nulo=True)

            if hodo_val is not None and hodo_val < 0:
                raise ValueError("O hodômetro não pode ser negativo.")
            if hori_val is not None and hori_val < 0:
                raise ValueError("O horímetro não pode ser negativo.")

            fornecedor = Fornecedor.query.get(forn_id) if forn_id else None
            if fornecedor:
                compativel, motivo = validar_compatibilidade_posto(fornecedor, categoria)
                if not compativel:
                    raise ValueError(motivo)

            abast.equipamento_id = equip_id
            abast.fornecedor_id = forn_id
            abast.categoria_insumo = categoria
            abast.quantidade = quantidade
            abast.hodometro = hodo_val
            abast.horimetro = hori_val
            abast.descricao_obs = request.form.get('descricao_obs', '').strip().upper()
            frente_val = request.form.get('frente_servico', '').strip().upper()
            abast.frente_servico = frente_val if frente_val else None
            obra_id = request.form.get('obra_id')
            abast.obra_id = int(obra_id) if obra_id else None
            db.session.commit()
            flash('Abastecimento atualizado!', 'success')
            next_url = request.form.get('next')
            if next_url and '/abastecimento/editar' not in next_url:
                return redirect(next_url)
            return redirect(url_for('relatorios.relatorio_fornecedor', fornecedor_id=abast.fornecedor_id,
                                    data_inicio=abast.data_abastecimento.strftime('%Y-%m-%d'),
                                    data_fim=abast.data_abastecimento.strftime('%Y-%m-%d')))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'danger')
            return redirect(url_for('operacoes.editar_abastecimento', id=id))

    return render_template(
        'editar_abastecimento.html', abast=abast,
        equipamentos=Equipamento.query.filter_by(ativo=True).all(),
        fornecedores=Fornecedor.query.filter_by(ativo=True).all(),
        obras_lista=Obra.query.filter_by(ativa=True).all()
    )


# ==========================================
# ENTRADAS DE NOTA FISCAL (NFs)
# ==========================================
@operacoes_bp.route('/entradas', methods=['GET', 'POST'])
@admin_required
def entradas():
    if request.method == 'POST':
        try:
            fornecedor_id = int(request.form.get('fornecedor_id'))
            fornecedor = Fornecedor.query.get_or_404(fornecedor_id)
            categoria = normalizar_combustivel(request.form.get('categoria_insumo'))
            quantidade = parse_float_ptbr(request.form.get('quantidade'), "Volume Recebido", positivo=True, permitir_nulo=False)

            compativel, motivo = validar_compatibilidade_posto(fornecedor, categoria)
            if not compativel:
                flash(motivo, 'danger')
                return redirect(url_for('operacoes.entradas'))

            obra_id_form = request.form.get('obra_id')
            obra_id = int(obra_id_form) if obra_id_form else (fornecedor.obra_id if fornecedor and fornecedor.obra_id else (current_user.obra_padrao_id or None))

            db.session.add(EntradaInsumo(
                data_entrada=datetime.strptime(request.form.get('data_entrada'), '%Y-%m-%d').date(),
                fornecedor_id=fornecedor_id,
                categoria_insumo=categoria,
                quantidade=quantidade,
                numero_nf=request.form.get('numero_nf', '').strip().upper(),
                usuario_id=current_user.id,
                obra_id=obra_id
            ))
            db.session.commit()
            flash(f'✅ Entrada de NF registrada com sucesso ({quantidade:.2f} L em {fornecedor.nome})!', 'success')
            return redirect(url_for('operacoes.entradas'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'danger')

    return render_template(
        'entradas.html',
        fornecedores=Fornecedor.query.filter_by(ativo=True).order_by(Fornecedor.nome).all(),
        obras_lista=Obra.query.filter_by(ativa=True).order_by(Obra.nome).all() if current_user.is_global else (
            Obra.query.filter_by(id=current_user.obra_padrao_id, ativa=True).all() if current_user.obra_padrao_id else []
        ),
        entradas=EntradaInsumo.query.order_by(EntradaInsumo.data_entrada.desc(), EntradaInsumo.id.desc()).limit(15).all()
    )


@operacoes_bp.route('/entrada/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
def editar_entrada(id):
    entrada = EntradaInsumo.query.get_or_404(id)
    if request.method == 'POST':
        try:
            fornecedor_id = int(request.form.get('fornecedor_id'))
            fornecedor = Fornecedor.query.get_or_404(fornecedor_id)
            categoria = normalizar_combustivel(request.form.get('categoria_insumo'))
            quantidade = parse_float_ptbr(request.form.get('quantidade'), "Volume Recebido", positivo=True, permitir_nulo=False)

            compativel, motivo = validar_compatibilidade_posto(fornecedor, categoria)
            if not compativel:
                raise ValueError(motivo)

            entrada.data_entrada = datetime.strptime(request.form.get('data_entrada'), '%Y-%m-%d').date()
            entrada.fornecedor_id = fornecedor_id
            entrada.categoria_insumo = categoria
            entrada.quantidade = quantidade
            entrada.numero_nf = request.form.get('numero_nf', '').strip().upper()
            obra_id = request.form.get('obra_id')
            entrada.obra_id = int(obra_id) if obra_id else None
            db.session.commit()
            flash('Entrada atualizada com sucesso!', 'success')
            next_url = request.form.get('next')
            if next_url and '/entrada/editar' not in next_url:
                return redirect(next_url)
            return redirect(url_for('relatorios.relatorio_fornecedor', fornecedor_id=entrada.fornecedor_id,
                                    data_inicio=entrada.data_entrada.strftime('%Y-%m-%d'),
                                    data_fim=entrada.data_entrada.strftime('%Y-%m-%d')))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'danger')
            return redirect(url_for('operacoes.editar_entrada', id=id))

    return render_template('editar_entrada.html', entrada=entrada,
                           fornecedores=Fornecedor.query.filter_by(ativo=True).all(),
                           obras_lista=Obra.query.filter_by(ativa=True).all())


@operacoes_bp.route('/entrada/excluir/<int:id>', methods=['POST'])
@admin_required
def excluir_entrada(id):
    entrada = EntradaInsumo.query.get_or_404(id)
    try:
        db.session.delete(entrada)
        db.session.commit()
        flash('Entrada excluída com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'danger')
    return redirect(request.referrer or url_for('operacoes.entradas'))


# ==========================================
# TRANSFERÊNCIAS (TRANSBORDOS)
# ==========================================
@operacoes_bp.route('/transferencia', methods=['GET', 'POST'])
@lancador_required
def transferencia():
    if request.method == 'POST':
        transferencia_id = request.form.get('transferencia_id', '').strip()
        origem_id = request.form.get('origem_id')
        destino_id = request.form.get('destino_id')
        data_hora_str = request.form.get('data_hora')
        litros_str = request.form.get('litros', '')
        tipo = request.form.get('tipo_combustivel')
        obs = request.form.get('observacao', '').strip().upper()

        if not origem_id or not destino_id:
            flash('Selecione os postos de origem e destino.', 'warning')
            return redirect(url_for('operacoes.transferencia'))

        if origem_id == destino_id:
            flash('Origem e Destino não podem ser iguais.', 'warning')
            return redirect(url_for('operacoes.transferencia'))

        try:
            litros = parse_float_ptbr(litros_str, "Volume de Transbordo", positivo=True, permitir_nulo=False)

            if not data_hora_str:
                flash('Data e hora do transbordo são obrigatórias.', 'danger')
                return redirect(url_for('operacoes.transferencia'))

            data_hora_obj = datetime.strptime(data_hora_str, '%Y-%m-%dT%H:%M')

            origem = Fornecedor.query.get(int(origem_id))
            destino = Fornecedor.query.get(int(destino_id))

            if not origem or not destino:
                flash('Base de origem ou destino inválida.', 'danger')
                return redirect(url_for('operacoes.transferencia'))

            comb_origem = normalizar_combustivel(origem.tipo_combustivel)
            comb_destino = normalizar_combustivel(destino.tipo_combustivel)
            if comb_origem != comb_destino:
                flash(f'Incompatibilidade: a origem armazena {comb_origem} e o destino armazena {comb_destino}. Mistura não permitida.', 'danger')
                return redirect(url_for('operacoes.transferencia'))

            tipo_canonico = normalizar_combustivel(tipo or comb_origem)

            obra_id_form = request.form.get('obra_id')
            obra_id = int(obra_id_form) if obra_id_form else (
                (destino.obra_id if destino and destino.obra_id else None) or
                (origem.obra_id if origem and origem.obra_id else None) or
                (current_user.obra_padrao_id or None)
            )

            if transferencia_id:
                transf = Transferencia.query.get_or_404(int(transferencia_id))
                transf.origem_id, transf.destino_id, transf.litros = int(origem_id), int(destino_id), litros
                transf.tipo_combustivel, transf.observacao, transf.data_hora = tipo_canonico, obs, data_hora_obj
                if obra_id:
                    transf.obra_id = obra_id
                db.session.commit()
                flash('Transferência atualizada com sucesso!', 'success')
            else:
                db.session.add(Transferencia(
                    origem_id=int(origem_id), destino_id=int(destino_id), litros=litros,
                    tipo_combustivel=tipo_canonico, observacao=obs, data_hora=data_hora_obj, usuario_id=current_user.id,
                    obra_id=obra_id
                ))
                db.session.commit()
                flash(f'✅ Transbordo de {litros:.2f}L registrado com sucesso!', 'success')
            return redirect(url_for('operacoes.transferencia'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'danger')

    return render_template(
        'transferencia.html',
        postos_internos=Fornecedor.query.filter_by(tipo_origem='Interno', ativo=True).order_by(Fornecedor.nome).all(),
        transferencias=Transferencia.query.order_by(Transferencia.data_hora.desc()).limit(50).all()
    )


@operacoes_bp.route('/transferencia/editar/<int:id>')
@lancador_required
def editar_transferencia(id):
    Transferencia.query.get_or_404(id)
    return redirect(url_for('operacoes.transferencia', editar=id))


@operacoes_bp.route('/transferencia/excluir/<int:id>', methods=['POST'])
@lancador_required
def excluir_transferencia(id):
    transf = Transferencia.query.get_or_404(id)
    try:
        db.session.delete(transf)
        db.session.commit()
        flash('Transferência excluída.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'danger')
    return redirect(url_for('operacoes.transferencia'))


# ==========================================
# IMPORTAÇÃO CSV GERAL
# ==========================================
@operacoes_bp.route('/importar', methods=['GET', 'POST'])
@admin_required
def importar_csv():
    if request.method == 'POST':
        if 'arquivo_csv' not in request.files:
            flash('Nenhum arquivo anexado.', 'danger')
            return redirect(request.url)

        arquivo = request.files['arquivo_csv']
        if not arquivo.filename or not arquivo.filename.lower().endswith('.csv'):
            flash('O arquivo deve ser .csv', 'danger')
            return redirect(request.url)

        obra_id = request.form.get('obra_id', '').strip()
        sucesso, ignorados, erros = CsvImporterService.importar_abastecimentos(arquivo, obra_id, current_user)

        if erros:
            flash(f'Leitura concluída. {sucesso} gravados, {ignorados} ignorados. Erros em {len(erros)} linhas.', 'warning')
        else:
            flash(f'✅ {sucesso} registros importados com sucesso!', 'success')

        return redirect(url_for('operacoes.importar_csv'))

    return render_template('importar_csv.html', obras_lista=Obra.query.filter_by(ativa=True).order_by(Obra.nome).all())