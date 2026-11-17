"""Worker de recorrências ("toda segunda", "todo dia 5").

Para cada regra ativa com proxima_execucao <= hoje (calendário da empresa):
  - lembrete     -> cria um follow-up (tarefa) com vencimento na data da regra;
  - oportunidade -> cria um card em Prospecção com o valor da regra;
  - avança proxima_execucao para a próxima data depois de hoje.

Garantias:
  - Sem duplicata: recorrencia_execucoes tem UNIQUE (recorrencia_id, data),
    então reprocessar ou rodar duas instâncias não gera o mesmo evento duas vezes;
  - FOR UPDATE SKIP LOCKED: duas instâncias não pegam a mesma regra;
  - Worker parado: cada data perdida gera seu evento, até 12 por regra
    (as mais recentes); as mais antigas são contadas como puladas;
  - Cliente Inativo: a regra avança sem gerar nada.

Uso (na raiz do projeto):
    python3 -m database.worker_recorrencias              # processa tudo
    python3 -m database.worker_recorrencias --dry-run    # só conta, não altera
    python3 -m database.worker_recorrencias --empresa 12 # restringe a uma empresa
"""
import argparse
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from database.conexao import conectar_banco  # noqa: E402
from recorrencia import hoje_na_empresa, ocorrencias_vencidas  # noqa: E402
from routes.oportunidades import ETAPA_INICIAL  # noqa: E402
from seguranca import fuso_empresa  # noqa: E402

LOTE = 500  # regras por execução (o restante fica para a próxima hora)

SQL_VENCIDAS = """
    SELECT r.id, r.empresa_id, r.cliente_id, r.tipo, r.titulo, r.valor, r.notas,
           r.frequencia, r.dia_semana, r.dia_mes, r.proxima_execucao, r.criado_por, c.status
    FROM recorrencias r
    JOIN clientes c ON c.id = r.cliente_id
    WHERE r.ativo
      AND r.proxima_execucao <= %(hoje)s
      AND (%(empresa_id)s::int IS NULL OR r.empresa_id = %(empresa_id)s::int)
    ORDER BY r.proxima_execucao, r.id
    LIMIT %(lote)s
    FOR UPDATE OF r SKIP LOCKED;
"""

COLUNAS = ("id", "empresa_id", "cliente_id", "tipo", "titulo", "valor", "notas",
           "frequencia", "dia_semana", "dia_mes", "proxima_execucao", "criado_por", "cliente_status")


def _gerar_evento(cursor, regra, data):
    """Cria o follow-up ou a oportunidade de uma data. None se já existia."""
    cursor.execute("""
        INSERT INTO recorrencia_execucoes (recorrencia_id, empresa_id, data_referencia)
        VALUES (%s, %s, %s)
        ON CONFLICT (recorrencia_id, data_referencia) DO NOTHING
        RETURNING id;
    """, (regra["id"], regra["empresa_id"], data))
    linha = cursor.fetchone()
    if not linha:
        return None
    execucao_id = linha[0]

    if regra["tipo"] == "lembrete":
        cursor.execute("""
            INSERT INTO tarefas (empresa_id, cliente_id, titulo, descricao, data_vencimento,
                                 concluida, recorrencia_id)
            VALUES (%s, %s, %s, %s, %s, FALSE, %s)
            RETURNING id;
        """, (regra["empresa_id"], regra["cliente_id"], regra["titulo"], regra["notas"], data, regra["id"]))
        cursor.execute("UPDATE recorrencia_execucoes SET tarefa_id = %s WHERE id = %s;",
                       (cursor.fetchone()[0], execucao_id))
        return "tarefa"

    # Data no título: cada ciclo vira um card distinguível no funil
    titulo = f"{regra['titulo']} · {data:%d/%m/%Y}"[:150]
    cursor.execute("""
        INSERT INTO oportunidades (empresa_id, cliente_id, titulo, valor, etapa,
                                   etapa_atualizada_em, responsavel_id, recorrencia_id)
        VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s)
        RETURNING id;
    """, (regra["empresa_id"], regra["cliente_id"], titulo, regra["valor"] or 0, ETAPA_INICIAL,
          regra["criado_por"], regra["id"]))
    cursor.execute("UPDATE recorrencia_execucoes SET oportunidade_id = %s WHERE id = %s;",
                   (cursor.fetchone()[0], execucao_id))
    return "oportunidade"


