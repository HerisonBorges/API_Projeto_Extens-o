import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";

const FOCAVEIS = 'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]';

/**
 * Diálogo acessível: foco inicial no primeiro campo, Tab preso dentro,
 * Esc e clique no fundo fecham (exceto com bloqueado=true), foco volta a quem abriu.
 */
export default function Modal({ titulo, descricao, onFechar, bloqueado = false, largura = "max-w-md", children }) {
  const tituloId = useId();
  const descricaoId = useId();
  const dialogo = useRef(null);

  const fecharRef = useRef(onFechar);
  fecharRef.current = bloqueado ? () => {} : onFechar;

  useEffect(() => {
    const anterior = document.activeElement;
    // No toque, focar um campo abre o teclado virtual sem a pessoa pedir:
    // foca o próprio diálogo (o leitor de tela anuncia o título). Com mouse/teclado, o 1º campo.
    const toque = window.matchMedia?.("(pointer: coarse)").matches;
    if (toque) dialogo.current?.focus();
    else dialogo.current?.querySelector(FOCAVEIS)?.focus();

    // A página de trás não rola enquanto o modal está aberto
    const overflowAnterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = overflowAnterior;
      anterior?.focus?.();
    };
  }, []);

  // Teclado virtual: a altura útil vira a da área visível e o campo focado é
  // trazido para a vista (iOS não redimensiona o layout quando o teclado abre)
  useEffect(() => {
    const vv = window.visualViewport;
    const el = dialogo.current;
    if (!el) return undefined;

    const ajustarAltura = () => {
      if (vv) el.style.maxHeight = `${Math.floor(vv.height * 0.92)}px`;
    };
    const trazerCampo = (e) => {
      if (!e.target.matches?.("input, select, textarea")) return;
      setTimeout(() => e.target.scrollIntoView?.({ block: "center", behavior: "smooth" }), 250);
    };

    ajustarAltura();
    vv?.addEventListener("resize", ajustarAltura);
    el.addEventListener("focusin", trazerCampo);
    return () => {
      vv?.removeEventListener("resize", ajustarAltura);
      el.removeEventListener("focusin", trazerCampo);
    };
  }, []);

  useEffect(() => {
    const aoTeclar = (e) => {
      if (e.key === "Escape") {
        fecharRef.current();
        return;
      }
      if (e.key !== "Tab" || !dialogo.current) return;

      const focaveis = [...dialogo.current.querySelectorAll(FOCAVEIS)].filter(
        (el) => !(el.type === "radio" && !el.checked)
      );
      if (focaveis.length === 0) return;

      const primeiro = focaveis[0];
      const ultimo = focaveis[focaveis.length - 1];
      const fora = !dialogo.current.contains(document.activeElement);

      if (e.shiftKey && (document.activeElement === primeiro || fora)) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && (document.activeElement === ultimo || fora)) {
        e.preventDefault();
        primeiro.focus();
      }
    };
    document.addEventListener("keydown", aoTeclar);
    return () => document.removeEventListener("keydown", aoTeclar);
  }, []);

  // Portal no <body>: um ancestral com backdrop-filter/transform (ex.: Card com
  // md:backdrop-blur-sm) vira o containing block de position:fixed e prenderia
  // o modal dentro do card, coberto pelos vizinhos
  return createPortal(
    <div
      onMouseDown={(e) => e.target === e.currentTarget && fecharRef.current()}
      // Celular: "bottom sheet" colado na base (alcance do polegar). sm+: centralizado.
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 sm:items-center sm:p-4"
    >
      <div
        ref={dialogo}
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
        aria-labelledby={tituloId}
        aria-describedby={descricao ? descricaoId : undefined}
        className={`max-h-[92dvh] w-full ${largura} overflow-y-auto overscroll-contain rounded-t-2xl border
                    border-sandro-borda/40 bg-sandro-painel px-5 pt-5 shadow-2xl shadow-black/50
                    pb-[calc(1.25rem+env(safe-area-inset-bottom))] focus:outline-none
                    sm:rounded-xl sm:p-6`}
      >
        {/* Alça visual do bottom sheet (só celular) */}
        <div aria-hidden="true" className="mx-auto -mt-1 mb-4 h-1 w-10 rounded-full bg-sandro-borda/50 sm:hidden" />
        <h2 id={tituloId} className="text-lg font-semibold text-white">{titulo}</h2>
        {descricao && (
          <p id={descricaoId} className="mt-1 text-sm text-sandro-label">{descricao}</p>
        )}
        <div className="mt-5">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
