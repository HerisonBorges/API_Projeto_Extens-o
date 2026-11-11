import { useEffect, useState } from "react";

import Header from "./components/layout/Header.jsx";
import Sidebar from "./components/layout/Sidebar.jsx";
import NovoLeadModal from "./components/leads/NovoLeadModal.jsx";
import { Aviso } from "./components/ui/Estado.jsx";
import ClienteDetalhe from "./pages/ClienteDetalhe.jsx";
import Clientes from "./pages/Clientes.jsx";
import Configuracoes from "./pages/Configuracoes.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Followups from "./pages/Followups.jsx";
import Funil from "./pages/Funil.jsx";
import Login from "./pages/Login.jsx";
import Relatorios from "./pages/Relatorios.jsx";
import { ROTAS, navegar, podeAcessar, useRota } from "./rotas.js";
import { definirAoEncerrarSessao, encerrarSessao, lerSessao } from "./services/api.js";

const PAGINAS = {
  dashboard: Dashboard,
  clientes: Clientes,
  funil: Funil,
  followups: Followups,
  relatorios: Relatorios,
  configuracoes: Configuracoes,
};

export default function App() {
  const [usuario, setUsuario] = useState(lerSessao);
  const [avisoLogin, setAvisoLogin] = useState(null);
  const [novoLead, setNovoLead] = useState(false);
  const [aviso, setAviso] = useState(null);
  // Incrementa para as telas recarregarem (ex.: após "+ Novo Lead")
  const [versao, setVersao] = useState(0);
  const rota = useRota();

  // Qualquer HORARIO_BLOQUEADO, 401 ou "Sair" cai aqui e volta ao login
  useEffect(() => {
    definirAoEncerrarSessao((motivo) => {
      setUsuario(null);
      setNovoLead(false);
      setAvisoLogin(motivo);
    });
  }, []);

  const permitido = usuario && podeAcessar(rota.pagina, usuario.perfil);

  // Atendimento digitando #/relatorios: volta ao Dashboard
  useEffect(() => {
    if (usuario && !permitido) navegar("dashboard");
  }, [usuario, permitido]);

  useEffect(() => {
    const titulo = usuario ? ROTAS[rota.pagina].titulo : "Entrar";
    document.title = `${titulo} · SANDRO CRM`;
  }, [usuario, rota.pagina]);

  if (!usuario) {
    return (
      <Login
        aviso={avisoLogin}
        onEntrar={(u) => {
          setAvisoLogin(null);
          setUsuario(u);
        }}
      />
    );
  }

  const detalheCliente = rota.pagina === "clientes" && rota.id;
  const Pagina = PAGINAS[permitido ? rota.pagina : "dashboard"];

  return (
    <div className="min-h-screen bg-sandro-fundo text-slate-200 md:flex">
      <a href="#conteudo"
         className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg
                    focus:bg-sandro-acento focus:px-4 focus:py-2 focus:font-bold focus:text-sandro-fundo">
        Pular para o conteúdo
      </a>

      <Sidebar usuario={usuario} ativa={rota.pagina} onSair={() => encerrarSessao(null)} />

      <div className="min-w-0 flex-1">
        <main id="conteudo" tabIndex={-1} className="space-y-6 p-4 focus:outline-none md:p-8">
          <Header
            titulo={detalheCliente ? "Cliente" : ROTAS[permitido ? rota.pagina : "dashboard"].titulo}
            usuario={usuario}
            onNovoLead={() => setNovoLead(true)}
            onSair={() => encerrarSessao(null)}
          />
          <Aviso mensagem={aviso} />

          {detalheCliente
            ? <ClienteDetalhe id={rota.id} versao={versao} />
            : <Pagina usuario={usuario} versao={versao} />}
        </main>
      </div>

      {novoLead && (
        <NovoLeadModal
          onFechar={() => setNovoLead(false)}
          onCriado={({ clienteId, nome }) => {
            setNovoLead(false);
            setAviso(`Lead "${nome}" cadastrado.`);
            setVersao((v) => v + 1);
            navegar("clientes", clienteId);
          }}
        />
      )}
    </div>
  );
}
