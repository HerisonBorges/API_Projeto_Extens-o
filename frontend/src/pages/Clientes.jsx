import { useCallback, useEffect, useMemo, useState } from "react";

import Abas from "../components/ui/Abas.jsx";
import Botao from "../components/ui/Botao.jsx";
import Card from "../components/ui/Card.jsx";
import { classeEntrada } from "../components/ui/Campo.jsx";
import { Aviso, Carregando, Erro, Vazio } from "../components/ui/Estado.jsx";
import Modal from "../components/ui/Modal.jsx";
import Paginacao from "../components/ui/Paginacao.jsx";
import StatusBadge from "../components/ui/StatusBadge.jsx";
import { navegar } from "../rotas.js";
import { excluirCliente, listarClientes } from "../services/api.js";

const POR_PAGINA = 8;
const ehInativo = (c) => (c.status ?? "").toLowerCase() === "inativo";

const TOM_STATUS = { Lead: "azul", Cliente: "permitido", Inativo: "neutro" };

// Busca sem acento e sem caixa: "joao" encontra "João"
const normalizar = (texto) =>
  (texto ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

export default function Clientes({ usuario, versao }) {
  const [clientes, setClientes] = useState(null);
  const [erro, setErro] = useState(null);
  const [filtro, setFiltro] = useState("todos");
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);
  const [excluindo, setExcluindo] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const [aviso, setAviso] = useState(null);

  const ehGestor = usuario.perfil === "Gestor";

  const carregar = useCallback(() => {
    setErro(null);
    listarClientes().then(setClientes).catch((e) => setErro(e.message));
  }, []);

  useEffect(carregar, [carregar, versao]);

  const filtrados = useMemo(() => {
    if (!clientes) return [];
    const termo = normalizar(busca.trim());
    return clientes
      .filter((c) => filtro === "todos" || (filtro === "inativos" ? ehInativo(c) : !ehInativo(c)))
      .filter((c) => !termo || normalizar(`${c.nome} ${c.email ?? ""}`).includes(termo))
      .reverse();
  }, [clientes, filtro, busca]);

  // Volta para a página 1 sempre que o filtro ou a busca mudam
  useEffect(() => setPagina(1), [filtro, busca]);

  async function confirmarExclusao() {
    setEnviando(true);
    try {
      await excluirCliente(excluindo.id);
      setAviso(`Cliente "${excluindo.nome}" excluído.`);
      setExcluindo(null);
      carregar();
    } catch (e) {
      setAviso(e.message);
      setExcluindo(null);
    } finally {
      setEnviando(false);
    }
  }

  if (erro) return <Erro mensagem={erro} onTentarDeNovo={carregar} />;

  const totalPaginas = Math.max(1, Math.ceil(filtrados.length / POR_PAGINA));
  const visiveis = filtrados.slice((pagina - 1) * POR_PAGINA, pagina * POR_PAGINA);
  const contagem = (fn) => (clientes ?? []).filter(fn).length;

  return (
    <div className="space-y-4">
      <Aviso mensagem={aviso} />

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-sandro-borda/20 px-5 py-4">
          <Abas
            rotulo="Filtrar clientes por status"
            valor={filtro}
            onChange={setFiltro}
            opcoes={[
              { valor: "todos", rotulo: "Todos", contagem: clientes?.length },
              { valor: "ativos", rotulo: "Ativos", contagem: contagem((c) => !ehInativo(c)) },
              { valor: "inativos", rotulo: "Inativos", contagem: contagem(ehInativo) },
            ]}
          />
          <div className="w-full sm:w-72">
            <label htmlFor="busca-clientes" className="sr-only">Buscar por nome, empresa ou e-mail</label>
            <input id="busca-clientes" type="search" placeholder="Buscar por nome, empresa ou e-mail"
                   value={busca} onChange={(e) => setBusca(e.target.value)} className={classeEntrada} />
          </div>
        </div>

        {!clientes && <Carregando texto="Carregando clientes..." />}
        {clientes && filtrados.length === 0 && (
          <Vazio>{busca ? `Nenhum cliente encontrado para "${busca}".` : "Nenhum cliente neste filtro."}</Vazio>
        )}

        {visiveis.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Clientes da empresa</caption>
              <thead className="border-b border-sandro-borda/20 text-xs uppercase tracking-wider text-sandro-label">
                <tr>
                  <th scope="col" className="px-5 py-3 font-medium">Cliente</th>
                  <th scope="col" className="px-5 py-3 font-medium">Contato</th>
                  <th scope="col" className="px-5 py-3 font-medium">Status</th>
                  <th scope="col" className="px-5 py-3 font-medium"><span className="sr-only">Ações</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sandro-borda/15">
                {visiveis.map((c) => (
                  <tr key={c.id} className="text-slate-200 hover:bg-sandro-suporte/15">
                    <td className="px-5 py-3 font-medium text-white">{c.nome}</td>
                    <td className="px-5 py-3">
                      <span className="block">{c.email ?? "—"}</span>
                      <span className="block text-xs text-sandro-label">{c.telefone ?? ""}</span>
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge tom={TOM_STATUS[c.status] ?? "neutro"}>{c.status ?? "—"}</StatusBadge>
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex justify-end gap-2">
                        <Botao variante="contorno" tamanho="sm" onClick={() => navegar("clientes", c.id)}
                               aria-label={`Abrir ${c.nome}`}>
                          Abrir
                        </Botao>
                        {ehGestor && (
                          <Botao variante="perigo" tamanho="sm" onClick={() => setExcluindo(c)}
                                 aria-label={`Excluir ${c.nome}`}>
                            Excluir
                          </Botao>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <Paginacao pagina={pagina} totalPaginas={totalPaginas} totalItens={filtrados.length} onMudar={setPagina} />
      </Card>

      {excluindo && (
        <Modal
          titulo="Excluir cliente?"
          descricao={`"${excluindo.nome}" e todo o histórico de interações serão apagados. Vendas registradas continuam nos relatórios, sem o nome do cliente.`}
          onFechar={() => setExcluindo(null)}
          bloqueado={enviando}
        >
          <div className="flex justify-end gap-3">
            <Botao variante="fantasma" onClick={() => setExcluindo(null)} disabled={enviando}>Cancelar</Botao>
            <Botao variante="perigo" onClick={confirmarExclusao} carregando={enviando} textoCarregando="Excluindo...">
              Excluir definitivamente
            </Botao>
          </div>
        </Modal>
      )}
    </div>
  );
}
