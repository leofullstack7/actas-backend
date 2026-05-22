from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
from openai import OpenAI
import os

app = FastAPI()


class ForceCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method == "OPTIONS":
            response = Response()
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "*"
            return response
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response


app.add_middleware(ForceCORSMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """Eres la secretaria de despacho del Honorable Concejo de Manizales. Redactas ACTAS OFICIALES con estilo jurídico-administrativo colombiano.

FORMATO OBLIGATORIO DE QUÓRUM:
"procedió de conformidad declarando que al llamado a lista respondieron los siguientes honorables concejales: [lista de nombres completos]. Anunciando que había quórum para deliberar y decidir."

ARTÍCULOS REALES DEL REGLAMENTO INTERNO — cítalos siempre:
- Artículo N°. 78: verificación del quórum
- Artículo N°. 79: lectura del orden del día
- Artículo N°. 80: aprobaciones por unanimidad
- Artículo N°. 104: proposiciones
- Artículo N°. 155: enmiendas en segundo debate

PROHIBIDO ABSOLUTAMENTE:
- CERO Markdown: ni #, ##, **, *, —
- CERO encabezados de sección
- CERO listas con viñetas ni numeradas
- CERO JSON ni listas técnicas
- Los nombres de concejales van DENTRO de los párrafos, nunca como títulos

TODO debe ser prosa corrida con conectores formales.

REGLAS ABSOLUTAS:
- Tercera persona siempre
- Nombres completos + partido político en cada mención
- Cada intervención mínimo 5 párrafos completos
- Conectores formales: "Acto seguido...", "Posteriormente...", "Seguidamente...", "A continuación...", "Prosiguió con el uso de la palabra...", "Retomó su intervención..."
- Números en letras cuando sean ordinales o fechas: "veintiséis (26)"
- Tu trabajo NO es resumir. Es redactar un documento EXTENSO, FORMAL y ELEGANTE"""


class ActaRequest(BaseModel):
    youtubeUrl: str


def extract_video_id(youtube_url: str) -> str:
    try:
        u = urlparse(youtube_url)
        if u.hostname in ("youtu.be",):
            return u.path.lstrip("/")
        if u.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
            if u.path.startswith("/watch"):
                return parse_qs(u.query).get("v", [None])[0]
            if u.path.startswith("/live/") or u.path.startswith("/shorts/"):
                return u.path.split("/")[2]
    except Exception:
        pass
    raise HTTPException(status_code=422, detail="No se pudo extraer el ID del video.")


async def get_transcript(youtube_url: str) -> str:
    video_id = extract_video_id(youtube_url)
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["es", "es-419", "es-CO", "en"])
        return " ".join([t["text"] for t in transcript])
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"No se encontró transcripción: {str(e)}")


def generar_parte(transcripcion: str, parte: int, parte_anterior: str = "") -> str:
    if parte == 1:
        user_prompt = f"""TRANSCRIPCIÓN DE LA SESIÓN:
{transcripcion}

INSTRUCCIONES:
Redacta SOLAMENTE los primeros puntos del orden del día con máximo detalle. NO desarrolles el cierre de la sesión ni los últimos puntos. Esos se desarrollarán en partes siguientes.

Para la apertura y quórum:
Inicia con la fórmula exacta: "En la ciudad de Manizales, siendo las [hora] del [día] de [mes] de [año], se reunió en sesión ordinaria el Honorable Concejo de Manizales..." Luego lista TODOS los concejales presentes por nombre completo, citando el artículo N°. 78.

Para cada concejal que interviene:
1. Describir su saludo y presentación inicial con protocolo formal
2. Desarrollar CADA argumento con contexto jurídico y político, mínimo 5 párrafos
3. Describir cómo relacionó sus puntos con el tema central
4. Describir su cierre y conclusión
5. Describir la reacción de la plenaria

Para cada votación:
1. Quién propuso someter a votación
2. Resultado exacto con fórmula: "fue aprobada por unanimidad"
3. Citar el artículo del Reglamento Interno aplicable

Termina tu texto EXACTAMENTE con esta frase:
"Agotados los puntos anteriores del orden del día, el presidente del Honorable Concejo procedió a dar paso al siguiente punto del orden del día."

CERO Markdown. CERO resúmenes. Desarrolla cada punto con el máximo detalle posible."""

    elif parte == 2:
        user_prompt = f"""TRANSCRIPCIÓN COMPLETA DE LA SESIÓN:
{transcripcion}

FINAL DE LA PRIMERA PARTE (continúa exactamente desde aquí):
{parte_anterior[-3000:]}

INSTRUCCIONES:
Continúa el acta exactamente desde donde terminó la primera parte. NO repitas ni una sola palabra ya escrita. NO pongas encabezado ni título, empieza directamente con el siguiente párrafo.

Revisa la transcripción y determina qué puntos del orden del día quedaron pendientes después de la primera parte. Desarrolla CADA uno de esos puntos con máximo detalle.

Para cada funcionario o concejal que intervenga:
- Desarrolla su intervención completa con mínimo 5 párrafos
- Cita sus argumentos exactos según la transcripción
- Usa conectores formales entre párrafos

Para cada votación o proposición:
- Quién la propuso
- Resultado con fórmula exacta
- Artículo del Reglamento Interno aplicable

Termina tu texto EXACTAMENTE con esta frase:
"Agotados los puntos anteriores del orden del día, el presidente del Honorable Concejo procedió a dar paso al siguiente punto del orden del día."

CERO Markdown. CERO resúmenes. Desarrolla cada punto con el máximo detalle posible."""

    else:
        user_prompt = f"""TRANSCRIPCIÓN COMPLETA DE LA SESIÓN:
{transcripcion}

FINAL DE LA SEGUNDA PARTE (continúa exactamente desde aquí):
{parte_anterior[-3000:]}

INSTRUCCIONES:
Continúa el acta exactamente desde donde terminó la segunda parte. NO repitas ni una sola palabra ya escrita. NO pongas encabezado ni título, empieza directamente con el siguiente párrafo.

Revisa la transcripción e identifica los temas que aún no han sido desarrollados. Desarrolla TODO lo que falte hasta cerrar la sesión completamente.

Para cada funcionario o concejal que aún no haya aparecido o que tenga intervenciones pendientes:
- Desarrolla su intervención completa con mínimo 5 párrafos
- Cita sus argumentos exactos según la transcripción
- Usa conectores formales entre párrafos

Para el cierre de la sesión incluye obligatoriamente:
- Resultado final de todas las votaciones pendientes
- Proposiciones de cierre con sus proponentes
- Fórmula exacta de clausura: "No siendo otro el objeto de la presente sesión, el señor Presidente declaró clausurada la sesión, siendo las [hora]."
- Firma de la Secretaria de Despacho y del Presidente del Concejo

CERO Markdown. CERO resúmenes. Este es el texto final del acta, debe cerrar completamente."""

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=4096,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or ""


@app.options("/generar-acta")
async def options_generar_acta(request: Request):
    return JSONResponse(content={}, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "*",
    })


@app.post("/generar-acta")
async def generar_acta(req: ActaRequest):
    transcripcion = await get_transcript(req.youtubeUrl)

    parte1 = generar_parte(transcripcion, 1)
    parte2 = generar_parte(transcripcion, 2, parte1)
    parte3 = generar_parte(transcripcion, 3, parte2)

    acta_completa = parte1 + "\n\n" + parte2 + "\n\n" + parte3

    return {"acta": acta_completa, "palabras": len(acta_completa.split())}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
