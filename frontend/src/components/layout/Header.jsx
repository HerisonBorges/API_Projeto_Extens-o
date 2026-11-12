import Botao from "../ui/Botao.jsx";

export default function Header({ titulo, usuario, onNovoLead, onSair, onAlterarSenha }) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-sandro-borda/20 pb-5">
      <div>
        <h1 className="text-2xl font-semibold text-white">{titulo}</h1>
        <p className="text-sm text-sandro-label">
          {usuario.empresa_nome ?? "Empresa"} · {usuario.nome} ({usuario.perfil})
        </p>
      </div>
      <div className="flex items-center gap-3">
        <Botao variante="fantasma" tamanho="sm" onClick={onAlterarSenha} className="md:hidden">
          Alterar senha
        </Botao>
        <Botao variante="fantasma" tamanho="sm" onClick={onSair} className="md:hidden">
          Sair
        </Botao>
        <Botao variante="primario" onClick={onNovoLead}>
          <span aria-hidden="true">+</span> Novo Lead
        </Botao>
      </div>
    </header>
  );
}
