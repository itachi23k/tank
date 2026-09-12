import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Obra, WhatsAppContato, WhatsAppLog
from app.routes.auth import admin_required
from app.services.stock_calculator import StockCalculator
from app.services.whatsapp_oficial import WhatsAppOficial

whatsapp_bp = Blueprint('whatsapp', __name__)


@whatsapp_bp.route('/whatsapp/painel')
@login_required
def painel():
    aba_ativa = request.args.get('aba', 'meta')
    data_param = request.args.get('data')
    data_ref = StockCalculator.parse_data_brasileira(data_param)

    if current_user.is_global:
        obras_visiveis = Obra.query.filter_by(ativa=True).order_by(Obra.nome).all()
    elif current_user.obra_padrao_id:
        obras_visiveis = [Obra.query.get(current_user.obra_padrao_id)]
    else:
        obras_visiveis = []

    obras_dados, data_atual, texto_geral = StockCalculator.calcular_dados_obras_whatsapp(
        obras_visiveis, data_referencia=data_ref
    )
    data_iso = data_ref.strftime('%Y-%m-%d')
    contatos = WhatsAppContato.query.order_by(WhatsAppContato.nome).all()
    contatos_data = []
    for c in contatos:
        contatos_data.append({
            'id': c.id,
            'nome': c.nome,
            'funcao': c.funcao or '',
            'numero': c.numero,
            'ativo': bool(c.ativo),
            'obras_ids': [o.id for o in c.obras],
            'obras_codigos': [o.codigo for o in c.obras],
            'obras_nomes': [o.nome for o in c.obras]
        })

    obras_resumo = []
    for item in obras_dados:
        obras_resumo.append({
            'id': str(item['obra'].id),
            'codigo': item['obra'].codigo,
            'nome': item['obra'].nome,
            'mensagem_texto': item['mensagem_texto']
        })

    logs = WhatsAppLog.query.order_by(WhatsAppLog.data_envio.desc()).limit(20).all()
    meta_configurada = bool(os.environ.get('WHATSAPP_TOKEN') and os.environ.get('WHATSAPP_PHONE_ID'))

    return render_template('whatsapp_painel.html',
                           obras_dados=obras_dados, contatos=contatos,
                           contatos_data=contatos_data, obras_resumo=obras_resumo,
                           logs=logs, data_atual=data_atual, data_iso=data_iso,
                           texto_geral=texto_geral, aba_ativa=aba_ativa,
                           meta_configurada=meta_configurada)


@whatsapp_bp.route('/whatsapp/log-envio-web', methods=['POST'])
@login_required
def log_envio_web():
    data = request.get_json(silent=True) or request.form
    contato_id = data.get('contato_id')
    obra_id = data.get('obra_id')
    mensagem = data.get('mensagem', '')
    if contato_id:
        try:
            log = WhatsAppLog(
                contato_id=int(contato_id),
                obra_id=int(obra_id) if obra_id else None,
                tipo_envio='web_whatsapp',
                mensagem=mensagem[:500] if mensagem else 'Relatório enviado via WhatsApp Web',
                status='sucesso'
            )
            db.session.add(log)
            db.session.commit()
            return {'success': True, 'sucesso': True}
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'error': str(e)}, 500
    return {'success': False, 'error': 'contato_id ausente'}, 400


