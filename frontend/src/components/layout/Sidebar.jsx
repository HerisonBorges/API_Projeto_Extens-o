import { useEffect, useRef, useState } from "react";

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

function classeLink(atual) {
  return atual
    ? "bg-sandro-acento font-bold text-sandro-fundo"
    : "text-slate-200 hover:bg-sandro-suporte/40";
}

export default function Sidebar(props) {
  return (
    <>
      <NavegacaoCelular {...props} />
      <SidebarDesktop {...props} />
    </>
  );
}

/**
 * Celular (< md): barra do topo fixa e compacta (56px) + gaveta lateral.
 * A gaveta anima só transform/opacity (camada própria na GPU, sem reflow),
 * fica "inert" quando fechada e fecha com Esc, fundo, troca de rota ou ao virar tablet.
 */
function NavegacaoCelular({ usuario, ativa, onSair, onAlterarSenha }) {
  const itens = Object.keys(ROTAS).filter((pagina) => podeAcessar(pagina, usuario.perfil));
  const [aberta, setAberta] = useState(false);
  const botaoMenu = useRef(null);
  const painel = useRef(null);

  useEffect(() => {
    if (!aberta) return undefined;
    const fechar = () => setAberta(false);
    const aoTeclar = (e) => {
      if (e.key === "Escape") {
        fechar();
        botaoMenu.current?.focus();
      }
    };
    const virouTablet = window.matchMedia("(min-width: 48rem)");
    const overflowAnterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    painel.current?.querySelector("a, button")?.focus();
    window.addEventListener("keydown", aoTeclar);
    window.addEventListener("hashchange", fechar);
    virouTablet.addEventListener("change", fechar);
    return () => {
      document.body.style.overflow = overflowAnterior;
      window.removeEventListener("keydown", aoTeclar);
      window.removeEventListener("hashchange", fechar);
      virouTablet.removeEventListener("change", fechar);
    };
  }, [aberta]);

  const acao = (fn) => () => {
    setAberta(false);
    fn();
  };

  return (
    <div className="sticky top-0 z-30 md:hidden">
      <div
        className="flex h-[calc(3.5rem+env(safe-area-inset-top))] items-center justify-between border-b
                   border-sandro-borda/25 bg-sandro-fundo/95 pl-4 pr-1 pt-[env(safe-area-inset-top)]"
      >
        <a href="#/dashboard" aria-label="SANDRO CRM, ir para o Dashboard"
           className={`flex min-h-12 items-center gap-2 rounded-lg ${focoVisivel}`}>
          <LogoSimbolo className="h-8 w-8" />
          <span className="text-sm font-bold tracking-wide text-white">SANDRO CRM</span>
        </a>
        <button
          ref={botaoMenu}
          type="button"
          onClick={() => setAberta(true)}
          aria-expanded={aberta}
          aria-controls="menu-celular"
          aria-label="Abrir menu"
          className={`flex h-12 w-12 items-center justify-center rounded-lg text-2xl text-white
                      active:bg-sandro-suporte/40 ${focoVisivel}`}
        >
          <span aria-hidden="true">☰</span>
        </button>
      </div>

      {/* Sempre montada para a transição funcionar; fechada = invisível + inert */}
      <div
        className={`fixed inset-0 z-40 ${aberta ? "" : "pointer-events-none"}`}
        inert={!aberta}
      >
        <div
          onClick={() => setAberta(false)}
          className={`absolute inset-0 bg-black/60 transition-opacity duration-200
                      ${aberta ? "opacity-100" : "opacity-0"}`}
        />
        <nav
          id="menu-celular"
          ref={painel}
          aria-label="Navegação principal"
          className={`absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col bg-sandro-painel
                      pb-[env(safe-area-inset-bottom)] pt-[env(safe-area-inset-top)]
                      transition-transform duration-200 ease-out will-change-transform
                      motion-reduce:transition-none ${aberta ? "translate-x-0" : "-translate-x-full"}`}
        >
          <div className="flex items-center justify-between py-3 pl-5 pr-1">
            <Logo />
            <button
              type="button"
              onClick={() => {
                setAberta(false);
                botaoMenu.current?.focus();
              }}
              aria-label="Fechar menu"
              className={`flex h-12 w-12 items-center justify-center rounded-lg text-xl text-sandro-label
                          hover:text-white ${focoVisivel}`}
            >
              <span aria-hidden="true">✕</span>
            </button>
          </div>

          <ul className="flex-1 space-y-1 overflow-y-auto overscroll-contain px-3">
            {itens.map((pagina) => (
              <li key={pagina}>
                <a
                  href={`#/${pagina}`}
                  aria-current={pagina === ativa ? "page" : undefined}
                  className={`flex min-h-12 items-center gap-3 rounded-lg px-4 text-base ${focoVisivel}
                              ${classeLink(pagina === ativa)}`}
                >
                  <span aria-hidden="true" className="w-5 text-center">{ICONES[pagina]}</span>
                  {ROTAS[pagina].titulo}
                </a>
              </li>
            ))}
          </ul>

          <div className="border-t border-sandro-borda/25 px-5 py-4">
            <p className="truncate text-sm text-white">{usuario.nome}</p>
            <p className="text-xs text-sandro-label">{usuario.perfil} · {usuario.empresa_nome ?? "Empresa"}</p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button type="button" onClick={acao(onAlterarSenha)}
                      className={`min-h-12 rounded-lg border border-sandro-borda/30 text-sm text-slate-200 ${focoVisivel}`}>
                Alterar senha
              </button>
              <button type="button" onClick={acao(onSair)}
                      className={`min-h-12 rounded-lg border border-rose-400/40 text-sm text-rose-200 ${focoVisivel}`}>
                Sair
              </button>
            </div>
          </div>
        </nav>
      </div>
    </div>
  );
}

