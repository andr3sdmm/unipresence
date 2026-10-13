"""
UniPresence - Privacy-preserving physical presence verification for large classrooms
Day 4: fixing what the real classroom pilot broke

WHAT CHANGED, AND WHY

On 22 September 2026 this ran in a real genetics lab: 22 students, the
professor operating it alone. 15 checked in. 7 could not.

The video the professor recorded shows what happened to them. A student
scans the attendance QR, is told "Primero registrate", types the code he
was given, and is told "Ese codigo ya fue usado". Both screens are the
system working exactly as written, and both are wrong about him. He HAD
registered, minutes earlier. The binding between a student and a phone
lives in a cookie, and a cookie lives inside one browser. He opened the
registration link inside WhatsApp, then scanned the QR with the camera,
which opens Safari. Two browsers, two cookie jars, one student the system
could no longer recognise.

So the diagnosis is not that students cheated or that the network failed.
It is that I built device binding on something narrower than a device.

Three changes follow from that:

1. A student who is not recognised at check-in can type their code right
   there and bind this browser, instead of being sent away. Re-binding is
   allowed on purpose: the alternative, which is what the pilot did, is to
   lock a present student out of their own attendance.

2. Re-binding is never silent. Every change is written to a device_changes
   table, counted on the teacher's screen while class runs, and marked in
   the CSV. The one-phone-one-student rule is now enforced by visibility
   rather than by refusal, which is the honest trade: a stolen code can
   move a registration, and the teacher sees that it moved.

3. The message that accused a student of theft is gone. It now offers the
   explanation that was true for all 7 of them, and keeps the warning for
   the case where it was not.

WHAT THIS DOES NOT FIX

The pilot also lost its stored data when Render's free instance went to
sleep. That needs a database that outlives the process, and it is the next
change, not this one.

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
LOCAL_TZ = ZoneInfo("America/Bogota")

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

    # Every time a roster code moves to a different browser or phone.
    #
    # This table is the price of letting students re-bind. Re-binding keeps
    # present students from being locked out, but it also means a leaked code
    # can be moved by whoever holds it. Writing every move down is what keeps
    # that visible instead of invisible.
    c.execute("""
        CREATE TABLE IF NOT EXISTS device_changes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            old_device TEXT,
            new_device TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            session_id INTEGER
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

    The CSV headers stay in Spanish because that file is maintained by the
    professor, not by the developer.

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


def to_local(iso_text: str | None) -> str:
    """UTC on disk, Bogota on screen. Storing UTC is correct; showing it is not."""
    if not iso_text:
        return ""
    return (datetime.fromisoformat(iso_text)
            .astimezone(LOCAL_TZ)
            .strftime("%Y-%m-%d %H:%M"))


# ---------------------------------------------------------------
# BINDING A CODE TO A BROWSER
#
# One function for all three paths that need it: registering for the first
# time, re-binding from the registration page, and re-binding in the middle
# of a check-in. They used to be three different pieces of logic, which is
# how the pilot ended up with two screens that contradicted each other.
# ---------------------------------------------------------------

