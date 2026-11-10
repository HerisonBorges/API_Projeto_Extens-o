export const formatarMoeda = (valor) =>
  Number(valor ?? 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export const formatarData = (iso) =>
  iso ? new Date(iso).toLocaleDateString("pt-BR", { dateStyle: "short" }) : "—";

export const formatarDataHora = (iso) =>
  iso
    ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })
    : "—";

// "AAAA-MM-DD" de amanhã no fuso do navegador (mínimo do input type=date)
export function amanhaISO() {
  const data = new Date();
  data.setDate(data.getDate() + 1);
  const mes = String(data.getMonth() + 1).padStart(2, "0");
  const dia = String(data.getDate()).padStart(2, "0");
  return `${data.getFullYear()}-${mes}-${dia}`;
}

export const ETAPA_FINAL = "Fechado";
