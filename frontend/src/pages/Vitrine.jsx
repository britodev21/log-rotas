import { Logo } from "../components/ui";

/**
 * Coluna de marca das telas de entrada.
 *
 * O desenho é um trajeto: três nós ligados por uma linha que se traça na
 * entrada. É a ideia do produto — origem, paradas, destino — sem recorrer a
 * caminhão nem a pin de mapa. Sai da tela abaixo de 1024px, onde o que
 * importa é o formulário.
 */
export function Vitrine() {
  return (
    <aside className="vitrine" aria-hidden="true">
      <div className="vitrine__malha" />
      <div className="vitrine__brilho" />

      <div className="vitrine__conteudo">
        <Logo tamanho={30} comTexto={false} />

        <h1 className="vitrine__titulo">Rotas que se planejam sozinhas</h1>

        <p className="vitrine__texto">
          Tecnologia para transformar rotas em uma operação mais inteligente:
          entregas organizadas, caminho calculado e o motorista sabendo
          exatamente aonde ir.
        </p>

        <svg
          className="vitrine__trajeto"
          viewBox="0 0 340 120"
          fill="none"
          role="presentation"
        >
          <path
            d="M18 96 C 70 96, 78 28, 132 28 S 218 96, 262 96 S 318 44, 322 24"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray="260"
          />
          <circle cx="18" cy="96" r="6" fill="currentColor" />
          <circle cx="132" cy="28" r="5" fill="var(--cinza-950)" stroke="currentColor" strokeWidth="2" />
          <circle cx="262" cy="96" r="5" fill="var(--cinza-950)" stroke="currentColor" strokeWidth="2" />
        </svg>
      </div>

      <div className="vitrine__rodape">
        <div className="vitrine__item">
          <span className="vitrine__item-rotulo">Operação</span>
          <span className="vitrine__item-valor">Britto Móveis e Corrimão</span>
        </div>
        <div className="vitrine__item">
          <span className="vitrine__item-rotulo">Região</span>
          <span className="vitrine__item-valor">Campo Grande, MS</span>
        </div>
      </div>
    </aside>
  );
}
