import { useState } from "react";
import { CloudOff, Download, RefreshCw, X } from "lucide-react";

import { Button } from "../ui";
import { useAplicativo } from "../../hooks/useAplicativo";
import "./BarraDoAplicativo.css";

const DISPENSOU_INSTALACAO = "logrotas.instalacao.dispensada";

/**
 * A faixa do aplicativo: sem conexão, versão nova e convite para instalar.
 *
 * Uma faixa só, no rodapé, com prioridade clara — sem conexão vem antes de
 * tudo, porque muda o que a pessoa pode fazer agora; atualização vem antes
 * do convite, porque é a única com prazo.
 *
 * O convite some quando a pessoa dispensa, e não volta. Barra de instalação
 * que reaparece toda semana é a razão de as pessoas ignorarem qualquer
 * faixa na tela.
 */
export function BarraDoAplicativo() {
  const { online, temAtualizacao, podeInstalar, atualizar, instalar } = useAplicativo();
  const [dispensou, setDispensou] = useState(() => {
    try {
      return localStorage.getItem(DISPENSOU_INSTALACAO) === "1";
    } catch {
      return false;
    }
  });

  function dispensar() {
    setDispensou(true);
    try {
      localStorage.setItem(DISPENSOU_INSTALACAO, "1");
    } catch {
      // Sem armazenamento (janela anônima), o convite volta na próxima vez.
    }
  }

  if (!online) {
    return (
      <div className="barra-app barra-app--atencao" role="status">
        <CloudOff size={16} strokeWidth={2} aria-hidden="true" />
        <span>
          <strong>Sem conexão.</strong> A tela continua aberta, mas o que você registrar
          agora não chega ao escritório.
        </span>
      </div>
    );
  }

  if (temAtualizacao) {
    return (
      <div className="barra-app" role="status">
        <RefreshCw size={16} strokeWidth={2} aria-hidden="true" />
        <span>Uma versão nova do Log Rotas está pronta.</span>
        <Button tamanho="sm" onClick={atualizar}>
          Atualizar agora
        </Button>
      </div>
    );
  }

  if (podeInstalar && !dispensou) {
    return (
      <div className="barra-app" role="status">
        <Download size={16} strokeWidth={2} aria-hidden="true" />
        <span>
          Instale o Log Rotas no celular: abre pelo ícone, sem digitar endereço, e continua
          abrindo onde o sinal está fraco.
        </span>
        <Button tamanho="sm" onClick={instalar}>
          Instalar
        </Button>
        <button
          type="button"
          className="barra-app__fechar"
          onClick={dispensar}
          aria-label="Agora não"
        >
          <X size={16} strokeWidth={2} aria-hidden="true" />
        </button>
      </div>
    );
  }

  return null;
}
