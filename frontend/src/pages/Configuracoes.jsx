import AcessoUsuarios from "../components/configuracoes/AcessoUsuarios.jsx";
import AutomacaoFunil from "../components/configuracoes/AutomacaoFunil.jsx";

// Duas seções restritas ao Gestor (a rota e a API bloqueiam os demais perfis)
export default function Configuracoes({ versao }) {
  return (
    <div className="grid gap-6 2xl:grid-cols-2">
      <AcessoUsuarios key={`acesso-${versao}`} />
      <AutomacaoFunil key={`automacao-${versao}`} />
    </div>
  );
}
