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

## Day 10 — October 25, 2026: attacking the app on purpose

**What I tested:** The five attacks in `attack-protocol.md`, with real phones and a test class of three made-up students. The phone that marked in each attack never saw the laptop.

| Attack | Expected | What happened |
|---|---|---|
| 1. Photo of an old QR | rejected | Rejected: "Ese QR ya venció" |
| 2. Live relay over a video call | works | Worked 5 out of 5 |
| 3. A friend's code on another phone | accepted with an alert | Accepted, and "Por revisar" showed the device change |
| 4. A friend from your own phone | impossible | Impossible: there is no field for another code |
| 5. The QR without being the professor | login page | Asked to log in |

The relay took about 20 to 45 seconds from the start of the call to the receipt (timed roughly by hand): answering, turning the camera, pointing at the screen and scanning with a second device. But once the QR reached the phone outside, it was only 4.6 to 18.4 seconds old (measured by the server). Chrome on the iPhone was slower than Safari to open the page.

**What failed:** Nothing that was expected to hold. The relay works, as expected.

**What I learned:** A shorter QR does not stop a relay: the relayed QR arrives about as fresh as one scanned in the room (Day 12 compares it with 218 real check-ins). What makes the relay hard is coordination: someone outside has to be on a call, with a second device, at the exact moment the professor shows the QR.

**What I decided:**

1. The professor can take attendance at a moment she does not announce: at the start, ten minutes in, or at the end. It does not stop a relay, but it makes it expensive and easy to notice.
2. No Bluetooth for now. Phone browsers on iPhone cannot use Bluetooth, so it would need an app or a beacon to buy, and the app must stay simple with nothing to install or buy. Kim, Lee and Paek (2018) also showed that a real beacon system can be faked with an Arduino.
3. The projected screen no longer shows names: only the QR and the count. Absent students and alerts stay behind a button for the professor.

Evidence: `media/dia10_01_ataque4_sin_campo_para_otro_codigo.png`, `media/dia10_02_ataque1_qr_vencido.jpg`, `media/dia10_03_ataque3_alerta_por_revisar.png`, `media/dia10_04_ataque5_pide_iniciar_sesion.jpg`, `media/dia10_05_ataque2_qr_por_videollamada.png`, `media/dia10_06_ataque2_recibo_desde_fuera.jpg`. Anonymous relay times in `analysis/data/dia10_tiempos_relevo.csv`.

## Day 11 — October 26, 2026: two large classes, about 50 students each

**What I tested:** Version 2.1 in two classes of the same course, in an auditorium, with the Banner list loaded and the groups chosen. Everyone was linking a phone for the first time.

| | Groups 3617–3619 (8:25) | Groups 3614–3616 (10:11) |
|---|---|---|
| On the list | 88 | 80 |
| Checked in with the QR | 50 | 52 |
| First check-in after the session opened | 27 s | 14 s |
| Checked in during the first minute | 33 | 36 |
| Last check-in | 2 min 18 s | 2 min 57 s |
| Time to tap Aceptar after scanning, median | 29 s | 21 s |
| Scans of an expired QR | 6 | 12 |

To start, the professor only said "vamos a llamar a lista" and showed the QR; she did not have to explain anything else. In the 8:25 class she also called the roll by hand and recorded it: 8 min 50 s in total. About 28 seconds went into finding the list, the first name came at 40 seconds, and the rest of the time was calling every name, waiting for each "presente", and then going back over the list for students who came in late. She does not normally call the roll: she did it only for this test (Day 13).

The first check-in came 14 to 27 seconds after the session opened, instead of almost two minutes on October 21: the app no longer sleeps, and the professor already knew it. The slow part was the first time: typing the code and accepting the data policy took a median of 21 to 29 seconds per student.

**What failed:**

1. The form asked for "carné o usuario", but the Banner list only has codes. 14 students in the first class and 17 in the second typed their username and waited as pending, while their row on the list showed them absent.
2. The pending students were approved with "Aprobar" instead of "Validar con la lista", so each of them was on the list twice (198 rows instead of 167).
3. The "not on the list" alerts said "Varios estudiantes" instead of the name, and the notice for 31 new phones in a row buried the alerts that needed a decision.
4. Expired scans could not say who they were, and there was no way to mark a student who arrived late with a note.

**What I decided:**

1. When the list only has codes, the form asks for the "Código de estudiante".
2. "Validar con la lista" also joins students who were approved by hand, and keeps the username they typed so it works next time.
3. Alerts name the student, alerts about one student come before general notices, and alerts already solved leave the list. "Por revisar" can be folded.
4. The report says who scanned an expired QR and whether they marked later, and any absent student can be marked present with a note, even after class.

**What this does not show:** I have not crossed the roll call with the QR name by name, so this day does not show who was in the room and did not scan. The roll call and the QR also measure different things: the roll call includes going back for late students, and the QR does not wait for them.

Evidence: `media/dia11_01_qr_proyectado_auditorio.jpg`, `media/dia11_02_conteo_en_vivo.jpg`, `media/dia11_03_qr_en_el_tiempo.png` (made by `analysis/checkin_timeline.py` from the anonymous times in `analysis/data/`).

## Day 12 — October 27, 2026: the same classes on their second day

**What I tested:** The same two classes the next day, with the fixes from Day 11. Most students had already linked their phone, so for them checking in should be one scan and one tap.

