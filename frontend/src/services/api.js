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

/**
 * A API manda quantos segundos faltam para a janela de acesso acabar (pelo
 * relógio do servidor). Aqui vira um instante local: só a contagem relativa
 * importa, então relógio ou fuso errado no aparelho não adiantam nem atrasam o fim.
 */
function comFimDaJanela(usuario) {
  const segundos = usuario.segundos_ate_fim_janela;
  return { ...usuario, fim_janela_em: segundos == null ? null : Date.now() + segundos * 1000 };
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
async function requisicao(caminho, { method = "GET", body, arquivo = false } = {}) {
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

  // Download (ex.: PDF): no sucesso devolve o arquivo; erros seguem o fluxo JSON abaixo
  if (arquivo && resposta.ok) {
    const disposicao = resposta.headers.get("Content-Disposition") ?? "";
    const nome = /filename="([^"]+)"/.exec(disposicao)?.[1] ?? "sandro-crm.pdf";
    return { blob: await resposta.blob(), nome };
  }

  const corpo = await resposta.json().catch(() => ({}));
  verificarResposta(resposta.status, corpo, token);
  return corpo;
}

/**
 * Regras de sessão comuns ao fetch e ao upload com progresso (XHR).
 * Lança ApiError quando a resposta não é de sucesso.
 */
function verificarResposta(status, corpo, token) {
  if (status === 403 && corpo.error === "HORARIO_BLOQUEADO") {
    encerrarSessao(corpo.message);
    throw new ApiError(403, corpo.message, "HORARIO_BLOQUEADO");
  }

  // Sessão derrubada pelo servidor: expirou, senha trocada, conta desativada etc.
  if (status === 401 && token) {
    const motivo = corpo.erro ?? "Sua sessão expirou. Entre novamente.";
    encerrarSessao(motivo);
    throw new ApiError(401, motivo, corpo.error);
  }

  if (status === 403 && corpo.error === "TROCA_SENHA_OBRIGATORIA") {
    aoExigirTrocaSenha();
    throw new ApiError(403, corpo.erro, "TROCA_SENHA_OBRIGATORIA");
  }

  if (status === 413) {
    throw new ApiError(413, "O arquivo passa de 1 MB. Divida em arquivos menores.");
  }

  if (status < 200 || status >= 300) {
    const erro = new ApiError(status, corpo.erro ?? corpo.message ?? "Erro inesperado.", corpo.error);
    erro.corpo = corpo; // ex.: lista de erros por linha da importação (422)
    throw erro;
  }
}

/**
 * Envia um arquivo (multipart) informando o progresso do upload.
 * fetch não expõe progresso de envio; XMLHttpRequest sim.
 */
function enviarArquivo(caminho, arquivo, { onProgresso } = {}) {
  const token = sessionStorage.getItem(CHAVE_TOKEN);
  return new Promise((resolver, rejeitar) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}${caminho}`);
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.responseType = "json";
    xhr.timeout = 120_000;
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgresso) onProgresso(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      try {
        verificarResposta(xhr.status, xhr.response ?? {}, token);
        resolver(xhr.response ?? {});
      } catch (erro) {
        rejeitar(erro);
      }
    };
    const semConexao = () => rejeitar(new ApiError(0, "Não foi possível falar com o servidor. Verifique sua conexão."));
    xhr.onerror = semConexao;
    xhr.ontimeout = semConexao;
    const dados = new FormData();
    dados.append("arquivo", arquivo);
    xhr.send(dados);
  });
}

/** Baixa um arquivo da API e dispara o download no navegador. */
async function baixarArquivo(caminho, nomePadrao) {
  const { blob, nome } = await requisicao(caminho, { arquivo: true });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nome === "sandro-crm.pdf" ? nomePadrao : nome;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Libera a memória depois que o navegador iniciar o download
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  return link.download;
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
  const usuario = comFimDaJanela(corpo.usuario);
  salvarSessao(corpo.token, usuario);
  return usuario;
}

/**
 * Relê a própria conta no servidor (perfil, janela, tempo restante).
 * Fora do horário a API responde HORARIO_BLOQUEADO e o interceptor encerra a sessão.
 */
export async function obterMeusDados() {
  const usuario = comFimDaJanela(await requisicao("/auth/me"));
  if (sessionStorage.getItem(CHAVE_TOKEN)) sessionStorage.setItem(CHAVE_USUARIO, JSON.stringify(usuario));
  return usuario;
}

/** Troca a própria senha. O servidor encerra as outras sessões e devolve um token novo. */
export async function alterarMinhaSenha(senhaAtual, novaSenha) {
  const corpo = await requisicao("/auth/senha", {
    method: "PUT",
    body: { senha_atual: senhaAtual, nova_senha: novaSenha },
  });
  const usuario = comFimDaJanela(corpo.usuario);
  salvarSessao(corpo.token, usuario);
  return usuario;
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
/** Alteração parcial: envie só os campos que mudaram. */
export const alterarCliente = (id, dados) => requisicao(`/clientes/${id}`, { method: "PUT", body: dados });
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
export const criarTarefa = (dados) => requisicao("/tarefas", { method: "POST", body: dados });
export const concluirTarefa = (id) => requisicao(`/tarefas/${id}/concluir`, { method: "PATCH" });
export const atualizarTarefa = (id, dados) =>
  requisicao(`/tarefas/${id}`, { method: "PUT", body: dados });
export const buscarAlertas = () => requisicao("/tarefas/alertas");

// ---- Relatórios e painel --------------------------------------------------
export const buscarRelatorio = (periodo) => requisicao(comQuery("/relatorios/vendas", { periodo }));

/** Baixa o PDF de faturamento do período e dispara o download no navegador. */
export const baixarPdfFaturamento = (periodo) =>
  baixarArquivo(comQuery("/relatorios/vendas/pdf", { periodo }), `sandro-crm-faturamento-${periodo}.pdf`);

// ---- Planilhas de clientes --------------------------------------------------
export const baixarModeloClientes = (formato) =>
  baixarArquivo(`/clientes/modelo?formato=${formato}`, `sandro-crm-modelo-clientes.${formato}`);
export const exportarClientes = (formato) =>
  baixarArquivo(`/clientes/exportar?formato=${formato}`, `sandro-crm-clientes.${formato}`);
/** simular=true: só valida e devolve a prévia, sem gravar. */
export const importarClientes = (arquivo, { simular = false, onProgresso } = {}) =>
  enviarArquivo(`/clientes/importar${simular ? "?simular=1" : ""}`, arquivo, { onProgresso });

// ---- Recorrências -----------------------------------------------------------
export const listarRecorrencias = ({ clienteId } = {}) =>
  requisicao(comQuery("/recorrencias", { cliente_id: clienteId }));
export const criarRecorrencia = (dados) => requisicao("/recorrencias", { method: "POST", body: dados });
export const alterarRecorrencia = (id, dados) => requisicao(`/recorrencias/${id}`, { method: "PUT", body: dados });
export const ativarRecorrencia = (id, ativo) =>
  requisicao(`/recorrencias/${id}/ativo`, { method: "PATCH", body: { ativo } });
export const excluirRecorrencia = (id) => requisicao(`/recorrencias/${id}`, { method: "DELETE" });

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
