import { useEffect, useState } from "react";

import {
  atualizarConfiguracoes,
  buscarConfiguracoes,
  cancelarReciclagem,
  listarOportunidades,
} from "../../services/api.js";
import ReciclagemModal from "../reciclagem/ReciclagemModal.jsx";
import Botao from "../ui/Botao.jsx";
import Card from "../ui/Card.jsx";
import Campo, { classeEntrada } from "../ui/Campo.jsx";
import { Aviso, Carregando, Erro, Vazio } from "../ui/Estado.jsx";
import StatusBadge from "../ui/StatusBadge.jsx";
import { ETAPA_FINAL, formatarData, formatarDataHora, formatarMoeda } from "../ui/formatos.js";

function StatusReciclagem({ op }) {
  if (op.status_reciclagem === "pendente") {
    return <StatusBadge tom="pendente" icone="⏱">Agendada · {formatarData(op.data_reciclagem_agendada)}</StatusBadge>;
  }
  if (op.status_reciclagem === "processado") return <StatusBadge tom="permitido" icone="↻">Reciclada</StatusBadge>;
  if (op.status_reciclagem === "cancelado") return <StatusBadge>Cancelada</StatusBadge>;
  return <span className="text-xs text-sandro-label">Sem agendamento</span>;
}

function AlertaOrcamento() {
  const [dias, setDias] = useState("");
  const [salvo, setSalvo] = useState(null);
  const [salvando, setSalvando] = useState(false);
  const [retorno, setRetorno] = useState(null);

  useEffect(() => {
    buscarConfiguracoes()
      .then((c) => {
        setDias(String(c.dias_alerta_orcamento));
        setSalvo(c.dias_alerta_orcamento);
      })
      .catch((e) => setRetorno({ ok: false, texto: e.message }));
  }, []);

  async function salvar(e) {
    e.preventDefault();
    setSalvando(true);
    setRetorno(null);
    try {
      const r = await atualizarConfiguracoes({ dias_alerta_orcamento: Number(dias) });
      setSalvo(r.dias_alerta_orcamento);
      setRetorno({ ok: true, texto: "Prazo atualizado." });
    } catch (erro) {
      setRetorno({ ok: false, texto: erro.message });
    } finally {
      setSalvando(false);
    }
  }

  return (
    <form onSubmit={salvar} className="flex flex-wrap items-end gap-3 px-5 py-4">
      <Campo rotulo="Alertar orçamento parado após (dias)" className="w-64"
             ajuda="RF04: propostas sem movimentação entram em Follow-ups.">
        {(p) => (
          <input {...p} type="number" min="1" step="1" required value={dias}
                 onChange={(e) => setDias(e.target.value)} className={classeEntrada} />
        )}
      </Campo>
      <Botao variante="primario" type="submit" carregando={salvando} textoCarregando="Salvando..."
             disabled={salvo === null || Number(dias) === salvo} className="mb-5">
        Salvar prazo
      </Botao>
      <p role="status" className={`mb-6 text-xs ${retorno?.ok ? "text-teal-400" : "text-rose-300"}`}>
        {retorno?.texto}
      </p>
    </form>
  );
}

export default function AutomacaoFunil() {
  const [fechadas, setFechadas] = useState(null);
  const [erro, setErro] = useState(null);
  const [reciclando, setReciclando] = useState(null);
  const [cancelandoId, setCancelandoId] = useState(null);
  const [aviso, setAviso] = useState(null);

  const carregar = () => {
    setErro(null);
    listarOportunidades()
      .then((ops) => setFechadas(ops.filter((o) => o.etapa === ETAPA_FINAL).reverse()))
      .catch((e) => setErro(e.message));
  };

  useEffect(carregar, []);

  async function cancelar(op) {
    setCancelandoId(op.id);
    try {
      await cancelarReciclagem(op.id);
      setAviso(`Reciclagem de "${op.titulo}" cancelada.`);
      carregar();
    } catch (e) {
      setAviso(e.message);
    } finally {
      setCancelandoId(null);
    }
  }

  return (
    <Card titulo="Reciclagem automática no funil">
      <AlertaOrcamento />

      <div className="border-t border-sandro-borda/20 px-5 pt-4">
        <p className="text-xs text-sandro-label">
          Vendas fechadas podem voltar ao início do funil como nova oportunidade, em uma data
          específica ou após 7, 10, 15 ou 30 dias. A venda original continua contando na receita.
        </p>
        <Aviso mensagem={aviso} />
      </div>

      {erro && <div className="p-5"><Erro mensagem={erro} onTentarDeNovo={carregar} /></div>}
      {!erro && !fechadas && <Carregando />}
      {fechadas && fechadas.length === 0 && <Vazio>Nenhuma venda fechada ainda.</Vazio>}

      {fechadas && fechadas.length > 0 && (
        <ul className="divide-y divide-sandro-borda/15">
          {fechadas.map((op) => (
            <li key={op.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-white">{op.titulo}</p>
                <p className="text-xs text-sandro-label">
                  {formatarMoeda(op.valor)} · fechada em {formatarDataHora(op.etapa_atualizada_em)}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <StatusReciclagem op={op} />
                {op.status_reciclagem === "pendente" ? (
                  <Botao variante="fantasma" tamanho="sm" carregando={cancelandoId === op.id}
                         textoCarregando="Cancelando..." onClick={() => cancelar(op)}
                         aria-label={`Cancelar reciclagem de ${op.titulo}`}>
                    Cancelar
                  </Botao>
                ) : (
                  op.status_reciclagem !== "processado" && (
                    <Botao variante="contorno" tamanho="sm" onClick={() => setReciclando(op)}
                           aria-label={`Reciclar lead: ${op.titulo}`}>
                      ↻ Reciclar Lead
                    </Botao>
                  )
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {reciclando && (
        <ReciclagemModal
          oportunidade={reciclando}
          onFechar={() => setReciclando(null)}
          onAgendado={(r) => {
            setAviso(`Reciclagem de "${reciclando.titulo}" agendada para ${formatarDataHora(r.data_reciclagem_agendada)}.`);
            setReciclando(null);
            carregar();
          }}
        />
      )}
    </Card>
  );
}
