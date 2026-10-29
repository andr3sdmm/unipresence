# Attack protocol — version 2.1

Five attacks against the app as it runs in class, done by hand with real phones. Each one tests one claim from `threat-model.md`. The expected messages are the ones the app actually shows (checked in `main.py`). Attacks that are expected to fail are run anyway, because a defence that was never attacked is only an assumption.

## Setup

- A separate class called "Prueba de ataques", with a made-up list of three students (codes 900000001, 900000002, 900000003). No real students take part.
- Laptop: the professor's live screen, logged in, attendance running.
- Phone A: the student in the room, linked to 900000001.
- Phone B: the student at home, linked to 900000002, in another room.
- Phone C: a phone that has never used the app.
- Both phones A and B scan once before starting, so they are already linked.
- Each phone screen-records the whole session. At the end, a screenshot of "Por revisar" and the report, and the "Tiempos (anónimo)" file is downloaded. After that, the test session is deleted with "Borrar sesión".

Before starting, write down the date, the time and where each phone is.

## Attack 1 — photo of an old QR

Claim tested: an old QR is useless.

1. Phone A takes a photo of the QR on the laptop and notes the second.
2. After 30 seconds, the photo is sent to phone B.
3. Phone B scans the photo.

Expected: "Vuelve a escanear. Ese QR ya venció." No attendance is recorded. The report counts one "Escaneó un QR vencido".

## Attack 2 — live relay over a video call

Claim tested: none. This attack is expected to work, and that is the main open risk.

1. Phone A starts a video call with phone B and points its camera at the QR on the laptop.
2. Phone B scans the QR from the call, with a third device or from a screenshot taken during the call, and taps Aceptar.
3. Repeat ten times, noting how long each attempt took and how many failed.

Expected: "Asistencia recibida" on phone B, even though it is not in the room. The server records how old the QR was when it was scanned (`qr_age_s`). That is the number `analysis/relay_analysis.py` compares with real students in class: if relayed scans are always older, a shorter QR lifetime would stop most relays without locking out students in the room.

## Attack 3 — a friend's code on another phone

Claim tested: a code that moves to another phone does not go unnoticed.

1. Phone C, which has never used the app, scans the QR.
2. It types 900000001 (phone A's student), accepts the policy and taps Aceptar.

Expected: the check-in is accepted on purpose (a present student is never refused), and the professor's screen shows under "Por revisar": "Su carné pasó a otro navegador o celular durante la clase". The professor can reject it, and the decision stays on record.

## Attack 4 — marking a friend from your own phone

Claim tested: a phone the app knows only marks for its owner.

1. Phone A, already linked, scans the QR.
2. Look for a way to enter a different code.

Expected: the page only shows the class, the name of phone A's student and the Aceptar button. There is no field to type another code, so phone A can only mark its own student.

## Attack 5 — the QR without being the professor

Claim tested: the QR only exists on the professor's screen. In version 1 this address was public for a while.

1. On phone B, in a private window, open `/session/<id>/qr` with the id of the running session.
2. Try the ids before and after it.

Expected: no QR image. The app sends the request to the login page.

## Already covered by automated tests

These are checked on every commit, so they are not repeated by hand: a class that ended accepts nothing, a scan cannot be used twice, a double tap creates one attendance, and professors cannot see each other's classes. See `testing.md`.

## Results

Done on October 25, 2026, in a test class with three made-up students. Details in `experiments.md`, Day 10.

| Attack | Expected | What happened | Evidence |
|---|---|---|---|
| 1. Photo of an old QR | rejected, "Ese QR ya venció" | Rejected with that message | `media/dia10_02_ataque1_qr_vencido.jpg` |
| 2. Live relay | works | Worked 5 out of 5 | `media/dia10_05_ataque2_qr_por_videollamada.png`, `media/dia10_06_ataque2_recibo_desde_fuera.jpg` |
| 3. Friend's code on another phone | accepted + alert under "Por revisar" | Accepted, and "Por revisar" showed the device change | `media/dia10_03_ataque3_alerta_por_revisar.png` |
| 4. Friend from your own phone | impossible, no code field | Only the class, the owner's name and Aceptar | `media/dia10_01_ataque4_sin_campo_para_otro_codigo.png` |
| 5. QR without login | login page, no image | Login page, for the current id and the ones before and after | `media/dia10_04_ataque5_pide_iniciar_sesion.jpg` |

For attack 2: 5 attempts, 5 receipts. From the start of the call to the receipt it took about 20 to 45 seconds, timed roughly by hand. The server measured how old the QR was when the phone outside opened it: 4.6 to 18.4 seconds (`analysis/data/dia10_tiempos_relevo.csv`). That is as fresh as a QR scanned inside the room, which `results.md` compares with 218 real check-ins.

## Afterwards

- `threat-model.md`: the old QR and the live relay sections now say what happened.
- `experiments.md`: Day 10.
- `analysis/data/`: the anonymous times of the relay attempts, next to the times of real classes.
- `media/`: one screenshot or photo per attack.