/** Tablet/desktop (≥ md): sidebar fixa com opção de recolher (preferência lembrada). */
function SidebarDesktop({ usuario, ativa, onSair, onAlterarSenha }) {
  const itens = Object.keys(ROTAS).filter((pagina) => podeAcessar(pagina, usuario.perfil));
  const [recolhida, setRecolhida] = useState(lerPreferencia);

  useEffect(() => {
    try {
      window.localStorage.setItem(CHAVE_PREFERENCIA, recolhida ? "1" : "0");
    } catch {
      // modo privado sem storage: só não lembra a preferência
    }
  }, [recolhida]);

  const md = (classeAberta, classeRecolhida) => (recolhida ? classeRecolhida : classeAberta);
  const iniciais = usuario.nome.trim().charAt(0).toUpperCase();

  return (
    <aside
      id="menu-principal"
      aria-label="Menu"
      className={`sticky top-0 hidden h-screen shrink-0 flex-col border-r border-sandro-borda/25
                  bg-sandro-painel/40 transition-[width] duration-200 motion-reduce:transition-none md:flex
                  ${md("w-64", "w-20")}`}
    >
      {/* Marca: sempre visível. Aberta = logo completo; recolhida = símbolo do SANDRO */}
      <div className={`relative flex items-center py-6 ${md("px-5", "justify-center px-0")}`}>
        <a href="#/dashboard" aria-label="SANDRO CRM, ir para o Dashboard" className={`rounded-lg ${focoVisivel}`}>
          {recolhida ? (
            <span className="block" title="SANDRO CRM · O poder da conexão">
              <LogoSimbolo className="h-11 w-11" />
            </span>
          ) : (
            <Logo comSlogan />
          )}
        </a>
      </div>

      <div className={`flex px-3 pb-2 ${md("justify-end", "justify-center")}`}>
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

      <nav aria-label="Navegação principal" className="flex flex-col gap-1 px-3">
        {itens.map((pagina) => {
          const atual = pagina === ativa;
          const titulo = ROTAS[pagina].titulo;
          return (
            <a
              key={pagina}
              href={`#/${pagina}`}
              aria-current={atual ? "page" : undefined}
              title={recolhida ? titulo : undefined}
              className={`flex items-center gap-3 rounded-lg py-2.5 text-sm transition ${focoVisivel}
                          ${md("px-4", "justify-center px-0")} ${classeLink(atual)}`}
            >
              <span aria-hidden="true" className={md("w-4 text-center", "text-lg")}>{ICONES[pagina]}</span>
              {/* Recolhida: o nome some da tela mas continua para o leitor de tela */}
              <span className={md("", "sr-only")}>{titulo}</span>
            </a>
          );
        })}
      </nav>

      <div className={`mt-auto border-t border-sandro-borda/25 py-5 ${md("px-5", "px-2")}`}>
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
