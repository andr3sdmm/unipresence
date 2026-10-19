"""
Tests for UniPresence v2.

They run against a real Postgres database, because the behaviour that matters
most (two people racing for one carne, one transaction per request) is the
database's behaviour. Point TEST_DATABASE_URL at an empty database you can wipe:

    TEST_DATABASE_URL="postgresql://..." pytest -q

Every test run drops and recreates the unipresence_v2 schema in that database.
Never point it at the production database.
"""

import csv
import io
import os
import re

import psycopg
import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")
if not TEST_DB:
    pytest.skip("TEST_DATABASE_URL is not set", allow_module_level=True)
os.environ["DATABASE_URL"] = TEST_DB

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
ANDROID_CHROME = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36")
INSTAGRAM = IPHONE + " Instagram 330.0.0"


@pytest.fixture(autouse=True)
def fresh_schema():
    with psycopg.connect(TEST_DB, autocommit=True) as conn:
        conn.execute(f"DROP SCHEMA IF EXISTS {main.SCHEMA} CASCADE")
    main.init_db()
    yield


def sql(query, params=()):
    with psycopg.connect(TEST_DB, autocommit=True) as conn:
        conn.execute(f"SET search_path TO {main.SCHEMA}")
        cur = conn.execute(query, params)
        return cur.fetchall() if cur.description else None


def teacher(email="prof@uni.edu", name="Prof. Rojas"):
    c = TestClient(main.app)
    r = c.post("/signup", data={"name": name, "email": email, "password": "clave-segura-1",
                                "institution": "Universidad del Norte"}, follow_redirects=False)
    assert r.status_code == 303
    return c


def student(ua=IPHONE):
    return TestClient(main.app, headers={"user-agent": ua})


def create_course(t, name="Genética G1", roster=""):
    r = t.post("/course/new", data={"name": name, "roster_text": roster}, follow_redirects=False)
    return int(re.search(r"/course/(\d+)", r.headers["location"]).group(1))


def start(t, course_id):
    r = t.post(f"/course/{course_id}/start", follow_redirects=False)
    return int(re.search(r"/session/(\d+)/live", r.headers["location"]).group(1))


def fresh_nonce(t, sid):
    assert t.get(f"/session/{sid}/qr").status_code == 200
    return sql("SELECT nonce FROM nonces WHERE session_id = %s ORDER BY expires_at DESC LIMIT 1",
               (sid,))[0][0]


def ticket_of(page):
    return re.search(r'name="ticket" value="([^"]+)"', page).group(1)


def scan(s, t, sid):
    return s.get(f"/checkin?s={sid}&n={fresh_nonce(t, sid)}")


ROSTER = "María Fernanda Rojas\t2021104567\nPérez, Juan\t2021104568\nValentina Castro\t2021104569"


def test_roster_paste_keeps_names_with_commas():
    t = teacher()
    cid = create_course(t, roster=ROSTER)
    names = {r[0] for r in sql("SELECT name FROM students")}
    assert names == {"María Fernanda Rojas", "Pérez, Juan", "Valentina Castro"}
    assert sql("SELECT has_roster FROM courses WHERE id = %s", (cid,))[0][0] is True


def test_first_checkin_then_one_tap():
    t = teacher()
    sid = start(t, create_course(t, roster=ROSTER))
    s = student()
    page = scan(s, t, sid).text
    assert "Primera vez en este celular" in page
    r = s.post("/checkin/accept", data={"ticket": ticket_of(page), "carne": "2021104567"})
    assert "Asistencia recibida" in r.text and "María Fernanda Rojas" in r.text
    assert re.search(r"C\d+-\d{4}-[A-Z2-9]{4}", r.text)

    # Next class: one tap, no typing.
    sid2 = start(t, sql("SELECT course_id FROM sessions WHERE id = %s", (sid,))[0][0])
    page2 = scan(s, t, sid2).text
    assert "Aceptar" in page2 and "Primera vez" not in page2 and "María Fernanda Rojas" in page2
    assert "Asistencia recibida" in s.post("/checkin/accept", data={"ticket": ticket_of(page2)}).text


def test_second_scan_same_class_shows_existing_receipt():
    t = teacher()
    sid = start(t, create_course(t, roster=ROSTER))
    s = student()
    s.post("/checkin/accept", data={"ticket": ticket_of(scan(s, t, sid).text), "carne": "2021104567"})
    assert "Ya tenías asistencia" in scan(s, t, sid).text
    assert sql("SELECT COUNT(*) FROM attendance")[0][0] == 1


