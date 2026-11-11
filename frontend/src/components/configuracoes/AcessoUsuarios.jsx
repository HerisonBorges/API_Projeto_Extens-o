import { useEffect, useState } from "react";

import { atualizarHorarioUsuario, listarUsuariosAcesso } from "../../services/api.js";
import Botao from "../ui/Botao.jsx";
import Card from "../ui/Card.jsx";
import { Carregando, Erro } from "../ui/Estado.jsx";
import StatusBadge from "../ui/StatusBadge.jsx";

const campoHora = `w-28 rounded-lg border border-sandro-borda/40 bg-sandro-fundo/80 px-2 py-1.5 text-sm
                   text-white focus:border-sandro-acento focus:outline-none focus:ring-2 focus:ring-sandro-acento/40`;

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
      setInicio(resposta.usuario.hora_inicio_acesso ?? "");
      setFim(resposta.usuario.hora_fim_acesso ?? "");
      setRetorno({ ok: true, texto: "Salvo." });
    } catch (e) {
      // Campos voltam ao que está gravado: a linha nunca mostra um horário que não vale
      setInicio(usuario.hora_inicio_acesso ?? "");
      setFim(usuario.hora_fim_acesso ?? "");
      setRetorno({ ok: false, texto: e.message });
    } finally {
      setSalvando(false);
    }
  }

  const irrestrito = usuario.hora_inicio_acesso === null;

  return (
    <tr className="align-top text-slate-200">
      <td className="px-5 py-3">
        <p className="font-medium text-white">{usuario.nome}</p>
        <p className="text-xs text-sandro-label">{usuario.email}</p>
      </td>
      <td className="px-5 py-3 text-sm">{usuario.perfil}</td>
      <td className="px-5 py-3">
        <div className="flex items-center gap-2">
          <label className="sr-only" htmlFor={`inicio-${usuario.id}`}>Início da jornada de {usuario.nome}</label>
          <input id={`inicio-${usuario.id}`} type="time" value={inicio}
                 onChange={(e) => setInicio(e.target.value)} className={campoHora} />
          <span aria-hidden="true" className="text-sandro-label">às</span>
          <label className="sr-only" htmlFor={`fim-${usuario.id}`}>Fim da jornada de {usuario.nome}</label>
          <input id={`fim-${usuario.id}`} type="time" value={fim}
                 onChange={(e) => setFim(e.target.value)} className={campoHora} />
        </div>
        {irrestrito && <p className="mt-1 text-xs text-sandro-label">Sem restrição (24/7)</p>}
      </td>
      <td className="px-5 py-3">
        {usuario.acesso_permitido
          ? <StatusBadge tom="permitido" icone="●">Permitido</StatusBadge>
          : <StatusBadge tom="bloqueado" icone="■">Bloqueado</StatusBadge>}
      </td>
      <td className="px-5 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <Botao variante="primario" tamanho="sm" disabled={!inicio || !fim} carregando={salvando}
                 textoCarregando="Salvando..." onClick={() => salvar(inicio, fim)}>
            Salvar
          </Botao>
          <Botao variante="fantasma" tamanho="sm" disabled={salvando || irrestrito}
                 onClick={() => salvar(null, null)}>
            Liberar 24h
          </Botao>
        </div>
        <p role="status" className={`mt-1 min-h-4 text-xs ${retorno?.ok ? "text-teal-400" : "text-rose-300"}`}>
          {retorno?.texto}
        </p>
      </td>
    </tr>
  );
}

export default function AcessoUsuarios() {
  const [usuarios, setUsuarios] = useState(null);
  const [erro, setErro] = useState(null);

  const carregar = () => {
    setErro(null);
    listarUsuariosAcesso().then(setUsuarios).catch((e) => setErro(e.message));
  };

  useEffect(carregar, []);

  const atualizar = (atualizado) =>
    setUsuarios((lista) => lista.map((u) => (u.id === atualizado.id ? atualizado : u)));

  return (
    <Card titulo="Controle de acesso por horário">
      <p className="px-5 pt-4 text-xs text-sandro-label">
        Fora da jornada o usuário não entra, e sessões abertas são encerradas na próxima ação.
        Início maior que o fim vale para turnos que cruzam a meia-noite.
      </p>

      {erro && <div className="p-5"><Erro mensagem={erro} onTentarDeNovo={carregar} /></div>}
      {!erro && !usuarios && <Carregando texto="Carregando usuários..." />}

      {usuarios && (
        <div className="overflow-x-auto">
          <table className="mt-3 w-full text-left text-sm">
            <caption className="sr-only">Usuários da empresa e suas jornadas de acesso</caption>
            <thead className="border-y border-sandro-borda/25 text-xs uppercase tracking-wider text-sandro-label">
              <tr>
                <th scope="col" className="px-5 py-3 font-medium">Usuário</th>
                <th scope="col" className="px-5 py-3 font-medium">Perfil</th>
                <th scope="col" className="px-5 py-3 font-medium">Jornada</th>
                <th scope="col" className="px-5 py-3 font-medium">Status agora</th>
                <th scope="col" className="px-5 py-3 font-medium"><span className="sr-only">Ações</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-sandro-borda/15">
              {usuarios.map((u) => <LinhaUsuario key={u.id} usuario={u} onAtualizado={atualizar} />)}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
