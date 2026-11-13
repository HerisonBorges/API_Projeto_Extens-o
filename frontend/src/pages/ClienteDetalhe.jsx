import { useCallback, useEffect, useState } from "react";

import Botao from "../components/ui/Botao.jsx";
import Card from "../components/ui/Card.jsx";
import Campo, { classeEntrada } from "../components/ui/Campo.jsx";
import { Carregando, Erro, Vazio } from "../components/ui/Estado.jsx";
import StatusBadge from "../components/ui/StatusBadge.jsx";
import {
  ETAPA_FINAL,
  TIPOS_INTERACAO,
  formatarDataHora,
  formatarMoeda,
} from "../components/ui/formatos.js";
import EditarClienteModal from "../components/clientes/EditarClienteModal.jsx";
import { buscarCliente, criarInteracao, listarInteracoes, listarOportunidades } from "../services/api.js";

const ICONE_TIPO = { "Ligação": "☎", WhatsApp: "✆", "E-mail": "✉", "Reunião": "◎" };
const TOM_STATUS = { Lead: "azul", Cliente: "permitido", Inativo: "neutro" };

function Dado({ rotulo, children }) {
  return (
    <div>
      <dt className="text-xs text-sandro-label">{rotulo}</dt>
      <dd className="mt-0.5 text-sm text-white">{children || "—"}</dd>
    </div>
  );
}

function NovaInteracao({ clienteId, oportunidades, onSalva }) {
  const [tipo, setTipo] = useState("Ligação");
  const [oportunidadeId, setOportunidadeId] = useState("");
  const [descricao, setDescricao] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);

  async function salvar(e) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      const r = await criarInteracao({
        cliente_id: clienteId,
        tipo,
        descricao,
        oportunidade_id: oportunidadeId ? Number(oportunidadeId) : null,
      });
      setDescricao("");
      onSalva(r.interacao);
    } catch (erroApi) {
      setErro(erroApi.message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={salvar} className="space-y-4 p-5">
      <fieldset>
        <legend className="mb-2 text-xs font-medium text-sandro-label">Canal</legend>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {TIPOS_INTERACAO.map((t) => (
            <label key={t}
                   className={`flex cursor-pointer items-center justify-center gap-1.5 rounded-lg border px-2 py-2 text-xs
                               transition has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-sandro-acento
                               ${tipo === t
                                 ? "border-sandro-acento bg-sandro-acento/10 font-semibold text-white"
                                 : "border-sandro-borda/40 text-sandro-label hover:text-white"}`}>
              <input type="radio" name="tipo-interacao" value={t} checked={tipo === t}
                     onChange={() => setTipo(t)} className="sr-only" />
              <span aria-hidden="true">{ICONE_TIPO[t]}</span> {t}
            </label>
          ))}
        </div>
      </fieldset>

      {oportunidades.length > 0 && (
        <Campo rotulo="Oportunidade relacionada (opcional)">
          {(p) => (
            <select {...p} value={oportunidadeId} onChange={(e) => setOportunidadeId(e.target.value)}
                    className={classeEntrada}>
              <option value="">Nenhuma</option>
              {oportunidades.map((o) => <option key={o.id} value={o.id}>{o.titulo} ({o.etapa})</option>)}
            </select>
          )}
        </Campo>
      )}

      <Campo rotulo="O que foi conversado *">
        {(p) => (
          <textarea {...p} required maxLength={2000} rows={3} value={descricao}
                    onChange={(e) => setDescricao(e.target.value)} className={classeEntrada}
                    placeholder="Ex.: Cliente pediu revisão do prazo de entrega." />
        )}
      </Campo>

      {erro && <p role="alert" className="rounded-lg bg-rose-950/80 px-3 py-2 text-sm text-rose-300">{erro}</p>}

      <div className="flex justify-end">
        <Botao variante="primario" type="submit" carregando={enviando} textoCarregando="Salvando..."
               disabled={!descricao.trim()}>
          Salvar no histórico
        </Botao>
      </div>
    </form>
  );
}

