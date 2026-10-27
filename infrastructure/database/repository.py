"""Adaptador de ProjectRepository sobre SQLAlchemy (ADR-001, seccion 4).

domain.projects.ports.ProjectRepository no sabe que existe SQLAlchemy;
esta clase es la unica que lo importa.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.projects.entities import EstadoProyecto, NivelConfidencialidad, Proyecto
from domain.projects.ports import ProjectRepository

from .models import ProyectoModel


def _to_entity(row: ProyectoModel) -> Proyecto:
    return Proyecto(
        id=row.id,
        nombre=row.nombre,
        perfil_id=row.perfil_id,
        objetivo=row.objetivo,
        usuarios_objetivo=[u for u in row.usuarios_objetivo_csv.split(",") if u],
        alcance=row.alcance,
        jurisdiccion=row.jurisdiccion,
        idioma=row.idioma,
        confidencialidad=NivelConfidencialidad(row.confidencialidad),
        responsables=[r for r in row.responsables_csv.split(",") if r],
        estado=EstadoProyecto(row.estado),
        ruta_carpeta=row.ruta_carpeta,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_row(proyecto: Proyecto, existing: Optional[ProyectoModel] = None) -> ProyectoModel:
    row = existing or ProyectoModel(id=proyecto.id)
    row.nombre = proyecto.nombre
    row.perfil_id = proyecto.perfil_id
    row.objetivo = proyecto.objetivo
    row.usuarios_objetivo_csv = ",".join(proyecto.usuarios_objetivo)
    row.alcance = proyecto.alcance
    row.jurisdiccion = proyecto.jurisdiccion
    row.idioma = proyecto.idioma
    row.confidencialidad = proyecto.confidencialidad.value
    row.responsables_csv = ",".join(proyecto.responsables)
    row.estado = proyecto.estado.value
    row.ruta_carpeta = proyecto.ruta_carpeta
    row.created_at = proyecto.created_at
    row.updated_at = proyecto.updated_at
    return row


class SqlAlchemyProjectRepository(ProjectRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, proyecto: Proyecto) -> None:
        existing = self._session.get(ProyectoModel, proyecto.id)
        row = _to_row(proyecto, existing)
        if existing is None:
            self._session.add(row)
        self._session.commit()

    def get(self, proyecto_id: str) -> Optional[Proyecto]:
        row = self._session.get(ProyectoModel, proyecto_id)
        return _to_entity(row) if row else None

    def get_by_name(self, nombre: str) -> Optional[Proyecto]:
        # Auditoria 2026-09-02 (hallazgo real de la auditoria independiente
        # de la ronda de Archivar/Eliminar proyecto): filtra por
        # estado=ACTIVO a proposito -- este metodo solo lo usa
        # `CrearProyecto` para el chequeo de nombre duplicado
        # (`DuplicateProjectNameError`, cuyo propio mensaje dice "un
        # proyecto ACTIVO con ese nombre"). Antes de este cambio, un
        # proyecto archivado bloqueaba para siempre reutilizar su nombre
        # -- contradiciendo el proposito mismo de archivar ("ya no
        # procede", ver Manual de Usuario 6.1). Con la restriccion unica
        # de la base ya removida (ver migracion
        # 'quita_restriccion_unica_de_nombre_en_proyectos'), puede haber
        # como maximo un proyecto ACTIVO con un nombre dado, pero
        # cualquier cantidad de proyectos ARCHIVADO con ese mismo nombre
        # -- por eso el filtro es imprescindible aqui, no solo cosmetico.
        stmt = select(ProyectoModel).where(
            ProyectoModel.nombre == nombre, ProyectoModel.estado == EstadoProyecto.ACTIVO.value
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return _to_entity(row) if row else None

    def list(self, incluir_archivados: bool = True) -> list[Proyecto]:
        stmt = select(ProyectoModel)
        if not incluir_archivados:
            stmt = stmt.where(ProyectoModel.estado == EstadoProyecto.ACTIVO.value)
        rows = self._session.execute(stmt).scalars().all()
        return [_to_entity(r) for r in rows]

    def delete(self, proyecto_id: str) -> None:
        # Auditoria 2026-09-02 (RAG_CONTENT_01): solo borra el indice en
        # aplicacion.db. Quien llama (EliminarProyecto) ya borro la
        # carpeta fisica del proyecto ANTES de llegar aqui -- ver el
        # docstring de ProjectRepository.delete() para el porque de ese
        # orden.
        row = self._session.get(ProyectoModel, proyecto_id)
        if row is not None:
            self._session.delete(row)
            self._session.commit()
