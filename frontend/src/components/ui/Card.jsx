// Painel corporativo: vidro mínimo, borda fina, profundidade escura
export default function Card({ as: Tag = "section", titulo, acao, className = "", children, ...props }) {
  return (
    <Tag
      // Celular: fundo quase opaco, sem backdrop-blur (o desfoque é refeito a cada
      // quadro de rolagem e derruba o fps em aparelhos simples). Tablet+: vidro.
      className={`rounded-xl border border-sandro-borda/25 bg-sandro-painel/90 shadow-sm shadow-black/30
                  md:bg-sandro-painel/70 md:backdrop-blur-sm ${className}`}
      {...props}
    >
      {(titulo || acao) && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-sandro-borda/20 px-5 py-4">
          {titulo && <h2 className="text-sm font-semibold text-white">{titulo}</h2>}
          {acao}
        </div>
      )}
      {children}
    </Tag>
  );
}
