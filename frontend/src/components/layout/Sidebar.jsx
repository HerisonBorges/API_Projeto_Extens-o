import { ROTAS, podeAcessar } from "../../rotas.js";
import Logo from "../marca/Logo.jsx";

const ICONES = {
  dashboard: "◧",
  clientes: "◉",
  funil: "▥",
  followups: "◷",
  relatorios: "▤",
  configuracoes: "⚙",
};

export default function Sidebar({ usuario, ativa, onSair, onAlterarSenha }) {
  const itens = Object.keys(ROTAS).filter((pagina) => podeAcessar(pagina, usuario.perfil));

  return (
    <aside
      className="flex w-full shrink-0 flex-col border-b border-sandro-borda/25 bg-sandro-painel/40
                 md:sticky md:top-0 md:h-screen md:w-64 md:border-r md:border-b-0"
    >
      <div className="px-5 py-6">
        <Logo comSlogan />
      </div>

      <nav aria-label="Navegação principal" className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:pb-0">
        {itens.map((pagina) => {
          const atual = pagina === ativa;
          return (
            <a
              key={pagina}
              href={`#/${pagina}`}
              aria-current={atual ? "page" : undefined}
              className={`flex shrink-0 items-center gap-3 rounded-lg px-4 py-2.5 text-sm transition
                          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sandro-acento
                          ${atual
                            ? "bg-sandro-acento font-bold text-sandro-fundo shadow-md shadow-sandro-acento/15"
                            : "text-slate-200 hover:bg-sandro-suporte/40"}`}
            >
              <span aria-hidden="true" className="w-4 text-center">{ICONES[pagina]}</span>
              {ROTAS[pagina].titulo}
            </a>
          );
        })}
      </nav>

      <div className="mt-auto hidden border-t border-sandro-borda/25 px-5 py-5 md:block">
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sandro-azul/60
                       text-sm font-bold text-white"
          >
            {usuario.nome.trim().charAt(0).toUpperCase()}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm text-white">{usuario.nome}</p>
            <p className="text-xs text-sandro-label">{usuario.perfil}</p>
          </div>
        </div>
        <div className="mt-4 flex gap-4">
          <button
            type="button"
            onClick={onAlterarSenha}
            className="text-xs text-sandro-label underline-offset-4 hover:text-white hover:underline
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sandro-acento"
          >
            Alterar minha senha
          </button>
          <button
            type="button"
            onClick={onSair}
            className="text-xs text-sandro-label underline-offset-4 hover:text-white hover:underline
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sandro-acento"
          >
            Sair
          </button>
        </div>
      </div>
    </aside>
  );
}
