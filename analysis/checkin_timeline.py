"""
checkin_timeline.py - how fast does a class check in with the QR?

Reads the anonymous check-in times of each pilot class (no names, no codes)
and draws how many students had checked in as time passed since the professor
opened the QR session. It makes two charts:

1. every class where it was everyone's first time with the app;
2. the same two large classes on their first and second day, when most
   students only had to tap Aceptar.

    python3 analysis/checkin_timeline.py

The times come from the report of each class. I only kept the seconds since
the session was opened, so nobody can be identified from these files.
"""
import csv
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
MEDIA = HERE.parent / "media"

FIRST_TIME = [
    # file, label, color, dashed
    ("dia08_tiempos_qr.csv", "Oct 21, group 3611", "#2a78d6", False),
    ("dia09_tiempos_qr.csv", "Oct 22, group 3609", "#eb6834", False),
    ("dia11_tiempos_grupos_3617_3619.csv", "Oct 26, groups 3617-3619", "#1baf7a", False),
    ("dia11_tiempos_grupos_3614_3616.csv", "Oct 26, groups 3614-3616", "#6250d6", False),
]
SECOND_DAY = [
    ("dia11_tiempos_grupos_3617_3619.csv", "Groups 3617-3619, Oct 26 (1st day)", "#1baf7a", True),
    ("dia12_tiempos_grupos_3617_3619.csv", "Groups 3617-3619, Oct 27 (2nd day)", "#1baf7a", False),
    ("dia11_tiempos_grupos_3614_3616.csv", "Groups 3614-3616, Oct 26 (1st day)", "#6250d6", True),
    ("dia12_tiempos_grupos_3614_3616.csv", "Groups 3614-3616, Oct 27 (2nd day)", "#6250d6", False),
]


def load(name):
    with open(HERE / "data" / name, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # The first files were made by hand from the report; since October 26
    # the app's anonymous export has the same number under another name.
    times = [round(float(r.get("seconds_since_session_opened") or r["seconds_since_start"]))
             for r in rows]
    one_tap = [float(r["accept_s"]) for r in rows if r.get("first_link") == "0"]
    return sorted(times), one_tap


def mmss(s):
    return f"{s // 60}:{s % 60:02d}"


def chart(classes, title, ymax, out):
    xmax = 180
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150)
    for name, label, color, dashed in classes:
        s, one_tap = load(name)
        extra = ""
        if one_tap:
            extra = f", {len(one_tap)} with one tap (median {statistics.median(one_tap):.0f} s)"
        print(f"{label}: {len(s)} check-ins, first at {mmss(s[0])}, last at "
              f"{mmss(s[-1])}, {sum(t <= 60 for t in s)} in the first minute{extra}")
        # step curve: the count goes up by one at each check-in
        xs, ys = [0, s[0]], [0, 0]
        for i, t in enumerate(s, 1):
            xs += [t, t]
            ys += [i - 1, i]
        xs.append(xmax)
        ys.append(len(s))
        ax.plot(xs, ys, color=color, lw=2, ls="--" if dashed else "-",
                label=f"{label}: {len(s)} students, {sum(t <= 60 for t in s)} in the first minute")

    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.set_xticks(range(0, xmax + 1, 30))
    ax.set_xticklabels([mmss(t) for t in range(0, xmax + 1, 30)])
    ax.set_xlabel("Time since the professor opened the QR session (min:s)")
    ax.set_ylabel("Students checked in")
    ax.set_title(title, loc="left")
    ax.legend(loc="upper left", frameon=False, fontsize=8.5)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="y", color="#e6e5e1", lw=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    MEDIA.mkdir(exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    print(f"Chart: {out}\n")


def main():
    chart(FIRST_TIME, "QR check-ins over time, first time with the app for every group",
          78, MEDIA / "dia11_03_qr_en_el_tiempo.png")
    chart(SECOND_DAY, "The same classes on their second day: most students only tap Aceptar",
          95, MEDIA / "dia12_02_primer_y_segundo_dia.png")


if __name__ == "__main__":
    main()
