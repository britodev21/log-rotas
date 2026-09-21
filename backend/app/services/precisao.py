"""Esta coordenada pode virar uma parada de entrega?

Existe porque a resposta estava espalhada e incompleta. O agrupamento de
paradas ja tinha um conceito de coordenada confiavel; o planejamento nao —
ele exigia apenas que latitude e longitude nao fossem nulas. O efeito e que
uma coordenada no nivel de RUA entrava na rota como se fosse o portao.

Isso nao e um detalhe em Campo Grande. Medido em 2026-09-21 contra o
OpenStreetMap:

    ruas com nome ................. 13.864
    predios mapeados .............. 17.404
    predios com numero de porta ....... 530

Numa cidade de cerca de 900 mil habitantes. Em oito enderecos reais das
avenidas principais, com CEP conferido, o Nominatim resolveu o numero em
ZERO deles — tanto em consulta de texto livre quanto estruturada. O dado
nao existe, entao nenhum provedor baseado em OSM resolve.

A consequencia pratica: "Avenida Afonso Pena, 3000" vira um ponto qualquer
de uma avenida de 10 km. A rota calculada em cima disso parece correta,
tem quilometragem, tem horario — e manda o caminhao para o lugar errado.

A regra aqui e a unica defesa honesta: coordenada grosseira NAO entra em
rota. Ou alguem marcou o ponto no mapa, ou o provedor resolveu no numero
do predio. Nao ha terceira opcao, e fingir que ha e o que causa entrega
errada.
"""

from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.sql.elements import ColumnElement

from app.core.enums import GeocodePrecision, GeocodeStatus

#: O provedor resolveu ate o numero do predio.
PRECISAO_CONFIAVEL = frozenset({GeocodePrecision.EXATO.value})

#: Um humano marcou o ponto no mapa. Vale mais que qualquer provedor, e
#: por isso nunca e sobrescrito pela geocodificacao automatica.
STATUS_CONFIAVEL = frozenset({GeocodeStatus.MANUAL.value})

#: Texto curto por precisao, para a tela dizer o que esta errado em vez de
#: um generico "endereco impreciso".
_EXPLICACAO = {
    GeocodePrecision.RUA.value: (
        "o provedor achou a rua, mas nao o numero — o ponto pode estar a "
        "quarteiroes do portao"
    ),
    GeocodePrecision.BAIRRO.value: "o provedor achou so o bairro",
    GeocodePrecision.CIDADE.value: "o provedor achou so a cidade",
}


def confiavel(registro) -> bool:
    """A coordenada deste registro serve para planejar uma entrega?

    Aceita qualquer objeto com `geocode_status` e `geocode_precision` —
    entrega, cliente ou base.
    """
    if registro.latitude is None or registro.longitude is None:
        return False
    return (
        registro.geocode_status in STATUS_CONFIAVEL
        or registro.geocode_precision in PRECISAO_CONFIAVEL
    )


def motivo(registro) -> str | None:
    """Por que esta coordenada nao serve. `None` quando serve.

    A mensagem e escrita para quem vai resolver, nao para quem escreveu o
    codigo: diz o que aconteceu e o que fazer.
    """
    if confiavel(registro):
        return None
    if registro.latitude is None or registro.longitude is None:
        return "sem coordenada"
    explicacao = _EXPLICACAO.get(
        registro.geocode_precision, "a origem da coordenada nao permite confirmar o ponto"
    )
    return f"posicao aproximada: {explicacao}"


def filtro_sql(modelo) -> ColumnElement[bool]:
    """A mesma regra de `confiavel`, em SQL, para listar o que falta.

    Existe porque a fila de revisao e o planejamento PRECISAM concordar. Ja
    discordaram: a fila listava apenas PENDENTE, AMBIGUO e FALHOU, e um
    registro OK com precisao RUA — o caso comum em Campo Grande — nao
    aparecia em lugar nenhum. O planejamento passou a recusar esse registro
    e a pessoa ficaria travada, sem tela que mostrasse qual endereco
    resolver.

    Duas copias da regra viram duas regras no dia em que alguem mexe numa
    so. Esta funcao e o par da de cima, e as duas mudam juntas.

    O `coalesce` nao e defensivo a toa. `geocode_precision` e nulo em todo
    registro que ainda nao foi geocodificado, e em SQL `NULL = 'EXATO'` nao
    e falso: e NULL. O OR devolve NULL, a negacao devolve NULL, e a linha
    some do resultado — justamente a linha que mais precisa aparecer na
    fila. O teste da fila pegou isso; a regra em Python e a em SQL
    discordavam no caso mais comum de todos.
    """
    confiavel_sql = or_(
        func.coalesce(modelo.geocode_status, "") == GeocodeStatus.MANUAL.value,
        func.coalesce(modelo.geocode_precision, "") == GeocodePrecision.EXATO.value,
    )
    return ~confiavel_sql
