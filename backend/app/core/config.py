"""Configuracao da aplicacao, carregada de variaveis de ambiente / .env.

Nenhum segredo tem valor padrao utilizavel: JWT_SECRET e DATABASE_URL sao
obrigatorios e a aplicacao se recusa a subir sem eles.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SECRET = "troque-este-valor-antes-de-usar-em-producao"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Aplicacao ---
    app_name: str = "Log Rotas"
    environment: str = "development"
    debug: bool = False

    # --- Banco ---
    database_url: str

    # --- Seguranca ---
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # Lista em texto separada por virgula. Declarada como str de proposito:
    # pydantic-settings tentaria interpretar list[str] como JSON.
    cors_origins: str = "http://localhost:5173"

    # --- Operacao ---
    default_timezone: str = "America/Campo_Grande"
    default_stop_service_minutes: int = 60

    # --- Provedores externos (Fases 4 e 5) ---
    geocoding_provider: str = "nominatim"
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "LogRotas/0.1"
    geocoding_provider_key: str = ""
    matrix_provider: str = "osrm"
    osrm_base_url: str = "https://router.project-osrm.org"
    map_provider_key: str = ""

    @field_validator("jwt_secret")
    @classmethod
    def _reject_weak_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError(
                "JWT_SECRET precisa de ao menos 32 caracteres. "
                'Gere um com: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return value

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "producao", "prod"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def assert_production_ready(self) -> None:
        """Barreira contra subir em producao com o segredo de exemplo."""
        if self.is_production and self.jwt_secret == PLACEHOLDER_SECRET:
            raise RuntimeError(
                "JWT_SECRET ainda e o valor de exemplo. Troque antes de rodar em producao."
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()  # type: ignore[call-arg]
    settings.assert_production_ready()
    return settings
