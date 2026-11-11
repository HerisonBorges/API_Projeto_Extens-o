"""Worker de reciclagem pós-venda.

Para cada oportunidade em 'Fechado' com reciclagem 'pendente' e data vencida:
  1. marca a original como 'processado' (ela continua em 'Fechado', então a
     receita e os KPIs não mudam);
  2. cria uma NOVA oportunidade em 'Prospecção' para o mesmo cliente,
     com oportunidade_origem_id apontando para a original.

Uso (na raiz do projeto):
    python3 -m database.worker_reciclagem              # processa tudo
    python3 -m database.worker_reciclagem --dry-run    # só lista, não altera
    python3 -m database.worker_reciclagem --empresa 12 # restringe a uma empresa

Agendamento sugerido (cron, a cada 15 minutos):
    */15 * * * * cd /caminho/do/projeto && python3 -m database.worker_reciclagem

É seguro rodar duas instâncias ao mesmo tempo: FOR UPDATE SKIP LOCKED garante
que cada agendamento é processado uma única vez.
"""
import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from database.conexao import conectar_banco  # noqa: E402
from routes.oportunidades import ETAPA_FINAL, ETAPA_INICIAL  # noqa: E402


PREFIXO_TITULO = "Reciclagem: "

SQL_PROCESSAR = """
    WITH vencidas AS (
        SELECT id
        FROM oportunidades
        WHERE etapa = %(etapa_final)s
          AND status_reciclagem = 'pendente'
          AND data_reciclagem_agendada <= NOW()
          AND (%(empresa_id)s::int IS NULL OR empresa_id = %(empresa_id)s::int)
        ORDER BY data_reciclagem_agendada
        FOR UPDATE SKIP LOCKED
    ),
    marcadas AS (
        UPDATE oportunidades o
        SET status_reciclagem = 'processado'
        FROM vencidas v
        WHERE o.id = v.id
        RETURNING o.id, o.empresa_id, o.cliente_id, o.titulo, o.valor, o.responsavel_id
    )
    INSERT INTO oportunidades (
        empresa_id, cliente_id, titulo, valor, etapa,
        etapa_atualizada_em, oportunidade_origem_id, responsavel_id
    )
    SELECT empresa_id,
           cliente_id,
           LEFT(%(prefixo)s || titulo, 150),
           valor,
           %(etapa_inicial)s,
           NOW(),
           id,
           responsavel_id
    FROM marcadas
    RETURNING id, oportunidade_origem_id, empresa_id;
"""

SQL_LISTAR = """
    SELECT id, empresa_id, titulo, data_reciclagem_agendada
    FROM oportunidades
    WHERE etapa = %(etapa_final)s
      AND status_reciclagem = 'pendente'
      AND data_reciclagem_agendada <= NOW()
      AND (%(empresa_id)s::int IS NULL OR empresa_id = %(empresa_id)s::int)
    ORDER BY data_reciclagem_agendada;
"""


def _parametros(empresa_id):
    return {
        "etapa_final": ETAPA_FINAL,
        "etapa_inicial": ETAPA_INICIAL,
        "prefixo": PREFIXO_TITULO,
        "empresa_id": empresa_id,
    }


def listar_vencidas(empresa_id=None):
    conexao = conectar_banco()
    try:
        with conexao.cursor() as cursor:
            cursor.execute(SQL_LISTAR, _parametros(empresa_id))
            return cursor.fetchall()
    finally:
        conexao.close()


def processar_reciclagens(empresa_id=None):
    """Processa os agendamentos vencidos em uma única transação.

    Retorna lista de dicts {nova_id, origem_id, empresa_id}.
    """
    conexao = conectar_banco()
    try:
        with conexao.cursor() as cursor:
            cursor.execute(SQL_PROCESSAR, _parametros(empresa_id))
            criadas = cursor.fetchall()
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()

    return [
        {"nova_id": nova, "origem_id": origem, "empresa_id": empresa}
        for nova, origem, empresa in criadas
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Worker de reciclagem pós-venda.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Apenas lista o que seria processado.")
    parser.add_argument("--empresa", type=int, default=None,
                        help="Processa apenas esta empresa_id.")
    args = parser.parse_args(argv)

    if args.dry_run:
        vencidas = listar_vencidas(args.empresa)
        print(f"[dry-run] {len(vencidas)} reciclagem(ns) vencida(s).")
        for op_id, empresa, titulo, data in vencidas:
            print(f"  oportunidade {op_id} (empresa {empresa}) '{titulo}' agendada para {data.isoformat()}")
        return 0

    criadas = processar_reciclagens(args.empresa)
    print(f"{len(criadas)} reciclagem(ns) processada(s).")
    for item in criadas:
        print(f"  origem {item['origem_id']} -> nova oportunidade {item['nova_id']} "
              f"(empresa {item['empresa_id']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
