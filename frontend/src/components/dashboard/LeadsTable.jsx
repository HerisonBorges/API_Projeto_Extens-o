import GlassCard from "../ui/GlassCard.jsx";
import StatusBadge from "../ui/StatusBadge.jsx";
import { ETAPA_FINAL, formatarData, formatarMoeda } from "../ui/formatos.js";

function CelulaReciclagem({ oportunidade }) {
  const { status_reciclagem: status, data_reciclagem_agendada: data } = oportunidade;

  if (status === "pendente") {
    return <StatusBadge tom="pendente" icone="⏱">Agendada · {formatarData(data)}</StatusBadge>;
  }
  if (status === "processado") {
    return <StatusBadge tom="permitido" icone="↻">Reciclada</StatusBadge>;
  }
  if (oportunidade.oportunidade_origem_id) {
    return <StatusBadge icone="↺">Origem #{oportunidade.oportunidade_origem_id}</StatusBadge>;
  }
  return <span className="text-kindra-label">—</span>;
}

export default function LeadsTable({ oportunidades, clientes, onReciclar, onCancelar, ocupadoId }) {
  const nomeCliente = (id) => clientes.find((c) => c.id === id)?.nome ?? "—";

  return (
    <GlassCard className="overflow-hidden p-0">
      <div className="flex items-center justify-between px-5 py-4">
        <h2 className="text-base font-semibold text-white">Leads e oportunidades</h2>
        <span className="text-xs text-kindra-label">{oportunidades.length} registros</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">
            Oportunidades da empresa, com etapa do funil, valor e status de reciclagem
          </caption>
          <thead className="border-y border-kindra-borda/30 text-xs uppercase tracking-wider text-kindra-label">
            <tr>
              <th scope="col" className="px-5 py-3 font-medium">Oportunidade</th>
              <th scope="col" className="px-5 py-3 font-medium">Cliente</th>
              <th scope="col" className="px-5 py-3 font-medium">Etapa</th>
              <th scope="col" className="px-5 py-3 text-right font-medium">Valor</th>
              <th scope="col" className="px-5 py-3 font-medium">Reciclagem</th>
              <th scope="col" className="px-5 py-3 font-medium"><span className="sr-only">Ações</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-kindra-borda/20">
            {oportunidades.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-kindra-label">
                  Nenhuma oportunidade cadastrada ainda.
                </td>
              </tr>
            )}

            {oportunidades.map((op) => {
              const final = op.etapa === ETAPA_FINAL;
              const pendente = op.status_reciclagem === "pendente";
              const ocupado = ocupadoId === op.id;

              return (
                <tr key={op.id} className="text-slate-200 hover:bg-kindra-suporte/20">
                  <td className="px-5 py-3 font-medium text-white">{op.titulo}</td>
                  <td className="px-5 py-3">{nomeCliente(op.cliente_id)}</td>
                  <td className="px-5 py-3">
                    <StatusBadge tom={final ? "permitido" : "neutro"}>{op.etapa}</StatusBadge>
                  </td>
                  <td className="px-5 py-3 text-right tabular-nums">{formatarMoeda(op.valor)}</td>
                  <td className="px-5 py-3"><CelulaReciclagem oportunidade={op} /></td>
                  <td className="px-5 py-3 text-right">
                    {final && !pendente && (
                      <button
                        type="button"
                        onClick={() => onReciclar(op)}
                        aria-label={`Reciclar lead: ${op.titulo}`}
                        className="rounded-lg border border-kindra-acento/60 px-3 py-1.5 text-xs font-medium
                                   text-kindra-acento transition hover:bg-kindra-acento hover:text-white
                                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-kindra-acento"
                      >
                        ↻ Reciclar Lead
                      </button>
                    )}
                    {pendente && (
                      <button
                        type="button"
                        onClick={() => onCancelar(op)}
                        disabled={ocupado}
                        aria-busy={ocupado}
                        aria-label={`Cancelar reciclagem de ${op.titulo}`}
                        className="rounded-lg px-3 py-1.5 text-xs text-kindra-label transition hover:text-rose-300
                                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-kindra-acento
                                   disabled:cursor-wait disabled:opacity-60"
                      >
                        {ocupado ? "Cancelando..." : "Cancelar"}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </GlassCard>
  );
}
