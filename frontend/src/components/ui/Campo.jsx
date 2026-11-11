import { useId } from "react";

export const classeEntrada = `w-full rounded-lg border border-sandro-borda/40 bg-sandro-fundo/80 px-3 py-2
  text-sm text-white placeholder:text-sandro-label/60 focus:border-sandro-acento focus:outline-none
  focus:ring-2 focus:ring-sandro-acento/40 disabled:opacity-60`;

/** Rótulo visível sempre ligado ao controle (htmlFor/id). */
export default function Campo({ rotulo, ajuda, erro, children, className = "" }) {
  const id = useId();
  const idAjuda = ajuda || erro ? `${id}-ajuda` : undefined;

  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-sandro-label">
        {rotulo}
      </label>
      {children({ id, "aria-describedby": idAjuda, "aria-invalid": erro ? true : undefined })}
      {(ajuda || erro) && (
        <p id={idAjuda} className={`mt-1 text-xs ${erro ? "text-rose-300" : "text-sandro-label"}`}>
          {erro ?? ajuda}
        </p>
      )}
    </div>
  );
}
