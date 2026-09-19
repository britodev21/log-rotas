import { Plus, Search } from "lucide-react";

import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  InputField,
  PageHeader,
  SelectField,
  SkeletonTable,
} from "../ui";
import "./CadastroPage.css";

/**
 * Casca das telas de cadastro.
 *
 * Reúne o que as quatro telas têm em comum — cabeçalho, barra de filtros,
 * contagem, e os três estados que toda listagem precisa tratar (carregando,
 * erro com nova tentativa, vazio). Cada página entrega só a sua tabela e o
 * seu modal.
 *
 * O estado vazio distingue dois casos que parecem iguais e não são: "ainda
 * não existe nada cadastrado", que pede um botão de criar, e "o filtro não
 * achou nada", que pede um botão de limpar o filtro. Tratar os dois como um
 * só faz a pessoa concluir que o cadastro sumiu.
 */
export function CadastroPage({
  titulo,
  descricao,
  icone,
  rotuloSingular,
  rotuloPlural,
  textoVazio,
  aoCriar,
  estado,
  colunas = 4,
  children,
}) {
  const { itens, carregando, erro, busca, setBusca, situacao, setSituacao, temFiltro } =
    estado;

  return (
    <>
      <PageHeader
        titulo={titulo}
        descricao={descricao}
        acoes={
          <Button icone={Plus} onClick={aoCriar}>
            Novo {rotuloSingular}
          </Button>
        }
      />

      <Card semPadding>
        <div className="filtros">
          <div className="filtros__busca">
            <InputField
              label="Buscar"
              placeholder={`Buscar ${rotuloPlural}`}
              icone={Search}
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
            />
          </div>

          <div className="filtros__campo">
            <SelectField
              label="Situação"
              value={situacao}
              onChange={(e) => setSituacao(e.target.value)}
            >
              <option value="">Todos</option>
              <option value="ativos">Ativos</option>
              <option value="inativos">Inativos</option>
            </SelectField>
          </div>

          {!carregando && !erro && itens.length > 0 && (
            <span className="filtros__contagem numero">
              {itens.length} {itens.length === 1 ? rotuloSingular : rotuloPlural}
            </span>
          )}
        </div>

        {carregando && <SkeletonTable linhas={4} colunas={colunas} />}

        {!carregando && erro && (
          <ErrorState
            titulo={`Não foi possível carregar ${rotuloPlural}`}
            mensagem={erro}
            aoTentarNovamente={estado.carregar}
          />
        )}

        {!carregando && !erro && itens.length === 0 && (
          <EmptyState
            icone={icone}
            titulo={temFiltro ? "Nada encontrado" : `Nenhum ${rotuloSingular} por aqui`}
            acao={
              temFiltro ? (
                <Button variante="secundario" onClick={estado.limparFiltros}>
                  Limpar filtros
                </Button>
              ) : (
                <Button icone={Plus} onClick={aoCriar}>
                  Cadastrar {rotuloSingular}
                </Button>
              )
            }
          >
            <p>
              {temFiltro
                ? "Nenhum registro corresponde à busca ou ao filtro selecionado."
                : textoVazio}
            </p>
          </EmptyState>
        )}

        {!carregando && !erro && itens.length > 0 && children}
      </Card>
    </>
  );
}
