# CRM Backend

API REST desenvolvida em Python utilizando Flask e PostgreSQL.

## Estrutura do projeto

CRM_BACKEND/
- app.py
- database/
  - __init__.py
  - conexao.py
- routes/
  - auth.py
  - clientes.py
  - configuracoes.py
  - dashboard.py
- requirements.txt

## Instalação

Criar ambiente virtual:

python -m venv venv

Ativar ambiente virtual no CMD:

venv\Scripts\activate

Instalar dependências:

pip install -r requirements.txt

Configurar variáveis de ambiente (nenhuma credencial fica no código):

Copie .env.example para .env e preencha. O app.py carrega o .env
automaticamente (python-dotenv). Variáveis: DB_HOST, DB_PORT, DB_NAME,
DB_USER, DB_PASSWORD (obrigatória), PGSSLMODE e SECRET_KEY.

Para o Supabase, use os dados de Project Settings > Database > Connect
(Session pooler). O usuário tem o formato postgres.<ref-do-projeto>.

Pool de conexões: database/conexao.py mantém até DB_POOL_MAX conexões abertas
(padrão 10) e as reaproveita. conectar_banco().close() devolve a conexão ao
pool; em código novo prefira "with get_db_connection() as conexao:". Conexões
não devolvidas numa requisição (ex.: exceção) são recuperadas pelo teardown
registrado no app.py. Se todas estiverem ocupadas, a requisição espera até
DB_POOL_TIMEOUT segundos.

Criar tabelas e aplicar migrações (não precisa de psql):

python3 -m database.aplicar_migracoes

Executar os cenários de aceite do QA contra o banco do .env
(cria dados de teste e os remove ao final):

python3 -m unittest tests.aceite_qa -v

Executar a API (desenvolvimento, com recarga automática):

FLASK_DEBUG=1 python3 app.py

Rotas de clientes, oportunidades, tarefas, relatórios e dashboard exigem o
cabeçalho Authorization: Bearer <token>, obtido em POST /auth/login.
O empresa_id é lido do token, não do corpo da requisição.

A API será executada em:

http://127.0.0.1:5000


## Banco de dados

Banco utilizado:

PostgreSQL

Nome do banco:

crm_db

Tabelas:

- empresas
- usuarios
- clientes
- oportunidades
- tarefas
- configuracoes

Todos os módulos devem utilizar o mesmo banco de dados.

A conexão está localizada em:

database/conexao.py


## Endpoints já desenvolvidos

### Autenticação

POST /auth/register

POST /auth/login

GET /auth/me/<id>


### Clientes

GET /clientes

GET /clientes/<id>

POST /clientes

PUT /clientes/<id>

DELETE /clientes/<id>


### Configurações

GET /configuracoes            (empresa do token; devolve padrões se não houver registro)

PUT /configuracoes            (somente Gestor; campos: notificacoes_email, tema_escuro, dias_alerta_orcamento)


### Dashboard

GET /dashboard/<empresa_id>


## Endpoints que ainda precisam ser desenvolvidos

Os próximos endpoints devem seguir a mesma organização utilizada no projeto.

Criar os novos arquivos dentro da pasta:

routes/

### Oportunidades

GET /oportunidades

GET /oportunidades/<id>

POST /oportunidades

PUT /oportunidades/<id>

DELETE /oportunidades/<id>

PATCH /oportunidades/<id>/etapa


### Tarefas

GET /tarefas

POST /tarefas

PUT /tarefas/<id>

DELETE /tarefas/<id>

PATCH /tarefas/<id>/concluir


### Relatórios

GET /relatorios/vendas


## Controle de acesso por horário

Cada usuário pode ter hora_inicio_acesso e hora_fim_acesso (NULL nos dois =
24/7). O horário é avaliado no fuso TZ_EMPRESA (padrão America/Sao_Paulo).
Início maior que o fim vale para turnos que cruzam a meia-noite. O fim é
exclusivo (08:00-18:00 permite até 17:59).

Fora da janela, o login e TODAS as rotas autenticadas respondem:

403 { "error": "HORARIO_BLOQUEADO", "message": "Acesso permitido apenas entre 08:00 e 18:00" }

Endpoints (somente Gestor, sempre na empresa do token):

GET /configuracoes/usuarios

PUT /configuracoes/usuarios/<id>   body: { "hora_inicio_acesso": "08:00", "hora_fim_acesso": "18:00" }

O Gestor não pode definir para si uma janela que o bloqueie agora (409).


