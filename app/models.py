from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager

# ==========================================
# 1. TABELA DE OBRAS (DEVE VIR PRIMEIRO!)
# ==========================================
class Obra(db.Model):
    __tablename__ = 'obras'
    
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False, index=True)
    nome = db.Column(db.String(150), nullable=False)
    local = db.Column(db.String(200))
    responsavel = db.Column(db.String(100))
    ativa = db.Column(db.Boolean, default=True, nullable=False)
    data_inicio = db.Column(db.Date)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos (usando string para evitar referência cruzada)
    abastecimentos = db.relationship('Abastecimento', backref='obra_rel', lazy=True)
    entradas = db.relationship('EntradaInsumo', backref='obra_rel', lazy=True)
    transferencias = db.relationship('Transferencia', backref='obra_rel', lazy=True)
    fornecedores = db.relationship('Fornecedor', backref='obra_rel', lazy=True)
    usuarios = db.relationship('Usuario', backref='obra_rel', lazy=True, foreign_keys='Usuario.obra_padrao_id')
    frentes_servico = db.relationship('FrenteServico', backref='obra_rel', lazy=True)
    
    def __repr__(self):
        return f"<Obra {self.codigo} - {self.nome}>"


# ==========================================
# 2. TABELA DE USUÁRIOS E PERMISSÕES (RBAC)
# ==========================================
class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    
    # Níveis de Acesso: 'administrador', 'lancador', 'leitor'
    nivel_acesso = db.Column(db.String(20), nullable=False, default='lancador')
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NOVO: Acesso a obras
    acesso_global = db.Column(db.Boolean, default=False)  # True = vê todas as obras
    obra_padrao_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=True)
    
    # Relacionamentos existentes
    abastecimentos_lancados = db.relationship('Abastecimento', backref='usuario_lancador', lazy=True)
    
    def set_senha(self, senha):
        """Gera o hash criptografado da senha."""
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        """Verifica se a senha informada corresponde ao hash salvo."""
        return check_password_hash(self.senha_hash, senha)

    @property
    def is_admin(self):
        return self.nivel_acesso == 'administrador'

    @property
    def is_lancador(self):
        return self.nivel_acesso in ['administrador', 'lancador']
    
    @property
    def is_global(self):
        """Usuário pode ver todas as obras?"""
        return self.acesso_global or self.is_admin

    def __repr__(self):
        return f"<Usuario {self.nome} ({self.nivel_acesso})>"


@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


# ==========================================
# 3. TABELA DE EQUIPAMENTOS (FROTA)
# ==========================================
class Equipamento(db.Model):
    __tablename__ = 'equipamentos'

    id = db.Column(db.Integer, primary_key=True)
    prefixo_placa = db.Column(db.String(30), unique=True, nullable=False, index=True)
    descricao = db.Column(db.String(100), nullable=True)
    tipo_equipamento = db.Column(db.String(50), nullable=True)
    locador = db.Column(db.String(100), nullable=True, default='CENTRAL DE EQUIPAMENTOS')
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamento: Todos os abastecimentos efetuados para esta máquina
    abastecimentos = db.relationship('Abastecimento', backref='equipamento_rel', lazy=True)
    alocacoes_frente = db.relationship('AlocacaoFrenteEquipamento', backref='equipamento_rel', lazy=True)

    def __repr__(self):
        return f"<Equipamento {self.prefixo_placa}>"


# ==========================================
# 3.1 TABELA DE FRENTES DE SERVIÇO E ALOCAÇÃO EM LOTE
# ==========================================
class FrenteServico(db.Model):
    __tablename__ = 'frentes_servico'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, index=True)
    descricao = db.Column(db.String(200), nullable=True)
    ativa = db.Column(db.Boolean, default=True, nullable=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=True, index=True)

    # Relacionamentos
    alocacoes = db.relationship('AlocacaoFrenteEquipamento', backref='frente_rel', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"<FrenteServico {self.nome}>"


class AlocacaoFrenteEquipamento(db.Model):
    """
    Representa o período de atuação em lote de um ou vários equipamentos em uma frente de serviço.
    """
    __tablename__ = 'alocacoes_frente_equipamento'

    id = db.Column(db.Integer, primary_key=True)
    frente_servico_id = db.Column(db.Integer, db.ForeignKey('frentes_servico.id'), nullable=False, index=True)
    equipamento_id = db.Column(db.Integer, db.ForeignKey('equipamentos.id'), nullable=False, index=True)
    data_inicio = db.Column(db.Date, nullable=False, index=True)
    data_fim = db.Column(db.Date, nullable=False, index=True)
    observacao = db.Column(db.String(200), nullable=True)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AlocacaoFrente {self.equipamento_id} -> Frente #{self.frente_servico_id} ({self.data_inicio} a {self.data_fim})>"


# ==========================================
# 4. TABELA DE FORNECEDORES / POSTOS / COMBOIOS
# ==========================================
class Fornecedor(db.Model):
    __tablename__ = 'fornecedores'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False, index=True)
    tipo_origem = db.Column(db.String(30), default='Interno')
    capacidade_litros = db.Column(db.Float, nullable=True)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=True, index=True)
    
    # NOVOS CAMPOS
    estoque_inicial = db.Column(db.Float, default=0.0, nullable=True)  # Saldo inicial do tanque
    categoria_tanque = db.Column(db.String(30), default='Tanque', nullable=True)  # 'Tanque', 'Comboio', 'Posto Externo'
    tipo_combustivel = db.Column(db.String(50), default='DIESEL S10', nullable=True)  # 'DIESEL S10', 'DIESEL S500', 'GASOLINA COMUM', etc.
    
    # Relacionamentos
    abastecimentos = db.relationship('Abastecimento', backref='fornecedor_rel', lazy=True)

    def __repr__(self):
        return f"<Fornecedor {self.nome} ({self.categoria_tanque} - {self.tipo_combustivel})>"


