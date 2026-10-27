"""Excepciones del contexto Gobernanza (Modulo 13)."""
from __future__ import annotations


class GovernanceDomainError(Exception):
    """Raiz de las excepciones de este contexto."""


class IncidenciasCriticasAbiertasError(GovernanceDomainError):
    """El documento tiene al menos una incidencia critica todavia
    abierta -- Documento Maestro, seccion 4.7 ("no aprobar documentos
    con incidencias criticas abiertas") y seccion 8.2 ("Incidencias
    criticas abiertas: 0"). Mensaje en espanol simple, sin exponer un
    error tecnico crudo (seccion 4.11.1: principios de baja friccion) --
    dice que falta (incidencias criticas abiertas) y que accion lo
    resuelve (resolverlas o reclasificar su severidad)."""

    def __init__(self, documento_id: str, cantidad: int):
        super().__init__(
            f"No se puede aprobar la revision del documento '{documento_id}': tiene "
            f"{cantidad} incidencia(s) critica(s) todavia abierta(s). Resuelvalas o "
            "reclasifique su severidad antes de continuar."
        )
        self.documento_id = documento_id
        self.cantidad = cantidad


class VigenciaDesconocidaError(GovernanceDomainError):
    """El documento es critico (`Documento.criticidad == CRITICO`) y su
    vigencia todavia es desconocida -- Documento Maestro, seccion 4.7
    ("bloquear documentos criticos con vigencia desconocida") y seccion
    8.2 ("Documentos criticos con vigencia desconocida: 0"). A
    diferencia de `IncidenciasCriticasAbiertasError`, esta regla solo
    aplica a documentos criticos: uno no critico puede aprobarse aunque
    su vigencia no se haya registrado todavia. Mensaje en espanol
    simple (seccion 4.11.1): que falta (vigencia desconocida) y que
    accion lo resuelve (registrarla desde el panel "Vigencia y
    fuente")."""

    def __init__(self, documento_id: str):
        super().__init__(
            f"No se puede aprobar la revision del documento '{documento_id}': es un documento "
            "critico y su vigencia todavia es desconocida (sin registrar, o registrada de forma "
            "incompleta). Registrela desde el panel 'Vigencia y fuente' antes de continuar."
        )
        self.documento_id = documento_id


class FuenteFaltanteError(GovernanceDomainError):
    """El documento no tiene una `domain.validity.entities.Fuente`
    registrada -- Documento Maestro, seccion 4.7 ("no liberar contenido
    sin fuente, hash y aprobacion") y Modulo 11. El hash de esa misma
    regla ya esta garantizado por construccion al llegar a VALIDADO (ver
    domain.documents.entities.Documento.liberar()); esta excepcion solo
    cubre la parte de fuente."""

    def __init__(self, documento_id: str):
        super().__init__(
            f"No se puede liberar el documento '{documento_id}': todavia no tiene una Fuente "
            "registrada. Registrela desde el panel 'Vigencia y fuente' antes de continuar."
        )
        self.documento_id = documento_id


class AprobacionFaltanteError(GovernanceDomainError):
    """El documento no tiene ninguna `domain.documents.entities.
    Aprobacion` registrada -- Documento Maestro, seccion 4.7 ("no
    liberar contenido sin fuente, hash y aprobacion"). Solo alcanzable
    manipulando el repositorio directamente: el flujo real
    (`Documento.aprobar_para_markdown()`) siempre crea una Aprobacion
    antes de llegar a APROBADO_PARA_MARKDOWN, paso previo obligatorio
    para alcanzar VALIDADO."""

    def __init__(self, documento_id: str):
        super().__init__(
            f"No se puede liberar el documento '{documento_id}': no tiene ninguna aprobacion "
            "registrada. Repita el paso de aprobacion para generar su Markdown antes de continuar."
        )
        self.documento_id = documento_id