## Reciclagem pós-venda

Apenas oportunidades na etapa Fechado podem ser recicladas.

POST /oportunidades/<id>/agendar-reciclagem   body: { "dias": 7 } ou { "data_agendada": "2026-12-25" }

DELETE /oportunidades/<id>/agendar-reciclagem   (cancela o agendamento pendente)

data_agendada aceita AAAA-MM-DD (meia-noite no fuso da empresa) ou ISO 8601
com fuso (ex.: 2026-12-25T00:00:00Z). Mover o card para fora de Fechado
cancela o agendamento pendente.

O worker cria uma NOVA oportunidade em Prospecção (ligada pela coluna
oportunidade_origem_id) e marca a original como processado. A venda original
continua em Fechado, então receita e KPIs não mudam.

python3 -m database.worker_reciclagem --dry-run   # lista sem alterar

python3 -m database.worker_reciclagem             # processa

Agende no cron, por exemplo a cada 15 minutos:

*/15 * * * * cd /caminho/do/projeto && python3 -m database.worker_reciclagem


## Produção (PaaS)

Comando de start: gunicorn app:app   (lê gunicorn.conf.py; há também um Procfile)

Variáveis obrigatórias no painel da plataforma:

APP_ENV=producao
SECRET_KEY=<nova, 32+ caracteres, diferente da de desenvolvimento>
CORS_ORIGINS=https://<seu-front>.netlify.app
DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, PGSSLMODE=require

A API se recusa a subir (e mostra o motivo no log) se faltar SECRET_KEY
forte, DB_PASSWORD ou, em produção, CORS_ORIGINS com https. Em produção o
Swagger fica desligado (SWAGGER_ATIVO=1 liga) e o debug nunca é ativado.

Conexões: cada worker do Gunicorn tem o próprio pool. Total no Supabase =
WEB_CONCURRENCY x DB_POOL_MAX. Comece com WEB_CONCURRENCY=2 e DB_POOL_MAX=5.

Monitoramento (sem autenticação):

GET /health          liveness (não toca no banco): use como health check do PaaS

GET /health/pronto   readiness (SELECT 1): 503 se o banco estiver fora

Desenvolvimento local: FLASK_DEBUG=1 python3 app.py


## Testes

python3 -m unittest tests.aceite_qa tests.test_reciclagem_horarios tests.test_pool tests.test_interacoes_relatorios tests.test_producao -v

Os testes rodam contra o banco do .env, criam empresas de teste e removem os
dados ao final.


## Front-end (frontend/)

React + Tailwind (Vite), identidade visual SANDRO CRM ("O poder da conexão").

Telas (rotas por hash, o F5 mantém a tela): #/dashboard, #/clientes,
#/clientes/<id>, #/funil, #/followups, #/relatorios (Gestor) e
#/configuracoes (Gestor).

cd frontend

npm install

npm run dev      # http://localhost:5173 (já liberado no CORS)

Se o caminho da pasta tiver ":" (ex.: "6 Semestre 2026:2"), o servidor de
desenvolvimento do Vite 8 recusa os arquivos (403). Nesse caso use:

npm run homologacao   # build + preview na mesma porta 5173 (sem hot reload)


## Dados de homologação (Loja Fênix)

python3 -m database.seed_fenix             # cria, se não existir

python3 -m database.seed_fenix --resetar   # apaga a Fênix e recria

Logins: gestor@lojafenix.com.br (Gestor, 24/7) e mariana@lojafenix.com.br
(Atendimento, 08:00-18:00). Senha: SEED_FENIX_SENHA ou "senha123".
Uso exclusivo em homologação.

A API é lida de VITE_API_URL (padrão http://127.0.0.1:5000).


## Padrão para novas rotas

Criar um Blueprint para cada módulo.

Exemplo:

oportunidades.py

Todas as rotas de oportunidades devem permanecer dentro desse arquivo.

Depois o Blueprint deve ser importado e registrado no app.py.

Exemplo:

from routes.oportunidades import oportunidades_bp

app.register_blueprint(oportunidades_bp)


## Regra importante

O CRM foi desenvolvido para funcionar com diferentes tipos de comércio.

Por isso, os dados devem continuar vinculados à empresa através do:

empresa_id

Não criar endpoints específicos para tipos de comércio.

Exemplo correto:

POST /clientes

Exemplo incorreto:

POST /clientes-padaria

POST /clientes-oficina

A mesma API deve funcionar para qualquer empresa.