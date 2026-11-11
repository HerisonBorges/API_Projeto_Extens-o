import { useId } from "react";

/** Símbolo: "S" de conexão (azuis), seta de crescimento e barras (ciano), nós de circuito. */
export function LogoSimbolo({ className = "h-10 w-10" }) {
  const gradiente = useId();
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={gradiente} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#4A68D0" />
          <stop offset="1" stopColor="#204C94" />
        </linearGradient>
      </defs>

      {/* Nós de conexão à esquerda */}
      <g stroke="#4A68D0" strokeWidth="1.6" strokeLinecap="round" opacity="0.85">
        <path d="M7 21h9" />
        <path d="M4 29h11" />
        <path d="M7 37h8" />
      </g>
      <g fill="none" stroke="#4A68D0" strokeWidth="1.6">
        <circle cx="5" cy="21" r="1.9" />
        <circle cx="2.6" cy="29" r="1.9" />
        <circle cx="5" cy="37" r="1.9" />
      </g>

      {/* "S" */}
      <path
        d="M45 14H27a9 9 0 0 0 0 18h11a9 9 0 0 1 0 18H18"
        fill="none"
        stroke={`url(#${gradiente})`}
        strokeWidth="7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Seta de crescimento */}
      <path d="M41 24 57 8" stroke="#0F969C" strokeWidth="3.4" strokeLinecap="round" />
      <path d="M48 7.5h9.5V17" fill="none" stroke="#0F969C" strokeWidth="3.4"
            strokeLinecap="round" strokeLinejoin="round" />

      {/* Barras dentro da curva inferior */}
      <g fill="#0F969C">
        <rect x="27" y="41" width="3" height="4.5" rx="1" />
        <rect x="32" y="38.5" width="3" height="7" rx="1" />
        <rect x="37" y="36" width="3" height="9.5" rx="1" />
      </g>
    </svg>
  );
}

export default function Logo({ tamanho = "md", comSlogan = false }) {
  const grande = tamanho === "lg";
  return (
    <div className="flex items-center gap-3">
      <LogoSimbolo className={grande ? "h-20 w-20" : "h-10 w-10"} />
      <div className={`border-l border-sandro-borda/40 ${grande ? "pl-4" : "pl-3"}`}>
        <p className={`font-extrabold leading-none tracking-wide text-white ${grande ? "text-4xl" : "text-lg"}`}>
          SANDRO <span className="text-sandro-acento">CRM</span>
        </p>
        {comSlogan && (
          <p className={`mt-2 uppercase tracking-[0.3em] text-sandro-label ${grande ? "text-xs" : "text-[0.6rem]"}`}>
            O poder da conexão
          </p>
        )}
      </div>
    </div>
  );
}
