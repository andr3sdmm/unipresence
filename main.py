"""
UniPresence - Verificacion de presencia fisica en aulas grandes
MVP dia 2: registro separado del check-in

CAMBIO PRINCIPAL respecto al dia 1:
El registro (amarrar un telefono a un codigo de estudiante) ya NO ocurre
durante el check-in. Son dos momentos distintos con necesidades distintas:

  REGISTRO   -> identificacion. Pasa una sola vez, antes de clase.
                Requiere escribir texto, asi que no puede tener una
                ventana de 10 segundos. No lleva nonce.

  CHECK-IN   -> verificacion de presencia. Pasa en cada clase.
                No requiere escribir nada. Ventana de 10 segundos.

Esta separacion salio de la primera prueba real: el QR expiraba mientras
se escribia el codigo de estudiante.

Como correrlo:
    source venv/bin/activate
    uvicorn main:app --reload
"""

import io
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import qrcode
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse

# ---------------------------------------------------------------
# CONFIGURACION
# ---------------------------------------------------------------

DB_PATH = "unipresence.db"

# Cuantos segundos vive cada QR de asistencia antes de expirar.
# Decision de diseno: mas corto = mas dificil reenviar por WhatsApp;
# mas largo = mas comodo para quien esta al fondo del salon.
NONCE_SEGUNDOS = 10

app = FastAPI(title="UniPresence")


# ---------------------------------------------------------------
# BASE DE DATOS
# ---------------------------------------------------------------

