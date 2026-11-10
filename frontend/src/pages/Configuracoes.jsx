import AcessoUsuarios from "../components/configuracoes/AcessoUsuarios.jsx";

export default function Configuracoes() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-white">Configurações</h1>
        <p className="text-sm text-kindra-label">Controle de acesso da equipe</p>
      </header>
      <AcessoUsuarios />
    </div>
  );
}
