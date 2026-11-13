import FormularioNovaSenha from "../components/conta/FormularioNovaSenha.jsx";
import Logo from "../components/marca/Logo.jsx";
import Card from "../components/ui/Card.jsx";

/** Primeiro acesso, senha redefinida ou conta reativada: troca antes de qualquer tela. */
export default function TrocaSenhaObrigatoria({ usuario, onConcluido, onSair }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-sandro-fundo px-4 py-12">
      <div className="w-full max-w-md space-y-6">
        <Logo comSlogan />
        <Card className="p-6">
          <h1 className="text-xl font-semibold text-white">Defina a sua senha</h1>
          <p className="mt-1 text-sm text-sandro-label">
            Olá, {usuario.nome}. Você entrou com uma senha temporária. Escolha uma senha pessoal
            para continuar. Só você deve conhecê-la.
          </p>
          <div className="mt-5">
            <FormularioNovaSenha rotuloAtual="Senha temporária" textoBotao="Definir senha e entrar"
                                 onConcluido={onConcluido} />
          </div>
        </Card>
        <button type="button" onClick={onSair}
                className="text-xs text-sandro-label underline-offset-4 hover:text-white hover:underline">
          Sair e voltar ao login
        </button>
      </div>
    </main>
  );
}
