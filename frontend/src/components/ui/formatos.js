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
