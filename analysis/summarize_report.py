"""
summarize_report.py - turn one exported UniPresence report into the numbers
that go into docs/results.md, and an anonymized copy safe for the repository.

    python3 analysis/summarize_report.py asistencia_genetica_2026-10-20.csv

The anonymized copy drops Carné, Nombre and Comprobante. Only that copy is
committed; the original export stays on the professor's computer.
"""
import csv
import sys
from collections import Counter
from pathlib import Path

DROP = {"Carné", "Nombre", "Comprobante"}


def main(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    # A check-in the professor rejected is kept in the report but is not presence.
    present = [r for r in rows if r["Estado"] not in ("Ausente", "Rechazado")]
    rejected = [r for r in rows if r["Estado"] == "Rechazado"]
    by_qr = [r for r in present if r["Método"] == "QR"]
    print(f"Students in the report: {len(rows)}")
    print(f"Present: {len(present)}  (by QR: {len(by_qr)}, by hand: {len(present) - len(by_qr)})")
    print(f"Rejected by the professor: {len(rejected)}")
    if present:
        print(f"Checked in without help: {len(by_qr) / len(present):.0%}")

    times = sorted(r["Hora"] for r in by_qr if r["Hora"])
    if times:
        print(f"First QR check-in: {times[0]}   last: {times[-1]}")

    for column in ("Estado", "Navegador", "Sistema", "App de origen", "Cambio de dispositivo"):
        counts = Counter(r[column] or "(vacío)" for r in present)
        print(f"{column}: " + ", ".join(f"{k} {v}" for k, v in counts.most_common()))

    flagged = [r for r in rows if r["Observación"]]
    print(f"Rows with an observation: {len(flagged)}")

    out = Path("analysis/data") / (Path(path).stem + "_anon.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    keep = [c for c in rows[0].keys() if c not in DROP] if rows else []
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Estudiante"] + keep)
        writer.writeheader()
        for i, r in enumerate(rows, start=1):
            writer.writerow({"Estudiante": f"E{i:02d}", **{c: r[c] for c in keep}})
    print(f"Anonymized copy: {out}")


if __name__ == "__main__":
    main(sys.argv[1])
