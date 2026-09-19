import { Outlet } from "react-router-dom";
import { LogOut } from "lucide-react";

import { Avatar, Button, Logo, PageTransition } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import "./DriverLayout.css";

/**
 * Casca do motorista.
 *
 * Nao e a casca administrativa encolhida. Nao tem menu lateral, nao tem
 * navegacao em niveis e nao tem nada que exija mirar: o motorista esta de
 * pe, com pressa, as vezes segurando caixa. Tudo que se toca respeita o
 * alvo minimo de 48px.
 */
export function DriverLayout() {
  const { usuario, sair } = useAuth();

  return (
    <div className="mot">
      <header className="mot__topo">
        <Logo tamanho={26} comTexto={false} />

        <div className="mot__identificacao">
          <span className="mot__marca">Log Rotas</span>
          <span className="mot__nome">{usuario?.name}</span>
        </div>

        <Avatar nome={usuario?.name} tamanho={32} />

        <Button
          variante="sutil"
          tamanho="sm"
          icone={LogOut}
          onClick={sair}
          aria-label="Sair"
          className="mot__sair"
        />
      </header>

      <main className="mot__conteudo">
        <PageTransition>
          <Outlet />
        </PageTransition>
      </main>
    </div>
  );
}
