"""
Utilitários de validação, conversão numérica e integridade de dados para o T.A.N.K.
"""
from typing import Optional, Dict, Any, Tuple
from app import db
from app.models import Abastecimento, Fornecedor
from sqlalchemy import func


def parse_float_ptbr(valor: Any, campo_nome: str = "Valor", positivo: bool = False, permitir_nulo: bool = True) -> Optional[float]:
    """
    Converte valores numéricos em string para float, suportando notação brasileira (vírgula decimal,
    ponto de milhar) e internacional.
    Exemplos aceitos:
      - '1.250,50' -> 1250.50
      - '1,250.50' -> 1250.50
      - '1250,50'  -> 1250.50
      - '1250.50'  -> 1250.50
      - 150        -> 150.0
    """
    if valor is None:
        if not permitir_nulo:
            raise ValueError(f"O campo {campo_nome} é obrigatório.")
        return None

    if isinstance(valor, (int, float)):
        v_num = float(valor)
    else:
        v_str = str(valor).strip()
        if not v_str:
            if not permitir_nulo:
                raise ValueError(f"O campo {campo_nome} é obrigatório.")
            return None

        # Remove caracteres indesejados mantendo dígitos, pontos, vírgulas e sinal
        v_str = v_str.replace(' ', '')

        if '.' in v_str and ',' in v_str:
            if v_str.find('.') < v_str.find(','):
                # Padrão BR: 1.250,50 -> 1250.50
                v_str = v_str.replace('.', '').replace(',', '.')
            else:
                # Padrão US: 1,250.50 -> 1250.50
                v_str = v_str.replace(',', '')
        elif ',' in v_str:
            # Padrão BR simples: 150,50 -> 150.50
            v_str = v_str.replace(',', '.')

        try:
            v_num = float(v_str)
        except ValueError:
            raise ValueError(f"Valor numérico inválido para o campo {campo_nome}: '{valor}'.")

    if positivo and v_num <= 0:
        raise ValueError(f"O campo {campo_nome} deve ser maior que zero (recebido: {v_num}).")

    return v_num


def normalizar_combustivel(nome: Optional[str]) -> str:
    """
    Normaliza a nomenclatura de combustíveis e insumos para as categorias canônicas do sistema.
    """
    if not nome:
        return 'DIESEL S10'

    n = str(nome).strip().upper()
    if n in ['S10', 'DIESEL S-10', 'DIESEL S 10', 'DIESELS10']:
        return 'DIESEL S10'
    elif n in ['S500', 'DIESEL S-500', 'DIESEL S 500', 'DIESELS500']:
        return 'DIESEL S500'
    elif n in ['GASOLINA', 'GASOLINA COMUM']:
        return 'GASOLINA COMUM'
    elif n in ['ARLA', 'ARLA 32', 'ARLA32']:
        return 'ARLA 32'
    elif 'LUBRIFICANTE' in n or 'OLEO' in n or 'ÓLEO' in n:
        return 'OLEO LUBRIFICANTE'
    elif 'GRAXA' in n:
        return 'GRAXA'
    return n


def validar_compatibilidade_posto(fornecedor: Optional[Fornecedor], insumo: str) -> Tuple[bool, str]:
    """
    Verifica se o combustível/insumo é compatível com o tipo armazenado no posto/tanque/comboio.
    """
    if not fornecedor:
        return False, "Posto ou fornecedor não informado."

    tipo_forn = normalizar_combustivel(fornecedor.tipo_combustivel)
    tipo_ins = normalizar_combustivel(insumo)

    # Postos externos podem fornecer mais de um combustível caso não tenham tanque restrito
    if fornecedor.tipo_origem == 'Externo' and not fornecedor.tipo_combustivel:
        return True, ""

    if tipo_forn != tipo_ins:
        return False, f"O posto/tanque '{fornecedor.nome}' armazena {tipo_forn}, mas foi informado {tipo_ins}."

    return True, ""


def obter_ultimas_leituras_equipamentos() -> Dict[int, Dict[str, Optional[float]]]:
    """
    Retorna as últimas leituras de hodômetro e horímetro de cada equipamento ativo em 2 consultas otimizadas.
    """
    try:
        # Último hodômetro
        sub_h = db.session.query(
            Abastecimento.equipamento_id,
            func.max(Abastecimento.id).label('max_id')
        ).filter(Abastecimento.hodometro.isnot(None)).group_by(Abastecimento.equipamento_id).subquery()

        hodos = dict(db.session.query(Abastecimento.equipamento_id, Abastecimento.hodometro).join(
            sub_h, Abastecimento.id == sub_h.c.max_id
        ).all())

        # Último horímetro
        sub_hr = db.session.query(
            Abastecimento.equipamento_id,
            func.max(Abastecimento.id).label('max_id')
        ).filter(Abastecimento.horimetro.isnot(None)).group_by(Abastecimento.equipamento_id).subquery()

        horis = dict(db.session.query(Abastecimento.equipamento_id, Abastecimento.horimetro).join(
            sub_hr, Abastecimento.id == sub_hr.c.max_id
        ).all())

        equip_ids = set(hodos.keys()).union(set(horis.keys()))
        resultado = {}
        for eid in equip_ids:
            resultado[eid] = {
                'hodometro': hodos.get(eid),
                'horimetro': horis.get(eid)
            }
        return resultado
    except Exception:
        return {}
