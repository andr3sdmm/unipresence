"""
UniPresence - Privacy-preserving physical presence verification for large classrooms
MVP day 2c: teacher authentication

WHAT CHANGED FROM 2b:

Two endpoints were open to anyone on the internet:

  /                 the teacher screen. Anyone with the link could start a
                    session, manually mark students present, and download the
                    CSV with every student name. Found while writing the
                    threat model.

  /qr/{session_id}  the attendance QR image. This one is worse. It returns a
                    freshly minted, currently valid nonce. A registered
                    student could request it from home, read the nonce and
                    check in without ever seeing the projector. Session ids
                    are small integers, so they are trivial to guess.
                    That breaks presence verification entirely.

Both now require a teacher session. The QR exists only on the projector again.

WHAT THIS DOES NOT SOLVE:
A single shared password means everyone who knows it has full access and
there is no record of who did what. The correct fix is institutional login
(each professor already has a university account). That is out of scope for
this prototype and is documented as an open risk.

HOW TO RUN:
    source venv/bin/activate
    TEACHER_PASSWORD=your-password uvicorn main:app --reload

The app refuses to serve teacher pages if TEACHER_PASSWORD is not set.
Failing closed is deliberate: a missing password must not silently mean
"no password".
"""

import csv
import hmac
import io
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import qrcode
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse

# ---------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------

DB_PATH = "unipresence.db"
ROSTER_PATH = "roster.csv"

# How long each attendance QR stays valid.
# Design decision: shorter makes relaying over WhatsApp harder; longer is
# easier for someone sitting at the back of a large lecture hall.
NONCE_SECONDS = 10

# Read from the environment, never hardcoded. This repository is public:
# a password written in the source is a password everyone has.
TEACHER_PASSWORD = os.environ.get("TEACHER_PASSWORD", "")

# Valid teacher session tokens, kept in memory.
# Restarting the server logs the teacher out, which is acceptable here.
# Tokens are random, so they reveal nothing about the password.
TEACHER_SESSIONS = set()

app = FastAPI(title="UniPresence")


# ---------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = connect()
    c = conn.cursor()

    # Students come from the course roster; they are not created on the fly.
    # device_id stays NULL until the person registers their phone.
    # SQLite allows several NULLs in a UNIQUE column, so this works.
    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            student_code     TEXT NOT NULL UNIQUE,
            name             TEXT NOT NULL,
            device_id        TEXT UNIQUE,
            registered_at    TEXT,
            registered_where TEXT
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


