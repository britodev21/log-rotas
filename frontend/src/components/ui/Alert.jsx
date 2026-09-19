import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";

import "./Alert.css";

const ICONES = {
  sucesso: CheckCircle2,
  erro: XCircle,
  atencao: AlertTriangle,
  info: Info,
};

/**
 * Aviso fixo no fluxo da pagina.
 *
 * Diferente do toast: o toast confirma uma acao e some; o Alert explica uma
 * condicao permanente da tela ("este numero ainda e uma estimativa", "estas
 * entregas estao sem endereco"). Se a mensagem some sozinha, e toast.
 */
export function Alert({ tom = "info", titulo, acao, children }) {
  const Icone = ICONES[tom] ?? Info;
  const urgente = tom === "erro" || tom === "atencao";

  return (
    <div
      className={`aviso aviso--${tom}`}
      role={urgente ? "alert" : "status"}
      aria-live={urgente ? "assertive" : "polite"}
    >
      <Icone className="aviso__icone" size={16} strokeWidth={2} aria-hidden="true" />
      <div className="aviso__conteudo">
        {titulo && <p className="aviso__titulo">{titulo}</p>}
        {children && <div className="aviso__corpo">{children}</div>}
      </div>
      {acao && <div className="aviso__acao">{acao}</div>}
    </div>
  );
}
