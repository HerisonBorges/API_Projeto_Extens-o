import Botao from "../ui/Botao.jsx";

// "Alterar senha" e "Sair" ficam na sidebar (tablet/desktop) e na gaveta do menu (celular)
export default function Header({ titulo, usuario, onNovoLead }) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-sandro-borda/20 pb-4 md:pb-5">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold text-white md:text-2xl">{titulo}</h1>
        <p className="truncate text-sm text-sandro-label">
          {usuario.empresa_nome ?? "Empresa"} · {usuario.nome} ({usuario.perfil})
        </p>
      </div>
      <Botao variante="primario" onClick={onNovoLead} className="shrink-0">
        <span aria-hidden="true">+</span> Novo Lead
      </Botao>
    </header>
  );
}
