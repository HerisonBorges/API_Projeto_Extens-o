import { useEffect, useState } from "react";

import { atualizarHorarioUsuario, listarUsuariosAcesso } from "../../services/api.js";
import GlassCard from "../ui/GlassCard.jsx";
import StatusBadge from "../ui/StatusBadge.jsx";

const campoHora = `w-28 rounded-lg border border-kindra-borda/40 bg-kindra-fundo/80 px-2 py-1.5 text-sm
                   text-white focus:border-kindra-acento focus:outline-none focus:ring-2
                   focus:ring-kindra-acento/40`;

function LinhaUsuario({ usuario, onAtualizado }) {
  const [inicio, setInicio] = useState(usuario.hora_inicio_acesso ?? "");
  const [fim, setFim] = useState(usuario.hora_fim_acesso ?? "");
  const [salvando, setSalvando] = useState(false);
  const [retorno, setRetorno] = useState(null);

  async function salvar(novoInicio, novoFim) {
    setSalvando(true);
    setRetorno(null);
    try {
      const resposta = await atualizarHorarioUsuario(usuario.id, novoInicio, novoFim);
      onAtualizado(resposta.usuario);
      setRetorno({ ok: true, texto: "Salvo." });
    } catch (e) {
      setRetorno({ ok: false, texto: e.message });
    } finally {
      setSalvando(false);
    }
  }

  const irrestrito = usuario.hora_inicio_acesso === null;

  return (
    <tr className="text-slate-200">
      <td className="px-5 py-3">
        <p className="font-medium text-white">{usuario.nome}</p>
        <p className="text-xs text-kindra-label">{usuario.email}</p>
      </td>
      <td className="px-5 py-3 text-sm">{usuario.perfil}</td>
      <td className="px-5 py-3">
        <div className="flex items-center gap-2">
          <label className="sr-only" htmlFor={`inicio-${usuario.id}`}>
            Início do acesso de {usuario.nome}
          </label>
          <input
            id={`inicio-${usuario.id}`}
            type="time"
            value={inicio}
            onChange={(e) => setInicio(e.target.value)}
            className={campoHora}
          />
          <span aria-hidden="true" className="text-kindra-label">às</span>
          <label className="sr-only" htmlFor={`fim-${usuario.id}`}>
            Fim do acesso de {usuario.nome}
          </label>
          <input
            id={`fim-${usuario.id}`}
            type="time"
            value={fim}
            onChange={(e) => setFim(e.target.value)}
            className={campoHora}
          />
        </div>
        {irrestrito && <p className="mt-1 text-xs text-kindra-label">Sem restrição (24/7)</p>}
      </td>
      <td className="px-5 py-3">
        {usuario.acesso_permitido ? (
          <StatusBadge tom="permitido" icone="●">Permitido</StatusBadge>
        ) : (
          <StatusBadge tom="bloqueado" icone="■">Bloqueado</StatusBadge>
        )}
      </td>
      <td className="px-5 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={salvando || !inicio || !fim}
            aria-busy={salvando}
            onClick={() => salvar(inicio, fim)}
            className="rounded-lg bg-kindra-acento px-3 py-1.5 text-xs font-medium text-white shadow-lg
                       shadow-kindra-acento/20 hover:brightness-110 focus-visible:outline-none
                       focus-visible:ring-2 focus-visible:ring-white/70 disabled:cursor-not-allowed
                       disabled:opacity-50"
          >
            {salvando ? "Salvando..." : "Salvar"}
          </button>
          <button
            type="button"
            disabled={salvando || irrestrito}
            onClick={() => {
              setInicio("");
              setFim("");
              salvar(null, null);
            }}
            className="rounded-lg px-3 py-1.5 text-xs text-kindra-label hover:text-white
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-kindra-acento
                       disabled:cursor-not-allowed disabled:opacity-40"
          >
            Liberar 24h
          </button>
        </div>
        <p
          role="status"
          className={`mt-1 min-h-4 text-xs ${retorno?.ok ? "text-teal-400" : "text-rose-400"}`}
        >
          {retorno?.texto}
        </p>
      </td>
    </tr>
  );
}

export default function AcessoUsuarios() {
  const [usuarios, setUsuarios] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);

  useEffect(() => {
    listarUsuariosAcesso()
      .then(setUsuarios)
      .catch((e) => setErro(e.message))
      .finally(() => setCarregando(false));
  }, []);

  const atualizar = (atualizado) =>
    setUsuarios((lista) => lista.map((u) => (u.id === atualizado.id ? atualizado : u)));

  return (
    <GlassCard className="overflow-hidden p-0">
      <div className="px-5 py-4">
        <h2 className="text-base font-semibold text-white">Horário de acesso por usuário</h2>
        <p className="text-xs text-kindra-label">
          Fora da janela o usuário não entra e sessões abertas são encerradas na próxima ação.
          Início maior que o fim vale para turnos que cruzam a meia-noite.
        </p>
      </div>

      {carregando && <p className="px-5 pb-5 text-sm text-kindra-label">Carregando usuários...</p>}
      {erro && <p role="alert" className="px-5 pb-5 text-sm text-rose-400">{erro}</p>}

      {!carregando && !erro && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Usuários da empresa e suas janelas de acesso</caption>
            <thead className="border-y border-kindra-borda/30 text-xs uppercase tracking-wider text-kindra-label">
              <tr>
                <th scope="col" className="px-5 py-3 font-medium">Usuário</th>
                <th scope="col" className="px-5 py-3 font-medium">Perfil</th>
                <th scope="col" className="px-5 py-3 font-medium">Janela</th>
                <th scope="col" className="px-5 py-3 font-medium">Status agora</th>
                <th scope="col" className="px-5 py-3 font-medium"><span className="sr-only">Ações</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-kindra-borda/20">
              {usuarios.map((u) => (
                <LinhaUsuario key={u.id} usuario={u} onAtualizado={atualizar} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </GlassCard>
  );
}
