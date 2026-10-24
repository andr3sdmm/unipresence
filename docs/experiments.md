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

**What I decided:** I decided to ask for the student's private code before showing or requesting their name so the course list is not exposed during registration. I also decided to use English for the repository and technical documentation, while keeping the student-facing interface in Spanish. For the current prototype, teacher access uses a shared password stored outside the repository as an environment variable. A future production version should use the University's institutional login instead.

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

## Day 5 — October 18, 2026: moving the data to Postgres

**What I built:** Moved all storage from a SQLite file inside the Render server to a free Postgres database on Neon. In the September 22 pilot the data was lost when the free Render instance went to sleep; now a restart or a new deploy no longer erases anything. The tests also run against a real Postgres.

## Day 6 — October 19, 2026: the course list does not have the student ID

**What I was preparing:** The second classroom test. Version 2 binds each phone to the student's university ID, and the professor uploads her course list so each check-in matches a student. I tested version 2 without students, using her real list (a spreadsheet exported from Brightspace at the start of the semester).

**What failed:**
1. The list does not have the student ID. It identifies students by OrgDefinedId, an internal Brightspace number students do not know. The test had not started, but the check-in design was already broken: a student cannot identify themselves with a number they do not know.
2. In a class without a list, an ID typed with a missing digit could not be fixed. Once a phone is linked, it keeps checking in with that ID, so only the professor can correct it.
3. Our test check-ins stayed mixed with the real classes, and there was no way to delete them.
4. Pages were slow. The free Render instance sleeps after inactivity, and every request opened a new connection to Neon.

**What I learned:** This is the second time the system broke because of an assumption about the real world, not because of a bug in the code. The first time, I assumed one phone means one browser. This time, I assumed the official list has an identifier the student knows.

**Options I considered:**
1. Use the institutional username or email as the key. Students know their email.
2. Make my own private codes from the list and hand them out on paper slips, like version 1.
3. Let students type their ID and name without checking them, and match them to the list by name after class.

**What I decided:**
1. Option 1. The first time, students can type their institutional username (the part of their email before the @), their ID, or their whole email. Only the username is saved, never the email address. Option 2 brings back the slips that broke the September 22 pilot. Option 3 came back later, for classes with no list (Day 8).
2. The professor can correct a student's ID or name. If the correct ID already exists, the two records are merged.
3. The professor can delete a whole class by typing its name. From now on, tests go in a separate test class that we delete afterwards.
4. Someone who is not on the list is no longer blocked. They show up as pending, and the professor approves or rejects them.
5. The app keeps a few database connections open and reuses them, instead of opening a new one for every request. The sleeping server is in Day 7.

**Baseline:** The same day, in class, the professor called the roll of a small group of 27 students by reading her Excel sheet: 1 min 47 s with the file already open (about 4 s per name), plus about 30 s to open it and get ready. Details in `results.md`.

## Day 7 — October 20, 2026: version 2.1, and the list was not from Brightspace

**What I built:** Version 2.1, with the changes from October 19. Also: Brightspace writes usernames as "#agomez", and the # is now ignored; a name that starts with = no longer runs as a formula when the report is opened in Excel; and the first time a phone is linked, the person has to accept a data policy (page /privacidad). Without that, nothing is saved.

**What failed:**
1. The professor's real list for Sistema Nervioso (167 students, 6 groups) did not come from Brightspace. It came from Banner, the university's student information system. Its columns are SPRIDEN_ID (the student code), SPRIDEN_LAST_NAME (the full name) and SSBSECT_CRN (the group, which students call NRC). The app did not recognize them: it saved everyone, but stuck the group number to each name and found no groups.
2. Render's free plan puts the app to sleep after 15 minutes without visits, and waking up takes about a minute. That is the first minute of a class.

**What I decided:**
1. The app now reads Banner's columns. The real list never goes into this repository.
2. Students do not have to know their group, because the list already says it. Students usually know their NRC better than the professor does, so if she is not sure which groups are in the room she can select all of them; the report shows each student's group.
3. Code cannot wake a sleeping server, so something outside has to visit it. A free scheduled job (cron-job.org) opens /healthz every 15 minutes (now every 10), from 6:00 to 17:00, Monday to Saturday, Bogota time.
4. Why the consent: Law 1581 of 2012 asks for prior, informed authorization before storing personal data, and a class without a list could be used at a conference where people might type a national ID.

**What I tested:** 33 automated tests for version 2.1: sign-in with username, the Banner list, the data policy consent, approving or rejecting pending students, and names that start with =. And the real Banner list: 167 students in 6 groups, and the count per group matched the file.

