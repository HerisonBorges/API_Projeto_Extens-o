import { useState } from "react";

import { entrar } from "../services/api.js";
import GlassCard from "../components/ui/GlassCard.jsx";

const campo = `w-full rounded-lg border border-kindra-borda/40 bg-kindra-fundo/80 px-3 py-2 text-white
               placeholder:text-kindra-label/60 focus:border-kindra-acento focus:outline-none
               focus:ring-2 focus:ring-kindra-acento/40`;

export default function Login({ aviso, onEntrar }) {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      onEntrar(await entrar(email, senha));
    } catch (e) {
      // HORARIO_BLOQUEADO chega aqui pelo aviso do App; outros erros ficam locais
      if (e.codigo !== "HORARIO_BLOQUEADO") setErro(e.message);
      setEnviando(false);
    }
  }

  const mensagem = erro ?? aviso;

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <GlassCard className="w-full max-w-sm p-8">
        <h1 className="text-2xl font-semibold text-white">SANDRO CRM</h1>
        <p className="mt-1 text-sm text-kindra-label">Entre com sua conta</p>

        {mensagem && (
          <p role="alert" className="mt-5 rounded-lg bg-rose-950/80 px-3 py-2 text-sm text-rose-300">
            {mensagem}
          </p>
        )}

        <form onSubmit={enviar} className="mt-6 space-y-4">
          <div>
            <label htmlFor="email" className="mb-1 block text-sm text-slate-200">E-mail</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={campo}
            />
          </div>
          <div>
            <label htmlFor="senha" className="mb-1 block text-sm text-slate-200">Senha</label>
            <input
              id="senha"
              type="password"
              autoComplete="current-password"
              required
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              className={campo}
            />
          </div>
          <button
            type="submit"
            disabled={enviando}
            aria-busy={enviando}
            className="w-full rounded-lg bg-kindra-acento py-2.5 text-sm font-bold text-kindra-fundo shadow-lg
                       shadow-kindra-acento/20 transition hover:brightness-110 focus-visible:outline-none
                       focus-visible:ring-2 focus-visible:ring-white/70 disabled:cursor-wait disabled:opacity-60"
          >
            {enviando ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </GlassCard>
    </main>
  );
}
