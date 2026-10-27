"""Contexto acotado Gobernanza (Modulo 13, Documento Maestro seccion
4.6: "Estados y dependencias" -- "impedir transiciones indebidas").

Nombre de paquete ya previsto en el ADR-001 (seccion 7, estructura de
directorios: "domain/ (... governance ...)"). Reune las reglas de
bloqueo que cruzan otros contextos (incidencias, vigencias) sin que
ninguno de esos contextos tenga que conocer a los demas -- mismo
principio de aislamiento que ya usan domain.documents/domain.incidents
entre si; la resolucion cruzada real vive en application.governance
(ver su docstring)."""
