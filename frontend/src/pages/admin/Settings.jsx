import { useCallback, useEffect, useState } from "react";
import { Building2, Clock, Save } from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { buscarConfiguracoes, salvarConfiguracoes } from "../../api/settings";
import {
  Alert,
  Button,
  Card,
  ErrorState,
  InputField,
  PageHeader,
  SkeletonText,
} from "../../components/ui";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { useToast } from "../../hooks/useToast";
import "./admin.css";

const CAMPOS_EMPRESA = [
  { campo: "company_name", label: "Nome da empresa", obrigatorio: true },
  { campo: "document", label: "CNPJ", placeholder: "00.000.000/0000-00" },
  { campo: "phone", label: "Telefone", placeholder: "(67) 0000-0000" },
  { campo: "email", label: "E-mail de contato", type: "email" },
];

export function Settings() {
  useDocumentTitle("Configurações");
  const toast = useToast();

  const [form, setForm] = useState(null);
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [alterado, setAlterado] = useState(false);

  const carregar = useCallback(async () => {
    setErro("");
    try {
      setForm(await buscarConfiguracoes());
      setAlterado(false);
    } catch (e) {
      console.error("Falha ao carregar configurações", e);
      setErro(mensagemDeErro(e, "Não foi possível carregar a configuração."));
    }
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const alterar = (campo) => (evento) => {
    setForm((atual) => ({ ...atual, [campo]: evento.target.value }));
    setAlterado(true);
  };

  async function enviar(evento) {
    evento.preventDefault();
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
      setAlterado(false);
      toast.sucesso("Configuração salva");
    } catch (e) {
      console.error("Falha ao salvar configurações", e);
      toast.erro("Não foi possível salvar", mensagemDeErro(e));
    } finally {
      setSalvando(false);
    }
  }

  if (erro && !form) {
    return (
      <>
        <PageHeader titulo="Configurações" />
        <Card>
          <ErrorState mensagem={erro} aoTentarNovamente={carregar} />
        </Card>
      </>
    );
  }

  if (!form) {
    return (
      <>
        <PageHeader titulo="Configurações" />
        <div className="form-grade">
          <Card titulo="Empresa">
            <SkeletonText linhas={6} />
          </Card>
          <Card titulo="Operação">
            <SkeletonText linhas={4} />
          </Card>
        </div>
      </>
    );
  }

  return (
    <form onSubmit={enviar} noValidate>
      <PageHeader
        titulo="Configurações"
        descricao="Dados da empresa e parâmetros usados pelo planejamento de rotas."
        acoes={
          <Button
            type="submit"
            icone={Save}
            carregando={salvando}
            disabled={!alterado}
            title={alterado ? undefined : "Nenhuma alteração para salvar"}
          >
            Salvar alterações
          </Button>
        }
      />

      <div className="form-grade">
        <Card titulo="Empresa" descricao="Identificação usada nos relatórios e documentos.">
          <div className="pilha">
            {CAMPOS_EMPRESA.map(({ campo, label, type, obrigatorio, placeholder }) => (
              <InputField
                key={campo}
                label={label}
                type={type}
                placeholder={placeholder}
                icone={campo === "company_name" ? Building2 : undefined}
                value={form[campo] ?? ""}
                onChange={alterar(campo)}
                obrigatorio={obrigatorio}
                required={obrigatorio}
              />
            ))}
          </div>
        </Card>

        <Card titulo="Operação" descricao="Parâmetros que o planejador vai usar.">
          <div className="pilha">
            <InputField
              label="Fuso horário"
              value={form.timezone ?? ""}
              onChange={alterar("timezone")}
              ajuda="Define a data de operação das rotas."
            />

            <InputField
              label="Tempo padrão por parada"
              type="number"
              min="1"
              max="1440"
              icone={Clock}
              value={form.default_stop_service_minutes ?? ""}
              onChange={alterar("default_stop_service_minutes")}
              ajuda="Minutos gastos em cada parada quando a entrega não informa o seu."
            />

            <Alert tom="atencao" titulo="Este número ainda é uma estimativa">
              O valor foi chutado, não medido. Numa operação dentro de Campo
              Grande, com deslocamentos de 10 a 25 minutos, é ele — e não a
              quilometragem — que determina quantos serviços cabem no dia de
              cada equipe. Ajuste assim que houver entregas reais registradas.
            </Alert>
          </div>
        </Card>
      </div>
    </form>
  );
}
