"""Caso de uso del Modulo 13 (Estados y dependencias): aplicar de
verdad la tercera regla de bloqueo -- "no liberar contenido sin fuente,
hash y aprobacion" (Documento Maestro, seccion 4.7). El "hash" de esa
regla ya esta garantizado por construccion al llegar a VALIDADO (ver
domain.documents.entities.Documento.liberar()); este caso de uso solo
verifica los otros dos requisitos: Fuente registrada (Modulo 11) y al
menos una Aprobacion registrada (Modulo 12/13).

Depende directamente de `domain.validity.ports.FuenteRepository` y
`domain.documents.ports.AprobacionRepository` (los puertos de los
contextos involucrados, no sus fachadas de aplicacion) -- mismo patron
de acoplamiento cruzado ya usado por
application.governance.verificar_documento_aprobable.
VerificarDocumentoAprobable. domain.governance sigue sin importar
domain.validity/domain.documents en absoluto."""
from __future__ import annotations

from domain.documents.ports import AprobacionRepository
from domain.governance.exceptions import AprobacionFaltanteError, FuenteFaltanteError
from domain.validity.ports import FuenteRepository


class VerificarDocumentoLiberable:
    def __init__(self, fuente_repository: FuenteRepository, aprobacion_repository: AprobacionRepository):
        self._fuente_repository = fuente_repository
        self._aprobacion_repository = aprobacion_repository

    def verificar(self, documento_id: str) -> None:
        """No devuelve nada si el documento puede liberarse. Lanza
        `FuenteFaltanteError`/`AprobacionFaltanteError` si no puede --
        quien llama (application.documents.commands.liberar_documento.
        LiberarDocumento) debe dejar que la excepcion se propague, no
        capturarla en silencio."""
        if self._fuente_repository.get_by_document(documento_id) is None:
            raise FuenteFaltanteError(documento_id)
        if not self._aprobacion_repository.list_by_document(documento_id):
            raise AprobacionFaltanteError(documento_id)
