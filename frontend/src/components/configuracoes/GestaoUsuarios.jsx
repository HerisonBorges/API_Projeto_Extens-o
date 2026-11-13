import { useCallback, useEffect, useState } from "react";

import {
  alterarUsuario,
  criarUsuario,
  desativarUsuario,
  listarAuditoria,
  listarUsuarios,
  reativarUsuario,
  redefinirSenhaUsuario,
} from "../../services/api.js";
import Botao from "../ui/Botao.jsx";
import Card from "../ui/Card.jsx";
import Campo, { classeEntrada } from "../ui/Campo.jsx";
import { Aviso, Carregando, Erro, Vazio } from "../ui/Estado.jsx";
import Modal from "../ui/Modal.jsx";
import StatusBadge from "../ui/StatusBadge.jsx";
import { formatarDataHora } from "../ui/formatos.js";

const PERFIS = ["Atendimento", "Gestor"];

const ROTULO_ACAO = {
  usuario_criado: "criou a conta de",
  usuario_alterado: "alterou os dados de",
  perfil_alterado: "alterou o perfil de",
  senha_redefinida: "redefiniu a senha de",
  senha_alterada: "trocou a própria senha",
  usuario_desativado: "desativou",
  usuario_reativado: "reativou",
  login_bloqueado: "bloqueio automático por tentativas de login:",
};

function Situacao({ u }) {
  if (!u.ativo) return <StatusBadge tom="neutro" icone="○">Desativado</StatusBadge>;
  if (u.bloqueado) return <StatusBadge tom="bloqueado" icone="■">Bloqueado</StatusBadge>;
  if (u.deve_trocar_senha) return <StatusBadge tom="pendente" icone="⏱">Aguardando 1º acesso</StatusBadge>;
  return <StatusBadge tom="permitido" icone="●">Ativo</StatusBadge>;
}

/** Mostra a senha temporária UMA vez, com cópia e orientação de entrega. */
function SenhaTemporaria({ resultado, onFechar }) {
  const [copiado, setCopiado] = useState(false);

  async function copiar() {
    try {
      await navigator.clipboard.writeText(resultado.senha_temporaria);
      setCopiado(true);
    } catch {
      setCopiado(false);
    }
  }

  return (
    <Modal titulo="Senha temporária gerada" descricao={`Para ${resultado.usuario.nome} (${resultado.usuario.email})`}
           onFechar={onFechar}>
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <code aria-label="Senha temporária"
                className="flex-1 select-all rounded-lg border border-sandro-acento/40 bg-sandro-fundo px-4 py-3
                           font-mono text-lg tracking-wider text-white">
            {resultado.senha_temporaria}
          </code>
          <Botao variante="contorno" onClick={copiar}>{copiado ? "Copiada" : "Copiar"}</Botao>
        </div>
        <p role="status" className="sr-only">{copiado ? "Senha copiada." : ""}</p>
        <ul className="list-disc space-y-1 pl-5 text-xs text-slate-300">
          <li>{resultado.aviso}</li>
          <li>No primeiro acesso, a pessoa será obrigada a criar uma senha própria.</li>
        </ul>
        <div className="flex justify-end">
          <Botao variante="primario" onClick={onFechar}>Já entreguei a senha</Botao>
        </div>
      </div>
    </Modal>
  );
}

function FormularioUsuario({ usuario, ehVoceMesmo, onSalvar, onFechar }) {
  const [form, setForm] = useState({
    nome: usuario?.nome ?? "",
    email: usuario?.email ?? "",
    perfil: usuario?.perfil ?? "Atendimento",
  });
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);
  const alterar = (campo) => (e) => setForm((f) => ({ ...f, [campo]: e.target.value }));

  async function salvar(e) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await onSalvar(form);
    } catch (erroApi) {
      setErro(erroApi.message);
      setEnviando(false);
    }
  }

  return (
    <Modal titulo={usuario ? "Editar usuário" : "Novo usuário"}
           descricao={usuario ? undefined : "A conta é criada com uma senha temporária, que você entrega à pessoa."}
           onFechar={onFechar} bloqueado={enviando}>
      <form onSubmit={salvar} className="space-y-4">
        <Campo rotulo="Nome *">
          {(p) => <input {...p} required maxLength={150} value={form.nome} onChange={alterar("nome")} className={classeEntrada} />}
        </Campo>
        <Campo rotulo="E-mail de acesso *">
          {(p) => <input {...p} type="email" required maxLength={150} value={form.email} onChange={alterar("email")} className={classeEntrada} />}
        </Campo>
        <Campo rotulo="Perfil" ajuda={ehVoceMesmo ? "Você não pode alterar o próprio perfil." :
          "Gestor administra usuários, relatórios e configurações. Atendimento opera o dia a dia."}>
          {(p) => (
            <select {...p} value={form.perfil} onChange={alterar("perfil")} disabled={ehVoceMesmo} className={classeEntrada}>
              {PERFIS.map((perfil) => <option key={perfil} value={perfil}>{perfil}</option>)}
            </select>
          )}
        </Campo>

        {erro && <p role="alert" className="rounded-lg bg-rose-950/80 px-3 py-2 text-sm text-rose-300">{erro}</p>}

        <div className="flex justify-end gap-3 pt-1">
          <Botao variante="fantasma" onClick={onFechar} disabled={enviando}>Cancelar</Botao>
          <Botao variante="primario" type="submit" carregando={enviando} textoCarregando="Salvando...">
            {usuario ? "Salvar alterações" : "Criar usuário"}
          </Botao>
        </div>
      </form>
    </Modal>
  );
}

