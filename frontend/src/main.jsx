import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { iniciar } from "./pwa/aplicativo";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/animations.css";

// Antes de montar: os eventos de instalação e de versão nova chegam cedo,
// e quem não estiver ouvindo os perde.
iniciar();

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
