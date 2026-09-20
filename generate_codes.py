"""
generate_codes.py - build the course roster and the slips to hand out

WHY THIS EXISTS

The security of UniPresence depends on each student receiving a code that
nobody else knows. That step happens outside the software, and the threat
model names it as the weakest link: if the codes are read aloud or posted
to a class WhatsApp group, the whole scheme collapses.

This script makes the honest option the easy one. It produces one slip per
student, with their name and their own code, ready to print, cut and hand
out individually.

USAGE

    python3 generate_codes.py students.csv

`students.csv` is whatever the professor exports from the university system.
It can also be a plain .txt file with one name per line.

It writes two files:

    roster.csv                  loaded by the app at startup
    codes_to_print.html         open it, print it, cut it, hand it out

PRIVACY

roster.csv will contain real student names. It must never be committed to
a public repository. The script prints a reminder and checks .gitignore.
"""

import csv
import html
import os
import random
import sys

ROSTER_OUT = "roster.csv"
SLIPS_OUT = "codes_to_print.html"
CODE_LENGTH = 6

# No 0/O, no 1/I/L. Someone copying a code off a paper slip should not have
# to guess which character they are looking at.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def read_names(path: str) -> list[str]:
    """
    Accept a CSV exported from anywhere, or a plain list of names.

    For a CSV we look for a column called nombre, name, estudiante or
    apellidos; if none matches we fall back to the first column.
    """
    if not os.path.exists(path):
        sys.exit(f"No encontre el archivo: {path}")

    if path.lower().endswith(".txt"):
        with open(path, encoding="utf-8-sig") as f:
            return [line.strip() for line in f if line.strip()]

    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        # Excel in Spanish often exports with semicolons instead of commas.
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.reader(f, dialect))

    if not rows:
        sys.exit("El archivo esta vacio.")

    header = [h.strip().lower() for h in rows[0]]
    wanted = ("nombre", "nombres", "name", "estudiante", "apellidos")
    column = next((i for i, h in enumerate(header) if h in wanted), None)

    if column is None:
        print("AVISO: no encontre una columna de nombres. Uso la primera.")
        print(f"       Encabezados vistos: {rows[0]}")
        column = 0
        data_rows = rows
    else:
        print(f"Uso la columna '{rows[0][column]}'.")
        data_rows = rows[1:]

    names = []
    for row in data_rows:
        if len(row) > column and row[column].strip():
            names.append(row[column].strip())
    return names


def make_codes(count: int) -> list[str]:
    """
    Distinct random codes.

    random.SystemRandom reads the operating system's randomness, unlike
    plain random(), whose sequence can be reproduced from its seed. These
    codes are secrets, so they must not be predictable.
    """
    rng = random.SystemRandom()
    codes = set()
    while len(codes) < count:
        codes.add("".join(rng.choice(ALPHABET) for _ in range(CODE_LENGTH)))
    return sorted(codes)


SLIP_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Codigos UniPresence</title>
<style>
  body {{ font-family: -apple-system, Helvetica, sans-serif; margin: 0; padding: 12mm; }}
  h1 {{ font-size: 16pt; margin: 0 0 6mm 0; }}
  .note {{ font-size: 9pt; color: #555; margin-bottom: 8mm; }}
  .sheet {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0; }}
  .slip {{ border: 1px dashed #999; padding: 8mm 6mm; min-height: 42mm;
           box-sizing: border-box; page-break-inside: avoid; }}
  .who {{ font-size: 11pt; margin-bottom: 3mm; }}
  .code {{ font-size: 24pt; font-weight: bold; letter-spacing: 3px;
           font-family: "SF Mono", Menlo, monospace; }}
  .hint {{ font-size: 8pt; color: #666; margin-top: 3mm; line-height: 1.35; }}
  @media print {{ .note {{ display: none; }} h1 {{ display: none; }} }}
</style>
</head>
<body>
<h1>Codigos UniPresence &mdash; {course}</h1>
<p class="note">Imprime, corta por las lineas punteadas y entrega cada papelito
a su estudiante. No los leas en voz alta ni los mandes al grupo del curso:
si todos conocen los codigos de todos, el sistema deja de servir.</p>
<div class="sheet">
{slips}
</div>
</body>
</html>
"""

SLIP = """  <div class="slip">
    <div class="who">{name}</div>
    <div class="code">{code}</div>
    <div class="hint">Registra tu telefono una sola vez en<br>{url}<br>
    Este codigo es tuyo. No lo compartas.</div>
  </div>
"""


def main():
    if len(sys.argv) < 2:
        sys.exit("Uso: python3 generate_codes.py <archivo-con-nombres>")

    source = sys.argv[1]
    course = sys.argv[2] if len(sys.argv) > 2 else "Genetica"
    url = os.environ.get("UNIPRESENCE_URL",
                         "https://unipresence-3g8o.onrender.com/register")

    names = read_names(source)
    if not names:
        sys.exit("No encontre ningun nombre en ese archivo.")

    # A duplicate name is not an error, but it is worth flagging: two people
    # called the same thing will get different codes, and whoever hands out
    # the slips needs to know which is which.
    seen, repeated = set(), set()
    for n in names:
        key = n.lower()
        if key in seen:
            repeated.add(n)
        seen.add(key)

    codes = make_codes(len(names))

    if os.path.exists(ROSTER_OUT):
        answer = input(f"{ROSTER_OUT} ya existe y se va a sobrescribir. "
                       f"Los codigos actuales se pierden. Continuar? (s/n) ")
        if answer.strip().lower() not in ("s", "si", "y", "yes"):
            sys.exit("Cancelado. No se toco nada.")

    with open(ROSTER_OUT, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["codigo", "nombre"])
        for name, code in zip(names, codes):
            writer.writerow([code, name])

    slips = "".join(
        SLIP.format(name=html.escape(name), code=code, url=html.escape(url))
        for name, code in zip(names, codes)
    )
    with open(SLIPS_OUT, "w", encoding="utf-8") as f:
        f.write(SLIP_PAGE.format(course=html.escape(course), slips=slips))

    print()
    print(f"Estudiantes: {len(names)}")
    print(f"Escrito: {ROSTER_OUT}")
    print(f"Escrito: {SLIPS_OUT}  (abrelo y dale imprimir)")

    if repeated:
        print()
        print("OJO, nombres repetidos:", ", ".join(sorted(repeated)))
        print("Revisa cual papelito le toca a cual persona antes de repartir.")

    # The roster now holds real names. A public repository is the wrong
    # place for it.
    ignored = False
    if os.path.exists(".gitignore"):
        with open(".gitignore", encoding="utf-8") as f:
            ignored = any(line.strip() == ROSTER_OUT for line in f)

    if not ignored:
        print()
        print("=" * 60)
        print("IMPORTANTE")
        print(f"{ROSTER_OUT} tiene nombres reales de estudiantes y tu")
        print("repositorio es publico. Antes del proximo commit:")
        print()
        print(f'    echo "{ROSTER_OUT}" >> .gitignore')
        print(f"    git rm --cached {ROSTER_OUT}")
        print()
        print("Y guarda roster.example.csv con los nombres inventados,")
        print("para que el repo siga teniendo un ejemplo que funcione.")
        print("=" * 60)


if __name__ == "__main__":
    main()
