# Telegram Finance Bot

Bot de Telegram para registrar ganhos e gastos por texto, salvar no Supabase e gerar resumo mensal.

## Requisitos

- Python 3.10+
- Conta no Telegram (token de bot via BotFather)
- Projeto Supabase

## Instalação

1. (Recomendado) Crie/ative um ambiente virtual:

**Windows (PowerShell)**

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instale as dependências:

```bash
pip install -r requirements.txt
```

3. Configure as variáveis no arquivo `.env`:

- `TELEGRAM_BOT_TOKEN`
- `MISTRAL_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`

4. Execute o schema no Supabase SQL Editor:

Arquivo: `database/schema.sql`

## Como rodar

Execução principal do bot (polling). O bot só responde enquanto este processo estiver rodando:

```bash
python main.py
```

## Comandos do bot

- `/start`: instruções rápidas
- `/resumo`: resumo do mês atual (ganhos, gastos e saldo)
- `/grafico`: gráfico de pizza dos gastos por categoria (mês atual)
- `/extrato`: últimos lançamentos (até 15)

## Scripts auxiliares

- Teste de parser IA: `python test_ai_parser.py`
- Teste de integração com banco: `python test_db_integration.py`
