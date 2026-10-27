"""Puerto (interfaz) del contexto Pruebas de aceptacion.

Definido en domain e implementado en infrastructure (ADR-001, seccion
4). Un solo metodo -- no hace falta agrupar varias operaciones como
`domain.reports.ports.ReportWriter`, porque cada corrida produce
exactamente un `InformeAceptacion`."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .entities import InformeAceptacion


class InformeAceptacionWriter(ABC):
    """Escribe el informe de una corrida de pruebas de aceptacion a
    disco -- no sabe nada de Documento/Fuente/Vigencia/Lote, solo del
    `InformeAceptacion` ya armado por
    `application.acceptance.commands.ejecutar_pruebas_aceptacion.
    EjecutarPruebasDeAceptacion`."""

    @abstractmethod
    def escribir(self, informe: InformeAceptacion) -> str:
        """Devuelve la ruta absoluta del archivo escrito. A diferencia
        de `domain.reports.ports.ReportWriter` (que siempre sobrescribe
        el mismo archivo), cada corrida de aceptacion debe quedar
        archivada por separado -- el nombre del archivo debe incluir
        `informe.fecha` para no pisar corridas anteriores."""
        ...
