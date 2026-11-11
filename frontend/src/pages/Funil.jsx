import { useCallback, useEffect, useState } from "react";

import ReciclagemModal from "../components/reciclagem/ReciclagemModal.jsx";
import Botao from "../components/ui/Botao.jsx";
import { Carregando, Erro } from "../components/ui/Estado.jsx";
import StatusBadge from "../components/ui/StatusBadge.jsx";
import {
  ETAPAS,
  ETAPA_FINAL,
  diasDesde,
  formatarData,
  formatarDataHora,
  formatarMoeda,
  plural,
} from "../components/ui/formatos.js";
import { cancelarReciclagem, listarClientes, listarOportunidades, moverOportunidade } from "../services/api.js";

function CardOportunidade({ op, cliente, onMover, onReciclar, onCancelar, movendo, arrastando, onArrastar }) {
  const indice = ETAPAS.indexOf(op.etapa);
  const final = op.etapa === ETAPA_FINAL;
  const dias = op.etapa_atualizada_em ? diasDesde(op.etapa_atualizada_em) : null;

  return (
    <li
      draggable={!movendo}
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", String(op.id));
        e.dataTransfer.effectAllowed = "move";
        onArrastar(op.id);
      }}
      onDragEnd={() => onArrastar(null)}
      aria-busy={movendo || undefined}
      className={`cursor-grab rounded-lg border border-sandro-borda/25 bg-sandro-fundo/70 p-3 shadow-sm transition
                  active:cursor-grabbing ${arrastando ? "opacity-40" : ""} ${movendo ? "opacity-60" : ""}`}
    >
      <p className="text-sm font-semibold text-white">{op.titulo}</p>
      <p className="mt-1 text-sm font-bold text-sandro-acento">{formatarMoeda(op.valor)}</p>

      <dl className="mt-2 space-y-0.5 text-xs">
        <div className="flex gap-1">
          <dt className="text-sandro-label">Cliente:</dt>
          <dd className="truncate text-slate-200">
            {cliente ? <a href={`#/clientes/${cliente.id}`} className="hover:underline">{cliente.nome}</a> : "—"}
          </dd>
        </div>
        <div className="flex gap-1">
          <dt className="text-sandro-label">Responsável:</dt>
          <dd className="truncate text-slate-200">{op.responsavel_nome ?? "—"}</dd>
        </div>
      </dl>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {dias !== null && !final && (
          <StatusBadge tom={dias >= 7 ? "pendente" : "neutro"}>
            {dias === 0 ? "Movido hoje" : `${plural(dias, "dia", "dias")} na etapa`}
          </StatusBadge>
        )}
        {op.status_reciclagem === "pendente" && (
          <StatusBadge tom="pendente" icone="⏱">Reciclagem · {formatarData(op.data_reciclagem_agendada)}</StatusBadge>
        )}
        {op.status_reciclagem === "processado" && <StatusBadge tom="permitido" icone="↻">Reciclada</StatusBadge>}
        {op.oportunidade_origem_id && <StatusBadge tom="azul" icone="↺">Pós-venda</StatusBadge>}
      </div>

      <div className="mt-3 flex items-center justify-between gap-2">
        <Botao tamanho="sm" variante="fantasma" disabled={indice === 0 || movendo}
               onClick={() => onMover(op, ETAPAS[indice - 1])}
               aria-label={`Voltar ${op.titulo} para ${ETAPAS[indice - 1] ?? "etapa anterior"}`}>
          ←
        </Botao>

        {final ? (
          op.status_reciclagem === "pendente" ? (
            <Botao tamanho="sm" variante="fantasma" onClick={() => onCancelar(op)}
                   aria-label={`Cancelar reciclagem de ${op.titulo}`}>
              Cancelar reciclagem
            </Botao>
          ) : op.status_reciclagem !== "processado" && (
            <Botao tamanho="sm" variante="contorno" onClick={() => onReciclar(op)}
                   aria-label={`Reciclar lead: ${op.titulo}`}>
              ↻ Reciclar Lead
            </Botao>
          )
        ) : (
          <Botao tamanho="sm" variante="primario" carregando={movendo} textoCarregando="Movendo..."
                 onClick={() => onMover(op, ETAPAS[indice + 1])}
                 aria-label={`Avançar ${op.titulo} para ${ETAPAS[indice + 1]}`}>
            Avançar →
          </Botao>
        )}
      </div>
    </li>
  );
}

