# Telegram Finance Bot

Controle pessoal em reais pelo Telegram, com Supabase, gráficos e CSV. Python 3.14.
Funciona em **Vercel por webhook** ou localmente por polling. Não precisa de IA para
registrar mensagens comuns nem para consultar dados. Mistral e os subprocessos MCP
foram removidos.

## Uso

- "gastei 50 reais em mercado"
- "paguei R$ 25,90 no Uber ontem"
- "recebi meu salário de 3000"
- "vou pagar 900 de aluguel amanhã"
- "quanto gastei com alimentação este mês?"
- "mostre minhas entradas e saídas"
- "gráfico do mês passado"

Uma transação por mensagem. O parser conservador pede reformulação quando encontra
valores, datas ou intenções ambíguas. Não faz conversão de moedas. Texto é suportado;
áudio, recibos/fotos, parcelas e transferências entre contas não são suportados.

| Comando | Resultado |
|---|---|
| /resumo, /contas | Entradas, saídas, saldo do período e valores planejados separados |
| /relatorio | Totais e categorias |
| /grafico | Gastos por categoria e entradas/saídas por mês (confirmados) |
| /extrato | Histórico do período, 10 registros por página, mais recentes por ID |
| /pendentes | Planejados do período |
| /exportar tudo | CSV de todos os registros ativos, inclusive planejados |
| /ver ID | Detalhes e botões para status/exclusão |
| /editar ID valor 25,90 | Corrige um valor |
| /editar ID categoria Alimentação | Corrige categoria |
| /editar ID data 2026-10-22 | Corrige a data |
| /editar ID descricao Novo texto | Corrige descrição |
| /confirmar ID, /desconfirmar ID | Alterna confirmado/planejado |
| /cancelar ID | Pede confirmação para excluir |
| /ajuda | Exemplos completos |

Relatórios aceitam hoje, ontem, semana (segunda a domingo), mês passado, 2026-10,
outubro 2026 ou intervalo inclusivo como 2026-10-01 2026-10-23. O padrão é o mês
atual em America/Sao_Paulo. Use "tudo" para todo o histórico e
"categoria:Alimentação" ao final para filtro exato. Filtros de categoria por linguagem
natural usam as categorias conhecidas; categorias próprias podem ser consultadas
explicitamente. "Entradas" e "saídas" filtram o tipo.

Registro explícito, sem IA: /gasto 25,90 Alimentação 2026-10-22 Almoço ou
/entrada 3000 Salário 2026-10-05 Pagamento. A categoria nesse formato é uma palavra;
categorias com espaços podem ser definidas depois por /editar.

O saldo é a soma dos lançamentos do período, **não** o saldo bancário. Não há saldo
inicial implícito. Datas futuras são planejadas; alterar uma data não altera o status.
Exclusão é lógica: o registro deixa de aparecer nos relatórios e mantém a chave
de deduplicação para impedir que uma repetição do Telegram o recrie.

## Preparar Supabase

1. Faça backup de public.transactions.
2. Pare a versão antiga antes de aplicar o upgrade.
3. Execute **database/schema.sql** no SQL Editor do projeto do bot. É o schema
   completo e também um upgrade transacional e repetível para a versão anterior.
   Preserva IDs e registros; datas históricas são derivadas de created_at no fuso
   America/Sao_Paulo, pois a versão antiga não gravava a data real da compra.
4. Configure uma chave **sb_secret_** ou a chave legada **service_role** no servidor.
   A chave anon não funciona mais: as antigas políticas liberavam todos os registros
   e foram removidas. RLS fica habilitado, com acesso de tabela restrito ao backend.
   Não use a chave secreta em frontend, repositório ou mensagens no Telegram.
5. Defina ALLOWED_TELEGRAM_USER_IDS com seu ID numérico. O bot é privado e cada
   consulta/alteração filtra o ID vindo do evento autenticado do Telegram.

A alteração restringe apenas transactions e finance_drafts; não altera as demais
tabelas do projeto. Integrações antigas que usavam anon nessa tabela precisam migrar.
Registros históricos inválidos não são corrigidos silenciosamente; novos valores
negativos/zero são recusados.

## Implantar na Vercel

