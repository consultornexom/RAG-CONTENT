"""Puerto (interfaz) del contexto Reportes.

Definido en domain e implementado en infrastructure (ADR-001, seccion
4). A diferencia de `domain.documents.ports.ManifestWriter` (un solo
metodo, porque solo existe un tipo de manifiesto), `ReportWriter` agrupa
los siete metodos de escritura de la seccion 7.1 en una sola interfaz --
mismo criterio que `DocumentRepository`/`TrabajoRepository` agrupan
varias operaciones relacionadas en un solo puerto, en vez de definir
siete interfaces de un solo metodo casi identicas entre si. Ninguno de
los siete sabe nada de Documento/Trabajo/Incidencia/Lote: solo reciben
las Filas o el Acta ya armados por `application.reports`."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .entities import (
    ActaCierreLote,
    FilaCalidad,
    FilaIncidencia,
    FilaInventario,
    FilaProcesamiento,
    FilaRevision,
    FilaTrazabilidad,
)


class ReportWriter(ABC):
    """Escribe cada informe/acta de la seccion 7.1 dentro de
    10_reportes/ del proyecto (Documento Maestro, seccion 4.5).
    Determinista: los seis informes tabulares sobrescriben siempre el
    mismo archivo (mismo criterio que `ManifestWriter`); el acta de
    cierre de lote usa un nombre distinto por lote (puede haber varias
    actas vivas a la vez, una por lote cerrado)."""

    @abstractmethod
    def escribir_inventario(self, filas: list[FilaInventario]) -> str:
        """Devuelve la ruta absoluta del archivo escrito (puede
        recibir una lista vacia -- proyecto sin documentos todavia)."""
        ...

    @abstractmethod
    def escribir_procesamiento(self, filas: list[FilaProcesamiento]) -> str: ...

    @abstractmethod
    def escribir_revision(self, filas: list[FilaRevision]) -> str: ...

    @abstractmethod
    def escribir_incidencias(self, filas: list[FilaIncidencia]) -> str: ...

    @abstractmethod
    def escribir_calidad(self, filas: list[FilaCalidad]) -> str: ...

    @abstractmethod
    def escribir_trazabilidad(self, filas: list[FilaTrazabilidad]) -> str: ...

    @abstractmethod
    def escribir_acta_cierre_lote(self, acta: ActaCierreLote) -> str:
        """A diferencia de los seis anteriores, no recibe una lista:
        un acta describe un solo lote. El nombre del archivo debe
        incluir `acta.lote_id` para no pisar el acta de otro lote."""
        ...
