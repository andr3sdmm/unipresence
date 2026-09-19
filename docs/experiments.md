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

**What I decided:** I decided to ask for the student's private code before showing or requesting their name so the course list is not exposed during registration. I also decided to use English for the repository and technical documentation, while keeping the student-facing interface in Spanish. For the current prototype, teacher access uses a shared password stored outside the repository as an environment variable. A future production version should use Universidad del Norte's institutional login instead.

**Still open:** The timestamps in the exported CSV are still displayed in UTC and need to be converted to the appropriate local time.