import { useCallback, useEffect, useRef, useState } from "react";

import { encerrarSessao, obterMeusDados } from "../../services/api.js";
import { formatarDuracao, rotuloFuso } from "../ui/formatos.js";

const AVISO_ANTES_MS = 5 * 60_000;
// Timers atrasam ou congelam com a aba em segundo plano e o aparelho suspenso:
// além do agendamento exato, confere de tempos em tempos e ao voltar para a aba
const CONFERIR_A_CADA_MS = 30_000;
const REVALIDAR_NO_MAXIMO_A_CADA_MS = 15_000;

// Campos que, se mudarem no servidor (ex.: Gestor alterou a jornada), a tela precisa refletir
const CAMPOS_VISIVEIS = ["nome", "perfil", "empresa_nome", "hora_inicio_acesso", "hora_fim_acesso",
  "fuso_horario", "deve_trocar_senha"];

/**
 * Encerra a sessão sozinho no fim da janela de acesso, com aviso 5 min antes.
 *
 * O servidor continua sendo a autoridade (toda requisição fora do horário
 * recebe HORARIO_BLOQUEADO). Isto cobre quem está com a tela parada: sem esse
 * controle, os dados ficariam à vista depois do expediente até a próxima ação.
 * Componente separado: o relógio interno re-renderiza só ele, não o App.
 */
export default function ControleJanelaAcesso({ usuario, onAtualizarUsuario }) {
  const [fim, setFim] = useState(usuario.fim_janela_em ?? null);
  const [agora, setAgora] = useState(() => Date.now());
  // "Entendi" vale para aquele fim; se a jornada mudar, o novo fim volta a avisar
  const [dispensadoPara, setDispensadoPara] = useState(null);
  const usuarioRef = useRef(usuario);
  const aoAtualizarRef = useRef(onAtualizarUsuario);
  const consultando = useRef(false);
  const ultimaConsulta = useRef(0);

  useEffect(() => {
    usuarioRef.current = usuario;
    aoAtualizarRef.current = onAtualizarUsuario;
  });

  const aplicar = useCallback((novo) => {
    setFim(novo.fim_janela_em ?? null);
    setAgora(Date.now());
    const anterior = usuarioRef.current;
    if (CAMPOS_VISIVEIS.some((campo) => anterior[campo] !== novo[campo])) aoAtualizarRef.current(novo);
  }, []);

  // Pergunta ao servidor. `noFim`: se não der para confirmar, encerra mesmo assim (falha fechada)
  const consultar = useCallback((noFim) => {
    if (consultando.current) return;
    consultando.current = true;
    ultimaConsulta.current = Date.now();
    obterMeusDados()
      .then(aplicar)
      .catch((e) => {
        // HORARIO_BLOQUEADO e 401 já encerraram a sessão no interceptor da API
        if (e.codigo === "HORARIO_BLOQUEADO" || e.status === 401 || !noFim) return;
        const u = usuarioRef.current;
        encerrarSessao(`Seu horário de acesso terminou às ${u.hora_fim_acesso} `
          + `(${rotuloFuso(u.fuso_horario)}). Entre de novo no próximo período.`);
      })
      .finally(() => {
        consultando.current = false;
      });
  }, [aplicar]);

  // Sessão restaurada do sessionStorage pode estar desatualizada: confere ao abrir,
  // ao voltar para a aba, ao reganhar foco e ao reconectar
  useEffect(() => {
    const revalidar = () => {
      if (document.visibilityState !== "visible") return;
      if (Date.now() - ultimaConsulta.current < REVALIDAR_NO_MAXIMO_A_CADA_MS) return;
      consultar(false);
    };
    revalidar();
    document.addEventListener("visibilitychange", revalidar);
    window.addEventListener("focus", revalidar);
    window.addEventListener("online", revalidar);
    return () => {
      document.removeEventListener("visibilitychange", revalidar);
      window.removeEventListener("focus", revalidar);
      window.removeEventListener("online", revalidar);
    };
  }, [consultar]);

  // Agenda o aviso e o fim; o intervalo cobre timers atrasados pela suspensão
  useEffect(() => {
    if (fim == null) return undefined;
    const conferir = () => {
      setAgora(Date.now());
      if (Date.now() >= fim) consultar(true);
    };
    const aviso = setTimeout(() => setAgora(Date.now()), Math.max(0, fim - AVISO_ANTES_MS - Date.now()));
    const final = setTimeout(conferir, Math.max(0, fim - Date.now()) + 500);
    const intervalo = setInterval(conferir, CONFERIR_A_CADA_MS);
    document.addEventListener("visibilitychange", conferir);
    return () => {
      clearTimeout(aviso);
      clearTimeout(final);
      clearInterval(intervalo);
      document.removeEventListener("visibilitychange", conferir);
    };
  }, [fim, consultar]);

  // Cada revalidação recalcula o fim com alguns ms de diferença: "mesmo fim" = até 1 min
  const dispensado = dispensadoPara != null && Math.abs(fim - dispensadoPara) < 60_000;
  if (fim == null || dispensado || fim - agora > AVISO_ANTES_MS) return null;
  return <AvisoFimDaJanela fim={fim} usuario={usuario} onDispensar={() => setDispensadoPara(fim)} />;
}

function AvisoFimDaJanela({ fim, usuario, onDispensar }) {
  const [agora, setAgora] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const restante = Math.max(0, fim - agora);
  const minutos = Math.floor(restante / 60_000);
  const segundos = String(Math.floor((restante % 60_000) / 1000)).padStart(2, "0");

  return (
    <div
      className="fixed inset-x-3 bottom-[calc(0.75rem+env(safe-area-inset-bottom))] z-40 rounded-xl border
                 border-amber-400/50 bg-[#2a2208] p-4 text-sm text-amber-100 shadow-lg shadow-black/40
                 md:left-auto md:right-6 md:bottom-6 md:max-w-sm"
    >
      {/* role=alert anuncia uma vez ao aparecer; o cronômetro fica fora dele para não repetir a cada segundo */}
      <p role="alert" className="font-semibold text-amber-50">
        Seu horário de acesso termina às {usuario.hora_fim_acesso} ({rotuloFuso(usuario.fuso_horario)}).
        <span className="sr-only"> A sessão será encerrada em cerca de {formatarDuracao(restante)}.</span>
      </p>
      <p className="mt-1" aria-hidden="true">
        A sessão será encerrada em <span className="font-bold tabular-nums">{minutos}:{segundos}</span>.
        Salve o que estiver fazendo.
      </p>
      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={onDispensar}
          className="rounded-lg border border-amber-400/40 px-3 py-1.5 text-xs font-medium text-amber-100
                     hover:bg-amber-400/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-300"
        >
          Entendi
        </button>
      </div>
    </div>
  );
}
