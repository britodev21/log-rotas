import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";

import "./Toast.css";

const ICONES = {
  sucesso: CheckCircle2,
  erro: XCircle,
  atencao: AlertTriangle,
  info: Info,
};

function Toast({ toast, aoFechar }) {
  const Icone = ICONES[toast.tom] ?? Info;
  const urgente = toast.tom === "erro";

  return (
    <div
      className={`toast toast--${toast.tom}`}
      role={urgente ? "alert" : "status"}
      aria-live={urgente ? "assertive" : "polite"}
    >
      <Icone className="toast__icone" size={17} strokeWidth={2} aria-hidden="true" />

      <div className="toast__conteudo">
        {toast.titulo && <p className="toast__titulo">{toast.titulo}</p>}
        {toast.mensagem && <p className="toast__mensagem">{toast.mensagem}</p>}
      </div>

      <button
        type="button"
        className="toast__fechar"
        onClick={() => aoFechar(toast.id)}
        aria-label="Dispensar notificacao"
      >
        <X size={14} strokeWidth={2.2} aria-hidden="true" />
      </button>
    </div>
  );
}

export function ToastViewport({ toasts, aoFechar }) {
  if (toasts.length === 0) return null;

  return (
    <div className="toast-area">
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} aoFechar={aoFechar} />
      ))}
    </div>
  );
}
