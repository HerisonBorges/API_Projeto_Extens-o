import AcessoUsuarios from "../components/configuracoes/AcessoUsuarios.jsx";
import AutomacaoFunil from "../components/configuracoes/AutomacaoFunil.jsx";
import GestaoUsuarios from "../components/configuracoes/GestaoUsuarios.jsx";

// Restrito ao Gestor (a rota e a API bloqueiam os demais perfis)
export default function Configuracoes({ usuario, versao }) {
  return (
    <div className="space-y-6">
      <GestaoUsuarios key={`usuarios-${versao}`} usuarioLogado={usuario} />
      <div className="grid gap-6 2xl:grid-cols-2">
        <AcessoUsuarios key={`acesso-${versao}`} />
        <AutomacaoFunil key={`automacao-${versao}`} />
      </div>
    </div>
  );
}
