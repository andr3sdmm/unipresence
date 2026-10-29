# Reviewer guide

A short path through this repository, if you only have a few minutes.

## In 2 minutes

1. **The problem and the first failure.** [`README.md`](../README.md), sections "The problem" and "How the design changed after the first pilot". Version 1 locked 7 of 22 present students out on September 22, and that failure is why version 2 exists.
2. **The main result.** [`results.md`](results.md), section "Summary". In a class of 88 on the list, the roll call by hand took 8 min 50 s and the QR about 2 min 40 s. On the second day, a student with a linked phone tapped Aceptar about 3 seconds after scanning. Before this, the professor did not take attendance in those classes at all.
3. **What does not work.** [`threat-model.md`](threat-model.md), "Live relay over video call". I attacked the app on purpose, and a relay over a video call worked 5 out of 5 times. The data shows that a shorter QR would not stop it.
4. **What the professor could not use.** [`experiments.md`](experiments.md), Day 13. Her interview: what she could not find, and what she asked for next.

## In 10 minutes

| If you want to see | Read |
|---|---|
| What happened in each class: what I tested, what failed, what I decided | [`experiments.md`](experiments.md) |
| Every number, how it was measured, and what it does not show | [`results.md`](results.md) |
| The five attacks and their results | [`attack-protocol.md`](attack-protocol.md) |
| How the app is built, with diagrams | [`architecture.md`](architecture.md) |
| The 50 automated tests, grouped by the promise each one checks | [`testing.md`](testing.md) |
| What data is stored, why, and for how long | [`data-handling.md`](data-handling.md) |

## The charts

- [`media/dia12_02_primer_y_segundo_dia.png`](../media/dia12_02_primer_y_segundo_dia.png): the same two large classes on their first and second day.
- [`media/dia12_03_edad_del_qr_clase_vs_relevo.png`](../media/dia12_03_edad_del_qr_clase_vs_relevo.png): how old the QR was when 218 real students scanned it, against the 5 relays.

Both are made from the anonymous times in [`analysis/data/`](../analysis/data/) by [`analysis/checkin_timeline.py`](../analysis/checkin_timeline.py) and [`analysis/relay_analysis.py`](../analysis/relay_analysis.py). The files only keep seconds, never names or codes.

## Where the important code is

Everything runs in [`main.py`](../main.py). The parts worth reading:

| What | Function |
|---|---|
| The QR the professor projects, a new one every 10 seconds | `attendance_qr` |
| A scan: checks that the QR is not older than 20 seconds and gives a one-use ticket | `checkin` |
| Tapping Aceptar: uses the ticket once, links the phone the first time | `checkin_accept` |
| Moving a code to another phone is allowed, but recorded as an alert | `bind_device` |
| Several new phones in a row from the same kind of browser | `check_burst` |
| Matching students who typed something that is not on the list | `suggest_matches`, `merge_students` |
| The anonymous export used for the charts | `export_timing` |

## What I did and what AI did

The application code was written with AI tools, under my direction. The problem, the design decisions, the pilots with a real professor, the attack tests and the analysis of the results are mine. The last section of the README says this in more detail.
