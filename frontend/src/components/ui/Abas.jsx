/** Filtro segmentado (Todos / Ativos / ...). Usa aria-pressed: é filtro, não navegação. */
export default function Abas({ rotulo, opcoes, valor, onChange }) {
  return (
    <div
      role="group"
      aria-label={rotulo}
      className="inline-flex flex-wrap gap-1 rounded-lg border border-sandro-borda/30 bg-sandro-fundo/60 p-1"
    >
      {opcoes.map((opcao) => {
        const ativa = opcao.valor === valor;
        return (
          <button
            key={opcao.valor}
            type="button"
            aria-pressed={ativa}
            onClick={() => onChange(opcao.valor)}
            className={`rounded-md px-3 py-1.5 text-xs transition focus-visible:outline-none
                        focus-visible:ring-2 focus-visible:ring-sandro-acento
                        ${ativa
                          ? "bg-sandro-acento font-bold text-sandro-fundo"
                          : "font-medium text-sandro-label hover:text-white"}`}
          >
            {opcao.rotulo}
            {opcao.contagem !== undefined && (
              <span className={`ml-1.5 ${ativa ? "text-sandro-fundo/80" : "text-sandro-label/80"}`}>
                {opcao.contagem}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
