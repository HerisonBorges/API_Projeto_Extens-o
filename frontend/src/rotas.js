import { useEffect, useState } from "react";

// Roteamento por hash (#/clientes/12): sobrevive ao F5 e ao botão Voltar
// sem depender de configuração no servidor nem de biblioteca extra.
export const ROTAS = {
  dashboard: { titulo: "Dashboard", perfis: ["Gestor", "Atendimento"] },
  clientes: { titulo: "Clientes", perfis: ["Gestor", "Atendimento"] },
  funil: { titulo: "Funil de Vendas", perfis: ["Gestor", "Atendimento"] },
  followups: { titulo: "Follow-ups", perfis: ["Gestor", "Atendimento"] },
  relatorios: { titulo: "Relatórios", perfis: ["Gestor"] },
  configuracoes: { titulo: "Configurações", perfis: ["Gestor"] },
};

function lerHash() {
  const [pagina = "dashboard", id] = window.location.hash.replace(/^#\/?/, "").split("/");
  return {
    pagina: ROTAS[pagina] ? pagina : "dashboard",
    id: id && /^\d+$/.test(id) ? Number(id) : null,
  };
}

export function useRota() {
  const [rota, setRota] = useState(lerHash);

  useEffect(() => {
    const aoMudar = () => {
      setRota(lerHash());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", aoMudar);
    return () => window.removeEventListener("hashchange", aoMudar);
  }, []);

  return rota;
}

export function navegar(pagina, id = null) {
  window.location.hash = id ? `/${pagina}/${id}` : `/${pagina}`;
}

export const podeAcessar = (pagina, perfil) => ROTAS[pagina]?.perfis.includes(perfil);
