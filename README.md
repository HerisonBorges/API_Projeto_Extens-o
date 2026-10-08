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

Executar a API:

python app.py

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

GET /configuracoes/<empresa_id>

PUT /configuracoes/<empresa_id>


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