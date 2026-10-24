"""
load_test.py - what happens when a whole class taps Aceptar at the same time?

On October 21 the 20 check-ins came within 42 seconds. A class of 100 will
send many requests in the same second. This script checks three things
against a real server and a real Postgres, not the test client:

1. N students scan the same QR and tap Aceptar at once (first time, so each
   one types a code and accepts the policy). Every one must get a receipt,
   and there must be exactly N attendance rows: none lost, none doubled.
2. One student taps Aceptar twice at the same instant with the same ticket.
   Only one attendance row may exist.
3. Response times, so we know how long the slowest student waited.

Run it against a LOCAL server with an empty database, never production:

    DATABASE_URL="postgresql://...empty db..." uvicorn main:app --port 8000
    python3 analysis/load_test.py --url http://127.0.0.1:8000 --students 100

All names and codes are made up.
"""
import argparse
import re
import secrets
import statistics
import threading
import time

import httpx

# Made-up 9-digit codes, different on every run so no student already exists.
BASE = 800000000 + secrets.randbelow(90000) * 1000

IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")


def teacher_with_class(url, n):
    t = httpx.Client(base_url=url, follow_redirects=False, timeout=60)
    email = f"load-{secrets.token_hex(4)}@example.edu"
    r = t.post("/signup", data={"name": "Prof. Prueba", "email": email,
                                "password": "clave-de-prueba-1", "institution": "Test"})
    assert r.status_code == 303, r.text[:300]
    roster = "\n".join(f"Estudiante Prueba {i}\t{BASE + i}" for i in range(n))
    r = t.post("/course/new", data={"name": "Prueba de carga", "roster_text": roster})
    course = int(re.search(r"/course/(\d+)", r.headers["location"]).group(1))
    r = t.post(f"/course/{course}/start")
    session = int(re.search(r"/session/(\d+)/live", r.headers["location"]).group(1))
    return t, session


def qr_link(t, session):
    """Ask for a new QR, as the live screen does. The image is not decoded:
    the script reads the nonce it just created from the database."""
    r = t.get(f"/session/{session}/qr")
    assert r.status_code == 200


def run_all_at_once(fn, items):
    """Start one thread per item and release them all at the same instant."""
    barrier = threading.Barrier(len(items))
    results = [None] * len(items)

    def worker(i, item):
        barrier.wait()
        start = time.perf_counter()
        try:
            results[i] = (fn(item), time.perf_counter() - start)
        except Exception as exc:  # a failure is a result, not a crash
            results[i] = (f"error: {exc!r}"[:120], time.perf_counter() - start)

    threads = [threading.Thread(target=worker, args=(i, it)) for i, it in enumerate(items)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--students", type=int, default=100)
    p.add_argument("--nonce-from-db", required=True,
                   help="psql connection string of the SAME empty database the server uses")
    a = p.parse_args()

    import psycopg
    t, session = teacher_with_class(a.url, a.students)

    def current_nonce():
        qr_link(t, session)
        with psycopg.connect(a.nonce_from_db) as db:
            return db.execute("SELECT nonce FROM unipresence_v2.nonces WHERE session_id = %s "
                              "ORDER BY expires_at DESC LIMIT 1", (session,)).fetchone()[0]

    def attendance_rows():
        with psycopg.connect(a.nonce_from_db) as db:
            return db.execute("SELECT COUNT(*), COUNT(DISTINCT student_id) FROM "
                              "unipresence_v2.attendance WHERE session_id = %s",
                              (session,)).fetchone()

    # 1. Everyone scans the same QR at once, then everyone taps Aceptar at once.
    nonce = current_nonce()
    phones = [httpx.Client(base_url=a.url, headers={"user-agent": IPHONE}, timeout=60)
              for _ in range(a.students)]

    def scan(phone):
        r = phone.get(f"/checkin?s={session}&n={nonce}")
        return re.search(r'name="ticket" value="([^"]+)"', r.text).group(1)

    scans = run_all_at_once(scan, phones)
    tickets = [res for res, _ in scans]

    def accept(i):
        r = phones[i].post("/checkin/accept", data={
            "ticket": tickets[i], "carne": str(BASE + i), "acepto": "on"})
        return "receipt" if "Asistencia recibida" in r.text else f"HTTP {r.status_code}"

    accepts = run_all_at_once(accept, list(range(a.students)))
    ok = sum(1 for res, _ in accepts if res == "receipt")
    rows, distinct = attendance_rows()
    times = sorted(sec for _, sec in accepts)

    print(f"1. {a.students} students tap Aceptar at the same instant")
    print(f"   receipts shown: {ok} of {a.students}")
    print(f"   attendance rows: {rows} (distinct students: {distinct})")
    print(f"   response time: median {statistics.median(times):.2f} s, "
          f"slowest {times[-1]:.2f} s")
    errors = [res for res, _ in accepts if res != "receipt"]
    if errors:
        print(f"   failures: {errors[:5]}")

    # 2. One student double-taps: two requests with the same ticket at once.
    extra = httpx.Client(base_url=a.url, headers={"user-agent": IPHONE}, timeout=60)
    t2, session2 = teacher_with_class(a.url, 1)
    session = session2
    t = t2
    nonce = current_nonce()
    r = extra.get(f"/checkin?s={session}&n={nonce}")
    ticket = re.search(r'name="ticket" value="([^"]+)"', r.text).group(1)

    def tap(_):
        r = extra.post("/checkin/accept", data={
            "ticket": ticket, "carne": str(BASE), "acepto": "on"})
        return "receipt" if "Asistencia recibida" in r.text else "refused"

    taps = run_all_at_once(tap, [0, 1])
    rows, _ = attendance_rows()
    print("2. One student taps Aceptar twice at the same instant")
    print(f"   answers: {[res for res, _ in taps]}")
    print(f"   attendance rows: {rows}")


if __name__ == "__main__":
    main()
