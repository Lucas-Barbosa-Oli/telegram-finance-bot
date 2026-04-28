# MCP Hub (Reutilizavel)

Hub MCP local para reutilizar tools entre varios projetos (bot, frontend, automacoes, etc.).

## Objetivo

- Centralizar tools de dominio (`finance`) e tools genericas (`core`).
- Evitar acoplamento com um unico projeto.
- Facilitar reaproveitamento em futuros apps.

## Estrutura

- `servers/finance`: tools de financas (Supabase).
- `servers/core`: tools genericas (health check e utilitarios HTTP).
- `shared`: config, logging e cliente Supabase compartilhados.

## Setup rapido

1. Crie e ative ambiente virtual:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instale dependencias:

```bash
pip install -r requirements.txt
```

3. Copie `.env.example` para `.env` e preencha valores.

## Como usar no bot atual

- Mantenha o bot atual funcionando normalmente.
- Comece migrando comandos aos poucos para chamar as tools daqui.
- Sugestao de ordem: `/extrato` -> `/resumo` -> gravacao de transacao.

## Contrato de resposta recomendado

Todas as tools retornam:

- Sucesso: `{ "ok": true, "data": ... }`
- Erro: `{ "ok": false, "error": { "code": "...", "message": "...", "details": ... } }`

## Proximos passos

- Adicionar servidor MCP (transporte stdio/http) por cima dessas funcoes.
- Adicionar autenticacao por token para ambiente externo.
- Versionar tools por dominio (`v1`, `v2`) quando houver quebra de contrato.
