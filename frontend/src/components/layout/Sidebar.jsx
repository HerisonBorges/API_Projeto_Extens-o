import { useEffect, useState } from "react";

import { ROTAS, podeAcessar } from "../../rotas.js";
import Logo, { LogoSimbolo } from "../marca/Logo.jsx";

const ICONES = {
  dashboard: "◧",
  clientes: "◉",
  funil: "▥",
  followups: "◷",
  relatorios: "▤",
  configuracoes: "⚙",
};

// Só preferência de interface (nenhum dado pessoal): pode ficar no localStorage
const CHAVE_PREFERENCIA = "sandro.sidebar.recolhida";

function lerPreferencia() {
  try {
    return window.localStorage.getItem(CHAVE_PREFERENCIA) === "1";
  } catch {
    return false;
  }
}

const focoVisivel = "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sandro-acento";

export default function Sidebar({ usuario, ativa, onSair, onAlterarSenha }) {
  const itens = Object.keys(ROTAS).filter((pagina) => podeAcessar(pagina, usuario.perfil));
  const [recolhida, setRecolhida] = useState(lerPreferencia);

  useEffect(() => {
    try {
      window.localStorage.setItem(CHAVE_PREFERENCIA, recolhida ? "1" : "0");
    } catch {
      // modo privado sem storage: só não lembra a preferência
    }
  }, [recolhida]);

  // Recolher só existe a partir do tablet (md); no celular a sidebar é a barra do topo
  const md = (classeAberta, classeRecolhida) => (recolhida ? classeRecolhida : classeAberta);
  const iniciais = usuario.nome.trim().charAt(0).toUpperCase();

  return (
    <aside
      id="menu-principal"
      aria-label="Menu"
      className={`flex w-full shrink-0 flex-col border-b border-sandro-borda/25 bg-sandro-painel/40
                  transition-[width] duration-200 md:sticky md:top-0 md:h-screen md:border-r md:border-b-0
                  ${md("md:w-64", "md:w-20")}`}
    >
      {/* Marca: sempre visível. Aberta = logo completo; recolhida = símbolo do SANDRO */}
      <div className={`relative flex items-center px-5 py-6 ${md("", "md:justify-center md:px-0")}`}>
        <a href="#/dashboard" aria-label="SANDRO CRM, ir para o Dashboard" className={`rounded-lg ${focoVisivel}`}>
          <span className={recolhida ? "md:hidden" : ""}><Logo comSlogan /></span>
          {recolhida && (
            <span className="hidden md:block" title="SANDRO CRM · O poder da conexão">
              <LogoSimbolo className="h-11 w-11" />
            </span>
          )}
        </a>
      </div>

      <div className={`hidden px-3 pb-2 md:flex ${md("justify-end", "justify-center")}`}>
        <button
          type="button"
          onClick={() => setRecolhida((v) => !v)}
          aria-expanded={!recolhida}
          aria-controls="menu-principal"
          aria-label={recolhida ? "Expandir menu" : "Recolher menu"}
          title={recolhida ? "Expandir menu" : "Recolher menu"}
          className={`flex h-8 items-center gap-2 rounded-lg border border-sandro-borda/30 px-2.5 text-xs
                      text-sandro-label transition hover:border-sandro-acento hover:text-white ${focoVisivel}`}
        >
          <span aria-hidden="true" className="text-base leading-none">{recolhida ? "»" : "«"}</span>
          {!recolhida && <span>Recolher</span>}
        </button>
      </div>

      <nav aria-label="Navegação principal" className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:pb-0">
        {itens.map((pagina) => {
          const atual = pagina === ativa;
          const titulo = ROTAS[pagina].titulo;
          return (
            <a
              key={pagina}
              href={`#/${pagina}`}
              aria-current={atual ? "page" : undefined}
              title={recolhida ? titulo : undefined}
              className={`flex shrink-0 items-center gap-3 rounded-lg px-4 py-2.5 text-sm transition ${focoVisivel}
                          ${md("", "md:justify-center md:px-0")}
                          ${atual
                            ? "bg-sandro-acento font-bold text-sandro-fundo shadow-md shadow-sandro-acento/15"
                            : "text-slate-200 hover:bg-sandro-suporte/40"}`}
            >
              <span aria-hidden="true" className={`w-4 text-center ${md("", "md:w-auto md:text-lg")}`}>
                {ICONES[pagina]}
              </span>
              {/* Recolhida: o nome some da tela mas continua para o leitor de tela */}
              <span className={md("", "md:sr-only")}>{titulo}</span>
            </a>
          );
        })}
      </nav>

      <div className={`mt-auto hidden border-t border-sandro-borda/25 py-5 md:block ${md("px-5", "px-2")}`}>
        <div className={`flex items-center gap-3 ${md("", "justify-center")}`}>
          <span
            aria-hidden="true"
            title={recolhida ? `${usuario.nome} · ${usuario.perfil}` : undefined}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sandro-azul/60
                       text-sm font-bold text-white"
          >
            {iniciais}
          </span>
          <div className={`min-w-0 ${md("", "sr-only")}`}>
            <p className="truncate text-sm text-white">{usuario.nome}</p>
            <p className="text-xs text-sandro-label">{usuario.perfil}</p>
          </div>
        </div>

        {recolhida ? (
          <div className="mt-4 flex flex-col items-center gap-2">
            <button type="button" onClick={onAlterarSenha} aria-label="Alterar minha senha" title="Alterar minha senha"
                    className={`rounded-lg px-2 py-1 text-base text-sandro-label hover:text-white ${focoVisivel}`}>
              <span aria-hidden="true">⚿</span>
            </button>
            <button type="button" onClick={onSair} aria-label="Sair" title="Sair"
                    className={`rounded-lg px-2 py-1 text-base text-sandro-label hover:text-rose-300 ${focoVisivel}`}>
              <span aria-hidden="true">⏻</span>
            </button>
          </div>
        ) : (
          <div className="mt-4 flex gap-4">
            <button type="button" onClick={onAlterarSenha}
                    className={`text-xs text-sandro-label underline-offset-4 hover:text-white hover:underline ${focoVisivel}`}>
              Alterar minha senha
            </button>
            <button type="button" onClick={onSair}
                    className={`text-xs text-sandro-label underline-offset-4 hover:text-white hover:underline ${focoVisivel}`}>
              Sair
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
