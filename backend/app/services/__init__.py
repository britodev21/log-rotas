"""Services — onde mora a regra de negocio.

Controlam a transacao (commit/rollback), levantam excecoes de dominio e nao
conhecem FastAPI. E o que permite testar a regra sem subir servidor HTTP.
"""
