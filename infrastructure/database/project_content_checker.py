"""Adaptador de ProjectContentChecker (Auditoria 2026-09-02,
RAG_CONTENT_01). Vive en infrastructure porque, a diferencia del resto
del contexto Proyectos, necesita abrir proyecto.db (contexto
Documentos) para responder -- domain.projects.ports.ProjectContentChecker
no sabe que existe SQLAlchemy ni proyecto.db, solo declara la pregunta
de negocio ("tiene documentos?")."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from domain.projects.entities import Proyecto
from domain.projects.ports import ProjectContentChecker

from .engine import build_engine
from .migrations import RUTA_LINEA_PROYECTO, upgrade_to_head
from .project_models import DocumentoModel


class SqlAlchemyProjectContentChecker(ProjectContentChecker):
    def _contar(self, proyecto: Proyecto) -> int:
        if not proyecto.ruta_carpeta:
            return 0
        db_path = Path(proyecto.ruta_carpeta) / "proyecto.db"
        if not db_path.exists():
            # Proyecto que nunca se abrio para trabajar todavia -- ver
            # docstring de ProjectContentChecker.tiene_documentos(). No
            # se llama a upgrade_to_head() en este caso: crearia
            # proyecto.db vacio solo por haber preguntado, un efecto
            # secundario que EliminarProyecto/ArchivarProyecto no
            # esperan de una simple consulta.
            return 0
        upgrade_to_head(db_path, RUTA_LINEA_PROYECTO)
        engine = build_engine(db_path)
        session = sessionmaker(bind=engine, future=True)()
        try:
            return session.execute(select(func.count()).select_from(DocumentoModel)).scalar_one()
        finally:
            session.close()
            engine.dispose()

    def tiene_documentos(self, proyecto: Proyecto) -> bool:
        return self._contar(proyecto) > 0

    def contar_documentos(self, proyecto: Proyecto) -> int:
        return self._contar(proyecto)
