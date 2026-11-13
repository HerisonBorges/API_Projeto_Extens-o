import { useState } from "react";

import { alterarMinhaSenha } from "../../services/api.js";
import Botao from "../ui/Botao.jsx";
import CampoSenha, { DICA_SENHA } from "../ui/CampoSenha.jsx";

/** Usado na troca obrigatória (primeiro acesso) e na troca voluntária. */
export default function FormularioNovaSenha({ rotuloAtual = "Senha atual", textoBotao = "Salvar nova senha", onConcluido, onCancelar }) {
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);

  const confirmacaoErrada = confirmacao.length > 0 && confirmacao !== nova;

  async function salvar(e) {
    e.preventDefault();
    setErro(null);
    if (nova.length < 10) return setErro("A nova senha precisa de pelo menos 10 caracteres.");
    if (nova !== confirmacao) return setErro("A confirmação não confere com a nova senha.");

    setEnviando(true);
    try {
      onConcluido(await alterarMinhaSenha(atual, nova));
    } catch (erroApi) {
      setErro(erroApi.message);
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={salvar} className="space-y-4">
      <CampoSenha rotulo={rotuloAtual} valor={atual} onChange={setAtual} autoComplete="current-password" />
      <CampoSenha rotulo="Nova senha" valor={nova} onChange={setNova} ajuda={DICA_SENHA} />
      <CampoSenha rotulo="Confirme a nova senha" valor={confirmacao} onChange={setConfirmacao}
                  erro={confirmacaoErrada ? "As senhas não são iguais." : undefined} />

      {erro && <p role="alert" className="rounded-lg bg-rose-950/80 px-3 py-2 text-sm text-rose-300">{erro}</p>}

      <div className="flex justify-end gap-3 pt-1">
        {onCancelar && <Botao variante="fantasma" onClick={onCancelar} disabled={enviando}>Cancelar</Botao>}
        <Botao variante="primario" type="submit" carregando={enviando} textoCarregando="Salvando..."
               disabled={!atual || !nova || !confirmacao}>
          {textoBotao}
        </Botao>
      </div>
    </form>
  );
}
