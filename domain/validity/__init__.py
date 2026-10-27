"""Contexto acotado Vigencias y fuentes (Modulo 11, Documento Maestro
seccion 4.6, fila 11: "Control formal de actualidad" -- "Emision,
vigencia, revision, sustituciones, autoridad, propietario, repositorio,
consulta y evidencia").

ADR-001 (seccion 5, tabla "Revision, normalizacion y gobierno
documental") modela esto como DOS entidades independientes -- Fuente y
Vigencia -- con una nota de diseno explicita: "Separa explicitamente
vigencia, validacion y autoridad -- no deben confundirse (mismo
principio que Source en RAG STUDIO)". Ver domain.validity.entities.
"""
