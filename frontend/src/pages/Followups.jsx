import { useCallback, useEffect, useMemo, useState } from "react";

import Abas from "../components/ui/Abas.jsx";
import Botao from "../components/ui/Botao.jsx";
import Card from "../components/ui/Card.jsx";
import { classeEntrada } from "../components/ui/Campo.jsx";
import { Aviso, Carregando, Erro, Vazio } from "../components/ui/Estado.jsx";
import StatusBadge from "../components/ui/StatusBadge.jsx";
import {
  amanhaISO,
  diasAte,
  formatarData,
  formatarMoeda,
  hojeISO,
  plural,
} from "../components/ui/formatos.js";
import {
  atualizarTarefa,
  buscarAlertas,
  concluirTarefa,
  listarClientes,
  listarTarefas,
} from "../services/api.js";

const FILTROS = {
  pendentes: () => true,
  atrasados: (d) => d !== null && d < 0,
  hoje: (d) => d === 0,
  proximos: (d) => d === null || d > 0,
};

function Prazo({ dias }) {
  if (dias === null) return <StatusBadge>Sem data</StatusBadge>;
  if (dias < 0) return <StatusBadge tom="bloqueado" icone="!">Atrasado há {plural(-dias, "dia", "dias")}</StatusBadge>;
  if (dias === 0) return <StatusBadge tom="pendente" icone="●">Hoje</StatusBadge>;
  return <StatusBadge tom="azul">Em {plural(dias, "dia", "dias")}</StatusBadge>;
}

function ItemTarefa({ tarefa, cliente, onConcluir, onReagendar }) {
  const [reagendando, setReagendando] = useState(false);
  const [data, setData] = useState(tarefa.data_vencimento ?? amanhaISO());
  const [ocupado, setOcupado] = useState(false);
  const dias = tarefa.data_vencimento ? diasAte(tarefa.data_vencimento) : null;

  const executar = async (acao) => {
    setOcupado(true);
    try {
      await acao();
    } finally {
      setOcupado(false);
    }
  };

  return (
    <li className={`px-5 py-4 ${dias !== null && dias < 0 ? "border-l-4 border-rose-500/70 bg-rose-950/20" : ""}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-white">{tarefa.titulo}</p>
          <p className="mt-0.5 text-xs text-sandro-label">
            {cliente ? <a href={`#/clientes/${cliente.id}`} className="hover:underline">{cliente.nome}</a> : "Sem cliente"}
            {" · "}{formatarData(tarefa.data_vencimento)}
          </p>
          {tarefa.descricao && <p className="mt-1 text-xs text-slate-300">{tarefa.descricao}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Prazo dias={dias} />
          <Botao tamanho="sm" variante="secundario" onClick={() => setReagendando((v) => !v)}
                 aria-expanded={reagendando} disabled={ocupado}>
            Reagendar
          </Botao>
          <Botao tamanho="sm" variante="primario" carregando={ocupado && !reagendando} textoCarregando="Concluindo..."
                 onClick={() => executar(() => onConcluir(tarefa))}>
            ✓ Concluir
          </Botao>
        </div>
      </div>

      {reagendando && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            executar(async () => {
              await onReagendar(tarefa, data);
              setReagendando(false);
            });
          }}
          className="mt-3 flex flex-wrap items-center gap-2"
        >
          <label htmlFor={`nova-data-${tarefa.id}`} className="text-xs text-sandro-label">Nova data</label>
          <input id={`nova-data-${tarefa.id}`} type="date" required min={hojeISO()} value={data}
                 onChange={(e) => setData(e.target.value)} className={`${classeEntrada} w-44`} />
          <Botao tamanho="sm" variante="primario" type="submit" carregando={ocupado} textoCarregando="Salvando...">
            Salvar data
          </Botao>
        </form>
      )}
    </li>
  );
}

