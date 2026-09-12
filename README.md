# ⛽ T.A.N.K - Sistema de Gestão de Combustíveis e Insumos

![Versão](https://img.shields.io/badge/versão-1.0.0-blue)
![Python](https://img.shields.io/badge/Python-3.10+-green)
![Flask](https://img.shields.io/badge/Flask-3.0-red)
![Licença](https://img.shields.io/badge/licença-Proprietária-orange)

Sistema ERP web para controle de abastecimento de frotas, gestão de estoque de combustíveis, transbordos entre tanques e controle multi-obras. Desenvolvido para atender demandas de terraplenagem, pavimentação e obras de infraestrutura.

---

## 🚀 Funcionalidades Principais

### 📊 Dashboard
- Cards de consumo e entradas **por tipo de combustível** (Diesel S10, S500, Gasolina, ARLA 32, etc.)
- Status em tempo real dos tanques/comboios com barras de progresso
- Visão segregada **por obra** (multi-tenant)
- Filtro rápido para visualizar dados de uma obra específica

### ⛽ Lançamentos
- Lançamento **em lote** de abastecimentos
- Múltiplas linhas com mesma data e obra
- Filtro dinâmico de fornecedores por obra selecionada
- Registro de hodômetro, horímetro e observações
- Histórico dos últimos lançamentos com opção de exclusão

### 🏗️ Gestão de Obras (Multi-Tenant)
- Cadastro de **múltiplas obras** independentes
- Cada obra com seus próprios tanques, fornecedores e relatórios
- Usuários com acesso **global** ou **restrito por obra**
- Equipamentos podem transitar entre obras diferentes

### 🚜 Gestão de Frota
- Cadastro individual ou **importação CSV em lote**
- 30+ tipos de equipamentos categorizados (veículos, terraplenagem, pavimentação, apoio)
- Controle de status (ativo/inativo)
- Edição e exclusão via modais flutuantes

### 🏪 Fornecedores e Tanques
- Cadastro de postos internos (tanques/comboios) e externos
- **Estoque inicial** configurável (não afeta métricas de "Recebido no Mês")
- Vinculação por obra
- Controle de capacidade e status

### 🔄 Transbordos
- Registro de transferências entre tanques/comboios
- Histórico completo com edição e exclusão
- Impacto automático no saldo físico dos tanques

### 📥 Entradas de Insumo (NFs)
- Registro de notas fiscais de compra
- Vínculo com fornecedor e obra
- Histórico e edição

### 📋 Relatórios
- **Dossiê por Equipamento**: Extrato detalhado com exportação Excel, PDF e CSV
- **Extrato de Fornecedor**: 3 abas (Saídas/Abastecimentos, Entradas/NFs, Transbordos Recebidos)
- **Consolidado Posto x Frota**: Ranking de consumo por equipamento em cada fornecedor
- **Balanço Físico de Estoque**: Entradas, saídas, transbordos e saldo teórico
- **Consumo por Locador**: Agrupamento por empresa locadora

### 📤 Exportações
- **Excel (.xlsx)**: Planilhas formatadas com 2 abas (extrato + resumo)
- **PDF**: Relatórios profissionais com tabelas e gráficos
- **CSV**: Compatível com qualquer planilha
- **Texto Puro**: Valores diários prontos para colar no Excel (A1, A2, A3...)
- **Cópia rápida**: Botões para copiar valores filtrados por tipo de combustível

### 🔐 Controle de Acesso (RBAC)
- **Administrador**: Acesso total (obras, usuários, frota, relatórios)
- **Lançador**: Registra abastecimentos e transbordos
- **Leitor**: Apenas consulta (dashboard e relatórios)
- Acesso global ou restrito por obra

### 🎨 Interface Moderna
- Design responsivo (desktop e mobile)
- **Dark mode** com persistência local
- Modais flutuantes com Alpine.js
- Notificações toast animadas
- Drag & drop para upload de arquivos

---

## 🛠️ Tecnologias Utilizadas

| Tecnologia | Uso |
|------------|-----|
| **Python 3.10+** | Backend |
| **Flask 3.0** | Framework web |
| **Flask-SQLAlchemy** | ORM e banco de dados |
| **Flask-Login** | Autenticação |
| **SQLite** | Banco de dados (desenvolvimento) |
| **PostgreSQL** | Banco de dados (produção) |
| **Tailwind CSS** | Estilização |
| **Alpine.js** | Interatividade frontend |
| **HTMX** | Requisições dinâmicas |
| **ReportLab** | Geração de PDF |
| **openpyxl** | Geração de Excel |

---

## 📦 Instalação

### Pré-requisitos
- Python 3.10 ou superior
- pip (gerenciador de pacotes)
- Git

### Passo a passo

```bash
# 1. Clonar o repositório
git clone https://github.com/itachi23k/frota_web/
cd frota_web

# 2. Criar ambiente virtual
python -m venv venv

# 3. Ativar ambiente virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 4. Instalar dependências
pip install -r requirements.txt

# 5. Executar a aplicação
flask run
