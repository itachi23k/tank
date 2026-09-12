"""
Serviço responsável pelo processamento e ingestão de planilhas CSV.
"""
import csv
import hashlib
from io import StringIO
from datetime import datetime
from app import db
from app.models import Equipamento, Fornecedor, Abastecimento, Obra, AlocacaoFrenteEquipamento
from app.utils import parse_float_ptbr, normalizar_combustivel, validar_compatibilidade_posto


class CsvImporterService:

    @staticmethod
    def _ler_conteudo(arquivo_stream):
        """Lê o arquivo testando UTF-8 e fallback para ISO-8859-1."""
        try:
            return arquivo_stream.read().decode('utf-8')
        except UnicodeDecodeError:
            arquivo_stream.seek(0)
            return arquivo_stream.read().decode('iso-8859-1')

    @staticmethod
    def _parse_float(valor):
        """Converte strings numéricas com suporte inteligente a vírgula ou ponto como separadores."""
        if valor is None:
            return None
        v = str(valor).strip()
        if not v:
            return None
        if '.' in v and ',' in v:
            if v.find('.') < v.find(','):
                v = v.replace('.', '').replace(',', '.')
            else:
                v = v.replace(',', '')
        elif ',' in v:
            v = v.replace(',', '.')
        return float(v)

    @classmethod
    def importar_equipamentos(cls, arquivo):
        """Processa a importação de frota via CSV."""
        conteudo = cls._ler_conteudo(arquivo)
        reader = csv.DictReader(conteudo.splitlines(), delimiter=';')
        
        sucesso, ignorados, erros = 0, 0, []

        for linha_num, row in enumerate(reader, start=2):
            try:
                prefixo = row.get('PREFIXO', '').strip().upper()
                modelo = row.get('MODELO', '').strip().upper()
                tipo = row.get('TIPO', '').strip()
                locador = row.get('LOCADOR', '').strip().upper()

                if not prefixo:
                    continue

                if Equipamento.query.filter_by(prefixo_placa=prefixo).first():
                    ignorados += 1
                    continue

                db.session.add(Equipamento(
                    prefixo_placa=prefixo,
                    descricao=modelo or None,
                    tipo_equipamento=tipo or None,
                    locador=locador or 'T.A.N.K',
                    ativo=True
                ))
                sucesso += 1
            except Exception as e:
                erros.append(f"Linha {linha_num}: {str(e)}")

        if sucesso > 0:
            db.session.commit()

        return sucesso, ignorados, erros

    @classmethod
    def importar_abastecimentos(cls, arquivo, obra_id_form, current_user):
        """Processa o CSV de abastecimentos com hash de unicidade e vínculo de obra."""
        conteudo = cls._ler_conteudo(arquivo)
        reader = csv.DictReader(conteudo.splitlines(), delimiter=';')
        
        obra_padrao = Obra.query.get(int(obra_id_form)) if obra_id_form else None
        sucesso, ignorados, erros = 0, 0, []

        for linha_num, row in enumerate(reader, start=2):
            try:
                placa = str(row.get('Placa', '')).strip().upper()
                equip = Equipamento.query.filter_by(prefixo_placa=placa).first()
                if not equip:
                    erros.append(f"Linha {linha_num}: Placa '{placa}' não cadastrada.")
                    continue

                forn_nome = str(row.get('Posto', '')).strip().upper()
                forn = Fornecedor.query.filter_by(nome=forn_nome).first()
                if not forn:
                    erros.append(f"Linha {linha_num}: Posto '{forn_nome}' não cadastrado.")
                    continue

                qtd = cls._parse_float(row.get('Volume')) or 0.0
                if qtd <= 0:
                    erros.append(f"Linha {linha_num}: Volume inválido ({qtd}). Deve ser maior que zero.")
                    continue

                hodo = cls._parse_float(row.get('Hodometro'))
                hori = cls._parse_float(row.get('Horimetro'))

                data_abast = datetime.strptime(str(row.get('Data', '')).strip(), '%d/%m/%Y').date()
                insumo = normalizar_combustivel(str(row.get('Insumo', '')).strip())
                
                compativel, msg_compat = validar_compatibilidade_posto(forn, insumo)
                if not compativel:
                    erros.append(f"Linha {linha_num}: {msg_compat}")
                    continue

                obs = str(row.get('Observacoes', '')).strip().upper()
                frente_csv = str(row.get('FrenteServico', row.get('Frente_Servico', row.get('Frente', '')))).strip().upper() or None

                if not frente_csv:
                    aloc = AlocacaoFrenteEquipamento.query.filter(
                        AlocacaoFrenteEquipamento.equipamento_id == equip.id,
                        AlocacaoFrenteEquipamento.data_inicio <= data_abast,
                        AlocacaoFrenteEquipamento.data_fim >= data_abast
                    ).first()
                    if aloc and aloc.frente_rel:
                        frente_csv = aloc.frente_rel.nome

                # Resolução da Obra
                abast_obra_id = None
                obra_csv = str(row.get('Obra', '')).strip().upper()
                if obra_csv:
                    o_enc = Obra.query.filter_by(codigo=obra_csv).first()
                    if o_enc:
                        abast_obra_id = o_enc.id

                if not abast_obra_id and obra_padrao:
                    abast_obra_id = obra_padrao.id
                if not abast_obra_id and forn.obra_id:
                    abast_obra_id = forn.obra_id
                if not abast_obra_id and current_user.obra_padrao_id:
                    abast_obra_id = current_user.obra_padrao_id

                # Hash SHA-256 para evitar duplicidades no banco
                string_unica = f"{data_abast}{placa}{forn_nome}{qtd}{insumo}{abast_obra_id}"
                hash_reg = hashlib.sha256(string_unica.encode('utf-8')).hexdigest()

                if Abastecimento.query.filter_by(hash_registro=hash_reg).first():
                    ignorados += 1
                    continue

                db.session.add(Abastecimento(
                    data_abastecimento=data_abast,
                    categoria_insumo=insumo,
                    quantidade=qtd,
                    hodometro=hodo,
                    horimetro=hori,
                    descricao_obs=obs,
                    frente_servico=frente_csv,
                    arquivo_origem=arquivo.filename,
                    linha_planilha=linha_num,
                    hash_registro=hash_reg,
                    equipamento_id=equip.id,
                    fornecedor_id=forn.id,
                    obra_id=abast_obra_id,
                    usuario_id=current_user.id
                ))
                sucesso += 1
            except Exception as e:
                erros.append(f"Linha {linha_num}: {str(e)}")

        if sucesso > 0:
            db.session.commit()

        return sucesso, ignorados, erros