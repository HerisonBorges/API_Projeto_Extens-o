import { useCallback, useEffect, useState } from "react";

import RodapeDashboard from "../components/dashboard/RodapeDashboard.jsx";
import GraficoBarras from "../components/graficos/GraficoBarras.jsx";
import GraficoDonut from "../components/graficos/GraficoDonut.jsx";
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

const soma = (lista) => lista.reduce((s, o) => s + o.valor, 0);

export default function Dashboard({ usuario, versao }) {
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState(null);
  const [atualizando, setAtualizando] = useState(false);

  const carregar = useCallback(async () => {
    setErro(null);
    setAtualizando(true);
    try {
      const [oportunidades, interacoes] = await Promise.all([
        listarOportunidades(),
        listarInteracoes({ limite: 8 }),
      ]);
      setDados({ oportunidades, interacoes, atualizadoEm: new Date().toISOString() });
    } catch (e) {
      setErro(e.message);
    } finally {
      setAtualizando(false);
    }
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar, versao]);

  if (erro) return <Erro mensagem={erro} onTentarDeNovo={carregar} />;
  if (!dados) return <Carregando texto="Carregando indicadores..." />;

  const ehGestor = usuario.perfil === "Gestor";
  // Relatórios é exclusivo do Gestor: o Atendimento vê as vendas no Funil
  const destinoVendas = ehGestor ? "#/relatorios" : "#/funil";

  const abertas = dados.oportunidades.filter((o) => o.etapa !== ETAPA_FINAL);
  const fechadas = dados.oportunidades.filter((o) => o.etapa === ETAPA_FINAL);
  const pipeline = soma(abertas);
  const receita = soma(fechadas);

  const porEtapa = ETAPAS.filter((e) => e !== ETAPA_FINAL).map((etapa) => ({
    rotulo: etapa,
    valor: soma(abertas.filter((o) => o.etapa === etapa)),
  }));

  const quentes = abertas.filter((o) => o.etapa === "Proposta" || o.etapa === "Negociação");
  const iniciais = abertas.filter((o) => o.etapa === "Prospecção" || o.etapa === "Qualificação");
  const totalCrm = receita + pipeline;

  const fatias = [
    {
      rotulo: "Receita realizada",
      valor: receita,
      cor: "#0F969C",
      href: destinoVendas,
      descricao: plural(fechadas.length, "venda fechada", "vendas fechadas"),
    },
    {
      rotulo: "Em fase final",
      valor: soma(quentes),
      cor: "#4A68D0",
      href: "#/funil",
      descricao: `Proposta e Negociação · ${plural(quentes.length, "negócio", "negócios")}`,
    },
    {
      rotulo: "Início do funil",
      valor: soma(iniciais),
      cor: "#204C94",
      href: "#/funil",
      descricao: `Prospecção e Qualificação · ${plural(iniciais.length, "negócio", "negócios")}`,
    },
  ];

  return (
    <div className="space-y-6">
      <section aria-label="Indicadores" className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Kpi rotulo="Leads ativos" valor={abertas.length} href="#/funil" acao="Ver no funil"
             detalhe={plural(abertas.length, "oportunidade em aberto", "oportunidades em aberto")} />
        <Kpi rotulo="Negócios fechados" valor={fechadas.length} href={destinoVendas}
             acao={ehGestor ? "Ver faturamento" : "Ver no funil"}
             detalhe={`${formatarMoeda(receita)} em vendas`} />
        <Kpi rotulo="Receita em pipeline" valor={formatarMoeda(pipeline)} destaque href="#/funil"
             acao="Ver oportunidades" detalhe="Soma das oportunidades em aberto" />
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card titulo="Pipeline por etapa">
          <div className="p-5">
            {pipeline > 0
              ? <GraficoBarras titulo="Valor em aberto por etapa do funil" dados={porEtapa} formatar={formatarMoedaCurta} />
              : <Vazio>Nenhuma oportunidade em aberto.</Vazio>}
          </div>
        </Card>

        <Card titulo="Composição financeira"
              acao={<span className="text-xs text-sandro-label">Realizado × em aberto</span>}>
          <div className="p-5">
            {totalCrm > 0 ? (
              <GraficoDonut
                titulo="Composição do valor no CRM: receita realizada e valor em aberto por fase do funil"
                fatias={fatias}
                centro={{ valor: formatarMoedaCurta(totalCrm), rotulo: "valor total no CRM" }}
                formatar={formatarMoeda}
              />
            ) : (
              <Vazio>Sem valores no CRM ainda.</Vazio>
            )}
          </div>
        </Card>
      </div>

      <Card titulo="Últimas interações"
            acao={<a href="#/clientes" className="alvo-toque text-xs text-sandro-acento hover:underline">Ver clientes</a>}>
        {dados.interacoes.length === 0 ? (
          <Vazio>Nenhuma interação registrada ainda.</Vazio>
        ) : (
          <>
          {/* Celular (< sm): cartões empilhados; o resumo quebra em até 2 linhas em vez de cortar */}
          <ul aria-label="As interações mais recentes com clientes" className="divide-y divide-sandro-borda/15 sm:hidden">
            {dados.interacoes.map((i) => (
              <li key={i.id}>
                <a href={`#/clientes/${i.cliente_id}`}
                   className="block px-4 py-3 active:bg-sandro-suporte/20 focus-visible:outline-none
                              focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-sandro-acento">
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium text-white">{i.cliente_nome}</span>
                    <StatusBadge tom="azul">{i.tipo}</StatusBadge>
                  </span>
                  <span className="mt-1 line-clamp-2 text-sm text-slate-300">{i.descricao}</span>
                  <span className="mt-1 block text-xs text-sandro-label">
                    {formatarDataHora(i.criado_em)}{i.usuario_nome && ` · por ${i.usuario_nome}`}
                  </span>
                </a>
              </li>
            ))}
          </ul>
          <div className="rolagem-x hidden sm:block">
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
                         className="alvo-toque font-medium text-white hover:text-sandro-acento hover:underline">
                        {i.cliente_nome}
                      </a>
                    </td>
                    <td className="px-5 py-3"><StatusBadge tom="azul">{i.tipo}</StatusBadge></td>
                    <td className="max-w-md truncate px-5 py-3" title={i.descricao}>{i.descricao}</td>
                    <td className="whitespace-nowrap px-5 py-3 text-xs text-sandro-label">
                      {formatarDataHora(i.criado_em)}
                      {i.usuario_nome && <span className="block">por {i.usuario_nome}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </>
        )}
      </Card>

      <RodapeDashboard usuario={usuario} atualizadoEm={dados.atualizadoEm}
                       onAtualizar={carregar} atualizando={atualizando} />
    </div>
  );
}
