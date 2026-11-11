import { useEffect, useId, useRef, useState } from "react";

import { agendarReciclagem } from "../../services/api.js";
import { amanhaISO, formatarMoeda } from "../ui/formatos.js";

const PRESETS_DIAS = [7, 15, 30];

function OpcaoModo({ valor, atual, onChange, titulo, descricao, inputRef }) {
  const selecionado = valor === atual;
  return (
    <label
      className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition
                  ${selecionado
                    ? "border-kindra-acento bg-kindra-acento/10 shadow-lg shadow-kindra-acento/20"
                    : "border-kindra-borda/30 hover:border-kindra-borda"}`}
    >
      <input
        ref={inputRef}
        type="radio"
        name="modo-reciclagem"
        value={valor}
        checked={selecionado}
        onChange={() => onChange(valor)}
        className="mt-1 accent-kindra-acento"
      />
      <span>
        <span className="block text-sm font-medium text-white">{titulo}</span>
        <span className="block text-xs text-kindra-label">{descricao}</span>
      </span>
    </label>
  );
}

export default function ReciclagemModal({ oportunidade, onFechar, onAgendado }) {
  const [modo, setModo] = useState("periodo");
  const [data, setData] = useState(amanhaISO());
  const [dias, setDias] = useState(PRESETS_DIAS[0]);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);

  const tituloId = useId();
  const primeiroCampo = useRef(null);

  // Foco inicial uma única vez, ao abrir; ao fechar, volta para quem abriu
  useEffect(() => {
    const anterior = document.activeElement;
    primeiroCampo.current?.focus();
    return () => anterior?.focus?.();
  }, []);

  // Esc fecha (exceto durante o envio). Ref evita reinscrever a cada render.
  const fecharRef = useRef(onFechar);
  fecharRef.current = enviando ? () => {} : onFechar;

  const dialogo = useRef(null);

  useEffect(() => {
    const aoTeclar = (e) => {
      if (e.key === "Escape") {
        fecharRef.current();
        return;
      }

      // Prende o Tab dentro do diálogo: do último volta ao primeiro e vice-versa
      if (e.key !== "Tab" || !dialogo.current) return;

      const focaveis = [...dialogo.current.querySelectorAll(
        'button:not([disabled]), input:not([disabled]), select:not([disabled])'
      )].filter((el) => !(el.type === "radio" && !el.checked));

      if (focaveis.length === 0) return;

      const primeiro = focaveis[0];
      const ultimo = focaveis[focaveis.length - 1];
      const foraDoDialogo = !dialogo.current.contains(document.activeElement);

      if (e.shiftKey && (document.activeElement === primeiro || foraDoDialogo)) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && (document.activeElement === ultimo || foraDoDialogo)) {
        e.preventDefault();
        primeiro.focus();
      }
    };

    document.addEventListener("keydown", aoTeclar);
    return () => document.removeEventListener("keydown", aoTeclar);
  }, []);

  // Clique no fundo escuro fecha; cliques dentro do painel não
  const aoClicarNoFundo = (e) => {
    if (e.target === e.currentTarget) fecharRef.current();
  };

  async function confirmar(evento) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);

    const agendamento = modo === "data" ? { data_agendada: data } : { dias: Number(dias) };

    try {
      const resposta = await agendarReciclagem(oportunidade.id, agendamento);
      onAgendado(resposta);
    } catch (e) {
      setErro(e.message);
      setEnviando(false);
    }
  }

  return (
    <div
      onMouseDown={aoClicarNoFundo}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
    >
      <div
        ref={dialogo}
        role="dialog"
        aria-modal="true"
        aria-labelledby={tituloId}
        className="w-full max-w-md rounded-2xl border border-kindra-borda/40 bg-kindra-painel/80 p-6
                   shadow-2xl shadow-black/40 backdrop-blur-xl"
      >
        <h2 id={tituloId} className="text-lg font-semibold text-white">Reciclar lead</h2>
        <p className="mt-1 text-sm text-kindra-label">
          {oportunidade.titulo} · {formatarMoeda(oportunidade.valor)}
        </p>
        <p className="mt-3 text-xs text-slate-300">
          Na data escolhida, uma nova oportunidade é criada em Prospecção para este cliente.
          A venda atual continua em Fechado e segue contando na receita.
        </p>

        <form onSubmit={confirmar} className="mt-5 space-y-4">
          <fieldset className="space-y-2">
            <legend className="mb-2 text-xs font-medium uppercase tracking-wider text-kindra-label">
              Quando reciclar
            </legend>
            <OpcaoModo
              valor="periodo"
              atual={modo}
              onChange={setModo}
              inputRef={primeiroCampo}
              titulo="Por período relativo"
              descricao="Daqui a X dias a partir de agora"
            />
            <OpcaoModo
              valor="data"
              atual={modo}
              onChange={setModo}
              titulo="Por data específica"
              descricao="À meia-noite do dia escolhido"
            />
          </fieldset>

          {modo === "periodo" ? (
            <div>
              <label htmlFor="dias-reciclagem" className="mb-1 block text-sm text-slate-200">
                Período
              </label>
              <select
                id="dias-reciclagem"
                value={dias}
                onChange={(e) => setDias(e.target.value)}
                className="w-full rounded-lg border border-kindra-borda/40 bg-kindra-fundo/80 px-3 py-2
                           text-white focus:border-kindra-acento focus:outline-none focus:ring-2
                           focus:ring-kindra-acento/40"
              >
                {PRESETS_DIAS.map((d) => (
                  <option key={d} value={d}>{d} dias</option>
                ))}
              </select>
            </div>
          ) : (
            <div>
              <label htmlFor="data-reciclagem" className="mb-1 block text-sm text-slate-200">
                Data
              </label>
              <input
                id="data-reciclagem"
                type="date"
                required
                min={amanhaISO()}
                value={data}
                onChange={(e) => setData(e.target.value)}
                className="w-full rounded-lg border border-kindra-borda/40 bg-kindra-fundo/80 px-3 py-2
                           text-white focus:border-kindra-acento focus:outline-none focus:ring-2
                           focus:ring-kindra-acento/40"
              />
            </div>
          )}

          {erro && (
            <p role="alert" className="rounded-lg bg-rose-950/80 px-3 py-2 text-sm text-rose-300">
              {erro}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onFechar}
              disabled={enviando}
              className="rounded-lg px-4 py-2 text-sm text-kindra-label hover:text-white
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-kindra-acento"
            >
              Voltar
            </button>
            <button
              type="submit"
              disabled={enviando}
              aria-busy={enviando}
              className="rounded-lg bg-kindra-acento px-4 py-2 text-sm font-bold text-kindra-fundo shadow-lg
                         shadow-kindra-acento/20 transition hover:brightness-110
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70
                         disabled:cursor-wait disabled:opacity-60"
            >
              {enviando ? "Agendando..." : "Confirmar agendamento"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
