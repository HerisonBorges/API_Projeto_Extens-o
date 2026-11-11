import { useState } from "react";

import { agendarReciclagem } from "../../services/api.js";
import Botao from "../ui/Botao.jsx";
import Campo, { classeEntrada } from "../ui/Campo.jsx";
import Modal from "../ui/Modal.jsx";
import { amanhaISO, formatarMoeda } from "../ui/formatos.js";

const PRESETS_DIAS = [7, 10, 15, 30];

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
  const [dias, setDias] = useState(PRESETS_DIAS[0]);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);

  async function confirmar(evento) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);

    const agendamento = modo === "data" ? { data_agendada: data } : { dias: Number(dias) };

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
          <Campo rotulo="Período">
            {(props) => (
              <select {...props} value={dias} onChange={(e) => setDias(e.target.value)} className={classeEntrada}>
                {PRESETS_DIAS.map((d) => <option key={d} value={d}>{d} dias</option>)}
              </select>
            )}
          </Campo>
        ) : (
          <Campo rotulo="Data">
            {(props) => (
              <input {...props} type="date" required min={amanhaISO()} value={data}
                     onChange={(e) => setData(e.target.value)} className={classeEntrada} />
            )}
          </Campo>
        )}

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
