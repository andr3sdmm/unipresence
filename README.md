# UniPresence

Privacy-preserving physical presence verification for large classrooms.

## The problem

Some Medicine courses at a university in Colombia have hundreds of students, while the university requires professors to record attendance. Calling students one by one can take a significant amount of class time, so in practice attendance may not always be recorded.

The challenge is not simply digitizing an attendance list. It is verifying that a student is physically present in the classroom without collecting sensitive data such as their location.

## How it works (version 2)

The teacher creates an account, creates a class (with or without a student list) and presses "Tomar asistencia". The projector shows a QR code that changes every 10 seconds.

The student points the phone camera at the QR, sees the name of the class and taps "Aceptar". The first time, the student enters their university code or institutional username and accepts the data policy, which binds that phone to their identity. After that, scanning and tapping "Aceptar" is enough. A green confirmation on screen is the receipt.

The server checks that the nonce in the QR exists and has not expired before recording attendance. If a code moves to a different phone or browser, the change is allowed but recorded, shown to the teacher during class and marked in the export. The browser used for each check-in is logged for fraud analysis.

## How the design changed after the first pilot

Version 1 asked each student to register once with a private code printed on a paper slip, through a separate registration link, before scanning the attendance QR.

On September 22, 2026 it ran in a real genetics lab: 22 students, the professor operating it alone. 15 checked in; 7 could not.

The professor's video showed why. Students opened the registration link inside WhatsApp, then scanned the attendance QR with the camera, which opens Safari. The phone binding lived in a browser cookie, and each browser keeps its own cookies, so the system no longer recognized them. It told students who had registered minutes earlier that their code was "already used". I had built device binding on something narrower than a device.

The problem was not cheating or the network. Every extra step I asked of students (a slip to keep, a code to type, a separate registration link, a second app) was a point where a real student could drop out. Version 2 is built around fewer steps: one QR, the student sees the class and taps "Aceptar". Device changes are no longer refused; they are recorded and made visible to the teacher.

The pilot also lost its stored data when the free Render instance went to sleep. That is why version 2 stores everything in Postgres.

## What is built

- A rotating attendance QR code
- One-scan check-in: scan, see the class, tap "Aceptar"
- Phone binding to the student's university code, with every device change logged and visible to the teacher
- Browser logging per check-in, for fraud analysis
- Individual teacher accounts, optionally restricted by a signup code
- Classes with or without a student list; the list is uploaded once through the teacher interface
- Manual attendance override for professors
- Attendance export to CSV and PDF
- Ending an attendance session and a page of previous classes
- Persistent storage in Postgres
- Automated tests

Added in version 2.1, after testing with the professor's real lists:

- Sign-in with the student code, the institutional username or the email (only the username is saved)
- Data policy consent the first time a phone is linked (Colombia's Law 1581 of 2012)
- Class lists exported from Brightspace or Banner, with groups
- Students who are not on the list wait as pending, and the professor validates them against the list later
- Correcting a student's code or name, and deleting test sessions with their data
- Reports that can be sorted and filtered, with an anonymous export of check-in times

## Results so far

Two real classes in October 2026 with version 2.1: every present student checked in with the QR (20 of 20 and 15 of 15), and nobody had to be marked by hand. Once students start scanning, the whole class is in within about a minute. Whether it saves the professor time is not proven yet. The numbers, how each was measured, and what they do not show are in [`docs/results.md`](docs/results.md).

![QR check-ins over time](media/dia09_01_qr_en_el_tiempo.png)

## What is not built yet

- BLE-based proximity verification, which would provide stronger evidence that a device is physically inside the classroom
- Protection against live relay attacks, such as someone sharing the current QR through a video call
- The university's institutional authentication for professors

Because BLE verification is not implemented, the prototype should not be treated as proof of physical presence under every attack scenario.

## Security

UniPresence is designed to reduce simple forms of attendance fraud without collecting student location data. Rotating nonces limit the usefulness of old QR codes, and teacher-only endpoints require an individual teacher account.

Version 2 makes a deliberate trade. University codes are not secret, so a student who knows a classmate's code can move that classmate's registration to another phone. The system does not block this, because blocking is exactly what locked 7 present students out in the first pilot. Instead, every device change is recorded, counted on the teacher's screen while class runs and marked in the export. The one-phone-one-student rule is enforced by visibility rather than by refusal.

Live relay remains possible. The full analysis, including vulnerabilities found during development and alternatives considered, is in [`docs/threat-model.md`](docs/threat-model.md).

## Running it locally

```bash
git clone https://github.com/andr3sdmm/unipresence.git
cd unipresence
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Version 2 stores everything in Postgres. Create a free database (for example on Neon), copy its connection string, and start the server with it:

```bash
DATABASE_URL="postgresql://..." uvicorn main:app --reload
```

Open the site, create a teacher account, create a class (with or without a list; `roster.example.csv` is a sample list), and press "Tomar asistencia".

Optional: `TEACHER_SIGNUP_CODE="..."` makes new teacher accounts require that code.

To run the tests, point them at an empty database they are allowed to wipe (never the production one):

```bash
pip install -r requirements-dev.txt
TEST_DATABASE_URL="postgresql://..." pytest -q
```

## Project log

Development decisions, tests, failures, and changes are documented in [`docs/experiments.md`](docs/experiments.md). What data is stored and why is in [`docs/data-handling.md`](docs/data-handling.md).

## A note on how this was built

AI tools were used to write the application code under my direction. I defined the problem, made the design decisions, tested the system, and analyzed its security behavior.

During testing, I independently found a problem with the manual attendance flow. Three additional security weaknesses were identified during an AI-assisted review of the design, including misuse of student codes and initially unprotected teacher and QR endpoints. I then incorporated the findings into the design and tested the resulting changes.

The most important problem was not found in testing but in the classroom pilot on September 22, from the professor's video. I diagnosed it and redesigned the check-in flow around it, which became version 2.

I wrote the project log and threat model to document the development process, including what worked, what failed, what was changed, and which risks remain open.
