import { useCallback, useEffect, useState } from "react";

import GraficoBarras from "../components/graficos/GraficoBarras.jsx";
import Card from "../components/ui/Card.jsx";
import { Carregando, Erro, Vazio } from "../components/ui/Estado.jsx";
import Kpi from "../components/ui/Kpi.jsx";
import StatusBadge from "../components/ui/StatusBadge.jsx";
import {
  ETAPAS,
  ETAPA_FINAL,
  formatarDataHora,
  formatarMoeda,
  formatarMoedaCurta,
  plural,
} from "../components/ui/formatos.js";
import { listarInteracoes, listarOportunidades } from "../services/api.js";

export default function Dashboard({ versao }) {
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState(null);

  const carregar = useCallback(async () => {
    setErro(null);
    try {
      const [oportunidades, interacoes] = await Promise.all([
        listarOportunidades(),
        listarInteracoes({ limite: 8 }),
      ]);
      setDados({ oportunidades, interacoes });
    } catch (e) {
      setErro(e.message);
    }
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar, versao]);

  if (erro) return <Erro mensagem={erro} onTentarDeNovo={carregar} />;
  if (!dados) return <Carregando texto="Carregando indicadores..." />;

  const abertas = dados.oportunidades.filter((o) => o.etapa !== ETAPA_FINAL);
  const fechadas = dados.oportunidades.filter((o) => o.etapa === ETAPA_FINAL);
  const pipeline = abertas.reduce((soma, o) => soma + o.valor, 0);

  const porEtapa = ETAPAS.filter((e) => e !== ETAPA_FINAL).map((etapa) => ({
    rotulo: etapa,
    valor: abertas.filter((o) => o.etapa === etapa).reduce((s, o) => s + o.valor, 0),
  }));

  return (
    <div className="space-y-6">
      <section aria-label="Indicadores" className="grid gap-4 sm:grid-cols-3">
        <Kpi rotulo="Leads ativos" valor={abertas.length}
             detalhe={plural(abertas.length, "oportunidade em aberto", "oportunidades em aberto")} />
        <Kpi rotulo="Negócios fechados" valor={fechadas.length}
             detalhe={`${formatarMoeda(fechadas.reduce((s, o) => s + o.valor, 0))} em vendas`} />
        <Kpi rotulo="Receita em pipeline" valor={formatarMoeda(pipeline)} destaque
             detalhe="Soma das oportunidades em aberto" />
      </section>

      <div className="grid gap-6 xl:grid-cols-5">
        <Card titulo="Pipeline por etapa" className="xl:col-span-2">
          <div className="p-5">
            {pipeline > 0
              ? <GraficoBarras titulo="Valor em aberto por etapa do funil" dados={porEtapa} formatar={formatarMoedaCurta} />
              : <Vazio>Nenhuma oportunidade em aberto.</Vazio>}
          </div>
        </Card>

        <Card titulo="Últimas interações" className="xl:col-span-3"
              acao={<a href="#/clientes" className="text-xs text-sandro-acento hover:underline">Ver clientes</a>}>
          {dados.interacoes.length === 0 ? (
            <Vazio>Nenhuma interação registrada ainda.</Vazio>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">As interações mais recentes com clientes</caption>
                <thead className="border-b border-sandro-borda/20 text-xs uppercase tracking-wider text-sandro-label">
                  <tr>
                    <th scope="col" className="px-5 py-3 font-medium">Cliente</th>
                    <th scope="col" className="px-5 py-3 font-medium">Canal</th>
                    <th scope="col" className="px-5 py-3 font-medium">Resumo</th>
                    <th scope="col" className="px-5 py-3 font-medium">Quando</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-sandro-borda/15">
                  {dados.interacoes.map((i) => (
                    <tr key={i.id} className="text-slate-200">
                      <td className="px-5 py-3">
                        <a href={`#/clientes/${i.cliente_id}`}
                           className="font-medium text-white hover:text-sandro-acento hover:underline">
                          {i.cliente_nome}
                        </a>
                      </td>
                      <td className="px-5 py-3"><StatusBadge tom="azul">{i.tipo}</StatusBadge></td>
                      <td className="max-w-xs truncate px-5 py-3" title={i.descricao}>{i.descricao}</td>
                      <td className="whitespace-nowrap px-5 py-3 text-xs text-sandro-label">
                        {formatarDataHora(i.criado_em)}
                        {i.usuario_nome && <span className="block">por {i.usuario_nome}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
