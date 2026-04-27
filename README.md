# Telegram Finance Bot

Bot de Telegram para registrar ganhos e gastos por texto, salvar no Supabase e gerar resumo mensal.

## Requisitos

- Python 3.10+
- Conta no Telegram (token de bot via BotFather)
- Projeto Supabase

## Instalação

1. Instale as dependências:

```bash
pip install -r requirements.txt
```

2. Configure as variáveis no arquivo `.env`:

- `TELEGRAM_BOT_TOKEN`
- `MISTRAL_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`

3. Execute o schema no Supabase SQL Editor:

Arquivo: `database/schema.sql`

## Como rodar

Execução principal do bot:

```bash
python main.py
```

## Scripts auxiliares

- Teste de parser IA: `python test_ai_parser.py`
- Teste de integração com banco: `python test_db_integration.py`
