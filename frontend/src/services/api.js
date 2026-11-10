const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:5000";

const CHAVE_TOKEN = "sandro.token";
const CHAVE_USUARIO = "sandro.usuario";

export class ApiError extends Error {
  constructor(status, mensagem, codigo) {
    super(mensagem);
    this.status = status;
    this.codigo = codigo;
  }
}

// Callback registrado pelo App para voltar à tela de login
let aoEncerrarSessao = () => {};

export function definirAoEncerrarSessao(callback) {
  aoEncerrarSessao = callback;
}

export function lerSessao() {
  const token = sessionStorage.getItem(CHAVE_TOKEN);
  const usuario = sessionStorage.getItem(CHAVE_USUARIO);
  return token && usuario ? JSON.parse(usuario) : null;
}

export function encerrarSessao(motivo = null) {
  sessionStorage.removeItem(CHAVE_TOKEN);
  sessionStorage.removeItem(CHAVE_USUARIO);
  aoEncerrarSessao(motivo);
}

/**
 * fetch com JWT e "interceptor" de sessão:
 * - 403 HORARIO_BLOQUEADO -> expulsa para o login na hora, com a mensagem da API
 * - 401 com sessão aberta -> token expirado ou usuário removido
 */
async function requisicao(caminho, { method = "GET", body } = {}) {
  const token = sessionStorage.getItem(CHAVE_TOKEN);

  const resposta = await fetch(`${API_URL}${caminho}`, {
    method,
    headers: {
      ...(body !== undefined && { "Content-Type": "application/json" }),
      ...(token && { Authorization: `Bearer ${token}` }),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const corpo = await resposta.json().catch(() => ({}));

  if (resposta.status === 403 && corpo.error === "HORARIO_BLOQUEADO") {
    encerrarSessao(corpo.message);
    throw new ApiError(403, corpo.message, "HORARIO_BLOQUEADO");
  }

  if (resposta.status === 401 && token) {
    encerrarSessao("Sua sessão expirou. Entre novamente.");
    throw new ApiError(401, "Sessão expirada.");
  }

  if (!resposta.ok) {
    throw new ApiError(resposta.status, corpo.erro ?? corpo.message ?? "Erro inesperado.");
  }

  return corpo;
}

export async function entrar(email, senha) {
  const corpo = await requisicao("/auth/login", { method: "POST", body: { email, senha } });
  sessionStorage.setItem(CHAVE_TOKEN, corpo.token);
  sessionStorage.setItem(CHAVE_USUARIO, JSON.stringify(corpo.usuario));
  return corpo.usuario;
}

export const buscarDashboard = (empresaId) => requisicao(`/dashboard/${empresaId}`);
export const listarOportunidades = () => requisicao("/oportunidades");
export const listarClientes = () => requisicao("/clientes");

export const agendarReciclagem = (id, agendamento) =>
  requisicao(`/oportunidades/${id}/agendar-reciclagem`, { method: "POST", body: agendamento });

export const cancelarReciclagem = (id) =>
  requisicao(`/oportunidades/${id}/agendar-reciclagem`, { method: "DELETE" });

export const listarUsuariosAcesso = () => requisicao("/configuracoes/usuarios");

export const atualizarHorarioUsuario = (id, inicio, fim) =>
  requisicao(`/configuracoes/usuarios/${id}`, {
    method: "PUT",
    body: { hora_inicio_acesso: inicio, hora_fim_acesso: fim },
  });
