import { useState } from "react";

import Logo from "../components/marca/Logo.jsx";
import Botao from "../components/ui/Botao.jsx";
import Campo, { classeEntrada } from "../components/ui/Campo.jsx";
import { encerrarSessao, entrar } from "../services/api.js";

const PERFIS = ["Gestor", "Atendimento"];

export default function Login({ aviso, onEntrar }) {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [perfil, setPerfil] = useState("Gestor");
  const [erro, setErro] = useState(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      const usuario = await entrar(email, senha);

      // O perfil é da conta; o seletor só confirma a intenção de quem entra
      if (usuario.perfil !== perfil) {
        encerrarSessao(`Esta conta é do perfil ${usuario.perfil}. Selecione "${usuario.perfil}" para entrar.`);
        setEnviando(false);
        return;
      }
      onEntrar(usuario);
    } catch (e) {
      // HORARIO_BLOQUEADO chega pelo aviso do App; outros erros ficam aqui
      if (e.codigo !== "HORARIO_BLOQUEADO") setErro(e.message);
      setEnviando(false);
    }
  }

  const mensagem = erro ?? aviso;
  const bloqueado = !erro && aviso?.startsWith("Acesso permitido apenas");

  return (
    <main className="grid min-h-screen md:grid-cols-2">
      {/* Marca */}
      <section
        aria-label="SANDRO CRM"
        className="relative flex items-center justify-center overflow-hidden border-b border-sandro-borda/20
                   bg-sandro-fundo px-8 py-16 md:border-r md:border-b-0"
      >
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -left-24 top-1/4 h-80 w-80 rounded-full bg-sandro-borda/15 blur-3xl"
        />
        <div className="relative">
          <Logo tamanho="lg" comSlogan />
          <p className="mt-8 max-w-sm text-sm leading-relaxed text-sandro-label">
            Clientes, funil de vendas e follow-ups da sua equipe em um só lugar.
          </p>
        </div>
      </section>

      {/* Formulário */}
      <section className="flex items-center justify-center bg-sandro-painel/30 px-6 py-12">
        <div className="w-full max-w-sm">
          <h1 className="text-2xl font-semibold text-white">Entrar</h1>
          <p className="mt-1 text-sm text-sandro-label">Use o e-mail cadastrado pela sua empresa.</p>

          {mensagem && (
            <div role="alert"
                 className="mt-6 flex gap-3 rounded-lg border border-rose-500/30 bg-rose-950/70 px-4 py-3 text-sm text-rose-200">
              <span aria-hidden="true">{bloqueado ? "⏱" : "!"}</span>
              <div>
                {bloqueado && <p className="font-semibold text-rose-100">Fora do seu horário de acesso</p>}
                <p>{mensagem}</p>
              </div>
            </div>
          )}

          <form onSubmit={enviar} className="mt-6 space-y-4">
            <fieldset>
              <legend className="mb-2 text-xs font-medium text-sandro-label">Perfil de acesso</legend>
              <div className="grid grid-cols-2 gap-2">
                {PERFIS.map((p) => (
                  <label
                    key={p}
                    className={`flex cursor-pointer items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm
                                transition has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-sandro-acento
                                ${perfil === p
                                  ? "border-sandro-acento bg-sandro-acento/10 font-semibold text-white"
                                  : "border-sandro-borda/40 text-sandro-label hover:text-white"}`}
                  >
                    <input type="radio" name="perfil" value={p} checked={perfil === p}
                           onChange={() => setPerfil(p)} className="sr-only" />
                    {p}
                  </label>
                ))}
              </div>
            </fieldset>

            <Campo rotulo="E-mail">
              {(props) => (
                <input {...props} type="email" autoComplete="email" required value={email}
                       onChange={(e) => setEmail(e.target.value)} className={classeEntrada} />
              )}
            </Campo>
            <Campo rotulo="Senha">
              {(props) => (
                <input {...props} type="password" autoComplete="current-password" required value={senha}
                       onChange={(e) => setSenha(e.target.value)} className={classeEntrada} />
              )}
            </Campo>

            <Botao variante="primario" type="submit" carregando={enviando} textoCarregando="Entrando..."
                   className="w-full py-2.5">
              Entrar no SANDRO
            </Botao>
          </form>
        </div>
      </section>
    </main>
  );
}