# ==========================================
# 5. TABELA PRINCIPAL DE ABASTECIMENTOS
# ==========================================
class Abastecimento(db.Model):
    __tablename__ = 'abastecimentos'

    id = db.Column(db.Integer, primary_key=True)
    data_abastecimento = db.Column(db.Date, nullable=False, index=True)
    categoria_insumo = db.Column(db.String(50), nullable=False, index=True)
    quantidade = db.Column(db.Float, nullable=False)
    hodometro = db.Column(db.Float, nullable=True)
    horimetro = db.Column(db.Float, nullable=True)
    descricao_obs = db.Column(db.String(255), nullable=True)
    frente_servico = db.Column(db.String(100), nullable=True, index=True)
    
    # Rastreabilidade da Ingestão de Planilhas (Contingência)
    arquivo_origem = db.Column(db.String(150), nullable=True)
    aba_origem = db.Column(db.String(50), nullable=True)
    linha_planilha = db.Column(db.Integer, nullable=True)
    hash_registro = db.Column(db.String(64), unique=True, nullable=True)

    # Chaves Estrangeiras
    equipamento_id = db.Column(db.Integer, db.ForeignKey('equipamentos.id'), nullable=False, index=True)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedores.id'), nullable=True, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    
    # NOVO: Vinculação com obra
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=True, index=True)

    data_registro_sistema = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Abastecimento {self.data_abastecimento} | Qtd: {self.quantidade}>"


# ==========================================
# 6. TABELA DE ENTRADAS DE INSUMO
# ==========================================
class EntradaInsumo(db.Model):
    __tablename__ = 'entradas_insumos'

    id = db.Column(db.Integer, primary_key=True)
    data_entrada = db.Column(db.Date, nullable=False)
    categoria_insumo = db.Column(db.String(50), nullable=False)
    quantidade = db.Column(db.Float, nullable=False)
    numero_nf = db.Column(db.String(50), nullable=True)
    
    # Chaves Estrangeiras
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedores.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    
    # NOVO: Vinculação com obra
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=True, index=True)

    # Relacionamentos
    fornecedor_rel = db.relationship('Fornecedor', backref='entradas_recebidas')
    usuario_rel = db.relationship('Usuario', backref='entradas_registradas')


# ==========================================
# 7. TABELA DE TRANSFERÊNCIAS
# ==========================================
class Transferencia(db.Model):
    __tablename__ = 'transferencias'

    id = db.Column(db.Integer, primary_key=True)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    litros = db.Column(db.Float, nullable=False)
    tipo_combustivel = db.Column(db.String(20), nullable=False, default='S10')
    observacao = db.Column(db.String(200))
    
    # Chaves Estrangeiras
    origem_id = db.Column(db.Integer, db.ForeignKey('fornecedores.id'), nullable=False)
    destino_id = db.Column(db.Integer, db.ForeignKey('fornecedores.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    
    # NOVO: Vinculação com obra
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=True, index=True)

    # Relacionamentos
    origem = db.relationship('Fornecedor', foreign_keys=[origem_id])
    destino = db.relationship('Fornecedor', foreign_keys=[destino_id])


class WhatsAppContato(db.Model):
    __tablename__ = 'whatsapp_contatos'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    funcao = db.Column(db.String(100))
    numero = db.Column(db.String(20), nullable=False, unique=True)
    ativo = db.Column(db.Boolean, default=True)
    receber_alertas_programados = db.Column(db.Boolean, default=True)
    receber_emergenciais = db.Column(db.Boolean, default=True)  # NOVO
    horario_envio = db.Column(db.String(5), default='07:00')     # NOVO
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    
    obras = db.relationship('Obra', secondary='whatsapp_contato_obra', backref='contatos_whatsapp')
    
    def __repr__(self):
        return f"<WhatsAppContato {self.nome} - {self.numero}>"


# Tabela associativa: contato x obra
whatsapp_contato_obra = db.Table(
    'whatsapp_contato_obra',
    db.Column('contato_id', db.Integer, db.ForeignKey('whatsapp_contatos.id'), primary_key=True),
    db.Column('obra_id', db.Integer, db.ForeignKey('obras.id'), primary_key=True)
)


class WhatsAppLog(db.Model):
    """
    Histórico de envios realizados
    """
    __tablename__ = 'whatsapp_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    contato_id = db.Column(db.Integer, db.ForeignKey('whatsapp_contatos.id'))
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=True)
    tipo_envio = db.Column(db.String(20))  # 'programado' ou 'emergencial'
    mensagem = db.Column(db.Text)
    status = db.Column(db.String(20))  # 'sucesso', 'erro'
    data_envio = db.Column(db.DateTime, default=datetime.utcnow)
    
    contato = db.relationship('WhatsAppContato', backref='logs')