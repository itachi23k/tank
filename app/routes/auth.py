from functools import wraps
from urllib.parse import urlsplit
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import Usuario

auth_bp = Blueprint('auth', __name__)


def is_safe_url(target):
    """Garante que o redirecionamento pós-login seja interno e seguro."""
    if not target:
        return False
    ref_url = urlsplit(request.host_url)
    test_url = urlsplit(target)
    return (not test_url.scheme and not test_url.netloc) or (test_url.netloc == ref_url.netloc)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Acesso negado. Funcionalidade restrita a Administradores.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function


def lancador_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_lancador:
            flash('Acesso negado. Você não tem permissão para realizar lançamentos.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and usuario.check_senha(senha):
            if not usuario.ativo:
                flash('Usuário inativo. Entre em contato com o Administrador.', 'warning')
                return render_template('login.html')

            login_user(usuario)
            flash(f'Bem-vindo de volta, {usuario.nome}!', 'success')
            
            next_page = request.args.get('next')
            if not is_safe_url(next_page):
                next_page = url_for('dashboard.index')
            return redirect(next_page)

        flash('E-mail ou senha incorretos. Tente novamente.', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sessão encerrada com sucesso.', 'info')
    return redirect(url_for('auth.login'))