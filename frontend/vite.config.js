import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Porta 5173 já está liberada no CORS do Flask (app.py)
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
});