def test_expired_qr_is_rejected_and_counted():
    t = teacher()
    sid = start(t, create_course(t, roster=ROSTER))
    n = fresh_nonce(t, sid)
    sql("UPDATE nonces SET expires_at = now() - interval '1 second' WHERE nonce = %s", (n,))
    assert "Vuelve a escanear" in student().get(f"/checkin?s={sid}&n={n}").text
    assert sql("SELECT COUNT(*) FROM events WHERE kind = 'qr_vencido'")[0][0] == 1


def test_ticket_cannot_be_used_twice():
    t = teacher()
    sid = start(t, create_course(t, roster=ROSTER))
    s = student()
    tk = ticket_of(scan(s, t, sid).text)
    s.post("/checkin/accept", data={"ticket": tk, "carne": "2021104567"})
    assert "ya se usó" in s.post("/checkin/accept", data={"ticket": tk, "carne": "2021104567"}).text


def test_carne_not_on_list_is_refused_and_flagged():
    t = teacher()
    sid = start(t, create_course(t, roster=ROSTER))
    s = student()
    r = s.post("/checkin/accept", data={"ticket": ticket_of(scan(s, t, sid).text), "carne": "9999999"})
    assert "no está en la lista" in r.text
    assert sql("SELECT COUNT(*) FROM attendance")[0][0] == 0
    assert sql("SELECT review FROM events WHERE kind = 'carne_no_en_lista'")[0][0] is True


def test_known_browser_cannot_mark_for_a_friend():
    t = teacher()
    sid = start(t, create_course(t, roster=ROSTER))
    s = student()
    s.post("/checkin/accept", data={"ticket": ticket_of(scan(s, t, sid).text), "carne": "2021104567"})
    sid2 = start(t, sql("SELECT course_id FROM sessions WHERE id = %s", (sid,))[0][0])
    # The form for a known browser has no carne field; a crafted one is ignored.
    r = s.post("/checkin/accept", data={"ticket": ticket_of(scan(s, t, sid2).text),
                                        "carne": "2021104568"})
    assert "María Fernanda Rojas" in r.text
    marked = {row[0] for row in sql("SELECT st.carne FROM attendance a JOIN students st "
                                    "ON st.id = a.student_id WHERE a.session_id = %s", (sid2,))}
    assert marked == {"2021104567"}


def test_private_window_with_friends_carne_goes_to_review():
    """Attack 4: a student in the room opens a private window and types a classmate's carne."""
    t = teacher()
    sid = start(t, create_course(t, roster=ROSTER))
    friend = student(IPHONE)
    friend.post("/checkin/accept", data={"ticket": ticket_of(scan(friend, t, sid).text),
                                         "carne": "2021104568"})
    sid2 = start(t, sql("SELECT course_id FROM sessions WHERE id = %s", (sid,))[0][0])
    incognito = student(ANDROID_CHROME)
    r = incognito.post("/checkin/accept", data={"ticket": ticket_of(scan(incognito, t, sid2).text),
                                                "carne": "2021104568"})
    assert "Asistencia recibida" in r.text  # not blocked...
    state = t.get(f"/session/{sid2}/state").json()
    labels = [a["label"] for a in state["alerts"]]
    assert main.EVENT_LABELS["cambio_dispositivo"] in labels  # ...but visible
    assert "Chrome" in state["alerts"][0]["detail"]


def test_class_without_list_builds_itself_and_needs_approval():
    t = teacher()
    cid = create_course(t, roster="")
    sid = start(t, cid)
    s = student()
    page = scan(s, t, sid).text
    assert 'name="nombre"' in page
    r = s.post("/checkin/accept", data={"ticket": ticket_of(page), "carne": "2021200001",
                                        "nombre": "Santiago Herrera"})
    assert "Asistencia recibida" in r.text
    assert sql("SELECT status FROM enrollments")[0][0] == "pendiente"
    t.post(f"/course/{cid}/approve", data={"all": "1"})
    assert sql("SELECT status FROM enrollments")[0][0] == "aprobado"


