import { useCallback, useEffect, useState } from "react";

import KpiCard from "../components/dashboard/KpiCard.jsx";
import LeadsTable from "../components/dashboard/LeadsTable.jsx";
import ReciclagemModal from "../components/reciclagem/ReciclagemModal.jsx";
import { formatarDataHora, formatarMoeda } from "../components/ui/formatos.js";
import {
  buscarDashboard,
  cancelarReciclagem,
  listarClientes,
  listarOportunidades,
} from "../services/api.js";

export default function Dashboard({ usuario }) {
  const [kpis, setKpis] = useState(null);
  const [oportunidades, setOportunidades] = useState([]);
  const [clientes, setClientes] = useState([]);
  const [erro, setErro] = useState(null);
  const [reciclando, setReciclando] = useState(null);
  const [cancelandoId, setCancelandoId] = useState(null);
  const [aviso, setAviso] = useState(null);

  const carregar = useCallback(async () => {
    try {
      const [painel, ops, cls] = await Promise.all([
        buscarDashboard(usuario.empresa_id),
        listarOportunidades(),
        listarClientes(),
      ]);
      setKpis(painel);
      setOportunidades(ops);
      setClientes(cls);
      setErro(null);
    } catch (e) {
      setErro(e.message);
    }
  }, [usuario.empresa_id]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function cancelar(op) {
    setCancelandoId(op.id);
    try {
      await cancelarReciclagem(op.id);
      setAviso(`Reciclagem de "${op.titulo}" cancelada.`);
      await carregar();
    } catch (e) {
      setAviso(e.message);
    } finally {
      setCancelandoId(null);
    }
  }

  async function aoAgendar(resposta) {
    setAviso(
      `Reciclagem de "${reciclando.titulo}" agendada para ` +
        `${formatarDataHora(resposta.data_reciclagem_agendada)}.`
    );
    setReciclando(null);
    await carregar();
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-white">Dashboard</h1>
        <p className="text-sm text-kindra-label">Olá, {usuario.nome}</p>
      </header>

      {erro && <p role="alert" className="rounded-lg bg-rose-950/80 px-4 py-3 text-sm text-rose-300">{erro}</p>}
      <p role="status" className="text-sm text-teal-400">{aviso}</p>

      <section aria-label="Indicadores" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard rotulo="Receita" valor={kpis ? formatarMoeda(kpis.receita_total) : "—"} destaque />
        <KpiCard rotulo="Vendas fechadas" valor={kpis?.vendas_fechadas ?? "—"} />
        <KpiCard rotulo="Oportunidades" valor={kpis?.total_oportunidades ?? "—"} />
        <KpiCard rotulo="Clientes" valor={kpis?.total_clientes ?? "—"} />
      </section>

      <LeadsTable
        oportunidades={oportunidades}
        clientes={clientes}
        onReciclar={setReciclando}
        onCancelar={cancelar}
        ocupadoId={cancelandoId}
      />

      {reciclando && (
        <ReciclagemModal
          oportunidade={reciclando}
          onFechar={() => setReciclando(null)}
          onAgendado={aoAgendar}
        />
      )}
    </div>
  );
}
