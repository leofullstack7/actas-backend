from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from pydantic import BaseModel
import httpx
import anthropic
import os
import tempfile
from generar_docx import texto_a_docx

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

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

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


async def get_transcript(youtube_url: str) -> str:
    async with httpx.AsyncClient(timeout=60.0) as http:
        resp = await http.get(
            "https://api.supadata.ai/v1/youtube/transcript",
            params={"url": youtube_url, "text": "true"},
            headers={"x-api-key": os.environ.get("SUPADATA_API_KEY")},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Supadata error: {resp.text}")
        data = resp.json()
        transcript = data.get("content") or data.get("text") or ""
        if not transcript:
            raise HTTPException(status_code=422, detail="No se encontró transcripción para este video.")
        return transcript


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

    elif parte == 3:
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

    elif parte == 4:
        user_prompt = f"""TRANSCRIPCIÓN COMPLETA DE LA SESIÓN:
{transcripcion[-8000:]}

FINAL DE LA TERCERA PARTE (continúa exactamente desde aquí):
{parte_anterior[-3000:]}

INSTRUCCIONES:
Continúa y CIERRA el acta definitivamente desde donde terminó la tercera parte. Este es el párrafo final del documento.

Incluye obligatoriamente:
- Cualquier intervención pendiente que aparezca en la transcripción
- Proposición de clausura con su proponente
- Fórmula exacta: "No siendo otro el objeto de la presente sesión, el señor Presidente declaró clausurada la sesión, siendo las [hora]."
- Bloque de firmas:

Para constancia se firma la presente acta,

[NOMBRE PRESIDENTE]
Presidente Honorable Concejo de Manizales

[NOMBRE SECRETARIA]
Secretaria de Despacho

CERO Markdown. CERO resúmenes. Cierra el documento completamente."""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text


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
    parte4 = generar_parte(transcripcion, 4, parte3)

    acta_completa = parte1 + "\n\n" + parte2 + "\n\n" + parte3 + "\n\n" + parte4

    return {"acta": acta_completa, "palabras": len(acta_completa.split())}


@app.post("/generar-acta-docx")
async def generar_acta_docx(req: ActaRequest):
    transcripcion = await get_transcript(req.youtubeUrl)
    parte1 = generar_parte(transcripcion, 1)
    parte2 = generar_parte(transcripcion, 2, parte1)
    parte3 = generar_parte(transcripcion, 3, parte2)
    parte4 = generar_parte(transcripcion, 4, parte3)
    acta_completa = parte1 + "\n\n" + parte2 + "\n\n" + parte3 + "\n\n" + parte4

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    texto_a_docx(acta_completa, tmp.name)

    return FileResponse(
        tmp.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="Acta_Concejo_Manizales.docx",
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
