"""Geocodificacao — converter endereco em coordenada.

Porta e adaptadores. O resto do sistema fala apenas com `GeocodingService`
e com os tipos de `base.py`; nenhuma outra camada sabe que existe Nominatim.
"""

from app.geocoding.base import Candidato, GeocodeResult, GeocodingProvider
from app.geocoding.nominatim import NominatimProvider
from app.geocoding.service import GeocodingService, chave_cache, normalizar_endereco

__all__ = [
    "Candidato",
    "GeocodeResult",
    "GeocodingProvider",
    "GeocodingService",
    "NominatimProvider",
    "chave_cache",
    "normalizar_endereco",
]