def processar_recorrencias(empresa_id=None, hoje=None, simular=False):
    """Processa as regras vencidas numa transação. `hoje` só é passado nos testes.

    Retorna um resumo só com contagens (nada de nomes ou títulos de clientes).
    """
    resumo = {"regras": 0, "tarefas": 0, "oportunidades": 0, "ja_existiam": 0,
              "puladas": 0, "cliente_inativo": 0, "empresas": set()}
    conexao = conectar_banco()
    try:
        with conexao.cursor() as cursor:
            if hoje is None:
                hoje = hoje_na_empresa(cursor, fuso_empresa())
            cursor.execute(SQL_VENCIDAS, {"hoje": hoje, "empresa_id": empresa_id, "lote": LOTE})
            regras = [dict(zip(COLUNAS, linha)) for linha in cursor.fetchall()]

            for regra in regras:
                resumo["regras"] += 1
                resumo["empresas"].add(regra["empresa_id"])
                datas, proxima, puladas = ocorrencias_vencidas(regra, hoje)
                resumo["puladas"] += puladas

                if regra["cliente_status"] == "Inativo":
                    resumo["cliente_inativo"] += 1
                elif not simular:
                    for data in datas:
                        gerado = _gerar_evento(cursor, regra, data)
                        if gerado == "tarefa":
                            resumo["tarefas"] += 1
                        elif gerado == "oportunidade":
                            resumo["oportunidades"] += 1
                        else:
                            resumo["ja_existiam"] += 1
                else:
                    chave = "tarefas" if regra["tipo"] == "lembrete" else "oportunidades"
                    resumo[chave] += len(datas)

                if not simular:
                    cursor.execute("UPDATE recorrencias SET proxima_execucao = %s WHERE id = %s;",
                                   (proxima, regra["id"]))
        if simular:
            conexao.rollback()
        else:
            conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()

    resumo["empresas"] = len(resumo["empresas"])
    resumo["hoje"] = hoje.isoformat()
    return resumo


def _resumo_github(linhas):
    destino = os.getenv("GITHUB_STEP_SUMMARY")
    if destino:
        with open(destino, "a", encoding="utf-8") as arquivo:
            arquivo.write("\n".join(linhas) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Worker de recorrências.")
    parser.add_argument("--dry-run", action="store_true", help="Apenas conta o que seria gerado.")
    parser.add_argument("--empresa", type=int, default=None, help="Processa apenas esta empresa_id.")
    args = parser.parse_args(argv)

    inicio = datetime.now(timezone.utc)
    escopo = f"empresa {args.empresa}" if args.empresa is not None else "todas as empresas"
    r = processar_recorrencias(args.empresa, simular=args.dry_run)
    duracao = (datetime.now(timezone.utc) - inicio).total_seconds()
    modo = "[dry-run] " if args.dry_run else ""

    # Logs de Actions em repositório público são públicos: só contagens
    print(f"{inicio:%Y-%m-%d %H:%M:%S}Z {modo}{r['regras']} regra(s) vencida(s) até {r['hoje']} ({escopo}): "
          f"{r['tarefas']} follow-up(s), {r['oportunidades']} oportunidade(s), "
          f"{r['ja_existiam']} já existiam, {r['puladas']} data(s) antiga(s) pulada(s), "
          f"{r['cliente_inativo']} com cliente inativo. {duracao:.1f}s.")
    _resumo_github([
        f"### Recorrências {'(simulação)' if args.dry_run else ''}",
        f"- Escopo: {escopo} · hoje = {r['hoje']}",
        f"- Regras vencidas: **{r['regras']}** em {r['empresas']} empresa(s)",
        f"- Follow-ups: {r['tarefas']} · Oportunidades: {r['oportunidades']}",
        f"- Já existiam: {r['ja_existiam']} · Puladas: {r['puladas']} · Cliente inativo: {r['cliente_inativo']}",
    ])
    return 0


if __name__ == "__main__":
    sys.exit(main())