export default function Followups({ versao }) {
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState(null);
  const [filtro, setFiltro] = useState("pendentes");
  const [aviso, setAviso] = useState(null);

  const carregar = useCallback(async () => {
    setErro(null);
    try {
      const [tarefas, clientes, alertas] = await Promise.all([
        listarTarefas({ concluida: false }),
        listarClientes(),
        buscarAlertas(),
      ]);
      setDados({ tarefas, alertas, clientes: Object.fromEntries(clientes.map((c) => [c.id, c])) });
    } catch (e) {
      setErro(e.message);
    }
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar, versao]);

  const comPrazo = useMemo(
    () => (dados?.tarefas ?? []).map((t) => ({ t, d: t.data_vencimento ? diasAte(t.data_vencimento) : null })),
    [dados]
  );

  if (erro) return <Erro mensagem={erro} onTentarDeNovo={carregar} />;
  if (!dados) return <Carregando texto="Carregando follow-ups..." />;

  const contar = (chave) => comPrazo.filter(({ d }) => FILTROS[chave](d)).length;
  const visiveis = comPrazo
    .filter(({ d }) => FILTROS[filtro](d))
    .sort((a, b) => (a.d ?? Infinity) - (b.d ?? Infinity));

  async function concluir(tarefa) {
    try {
      await concluirTarefa(tarefa.id);
      setAviso(`"${tarefa.titulo}" concluída.`);
      setDados((d) => ({ ...d, tarefas: d.tarefas.filter((t) => t.id !== tarefa.id) }));
    } catch (e) {
      setAviso(e.message);
    }
  }

  async function reagendar(tarefa, data) {
    try {
      await atualizarTarefa(tarefa.id, {
        titulo: tarefa.titulo,
        descricao: tarefa.descricao,
        cliente_id: tarefa.cliente_id,
        oportunidade_id: tarefa.oportunidade_id,
        data_vencimento: data,
      });
      setAviso(`"${tarefa.titulo}" reagendada para ${formatarData(data)}.`);
      setDados((d) => ({
        ...d,
        tarefas: d.tarefas.map((t) => (t.id === tarefa.id ? { ...t, data_vencimento: data } : t)),
      }));
    } catch (e) {
      setAviso(e.message);
    }
  }

  const { orcamentos_parados: parados, dias_alerta_orcamento: diasAlerta } = dados.alertas;

  return (
    <div className="space-y-6">
      {/* RF04: orçamentos parados há mais de X dias (configurável por empresa) */}
      <Card
        titulo="Orçamentos parados"
        acao={<span className="text-xs text-sandro-label">Propostas sem movimento há mais de {plural(diasAlerta, "dia", "dias")}</span>}
        className={parados.length ? "border-amber-500/40" : ""}
      >
        {parados.length === 0 ? (
          <Vazio>Nenhuma proposta parada no momento.</Vazio>
        ) : (
          <ul className="divide-y divide-sandro-borda/15">
            {parados.map((o) => (
              <li key={o.id} className="flex flex-wrap items-center justify-between gap-3 border-l-4 border-amber-500/70 px-5 py-3">
                <div>
                  <p className="text-sm font-medium text-white">{o.titulo}</p>
                  <p className="text-xs text-sandro-label">
                    {dados.clientes[o.cliente_id]?.nome ?? "Sem cliente"} · {formatarMoeda(o.valor)}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge tom="pendente" icone="⚠">Parado há {plural(o.dias_parado, "dia", "dias")}</StatusBadge>
                  <a href="#/funil" className="text-xs text-sandro-acento hover:underline">Ver no funil</a>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card
        titulo="Follow-ups"
        acao={
          <Abas
            rotulo="Filtrar follow-ups por prazo"
            valor={filtro}
            onChange={setFiltro}
            opcoes={[
              { valor: "pendentes", rotulo: "Pendentes", contagem: contar("pendentes") },
              { valor: "atrasados", rotulo: "Atrasados", contagem: contar("atrasados") },
              { valor: "hoje", rotulo: "Hoje", contagem: contar("hoje") },
              { valor: "proximos", rotulo: "Próximos", contagem: contar("proximos") },
            ]}
          />
        }
      >
        <div className="px-5 pt-3"><Aviso mensagem={aviso} /></div>
        {visiveis.length === 0 ? (
          <Vazio>Nada por aqui neste filtro.</Vazio>
        ) : (
          <ul className="divide-y divide-sandro-borda/15">
            {visiveis.map(({ t }) => (
              <ItemTarefa key={`${t.id}-${t.data_vencimento}`} tarefa={t} cliente={dados.clientes[t.cliente_id]}
                          onConcluir={concluir} onReagendar={reagendar} />
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
