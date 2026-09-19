import { AlertTriangle, RotateCw } from "lucide-react";

import { Button } from "./Button";
import "./States.css";

/**
 * Estado vazio.
 *
 * Tela sem dado não pode parecer tela quebrada. Todo estado vazio diz o que
 * está faltando, por que importa e qual é o próximo passo — com o botão que
 * executa esse passo, quando ele existe.
 */
export function EmptyState({ icone: Icone, titulo, children, acao, compacto = false }) {
  return (
    <div className={`estado ${compacto ? "estado--compacto" : ""}`}>
      {Icone && (
        <div className="estado__icone" aria-hidden="true">
          <Icone size={20} strokeWidth={1.8} />
        </div>
      )}
      <h4 className="estado__titulo">{titulo}</h4>
      {children && <div className="estado__texto">{children}</div>}
      {acao && <div className="estado__acao">{acao}</div>}
    </div>
  );
}

/**
 * Estado de erro com possibilidade de nova tentativa.
 *
 * O usuário lê uma frase em português; o detalhe técnico vai para o console,
 * onde serve a quem precisa depurar. Mostrar "AxiosError: Request failed with
 * status code 500" na tela não ajuda ninguém a resolver nada.
 */
export function ErrorState({
  titulo = "Não foi possível carregar",
  mensagem = "Tente novamente em alguns instantes.",
  aoTentarNovamente,
  compacto = false,
}) {
  return (
    <div className={`estado estado--erro ${compacto ? "estado--compacto" : ""}`}>
      <div className="estado__icone estado__icone--erro" aria-hidden="true">
        <AlertTriangle size={20} strokeWidth={1.8} />
      </div>
      <h4 className="estado__titulo">{titulo}</h4>
      <div className="estado__texto">
        <p>{mensagem}</p>
      </div>
      {aoTentarNovamente && (
        <div className="estado__acao">
          <Button variante="secundario" icone={RotateCw} onClick={aoTentarNovamente}>
            Tentar novamente
          </Button>
        </div>
      )}
    </div>
  );
}