def bind_device(conn, student, device_id: str, session_id: int | None):
    """
    Point a roster code at this browser.

    Returns (status, extra):
        "ok"      first binding
        "moved"   taken from another browser, logged in device_changes
        "same"    already this browser, nothing to do
        "taken"   this browser already belongs to another student (extra=row)
        "retry"   someone else changed it while we were working
    """
    owner = conn.execute(
        "SELECT * FROM students WHERE device_id = ?", (device_id,)
    ).fetchone()
    if owner and owner["id"] != student["id"]:
        # The one rule that does not bend: a phone is one student's phone.
        # Without this, two people share a handset and both get marked.
        return "taken", owner

    previous = student["device_id"]
    if previous == device_id:
        return "same", None

    active = conn.execute(
        "SELECT id FROM sessions WHERE active = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    where = "aula" if active else "pre"

    # `device_id IS ?` holds the old value, NULL included, so the write only
    # lands if nothing changed since we read the row. Two people confirming
    # the same code at the same instant still produces exactly one winner.
    cur = conn.execute(
        "UPDATE students SET device_id = ?, "
        "registered_at = COALESCE(registered_at, ?), "
        "registered_where = COALESCE(registered_where, ?) "
        "WHERE id = ? AND device_id IS ?",
        (device_id, now(), where, student["id"], previous),
    )
    if cur.rowcount == 0:
        conn.rollback()
        return "retry", None

    if previous:
        conn.execute(
            "INSERT INTO device_changes "
            "(student_id, old_device, new_device, changed_at, session_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (student["id"], previous, device_id, now(), session_id),
        )

    conn.commit()
    return ("moved" if previous else "ok"), None


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
    """Wrap a fragment in the shared student-facing page shell."""
    return f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>UniPresence</title>
<style>
  body {{ font-family: -apple-system, sans-serif; padding: 40px 24px; text-align: center; }}
  .ok {{ color: #1a7f37; font-size: 28px; font-weight: bold; }}
  .error {{ color: #b91c1c; font-size: 24px; font-weight: bold; }}
  .name {{ font-size: 30px; font-weight: bold; margin: 20px 0; }}
  input, button {{ font-size: 20px; padding: 12px; width: 100%; box-sizing: border-box; margin: 8px 0; }}
  button {{ background: #1a7f37; color: white; border: none; border-radius: 8px; }}
  button.grey {{ background: #666; }}
  a.link-button {{ display: block; background: #1a7f37; color: white; padding: 16px;
                   text-decoration: none; border-radius: 8px; margin-top: 16px; font-size: 20px; }}
  form {{ max-width: 420px; margin: 0 auto; }}
  table {{ margin: 0 auto; border-collapse: collapse; }}
  th, td {{ padding: 10px 16px; border-bottom: 1px solid #ddd; text-align: left; }}
  th {{ color: #555; font-weight: normal; }}
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
    warning = "<p class='error'>Contrasena incorrecta</p>" if error else ""
    return wrap(f"""
        {warning}
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
    #count { font-size: 60px; font-weight: bold; margin: 12px; }
    #finalCount { font-size: 60px; font-weight: bold; margin: 12px; }
    button { font-size: 22px; padding: 14px 28px; cursor: pointer; margin: 6px; }
    button.end { background: #b91c1c; color: white; border: none; border-radius: 8px; }
    .row { display: flex; justify-content: center; gap: 40px; align-items: flex-start; }
    .panel { text-align: center; }
    h3 { color: #555; font-weight: normal; }
    .logout { position: absolute; top: 16px; right: 24px; font-size: 14px; color: #888; }
    .warn { color: #b91c1c; max-width: 480px; margin: 16px auto; }
  </style>
</head>
<body>
  <a class="logout" href="/logout">Salir</a>
  <h1>UniPresence</h1>

  <div id="before">
    <button onclick="startSession()">Iniciar asistencia</button>
    <p><a href="/qr-register-page">Mostrar QR de registro</a></p>
    <p><a href="/sessions">Ver clases anteriores</a></p>
  </div>

  <div id="during" style="display:none">
    <div class="row">
      <div class="panel">
        <h3>Escanea para marcar asistencia</h3>
        <img id="qr" src="">
      </div>
      <div class="panel">
        <h3>Presentes</h3>
        <div id="count">0</div>
        <p id="changes"></p>
        <button onclick="downloadCsv()">Descargar CSV</button>
        <hr>
        <h3>Agregar manualmente</h3>
        <input id="manualCode" placeholder="Codigo de estudiante">
        <button onclick="addManual()">Agregar</button>
        <p id="manualMessage"></p>
        <hr>
        <button class="end" onclick="endSession()">Terminar asistencia</button>
      </div>
    </div>
  </div>

  <div id="finished" style="display:none">
    <h2>Asistencia terminada</h2>
    <div id="finalCount"></div>
    <p>estudiantes presentes</p>
    <p id="finalChanges" style="color:#b45309"></p>
    <button onclick="downloadCsv()">Descargar CSV</button>
    <p class="warn">Descarga el archivo ahora. En el plan gratuito de Render
    los datos se pierden si el servicio se reinicia.</p>
    <p><a href="/sessions">Ver clases anteriores</a> &middot; <a href="/">Volver al inicio</a></p>
  </div>

<script>
let sessionId = null;
let qrTimer = null;
let countTimer = null;

async function startSession() {
  const name = prompt('Nombre de la clase', 'Genetica');
  if (name === null) return;
  const response = await fetch('/session/start?course_name=' +
                               encodeURIComponent(name || 'Clase'),
                               { method: 'POST' });
  const data = await response.json();
  sessionId = data.session_id;

  document.getElementById('before').style.display = 'none';
  document.getElementById('during').style.display = 'block';

  refreshQR();
  refreshCount();

  // The ?t= forces the browser to fetch the image again instead of
  // reusing the cached one.
  qrTimer = setInterval(refreshQR, SECONDS * 1000);
  countTimer = setInterval(refreshCount, 3000);
}

async function endSession() {
  if (!confirm('Terminar la asistencia de esta clase?')) return;

  // Stop the timers first, so nothing keeps minting nonces for a
  // session that is already closed.
  clearInterval(qrTimer);
  clearInterval(countTimer);

  const response = await fetch('/session/' + sessionId + '/end', { method: 'POST' });
  const data = await response.json();

  document.getElementById('during').style.display = 'none';
  document.getElementById('finished').style.display = 'block';
  document.getElementById('finalCount').textContent = data.count + ' de ' + data.total;
  if (data.changes) {
    document.getElementById('finalChanges').textContent =
      data.changes + ' estudiante(s) cambiaron de dispositivo en esta clase';
  }
}

function refreshQR() {
  document.getElementById('qr').src = '/qr/' + sessionId + '?t=' + Date.now();
}

async function refreshCount() {
  const response = await fetch('/session/' + sessionId + '/count');
  const data = await response.json();
  document.getElementById('count').textContent = data.count + ' de ' + data.total;
  // Only shown when it happens. A zero on screen every class teaches the
  // teacher to ignore the line.
  document.getElementById('changes').textContent =
    data.changes ? 'Cambios de dispositivo: ' + data.changes : '';
}

async function addManual() {
  const code = document.getElementById('manualCode').value.trim();
  if (!code) return;
  const form = new FormData();
  form.append('student_code', code);
  form.append('session_id', sessionId);
  const response = await fetch('/manual', { method: 'POST', body: form });
  const data = await response.json();
  document.getElementById('manualMessage').textContent = data.message;
  document.getElementById('manualCode').value = '';
  refreshCount();
}

function downloadCsv() {
  window.location = '/session/' + sessionId + '/csv';
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


@app.get("/qr-register-page", response_class=HTMLResponse)
def registration_qr_page(request: Request):
    """Screen to project at the start of the first class."""
    if not is_teacher(request):
        return RedirectResponse("/login", status_code=303)
    return wrap("""
        <h1>Registro UniPresence</h1>
        <p>Escanea una sola vez. Necesitas el codigo que te entregaron.</p>
        <p>Esto no marca asistencia.</p>
        <img src="/qr-register" style="width:380px">
        <p><a href="/">Volver</a></p>
    """)


@app.get("/sessions", response_class=HTMLResponse)
def sessions_page(request: Request):
    """
    Every session ever held, with its download link.

    Without this page the attendance data only existed in the browser tab
    that started the session. Closing the tab after class made it
    unreachable, which on the day of a real experiment means losing it.
    """
    if not is_teacher(request):
        return RedirectResponse("/login", status_code=303)

    conn = connect()
    rows = conn.execute("""
        SELECT s.id, s.course_name, s.started_at, s.ended_at, s.active,
               (SELECT COUNT(*) FROM attendance a WHERE a.session_id = s.id) AS present
        FROM sessions s
        ORDER BY s.id DESC
    """).fetchall()
    conn.close()

    if not rows:
        return wrap("<h2>Clases anteriores</h2><p>Todavia no hay ninguna.</p>"
                    "<p><a href='/'>Volver</a></p>")

    body = ["<h2>Clases anteriores</h2><table>",
            "<tr><th>Clase</th><th>Inicio</th><th>Fin</th>"
            "<th>Presentes</th><th></th></tr>"]
    for r in rows:
        state = "en curso" if r["active"] else to_local(r["ended_at"])
        body.append(
            f"<tr><td>{r['course_name']} #{r['id']}</td>"
            f"<td>{to_local(r['started_at'])}</td>"
            f"<td>{state}</td>"
            f"<td>{r['present']}</td>"
            f"<td><a href='/session/{r['id']}/csv'>Descargar CSV</a></td></tr>"
        )
    body.append("</table><p><a href='/'>Volver</a></p>")
    return wrap("".join(body))


# ---------------------------------------------------------------
# SESSIONS  (teacher only)
# ---------------------------------------------------------------

@app.post("/session/start")
def start_session(request: Request, course_name: str = "Genetica"):
    if not is_teacher(request):
        return Response(status_code=401)

    conn = connect()

    # Close anything left open. If a previous class was never ended, every
    # later registration would be labelled as happening in the classroom.
    conn.execute(
        "UPDATE sessions SET active = 0, ended_at = ? WHERE active = 1",
        (now(),),
    )

    c = conn.cursor()
    c.execute(
        "INSERT INTO sessions (course_name, started_at, active) VALUES (?, ?, 1)",
        (course_name, now()),
    )
    conn.commit()
    session_id = c.lastrowid
    conn.close()
    return {"session_id": session_id, "course_name": course_name}


@app.post("/session/{session_id}/end")
def end_session(session_id: int, request: Request):
    if not is_teacher(request):
        return Response(status_code=401)

    conn = connect()
    conn.execute(
        "UPDATE sessions SET active = 0, ended_at = ? WHERE id = ? AND active = 1",
        (now(), session_id),
    )
    conn.commit()

    present = conn.execute(
        "SELECT COUNT(*) AS n FROM attendance WHERE session_id = ?", (session_id,)
    ).fetchone()["n"]
    total = conn.execute("SELECT COUNT(*) AS n FROM students").fetchone()["n"]
    changes = conn.execute(
        "SELECT COUNT(*) AS n FROM device_changes WHERE session_id = ?", (session_id,)
    ).fetchone()["n"]
    conn.close()
    return {"count": present, "total": total, "changes": changes}


@app.get("/session/{session_id}/count")
def session_count(session_id: int, request: Request):
    if not is_teacher(request):
        return Response(status_code=401)

    conn = connect()
    present = conn.execute(
        "SELECT COUNT(*) AS n FROM attendance WHERE session_id = ?", (session_id,)
    ).fetchone()["n"]
    total = conn.execute("SELECT COUNT(*) AS n FROM students").fetchone()["n"]
    # Device changes during THIS class. A couple are normal, a student who
    # changed phones. A sudden run of them during an exam is worth a look.
    changes = conn.execute(
        "SELECT COUNT(*) AS n FROM device_changes WHERE session_id = ?", (session_id,)
    ).fetchone()["n"]
    conn.close()
    return {"count": present, "total": total, "changes": changes}


@app.get("/session/{session_id}/csv")
def export_csv(session_id: int, request: Request):
    """
    Download the attendance list. The first thing a professor wants to see.

    The column headers stay in Spanish: this file is opened by the professor,
    not by a developer.
    """
    if not is_teacher(request):
        return Response(status_code=401)

    conn = connect()
    rows = conn.execute("""
        SELECT s.student_code, s.name, a.timestamp, a.method, s.registered_where,
               (SELECT COUNT(*) FROM device_changes d
                 WHERE d.student_id = s.id AND d.session_id = a.session_id) AS moved
        FROM attendance a
        JOIN students s ON s.id = a.student_id
        WHERE a.session_id = ?
        ORDER BY s.name
    """, (session_id,)).fetchall()
    conn.close()

    lines = ["codigo,nombre,hora,metodo,donde_se_registro,cambio_de_dispositivo"]
    for r in rows:
        lines.append(
            f"{r['student_code']},{r['name']},{to_local(r['timestamp'])},"
            f"{r['method']},{r['registered_where'] or ''},"
            f"{'si' if r['moved'] else 'no'}"
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


@app.get("/qr-register")
def registration_qr(request: Request):
    """
    Fixed registration QR. It does not rotate, expire or carry a nonce.

    Leaving this one public is safe: it encodes nothing but the address of
    the registration page. Without an assigned code, that page grants
    nothing.
    """
    base = str(request.base_url).rstrip("/")
    return qr_png(f"{base}/register")


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
    <p style="color:#666;font-size:15px">Hazlo en el mismo navegador con el
    que vas a escanear el QR en clase. Si abriste este enlace dentro de
    WhatsApp o Instagram, mejor cierra y escanea el QR con la camara.</p>
    <form method="post" action="/register">
      <input name="student_code" placeholder="Codigo" required autofocus autocapitalize="characters">
      <button type="submit">Continuar</button>
    </form>
"""


@app.get("/register", response_class=HTMLResponse)
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
                f"<div class='name'>{student['name']}</div>"
                f"<p>En clase solo escanea el QR de asistencia.</p>"
            )

    response = HTMLResponse(wrap(CODE_FORM))
    if not device_id:
        new_id = secrets.token_hex(16)
        response.set_cookie("device_id", new_id, max_age=31536000,
                            httponly=True, samesite="lax")
    return response


@app.post("/register", response_class=HTMLResponse)
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
            f"<div class='name'>{already['name']}</div>"
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
        # The pilot answered this case with "Ese codigo ya fue usado. Si tu
        # no lo registraste, avisale a la profesora de inmediato", which told
        # 7 students they were thieves of their own code. The common cause is
        # far more boring: they registered in another browser.
        #
        # So: offer the move, and keep the warning for the case where the
        # student really did not do it.
        return wrap(f"""
            <h2>Ese codigo ya esta vinculado</h2>
            <div class="name">{student['name']}</div>
            <p>Esta asociado a otro navegador o a otro telefono. Si fuiste tu,
            puedes pasarlo a este.</p>
            <form method="post" action="/register/relink">
              <input type="hidden" name="student_code" value="{student['student_code']}">
              <button type="submit">Si, soy yo, vincular aqui</button>
            </form>
            <p style="margin-top:20px;color:#666">El cambio le aparece a tu
            profesora. Si no eres tu, no sigas: avisale de inmediato.</p>
        """)

    return wrap(f"""
        <h2>Confirma</h2>
        <div class="name">{student['name']}</div>
        <form method="post" action="/register/confirm">
          <input type="hidden" name="student_code" value="{student['student_code']}">
          <button type="submit">Si, soy yo</button>
        </form>
        <form method="get" action="/register">
          <button type="submit" class="grey">No, volver</button>
        </form>
    """)


@app.post("/register/confirm", response_class=HTMLResponse)
def step2_confirm(request: Request, student_code: str = Form(...)):
    """Step 2: bind this browser to that student."""
    return _finish_binding(request, student_code, moving=False)


@app.post("/register/relink", response_class=HTMLResponse)
def relink(request: Request, student_code: str = Form(...)):
    """Move a code that is already bound somewhere else to this browser."""
    return _finish_binding(request, student_code, moving=True)


def _finish_binding(request: Request, student_code: str, moving: bool):
    device_id = request.cookies.get("device_id")
    if not device_id:
        return wrap("<p class='error'>No se pudo identificar este navegador</p>"
                    "<p>Recarga la pagina e intenta de nuevo.</p>")

    code = student_code.strip().upper()
    conn = connect()
    student = conn.execute(
        "SELECT * FROM students WHERE UPPER(student_code) = ?", (code,)
    ).fetchone()

    if student is None:
        conn.close()
        return wrap("<p class='error'>Ese codigo no existe</p>" + CODE_FORM)

    active = conn.execute(
        "SELECT id FROM sessions WHERE active = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    status, other = bind_device(conn, student, device_id,
                               active["id"] if active else None)
    conn.close()

    if status == "taken":
        return wrap(f"<p class='error'>Este telefono ya esta registrado</p>"
                    f"<div class='name'>{other['name']}</div>"
                    f"<p>Un telefono solo puede pertenecer a un estudiante.</p>")

    if status == "retry":
        return wrap("<p class='error'>Intentalo otra vez</p>"
                    "<p>Alguien uso ese codigo en el mismo instante.</p>")

    headline = "Telefono vinculado de nuevo" if status == "moved" else "Telefono registrado"
    note = ("<p style='color:#666'>Tu profesora vera que lo cambiaste de "
            "navegador.</p>" if status == "moved" else "")

    return wrap(
        f"<p class='ok'>{headline}</p>"
        f"<div class='name'>{student['name']}</div>"
        f"<p>En clase, apunta la camara al QR de la pantalla. "
        f"No vas a tener que escribir nada.</p>" + note
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

    # Not recognised. In the pilot this screen sent the student away to
    # register, and for 7 of them that was a dead end: they were already
    # registered, in another browser, so registering again told them their
    # own code was taken.
    #
    # Now the code box is right here. The nonce will usually expire while
    # they type, and that is fine: binding is the slow part and happens
    # once. The next scan is instant.
    if student is None:
        conn.close()
        response = HTMLResponse(wrap(f"""
            <h2>Vincula este telefono</h2>
            <p>Este navegador todavia no esta asociado a ningun estudiante.
            Puede que te hayas registrado desde otra app.</p>
            <form method="post" action="/checkin/link">
              <input type="hidden" name="s" value="{s}">
              <input type="hidden" name="n" value="{n}">
              <input name="student_code" placeholder="Tu codigo" required autofocus
                     autocapitalize="characters">
              <button type="submit">Vincular</button>
            </form>
            <p style="margin-top:20px;color:#666">Se hace una sola vez desde
            este navegador.</p>
        """))
        if not device_id:
            response.set_cookie("device_id", secrets.token_hex(16),
                                max_age=31536000, httponly=True, samesite="lax")
        return response

    # A closed session accepts nothing, even with a nonce that has not
    # expired yet.
    session_row = conn.execute(
        "SELECT active FROM sessions WHERE id = ?", (s,)
    ).fetchone()
    if session_row is None or not session_row["active"]:
        conn.close()
        return wrap("<p class='error'>Esta clase ya termino</p>"
                    "<p>Si crees que es un error, avisale a la profesora.</p>")

    valid, reason = check_nonce(conn, s, n)
    if not valid:
        conn.close()
        return wrap(f"<p class='error'>{reason}</p>")

    message = record_attendance(conn, s, student["id"], n, "qr")
    conn.close()
    return wrap(f"{message}<div class='name'>{student['name']}</div>")


@app.post("/checkin/link", response_class=HTMLResponse)
def checkin_link(request: Request,
                 s: int = Form(...),
                 n: str = Form(...),
                 student_code: str = Form(...)):
    """
    Bind this browser from inside a check-in, then try to mark attendance.

    This is the path the 7 students of the pilot needed and did not have.
    """
    device_id = request.cookies.get("device_id")
    if not device_id:
        return wrap("<p class='error'>No se pudo identificar este navegador</p>"
                    "<p>Recarga la pagina e intenta de nuevo.</p>")

    code = student_code.strip().upper()
    conn = connect()
    student = conn.execute(
        "SELECT * FROM students WHERE UPPER(student_code) = ?", (code,)
    ).fetchone()

    if student is None:
        conn.close()
        return wrap("<p class='error'>Ese codigo no existe</p>"
                    "<p>Revisa como esta escrito. Si sigue sin funcionar, "
                    "avisale a la profesora y te agrega a mano.</p>")

    status, other = bind_device(conn, student, device_id, s)

    if status == "taken":
        conn.close()
        return wrap(f"<p class='error'>Este telefono ya es de otro estudiante</p>"
                    f"<div class='name'>{other['name']}</div>"
                    f"<p>Un telefono solo puede marcar por una persona.</p>")

    if status == "retry":
        conn.close()
        return wrap("<p class='error'>Intentalo otra vez</p>"
                    "<p>Alguien uso ese codigo en el mismo instante.</p>")

    # The session may have closed, or the nonce expired while they typed.
    # Either way the binding above is already saved, so the next scan works.
    session_row = conn.execute(
        "SELECT active FROM sessions WHERE id = ?", (s,)
    ).fetchone()
    if session_row is None or not session_row["active"]:
        conn.close()
        return wrap(f"<p class='ok'>Telefono vinculado</p>"
                    f"<div class='name'>{student['name']}</div>"
                    f"<p>Esta clase ya termino. Avisale a la profesora para "
                    f"que te marque a mano.</p>")

    valid, _ = check_nonce(conn, s, n)
    if not valid:
        conn.close()
        return wrap(f"<p class='ok'>Telefono vinculado</p>"
                    f"<div class='name'>{student['name']}</div>"
                    f"<p>Ahora escanea otra vez el QR de la pantalla. "
                    f"Esta vez no tienes que escribir nada.</p>")

    message = record_attendance(conn, s, student["id"], n, "qr")
    conn.close()
    return wrap(f"{message}<div class='name'>{student['name']}</div>")


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
        return {"message": "Ese codigo no esta en la lista del curso."}

    result = record_attendance(conn, session_id, student["id"], None, "manual")
    conn.close()
    name = student["name"]
    return {"message": f"{name}: agregado." if "registrada" in result
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