const CONFIRMACOES = {
  redefinir: {
    titulo: "Redefinir senha?",
    texto: (u) => `A senha atual de ${u.nome} deixa de funcionar e as sessões abertas são encerradas. Uma senha temporária será gerada.`,
    botao: "Redefinir senha",
    executar: (u) => redefinirSenhaUsuario(u.id),
  },
  desativar: {
    titulo: "Desativar usuário?",
    texto: (u) => `${u.nome} perde o acesso imediatamente, inclusive sessões abertas. O histórico é mantido e a conta pode ser reativada.`,
    botao: "Desativar",
    executar: (u) => desativarUsuario(u.id),
  },
  reativar: {
    titulo: "Reativar usuário?",
    texto: (u) => `${u.nome} volta a ter acesso com uma senha temporária nova. A senha antiga não volta a valer.`,
    botao: "Reativar",
    executar: (u) => reativarUsuario(u.id),
  },
};

function Confirmacao({ tipo, usuario, onConcluido, onFechar }) {
  const config = CONFIRMACOES[tipo];
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);

  async function confirmar() {
    setEnviando(true);
    setErro(null);
    try {
      onConcluido(await config.executar(usuario));
    } catch (e) {
      setErro(e.message);
      setEnviando(false);
    }
  }

  return (
    <Modal titulo={config.titulo} descricao={config.texto(usuario)} onFechar={onFechar} bloqueado={enviando}>
      {erro && <p role="alert" className="mb-4 rounded-lg bg-rose-950/80 px-3 py-2 text-sm text-rose-300">{erro}</p>}
      <div className="flex justify-end gap-3">
        <Botao variante="fantasma" onClick={onFechar} disabled={enviando}>Cancelar</Botao>
        <Botao variante={tipo === "desativar" ? "perigo" : "primario"} onClick={confirmar}
               carregando={enviando} textoCarregando="Aguarde...">
          {config.botao}
        </Botao>
      </div>
    </Modal>
  );
}

