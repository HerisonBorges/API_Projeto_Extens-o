export const ETAPAS = ["Prospecção", "Qualificação", "Proposta", "Negociação", "Fechado"];
export const ETAPA_FINAL = "Fechado";
export const TIPOS_INTERACAO = ["Ligação", "WhatsApp", "E-mail", "Reunião"];

export const formatarMoeda = (valor) =>
  Number(valor ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export const formatarMoedaCurta = (valor) =>
  Number(valor ?? 0).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    notation: "compact",
    maximumFractionDigits: 1,
  });

export const formatarPercentual = (valor) =>
  `${Number(valor ?? 0).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;

// "AAAA-MM-DD" é data de calendário: interpretar como local, nunca como UTC
function dataLocal(iso) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) {
    const [a, m, d] = iso.split("-").map(Number);
    return new Date(a, m - 1, d);
  }
  return new Date(iso);
}

export const formatarData = (iso) =>
  iso ? dataLocal(iso).toLocaleDateString("pt-BR", { dateStyle: "short" }) : "—";

export const formatarDataHora = (iso) =>
  iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";

export function formatarMes(anoMes) {
  const [ano, mes] = anoMes.split("-").map(Number);
  return new Date(ano, mes - 1, 1)
    .toLocaleDateString("pt-BR", { month: "short", year: "2-digit" })
    .replace(".", "");
}

function isoLocal(data) {
  const mes = String(data.getMonth() + 1).padStart(2, "0");
  const dia = String(data.getDate()).padStart(2, "0");
  return `${data.getFullYear()}-${mes}-${dia}`;
}

export const hojeISO = () => isoLocal(new Date());

// "AAAA-MM-DD" daqui a N dias, no calendário local
export function daquiDiasISO(dias) {
  const data = new Date();
  data.setDate(data.getDate() + dias);
  return isoLocal(data);
}

export function amanhaISO() {
  const data = new Date();
  data.setDate(data.getDate() + 1);
  return isoLocal(data);
}

// Dias de calendário de hoje até a data (negativo = passado)
export function diasAte(isoData) {
  const alvo = dataLocal(isoData);
  const hoje = dataLocal(hojeISO());
  return Math.round((alvo - hoje) / 86_400_000);
}

// Dias inteiros desde um timestamp
export const diasDesde = (isoTimestamp) =>
  Math.max(0, Math.floor((Date.now() - new Date(isoTimestamp)) / 86_400_000));

export const plural = (n, singular, pluralTexto) => `${n} ${n === 1 ? singular : pluralTexto}`;

// Duração legível: "45 min", "5 h", "3 dias" (arredonda para cima: "vence em 1 min", nunca "0")
export function formatarDuracao(ms) {
  const minutos = Math.max(1, Math.ceil(Math.abs(ms) / 60_000));
  if (minutos < 60) return `${minutos} min`;
  const horas = Math.round(minutos / 60);
  if (horas < 48) return `${horas} h`;
  return plural(Math.round(horas / 24), "dia", "dias");
}

// Nome amigável do fuso em que a API avalia a janela de acesso
const NOMES_FUSO = { "America/Sao_Paulo": "horário de Brasília" };
export const rotuloFuso = (fuso) => NOMES_FUSO[fuso] ?? fuso ?? "horário da empresa";

export function descreverJanela(usuario) {
  if (!usuario.hora_inicio_acesso || !usuario.hora_fim_acesso) return "Acesso sem restrição de horário";
  return `Acesso das ${usuario.hora_inicio_acesso} às ${usuario.hora_fim_acesso} (${rotuloFuso(usuario.fuso_horario)})`;
}

// ---- Recorrências -----------------------------------------------------------
// ISO 8601, igual ao servidor: 1 = segunda ... 7 = domingo
export const DIAS_SEMANA = [
  { valor: 1, rotulo: "Segunda-feira" },
  { valor: 2, rotulo: "Terça-feira" },
  { valor: 3, rotulo: "Quarta-feira" },
  { valor: 4, rotulo: "Quinta-feira" },
  { valor: 5, rotulo: "Sexta-feira" },
  { valor: 6, rotulo: "Sábado" },
  { valor: 7, rotulo: "Domingo" },
];

export function descreverRecorrencia({ frequencia, dia_semana: diaSemana, dia_mes: diaMes }) {
  if (frequencia === "semanal") {
    const dia = DIAS_SEMANA.find((d) => d.valor === Number(diaSemana))?.rotulo.toLowerCase() ?? "?";
    return Number(diaSemana) >= 6 ? `Todo ${dia}` : `Toda ${dia}`;
  }
  return `Todo dia ${diaMes}${Number(diaMes) > 28 ? " (ou o último dia do mês)" : ""}`;
}

/**
 * Prévia da próxima data, com a mesma regra do servidor (recorrencia.py).
 * O servidor recalcula no fuso da empresa: isto é só para a pessoa conferir.
 */
export function proximaOcorrenciaISO({ frequencia, dia_semana: diaSemana, dia_mes: diaMes }, aPartirDe = new Date()) {
  const inicio = new Date(aPartirDe.getFullYear(), aPartirDe.getMonth(), aPartirDe.getDate());
  if (frequencia === "semanal") {
    const hoje = inicio.getDay() === 0 ? 7 : inicio.getDay();
    inicio.setDate(inicio.getDate() + ((Number(diaSemana) - hoje + 7) % 7));
    return isoLocal(inicio);
  }
  const noMes = (ano, mes) => new Date(ano, mes, Math.min(Number(diaMes), new Date(ano, mes + 1, 0).getDate()));
  const candidata = noMes(inicio.getFullYear(), inicio.getMonth());
  return isoLocal(candidata >= inicio ? candidata : noMes(inicio.getFullYear(), inicio.getMonth() + 1));
}

export function formatarDocumento(documento) {
  if (!documento) return null;
  if (documento.length === 11) {
    return `${documento.slice(0, 3)}.${documento.slice(3, 6)}.${documento.slice(6, 9)}-${documento.slice(9)}`;
  }
  return `${documento.slice(0, 2)}.${documento.slice(2, 5)}.${documento.slice(5, 8)}/${documento.slice(8, 12)}-${documento.slice(12)}`;
}
