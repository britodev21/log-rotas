"""Consulta de CEP pelos Correios, via ViaCEP.

Existe por uma razao pratica: endereco brasileiro digitado por extenso e a
pior entrada possivel para geocodificacao. "Av. Calogeras 1500" tem dezenas
de grafias, e o Nominatim erra ou nao acha.

CEP mais numero, nao. O ViaCEP devolve logradouro, bairro, cidade e UF
normalizados, e a partir disso o endereco montado acerta muito mais.

O ViaCEP e gratuito, sem chave e sem limite documentado. Mesmo assim ha
cache em memoria: numa importacao, o mesmo CEP se repete bastante.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

from app.core.errors import NotFoundError, ValidationError

logger = logging.getLogger(__name__)

VIACEP_URL = "https://viacep.com.br/ws/{cep}/json/"

#: Cache de processo. Pequeno de proposito: e conveniencia, nao camada de
#: persistencia. Some no restart, e isso nao tem consequencia nenhuma.
_cache: dict[str, EnderecoCep] = {}
_LIMITE_CACHE = 2000


@dataclass(frozen=True)
class EnderecoCep:
    cep: str
    logradouro: str | None
    bairro: str | None
    cidade: str
    uf: str
    complemento: str | None = None

    def montar(self, numero: str | None = None, complemento: str | None = None) -> str:
        """Monta o endereco de uma linha, na ordem que o geocodificador espera.

        Numero logo depois do logradouro, cidade e UF no fim. O CEP entra
        tambem: e o que desempata rua de mesmo nome em bairros diferentes.
        """
        partes = []
        if self.logradouro:
            partes.append(f"{self.logradouro}, {numero}" if numero else self.logradouro)
        if complemento:
            partes.append(complemento)
        if self.bairro:
            partes.append(self.bairro)
        partes.append(f"{self.cidade} - {self.uf}")
        partes.append(formatar_cep(self.cep))
        return ", ".join(partes)


def limpar_cep(bruto: str) -> str:
    digitos = re.sub(r"\D", "", bruto or "")
    if len(digitos) != 8:
        raise ValidationError(
            "CEP invalido. Informe os 8 digitos.", details={"recebido": bruto}
        )
    return digitos


def formatar_cep(digitos: str) -> str:
    return f"{digitos[:5]}-{digitos[5:]}"


def consultar(cep: str) -> EnderecoCep:
    """Busca o endereco de um CEP. Levanta NotFoundError se nao existir."""
    limpo = limpar_cep(cep)

    if limpo in _cache:
        return _cache[limpo]

    try:
        with httpx.Client(timeout=8.0) as cliente:
            resposta = cliente.get(VIACEP_URL.format(cep=limpo))
            resposta.raise_for_status()
            dados = resposta.json()
    except httpx.HTTPError as exc:
        logger.warning("Falha ao consultar o ViaCEP: %s", exc)
        raise ValidationError(
            "Nao foi possivel consultar o CEP agora. Digite o endereco manualmente."
        ) from exc
    except ValueError as exc:
        raise ValidationError("Resposta invalida do servico de CEP.") from exc

    # O ViaCEP responde 200 com {"erro": true} para CEP inexistente — um
    # status de sucesso carregando uma falha. Tratar so o codigo HTTP faria
    # o sistema aceitar um endereco vazio.
    if dados.get("erro"):
        raise NotFoundError(
            f"CEP {formatar_cep(limpo)} nao encontrado.", details={"cep": limpo}
        )

    endereco = EnderecoCep(
        cep=limpo,
        logradouro=(dados.get("logradouro") or "").strip() or None,
        bairro=(dados.get("bairro") or "").strip() or None,
        cidade=(dados.get("localidade") or "").strip(),
        uf=(dados.get("uf") or "").strip().upper(),
        complemento=(dados.get("complemento") or "").strip() or None,
    )

    if len(_cache) < _LIMITE_CACHE:
        _cache[limpo] = endereco

    return endereco
