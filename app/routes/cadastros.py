from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Obra, Equipamento, Fornecedor, Usuario, Abastecimento, EntradaInsumo, Transferencia, FrenteServico, AlocacaoFrenteEquipamento
from app.routes.auth import admin_required
from app.services.csv_importer import CsvImporterService

cadastros_bp = Blueprint('cadastros', __name__)


# ==========================================
# GESTÃO DE OBRAS
# ==========================================
@cadastros_bp.route('/obras', methods=['GET', 'POST'])
@admin_required
def obras():
    if request.method == 'POST':
        try:
            obra_id = request.form.get('obra_id', '').strip()
            codigo = request.form.get('codigo', '').strip().upper()
            nome = request.form.get('nome', '').strip().upper()
            local = request.form.get('local', '').strip().upper()
            responsavel = request.form.get('responsavel', '').strip().upper()
            data_inicio_str = request.form.get('data_inicio', '').strip()

            if not codigo or not nome:
                flash('Código e Nome da obra são obrigatórios.', 'danger')
                return redirect(url_for('cadastros.obras'))

            data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else None

            if obra_id:
                obra = Obra.query.get_or_404(int(obra_id))
                existe = Obra.query.filter(Obra.codigo == codigo, Obra.id != obra.id).first()
                if existe:
                    flash(f'Já existe uma obra com o código {codigo}.', 'warning')
                    return redirect(url_for('cadastros.obras'))
                obra.codigo, obra.nome, obra.local, obra.responsavel, obra.data_inicio = codigo, nome, local or None, responsavel or None, data_inicio
                db.session.commit()
                flash(f'Obra "{nome}" atualizada com sucesso!', 'success')
            else:
                if Obra.query.filter_by(codigo=codigo).first():
                    flash(f'Já existe uma obra com o código {codigo}.', 'warning')
                    return redirect(url_for('cadastros.obras'))
                db.session.add(Obra(codigo=codigo, nome=nome, local=local or None, responsavel=responsavel or None, data_inicio=data_inicio, ativa=True))
                db.session.commit()
                flash(f'Obra "{nome}" cadastrada com sucesso!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao processar obra: {str(e)}', 'danger')
        return redirect(url_for('cadastros.obras'))

    return render_template('obras.html', obras=Obra.query.order_by(Obra.ativa.desc(), Obra.nome.asc()).all())


@cadastros_bp.route('/obra/toggle/<int:id>', methods=['POST'])
@admin_required
def toggle_obra(id):
    obra = Obra.query.get_or_404(id)
    try:
        obra.ativa = not obra.ativa
        if not obra.ativa:
            for forn in Fornecedor.query.filter_by(obra_id=obra.id).all():
                forn.ativo = False
        db.session.commit()
        flash(f'Obra "{obra.nome}" {"ativada" if obra.ativa else "inativada"}!', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'danger')
    return redirect(url_for('cadastros.obras'))


