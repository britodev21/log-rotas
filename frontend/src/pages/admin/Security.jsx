import { useCallback, useEffect, useState } from "react";
import { Eraser, Lock, LockOpen, ShieldCheck } from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { manutencao as apiManutencao } from "../../api/manutencao";
import { seguranca as api } from "../../api/seguranca";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  SkeletonList,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
} from "../../components/ui";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { useToast } from "../../hooks/useToast";
import { dataHora, hora } from "../../utils/formato";
import "./admin.css";

/** O que cada evento quer dizer, em português, e o peso visual dele. */
const EVENTOS = {
  CONTA_BLOQUEADA: { texto: "Conta bloqueada por tentativas", tom: "perigo" },
  IP_BLOQUEADO: { texto: "IP bloqueado por tentativas", tom: "perigo" },
  CONTA_DESBLOQUEADA: { texto: "Conta desbloqueada", tom: "info" },
  SENHA_TROCADA: { texto: "Trocou a própria senha", tom: "neutro" },
  SENHA_REDEFINIDA: { texto: "Senha redefinida por administrador", tom: "atencao" },
  USUARIO_CRIADO: { texto: "Usuário criado", tom: "sucesso" },
  PAPEL_ALTERADO: { texto: "Papel alterado", tom: "atencao" },
  USUARIO_DESATIVADO: { texto: "Usuário desativado", tom: "atencao" },
  USUARIO_REATIVADO: { texto: "Usuário reativado", tom: "info" },
};

const PAPEL = { ADMIN: "administrador", MOTORISTA: "motorista" };

/** Nome de cada tipo de dado que a limpeza apaga, na ordem da tela. */
const APAGADOS = [
  ["posicoes", "posições do GPS"],
  ["tentativas_login", "tentativas de login"],
  ["eventos_seguranca", "eventos de segurança"],
  ["cache_falhas", "endereços que falharam"],
  ["cache_google", "conferências do Google"],
  ["cache_transito", "trechos de trânsito"],
];

function resumoDaLimpeza(execucao) {
  if (execucao.erro) return `Falhou: ${execucao.erro}`;
  const partes = APAGADOS.filter(([chave]) => execucao.resultado?.[chave] > 0).map(
    ([chave, nome]) => `${execucao.resultado[chave].toLocaleString("pt-BR")} ${nome}`
  );
  return partes.length ? `Apagou ${partes.join(", ")}.` : "Nada tinha passado do prazo.";
}

function detalheDoEvento(e) {
  const d = e.detalhe ?? {};
  if (e.tipo === "PAPEL_ALTERADO") return `de ${PAPEL[d.de] ?? d.de} para ${PAPEL[d.para] ?? d.para}`;
  if (e.tipo === "CONTA_BLOQUEADA") return `${d.falhas} falhas · ${d.minutos} min`;
  if (e.tipo === "USUARIO_CRIADO") return PAPEL[d.papel] ?? d.papel ?? "";
  return "";
}

/**
 * Segurança: quem tentou entrar, quem mudou o quê, e as regras em vigor.
 *
 * As regras são lidas do servidor, não escritas aqui: um texto fixo na tela
 * poderia dizer "5 tentativas" enquanto o servidor, reconfigurado, bloqueia
 * em 3.
 */
