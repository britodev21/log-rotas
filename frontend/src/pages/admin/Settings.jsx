import { useEffect, useState } from "react";

import { mensagemDeErro } from "../../api/client";
import { buscarConfiguracoes, salvarConfiguracoes } from "../../api/settings";
import { Alert, Button, Card, InputField, PageHeader } from "../../components/ui";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import "./admin.css";

const CAMPOS_TEXTO = [
  { campo: "company_name", label: "Nome da empresa", obrigatorio: true },
  { campo: "document", label: "CNPJ" },
  { campo: "phone", label: "Telefone" },
  { campo: "email", label: "E-mail de contato", type: "email" },
];

export function Settings() {
  useDocumentTitle("Configuracoes");

  const [form, setForm] = useState(null);
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    let cancelado = false;
    buscarConfiguracoes()
      .then((dados) => !cancelado && setForm(dados))
      .catch(
        (e) =>
          !cancelado &&
          setErro(mensagemDeErro(e, "Nao foi possivel carregar a configuracao.")),
      );
    return () => {
      cancelado = true;
    };
  }, []);

  const alterar = (campo) => (evento) =>
    setForm((atual) => ({ ...atual, [campo]: evento.target.value }));

  async function aoEnviar(evento) {
    evento.preventDefault();
    setErro("");
    setAviso("");
    setSalvando(true);
    try {
      const atualizado = await salvarConfiguracoes({
        company_name: form.company_name,
        document: form.document,
        phone: form.phone,
        email: form.email,
        timezone: form.timezone,
        default_stop_service_minutes: Number(form.default_stop_service_minutes),
      });
      setForm(atualizado);
      setAviso("Configuracao salva.");
    } catch (e) {
      setErro(mensagemDeErro(e, "Nao foi possivel salvar."));
    } finally {
      setSalvando(false);
    }
  }

  if (!form) {
    return (
      <>
        <PageHeader titulo="Configuracoes" />
        {erro ? <Alert tom="erro">{erro}</Alert> : <p className="texto-suave">Carregando...</p>}
      </>
    );
  }

  return (
    <>
      <PageHeader
        titulo="Configuracoes"
        descricao="Dados da empresa e parametros usados pelo planejamento de rotas."
      />

      {erro && <Alert tom="erro">{erro}</Alert>}
      {aviso && <Alert tom="sucesso">{aviso}</Alert>}

      <form onSubmit={aoEnviar} noValidate>
        <div className="grade grade--duas">
          <Card titulo="Empresa">
            <div className="pilha">
              {CAMPOS_TEXTO.map(({ campo, label, type, obrigatorio }) => (
                <InputField
                  key={campo}
                  label={label}
                  type={type}
                  value={form[campo] ?? ""}
                  onChange={alterar(campo)}
                  obrigatorio={obrigatorio}
                  required={obrigatorio}
                />
              ))}
            </div>
          </Card>

          <Card titulo="Operacao">
            <div className="pilha">
              <InputField
                label="Fuso horario"
                value={form.timezone ?? ""}
                onChange={alterar("timezone")}
                ajuda="Usado para definir a data de operacao das rotas."
              />
              <InputField
                label="Tempo padrao por parada (minutos)"
                type="number"
                min="1"
                max="1440"
                value={form.default_stop_service_minutes ?? ""}
                onChange={alterar("default_stop_service_minutes")}
                ajuda="Tempo gasto em cada parada quando a entrega nao informa o seu."
              />

              <Alert tom="atencao" titulo="Este numero ainda e um chute">
                O valor inicial foi estimado, nao medido. Quando a operacao
                registrar entregas reais, ajuste-o aqui: e ele que determina
                quantos servicos cabem no dia de cada equipe.
              </Alert>
            </div>
          </Card>
        </div>

        <div className="tabela__acoes" style={{ marginTop: "var(--esp-5)" }}>
          <Button type="submit" carregando={salvando}>
            Salvar alteracoes
          </Button>
        </div>
      </form>
    </>
  );
}
