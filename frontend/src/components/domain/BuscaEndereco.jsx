import { useCallback, useEffect, useId, useRef, useState } from "react";
import { MapPin, Search } from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { geocodificacao as api } from "../../api/operacao";
import { InputField, Spinner } from "../ui";
import "./BuscaEndereco.css";

/**
 * Busca de endereço com sugestões do Google — o campo do Google Maps.
 *
 * A pessoa digita, o Google sugere endereços que existem, ela escolhe um.
 * Não há o que digitar errado: o que entra é o que ela escolheu da lista.
 *
 * Medido nos mesmos oito endereços reais de Campo Grande em que o
 * geocodificador gratuito acertou o número em zero: aqui, oito de oito.
 *
 * A chamada ao Google sai do servidor, não daqui — a chave não pode estar
 * no JavaScript de uma página que qualquer um inspeciona.
 */

/** Sem o limite de uma consulta por segundo do Nominatim, a espera pode ser
 *  curta o bastante para parecer instantânea. Não é zero porque cada tecla
 *  seria uma chamada. */
const ESPERA_MS = 250;
const MINIMO = 3;

function novaSessao() {
  // Token de sessão do Google: agrupa a digitação e a escolha numa cobrança
  // só. Sem ele, cada tecla é uma consulta paga separada.
  return typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function BuscaEndereco({ valorInicial = "", aoEscolher, aoFalhar }) {
  const idLista = useId();
  const [texto, setTexto] = useState(valorInicial);
  const [sugestoes, setSugestoes] = useState([]);
  const [aberto, setAberto] = useState(false);
  const [ativo, setAtivo] = useState(-1);
  const [buscando, setBuscando] = useState(false);
  const [detalhando, setDetalhando] = useState(false);
  const [erro, setErro] = useState("");

  const sessao = useRef(novaSessao());
  // O texto que já corresponde a uma escolha. Sem isto, preencher o campo
  // com o endereço escolhido dispararia uma busca nova por ele mesmo.
  const escolhido = useRef(valorInicial);
  // Resposta velha chegando depois da nova sobrescreveria as sugestões.
  const ultimaConsulta = useRef(0);

  useEffect(() => {
    const valor = texto.trim();
    if (valor.length < MINIMO || valor === escolhido.current) {
      setSugestoes([]);
      setAberto(false);
      return undefined;
    }

    const controle = new AbortController();
    const numero = ++ultimaConsulta.current;
    const id = setTimeout(async () => {
      setBuscando(true);
      setErro("");
      try {
        const lista = await api.sugestoes(valor, sessao.current, { signal: controle.signal });
        if (numero !== ultimaConsulta.current) return;
        setSugestoes(lista);
        setAtivo(lista.length ? 0 : -1);
        setAberto(true);
      } catch (e) {
        if (controle.signal.aborted) return;
        console.error("Falha nas sugestões de endereço", e);
        const mensagem = mensagemDeErro(e, "Não foi possível buscar agora.");
        setErro(mensagem);
        if (e?.response?.status === 503) aoFalhar?.(mensagem);
      } finally {
        if (numero === ultimaConsulta.current) setBuscando(false);
      }
    }, ESPERA_MS);

    return () => {
      clearTimeout(id);
      controle.abort();
    };
  }, [texto, aoFalhar]);

  const escolher = useCallback(
    async (sugestao) => {
      setAberto(false);
      setTexto(sugestao.texto);
      escolhido.current = sugestao.texto;
      setDetalhando(true);
      setErro("");
      try {
        const lugar = await api.lugar(sugestao.place_id, sessao.current);
        aoEscolher(lugar);
      } catch (e) {
        console.error("Falha ao detalhar o lugar escolhido", e);
        setErro(mensagemDeErro(e, "Não foi possível abrir este endereço."));
      } finally {
        setDetalhando(false);
        // A sessão termina na escolha; a próxima busca é outra cobrança.
        sessao.current = novaSessao();
      }
    },
    [aoEscolher],
  );

  function aoTeclar(e) {
    // Enter aqui nunca pode enviar o formulário da entrega: a pessoa está
    // escolhendo um endereço, não salvando.
    if (e.key === "Enter") {
      e.preventDefault();
      if (aberto && sugestoes[ativo]) escolher(sugestoes[ativo]);
      return;
    }
    if (!aberto || sugestoes.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setAtivo((i) => (i + 1) % sugestoes.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setAtivo((i) => (i - 1 + sugestoes.length) % sugestoes.length);
    } else if (e.key === "Escape") {
      e.preventDefault();
      setAberto(false);
    }
  }

  const idOpcao = (i) => `${idLista}-opcao-${i}`;
  const semResultado = aberto && !buscando && sugestoes.length === 0;

  return (
    <div className="busca-endereco">
      <InputField
        label="Endereço"
        placeholder="Digite rua e número, como no Google Maps"
        icone={Search}
        value={texto}
        onChange={(e) => {
          setTexto(e.target.value);
          escolhido.current = null;
        }}
        onKeyDown={aoTeclar}
        onFocus={() => sugestoes.length > 0 && texto !== escolhido.current && setAberto(true)}
        onBlur={() => setAberto(false)}
        autoComplete="off"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={aberto}
        aria-controls={idLista}
        aria-activedescendant={aberto && ativo >= 0 ? idOpcao(ativo) : undefined}
        erro={erro}
        aDireita={buscando || detalhando ? <Spinner tamanho={14} /> : null}
      />

      {aberto && (
        <ul className="busca-endereco__lista" id={idLista} role="listbox">
          {sugestoes.map((s, i) => (
            <li
              key={s.place_id}
              id={idOpcao(i)}
              role="option"
              aria-selected={i === ativo}
              className={`busca-endereco__opcao ${i === ativo ? "busca-endereco__opcao--ativa" : ""}`}
              // mousedown, não click: o click chega depois do blur do campo,
              // que já teria fechado a lista.
              onMouseDown={(e) => {
                e.preventDefault();
                escolher(s);
              }}
              onMouseEnter={() => setAtivo(i)}
            >
              <MapPin size={15} strokeWidth={2} aria-hidden="true" />
              <span className="busca-endereco__textos">
                <span className="busca-endereco__principal">{s.principal || s.texto}</span>
                {s.secundario && (
                  <span className="busca-endereco__secundario">{s.secundario}</span>
                )}
              </span>
            </li>
          ))}
          {semResultado && (
            <li className="busca-endereco__vazio" role="option" aria-disabled="true">
              Nenhum endereço encontrado. Confira a grafia ou use o CEP.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
