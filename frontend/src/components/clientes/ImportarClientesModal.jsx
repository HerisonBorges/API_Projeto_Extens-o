import { useId, useRef, useState } from "react";

import { baixarModeloClientes, exportarClientes, importarClientes } from "../../services/api.js";
import Botao from "../ui/Botao.jsx";
import Modal from "../ui/Modal.jsx";
import StatusBadge from "../ui/StatusBadge.jsx";
import { formatarDocumento, formatarMoeda } from "../ui/formatos.js";

const LIMITE_BYTES = 1024 * 1024;
const EXTENSOES = [".xlsx", ".csv"];

const tamanhoLegivel = (bytes) => (bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(0)} KB`);

/** Checagem só de conveniência (resposta imediata). O servidor valida tudo de novo. */
function problemaNoArquivo(arquivo) {
  const nome = arquivo.name.toLowerCase();
  if (!EXTENSOES.some((ext) => nome.endsWith(ext))) return "Envie um arquivo .xlsx ou .csv.";
  if (arquivo.size === 0) return "O arquivo está vazio.";
  if (arquivo.size > LIMITE_BYTES) return "O arquivo passa de 1 MB. Divida em arquivos menores.";
  return null;
}

function BarraProgresso({ rotulo, porcentagem }) {
  const enviado = porcentagem >= 100;
  return (
    <div className="space-y-1.5" aria-live="polite">
      <div className="flex justify-between text-xs text-sandro-label">
        <span>{enviado ? "Validando no servidor..." : rotulo}</span>
        <span className="tabular-nums">{porcentagem}%</span>
      </div>
      <div role="progressbar" aria-label={rotulo} aria-valuemin={0} aria-valuemax={100} aria-valuenow={porcentagem}
           className="h-2 overflow-hidden rounded-full bg-sandro-suporte/40">
        {/* transform (GPU) em vez de width: a barra anima sem recalcular o layout */}
        <div className={`h-full w-full origin-left bg-sandro-acento transition-transform duration-200
                         motion-reduce:transition-none ${enviado ? "animate-pulse" : ""}`}
             style={{ transform: `scaleX(${porcentagem / 100})` }} />
      </div>
    </div>
  );
}

function ListaErros({ erros, total }) {
  return (
    <div className="space-y-2">
      <p role="alert" className="rounded-lg bg-rose-950/80 px-3 py-2 text-sm text-rose-200">
        {total} problema(s) encontrados. <strong>Nada foi importado.</strong> Corrija na planilha e envie de novo.
      </p>
      <ul className="max-h-56 divide-y divide-sandro-borda/15 overflow-y-auto overscroll-contain rounded-lg border
                     border-sandro-borda/25 text-sm">
        {erros.map((e, i) => (
          <li key={`${e.linha}-${e.coluna}-${i}`} className="px-3 py-2">
            <span className="font-semibold text-white">Linha {e.linha}</span>
            <span className="text-sandro-label"> · {e.coluna}</span>
            <p className="text-rose-300">{e.mensagem}</p>
          </li>
        ))}
      </ul>
      {total > erros.length && (
        <p className="text-xs text-sandro-label">Mostrando os primeiros {erros.length} de {total}.</p>
      )}
    </div>
  );
}

function textoRecorrencia(r) {
  if (!r) return "—";
  const valor = r.tipo === "oportunidade" && r.valor != null ? ` · ${formatarMoeda(r.valor)}` : "";
  return `${r.descricao} · ${r.tipo === "oportunidade" ? "Oportunidade" : "Follow-up"}${valor}`;
}

function Previa({ linhas }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-sandro-label">
        Prévia das primeiras {linhas.length} linhas
      </h3>
      {/* Celular: cartões; a partir de sm: tabela com rolagem horizontal dentro do modal */}
      <ul className="space-y-2 sm:hidden">
        {linhas.map((l) => (
          <li key={l.linha} className="rounded-lg border border-sandro-borda/25 bg-sandro-fundo/50 px-3 py-2 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate font-medium text-white">{l.nome}</span>
              <span className="shrink-0 text-xs text-sandro-label">Linha {l.linha}</span>
            </div>
            <p className="truncate text-xs text-slate-300">
              {[formatarDocumento(l.documento), l.email, l.telefone].filter(Boolean).join(" · ") || "Sem contato"}
            </p>
            <p className="mt-1 text-xs text-sandro-label">{l.status} · {textoRecorrencia(l.recorrencia)}</p>
          </li>
        ))}
      </ul>
      <div className="rolagem-x hidden rounded-lg border border-sandro-borda/25 sm:block">
        <table className="w-full min-w-[40rem] text-left text-sm">
          <caption className="sr-only">Prévia das primeiras linhas da planilha</caption>
          <thead className="border-b border-sandro-borda/20 text-xs uppercase tracking-wider text-sandro-label">
            <tr>
              <th scope="col" className="px-3 py-2 font-medium">Linha</th>
              <th scope="col" className="px-3 py-2 font-medium">Cliente</th>
              <th scope="col" className="px-3 py-2 font-medium">CPF/CNPJ</th>
              <th scope="col" className="px-3 py-2 font-medium">Contato</th>
              <th scope="col" className="px-3 py-2 font-medium">Status</th>
              <th scope="col" className="px-3 py-2 font-medium">Recorrência</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-sandro-borda/15 text-slate-200">
            {linhas.map((l) => (
              <tr key={l.linha}>
                <td className="px-3 py-2 text-xs text-sandro-label">{l.linha}</td>
                <td className="px-3 py-2 font-medium text-white">{l.nome}</td>
                <td className="whitespace-nowrap px-3 py-2">{formatarDocumento(l.documento) ?? "—"}</td>
                <td className="px-3 py-2">
                  <span className="block">{l.email ?? "—"}</span>
                  <span className="block text-xs text-sandro-label">{l.telefone ?? ""}</span>
                </td>
                <td className="px-3 py-2">{l.status}</td>
                <td className="px-3 py-2 text-xs">{textoRecorrencia(l.recorrencia)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/**
 * Importar e exportar clientes em planilha (somente Gestor).
 * Etapas: escolher -> enviando (validação) -> prévia -> importando -> concluído.
 */
export default function ImportarClientesModal({ onFechar, onImportado }) {
  const idEntrada = useId();
  const entrada = useRef(null);
  const [etapa, setEtapa] = useState("escolher");
  const [arquivo, setArquivo] = useState(null);
  const [arrastando, setArrastando] = useState(false);
  const [progresso, setProgresso] = useState(0);
  const [resultado, setResultado] = useState(null);
  const [erro, setErro] = useState(null);
  const [baixando, setBaixando] = useState(null);

  const ocupado = etapa === "enviando" || etapa === "importando";

  async function validar(escolhido) {
    setErro(null);
    setResultado(null);
    const problema = problemaNoArquivo(escolhido);
    if (problema) {
      setArquivo(null);
      return setErro(problema);
    }
    setArquivo(escolhido);
    setProgresso(0);
    setEtapa("enviando");
    try {
      const r = await importarClientes(escolhido, { simular: true, onProgresso: setProgresso });
      setResultado(r);
      setEtapa("previa");
    } catch (e) {
      setErro(e.message);
      setEtapa("escolher");
    }
  }

  async function confirmar() {
    setErro(null);
    setProgresso(0);
    setEtapa("importando");
    try {
      const r = await importarClientes(arquivo, { onProgresso: setProgresso });
      setResultado(r);
      setEtapa("concluido");
      onImportado(r);
    } catch (e) {
      // 422: alguém mudou o banco entre a prévia e a confirmação (ex.: CPF cadastrado)
      if (e.corpo?.erros) setResultado({ ...e.corpo, valido: false });
      setErro(e.corpo?.erros ? null : e.message);
      setEtapa("previa");
    }
  }

  async function baixar(tipo, formato) {
    setErro(null);
    setBaixando(`${tipo}-${formato}`);
    try {
      await (tipo === "modelo" ? baixarModeloClientes(formato) : exportarClientes(formato));
    } catch (e) {
      setErro(e.message);
    } finally {
      setBaixando(null);
    }
  }

  function aoSoltar(e) {
    e.preventDefault();
    setArrastando(false);
    if (ocupado) return;
    const solto = e.dataTransfer.files?.[0];
    if (solto) validar(solto);
  }

  function recomecar() {
    setArquivo(null);
    setResultado(null);
    setErro(null);
    setEtapa("escolher");
    if (entrada.current) entrada.current.value = "";
  }

  return (
    <Modal titulo="Importar e exportar clientes"
           descricao="Planilha .xlsx ou .csv no modelo oficial, até 2000 linhas e 1 MB."
           onFechar={onFechar} bloqueado={ocupado} largura="max-w-3xl">
      <div className="space-y-5">
        {/* 1. Modelo e exportação */}
        <section aria-labelledby={`${idEntrada}-modelo`} className="space-y-2">
          <h3 id={`${idEntrada}-modelo`} className="text-xs font-medium uppercase tracking-wider text-sandro-label">
            1. Baixe o modelo ou seus clientes atuais
          </h3>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Botao tamanho="sm" variante="secundario" onClick={() => baixar("modelo", "xlsx")}
                   carregando={baixando === "modelo-xlsx"} textoCarregando="Baixando...">Modelo .xlsx</Botao>
            <Botao tamanho="sm" variante="secundario" onClick={() => baixar("modelo", "csv")}
                   carregando={baixando === "modelo-csv"} textoCarregando="Baixando...">Modelo .csv</Botao>
            <Botao tamanho="sm" variante="secundario" onClick={() => baixar("exportar", "xlsx")}
                   carregando={baixando === "exportar-xlsx"} textoCarregando="Baixando..."
                   aria-label="Exportar clientes atuais em .xlsx">Exportar .xlsx</Botao>
            <Botao tamanho="sm" variante="secundario" onClick={() => baixar("exportar", "csv")}
                   carregando={baixando === "exportar-csv"} textoCarregando="Baixando..."
                   aria-label="Exportar clientes atuais em .csv">Exportar .csv</Botao>
          </div>
          <p className="text-xs text-sandro-label">
            O modelo tem uma aba “Instruções”. Para dar várias recorrências ao mesmo cliente, repita a linha com o
            mesmo CPF/CNPJ.
          </p>
        </section>

        {/* 2. Envio */}
        <section aria-labelledby={`${idEntrada}-envio`} className="space-y-3">
          <h3 id={`${idEntrada}-envio`} className="text-xs font-medium uppercase tracking-wider text-sandro-label">
            2. Envie a planilha preenchida
          </h3>

          {(etapa === "escolher" || etapa === "previa") && (
            <label
              htmlFor={idEntrada}
              onDragOver={(e) => { e.preventDefault(); setArrastando(true); }}
              onDragLeave={() => setArrastando(false)}
              onDrop={aoSoltar}
              className={`flex min-h-32 cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2
                          border-dashed px-4 py-6 text-center transition
                          has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-sandro-acento
                          ${arrastando ? "border-sandro-acento bg-sandro-acento/10" : "border-sandro-borda/40 hover:border-sandro-acento/70"}`}
            >
              <input ref={entrada} id={idEntrada} type="file" accept=".xlsx,.csv" className="sr-only"
                     onChange={(e) => e.target.files?.[0] && validar(e.target.files[0])} />
              <span aria-hidden="true" className="text-2xl text-sandro-acento">⤒</span>
              <span className="text-sm font-medium text-white">
                {arquivo ? "Trocar arquivo" : "Arraste a planilha aqui ou toque para escolher"}
              </span>
              <span className="text-xs text-sandro-label">.xlsx ou .csv · até 1 MB</span>
            </label>
          )}

          {arquivo && (
            <p className="flex flex-wrap items-center gap-2 text-sm text-slate-200">
              <span aria-hidden="true">▤</span>
              <span className="min-w-0 truncate font-medium">{arquivo.name}</span>
              <span className="text-xs text-sandro-label">{tamanhoLegivel(arquivo.size)}</span>
            </p>
          )}

          {etapa === "enviando" && <BarraProgresso rotulo="Enviando para validação" porcentagem={progresso} />}
          {etapa === "importando" && <BarraProgresso rotulo="Importando" porcentagem={progresso} />}
          {erro && <p role="alert" className="rounded-lg bg-rose-950/80 px-3 py-2 text-sm text-rose-300">{erro}</p>}
        </section>

        {/* 3. Prévia / resultado */}
        {etapa === "previa" && resultado && (
          <section className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <StatusBadge tom="azul">{resultado.linhas} linha(s)</StatusBadge>
              <StatusBadge tom="azul">{resultado.clientes} cliente(s)</StatusBadge>
              <StatusBadge tom="azul">{resultado.recorrencias} recorrência(s)</StatusBadge>
              {resultado.valido
                ? <StatusBadge tom="permitido" icone="✓">Pronto para importar</StatusBadge>
                : <StatusBadge tom="bloqueado" icone="!">{resultado.total_erros} problema(s)</StatusBadge>}
            </div>
            {resultado.avisos?.length > 0 && (
              <p className="text-xs text-amber-200">{resultado.avisos.join(" · ")}</p>
            )}
            {!resultado.valido && <ListaErros erros={resultado.erros} total={resultado.total_erros} />}
            {resultado.previa?.length > 0 && <Previa linhas={resultado.previa} />}
          </section>
        )}

        {etapa === "concluido" && resultado && (
          <p role="status" className="rounded-lg bg-teal-950/70 px-3 py-3 text-sm text-teal-200">
            <span aria-hidden="true">✓ </span>{resultado.mensagem}
          </p>
        )}

        <div className="flex flex-col-reverse gap-3 border-t border-sandro-borda/20 pt-4 sm:flex-row sm:justify-end">
          {etapa === "concluido" ? (
            <>
              <Botao variante="fantasma" onClick={recomecar}>Importar outro arquivo</Botao>
              <Botao variante="primario" onClick={onFechar}>Concluir</Botao>
            </>
          ) : (
            <>
              <Botao variante="fantasma" onClick={onFechar} disabled={ocupado}>Cancelar</Botao>
              {etapa === "previa" && !resultado?.valido && (
                <Botao variante="secundario" onClick={recomecar}>Escolher outro arquivo</Botao>
              )}
              <Botao variante="primario" onClick={confirmar}
                     disabled={etapa !== "previa" || !resultado?.valido}
                     carregando={etapa === "importando"} textoCarregando="Importando...">
                {resultado?.valido ? `Importar ${resultado.clientes} cliente(s)` : "Importar"}
              </Botao>
            </>
          )}
        </div>
      </div>
    </Modal>
  );
}
