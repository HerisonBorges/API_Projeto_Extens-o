"""Modelo, exportação e importação de clientes em planilha.

  GET  /clientes/modelo?formato=xlsx|csv      modelo oficial vazio (qualquer perfil)
  GET  /clientes/exportar?formato=xlsx|csv    clientes da empresa no mesmo layout (Gestor)
  POST /clientes/importar[?simular=1]         multipart, campo "arquivo" (Gestor)

simular=1 valida e devolve a prévia sem gravar nada. Sem simular, grava tudo
numa única transação: com qualquer linha inválida, nada entra (422).
"""
from flask import Blueprint, Response, g, jsonify, request
from psycopg2 import errors

from database.conexao import get_db_connection
from documento import formatar_documento
from importacao import (
    LIMITE_ERROS_LISTADOS,
    ArquivoInvalido,
    gerar_csv,
    gerar_xlsx,
    ler_planilha,
    nome_seguro,
    previa,
    sha256,
    validar_linhas,
)
from recorrencia import DIAS_SEMANA, hoje_na_empresa
from routes.recorrencias import inserir_recorrencia
from seguranca import fuso_empresa, perfil_requerido, token_obrigatorio


importacao_bp = Blueprint("importacao", __name__, url_prefix="/clientes")

TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _formato():
    formato = request.args.get("formato", "xlsx")
    return formato if formato in ("xlsx", "csv") else None


