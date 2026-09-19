import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { LogOut, Menu, PanelLeftClose, User, X } from "lucide-react";

import {
  Avatar,
  Button,
  Dropdown,
  DropdownItem,
  DropdownLabel,
  DropdownSeparator,
  Logo,
  PageTransition,
  ThemeToggle,
  Tooltip,
} from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { CONTEXTO_ROTA, GRUPOS } from "./navegacao";
import "./AdminLayout.css";

export function AdminLayout() {
  const { usuario, sair } = useAuth();
  const { pathname } = useLocation();

  const [gavetaAberta, setGavetaAberta] = useState(false);
  const [recolhida, setRecolhida] = useState(() => {
    try {
      return localStorage.getItem("logrotas.lateral") === "recolhida";
    } catch {
      return false;
    }
  });

  // Navegar fecha a gaveta: no celular ela cobre a tela, e deixá-la aberta
  // esconderia exatamente a página que a pessoa acabou de pedir.
  useEffect(() => {
    setGavetaAberta(false);
  }, [pathname]);

  useEffect(() => {
    if (!gavetaAberta) return;
    const aoTeclar = (e) => e.key === "Escape" && setGavetaAberta(false);
    document.addEventListener("keydown", aoTeclar);
    return () => document.removeEventListener("keydown", aoTeclar);
  }, [gavetaAberta]);

  function alternarRecolhida() {
    const proximo = !recolhida;
    setRecolhida(proximo);
    try {
      localStorage.setItem("logrotas.lateral", proximo ? "recolhida" : "expandida");
    } catch {
      /* preferência vale só nesta sessão */
    }
  }

  const contexto = CONTEXTO_ROTA[pathname] ?? { titulo: "Log Rotas", contexto: "" };

  return (
    <div className={`app ${recolhida ? "app--recolhida" : ""}`}>
      {/* --- Lateral ---------------------------------------------------- */}
      <aside
        className={`lateral ${gavetaAberta ? "lateral--aberta" : ""}`}
        aria-label="Menu principal"
      >
        <div className="lateral__marca">
          {recolhida ? <Logo tamanho={26} comTexto={false} /> : <Logo tamanho={26} />}
          <button
            type="button"
            className="lateral__fechar"
            onClick={() => setGavetaAberta(false)}
            aria-label="Fechar menu"
          >
            <X size={18} strokeWidth={2} aria-hidden="true" />
          </button>
        </div>

        <nav className="lateral__nav">
          {GRUPOS.map((grupo) => (
            <div className="lateral__grupo" key={grupo.titulo}>
              <p className="lateral__grupo-titulo">{grupo.titulo}</p>
              <ul>
                {grupo.itens.map((item) => (
                  <li key={item.rotulo}>
                    {item.para ? (
                      <NavLink
                        to={item.para}
                        end={item.fim}
                        className={({ isActive }) =>
                          `nav-item ${isActive ? "nav-item--ativo" : ""}`
                        }
                        title={recolhida ? item.rotulo : undefined}
                      >
                        <item.icone size={17} strokeWidth={2} aria-hidden="true" />
                        <span className="nav-item__rotulo">{item.rotulo}</span>
                      </NavLink>
                    ) : (
                      <span
                        className="nav-item nav-item--futuro"
                        aria-disabled="true"
                        title={`Disponível na ${item.fase}`}
                      >
                        <item.icone size={17} strokeWidth={2} aria-hidden="true" />
                        <span className="nav-item__rotulo">{item.rotulo}</span>
                        <span className="nav-item__fase">{item.fase}</span>
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="lateral__rodape">
          <Tooltip texto={recolhida ? "Expandir menu" : "Recolher menu"} lado="direita">
            <Button
              variante="sutil"
              tamanho="sm"
              icone={PanelLeftClose}
              onClick={alternarRecolhida}
              className="lateral__recolher"
              aria-label={recolhida ? "Expandir menu" : "Recolher menu"}
            />
          </Tooltip>
        </div>
      </aside>

      {gavetaAberta && (
        <div
          className="app__cobertura"
          onClick={() => setGavetaAberta(false)}
          aria-hidden="true"
        />
      )}

      {/* --- Coluna principal -------------------------------------------- */}
      <div className="app__coluna">
        <header className="topo">
          <button
            type="button"
            className="topo__menu"
            onClick={() => setGavetaAberta(true)}
            aria-label="Abrir menu"
          >
            <Menu size={20} strokeWidth={2} aria-hidden="true" />
          </button>

          <div className="topo__contexto">
            <h2 className="topo__titulo">{contexto.titulo}</h2>
            {contexto.contexto && (
              <p className="topo__descricao">{contexto.contexto}</p>
            )}
          </div>

          <div className="topo__acoes">
            <ThemeToggle />

            <Dropdown
              gatilho={
                <button type="button" className="topo__usuario" aria-label="Menu do usuário">
                  <Avatar nome={usuario?.name} tamanho={28} />
                  <span className="topo__usuario-nome">{usuario?.name}</span>
                </button>
              }
            >
              <DropdownLabel>{usuario?.email}</DropdownLabel>
              <DropdownSeparator />
              <DropdownItem icone={User} disabled>
                Meu perfil
              </DropdownItem>
              <DropdownSeparator />
              <DropdownItem icone={LogOut} onClick={sair} perigo>
                Sair
              </DropdownItem>
            </Dropdown>
          </div>
        </header>

        <main className="app__conteudo">
          <PageTransition>
            <Outlet />
          </PageTransition>
        </main>
      </div>
    </div>
  );
}
