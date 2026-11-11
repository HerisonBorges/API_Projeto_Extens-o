import Botao from "./Botao.jsx";

export default function Paginacao({ pagina, totalPaginas, totalItens, onMudar }) {
  if (totalPaginas <= 1) return null;

  return (
    <nav
      aria-label="Paginação"
      className="flex items-center justify-between gap-3 border-t border-sandro-borda/20 px-5 py-3 text-xs text-sandro-label"
    >
      <span>
        Página {pagina} de {totalPaginas} · {totalItens} registros
      </span>
      <div className="flex gap-2">
        <Botao tamanho="sm" disabled={pagina === 1} onClick={() => onMudar(pagina - 1)}>
          ← Anterior
        </Botao>
        <Botao tamanho="sm" disabled={pagina === totalPaginas} onClick={() => onMudar(pagina + 1)}>
          Próxima →
        </Botao>
      </div>
    </nav>
  );
}
