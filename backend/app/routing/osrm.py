"""Adaptador do OSRM — distancia e tempo pela malha viaria real."""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings
from app.core.enums import MatrixSource
from app.routing.base import MatrixProvider, Matriz, Ponto, Trajeto

logger = logging.getLogger(__name__)


class OSRMIndisponivel(RuntimeError):
    """O provedor nao respondeu ou respondeu algo inutilizavel."""


class OSRMProvider(MatrixProvider):
    """Distancias e tempos reais, calculados sobre o OpenStreetMap.

    O servidor publico de demonstracao serve para desenvolvimento, mas nao
    tem garantia de disponibilidade e a politica nao cobre uso comercial de
    volume. Em producao isto aponta para um OSRM proprio na VPS, com o
    extrato de Mato Grosso do Sul — e a troca e uma URL no `.env`.
    """

    nome = "osrm"
    source = MatrixSource.OSRM
    estimada = False

    def __init__(self, *, base_url: str | None = None, timeout: float = 20.0) -> None:
        self.base_url = (base_url or get_settings().osrm_base_url).rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------ #
    def _coordenadas(self, pontos: list[Ponto]) -> str:
        # O OSRM espera longitude,latitude — a ordem inversa da que se usa
        # em quase todo o resto. Trocar isso poe as paradas no oceano.
        return ";".join(f"{p.longitude},{p.latitude}" for p in pontos)

    def _get(self, caminho: str, params: dict) -> dict:
        try:
            with httpx.Client(timeout=self.timeout) as cliente:
                resposta = cliente.get(f"{self.base_url}{caminho}", params=params)
                resposta.raise_for_status()
                dados = resposta.json()
        except httpx.HTTPError as exc:
            raise OSRMIndisponivel(f"Falha ao consultar o servico de rotas: {exc}") from exc
        except ValueError as exc:
            raise OSRMIndisponivel("Resposta invalida do servico de rotas.") from exc

        if dados.get("code") != "Ok":
            raise OSRMIndisponivel(
                f"O servico de rotas respondeu: {dados.get('message') or dados.get('code')}"
            )
        return dados

    # ------------------------------------------------------------------ #
    def matriz(self, pontos: list[Ponto]) -> Matriz:
        if len(pontos) < 2:
            raise OSRMIndisponivel("A matriz precisa de ao menos dois pontos.")

        dados = self._get(
            f"/table/v1/driving/{self._coordenadas(pontos)}",
            {"annotations": "duration,distance"},
        )

        duracoes_brutas = dados.get("durations")
        distancias_brutas = dados.get("distances")
        if not duracoes_brutas:
            raise OSRMIndisponivel("O servico de rotas nao devolveu durações.")

        n = len(pontos)
        duracoes = [[0] * n for _ in range(n)]
        distancias = [[0] * n for _ in range(n)]
        inalcancaveis: list[str] = []

        for i in range(n):
            for j in range(n):
                d = duracoes_brutas[i][j]
                m = distancias_brutas[i][j] if distancias_brutas else None

                # null significa "sem caminho por estrada". Acontece com
                # coordenada caida dentro de quadra, area fechada ou erro de
                # geocodificacao. Nao pode virar zero: o otimizador leria
                # como "de graca" e mandaria o motorista para la primeiro.
                if d is None:
                    inalcancaveis.append(pontos[j].rotulo or pontos[j].id)
                    duracoes[i][j] = 10**7
                    distancias[i][j] = 10**7
                else:
                    duracoes[i][j] = round(d)
                    distancias[i][j] = round(m) if m is not None else 0

        avisos = []
        if inalcancaveis:
            unicos = sorted(set(inalcancaveis))
            avisos.append(
                "Sem caminho por estrada ate: "
                + ", ".join(unicos[:5])
                + (f" e mais {len(unicos) - 5}." if len(unicos) > 5 else ".")
            )

        return Matriz(
            pontos=pontos,
            distancias=distancias,
            duracoes=duracoes,
            source=self.source,
            estimada=False,
            detalhe="Distancias e tempos calculados sobre a malha viaria (OSRM).",
            avisos=avisos,
        )

    def trajeto(self, pontos: list[Ponto]) -> Trajeto:
        if len(pontos) < 2:
            return Trajeto(0, 0, None, self.source, False)

        dados = self._get(
            f"/route/v1/driving/{self._coordenadas(pontos)}",
            {"overview": "full", "geometries": "polyline"},
        )

        rotas = dados.get("routes") or []
        if not rotas:
            raise OSRMIndisponivel("O servico de rotas nao devolveu trajeto.")

        rota = rotas[0]
        return Trajeto(
            distancia_m=round(rota.get("distance", 0)),
            duracao_s=round(rota.get("duration", 0)),
            geometria=rota.get("geometry"),
            source=self.source,
            estimada=False,
        )
