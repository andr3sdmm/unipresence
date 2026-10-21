"""
relay_analysis.py - is there a QR lifetime that lets almost every present
student in and keeps most relays out?

Inputs are the anonymous "Tiempos (anónimo)" exports (timing.csv) from the
report page. Legitimate check-ins come from a real class; relay attempts come
from a separate session used only for the attack protocol.

    python3 analysis/relay_analysis.py --class analysis/data/tiempos_clase.csv \
                                       --relay analysis/data/tiempos_relevo.csv

qr_age_s is how old the QR was when the phone opened it. That is the number a
shorter lifetime would cut. accept_s (time to tap Aceptar) is reported too,
but it does not decide anything: the ticket gives the student 3 minutes.
"""
import argparse
import csv
import statistics
from pathlib import Path

CHART = Path(__file__).parent / "relay_histogram.png"


def ages(paths):
    out = []
    for path in paths or []:
        with open(path, encoding="utf-8") as f:
            out += [float(r["qr_age_s"]) for r in csv.DictReader(f) if r["qr_age_s"]]
    return sorted(out)


def describe(name, values):
    if not values:
        print(f"{name}: no data")
        return
    q = statistics.quantiles(values, n=20) if len(values) > 1 else [values[0]] * 19
    print(f"{name}: n={len(values)}  median={statistics.median(values):.1f}s  "
          f"p90={q[17]:.1f}s  p95={q[18]:.1f}s  max={values[-1]:.1f}s")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--class", dest="legit", nargs="+", required=True)
    p.add_argument("--relay", nargs="*")
    a = p.parse_args()
    legit, relay = ages(a.legit), ages(a.relay)
    describe("Present students", legit)
    describe("Relay attempts  ", relay)

    print("\nLifetime  present let in  relays let in")
    for life in (5, 8, 10, 12, 15, 20):
        ok = sum(v <= life for v in legit) / len(legit)
        bad = (sum(v <= life for v in relay) / len(relay)) if relay else float("nan")
        print(f"{life:>6}s  {ok:>14.0%}  {bad:>13.0%}")

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n(matplotlib not installed: no chart)")
        return
    bins = [x / 2 for x in range(0, 42)]
    plt.hist(legit, bins=bins, alpha=0.6, label="Present students")
    if relay:
        plt.hist(relay, bins=bins, alpha=0.6, label="Relay attempts")
    plt.xlabel("Age of the QR when scanned (s)")
    plt.ylabel("Check-ins")
    plt.legend()
    plt.savefig(CHART, dpi=150, bbox_inches="tight")
    print(f"\nChart: {CHART}")


if __name__ == "__main__":
    main()
