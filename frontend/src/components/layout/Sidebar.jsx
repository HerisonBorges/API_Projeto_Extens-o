const ITENS = [
  { id: "dashboard", rotulo: "Dashboard", icone: "◧", perfis: ["Gestor", "Atendimento"] },
  { id: "configuracoes", rotulo: "Configurações", icone: "⚙", perfis: ["Gestor"] },
];

export default function Sidebar({ usuario, ativa, onNavegar, onSair }) {
  const itens = ITENS.filter((item) => item.perfis.includes(usuario.perfil));

  return (
    <aside
      className="flex w-full shrink-0 flex-col border-b border-kindra-borda/30 bg-kindra-painel/40
                 backdrop-blur-xl md:min-h-screen md:w-64 md:border-r md:border-b-0"
    >
      <div className="px-6 py-6">
        <p className="text-lg font-semibold tracking-wide text-white">SANDRO CRM</p>
        <p className="text-xs text-kindra-label">Kindra · Smoked Glass</p>
      </div>

      <nav aria-label="Navegação principal" className="flex gap-1 px-3 md:flex-col">
        {itens.map((item) => {
          const atual = item.id === ativa;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavegar(item.id)}
              aria-current={atual ? "page" : undefined}
              className={`flex items-center gap-3 rounded-xl px-4 py-2.5 text-left text-sm transition
                          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-kindra-acento
                          ${atual
                            ? "bg-kindra-acento font-bold text-kindra-fundo shadow-lg shadow-kindra-acento/20"
                            : "text-slate-200 hover:bg-kindra-suporte/40"}`}
            >
              <span aria-hidden="true">{item.icone}</span>
              {item.rotulo}
            </button>
          );
        })}
      </nav>

      <div className="mt-auto hidden border-t border-kindra-borda/30 px-6 py-5 md:block">
        <p className="truncate text-sm text-white">{usuario.nome}</p>
        <p className="text-xs text-kindra-label">{usuario.perfil}</p>
        <button
          type="button"
          onClick={onSair}
          className="mt-3 text-xs text-kindra-label underline-offset-4 hover:text-white hover:underline
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-kindra-acento"
        >
          Sair
        </button>
      </div>
    </aside>
  );
}
