"""Seed de homologação: Loja Fênix.

Cria empresa, usuários, clientes, oportunidades em todas as etapas, tarefas e
interações, cobrindo o roteiro de homologação no navegador:
  - Gestor 24/7 e Atendimento com janela 08:00-18:00
  - venda Fechada sem agendamento (testar o modal "Reciclar Lead")
  - venda Fechada com reciclagem JÁ VENCIDA (testar o worker na hora)
  - orçamento parado há 9 dias (alerta RF04) e follow-up atrasado
  - histórico de interações por canal (Ligação, WhatsApp, E-mail, Reunião)

Uso (na raiz do projeto):
    python3 -m database.seed_fenix             # cria, se ainda não existir
    python3 -m database.seed_fenix --resetar   # recria os dados de negócio

--resetar mantém a empresa e usuários criados fora do seed (ex.: sua conta);
apaga e recria clientes, oportunidades, tarefas, interações e configurações,
e restaura os usuários do seed (senha, perfil e horário).

Senha dos usuários do seed: variável SEED_FENIX_SENHA ou "senha123".
Uso exclusivo em homologação: não rode em produção.
"""
import argparse
import os
import sys

import bcrypt
from dotenv import load_dotenv

load_dotenv()

from config import em_producao  # noqa: E402
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
    ("Mercado Bom Preço", "compras@bompreco.exemplo", "(11) 3000-0005", "Inativo"),
]

OPORTUNIDADES = [
    # titulo, cliente, valor, etapa, dias desde a mudança de etapa, reciclagem, responsável
    ("Kit vitrine iluminada", 0, 4800, "Fechado", 3, None, 0),
    ("Reforma da fachada", 2, 12000, "Fechado", 40, "vencida", 0),
    ("Uniformes da equipe", 1, 2300, "Proposta", 9, None, 1),
    ("Sistema de som ambiente", 3, 3500, "Negociação", 2, None, 1),
    ("Consultoria de layout", 1, 1500, "Qualificação", 1, None, 1),
    ("Etiquetas personalizadas", 3, 900, "Prospecção", 0, None, 1),
]

TAREFAS = [
    # titulo, cliente, dias até o vencimento (negativo = atrasada)
    ("Ligar para confirmar medidas", 1, -2),
    ("Enviar catálogo de uniformes", 1, 0),
    ("Visita técnica na oficina", 3, 5),
]

INTERACOES = [
    # cliente, oportunidade (índice ou None), usuário, tipo, descrição, dias atrás
    (0, 0, 0, "Reunião", "Apresentação do projeto da vitrine na loja.", 12),
    (0, 0, 0, "E-mail", "Envio da proposta final com prazo de instalação.", 5),
    (2, 1, 0, "Ligação", "Cliente aprovou o orçamento da fachada.", 41),
    (1, 2, 1, "WhatsApp", "Enviadas fotos dos modelos de uniforme.", 9),
    (1, 4, 1, "Ligação", "Agendada visita para medir o espaço.", 1),
    (3, 3, 1, "WhatsApp", "Cliente pediu desconto no sistema de som.", 2),
    (3, 5, 1, "E-mail", "Primeiro contato sobre etiquetas.", 0),
]


def limpar_dados_de_negocio(cursor, empresa_id):
    for tabela in ("interacoes", "tarefas", "oportunidades", "clientes", "configuracoes"):
        cursor.execute(f"DELETE FROM {tabela} WHERE empresa_id = %s;", (empresa_id,))


def garantir_empresa(cursor):
    cursor.execute("SELECT id FROM empresas WHERE nome = %s ORDER BY id LIMIT 1;",
                   (NOME_EMPRESA,))
    linha = cursor.fetchone()
    if linha:
        return linha[0]

    cursor.execute("""
        INSERT INTO empresas (nome, email) VALUES (%s, 'contato@lojafenix.com.br')
        RETURNING id;
    """, (NOME_EMPRESA,))
    return cursor.fetchone()[0]