function Auditoria({ versao }) {
  const [eventos, setEventos] = useState(null);
  const [erro, setErro] = useState(null);

  useEffect(() => {
    listarAuditoria(20).then(setEventos).catch((e) => setErro(e.message));
  }, [versao]);

  return (
    <Card titulo="Histórico de acessos e permissões">
      {erro && <div className="p-5"><Erro mensagem={erro} /></div>}
      {!erro && !eventos && <Carregando />}
      {eventos?.length === 0 && <Vazio>Nenhum evento registrado ainda.</Vazio>}
      {eventos?.length > 0 && (
        <ol className="divide-y divide-sandro-borda/15">
          {eventos.map((e) => (
            <li key={e.id} className="flex flex-wrap items-baseline justify-between gap-2 px-5 py-2.5 text-sm">
              <span className="text-slate-200">
                <strong className="font-medium text-white">{e.ator_nome ?? "Sistema"}</strong>{" "}
                {ROTULO_ACAO[e.acao] ?? e.acao}{" "}
                {e.acao !== "senha_alterada" && <strong className="font-medium text-white">{e.alvo_nome ?? "—"}</strong>}
                {e.acao === "perfil_alterado" && ` (${e.detalhes.de} → ${e.detalhes.para})`}
              </span>
              <time dateTime={e.criado_em} className="text-xs text-sandro-label">{formatarDataHora(e.criado_em)}</time>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

export default function GestaoUsuarios({ usuarioLogado }) {
  const [usuarios, setUsuarios] = useState(null);
  const [erro, setErro] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [editando, setEditando] = useState(null); // null | "novo" | usuario
  const [confirmando, setConfirmando] = useState(null); // { tipo, usuario }
  const [senhaGerada, setSenhaGerada] = useState(null);
  const [versao, setVersao] = useState(0);

  const carregar = useCallback(() => {
    setErro(null);
    listarUsuarios().then(setUsuarios).catch((e) => setErro(e.message));
  }, []);

  useEffect(carregar, [carregar, versao]);
  const atualizar = () => setVersao((v) => v + 1);

  async function salvarUsuario(form) {
    if (editando === "novo") {
      const resultado = await criarUsuario(form);
      setEditando(null);
      setSenhaGerada(resultado);
      setAviso(`Conta de ${resultado.usuario.nome} criada.`);
    } else {
      const mudancas = Object.fromEntries(Object.entries(form).filter(([k, v]) => v !== editando[k]));
      const resultado = await alterarUsuario(editando.id, mudancas);
      setEditando(null);
      setAviso(`Dados de ${resultado.usuario.nome} atualizados.`);
    }
    atualizar();
  }

  return (
    <div className="space-y-6">
      <Card
        titulo="Usuários da equipe"
        acao={<Botao variante="primario" tamanho="sm" onClick={() => setEditando("novo")}>+ Novo usuário</Botao>}
      >
        <div className="px-5 pt-3"><Aviso mensagem={aviso} /></div>
        {erro && <div className="p-5"><Erro mensagem={erro} onTentarDeNovo={carregar} /></div>}
        {!erro && !usuarios && <Carregando texto="Carregando usuários..." />}

        {usuarios && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Usuários da empresa, perfil e situação da conta</caption>
              <thead className="border-y border-sandro-borda/25 text-xs uppercase tracking-wider text-sandro-label">
                <tr>
                  <th scope="col" className="px-5 py-3 font-medium">Usuário</th>
                  <th scope="col" className="px-5 py-3 font-medium">Perfil</th>
                  <th scope="col" className="px-5 py-3 font-medium">Situação</th>
                  <th scope="col" className="px-5 py-3 font-medium">Último acesso</th>
                  <th scope="col" className="px-5 py-3 font-medium"><span className="sr-only">Ações</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sandro-borda/15">
                {usuarios.map((u) => {
                  const voce = u.id === usuarioLogado.id;
                  return (
                    <tr key={u.id} className={`text-slate-200 ${u.ativo ? "" : "opacity-70"}`}>
                      <td className="px-5 py-3">
                        <p className="font-medium text-white">{u.nome}{voce && <span className="ml-2 text-xs text-sandro-label">(você)</span>}</p>
                        <p className="text-xs text-sandro-label">{u.email}</p>
                      </td>
                      <td className="px-5 py-3">{u.perfil}</td>
                      <td className="px-5 py-3"><Situacao u={u} /></td>
                      <td className="px-5 py-3 text-xs text-sandro-label">
                        {u.ultimo_login_em ? formatarDataHora(u.ultimo_login_em) : "Nunca"}
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex flex-wrap justify-end gap-2">
                          <Botao tamanho="sm" variante="secundario" onClick={() => setEditando(u)}
                                 aria-label={`Editar ${u.nome}`}>Editar</Botao>
                          {!voce && u.ativo && (
                            <>
                              <Botao tamanho="sm" variante="contorno" aria-label={`Redefinir senha de ${u.nome}`}
                                     onClick={() => setConfirmando({ tipo: "redefinir", usuario: u })}>
                                Redefinir senha
                              </Botao>
                              <Botao tamanho="sm" variante="perigo" aria-label={`Desativar ${u.nome}`}
                                     onClick={() => setConfirmando({ tipo: "desativar", usuario: u })}>
                                Desativar
                              </Botao>
                            </>
                          )}
                          {!voce && !u.ativo && (
                            <Botao tamanho="sm" variante="contorno" aria-label={`Reativar ${u.nome}`}
                                   onClick={() => setConfirmando({ tipo: "reativar", usuario: u })}>
                              Reativar
                            </Botao>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Auditoria versao={versao} />

      {editando && (
        <FormularioUsuario
          usuario={editando === "novo" ? null : editando}
          ehVoceMesmo={editando !== "novo" && editando.id === usuarioLogado.id}
          onSalvar={salvarUsuario}
          onFechar={() => setEditando(null)}
        />
      )}

      {confirmando && (
        <Confirmacao
          tipo={confirmando.tipo}
          usuario={confirmando.usuario}
          onFechar={() => setConfirmando(null)}
          onConcluido={(resultado) => {
            setConfirmando(null);
            setAviso(resultado.mensagem);
            if (resultado.senha_temporaria) setSenhaGerada(resultado);
            atualizar();
          }}
        />
      )}

      {senhaGerada && <SenhaTemporaria resultado={senhaGerada} onFechar={() => setSenhaGerada(null)} />}
    </div>
  );
}
