const TONS = {
  permitido: "bg-teal-950/80 text-teal-400 ring-teal-500/30",
  bloqueado: "bg-rose-950/80 text-rose-400 ring-rose-500/30",
  pendente: "bg-amber-950/80 text-amber-300 ring-amber-500/30",
  neutro: "bg-kindra-suporte/40 text-kindra-label ring-kindra-suporte/60",
};

// O texto sempre acompanha a cor: o status não depende só da percepção de cor
export default function StatusBadge({ tom = "neutro", icone, children }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs
                  font-medium ring-1 ring-inset ${TONS[tom]}`}
    >
      {icone && <span aria-hidden="true">{icone}</span>}
      {children}
    </span>
  );
}
