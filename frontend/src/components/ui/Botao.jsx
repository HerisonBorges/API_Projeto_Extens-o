const VARIANTES = {
  // Texto #05161A sobre #0F969C: 5,16:1 (WCAG AA)
  primario:
    "bg-sandro-acento font-bold text-sandro-fundo shadow-md shadow-sandro-acento/15 hover:brightness-110",
  contorno:
    "border border-sandro-acento/60 font-medium text-sandro-acento hover:bg-sandro-acento hover:text-sandro-fundo",
  secundario:
    "border border-sandro-borda/50 font-medium text-slate-200 hover:bg-sandro-suporte/40",
  perigo: "border border-rose-500/40 font-medium text-rose-300 hover:bg-rose-950/60",
  fantasma: "font-medium text-sandro-label hover:text-white",
};

const TAMANHOS = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
};

export default function Botao({
  variante = "secundario",
  tamanho = "md",
  carregando = false,
  textoCarregando,
  className = "",
  children,
  disabled,
  type = "button",
  ...props
}) {
  return (
    <button
      type={type}
      disabled={disabled || carregando}
      aria-busy={carregando || undefined}
      className={`inline-flex items-center justify-center gap-2 rounded-lg transition
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sandro-acento
                  focus-visible:ring-offset-2 focus-visible:ring-offset-sandro-fundo
                  disabled:cursor-not-allowed disabled:opacity-50
                  ${carregando ? "cursor-wait" : ""} ${VARIANTES[variante]} ${TAMANHOS[tamanho]} ${className}`}
      {...props}
    >
      {carregando ? textoCarregando ?? children : children}
    </button>
  );
}
