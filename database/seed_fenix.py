"""Seed de homologação: Loja Fênix.

Cria empresa, usuários, clientes, oportunidades em todas as etapas e tarefas,
cobrindo o roteiro de homologação no navegador:
  - Gestor 24/7 e Atendimento com janela 08:00-18:00
  - venda Fechada sem agendamento (testar o modal "Reciclar Lead")
  - venda Fechada com reciclagem JÁ VENCIDA (testar o worker na hora)
  - orçamento parado há 9 dias (alerta RF04) e follow-up atrasado

Uso (na raiz do projeto):
    python3 -m database.seed_fenix             # cria, se ainda não existir
    python3 -m database.seed_fenix --resetar   # apaga a Fênix e recria do zero

Senha dos dois usuários: variável SEED_FENIX_SENHA ou "senha123".
Uso exclusivo em homologação: não rode em produção.
"""
import argparse
import os
import sys

import bcrypt
from dotenv import load_dotenv

load_dotenv()

from database.conexao import get_db_connection  # noqa: E402


NOME_EMPRESA = "Loja Fênix"
SENHA = os.getenv("SEED_FENIX_SENHA", "senha123")

USUARIOS = [
    # nome, email, perfil, inicio, fim
    ("Carlos Gestor", "gestor@lojafenix.com.br", "Gestor", None, None),
    ("Mariana Vendedora", "mariana@lojafenix.com.br", "Atendimento", "08:00", "18:00"),
]

CLIENTES = [
    # nome, email, telefone, status
    ("Ana Exemplo", "ana@exemplo.com", "(11) 90000-0001", "Cliente"),
    ("Bruno Exemplo", "bruno@exemplo.com", "(11) 90000-0002", "Lead"),
    ("Padaria Estrela", "contato@padariaestrela.exemplo", "(11) 3000-0003", "Cliente"),
    ("Oficina Rota Sul", "oficina@rotasul.exemplo", "(11) 3000-0004", "Lead"),
]

OPORTUNIDADES = [
    # titulo, indice do cliente, valor, etapa, dias desde a última mudança de etapa, reciclagem
    ("Kit vitrine iluminada", 0, 4800, "Fechado", 3, None),
    ("Reforma da fachada", 2, 12000, "Fechado", 40, "vencida"),
    ("Uniformes da equipe", 1, 2300, "Proposta", 9, None),
    ("Sistema de som ambiente", 3, 3500, "Negociação", 2, None),
    ("Consultoria de layout", 1, 1500, "Qualificação", 1, None),
    ("Etiquetas personalizadas", 3, 900, "Prospecção", 0, None),
]

TAREFAS = [
    # titulo, indice do cliente, dias até o vencimento (negativo = atrasada)
    ("Ligar para confirmar medidas", 1, -2),
    ("Enviar catálogo de uniformes", 1, 1),
    ("Visita técnica na oficina", 3, 5),
]


def apagar_empresa(cursor, empresa_id):
    for tabela in ("tarefas", "oportunidades", "clientes", "configuracoes", "usuarios"):
        cursor.execute(f"DELETE FROM {tabela} WHERE empresa_id = %s;", (empresa_id,))
    cursor.execute("DELETE FROM empresas WHERE id = %s;", (empresa_id,))


def popular(cursor):
    cursor.execute("""
        INSERT INTO empresas (nome, email) VALUES (%s, 'contato@lojafenix.com.br')
        RETURNING id;
    """, (NOME_EMPRESA,))
    empresa_id = cursor.fetchone()[0]

    senha_hash = bcrypt.hashpw(SENHA.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    for nome, email, perfil, inicio, fim in USUARIOS:
        cursor.execute("""
            INSERT INTO usuarios (empresa_id, nome, email, senha, perfil,
                                  hora_inicio_acesso, hora_fim_acesso)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """, (empresa_id, nome, email, senha_hash, perfil, inicio, fim))

    cursor.execute("""
        INSERT INTO configuracoes (empresa_id, notificacoes_email, tema_escuro,
                                   dias_alerta_orcamento)
        VALUES (%s, TRUE, TRUE, 7);
    """, (empresa_id,))

    cliente_ids = []
    for nome, email, telefone, status in CLIENTES:
        cursor.execute("""
            INSERT INTO clientes (empresa_id, nome, email, telefone, status)
            VALUES (%s, %s, %s, %s, %s) RETURNING id;
        """, (empresa_id, nome, email, telefone, status))
        cliente_ids.append(cursor.fetchone()[0])

    for titulo, cliente, valor, etapa, dias_etapa, reciclagem in OPORTUNIDADES:
        cursor.execute("""
            INSERT INTO oportunidades (empresa_id, cliente_id, titulo, valor, etapa,
                                       etapa_atualizada_em, status_reciclagem,
                                       data_reciclagem_agendada)
            VALUES (%s, %s, %s, %s, %s,
                    NOW() - make_interval(days => %s),
                    CASE WHEN %s THEN 'pendente' ELSE 'nenhum' END,
                    CASE WHEN %s THEN NOW() - INTERVAL '5 minutes' END);
        """, (empresa_id, cliente_ids[cliente], titulo, valor, etapa, dias_etapa,
              reciclagem == "vencida", reciclagem == "vencida"))

    for titulo, cliente, dias in TAREFAS:
        cursor.execute("""
            INSERT INTO tarefas (empresa_id, cliente_id, titulo, data_vencimento, concluida)
            VALUES (%s, %s, %s, CURRENT_DATE + %s, FALSE);
        """, (empresa_id, cliente_ids[cliente], titulo, dias))

    return empresa_id


def main(argv=None):
    parser = argparse.ArgumentParser(description="Seed de homologação da Loja Fênix.")
    parser.add_argument("--resetar", action="store_true",
                        help="Apaga os dados da Loja Fênix e recria do zero.")
    args = parser.parse_args(argv)

    emails = [u[1] for u in USUARIOS]

    with get_db_connection() as conexao:
        try:
            with conexao.cursor() as cursor:
                cursor.execute("SELECT id FROM empresas WHERE nome = %s;", (NOME_EMPRESA,))
                existentes = [linha[0] for linha in cursor.fetchall()]

                # E-mails do seed presos a outra empresa bloqueariam o INSERT
                cursor.execute("""
                    SELECT DISTINCT empresa_id FROM usuarios WHERE email = ANY(%s);
                """, (emails,))
                donas_dos_emails = {linha[0] for linha in cursor.fetchall()}

                if existentes and not args.resetar:
                    print(f"Loja Fênix já existe (empresa_id {existentes[0]}). "
                          "Use --resetar para recriar.")
                    return 0

                estranhas = donas_dos_emails - set(existentes)
                if estranhas:
                    print(f"Os e-mails do seed já pertencem a outra empresa {sorted(estranhas)}. "
                          "Nada foi alterado.")
                    return 1

                for empresa_id in existentes:
                    apagar_empresa(cursor, empresa_id)

                empresa_id = popular(cursor)

            conexao.commit()
        except Exception:
            conexao.rollback()
            raise

    print(f"Seed Loja Fênix criado. empresa_id = {empresa_id}")
    print(f"  {len(USUARIOS)} usuários, {len(CLIENTES)} clientes, "
          f"{len(OPORTUNIDADES)} oportunidades, {len(TAREFAS)} tarefas")
    print("  Logins: gestor@lojafenix.com.br e mariana@lojafenix.com.br")
    return 0


if __name__ == "__main__":
    sys.exit(main())
