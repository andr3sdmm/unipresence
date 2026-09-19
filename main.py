"""
UniPresence - Verificacion de presencia fisica en aulas grandes
MVP dia 1: QR dinamico + registro de dispositivo

Como correrlo:
    source venv/bin/activate
    uvicorn main:app --reload

Luego abrir http://localhost:8000 en el navegador.
"""

import io
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import qrcode
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse

# ---------------------------------------------------------------
# CONFIGURACION
# ---------------------------------------------------------------

DB_PATH = "unipresence.db"

# Cuantos segundos vive cada QR antes de expirar.
# Este numero es una decision de diseno: mientras mas corto, mas dificil
# reenviar el QR por WhatsApp; mientras mas largo, mas comodo para el
# estudiante que esta al fondo del salon.
NONCE_SEGUNDOS = 10

app = FastAPI(title="UniPresence")


# ---------------------------------------------------------------
# BASE DE DATOS
# ---------------------------------------------------------------

def conectar():
    """Abre una conexion a SQLite. row_factory permite leer por nombre de columna."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def iniciar_db():
    """Crea las cuatro tablas si no existen. Se ejecuta al arrancar el servidor."""
    conn = conectar()
    c = conn.cursor()

    # Un estudiante y el dispositivo al que quedo amarrado.
    # device_id es UNIQUE: un telefono solo puede pertenecer a un estudiante.
    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            student_code  TEXT NOT NULL UNIQUE,
            device_id     TEXT NOT NULL UNIQUE,
            registered_at TEXT NOT NULL
        )
    """)

    # Una sesion = una clase concreta en una fecha concreta.
    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name TEXT NOT NULL,
            started_at  TEXT NOT NULL,
            ended_at    TEXT,
            active      INTEGER NOT NULL DEFAULT 1
        )
    """)

    # Cada nonce corresponde a un QR mostrado en el proyector.
    # OJO: varios estudiantes escanean el MISMO QR al mismo tiempo, asi que
    # un nonce NO es de un solo uso. Lo que lo protege es la expiracion.
    c.execute("""
        CREATE TABLE IF NOT EXISTS nonces (
            nonce      TEXT PRIMARY KEY,
            session_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_by    TEXT
        )
    """)

    # El registro de asistencia.
    # UNIQUE(session_id, student_id) impide registrar dos veces en la misma clase.
    # method distingue 'qr' de 'manual' para que al analizar resultados no se mezclen.
    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            timestamp  TEXT NOT NULL,
            method     TEXT NOT NULL,
            nonce_used TEXT,
            UNIQUE(session_id, student_id)
        )
    """)

    conn.commit()
    conn.close()


@app.on_event("startup")
def al_arrancar():
    iniciar_db()


