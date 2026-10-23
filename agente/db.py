"""Almacenamiento local SQLite para leads, conversaciones y borradores del agente."""
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

DB_PATH = Path("leads.db")

def obtener_conexion() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_bd():
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversaciones (
                id TEXT PRIMARY KEY,
                contacto_numero TEXT,
                contacto_nombre TEXT,
                pais TEXT,
                mensajes JSON,
                ultimo_mensaje TEXT,
                actualizado_en TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id TEXT PRIMARY KEY,
                telefono TEXT UNIQUE,
                nombre TEXT,
                pais TEXT,
                score INTEGER DEFAULT 0,
                temperatura TEXT DEFAULT 'frio',
                etapa TEXT DEFAULT 'nuevo',
                objeciones TEXT,
                experiencia TEXT,
                notas TEXT,
                actualizado_en TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pendientes (
                id TEXT PRIMARY KEY,
                conversacion_id TEXT,
                telefono TEXT,
                nombre TEXT,
                mensaje_usuario TEXT,
                borrador_respuesta TEXT,
                calificacion JSON,
                pasos JSON,
                estado TEXT DEFAULT 'pendiente', -- pendiente, aprobado, rechazado
                creado_en TEXT
            )
        """)
        conn.commit()

inicializar_bd()

def guardar_mensaje(conversacion_id: str, telefono: str, nombre: Optional[str], rol: str, contenido: str, pais: str = "México") -> List[Dict[str, Any]]:
    ahora = datetime.now(timezone.utc).isoformat()
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT mensajes FROM conversaciones WHERE id = ?", (conversacion_id,))
        row = cursor.fetchone()
        mensajes = []
        if row and row["mensajes"]:
            try:
                mensajes = json.loads(row["mensajes"])
            except Exception:
                mensajes = []
        
        nuevo_msg = {
            "rol": rol,
            "contenido": contenido,
            "fecha": ahora
        }
        mensajes.append(nuevo_msg)
        
        cursor.execute("""
            INSERT INTO conversaciones (id, contacto_numero, contacto_nombre, pais, mensajes, ultimo_mensaje, actualizado_en)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                mensajes = excluded.mensajes,
                ultimo_mensaje = excluded.ultimo_mensaje,
                contacto_nombre = COALESCE(excluded.contacto_nombre, conversaciones.contacto_nombre),
                pais = COALESCE(excluded.pais, conversaciones.pais),
                actualizado_en = excluded.actualizado_en
        """, (conversacion_id, telefono, nombre, pais, json.dumps(mensajes, ensure_ascii=False), contenido, ahora))
        conn.commit()
        return mensajes

def obtener_conversacion(conversacion_id: str) -> Optional[Dict[str, Any]]:
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversaciones WHERE id = ?", (conversacion_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "contacto_numero": row["contacto_numero"],
            "contacto_nombre": row["contacto_nombre"],
            "pais": row["pais"],
            "mensajes": json.loads(row["mensajes"]) if row["mensajes"] else [],
            "ultimo_mensaje": row["ultimo_mensaje"],
            "actualizado_en": row["actualizado_en"]
        }

def listar_conversaciones() -> List[Dict[str, Any]]:
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversaciones ORDER BY actualizado_en DESC")
        rows = cursor.fetchall()
        res = []
        for r in rows:
            res.append({
                "id": r["id"],
                "contacto_numero": r["contacto_numero"],
                "contacto_nombre": r["contacto_nombre"],
                "pais": r["pais"],
                "mensajes": json.loads(r["mensajes"]) if r["mensajes"] else [],
                "ultimo_mensaje": r["ultimo_mensaje"],
                "actualizado_en": r["actualizado_en"]
            })
        return res

def upsert_lead(telefono: str, nombre: Optional[str] = None, pais: Optional[str] = None,
                score: Optional[int] = None, temperatura: Optional[str] = None,
                etapa: Optional[str] = None, objeciones: Optional[str] = None,
                experiencia: Optional[str] = None, notas: Optional[str] = None):
    ahora = datetime.now(timezone.utc).isoformat()
    lead_id = f"lead_{abs(hash(telefono)) % 1000000}"
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO leads (id, telefono, nombre, pais, score, temperatura, etapa, objeciones, experiencia, notas, actualizado_en)
            VALUES (?, ?, ?, ?, COALESCE(?, 0), COALESCE(?, 'frio'), COALESCE(?, 'nuevo'), ?, ?, ?, ?)
            ON CONFLICT(telefono) DO UPDATE SET
                nombre = COALESCE(excluded.nombre, leads.nombre),
                pais = COALESCE(excluded.pais, leads.pais),
                score = COALESCE(excluded.score, leads.score),
                temperatura = COALESCE(excluded.temperatura, leads.temperatura),
                etapa = COALESCE(excluded.etapa, leads.etapa),
                objeciones = COALESCE(excluded.objeciones, leads.objeciones),
                experiencia = COALESCE(excluded.experiencia, leads.experiencia),
                notas = COALESCE(excluded.notas, leads.notas),
                actualizado_en = excluded.actualizado_en
        """, (lead_id, telefono, nombre, pais, score, temperatura, etapa, objeciones, experiencia, notas, ahora))
        conn.commit()

