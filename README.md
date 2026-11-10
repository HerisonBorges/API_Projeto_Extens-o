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

Criar tabelas e aplicar migrações (não precisa de psql):

python3 -m database.aplicar_migracoes

Executar os cenários de aceite do QA contra o banco do .env
(cria dados de teste e os remove ao final):

python3 -m unittest tests.aceite_qa -v

Executar a API:

python app.py

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


## Testes

python3 -m unittest tests.aceite_qa tests.test_reciclagem_horarios -v

Os testes rodam contra o banco do .env, criam empresas de teste e removem os
dados ao final.


## Front-end (frontend/)

React + Tailwind (Vite), tema Kindra Smoked Glass.

cd frontend

npm install

npm run dev      # http://localhost:5173 (já liberado no CORS)

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