def garantir_usuarios(cursor, empresa_id):
    senha_hash = bcrypt.hashpw(SENHA.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    ids = []

    for nome, email, perfil, inicio, fim in USUARIOS:
        cursor.execute("""
            INSERT INTO usuarios (empresa_id, nome, email, senha, perfil,
                                  hora_inicio_acesso, hora_fim_acesso)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET
                nome = EXCLUDED.nome,
                senha = EXCLUDED.senha,
                perfil = EXCLUDED.perfil,
                hora_inicio_acesso = EXCLUDED.hora_inicio_acesso,
                hora_fim_acesso = EXCLUDED.hora_fim_acesso
            WHERE usuarios.empresa_id = EXCLUDED.empresa_id
            RETURNING id;
        """, (empresa_id, nome, email, senha_hash, perfil, inicio, fim))
        ids.append(cursor.fetchone()[0])

    return ids


def popular_dados(cursor, empresa_id, usuario_ids):
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

    oportunidade_ids = []
    for titulo, cliente, valor, etapa, dias_etapa, reciclagem, responsavel in OPORTUNIDADES:
        vencida = reciclagem == "vencida"
        cursor.execute("""
            INSERT INTO oportunidades (empresa_id, cliente_id, titulo, valor, etapa,
                                       criado_em, etapa_atualizada_em, status_reciclagem,
                                       data_reciclagem_agendada, responsavel_id)
            VALUES (%s, %s, %s, %s, %s,
                    NOW() - make_interval(days => %s + 7),
                    NOW() - make_interval(days => %s),
                    CASE WHEN %s THEN 'pendente' ELSE 'nenhum' END,
                    CASE WHEN %s THEN NOW() - INTERVAL '5 minutes' END,
                    %s)
            RETURNING id;
        """, (empresa_id, cliente_ids[cliente], titulo, valor, etapa, dias_etapa, dias_etapa,
              vencida, vencida, usuario_ids[responsavel]))
        oportunidade_ids.append(cursor.fetchone()[0])

    for titulo, cliente, dias in TAREFAS:
        cursor.execute("""
            INSERT INTO tarefas (empresa_id, cliente_id, titulo, data_vencimento, concluida)
            VALUES (%s, %s, %s, CURRENT_DATE + %s, FALSE);
        """, (empresa_id, cliente_ids[cliente], titulo, dias))

    for cliente, oportunidade, usuario, tipo, descricao, dias in INTERACOES:
        cursor.execute("""
            INSERT INTO interacoes (empresa_id, cliente_id, oportunidade_id, usuario_id,
                                    tipo, descricao, criado_em)
            VALUES (%s, %s, %s, %s, %s, %s, NOW() - make_interval(days => %s));
        """, (empresa_id, cliente_ids[cliente],
              oportunidade_ids[oportunidade] if oportunidade is not None else None,
              usuario_ids[usuario], tipo, descricao, dias))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Seed de homologação da Loja Fênix.")
    parser.add_argument("--resetar", action="store_true",
                        help="Recria os dados de negócio (mantém empresa e usuários extras).")
    parser.add_argument("--sim", action="store_true",
                        help="Confirma o --resetar (sem isso, só mostra o que seria apagado).")
    args = parser.parse_args(argv)

    if em_producao():
        print("Recusado: APP_ENV=producao. O seed cria contas com senha conhecida "
              "e o --resetar apaga dados. Use só em homologação.")
        return 2

    emails = [u[1] for u in USUARIOS]

    with get_db_connection() as conexao:
        try:
            with conexao.cursor() as cursor:
                cursor.execute("SELECT id FROM empresas WHERE nome = %s ORDER BY id;",
                               (NOME_EMPRESA,))
                existentes = [linha[0] for linha in cursor.fetchall()]

                if existentes and not args.resetar:
                    print(f"Loja Fênix já existe (empresa_id {existentes[0]}). "
                          "Use --resetar para recriar os dados.")
                    return 0

                # E-mails do seed presos a outra empresa: não mexe em nada
                cursor.execute("""
                    SELECT DISTINCT empresa_id FROM usuarios WHERE email = ANY(%s);
                """, (emails,))
                estranhas = {linha[0] for linha in cursor.fetchall()} - set(existentes[:1])
                if estranhas:
                    print(f"Os e-mails do seed já pertencem a outra empresa {sorted(estranhas)}. "
                          "Nada foi alterado.")
                    return 1

                # --resetar apaga dados reais: mostra o impacto e exige --sim
                if existentes and not args.sim:
                    contagens = {}
                    for tabela in ("clientes", "oportunidades", "tarefas", "interacoes"):
                        cursor.execute(f"SELECT COUNT(*) FROM {tabela} WHERE empresa_id = %s;",
                                       (existentes[0],))
                        contagens[tabela] = cursor.fetchone()[0]
                    print(f"--resetar vai APAGAR da Loja Fênix (empresa_id {existentes[0]}), "
                          f"no banco {os.getenv('DB_HOST', 'localhost')}:")
                    for tabela, total in contagens.items():
                        print(f"  {total} {tabela}")
                    print("e restaurar as senhas dos usuários do seed. Nada foi alterado.")
                    print("Para confirmar: python3 -m database.seed_fenix --resetar --sim")
                    return 1

                empresa_id = garantir_empresa(cursor)
                limpar_dados_de_negocio(cursor, empresa_id)
                usuario_ids = garantir_usuarios(cursor, empresa_id)
                popular_dados(cursor, empresa_id, usuario_ids)

                cursor.execute("SELECT COUNT(*) FROM usuarios WHERE empresa_id = %s;",
                               (empresa_id,))
                total_usuarios = cursor.fetchone()[0]

            conexao.commit()
        except Exception:
            conexao.rollback()
            raise

    print(f"Seed Loja Fênix pronto. empresa_id = {empresa_id}")
    print(f"  {total_usuarios} usuários ({len(USUARIOS)} do seed), {len(CLIENTES)} clientes, "
          f"{len(OPORTUNIDADES)} oportunidades, {len(TAREFAS)} tarefas, "
          f"{len(INTERACOES)} interações")
    print("  Logins do seed: gestor@lojafenix.com.br e mariana@lojafenix.com.br")
    return 0


if __name__ == "__main__":
    sys.exit(main())