export default function ClienteDetalhe({ id, versao }) {
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState(null);
  const [editando, setEditando] = useState(false);
  const [aviso, setAviso] = useState(null);

  const carregar = useCallback(async () => {
    setErro(null);
    setDados(null);
    try {
      const [cliente, oportunidades, interacoes] = await Promise.all([
        buscarCliente(id),
        listarOportunidades(),
        listarInteracoes({ clienteId: id, limite: 200 }),
      ]);
      setDados({
        cliente,
        oportunidades: oportunidades.filter((o) => o.cliente_id === id),
        interacoes,
      });
    } catch (e) {
      setErro(e.status === 404 ? "Cliente não encontrado." : e.message);
    }
  }, [id]);

  useEffect(() => {
    carregar();
  }, [carregar, versao]);

  const voltar = (
    <a href="#/clientes" className="inline-flex items-center gap-1 text-sm text-sandro-label hover:text-white">
      <span aria-hidden="true">←</span> Voltar para Clientes
    </a>
  );

  if (erro) return <div className="space-y-4">{voltar}<Erro mensagem={erro} onTentarDeNovo={carregar} /></div>;
  if (!dados) return <Carregando texto="Carregando cliente..." />;

  const { cliente, oportunidades, interacoes } = dados;

  return (
    <div className="space-y-4">
      {voltar}

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Coluna esquerda: cadastro e oportunidades */}
        <div className="space-y-6 lg:col-span-2">
          <Card
            titulo={cliente.nome}
            acao={
              <div className="flex items-center gap-2">
                <StatusBadge tom={TOM_STATUS[cliente.status] ?? "neutro"}>{cliente.status}</StatusBadge>
                <Botao tamanho="sm" variante="secundario" onClick={() => setEditando(true)}
                       aria-label={`Editar dados de ${cliente.nome}`}>
                  Editar
                </Botao>
              </div>
            }
          >
            <dl className="grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
              <Dado rotulo="E-mail">{cliente.email}</Dado>
              <Dado rotulo="Telefone">{cliente.telefone}</Dado>
              <Dado rotulo="Código">#{cliente.id}</Dado>
              <Dado rotulo="Interações">{interacoes.length}</Dado>
            </dl>
            <p role="status" className="border-t border-sandro-borda/20 px-5 py-2 text-xs text-sandro-label">
              {aviso ?? (cliente.atualizado_em
                ? `Última alteração em ${formatarDataHora(cliente.atualizado_em)}` +
                  (cliente.atualizado_por_nome ? ` por ${cliente.atualizado_por_nome}` : "")
                : "Dados não alterados desde o cadastro.")}
            </p>
          </Card>

          <Card titulo="Oportunidades associadas">
            {oportunidades.length === 0 ? (
              <Vazio>Nenhuma oportunidade para este cliente.</Vazio>
            ) : (
              <ul className="divide-y divide-sandro-borda/15">
                {oportunidades.map((o) => (
                  <li key={o.id} className="flex items-center justify-between gap-3 px-5 py-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-white">{o.titulo}</p>
                      <p className="text-xs text-sandro-label">
                        {formatarMoeda(o.valor)}{o.responsavel_nome && ` · ${o.responsavel_nome}`}
                      </p>
                    </div>
                    <StatusBadge tom={o.etapa === ETAPA_FINAL ? "permitido" : "neutro"}>{o.etapa}</StatusBadge>
                  </li>
                ))}
              </ul>
            )}
            <div className="border-t border-sandro-borda/20 px-5 py-3">
              <a href="#/funil" className="text-xs text-sandro-acento hover:underline">Abrir no funil de vendas →</a>
            </div>
          </Card>
        </div>

        {/* Coluna direita: nova interação + histórico */}
        <div className="space-y-6 lg:col-span-3">
          <Card titulo="Nova interação">
            <NovaInteracao
              clienteId={cliente.id}
              oportunidades={oportunidades}
              onSalva={(nova) => setDados((d) => ({ ...d, interacoes: [nova, ...d.interacoes] }))}
            />
          </Card>

          <Card titulo="Histórico de interações">
            {interacoes.length === 0 ? (
              <Vazio>Nenhuma interação registrada. Use o formulário acima para começar o histórico.</Vazio>
            ) : (
              <ol className="relative space-y-5 p-5 before:absolute before:bottom-5 before:left-[2.05rem] before:top-5 before:w-px before:bg-sandro-borda/30">
                {interacoes.map((i) => (
                  <li key={i.id} className="relative flex gap-4">
                    <span aria-hidden="true"
                          className="z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border
                                     border-sandro-borda/50 bg-sandro-fundo text-sm text-sandro-acento">
                      {ICONE_TIPO[i.tipo]}
                    </span>
                    <div className="min-w-0 flex-1 rounded-lg border border-sandro-borda/20 bg-sandro-fundo/40 px-4 py-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <StatusBadge tom="azul">{i.tipo}</StatusBadge>
                        <time dateTime={i.criado_em} className="text-xs text-sandro-label">
                          {formatarDataHora(i.criado_em)}
                        </time>
                      </div>
                      <p className="mt-2 whitespace-pre-line text-sm text-slate-200">{i.descricao}</p>
                      {i.usuario_nome && <p className="mt-1 text-xs text-sandro-label">por {i.usuario_nome}</p>}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </div>
      </div>

      {editando && (
        <EditarClienteModal
          cliente={cliente}
          onFechar={() => setEditando(false)}
          onSalvo={(atualizado) => {
            setDados((d) => ({ ...d, cliente: atualizado }));
            setEditando(false);
            setAviso(`Dados de ${atualizado.nome} salvos.`);
          }}
        />
      )}
    </div>
  );
}