@cadastros_bp.route('/obra/excluir/<int:id>', methods=['POST'])
@admin_required
def excluir_obra(id):
    obra = Obra.query.get_or_404(id)
    try:
        tem_registros = (
            Abastecimento.query.filter_by(obra_id=id).first() or
            EntradaInsumo.query.filter_by(obra_id=id).first() or
            Transferencia.query.filter_by(obra_id=id).first() or
            Fornecedor.query.filter_by(obra_id=id).first() or
            Usuario.query.filter_by(obra_padrao_id=id).first()
        )
        if tem_registros:
            obra.ativa = False
            db.session.commit()
            flash(f'Obra "{obra.nome}" possui vínculos e foi apenas inativada.', 'warning')
        else:
            nome = obra.nome
            db.session.delete(obra)
            db.session.commit()
            flash(f'Obra "{nome}" excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'danger')
    return redirect(url_for('cadastros.obras'))


# ==========================================
# GESTÃO DE EQUIPAMENTOS
# ==========================================
@cadastros_bp.route('/equipamentos', methods=['GET', 'POST'])
@admin_required
def equipamentos():
    if request.method == 'POST':
        prefixo = request.form.get('prefixo_placa', '').strip().upper()
        descricao = request.form.get('descricao', '').strip().upper()
        tipo = request.form.get('tipo_equipamento', '').strip()
        locador = request.form.get('locador', '').strip().upper()

        if Equipamento.query.filter_by(prefixo_placa=prefixo).first():
            flash(f'O equipamento {prefixo} já está cadastrado!', 'warning')
        else:
            db.session.add(Equipamento(
                prefixo_placa=prefixo, descricao=descricao, tipo_equipamento=tipo,
                locador=locador or 'CENTRAL DE EQUIPAMENTOS', ativo=True
            ))
            db.session.commit()
            flash(f'Equipamento {prefixo} cadastrado com sucesso!', 'success')
        return redirect(url_for('cadastros.equipamentos'))

    return render_template('equipamentos.html', equipamentos=Equipamento.query.order_by(Equipamento.prefixo_placa).all())


@cadastros_bp.route('/equipamento/toggle/<int:id>', methods=['POST'])
@admin_required
def toggle_equipamento(id):
    eq = Equipamento.query.get_or_404(id)
    eq.ativo = not eq.ativo
    db.session.commit()
    flash(f'Equipamento {eq.prefixo_placa} {"ativado" if eq.ativo else "inativado"}!', 'info')
    return redirect(url_for('cadastros.equipamentos'))


@cadastros_bp.route('/equipamento/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
def editar_equipamento(id):
    eq = Equipamento.query.get_or_404(id)
    if request.method == 'POST':
        eq.prefixo_placa = request.form.get('prefixo_placa', '').strip().upper()
        eq.descricao = request.form.get('descricao', '').strip().upper()
        eq.tipo_equipamento = request.form.get('tipo_equipamento', '').strip()
        eq.locador = request.form.get('locador', '').strip().upper()
        db.session.commit()
        flash(f'Equipamento {eq.prefixo_placa} atualizado!', 'success')
        return redirect(url_for('cadastros.equipamentos'))
    return redirect(url_for('cadastros.equipamentos', editar=id))


@cadastros_bp.route('/equipamento/excluir/<int:id>', methods=['POST'])
@admin_required
def excluir_equipamento(id):
    eq = Equipamento.query.get_or_404(id)
    try:
        tem_registros = Abastecimento.query.filter_by(equipamento_id=id).first()
        if tem_registros:
            eq.ativo = False
            db.session.commit()
            flash(f'Equipamento "{eq.prefixo_placa}" possui vínculos de abastecimento e foi apenas inativado.', 'warning')
        else:
            prefixo = eq.prefixo_placa
            db.session.delete(eq)
            db.session.commit()
            flash(f'Equipamento {prefixo} excluído com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir: {str(e)}', 'danger')
    return redirect(url_for('cadastros.equipamentos'))


@cadastros_bp.route('/equipamentos/importar', methods=['POST'])
@admin_required
def importar_equipamentos_csv():
    if 'arquivo_csv' not in request.files:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(url_for('cadastros.equipamentos'))
    
    arquivo = request.files['arquivo_csv']
    if not arquivo.filename or not arquivo.filename.lower().endswith('.csv'):
        flash('Envie um arquivo válido no formato .csv', 'danger')
        return redirect(url_for('cadastros.equipamentos'))

    sucesso, ignorados, erros = CsvImporterService.importar_equipamentos(arquivo)

    if sucesso > 0:
        flash(f'✅ {sucesso} equipamento(s) importado(s)!', 'success')
    if ignorados > 0:
        flash(f'⚠️ {ignorados} registros ignorados (já cadastrados).', 'warning')
    if erros:
        for erro in erros[:3]:
            flash(erro, 'danger')

    return redirect(url_for('cadastros.equipamentos'))


# ==========================================
# GESTÃO DE FORNECEDORES E TANQUES
# ==========================================
@cadastros_bp.route('/fornecedores', methods=['GET', 'POST'])
@admin_required
def fornecedores():
    if request.method == 'POST':
        try:
            fornecedor_id = request.form.get('fornecedor_id', '').strip()
            nome = request.form.get('nome', '').strip().upper()
            tipo = request.form.get('tipo_origem', '').strip()
            obra_id = request.form.get('obra_id', '').strip()
            capacidade_str = request.form.get('capacidade_litros', '').strip()
            estoque_inicial_str = request.form.get('estoque_inicial', '').strip()
            categoria_tanque = request.form.get('categoria_tanque', '').strip()
            tipo_combustivel = request.form.get('tipo_combustivel', '').strip()

            categoria = 'Posto Externo' if tipo == 'Externo' else (categoria_tanque or 'Tanque')
            combustivel = tipo_combustivel or 'DIESEL S10'
            capacidade = float(capacidade_str.replace(',', '.')) if capacidade_str else None
            estoque_inicial = float(estoque_inicial_str.replace(',', '.')) if estoque_inicial_str else 0.0

            if not nome:
                flash('O nome é obrigatório!', 'danger')
                return redirect(url_for('cadastros.fornecedores'))

            if fornecedor_id:
                forn = Fornecedor.query.get_or_404(int(fornecedor_id))
                forn.nome, forn.tipo_origem, forn.categoria_tanque, forn.tipo_combustivel = nome, tipo or 'Interno', categoria, combustivel
                forn.capacidade_litros, forn.obra_id, forn.estoque_inicial = capacidade, int(obra_id) if obra_id else None, estoque_inicial
                db.session.commit()
                flash(f'Fornecedor "{nome}" atualizado!', 'success')
            else:
                if Fornecedor.query.filter_by(nome=nome).first():
                    flash(f'O fornecedor "{nome}" já existe!', 'warning')
                else:
                    db.session.add(Fornecedor(
                        nome=nome, tipo_origem=tipo or 'Interno', categoria_tanque=categoria,
                        tipo_combustivel=combustivel, capacidade_litros=capacidade,
                        obra_id=int(obra_id) if obra_id else None, estoque_inicial=estoque_inicial, ativo=True
                    ))
                    db.session.commit()
                    flash(f'Fornecedor "{nome}" cadastrado!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'danger')
        return redirect(url_for('cadastros.fornecedores'))

    return render_template(
        'fornecedores.html',
        fornecedores=Fornecedor.query.order_by(Fornecedor.tipo_origem.desc(), Fornecedor.nome.asc()).all(),
        obras_lista=Obra.query.filter_by(ativa=True).order_by(Obra.nome).all()
    )


@cadastros_bp.route('/fornecedor/toggle/<int:id>', methods=['POST'])
@admin_required
def toggle_fornecedor(id):
    forn = Fornecedor.query.get_or_404(id)
    forn.ativo = not forn.ativo
    db.session.commit()
    flash(f'Fornecedor {forn.nome} {"ativado" if forn.ativo else "inativado"}!', 'info')
    return redirect(url_for('cadastros.fornecedores'))


@cadastros_bp.route('/fornecedor/excluir/<int:id>', methods=['POST'])
@admin_required
def excluir_fornecedor(id):
    forn = Fornecedor.query.get_or_404(id)
    try:
        tem_registros = (
            Abastecimento.query.filter_by(fornecedor_id=id).first() or
            EntradaInsumo.query.filter_by(fornecedor_id=id).first() or
            Transferencia.query.filter_by(origem_id=id).first() or
            Transferencia.query.filter_by(destino_id=id).first()
        )
        if tem_registros:
            forn.ativo = False
            db.session.commit()
            flash(f'Fornecedor "{forn.nome}" possui vínculos e foi inativado.', 'warning')
        else:
            nome = forn.nome
            db.session.delete(forn)
            db.session.commit()
            flash(f'Fornecedor "{nome}" excluído permanentemente!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'danger')
    return redirect(url_for('cadastros.fornecedores'))


# ==========================================
# GESTÃO DE USUÁRIOS
# ==========================================
@cadastros_bp.route('/usuarios', methods=['GET', 'POST'])
@admin_required
def usuarios():
    if request.method == 'POST':
        try:
            usuario_id = request.form.get('usuario_id', '').strip()
            nome = request.form.get('nome', '').strip().upper()
            email = request.form.get('novo_email', '').strip().lower()
            senha = request.form.get('nova_senha', '')
            papel = request.form.get('papel', 'lancador')
            acesso_global = request.form.get('acesso_global') == 'true'
            obra_padrao_id = request.form.get('obra_padrao_id', '').strip()

            if usuario_id:
                user = Usuario.query.get_or_404(int(usuario_id))
                if user.id == current_user.id:
                    flash('Você não pode alterar sua própria conta por aqui.', 'warning')
                    return redirect(url_for('cadastros.usuarios'))
                user.nome, user.email, user.nivel_acesso = nome, email, papel
                user.acesso_global, user.obra_padrao_id = acesso_global, int(obra_padrao_id) if obra_padrao_id else None
                if senha:
                    if len(senha) < 6:
                        flash('A senha deve ter no mínimo 6 caracteres!', 'danger')
                        return redirect(url_for('cadastros.usuarios'))
                    user.set_senha(senha)
                db.session.commit()
                flash(f'Usuário "{nome}" atualizado!', 'success')
            else:
                if Usuario.query.filter_by(email=email).first():
                    flash('Este e-mail já está em uso!', 'danger')
                else:
                    novo_user = Usuario(
                        nome=nome, email=email, nivel_acesso=papel, acesso_global=acesso_global,
                        obra_padrao_id=int(obra_padrao_id) if obra_padrao_id else None, ativo=True
                    )
                    novo_user.set_senha(senha)
                    db.session.add(novo_user)
                    db.session.commit()
                    flash(f'Usuário "{nome}" cadastrado!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'danger')
        return redirect(url_for('cadastros.usuarios'))

    return render_template(
        'usuarios.html',
        usuarios=Usuario.query.order_by(Usuario.nome).all(),
        obras_lista=Obra.query.filter_by(ativa=True).order_by(Obra.nome).all()
    )


@cadastros_bp.route('/usuario/toggle/<int:id>', methods=['POST'])
@admin_required
def toggle_usuario(id):
    if id == current_user.id:
        flash('Você não pode inativar a própria conta.', 'warning')
        return redirect(url_for('cadastros.usuarios'))
    user = Usuario.query.get_or_404(id)
    user.ativo = not user.ativo
    db.session.commit()
    flash(f'Usuário {user.nome} {"ativado" if user.ativo else "inativado"}!', 'info')
    return redirect(url_for('cadastros.usuarios'))


@cadastros_bp.route('/usuario/excluir/<int:id>', methods=['POST'])
@admin_required
def excluir_usuario(id):
    if id == current_user.id:
        flash('Você não pode excluir sua própria conta!', 'danger')
        return redirect(url_for('cadastros.usuarios'))
    user = Usuario.query.get_or_404(id)
    try:
        tem_registros = (
            Abastecimento.query.filter_by(usuario_id=id).first() or
            EntradaInsumo.query.filter_by(usuario_id=id).first() or
            Transferencia.query.filter_by(usuario_id=id).first()
        )
        if tem_registros:
            user.ativo = False
            db.session.commit()
            flash(f'Usuário {user.nome} possui vínculos e foi inativado.', 'warning')
        else:
            nome = user.nome
            db.session.delete(user)
            db.session.commit()
            flash(f'Usuário {nome} excluído!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'danger')
    return redirect(url_for('cadastros.usuarios'))


# ==========================================
# GESTÃO DE FRENTES DE SERVIÇO E ALOCAÇÃO EM LOTE
# ==========================================
@cadastros_bp.route('/frentes-servico', methods=['GET', 'POST'])
@login_required
def frentes_servico():
    obra_id_param = request.args.get('obra_id', '').strip()
    obra_id_int = int(obra_id_param) if (obra_id_param and obra_id_param.isdigit()) else None
    
    if not obra_id_int and not current_user.is_global and current_user.obra_padrao_id:
        obra_id_int = current_user.obra_padrao_id

    if request.method == 'POST':
        acao = request.form.get('acao', '')

        if acao == 'cadastrar_frente':
            try:
                frente_id = request.form.get('frente_id', '').strip()
                nome = request.form.get('nome', '').strip().upper()
                descricao = request.form.get('descricao', '').strip().upper()
                obra_id_form = request.form.get('obra_id', '').strip()

                if not nome:
                    flash('O nome da Frente de Serviço é obrigatório.', 'danger')
                    return redirect(url_for('cadastros.frentes_servico', obra_id=obra_id_param))

                f_obra_id = int(obra_id_form) if obra_id_form else (obra_id_int or None)

                if frente_id:
                    frente = FrenteServico.query.get_or_404(int(frente_id))
                    frente.nome = nome
                    frente.descricao = descricao or None
                    frente.obra_id = f_obra_id
                    db.session.commit()
                    flash(f'Frente de Serviço "{nome}" atualizada com sucesso!', 'success')
                else:
                    existe = FrenteServico.query.filter_by(nome=nome, obra_id=f_obra_id).first()
                    if existe:
                        flash(f'A Frente de Serviço "{nome}" já está cadastrada para esta obra.', 'warning')
                    else:
                        db.session.add(FrenteServico(
                            nome=nome, descricao=descricao or None, obra_id=f_obra_id, ativa=True
                        ))
                        db.session.commit()
                        flash(f'Frente de Serviço "{nome}" cadastrada com sucesso!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao salvar Frente de Serviço: {str(e)}', 'danger')

        elif acao == 'alocar_lote':
            try:
                frente_servico_id = request.form.get('frente_servico_id', '').strip()
                data_inicio_str = request.form.get('data_inicio', '').strip()
                data_fim_str = request.form.get('data_fim', '').strip()
                equipamento_ids = request.form.getlist('equipamento_ids[]')
                vincular_abastecimentos = request.form.get('vincular_abastecimentos') in ['true', 'on', '1', True]
                observacao = request.form.get('observacao', '').strip().upper()

                if not frente_servico_id or not data_inicio_str or not data_fim_str or not equipamento_ids:
                    flash('Preencha a Frente de Serviço, Período (Início e Fim) e selecione ao menos um equipamento.', 'danger')
                    return redirect(url_for('cadastros.frentes_servico', obra_id=obra_id_param))

                frente = FrenteServico.query.get_or_404(int(frente_servico_id))
                dt_ini = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
                dt_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()

                if dt_fim < dt_ini:
                    flash('A Data Fim não pode ser anterior à Data Início.', 'warning')
                    return redirect(url_for('cadastros.frentes_servico', obra_id=obra_id_param))

                eq_ids_ints = [int(eid) for eid in equipamento_ids if eid.isdigit()]
                alocacoes_criadas = 0
                abastecimentos_atualizados = 0

                for eq_id in eq_ids_ints:
                    aloc = AlocacaoFrenteEquipamento(
                        frente_servico_id=frente.id,
                        equipamento_id=eq_id,
                        data_inicio=dt_ini,
                        data_fim=dt_fim,
                        observacao=observacao or None
                    )
                    db.session.add(aloc)
                    alocacoes_criadas += 1

                    if vincular_abastecimentos:
                        abasts = Abastecimento.query.filter(
                            Abastecimento.equipamento_id == eq_id,
                            Abastecimento.data_abastecimento >= dt_ini,
                            Abastecimento.data_abastecimento <= dt_fim
                        ).all()
                        for ab in abasts:
                            ab.frente_servico = frente.nome
                            abastecimentos_atualizados += 1

                db.session.commit()
                msg = f'⚡ Alocação em lote realizada com sucesso! {alocacoes_criadas} equipamento(s) vinculados à frente "{frente.nome}" de {dt_ini.strftime("%d/%m/%Y")} a {dt_fim.strftime("%d/%m/%Y")}.'
                if vincular_abastecimentos:
                    msg += f' ({abastecimentos_atualizados} abastecimentos vinculados no período).'
                flash(msg, 'success')

            except Exception as e:
                db.session.rollback()
                flash(f'Erro ao processar alocação em lote: {str(e)}', 'danger')

        return redirect(url_for('cadastros.frentes_servico', obra_id=obra_id_param))

    # Query de frentes
    query_frentes = FrenteServico.query
    if obra_id_int:
        query_frentes = query_frentes.filter((FrenteServico.obra_id == obra_id_int) | (FrenteServico.obra_id.is_(None)))
    frentes_lista = query_frentes.order_by(FrenteServico.ativa.desc(), FrenteServico.nome.asc()).all()

    # Query de equipamentos
    equipamentos_lista = Equipamento.query.filter_by(ativo=True).order_by(Equipamento.prefixo_placa.asc()).all()

    # Query de alocações recentes
    query_aloc = AlocacaoFrenteEquipamento.query.join(FrenteServico)
    if obra_id_int:
        query_aloc = query_aloc.filter((FrenteServico.obra_id == obra_id_int) | (FrenteServico.obra_id.is_(None)))
    alocaes_recentes = query_aloc.order_by(AlocacaoFrenteEquipamento.data_cadastro.desc()).limit(100).all()

    obras_lista = Obra.query.filter_by(ativa=True).order_by(Obra.nome.asc()).all()
    obra_sel = Obra.query.get(obra_id_int) if obra_id_int else None

    # Métricas gerais
    total_frentes_ativas = sum(1 for f in frentes_lista if f.ativa)
    total_alocacoes = len(alocaes_recentes)

    return render_template(
        'frentes_servico.html',
        frentes_lista=frentes_lista,
        equipamentos_lista=equipamentos_lista,
        alocaes_recentes=alocaes_recentes,
        obras_lista=obras_lista,
        obra_sel=obra_sel,
        obra_id_sel=str(obra_id_int) if obra_id_int else '',
        total_frentes_ativas=total_frentes_ativas,
        total_alocacoes=total_alocacoes
    )


@cadastros_bp.route('/frente-servico/toggle/<int:id>', methods=['POST'])
@login_required
def toggle_frente_servico(id):
    frente = FrenteServico.query.get_or_404(id)
    frente.ativa = not frente.ativa
    db.session.commit()
    flash(f'Frente de Serviço "{frente.nome}" {"ativada" if frente.ativa else "inativada"}!', 'info')
    return redirect(url_for('cadastros.frentes_servico'))


@cadastros_bp.route('/frente-servico/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_frente_servico(id):
    frente = FrenteServico.query.get_or_404(id)
    limpar = request.form.get('limpar_abastecimentos') in ['true', 'on', '1', True]
    try:
        nome = frente.nome
        if limpar:
            Abastecimento.query.filter_by(frente_servico=nome).update({'frente_servico': None})
            db.session.delete(frente)
            db.session.commit()
            flash(f'Frente "{nome}" excluída e abastecimentos desvinculados da média de consumo com sucesso!', 'success')
        else:
            tem_abasts = Abastecimento.query.filter_by(frente_servico=nome).first()
            if tem_abasts:
                frente.ativa = False
                db.session.commit()
                flash(f'Frente "{nome}" possui abastecimentos vinculados e foi inativada. Use a opção "Limpar Abastecimentos" se desejar removê-la completamente da Média de Consumo.', 'warning')
            else:
                db.session.delete(frente)
                db.session.commit()
                flash(f'Frente "{nome}" excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir Frente: {str(e)}', 'danger')
    return redirect(url_for('cadastros.frentes_servico'))


@cadastros_bp.route('/frente-servico/desvincular-abastecimentos/<int:id>', methods=['POST'])
@login_required
def desvincular_abastecimentos_frente(id):
    frente = FrenteServico.query.get_or_404(id)
    try:
        nome = frente.nome
        qtd = Abastecimento.query.filter_by(frente_servico=nome).update({'frente_servico': None})
        db.session.commit()
        flash(f'✅ {qtd} abastecimentos foram desvinculados da frente "{nome}" e removidos da Média de Consumo!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao desvincular abastecimentos: {str(e)}', 'danger')
    return redirect(url_for('cadastros.frentes_servico'))



@cadastros_bp.route('/alocacao-frente/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_alocacao_frente(id):
    aloc = AlocacaoFrenteEquipamento.query.get_or_404(id)
    try:
        db.session.delete(aloc)
        db.session.commit()
        flash('Alocação de período excluída.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir alocação: {str(e)}', 'danger')
    return redirect(url_for('cadastros.frentes_servico'))


@cadastros_bp.route('/alocacao-frente/sync/<int:id>', methods=['POST'])
@login_required
def sync_alocacao_frente(id):
    aloc = AlocacaoFrenteEquipamento.query.get_or_404(id)
    try:
        frente_nome = aloc.frente_rel.nome
        abasts = Abastecimento.query.filter(
            Abastecimento.equipamento_id == aloc.equipamento_id,
            Abastecimento.data_abastecimento >= aloc.data_inicio,
            Abastecimento.data_abastecimento <= aloc.data_fim
        ).all()
        for ab in abasts:
            ab.frente_servico = frente_nome
        db.session.commit()
        flash(f'✅ {len(abasts)} abastecimentos do equipamento {aloc.equipamento_rel.prefixo_placa} sincronizados para "{frente_nome}".', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao sincronizar abastecimentos: {str(e)}', 'danger')
    return redirect(url_for('cadastros.frentes_servico'))