export function Security() {
  useDocumentTitle("Segurança");
  const toast = useToast();
  const [politica, setPolitica] = useState(null);
  const [bloqueios, setBloqueios] = useState(null);
  const [eventos, setEventos] = useState(null);
  const [erro, setErro] = useState("");
  const [liberando, setLiberando] = useState(null);
  const [guarda, setGuarda] = useState(null);
  const [limpando, setLimpando] = useState(false);

  const carregar = useCallback(async () => {
    setErro("");
    try {
      const [p, b, e, g] = await Promise.all([
        api.politica(),
        api.bloqueios(),
        api.eventos(100),
        apiManutencao.ler(),
      ]);
      setPolitica(p);
      setBloqueios(b);
      setEventos(e);
      setGuarda(g);
    } catch (e) {
      console.error("Falha ao carregar a segurança", e);
      setErro(mensagemDeErro(e, "Não foi possível carregar."));
    }
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function desbloquear(email) {
    setLiberando(email);
    try {
      setBloqueios(await api.desbloquear(email));
      toast.sucesso("Conta desbloqueada", `${email} já pode entrar de novo.`);
      setEventos(await api.eventos(100));
    } catch (e) {
      console.error("Falha ao desbloquear", e);
      toast.erro("Não foi possível desbloquear", mensagemDeErro(e));
    } finally {
      setLiberando(null);
    }
  }

  async function limparAgora() {
    setLimpando(true);
    try {
      const g = await apiManutencao.limpar();
      setGuarda(g);
      toast.sucesso("Limpeza concluída", resumoDaLimpeza(g.ultimas[0]));
    } catch (e) {
      console.error("Falha na limpeza", e);
      toast.erro("Não foi possível limpar", mensagemDeErro(e));
    } finally {
      setLimpando(false);
    }
  }

  if (erro) {
    return (
      <>
        <PageHeader titulo="Segurança" />
        <Card>
          <ErrorState mensagem={erro} aoTentarNovamente={carregar} />
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        titulo="Segurança"
        descricao="Quem tentou entrar, quem mudou o quê, e as regras em vigor."
      />

      <div className="seguranca-grade">
        <Card
          titulo="Contas bloqueadas agora"
          descricao="Por tentativas erradas de senha. Liberam sozinhas quando o tempo acaba."
        >
          {!bloqueios && <SkeletonList itens={2} />}
          {bloqueios?.length === 0 && (
            <EmptyState icone={LockOpen} titulo="Nenhuma conta bloqueada" compacto>
              <p>Quando alguém errar a senha várias vezes seguidas, a conta aparece aqui.</p>
            </EmptyState>
          )}
          {bloqueios?.length > 0 && (
            <ul className="bloqueios">
              {bloqueios.map((b) => (
                <li key={b.email} className="bloqueios__item">
                  <Lock size={16} strokeWidth={2} aria-hidden="true" />
                  <div className="bloqueios__quem">
                    <strong>{b.nome ?? "E-mail sem conta"}</strong>
                    <span>{b.email}</span>
                    <span className="texto-3">
                      {b.falhas} tentativas erradas · libera às {hora(b.ate)}
                    </span>
                  </div>
                  <Button
                    variante="secundario"
                    tamanho="sm"
                    icone={LockOpen}
                    carregando={liberando === b.email}
                    onClick={() => desbloquear(b.email)}
                  >
                    Desbloquear
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card titulo="Regras em vigor" descricao="Lidas do servidor, como ele as aplica.">
          {!politica ? (
            <SkeletonList itens={4} />
          ) : (
            <dl className="politica">
              <dt>Senha</dt>
              <dd>
                Mínimo de {politica.senha_minima} caracteres. Recusa as senhas mais conhecidas,
                sequências e o nome da pessoa ou da empresa. Frase longa é aceita; não exige
                símbolo nem troca periódica.
              </dd>
              <dt>Tentativas de login</dt>
              <dd>
                {politica.login_max_falhas_conta} erros na mesma conta em{" "}
                {politica.login_janela_minutos} min bloqueiam a conta por{" "}
                {politica.login_bloqueio_minutos} min. {politica.login_max_falhas_ip} erros do
                mesmo endereço de internet bloqueiam o endereço. Vale também para e-mail que
                não existe.
              </dd>
              <dt>Sessão</dt>
              <dd>
                Acesso de {politica.sessao_minutos} min, renovado sozinho por até{" "}
                {politica.renovacao_dias} dias. Trocar a senha ou desativar o usuário encerra as
                sessões abertas na hora.
              </dd>
              <dt>Conexão segura (HSTS)</dt>
              <dd>
                <Badge tom={politica.hsts ? "sucesso" : "neutro"} ponto>
                  {politica.hsts ? "ligado" : "desligado"}
                </Badge>{" "}
                {politica.hsts
                  ? "O navegador só aceita o sistema por HTTPS."
                  : "Liga quando o sistema estiver no ar com HTTPS."}
              </dd>
            </dl>
          )}
        </Card>
      </div>

      <Card
        titulo="Guarda dos dados"
        descricao={
          guarda?.hora_agendada != null
            ? `O que passa do prazo é apagado sozinho, todo dia a partir das ${guarda.hora_agendada}h.`
            : "A limpeza automática está desligada neste servidor (LIMPEZA_HORA)."
        }
        acoes={
          <Button
            variante="secundario"
            tamanho="sm"
            icone={Eraser}
            carregando={limpando}
            disabled={!guarda}
            onClick={limparAgora}
          >
            Limpar agora
          </Button>
        }
        className="guarda"
      >
        {!guarda ? (
          <SkeletonList itens={3} />
        ) : (
          <div className="guarda__grade">
            <dl className="politica">
              <dt>Posições do GPS</dt>
              <dd>
                {guarda.retencao_posicoes_dias} dias. É o trajeto diário de uma pessoa (LGPD):
                serve para tirar dúvida sobre uma rota, não para ficar guardado para sempre.
              </dd>
              <dt>Tentativas de login</dt>
              <dd>{guarda.retencao_tentativas_login_dias} dias.</dd>
              <dt>Eventos de segurança</dt>
              <dd>
                {guarda.retencao_eventos_seguranca_dias} dias. Ficam mais porque respondem
                perguntas que aparecem muito depois.
              </dd>
              <dt>Endereço que falhou</dt>
              <dd>
                {guarda.retencao_cache_falhas_dias} dias. Depois disso, a busca é tentada de novo
                — o mapa da rua pode ter sido corrigido. Endereço encontrado fica.
              </dd>
            </dl>

            <div>
              <h4 className="guarda__subtitulo">Últimas execuções</h4>
              {guarda.ultimas.length === 0 ? (
                <p className="texto-3">Ainda não rodou nenhuma vez.</p>
              ) : (
                <ul className="guarda__execucoes">
                  {guarda.ultimas.slice(0, 5).map((x) => (
                    <li key={x.id}>
                      <span className="numero">{dataHora(x.iniciada_em)}</span>
                      <Badge tom={x.erro ? "perigo" : x.origem === "MANUAL" ? "info" : "neutro"}>
                        {x.erro ? "falhou" : x.origem === "MANUAL" ? "manual" : "automática"}
                      </Badge>
                      <span className="guarda__resumo">{resumoDaLimpeza(x)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </Card>

      <Card titulo="Eventos recentes" descricao="Os últimos 100." semPadding>
        {!eventos && <SkeletonList itens={5} />}
        {eventos?.length === 0 && (
          <EmptyState icone={ShieldCheck} titulo="Nenhum evento ainda" compacto>
            <p>Criação de usuários, trocas de senha e bloqueios aparecem aqui.</p>
          </EmptyState>
        )}
        {eventos?.length > 0 && (
          <Table>
            <THead>
              <TH largura="150px">Quando</TH>
              <TH>O quê</TH>
              <TH>Sobre</TH>
              <TH>Quem fez</TH>
              <TH largura="130px">Endereço</TH>
            </THead>
            <TBody>
              {eventos.map((e) => {
                const info = EVENTOS[e.tipo] ?? { texto: e.tipo, tom: "neutro" };
                const detalhe = detalheDoEvento(e);
                return (
                  <TR key={e.id}>
                    <TD>
                      <span className="numero">{dataHora(e.quando)}</span>
                    </TD>
                    <TD>
                      <Badge tom={info.tom}>{info.texto}</Badge>
                      {detalhe && <span className="evento__detalhe">{detalhe}</span>}
                    </TD>
                    <TD>{e.sobre ?? e.email ?? "—"}</TD>
                    <TD>{e.quem ?? (e.tipo.endsWith("BLOQUEADA") || e.tipo.endsWith("BLOQUEADO") ? "o sistema" : "—")}</TD>
                    <TD>
                      <span className="numero texto-3">{e.ip ?? "—"}</span>
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        )}
      </Card>
    </>
  );
}