@whatsapp_bp.route('/whatsapp/enviar-relatorio', methods=['POST'])
@login_required
def enviar_relatorio():
    obra_id, contato_id = request.form.get('obra_id'), request.form.get('contato_id')
    modo_envio = request.form.get('modo_envio', 'template')
    mensagem_personalizada = request.form.get('mensagem_personalizada', '').strip()
    data_param = request.form.get('data') or request.form.get('data_referencia')
    data_ref = StockCalculator.parse_data_brasileira(data_param)
    data_formatada_redir = data_ref.strftime('%d/%m/%Y')

    if not obra_id or not contato_id:
        flash('Selecione uma obra e um contato.', 'warning')
        return redirect(url_for('whatsapp.painel', aba='meta', data=data_formatada_redir))

    try:
        obra = Obra.query.get(int(obra_id))
        contato = WhatsAppContato.query.get(int(contato_id))

        if not obra or not contato:
            flash('Obra ou contato não encontrado.', 'danger')
            return redirect(url_for('whatsapp.painel', aba='meta', data=data_formatada_redir))

        obras_dados, data_formatada, _ = StockCalculator.calcular_dados_obras_whatsapp([obra], data_referencia=data_ref)
        dados_obra = obras_dados[0] if obras_dados else None

        if not dados_obra:
            flash('Não foi possível compilar dados da obra.', 'danger')
            return redirect(url_for('whatsapp.painel', aba='meta', data=data_formatada_redir))

        wpp = WhatsAppOficial()

        if modo_envio == 'template':
            template_name = "relatorio_diario_obra"
            template_language = "pt_BR"
            params = dados_obra['params_template']
            sucesso, resposta = wpp.enviar_template(
                destinatario=contato.numero,
                template_name=template_name,
                language_code=template_language,
                body_parameters=params
            )
            msg_salvar = f"[TEMPLATE: {template_name} | {data_formatada}] {', '.join(params)}"
            tipo_log = 'meta_template'
        else:
            mensagem = mensagem_personalizada if mensagem_personalizada else dados_obra['mensagem_texto']
            sucesso, resposta = wpp.enviar_texto(contato.numero, mensagem)
            msg_salvar = mensagem[:500]
            tipo_log = 'meta_texto'

        log = WhatsAppLog(
            contato_id=contato.id, obra_id=obra.id, tipo_envio=tipo_log,
            mensagem=msg_salvar, status='sucesso' if sucesso else 'erro'
        )
        db.session.add(log)
        db.session.commit()

        if sucesso:
            flash(f'✅ Relatório ({data_formatada}) enviado para {contato.nome}!', 'success')
        else:
            flash(f'❌ Erro Meta API: {resposta}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'⚠️ Erro inesperado: {str(e)}', 'danger')

    return redirect(url_for('whatsapp.painel', aba='meta', data=data_formatada_redir))


@whatsapp_bp.route('/whatsapp/contatos', methods=['GET', 'POST'])
@admin_required
def contatos():
    if request.method == 'POST':
        try:
            contato_id = request.form.get('contato_id', '').strip()
            nome, funcao, numero = request.form.get('nome', '').strip(), request.form.get('funcao', '').strip(), request.form.get('numero', '').strip()
            horario_envio = request.form.get('horario_envio', '07:00')
            receber_alertas = request.form.get('receber_alertas') == '1'
            receber_emergenciais = request.form.get('receber_emergenciais') == '1'
            obras_selecionadas = request.form.getlist('obras')

            if contato_id:
                contato = WhatsAppContato.query.get_or_404(int(contato_id))
                contato.nome, contato.funcao, contato.numero, contato.horario_envio = nome, funcao, numero, horario_envio
                contato.receber_alertas_programados, contato.receber_emergenciais = receber_alertas, receber_emergenciais
                contato.obras = Obra.query.filter(Obra.id.in_([int(o) for o in obras_selecionadas])).all()
                flash('Contato atualizado!', 'success')
            else:
                novo_c = WhatsAppContato(
                    nome=nome, funcao=funcao, numero=numero, horario_envio=horario_envio,
                    receber_alertas_programados=receber_alertas, receber_emergenciais=receber_emergenciais
                )
                novo_c.obras = Obra.query.filter(Obra.id.in_([int(o) for o in obras_selecionadas])).all()
                db.session.add(novo_c)
                flash('Contato cadastrado!', 'success')
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Erro: {str(e)}', 'danger')
        return redirect(url_for('whatsapp.contatos'))

    return render_template(
        'whatsapp_contatos.html',
        contatos=WhatsAppContato.query.order_by(WhatsAppContato.nome).all(),
        obras_lista=Obra.query.filter_by(ativa=True).order_by(Obra.nome).all()
    )


@whatsapp_bp.route('/whatsapp/contato/toggle/<int:id>', methods=['POST'])
@admin_required
def toggle_contato(id):
    c = WhatsAppContato.query.get_or_404(id)
    c.ativo = not c.ativo
    db.session.commit()
    flash(f'Contato {c.nome} {"ativado" if c.ativo else "inativado"}!', 'info')
    return redirect(url_for('whatsapp.contatos'))


@whatsapp_bp.route('/whatsapp/contato/excluir/<int:id>', methods=['POST'])
@admin_required
def excluir_contato(id):
    c = WhatsAppContato.query.get_or_404(id)
    nome = c.nome
    try:
        db.session.delete(c)
        db.session.commit()
        flash(f'Contato {nome} excluído!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'danger')
    return redirect(url_for('whatsapp.contatos'))


@whatsapp_bp.route('/whatsapp/envio-emergencial', methods=['POST'])
@admin_required
def envio_emergencial():
    from app.services.agendador import AgendadorWhatsApp
    agendador = AgendadorWhatsApp(current_app._get_current_object())
    sucesso, resultados = agendador.envio_emergencial()
    if sucesso:
        flash(f'🚨 Alerta emergencial enviado para {len(resultados)} contatos!', 'success')
    else:
        flash(f'Erro: {resultados}', 'danger')
    return redirect(url_for('whatsapp.contatos'))