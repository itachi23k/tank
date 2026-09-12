"""
Agendador de tarefas - Envio programado respeitando horário individual e emergencial
"""
import time
import threading
from datetime import datetime
from collections import defaultdict
from flask import current_app
from app import db
from app.models import Obra, Fornecedor, Abastecimento, EntradaInsumo, Transferencia, WhatsAppContato, WhatsAppLog
from app.services.whatsapp_oficial import WhatsAppOficial


class AgendadorWhatsApp:
    def __init__(self, app):
        self.app = app
        self.whatsapp = WhatsAppOficial(app)
        self.thread = None
        self.ultimos_envios = set()

    def _calcular_saldo_tanque(self, fornecedor):
        entradas = db.session.query(db.func.sum(EntradaInsumo.quantidade)).filter_by(
            fornecedor_id=fornecedor.id
        ).scalar() or 0
        saidas = db.session.query(db.func.sum(Abastecimento.quantidade)).filter_by(
            fornecedor_id=fornecedor.id
        ).scalar() or 0
        transf_recebidas = db.session.query(db.func.sum(Transferencia.litros)).filter_by(
            destino_id=fornecedor.id
        ).scalar() or 0
        transf_enviadas = db.session.query(db.func.sum(Transferencia.litros)).filter_by(
            origem_id=fornecedor.id
        ).scalar() or 0
        estoque_inicial = fornecedor.estoque_inicial or 0
        return estoque_inicial + entradas + transf_recebidas - saidas - transf_enviadas

    def _processar_contato(self, contato):
        """
        Envia relatório para um contato no horário programado.
        """
        obras_contato = contato.obras if contato.obras else Obra.query.filter_by(ativa=True).all()
        if not obras_contato:
            print(f"[AVISO] Contato {contato.nome} sem obras vinculadas")
            return

        for obra in obras_contato:
            if not obra.ativa:
                continue

            tanques = Fornecedor.query.filter_by(
                obra_id=obra.id,
                tipo_origem='Interno',
                ativo=True
            ).all()

            tanques_fixos = []
            comboios_moveis = []
            resumo_tipos = defaultdict(lambda: {'disponivel': 0, 'capacidade': 0})

            for t in tanques:
                saldo = self._calcular_saldo_tanque(t)
                tipo_combustivel = t.tipo_combustivel or 'DIESEL S10'
                categoria = t.categoria_tanque or 'Tanque'

                item = {
                    'nome': t.nome,
                    'saldo': saldo,
                    'capacidade': t.capacidade_litros,
                    'tipo_combustivel': tipo_combustivel,
                    'categoria': categoria
                }

                if categoria == 'Comboio':
                    comboios_moveis.append(item)
                else:
                    tanques_fixos.append(item)

                resumo_tipos[tipo_combustivel]['disponivel'] += saldo
                if t.capacidade_litros:
                    resumo_tipos[tipo_combustivel]['capacidade'] += t.capacidade_litros

            mensagem = self.whatsapp.montar_relatorio_diario(
                obra, tanques_fixos, comboios_moveis, resumo_tipos
            )
            sucesso, resposta = self.whatsapp.enviar_texto(contato.numero, mensagem)

            log = WhatsAppLog(
                contato_id=contato.id,
                obra_id=obra.id,
                tipo_envio='programado',
                mensagem=mensagem[:500],
                status='sucesso' if sucesso else 'erro'
            )
            db.session.add(log)
            db.session.commit()

            print(f"   [{datetime.now().strftime('%H:%M')}] {contato.nome} -> {obra.codigo}: {resposta}")
            time.sleep(2)

    def _verificar_envios_por_horario(self):
        """
        Verifica a cada 30s se existe contato ativo com horario_envio igual à hora atual.
        """
        with self.app.app_context():
            hora_atual = datetime.now().strftime('%H:%M')
            contatos = WhatsAppContato.query.filter_by(
                ativo=True,
                receber_alertas_programados=True,
                horario_envio=hora_atual
            ).all()

            if contatos:
                print(f"[{datetime.now()}] [DISPARO] Enviando para {len(contatos)} contato(s) as {hora_atual}")

            hoje_prefix = datetime.now().strftime('%Y%m%d')
            # Limpa chaves de dias anteriores para manter uso de memória sob controle
            if len(self.ultimos_envios) > 200:
                self.ultimos_envios = {k for k in self.ultimos_envios if f"_{hoje_prefix}" in k}

            for contato in contatos:
                chave = f"{contato.id}_{hoje_prefix}{datetime.now().strftime('%H%M')}"
                if chave in self.ultimos_envios:
                    continue
                self.ultimos_envios.add(chave)
                self._processar_contato(contato)

    def envio_emergencial(self, obra_id=None, contato_ids=None):
        """
        Envio emergencial (manual) para contatos específicos.
        Mantido igual ao original.
        """
        with self.app.app_context():
            print(f"\n[{datetime.now()}] [EMERGENCIAL] INICIANDO ENVIO EMERGENCIAL")

            if contato_ids:
                contatos = WhatsAppContato.query.filter(
                    WhatsAppContato.id.in_(contato_ids),
                    WhatsAppContato.ativo == True
                ).all()
            elif obra_id:
                contatos = WhatsAppContato.query.filter(
                    WhatsAppContato.ativo == True,
                    WhatsAppContato.obras.any(id=obra_id)
                ).all()
            else:
                contatos = WhatsAppContato.query.filter_by(ativo=True).all()

            if not contatos:
                return False, "Nenhum contato encontrado"

            resultados = []
            for contato in contatos:
                obras_contato = contato.obras if contato.obras else Obra.query.filter_by(ativa=True).all()

                for obra in obras_contato:
                    if obra_id and obra.id != int(obra_id):
                        continue

                    tanques = Fornecedor.query.filter_by(
                        obra_id=obra.id,
                        tipo_origem='Interno',
                        ativo=True
                    ).all()

                    tanques_fixos = []
                    comboios_moveis = []
                    resumo_tipos = defaultdict(lambda: {'disponivel': 0, 'capacidade': 0})

                    for t in tanques:
                        saldo = self._calcular_saldo_tanque(t)
                        tipo_combustivel = t.tipo_combustivel or 'DIESEL S10'
                        categoria = t.categoria_tanque or 'Tanque'

                        item = {
                            'nome': t.nome,
                            'saldo': saldo,
                            'capacidade': t.capacidade_litros,
                            'tipo_combustivel': tipo_combustivel,
                            'categoria': categoria
                        }

                        if categoria == 'Comboio':
                            comboios_moveis.append(item)
                        else:
                            tanques_fixos.append(item)

                        resumo_tipos[tipo_combustivel]['disponivel'] += saldo
                        if t.capacidade_litros:
                            resumo_tipos[tipo_combustivel]['capacidade'] += t.capacidade_litros

                    mensagem = "🚨 *ALERTA EMERGENCIAL*\n\n"
                    mensagem += self.whatsapp.montar_relatorio_diario(
                        obra, tanques_fixos, comboios_moveis, resumo_tipos
                    )

                    sucesso, resposta = self.whatsapp.enviar_texto(contato.numero, mensagem)

                    log = WhatsAppLog(
                        contato_id=contato.id,
                        obra_id=obra.id,
                        tipo_envio='emergencial',
                        mensagem=mensagem[:500],
                        status='sucesso' if sucesso else 'erro'
                    )
                    db.session.add(log)

                    resultados.append({
                        'contato': contato.nome,
                        'obra': obra.codigo,
                        'sucesso': sucesso,
                        'resposta': resposta
                    })

                    time.sleep(2)

            db.session.commit()
            return True, resultados

    def iniciar(self):
        """
        Inicia o agendador em thread separada, verificando a cada 30 segundos
        se existe contato com horario_envio igual à hora atual.
        """
        print("[OK] Agendador WhatsApp iniciado!")
        print("[INFO] Envio programado respeitando horario individual")

        def run_schedule():
            while True:
                self._verificar_envios_por_horario()
                time.sleep(30)

        self.thread = threading.Thread(target=run_schedule, daemon=True)
        self.thread.start()