def _arquivo(conteudo, formato, nome_base):
    return Response(
        conteudo,
        mimetype=TIPO_XLSX if formato == "xlsx" else "text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{nome_base}.{formato}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@importacao_bp.route("/modelo", methods=["GET"])
@token_obrigatorio
def baixar_modelo():
    formato = _formato()
    if not formato:
        return jsonify({"erro": "formato inválido. Use xlsx ou csv."}), 400
    conteudo = gerar_xlsx([]) if formato == "xlsx" else gerar_csv([])
    return _arquivo(conteudo, formato, "sandro-crm-modelo-clientes")


@importacao_bp.route("/exportar", methods=["GET"])
@token_obrigatorio
@perfil_requerido("Gestor")
def exportar_clientes():
    """Uma linha por recorrência (cliente sem recorrência = uma linha).
    O mesmo arquivo pode ser importado em outra conta (o CPF/CNPJ agrupa as linhas)."""
    formato = _formato()
    if not formato:
        return jsonify({"erro": "formato inválido. Use xlsx ou csv."}), 400

    with get_db_connection() as conexao, conexao.cursor() as cursor:
        cursor.execute("""
            SELECT c.nome, c.documento, c.email, c.telefone, c.status,
                   r.tipo, r.frequencia, r.dia_semana, r.dia_mes, r.titulo, r.valor, r.notas
            FROM clientes c
            LEFT JOIN recorrencias r ON r.cliente_id = c.id AND r.empresa_id = c.empresa_id AND r.ativo
            WHERE c.empresa_id = %s
            ORDER BY c.nome, c.id, r.id;
        """, (g.empresa_id,))
        linhas = []
        for (nome, documento, email, telefone, status,
             tipo, frequencia, dia_semana, dia_mes, titulo, valor, notas) in cursor.fetchall():
            dia = DIAS_SEMANA[dia_semana].replace("-feira", "") if dia_semana else dia_mes
            linhas.append([
                nome, formatar_documento(documento), email, telefone, status,
                tipo, frequencia, dia, titulo,
                f"{valor:.2f}".replace(".", ",") if valor is not None else None, notas,
            ])

    conteudo = gerar_xlsx(linhas, com_instrucoes=False) if formato == "xlsx" else gerar_csv(linhas)
    return _arquivo(conteudo, formato, "sandro-crm-clientes")


@importacao_bp.route("/importar", methods=["POST"])
@token_obrigatorio
@perfil_requerido("Gestor")
def importar_clientes():
    arquivo = request.files.get("arquivo")
    if arquivo is None or not arquivo.filename:
        return jsonify({"erro": "Envie a planilha no campo 'arquivo' (multipart/form-data)."}), 400
    simular = request.args.get("simular") == "1"

    conteudo = arquivo.read()
    try:
        formato, linhas = ler_planilha(arquivo.filename, conteudo)
        registros, erros, avisos = validar_linhas(linhas)
    except ArquivoInvalido as problema:
        return jsonify({"erro": str(problema)}), 400

    clientes_novos = {r["chave"] for r in registros}
    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            # CPF/CNPJ que já existe NESTA empresa (outras empresas não contam nem aparecem)
            documentos = sorted({r["cliente"]["documento"] for r in registros if r["cliente"]["documento"]})
            if documentos:
                cursor.execute("""
                    SELECT documento, id FROM clientes
                    WHERE empresa_id = %s AND documento = ANY(%s);
                """, (g.empresa_id, documentos))
                existentes = dict(cursor.fetchall())
                for r in registros:
                    doc = r["cliente"]["documento"]
                    if doc in existentes:
                        erros.append({"linha": r["linha"], "coluna": "CPF/CNPJ",
                                      "mensagem": f"Já existe um cliente com este CPF/CNPJ (código #{existentes[doc]})."})

            erros.sort(key=lambda e: e["linha"])
            resumo = {
                "linhas": len(registros) + len({e["linha"] for e in erros}),
                "clientes": len(clientes_novos),
                "recorrencias": sum(1 for r in registros if r["recorrencia"]),
                "erros": erros[:LIMITE_ERROS_LISTADOS],
                "total_erros": len(erros),
                "avisos": avisos,
            }

            if simular:
                return jsonify({**resumo, "valido": not erros, "previa": previa(registros)}), 200
            if erros:
                return jsonify({**resumo, "valido": False,
                                "erro": f"Nada foi importado: {len(erros)} problema(s) na planilha. "
                                        "Corrija as linhas indicadas e envie de novo."}), 422

            # Tudo numa transação: qualquer falha desfaz o arquivo inteiro
            hoje = hoje_na_empresa(cursor, fuso_empresa())
            ids = {}
            try:
                for r in registros:
                    if r["chave"] not in ids:
                        c = r["cliente"]
                        cursor.execute("""
                            INSERT INTO clientes (empresa_id, nome, documento, email, telefone, status,
                                                  atualizado_em, atualizado_por)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
                            RETURNING id;
                        """, (g.empresa_id, c["nome"], c["documento"], c["email"], c["telefone"],
                              c["status"], g.usuario_id))
                        ids[r["chave"]] = cursor.fetchone()[0]
                    if r["recorrencia"]:
                        inserir_recorrencia(cursor, g.empresa_id, ids[r["chave"]], r["recorrencia"],
                                            g.usuario_id, hoje)
                cursor.execute("""
                    INSERT INTO importacoes (empresa_id, usuario_id, arquivo_nome, formato, sha256,
                                             linhas, clientes_criados, recorrencias_criadas)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """, (g.empresa_id, g.usuario_id, nome_seguro(arquivo.filename), formato, sha256(conteudo),
                      resumo["linhas"], len(ids), resumo["recorrencias"]))
            except errors.UniqueViolation:
                # Outro usuário cadastrou o mesmo CPF/CNPJ durante a importação
                conexao.rollback()
                return jsonify({"erro": "Um CPF/CNPJ da planilha acabou de ser cadastrado por outra pessoa. "
                                        "Nada foi importado; envie de novo para ver a linha."}), 409
        conexao.commit()

    return jsonify({
        "mensagem": f"{len(ids)} cliente(s) e {resumo['recorrencias']} recorrência(s) importados.",
        "clientes_criados": len(ids),
        "recorrencias_criadas": resumo["recorrencias"],
        "avisos": avisos,
    }), 201
