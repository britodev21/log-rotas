"""Repositorio base dos cadastros.

Os quatro cadastros da Fase 3 fazem exatamente as mesmas quatro consultas:
buscar por id, listar com filtro de situacao e busca textual, conferir
unicidade e inserir. Escrever isso quatro vezes garantiria quatro variacoes
sutis — e a quinta tabela repetiria o erro.

O que NAO entra aqui: regra de negocio, commit e excecao. O repositorio
devolve modelo ou None; quem decide o que isso significa e o service.
"""

from __future__ import annotations

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.db.base import Base


class CrudRepository[M: Base]:
    #: Colunas varridas pela busca textual. Definido por cada subclasse.
    campos_busca: tuple[str, ...] = ("name",)
    #: Ordenacao padrao da listagem.
    ordem: str = "name"

    def __init__(self, session: Session, modelo: type[M]) -> None:
        self.session = session
        self.modelo = modelo

    # --- leitura ---------------------------------------------------------- #
    def get(self, registro_id: int) -> M | None:
        return self.session.get(self.modelo, registro_id)

    def listar(self, *, active: bool | None = None, search: str | None = None) -> list[M]:
        stmt = self._base_select()

        if active is not None:
            stmt = stmt.where(self.modelo.active.is_(active))

        if search and search.strip():
            termo = f"%{search.strip().lower()}%"
            condicoes = [
                func.lower(getattr(self.modelo, campo)).like(termo)
                for campo in self.campos_busca
                if hasattr(self.modelo, campo)
            ]
            if condicoes:
                stmt = stmt.where(or_(*condicoes))

        return list(self.session.scalars(stmt).unique())

    def _base_select(self) -> Select:
        return select(self.modelo).order_by(getattr(self.modelo, self.ordem))

    def existe_campo(self, campo: str, valor, *, excluir_id: int | None = None) -> bool:
        """Confere unicidade de um campo, ignorando o proprio registro."""
        coluna = getattr(self.modelo, campo)
        stmt = select(self.modelo.id).where(coluna == valor)
        if excluir_id is not None:
            stmt = stmt.where(self.modelo.id != excluir_id)
        return self.session.scalar(stmt.limit(1)) is not None

    def contar(self, *, active: bool | None = None) -> int:
        stmt = select(func.count()).select_from(self.modelo)
        if active is not None:
            stmt = stmt.where(self.modelo.active.is_(active))
        return self.session.scalar(stmt) or 0

    # --- escrita ---------------------------------------------------------- #
    def add(self, registro: M) -> M:
        self.session.add(registro)
        self.session.flush()  # atribui o id sem encerrar a transacao
        return registro

    def remover(self, registro: M) -> None:
        self.session.delete(registro)
        self.session.flush()
