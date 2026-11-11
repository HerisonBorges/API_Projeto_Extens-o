import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Porta 5173 já está liberada no CORS do Flask (app.py).
// O preview usa a mesma porta: o dev server do Vite 8 recusa caminhos com ":"
// (ex.: "6 Semestre 2026:2"), então nessa pasta use "npm run homologacao".
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
  preview: { port: 5173, strictPort: true },
});
