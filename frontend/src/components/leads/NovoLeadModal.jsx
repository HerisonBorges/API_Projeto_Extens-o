import { useState } from "react";

import { criarCliente, criarOportunidade } from "../../services/api.js";
import Botao from "../ui/Botao.jsx";
import Campo, { classeEntrada } from "../ui/Campo.jsx";
import Modal from "../ui/Modal.jsx";

const VAZIO = { nome: "", email: "", telefone: "", titulo: "", valor: "" };

/** Cria o cliente (status Lead) e, se houver título, a oportunidade em Prospecção. */
export default function NovoLeadModal({ onFechar, onCriado }) {
  const [form, setForm] = useState(VAZIO);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);

  const alterar = (campo) => (e) => setForm((f) => ({ ...f, [campo]: e.target.value }));

  async function salvar(evento) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);

    let clienteId = null;
    try {
      clienteId = (await criarCliente({
        nome: form.nome.trim(),
        email: form.email.trim() || null,
        telefone: form.telefone.trim() || null,
        status: "Lead",
      })).cliente_id;

      if (form.titulo.trim()) {
        await criarOportunidade({
          cliente_id: clienteId,
          titulo: form.titulo.trim(),
          valor: Number(form.valor) || 0,
          etapa: "Prospecção",
        });
      }
      onCriado({ clienteId, nome: form.nome.trim() });
    } catch (e) {
      // Cliente criado mas oportunidade falhou: avisa sem perder o cadastro
      setErro(clienteId
        ? `Cliente salvo, mas a oportunidade não foi criada: ${e.message}`
        : e.message);
      setEnviando(false);
    }
  }

  return (
    <Modal
      titulo="Novo lead"
      descricao="Cadastra o contato como Lead e, se quiser, já abre uma oportunidade no funil."
      onFechar={onFechar}
      bloqueado={enviando}
      largura="max-w-lg"
    >
      <form onSubmit={salvar} className="grid gap-4 sm:grid-cols-2">
        <Campo rotulo="Nome ou empresa *" className="sm:col-span-2">
          {(p) => <input {...p} required autoComplete="off" value={form.nome} onChange={alterar("nome")} className={classeEntrada} />}
        </Campo>
        <Campo rotulo="E-mail">
          {(p) => <input {...p} type="email" value={form.email} onChange={alterar("email")} className={classeEntrada} />}
        </Campo>
        <Campo rotulo="Telefone">
          {(p) => <input {...p} type="tel" value={form.telefone} onChange={alterar("telefone")} className={classeEntrada} />}
        </Campo>
        <Campo rotulo="Oportunidade (opcional)" ajuda="Ex.: Orçamento de vitrine" className="sm:col-span-1">
          {(p) => <input {...p} value={form.titulo} onChange={alterar("titulo")} className={classeEntrada} />}
        </Campo>
        <Campo rotulo="Valor estimado (R$)">
          {(p) => (
            <input {...p} type="number" min="0" step="0.01" inputMode="decimal" disabled={!form.titulo.trim()}
                   value={form.valor} onChange={alterar("valor")} className={classeEntrada} />
          )}
        </Campo>

        {erro && (
          <p role="alert" className="rounded-lg bg-rose-950/80 px-3 py-2 text-sm text-rose-300 sm:col-span-2">{erro}</p>
        )}

        <div className="flex justify-end gap-3 pt-2 sm:col-span-2">
          <Botao variante="fantasma" onClick={onFechar} disabled={enviando}>Cancelar</Botao>
          <Botao variante="primario" type="submit" carregando={enviando} textoCarregando="Salvando...">
            Salvar lead
          </Botao>
        </div>
      </form>
    </Modal>
  );
}
