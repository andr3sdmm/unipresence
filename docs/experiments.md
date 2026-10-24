# Experiments log

## Day 1 — September 18, 2026

**What I built:** A server that generates a QR code that changes every 10 seconds, a teacher screen, and a page where students can register their attendance.

**What I tested:** My first test with two real devices: a MacBook displaying the QR code and an iPhone scanning it through ngrok.

**What failed:** I scanned a QR code that changed every 10 seconds. After scanning it, the page asked for my personal code, but while I was typing it the QR expired and I had to repeat the process.

**What I decided:** Separate student registration from attendance check-in so students do not have to enter their information before the QR expires.


## Day 2 — September 19, 2026

**What I built:** I added a course list with individually assigned student codes, a two-step registration and check-in process, manual attendance override, CSV attendance export, deployment on Render, and password authentication for the teacher interface.

**What I tested:** I tested valid, invalid, and already-used student codes. I also tested the phone-to-student binding to make sure the same phone could not register multiple students, and tested the complete process from registration to attendance check-in. Finally, I tested `/qr/1` in an incognito browser before and after adding teacher authentication to confirm that it could no longer be accessed without authorization.

**What failed:** Four important problems came up today. First, the manual attendance option rejected students who had not previously registered a phone. I found this problem myself while testing different situations in the system.

Three additional problems were identified during a review of the design with an AI assistant. A student could register using another student's code if they obtained it before the real owner used it. The review also identified that the teacher screen was accessible without authentication and that the `/qr/{session_id}` endpoint was public, allowing anyone with the URL to obtain a valid nonce. The teacher screen and QR endpoint were later placed behind the authenticated teacher session, while the assigned-code system was redesigned to reduce the risk of code misuse.

**What I decided:** I decided to ask for the student's private code before showing or requesting their name so the course list is not exposed during registration. I also decided to use English for the repository and technical documentation, while keeping the student-facing interface in Spanish. For the current prototype, teacher access uses a shared password stored outside the repository as an environment variable. A future production version should use University's institutional login instead.

**Still open:** The timestamps in the exported CSV are still displayed in UTC and need to be converted to the appropriate local time.


## Day 4 — September 22, 2026: first classroom pilot

**What I tested:** The system ran in a real genetics lab at the university: 22 students, the professor operating it alone. Each student received a printed slip with their private code, registered through a registration QR, and then scanned the rotating attendance QR.

**What happened:** 15 students checked in. 7 could not.

**What failed:** The professor's video shows the same sequence for the students who failed. A student scans the attendance QR, is told "Primero registrate", types the code from the slip, and is told "Ese codigo ya fue usado". Both screens were the system working exactly as written, and both were wrong: the student had registered minutes earlier.

The cause: students opened the registration link inside WhatsApp, then scanned the attendance QR with the phone camera, which opens Safari. The binding between a student and a phone was stored in a browser cookie, and each browser keeps its own cookies. Two browsers, two cookie jars, one student the system could no longer recognize. I had built device binding on something narrower than a device.

The pilot also lost its stored data when the free Render instance went to sleep.

Evidence: `media/dia04_01_primero_registrate.png`, `media/dia04_03_codigo_ya_usado.jpg`, `media/dia04_04_proyector.jpg`, `media/dia04_05_papelito.jpg`.

**What I decided:** The problem was not cheating and not the network. It was the number of steps. Each one (keeping a slip, typing a code, using a separate registration link, crossing from one app to another) was a point where a real student could fall out of the flow. Immediate changes:

1. A student who is not recognized at check-in can type their code right there and bind that browser, instead of being sent away.
2. Re-binding is never silent: every change is written to a `device_changes` table, counted on the teacher's screen during class, and marked in the CSV. The one-phone-one-student rule is enforced by visibility rather than by refusal.
3. The error message that implied the student had used someone else's code was replaced with one that explains the real cause.

Evidence of the fix: `media/dia04_06_casilla_vincular.png`, `media/dia04_07_vinculado_de_nuevo.png`, `media/dia04_08_cambio_visible_profesor.png`.

**Still open:** Persistent storage, and a flow with even fewer steps. Both led to version 2.


## Version 2 — October 2026

**Why:** The September 22 pilot showed that the real failure point was friction for the students, and that the free deployment could lose data. 

After the pilot I talked with the professor. We wanted to simplify it for both sides: she uploads her class list once, and a student only types their ID the first time; after that, scanning and tapping "Aceptar" is enough. We also kept the option to take attendance without a list. A class can start empty and build its list from the people who check in. We were thinking of cases where people are not on any list, like a conference, where each person registers with their name and an ID.

**What I built:** Students scan one QR, see the class name and tap "Aceptar". The first time, they enter their university code, which binds the phone; slips and the separate registration link are no longer needed. The browser used for each check-in is logged for fraud analysis. Teachers have individual accounts (optionally restricted by a signup code), can create classes with or without a student list, upload the list once through the interface, and export attendance to CSV or PDF. All data is stored in Postgres, and the project has automated tests.

I also changed the teacher's screen: besides the QR and the counter, it now shows who is still missing (tapping a name marks them by hand), the last students who checked in, and a "Por revisar" list with the alerts. Before starting, the professor picks which groups are in the room.

Evidence: `media/dia06_01_pantalla_profesor.png`

**Design trade-off:** University codes are not secret, so they cannot protect registration the way private slips did. I accepted this on purpose: device changes are allowed but always recorded and shown to the teacher, so a misused code becomes visible instead of locking out a present student.

**Next:** Time a manual roll call (paper list, no sign-in sheet) in a small class and then in a large one, to have a baseline. Only then run the version 2 pilot and compare. Results go in `docs/results.md`.

**Finished:** October 18, 2026.

