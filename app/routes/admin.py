from flask import Blueprint, Response, request, flash, redirect, url_for, current_app
from flask_login import current_user
from app.routes.auth import admin_required
from app.services.backup_service import BackupService

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/backup-json')
@admin_required
def backup_json():
    json_data = BackupService.gerar_backup_json()
    response = current_app.response_class(response=json_data, mimetype='application/json')
    response.headers['Content-Disposition'] = 'attachment; filename=TANK_Backup.json'
    return response


@admin_bp.route('/restore-backup', methods=['POST'])
@admin_required
def restore_backup():
    file = request.files['backup_file']
    mode = request.form.get('mode', 'merge')
    try:
        BackupService.restaurar_backup(file, mode, current_user.id)
        flash('Dados importados com sucesso! Sessão e usuários preservados.', 'success')
    except Exception as e:
        flash(f'Erro ao restaurar: {str(e)}', 'danger')
    return redirect(url_for('dashboard.index'))


@admin_bp.route('/export-obras-csv')
@admin_required
def export_obras_csv():
    csv_data = BackupService.exportar_obras_csv()
    return Response(csv_data, mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=obras.csv'})


@admin_bp.route('/export-movimentacoes-csv')
@admin_required
def export_movimentacoes_csv():
    csv_data = BackupService.exportar_movimentacoes_csv()
    return Response(csv_data, mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=movimentacoes.csv'})


@admin_bp.route('/reset-database', methods=['POST'])
@admin_required
def reset_database():
    try:
        BackupService.reset_database()
        flash('Banco restaurado para estado inicial. Faça login com o usuário padrão.', 'warning')
    except Exception as e:
        flash(f'Erro ao resetar banco: {str(e)}', 'danger')
    return redirect(url_for('auth.login'))