def test_burst_of_new_links_is_flagged():
    t = teacher()
    sid = start(t, create_course(t, roster=""))
    for i in range(3):
        s = student(ANDROID_CHROME)
        s.post("/checkin/accept", data={"ticket": ticket_of(scan(s, t, sid).text),
                                        "carne": f"20213000{i}", "nombre": f"Estudiante {i}"})
    assert sql("SELECT COUNT(*) FROM events WHERE kind = 'rafaga' AND review")[0][0] == 1


def test_link_opened_inside_instagram_is_flagged():
    t = teacher()
    sid = start(t, create_course(t, roster=ROSTER))
    s = student(INSTAGRAM)
    s.post("/checkin/accept", data={"ticket": ticket_of(scan(s, t, sid).text), "carne": "2021104569"})
    assert sql("SELECT detail FROM events WHERE kind = 'desde_app'")[0][0] == "Instagram"
    assert sql("SELECT in_app, browser, os FROM attendance")[0] == ("Instagram", "Safari", "iOS")


def test_closed_class_accepts_nothing():
    t = teacher()
    sid = start(t, create_course(t, roster=ROSTER))
    s = student()
    page = scan(s, t, sid).text
    t.post(f"/session/{sid}/end", follow_redirects=False)
    r = s.post("/checkin/accept", data={"ticket": ticket_of(page), "carne": "2021104567"})
    assert "Vuelve a escanear" in r.text or "ya terminó" in r.text
    assert sql("SELECT COUNT(*) FROM attendance")[0][0] == 0


def test_manual_mark_and_reports():
    t = teacher()
    cid = create_course(t, roster=ROSTER)
    sid = start(t, cid)
    s = student()
    s.post("/checkin/accept", data={"ticket": ticket_of(scan(s, t, sid).text), "carne": "2021104567"})
    juan = sql("SELECT id FROM students WHERE carne = '2021104568'")[0][0]
    assert "marcado a mano" in t.post(f"/session/{sid}/manual", data={"student_id": juan}).json()["message"]
    t.post(f"/session/{sid}/end", follow_redirects=False)

    page = t.get(f"/session/{sid}/report").text
    assert "2 de 3" in page and "Firma del profesor" in page

    rows = list(csv.reader(io.StringIO(t.get(f"/session/{sid}/export.csv").content.decode("utf-8-sig"))))
    header, data = rows[0], rows[1:]
    assert len(header) == len(main.REPORT_COLUMNS)
    by_name = {r[1]: dict(zip(header, r)) for r in data}
    assert by_name["Pérez, Juan"]["Estado"] == "Manual"      # the comma did not shift columns
    assert by_name["Valentina Castro"]["Estado"] == "Ausente"
    assert by_name["María Fernanda Rojas"]["Celular"] == "Celular #1"
    device = sql("SELECT device_id FROM students WHERE carne = '2021104567'")[0][0]
    assert device not in t.get(f"/session/{sid}/export.csv").text  # never the cookie value

    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(t.get(f"/session/{sid}/export.xlsx").content))
    assert wb.active.max_row == 4


