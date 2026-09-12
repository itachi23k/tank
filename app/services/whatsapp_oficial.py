"""
Serviço WhatsApp via Meta API Oficial (WhatsApp Cloud API)
"""
import os
import requests
from datetime import datetime
from collections import defaultdict


class WhatsAppOficial:
    
    def __init__(self, app=None):
        self.token = os.environ.get('WHATSAPP_TOKEN', '')
        self.phone_number_id = os.environ.get('WHATSAPP_PHONE_ID', '')
        self.api_url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"
    
    def enviar_texto(self, destinatario, mensagem):
        """Envia mensagem de texto via API oficial do Meta."""
        if not self.token or not self.phone_number_id:
            return False, "Credenciais Meta não configuradas (.env)"
        
        try:
            numero = str(destinatario).strip().replace('+', '').replace(' ', '')
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            data = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": numero,
                "type": "text",
                "text": {
                    "preview_url": False,
                    "body": mensagem
                }
            }
            response = requests.post(self.api_url, headers=headers, json=data, timeout=15)
            if response.status_code in (200, 201):
                return True, "Enviado com sucesso"
            else:
                erro = response.json()
                return False, erro.get('error', {}).get('message', 'Erro desconhecido da Meta API')
        except Exception as e:
            return False, str(e)

    def enviar_template(self, destinatario, template_name="relatorio_diario_obra", language_code="pt_BR", body_parameters=None):
        """Envia mensagem estruturada por Template via WhatsApp Cloud API."""
        if not self.token or not self.phone_number_id:
            return False, "Credenciais Meta não configuradas"

        try:
            numero = str(destinatario).strip().replace('+', '').replace(' ', '')
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            components = []
            if body_parameters:
                params = [{"type": "text", "text": str(p)} for p in body_parameters]
                components.append({
                    "type": "body",
                    "parameters": params
                })

            data = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": numero,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {
                        "code": language_code
                    }
                }
            }
            if components:
                data["template"]["components"] = components

            response = requests.post(self.api_url, headers=headers, json=data, timeout=15)
            if response.status_code in (200, 201):
                return True, f"Template '{template_name}' enviado com sucesso"
            else:
                erro = response.json()
                return False, erro.get('error', {}).get('message', 'Erro na API da Meta')
        except Exception as e:
            return False, str(e)

    def montar_parametros_template_obra(self, obra, tanques_fixos, comboios_moveis, resumo_tipos, data_formatada=None):
        """Gera a lista ordenada de 5 parâmetros para o template homologado."""
        data_str = data_formatada if data_formatada else datetime.now().strftime('%d/%m/%Y')
        obra_str = f"{obra.codigo} - {obra.nome}"

        if tanques_fixos:
            canteiro_tipos = defaultdict(float)
            for t in tanques_fixos:
                tipo = t.get('tipo_combustivel', 'DIESEL S10')
                canteiro_tipos[tipo] += t.get('saldo', 0)
            canteiro_str = " | ".join([f"{tipo}: {self._formatar_numero(s)}L" for tipo, s in sorted(canteiro_tipos.items())])
        else:
            canteiro_str = "Sem saldo"

        if comboios_moveis:
            comboios_str = " | ".join([f"{c['nome']}: {self._formatar_numero(c.get('saldo', 0))}L" for c in comboios_moveis])
        else:
            comboios_str = "Nenhum em operação"

        if resumo_tipos:
            resumo_str = " | ".join([f"{tipo}: {self._formatar_numero(dados['disponivel'])}L" for tipo, dados in sorted(resumo_tipos.items())])
        else:
            resumo_str = "Sem movimentação"

        return [data_str, obra_str, canteiro_str, comboios_str, resumo_str]

    def _formatar_numero(self, valor):
        return f"{valor:,.0f}".replace(',', '.')

    def montar_relatorio_diario(self, obra, tanques_fixos, comboios_moveis, resumo_tipos, data_formatada=None):
        """Monta o relatório diário formatado para envio direto ou cópia."""
        data_str = data_formatada if data_formatada else datetime.now().strftime('%d/%m/%Y')
        mensagem = "📊 *RELATÓRIO DIÁRIO DE COMBUSTÍVEIS*\n"
        mensagem += f"📅 _{data_str}_\n\n"
        mensagem += "===============================\n"
        mensagem += f"⛽ *{obra.nome}* ({obra.codigo})\n"
        if obra.local:
            mensagem += f"📍 _{obra.local}_\n"

        mensagem += "\n🛢️ *CANTEIRO (ESTOQUE FIXO)*\n"
        if tanques_fixos:
            canteiro_tipos = defaultdict(float)
            for tanque in tanques_fixos:
                tipo_combustivel = tanque.get('tipo_combustivel', 'DIESEL S10')
                canteiro_tipos[tipo_combustivel] += tanque['saldo']
            for tipo, saldo in sorted(canteiro_tipos.items()):
                mensagem += f"  • {tipo}: *{self._formatar_numero(saldo)}L*\n"
        else:
            mensagem += "  _Sem saldo em canteiro_\n"

        mensagem += "\n🚜 *COMBOIOS (ESTOQUE MÓVEL)*\n"
        if comboios_moveis:
            for comboio in comboios_moveis:
                tipo = comboio.get('tipo_combustivel', 'DIESEL S10')
                mensagem += f"  • {comboio['nome']} ({tipo}): *{self._formatar_numero(comboio['saldo'])}L*\n"
        else:
            mensagem += "  _Nenhum comboio em operação_\n"

        mensagem += "\n📊 *RESUMO POR TIPO*\n"
        if resumo_tipos:
            for tipo, dados in sorted(resumo_tipos.items()):
                mensagem += f"  • {tipo}: *{self._formatar_numero(dados['disponivel'])}L*\n"

        mensagem += "\n⚙️ _Gerado via T.A.N.K - Gestão Inteligente de Combustíveis_"
        return mensagem