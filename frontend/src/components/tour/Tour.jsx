import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, X } from "lucide-react";

import { Button } from "../ui";
import "./tour.css";

/** Quanto esperar o alvo aparecer depois de trocar de tela. */
const ESPERA_MAX_MS = 4000;
const INTERVALO_MS = 120;
/** Respiro entre o recorte e o elemento, para ele não ficar colado na borda. */
const FOLGA = 6;

/**
 * Tutorial guiado: destaca um ponto da tela e explica o que ele faz.
 *
 * Por que guiado, e não uma página de ajuda: ninguém lê manual antes de
 * usar. O tutorial que funciona é o que aponta para o botão de verdade, na
 * tela de verdade, na ordem em que a pessoa vai precisar dele.
 *
 * Cada passo pode pedir uma tela (`rota`) e um elemento (`alvo`). Se o
 * elemento não aparecer — porque a tela está vazia, porque o motorista não
 * tem rota hoje —, o passo continua valendo: vira um balão no meio da tela
 * com o mesmo texto. Um tutorial que trava porque a tela está diferente é
 * pior do que nenhum.
 */
export function Tour({ passos, aberto, aoFechar }) {
  const [indice, setIndice] = useState(0);
  const [area, setArea] = useState(null);
  const navegar = useNavigate();
  const { pathname } = useLocation();
  const cancelado = useRef(false);

  const passo = passos[indice];
  const ultimo = indice === passos.length - 1;

  // Recomeça do zero a cada abertura.
  useEffect(() => {
    if (aberto) {
      setIndice(0);
      setArea(null);
    }
  }, [aberto]);

  /** Mede o alvo; devolve false quando ele ainda não tem tamanho. */
  const medir = useCallback((elemento) => {
    const r = elemento.getBoundingClientRect();
    // Tamanho zero: a tela ainda está montando e o elemento que achamos já
    // foi trocado por outro. Medir agora poria o destaque no canto da tela.
    if (r.width === 0 || r.height === 0) return false;
    setArea({
      topo: r.top - FOLGA,
      esquerda: r.left - FOLGA,
      largura: r.width + FOLGA * 2,
      altura: r.height + FOLGA * 2,
    });
    return true;
  }, []);

  // Leva até a tela do passo, espera o elemento existir e o destaca.
  useEffect(() => {
    if (!aberto || !passo) return undefined;
    cancelado.current = false;

    if (passo.rota && pathname !== passo.rota) navegar(passo.rota);

    if (!passo.alvo) {
      setArea(null);
      return undefined;
    }

    const inicio = Date.now();
    let temporizador;
    const procurar = () => {
      if (cancelado.current) return;
      const elemento = document.querySelector(passo.alvo);
      if (elemento) {
        elemento.scrollIntoView({ block: "center", behavior: "smooth" });
        // Depois da rolagem, e não antes: a posição muda com ela. E o alvo é
        // buscado de novo a cada tentativa, porque a tela pode trocar o
        // elemento enquanto carrega.
        const fixar = (tentativa) => {
          if (cancelado.current) return;
          const atual = document.querySelector(passo.alvo);
          if (atual && medir(atual)) return;
          if (tentativa > 12) {
            setArea(null);
            return;
          }
          temporizador = setTimeout(() => fixar(tentativa + 1), INTERVALO_MS);
        };
        temporizador = setTimeout(() => fixar(0), 320);
        return;
      }
      if (Date.now() - inicio > ESPERA_MAX_MS) {
        setArea(null); // Não achou: o passo vira explicação no centro.
        return;
      }
      temporizador = setTimeout(procurar, INTERVALO_MS);
    };
    procurar();

    return () => {
      cancelado.current = true;
      clearTimeout(temporizador);
    };
  }, [aberto, passo, pathname, navegar, medir]);

  // A tela mexe (rolagem, giro do celular): o recorte acompanha.
  useEffect(() => {
    if (!aberto || !passo?.alvo) return undefined;
    const atualizar = () => {
      const elemento = document.querySelector(passo.alvo);
      if (elemento) medir(elemento);
    };

    window.addEventListener("resize", atualizar);
    window.addEventListener("scroll", atualizar, true);
    return () => {
      window.removeEventListener("resize", atualizar);
      window.removeEventListener("scroll", atualizar, true);
    };
  }, [aberto, passo, medir]);

  useEffect(() => {
    if (!aberto) return undefined;
    const tecla = (e) => {
      if (e.key === "Escape") aoFechar();
      if (e.key === "ArrowRight") setIndice((i) => Math.min(i + 1, passos.length - 1));
      if (e.key === "ArrowLeft") setIndice((i) => Math.max(i - 1, 0));
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [aberto, aoFechar, passos.length]);

  if (!aberto || !passo) return null;

  return createPortal(
    <div className="tour" role="dialog" aria-modal="true" aria-label="Tutorial">
      {area ? (
        <div
          className="tour__recorte"
          style={{
            top: `${area.topo}px`,
            left: `${area.esquerda}px`,
            width: `${area.largura}px`,
            height: `${area.altura}px`,
          }}
        />
      ) : (
        <div className="tour__fundo" />
      )}

      <div className={`tour__balao ${area ? posicao(area) : "tour__balao--centro"}`} style={estilo(area)}>
        <span className="tour__contador">
          {indice + 1} de {passos.length}
        </span>
        <h2 className="tour__titulo">{passo.titulo}</h2>
        <p className="tour__texto">{passo.texto}</p>

        <div className="tour__acoes">
          <button type="button" className="tour__pular" onClick={aoFechar}>
            Sair do tutorial
          </button>
          <div className="tour__navegacao">
            {indice > 0 && (
              <Button
                variante="secundario"
                tamanho="sm"
                icone={ArrowLeft}
                onClick={() => setIndice((i) => i - 1)}
              >
                Voltar
              </Button>
            )}
            <Button
              tamanho="sm"
              icone={ultimo ? Check : ArrowRight}
              onClick={() => (ultimo ? aoFechar() : setIndice((i) => i + 1))}
            >
              {ultimo ? "Entendi" : "Próximo"}
            </Button>
          </div>
        </div>

        <button type="button" className="tour__fechar" onClick={aoFechar} aria-label="Fechar tutorial">
          <X size={16} strokeWidth={2} aria-hidden="true" />
        </button>
      </div>
    </div>,
    document.body,
  );
}

/** O balão fica embaixo do alvo; em cima quando não há espaço. */
function posicao(area) {
  const cabeEmbaixo = area.topo + area.altura + 220 < window.innerHeight;
  return cabeEmbaixo ? "tour__balao--abaixo" : "tour__balao--acima";
}

function estilo(area) {
  if (!area) return undefined;
  const cabeEmbaixo = area.topo + area.altura + 220 < window.innerHeight;
  const largura = Math.min(360, window.innerWidth - 32);
  const esquerda = Math.min(
    Math.max(16, area.esquerda + area.largura / 2 - largura / 2),
    window.innerWidth - largura - 16,
  );
  return {
    width: `${largura}px`,
    left: `${esquerda}px`,
    ...(cabeEmbaixo
      ? { top: `${area.topo + area.altura + 12}px` }
      : { bottom: `${window.innerHeight - area.topo + 12}px` }),
  };
}
