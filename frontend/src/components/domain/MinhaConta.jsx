import { useState } from "react";
import { KeyRound, ShieldAlert } from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { useAuth } from "../../hooks/useAuth";
import { useToast } from "../../hooks/useToast";
import { Alert, Badge, Button, InputField, Modal } from "../ui";
import "./MinhaConta.css";

const SENHA_MINIMA = 10;

/**
 * Minha conta: quem sou eu e a troca da própria senha.
 *
 * Existia a rota no servidor e nenhuma tela para ela — ninguém conseguia
 * trocar a senha pelo sistema. Com a política de senha nova, isso deixou de
 * ser detalhe: o aviso "sua senha é fraca" precisa ter onde ser resolvido.
 *
 * A orientação segue a política (docs/SEGURANCA.md): frase longa vale mais
 * que símbolo e maiúscula. A tela não pede "1 maiúscula, 1 número" — isso
 * produz `Senha@2024`, que a política recusa.
 */
export function MinhaConta({ aberto, onFechar }) {
  const { usuario, trocarSenha, senhaFraca } = useAuth();
  const toast = useToast();
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [erro, setErro] = useState("");
  const [problemas, setProblemas] = useState([]);
  const [salvando, setSalvando] = useState(false);

  function fechar() {
    setAtual("");
    setNova("");
    setConfirmacao("");
    setErro("");
    setProblemas([]);
    onFechar();
  }

  const naoConfere = confirmacao.length > 0 && confirmacao !== nova;
  const curta = nova.length > 0 && nova.length < SENHA_MINIMA;

  async function enviar(evento) {
    evento.preventDefault();
    setErro("");
    setProblemas([]);
    if (nova !== confirmacao) {
      setErro("A confirmação não confere com a senha nova.");
      return;
    }
    setSalvando(true);
    try {
      await trocarSenha(atual, nova);
      toast.sucesso(
        "Senha trocada",
        "As sessões abertas em outros aparelhos foram encerradas.",
      );
      fechar();
    } catch (e) {
      console.error("Falha ao trocar a senha", e);
      const lista = e?.response?.data?.detalhes?.problemas;
      if (Array.isArray(lista) && lista.length) {
        setProblemas(lista);
      } else {
        setErro(mensagemDeErro(e, "Não foi possível trocar a senha."));
      }
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Modal aberto={aberto} titulo="Minha conta" descricao={usuario?.email} onFechar={fechar}>
      <form className="form-modal minha-conta" onSubmit={enviar} noValidate>
        <div className="minha-conta__quem">
          <strong>{usuario?.name}</strong>
          <Badge tom="neutro">{usuario?.role === "ADMIN" ? "administrador" : "motorista"}</Badge>
        </div>

        {senhaFraca && (
          <Alert tom="atencao" titulo="Troque a sua senha">
            A senha que você usa está entre as mais conhecidas (ou leva o seu nome) — é das
            primeiras que alguém tentaria para entrar na sua conta.
          </Alert>
        )}

        <p className="minha-conta__dica">
          <ShieldAlert size={15} strokeWidth={2} aria-hidden="true" />
          <span>
            Use pelo menos {SENHA_MINIMA} caracteres. Uma frase que só você conhece —
            <em> “pão de queijo quente”</em> — é mais forte e mais fácil de lembrar do que
            trocar letras por símbolos. Não use seu nome nem o da empresa.
          </span>
        </p>

        {erro && <Alert tom="erro">{erro}</Alert>}
        {problemas.length > 0 && (
          <Alert tom="erro" titulo="Esta senha não serve">
            <ul className="minha-conta__problemas">
              {problemas.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </Alert>
        )}

        <InputField
          label="Senha atual"
          type="password"
          autoComplete="current-password"
          value={atual}
          onChange={(e) => setAtual(e.target.value)}
          required
        />
        <InputField
          label="Senha nova"
          type="password"
          autoComplete="new-password"
          value={nova}
          onChange={(e) => setNova(e.target.value)}
          erro={curta ? `Faltam ${SENHA_MINIMA - nova.length} caracteres.` : ""}
          required
        />
        <InputField
          label="Repita a senha nova"
          type="password"
          autoComplete="new-password"
          value={confirmacao}
          onChange={(e) => setConfirmacao(e.target.value)}
          erro={naoConfere ? "Não confere com a senha nova." : ""}
          required
        />

        <div className="acoes-direita">
          <Button variante="secundario" onClick={fechar}>
            Cancelar
          </Button>
          <Button
            type="submit"
            icone={KeyRound}
            carregando={salvando}
            disabled={!atual || nova.length < SENHA_MINIMA || naoConfere}
          >
            Trocar senha
          </Button>
        </div>
      </form>
    </Modal>
  );
}

/** Faixa no topo enquanto a senha em uso for fraca. */
export function AvisoSenhaFraca({ aoAbrir }) {
  const { senhaFraca } = useAuth();
  if (!senhaFraca) return null;
  return (
    <div className="aviso-senha" role="status">
      <ShieldAlert size={16} strokeWidth={2} aria-hidden="true" />
      <span>
        Sua senha está entre as mais conhecidas. Troque para proteger a sua conta.
      </span>
      <Button variante="secundario" tamanho="sm" icone={KeyRound} onClick={aoAbrir}>
        Trocar agora
      </Button>
    </div>
  );
}
