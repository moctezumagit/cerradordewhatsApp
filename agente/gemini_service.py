"""Servicio de Inteligencia Artificial para el Cerrador de WhatsApp con Google Gemini."""
import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional

# Cargar configuraciones
CONFIG_DIR = Path("config")

def cargar_playbook() -> Dict[str, Any]:
    playbook_path = CONFIG_DIR / "playbook.yaml"
    if playbook_path.exists():
        with open(playbook_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def cargar_catalogo() -> Dict[str, Any]:
    catalogo_path = CONFIG_DIR / "catalogo.yaml"
    if catalogo_path.exists():
        with open(catalogo_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def cargar_agenda() -> Dict[str, Any]:
    agenda_path = CONFIG_DIR / "agenda.yaml"
    if agenda_path.exists():
        with open(agenda_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def obtener_prompt_sistema() -> str:
    playbook = cargar_playbook().get("playbook", {})
    catalogo = cargar_catalogo().get("negocio", {})
    agenda = cargar_agenda().get("agenda", {})

    objeciones_texto = ""
    for idx, obj in enumerate(playbook.get("objeciones", []), 1):
        objeciones_texto += f"\nObjeción {idx}: «{obj.get('objecion')}»\nGuía de respuesta: {obj.get('respuesta')}\n"

    return f"""Eres el Agente Calificador y Cerrador de WhatsApp oficial para el equipo de María de Jesús Vera.
Tu misión es actuar como setter y closer experto: conversar con prospectos que llegan por WhatsApp, filtrar y calificar su perfil, responder sus objeciones con liderazgo y derivarlos a agendar la LLAMADA 1 A 1 GRATUITA DE ORIENTACIÓN (15 minutos) con María de Jesús Vera (+52 244 123 5715).

--- INFORMACIÓN CLAVE DEL NEGOCIO ---
- Oferta: Programa de red de Asociados / Consultores Independientes en la industria de bienestar digital y biotecnología celular (más de 45 años de ciencia, investigación médica y patentes internacionales).
- Operación: Logística y envíos 100% automatizados directos de fábrica al cliente (sin inventario detenido en casa, sin cobrar fiado, sin bodegas).
- Propuesta al prospecto: NO se vende producto en frío ni venta individual. Se ofrece SUMARSE COMO SOCIO y construir equipo red con sistema paso a paso, capacitación remota y mentoría real 1 a 1 sin descuidar su empleo o negocio actual (en paralelo, 10-12 hrs/semana).
- Países atendidos: México, Colombia, Perú y Ecuador.
- Contacto de la mentora: María de Jesús Vera (+52 244 123 5715). Enlace directo: https://wa.me/522441235715

--- REGLAS DE ORO OBLIGATORIAS (INQUEBRANTABLES) ---
1. TRATAMIENTO DE TÚ: Habla siempre de TÚ (público México y LatAm). Jamás uses "vos" ni "usted".
2. TONO Y RECONOCIMIENTO: Cercano, empático, profesional, consultivo y con postura de liderazgo. Usa tu frase firma con naturalidad: «Te felicito por abrirte a escuchar» o «Te felicito por abrirte al cambio de mentalidad». Valida siempre la experiencia del prospecto si ya vende por catálogo, tiene negocio o red. Nunca lo trates como principiante.
3. PROHIBIDO DAR PRECIOS O CIFRAS DE INGRESOS: NUNCA des montos exactos, porcentajes garantizados ni prometas ingresos mensuales. La activación es con una caja de producto y los costos y paquetes exactos se presentan de forma transparente en la llamada de 15 min según su país.
4. CIERRE Y DERIVACIÓN: El único objetivo de cierre es agendar la llamada de 15 minutos (por videollamada o teléfono) con María de Jesús Vera o darle el enlace a su WhatsApp oficial (+52 244 123 5715). NO hay enlaces de pago ni venta directa en el chat.
5. MENSAJES CORTOS: Estilo WhatsApp, 2 a 3 líneas claras y fluidas por mensaje. Cierra casi siempre con una pregunta clara o una propuesta de horario (mañana o tarde).

--- PLAYBOOK DE OBJECIONES OFICIALES ---
{objeciones_texto}

--- FORMATO DE SALIDA (ESTRICTAMENTE JSON) ---
Debes responder con un objeto JSON válido con esta estructura:
{{
  "calificacion": {{
    "score": <número entre 0 y 100>,
    "temperatura": <"caliente", "tibio" o "frio">,
    "urgencia": <"alta", "media" o "baja">,
    "intencion": <resumen en 1 frase de lo que busca el prospecto>,
    "pais": <"México", "Colombia", "Perú", "Ecuador" o "Desconocido">,
    "experiencia": <resumen si tiene experiencia en ventas/comercio o novato>,
    "motivo": <explicación del score>
  }},
  "objecion_detectada": <nombre de la objeción detectada o null>,
  "objecion_en_playbook": <true si está en el playbook, false si es una objeción nueva o no contemplada>,
  "horario_ofrecido": <franja horaria sugerida o null>,
  "agendado": <true si el usuario acordó tener la llamada, false en otro caso>,
  "escalar": <true si el usuario está enojado, pide hablar con un humano urgente o exige cosas fuera de catálogo>,
  "crm_etapa": <"nuevo", "calificado", "agendado", "en_seguimiento", "escalado" o "perdido">,
  "proximo_paso": <acción siguiente recomendada para María o el sistema>,
  "respuesta_texto": <el mensaje exacto que el agente enviará por WhatsApp al prospecto>
}}
"""

def analizar_mensaje_con_gemini(
    mensaje_actual: str,
    historial: List[Dict[str, Any]],
    nombre_contacto: Optional[str] = None,
    api_key_override: Optional[str] = None,
    modelo_override: Optional[str] = None
) -> Dict[str, Any]:
    """Envía la conversación a Google Gemini y retorna el análisis estructurado de 6 pasos."""
    api_key = api_key_override or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    modelo = modelo_override or os.getenv("MODELO_GEMINI", "gemini-3.8-flash")

    # Si hay API Key disponible, invocamos el SDK oficial de Gemini
    if api_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)

            # Preparar contexto de chat
            contenido_conversacion = f"Prospecto: {nombre_contacto or 'Contacto'}\n\nHistorial previo:\n"
            for m in historial[-8:]: # últimos 8 turnos
                rol = "Prospecto" if m.get("rol") == "usuario" else "Agente María Closer"
                contenido_conversacion += f"- {rol}: {m.get('contenido')}\n"

            contenido_conversacion += f"\nNuevo mensaje del prospecto:\n«{mensaje_actual}»\n\nAnaliza y genera la respuesta en formato JSON estricto."

            response = client.models.generate_content(
                model=modelo,
                contents=contenido_conversacion,
                config=types.GenerateContentConfig(
                    system_instruction=obtener_prompt_sistema(),
                    response_mime_type="application/json",
                    temperature=0.3
                )
            )

            if response and response.text:
                data = json.loads(response.text)
                return data

        except Exception as e:
            # Si falla la llamada externa, cae al motor inteligente local
            print(f"Aviso: Falló la llamada a Gemini ({e}). Usando motor de respaldo con Playbook.")

    # Motor de respaldo local de alta fidelidad basado en el Playbook oficial
    return _generar_respuesta_local_playbook(mensaje_actual, historial, nombre_contacto)


def _generar_respuesta_local_playbook(
    mensaje: str,
    historial: List[Dict[str, Any]],
    nombre: Optional[str]
) -> Dict[str, Any]:
    """Generador local inteligente basado 100% en las 10 objeciones y directrices de María de Jesús Vera."""
    m_lower = mensaje.lower().strip()
    nombre_txt = f"{nombre}, " if nombre else ""

    # Detección de Objeciones
    objecion = None
    objecion_playbook = True
    score = 50
    temperatura = "tibio"
    urgencia = "media"
    agendado = False
    escalar = False
    etapa = "calificado"
    horario = None

    if any(k in m_lower for k in ["piramide", "pirámide", "estafa", "fraude"]):
        objecion = "¿Es pirámide / es estafa?"
        respuesta = (
            f"Te entiendo perfecto la duda, {nombre_txt}es natural cuidar el tiempo y el patrimonio. Te felicito por abrirte a escuchar con criterio.\n\n"
            "Esta es una red de mercadeo formal respaldada por una empresa internacional con más de 45 años de ciencia, patentes médicas e investigación clínica, y producto físico de consumo recurrente con logística automatizada.\n\n"
            "La explicación completa del modelo y sus reglas te las presenta María en la llamada de orientación de 15 minutos. ¿Te gustaría coordinar ese espacio?"
        )
        score = 65
        horario = "Mañana o tarde"

    elif any(k in m_lower for k in ["cuanto se gana", "cuánto se gana", "cuanto gano", "ganancias", "ingresos"]):
        objecion = "¿Cuánto se gana?"
        respuesta = (
            f"Es una pregunta muy válida cuando se emprende, {nombre_txt}y te felicito por tener visión de negocio.\n\n"
            "Las comisiones dependen directamente de la productividad y del crecimiento del equipo, por lo que no prometemos cifras mágicas ni garantías fijas sin conocer tu dedicación. Lo que sí te aseguramos es el sistema paso a paso, las capacitaciones y la mentoría 1 a 1 para que logres resultados sostenibles.\n\n"
            "En la llamada de orientación María te muestra el plan oficial y cómo proyectar tus metas. ¿Qué día te viene mejor para platicar 15 minutos con ella?"
        )
        score = 70
        horario = "15 minutos con María"

    elif any(k in m_lower for k in ["cuanto cuesta", "cuánto cuesta", "precio", "costo", "inversion", "inversión", "para entrar"]):
        objecion = "¿Cuánto cuesta entrar?"
        respuesta = (
            f"La activación al negocio se realiza mediante un paquete de producto inicial (una caja de producto), con logística y envíos directos de fábrica.\n\n"
            "El monto exacto y las promociones vigentes varían según tu país (México, Colombia, Perú o Ecuador) y se confirman con total transparencia en la llamada de orientación personalizada con María.\n\n"
            "¿Desde qué país nos escribes para tener a la mano los detalles correspondientes?"
        )
        score = 75
        temperatura = "caliente"

    elif any(k in m_lower for k in ["otra compañía", "otra empresa", "ya vendo", "catálogo", "catalogo", "mary kay", "betterware", "omnilife", "amway", "herbalife", "natura"]):
        objecion = "Ya estoy en otra compañía / ya vendo otra cosa"
        respuesta = (
            f"¡Te felicito por esa trayectoria, {nombre_txt}es una gran ventaja! Las personas con experiencia comercial y contactos como tú son justo el perfil ideal para este equipo.\n\n"
            "No se te pide en ningún momento dejar lo que ya haces; la propuesta está diseñada para sumar en paralelo de forma apalancada y sin descuidar tu actividad principal.\n\n"
            "¿Te gustaría conocer en 15 minutos cómo compaginar ambos proyectos con el acompañamiento de María?"
        )
        score = 85
        temperatura = "caliente"
        etapa = "calificado"
        horario = "Llamada de 15 minutos"

    elif any(k in m_lower for k in ["me dejaron solo", "ya lo intente", "ya lo intenté", "no me apoyaron"]):
        objecion = "Ya lo intenté y me dejaron solo"
        respuesta = (
            f"Te comprendo totalmente, {nombre_txt}y es muy frustrante. El problema en esos casos no fue el modelo de negocio, sino el abandono del equipo.\n\n"
            "Aquí la diferencia fundamental es que cuentas con un sistema probado, capacitación remota y acompañamiento real 1 a 1 de la mano de María de Jesús Vera desde tu primer día.\n\n"
            "¿Te gustaría agendar una breve llamada para que conozcas la metodología de trabajo?"
        )
        score = 80
        temperatura = "caliente"

    elif any(k in m_lower for k in ["no tengo tiempo", "tiempo", "mi trabajo", "ocupado", "no puedo dejar"]):
        objecion = "No tengo tiempo / No puedo dejar mi trabajo o negocio actual"
        respuesta = (
            f"Tiene todo el sentido, {nombre_txt}y por eso te felicito por abrirte a escuchar alternativas inteligentes.\n\n"
            "Precisamente este modelo está diseñado para construirse a tiempo parcial (de 10 a 12 horas por semana), en paralelo a tu ocupación actual sin descuidar tus ingresos principales. Con el sistema de envíos automatizados no inviertes tiempo en repartos ni cobranza.\n\n"
            "¿En qué horario sueles tener un espacio más despejado para una llamada de 15 minutos?"
        )
        score = 75

    elif any(k in m_lower for k in ["menudeo", "cobrar", "fiado", "perseguir", "vender"]):
        objecion = "No me gusta vender al menudeo, cobrar ni andar persiguiendo gente"
        respuesta = (
            f"Te entiendo al 100%, {nombre_txt}a nadie le gusta andar cobrando ni persiguiendo amigos.\n\n"
            "Nosotros no trabajamos con venta tradicional ni cobramos fiado. La compañía se encarga de toda la logística de envíos directos de fábrica y facturación al cliente. Tu enfoque como socio es liderar, duplicar y construir equipo con prospección profesional.\n\n"
            "¿Te parece si revisamos esta dinámica en una llamada breve de 15 minutos con María?"
        )
        score = 80
        temperatura = "caliente"

    elif any(k in m_lower for k in ["inventario", "detenido", "stock", "en casa"]):
        objecion = "Tengo producto/inventario detenido en casa"
        respuesta = (
            f"Esa es una de las grandes razones por las que muchos socios se unieron a nosotros: nuestro modelo funciona con envíos directos de fábrica al domicilio del cliente.\n\n"
            "No requieres acumular stock, no necesitas bodegas en casa ni te arriesgas a que se te quede producto detenido.\n\n"
            "¿Te gustaría platicar 15 minutos con María para conocer cómo opera esta logística?"
        )
        score = 85
        temperatura = "caliente"

    elif any(k in m_lower for k in ["pdf", "video", "vídeo", "informacion", "información", "mandame", "mándame", "enviame", "envíame"]):
        objecion = "Envíame toda la información por PDF o video antes de hablar"
        respuesta = (
            f"Con gusto te compartimos material, {nombre_txt}sin embargo, cuidamos mucho el tiempo de ambos y la propuesta se personaliza según tu disponibilidad, experiencia y país.\n\n"
            "Por eso, la llamada de orientación de 15 minutos con María es el espacio más productivo para resolver dudas específicas y ver si hay encaje mutuo.\n\n"
            "¿Prefieres mañana por la mañana o por la tarde para coordinar?"
        )
        score = 70

    elif any(k in m_lower for k in ["si", "sí", "me interesa", "agendar", "coordinar", "quiero la llamada", "perfecto", "mañana", "tarde"]):
        agendado = True
        etapa = "agendado"
        score = 95
        temperatura = "caliente"
        urgencia = "alta"
        respuesta = (
            f"¡Excelente decisión, {nombre_txt}te felicito por abrirte al cambio de mentalidad y a nuevas oportunidades!\n\n"
            "Ya le pasé tu contacto a María de Jesús Vera para tu llamada de orientación de 15 minutos. También puedes mandarle un mensaje directo a su WhatsApp oficial haciendo clic aquí:\n"
            "👉 https://wa.me/522441235715\n\n"
            "¿Prefieres que la llamada sea por la mañana (10:00 - 13:00) o por la tarde (16:00 - 19:00)?"
        )
        horario = "10:00 - 13:00 o 16:00 - 19:00"

    else:
        # Mensaje de bienvenida / inicio
        respuesta = (
            f"Hola, {nombre_txt}¡te felicito por abrirte a escuchar! Qué gusto saludarte.\n\n"
            "Te platico brevemente: este es un programa para asociarte como Consultor Independiente en la industria del bienestar y biotecnología celular, con más de 45 años de ciencia y envíos 100% automatizados sin almacenar inventario ni cobrar fiado.\n\n"
            "Cuéntame, ¿actualmente ya tienes experiencia en ventas, comercio o redes, o buscas iniciar desde cero a tiempo parcial?"
        )

    # Detección de país
    pais = "México"
    if "colombia" in m_lower:
        pais = "Colombia"
    elif "peru" in m_lower or "perú" in m_lower:
        pais = "Perú"
    elif "ecuador" in m_lower:
        pais = "Ecuador"

    return {
        "calificacion": {
            "score": score,
            "temperatura": temperatura,
            "urgencia": urgencia,
            "intencion": "Sumarse como socio en red de mercadeo / orientación",
            "pais": pais,
            "experiencia": "Con experiencia previa o ventas por catálogo/comercio",
            "motivo": f"Prospecto calificado con respuesta afín al Playbook. Objeción: {objecion or 'Indagación inicial'}."
        },
        "objecion_detectada": objecion,
        "objecion_en_playbook": objecion_playbook,
        "horario_ofrecido": horario,
        "agendado": agendado,
        "escalar": escalar,
        "crm_etapa": etapa,
        "proximo_paso": "Derivar a llamada de 15 minutos con María de Jesús Vera (+52 244 123 5715)",
        "respuesta_texto": respuesta
    }
