# run.py
import os
import sys
import glob

base_dir = os.path.dirname(os.path.abspath(__file__))

# Suporte automático a venv local (.venv)
venv_site_pkgs = glob.glob(os.path.join(base_dir, '.venv', 'lib', 'python*', 'site-packages'))
for p in venv_site_pkgs:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

site_pkgs = os.path.join(base_dir, 'site-packages')
if os.path.exists(site_pkgs) and site_pkgs not in sys.path:
    sys.path.insert(0, site_pkgs)

import socket
import argparse
from app import create_app

# Garantir suporte UTF-8 no terminal Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

app = create_app()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="T.A.N.K - Gestão de Frota")
    parser.add_argument('--port', type=int, default=3000, help='Porta do servidor')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host do servidor')
    args, _ = parser.parse_known_args()

    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = '127.0.0.1'
    
    print("=" * 60)
    print("🚛 T.A.N.K - Gestão de Frota - Servidor de Desenvolvimento")
    print("=" * 60)
    print(f"📡 Servidor rodando em: http://{args.host}:{args.port}")
    print("=" * 60)
    
    # Roda o servidor na porta especificada
    app.run(debug=False, host=args.host, port=args.port)