def load_roster():
    """
    Read roster.csv and insert any students that are missing.

    INSERT OR IGNORE means: if the code already exists, do nothing. The
    server can restart without wiping existing registrations, and new
    students can be appended to the file without breaking anything.
    """
    if not os.path.exists(ROSTER_PATH):
        print(f"WARNING: {ROSTER_PATH} not found. No course roster loaded.")
        return

    conn = connect()
    added = 0
    with open(ROSTER_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = (row.get("codigo") or "").strip()
            name = (row.get("nombre") or "").strip()
            if not code or not name:
                continue
            cur = conn.execute(
                "INSERT OR IGNORE INTO students (student_code, name) VALUES (?, ?)",
                (code, name),
            )
            added += cur.rowcount
    conn.commit()
    conn.close()
    print(f"Course roster loaded. New students: {added}")


@app.on_event("startup")
def on_startup():
    init_db()
    load_roster()
    if not TEACHER_PASSWORD:
        print("WARNING: TEACHER_PASSWORD is not set. Teacher pages are disabled.")


def now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------
# TEACHER AUTHENTICATION
#
# Student-facing pages stay open: a student has no account and must be able
# to register and check in with nothing but a phone. Everything the teacher
# touches is behind this gate.
# ---------------------------------------------------------------

def is_teacher(request: Request) -> bool:
    token = request.cookies.get("teacher_session")
    return bool(token) and token in TEACHER_SESSIONS


def wrap(body: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>UniPresence</title>
<style>
  body {{ font-family: -apple-system, sans-serif; padding: 40px 24px; text-align: center; }}
  .ok {{ color: #1a7f37; font-size: 28px; font-weight: bold; }}
  .error {{ color: #b91c1c; font-size: 24px; font-weight: bold; }}
  .nombre {{ font-size: 30px; font-weight: bold; margin: 20px 0; }}
  input, button {{ font-size: 20px; padding: 12px; width: 100%; box-sizing: border-box; margin: 8px 0; }}
  button {{ background: #1a7f37; color: white; border: none; border-radius: 8px; }}
  button.gris {{ background: #666; }}
  a.boton {{ display: block; background: #1a7f37; color: white; padding: 16px;
             text-decoration: none; border-radius: 8px; margin-top: 16px; font-size: 20px; }}
  form {{ max-width: 420px; margin: 0 auto; }}
</style>
</head>
<body>{body}</body>
</html>
"""


@app.get("/login", response_class=HTMLResponse)
def login_page(error: str = ""):
    if not TEACHER_PASSWORD:
        return wrap(
            "<p class='error'>Configuracion incompleta</p>"
            "<p>El servidor no tiene contrasena configurada.</p>"
        )
    aviso = "<p class='error'>Contrasena incorrecta</p>" if error else ""
    return wrap(f"""
        {aviso}
        <h2>UniPresence</h2>
        <p>Pantalla del profesor</p>
        <form method="post" action="/login">
          <input type="password" name="password" placeholder="Contrasena" required autofocus>
          <button type="submit">Entrar</button>
        </form>
    """)


@app.post("/login")
def do_login(password: str = Form(...)):
    # compare_digest instead of == : it takes the same time whether the
    # first character is wrong or only the last one, so an attacker cannot
    # guess the password one character at a time by measuring responses.
    if not TEACHER_PASSWORD or not hmac.compare_digest(password, TEACHER_PASSWORD):
        return RedirectResponse("/login?error=1", status_code=303)

    token = secrets.token_urlsafe(32)
    TEACHER_SESSIONS.add(token)

    response = RedirectResponse("/", status_code=303)
    response.set_cookie("teacher_session", token, max_age=43200,
                        httponly=True, samesite="lax")
    return response


@app.get("/logout")
def logout(request: Request):
    token = request.cookies.get("teacher_session")
    TEACHER_SESSIONS.discard(token)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("teacher_session")
    return response


# ---------------------------------------------------------------
# TEACHER SCREEN
# ---------------------------------------------------------------

TEACHER_PAGE = """
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
    .salir { position: absolute; top: 16px; right: 24px; font-size: 14px; color: #888; }
  </style>
</head>
<body>
  <a class="salir" href="/logout">Salir</a>
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
        <h3>Presentes</h3>
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

  // The ?t= forces the browser to fetch the image again instead of
  // reusing the cached one.
  setInterval(refrescarQR, SECONDS * 1000);
  setInterval(refrescarContador, 3000);
}

function refrescarQR() {
  document.getElementById('qr').src = '/qr/' + sesion + '?t=' + Date.now();
}

async function refrescarContador() {
  const r = await fetch('/session/' + sesion + '/count');
  const datos = await r.json();
  document.getElementById('contador').textContent = datos.count + ' de ' + datos.total;
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
def teacher_screen(request: Request):
    if not is_teacher(request):
        return RedirectResponse("/login", status_code=303)
    return HTMLResponse(TEACHER_PAGE.replace("SECONDS", str(NONCE_SECONDS)))


@app.get("/qr-registro-pagina", response_class=HTMLResponse)
def registration_qr_page(request: Request):
    """Screen to project at the start of the first class."""
    if not is_teacher(request):
        return RedirectResponse("/login", status_code=303)
    return wrap("""
        <h1>Registro UniPresence</h1>
        <p>Escanea una sola vez. Necesitas el codigo que te entregaron.</p>
        <p>Esto no marca asistencia.</p>
        <img src="/qr-registro" style="width:380px">
        <p><a href="/">Volver</a></p>
    """)


# ---------------------------------------------------------------
# SESSIONS  (teacher only)
# ---------------------------------------------------------------

@app.post("/session/start")
def start_session(request: Request, course_name: str = "Genetica"):
    if not is_teacher(request):
        return Response(status_code=401)

    conn = connect()
    c = conn.cursor()
    c.execute(
        "INSERT INTO sessions (course_name, started_at, active) VALUES (?, ?, 1)",
        (course_name, now()),
    )
    conn.commit()
    session_id = c.lastrowid
    conn.close()
    return {"session_id": session_id, "course_name": course_name}


@app.get("/session/{session_id}/count")
def session_count(session_id: int, request: Request):
    if not is_teacher(request):
        return Response(status_code=401)

    conn = connect()
    present = conn.execute(
        "SELECT COUNT(*) AS n FROM attendance WHERE session_id = ?", (session_id,)
    ).fetchone()["n"]
    total = conn.execute("SELECT COUNT(*) AS n FROM students").fetchone()["n"]
    conn.close()
    return {"count": present, "total": total}


@app.get("/session/{session_id}/csv")
def export_csv(session_id: int, request: Request):
    """Download the attendance list. The first thing a professor wants to see."""
    if not is_teacher(request):
        return Response(status_code=401)

    conn = connect()
    rows = conn.execute("""
        SELECT s.student_code, s.name, a.timestamp, a.method, s.registered_where
        FROM attendance a
        JOIN students s ON s.id = a.student_id
        WHERE a.session_id = ?
        ORDER BY s.name
    """, (session_id,)).fetchall()
    conn.close()

    lines = ["codigo,nombre,hora,metodo,donde_se_registro"]
    for r in rows:
        # Stored in UTC, shown in Bogota time. Storing UTC is correct;
        # displaying it is not.
        hora = datetime.fromisoformat(r["timestamp"]).astimezone(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d %H:%M")
        lines.append(
            f"{r['student_code']},{r['name']},{hora},{r['method']},{r['registered_where'] or ''}"
        )
    text = "\n".join(lines)

    return StreamingResponse(
        io.BytesIO(text.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=asistencia_{session_id}.csv"},
    )


# ---------------------------------------------------------------
# QR CODES
# ---------------------------------------------------------------

def qr_png(url: str) -> StreamingResponse:
    img = qrcode.make(url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png",
                             headers={"Cache-Control": "no-store"})


@app.get("/qr/{session_id}")
def attendance_qr(session_id: int, request: Request):
    """
    Mint a new nonce and return the attendance QR as a PNG.

    TEACHER ONLY, and this is the important part. This endpoint hands out a
    currently valid nonce. While it was public, a registered student could
    request it from anywhere and check in without being in the room, which
    defeats the entire point of the system. Session ids are small integers
    and easy to guess, so obscurity was no protection at all.

    Behind the gate, the QR only exists where the teacher projects it.

    Note on design: the QR carries a full URL rather than a bare code, so the
    phone's built-in camera opens it directly. No QR reader to write, no
    camera permission to request, and it works the same on iOS and Android.
    """
    if not is_teacher(request):
        return Response(status_code=401)

    nonce = secrets.token_hex(8)
    created = datetime.now(timezone.utc)
    expires = created + timedelta(seconds=NONCE_SECONDS)

    conn = connect()
    conn.execute(
        "INSERT INTO nonces (nonce, session_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (nonce, session_id, created.isoformat(), expires.isoformat()),
    )
    conn.commit()
    conn.close()

    base = str(request.base_url).rstrip("/")
    return qr_png(f"{base}/checkin?s={session_id}&n={nonce}")


@app.get("/qr-registro")
def registration_qr(request: Request):
    """
    Fixed registration QR. It does not rotate, expire or carry a nonce.

    Leaving this one public is safe: it encodes nothing but the address of
    the registration page. Without an assigned code, that page grants
    nothing.
    """
    base = str(request.base_url).rstrip("/")
    return qr_png(f"{base}/registro")


# ---------------------------------------------------------------
# REGISTRATION, IN TWO STEPS  (open to students)
#   step 1: type the assigned code
#   step 2: confirm the name is right
#
# Order matters: asking for the code FIRST avoids publishing the whole
# course roster on a page open to the internet.
# ---------------------------------------------------------------

CODE_FORM = """
    <h2>Registro</h2>
    <p>Escribe el codigo que te entregaron. Se hace una sola vez
    y no marca asistencia.</p>
    <form method="post" action="/registro">
      <input name="student_code" placeholder="Codigo" required autofocus autocapitalize="characters">
      <button type="submit">Continuar</button>
    </form>
"""


@app.get("/registro", response_class=HTMLResponse)
def registration_page(request: Request):
    device_id = request.cookies.get("device_id")

    if device_id:
        conn = connect()
        student = conn.execute(
            "SELECT * FROM students WHERE device_id = ?", (device_id,)
        ).fetchone()
        conn.close()
        if student:
            return wrap(
                f"<p class='ok'>Ya estas registrado</p>"
                f"<div class='nombre'>{student['name']}</div>"
                f"<p>En clase solo escanea el QR de asistencia.</p>"
            )

    response = HTMLResponse(wrap(CODE_FORM))
    if not device_id:
        new_id = secrets.token_hex(16)
        response.set_cookie("device_id", new_id, max_age=31536000,
                            httponly=True, samesite="lax")
    return response


@app.post("/registro", response_class=HTMLResponse)
def step1_check_code(request: Request, student_code: str = Form(...)):
    """Step 1: does the code exist and is it unclaimed? If so, show the name."""
    device_id = request.cookies.get("device_id")
    if not device_id:
        return wrap("<p class='error'>No se pudo identificar el dispositivo. "
                    "Recarga la pagina e intenta de nuevo.</p>")

    code = student_code.strip().upper()

    conn = connect()
    student = conn.execute(
        "SELECT * FROM students WHERE UPPER(student_code) = ?", (code,)
    ).fetchone()

    # This phone already belongs to someone else.
    already = conn.execute(
        "SELECT * FROM students WHERE device_id = ?", (device_id,)
    ).fetchone()
    conn.close()

    if already:
        return wrap(
            f"<p class='error'>Este telefono ya esta registrado</p>"
            f"<div class='nombre'>{already['name']}</div>"
            f"<p>Un telefono solo puede pertenecer a un estudiante.</p>"
        )

    if student is None:
        return wrap(
            "<p class='error'>Ese codigo no existe</p>"
            "<p>Revisa que este bien escrito. Si sigue sin funcionar, "
            "avisale a la profesora.</p>"
            + CODE_FORM
        )

    if student["device_id"]:
        # Someone already used that code. If it was not you, the code leaked
        # and that needs reporting. This is what makes the attack visible.
        return wrap(
            "<p class='error'>Ese codigo ya fue usado</p>"
            "<p>Si tu no lo registraste, avisale a la profesora de inmediato.</p>"
        )

    return wrap(f"""
        <h2>Confirma</h2>
        <div class="nombre">{student['name']}</div>
        <form method="post" action="/registro/confirmar">
          <input type="hidden" name="student_code" value="{student['student_code']}">
          <button type="submit">Si, soy yo</button>
        </form>
        <form method="get" action="/registro">
          <button type="submit" class="gris">No, volver</button>
        </form>
    """)


@app.post("/registro/confirmar", response_class=HTMLResponse)
def step2_confirm(request: Request, student_code: str = Form(...)):
    """Step 2: bind this phone to that student."""
    device_id = request.cookies.get("device_id")
    if not device_id:
        return wrap("<p class='error'>No se pudo identificar el dispositivo.</p>")

    code = student_code.strip().upper()

    conn = connect()
    active = conn.execute(
        "SELECT id FROM sessions WHERE active = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    where = "aula" if active else "pre"

    # WHERE device_id IS NULL is what protects against two people confirming
    # the same code at the same moment: only the first write succeeds.
    cur = conn.execute(
        "UPDATE students SET device_id = ?, registered_at = ?, registered_where = ? "
        "WHERE UPPER(student_code) = ? AND device_id IS NULL",
        (device_id, now(), where, code),
    )
    conn.commit()

    if cur.rowcount == 0:
        conn.close()
        return wrap("<p class='error'>Ese codigo ya fue usado</p>"
                    "<p>Avisale a la profesora.</p>")

    student = conn.execute(
        "SELECT * FROM students WHERE device_id = ?", (device_id,)
    ).fetchone()
    conn.close()

    return wrap(
        f"<p class='ok'>Telefono registrado</p>"
        f"<div class='nombre'>{student['name']}</div>"
        f"<p>En clase, apunta la camara al QR de la pantalla. "
        f"No vas a tener que escribir nada.</p>"
    )


# ---------------------------------------------------------------
# CHECK-IN  (open to students, fast, no typing)
# ---------------------------------------------------------------

def check_nonce(conn, session_id: int, nonce: str):
    row = conn.execute(
        "SELECT * FROM nonces WHERE nonce = ? AND session_id = ?", (nonce, session_id)
    ).fetchone()

    if row is None:
        return False, "Codigo invalido."

    if datetime.now(timezone.utc) > datetime.fromisoformat(row["expires_at"]):
        return False, "Este codigo ya expiro. Escanea el QR actual de la pantalla."

    return True, ""


@app.get("/checkin", response_class=HTMLResponse)
def checkin(s: int, n: str, request: Request):
    device_id = request.cookies.get("device_id")

    conn = connect()
    student = None
    if device_id:
        student = conn.execute(
            "SELECT * FROM students WHERE device_id = ?", (device_id,)
        ).fetchone()

    # Unregistered phone: we do not ask for the code here, because typing it
    # takes longer than the 10 seconds the nonce lasts. Send them to register.
    if student is None:
        conn.close()
        return wrap("""
            <h2>Primero registrate</h2>
            <p>Este telefono todavia no esta asociado a ningun estudiante.</p>
            <a class="boton" href="/registro">Registrarme ahora</a>
            <p style="margin-top:20px;color:#666">Necesitas el codigo que te
            entregaron. Despues de registrarte, vuelve a escanear el QR.</p>
        """)

    valid, reason = check_nonce(conn, s, n)
    if not valid:
        conn.close()
        return wrap(f"<p class='error'>{reason}</p>")

    message = record_attendance(conn, s, student["id"], n, "qr")
    conn.close()
    return wrap(f"{message}<div class='nombre'>{student['name']}</div>")


@app.post("/manual")
def manual_override(request: Request,
                    student_code: str = Form(...),
                    session_id: int = Form(...)):
    """
    Teacher override: for the student with a dead battery, no data, or who
    never registered a phone.

    With the roster loaded this works for anyone on the list, registered or
    not. Before the roster existed it did not.
    """
    if not is_teacher(request):
        return Response(status_code=401)

    conn = connect()
    student = conn.execute(
        "SELECT * FROM students WHERE UPPER(student_code) = ?",
        (student_code.strip().upper(),),
    ).fetchone()

    if student is None:
        conn.close()
        return {"mensaje": "Ese codigo no esta en la lista del curso."}

    message = record_attendance(conn, session_id, student["id"], None, "manual")
    conn.close()
    name = student["name"]
    return {"mensaje": f"{name}: agregado." if "registrada" in message
            else f"{name}: ya estaba."}


def record_attendance(conn, session_id: int, student_id: int,
                      nonce: str | None, method: str) -> str:
    try:
        conn.execute(
            "INSERT INTO attendance (session_id, student_id, timestamp, method, nonce_used) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, student_id, now(), method, nonce),
        )
        conn.commit()
        return "<p class='ok'>Asistencia registrada</p>"
    except sqlite3.IntegrityError:
        return "<p class='ok'>Ya estabas registrado en esta clase</p>"
