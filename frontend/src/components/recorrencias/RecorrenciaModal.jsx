import { useId, useState } from "react";

import { alterarRecorrencia, criarRecorrencia } from "../../services/api.js";
import Botao from "../ui/Botao.jsx";
import Campo, { classeEntrada } from "../ui/Campo.jsx";
import Modal from "../ui/Modal.jsx";
import CamposFrequencia, { FREQUENCIA_PADRAO, corpoFrequencia } from "./CamposFrequencia.jsx";

const TIPOS = [
  { valor: "lembrete", rotulo: "Lembrete", ajuda: "Cria um follow-up na data" },
  { valor: "oportunidade", rotulo: "Oportunidade", ajuda: "Cria um card no funil, com valor" },
];

/**
 * Cria (recorrencia = null) ou edita uma regra do cliente.
 * Ex.: "Compra semanal de pães, toda segunda, R$ 350" ou "Fechamento todo dia 5".
 */
export default function RecorrenciaModal({ cliente, recorrencia = null, onFechar, onSalva }) {
  const nomeTipo = useId();
  const [form, setForm] = useState(() => ({
    tipo: recorrencia?.tipo ?? "lembrete",
    titulo: recorrencia?.titulo ?? "",
    valor: recorrencia?.valor ?? "",
    notas: recorrencia?.notas ?? "",
  }));
  const [frequencia, setFrequencia] = useState(() => (recorrencia
    ? { frequencia: recorrencia.frequencia, dia_semana: recorrencia.dia_semana ?? 1, dia_mes: recorrencia.dia_mes ?? 5 }
    : FREQUENCIA_PADRAO));
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);

  const alterar = (campo) => (e) => setForm((f) => ({ ...f, [campo]: e.target.value }));

  async function salvar(e) {
    e.preventDefault();
    setErro(null);
    if (!form.titulo.trim()) return setErro("Dê um título à recorrência.");
    const valor = form.tipo === "oportunidade" && form.valor !== "" ? Number(form.valor) : null;
    if (valor !== null && (!Number.isFinite(valor) || valor < 0)) return setErro("Valor inválido.");

    const corpo = {
      tipo: form.tipo,
      titulo: form.titulo.trim(),
      valor,
      notas: form.notas.trim() || null,
      ...corpoFrequencia(frequencia),
    };
    setEnviando(true);
    try {
      const r = recorrencia
        ? await alterarRecorrencia(recorrencia.id, corpo)
        : await criarRecorrencia({ ...corpo, cliente_id: cliente.id });
      onSalva(r.recorrencia);
    } catch (erroApi) {
      setErro(erroApi.message);
      setEnviando(false);
    }
  }

  return (
    <Modal
      titulo={recorrencia ? "Editar recorrência" : "Nova recorrência"}
      descricao={`Repete automaticamente para ${cliente.nome}.`}
      onFechar={onFechar}
      bloqueado={enviando}
      largura="max-w-lg"
    >
      <form onSubmit={salvar} className="space-y-4">
        <fieldset>
          <legend className="mb-2 text-xs font-medium text-sandro-label">O que acontece na data</legend>
          <div className="grid grid-cols-2 gap-2">
            {TIPOS.map((t) => (
              <label key={t.valor}
                     className={`flex cursor-pointer flex-col justify-center rounded-lg border px-3 py-2 text-sm transition
                                 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-sandro-acento
                                 ${form.tipo === t.valor
                                   ? "border-sandro-acento bg-sandro-acento/10 text-white"
                                   : "border-sandro-borda/40 text-sandro-label hover:text-white"}`}>
                <input type="radio" name={nomeTipo} value={t.valor} checked={form.tipo === t.valor}
                       onChange={alterar("tipo")} className="sr-only" />
                <span className="font-semibold">{t.rotulo}</span>
                <span className="text-xs text-sandro-label">{t.ajuda}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="grid gap-4 sm:grid-cols-3">
          <Campo rotulo="Título *" className={form.tipo === "oportunidade" ? "sm:col-span-2" : "sm:col-span-3"}>
            {(p) => (
              <input {...p} required maxLength={150} value={form.titulo} onChange={alterar("titulo")}
                     placeholder={form.tipo === "oportunidade" ? "Ex.: Compra semanal de pães" : "Ex.: Fechamento do mês"}
                     className={classeEntrada} />
            )}
          </Campo>
          {form.tipo === "oportunidade" && (
            <Campo rotulo="Valor (R$)">
              {(p) => (
                <input {...p} type="number" min="0" max="9999999999.99" step="0.01" inputMode="decimal"
                       value={form.valor} onChange={alterar("valor")} className={classeEntrada} />
              )}
            </Campo>
          )}
        </div>

        <CamposFrequencia valor={frequencia} onChange={setFrequencia} />

        <Campo rotulo="Notas de compra" ajuda="Aparecem no follow-up gerado. Até 2000 caracteres.">
          {(p) => (
            <textarea {...p} rows={2} maxLength={2000} value={form.notas} onChange={alterar("notas")}
                      placeholder="Ex.: 20 kg de farinha, entregar até 8h" className={classeEntrada} />
          )}
        </Campo>

        {erro && <p role="alert" className="rounded-lg bg-rose-950/80 px-3 py-2 text-sm text-rose-300">{erro}</p>}

        <div className="flex flex-col-reverse gap-3 pt-1 sm:flex-row sm:justify-end">
          <Botao variante="fantasma" onClick={onFechar} disabled={enviando}>Cancelar</Botao>
          <Botao variante="primario" type="submit" carregando={enviando} textoCarregando="Salvando...">
            {recorrencia ? "Salvar alterações" : "Criar recorrência"}
          </Botao>
        </div>
      </form>
    </Modal>
  );
}
