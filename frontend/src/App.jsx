import { useEffect, useState } from "react";

import Sidebar from "./components/layout/Sidebar.jsx";
import Configuracoes from "./pages/Configuracoes.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Login from "./pages/Login.jsx";
import { definirAoEncerrarSessao, encerrarSessao, lerSessao } from "./services/api.js";

export default function App() {
  const [usuario, setUsuario] = useState(lerSessao);
  const [pagina, setPagina] = useState("dashboard");
  const [avisoLogin, setAvisoLogin] = useState(null);

  // Qualquer resposta HORARIO_BLOQUEADO ou 401 cai aqui e volta ao login
  useEffect(() => {
    definirAoEncerrarSessao((motivo) => {
      setUsuario(null);
      setPagina("dashboard");
      setAvisoLogin(motivo);
    });
  }, []);

  if (!usuario) {
    return (
      <Fundo>
        <Login
          aviso={avisoLogin}
          onEntrar={(u) => {
            setAvisoLogin(null);
            setUsuario(u);
          }}
        />
      </Fundo>
    );
  }

  const podeConfigurar = usuario.perfil === "Gestor";

  return (
    <Fundo>
      <div className="flex min-h-screen flex-col md:flex-row">
        <Sidebar
          usuario={usuario}
          ativa={pagina}
          onNavegar={setPagina}
          onSair={() => encerrarSessao(null)}
        />
        <main className="flex-1 p-4 md:p-8">
          {pagina === "configuracoes" && podeConfigurar ? (
            <Configuracoes />
          ) : (
            <Dashboard usuario={usuario} />
          )}
        </main>
      </div>
    </Fundo>
  );
}

// Fundo escuro com iluminação radial ciano desfocada
function Fundo({ children }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-kindra-fundo text-slate-200">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 left-1/3 h-[32rem] w-[32rem] rounded-full
                   bg-kindra-acento/20 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-48 -right-24 h-[28rem] w-[28rem] rounded-full
                   bg-kindra-borda/20 blur-3xl"
      />
      <div className="relative">{children}</div>
    </div>
  );
}
