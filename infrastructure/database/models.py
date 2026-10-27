"""Modelos SQLAlchemy para la base global (aplicacion.db).

Pydantic (domain.projects.entities) valida en los limites de
application/domain; estos modelos ORM son detalle de infrastructure y
nunca se exponen fuera de este paquete (ADR-001, seccion 9).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .types import UTCDateTime


class Base(DeclarativeBase):
    pass


class ProyectoModel(Base):
    __tablename__ = "proyectos"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    # unique=True removido (Auditoria 2026-09-02, hallazgo real de la
    # auditoria independiente de la ronda de Archivar/Eliminar proyecto):
    # con el `unique=True` original, un proyecto archivado ("Cliente
    # ACME", ya no procede) bloqueaba para siempre volver a crear un
    # proyecto activo con el mismo nombre -- justo el escenario que
    # motivo agregar Archivar en primer lugar. La unicidad ahora se
    # exige solo entre proyectos ACTIVOS, en la capa de aplicacion
    # (`CrearProyecto`, via `ProjectRepository.get_by_name()` filtrando
    # por estado -- ver infrastructure/database/repository.py). Ver
    # migracion 'quita_restriccion_unica_de_nombre_en_proyectos' para el
    # cambio de esquema correspondiente.
    nombre: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    perfil_id: Mapped[str] = mapped_column(String(100), nullable=False)
    objetivo: Mapped[str] = mapped_column(Text, default="")
    usuarios_objetivo_csv: Mapped[str] = mapped_column(Text, default="")
    alcance: Mapped[str] = mapped_column(Text, default="")
    jurisdiccion: Mapped[str] = mapped_column(String(200), default="")
    idioma: Mapped[str] = mapped_column(String(10), default="es")
    confidencialidad: Mapped[str] = mapped_column(String(20), nullable=False)
    responsables_csv: Mapped[str] = mapped_column(Text, default="")
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    ruta_carpeta: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)


class EventoAuditoriaModel(Base):
    __tablename__ = "eventos_auditoria"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # index=True agregado en la cuarta ronda de correcciones (2026-08-01,
    # hallazgo de la tercera auditoria general): `CerrarLote` ahora audita
    # la resolucion de cada documento por separado (ver
    # `application/batches/commands/cerrar_lote.py`), asi que un lote con
    # muchos documentos genera muchas filas por cierre. Cualquier consulta
    # que filtre el historial de auditoria por proyecto (paneles futuros,
    # informes, soporte) hacia un table scan completo de la tabla global
    # sin este indice -- ver migracion
    # 'agrega_indice_proyecto_id_en_eventos_auditoria'.
    proyecto_id: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    accion: Mapped[str] = mapped_column(String(200), nullable=False)
    valor_anterior: Mapped[str | None] = mapped_column(Text, nullable=True)
    valor_nuevo: Mapped[str | None] = mapped_column(Text, nullable=True)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    fecha: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
