import { useState } from "react";

import { agendarReciclagem } from "../../services/api.js";
import Botao from "../ui/Botao.jsx";
import Campo, { classeEntrada } from "../ui/Campo.jsx";
import Modal from "../ui/Modal.jsx";
import { amanhaISO, daquiDiasISO, formatarData, formatarMoeda } from "../ui/formatos.js";

const PRESETS_DIAS = [7, 10, 15, 30];
const OUTRO = "outro";
// Mesmos limites da API (routes/oportunidades.py)
const DIAS_MINIMO = 1;
const DIAS_MAXIMO = 365;

function OpcaoModo({ valor, atual, onChange, titulo, descricao }) {
  const selecionado = valor === atual;
  return (
    <label
      className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition
                  ${selecionado
                    ? "border-sandro-acento bg-sandro-acento/10"
                    : "border-sandro-borda/30 hover:border-sandro-borda"}`}
    >
      <input
        type="radio"
        name="modo-reciclagem"
        value={valor}
        checked={selecionado}
        onChange={() => onChange(valor)}
        className="mt-1 accent-sandro-acento"
      />
      <span>
        <span className="block text-sm font-medium text-white">{titulo}</span>
        <span className="block text-xs text-sandro-label">{descricao}</span>
      </span>
    </label>
  );
}

export default function ReciclagemModal({ oportunidade, onFechar, onAgendado }) {
  const [modo, setModo] = useState("periodo");
  const [data, setData] = useState(amanhaISO());
  const [preset, setPreset] = useState(String(PRESETS_DIAS[0]));
  const [diasOutro, setDiasOutro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);

  const customizado = preset === OUTRO;
  const dias = customizado ? Number(diasOutro) : Number(preset);
  const diasValidos = Number.isInteger(dias) && dias >= DIAS_MINIMO && dias <= DIAS_MAXIMO;

  // Prévia em linguagem natural: o cliente vê o dia exato antes de confirmar
  const previa = modo === "data"
    ? (data ? formatarData(data) : null)
    : (diasValidos ? formatarData(daquiDiasISO(dias)) : null);

  async function confirmar(evento) {
    evento.preventDefault();
    setErro(null);
    if (modo === "periodo" && !diasValidos) {
      setErro(`Informe um número inteiro de ${DIAS_MINIMO} a ${DIAS_MAXIMO} dias.`);
      return;
    }
    setEnviando(true);

    const agendamento = modo === "data" ? { data_agendada: data } : { dias };

    try {
      onAgendado(await agendarReciclagem(oportunidade.id, agendamento));
    } catch (e) {
      setErro(e.message);
      setEnviando(false);
    }
  }

  return (
    <Modal
      titulo="Reciclar lead"
      descricao={`${oportunidade.titulo} · ${formatarMoeda(oportunidade.valor)}`}
      onFechar={onFechar}
      bloqueado={enviando}
    >
      <p className="text-xs text-slate-300">
        Na data escolhida, uma nova oportunidade é criada em Prospecção para este cliente.
        A venda atual continua em Fechado e segue contando na receita.
      </p>

      <form onSubmit={confirmar} className="mt-5 space-y-4">
        <fieldset className="space-y-2">
          <legend className="mb-2 text-xs font-medium uppercase tracking-wider text-sandro-label">
            Quando reciclar
          </legend>
          <OpcaoModo valor="periodo" atual={modo} onChange={setModo}
                     titulo="Por período relativo" descricao="Daqui a X dias a partir de agora" />
          <OpcaoModo valor="data" atual={modo} onChange={setModo}
                     titulo="Por data específica" descricao="À meia-noite do dia escolhido" />
        </fieldset>

        {modo === "periodo" ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo rotulo="Período">
              {(props) => (
                <select {...props} value={preset} onChange={(e) => setPreset(e.target.value)} className={classeEntrada}>
                  {PRESETS_DIAS.map((d) => (
                    <option key={d} value={d}>{d} dias{d === 30 ? " (≈ 1 mês)" : ""}</option>
                  ))}
                  <option value={OUTRO}>Outro período…</option>
                </select>
              )}
            </Campo>
            {customizado && (
              <Campo rotulo="Quantos dias" ajuda={`De ${DIAS_MINIMO} a ${DIAS_MAXIMO}.`}>
                {(props) => (
                  <input {...props} type="number" required autoFocus inputMode="numeric"
                         min={DIAS_MINIMO} max={DIAS_MAXIMO} step="1" value={diasOutro}
                         onChange={(e) => setDiasOutro(e.target.value)} className={classeEntrada} />
                )}
              </Campo>
            )}
          </div>
        ) : (
          <Campo rotulo="Data">
            {(props) => (
              <input {...props} type="date" required min={amanhaISO()} value={data}
                     onChange={(e) => setData(e.target.value)} className={classeEntrada} />
            )}
          </Campo>
        )}

        <p role="status" className="rounded-lg border border-sandro-borda/30 bg-sandro-fundo/50 px-3 py-2 text-sm text-slate-200">
          {previa
            ? <>Volta ao funil em <strong className="text-white">{previa}</strong>
                {modo === "data" ? " (a partir da meia-noite)" : ""}. Pode levar até 1 hora para aparecer.</>
            : "Escolha quando o lead deve voltar ao funil."}
        </p>

        {erro && (
          <p role="alert" className="rounded-lg bg-rose-950/80 px-3 py-2 text-sm text-rose-300">{erro}</p>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Botao variante="fantasma" onClick={onFechar} disabled={enviando}>Voltar</Botao>
          <Botao variante="primario" type="submit" carregando={enviando} textoCarregando="Agendando...">
            Confirmar agendamento
          </Botao>
        </div>
      </form>
    </Modal>
  );
}
