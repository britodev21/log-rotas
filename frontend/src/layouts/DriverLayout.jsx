import { useState } from "react";
import { Outlet } from "react-router-dom";
import { KeyRound, LogOut } from "lucide-react";

import { Avatar, Button, Logo, PageTransition } from "../components/ui";
import { AvisoSenhaFraca, MinhaConta } from "../components/domain";
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
  const [contaAberta, setContaAberta] = useState(false);

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
          icone={KeyRound}
          onClick={() => setContaAberta(true)}
          aria-label="Minha conta"
          className="mot__sair"
        />

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
        <AvisoSenhaFraca aoAbrir={() => setContaAberta(true)} />
        <PageTransition>
          <Outlet />
        </PageTransition>
      </main>
      <MinhaConta aberto={contaAberta} onFechar={() => setContaAberta(false)} />
    </div>
  );
}
