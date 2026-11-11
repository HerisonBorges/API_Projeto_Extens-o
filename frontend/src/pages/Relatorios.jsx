import { useCallback, useEffect, useState } from "react";

import GraficoBarras from "../components/graficos/GraficoBarras.jsx";
import Abas from "../components/ui/Abas.jsx";
import Card from "../components/ui/Card.jsx";
import { Carregando, Erro, Vazio } from "../components/ui/Estado.jsx";
import Kpi from "../components/ui/Kpi.jsx";
import {
  formatarData,
  formatarMes,
  formatarMoeda,
  formatarMoedaCurta,
  formatarPercentual,
} from "../components/ui/formatos.js";
import { buscarRelatorio } from "../services/api.js";

const PERIODOS = [
  { valor: "mes", rotulo: "Mês" },
  { valor: "trimestre", rotulo: "Trimestre" },
  { valor: "ano", rotulo: "Ano" },
];

const NOME_PERIODO = { mes: "neste mês", trimestre: "neste trimestre", ano: "neste ano" };

export default function Relatorios({ versao }) {
  const [periodo, setPeriodo] = useState("mes");
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState(null);

  const carregar = useCallback(async () => {
    setErro(null);
    try {
      setDados(await buscarRelatorio(periodo));
    } catch (e) {
      setErro(e.message);
    }
  }, [periodo]);

  useEffect(() => {
    carregar();
  }, [carregar, versao]);

  const acumulado = dados?.serie_mensal.reduce((s, m) => s + m.receita, 0) ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Abas rotulo="Período do relatório" valor={periodo} onChange={setPeriodo} opcoes={PERIODOS} />
        {dados?.inicio_periodo && (
          <p className="text-xs text-sandro-label">Desde {formatarData(dados.inicio_periodo)}</p>
        )}
      </div>

      {erro && <Erro mensagem={erro} onTentarDeNovo={carregar} />}
      {!erro && !dados && <Carregando texto="Calculando indicadores..." />}

      {dados && (
        <>
          <section aria-label="Indicadores do período" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi rotulo="Faturamento" valor={formatarMoeda(dados.receita_total)} destaque
                 detalhe={`Vendas fechadas ${NOME_PERIODO[periodo]}`} />
            <Kpi rotulo="Taxa de conversão" valor={formatarPercentual(dados.taxa_conversao)}
                 detalhe={`Das ${dados.total_oportunidades} oportunidades criadas ${NOME_PERIODO[periodo]}`} />
            <Kpi rotulo="Ticket médio" valor={formatarMoeda(dados.ticket_medio)} />
            <Kpi rotulo="Negócios fechados" valor={dados.vendas_fechadas} />
          </section>

          <div className="grid gap-6 xl:grid-cols-5">
            <Card titulo="Faturamento mensal (12 meses)" className="xl:col-span-3"
                  acao={<span className="text-xs text-sandro-label">Acumulado: {formatarMoeda(acumulado)}</span>}>
              <div className="p-5">
                <GraficoBarras
                  titulo="Faturamento por mês nos últimos 12 meses"
                  cor="ciano"
                  formatar={formatarMoedaCurta}
                  dados={dados.serie_mensal.map((m) => ({ rotulo: formatarMes(m.mes), valor: m.receita }))}
                />
              </div>
            </Card>

            <Card titulo="Funil atual" className="xl:col-span-2">
              <div className="p-5">
                <GraficoBarras
                  titulo="Quantidade de oportunidades por etapa"
                  dados={dados.funil.map((f) => ({ rotulo: f.etapa, valor: f.quantidade }))}
                />
              </div>
            </Card>
          </div>

          <Card titulo={`Desempenho por canal ${NOME_PERIODO[periodo]}`}>
            {dados.canais.every((c) => c.interacoes === 0) ? (
              <Vazio>Nenhuma interação registrada neste período.</Vazio>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Interações e conversão por canal de contato</caption>
                  <thead className="border-b border-sandro-borda/20 text-xs uppercase tracking-wider text-sandro-label">
                    <tr>
                      <th scope="col" className="px-5 py-3 font-medium">Canal</th>
                      <th scope="col" className="px-5 py-3 text-right font-medium">Interações</th>
                      <th scope="col" className="px-5 py-3 text-right font-medium">Clientes contatados</th>
                      <th scope="col" className="px-5 py-3 text-right font-medium">Com venda</th>
                      <th scope="col" className="w-1/3 px-5 py-3 font-medium">Conversão</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-sandro-borda/15 text-slate-200">
                    {dados.canais.map((c) => {
                      const taxa = c.clientes_contatados ? (c.clientes_com_venda / c.clientes_contatados) * 100 : 0;
                      return (
                        <tr key={c.canal}>
                          <th scope="row" className="px-5 py-3 font-medium text-white">{c.canal}</th>
                          <td className="px-5 py-3 text-right tabular-nums">{c.interacoes}</td>
                          <td className="px-5 py-3 text-right tabular-nums">{c.clientes_contatados}</td>
                          <td className="px-5 py-3 text-right tabular-nums">{c.clientes_com_venda}</td>
                          <td className="px-5 py-3">
                            <div className="flex items-center gap-3">
                              <div className="h-2 flex-1 overflow-hidden rounded-full bg-sandro-suporte/40" aria-hidden="true">
                                <div className="h-full rounded-full bg-linear-to-r from-sandro-azul to-sandro-acento"
                                     style={{ width: `${taxa}%` }} />
                              </div>
                              <span className="w-12 text-right text-xs tabular-nums">{formatarPercentual(taxa)}</span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
