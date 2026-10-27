"""Contexto de aplicacion Vigencias y fuentes (Modulo 11).

Igual que application.incidents con RegistrarIncidencia, los casos de
uso de aqui dependen directamente de
`domain.documents.ports.DocumentRepository` (el puerto del otro
contexto, no su fachada `DocumentsService`) para validar que el
documento referenciado exista antes de registrar una Fuente/Vigencia --
`domain.validity` no importa `domain.documents` en absoluto."""
