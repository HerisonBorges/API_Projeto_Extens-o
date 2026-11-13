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

### Agendamento em produção (GitHub Actions)

O workflow .github/workflows/worker_reciclagem.yml roda o worker de hora em
hora (minuto 7, fora do pico do minuto 0) e pode ser disparado manualmente em
Actions > "Worker de reciclagem" > Run workflow (simulação ligada por padrão).
Só roda a partir da branch padrão (main).

Configuração, uma vez:

1. No SQL Editor do Supabase de produção, rode database/papel_worker.sql e
   depois, separadamente, ALTER ROLE sandro_worker PASSWORD '<senha-gerada>';
   O papel só lê/escreve oportunidades (sem DELETE, sem clientes/usuários).
2. Em Settings > Environments, crie "producao" e cadastre os secrets:
   DB_HOST, DB_PORT, DB_NAME, DB_USER (sandro_worker.<ref-do-projeto>), DB_PASSWORD.
3. Rode manualmente com simulação ligada e confira o resumo da execução.

Os logs do Actions em repositório público são públicos: o worker imprime só
IDs, datas e contagens, nunca títulos ou dados de clientes.

Fora do GitHub (servidor próprio), o equivalente em cron:

7 * * * * cd /caminho/do/projeto && python3 -m database.worker_reciclagem


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

python3 -m unittest tests.aceite_qa tests.test_reciclagem_horarios tests.test_pool tests.test_interacoes_relatorios tests.test_producao tests.test_workflow -v

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

A API é lida de VITE_API_URL (padrão local: http://127.0.0.1:5000).


## Publicação do front no Netlify

O netlify.toml na raiz já configura tudo (base frontend/, build, Node 22,
fallback de rotas, cabeçalhos de segurança e cache). No Netlify:

1. Add new site > Import an existing project > escolha este repositório.
   Os campos de build vêm do netlify.toml: não altere.
2. Site configuration > Environment variables: VITE_API_URL=https://<sua-api>
   (sem barra no final). Sem ela o build falha com a mensagem do motivo.
3. Publique e copie a URL do site (ex.: https://sandro-crm.netlify.app).
4. Na API, cadastre essa URL em CORS_ORIGINS e reinicie a API.

Checagens locais do build de produção:

VITE_API_URL=https://<sua-api> npm run build   # falha se faltar a URL ou se não for https

Cabeçalhos: CSP que só permite scripts/estilos do próprio site e chamadas
HTTPS, bloqueio de iframe (X-Frame-Options/frame-ancestors), nosniff e
Referrer-Policy. O site usa noindex: não aparece em buscadores.


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


## Checklist de Go-Live

Siga na ordem: cada etapa usa algo produzido na anterior.

### 0. Antes de começar

- [ ] Use um projeto Supabase de PRODUÇÃO separado do de homologação. O banco
      de homologação tem a Loja Fênix, usuários de teste com senha conhecida
      (senha123) e contas pessoais de teste: nada disso deve ir para produção.
- [ ] Gere credenciais novas para produção (senha do banco, SECRET_KEY). Não
      reaproveite as de desenvolvimento nem senhas que já passaram por chat,
      e-mail ou documentos.
- [ ] Escolha o nome do site no Netlify (ex.: sandro-crm), que define a URL
      https://sandro-crm.netlify.app usada no CORS da API.

### 1. Banco de dados (Supabase de produção)

- [ ] Rode as migrações apontando o .env local para o banco de produção:
      python3 -m database.aplicar_migracoes   (todos os arquivos devem dar OK)
- [ ] NÃO rode database/seed_fenix.py em produção.
- [ ] No SQL Editor, rode database/papel_worker.sql e, separadamente:
      ALTER ROLE sandro_worker PASSWORD '<senha-longa-gerada>';
- [ ] Use o Session pooler, porta 5432 (o pool da API mantém sessões abertas;
      a porta 6543, Transaction pooler, não foi testada).
- [ ] Volte o .env local para o banco de homologação.

### 2. API (PaaS)

- [ ] Start command: gunicorn app:app   (Python da versão em .python-version)
- [ ] Variáveis: APP_ENV=producao, SECRET_KEY (nova, 32+ caracteres),
      CORS_ORIGINS=https://<site>.netlify.app, DB_HOST, DB_PORT=5432, DB_NAME,
      DB_USER, DB_PASSWORD, PGSSLMODE=require, WEB_CONCURRENCY=2, DB_POOL_MAX=5,
      TZ_EMPRESA=America/Sao_Paulo
- [ ] Health check da plataforma: /health   (não use /health/pronto aqui: uma
      oscilação do banco faria a plataforma reiniciar a API sem necessidade)
- [ ] Depois do deploy, confira:
      - GET https://<api>/health          -> 200 {"status": "ok"}
      - GET https://<api>/health/pronto   -> 200 com "banco": "ok"
      - GET https://<api>/apidocs/        -> 404 (Swagger desligado)
      - No log da plataforma, nenhuma linha "Configuração inválida".

### 3. Front-end (Netlify)

- [ ] Importe o repositório. Os campos de build vêm do netlify.toml: não altere.
- [ ] Variável: VITE_API_URL=https://<api>   (sem barra no final)
- [ ] Publique e confira, no navegador, com o console (F12) aberto:
      - a tela de login carrega com a marca SANDRO CRM;
      - nenhum erro de CORS ou de Content-Security-Policy no console;
      - F5 em qualquer tela mantém a tela.

### 4. Primeiro acesso

- [ ] Crie a empresa e o primeiro Gestor (o banco de produção começa vazio):
      POST https://<api>/auth/register
      {"nome_empresa": "...", "nome_usuario": "...", "email": "...", "senha": "..."}
- [ ] Entre pelo site e percorra as 8 telas: Dashboard, Clientes, Detalhe,
      Funil, Follow-ups, Relatórios, Configurações e "+ Novo Lead".
- [ ] Cadastre um cliente e uma oportunidade de teste e mova no funil
      (os mesmos cenários de tests/aceite_qa.py, feitos à mão). Exclua depois.
- [ ] Teste a janela de horário: crie um usuário Atendimento, defina um
      horário que exclua o horário atual e confirme o bloqueio no login.

### 5. Worker de reciclagem (GitHub Actions)

- [ ] Settings > Environments > New environment: producao
- [ ] Secrets do environment: DB_HOST, DB_PORT=5432, DB_NAME,
      DB_USER=sandro_worker.<ref-do-projeto>, DB_PASSWORD (a do papel)
- [ ] Faça o merge de feature/deploy-producao na main SÓ depois dos secrets
      (sem eles o workflow falha a cada hora e o GitHub envia e-mail).
- [ ] Actions > "Worker de reciclagem" > Run workflow com simulação ligada:
      o resumo deve mostrar "Vencidas, que seriam processadas: 0".
- [ ] Na hora seguinte, confira a primeira execução agendada (verde).

### 6. Depois do go-live

- [ ] Monitore /health com um serviço externo de uptime (opcional).
- [ ] Repositório público: o GitHub desativa agendamentos após 60 dias sem
      atividade no repositório. Se o worker parar, reative em Actions.
- [ ] Rollback: no Netlify, "Publish deploy" de uma versão anterior; na PaaS,
      redeploy do commit anterior. As migrações só adicionam colunas e tabelas,
      então a versão anterior do código continua funcionando com o banco novo.
