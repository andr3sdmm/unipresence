# Threat model — UniPresence

## 1. The attacker

The attacker can be a student who is not physically in the classroom but wants to be marked present. They may have access to a phone, WhatsApp or another messaging app, and a friend who is actually in the classroom.

The attacker could also be any person who obtains the URL of the teacher screen. In the initial version of the system, this attacker did not need to be a student or have someone inside the classroom because the teacher screen did not require authentication. The teacher screen and the related QR endpoint are now protected by the authenticated teacher session.

## 2. What we are trying to prevent

We want to prevent students who are not physically present in class from successfully registering attendance.

## 3. Attacks considered

### Old QR / screenshot

A student could take a screenshot of the QR code and send it to someone who is not in class. The QR changes every 10 seconds and each one is accepted for 20 seconds, so an old photo stops working quickly. I tested it with two phones on October 25, 2026: a photo sent 30 seconds later was rejected with "Vuelve a escanear. Ese QR ya venció." (`attack-protocol.md`, attack 1). If the phone is already linked, the report also says who scanned the expired QR.

### Registering with someone else's code

A student could get another student's code and try to register attendance with it. Before the assigned-code system was added, nothing prevented this because anyone could register using any valid code.

**Version 1.** Each student received a secret code privately on a printed slip. Security depended on keeping that code secret. If an attacker got another student's code before the real owner registered, the attack could still work, but it became noticeable: when the real student tried to register, the code was rejected as already used.

**What the pilot showed.** On September 22, 2026, that same rejection hit 7 honest students. Their registration was stored in a browser cookie; they had registered inside WhatsApp's browser and then checked in from Safari, so the system treated them as new and refused their own code. A rule meant to stop impostors was locking out present students.

**Version 2.** Students bind their phone with their university code, which is not secret. A student who knows a classmate's code can therefore move that classmate's registration to another phone. The system allows this on purpose, but never silently: every device change is recorded, counted on the teacher's screen while class runs, and marked in the export, together with the browser used. The attack is not prevented; it is made visible to the person who can act on it.

### Registering several people from one phone

One student could try to register attendance for several classmates using the same phone. Version 1 prevented this by associating the device with the first registered student. I tested this attack, and the system displayed: "Este teléfono ya está registrado — Andres Marino." In version 2 this cannot happen: a browser the app already knows only marks for its owner, and its check-in page has no field to type another code (`test_known_browser_cannot_mark_for_a_friend`).

### Device binding narrower than a device

Found in the September 22 pilot, not in testing. Binding a student to a "phone" through a cookie actually binds them to one browser on that phone. Messaging apps open links in their own built-in browser, so a single phone can look like several devices. This caused false rejections rather than fraud, but it means the binding is weaker evidence of "same phone" than it appears.

### Live relay over video call

A student outside the classroom could communicate live with a friend inside the classroom and receive the current attendance information before it expires.

This is not only a theory. The professor of the pilots told me that students already send the QR to classmates who are not in class, as a photo on WhatsApp or another messaging app, and that this was the complaint when other professors tried QR attendance. A forwarded photo is the same attack as the old QR above, only faster: if it arrives in less than 20 seconds, it works. I have tested a photo sent after 30 seconds (rejected), but not one forwarded right away.

I tested it on October 25, 2026: a friend in the room points a video call at the projected QR and the student at home scans it from a second device. It worked 5 out of 5 times (`attack-protocol.md`, attack 2).

I expected that a shorter QR would make the relay harder. The data says it does not. The server keeps how old the QR was when each phone opened it. The relayed QRs were 4.6 to 18.4 seconds old; the 218 real check-ins in two large classes were 2.4 to 19.6 seconds old (median 8.5 s). A 15-second QR would still let in 4 of the 5 relays, and would lock out 5 % of the students in the room (`results.md`, relay section).

What makes a relay hard is coordination, not the clock: someone outside has to be on a call, with a second device, at the exact moment the QR is shown. So the defence is procedural. The professor can take attendance at a moment she does not announce, and a student who marks from a phone that belongs to someone else, or in a burst of new phones, shows up under "Por revisar". This makes the relay expensive and visible. It does not make it impossible.

### Unauthenticated teacher screen

The teacher screen originally did not require a password or any other form of authentication. Anyone who had the link could access it, start an attendance session, manually mark students from the course list as present, and download the CSV containing student names and attendance information.

Nothing prevented this attack when it was discovered. I found the vulnerability while writing this threat model rather than through a formal test of the system.

I fixed it the same day by adding password authentication to the teacher screen. The password is stored as an environment variable and is never included in the repository.

While implementing this protection, I discovered a more serious related vulnerability: the `/qr/{session_id}` endpoint was also publicly accessible and returned a valid nonce to anyone who requested it. This meant that a student who had already registered their device could obtain the current nonce remotely and mark themselves present from home, without needing an accomplice in the classroom or access to the projected QR code.

Both the teacher interface and the QR endpoint are now protected by the same authenticated teacher session.

## 4. Alternatives evaluated and rejected

### Bluetooth (BLE) proximity

Bluetooth would give stronger evidence that the phone is in the room, and I had planned it as the next phase. I rejected it after the relay test. Safari on the iPhone does not support Web Bluetooth, and most students in these classes use an iPhone, so it would need an app to install or a beacon to buy. One rule of this project, from the first pilot and from the professor, is that it has to work with nothing to install and nothing to buy. Kim, Lee and Paek (2018) also showed that a real beacon attendance system could be faked with an Arduino, so it would not close the gap either.

### GPS geolocation

GPS was considered as a way to verify that students were physically near the classroom, but it was rejected for three main reasons. First, GPS does not provide enough precision indoors to reliably determine whether a student is actually inside a specific classroom. Second, a student could fake their location using a free location-spoofing app. Third, collecting students' location data, even only at the moment of check-in, would go against the privacy-focused design of the system.

## 5. Open risks

The system still has some risks that it does not completely solve. A live relay works (tested 5 out of 5), and no QR lifetime stops it without locking out present students. It is made visible and expensive, not impossible.

University codes are not secret, so in version 2 a student can move a classmate's registration to their own phone. The system records and displays this instead of preventing it. Detection depends on the teacher looking at the device-change count and the export.

Version 1 used a shared teacher password, which could not identify which teacher performed an action. Version 2 replaces it with individual teacher accounts, so actions can be associated with a specific account. Anyone who knows the optional signup code can still create a teacher account; the signup code is a shared secret. Integrating the university's institutional login would close this gap and is outside the scope of the current prototype.

Version 1 ran on the free Render plan, which put the service to sleep after inactivity and lost stored data during the September 22 pilot. Version 2 stores all data in Postgres, so data survives restarts.
