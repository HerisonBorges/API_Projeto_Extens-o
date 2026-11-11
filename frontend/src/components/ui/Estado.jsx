export function Carregando({ texto = "Carregando..." }) {
  return (
    <p role="status" className="px-5 py-8 text-center text-sm text-sandro-label">
      {texto}
    </p>
  );
}

export function Vazio({ children }) {
  return <p className="px-5 py-8 text-center text-sm text-sandro-label">{children}</p>;
}

export function Erro({ mensagem, onTentarDeNovo }) {
  if (!mensagem) return null;
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-500/30
                 bg-rose-950/60 px-4 py-3 text-sm text-rose-200"
    >
      <span>{mensagem}</span>
      {onTentarDeNovo && (
        <button
          type="button"
          onClick={onTentarDeNovo}
          className="text-xs font-semibold underline underline-offset-4 hover:text-white
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sandro-acento"
        >
          Tentar de novo
        </button>
      )}
    </div>
  );
}

export function Aviso({ mensagem }) {
  return (
    <p role="status" aria-live="polite" className="min-h-5 text-sm text-teal-400">
      {mensagem}
    </p>
  );
}