export default function Funil({ versao }) {
  const [ops, setOps] = useState(null);
  const [clientes, setClientes] = useState({});
  const [erro, setErro] = useState(null);
  const [movendoId, setMovendoId] = useState(null);
  const [arrastandoId, setArrastandoId] = useState(null);
  const [colunaAlvo, setColunaAlvo] = useState(null);
  const [reciclando, setReciclando] = useState(null);
  const [anuncio, setAnuncio] = useState("");
  const [falha, setFalha] = useState(null);

  const carregar = useCallback(async () => {
    setErro(null);
    try {
      const [listaOps, listaClientes] = await Promise.all([listarOportunidades(), listarClientes()]);
      setOps(listaOps);
      setClientes(Object.fromEntries(listaClientes.map((c) => [c.id, c])));
    } catch (e) {
      setErro(e.message);
    }
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar, versao]);

  async function mover(op, etapa) {
    if (!etapa || etapa === op.etapa) return;
    setFalha(null);
    setMovendoId(op.id);
    const anterior = ops;
    // Otimista: move já, desfaz se a API recusar
    setOps((lista) => lista.map((o) =>
      o.id === op.id ? { ...o, etapa, etapa_atualizada_em: new Date().toISOString() } : o));
    try {
      await moverOportunidade(op.id, etapa);
      setAnuncio(`${op.titulo} movida para ${etapa}.`);
      // Sair de Fechado cancela reciclagem pendente: recarrega para refletir
      if (op.etapa === ETAPA_FINAL) carregar();
    } catch (e) {
      setOps(anterior);
      setFalha(`Não foi possível mover "${op.titulo}": ${e.message}`);
    } finally {
      setMovendoId(null);
    }
  }

  async function cancelar(op) {
    try {
      await cancelarReciclagem(op.id);
      setAnuncio(`Reciclagem de ${op.titulo} cancelada.`);
      carregar();
    } catch (e) {
      setFalha(e.message);
    }
  }

  if (erro) return <Erro mensagem={erro} onTentarDeNovo={carregar} />;
  if (!ops) return <Carregando texto="Carregando funil..." />;

  return (
    <div className="space-y-4">
      <p className="text-sm text-sandro-label">
        Arraste os cards entre as colunas ou use os botões ← e →. Vendas em Fechado podem ser recicladas.
      </p>
      <p role="status" aria-live="polite" className="sr-only">{anuncio}</p>
      <Erro mensagem={falha} />

      <div className="flex gap-4 overflow-x-auto pb-4">
        {ETAPAS.map((etapa) => {
          const daEtapa = ops.filter((o) => o.etapa === etapa);
          const total = daEtapa.reduce((s, o) => s + o.valor, 0);
          const alvo = colunaAlvo === etapa;

          return (
            <section
              key={etapa}
              aria-labelledby={`coluna-${etapa}`}
              onDragOver={(e) => {
                e.preventDefault();
                setColunaAlvo(etapa);
              }}
              onDragLeave={(e) => {
                if (!e.currentTarget.contains(e.relatedTarget)) setColunaAlvo(null);
              }}
              onDrop={(e) => {
                e.preventDefault();
                setColunaAlvo(null);
                const op = ops.find((o) => o.id === Number(e.dataTransfer.getData("text/plain")));
                if (op) mover(op, etapa);
              }}
              className={`flex w-72 shrink-0 flex-col rounded-xl border bg-sandro-painel/60 transition
                          ${alvo ? "border-sandro-acento" : "border-sandro-borda/25"}`}
            >
              <header className="border-b border-sandro-borda/20 px-4 py-3">
                <div className="flex items-center justify-between">
                  <h2 id={`coluna-${etapa}`} className="text-sm font-semibold text-white">{etapa}</h2>
                  <span className="rounded-full bg-sandro-suporte/50 px-2 py-0.5 text-xs text-sandro-label">
                    {daEtapa.length}
                  </span>
                </div>
                <p className="mt-0.5 text-xs tabular-nums text-sandro-label">{formatarMoeda(total)}</p>
              </header>

              <ul className="flex min-h-32 flex-1 flex-col gap-3 p-3">
                {daEtapa.length === 0 && (
                  <li className="rounded-lg border border-dashed border-sandro-borda/30 px-3 py-6 text-center text-xs text-sandro-label">
                    Solte um card aqui
                  </li>
                )}
                {daEtapa.map((op) => (
                  <CardOportunidade
                    key={op.id}
                    op={op}
                    cliente={clientes[op.cliente_id]}
                    movendo={movendoId === op.id}
                    arrastando={arrastandoId === op.id}
                    onArrastar={setArrastandoId}
                    onMover={mover}
                    onReciclar={setReciclando}
                    onCancelar={cancelar}
                  />
                ))}
              </ul>
            </section>
          );
        })}
      </div>

      {reciclando && (
        <ReciclagemModal
          oportunidade={reciclando}
          onFechar={() => setReciclando(null)}
          onAgendado={(r) => {
            setAnuncio(`Reciclagem de ${reciclando.titulo} agendada para ${formatarDataHora(r.data_reciclagem_agendada)}.`);
            setReciclando(null);
            carregar();
          }}
        />
      )}
    </div>
  );
}