def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def iniciar_db():
    conn = conectar()
    c = conn.cursor()

    # registered_where guarda si el estudiante se registro antes de clase
    # ('pre') o dentro del salon ('aula'). Sirve para medir adopcion.
    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            student_code    TEXT NOT NULL UNIQUE,
            device_id       TEXT NOT NULL UNIQUE,
            registered_at   TEXT NOT NULL,
            registered_where TEXT NOT NULL DEFAULT 'pre'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name TEXT NOT NULL,
            started_at  TEXT NOT NULL,
            ended_at    TEXT,
            active      INTEGER NOT NULL DEFAULT 1
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS nonces (
            nonce      TEXT PRIMARY KEY,
            session_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_by    TEXT
        )
    """)

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
    return datetime.now(timezone.utc).isoformat()


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
  a.boton {{ display: block; background: #1a7f37; color: white; padding: 16px;
             text-decoration: none; border-radius: 8px; margin-top: 16px; font-size: 20px; }}
</style>
</head>
<body>{cuerpo}</body>
</html>
"""


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
    body { font-family: -apple-system, sans-serif; text-align: center; padding: 30px; }
    #qr { width: 380px; height: 380px; }
    #contador { font-size: 60px; font-weight: bold; margin: 12px; }
    button { font-size: 22px; padding: 14px 28px; cursor: pointer; margin: 6px; }
    .fila { display: flex; justify-content: center; gap: 40px; align-items: flex-start; }
    .panel { text-align: center; }
    h3 { color: #555; font-weight: normal; }
  </style>
</head>
<body>
  <h1>UniPresence</h1>

  <div id="antes">
    <button onclick="iniciar()">Iniciar asistencia</button>
    <p><a href="/qr-registro-pagina">Mostrar QR de registro</a></p>
  </div>

  <div id="durante" style="display:none">
    <div class="fila">
      <div class="panel">
        <h3>Escanea para marcar asistencia</h3>
        <img id="qr" src="">
      </div>
      <div class="panel">
        <h3>Registrados</h3>
        <div id="contador">0</div>
        <button onclick="exportar()">Descargar CSV</button>
        <hr>
        <h3>Agregar manualmente</h3>
        <input id="codigoManual" placeholder="Codigo de estudiante">
        <button onclick="manual()">Agregar</button>
        <p id="msgManual"></p>
      </div>
    </div>
  </div>

<script>
let sesion = null;

async function iniciar() {
  const r = await fetch('/session/start', { method: 'POST' });
  const datos = await r.json();
  sesion = datos.session_id;

  document.getElementById('antes').style.display = 'none';
  document.getElementById('durante').style.display = 'block';

  refrescarQR();
  refrescarContador();

  // El ?t= obliga al navegador a pedir la imagen de nuevo
  // en vez de reusar la que tiene en cache.
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

async function manual() {
  const codigo = document.getElementById('codigoManual').value.trim();
  if (!codigo) return;
  const cuerpo = new FormData();
  cuerpo.append('student_code', codigo);
  cuerpo.append('session_id', sesion);
  const r = await fetch('/manual', { method: 'POST', body: cuerpo });
  const datos = await r.json();
  document.getElementById('msgManual').textContent = datos.mensaje;
  document.getElementById('codigoManual').value = '';
  refrescarContador();
}

function exportar() {
  window.location = '/session/' + sesion + '/csv';
}
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def pantalla_profesor():
    return PAGINA_PROFESOR.replace("SEGUNDOS", str(NONCE_SEGUNDOS))


@app.get("/qr-registro-pagina", response_class=HTMLResponse)
def pagina_qr_registro():
    """Pantalla para proyectar al inicio de la primera clase."""
    return envolver("""
        <h1>Registro UniPresence</h1>
        <p>Escanea una sola vez. No marca asistencia.</p>
        <img src="/qr-registro" style="width:380px">
        <p><a href="/">Volver</a></p>
    """)


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


@app.get("/session/{session_id}/csv")
def exportar_csv(session_id: int):
    """Descarga la lista de asistencia. Lo primero que quiere ver un profesor."""
    conn = conectar()
    filas = conn.execute("""
        SELECT s.student_code, a.timestamp, a.method, s.registered_where
        FROM attendance a
        JOIN students s ON s.id = a.student_id
        WHERE a.session_id = ?
        ORDER BY a.timestamp
    """, (session_id,)).fetchall()
    conn.close()

    lineas = ["codigo_estudiante,hora,metodo,donde_se_registro"]
    for f in filas:
        lineas.append(f"{f['student_code']},{f['timestamp']},{f['method']},{f['registered_where']}")
    csv = "\n".join(lineas)

    return StreamingResponse(
        io.BytesIO(csv.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=asistencia_{session_id}.csv"},
    )


# ---------------------------------------------------------------
# QR DE ASISTENCIA (rotativo)
# ---------------------------------------------------------------

def png_de_qr(url: str) -> StreamingResponse:
    img = qrcode.make(url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png",
                             headers={"Cache-Control": "no-store"})


@app.get("/qr/{session_id}")
def generar_qr(session_id: int, request: Request):
    """
    Crea un nonce nuevo y devuelve el PNG del QR de asistencia.

    El QR no contiene un codigo: contiene una URL completa. Asi la camara
    nativa del celular la lee y ofrece abrirla, sin necesidad de programar
    un lector de QR ni pedir permiso de camara.
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

    base = str(request.base_url).rstrip("/")
    return png_de_qr(f"{base}/checkin?s={session_id}&n={nonce}")


@app.get("/qr-registro")
def generar_qr_registro(request: Request):
    """
    QR FIJO de registro. No rota, no expira, no lleva nonce.

    Es seguro que sea fijo porque registrarse no marca asistencia: solo
    amarra un telefono a un codigo de estudiante. La verificacion de
    presencia sigue dependiendo del QR rotativo.
    """
    base = str(request.base_url).rstrip("/")
    return png_de_qr(f"{base}/registro")


# ---------------------------------------------------------------
# REGISTRO (una sola vez, sin prisa)
# ---------------------------------------------------------------

@app.get("/registro", response_class=HTMLResponse)
def pagina_registro(request: Request):
    device_id = request.cookies.get("device_id")

    if device_id:
        conn = conectar()
        estudiante = conn.execute(
            "SELECT * FROM students WHERE device_id = ?", (device_id,)
        ).fetchone()
        conn.close()
        if estudiante:
            return envolver(
                f"<p class='ok'>Ya estas registrado</p>"
                f"<p>Codigo: {estudiante['student_code']}</p>"
                f"<p>En clase solo escanea el QR de asistencia.</p>"
            )

    html = envolver("""
        <h2>Registro</h2>
        <p>Escribe tu codigo de estudiante. Esto se hace una sola vez
        y no marca asistencia.</p>
        <form method="post" action="/registro">
          <input name="student_code" placeholder="Codigo de estudiante" required autofocus>
          <button type="submit">Registrar mi telefono</button>
        </form>
    """)

    respuesta = HTMLResponse(html)
    if not device_id:
        nuevo = secrets.token_hex(16)
        respuesta.set_cookie("device_id", nuevo, max_age=31536000,
                             httponly=True, samesite="lax")
    return respuesta


@app.post("/registro", response_class=HTMLResponse)
def hacer_registro(request: Request, student_code: str = Form(...)):
    device_id = request.cookies.get("device_id")
    if not device_id:
        return envolver("<p class='error'>No se pudo identificar el dispositivo. "
                        "Recarga la pagina e intenta de nuevo.</p>")

    # Si hay una sesion activa, asumimos que se esta registrando en el salon.
    conn = conectar()
    activa = conn.execute(
        "SELECT id FROM sessions WHERE active = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    donde = "aula" if activa else "pre"

    try:
        conn.execute(
            "INSERT INTO students (student_code, device_id, registered_at, registered_where) "
            "VALUES (?, ?, ?, ?)",
            (student_code.strip(), device_id, ahora(), donde),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return envolver(
            "<p class='error'>Ese codigo ya esta registrado en otro telefono, "
            "o este telefono ya pertenece a otro estudiante.</p>"
            "<p>Si es un error, avisale a la profesora.</p>"
        )

    conn.close()
    return envolver(
        "<p class='ok'>Telefono registrado</p>"
        "<p>En clase, apunta la camara al QR de la pantalla. "
        "No vas a tener que escribir nada.</p>"
    )


# ---------------------------------------------------------------
# CHECK-IN (rapido, sin escribir)
# ---------------------------------------------------------------

def validar_nonce(conn, session_id: int, nonce: str):
    fila = conn.execute(
        "SELECT * FROM nonces WHERE nonce = ? AND session_id = ?", (nonce, session_id)
    ).fetchone()

    if fila is None:
        return False, "Codigo invalido."

    if datetime.now(timezone.utc) > datetime.fromisoformat(fila["expires_at"]):
        return False, "Este codigo ya expiro. Escanea el QR actual de la pantalla."

    return True, ""


@app.get("/checkin", response_class=HTMLResponse)
def checkin(s: int, n: str, request: Request):
    device_id = request.cookies.get("device_id")

    conn = conectar()
    estudiante = None
    if device_id:
        estudiante = conn.execute(
            "SELECT * FROM students WHERE device_id = ?", (device_id,)
        ).fetchone()

    # Telefono sin registrar: no le pedimos el codigo aqui, porque escribirlo
    # toma mas de los 10 segundos que dura el nonce. Lo mandamos a registrarse.
    if estudiante is None:
        conn.close()
        return envolver("""
            <h2>Primero registrate</h2>
            <p>Este telefono todavia no esta asociado a ningun codigo
            de estudiante.</p>
            <a class="boton" href="/registro">Registrarme ahora</a>
            <p style="margin-top:20px;color:#666">Despues de registrarte,
            vuelve a escanear el QR de la pantalla.</p>
        """)

    valido, motivo = validar_nonce(conn, s, n)
    if not valido:
        conn.close()
        return envolver(f"<p class='error'>{motivo}</p>")

    mensaje = registrar_asistencia(conn, s, estudiante["id"], n, "qr")
    conn.close()
    return envolver(mensaje)


@app.post("/manual")
def agregar_manual(student_code: str = Form(...), session_id: int = Form(...)):
    """
    Anulacion manual del profesor: para el estudiante sin bateria, sin datos,
    o que dejo el telefono en el carro. Sin esto, cualquier director de
    departamento descarta el sistema en los primeros treinta segundos.
    """
    conn = conectar()
    estudiante = conn.execute(
        "SELECT * FROM students WHERE student_code = ?", (student_code.strip(),)
    ).fetchone()

    if estudiante is None:
        conn.close()
        return {"mensaje": "Ese codigo no esta registrado."}

    mensaje = registrar_asistencia(conn, session_id, estudiante["id"], None, "manual")
    conn.close()
    return {"mensaje": "Agregado." if "registrada" in mensaje else "Ya estaba."}


def registrar_asistencia(conn, session_id: int, student_id: int,
                         nonce: str | None, method: str) -> str:
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