O Hobby serve a projetos pessoais sujeitos às cotas da Vercel; uso gratuito não
é ilimitado. Não use polling em uma Function. Veja [FastAPI na Vercel](https://vercel.com/docs/frameworks/backend/fastapi)
e [plano Hobby](https://vercel.com/docs/plans/hobby).

1. Importe este repositório no seu projeto Vercel, com preset **FastAPI** e raiz
   do repositório. app.py exporta o app; .python-version seleciona Python 3.14.
   Não configure um comando permanente "python main.py".
2. Em Environment Variables, **Production**, cadastre:
   - TELEGRAM_BOT_TOKEN (do BotFather)
   - SUPABASE_URL (URL do projeto)
   - SUPABASE_SECRET_KEY (segredo do servidor)
   - ALLOWED_TELEGRAM_USER_IDS (seu ID; vários IDs separados por vírgula)
   - BOT_TIMEZONE=America/Sao_Paulo
   - TELEGRAM_WEBHOOK_SECRET (gere com python -c "import secrets; print(secrets.token_urlsafe(32))")
   - OPENAI_ENABLED=false
3. Faça deploy. Verifique https://SEU-DOMINIO/health (liveness; não testa credenciais).
   A URL de produção deve estar acessível sem login da Vercel. Preview deployments
   não devem receber o webhook nem segredos de produção.
4. Instale as dependências localmente e preencha .env com as mesmas configurações.
   Execute **uma vez**, com o domínio estável de produção:
   python -m scripts.configure_telegram webhook https://SEU-DOMINIO
   O script primeiro verifica as colunas do banco, depois registra o webhook
   com segredo e comandos. Não imprime os segredos.
5. Confira python -m scripts.configure_telegram status. Envie uma compra no Telegram,
   consulte /extrato, /resumo e /grafico, depois exclua a compra de teste se necessário.
   Não mantenha uma cópia local/antiga em polling ao mesmo tempo.

O webhook valida X-Telegram-Bot-Api-Secret-Token, aguarda o processamento antes
de responder e retorna 503 em falhas transitórias para permitir nova entrega.
Uma chave única por usuário/chat/mensagem evita duplicação de lançamentos, mesmo
após exclusão. Respostas no chat podem se repetir caso a confirmação HTTP se perca;
não há garantia de entrega exatamente uma vez para mensagens do Telegram.
Os rascunhos de IA são persistidos no banco e expiram após 15 minutos; rascunhos
expirados do usuário são limpos ao criar o próximo. Não é necessário cron.

## Rodar no computador

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copie .env.example para .env e configure as variáveis. Se já usava webhook:
python -m scripts.configure_telegram polling
python main.py

O comando de configuração preserva atualizações pendentes. Ao voltar à Vercel,
pare o polling e registre novamente o webhook de produção.

## OpenAI opcional

Defina OPENAI_ENABLED=true, OPENAI_API_KEY e OPENAI_MODEL (padrão gpt-4o-mini).
Apenas mensagens não compreendidas localmente são enviadas para interpretação.
Histórico, totais, IDs e credenciais do Supabase nunca entram no prompt.
A API pode ter custo separado. Com OPENAI_ENABLED=false, nenhuma chamada é feita,
mesmo que uma chave exista no ambiente.

Usa [Responses com Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
store=false e timeout de 12 s. A saída é validada e **sempre** pede confirmação
por botão antes de gravar a transação. Sem chave, em falha, recusa ou resposta
inválida, oferece o registro explícito. A IA não executa SQL nem calcula relatórios.

## Arquitetura e testes

- HTTP assíncrono com conexões reutilizadas na execução; sem subprocessos por ação.
- Apenas uma gravação na compra comum; não busca o mês inteiro após cada compra.
- Decimal para totais; data da compra separada da data de criação.
- Leitura por cursor ID, inclusive quando o limite do Supabase é menor que a página.
- Índices por usuário/data e usuário/ID; exclusão lógica.
- Limite de 50.000 registros por consulta: recusa em vez de devolver total parcial.
- PNG local, sem serviço externo de gráficos; matplotlib só é carregado ao pedir gráfico.
- Dependências diretas e transitivas fixadas em requirements.txt, compatível com o build da Vercel.

pip install -r requirements-dev.txt
python -m pytest -q
npm ci --prefix tests
npm test --prefix tests

Testes não enviam mensagens reais, não usam chaves e não alteram dados reais.
PGlite executa o schema em PostgreSQL isolado para validar instalação, upgrade,
RLS/grants e deduplicação. GitHub Actions executa testes Python e SQL em Linux.

Antes de ativar em produção: aplicar schema, definir segredos, implantar e registrar
webhook. A saúde HTTP sozinha não confirma que Telegram e Supabase estão conectados.
