import { useEffect, useState } from "react";

import { criarTarefa, listarClientes, listarOportunidades } from "../../services/api.js";
import Botao from "../ui/Botao.jsx";
import Campo, { classeEntrada } from "../ui/Campo.jsx";
import Modal from "../ui/Modal.jsx";
import { ETAPA_FINAL, daquiDiasISO, formatarData, hojeISO } from "../ui/formatos.js";

const ATALHOS = [
  { rotulo: "Hoje", dias: 0 },
  { rotulo: "Amanhã", dias: 1 },
  { rotulo: "Em 3 dias", dias: 3 },
  { rotulo: "Em 1 semana", dias: 7 },
];

/**
 * Agenda um follow-up.
 * - cliente: fixa o cliente (detalhe do cliente). Sem ele, a pessoa escolhe na lista.
 * - sugestao: { titulo, oportunidadeId } para pré-preencher (ex.: depois de uma interação).
 */
export default function NovoFollowupModal({ cliente = null, sugestao = {}, onFechar, onCriado }) {
  const [clientes, setClientes] = useState(cliente ? [cliente] : null);
  const [oportunidades, setOportunidades] = useState([]);
  const [form, setForm] = useState({
    clienteId: cliente ? String(cliente.id) : "",
    oportunidadeId: sugestao.oportunidadeId ? String(sugestao.oportunidadeId) : "",
    titulo: sugestao.titulo ?? "",
    data: daquiDiasISO(1),
    descricao: "",
  });
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);

  const alterar = (campo) => (e) => setForm((f) => ({ ...f, [campo]: e.target.value }));

  useEffect(() => {
    if (!cliente) listarClientes().then(setClientes).catch((e) => setErro(e.message));
    listarOportunidades()
      .then((ops) => setOportunidades(ops.filter((o) => o.etapa !== ETAPA_FINAL)))
      .catch(() => setOportunidades([]));
  }, [cliente]);

  const doCliente = oportunidades.filter((o) => String(o.cliente_id) === form.clienteId);

  async function salvar(e) {
    e.preventDefault();
    setErro(null);
    if (!form.titulo.trim()) return setErro("Diga o que precisa ser feito.");
    if (!form.data) return setErro("Escolha a data.");

    setEnviando(true);
    try {
      await criarTarefa({
        titulo: form.titulo.trim(),
        descricao: form.descricao.trim() || null,
        data_vencimento: form.data,
        cliente_id: form.clienteId ? Number(form.clienteId) : null,
        oportunidade_id: form.oportunidadeId ? Number(form.oportunidadeId) : null,
      });
      onCriado({ titulo: form.titulo.trim(), data: form.data });
    } catch (erroApi) {
      setErro(erroApi.message);
      setEnviando(false);
    }
  }

  return (
    <Modal
      titulo="Novo follow-up"
      descricao={cliente ? `Próximo contato com ${cliente.nome}` : "Agende o próximo contato com um cliente."}
      onFechar={onFechar}
      bloqueado={enviando}
      largura="max-w-lg"
    >
      <form onSubmit={salvar} className="space-y-4">
        {!cliente && (
          <Campo rotulo="Cliente">
            {(p) => (
              <select {...p} value={form.clienteId} disabled={!clientes}
                      onChange={(e) => setForm((f) => ({ ...f, clienteId: e.target.value, oportunidadeId: "" }))}
                      className={classeEntrada}>
                <option value="">{clientes ? "Sem cliente vinculado" : "Carregando clientes..."}</option>
                {(clientes ?? []).map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
              </select>
            )}
          </Campo>
        )}

        <Campo rotulo="O que precisa ser feito *">
          {(p) => (
            <input {...p} required maxLength={150} value={form.titulo} onChange={alterar("titulo")}
                   placeholder="Ex.: Ligar para confirmar o orçamento" className={classeEntrada} />
          )}
        </Campo>

        <fieldset>
          <legend className="mb-2 text-xs font-medium text-sandro-label">Quando *</legend>
          <div className="flex flex-wrap items-center gap-2">
            {ATALHOS.map(({ rotulo, dias }) => {
              const valor = daquiDiasISO(dias);
              const ativo = form.data === valor;
              return (
                <button key={rotulo} type="button" aria-pressed={ativo}
                        onClick={() => setForm((f) => ({ ...f, data: valor }))}
                        className={`rounded-md border px-3 py-1.5 text-xs transition focus-visible:outline-none
                                    focus-visible:ring-2 focus-visible:ring-sandro-acento
                                    ${ativo
                                      ? "border-sandro-acento bg-sandro-acento font-bold text-sandro-fundo"
                                      : "border-sandro-borda/40 text-sandro-label hover:text-white"}`}>
                  {rotulo}
                </button>
              );
            })}
            <label htmlFor="data-followup" className="sr-only">Data do follow-up</label>
            <input id="data-followup" type="date" required min={hojeISO()} value={form.data}
                   onChange={alterar("data")} className={`${classeEntrada} w-44`} />
          </div>
          <p className="mt-1 text-xs text-sandro-label">{formatarData(form.data)}</p>
        </fieldset>

        {doCliente.length > 0 && (
          <Campo rotulo="Oportunidade relacionada (opcional)">
            {(p) => (
              <select {...p} value={form.oportunidadeId} onChange={alterar("oportunidadeId")} className={classeEntrada}>
                <option value="">Nenhuma</option>
                {doCliente.map((o) => <option key={o.id} value={o.id}>{o.titulo} ({o.etapa})</option>)}
              </select>
            )}
          </Campo>
        )}

        <Campo rotulo="Observações (opcional)">
          {(p) => (
            <textarea {...p} rows={2} maxLength={2000} value={form.descricao} onChange={alterar("descricao")}
                      className={classeEntrada} />
          )}
        </Campo>

        {erro && <p role="alert" className="rounded-lg bg-rose-950/80 px-3 py-2 text-sm text-rose-300">{erro}</p>}

        <div className="flex justify-end gap-3 pt-1">
          <Botao variante="fantasma" onClick={onFechar} disabled={enviando}>Cancelar</Botao>
          <Botao variante="primario" type="submit" carregando={enviando} textoCarregando="Agendando...">
            Agendar follow-up
          </Botao>
        </div>
      </form>
    </Modal>
  );
}