def test_teachers_cannot_see_each_others_classes():
    a = teacher("a@uni.edu", "Prof. A")
    cid = create_course(a, roster=ROSTER)
    b = teacher("b@uni.edu", "Prof. B")
    r = b.get(f"/course/{cid}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"
    sid = start(a, cid)
    assert b.get(f"/session/{sid}/qr", follow_redirects=False).status_code == 303
    assert b.get(f"/session/{sid}/export.csv", follow_redirects=False).status_code == 303


def test_student_typed_name_is_escaped_on_teacher_pages():
    t = teacher()
    cid = create_course(t, roster="")
    sid = start(t, cid)
    s = student()
    s.post("/checkin/accept", data={"ticket": ticket_of(scan(s, t, sid).text),
                                    "carne": "2021400001", "nombre": "<script>alert(1)</script>"})
    page = t.get(f"/course/{cid}").text
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_qr_is_teacher_only():
    t = teacher()
    sid = start(t, create_course(t, roster=ROSTER))
    assert student().get(f"/session/{sid}/qr", follow_redirects=False).status_code == 303


def test_roster_from_excel_and_semicolon_csv():
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.append(["Código", "Apellidos y nombres"])
    wb.active.append([2021104567, "Rojas María"])
    wb.active.append([2021104568.0, "Pérez Juan"])
    buf = io.BytesIO(); wb.save(buf)
    t = teacher()
    r = t.post("/course/new", data={"name": "Excel"},
               files={"roster_file": ("lista.xlsx", buf.getvalue())}, follow_redirects=False)
    assert r.status_code == 303
    assert sorted(x[0] for x in sql("SELECT carne FROM students")) == ["2021104567", "2021104568"]
    t.post("/course/new", data={"name": "CSV"},
           files={"roster_file": ("lista.csv", "nombre;carné\nAna Gómez;2021104570\n".encode("latin-1"))})
    assert sql("SELECT name FROM students WHERE carne = '2021104570'")[0][0] == "Ana Gómez"


def test_brightspace_export_with_several_groups():
    """The Uninorte grade export: OrgDefinedId, Last Name, First Name, Email, Sections."""
    import json
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["OrgDefinedId", "Last Name", "First Name", "Email", "Sections"])
    ws.append(["170001", "GOMEZ DIAZ", "ANA", "ana@uni.edu", "FUNDAMENTOS MD2026303604"])
    ws.append(["170002", "PEREZ ROA", "LUIS", "luis@uni.edu", "FUNDAMENTOS MD2026303604"])
    ws.append(["170003", "MARIN SOTO", "EVA", "eva@uni.edu", "FUNDAMENTOS MD2026303605"])
    buf = io.BytesIO(); wb.save(buf)
    t = teacher()
    r = t.post("/course/new", data={"name": "Fundamentos"},
               files={"roster_file": ("export.xlsx", buf.getvalue())})
    assert "¿Qué grupos son tuyos?" in r.text and "2 grupos" in r.text and "Grupo 3604" in r.text
    payload = re.search(r'name="payload" value="([^"]+)"', r.text).group(1)
    import html as _html
    payload = _html.unescape(payload)
    assert "@" not in payload  # emails never travel further
    t.post("/course/new/groups", data={"name": "Fundamentos", "payload": payload,
                                       "sections": ["FUNDAMENTOS MD2026303604"]})
    names = sorted(x[0] for x in sql("SELECT name FROM students"))
    assert names == ["Ana Gomez Diaz", "Luis Perez Roa"]



def test_choose_todays_groups_when_class_has_several():
    """One list, several groups: 7:00 with group 3614, 9:00 with group 3615."""
    t = teacher()
    roster = ("OrgDefinedId,Last Name,First Name,Sections\n"
              "180001,ROJAS,ANA,SISTEMA NERVIOSO2026303614\n"
              "180002,DIAZ,LUIS,SISTEMA NERVIOSO2026303614\n"
              "180003,SOTO,EVA,SISTEMA NERVIOSO2026303615\n")
    r = t.post("/course/new", data={"name": "Sistema Nervioso", "roster_text": roster})
    import html as _html
    payload = _html.unescape(re.search(r'name="payload" value="([^"]+)"', r.text).group(1))
    r = t.post("/course/new/groups", follow_redirects=False,
               data={"name": "Sistema Nervioso", "payload": payload,
                     "sections": ["SISTEMA NERVIOSO2026303614", "SISTEMA NERVIOSO2026303615"]})
    cid = int(re.search(r"/course/(\d+)", r.headers["location"]).group(1))
    assert sql("SELECT COUNT(*) FROM enrollments")[0][0] == 3

    picker = t.post(f"/course/{cid}/start")
    assert "¿Qué grupos están en el salón ahora?" in picker.text and "Grupo 3615" in picker.text
    r = t.post(f"/course/{cid}/start", follow_redirects=False,
               data={"chosen": "1", "sections": ["SISTEMA NERVIOSO2026303614"]})
    sid = int(re.search(r"/session/(\d+)/live", r.headers["location"]).group(1))

    state = t.get(f"/session/{sid}/state").json()
    assert state["total"] == 2
    assert sorted(a["name"] for a in state["absent"]) == ["Ana Rojas", "Luis Diaz"]

    # Eva, from the other group, shows up anyway: she is marked and flagged in the report.
    s = student()
    s.post("/checkin/accept", data={"ticket": ticket_of(scan(s, t, sid).text), "carne": "180003"})
    rows = list(csv.reader(io.StringIO(t.get(f"/session/{sid}/export.csv").content.decode("utf-8-sig"))))
    by_name = {r[1]: dict(zip(rows[0], r)) for r in rows[1:]}
    assert set(by_name) == {"Ana Rojas", "Luis Diaz", "Eva Soto"}
    assert "otro grupo" in by_name["Eva Soto"]["Observación"]
    assert by_name["Ana Rojas"]["Grupo"] == "Grupo 3614"
