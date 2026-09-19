import { useId } from "react";

import "./Field.css";

/**
 * Campo de formulario com rotulo, ajuda e erro ligados por aria.
 *
 * Centralizar isso evita o erro classico de rotulo solto, que quebra leitor
 * de tela e o clique no texto do rotulo.
 */
export function Field({ label, erro, ajuda, obrigatorio = false, children, id }) {
  const gerado = useId();
  const campoId = id || gerado;
  const ajudaId = ajuda ? `${campoId}-ajuda` : undefined;
  const erroId = erro ? `${campoId}-erro` : undefined;

  return (
    <div className={`campo ${erro ? "campo--erro" : ""}`}>
      <label className="campo__rotulo" htmlFor={campoId}>
        {label}
        {obrigatorio && (
          <span className="campo__obrigatorio" aria-hidden="true">
            *
          </span>
        )}
      </label>

      {children({
        id: campoId,
        "aria-describedby": [ajudaId, erroId].filter(Boolean).join(" ") || undefined,
        "aria-invalid": erro ? true : undefined,
        className: "campo__controle",
      })}

      {ajuda && !erro && (
        <p className="campo__ajuda" id={ajudaId}>
          {ajuda}
        </p>
      )}
      {erro && (
        <p className="campo__mensagem-erro" id={erroId} role="alert">
          {erro}
        </p>
      )}
    </div>
  );
}

/** Atalho para o caso mais comum: um <input> simples. */
export function InputField({ label, erro, ajuda, obrigatorio, ...props }) {
  return (
    <Field label={label} erro={erro} ajuda={ajuda} obrigatorio={obrigatorio}>
      {(atributos) => <input {...atributos} {...props} />}
    </Field>
  );
}

/** Atalho para <select>. */
export function SelectField({ label, erro, ajuda, obrigatorio, children, ...props }) {
  return (
    <Field label={label} erro={erro} ajuda={ajuda} obrigatorio={obrigatorio}>
      {(atributos) => (
        <select {...atributos} {...props}>
          {children}
        </select>
      )}
    </Field>
  );
}
