import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { Button } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import "./AdminLayout.css";

// Itens ja implementados.
const NAVEGACAO = [
  { para: "/admin", rotulo: "Painel", fim: true },
  { para: "/admin/usuarios", rotulo: "Usuarios" },
  { para: "/admin/configuracoes", rotulo: "Configuracoes" },
];

// Itens que ainda nao existem. Aparecem desabilitados, com a fase em que
// entram, em vez de levarem a uma tela vazia fingindo funcionar.
const PLANEJADO = [
  { rotulo: "Entregas", fase: "Fase 3" },
  { rotulo: "Clientes", fase: "Fase 3" },
  { rotulo: "Motoristas", fase: "Fase 3" },
  { rotulo: "Veiculos", fase: "Fase 3" },
  { rotulo: "Bases", fase: "Fase 3" },
  { rotulo: "Planejador", fase: "Fase 7" },
  { rotulo: "Rotas", fase: "Fase 7" },
];

export function AdminLayout() {
  const { usuario, sair } = useAuth();
  const [menuAberto, setMenuAberto] = useState(false);

  return (
    <div className="admin">
      <header className="admin__topo">
        <button
          type="button"
          className="admin__menu-botao"
          onClick={() => setMenuAberto((v) => !v)}
          aria-expanded={menuAberto}
          aria-label="Abrir menu"
        >
          <span aria-hidden="true">&#9776;</span>
        </button>

        <span className="admin__marca">Log Rotas</span>

        <div className="admin__usuario">
          <span className="admin__usuario-nome">{usuario?.name}</span>
          <Button variante="secundario" onClick={sair}>
            Sair
          </Button>
        </div>
      </header>

      <div className="admin__corpo">
        <nav
          className={`admin__lateral ${menuAberto ? "admin__lateral--aberta" : ""}`}
          aria-label="Menu principal"
        >
          <ul className="admin__lista">
            {NAVEGACAO.map((item) => (
              <li key={item.para}>
                <NavLink
                  to={item.para}
                  end={item.fim}
                  className={({ isActive }) =>
                    `admin__link ${isActive ? "admin__link--ativo" : ""}`
                  }
                  onClick={() => setMenuAberto(false)}
                >
                  {item.rotulo}
                </NavLink>
              </li>
            ))}
          </ul>

          <p className="admin__secao">Em construcao</p>
          <ul className="admin__lista">
            {PLANEJADO.map((item) => (
              <li key={item.rotulo}>
                <span className="admin__link admin__link--planejado" aria-disabled="true">
                  {item.rotulo}
                  <span className="admin__fase">{item.fase}</span>
                </span>
              </li>
            ))}
          </ul>
        </nav>

        {menuAberto && (
          <div
            className="admin__sombra"
            onClick={() => setMenuAberto(false)}
            aria-hidden="true"
          />
        )}

        <main className="admin__conteudo">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
