import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // host: true expoe o dev server na rede local, necessario para testar a
    // interface do motorista em um celular de verdade.
    //
    // ATENCAO: navegador so libera navigator.geolocation em contexto seguro.
    // http://localhost conta como seguro, http://192.168.x.x NAO. Para testar
    // localizacao no celular sera preciso HTTPS (tunel ou certificado local).
    // Ver docs/LIMITACOES.md.
    host: true,
    proxy: {
      // Evita CORS no desenvolvimento: o frontend chama /api e o Vite
      // encaminha para o backend.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
