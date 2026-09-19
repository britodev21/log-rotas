import { Logo } from "./Logo";
import "./Splash.css";

/**
 * Tela de abertura.
 *
 * Usada no instante em que a aplicacao confere com o backend se a sessao
 * guardada ainda vale. Nao e carregamento de dado de uma tela — e a
 * inicializacao do sistema, entao aqui cabe a marca, e nao um esqueleto de
 * uma pagina que ainda nao se sabe qual sera.
 *
 * A barra e indeterminada de proposito: nao existe progresso real a medir.
 */
export function Splash({ mensagem = "Abrindo o Log Rotas" }) {
  return (
    <div className="abertura" role="status" aria-live="polite">
      <div className="abertura__conteudo">
        <Logo tamanho={40} comTexto={false} />
        <span className="abertura__nome">Log Rotas</span>
        <div className="abertura__barra" aria-hidden="true">
          <span />
        </div>
        <span className="sr-apenas">{mensagem}</span>
      </div>
    </div>
  );
}
