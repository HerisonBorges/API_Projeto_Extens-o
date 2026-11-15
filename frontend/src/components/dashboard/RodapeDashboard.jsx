/* global __APP_VERSION__ */
import { LogoSimbolo } from "../marca/Logo.jsx";
import { formatarDataHora } from "../ui/formatos.js";

const VERSAO = typeof __APP_VERSION__ === "string" ? __APP_VERSION__ : "dev";

function janela(usuario) {
  if (!usuario.hora_inicio_acesso || !usuario.hora_fim_acesso) return "Acesso sem restrição de horário";
  return `Seu acesso: ${usuario.hora_inicio_acesso} às ${usuario.hora_fim_acesso}`;
}

/** Rodapé do Dashboard: identidade do CRM, contexto da sessão e atualização dos dados. */
export default function RodapeDashboard({ usuario, atualizadoEm, onAtualizar, atualizando }) {
  const atalhos = [
    { href: "#/clientes", rotulo: "Clientes" },
    { href: "#/funil", rotulo: "Funil de Vendas" },
    { href: "#/followups", rotulo: "Follow-ups" },
    ...(usuario.perfil === "Gestor" ? [{ href: "#/relatorios", rotulo: "Relatórios" }] : []),
  ];

  return (
    <footer
      aria-label="Informações do SANDRO CRM"
      className="mt-10 rounded-xl border border-sandro-borda/20 bg-sandro-painel/40 px-5 py-5 text-xs text-sandro-label"
    >
      <div className="grid gap-5 md:grid-cols-3">
        <div className="flex items-start gap-3">
          <LogoSimbolo className="h-9 w-9 shrink-0" />
          <div>
            <p className="text-sm font-bold text-white">SANDRO <span className="text-sandro-acento">CRM</span></p>
            <p className="uppercase tracking-[0.25em]">O poder da conexão</p>
            <p className="mt-1">Versão {VERSAO}</p>
          </div>
        </div>

        <dl className="space-y-1">
          <div className="flex gap-1">
            <dt className="text-sandro-label">Empresa:</dt>
            <dd className="text-slate-200">{usuario.empresa_nome ?? "—"}</dd>
          </div>
          <div className="flex gap-1">
            <dt>Sessão:</dt>
            <dd className="text-slate-200">{usuario.nome} ({usuario.perfil})</dd>
          </div>
          <div>{janela(usuario)}</div>
        </dl>

        <div className="space-y-2 md:text-right">
          <p role="status">
            {atualizadoEm ? `Dados atualizados em ${formatarDataHora(atualizadoEm)}` : "Atualizando dados..."}
          </p>
          <button
            type="button"
            onClick={onAtualizar}
            disabled={atualizando}
            aria-busy={atualizando || undefined}
            className="rounded-md border border-sandro-borda/40 px-2.5 py-1 text-xs text-slate-200 transition
                       hover:border-sandro-acento hover:text-white focus-visible:outline-none focus-visible:ring-2
                       focus-visible:ring-sandro-acento disabled:cursor-wait disabled:opacity-60"
          >
            {atualizando ? "Atualizando..." : "↻ Atualizar agora"}
          </button>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-sandro-borda/20 pt-4">
        <nav aria-label="Atalhos do rodapé" className="-ml-1 flex flex-wrap gap-x-2 gap-y-1">
          {atalhos.map((a) => (
            <a key={a.href} href={a.href}
               className="alvo-toque px-1.5 hover:text-white hover:underline focus-visible:outline-none focus-visible:ring-2
                          focus-visible:ring-sandro-acento">
              {a.rotulo}
            </a>
          ))}
        </nav>
        <p>© {new Date().getFullYear()} SANDRO CRM · Dados restritos à sua empresa</p>
      </div>
    </footer>
  );
}
