"""Puertos del contexto Seguridad (ADR-001, seccion 4: domain define,
infrastructure implementa).

`CredentialStore` guarda UN secreto (la clave de cifrado de respaldos de
un proyecto); `RespaldoStore` agrupa empaquetado + cifrado + nombrado de
archivo + restauracion en un solo puerto -- mismo criterio de
granularidad que `domain.reports.ports.ReportWriter` (la logica de "como
se guarda en disco" vive entera en infrastructure; application solo pide
"crea un respaldo" / "restaura este respaldo", sin saber que hay un zip
ni un algoritmo Fernet de por medio)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from .entities import RespaldoProyecto, RestauracionRespaldo


class CredentialStore(ABC):
    """Almacen de credenciales del sistema operativo (ADR-001, seccion
    14.1: "mismo puerto y mismo adaptador (KeyringCredentialStore) que
    RAG STUDIO"). Nunca en texto plano, nunca en un archivo propio de la
    aplicacion, nunca en logs -- solo a traves de este puerto."""

    @abstractmethod
    def guardar_secreto(self, nombre: str, valor: str) -> None: ...

    @abstractmethod
    def obtener_secreto(self, nombre: str) -> Optional[str]:
        """`None` si no existe ningun secreto guardado con ese nombre --
        nunca lanza una excepcion por ausencia (ausencia es un estado
        valido y esperado, resuelto por quien llama: `CrearRespaldo`
        genera una clave nueva, `RestaurarRespaldo` lanza
        `ClaveDeRespaldoNoEncontradaError`)."""
        ...

    @abstractmethod
    def eliminar_secreto(self, nombre: str) -> None:
        """Idempotente: no lanza una excepcion si el secreto ya no
        existia."""
        ...


class RespaldoStore(ABC):
    """Crea y restaura respaldos cifrados de la carpeta completa de un
    proyecto (ADR-001, seccion 14.3; Documento Maestro, seccion 9:
    "Respaldos cifrados y pruebas de restauracion"), dentro de
    `13_respaldos/` del propio proyecto (Documento Maestro, seccion 4.5,
    carpeta reservada desde la Fase 1, sin uso real hasta esta fase)."""

    @abstractmethod
    def generar_clave(self) -> str:
        """Genera una clave de cifrado nueva, compatible con el
        algoritmo que use `crear()`/`restaurar()` -- domain no sabe cual
        es (Fernet, hoy); solo sabe que es una cadena que
        `CredentialStore` puede guardar tal cual."""
        ...

    @abstractmethod
    def crear(self, carpeta_proyecto: Path, proyecto_id: str, clave: str) -> RespaldoProyecto: ...

    @abstractmethod
    def restaurar(self, ruta_archivo: Path, clave: str, destino: Path) -> RestauracionRespaldo:
        """Nunca lanza una excepcion por clave incorrecta, archivo
        corrupto o archivo alterado -- eso es un resultado ESPERADO de
        una "prueba de restauracion" (Documento Maestro, seccion 9), no
        un error de programacion: se refleja en
        `RestauracionRespaldo.exitosa`/`detalle`."""
        ...
