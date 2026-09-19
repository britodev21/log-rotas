import { useCallback, useEffect, useState } from "react";

import { mensagemDeErro } from "../api/client";

/**
 * Carregamento, filtros e estados de uma tela de cadastro.
 *
 * As quatro telas da Fase 3 fazem a mesma coisa: buscam com filtro de
 * situacao e busca textual, tratam carregando / erro / vazio e recarregam
 * apos gravar. Repetir isso quatro vezes garantiria quatro variacoes sutis
 * de comportamento.
 */
export function useCadastro(recurso, { rotulo = "os registros" } = {}) {
  const [itens, setItens] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [busca, setBusca] = useState("");
  const [situacao, setSituacao] = useState("");

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro("");
    try {
      const filtros = {};
      if (busca.trim()) filtros.search = busca.trim();
      if (situacao) filtros.active = situacao === "ativos";
      setItens(await recurso.listar(filtros));
    } catch (e) {
      // Detalhe tecnico no console, frase em portugues na tela.
      console.error(`Falha ao listar ${rotulo}`, e);
      setErro(mensagemDeErro(e, `Nao foi possivel carregar ${rotulo}.`));
    } finally {
      setCarregando(false);
    }
  }, [recurso, busca, situacao, rotulo]);

  // Espera a digitacao parar: sem isso seria uma requisicao por tecla.
  useEffect(() => {
    const id = setTimeout(carregar, busca ? 300 : 0);
    return () => clearTimeout(id);
  }, [carregar, busca]);

  const limparFiltros = useCallback(() => {
    setBusca("");
    setSituacao("");
  }, []);

  return {
    itens,
    carregando,
    erro,
    busca,
    setBusca,
    situacao,
    setSituacao,
    temFiltro: Boolean(busca.trim() || situacao),
    carregar,
    limparFiltros,
  };
}
