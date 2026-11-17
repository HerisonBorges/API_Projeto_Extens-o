import { useCallback, useEffect, useState } from "react";

import { ativarRecorrencia, excluirRecorrencia, listarRecorrencias } from "../../services/api.js";
import Botao from "../ui/Botao.jsx";
import Card from "../ui/Card.jsx";
import { Carregando, Erro, Vazio } from "../ui/Estado.jsx";
import Modal from "../ui/Modal.jsx";
import StatusBadge from "../ui/StatusBadge.jsx";
import { descreverRecorrencia, formatarData, formatarMoeda } from "../ui/formatos.js";
import RecorrenciaModal from "./RecorrenciaModal.jsx";

/** Regras recorrentes do cliente: o worker gera follow-ups/oportunidades em cada data. */
export default function RecorrenciasCliente({ cliente, usuario, onAviso }) {
  const [regras, setRegras] = useState(null);
  const [erro, setErro] = useState(null);
  const [editando, setEditando] = useState(null); // null | "nova" | regra
  const [excluindo, setExcluindo] = useState(null);
  const [ocupado, setOcupado] = useState(null); // id da regra com ação em andamento

  const carregar = useCallback(() => {
    listarRecorrencias({ clienteId: cliente.id })
      .then((lista) => {
        setErro(null);
        setRegras(lista);
      })
      .catch((e) => setErro(e.message));
  }, [cliente.id]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const substituir = (nova) => setRegras((lista) => {
    const sem = (lista ?? []).filter((r) => r.id !== nova.id);
    return [...sem, nova].sort((a, b) => Number(b.ativo) - Number(a.ativo)
      || a.proxima_execucao.localeCompare(b.proxima_execucao));
  });

  async function alternar(regra) {
    setOcupado(regra.id);
    try {
      const r = await ativarRecorrencia(regra.id, !regra.ativo);
      substituir(r.recorrencia);
      onAviso(`"${regra.titulo}" ${r.recorrencia.ativo ? "retomada" : "pausada"}.`);
    } catch (e) {
      onAviso(e.message);
    } finally {
      setOcupado(null);
    }
  }

  async function confirmarExclusao() {
    setOcupado(excluindo.id);
    try {
      await excluirRecorrencia(excluindo.id);
      setRegras((lista) => lista.filter((r) => r.id !== excluindo.id));
      onAviso(`Recorrência "${excluindo.titulo}" excluída. O que já foi gerado continua.`);
      setExcluindo(null);
    } catch (e) {
      onAviso(e.message);
      setExcluindo(null);
    } finally {
      setOcupado(null);
    }
  }

  return (
    <Card
      titulo="Recorrências"
      acao={
        <Botao tamanho="sm" variante="contorno" onClick={() => setEditando("nova")}
               aria-label={`Nova recorrência para ${cliente.nome}`}>
          + Nova recorrência
        </Botao>
      }
    >
      {erro && <div className="p-5"><Erro mensagem={erro} onTentarDeNovo={carregar} /></div>}
      {!erro && !regras && <Carregando texto="Carregando recorrências..." />}
      {regras && regras.length === 0 && (
        <Vazio>Nenhuma recorrência. Ex.: “compra toda segunda” ou “fechamento todo dia 5”.</Vazio>
      )}
      {regras && regras.length > 0 && (
        <ul className="divide-y divide-sandro-borda/15">
          {regras.map((r) => (
            <li key={r.id} className={`space-y-2 px-5 py-3 ${r.ativo ? "" : "opacity-70"}`}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-white">{r.titulo}</p>
                  <p className="text-xs text-sandro-label">
                    {descreverRecorrencia(r)}
                    {" · "}{r.tipo === "oportunidade"
                      ? `Oportunidade${r.valor != null ? ` de ${formatarMoeda(r.valor)}` : ""}`
                      : "Follow-up"}
                  </p>
                </div>
                {r.ativo
                  ? <StatusBadge tom="azul" icone="↻">Próxima: {formatarData(r.proxima_execucao)}</StatusBadge>
                  : <StatusBadge tom="neutro" icone="⏸">Pausada</StatusBadge>}
              </div>
              {r.notas && <p className="text-xs text-slate-300">{r.notas}</p>}
              <div className="flex flex-wrap gap-2">
                <Botao tamanho="sm" variante="secundario" onClick={() => setEditando(r)}
                       aria-label={`Editar recorrência ${r.titulo}`}>Editar</Botao>
                <Botao tamanho="sm" variante="secundario" onClick={() => alternar(r)}
                       carregando={ocupado === r.id} textoCarregando="Salvando..."
                       aria-label={`${r.ativo ? "Pausar" : "Retomar"} recorrência ${r.titulo}`}>
                  {r.ativo ? "Pausar" : "Retomar"}
                </Botao>
                {usuario.perfil === "Gestor" && (
                  <Botao tamanho="sm" variante="perigo" onClick={() => setExcluindo(r)}
                         aria-label={`Excluir recorrência ${r.titulo}`}>Excluir</Botao>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {editando && (
        <RecorrenciaModal
          cliente={cliente}
          recorrencia={editando === "nova" ? null : editando}
          onFechar={() => setEditando(null)}
          onSalva={(salva) => {
            substituir(salva);
            onAviso(`"${salva.titulo}": ${salva.descricao.toLowerCase()}, próxima em ${formatarData(salva.proxima_execucao)}.`);
            setEditando(null);
          }}
        />
      )}

      {excluindo && (
        <Modal titulo="Excluir recorrência?"
               descricao={`"${excluindo.titulo}" deixa de se repetir. Follow-ups e oportunidades já gerados continuam.`}
               onFechar={() => setExcluindo(null)} bloqueado={ocupado === excluindo.id}>
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <Botao variante="fantasma" onClick={() => setExcluindo(null)} disabled={ocupado === excluindo.id}>Cancelar</Botao>
            <Botao variante="perigo" onClick={confirmarExclusao} carregando={ocupado === excluindo.id}
                   textoCarregando="Excluindo...">Excluir</Botao>
          </div>
        </Modal>
      )}
    </Card>
  );
}