def ahora():
    """Hora actual en UTC, como texto ISO. Siempre UTC para evitar lios de zona horaria."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------
# PANTALLA DEL PROFESOR
# ---------------------------------------------------------------

PAGINA_PROFESOR = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>UniPresence</title>
  <style>
    body { font-family: -apple-system, sans-serif; text-align: center; padding: 40px; }
    #qr { width: 400px; height: 400px; }
    #contador { font-size: 64px; font-weight: bold; margin: 20px; }
    button { font-size: 24px; padding: 16px 32px; cursor: pointer; }
  </style>
</head>
<body>
  <h1>UniPresence</h1>
  <div id="antes">
    <button onclick="iniciar()">Iniciar asistencia</button>
  </div>
  <div id="durante" style="display:none">
    <img id="qr" src="">
    <div id="contador">0</div>
    <p>estudiantes registrados</p>
  </div>

<script>
let sesion = null;

async function iniciar() {
  // Le pide al servidor que cree una sesion nueva.
  const r = await fetch('/session/start', { method: 'POST' });
  const datos = await r.json();
  sesion = datos.session_id;

  document.getElementById('antes').style.display = 'none';
  document.getElementById('durante').style.display = 'block';

  refrescarQR();
  refrescarContador();

  // El QR se renueva cada NONCE_SEGUNDOS. El truco del ?t= es obligar al
  // navegador a pedir la imagen de nuevo en vez de usar la que tiene guardada.
  setInterval(refrescarQR, SEGUNDOS * 1000);
  setInterval(refrescarContador, 3000);
}

function refrescarQR() {
  document.getElementById('qr').src = '/qr/' + sesion + '?t=' + Date.now();
}

async function refrescarContador() {
  const r = await fetch('/session/' + sesion + '/count');
  const datos = await r.json();
  document.getElementById('contador').textContent = datos.count;
}
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def pantalla_profesor():
    # Inserta el valor real de NONCE_SEGUNDOS dentro del JavaScript.
    return PAGINA_PROFESOR.replace("SEGUNDOS", str(NONCE_SEGUNDOS))


# ---------------------------------------------------------------
# SESIONES
# ---------------------------------------------------------------

@app.post("/session/start")
def iniciar_sesion(course_name: str = "Genetica"):
    conn = conectar()
    c = conn.cursor()
    c.execute(
        "INSERT INTO sessions (course_name, started_at, active) VALUES (?, ?, 1)",
        (course_name, ahora()),
    )
    conn.commit()
    session_id = c.lastrowid
    conn.close()
    return {"session_id": session_id, "course_name": course_name}


@app.get("/session/{session_id}/count")
def contar(session_id: int):
    conn = conectar()
    fila = conn.execute(
        "SELECT COUNT(*) AS n FROM attendance WHERE session_id = ?", (session_id,)
    ).fetchone()
    conn.close()
    return {"count": fila["n"]}


# ---------------------------------------------------------------
# GENERACION DEL QR
# ---------------------------------------------------------------

@app.get("/qr/{session_id}")
def generar_qr(session_id: int, request: Request):
    """
    Crea un nonce nuevo y devuelve un PNG del QR.

    DECISION CLAVE DEL DISENO: el QR no contiene un codigo, contiene una URL
    completa. Asi la camara nativa del celular (iPhone o Android) lo lee y
    ofrece abrir el enlace directamente. No hay que programar ningun lector
    de QR ni pedir permiso de camara.
    """
    nonce = secrets.token_hex(8)
    creado = datetime.now(timezone.utc)
    expira = creado + timedelta(seconds=NONCE_SEGUNDOS)

    conn = conectar()
    conn.execute(
        "INSERT INTO nonces (nonce, session_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (nonce, session_id, creado.isoformat(), expira.isoformat()),
    )
    conn.commit()
    conn.close()

    # base_url viene del servidor, asi funciona igual en local, en ngrok y en Render.
    url = f"{str(request.base_url).rstrip('/')}/checkin?s={session_id}&n={nonce}"

    img = qrcode.make(url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},  # que el navegador nunca lo reuse
    )


# ---------------------------------------------------------------
# CHECK-IN DEL ESTUDIANTE
# ---------------------------------------------------------------

def envolver(cuerpo: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>UniPresence</title>
<style>
  body {{ font-family: -apple-system, sans-serif; padding: 40px 24px; text-align: center; }}
  .ok {{ color: #1a7f37; font-size: 28px; font-weight: bold; }}
  .error {{ color: #b91c1c; font-size: 24px; font-weight: bold; }}
  input, button {{ font-size: 20px; padding: 12px; width: 100%; box-sizing: border-box; margin: 8px 0; }}
</style>
</head>
<body>{cuerpo}</body>
</html>
"""


def validar_nonce(conn, session_id: int, nonce: str):
    """Devuelve (True, '') si el nonce sirve, o (False, motivo) si no."""
    fila = conn.execute(
        "SELECT * FROM nonces WHERE nonce = ? AND session_id = ?", (nonce, session_id)
    ).fetchone()

    if fila is None:
        return False, "Codigo invalido."

    if datetime.now(timezone.utc) > datetime.fromisoformat(fila["expires_at"]):
        return False, "Este codigo ya expiro. Escanea el QR actual en la pantalla."

    return True, ""


