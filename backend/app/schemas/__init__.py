"""Schemas Pydantic — o contrato HTTP da API.

Sao separados dos modelos SQLAlchemy de proposito: o que entra e sai pela
rede nao deve ser ditado pelo formato da tabela (password_hash e
token_version, por exemplo, nunca saem daqui).
"""