Evidence: `media/dia07_01_consentimiento.png` (first time on a phone: code or username, full name, and the data policy checkbox), `media/dia07_02_asistencia_recibida.png` (the receipt the student sees, so they know their attendance was saved and do not try to check in again).

## Day 8 — October 21, 2026: first class with version 2.1, attendance first and list later

**What I tested:** Version 2.1 in a real class of Fundamentos de Ciencias Básicas, group 3611, which has 26 students on the list. The professor did not have the list yet, so she took attendance without one. She timed both methods and recorded the roll call on video.

| | Time |
|---|---|
| Roll call by hand (video, names only, 26 names) | 2 min 12 s |
| With the QR, timed by the professor | 1 min 24 s |
| With the QR, first to last check-in (server times) | 42 s |
| With the QR, session open to close (08:26 to 08:29) | about 3 min |

20 students were present and all 20 checked in with the QR; the other 6 were absent.

The server saves the time of every check-in, to the second. The session opened at 08:26:02. The first student checked in 1 min 49 s later and the last one at 2 min 31 s, so the 20 check-ins took only 42 seconds, about 2 seconds per student. By hand, each name took about 5 seconds (2 min 12 s for 26 names). The professor's 1 min 24 s probably started when she told the class to scan, about 40 seconds before the first check-in. I do not know exactly what filled the first minute and a half: explaining, projecting the QR, students opening the camera. It was everyone's first time: each student had to type their code and accept the data policy. The next time it should be one tap.

Evidence: the anonymous times in `analysis/data/dia08_tiempos_qr.csv` (no names or codes). The chart is in Day 9.

The video is kept privately. It shows students' faces and names, so it does not go into this repository.

**What failed:**
1. The professor found the web address hard to type. She uses the classroom's shared computer, so she cannot save it as a bookmark.
2. The scheduled visit that keeps Render awake did not run: cron-job.org was under maintenance, so the app was asleep when class started.
3. The list the professor had later, a Brightspace export, did not contain the code the students typed. 15 typed their 9-digit student code and 5 their username, but the list's OrgDefinedId is a 6-digit internal number. Uploading it would have added the whole list next to the 20 pending students, as different people.

**What I decided:**
1. When a list is uploaded to a class with pending students, the app suggests a match for each one: same code or username, same name (every word of one name is in the other, and only one person fits), or a similar name, which is not pre-selected. The professor confirms; a name alone never validates anyone. With the real data: 5 exact, 13 by name, 2 similar, all 20 found. Each student keeps their attendance, their phone and the code they typed.
2. One free service was not enough to keep Render awake, so the next day (October 22) we moved to Render's paid plan (7 USD a month), which never sleeps.
3. A short address that is easy to type on any computer: is.gd/asiste.

**What this does not show:** one class of 26, and a professor who knew it was a test. The second time the same students check in should be a single tap; that is the next thing to measure.

## Day 9 — October 22, 2026: second class, group 3609, with the list loaded

**What I tested:** Version 2.1 in Fundamentos, group 3609, which has 22 students on the list, with the Brightspace list already loaded. The professor recorded the roll call on video, from opening her computer to the last name: 2 min 16 s (about 20 s of that was opening the list).

15 students were present and all 15 checked in with the QR; the other 7 were absent. By hand that is about 5 seconds per name, like October 21.

With the QR, the session opened at 08:19:28. The first student checked in 48 s later and the last at 1 min 51 s, so the 15 check-ins took 63 seconds. 13 of them came in the first 42 seconds; the last two were the students who typed a code that was not on the list. The first check-in came a minute earlier than on October 21. This was also the first class with the app for this group, so every student linked their phone.

Evidence: `media/dia09_01_qr_en_el_tiempo.png`, made by `analysis/checkin_timeline.py` from the anonymous times of both classes.

**What failed:**
1. Two students typed their 9-digit student code. The Brightspace list only has a 6-digit internal id, so the app did not find them and they waited as pending. The same two names are on the list as absent, with their 6-digit id, so the report showed each of them twice. One wrote "Andrés" with an accent, the other added his middle name.
2. The professor said the slow part with the QR is opening the page: the browser on the classroom computer does not find it easily.
3. The alert for several new phones in a row fired again: 3 phones with Safari on iOS in less than a minute. This time it named them, and it was normal: they were linking their phones for the first time.

**What I decided:**
1. Validate the two pending students with "Validar con la lista".
2. Upload the Banner list for this class, which has the 9-digit codes, so the code students know is found directly. A second list now updates the codes by name instead of duplicating students.
3. The short address is.gd/asiste, so opening the page takes seconds.
