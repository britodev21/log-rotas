import { useId } from "react";

import "./Field.css";

/**
 * Campo de formulário com rótulo, ajuda e erro ligados por aria.
 *
 * Centralizar isso evita o erro clássico do rótulo solto, que quebra leitor
 * de tela e impede o clique no texto para focar o campo.
 *
 * Nenhum erro de formulário usa alert() do navegador: a mensagem nasce
 * junto do campo que a causou.
 */
export function Field({ label, erro, ajuda, obrigatorio = false, children, id }) {
  const gerado = useId();
  const campoId = id || gerado;
  const ajudaId = ajuda ? `${campoId}-ajuda` : undefined;
  const erroId = erro ? `${campoId}-erro` : undefined;

  return (
    <div className={`campo ${erro ? "campo--erro" : ""}`}>
      {label && (
        <label className="campo__rotulo" htmlFor={campoId}>
          {label}
          {obrigatorio && (
            <span className="campo__obrigatorio" aria-hidden="true">
              *
            </span>
          )}
        </label>
      )}

      {children({
        id: campoId,
        "aria-describedby": [ajudaId, erroId].filter(Boolean).join(" ") || undefined,
        "aria-invalid": erro ? true : undefined,
      })}

      {ajuda && !erro && (
        <p className="campo__ajuda" id={ajudaId}>
          {ajuda}
        </p>
      )}
      {erro && (
        <p className="campo__erro" id={erroId} role="alert">
          {erro}
        </p>
      )}
    </div>
  );
}

/** Input com suporte a ícone à esquerda e elemento à direita. */
export function InputField({
  label,
  erro,
  ajuda,
  obrigatorio,
  icone: Icone,
  aDireita,
  className = "",
  ...props
}) {
  return (
    <Field label={label} erro={erro} ajuda={ajuda} obrigatorio={obrigatorio}>
      {(atributos) => (
        <div
          className={`controle ${Icone ? "controle--com-icone" : ""} ${
            aDireita ? "controle--com-acao" : ""
          }`}
        >
          {Icone && (
            <Icone size={16} strokeWidth={2} className="controle__icone" aria-hidden="true" />
          )}
          <input className={`controle__campo ${className}`} {...atributos} {...props} />
          {aDireita && <div className="controle__acao">{aDireita}</div>}
        </div>
      )}
    </Field>
  );
}

export function SelectField({ label, erro, ajuda, obrigatorio, children, className = "", ...props }) {
  return (
    <Field label={label} erro={erro} ajuda={ajuda} obrigatorio={obrigatorio}>
      {(atributos) => (
        <div className="controle controle--select">
          <select className={`controle__campo ${className}`} {...atributos} {...props}>
            {children}
          </select>
          {/* Seta própria: a nativa varia entre navegadores e destoaria do
              resto do sistema. */}
          <svg
            className="controle__seta"
            width="12"
            height="12"
            viewBox="0 0 12 12"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M3 4.5 6 7.5 9 4.5"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      )}
    </Field>
  );
}

export function TextareaField({ label, erro, ajuda, obrigatorio, className = "", ...props }) {
  return (
    <Field label={label} erro={erro} ajuda={ajuda} obrigatorio={obrigatorio}>
      {(atributos) => (
        <div className="controle">
          <textarea
            className={`controle__campo controle__campo--area ${className}`}
            rows={3}
            {...atributos}
            {...props}
          />
        </div>
      )}
    </Field>
  );
}
