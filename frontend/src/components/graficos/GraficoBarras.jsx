import { useId } from "react";

const CORES = {
  // Transição sutil ciano -> azuis da marca
  azul: "bg-linear-to-t from-sandro-azul to-sandro-azul-claro",
  ciano: "bg-linear-to-t from-sandro-azul-claro to-sandro-acento",
};

/**
 * Barras verticais em HTML/CSS (sem biblioteca). Para leitores de tela,
 * o gráfico é descrito por uma tabela equivalente (sr-only).
 */
export default function GraficoBarras({ titulo, dados, formatar = String, cor = "azul", altura = "h-48" }) {
  const idTabela = useId();
  const maximo = Math.max(...dados.map((d) => d.valor), 0);

  return (
    <figure>
      <div className={`flex ${altura} items-end gap-2`} aria-hidden="true">
        {dados.map((d) => {
          const pct = maximo ? Math.max((d.valor / maximo) * 100, d.valor > 0 ? 3 : 0) : 0;
          return (
            <div key={d.rotulo} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1">
              <span className="truncate text-[0.65rem] tabular-nums text-sandro-label">
                {d.valor > 0 ? formatar(d.valor) : ""}
              </span>
              <div
                title={`${d.rotulo}: ${formatar(d.valor)}`}
                className={`w-full max-w-12 rounded-t ${d.valor > 0 ? CORES[cor] : "bg-sandro-suporte/30"}`}
                style={{ height: `${pct || 2}%` }}
              />
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex gap-2" aria-hidden="true">
        {dados.map((d) => (
          <span key={d.rotulo} className="min-w-0 flex-1 truncate text-center text-[0.65rem] text-sandro-label">
            {d.rotulo}
          </span>
        ))}
      </div>

      <table id={idTabela} className="sr-only">
        <caption>{titulo}</caption>
        <tbody>
          {dados.map((d) => (
            <tr key={d.rotulo}>
              <th scope="row">{d.rotulo}</th>
              <td>{formatar(d.valor)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
