"""Servidor FastAPI para el Agente Cerrador de WhatsApp con Google Gemini."""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, Response, HTTPException, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agente.db import (
    guardar_mensaje,
    obtener_conversacion,
    listar_conversaciones,
    upsert_lead,
    listar_leads,
    guardar_pendiente,
    listar_pendientes,
    resolver_pendiente
)
from agente.gemini_service import analizar_mensaje_con_gemini, cargar_playbook

app = FastAPI(title="WhatsApp Closer Agent · Gemini", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PANEL_PATH = Path("panel/index.html")

# Modelos Pydantic
class ChatSimuladorRequest(BaseModel):
    conversacion_id: str
    mensaje: str
    telefono: Optional[str] = "+52 244 123 5715"
    nombre: Optional[str] = "Prospecto Emprendedor"
    api_key: Optional[str] = None
    modelo: Optional[str] = None

class ResolverPendienteRequest(BaseModel):
    pendiente_id: str
    accion: str # 'aprobar' o 'rechazar'
    texto_editado: Optional[str] = None

# Rutas principales
@app.get("/", response_class=HTMLResponse)
@app.get("/panel", response_class=HTMLResponse)
async def ver_panel():
    if PANEL_PATH.exists():
        with open(PANEL_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    return HTMLResponse(content="<h1>Panel en construcción</h1>", status_code=200)

@app.get("/salud")
async def estado_salud():
    return {
        "estado": "ok",
        "servicio": "whatsapp-closer-agentkit",
        "proveedor_ia": "google-gemini",
        "mentora": "María de Jesús Vera",
        "telefono_oficial": "+52 244 123 5715",
        "modo": "borrador"
    }

# Endpoint para el Simulador de WhatsApp en Vivo
@app.post("/api/chat")
async def chat_simulador(req: ChatSimuladorRequest):
    # Guardar mensaje del usuario
    historial = guardar_mensaje(
        conversacion_id=req.conversacion_id,
        telefono=req.telefono or "+52 244 123 5715",
        nombre=req.nombre,
        rol="usuario",
        contenido=req.mensaje
    )

    # Analizar con Gemini + Playbook
    analisis = analizar_mensaje_con_gemini(
        mensaje_actual=req.mensaje,
        historial=historial,
        nombre_contacto=req.nombre,
        api_key_override=req.api_key,
        modelo_override=req.modelo
    )

    respuesta_texto = analisis.get("respuesta_texto", "")
    calificacion = analisis.get("calificacion", {})

    # Guardar respuesta del agente
    guardar_mensaje(
        conversacion_id=req.conversacion_id,
        telefono=req.telefono or "+52 244 123 5715",
        nombre=req.nombre,
        rol="asistente",
        contenido=respuesta_texto
    )

    # Actualizar CRM
    upsert_lead(
        telefono=req.telefono or "+52 244 123 5715",
        nombre=req.nombre,
        pais=calificacion.get("pais", "México"),
        score=calificacion.get("score", 50),
        temperatura=calificacion.get("temperatura", "tibio"),
        etapa=analisis.get("crm_etapa", "calificado"),
        objeciones=analisis.get("objecion_detectada"),
        experiencia=calificacion.get("experiencia"),
        notas=calificacion.get("motivo")
    )

    # Si está en modo borrador, registrar en pendientes
    pendiente_id = f"pend_{req.conversacion_id}_{len(historial)}"
    guardar_pendiente(
        pendiente_id=pendiente_id,
        conversacion_id=req.conversacion_id,
        telefono=req.telefono or "+52 244 123 5715",
        nombre=req.nombre or "Prospecto",
        mensaje_usuario=req.mensaje,
        borrador_respuesta=respuesta_texto,
        calificacion=calificacion,
        pasos=[
            {"paso": 1, "nombre": "contexto", "estado": "ok"},
            {"paso": 2, "nombre": "calificacion", "score": calificacion.get("score", 50), "temperatura": calificacion.get("temperatura", "tibio")},
            {"paso": 3, "nombre": "playbook", "objecion": analisis.get("objecion_detectada")},
            {"paso": 4, "nombre": "agenda", "horario": analisis.get("horario_ofrecido")},
            {"paso": 5, "nombre": "crm", "etapa": analisis.get("crm_etapa")},
            {"paso": 6, "nombre": "escalacion", "escalar": analisis.get("escalar")}
        ]
    )

    return analisis

# Endpoints de API para el panel
@app.get("/api/conversaciones")
async def api_conversaciones():
    return listar_conversaciones()

@app.get("/api/leads")
async def api_leads():
    return listar_leads()

@app.get("/api/pendientes")
async def api_pendientes(solo_activos: bool = True):
    return listar_pendientes(solo_activos=solo_activos)

@app.post("/api/aprobar")
async def api_aprobar(req: ResolverPendienteRequest):
    resolver_pendiente(req.pendiente_id, accion="aprobar", texto_editado=req.texto_editado)
    return {"status": "ok", "mensaje": "Borrador aprobado para envío."}

@app.post("/api/rechazar")
async def api_rechazar(req: ResolverPendienteRequest):
    resolver_pendiente(req.pendiente_id, accion="rechazar")
    return {"status": "ok", "mensaje": "Borrador descartado."}

@app.get("/api/playbook")
async def api_playbook():
    return cargar_playbook()

# Webhooks para WhatsApp en producción (Meta, Zernio y Demo)
@app.get("/webhook/meta")
async def verificar_webhook_meta(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token")
):
    token_esperado = os.getenv("WHATSAPP_VERIFY_TOKEN", "closer_token_seguro")
    if hub_mode == "subscribe" and hub_verify_token == token_esperado:
        return Response(content=hub_challenge or "", media_type="text/plain")
    raise HTTPException(status_code=403, detail="Token de verificación inválido")

@app.post("/webhook/meta")
async def webhook_meta(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    # Procesamiento asíncrono de mensajes entrantes de Meta
    return {"status": "recibido", "proveedor": "meta"}

@app.post("/webhook/zernio")
async def webhook_zernio(request: Request):
    body = await request.json()
    return {"status": "recibido", "proveedor": "zernio"}

@app.post("/webhook/demo")
async def webhook_demo(request: Request):
    body = await request.json()
    return {"status": "recibido", "proveedor": "demo"}
