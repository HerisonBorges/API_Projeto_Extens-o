import { useId } from "react";

import Campo, { classeEntrada } from "../ui/Campo.jsx";
import { DIAS_SEMANA, descreverRecorrencia, formatarData, proximaOcorrenciaISO } from "../ui/formatos.js";

const FREQUENCIAS = [
  { valor: "semanal", rotulo: "Semanal", ajuda: "Ex.: toda segunda" },
  { valor: "mensal", rotulo: "Mensal", ajuda: "Ex.: todo dia 5" },
];

const DIAS_MES = Array.from({ length: 31 }, (_, i) => i + 1);

/** Frequência (semanal/mensal) + dia, com a prévia da próxima data. */
export default function CamposFrequencia({ valor, onChange, aPartirDe }) {
  const nome = useId();
  const definir = (campos) => onChange({ ...valor, ...campos });

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <fieldset className="sm:col-span-2">
        <legend className="mb-2 text-xs font-medium text-sandro-label">Frequência</legend>
        <div className="grid grid-cols-2 gap-2">
          {FREQUENCIAS.map((f) => (
            <label key={f.valor}
                   className={`flex cursor-pointer flex-col justify-center rounded-lg border px-3 py-2 text-sm transition
                               has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-sandro-acento
                               ${valor.frequencia === f.valor
                                 ? "border-sandro-acento bg-sandro-acento/10 text-white"
                                 : "border-sandro-borda/40 text-sandro-label hover:text-white"}`}>
              <input type="radio" name={nome} value={f.valor} checked={valor.frequencia === f.valor}
                     onChange={() => definir({ frequencia: f.valor })} className="sr-only" />
              <span className="font-semibold">{f.rotulo}</span>
              <span className="text-xs text-sandro-label">{f.ajuda}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {valor.frequencia === "semanal" ? (
        <Campo rotulo="Dia da semana" className="sm:col-span-2">
          {(p) => (
            <select {...p} value={valor.dia_semana} onChange={(e) => definir({ dia_semana: Number(e.target.value) })}
                    className={classeEntrada}>
              {DIAS_SEMANA.map((d) => <option key={d.valor} value={d.valor}>{d.rotulo}</option>)}
            </select>
          )}
        </Campo>
      ) : (
        <Campo rotulo="Dia do mês" className="sm:col-span-2"
               ajuda={valor.dia_mes > 28 ? "Nos meses mais curtos, vale o último dia do mês." : undefined}>
          {(p) => (
            <select {...p} value={valor.dia_mes} onChange={(e) => definir({ dia_mes: Number(e.target.value) })}
                    className={classeEntrada}>
              {DIAS_MES.map((d) => <option key={d} value={d}>Dia {d}</option>)}
            </select>
          )}
        </Campo>
      )}

      <p className="rounded-lg border border-sandro-borda/25 bg-sandro-fundo/50 px-3 py-2 text-xs text-sandro-label sm:col-span-2">
        <span className="font-semibold text-white">{descreverRecorrencia(valor)}</span>
        {" · "}próxima em {formatarData(proximaOcorrenciaISO(valor, aPartirDe))}
      </p>
    </div>
  );
}

export const FREQUENCIA_PADRAO = { frequencia: "mensal", dia_semana: 1, dia_mes: 5 };

/** Corpo da API: só o dia que vale para a frequência escolhida. */
export function corpoFrequencia(valor) {
  return valor.frequencia === "semanal"
    ? { frequencia: "semanal", dia_semana: Number(valor.dia_semana) }
    : { frequencia: "mensal", dia_mes: Number(valor.dia_mes) };
}
