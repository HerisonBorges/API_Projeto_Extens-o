import { useState } from "react";

import Campo, { classeEntrada } from "./Campo.jsx";

export const DICA_SENHA = "Mínimo de 10 caracteres. Evite senhas comuns e não use o seu e-mail.";

/** Campo de senha com botão Mostrar/Ocultar acessível. */
export default function CampoSenha({ rotulo, valor, onChange, autoComplete = "new-password", ajuda, erro }) {
  const [visivel, setVisivel] = useState(false);

  return (
    <Campo rotulo={rotulo} ajuda={ajuda} erro={erro}>
      {(props) => (
        <div className="relative">
          <input
            {...props}
            type={visivel ? "text" : "password"}
            autoComplete={autoComplete}
            required
            maxLength={72}
            value={valor}
            onChange={(e) => onChange(e.target.value)}
            className={`${classeEntrada} pr-20`}
          />
          <button
            type="button"
            onClick={() => setVisivel((v) => !v)}
            aria-pressed={visivel}
            aria-label={visivel ? `Ocultar ${rotulo.toLowerCase()}` : `Mostrar ${rotulo.toLowerCase()}`}
            className="absolute inset-y-0 right-0 px-3 text-xs text-sandro-label hover:text-white
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sandro-acento"
          >
            {visivel ? "Ocultar" : "Mostrar"}
          </button>
        </div>
      )}
    </Campo>
  );
}
