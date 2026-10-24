"""
checkin_timeline.py - how fast does a class check in with the QR?

Reads the anonymous check-in times of each pilot class (no names, no codes)
and draws how many students had checked in as time passed since the professor
opened the QR session.

    python3 analysis/checkin_timeline.py

The times come from the report of each class. I only kept the seconds since
the session was opened, so nobody can be identified from these files.
"""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
CLASSES = [
    # file, label, color
    ("dia08_tiempos_qr.csv", "Oct 21, group 3611", "#2a78d6"),
    ("dia09_tiempos_qr.csv", "Oct 22, group 3609", "#eb6834"),
]
CHART = HERE.parent / "media" / "dia09_01_qr_en_el_tiempo.png"


def load(name):
    with open(HERE / "data" / name, encoding="utf-8") as f:
        return [int(r["seconds_since_session_opened"]) for r in csv.DictReader(f)]


def mmss(s):
    return f"{s // 60}:{s % 60:02d}"


def main():
    fig, ax = plt.subplots(figsize=(8, 4.4), dpi=150)
    for name, label, color in CLASSES:
        s = sorted(load(name))
        print(f"{label}: {len(s)} check-ins, first at {mmss(s[0])}, last at "
              f"{mmss(s[-1])}, first to last {s[-1] - s[0]} s")
        # step curve: the count goes up by one at each check-in
        xs, ys = [0, s[0]], [0, 0]
        for i, t in enumerate(s, 1):
            xs += [t, t]
            ys += [i - 1, i]
        xs.append(180)
        ys.append(len(s))
        ax.plot(xs, ys, color=color, lw=2, label=label)
        ax.text(182, len(s), f"{label}\n{len(s)} in {s[-1] - s[0]} s",
                va="center", fontsize=9, color="#52514e")

    ax.set_xlim(0, 180)
    ax.set_ylim(0, 22)
    ax.set_yticks(range(0, 21, 5))
    ax.set_xticks(range(0, 181, 30))
    ax.set_xticklabels([mmss(t) for t in range(0, 181, 30)])
    ax.set_xlabel("Time since the professor opened the QR session (min:s)")
    ax.set_ylabel("Students checked in")
    ax.set_title("QR check-ins over time, first class of each group", loc="left")
    ax.legend(loc="upper left", frameon=False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", color="#e6e5e1", lw=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    CHART.parent.mkdir(exist_ok=True)
    fig.savefig(CHART, bbox_inches="tight")
    print(f"Chart: {CHART}")


if __name__ == "__main__":
    main()