| | Groups 3617–3619 | Groups 3614–3616 |
|---|---|---|
| Checked in with the QR | 52 (Oct 26: 50) | 64 (Oct 26: 52) |
| First check-in after the session opened | 12 s | 8 s |
| Checked in during the first minute | 45 (Oct 26: 33) | 56 (Oct 26: 36) |
| Last check-in | 2 min 8 s | 2 min 23 s |
| Only tapped Aceptar | 30, median 3.3 s | 33, median 2.8 s |
| Linked a phone for the first time | 22, median 11 s | 31, median 16 s |

In groups 3617–3619 the professor counted about 54 students in the room, and 52 checked in. She spent about 40 seconds opening the link and explaining, and closed the QR at about 2 min 40 s. The day before, the roll call by hand in the same groups took 8 min 50 s. They are different days and the roll call also went back for late students, so this is not an exact comparison, but the difference is too large to come from that alone.

A student who had already linked their phone tapped Aceptar about 3 seconds after scanning, against 21 to 29 seconds on the first day. That is the whole point of version 2: the effort is paid once.

I also compared how old the QR was when each phone opened it. With 218 real check-ins from both days, the median was 8.5 seconds and 95 % were under 15 seconds. The five relays from Day 10 were 4.6 to 18.4 seconds old. A 15-second QR would let in 95 % of the students in the room and 4 of the 5 relays. No QR lifetime separates them, so I kept 20 seconds.

**What failed:**

1. 2 of the about 54 students the professor counted did not check in. I do not know why: the count was approximate and nobody reported a problem.
2. 31 phones were linked for the first time in groups 3614–3616 on the second day, more than I expected. The anonymous export does not say whether they were students who missed Monday or students on a new browser.

**What I decided:**

1. Keep the QR at 20 seconds. Against the relay, the defence is an unannounced moment and the professor's alerts, not a shorter QR.
2. A student from another group of the same course is marked present, with "Es de otro grupo" in the report. The summary of absences for the 25 % rule has to count that class too.

Evidence: `media/dia12_01_qr_proyectado_segundo_dia.jpg`, `media/dia12_02_primer_y_segundo_dia.png` (made by `analysis/checkin_timeline.py`), `media/dia12_03_edad_del_qr_clase_vs_relevo.png` (made by `analysis/relay_analysis.py`).

## Day 13 — October 28, 2026: what the professor said

**What I did:** I interviewed the professor about the two large classes, with 15 questions. She answered with voice notes, in Spanish; these are her answers, translated.

**What she said:**

1. Before the app she did not take attendance in these classes, and no professor did, because by hand it takes too much class time. The 8 min 50 s roll call on Day 11 was the first time, only for this test.
2. The slowest part of the QR was opening the page. She had to look for the link in our chat and type it letter by letter, because it is not easy to remember.
3. For her, there was no difference between Monday and Tuesday, even though the students were faster on Tuesday. Her part, opening the page and waiting, did not change.
4. She sees the alerts under "Por revisar", but does not understand what they are for or how they help her.
5. Some students arrived as she was closing the QR and could not check in. She told them they would do it by hand at the end, but she did not find how. A student from another group (another NRC) also told her he was in her class, and she did not know how to add him.
6. She counted heads and compared them with the count on the screen, and they usually matched. She also said that students do send the QR to classmates who are not in class, as a photo on WhatsApp or another messaging app, and that this was the complaint when other professors tried QR attendance before.
7. Taking attendance at a moment she does not announce: "podría ser" (maybe).
8. For the rule that more than 25 % of absences means no final exam, she wants a table, student by student, with their absences. She would enter the total number of classes, and the table would show each percentage and warn her when a student has 3, 2 or 1 absences left. With that and the QR, she would not need the paper list anymore.
9. She would like to keep using the app, but first she needs to know how the alerts work, how to mark a student after closing the QR, and how to add a student from another group.
10. She can ask a colleague to try it in a class.

**What I learned:**

1. The QR is not replacing a roll call. It is replacing no attendance at all, because nobody calls the roll in a class this size.
2. The button to mark a late student already existed, in the report, next to each absent student. She did not find it. A feature the professor cannot find does not exist for her.
3. The alerts were designed for me, not for her. They say what the system saw, not what she should do.
4. Sending the QR to absent classmates is not only a theory from my threat model: she says students already do it, and not by video call, as I tested, but with a photo on WhatsApp. On October 25 I only tested a photo sent 30 seconds later, which was rejected. A photo forwarded right away is a faster relay, and I have not tested it.

**What I decided:**

1. Next: the absence summary she asked for, with the total of classes, the percentage and a warning at 3, 2 and 1 absences left.
2. Show "mark a student by hand" and "add a student from another group" on the professor's screen, not only in the report.
3. Each alert says in one sentence what she can do about it.
4. A link that is easy to remember, saved as a bookmark on the classroom computers.
5. Test a photo forwarded right away on WhatsApp, and measure how old the QR is when it arrives.
6. Test a QR that changes faster. Shortening the QR alone does not work: a student with a linked phone taps Aceptar about 3 seconds after scanning, but that is after the QR was already checked. When the camera reads the QR, it is already up to 10 seconds old, because it only changes every 10 seconds. Returning students scanned a QR that was 8.4 seconds old (median), almost the same as new students (8.6 s), and with a 5-second QR only 10 of their 63 check-ins would have got in. If the QR changed every 2 or 3 seconds instead, it would always be fresh on the screen, and a shorter life might be possible. That needs a real class to check.
7. Try the unannounced moment, and a second professor.

None of these are built yet; each one will get its own day in this log when it is.
