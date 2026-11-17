# Importação/exportação de clientes e recorrências

## Visão geral

```
Planilha (.xlsx/.csv) ──► POST /clientes/importar?simular=1 ──► prévia + erros por linha (nada gravado)
                     └──► POST /clientes/importar ──────────► transação única: clientes + recorrências + registro
Cliente ──► recorrencias (regra) ──► worker (GitHub Actions, de hora em hora)
                                       ├─ lembrete     → tarefas (follow-up)
                                       └─ oportunidade → oportunidades (Prospecção)
                                     recorrencia_execucoes: UNIQUE (regra, data) = sem duplicata
```

| Arquivo | Papel |
|---|---|
| `database/migracao_importacao_recorrencias.sql` | `clientes.documento`, `recorrencias`, `recorrencia_execucoes`, `importacoes`, `recorrencia_id` em tarefas/oportunidades |
| `documento.py` | CPF e CNPJ (inclusive o CNPJ alfanumérico, IN RFB nº 2.229/2024) |
| `recorrencia.py` | Validação e cálculo de datas (funções puras) |
| `importacao.py` | Leitura segura do arquivo, validação por linha, geração do modelo/exportação |
| `routes/importacao.py` | `GET /clientes/modelo`, `GET /clientes/exportar`, `POST /clientes/importar` |
| `routes/recorrencias.py` | CRUD de regras |
| `database/worker_recorrencias.py` | Gera os eventos nas datas |

## Endpoints

| Método | Rota | Perfil | O que faz |
|---|---|---|---|
| GET | `/clientes/modelo?formato=xlsx\|csv` | todos | Modelo oficial vazio (aba "Instruções" no .xlsx) |
| GET | `/clientes/exportar?formato=xlsx\|csv` | Gestor | Clientes da empresa no mesmo layout (uma linha por recorrência) |
| POST | `/clientes/importar[?simular=1]` | Gestor | `multipart/form-data`, campo `arquivo` |
| GET | `/recorrencias[?cliente_id=]` | todos | Regras da empresa |
| POST | `/recorrencias` | todos | `{cliente_id, tipo, titulo, valor?, notas?, frequencia, dia_semana\|dia_mes}` |
| PUT | `/recorrencias/<id>` | todos | Substitui a regra; próxima data recalculada a partir de hoje |
| PATCH | `/recorrencias/<id>/ativo` | todos | `{ativo: bool}`; retomar conta a partir de hoje |
| DELETE | `/recorrencias/<id>` | Gestor | Exclui a regra (o que já foi gerado continua) |
| POST | `/oportunidades` | todos | Aceita `recorrencia: {frequencia, dia_semana\|dia_mes}`, na mesma transação |

Respostas da importação:

- `200` (simular): `{valido, linhas, clientes, recorrencias, erros[], total_erros, avisos[], previa[5]}`
- `201`: `{mensagem, clientes_criados, recorrencias_criadas}`
- `400`: problema no arquivo inteiro (`{erro}`), ex.: extensão, macro, XML com DTD, zip bomb
- `413`: acima de 1 MB
- `422`: linhas inválidas, nada gravado: `erros = [{linha, coluna, mensagem}]` (até 100)
- `409`: CPF/CNPJ cadastrado por outra pessoa durante a importação

## Segurança

| Ameaça | Defesa |
|---|---|
| CSV/Formula Injection | Célula que começa com `= + - @` é recusada na entrada (telefone pode começar com `+55`); na saída, o texto ganha `'` na frente (OWASP) |
| XSS armazenado | Marcação HTML (`<tag`) é recusada; o React escapa tudo; o PDF usa `escape()` |
| XXE / billion laughs | Qualquer parte XML com `<!DOCTYPE`/`<!ENTITY` (inclusive UTF-16) é recusada antes do openpyxl; o openpyxl ainda usa `defusedxml` |
| Zip bomb | Máximo de 25 MB descompactado, 200 entradas e taxa de compressão de 100:1 |
| Macros | `.xlsm/.xls/.xlsb` e `.xlsx` com `vbaProject.bin` são recusados |
| Arquivo disfarçado | Extensão + assinatura (`PK` no .xlsx, sem bytes nulos no .csv) |
| Abuso de volume | 1 MB (`MAX_CONTENT_LENGTH`) e 2000 linhas por arquivo |
| Vazamento entre empresas | `empresa_id` sempre do JWT; CPF/CNPJ único por empresa; regra de outra empresa = 404 |
| Persistência | O arquivo é lido da memória e descartado; `importacoes` guarda só nome saneado, SHA-256 e contagens |

## Motor de recorrência

- Datas no calendário da empresa (`TZ_EMPRESA`), pelo relógio do banco.
- "Todo dia 31" vira o último dia nos meses curtos (28/29 em fevereiro).
- Worker parado: cada data perdida gera seu evento, até 12 por regra (as mais recentes).
- Cliente Inativo: a regra avança sem gerar nada.
- Nova oportunidade com repetição: a de hoje é a criada na tela; a primeira repetição começa amanhã.
- O worker roda no mesmo workflow da reciclagem (`.github/workflows/worker_reciclagem.yml`),
  com o papel restrito `sandro_worker`: sem DELETE e sem ler nome/e-mail/telefone de clientes.

## Produção (antes de ligar)

1. Migração: `python3 -m database.aplicar_migracoes` (aditiva).
2. Rodar de novo `database/papel_worker.sql` no SQL Editor (permissões novas do worker).
3. `requirements.txt` ganhou `openpyxl`, `et_xmlfile` e `defusedxml`.

## Testes

```
python3 -m pip install -r requirements-dev.txt
python3 -m pytest tests/test_importacao_recorrencias.py -v
```

O worker é sempre chamado com `empresa_id` da empresa de teste: o banco de testes
é compartilhado e, sem o filtro, as regras reais seriam processadas.

## Limitações conhecidas

- Importação só cria clientes: CPF/CNPJ já cadastrado é erro (não atualiza o cadastro).
- Sem limite de taxa (rate limit) nas rotas de upload.
- O cadastro manual (`POST /clientes`) ainda aceita nome começando com `=`; a exportação neutraliza.
