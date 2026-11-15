import { useId, useState } from "react";

// Raio que dá circunferência = 100: o tamanho de cada fatia vira "percentual"
const RAIO = 15.9155;
const ESPACO = 0.8; // vão entre fatias, em pontos percentuais

/**
 * Donut em SVG puro. fatias = [{ rotulo, valor, cor, href?, descricao? }].
 * centro = { valor, rotulo } exibido no meio. Para leitor de tela, uma tabela
 * equivalente (sr-only) descreve as fatias com valor e percentual.
 */
export default function GraficoDonut({ titulo, fatias, centro, formatar = String }) {
  const idTabela = useId();
  const [ativa, setAtiva] = useState(null);
  const total = fatias.reduce((s, f) => s + Math.max(f.valor, 0), 0);
  const comValor = fatias.filter((f) => f.valor > 0);
  const espaco = comValor.length > 1 ? ESPACO : 0;

  let acumulado = 0;
  const arcos = fatias.map((f, i) => {
    const pct = total ? (Math.max(f.valor, 0) / total) * 100 : 0;
    const inicio = acumulado;
    acumulado += pct;
    return { ...f, indice: i, pct, inicio };
  });

  const percentual = (pct) => `${pct.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
  const destaque = ativa === null ? null : arcos[ativa];

  return (
    <figure className="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
      <div className="relative h-44 w-44 shrink-0" aria-hidden="true">
        <svg viewBox="0 0 42 42" className="h-full w-full -rotate-90">
          <circle cx="21" cy="21" r={RAIO} fill="none" stroke="currentColor" strokeWidth="5"
                  className="text-sandro-suporte/30" />
          {arcos.filter((a) => a.pct > 0).map((a) => {
            const tamanho = Math.max(a.pct - espaco, 0.3);
            const apagada = ativa !== null && ativa !== a.indice;
            return (
              <circle
                key={a.rotulo}
                cx="21" cy="21" r={RAIO} fill="none"
                stroke={a.cor}
                strokeWidth={ativa === a.indice ? 6.5 : 5}
                strokeDasharray={`${tamanho} ${100 - tamanho}`}
                strokeDashoffset={-a.inicio}
                className="transition-all duration-200"
                style={{ opacity: apagada ? 0.35 : 1 }}
                onMouseEnter={() => setAtiva(a.indice)}
                onMouseLeave={() => setAtiva(null)}
              />
            );
          })}
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-lg font-semibold tabular-nums text-white">
            {destaque ? percentual(destaque.pct) : centro.valor}
          </span>
          <span className="max-w-24 text-[0.65rem] leading-tight text-sandro-label">
            {destaque ? destaque.rotulo : centro.rotulo}
          </span>
        </div>
      </div>

      <ul className="w-full space-y-2" onMouseLeave={() => setAtiva(null)}>
        {arcos.map((a) => {
          const conteudo = (
            <>
              <span aria-hidden="true" className="mt-1 h-3 w-3 shrink-0 rounded-sm" style={{ background: a.cor }} />
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline justify-between gap-2">
                  <span className="truncate text-sm text-white">{a.rotulo}</span>
                  <span className="text-xs tabular-nums text-sandro-label">{percentual(a.pct)}</span>
                </span>
                <span className="block text-sm font-semibold tabular-nums text-slate-200">{formatar(a.valor)}</span>
                {a.descricao && <span className="block text-xs text-sandro-label">{a.descricao}</span>}
              </span>
            </>
          );
          const eventos = {
            onMouseEnter: () => setAtiva(a.indice),
            onFocus: () => setAtiva(a.indice),
            onBlur: () => setAtiva(null),
          };
          return (
            <li key={a.rotulo}>
              {a.href ? (
                <a href={a.href} {...eventos}
                   aria-label={`${a.rotulo}: ${formatar(a.valor)}, ${percentual(a.pct)}. Ver detalhes`}
                   className="flex gap-3 rounded-lg px-2 py-1.5 transition hover:bg-sandro-suporte/30
                              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sandro-acento">
                  {conteudo}
                </a>
              ) : (
                <div {...eventos} className="flex gap-3 px-2 py-1.5">{conteudo}</div>
              )}
            </li>
          );
        })}
      </ul>

      <table id={idTabela} className="sr-only">
        <caption>{titulo}</caption>
        <tbody>
          {arcos.map((a) => (
            <tr key={a.rotulo}>
              <th scope="row">{a.rotulo}</th>
              <td>{formatar(a.valor)}</td>
              <td>{percentual(a.pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
