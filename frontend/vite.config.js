import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const LOCAL = /^http:\/\/(localhost|127\.0\.0\.1)(:\d{1,5})?$/;
const ORIGEM = /^https?:\/\/[^/\s?#]+$/;

/**
 * O build de produção (Netlify) precisa saber onde está a API. Sem isso o site
 * publicado tentaria falar com 127.0.0.1 e ninguém conseguiria entrar: melhor
 * o build falhar com a mensagem certa do que publicar um site quebrado.
 */
function validarApiUrl(valor) {
  const url = (valor ?? "").trim().replace(/\/+$/, "");
  if (!url) {
    throw new Error(
      "VITE_API_URL não definida. No Netlify: Site configuration > Environment variables " +
        "(ex.: https://sandro-crm-api.onrender.com)."
    );
  }
  if (!ORIGEM.test(url)) throw new Error(`VITE_API_URL inválida: "${url}" (use https://host, sem caminho).`);
  if (url.startsWith("http://") && !LOCAL.test(url)) {
    throw new Error(`VITE_API_URL precisa de https em produção: "${url}".`);
  }
  return url;
}

// Porta 5173 já está liberada no CORS do Flask em desenvolvimento.
// O dev server do Vite 8 recusa caminhos com ":" (ex.: "6 Semestre 2026:2"):
// nessa pasta use "npm run homologacao" (build em modo homologacao + preview).
export default defineConfig(({ command, mode }) => {
  // loadEnv lê .env.[mode] e também process.env (variáveis do painel do Netlify)
  const env = loadEnv(mode, process.cwd(), "VITE_");

  if (command === "build" && mode === "production") {
    validarApiUrl(env.VITE_API_URL);
  }

  return {
    plugins: [react(), tailwindcss()],
    server: { port: 5173 },
    preview: { port: 5173, strictPort: true },
    build: {
      // Mapas de código-fonte não vão para produção
      sourcemap: false,
    },
  };
});