@app.get("/checkin", response_class=HTMLResponse)
def checkin(s: int, n: str, request: Request):
    device_id = request.cookies.get("device_id")

    conn = conectar()
    valido, motivo = validar_nonce(conn, s, n)
    if not valido:
        conn.close()
        return envolver(f"<p class='error'>{motivo}</p>")

    # Dispositivo nuevo: pedirle su codigo de estudiante una sola vez.
    if not device_id:
        conn.close()
        nuevo = secrets.token_hex(16)
        html = envolver(f"""
            <h2>Primera vez</h2>
            <p>Escribe tu codigo de estudiante. Solo se pide una vez.</p>
            <form method="post" action="/register">
              <input name="student_code" placeholder="Codigo de estudiante" required autofocus>
              <input type="hidden" name="s" value="{s}">
              <input type="hidden" name="n" value="{n}">
              <button type="submit">Registrar</button>
            </form>
        """)
        respuesta = HTMLResponse(html)
        # max_age de un ano: el amarre dispositivo-estudiante debe sobrevivir.
        respuesta.set_cookie("device_id", nuevo, max_age=31536000, httponly=True, samesite="lax")
        return respuesta

    estudiante = conn.execute(
        "SELECT * FROM students WHERE device_id = ?", (device_id,)
    ).fetchone()

    # Tiene cookie pero nunca completo el registro.
    if estudiante is None:
        conn.close()
        return envolver(f"""
            <h2>Primera vez</h2>
            <form method="post" action="/register">
              <input name="student_code" placeholder="Codigo de estudiante" required autofocus>
              <input type="hidden" name="s" value="{s}">
              <input type="hidden" name="n" value="{n}">
              <button type="submit">Registrar</button>
            </form>
        """)

    mensaje = registrar_asistencia(conn, s, estudiante["id"], n, "qr")
    conn.close()
    return envolver(mensaje)


@app.post("/register", response_class=HTMLResponse)
def registrar_dispositivo(
    request: Request,
    student_code: str = Form(...),
    s: int = Form(...),
    n: str = Form(...),
):
    """Amarra este dispositivo a un codigo de estudiante y registra la asistencia."""
    device_id = request.cookies.get("device_id")
    if not device_id:
        return envolver("<p class='error'>No se pudo identificar el dispositivo. Vuelve a escanear.</p>")

    conn = conectar()
    valido, motivo = validar_nonce(conn, s, n)
    if not valido:
        conn.close()
        return envolver(f"<p class='error'>{motivo}</p>")

    try:
        conn.execute(
            "INSERT INTO students (student_code, device_id, registered_at) VALUES (?, ?, ?)",
            (student_code.strip(), device_id, ahora()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Salta si el codigo ya existe con OTRO dispositivo, o si este
        # dispositivo ya esta amarrado a otro codigo. Esa es la defensa
        # contra registrar a varios companeros desde un mismo telefono.
        conn.close()
        return envolver(
            "<p class='error'>Ese codigo ya esta registrado en otro dispositivo, "
            "o este dispositivo ya pertenece a otro estudiante.</p>"
        )

    estudiante = conn.execute(
        "SELECT * FROM students WHERE device_id = ?", (device_id,)
    ).fetchone()

    mensaje = registrar_asistencia(conn, s, estudiante["id"], n, "qr")
    conn.close()
    return envolver(mensaje)


def registrar_asistencia(conn, session_id: int, student_id: int, nonce: str, method: str) -> str:
    try:
        conn.execute(
            "INSERT INTO attendance (session_id, student_id, timestamp, method, nonce_used) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, student_id, ahora(), method, nonce),
        )
        conn.commit()
        return "<p class='ok'>Asistencia registrada</p>"
    except sqlite3.IntegrityError:
        return "<p class='ok'>Ya estabas registrado en esta clase</p>"
