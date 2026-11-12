// Em produção o build garante VITE_API_URL em https (vite.config.js).
// Em desenvolvimento/homologação local, cai na API local.
const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:5000").trim().replace(/\/+$/, "");

const CHAVE_TOKEN = "sandro.token";
const CHAVE_USUARIO = "sandro.usuario";

export class ApiError extends Error {
  constructor(status, mensagem, codigo) {
    super(mensagem);
    this.status = status;
    this.codigo = codigo;
  }
}

// Callbacks registrados pelo App: voltar ao login / exigir troca de senha
let aoEncerrarSessao = () => {};
let aoExigirTrocaSenha = () => {};

export function definirAoEncerrarSessao(callback) {
  aoEncerrarSessao = callback;
}

export function definirAoExigirTrocaSenha(callback) {
  aoExigirTrocaSenha = callback;
}

function salvarSessao(token, usuario) {
  sessionStorage.setItem(CHAVE_TOKEN, token);
  sessionStorage.setItem(CHAVE_USUARIO, JSON.stringify(usuario));
}

export function lerSessao() {
  const token = sessionStorage.getItem(CHAVE_TOKEN);
  const usuario = sessionStorage.getItem(CHAVE_USUARIO);
  return token && usuario ? JSON.parse(usuario) : null;
}

export function encerrarSessao(motivo = null) {
  const tinhaSessao = sessionStorage.getItem(CHAVE_TOKEN) !== null;
  sessionStorage.removeItem(CHAVE_TOKEN);
  sessionStorage.removeItem(CHAVE_USUARIO);
  // Várias requisições podem falhar juntas: avisa o App uma única vez
  if (tinhaSessao || motivo) aoEncerrarSessao(motivo);
}

/**
 * fetch com JWT e "interceptor" de sessão:
 * - 403 HORARIO_BLOQUEADO -> expulsa para o login na hora, com a mensagem da API
 * - 401 com sessão aberta -> token expirado ou usuário removido
 */
async function requisicao(caminho, { method = "GET", body } = {}) {
  const token = sessionStorage.getItem(CHAVE_TOKEN);

  let resposta;
  try {
    resposta = await fetch(`${API_URL}${caminho}`, {
      method,
      headers: {
        ...(body !== undefined && { "Content-Type": "application/json" }),
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Não foi possível falar com o servidor. Verifique sua conexão.");
  }

  const corpo = await resposta.json().catch(() => ({}));

  if (resposta.status === 403 && corpo.error === "HORARIO_BLOQUEADO") {
    encerrarSessao(corpo.message);
    throw new ApiError(403, corpo.message, "HORARIO_BLOQUEADO");
  }

  // Sessão derrubada pelo servidor: expirou, senha trocada, conta desativada etc.
  if (resposta.status === 401 && token) {
    const motivo = corpo.erro ?? "Sua sessão expirou. Entre novamente.";
    encerrarSessao(motivo);
    throw new ApiError(401, motivo, corpo.error);
  }

  if (resposta.status === 403 && corpo.error === "TROCA_SENHA_OBRIGATORIA") {
    aoExigirTrocaSenha();
    throw new ApiError(403, corpo.erro, "TROCA_SENHA_OBRIGATORIA");
  }

  if (!resposta.ok) {
    throw new ApiError(resposta.status, corpo.erro ?? corpo.message ?? "Erro inesperado.", corpo.error);
  }

  return corpo;
}

const comQuery = (caminho, params) => {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
  ).toString();
  return query ? `${caminho}?${query}` : caminho;
};

// ---- Autenticação ---------------------------------------------------------
export async function entrar(email, senha) {
  const corpo = await requisicao("/auth/login", { method: "POST", body: { email, senha } });
  salvarSessao(corpo.token, corpo.usuario);
  return corpo.usuario;
}

/** Troca a própria senha. O servidor encerra as outras sessões e devolve um token novo. */
export async function alterarMinhaSenha(senhaAtual, novaSenha) {
  const corpo = await requisicao("/auth/senha", {
    method: "PUT",
    body: { senha_atual: senhaAtual, nova_senha: novaSenha },
  });
  salvarSessao(corpo.token, corpo.usuario);
  return corpo.usuario;
}

// ---- Usuários (somente Gestor) ---------------------------------------------
export const listarUsuarios = () => requisicao("/usuarios");
export const criarUsuario = (dados) => requisicao("/usuarios", { method: "POST", body: dados });
export const alterarUsuario = (id, dados) => requisicao(`/usuarios/${id}`, { method: "PUT", body: dados });
export const redefinirSenhaUsuario = (id) => requisicao(`/usuarios/${id}/redefinir-senha`, { method: "POST" });
export const desativarUsuario = (id) => requisicao(`/usuarios/${id}/desativar`, { method: "POST" });
export const reativarUsuario = (id) => requisicao(`/usuarios/${id}/reativar`, { method: "POST" });
export const listarAuditoria = (limite = 30) => requisicao(`/usuarios/auditoria?limite=${limite}`);

// ---- Clientes -------------------------------------------------------------
export const listarClientes = () => requisicao("/clientes");
export const buscarCliente = (id) => requisicao(`/clientes/${id}`);
export const criarCliente = (dados) => requisicao("/clientes", { method: "POST", body: dados });
export const excluirCliente = (id) => requisicao(`/clientes/${id}`, { method: "DELETE" });

// ---- Oportunidades / Funil ------------------------------------------------
export const listarOportunidades = () => requisicao("/oportunidades");
export const criarOportunidade = (dados) =>
  requisicao("/oportunidades", { method: "POST", body: dados });
export const moverOportunidade = (id, etapa) =>
  requisicao(`/oportunidades/${id}/etapa`, { method: "PATCH", body: { etapa } });

export const agendarReciclagem = (id, agendamento) =>
  requisicao(`/oportunidades/${id}/agendar-reciclagem`, { method: "POST", body: agendamento });
export const cancelarReciclagem = (id) =>
  requisicao(`/oportunidades/${id}/agendar-reciclagem`, { method: "DELETE" });

// ---- Interações -----------------------------------------------------------
export const listarInteracoes = ({ clienteId, limite } = {}) =>
  requisicao(comQuery("/interacoes", { cliente_id: clienteId, limite }));
export const criarInteracao = (dados) =>
  requisicao("/interacoes", { method: "POST", body: dados });

// ---- Tarefas / Follow-ups -------------------------------------------------
export const listarTarefas = ({ concluida } = {}) =>
  requisicao(comQuery("/tarefas", { concluida }));
export const concluirTarefa = (id) => requisicao(`/tarefas/${id}/concluir`, { method: "PATCH" });
export const atualizarTarefa = (id, dados) =>
  requisicao(`/tarefas/${id}`, { method: "PUT", body: dados });
export const buscarAlertas = () => requisicao("/tarefas/alertas");

// ---- Relatórios e painel --------------------------------------------------
export const buscarRelatorio = (periodo) => requisicao(comQuery("/relatorios/vendas", { periodo }));

// ---- Configurações --------------------------------------------------------
export const buscarConfiguracoes = () => requisicao("/configuracoes");
export const atualizarConfiguracoes = (dados) =>
  requisicao("/configuracoes", { method: "PUT", body: dados });
export const listarUsuariosAcesso = () => requisicao("/configuracoes/usuarios");
export const atualizarHorarioUsuario = (id, inicio, fim) =>
  requisicao(`/configuracoes/usuarios/${id}`, {
    method: "PUT",
    body: { hora_inicio_acesso: inicio, hora_fim_acesso: fim },
  });