def listar_leads() -> List[Dict[str, Any]]:
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads ORDER BY score DESC, actualizado_en DESC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def guardar_pendiente(pendiente_id: str, conversacion_id: str, telefono: str, nombre: str,
                      mensaje_usuario: str, borrador_respuesta: str, calificacion: Dict[str, Any], pasos: List[Dict[str, Any]]):
    ahora = datetime.now(timezone.utc).isoformat()
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pendientes (id, conversacion_id, telefono, nombre, mensaje_usuario, borrador_respuesta, calificacion, pasos, estado, creado_en)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?)
            ON CONFLICT(id) DO UPDATE SET
                borrador_respuesta = excluded.borrador_respuesta,
                calificacion = excluded.calificacion,
                pasos = excluded.pasos,
                estado = 'pendiente',
                creado_en = excluded.creado_en
        """, (pendiente_id, conversacion_id, telefono, nombre, mensaje_usuario, borrador_respuesta,
              json.dumps(calificacion, ensure_ascii=False), json.dumps(pasos, ensure_ascii=False), ahora))
        conn.commit()

def listar_pendientes(solo_activos: bool = True) -> List[Dict[str, Any]]:
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        if solo_activos:
            cursor.execute("SELECT * FROM pendientes WHERE estado = 'pendiente' ORDER BY creado_en DESC")
        else:
            cursor.execute("SELECT * FROM pendientes ORDER BY creado_en DESC")
        rows = cursor.fetchall()
        resultado = []
        for r in rows:
            resultado.append({
                "id": r["id"],
                "conversacion_id": r["conversacion_id"],
                "telefono": r["telefono"],
                "nombre": r["nombre"],
                "mensaje_usuario": r["mensaje_usuario"],
                "borrador_respuesta": r["borrador_respuesta"],
                "calificacion": json.loads(r["calificacion"]) if r["calificacion"] else {},
                "pasos": json.loads(r["pasos"]) if r["pasos"] else [],
                "estado": r["estado"],
                "creado_en": r["creado_en"]
            })
        return resultado

def resolver_pendiente(pendiente_id: str, accion: str, texto_editado: Optional[str] = None):
    with obtener_conexion() as conn:
        cursor = conn.cursor()
        if accion == "aprobar":
            if texto_editado:
                cursor.execute("UPDATE pendientes SET estado = 'aprobado', borrador_respuesta = ? WHERE id = ?", (texto_editado, pendiente_id))
            else:
                cursor.execute("UPDATE pendientes SET estado = 'aprobado' WHERE id = ?", (pendiente_id,))
        else:
            cursor.execute("UPDATE pendientes SET estado = 'rechazado' WHERE id = ?", (pendiente_id,))
        conn.commit()
