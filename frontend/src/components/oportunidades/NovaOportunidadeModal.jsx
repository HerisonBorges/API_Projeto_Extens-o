import { useEffect, useState } from "react";

import { criarOportunidade, listarClientes } from "../../services/api.js";
import Botao from "../ui/Botao.jsx";
import Campo, { classeEntrada } from "../ui/Campo.jsx";
import Modal from "../ui/Modal.jsx";
import { ETAPAS, ETAPA_FINAL, descreverRecorrencia } from "../ui/formatos.js";
import CamposFrequencia, { FREQUENCIA_PADRAO, corpoFrequencia } from "../recorrencias/CamposFrequencia.jsx";

// Começa no funil: abrir direto em "Fechado" seria registrar venda, não oportunidade
const ETAPAS_INICIAIS = ETAPAS.filter((e) => e !== ETAPA_FINAL);

/**
 * Nova oportunidade para um cliente que JÁ existe.
 * - cliente: fixa o cliente (detalhe do cliente). Sem ele, escolhe na lista (Kanban).
 */
export default function NovaOportunidadeModal({ cliente = null, onFechar, onCriada }) {
  const [clientes, setClientes] = useState(cliente ? [cliente] : null);
  const [form, setForm] = useState({
    clienteId: cliente ? String(cliente.id) : "",
    titulo: "",
    valor: "",
    etapa: ETAPAS_INICIAIS[0],
  });
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);
  const [repetir, setRepetir] = useState(false);
  const [frequencia, setFrequencia] = useState(FREQUENCIA_PADRAO);
  // A oportunidade de hoje é esta: a primeira repetição conta a partir de amanhã
  const [amanha] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d;
  });

  const alterar = (campo) => (e) => setForm((f) => ({ ...f, [campo]: e.target.value }));

  useEffect(() => {
    if (cliente) return;
    listarClientes()
      .then((lista) => setClientes(lista.filter((c) => c.status !== "Inativo")))
      .catch((e) => setErro(e.message));
  }, [cliente]);

  async function salvar(e) {
    e.preventDefault();
    setErro(null);
    if (!form.clienteId) return setErro("Escolha o cliente.");
    if (!form.titulo.trim()) return setErro("Dê um nome à oportunidade.");
    const valor = form.valor === "" ? 0 : Number(form.valor);
    if (!Number.isFinite(valor) || valor < 0) return setErro("Valor inválido.");

    setEnviando(true);
    try {
      const r = await criarOportunidade({
        cliente_id: Number(form.clienteId),
        titulo: form.titulo.trim(),
        valor,
        etapa: form.etapa,
        ...(repetir && { recorrencia: corpoFrequencia(frequencia) }),
      });
      onCriada({
        id: r.oportunidade_id,
        titulo: form.titulo.trim(),
        etapa: form.etapa,
        repeticao: repetir ? descreverRecorrencia(frequencia).toLowerCase() : null,
      });
    } catch (erroApi) {
      setErro(erroApi.message);
      setEnviando(false);
    }
  }

  return (
    <Modal
      titulo="Nova oportunidade"
      descricao={cliente ? `Novo negócio com ${cliente.nome}` : "Novo negócio com um cliente já cadastrado."}
      onFechar={onFechar}
      bloqueado={enviando}
      largura="max-w-lg"
    >
      <form onSubmit={salvar} className="grid gap-4 sm:grid-cols-2">
        {!cliente && (
          <Campo rotulo="Cliente *" className="sm:col-span-2"
                 ajuda="Cliente novo? Use o botão + Novo Lead no topo da tela.">
            {(p) => (
              <select {...p} required value={form.clienteId} onChange={alterar("clienteId")}
                      disabled={!clientes} className={classeEntrada}>
                <option value="">{clientes ? "Escolha o cliente" : "Carregando clientes..."}</option>
                {(clientes ?? []).map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
              </select>
            )}
          </Campo>
        )}

        <Campo rotulo="Nome da oportunidade *" className="sm:col-span-2">
          {(p) => (
            <input {...p} required maxLength={150} value={form.titulo} onChange={alterar("titulo")}
                   placeholder="Ex.: Reposição de estoque de Natal" className={classeEntrada} />
          )}
        </Campo>

        <Campo rotulo="Valor estimado (R$)">
          {(p) => (
            <input {...p} type="number" min="0" max="9999999999.99" step="0.01" inputMode="decimal"
                   value={form.valor} onChange={alterar("valor")} className={classeEntrada} />
          )}
        </Campo>

        <Campo rotulo="Etapa inicial">
          {(p) => (
            <select {...p} value={form.etapa} onChange={alterar("etapa")} className={classeEntrada}>
              {ETAPAS_INICIAIS.map((etapa) => <option key={etapa} value={etapa}>{etapa}</option>)}
            </select>
          )}
        </Campo>

        <div className="space-y-3 rounded-lg border border-sandro-borda/25 p-3 sm:col-span-2">
          <label className="flex min-h-12 cursor-pointer items-center gap-3 text-sm text-white">
            <input type="checkbox" checked={repetir} onChange={(e) => setRepetir(e.target.checked)}
                   className="h-5 w-5 shrink-0 accent-sandro-acento" />
            <span>
              Repetir automaticamente
              <span className="block text-xs text-sandro-label">
                Ex.: cliente que compra toda semana. Um card novo entra em Prospecção em cada data.
              </span>
            </span>
          </label>
          {repetir && <CamposFrequencia valor={frequencia} onChange={setFrequencia} aPartirDe={amanha} />}
        </div>

        {erro && (
          <p role="alert" className="rounded-lg bg-rose-950/80 px-3 py-2 text-sm text-rose-300 sm:col-span-2">{erro}</p>
        )}

        <div className="flex flex-col-reverse gap-3 pt-1 sm:col-span-2 sm:flex-row sm:justify-end">
          <Botao variante="fantasma" onClick={onFechar} disabled={enviando}>Cancelar</Botao>
          <Botao variante="primario" type="submit" carregando={enviando} textoCarregando="Criando...">
            Criar oportunidade
          </Botao>
        </div>
      </form>
    </Modal>
  );
}
