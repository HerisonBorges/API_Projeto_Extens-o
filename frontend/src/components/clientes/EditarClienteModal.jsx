import { useState } from "react";

import { alterarCliente } from "../../services/api.js";
import Botao from "../ui/Botao.jsx";
import Campo, { classeEntrada } from "../ui/Campo.jsx";
import Modal from "../ui/Modal.jsx";

export const STATUS_CLIENTE = [
  { valor: "Lead", descricao: "Ainda não comprou" },
  { valor: "Cliente", descricao: "Já comprou" },
  { valor: "Inativo", descricao: "Sem relacionamento ativo" },
];

const normalizar = (v) => (v ?? "").trim();

/** Edita nome, e-mail, telefone e status. Envia só o que mudou. */
export default function EditarClienteModal({ cliente, onFechar, onSalvo }) {
  const [form, setForm] = useState({
    nome: cliente.nome ?? "",
    email: cliente.email ?? "",
    telefone: cliente.telefone ?? "",
    status: cliente.status ?? "Lead",
  });
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);

  const alterar = (campo) => (e) => setForm((f) => ({ ...f, [campo]: e.target.value }));

  const mudancas = Object.fromEntries(
    Object.entries(form).filter(([campo, valor]) => normalizar(valor) !== normalizar(cliente[campo]))
  );
  const nadaMudou = Object.keys(mudancas).length === 0;

  async function salvar(e) {
    e.preventDefault();
    setErro(null);
    if (!form.nome.trim()) return setErro("O nome é obrigatório.");

    setEnviando(true);
    try {
      const resposta = await alterarCliente(cliente.id, mudancas);
      onSalvo(resposta.cliente);
    } catch (erroApi) {
      setErro(erroApi.message);
      setEnviando(false);
    }
  }

  return (
    <Modal titulo="Editar cliente" descricao={cliente.nome} onFechar={onFechar} bloqueado={enviando} largura="max-w-lg">
      <form onSubmit={salvar} className="grid gap-4 sm:grid-cols-2">
        <Campo rotulo="Nome ou empresa *" className="sm:col-span-2">
          {(p) => <input {...p} required maxLength={150} value={form.nome} onChange={alterar("nome")} className={classeEntrada} />}
        </Campo>
        <Campo rotulo="E-mail" ajuda="Deixe em branco para remover.">
          {(p) => <input {...p} type="email" maxLength={150} value={form.email} onChange={alterar("email")} className={classeEntrada} />}
        </Campo>
        <Campo rotulo="Telefone" ajuda="Ex.: (11) 90000-0000">
          {(p) => <input {...p} type="tel" maxLength={30} value={form.telefone} onChange={alterar("telefone")} className={classeEntrada} />}
        </Campo>

        <fieldset className="sm:col-span-2">
          <legend className="mb-2 text-xs font-medium text-sandro-label">Status</legend>
          <div className="grid gap-2 sm:grid-cols-3">
            {STATUS_CLIENTE.map(({ valor, descricao }) => (
              <label key={valor}
                     className={`flex cursor-pointer flex-col rounded-lg border px-3 py-2 text-sm transition
                                 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-sandro-acento
                                 ${form.status === valor
                                   ? "border-sandro-acento bg-sandro-acento/10 text-white"
                                   : "border-sandro-borda/40 text-sandro-label hover:text-white"}`}>
                <input type="radio" name="status-cliente" value={valor} checked={form.status === valor}
                       onChange={alterar("status")} className="sr-only" />
                <span className="font-semibold">{valor}</span>
                <span className="text-xs text-sandro-label">{descricao}</span>
              </label>
            ))}
          </div>
        </fieldset>

        {erro && (
          <p role="alert" className="rounded-lg bg-rose-950/80 px-3 py-2 text-sm text-rose-300 sm:col-span-2">{erro}</p>
        )}

        <div className="flex justify-end gap-3 pt-1 sm:col-span-2">
          <Botao variante="fantasma" onClick={onFechar} disabled={enviando}>Cancelar</Botao>
          <Botao variante="primario" type="submit" carregando={enviando} textoCarregando="Salvando..."
                 disabled={nadaMudou}>
            Salvar alterações
          </Botao>
        </div>
      </form>
    </Modal>
  );
}
