import { useEffect, useId, useRef } from "react";

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
    dialogo.current?.querySelector(FOCAVEIS)?.focus();
    return () => anterior?.focus?.();
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

  return (
    <div
      onMouseDown={(e) => e.target === e.currentTarget && fecharRef.current()}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
    >
      <div
        ref={dialogo}
        role="dialog"
        aria-modal="true"
        aria-labelledby={tituloId}
        aria-describedby={descricao ? descricaoId : undefined}
        className={`max-h-[90vh] w-full ${largura} overflow-y-auto rounded-xl border border-sandro-borda/40
                    bg-sandro-painel p-6 shadow-2xl shadow-black/50`}
      >
        <h2 id={tituloId} className="text-lg font-semibold text-white">{titulo}</h2>
        {descricao && (
          <p id={descricaoId} className="mt-1 text-sm text-sandro-label">{descricao}</p>
        )}
        <div className="mt-5">{children}</div>
      </div>
    </div>
  );
}
