"""Casos de uso del contexto Gobernanza (Modulo 13). Aqui, y no en
domain.governance, se resuelve el cruce real con otros contextos
(incidencias hoy; vigencias en una fase posterior) -- mismo principio
ya usado por application.incidents.commands.registrar_incidencia
(que depende directamente de domain.documents.ports.DocumentRepository
para validar que el documento referenciado existe): el acoplamiento
cruzado se permite en application, nunca en domain."""
